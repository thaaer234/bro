from django.contrib import admin

from .models import (
    AcademicYear,
    QuickCourse,
    QuickCourseWithdrawal,
    QuickCourseTimeOption,
    QuickCourseSession,
    QuickCourseSessionAttendance,
    QuickCourseSessionEnrollment,
    QuickEnrollment,
    QuickStudent,
    QuickStudentReceipt,
)


@admin.register(AcademicYear)
class AcademicYearAdmin(admin.ModelAdmin):
    list_display = ['name', 'year', 'start_date', 'end_date', 'is_active', 'is_closed', 'created_at']
    list_filter = ['is_active', 'is_closed', 'start_date', 'created_at']
    search_fields = ['name', 'year']
    readonly_fields = ['created_at', 'updated_at', 'closed_at']
    date_hierarchy = 'start_date'


@admin.register(QuickCourse)
class QuickCourseAdmin(admin.ModelAdmin):
    list_display = ['name', 'course_type', 'academic_year', 'price', 'duration_weeks', 'is_active', 'created_at']
    list_filter = ['course_type', 'is_active', 'academic_year', 'created_at']
    search_fields = ['name', 'name_ar', 'description']
    readonly_fields = ['created_at', 'updated_at']
    raw_id_fields = ['academic_year', 'cost_center', 'created_by']
    list_editable = ['is_active', 'price']


@admin.register(QuickStudent)
class QuickStudentAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'phone', 'student_type', 'course_track', 'academic_year', 'is_active', 'created_at', 'balance']
    list_filter = ['student_type', 'course_track', 'is_active', 'academic_year', 'created_at']
    search_fields = ['full_name', 'phone', 'email', 'student__full_name']
    readonly_fields = ['created_at', 'updated_at', 'balance', 'auto_academic_year']
    raw_id_fields = ['student', 'academic_year', 'created_by']
    list_editable = ['is_active']


@admin.register(QuickEnrollment)
class QuickEnrollmentAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'student', 'course', 'enrollment_date', 'net_amount', 'is_completed', 'created_at']
    list_filter = ['is_completed', 'enrollment_date', 'payment_method', 'created_at']
    search_fields = ['student__full_name', 'course__name']
    readonly_fields = ['created_at', 'updated_at', 'calculated_net_amount']
    raw_id_fields = ['student', 'course']
    list_editable = ['is_completed']


@admin.register(QuickCourseWithdrawal)
class QuickCourseWithdrawalAdmin(admin.ModelAdmin):
    list_display = ['student', 'course', 'withdrawn_at', 'withdrawn_by', 'created_at']
    list_filter = ['course', 'withdrawn_at', 'created_at']
    search_fields = ['student__full_name', 'course__name', 'withdrawal_reason']
    readonly_fields = ['created_at', 'updated_at', 'withdrawn_at']
    raw_id_fields = ['student', 'course', 'withdrawn_by']


@admin.register(QuickStudentReceipt)
class QuickStudentReceiptAdmin(admin.ModelAdmin):
    list_display = ['receipt_number', 'student_name', 'course_name', 'paid_amount', 'date', 'is_printed', 'created_at']
    list_filter = ['is_printed', 'payment_method', 'date', 'created_at']
    search_fields = ['receipt_number', 'student_name', 'course_name']
    readonly_fields = ['created_at', 'updated_at', 'receipt_number']
    raw_id_fields = ['quick_student', 'course', 'quick_enrollment', 'journal_entry', 'created_by']
    list_editable = ['is_printed']
    date_hierarchy = 'date'

    def save_model(self, request, obj, form, change):
        if not obj.receipt_number:
            obj.generate_receipt_number()
        super().save_model(request, obj, form, change)


@admin.register(QuickCourseSession)
class QuickCourseSessionAdmin(admin.ModelAdmin):
    list_display = ['title', 'course', 'start_date', 'end_date', 'start_time', 'capacity', 'is_active']
    list_filter = ['is_active', 'course__course_type', 'start_date']
    search_fields = ['title', 'code', 'course__name', 'room_name']
    raw_id_fields = ['course', 'created_by']


@admin.register(QuickCourseTimeOption)
class QuickCourseTimeOptionAdmin(admin.ModelAdmin):
    list_display = ['title', 'course', 'start_date', 'end_date', 'start_time', 'max_capacity', 'priority', 'is_active']
    list_filter = ['is_active', 'course__course_type', 'start_date']
    search_fields = ['title', 'course__name', 'meeting_days']
    raw_id_fields = ['course', 'preferred_room', 'created_by']


@admin.register(QuickCourseSessionEnrollment)
class QuickCourseSessionEnrollmentAdmin(admin.ModelAdmin):
    list_display = ['session', 'enrollment', 'assigned_by', 'assigned_at']
    list_filter = ['session__course', 'session__start_date']
    search_fields = ['session__title', 'enrollment__student__full_name', 'enrollment__course__name']
    raw_id_fields = ['session', 'enrollment', 'assigned_by']


@admin.register(QuickCourseSessionAttendance)
class QuickCourseSessionAttendanceAdmin(admin.ModelAdmin):
    list_display = ['session', 'enrollment', 'attendance_date', 'day_number', 'status']
    list_filter = ['status', 'attendance_date', 'session__course']
    search_fields = ['session__title', 'enrollment__student__full_name', 'notes']
    raw_id_fields = ['session', 'enrollment', 'created_by']
