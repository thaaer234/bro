from django.urls import path
from . import views
from employ.decorators import require_employee_perm

app_name = "attendance"

urlpatterns = [
    # حضور الطلاب
    path('attendance/', require_employee_perm('attendance_view')(views.attendance.as_view()), name="attendance"),
    path('attendance/detail/<int:classroom_id>/<str:date>/', require_employee_perm('attendance_view')(views.AttendanceDetailView.as_view()), name='attendance_detail'),
    path('attendance/export/<int:classroom_id>/<str:date>/', require_employee_perm('attendance_export')(views.export_attendance_to_excel), name='export_attendance'),
    path('api/students/', require_employee_perm('attendance_view')(views.get_students), name='get_students'),
    path('attendance/take/', require_employee_perm('attendance_take')(views.TakeAttendanceView.as_view()), name='take_attendance'),
    path('attendance/update/<int:classroom_id>/<str:date>/', require_employee_perm('attendance_edit')(views.UpdateAttendanceView.as_view()), name='update_attendance'),
    path('attendance/delete/<int:classroom_id>/<str:date>/', require_employee_perm('attendance_edit')(views.DeleteAttendanceView.as_view()), name='delete_attendance'),
    path('attendance/tools/', require_employee_perm('attendance_edit')(views.AttendanceToolsView.as_view()), name='attendance_tools'),
    path('take-students-attendance/', require_employee_perm('attendance_take')(views.TakeStudentsAttendanceView.as_view()), name='take_students_attendance'),
    
    # حضور المدرسين
    path('teacher-attendance/', require_employee_perm('attendance_teacher_view')(views.TeacherAttendanceView.as_view()), name='teacher_attendance'),
    path('take-teacher-attendance/', require_employee_perm('attendance_teacher_take')(views.TakeTeacherAttendanceView.as_view()), name='take_teacher_attendance'),
    path('teacher-attendance/date/<str:date>/', require_employee_perm('attendance_teacher_view')(views.teacher_attendance_by_date), name='teacher_attendance_by_date'),
    path('teacher-attendance/update/<int:attendance_id>/', require_employee_perm('attendance_edit')(views.UpdateTeacherAttendanceView.as_view()), name='update_teacher_attendance'),
    
    # الحذف
    path('teacher-attendance/delete-daily/<str:date_str>/', 
         views.DeleteDailyTeacherAttendanceView.as_view(), 
         name='delete_daily_attendance'),
#     path('delete-daily-with-accruals/<str:date_str>/', 
     #     require_employee_perm('attendance_edit')(views.delete_daily_attendance_with_accruals), 
     #     name='delete_daily_with_accruals'),
    
    # التصحيح
#     path('debug-teacher-attendance/', require_employee_perm('attendance_edit')(views.debug_teacher_attendance), name='debug_teacher_attendance'),
#     path('debug-teacher-attendance/<int:teacher_id>/', require_employee_perm('attendance_edit')(views.debug_teacher_attendance), name='debug_teacher_attendance_single'),
#     path('fix-half-session-accruals/', require_employee_perm('attendance_edit')(views.fix_half_session_accruals), name='fix_half_session_accruals'),
    path('import-teacher-attendance/', require_employee_perm('attendance_edit')(views.ImportTeacherAttendanceView.as_view()), 
         name='import_teacher_attendance'),
    path('export-attendance-template/', require_employee_perm('attendance_export')(views.ExportAttendanceTemplateView.as_view()), 
         name='export_attendance_template'),
    path('get-teachers-list/', require_employee_perm('attendance_view')(views.GetTeachersListView.as_view()), 
         name='get_teachers_list'),
]
