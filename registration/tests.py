from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase

from .middleware import SingleActiveSessionMiddleware


class FakeSession(dict):
    def __init__(self, session_key):
        super().__init__()
        self.session_key = session_key

    def flush(self):
        self.clear()
        self.session_key = ''


class SingleActiveSessionMiddlewareTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def _user(self, session_key='active-session'):
        return SimpleNamespace(
            is_authenticated=True,
            session_state=SimpleNamespace(session_key=session_key, updated_at=None),
            get_username=lambda: 'session-user',
        )

    def _request(self, path='/pages/', session_key='current-session'):
        request = self.factory.get(path)
        request.session = FakeSession(session_key)
        request.user = self._user()
        return request

    def test_allows_current_active_session(self):
        request = self._request(session_key='active-session')

        response = SingleActiveSessionMiddleware(lambda req: 'ok')(request)

        self.assertEqual(response, 'ok')

    def test_renders_full_page_for_replaced_session(self):
        old_request = self._request(session_key='old-session')
        old_request.user = self._user(session_key='new-session')

        def fake_render(request, template_name, context=None, status=200):
            return HttpResponse('تم إنهاء جلستك', status=status)

        with patch('registration.middleware.logout', lambda request: request.session.flush()), \
                patch('registration.middleware.render', fake_render):
            response = SingleActiveSessionMiddleware(lambda req: 'ok')(old_request)

        self.assertEqual(response.status_code, 440)
        self.assertIn('تم إنهاء جلستك', response.content.decode())

    def test_skips_anonymous_users(self):
        request = self._request()
        request.user = AnonymousUser()

        response = SingleActiveSessionMiddleware(lambda req: 'ok')(request)

        self.assertEqual(response, 'ok')
