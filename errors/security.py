import hashlib
import json
import logging
import base64
import binascii
import io
import uuid
from collections import Counter
from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.core.files.base import ContentFile
from django.core.mail import EmailMultiAlternatives
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Count
from django.template.loader import render_to_string
from django.utils import timezone

from .models import SecurityArtifact, SecurityBlocklist, SecurityBranding, SecurityEvent, SecurityIncident, UserTracking

logger = logging.getLogger(__name__)

try:
    from PIL import Image
except Exception:  # pragma: no cover
    Image = None

if Image and hasattr(Image, 'Resampling'):
    RESAMPLING_LANCZOS = Image.Resampling.LANCZOS
else:  # pragma: no cover
    RESAMPLING_LANCZOS = Image.LANCZOS if Image else None

KNOWN_ATTACK_TOOLS = {
    'sqlmap': 'sqlmap',
    'nikto': 'nikto',
    'nmap': 'nmap',
    'acunetix': 'acunetix',
    'wpscan': 'wpscan',
    'masscan': 'masscan',
}


def build_email_context(extra=None):
    branding = SecurityBranding.objects.order_by('-updated_at').first()
    context = {
        'brand_name': branding.brand_name if branding else getattr(settings, 'SECURITY_BRAND_NAME', 'Security Center'),
        'brand_short': branding.brand_short if branding else getattr(settings, 'SECURITY_BRAND_SHORT', 'Security'),
        'support_email': branding.support_email if branding else getattr(settings, 'SECURITY_SUPPORT_EMAIL', ''),
        'dashboard_url': branding.dashboard_url if branding else getattr(settings, 'SECURITY_DASHBOARD_URL', ''),
        'logo_url': branding.logo_url if branding else getattr(settings, 'SECURITY_LOGO_URL', ''),
        'subject_prefix': branding.subject_prefix if branding else getattr(settings, 'EMAIL_SUBJECT_PREFIX', ''),
        'sender_name': branding.sender_name if branding else getattr(settings, 'SECURITY_BRAND_NAME', 'Security Center'),
    }
    if extra:
        context.update(extra)
    return context


def get_from_email():
    branding = SecurityBranding.objects.order_by('-updated_at').first()
    sender_name = branding.sender_name if branding else getattr(settings, 'SECURITY_BRAND_NAME', 'Security Center')
    host_user = getattr(settings, 'EMAIL_HOST_USER', '')
    if host_user:
        return f"{sender_name} <{host_user}>"
    return getattr(settings, 'DEFAULT_FROM_EMAIL', sender_name)


def get_monitoring_settings():
    defaults = {
        'ENABLED': True,
        'ALERT_EMAILS': [],
        'DAILY_REPORT_EMAILS': [],
        'MAX_HTML_CAPTURE': 20000,
        'MAX_BODY_CAPTURE': 2000,
        'BRUTE_FORCE_WINDOW_SECONDS': 900,
        'BRUTE_FORCE_THRESHOLD': 8,
        'REPORT_INCLUDE_ARTIFACTS': True,
    }
    configured = getattr(settings, 'SECURITY_MONITORING', {})
    merged = defaults.copy()
    merged.update(configured)
    return merged


def get_client_ip(request):
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def build_fingerprint(request, client_telemetry=None):
    parts = [
        get_client_ip(request) or '',
        request.META.get('HTTP_USER_AGENT', ''),
        request.META.get('HTTP_ACCEPT_LANGUAGE', ''),
    ]
    if client_telemetry:
        parts.extend([
            str(client_telemetry.get('screen', '')),
            str(client_telemetry.get('timezone', '')),
            str(client_telemetry.get('platform', '')),
            str(client_telemetry.get('touchPoints', '')),
            str(client_telemetry.get('clientId', '')),
        ])
    raw = '|'.join(parts)
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


def sanitize_mapping(mapping, limit=50, value_limit=200):
    clean = {}
    for index, (key, value) in enumerate(mapping.items()):
        if index >= limit:
            break
        if isinstance(value, (list, tuple)):
            clean[key] = [str(item)[:value_limit] for item in value[:10]]
        else:
            clean[key] = str(value)[:value_limit]
    return clean


def get_uploaded_files_metadata(request):
    files = []
    for file_key, upload in request.FILES.items():
        files.append({
            'field': file_key,
            'name': upload.name,
            'size': upload.size,
            'content_type': getattr(upload, 'content_type', ''),
        })
    return files


def get_attack_tool(user_agent):
    agent = (user_agent or '').lower()
    for marker, label in KNOWN_ATTACK_TOOLS.items():
        if marker in agent:
            return label
    return ''


