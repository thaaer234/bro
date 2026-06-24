from django.contrib import admin
from .models import TechnicalReport


@admin.register(TechnicalReport)
class TechnicalReportAdmin(admin.ModelAdmin):
    list_display = ('report_number', 'employee', 'department', 'incident_date', 'is_resolved')
    list_filter = ('is_resolved', 'department', 'incident_date')
    search_fields = ('report_number', 'employee__username', 'employee__first_name', 'employee__last_name', 'issue_description')
    readonly_fields = ('report_date',)
    fieldsets = (
        ('المعلومات الأساسية', {
            'fields': ('employee', 'job_title', 'department', 'incident_date', 'report_date', 'report_number', 'is_resolved')
        }),
        ('تفاصيل المشكلة والحل', {
            'fields': ('issue_description', 'issue_impact', 'code_solution', 'employee_instructions', 'recommendations')
        }),
    )
