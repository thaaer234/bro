import json
import logging
from collections import Counter
from datetime import datetime, time, timedelta
from urllib.parse import urljoin

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.core.serializers.json import DjangoJSONEncoder
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from .models import BiometricLog, EmployeeAttendance

logger = logging.getLogger(__name__)


PUNCH_LABELS = {
    'check_in': 'دخول',
    'check_out': 'خروج',
    'break_out': 'خروج استراحة',
    'break_in': 'عودة من الاستراحة',
    'unknown': 'بصمة',
}


def _recipient_emails():
    configured = getattr(settings, 'BIOMETRIC_ATTENDANCE_EMAILS', None)
    if configured:
        return list(dict.fromkeys(email.strip() for email in configured if email and email.strip()))

    fallback = []
    for source in (
        getattr(settings, 'SECURITY_ALERT_EMAILS', []),
        getattr(settings, 'PASSWORD_RESET_APPROVAL_EMAILS', []),
        [getattr(settings, 'EMAIL_HOST_USER', '')],
    ):
        fallback.extend(source)
    return list(dict.fromkeys(email.strip() for email in fallback if email and email.strip()))


def _from_email():
    sender_name = getattr(settings, 'BIOMETRIC_EMAIL_SENDER_NAME', 'نظام بصمة الموظفين')
    host_user = getattr(settings, 'EMAIL_HOST_USER', '')
    if host_user:
        return f'{sender_name} <{host_user}>'
    return getattr(settings, 'DEFAULT_FROM_EMAIL', sender_name)


def _format_local_dt(value):
    if not value:
        return '-'
    text = timezone.localtime(value).strftime('%Y-%m-%d %I:%M %p')
    return text.replace('AM', 'ص').replace('PM', 'م')


def _format_time(value):
    if not value:
        return '-'
    text = timezone.localtime(value).strftime('%I:%M %p')
    return text.replace('AM', 'ص').replace('PM', 'م')


def _format_duration(seconds):
    seconds = int(seconds or 0)
    hours, remainder = divmod(seconds, 3600)
    minutes = remainder // 60
    if hours and minutes:
        return f'{hours} ساعة و {minutes} دقيقة'
    if hours:
        return f'{hours} ساعة'
    return f'{minutes} دقيقة'


def _send_template_email(subject, text_template, html_template, context, attachment=None):
    recipients = _recipient_emails()
    if not recipients:
        logger.warning('No biometric attendance email recipients configured.')
        return 0

    subject_prefix = getattr(settings, 'EMAIL_SUBJECT_PREFIX', '')
    if subject_prefix and not subject.startswith(subject_prefix):
        subject = f'{subject_prefix}{subject}'

    try:
        body = render_to_string(text_template, context)
        html_body = render_to_string(html_template, context)
        email = EmailMultiAlternatives(
            subject=subject,
            body=body,
            to=recipients,
            from_email=_from_email(),
            reply_to=[settings.DEFAULT_FROM_EMAIL] if getattr(settings, 'DEFAULT_FROM_EMAIL', None) else None,
        )
        email.attach_alternative(html_body, 'text/html')
        if attachment:
            email.attach(**attachment)
        return email.send(fail_silently=False)
    except Exception:
        logger.exception('Failed to send biometric attendance email.')
        return 0


def _employee_name(employee, device_user_id=''):
    if employee:
        return employee.full_name
    return f'غير مربوط ({device_user_id})'


def _same_minute(left, right):
    if not left or not right:
        return False
    return abs((left - right).total_seconds()) < 60


def _review_status_label(value):
    labels = {
        'not_required': 'لا تحتاج مراجعة',
        'pending': 'بانتظار القرار',
        'justified': 'مسامحة',
        'unjustified': 'محاسبة',
    }
    return labels.get(value, value or '-')


def _attendance_for_log(log):
    if not log.employee_id:
        return None
    target_date = timezone.localtime(log.punch_time).date()
    return (
        EmployeeAttendance.objects
        .filter(employee=log.employee, date=target_date)
        .select_related('employee__user', 'employee__default_shift')
        .first()
    )