def is_new_ip_for_user(request, ip_address):
    if not getattr(request, 'user', None) or not request.user.is_authenticated or not ip_address:
        return False
    return not UserTracking.objects.filter(user=request.user, ip_address=ip_address).exists()


def score_incident(category, attack_tool='', is_new_ip=False, blocked=False, files=None, telemetry=None):
    score = 20
    category_weights = {
        'brute_force': 40,
        'admin_probe': 35,
        'suspicious_request': 30,
        'blocked_request': 50,
        'frontend_signal': 15,
    }
    score += category_weights.get(category, 10)
    if attack_tool:
        score += 30
    if is_new_ip:
        score += 15
    if blocked:
        score += 25
    if files:
        score += 10
    if telemetry and telemetry.get('typingProfile', {}).get('suspicious'):
        score += 10
    return min(score, 100)


def severity_from_score(score):
    if score >= 85:
        return 'critical'
    if score >= 65:
        return 'high'
    if score >= 40:
        return 'medium'
    return 'low'


def get_geo_context(request):
    if not get_monitoring_settings().get('ENABLE_GEO_LOOKUPS', False):
        return {'country': '', 'city': '', 'latitude': None, 'longitude': None}
    try:
        from .middleware import AdvancedErrorTrackingMiddleware
        middleware = AdvancedErrorTrackingMiddleware(lambda r: None)
        data = middleware.get_advanced_location_info(request)
        return {
            'country': data.get('country', ''),
            'city': data.get('city', ''),
            'latitude': data.get('lat'),
            'longitude': data.get('lon'),
        }
    except Exception:
        return {'country': '', 'city': '', 'latitude': None, 'longitude': None}


def attach_screenshot_artifact(incident, screenshot_data, label='Browser screenshot'):
    if not incident or not screenshot_data or not isinstance(screenshot_data, str):
        return None
    if not screenshot_data.startswith('data:image/'):
        return None
    try:
        header, encoded = screenshot_data.split(';base64,', 1)
        ext = header.split('/')[1].split(';')[0].lower()
        if ext not in {'png', 'jpg', 'jpeg', 'webp'}:
            ext = 'jpg'
        content = base64.b64decode(encoded)
    except (ValueError, binascii.Error):
        return None

    if Image:
        try:
            image = Image.open(io.BytesIO(content))
            max_side = 1800
            image.thumbnail((max_side, max_side), RESAMPLING_LANCZOS)
            optimized = io.BytesIO()
            if ext == 'png' or image.mode in {'RGBA', 'LA', 'P'}:
                if image.mode not in {'RGB', 'RGBA'}:
                    image = image.convert('RGBA')
                image.save(optimized, format='PNG', optimize=True)
                ext = 'png'
            else:
                if image.mode not in {'RGB', 'L'}:
                    image = image.convert('RGB')
                image.save(optimized, format='JPEG', quality=88, optimize=True)
                ext = 'jpg'
            content = optimized.getvalue()
        except Exception:
            logger.exception('Failed to optimize screenshot artifact.')

    artifact = SecurityArtifact(
        incident=incident,
        artifact_type='screenshot',
        label=label,
    )
    artifact.file.save(
        f"security-shot-{uuid.uuid4().hex}.{ext}",
        ContentFile(content),
        save=True,
    )
    return artifact


def attach_recent_screenshot_artifact(incident, request, label='Recovered login screenshot'):
    if not incident or not request:
        return None
    recent_cutoff = timezone.now() - timedelta(minutes=5)
    recent_artifact = (
        SecurityArtifact.objects
        .filter(
            artifact_type='screenshot',
            incident__detected_at__gte=recent_cutoff,
            incident__ip_address=get_client_ip(request),
            incident__fingerprint_hash=build_fingerprint(request),
        )
        .exclude(file='')
        .exclude(file__isnull=True)
        .select_related('incident')
        .order_by('-created_at')
        .first()
    )
    if not recent_artifact or not recent_artifact.file:
        return None
    try:
        recent_artifact.file.open('rb')
        clone = SecurityArtifact(
            incident=incident,
            artifact_type='screenshot',
            label=label,
        )
        clone.file.save(
            f"security-shot-{uuid.uuid4().hex}.{recent_artifact.file.name.split('.')[-1]}",
            ContentFile(recent_artifact.file.read()),
            save=True,
        )
        return clone
    except Exception:
        logger.exception('Failed to clone recent screenshot artifact for login incident.')
        return None
    finally:
        try:
            recent_artifact.file.close()
        except Exception:
            pass


