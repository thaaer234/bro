from django.urls import path

from employ.decorators import require_employee_perm, require_superuser

from . import views

app_name = 'quick'

urlpatterns = [
    path('academic-years/', require_employee_perm('students_view')(views.AcademicYearListView.as_view()), name='academic_year_list'),
    path('academic-years/create/', require_employee_perm('students_create')(views.AcademicYearCreateView.as_view()), name='academic_year_create'),
    path('academic-years/<int:pk>/close/', require_employee_perm('students_edit')(views.CloseAcademicYearView.as_view()), name='academic_year_close'),

    path('courses/', require_employee_perm('course_accounting_view')(views.QuickCourseListView.as_view()), name='course_list'),
    path('classrooms/', require_employee_perm('course_accounting_view')(views.QuickClassroomListView.as_view()), name='classroom_list'),
    path('classrooms/create/', require_employee_perm('course_accounting_edit')(views.QuickClassroomCreateView.as_view()), name='classroom_create'),
    path('classrooms/<int:pk>/update/', require_employee_perm('course_accounting_edit')(views.QuickClassroomUpdateView.as_view()), name='classroom_update'),
    path('courses/create/', require_employee_perm('course_accounting_create')(views.QuickCourseCreateView.as_view()), name='course_create'),
    path('courses/<int:pk>/', require_employee_perm('course_accounting_view')(views.QuickCourseDetailView.as_view()), name='course_detail'),
    path('courses/<int:pk>/update/', require_employee_perm('course_accounting_edit')(views.QuickCourseUpdateView.as_view()), name='course_update'),
    path('courses/<int:course_id>/sessions/', require_employee_perm('course_accounting_view')(views.QuickCourseSessionsManageView.as_view()), name='course_sessions_manage'),
    path('courses/<int:course_id>/time-options/', require_employee_perm('course_accounting_view')(views.QuickCourseTimeOptionsManageView.as_view()), name='course_time_options_manage'),
    path('courses/<int:course_id>/sessions/add/', require_employee_perm('course_accounting_edit')(views.quick_course_add_session), name='course_add_session'),
    path('courses/<int:course_id>/time-options/add/', require_employee_perm('course_accounting_edit')(views.quick_course_add_time_option), name='course_add_time_option'),
    path('courses/<int:course_id>/generate-schedule/', require_employee_perm('course_accounting_edit')(views.quick_course_generate_schedule), name='course_generate_schedule'),
    path('courses/generate-all-schedules/', require_employee_perm('course_accounting_edit')(views.quick_generate_all_schedules), name='generate_all_schedules'),
    path('courses/<int:course_id>/transfer-students/', require_employee_perm('course_accounting_edit')(views.quick_course_transfer_students), name='course_transfer_students'),
    path('courses/<int:course_id>/auto-assign/', require_employee_perm('course_accounting_edit')(views.quick_course_auto_assign_students), name='course_auto_assign_students'),
    path('sessions/<int:session_id>/students/', require_employee_perm('course_accounting_view')(views.QuickCourseSessionStudentsView.as_view()), name='course_session_students'),
    path('sessions/<int:session_id>/assign-students/', require_employee_perm('course_accounting_edit')(views.quick_course_session_assign_students), name='course_session_assign_students'),
    path('sessions/<int:session_id>/extend/', require_employee_perm('course_accounting_edit')(views.quick_course_session_extend), name='course_session_extend'),
    path('sessions/<int:session_id>/attendance/', require_employee_perm('attendance_take')(views.QuickCourseSessionAttendanceView.as_view()), name='course_session_attendance'),
    path('attendance/quick-courses/', require_employee_perm('attendance_view')(views.QuickCourseAttendanceDashboardView.as_view()), name='quick_course_attendance'),
    path('attendance/quick-courses/archive/', require_employee_perm('attendance_view')(views.QuickCourseAttendanceArchiveView.as_view()), name='quick_course_attendance_archive'),

    path('students/', require_employee_perm('students_view')(views.QuickStudentListView.as_view()), name='student_list'),
    path('students/create/', require_employee_perm('students_create')(views.QuickStudentCreateView.as_view()), name='student_create'),
    path('students/check-exists/', require_employee_perm('students_create')(views.quick_student_exists), name='student_exists'),
    path('students/<int:pk>/', require_employee_perm('students_profile')(views.QuickStudentDetailView.as_view()), name='student_detail'),
    path('students/<int:student_id>/register-course/', require_employee_perm('students_register_course')(views.register_quick_course), name='register_quick_course'),
    path('students/<int:pk>/update/', require_employee_perm('students_edit')(views.QuickStudentUpdateView.as_view()), name='student_update'),

    path('enrollments/create/', require_employee_perm('students_register_course')(views.QuickEnrollmentCreateView.as_view()), name='enrollment_create'),

    path('reports/outstanding/', require_employee_perm('accounting_outstanding')(views.QuickOutstandingCoursesView.as_view()), name='outstanding_courses'),
    path('reports/outstanding/<int:course_id>/', require_employee_perm('accounting_outstanding')(views.QuickOutstandingCourseDetailView.as_view()), name='outstanding_course_detail'),
    path('reports/outstanding/<int:course_id>/students/', require_employee_perm('accounting_outstanding')(views.QuickCourseStudentsView.as_view()), name='course_students'),
    path('reports/outstanding/export/quick-courses/', require_employee_perm('accounting_outstanding')(views.export_quick_outstanding_excel), name='export_quick_outstanding_excel'),
    path('reports/statements/export/quick-courses/', require_employee_perm('accounting_outstanding')(views.export_quick_course_statement_excel), name='export_quick_course_statement_excel'),
    path('reports/outstanding/print/quick-courses/', require_employee_perm('accounting_outstanding')(views.QuickOutstandingCoursesPrintView.as_view()), name='outstanding_courses_print'),
    path('reports/late-payments/', require_employee_perm('accounting_outstanding')(views.QuickLatePaymentCoursesView.as_view()), name='late_payment_courses'),
    path('reports/late-payments/<int:course_id>/', require_employee_perm('accounting_outstanding')(views.QuickLatePaymentCourseDetailView.as_view()), name='late_payment_course_detail'),
    path('reports/late-payments/<int:course_id>/bulk-withdraw/', require_employee_perm('students_withdraw')(views.bulk_withdraw_quick_students), name='bulk_withdraw_quick_students'),
    path('reports/late-payments/print/', require_employee_perm('accounting_outstanding')(views.QuickLatePaymentCoursesPrintView.as_view()), name='late_payment_courses_print'),
    path('reports/student-intersections/', require_employee_perm('students_view')(views.QuickStudentIntersectionView.as_view()), name='student_intersections'),
    path('reports/schedules/quick-courses/', require_employee_perm('course_accounting_view')(views.QuickCourseSchedulePrintView.as_view()), name='quick_course_schedule_print'),

    path('reports/duplicate-students/', require_superuser(views.quick_duplicate_students_report), name='duplicate_students_report'),
    path('reports/merge-students/', require_superuser(views.quick_duplicate_students_report), name='merge_students_tool'),
    path('reports/duplicate-students/print/', require_superuser(views.quick_duplicate_students_print), name='duplicate_students_print'),
    path('reports/duplicate-students/print/all/', require_superuser(views.quick_duplicate_students_full_print), name='duplicate_students_full_print'),
    path('reports/accounting-fix/', require_superuser(views.quick_accounting_fix_tool), name='accounting_fix_tool'),
    path('reports/withdrawal-fix/', require_superuser(views.quick_withdrawal_fix_tool), name='withdrawal_fix_tool'),

    path('student/<int:student_id>/profile/', require_employee_perm('students_profile')(views.QuickStudentProfileView.as_view()), name='student_profile'),
    path('student/<int:student_id>/statement/', require_employee_perm('students_statement')(views.QuickStudentStatementView.as_view()), name='student_statement'),
    path('student/<int:student_id>/quick-receipt/', require_employee_perm('students_receipt')(views.quick_student_quick_receipt), name='quick_student_quick_receipt'),
    path('student/<int:student_id>/update-discount/', require_employee_perm('students_edit')(views.update_quick_student_discount), name='update_quick_student_discount'),
    path('student/<int:student_id>/withdraw/', require_employee_perm('students_withdraw')(views.withdraw_quick_student), name='withdraw_quick_student'),
    path('student/<int:student_id>/refund/', require_employee_perm('students_withdraw')(views.refund_quick_student), name='refund_quick_student'),
    path('student/<int:student_id>/delete/', require_employee_perm('students_edit')(views.quick_delete_student), name='delete_student'),

    path('student-receipt/<int:receipt_id>/print/', require_employee_perm('students_receipt')(views.quick_student_receipt_print), name='student_receipt_print'),
    path('receipt/<int:receipt_id>/print/', require_employee_perm('students_receipt')(views.quick_student_receipt_print), name='quick_student_receipt_print'),
    path('students/<int:student_id>/receipts/print-multiple/', require_employee_perm('students_receipt')(views.quick_multiple_receipt_print), name='quick_multiple_receipt_print'),
    path('students/<int:student_id>/receipts/payload/', require_employee_perm('students_receipt')(views.quick_multiple_receipt_payload), name='quick_multiple_receipt_payload'),
    path('students/<int:student_id>/receipts/enqueue-print/', require_employee_perm('students_receipt')(views.quick_multiple_receipt_enqueue_print), name='quick_multiple_receipt_enqueue_print'),
    path('students/<int:student_id>/receipts/print-server/', require_employee_perm('students_receipt')(views.quick_multiple_receipt_server_print), name='quick_multiple_receipt_server_print'),
    path('agent/print-jobs/next/', views.quick_print_agent_next_job, name='quick_print_agent_next_job'),
    path('agent/print-jobs/<int:job_id>/update/', views.quick_print_agent_job_update, name='quick_print_agent_job_update'),
    path('students/<int:student_id>/quick-receipt/', require_employee_perm('students_receipt')(views.quick_student_quick_receipt), name='student_quick_receipt'),
    path('students/<int:student_id>/update-discount/', require_employee_perm('students_edit')(views.update_quick_student_discount), name='update_student_discount'),
    path('students/<int:student_id>/withdraw/', require_employee_perm('students_withdraw')(views.withdraw_quick_student), name='withdraw_student'),
    path('students/<int:student_id>/refund/', require_employee_perm('students_withdraw')(views.refund_quick_student), name='refund_student'),
    path('auto-assign-years/', require_employee_perm('students_edit')(views.auto_assign_academic_years), name='auto_assign_years'),
]
