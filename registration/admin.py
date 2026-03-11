# admin.py
from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import UserProfile, PasswordResetRequest, PasswordChangeHistory

# إلغاء تسجيل User الافتراضي أولاً
admin.site.unregister(User)

class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'الملف الشخصي'
    fields = ['phone', 'address', 'profile_picture', 'created_at', 'updated_at']
    readonly_fields = ['created_at', 'updated_at']
    extra = 0

class UserAdmin(BaseUserAdmin):
    inlines = [UserProfileInline]
    list_display = ['username', 'email', 'first_name', 'last_name', 'is_staff', 'is_active', 'date_joined']
    list_filter = ['is_staff', 'is_superuser', 'is_active', 'date_joined']
    search_fields = ['username', 'email', 'first_name', 'last_name']
    
    # الحقول المعروضة في صفحة التعديل
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('معلومات شخصية', {'fields': ('first_name', 'last_name', 'email')}),
        ('الصلاحيات', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        ('تواريخ مهمة', {'fields': ('last_login', 'date_joined')}),
    )

# تسجيل User مع الإعدادات المخصصة
admin.site.register(User, UserAdmin)

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'phone', 'created_at', 'updated_at']
    list_filter = ['created_at', 'updated_at']
    search_fields = ['user__username', 'user__email', 'phone', 'address']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = [
        ('المستخدم', {
            'fields': ['user']
        }),
        ('معلومات الاتصال', {
            'fields': ['phone', 'address']
        }),
        ('الصورة الشخصية', {
            'fields': ['profile_picture']
        }),
        ('التواريخ', {
            'fields': ['created_at', 'updated_at'],
            'classes': ['collapse']
        }),
    ]

@admin.register(PasswordResetRequest)
class PasswordResetRequestAdmin(admin.ModelAdmin):
    list_display = ['user', 'code', 'is_approved', 'is_used', 'created_at', 'approved_at', 'expires_at', 'approved_by', 'is_expired']
    list_filter = ['is_approved', 'is_used', 'created_at', 'approved_at']
    search_fields = ['user__username', 'user__email', 'code', 'reason']
    readonly_fields = ['created_at', 'approved_at', 'expires_at', 'code']
    list_per_page = 20
    
    fieldsets = [
        ('معلومات المستخدم', {
            'fields': ['user', 'reason']
        }),
        ('حالة الطلب', {
            'fields': ['is_approved', 'is_used', 'code']
        }),
        ('التواريخ', {
            'fields': ['created_at', 'approved_at', 'expires_at']
        }),
        ('المشرف', {
            'fields': ['approved_by']
        }),
    ]
    
    def is_expired(self, obj):
        from django.utils import timezone
        if obj.expires_at:
            return timezone.now() > obj.expires_at
        return False
    is_expired.boolean = True
    is_expired.short_description = 'منتهي الصلاحية'

@admin.register(PasswordChangeHistory)
class PasswordChangeHistoryAdmin(admin.ModelAdmin):
    list_display = ['user', 'changed_at', 'changed_by', 'has_reset_request']
    list_filter = ['changed_at', 'changed_by']
    search_fields = ['user__username', 'user__email', 'changed_by__username']
    readonly_fields = ['changed_at', 'old_password_hash', 'new_password_hash']
    date_hierarchy = 'changed_at'
    list_per_page = 25
    
    fieldsets = [
        ('معلومات التغيير', {
            'fields': ['user', 'changed_by', 'changed_at', 'reset_request']
        }),
        ('كلمات المرور (لأغراض التدقيق)', {
            'fields': ['old_password_hash', 'new_password_hash'],
            'classes': ['collapse']
        }),
    ]
    
    def has_reset_request(self, obj):
        return obj.reset_request is not None
    has_reset_request.boolean = True
    has_reset_request.short_description = 'مرتبط بطلب'