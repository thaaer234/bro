from django.contrib import admin
from django.utils.html import format_html
from django.urls import path
from django.shortcuts import render, redirect
from django.db.models import Count, Q
import datetime
import json
from .models import ErrorLog, SecurityAlert, ErrorAnalytics, UserTracking, SecurityIncident, SecurityArtifact, SecurityBlocklist, SecurityEvent, SecurityBranding

class ErrorLogAdmin(admin.ModelAdmin):
    list_display = [
        'timestamp', 'error_code_badge', 'path', 'user', 
        'ip_address', 'device_type', 'country', 'attempted_admin', 
        'resolved_status', 'map_button', 'dashboard_button'
    ]
    
    list_filter = [
        'error_code', 'attempted_admin', 'device_type', 
        'country', 'timestamp', 'resolved', 'severity',
        'browser', 'os', 'is_bot'
    ]
    
    search_fields = [
        'path', 'user__username', 'ip_address', 'user_agent',
        'country', 'city', 'mac_address', 'hostname'
    ]
    
    readonly_fields = [
        'timestamp', 'user', 'ip_address', 'mac_address', 'hostname',
        'user_agent', 'device_type', 'browser', 'browser_version',
        'os', 'os_version', 'device_brand', 'device_model',
        'is_bot', 'is_mobile', 'is_tablet', 'is_pc',
        'path', 'method', 'error_code', 'error_message',
        'attempted_admin', 'attempted_path', 'country', 'country_code',
        'city', 'region', 'latitude', 'longitude', 'postal_code',
        'continent', 'asn', 'organization', 'reverse_dns',
        'isp', 'timezone', 'response_time'
    ]
    
    fieldsets = (
        ('معلومات الشبكة المتقدمة', {
            'fields': (
                'ip_address', 'mac_address', 'hostname', 
                'isp', 'asn', 'organization', 'reverse_dns'
            )
        }),
        ('معلومات الموقع الجغرافي', {
            'fields': (
                ('country', 'country_code'), 
                ('city', 'region'),
                ('latitude', 'longitude'),
                'continent', 'timezone', 'postal_code'
            )
        }),
        ('معلومات الجهاز المتقدمة', {
            'fields': (
                'device_type', 'device_brand', 'device_model',
                ('browser', 'browser_version'),
                ('os', 'os_version'),
                ('is_bot', 'is_mobile', 'is_tablet', 'is_pc'),
                'user_agent'
            )
        }),
        ('معلومات الخطأ', {
            'fields': (
                'error_code', 'error_message', 'path', 'method', 
                'attempted_admin', 'attempted_path', 'severity',
                'response_time'
            )
        }),
        ('حل الخطأ', {
            'fields': ('resolved', 'resolved_at', 'resolved_by', 'notes')
        }),
        ('التوقيت', {
            'fields': ('timestamp',)
        })
    )
    
    actions = ['mark_as_resolved', 'mark_as_unresolved', 'export_to_json']
    
    def error_code_badge(self, obj):
        colors = {
            404: '#27DEBF',
            403: '#FFA726', 
            500: '#FF6B6B',
            503: '#42A5F5',
            400: '#AB47BC',
            401: '#5C6BC0'
        }
        color = colors.get(obj.error_code, '#666666')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 4px 8px; border-radius: 12px; font-weight: bold;">{}</span>',
            color, obj.error_code
        )
    error_code_badge.short_description = 'كود الخطأ'
    
    def resolved_status(self, obj):
        if obj.resolved:
            return format_html('<span style="color: green;">✓ تم الحل</span>')
        return format_html('<span style="color: red;">✗ قيد المعالجة</span>')
    resolved_status.short_description = 'الحالة'
    
    def map_button(self, obj):
        if obj.latitude and obj.longitude:
            return format_html(
                '<a href="/admin/errors/errorlog/{}/map/" class="button" style="background: #417690; color: white; padding: 5px 10px; border-radius: 4px; text-decoration: none;">🗺️ عرض الخريطة</a>',
                obj.id
            )
        return format_html('<span style="color: #999;">لا توجد إحداثيات</span>')
    map_button.short_description = 'الخريطة'
    
    def dashboard_button(self, obj):
        return format_html(
            '<a href="/errors/dashboard/" class="button" style="background: #FF2E63; color: white; padding: 5px 10px; border-radius: 4px; text-decoration: none; margin-right: 5px;">📊 الداشبورد</a>'
        )
    dashboard_button.short_description = 'الإجراءات'
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('<uuid:object_id>/map/', self.admin_site.admin_view(self.map_view), name='error_log_map'),
        ]
        return custom_urls + urls
    
    def map_view(self, request, object_id):
        error_log = ErrorLog.objects.get(id=object_id)
        context = {
            'title': f'الموقع الجغرافي للخطأ {error_log.error_code}',
            'error_log': error_log,
            'latitude': error_log.latitude,
            'longitude': error_log.longitude,
            'country': error_log.country,
            'city': error_log.city,
            'ip_address': error_log.ip_address,
        }
        return render(request, 'admin/errors/errorlog/map_view.html', context)
    
    def mark_as_resolved(self, request, queryset):
        updated = queryset.update(resolved=True, resolved_by=request.user, resolved_at=datetime.datetime.now())
        self.message_user(request, f"تم حل {updated} من سجلات الأخطاء")
    
    def mark_as_unresolved(self, request, queryset):
        updated = queryset.update(resolved=False, resolved_by=None, resolved_at=None)
        self.message_user(request, f"تم تعيين {updated} من سجلات الأخطاء كغير محلولة")
    
    def export_to_json(self, request, queryset):
        import json
        from django.http import HttpResponse
        
        data = list(queryset.values(
            'timestamp', 'ip_address', 'mac_address', 'user__username',
            'path', 'error_code', 'country', 'city', 'latitude', 'longitude',
            'device_type', 'browser', 'os', 'severity'
        ))
        
        response = HttpResponse(json.dumps(data, indent=2, default=str), content_type='application/json')
        response['Content-Disposition'] = 'attachment; filename="error_logs_export.json"'
        return response
    
    def has_add_permission(self, request):
        return False

