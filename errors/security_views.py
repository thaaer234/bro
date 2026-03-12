import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.db.models import Count

from .models import SecurityArtifact, SecurityBlocklist, SecurityBranding, SecurityIncident
from .security import alternative_capture, send_daily_report


def _staff(user):
    return user.is_staff


@login_required
@user_passes_test(_staff)
def security_dashboard(request):
    incidents = SecurityIncident.objects.all().order_by('-detected_at')[:100]
    screenshot_artifacts = SecurityArtifact.objects.filter(
        artifact_type='screenshot',
        file__isnull=False,
    ).select_related('incident').order_by('-created_at')[:48]
    selected = None
    incident_id = request.GET.get('incident')
    if incident_id:
        selected = SecurityIncident.objects.filter(pk=incident_id).prefetch_related('artifacts', 'events').first()
    branding = SecurityBranding.objects.order_by('-updated_at').first()
    stats = {
        'open_incidents': SecurityIncident.objects.filter(status='open').count(),
        'critical_incidents': SecurityIncident.objects.filter(severity='critical').count(),
        'blocked_rules': SecurityBlocklist.objects.filter(is_active=True).count(),
        'today_incidents': SecurityIncident.objects.filter(detected_at__date=timezone.localdate()).count(),
        'heatmap_data': list(
            SecurityIncident.objects.exclude(latitude__isnull=True).exclude(longitude__isnull=True)
            .values('country', 'city', 'latitude', 'longitude')
            .annotate(total=Count('id'))[:100]
        ),
        'category_stats': list(SecurityIncident.objects.values('category').annotate(total=Count('id')).order_by('-total')[:10]),
        'recent_blocks': SecurityBlocklist.objects.order_by('-updated_at')[:20],
        'screenshot_artifacts': screenshot_artifacts,
        'screenshots_count': screenshot_artifacts.count(),
        'recent_timeline': SecurityIncident.objects.order_by('-detected_at')[:20],
        'branding': branding,
    }
    return render(request, 'errors/security_dashboard.html', {
        'incidents': incidents,
        'selected_incident': selected,
        **stats,
    })


@require_POST
@login_required
@user_passes_test(_staff)
def block_indicator(request):
    target_type = request.POST.get('target_type', '').strip()
    value = request.POST.get('value', '').strip()
    if target_type not in {'ip', 'fingerprint', 'user'} or not value:
        return HttpResponseBadRequest('بيانات الحظر غير صحيحة.')
    rule, created = SecurityBlocklist.objects.update_or_create(
        target_type=target_type,
        value=value,
        defaults={
            'reason': request.POST.get('reason', 'Manual security action')[:255],
            'notes': request.POST.get('notes', ''),
            'is_active': True,
            'created_by': request.user,
            'expires_at': None,
        },
    )
    messages.success(request, f'تم حفظ قاعدة الحظر: {rule.target_type}:{rule.value}')
    return redirect('security_dashboard')


@require_POST
@login_required
@user_passes_test(_staff)
def unblock_indicator(request, rule_id):
    rule = get_object_or_404(SecurityBlocklist, pk=rule_id)
    rule.is_active = False
    rule.save(update_fields=['is_active', 'updated_at'])
    messages.success(request, f'تم فك الحظر: {rule.target_type}:{rule.value}')
    return redirect('security_dashboard')


@require_POST
def security_telemetry_api(request):
    try:
        payload = json.loads(request.body.decode('utf-8'))
    except Exception:
        return JsonResponse({'ok': False, 'error': 'invalid_json'}, status=400)

    if not payload.get('consent'):
        return JsonResponse({'ok': False, 'error': 'consent_required'}, status=400)

    telemetry = {
        'clientId': payload.get('clientId', '')[:100],
        'timezone': payload.get('timezone', '')[:100],
        'screen': payload.get('screen', ''),
        'platform': payload.get('platform', '')[:100],
        'touchPoints': payload.get('touchPoints', 0),
        'pageHistory': payload.get('pageHistory', [])[:20],
        'clickPath': payload.get('clickPath', [])[:50],
        'typingProfile': payload.get('typingProfile', {}),
        'fileMetadata': payload.get('fileMetadata', [])[:20],
    }
    incident = alternative_capture(
        request,
        reason='frontend_signal',
        client_telemetry=telemetry,
        source='frontend',
        extra_context={
            'title': 'إشارة رصد من الواجهة الأمامية',
            'summary': payload.get('summary', 'تم استلام telemetry مصرح به من الواجهة الأمامية.')[:500],
        },
    )
    return JsonResponse({'ok': True, 'incident_id': str(incident.id) if incident else None})


@require_POST
@login_required
@user_passes_test(_staff)
def send_security_report_now(request):
    count = send_daily_report()
    messages.success(request, f'تم إرسال التقرير الأمني. عدد الحوادث المضمنة: {count}')
    return redirect('security_dashboard')


@require_POST
@login_required
@user_passes_test(_staff)
def update_security_branding(request):
    branding, _ = SecurityBranding.objects.get_or_create(
        pk=1,
        defaults={
            'brand_name': 'مركز الأمن - معهد اليمان',
            'brand_short': 'مركز الأمن',
            'sender_name': 'مركز الأمن - معهد اليمان',
            'support_email': 'mhmadwerc8@gmail.com',
            'alert_recipient': 'thaaeralmasre98@gmail.com',
            'dashboard_url': request.build_absolute_uri('/security/'),
        },
    )
    branding.brand_name = request.POST.get('brand_name', branding.brand_name)[:255]
    branding.brand_short = request.POST.get('brand_short', branding.brand_short)[:120]
    branding.sender_name = request.POST.get('sender_name', branding.sender_name)[:255]
    branding.support_email = request.POST.get('support_email', branding.support_email)
    branding.alert_recipient = request.POST.get('alert_recipient', branding.alert_recipient)
    branding.dashboard_url = request.POST.get('dashboard_url', branding.dashboard_url)
    branding.logo_url = request.POST.get('logo_url', branding.logo_url)
    branding.subject_prefix = request.POST.get('subject_prefix', branding.subject_prefix)[:120]
    branding.save()
    messages.success(request, 'تم تحديث هوية البريد الأمني بنجاح.')
    return redirect('security_dashboard')
