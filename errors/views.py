from django.shortcuts import render
from django.http import HttpResponseNotFound, HttpResponseForbidden, HttpResponseServerError, JsonResponse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils import timezone
from django.db.models import Count, Q, Max
from .models import ErrorLog, SecurityAlert, ErrorAnalytics, UserTracking
import user_agents
import requests
from datetime import datetime, timedelta
import json

def error_404_view(request, exception=None):
    log_error(request, 404)
    context = {
        'requested_path': request.path,
        'message': 'الصفحة التي تبحث عنها غير موجودة.',
        'suggestions': get_suggestions(request.path)
    }
    return HttpResponseNotFound(render(request, 'errors/404.html', context))

def error_403_view(request, exception=None):
    log_error(request, 403)
    context = {
        'requested_path': request.path,
        'message': 'ليس لديك صلاحية للوصول إلى هذه الصفحة.'
    }
    return HttpResponseForbidden(render(request, 'errors/403.html', context))

def error_500_view(request):
    log_error(request, 500)
    context = {
        'message': 'حدث خطأ داخلي في الخادم.',
        'support_contact': '00966500000000'
    }
    return HttpResponseServerError(render(request, 'errors/500.html', context))

def error_503_view(request):
    log_error(request, 503)
    context = {
        'message': 'الخدمة غير متاحة حاليًا للصيانة.',
        'maintenance_window': '30 دقيقة'
    }
    return HttpResponseServerError(render(request, 'errors/503.html', context))

def get_suggestions(path):
    """تقديم اقتراحات للمستخدم بناءً على المسار المطلوب"""
    suggestions = []
    path_lower = path.lower()
    
    if 'admin' in path_lower:
        suggestions.append('قد تكون تبحث عن لوحة التحكم الإدارية')
    elif 'login' in path_lower:
        suggestions.append('تسجيل الدخول متوفر عبر /login/')
    elif 'student' in path_lower:
        suggestions.append('قسم الطلاب متوفر عبر /students/')
    elif 'course' in path_lower:
        suggestions.append('قسم الكورسات متوفر عبر /courses/')
    
    suggestions.extend([
        'تحقق من كتابة الرابط بشكل صحيح',
        'استخدم شريط البحث للعثور على ما تريد',
        'انتقل إلى الصفحة الرئيسية واستكشف الموقع'
    ])
    
    return suggestions

def log_error(request, error_code):
    try:
        user_agent_string = request.META.get('HTTP_USER_AGENT', '')
        ua = user_agents.parse(user_agent_string)
        
        admin_keywords = [
            'admin', 'sham', 'dashboard', 'backend', 'administrator', 
            'control', 'manage', 'panel', 'cpanel', 'webadmin', 'phpmyadmin'
        ]
        
        security_keywords = [
            'union select', 'select *', 'insert into', 'drop table', 
            'script>', '<iframe', '../', 'etc/passwd'
        ]
        
        attempted_admin = any(keyword in request.path.lower() for keyword in admin_keywords)
        
        # كشف الهجمات الأمنية
        request_string = (request.path + str(request.GET) + str(request.POST)).lower()
        security_threat = any(keyword in request_string for keyword in security_keywords)
        
        if security_threat:
            SecurityAlert.objects.create(
                alert_type='sql_injection' if any(sql in request_string for sql in ['union', 'select', 'insert', 'drop']) else 'xss',
                ip_address=get_client_ip(request),
                user=request.user if request.user.is_authenticated else None,
                description=f'محاولة هجوم مكتشفة على المسار: {request.path}',
                severity='high'
            )
        
        location_info = get_location_info(request)
        
        ErrorLog.objects.create(
            user=request.user if request.user.is_authenticated else None,
            ip_address=get_client_ip(request),
            user_agent=user_agent_string,
            device_type=get_device_type(ua),
            browser=ua.browser.family,
            os=ua.os.family,
            path=request.path,
            method=request.method,
            error_code=error_code,
            attempted_admin=attempted_admin,
            attempted_path=request.path,
            country=location_info.get('country', ''),
            city=location_info.get('city', ''),
            latitude=location_info.get('latitude'),
            longitude=location_info.get('longitude'),
            severity='high' if attempted_admin or security_threat else 'medium'
        )
        
        # تحديث الإحصائيات اليومية
        update_daily_analytics()
        
    except Exception as e:
        print(f"Error logging in views failed: {e}")
        pass

def update_daily_analytics():
    """تحديث إحصائيات الأخطاء اليومية"""
    today = timezone.now().date()
    analytics, created = ErrorAnalytics.objects.get_or_create(date=today)
    
    # حساب الإحصائيات
    today_errors = ErrorLog.objects.filter(timestamp__date=today)
    analytics.total_errors = today_errors.count()
    analytics.error_404_count = today_errors.filter(error_code=404).count()
    analytics.error_403_count = today_errors.filter(error_code=403).count()
    analytics.error_500_count = today_errors.filter(error_code=500).count()
    
    # حساب الزوار الفريدين (مبسط)
    unique_ips = today_errors.values('ip_address').distinct().count()
    analytics.unique_visitors = unique_ips
    
    # المسار الأكثر طلباً
    from django.db.models import Count
    most_common = today_errors.values('path').annotate(count=Count('path')).order_by('-count').first()
    if most_common:
        analytics.most_common_path = most_common['path']
    
    analytics.save()

