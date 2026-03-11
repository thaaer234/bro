from django.contrib import admin
from .models import MobileUser, EmergencyAlert, Announcement


@admin.register(MobileUser)
class MobileUserAdmin(admin.ModelAdmin):
    list_display = [
        'username', 'phone_number', 'user_type', 'student', 'teacher',
        'is_active', 'is_verified', 'last_login', 'created_at'
    ]
    list_filter = ['user_type', 'is_active', 'is_verified', 'created_at']
    search_fields = [
        'username', 'phone_number', 'student__full_name', 'teacher__full_name'
    ]
    readonly_fields = ['last_login', 'created_at', 'updated_at']
    ordering = ['-created_at']

    fieldsets = (
        ('Account', {
            'fields': ('username', 'password_hash', 'user_type', 'is_active', 'is_verified')
        }),
        ('Relations', {
            'fields': ('student', 'teacher', 'django_user')
        }),
        ('Contact & Device', {
            'fields': ('phone_number', 'device_token')
        }),
        ('Meta', {
            'fields': ('last_login', 'created_at', 'updated_at')
        }),
    )


@admin.register(EmergencyAlert)
class EmergencyAlertAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'alert_type', 'status', 'location', 'created_at']
    list_filter = ['alert_type', 'status', 'created_at']
    search_fields = ['user__username', 'message', 'location']
    readonly_fields = ['created_at', 'updated_at', 'responded_at']
    ordering = ['-created_at']

    actions = ['mark_as_resolved']

    @admin.action(description='Mark selected alerts as resolved')
    def mark_as_resolved(self, request, queryset):
        queryset.update(status='resolved')


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ['title', 'target_audience', 'is_active', 'is_important', 'publish_date']
    list_filter = ['target_audience', 'is_active', 'is_important', 'publish_date']
    search_fields = ['title', 'content']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-publish_date']
