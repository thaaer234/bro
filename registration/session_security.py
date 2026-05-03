from django.db import OperationalError, ProgrammingError

from .models import UserSessionState


def get_client_ip(request):
    forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded_for:
        return forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR') or None


def mark_active_session(request, user):
    if not request.session.session_key:
        request.session.save()

    try:
        UserSessionState.objects.update_or_create(
            user=user,
            defaults={
                'session_key': request.session.session_key or '',
                'ip_address': get_client_ip(request),
                'user_agent': request.META.get('HTTP_USER_AGENT', '')[:2000],
            },
        )
    except (OperationalError, ProgrammingError):
        pass
