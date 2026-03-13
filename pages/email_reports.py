import json
import logging
import smtplib
import time
from datetime import timedelta
from collections import defaultdict

from django.conf import settings
from django.contrib.auth.models import User
from django.core.mail import EmailMultiAlternatives
from django.core.serializers.json import DjangoJSONEncoder
from django.template.loader import render_to_string
from django.utils import timezone

from accounts.models import ExpenseEntry, StudentReceipt
from attendance.models import Attendance, TeacherAttendance
from quick.models import QuickStudentReceipt

from .models import ActivityLog, SystemReport
from .reporting import build_system_report_summary, create_system_report

logger = logging.getLogger(__name__)


ACTION_LABELS = {
    'create': 'إنشاء',
    'update': 'تعديل',
    'delete': 'حذف',
    'login': 'دخول',
    'logout': 'خروج',
    'view': 'عرض',
    'other': 'أخرى',
}


def _resolve_recipients(explicit_recipients=None):
    if explicit_recipients:
        return explicit_recipients
    configured = getattr(settings, 'DAILY_OPERATIONS_REPORT_EMAILS', None)
    if configured:
        return [item.strip() for item in configured if item.strip()]
    fallback = getattr(settings, 'SECURITY_REPORT_EMAILS', [])
    return [item.strip() for item in fallback if item.strip()]


def _from_email():
    return getattr(settings, 'DEFAULT_FROM_EMAIL', getattr(settings, 'EMAIL_HOST_USER', ''))


def _report_limits():
    return {
        'max_users': max(1, int(getattr(settings, 'DAILY_OPERATIONS_EMAIL_MAX_USERS', 12))),
        'max_operations': max(1, int(getattr(settings, 'DAILY_OPERATIONS_EMAIL_MAX_OPERATIONS_PER_USER', 5))),
        'max_receipts': max(1, int(getattr(settings, 'DAILY_OPERATIONS_EMAIL_MAX_RECEIPTS_PER_USER', 5))),
        'attach_json': bool(getattr(settings, 'DAILY_OPERATIONS_EMAIL_ATTACH_JSON', False)),
        'include_html': bool(getattr(settings, 'DAILY_OPERATIONS_EMAIL_INCLUDE_HTML', True)),
    }


def _format_dt(value):
    if not value:
        return ''
    return timezone.localtime(value).strftime('%Y-%m-%d %H:%M')


def _format_time(value):
    if not value:
        return ''
    return timezone.localtime(value).strftime('%H:%M')


def _send_email_with_retries(email_message, attempts=3, delay_seconds=3):
    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            email_message.connection = None
            return email_message.send(fail_silently=False)
        except (smtplib.SMTPException, OSError) as exc:
            last_error = exc
            logger.warning(
                'Daily operations report email send attempt %s/%s failed: %s',
                attempt,
                attempts,
                exc,
            )
            if attempt < attempts:
                time.sleep(delay_seconds)
    raise last_error


def _build_period(day):
    tz = timezone.get_current_timezone()
    start = timezone.make_aware(timezone.datetime.combine(day, timezone.datetime.min.time()), tz)
    end = start + timedelta(days=1)
    return start, end


