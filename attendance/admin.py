from django.contrib import admin
from .models import Attendance, TeacherAttendance

@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ['student', 'classroom', 'date', 'status', 'notes']
    list_filter = ['date', 'status', 'classroom']
    search_fields = ['student__full_name', 'notes']
    date_hierarchy = 'date'

@admin.register(TeacherAttendance)
class TeacherAttendanceAdmin(admin.ModelAdmin):
    list_display = ['teacher', 'date', 'status', 'session_count', 'has_salary_accrual']
    list_filter = ['date', 'status']
    search_fields = ['teacher__full_name', 'notes']
    date_hierarchy = 'date'
    
    def has_salary_accrual(self, obj):
        return obj.has_salary_accrual()
    has_salary_accrual.boolean = True
    has_salary_accrual.short_description = 'له قيد راتب'