def _shift_bounds_for_attendance(attendance):
    shift = attendance.employee.effective_shift if attendance and attendance.employee_id else None
    if not shift:
        return None, None
    try:
        return shift.get_bounds_for_date(attendance.date)
    except Exception:
        logger.debug('Unable to resolve shift bounds for attendance %s', attendance.pk, exc_info=True)
        return None, None


def _base_url():
    value = (
        getattr(settings, 'BIOMETRIC_DECISION_BASE_URL', '')
        or getattr(settings, 'SITE_URL', '')
        or getattr(settings, 'PASSWORD_RESET_BASE_URL', '')
        or 'http://127.0.0.1:8000'
    )
    return value.rstrip('/') + '/'


def _absolute_url(path):
    return urljoin(_base_url(), path.lstrip('/'))


def _decision_links(attendance):
    if not attendance:
        return {}

    def link(action):
        path = reverse('employ:attendance_email_decision', kwargs={'pk': attendance.pk, 'action': action})
        return _absolute_url(path)

    links = {}
    if attendance.late_seconds or attendance.early_leave_seconds:
        links['forgive'] = link('forgive')
        links['charge'] = link('charge')
    if attendance.overtime_seconds:
        links['count_overtime'] = link('count_overtime')
        links['deny_overtime'] = link('deny_overtime')
    return links


def _status_for_attendance(attendance):
    if not attendance:
        return 'تم تسجيل البصمة', '#17324d'

    has_late = attendance.late_seconds > 0
    has_early = attendance.early_leave_seconds > 0
    has_overtime = attendance.overtime_seconds > 0

    if has_overtime and has_late and has_early:
        return (
            f'إضافي مع دخول متأخر وخروج مبكر: إضافي {_format_duration(attendance.overtime_seconds)}، '
            f'تأخير {_format_duration(attendance.late_seconds)}، خروج مبكر {_format_duration(attendance.early_leave_seconds)}'
        ), '#7c3aed'
    if has_overtime and has_late:
        return f'إضافي مع دخول متأخر: إضافي {_format_duration(attendance.overtime_seconds)} وتأخير {_format_duration(attendance.late_seconds)}', '#7c3aed'
    if has_overtime and has_early:
        return f'إضافي مع خروج مبكر: إضافي {_format_duration(attendance.overtime_seconds)} وخروج مبكر {_format_duration(attendance.early_leave_seconds)}', '#7c3aed'
    if has_overtime:
        return f'إضافي دخول نظامي: {_format_duration(attendance.overtime_seconds)}', '#047857'
    if has_late and has_early:
        return f'دخل متأخر وخرج مبكراً: تأخير {_format_duration(attendance.late_seconds)} وخروج مبكر {_format_duration(attendance.early_leave_seconds)}', '#b42318'
    if has_late:
        return f'تأخير بمقدار {_format_duration(attendance.late_seconds)}', '#b54708'
    if has_early:
        return f'خروج مبكر بمقدار {_format_duration(attendance.early_leave_seconds)}', '#b54708'
    if attendance.status == 'present':
        return 'دوام طبيعي', '#047857'
    status_labels = {
        'partial': 'دوام جزئي',
        'absent': 'غائب',
        'vacation': 'إجازة',
        'weekend': 'عطلة',
    }
    return status_labels.get(attendance.status, attendance.status or 'تم تسجيل البصمة'), '#17324d'


