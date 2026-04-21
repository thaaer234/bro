from django.contrib import admin

from .models import (
    AcademicYearAccess,
    AcademicYearStateLog,
    AcademicYearSystemState,
    AcademicYearTransferBatch,
    AcademicYearTransferCourseItem,
    AcademicYearTransferLog,
)


@admin.register(AcademicYearAccess)
class AcademicYearAccessAdmin(admin.ModelAdmin):
    list_display = [
        "academic_year",
        "requires_password",
        "is_read_only",
        "is_archived",
        "allow_reporting",
        "updated_at",
    ]
    list_filter = ["requires_password", "is_read_only", "is_archived", "allow_reporting"]
    search_fields = ["academic_year__name", "academic_year__year"]
    readonly_fields = ["password_hash", "created_at", "updated_at"]
    raw_id_fields = ["academic_year"]


@admin.register(AcademicYearSystemState)
class AcademicYearSystemStateAdmin(admin.ModelAdmin):
    list_display = ["singleton_key", "active_academic_year", "updated_by", "updated_at"]
    readonly_fields = ["updated_at"]
    raw_id_fields = ["active_academic_year", "updated_by"]


@admin.register(AcademicYearStateLog)
class AcademicYearStateLogAdmin(admin.ModelAdmin):
    list_display = ["academic_year", "action", "performed_by", "created_at"]
    list_filter = ["action", "created_at"]
    search_fields = ["academic_year__name", "academic_year__year", "notes"]
    readonly_fields = ["created_at"]
    raw_id_fields = ["academic_year", "performed_by"]


class AcademicYearTransferCourseItemInline(admin.TabularInline):
    model = AcademicYearTransferCourseItem
    extra = 0
    raw_id_fields = ["source_course", "target_course"]
    readonly_fields = [
        "student_count",
        "enrollment_count",
        "receipt_count",
        "journal_entry_count",
        "status",
    ]


@admin.register(AcademicYearTransferBatch)
class AcademicYearTransferBatchAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "source_academic_year",
        "target_academic_year",
        "status",
        "created_by",
        "executed_at",
        "created_at",
    ]
    list_filter = ["status", "created_at", "executed_at"]
    search_fields = [
        "source_academic_year__name",
        "source_academic_year__year",
        "target_academic_year__name",
        "target_academic_year__year",
        "notes",
    ]
    readonly_fields = ["summary_json", "failure_reason", "executed_at", "created_at", "updated_at"]
    raw_id_fields = ["source_academic_year", "target_academic_year", "created_by"]
    inlines = [AcademicYearTransferCourseItemInline]


@admin.register(AcademicYearTransferLog)
class AcademicYearTransferLogAdmin(admin.ModelAdmin):
    list_display = ["batch", "level", "message", "created_at"]
    list_filter = ["level", "created_at"]
    search_fields = ["message"]
    readonly_fields = ["created_at"]
    raw_id_fields = ["batch"]