class SecurityAlertAdmin(admin.ModelAdmin):
    list_display = ['timestamp', 'alert_type', 'ip_address', 'user', 'severity_badge', 'resolved', 'map_button', 'dashboard_button']
    list_filter = ['alert_type', 'severity', 'resolved', 'timestamp']
    search_fields = ['ip_address', 'user__username', 'description', 'mac_address']
    readonly_fields = ['timestamp']
    
    def severity_badge(self, obj):
        colors = {
            'low': '#27DEBF',
            'medium': '#FFA726',
            'high': '#FF6B6B',
            'critical': '#8B0000'
        }
        color = colors.get(obj.severity, '#666666')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 4px 8px; border-radius: 12px; font-weight: bold;">{}</span>',
            color, obj.get_severity_display()
        )
    severity_badge.short_description = 'الشدة'
    
    def map_button(self, obj):
        if obj.latitude and obj.longitude:
            return format_html(
                '<a href="/admin/errors/securityalert/{}/map/" class="button" style="background: #dc3545; color: white; padding: 5px 10px; border-radius: 4px; text-decoration: none;">🗺️ عرض الخريطة</a>',
                obj.id
            )
        return format_html('<span style="color: #999;">لا توجد إحداثيات</span>')
    map_button.short_description = 'الخريطة'
    
    def dashboard_button(self, obj):
        return format_html(
            '<a href="/errors/dashboard/" class="button" style="background: #FF2E63; color: white; padding: 5px 10px; border-radius: 4px; text-decoration: none; margin-right: 5px;">📊 الداشبورد</a>'
        )
    dashboard_button.short_description = 'الإجراءات'

class ErrorAnalyticsAdmin(admin.ModelAdmin):
    list_display = ['date', 'total_errors', 'error_404_count', 'error_403_count', 'error_500_count', 'unique_visitors', 'unique_countries', 'dashboard_button']
    readonly_fields = ['date', 'total_errors', 'error_404_count', 'error_403_count', 'error_500_count', 'unique_visitors', 'unique_countries', 'most_common_path', 'most_common_country', 'average_response_time']
    
    def dashboard_button(self, obj):
        return format_html(
            '<a href="/errors/dashboard/" class="button" style="background: #FF2E63; color: white; padding: 5px 10px; border-radius: 4px; text-decoration: none;">📊 الداشبورد</a>'
        )
    dashboard_button.short_description = 'الإجراءات'
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False

class UserTrackingAdmin(admin.ModelAdmin):
    list_display = ['user', 'ip_address', 'mac_address', 'first_seen', 'last_seen', 'session_count', 'location_button', 'dashboard_button']
    list_filter = ['first_seen', 'last_seen']
    search_fields = ['user__username', 'ip_address', 'mac_address']
    readonly_fields = ['user', 'ip_address', 'mac_address', 'user_agent', 'location_data', 'device_info', 'first_seen', 'last_seen', 'session_count']
    
    def location_button(self, obj):
        location_data = obj.location_data or {}
        if location_data.get('lat') and location_data.get('lon'):
            return format_html(
                '<a href="/admin/errors/usertracking/{}/map/" class="button" style="background: #28a745; color: white; padding: 5px 10px; border-radius: 4px; text-decoration: none;">🗺️ عرض الموقع</a>',
                obj.id
            )
        return format_html('<span style="color: #999;">لا توجد إحداثيات</span>')
    location_button.short_description = 'الموقع'
    
    def dashboard_button(self, obj):
        return format_html(
            '<a href="/errors/dashboard/" class="button" style="background: #FF2E63; color: white; padding: 5px 10px; border-radius: 4px; text-decoration: none; margin-right: 5px;">📊 الداشبورد</a>'
        )
    dashboard_button.short_description = 'الإجراءات'