def alternative_capture(request, reason, response=None, extra_context=None, client_telemetry=None, source='middleware'):
    cfg = get_monitoring_settings()
    if not cfg.get('ENABLED', True):
        return None

    ip_address = get_client_ip(request)
    fingerprint_hash = build_fingerprint(request, client_telemetry=client_telemetry)
    user_agent = request.META.get('HTTP_USER_AGENT', '')
    geo = get_geo_context(request)
    files = get_uploaded_files_metadata(request)
    html_snapshot = ''
    if response is not None:
        try:
            content_type = response.get('Content-Type', '')
            if 'text/html' in content_type and hasattr(response, 'content'):
                html_snapshot = response.content.decode('utf-8', errors='ignore')[: cfg['MAX_HTML_CAPTURE']]
        except Exception:
            html_snapshot = ''

    attack_tool = get_attack_tool(user_agent)
    new_ip = is_new_ip_for_user(request, ip_address)
    forensic_context = extra_context.copy() if extra_context else {}
    if client_telemetry:
        forensic_context['frontend_telemetry'] = client_telemetry
    if files:
        forensic_context['uploads'] = files

    threat_score = score_incident(
        category=reason,
        attack_tool=attack_tool,
        is_new_ip=new_ip,
        blocked=bool(forensic_context.get('blocked')),
        files=files,
        telemetry=client_telemetry,
    )
    severity = severity_from_score(threat_score)

    recent_window = timezone.now() - timedelta(minutes=15)
    incident = SecurityIncident.objects.filter(category=reason, ip_address=ip_address, fingerprint_hash=fingerprint_hash, detected_at__gte=recent_window).order_by('-detected_at').first()
    is_new_incident = incident is None
    if incident:
        incident.last_seen_at = timezone.now()
        incident.event_count += 1
        incident.threat_score = max(incident.threat_score, threat_score)
        incident.severity = severity_from_score(incident.threat_score)
        incident.summary = incident.summary or forensic_context.get('summary', '')
        incident.request_headers = incident.request_headers or sanitize_mapping({k: v for k, v in request.META.items() if k.startswith('HTTP_')})
        incident.request_query = incident.request_query or sanitize_mapping(request.GET)
        incident.request_post = incident.request_post or sanitize_mapping(request.POST)
        incident.forensic_context.update(forensic_context)
        incident.save()
    else:
        incident = SecurityIncident.objects.create(
            source=source,
            category=reason,
            title=forensic_context.get('title') or reason.replace('_', ' ').title(),
            summary=forensic_context.get('summary', ''),
            severity=severity,
            threat_score=threat_score,
            user=request.user if getattr(request, 'user', None) and request.user.is_authenticated else None,
            username_snapshot=getattr(request.user, 'username', '') if getattr(request, 'user', None) and request.user.is_authenticated else '',
            ip_address=ip_address,
            fingerprint_hash=fingerprint_hash,
            user_agent=user_agent[:1000],
            method=request.method,
            path=request.path[:500],
            referer=request.META.get('HTTP_REFERER', '')[:500],
            request_id=request.META.get('HTTP_X_REQUEST_ID', '')[:64],
            country=geo['country'],
            city=geo['city'],
            latitude=geo['latitude'],
            longitude=geo['longitude'],
            attack_tool=attack_tool,
            is_known_bot=bool(attack_tool),
            is_new_ip_for_user=new_ip,
            is_blocked=bool(forensic_context.get('blocked')),
            html_snapshot=html_snapshot,
            request_headers=sanitize_mapping({k: v for k, v in request.META.items() if k.startswith('HTTP_')}),
            request_query=sanitize_mapping(request.GET),
            request_post=sanitize_mapping(request.POST),
            forensic_context=forensic_context,
            first_seen_at=timezone.now(),
            last_seen_at=timezone.now(),
        )

    SecurityArtifact.objects.create(
        incident=incident,
        artifact_type='headers',
        label='Request headers',
        content=incident.request_headers,
    )
    if html_snapshot:
        SecurityArtifact.objects.create(
            incident=incident,
            artifact_type='html',
            label='HTML snapshot',
            text_content=html_snapshot,
        )
    if files:
        SecurityArtifact.objects.create(
            incident=incident,
            artifact_type='upload_metadata',
            label='Uploaded file metadata',
            content={'files': files},
        )
    if client_telemetry:
        SecurityArtifact.objects.create(
            incident=incident,
            artifact_type='frontend_telemetry',
            label='Frontend telemetry',
            content=client_telemetry,
        )
        attach_screenshot_artifact(
            incident,
            client_telemetry.get('screenshot'),
            label='Frontend captured screenshot',
        )

    SecurityEvent.objects.create(
        incident=incident,
        event_type=reason,
        ip_address=ip_address,
        fingerprint_hash=fingerprint_hash,
        path=request.path,
        payload={'severity': severity, 'threat_score': threat_score},
    )

    if should_send_realtime_alert(incident, is_new_incident=is_new_incident):
        send_incident_alert(incident)

    return incident


