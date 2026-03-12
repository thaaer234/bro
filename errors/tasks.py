try:
    from celery import shared_task
except Exception:
    def shared_task(*args, **kwargs):
        def decorator(func):
            return func
        return decorator

from .security import send_daily_report


@shared_task

def send_daily_security_report_task(date_string=None):
    from django.utils import timezone
    day = timezone.datetime.fromisoformat(date_string).date() if date_string else None
    return send_daily_report(day=day)
