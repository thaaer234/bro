from django.contrib.auth import logout
from django.db import OperationalError, ProgrammingError
from django.shortcuts import render


class SingleActiveSessionMiddleware:
    EXCLUDED_PREFIXES = (
        '/login/',
        '/logout/',
        '/static/',
        '/media/',
        '/favicon.ico',
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if self._should_check(request):
            try:
                state = getattr(request.user, 'session_state', None)
                current_key = request.session.session_key or ''
                if state and state.session_key and current_key and state.session_key != current_key:
                    username = request.user.get_username()
                    active_at = state.updated_at
                    logout(request)
                    return render(
                        request,
                        'registration/session_replaced.html',
                        {
                            'username': username,
                            'active_at': active_at,
                        },
                        status=440,
                    )
            except (OperationalError, ProgrammingError):
                pass

        return self.get_response(request)

    def _should_check(self, request):
        user = getattr(request, 'user', None)
        if not user or not user.is_authenticated:
            return False
        return not any(request.path.startswith(prefix) for prefix in self.EXCLUDED_PREFIXES)