def _punch_context(log):
    attendance = _attendance_for_log(log)
    employee_name = _employee_name(log.employee, log.device_user_id)
    punch_label = PUNCH_LABELS.get(log.punch_type, PUNCH_LABELS['unknown'])
    shift_start, shift_end = _shift_bounds_for_attendance(attendance)
    status_label, status_color = _status_for_attendance(attendance)

    is_check_in_event = bool(attendance and _same_minute(log.punch_time, attendance.check_in))
    is_check_out_event = bool(attendance and _same_minute(log.punch_time, attendance.check_out))
    is_late = bool(attendance and attendance.late_seconds > 0 and attendance.status != 'vacation')
    is_early_leave = bool(attendance and attendance.early_leave_seconds > 0 and attendance.status != 'vacation')
    has_overtime = bool(attendance and attendance.overtime_seconds > 0)

    title = f'{employee_name} - {status_label}'
    summary_line = f'{employee_name}: {status_label}.'
    if attendance:
        summary_line += f' العمل الفعلي {_format_duration(attendance.worked_seconds)}'
        if attendance.employee.effective_shift:
            summary_line += f' من أصل {_format_duration(attendance.employee.effective_shift.required_work_seconds)} حسب الشفت.'
        else:
            summary_line += '.'

    metric_rows = [
        {'label': 'الموظف', 'value': employee_name},
        {'label': 'الحالة', 'value': status_label},
        {'label': 'البصمة', 'value': f'{punch_label} - {_format_local_dt(log.punch_time)}'},
    ]

    if attendance:
        shift_name = attendance.employee.effective_shift.name if attendance.employee.effective_shift else 'بدون شفت'
        metric_rows.extend([
            {'label': 'الشفت', 'value': shift_name},
            {'label': 'وقت الدوام', 'value': f'{_format_time(shift_start)} - {_format_time(shift_end)}' if shift_start or shift_end else '-'},
            {'label': 'ساعات الشفت', 'value': _format_duration(attendance.employee.effective_shift.required_work_seconds) if attendance.employee.effective_shift else '-'},
            {'label': 'ساعات العمل الفعلي', 'value': _format_duration(attendance.worked_seconds)},
            {'label': 'قرار السجل', 'value': _review_status_label(attendance.review_status)},
        ])
        if attendance.late_seconds:
            metric_rows.append({'label': 'التأخير', 'value': _format_duration(attendance.late_seconds)})
        if attendance.early_leave_seconds:
            metric_rows.append({'label': 'الخروج المبكر', 'value': _format_duration(attendance.early_leave_seconds)})
        if attendance.overtime_seconds:
            metric_rows.append({'label': 'الإضافي', 'value': _format_duration(attendance.overtime_seconds)})

    return {
        'attendance': attendance,
        'employee_name': employee_name,
        'punch_label': punch_label,
        'title': title,
        'status_label': status_label,
        'status_color': status_color,
        'summary_line': summary_line,
        'metric_rows': metric_rows,
        'decision_links': _decision_links(attendance),
        'is_late': is_late,
        'is_early_leave': is_early_leave,
        'has_overtime': has_overtime,
        'is_check_in_event': is_check_in_event,
        'is_check_out_event': is_check_out_event,
    }


def send_biometric_punch_email(log):
    punch_context = _punch_context(log)
    context = {
        'brand_name': getattr(settings, 'BIOMETRIC_EMAIL_BRAND_NAME', 'معهد اليمان'),
        'brand_short': getattr(settings, 'BIOMETRIC_EMAIL_BRAND_SHORT', 'دوام الموظفين'),
        'punch_time': _format_local_dt(log.punch_time),
        'device_user_id': log.device_user_id,
        'log': log,
        **punch_context,
    }
    return _send_template_email(
        subject=context['title'],
        text_template='employ/emails/biometric_punch_email.txt',
        html_template='employ/emails/biometric_punch_email.html',
        context=context,
    )


