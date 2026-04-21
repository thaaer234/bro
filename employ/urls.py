from django.contrib import admin
from django.urls import path
from . import views
from employ.decorators import require_employee_perm

app_name = "employ"

urlpatterns = [
    # إدارة المدرسين
    path('teachers/', require_employee_perm('teachers_view')(views.teachers.as_view()), name="teachers"),
    path('teacher-cards-print/', require_employee_perm('teachers_view')(views.TeacherCardsPrintView.as_view()), name="teacher_cards_print"),
    path('teacher-cards-print/pdf/', require_employee_perm('teachers_view')(views.teacher_cards_print_pdf), name="teacher_cards_print_pdf"),
    path('delete/<int:pk>/', require_employee_perm('teachers_delete')(views.TeacherDeleteView.as_view()), name="delete_teacher"),
    path('teacher/<int:pk>/', require_employee_perm('teachers_profile')(views.TeacherProfileView.as_view()), name='teacher_profile'),
    path('teacher/update/<int:pk>/', require_employee_perm('teachers_edit')(views.TeacherUpdateView.as_view()), name='update_teacher'),
    path('employee/<int:pk>/', require_employee_perm('hr_profile')(views.EmployeeProfileView.as_view()), name='employee_profile'),
    # path('employee/<int:pk>/pay-salary/', require_employee_perm('hr_salary_pay')(views.PayEmployeeSalaryView.as_view()), name='pay_employee_salary'),
    path('employee/<int:pk>/permissions/', require_employee_perm('hr_permissions')(views.EmployeePermissionsView.as_view()), name='employee_permissions'),
    path('employee/<int:pk>/cash-account/create/', require_employee_perm('hr_permissions')(views.CreateEmployeeCashAccountView.as_view()), name='create_employee_cash_account'),
    path('hr/', require_employee_perm('hr_view')(views.hr.as_view()), name="hr"),
    path('hr/settings/', require_employee_perm('hr_edit')(views.HRSettingsView.as_view()), name='hr_settings'),
    path('hr/settings/departments/create/', require_employee_perm('hr_edit')(views.DepartmentCreateView.as_view()), name='department_create'),
    path('hr/settings/job-titles/create/', require_employee_perm('hr_edit')(views.JobTitleCreateView.as_view()), name='job_title_create'),
    path('hr/settings/shifts/create/', require_employee_perm('hr_edit')(views.ShiftCreateView.as_view()), name='shift_create'),
    path('hr/settings/policies/create/', require_employee_perm('hr_edit')(views.AttendancePolicyCreateView.as_view()), name='attendance_policy_create'),
    path('hr/settings/salary-rules/create/', require_employee_perm('hr_edit')(views.SalaryRuleCreateView.as_view()), name='salary_rule_create'),
    path('create/', require_employee_perm('teachers_create')(views.CreateTeacherView.as_view()), name="create"),
    path('delete-employee/<int:pk>/', require_employee_perm('hr_delete')(views.EmployeeDeleteView.as_view()), name='employee_delete'),
    path('register/', require_employee_perm('hr_create')(views.EmployeeCreateView.as_view()), name='employee_register'),
    path('update/', require_employee_perm('hr_view')(views.select_employee), name='select_employee'),
    path('update/<int:pk>/', require_employee_perm('hr_edit')(views.EmployeeUpdateView.as_view()), name='employee_update'),
    path('biometric/', require_employee_perm('hr_view')(views.BiometricDashboardView.as_view()), name='biometric_dashboard'),
    path('biometric/devices/create/', require_employee_perm('hr_edit')(views.BiometricDeviceCreateView.as_view()), name='biometric_device_create'),
    path('biometric/import/', require_employee_perm('hr_edit')(views.BiometricImportView.as_view()), name='biometric_import'),
    path('biometric/push/', views.BiometricPushApiView.as_view(), name='biometric_push'),
    path('attendance/employees/', require_employee_perm('hr_view')(views.EmployeeAttendanceListView.as_view()), name='attendance_list'),
    path('attendance/employees/rebuild/', require_employee_perm('hr_edit')(views.EmployeeAttendanceRebuildView.as_view()), name='attendance_rebuild'),
    path('attendance/employees/<int:pk>/edit/', require_employee_perm('hr_edit')(views.EmployeeAttendanceUpdateView.as_view()), name='attendance_update'),
    path('attendance/employees/summary/', require_employee_perm('hr_view')(views.AttendanceSummaryView.as_view()), name='attendance_summary'),
    path('payroll/', require_employee_perm('hr_salary')(views.PayrollDashboardView.as_view()), name='payroll_dashboard'),
    path('payroll/periods/create/', require_employee_perm('hr_salary')(views.PayrollPeriodCreateView.as_view()), name='payroll_period_create'),
    path('payroll/periods/<int:pk>/generate/', require_employee_perm('hr_salary')(views.PayrollGenerateView.as_view()), name='payroll_generate'),
    path('reports/hr/', require_employee_perm('reports_attendance')(views.EmployeeReportsView.as_view()), name='employee_reports'),
    
    # الإجازات
    path('vacations/', require_employee_perm('hr_vacations')(views.VacationListView.as_view()), name='vacation_list'),
    path('vacations/create/', require_employee_perm('hr_vacations')(views.VacationCreateView.as_view()), name='vacation_create'),
    path('vacations/update/<int:pk>/', require_employee_perm('hr_vacations')(views.VacationUpdateView.as_view()), name='vacation_update'),
    
    # رواتب المدرسين
    # path('teacher/<int:pk>/pay-salary/', require_employee_perm('teachers_salary_pay')(views.PayTeacherSalaryView.as_view()), name='pay_teacher_salary'),
    # path('teacher/<int:pk>/create-accrual/', require_employee_perm('teachers_salary_accrual')(views.CreateTeacherAccrualView.as_view()), name='create_teacher_accrual'),
    path('salary-management/', require_employee_perm('teachers_salary')(views.SalaryManagementView.as_view()), name='salary_management'),
    
    # سلف المدرسين
    path('teacher/<int:teacher_id>/advance/create/', require_employee_perm('teachers_advance_create')(views.TeacherAdvanceCreateView.as_view()), name='teacher_advance_create'),
    path('teacher/<int:teacher_id>/advances/', require_employee_perm('teachers_advance')(views.TeacherAdvanceListView.as_view()), name='teacher_advance_list'),
    path('teacher/<int:teacher_id>/advance/<int:pk>/edit/', require_employee_perm('teachers_advance')(views.TeacherAdvanceUpdateView.as_view()), name='teacher_advance_edit'),
    
    # سلف الموظفين
    path('employee/advance/create/', require_employee_perm('hr_advances_create')(views.EmployeeAdvanceCreateView.as_view()), name='employee_advance_create'),
    path('employee/advance/list/', require_employee_perm('hr_advances')(views.EmployeeAdvanceListView.as_view()), name='employee_advance_list'),
    
    # صفحة عدم الصلاحية
    path("denied/", views.no_permission, name="no_permission"),


     path('teacher/<int:pk>/create-advance-account/', 
         views.CreateTeacherAdvanceAccountView.as_view(), 
         name='create_teacher_advance_account'),
    
    # الرواتب اليدوية
    path('teacher/<int:pk>/add-manual-salary/', 
         views.AddManualSalaryView.as_view(), 
         name='add_manual_salary'),
    path('manual-salary/<int:pk>/edit/', 
         views.EditManualSalaryView.as_view(), 
         name='edit_manual_salary'),
    path('manual-salary/<int:pk>/view/', 
         views.ViewManualSalaryView.as_view(), 
         name='view_manual_salary'),
    path('manual-salary/<int:pk>/pay/', 
         views.PayManualSalaryView.as_view(), 
         name='pay_manual_salary'),
]