# لوحة تحكم مخصصة مع زر الداشبورد
class CustomAdminSite(admin.AdminSite):
    site_header = "نظام مراقبة الأخطاء المتقدم - معهد اليمان"
    site_title = "نظام المراقبة المتقدم"
    index_title = "لوحة التحكم الرئيسية - المراقبة الشاملة"
    
    def get_app_list(self, request, app_label=None):
        """
        إضافة زر الداشبورد في قائمة التطبيقات
        """
        app_list = super().get_app_list(request, app_label)
        
        # إضافة داشبورد الأخطاء كتطبيق منفصل
        dashboard_app = {
            'name': '📊 لوحة تحكم الأخطاء',
            'app_label': 'errors_dashboard',
            'app_url': '/admin/errors-dashboard/',
            'has_module_perms': request.user.is_staff,
            'models': [
                {
                    'name': 'عرض الإحصائيات الحية',
                    'object_name': 'error_dashboard',
                    'admin_url': '/errors/dashboard/',
                    'view_only': True,
                }
            ],
        }
        
        # إضافة التطبيق في البداية
        app_list.insert(0, dashboard_app)
        return app_list
    
    def index(self, request, extra_context=None):
        # إحصائيات سريعة
        today = datetime.date.today()
        last_week = today - datetime.timedelta(days=7)
        
        # إحصائيات الأخطاء
        error_stats = {
            'total_errors': ErrorLog.objects.count(),
            'recent_errors': ErrorLog.objects.filter(timestamp__date=today).count(),
            'unresolved_errors': ErrorLog.objects.filter(resolved=False).count(),
            'security_alerts': SecurityAlert.objects.filter(resolved=False).count(),
        }
        
        # توزيع الأخطاء حسب البلد
        error_by_country = ErrorLog.objects.filter(country__isnull=False).values('country').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        # الأخطاء الحرجة
        critical_errors = ErrorLog.objects.filter(severity='critical', resolved=False)[:5]
        
        # بيانات للخرائط
        map_data = list(ErrorLog.objects.filter(
            latitude__isnull=False, 
            longitude__isnull=False
        ).values('latitude', 'longitude', 'country', 'city', 'error_code', 'ip_address')[:100])
        
        extra_context = extra_context or {}
        extra_context.update({
            'error_stats': error_stats,
            'error_by_country': error_by_country,
            'critical_errors': critical_errors,
            'map_data_json': json.dumps(map_data),
            'show_dashboard_button': True,
        })
        
        return super().index(request, extra_context)
    
    def get_urls(self):
        urls = super().get_urls()
        from django.urls import path
        custom_urls = [
            path('errors-dashboard/', self.admin_view(self.error_dashboard_redirect), name='error_dashboard_redirect'),
        ]
        return custom_urls + urls
    
    def error_dashboard_redirect(self, request):
        """توجيه إلى داشبورد الأخطاء"""
        return redirect('/errors/dashboard/')

# إنشاء instance مخصص من AdminSite
admin_site = CustomAdminSite(name='custom_admin')

# تسجيل النماذج مع الـ Admin Site المخصص
# بدلاً من الكود المعلق، استخدم التسجيل العادي
# admin.site.register(ErrorLog, ErrorLogAdmin)
# admin.site.register(SecurityAlert, SecurityAlertAdmin)
# admin.site.register(ErrorAnalytics, ErrorAnalyticsAdmin)
# admin.site.register(UserTracking, UserTrackingAdmin)
@admin.register(SecurityIncident)
class SecurityIncidentAdmin(admin.ModelAdmin):
    list_display = ['detected_at', 'title', 'severity', 'threat_score', 'ip_address', 'category', 'status']
    list_filter = ['severity', 'category', 'status', 'source']
    search_fields = ['title', 'ip_address', 'path', 'fingerprint_hash']
    readonly_fields = ['detected_at', 'created_at', 'updated_at']


@admin.register(SecurityArtifact)
class SecurityArtifactAdmin(admin.ModelAdmin):
    list_display = ['created_at', 'incident', 'artifact_type', 'label']
    list_filter = ['artifact_type', 'created_at']
    search_fields = ['label', 'incident__title']


@admin.register(SecurityBlocklist)
class SecurityBlocklistAdmin(admin.ModelAdmin):
    list_display = ['created_at', 'target_type', 'value', 'is_active', 'expires_at', 'last_match_at']
    list_filter = ['target_type', 'is_active']
    search_fields = ['value', 'reason', 'notes']


@admin.register(SecurityEvent)
class SecurityEventAdmin(admin.ModelAdmin):
    list_display = ['created_at', 'event_type', 'ip_address', 'path', 'incident']
    list_filter = ['event_type', 'created_at']
    search_fields = ['ip_address', 'path', 'fingerprint_hash']


@admin.register(SecurityBranding)
class SecurityBrandingAdmin(admin.ModelAdmin):
    list_display = ['brand_name', 'sender_name', 'support_email', 'alert_recipient', 'updated_at']
