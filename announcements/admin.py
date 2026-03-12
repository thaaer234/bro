from django.contrib import admin

from .models import Announcement, AnnouncementReceipt


class AnnouncementReceiptInline(admin.TabularInline):
    model = AnnouncementReceipt
    extra = 0
    fields = ["recipient_user", "recipient_student", "recipient_teacher", "login_role", "first_seen_at", "read_at", "dismissed_at"]
    readonly_fields = fields
    can_delete = False

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ["title", "audience_type", "is_active", "starts_at", "ends_at", "read_count", "dismiss_count", "created_by"]
    list_filter = ["audience_type", "is_active", "show_as_popup", "created_at"]
    search_fields = ["title", "message"]
    readonly_fields = ["created_at", "updated_at", "read_count", "dismiss_count"]
    inlines = [AnnouncementReceiptInline]

    def save_model(self, request, obj, form, change):
        if not obj.created_by_id:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(AnnouncementReceipt)
class AnnouncementReceiptAdmin(admin.ModelAdmin):
    list_display = ["announcement", "recipient_label", "read_at", "dismissed_at", "updated_at"]
    list_filter = ["announcement__audience_type", "read_at", "dismissed_at"]
    search_fields = ["announcement__title", "recipient_user__username", "recipient_student__full_name", "recipient_teacher__full_name", "login_role"]
    readonly_fields = ["created_at", "updated_at", "first_seen_at", "read_at", "dismissed_at"]

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