@login_required
@user_passes_test(lambda u: u.is_staff)
def error_dashboard(request):
    """لوحة تحكم للأخطاء للموظفين"""
    today = timezone.now().date()
    last_week = today - timedelta(days=7)
    
    # إحصائيات سريعة
    stats = {
        'total_errors': ErrorLog.objects.count(),
        'today_errors': ErrorLog.objects.filter(timestamp__date=today).count(),
        'unresolved_errors': ErrorLog.objects.filter(resolved=False).count(),
        'recent_errors': ErrorLog.objects.filter(timestamp__gte=last_week),
        'error_distribution': ErrorLog.objects.values('error_code').annotate(count=Count('error_code')),
        'security_alerts': SecurityAlert.objects.filter(resolved=False).count(),
    }
    
    # إحصائيات إضافية للتتبع المتقدم
    stats['top_error_pages'] = ErrorLog.objects.values('path').annotate(
        count=Count('path')
    ).order_by('-count')[:10]
    
    # النشاط اليومي (آخر 24 ساعة)
    hourly_activity = []
    for i in range(24):
        hour = (timezone.now() - timedelta(hours=i)).hour
        count = ErrorLog.objects.filter(
            timestamp__hour=hour,
            timestamp__date=today
        ).count()
        hourly_activity.append({
            'hour': f'{hour:02d}:00',
            'count': count,
            'percentage': min(count * 5, 100)  # نسبة مبسطة للعرض
        })
    stats['hourly_activity'] = hourly_activity[::-1]  # عكس الترتيب
    
    return render(request, 'errors/dashboard.html', stats)

@login_required
@user_passes_test(lambda u: u.is_staff)
def error_analytics_view(request):
    """عرض تحليلات مفصلة للأخطاء"""
    period = request.GET.get('period', '7days')
    
    if period == '30days':
        days = 30
    elif period == '90days':
        days = 90
    else:
        days = 7
    
    start_date = timezone.now().date() - timedelta(days=days)
    analytics = ErrorAnalytics.objects.filter(date__gte=start_date).order_by('date')
    
    context = {
        'analytics': analytics,
        'period': period,
        'days': days
    }
    
    return render(request, 'errors/analytics.html', context)

@login_required
@user_passes_test(lambda u: u.is_staff)
def network_analysis_view(request):
    """تحليل الشبكة والمستخدمين"""
    # المستخدمين النشطين
    active_users = UserTracking.objects.filter(
        last_seen__gte=timezone.now() - timedelta(days=7)
    ).select_related('user')
    
    # تحليل الشبكة
    network_analysis = ErrorLog.objects.filter(
        ip_address__isnull=False
    ).values('ip_address', 'country', 'isp').annotate(
        error_count=Count('id'),
        last_seen=Max('timestamp')
    ).order_by('-error_count')[:20]
    
    context = {
        'active_users': active_users,
        'network_analysis': network_analysis,
        'total_tracked_users': UserTracking.objects.count(),
        'unique_ips': ErrorLog.objects.values('ip_address').distinct().count(),
    }
    
    return render(request, 'errors/network_analysis.html', context)

def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

def get_device_type(ua):
    if ua.is_mobile:
        return 'Mobile'
    elif ua.is_tablet:
        return 'Tablet'
    elif ua.is_pc:
        return 'Desktop'
    elif ua.is_bot:
        return 'Bot'
    else:
        return 'Unknown'

def get_location_info(request):
    try:
        ip = get_client_ip(request)
        if ip and ip not in ['127.0.0.1', 'localhost', '::1']:
            response = requests.get(f'http://ip-api.com/json/{ip}', timeout=3)
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    return {
                        'country': data.get('country', ''),
                        'city': data.get('city', ''),
                        'latitude': data.get('lat'),
                        'longitude': data.get('lon')
                    }
    except:
        pass
    return {}

def error_analytics_view(request):
    # جمع بيانات تحليلات الأخطاء
    error_stats = {
        'total_errors': 100,  # مثال - استبدل ببياناتك الحقيقية
        'recent_errors': 25,
        'resolved_errors': 75,
        'error_categories': {
            '404': 40,
            '500': 30,
            '403': 20,
            'other': 10
        }
    }
    
    # تعريف context بشكل صحيح
    context = {
        'error_stats': error_stats,
        'page_title': 'تحليلات الأخطاء',
        # أضف أي متغيرات أخرى تحتاجها
    }
    
    return render(request, 'errors/analytics.html', context)



