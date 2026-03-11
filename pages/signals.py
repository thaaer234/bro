from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.core.exceptions import ObjectDoesNotExist
from decimal import Decimal
from .models import ActivityLog, SystemReport
import inspect
from django.db import connection

def table_exists(table_name):
    """يتأكد إذا الجدول موجود فعلاً بالـ DB"""
    return table_name in connection.introspection.table_names()

def get_current_user():
    """الحصول على المستخدم الحالي"""
    try:
        for frame_record in inspect.stack():
            frame = frame_record[0]
            request = frame.f_locals.get('request')
            if request and hasattr(request, 'user'):
                return request.user
    except:
        pass
    return None

@receiver(post_save)
def log_save(sender, instance, created, **kwargs):
    excluded_models = ['ActivityLog', 'LogEntry', 'Session', 'ContentType']
    if sender.__name__ in excluded_models:
        return
    
    # 🛑 وقف التنفيذ إذا جدول ActivityLog لسا ما انبنى
    if not table_exists('pages_activitylog'):
        return

    try:
        user = get_current_user()
        if user and user.is_superuser:
            return

        action = 'create' if created else 'update'
        ActivityLog.objects.create(
            user=user,
            action=action,
            content_type=sender.__name__,
            object_id=instance.id,
            object_repr=str(instance)[:200],
            details=f"تم {action} {sender.__name__}: {instance}"
        )
    except Exception as e:
        print(f"Error logging activity: {e}")

@receiver(post_delete)
def log_delete(sender, instance, **kwargs):
    excluded_models = ['ActivityLog', 'LogEntry', 'Session', 'ContentType']
    if sender.__name__ in excluded_models:
        return

    if not table_exists('pages_activitylog'):
        return
    
    try:
        user = get_current_user()
        if user and user.is_superuser:
            return

        ActivityLog.objects.create(
            user=user,
            action='delete',
            content_type=sender.__name__,
            object_id=instance.id,
            object_repr=str(instance)[:200],
            details=f"تم حذف {sender.__name__}: {instance}"
        )
    except Exception as e:
        print(f"Error logging delete activity: {e}")

@receiver(user_logged_in)
def log_login(sender, request, user, **kwargs):
    if not table_exists('pages_activitylog'):
        return

    if user.is_superuser:
        return

    ActivityLog.objects.create(
        user=user,
        action='login',
        content_type='User',
        object_id=user.id,
        object_repr=user.username,
        details="تم تسجيل الدخول إلى النظام"
    )

@receiver(user_logged_out)
def log_logout(sender, request, user, **kwargs):
    if not table_exists('pages_activitylog'):
        return

    if user.is_superuser:
        return

    ActivityLog.objects.create(
        user=user,
        action='logout',
        content_type='User',
        object_id=user.id,
        object_repr=user.username,
        details="تم تسجيل الخروج من النظام"
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
            details="Large change detected in system report. " + "; ".join(changes),
        )
