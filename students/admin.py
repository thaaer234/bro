from django.contrib import admin
from .models import Student, StudentWarning


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'student_number','academic_year', 'branch', 'gender', 'is_active']
    list_filter = ['branch', 'gender', 'is_active', 'registration_date']
    search_fields = ['full_name', 'student_number', 'father_phone']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('المعلومات الأساسية', {
            'fields': ('full_name', 'student_number', 'gender', 'branch', 'birth_date', 'nationality','academic_year')
        }),
        ('معلومات الأب', {
            'fields': ('father_name', 'father_job', 'father_phone')
        }),
        ('معلومات الأم', {
            'fields': ('mother_name', 'mother_job', 'mother_phone')
        }),
        ('معلومات التواصل', {
            'fields': ('address', 'home_phone')
        }),
        ('معلومات أكاديمية', {
            'fields': ('tase3', 'previous_school', 'elementary_school')
        }),
        ('الحسم', {
            'fields': ('discount_percent', 'discount_amount', 'discount_reason')
        }),
        ('أخرى', {
            'fields': ('disease', 'how_knew_us', 'notes', 'is_active', 'added_by')
        }),
    )


@admin.register(StudentWarning)
class StudentWarningAdmin(admin.ModelAdmin):
    list_display = ['student', 'title', 'severity', 'is_active', 'created_at', 'created_by']
    list_filter = ['severity', 'is_active', 'created_at']
    search_fields = ['student__full_name', 'title', 'details']

