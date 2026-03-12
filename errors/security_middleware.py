import re
import time

from django.core.cache import cache
from django.http import HttpResponseForbidden

from .security import alternative_capture, build_fingerprint, get_client_ip, match_active_blocks, get_monitoring_settings

SUSPICIOUS_PATTERNS = [
    r'union\s+select',
    r'<script',
    r'\.\./',
    r'cmd\.exe',
    r'/etc/passwd',
]
ADMIN_PROBE_PATTERNS = ['/admin/', '/wp-admin/', '/phpmyadmin/', '/manager/', '/backend/']


class SecurityIntelligenceMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start = time.time()
        fingerprint_hash = build_fingerprint(request)
        ip_address = get_client_ip(request)
        request.security_fingerprint_hash = fingerprint_hash
        rules = match_active_blocks(ip_address=ip_address, fingerprint_hash=fingerprint_hash, user=getattr(request, 'user', None))
        if rules:
            incident = alternative_capture(
                request,
                reason='blocked_request',
                extra_context={
                    'title': 'Blocked request matched active security rule',
                    'summary': ', '.join(f'{r.target_type}:{r.value}' for r in rules),
                    'blocked': True,
                },
            )
            return HttpResponseForbidden('Access denied by security policy.')

        response = self.get_response(request)
        request.security_response_ms = round((time.time() - start) * 1000, 2)

        reason, extra = self.inspect_request(request, response)
        if reason:
            alternative_capture(request, reason=reason, response=response, extra_context=extra)
        return response

    def inspect_request(self, request, response):
        raw = ' '.join([
            request.path,
            str(request.GET),
            str(request.POST),
            request.META.get('HTTP_USER_AGENT', ''),
        ]).lower()

        ua = request.META.get('HTTP_USER_AGENT', '')
        for marker in ('sqlmap', 'nikto', 'nmap', 'acunetix', 'wpscan', 'masscan'):
            if marker in ua.lower():
                return 'suspicious_request', {
                    'title': f'Known offensive tool detected: {marker}',
                    'summary': f'User-Agent matched {marker}',
                }

        if any(request.path.lower().startswith(p) for p in ADMIN_PROBE_PATTERNS) and response.status_code in {403, 404}:
            return 'admin_probe', {
                'title': 'Unauthorized admin path probe',
                'summary': f'Attempted path {request.path}',
            }

        for pattern in SUSPICIOUS_PATTERNS:
            if re.search(pattern, raw, re.IGNORECASE):
                return 'suspicious_request', {
                    'title': 'Suspicious request payload detected',
                    'summary': f'Pattern matched: {pattern}',
                }

        login_paths = ['/login/', '/accounts/login/']
        if any(request.path.startswith(path) for path in login_paths) and request.method == 'POST':
            key = f"security:login:{get_client_ip(request)}"
            window = get_monitoring_settings()['BRUTE_FORCE_WINDOW_SECONDS']
            attempts = cache.get(key, 0) + 1
            cache.set(key, attempts, timeout=window)
            if attempts >= get_monitoring_settings()['BRUTE_FORCE_THRESHOLD']:
                return 'brute_force', {
                    'title': 'Repeated failed or risky login traffic',
                    'summary': f'Login attempts reached {attempts} within {window} seconds',
                }

        return None, None