def build_daily_operations_payload(day=None, report=None):
    day = day or timezone.localdate()
    limits = _report_limits()
    start_dt, end_dt = _build_period(day)
    if report is None:
        report = create_system_report(
            period_start=day,
            period_end=day,
            report_type='manual',
        )
    summary = report.summary or build_system_report_summary(day, day)

    activity_qs = (
        ActivityLog.objects
        .filter(timestamp__gte=start_dt, timestamp__lt=end_dt, user__isnull=False)
        .select_related('user')
        .order_by('timestamp')
    )
    logs_by_user = defaultdict(list)
    attendance_ids_by_user = defaultdict(list)
    teacher_attendance_ids_by_user = defaultdict(list)
    for log in activity_qs:
        logs_by_user[log.user_id].append(log)
        if log.action == 'create' and log.content_type == 'Attendance' and log.object_id:
            attendance_ids_by_user[log.user_id].append(log.object_id)
        if log.action == 'create' and log.content_type == 'TeacherAttendance' and log.object_id:
            teacher_attendance_ids_by_user[log.user_id].append(log.object_id)

    attendance_map = {}
    for row in Attendance.objects.filter(id__in={pk for values in attendance_ids_by_user.values() for pk in values}).select_related('classroom', 'student'):
        attendance_map[row.id] = row

    teacher_attendance_map = {}
    for row in TeacherAttendance.objects.filter(id__in={pk for values in teacher_attendance_ids_by_user.values() for pk in values}).select_related('teacher'):
        teacher_attendance_map[row.id] = row

    regular_receipt_rows = (
        StudentReceipt.objects
        .filter(date=day)
        .select_related('created_by', 'course', 'student_profile', 'student')
        .order_by('created_by_id', 'id')
    )
    quick_receipt_rows = (
        QuickStudentReceipt.objects
        .filter(date=day)
        .select_related('created_by', 'course', 'quick_student')
        .order_by('created_by_id', 'id')
    )
    expense_rows = (
        ExpenseEntry.objects
        .filter(date=day)
        .select_related('created_by')
        .order_by('created_by_id', 'id')
    )

    regular_receipts_by_user = defaultdict(list)
    for receipt in regular_receipt_rows:
        if receipt.created_by_id:
            regular_receipts_by_user[receipt.created_by_id].append({
                'course_name': getattr(receipt.course, 'name_ar', None) or getattr(receipt.course, 'name', 'غير محدد'),
                'student_name': getattr(receipt.student_profile, 'full_name', None) or getattr(receipt.student, 'full_name', None) or 'غير محدد',
                'amount': str(receipt.paid_amount),
                'receipt_number': getattr(receipt, 'receipt_number', '') or '',
            })

    quick_receipts_by_user = defaultdict(list)
    for receipt in quick_receipt_rows:
        if receipt.created_by_id:
            quick_receipts_by_user[receipt.created_by_id].append({
                'course_name': getattr(receipt.course, 'name_ar', None) or getattr(receipt.course, 'name', 'غير محدد'),
                'student_name': getattr(receipt.quick_student, 'full_name', None) or getattr(receipt, 'student_name', '') or 'غير محدد',
                'amount': str(receipt.paid_amount),
                'receipt_number': getattr(receipt, 'receipt_number', '') or '',
            })

    expenses_by_user = defaultdict(list)
    for expense in expense_rows:
        if expense.created_by_id:
            expenses_by_user[expense.created_by_id].append({
                'description': expense.description,
                'category': getattr(expense, 'category', ''),
                'amount': str(expense.amount),
            })

    summary_users = {
        row.get('user_id'): row
        for row in summary.get('details', {}).get('users', [])
        if row.get('user_id')
    }
    user_map = User.objects.in_bulk(summary_users.keys())
    user_details = []

    for user_id, user_summary in sorted(summary_users.items(), key=lambda item: item[1].get('activity_total', 0), reverse=True):
        logs = logs_by_user.get(user_id, [])
        user = logs[0].user if logs else user_map.get(user_id)
        if not user:
            continue
        login_times = [_format_time(log.timestamp) for log in logs if log.action == 'login']
        logout_times = [_format_time(log.timestamp) for log in logs if log.action == 'logout']

        student_attendance_summary = defaultdict(int)
        for attendance_id in attendance_ids_by_user.get(user_id, []):
            attendance = attendance_map.get(attendance_id)
            if attendance and attendance.classroom_id:
                student_attendance_summary[str(attendance.classroom)] += 1

        teacher_attendance_summary = []
        for attendance_id in teacher_attendance_ids_by_user.get(user_id, []):
            attendance = teacher_attendance_map.get(attendance_id)
            if attendance:
                teacher_attendance_summary.append({
                    'teacher_name': attendance.teacher.full_name,
                    'branch': attendance.branch,
                    'sessions': str(attendance.total_sessions),
                })

        employee = getattr(user, 'employee_profile', None)
        cash_account = employee.get_cash_account() if employee else None
        cash_box = None
        if cash_account:
            cash_box = {
                'code': cash_account.code,
                'name': cash_account.display_name,
                'balance': str(cash_account.get_net_balance()),
            }

        operations = []
        for log in logs:
            if log.action in {'login', 'logout'}:
                continue
            operations.append({
                'time': _format_dt(log.timestamp),
                'action': ACTION_LABELS.get(log.action, log.action),
                'content_type': log.content_type,
                'object_repr': log.object_repr,
                'details': log.details,
                'path': log.path,
                'ip_address': log.ip_address or '',
            })
            if len(operations) >= limits['max_operations']:
                break

        user_details.append({
            'user_id': user_id,
            'full_name': user_summary.get('full_name') or user.get_full_name() or user.get_username(),
            'username': user_summary.get('username') or user.get_username(),
            'permissions': user_summary.get('permissions', []),
            'logins': login_times,
            'logouts': logout_times,
            'activity_total': user_summary.get('activity_total', 0),
            'active_time_label': user_summary.get('active_time_label', ''),
            'receipts_students_count': user_summary.get('receipts_students_count', 0),
            'receipts_students_amount': user_summary.get('receipts_students_amount', '0'),
            'receipts_quick_count': user_summary.get('receipts_quick_count', 0),
            'receipts_quick_amount': user_summary.get('receipts_quick_amount', '0'),
            'expenses_count': user_summary.get('expenses_count', 0),
            'expenses_amount': user_summary.get('expenses_amount', '0'),
            'attendance_students_count': user_summary.get('attendance_students_count', 0),
            'attendance_classrooms_count': len(student_attendance_summary),
            'attendance_teachers_count': user_summary.get('attendance_teachers_count', 0),
            'teacher_sessions_count': user_summary.get('teacher_sessions_count', '0'),
            'net_balance': user_summary.get('net_balance', '0'),
            'cash_box': cash_box,
            'student_attendance_summary': [
                {'classroom_name': name, 'records_count': count}
                for name, count in sorted(student_attendance_summary.items())
            ],
            'teacher_attendance_summary': teacher_attendance_summary,
            'regular_receipts': regular_receipts_by_user.get(user_id, [])[:limits['max_receipts']],
            'quick_receipts': quick_receipts_by_user.get(user_id, [])[:limits['max_receipts']],
            'expenses': expenses_by_user.get(user_id, [])[:limits['max_receipts']],
            'operations': operations,
        })

    user_details = user_details[:limits['max_users']]

    return {
        'date': day,
        'generated_at': timezone.now(),
        'report_id': report.pk,
        'summary': summary,
        'users': user_details,
        'email_limits': limits,
    }


