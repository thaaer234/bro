from django.contrib import admin
from .models import AcademicYear, QuickCourse, QuickStudent, QuickEnrollment, QuickStudentReceipt

@admin.register(AcademicYear)
class AcademicYearAdmin(admin.ModelAdmin):
    list_display = ['name', 'year', 'start_date', 'end_date', 'is_active', 'is_closed', 'created_at']
    list_filter = ['is_active', 'is_closed', 'start_date', 'created_at']
    search_fields = ['name', 'year']
    readonly_fields = ['created_at', 'updated_at', 'closed_at']
    date_hierarchy = 'start_date'
    fieldsets = (
        ('المعلومات الأساسية', {
            'fields': ('name', 'year', 'start_date', 'end_date')
        }),
        ('الحالة', {
            'fields': ('is_active', 'is_closed')
        }),
        ('معلومات الإقفال', {
            'fields': ('closed_by', 'closed_at'),
            'classes': ('collapse',)
        }),
        ('التواريخ', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

@admin.register(QuickCourse)
class QuickCourseAdmin(admin.ModelAdmin):
    list_display = ['name', 'name_ar', 'course_type', 'academic_year', 'price', 'duration_weeks', 'is_active', 'created_at']
    list_filter = ['course_type', 'is_active', 'academic_year', 'created_at']
    search_fields = ['name', 'name_ar', 'description']
    readonly_fields = ['created_at', 'updated_at']
    raw_id_fields = ['academic_year', 'cost_center', 'created_by']
    list_editable = ['is_active', 'price']
    fieldsets = (
        ('المعلومات الأساسية', {
            'fields': ('name', 'name_ar', 'course_type', 'academic_year')
        }),
        ('التفاصيل المالية', {
            'fields': ('price', 'cost_center')
        }),
        ('معلومات الدورة', {
            'fields': ('duration_weeks', 'hours_per_week', 'description')
        }),
        ('الحالة والإعدادات', {
            'fields': ('is_active', 'created_by')
        }),
        ('التواريخ', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

@admin.register(QuickStudent)
class QuickStudentAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'phone', 'student_type', 'course_track', 'academic_year', 'is_active', 'created_at', 'balance']
    list_filter = ['student_type', 'course_track', 'is_active', 'academic_year', 'created_at']
    search_fields = ['full_name', 'phone', 'email', 'student__full_name']
    readonly_fields = ['created_at', 'updated_at', 'balance', 'auto_academic_year']
    raw_id_fields = ['student', 'academic_year', 'created_by']
    list_editable = ['is_active']
    fieldsets = (
        ('المعلومات الأساسية', {
            'fields': ('student', 'full_name', 'phone', 'email')
        }),
        ('النوع والفصل', {
            'fields': ('student_type', 'course_track', 'academic_year')
        }),
        ('معلومات إضافية', {
            'fields': ('notes', 'is_active', 'created_by')
        }),
        ('المعلومات المالية', {
            'fields': ('balance', 'auto_academic_year'),
            'classes': ('collapse',)
        }),
        ('التواريخ', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

@admin.register(QuickEnrollment)
class QuickEnrollmentAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'student', 'course', 'enrollment_date', 'net_amount', 'is_completed', 'created_at']
    list_filter = ['is_completed', 'enrollment_date', 'payment_method', 'created_at']
    search_fields = ['student__full_name', 'course__name']
    readonly_fields = ['created_at', 'updated_at', 'calculated_net_amount']
    raw_id_fields = ['student', 'course']
    list_editable = ['is_completed']
    fieldsets = (
        ('المعلومات الأساسية', {
            'fields': ('student', 'course', 'enrollment_date')
        }),
        ('المعلومات المالية', {
            'fields': ('total_amount', 'net_amount', 'discount_percent', 'discount_amount', 'payment_method')
        }),
        ('حالة التسجيل', {
            'fields': ('is_completed', 'completion_date')
        }),
        ('الحقول المحسوبة', {
            'fields': ('calculated_net_amount',),
            'classes': ('collapse',)
        }),
        ('التواريخ', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

@admin.register(QuickStudentReceipt)
class QuickStudentReceiptAdmin(admin.ModelAdmin):
    list_display = ['receipt_number', 'student_name', 'course_name', 'paid_amount', 'date', 'is_printed', 'created_at']
    list_filter = ['is_printed', 'payment_method', 'date', 'created_at']
    search_fields = ['receipt_number', 'student_name', 'course_name']
    readonly_fields = ['created_at', 'updated_at', 'receipt_number']
    raw_id_fields = ['quick_student', 'course', 'quick_enrollment', 'journal_entry', 'created_by']
    list_editable = ['is_printed']
    date_hierarchy = 'date'
    fieldsets = (
        ('المعلومات الأساسية', {
            'fields': ('receipt_number', 'date', 'quick_student', 'student_name')
        }),
        ('معلومات الدورة', {
            'fields': ('course', 'course_name', 'quick_enrollment')
        }),
        ('المعلومات المالية', {
            'fields': ('amount', 'paid_amount', 'discount_percent', 'discount_amount', 'payment_method')
        }),
        ('الحالة والإعدادات', {
            'fields': ('is_printed', 'notes', 'journal_entry', 'created_by')
        }),
        ('التواريخ', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def save_model(self, request, obj, form, change):
        """توليد رقم الإيصال تلقائياً عند الإنشاء"""
        if not obj.receipt_number:
            obj.generate_receipt_number()
        super().save_model(request, obj, form, change)
