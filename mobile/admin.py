from django.contrib import admin
from django.db.models import Count, IntegerField, OuterRef, Subquery, Q

from employ.models import Teacher
from students.models import Student

from .models import MobileDeviceToken, MobileNotification


class MobileDeviceTokenAnonymousFilter(admin.SimpleListFilter):
    title = "مستخدم مرتبط"
    parameter_name = "linked_user"

    def lookups(self, request, model_admin):
        return (
            ("yes", "مرتبط"),
            ("no", "غير مرتبط"),
        )

    def queryset(self, request, queryset):
        if self.value() == "yes":
            return queryset.filter(user_type__isnull=False, user_id__isnull=False)
        if self.value() == "no":
            return queryset.filter(Q(user_type__isnull=True) | Q(user_id__isnull=True))
        return queryset


@admin.register(MobileNotification)
class MobileNotificationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "student_name",
        "notification_type",
        "title",
        "teacher_name",
        "created_at",
        "is_read",
    )
    list_filter = ("notification_type", "is_read", "created_at")
    search_fields = ("title", "message", "student__full_name", "teacher__full_name")
    autocomplete_fields = ("student", "teacher")
    readonly_fields = ("created_at",)
    ordering = ("-created_at",)

    def student_name(self, obj):
        return obj.student.full_name if obj.student_id else "-"

    student_name.short_description = "اسم الطالب"

    def teacher_name(self, obj):
        return obj.teacher.full_name if obj.teacher_id else "-"

    teacher_name.short_description = "اسم المدرس"


@admin.register(MobileDeviceToken)
class MobileDeviceTokenAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user_type",
        "login_role",
        "user_id",
        "user_name",
        "linked_user",
        "mobile_name",
        "platform",
        "token_short",
        "notification_count",
        "last_seen_at",
    )
    list_filter = (
        MobileDeviceTokenAnonymousFilter,
        "user_type",
        "login_role",
        "platform",
        "created_at",
        "last_seen_at",
    )
    search_fields = ("token", "device_id", "device_name", "app_version", "user_id")
    readonly_fields = ("created_at", "updated_at", "last_seen_at")
    ordering = ("-last_seen_at", "-created_at")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        notification_count = (
            MobileNotification.objects.filter(student_id=OuterRef("user_id"))
            .values("student_id")
            .annotate(total=Count("id"))
            .values("total")
        )
        return qs.annotate(
            _notification_count=Subquery(notification_count, output_field=IntegerField())
        )

    def user_name(self, obj):
        if obj.user_type == "parent":
            return (
                Student.objects.filter(id=obj.user_id)
                .values_list("full_name", flat=True)
                .first()
                or "-"
            )
        if obj.user_type == "teacher":
            return (
                Teacher.objects.filter(id=obj.user_id)
                .values_list("full_name", flat=True)
                .first()
                or "-"
            )
        return "-"

    user_name.short_description = "اسم المستخدم"

    def linked_user(self, obj):
        return bool(obj.user_type and obj.user_id)

    linked_user.boolean = True
    linked_user.short_description = "مستخدم مرتبط"

    def mobile_name(self, obj):
        parts = []
        if obj.device_name:
            parts.append(obj.device_name)
        if obj.device_id:
            parts.append(obj.device_id)
        if obj.app_version:
            parts.append(f"v{obj.app_version}")
        return " / ".join(parts) if parts else "-"

    mobile_name.short_description = "اسم الجهاز"

    def token_short(self, obj):
        token = obj.token or ""
        if len(token) <= 24:
            return token
        return f"{token[:12]}...{token[-8:]}"

    token_short.short_description = "التوكن"

    def notification_count(self, obj):
        if obj.user_type != "parent":
            return "-"
        return obj._notification_count or 0

    notification_count.short_description = "عدد الإشعارات"