def send_daily_operations_report(day=None, requested_by=None, recipients=None, report_type='manual'):
    day = day or timezone.localdate()
    limits = _report_limits()
    summary = build_system_report_summary(
        period_start=day,
        period_end=day,
        use_cache=False,
    )
    report = SystemReport.objects.create(
        created_by=requested_by,
        period_start=day,
        period_end=day,
        report_type=report_type,
        summary=summary,
    )
    payload = build_daily_operations_payload(day=day, report=report)
    recipient_list = _resolve_recipients(recipients)
    if not recipient_list:
        return {'sent': False, 'report_id': report.pk, 'recipients': []}

    context = {
        'date': day,
        'generated_at': payload['generated_at'],
        'report': report,
        'summary': payload['summary'],
        'users': payload['users'],
        'email_limits': limits,
    }
    subject = f"التقرير اليومي لعمليات المستخدمين - {day}"
    body = render_to_string('pages/emails/daily_operations_report.txt', context)
    email = EmailMultiAlternatives(
        subject=subject,
        body=body,
        to=recipient_list,
        from_email=_from_email(),
    )
    if limits['include_html']:
        html_body = render_to_string('pages/emails/daily_operations_report.html', context)
        email.attach_alternative(html_body, 'text/html')
    if limits['attach_json']:
        email.attach(
            filename=f'daily-operations-report-{day}.json',
            content=json.dumps(payload, cls=DjangoJSONEncoder, ensure_ascii=False, indent=2),
            mimetype='application/json',
        )
    try:
        _send_email_with_retries(email)
    except Exception as exc:
        logger.exception('Failed to send daily operations report email.')
        return {
            'sent': False,
            'report_id': report.pk,
            'recipients': recipient_list,
            'error': str(exc),
        }
    return {'sent': True, 'report_id': report.pk, 'recipients': recipient_list}
