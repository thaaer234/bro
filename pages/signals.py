import inspect
from decimal import Decimal

from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.db import connection
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import ActivityLog, SystemReport


def table_exists(table_name):
    return table_name in connection.introspection.table_names()


def get_current_request():
    try:
        for frame_record in inspect.stack():
            frame = frame_record[0]
            request = frame.f_locals.get('request')
            if request and hasattr(request, 'user'):
                return request
    except Exception:
        return None
    return None


def get_request_context():
    request = get_current_request()
    if not request:
        return None, None, '', '', {}

    forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    ip_address = forwarded.split(',')[0].strip() if forwarded else request.META.get('REMOTE_ADDR', '')
    extra_data = {
        'query_string': request.META.get('QUERY_STRING', ''),
        'referer': request.META.get('HTTP_REFERER', ''),
    }
    user = getattr(request, 'user', None)
    if not getattr(user, 'is_authenticated', False):
        user = None
    return request, user, ip_address, request.path[:255], extra_data


def normalize_object_id(instance):
    object_id = getattr(instance, 'id', None)
    return object_id if isinstance(object_id, int) else None


@receiver(post_save)
def log_save(sender, instance, created, **kwargs):
    excluded_models = {'ActivityLog', 'LogEntry', 'Session', 'ContentType', 'DailyEmailReportSchedule'}
    if sender.__name__ in excluded_models or not table_exists('pages_activitylog'):
        return

    try:
        request, user, ip_address, path, extra_data = get_request_context()
        if user and user.is_superuser:
            return

        action = 'create' if created else 'update'
        ActivityLog.objects.create(
            user=user,
            action=action,
            content_type=sender.__name__,
            object_id=normalize_object_id(instance),
            object_repr=str(instance)[:200],
            details=f"تم {action} {sender.__name__}: {instance}",
            ip_address=ip_address,
            path=path,
            method=getattr(request, 'method', '')[:10] if request else '',
            extra_data={
                **extra_data,
                'model': sender.__name__,
                'created': created,
                'object_pk': str(getattr(instance, 'pk', '')) if getattr(instance, 'pk', None) is not None else None,
            },
        )
    except Exception as e:
        print(f"Error logging activity: {e}")


@receiver(post_delete)
def log_delete(sender, instance, **kwargs):
    excluded_models = {'ActivityLog', 'LogEntry', 'Session', 'ContentType', 'DailyEmailReportSchedule'}
    if sender.__name__ in excluded_models or not table_exists('pages_activitylog'):
        return

    try:
        request, user, ip_address, path, extra_data = get_request_context()
        if user and user.is_superuser:
            return

        ActivityLog.objects.create(
            user=user,
            action='delete',
            content_type=sender.__name__,
            object_id=normalize_object_id(instance),
            object_repr=str(instance)[:200],
            details=f"تم حذف {sender.__name__}: {instance}",
            ip_address=ip_address,
            path=path,
            method=getattr(request, 'method', '')[:10] if request else '',
            extra_data={
                **extra_data,
                'model': sender.__name__,
                'object_pk': str(getattr(instance, 'pk', '')) if getattr(instance, 'pk', None) is not None else None,
            },
        )
    except Exception as e:
        print(f"Error logging delete activity: {e}")


@receiver(user_logged_in)
def log_login(sender, request, user, **kwargs):
    if not table_exists('pages_activitylog') or user.is_superuser:
        return

    ip_address = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', '')) if request else ''
    ip_address = ip_address.split(',')[0].strip() if ip_address else ''
    ActivityLog.objects.create(
        user=user,
        action='login',
        content_type='User',
        object_id=user.id,
        object_repr=user.username,
        details='تم تسجيل الدخول إلى النظام',
        ip_address=ip_address,
        path=request.path[:255] if request else '',
        method=request.method[:10] if request else '',
        extra_data={
            'session_key': getattr(getattr(request, 'session', None), 'session_key', ''),
            'user_agent': request.META.get('HTTP_USER_AGENT', '') if request else '',
        },
    )


@receiver(user_logged_out)
def log_logout(sender, request, user, **kwargs):
    if not table_exists('pages_activitylog') or not user or user.is_superuser:
        return

    ip_address = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', '')) if request else ''
    ip_address = ip_address.split(',')[0].strip() if ip_address else ''
    ActivityLog.objects.create(
        user=user,
        action='logout',
        content_type='User',
        object_id=user.id,
        object_repr=user.username,
        details='تم تسجيل الخروج من النظام',
        ip_address=ip_address,
        path=request.path[:255] if request else '',
        method=request.method[:10] if request else '',
        extra_data={
            'session_key': getattr(getattr(request, 'session', None), 'session_key', ''),
            'user_agent': request.META.get('HTTP_USER_AGENT', '') if request else '',
        },
    )


def _to_decimal(value):
    if value in (None, ''):
        return Decimal('0')
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal('0')


@receiver(post_save, sender=SystemReport)
def alert_on_report_change(sender, instance, created, **kwargs):
    if not created:
        return

    previous = SystemReport.objects.exclude(pk=instance.pk).order_by('-created_at').first()
    if not previous or not instance.summary or not previous.summary:
        return

    fields = {
        'users_total': ('counts', 'users_total'),
        'students_total': ('counts', 'students_total'),
        'transactions_count': ('transactions', 'count'),
        'debit_total': ('transactions', 'debit_total'),
        'credit_total': ('transactions', 'credit_total'),
    }
    threshold = Decimal('0.20')
    changes = []

    for label, path in fields.items():
        current = instance.summary
        previous_data = previous.summary
        for key in path:
            current = current.get(key, {})
            previous_data = previous_data.get(key, {})
        current_value = _to_decimal(current)
        previous_value = _to_decimal(previous_data)
        if previous_value == 0:
            continue
        change_ratio = (current_value - previous_value).copy_abs() / previous_value
        if change_ratio >= threshold:
            changes.append(f"{label}: {previous_value} -> {current_value}")

    if changes:
        ActivityLog.objects.create(
            user=instance.created_by,
            action='other',
            content_type='SystemReport',
            object_id=instance.id,
            object_repr=str(instance)[:200],
            details='Large change detected in system report. ' + '; '.join(changes),
            extra_data={'changes': changes},
        )
