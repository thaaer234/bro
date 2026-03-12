from .services import get_active_announcements_for_user


def web_announcements(request):
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return {"web_announcements": []}
    return {"web_announcements": get_active_announcements_for_user(request.user)}