def build_biometric_summary(start_date, end_date, label='ملخص البصمات'):
    start_dt = timezone.make_aware(datetime.combine(start_date, time.min))
    end_dt = timezone.make_aware(datetime.combine(end_date + timedelta(days=1), time.min))

    logs = list(
        BiometricLog.objects.filter(
            punch_time__gte=start_dt,
            punch_time__lt=end_dt,
        ).select_related('employee__user', 'device').order_by('punch_time')
    )
    attendances = list(
        EmployeeAttendance.objects.filter(
            date__gte=start_date,
            date__lte=end_date,
        ).select_related('employee__user').order_by('date', 'employee__user__first_name', 'employee__user__last_name')
    )

    late_rows = [row for row in attendances if row.late_seconds or row.early_leave_seconds]
    overtime_rows = [row for row in attendances if row.overtime_seconds]
    absent_rows = [row for row in attendances if row.status == 'absent']

    by_type = Counter(log.punch_type for log in logs)
    by_day = Counter(timezone.localtime(log.punch_time).date() for log in logs)
    total_late_seconds = sum(row.late_seconds for row in late_rows)
    total_early_leave_seconds = sum(row.early_leave_seconds for row in late_rows)
    total_overtime_seconds = sum(row.overtime_seconds for row in overtime_rows)

    log_rows = [
        {
            'time': _format_local_dt(log.punch_time),
            'employee': _employee_name(log.employee, log.device_user_id),
            'type': PUNCH_LABELS.get(log.punch_type, PUNCH_LABELS['unknown']),
            'device': log.device.name if log.device_id else '-',
            'device_user_id': log.device_user_id,
        }
        for log in logs[:150]
    ]

    late_details = [
        {
            'date': row.date,
            'employee': row.employee.full_name,
            'late': _format_duration(row.late_seconds) if row.late_seconds else '',
            'early_leave': _format_duration(row.early_leave_seconds) if row.early_leave_seconds else '',
            'review_status': _review_status_label(row.review_status),
        }
        for row in late_rows
    ]
    overtime_details = [
        {
            'date': row.date,
            'employee': row.employee.full_name,
            'overtime': _format_duration(row.overtime_seconds),
        }
        for row in overtime_rows
    ]

    return {
        'label': label,
        'start_date': start_date,
        'end_date': end_date,
        'generated_at': timezone.localtime(),
        'logs_count': len(logs),
        'attendance_count': len(attendances),
        'late_count': len(late_rows),
        'overtime_count': len(overtime_rows),
        'absent_count': len(absent_rows),
        'by_type': {PUNCH_LABELS.get(key, key): value for key, value in by_type.items()},
        'by_day': [{'date': key, 'total': by_day[key]} for key in sorted(by_day)],
        'logs': log_rows,
        'hidden_logs_count': max(0, len(logs) - len(log_rows)),
        'late_details': late_details,
        'overtime_details': overtime_details,
        'total_late_seconds': total_late_seconds,
        'total_early_leave_seconds': total_early_leave_seconds,
        'total_overtime_seconds': total_overtime_seconds,
        'total_late_display': _format_duration(total_late_seconds),
        'total_early_leave_display': _format_duration(total_early_leave_seconds),
        'total_overtime_display': _format_duration(total_overtime_seconds),
    }


def send_biometric_summary(start_date, end_date, label='ملخص البصمات', filename_prefix='biometric-summary'):
    report = build_biometric_summary(start_date, end_date, label=label)
    context = {
        'brand_name': getattr(settings, 'BIOMETRIC_EMAIL_BRAND_NAME', 'معهد اليمان'),
        'brand_short': getattr(settings, 'BIOMETRIC_EMAIL_BRAND_SHORT', 'دوام الموظفين'),
        'report': report,
    }
    attachment = {
        'filename': f'{filename_prefix}-{start_date:%Y-%m-%d}-to-{end_date:%Y-%m-%d}.json',
        'content': json.dumps(report, cls=DjangoJSONEncoder, ensure_ascii=False, indent=2),
        'mimetype': 'application/json',
    }
    sent = _send_template_email(
        subject=f'{label} - {start_date:%Y-%m-%d} إلى {end_date:%Y-%m-%d}',
        text_template='employ/emails/biometric_summary_email.txt',
        html_template='employ/emails/biometric_summary_email.html',
        context=context,
        attachment=attachment,
    )
    return sent, report


def send_daily_biometric_summary(target_date=None):
    target_date = target_date or timezone.localdate()
    sent, _report = send_biometric_summary(
        target_date,
        target_date,
        label='ملخص بصمات اليوم',
        filename_prefix='biometric-daily-summary',
    )
    return sent


def send_weekly_biometric_summary(reference_date=None):
    reference_date = reference_date or timezone.localdate()
    start_date = reference_date - timedelta(days=6)
    return send_biometric_summary(
        start_date,
        reference_date,
        label='ملخص بصمات الأسبوع',
        filename_prefix='biometric-weekly-summary',
    )