def capture_login_event(request, success, username='', failure_reason=''):
    screenshot_data = request.POST.get('security_screenshot', '')
    ip_address = get_client_ip(request)
    fingerprint_hash = build_fingerprint(request)
    geo = get_geo_context(request)
    category = 'login_success' if success else 'login_failure'
    severity = 'low' if success else 'medium'
    title = 'تم تسجيل الدخول بنجاح' if success else 'فشل تسجيل الدخول'
    summary = (
        f"تم تسجيل الدخول بنجاح للمستخدم {username or getattr(request.user, 'username', '') or 'غير محدد'}."
        if success else
        f"فشلت محاولة تسجيل الدخول باسم المستخدم {username or 'غير محدد'}."
    )
    if failure_reason:
        summary = f"{summary} السبب: {failure_reason}"

    user_obj = getattr(request, 'user', None)
    if not getattr(user_obj, 'is_authenticated', False):
        user_obj = None

    incident = SecurityIncident.objects.create(
        source='manual',
        category=category,
        title=title,
        summary=summary,
        severity=severity,
        threat_score=20 if success else 45,
        user=user_obj,
        username_snapshot=(getattr(user_obj, 'username', '') or username or '')[:150],
        ip_address=ip_address,
        fingerprint_hash=fingerprint_hash,
        user_agent=request.META.get('HTTP_USER_AGENT', '')[:1000],
        method=request.method[:10],
        path=request.path[:500],
        referer=request.META.get('HTTP_REFERER', '')[:500],
        country=geo['country'],
        city=geo['city'],
        latitude=geo['latitude'],
        longitude=geo['longitude'],
        first_seen_at=timezone.now(),
        last_seen_at=timezone.now(),
        request_headers=sanitize_mapping({k: v for k, v in request.META.items() if k.startswith('HTTP_')}),
        request_query=sanitize_mapping(request.GET),
        request_post=sanitize_mapping({'username': username}),
        forensic_context={'login_success': success, 'failure_reason': failure_reason},
    )

    SecurityEvent.objects.create(
        incident=incident,
        event_type=category,
        ip_address=ip_address,
        fingerprint_hash=fingerprint_hash,
        path=request.path,
        payload={'success': success, 'username': username, 'reason': failure_reason},
    )
    SecurityArtifact.objects.create(
        incident=incident,
        artifact_type='headers',
        label='Login request headers',
        content=incident.request_headers,
    )
    screenshot_artifact = attach_screenshot_artifact(
        incident,
        screenshot_data,
        label='Login page screenshot',
    )
    if screenshot_artifact is None:
        attach_recent_screenshot_artifact(
            incident,
            request,
            label='Recovered login screenshot',
        )
    send_incident_alert(incident)
    return incident


def send_incident_alert(incident):
    cfg = get_monitoring_settings()
    if not cfg.get('ENABLE_EMAIL_ALERTS', False):
        return 0
    branding = SecurityBranding.objects.order_by('-updated_at').first()
    recipients = [branding.alert_recipient] if branding and branding.alert_recipient else (cfg.get('ALERT_EMAILS') or [])
    if not recipients:
        return
    subject = f"{settings.EMAIL_SUBJECT_PREFIX}تنبيه أمني {incident.severity} - {incident.title}"
    context = build_email_context({'incident': incident})
    body = render_to_string('errors/security_alert_email.txt', context)
    html_body = render_to_string('errors/security_alert_email.html', context)
    email = EmailMultiAlternatives(
        subject=subject,
        body=body,
        to=recipients,
        from_email=get_from_email(),
        reply_to=[settings.DEFAULT_FROM_EMAIL] if settings.DEFAULT_FROM_EMAIL else None,
    )
    email.attach_alternative(html_body, 'text/html')
    screenshot = incident.artifacts.filter(artifact_type='screenshot', file__isnull=False).order_by('-created_at').first()
    if screenshot and screenshot.file:
        try:
            screenshot.file.open('rb')
            filename = screenshot.file.name.split('/')[-1]
            extension = filename.rsplit('.', 1)[-1].lower() if '.' in filename else 'jpg'
            mimetype = {
                'jpg': 'image/jpeg',
                'jpeg': 'image/jpeg',
                'png': 'image/png',
                'webp': 'image/webp',
            }.get(extension, 'application/octet-stream')
            email.attach(
                filename=filename,
                content=screenshot.file.read(),
                mimetype=mimetype,
            )
        except Exception:
            logger.exception('Failed to attach screenshot for incident %s.', incident.pk)
        finally:
            try:
                screenshot.file.close()
            except Exception:
                pass
    try:
        return email.send(fail_silently=False)
    except Exception:
        logger.exception('Failed to send incident alert for incident %s with attachment.', incident.pk)
        if screenshot:
            fallback_email = EmailMultiAlternatives(
                subject=subject,
                body=body,
                to=recipients,
                from_email=get_from_email(),
                reply_to=[settings.DEFAULT_FROM_EMAIL] if settings.DEFAULT_FROM_EMAIL else None,
            )
            fallback_email.attach_alternative(html_body, 'text/html')
            try:
                return fallback_email.send(fail_silently=False)
            except Exception:
                logger.exception('Failed to send fallback incident alert for incident %s.', incident.pk)
                return 0
        return 0


