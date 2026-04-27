from django.contrib import admin
from .models import (
    BiometricDevice,
    BiometricLog,
    Employee,
    EmployeeAttendance,
    EmployeePermission,
    HRHoliday,
    Teacher,
    Vacation,
)

@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    """
    نسخة آمنة لا تعتمد على حقول غير موجودة.
    إذا كانت لديك حقول مثل position/hire_date/salary لاحقًا، أضفها هنا.
    """
    list_display = ('full_name_display', 'username_display',)
    search_fields = ('user__first_name', 'user__last_name', 'user__username',)
    ordering = ('-id',)

    @admin.display(description='الاسم الكامل')
    def full_name_display(self, obj: Employee):
        if hasattr(obj, 'full_name') and obj.full_name:
            return obj.full_name
        u = getattr(obj, 'user', None)
        if u:
            return u.get_full_name() or u.get_username()
        return str(obj)

    @admin.display(description='اسم المستخدم')
    def username_display(self, obj: Employee):
        u = getattr(obj, 'user', None)
        return u.get_username() if u else ''


@admin.register(Teacher)
class TeacherAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'phone_number', 'salary_type', 'hourly_rate', 'monthly_salary', 'hire_date')
    list_filter = ('salary_type', 'hire_date')
    search_fields = ('full_name', 'phone_number')
    ordering = ('-created_at',)


@admin.register(Vacation)
class VacationAdmin(admin.ModelAdmin):
    list_display = ('employee', 'vacation_type', 'status', 'start_date', 'end_date', 'is_replacement_secured')
    list_filter = ('vacation_type', 'status', 'is_replacement_secured', 'start_date', 'end_date')
    search_fields = ('employee__user__first_name', 'employee__user__last_name', 'employee__user__username')
    ordering = ('-created_at',)


@admin.register(EmployeePermission)
class EmployeePermissionAdmin(admin.ModelAdmin):
    list_display = ('employee', 'permission', 'is_granted', 'granted_by', 'granted_at')
    list_filter = ('permission', 'is_granted', 'granted_at')
    search_fields = ('employee__user__first_name', 'employee__user__last_name', 'employee__user__username')
    ordering = ('-granted_at',)


@admin.register(BiometricDevice)
class BiometricDeviceAdmin(admin.ModelAdmin):
    list_display = ('name', 'serial', 'ip', 'port', 'location', 'active', 'last_synced_at', 'created_at')
    list_filter = ('active', 'created_at', 'last_synced_at')
    search_fields = ('name', 'serial', 'ip', 'location')
    readonly_fields = ('created_at', 'last_synced_at')
    ordering = ('name',)


@admin.register(BiometricLog)
class BiometricLogAdmin(admin.ModelAdmin):
    list_display = ('punch_time', 'device_user_id', 'employee', 'punch_type', 'device', 'created_at')
    list_filter = ('punch_type', 'device', 'created_at', 'punch_time')
    search_fields = (
        'device_user_id',
        'employee__user__first_name',
        'employee__user__last_name',
        'employee__user__username',
        'device__name',
        'device__serial',
    )
    readonly_fields = ('created_at',)
    autocomplete_fields = ('employee', 'device')
    date_hierarchy = 'punch_time'
    list_select_related = ('employee__user', 'device')
    ordering = ('-punch_time',)


@admin.register(EmployeeAttendance)
class EmployeeAttendanceAdmin(admin.ModelAdmin):
    list_display = (
        'date',
        'employee',
        'status',
        'check_in',
        'check_out',
        'review_status',
        'source',
        'is_manually_adjusted',
    )
    list_filter = ('status', 'review_status', 'source', 'is_manually_adjusted', 'date')
    search_fields = (
        'employee__user__first_name',
        'employee__user__last_name',
        'employee__user__username',
        'employee__biometric_user_id',
        'notes',
        'review_notes',
    )
    readonly_fields = ('updated_at', 'reviewed_at')
    autocomplete_fields = ('employee', 'reviewed_by')
    date_hierarchy = 'date'
    list_select_related = ('employee__user', 'reviewed_by')
    ordering = ('-date', 'employee__user__first_name')


@admin.register(HRHoliday)
class HRHolidayAdmin(admin.ModelAdmin):
    list_display = ('name', 'start_date', 'end_date', 'overtime_multiplier', 'is_paid', 'is_active')
    list_filter = ('is_active', 'is_paid', 'start_date', 'end_date')
    search_fields = ('name', 'notes')
    ordering = ('-start_date', 'name')