def should_send_realtime_alert(incident, is_new_incident=False):
    cfg = get_monitoring_settings()
    if not cfg.get('ENABLE_EMAIL_ALERTS', False):
        return False
    if incident.category in {'login_success', 'login_failure'}:
        return cfg.get('ENABLE_LOGIN_EVENT_EMAILS', False)
    if incident.category == 'frontend_signal' and incident.severity == 'low':
        return False
    throttle_key = f"security:alert:{incident.category}:{incident.ip_address}:{incident.fingerprint_hash}"
    if is_new_incident:
        if cache.get(throttle_key):
            return False
        cache.set(throttle_key, True, timeout=600)
        return True
    if incident.severity in {'high', 'critical'} and not cache.get(throttle_key):
        cache.set(throttle_key, True, timeout=600)
        return True
    return False


def build_daily_report(day=None):
    day = day or timezone.localdate()
    start = timezone.make_aware(timezone.datetime.combine(day, timezone.datetime.min.time()))
    end = start + timedelta(days=1)
    incidents = SecurityIncident.objects.filter(detected_at__gte=start, detected_at__lt=end).order_by('-threat_score')
    by_severity = Counter(incidents.values_list('severity', flat=True))
    by_category = list(incidents.values('category').annotate(total=Count('id')).order_by('-total')[:10])
    top_ips = list(incidents.values('ip_address').annotate(total=Count('id')).order_by('-total')[:10])
    return {
        'date': day,
        'count': incidents.count(),
        'by_severity': dict(by_severity),
        'by_category': by_category,
        'top_ips': top_ips,
        'incidents': list(incidents[:25].values('id', 'title', 'severity', 'threat_score', 'ip_address', 'path', 'category', 'detected_at')),
    }


def send_daily_report(day=None):
    branding = SecurityBranding.objects.order_by('-updated_at').first()
    recipients = [branding.alert_recipient] if branding and branding.alert_recipient else (get_monitoring_settings().get('DAILY_REPORT_EMAILS') or [])
    if not recipients:
        return 0
    report = build_daily_report(day=day)
    subject = f"{settings.EMAIL_SUBJECT_PREFIX}التقرير الأمني اليومي - {report['date']}"
    context = build_email_context(report)
    body = render_to_string('errors/security_report_email.txt', context)
    html_body = render_to_string('errors/security_report_email.html', context)
    email = EmailMultiAlternatives(
        subject=subject,
        body=body,
        to=recipients,
        from_email=get_from_email(),
        reply_to=[settings.DEFAULT_FROM_EMAIL] if settings.DEFAULT_FROM_EMAIL else None,
    )
    email.attach_alternative(html_body, 'text/html')
    email.attach(
        filename=f"security-report-{report['date']}.json",
        content=json.dumps(report, cls=DjangoJSONEncoder, ensure_ascii=False, indent=2),
        mimetype='application/json',
    )
    email.send(fail_silently=True)
    return report['count']


def match_active_blocks(ip_address='', fingerprint_hash='', user=None):
    now = timezone.now()
    rules = SecurityBlocklist.objects.filter(is_active=True)
    matched = []
    if ip_address:
        matched.extend(list(rules.filter(target_type='ip', value=ip_address)))
    if fingerprint_hash:
        matched.extend(list(rules.filter(target_type='fingerprint', value=fingerprint_hash)))
    if user and getattr(user, 'is_authenticated', False):
        matched.extend(list(rules.filter(target_type='user', value=str(user.pk))))
    active = []
    for rule in matched:
        if rule.expires_at and rule.expires_at <= now:
            continue
        rule.last_match_at = now
        rule.save(update_fields=['last_match_at'])
        active.append(rule)
    return active

