from django.urls import path
from . import views
from employ.decorators import require_employee_perm

app_name = 'students'

urlpatterns = [
    # الصفحة الرئيسية للطلاب
    path('', require_employee_perm('students_view')(views.StudentListView.as_view()), name='student'),
    path('', require_employee_perm('students_view')(views.StudentListView.as_view()), name='student_list'),
    path('branch/<int:academic_year_id>/<str:branch_name>/', require_employee_perm('students_view')(views.BranchStudentsView.as_view()), name='branch_students'),
    path('quick/<int:academic_year_id>/', require_employee_perm('students_view')(views.QuickStudentsView.as_view()), name='quick_students'),
    path('quick/', require_employee_perm('students_view')(views.QuickStudentsAllView.as_view()), name='quick_students_all'),
    path('search/', require_employee_perm('students_view')(views.StudentSearchView.as_view()), name='student_search'),

    # ملفات الطلاب الشخصية
    path('<int:student_id>/profile/', require_employee_perm('students_profile')(views.StudentProfileView.as_view()), name='student_profile'),
    path('<int:student_id>/warnings/add/', require_employee_perm('students_edit')(views.add_student_warning), name='add_student_warning'),
    path('<int:student_id>/statement/', require_employee_perm('students_statement')(views.StudentStatementView.as_view()), name='student_statement'),
    path('fix-arabic-mojibake/', views.fix_arabic_mojibake_records, name='fix_arabic_mojibake'),
    
    # إجراءات الطلاب
    path('<int:student_id>/register-course/', require_employee_perm('students_register_course')(views.register_course), name='register_course'),
    path('<int:student_id>/withdraw/', require_employee_perm('students_withdraw')(views.withdraw_student), name='withdraw_student'),
    path('update/<int:pk>/', require_employee_perm('students_edit')(views.UpdateStudentView.as_view()), name='update_student'),
    path('<int:student_id>/detailed-report/', require_employee_perm('students_profile')(views.StudentDetailedReportView.as_view()), name='student_detailed_report'),
        # 🟢 أضف هذين المسارين الجديدين
    # path('<int:student_id>/create-account/', views.create_student_account, name='create_student_account'),
    # path('<int:student_id>/create-course-account/', views.create_course_account, name='create_course_account'),
    # إدارة الطلاب
    path('create/', require_employee_perm('students_create')(views.CreateStudentView.as_view()), name='create_student'),
    path('delete/<int:pk>/', require_employee_perm('students_delete')(views.StudentDeleteView.as_view()), name='delete_student'),
    path('deactivate/<int:pk>/', require_employee_perm('students_edit')(views.DeactivateStudentView.as_view()), name='deactivate_student'),
    
    # صفحات أخرى
    path('groups/', require_employee_perm('students_view')(views.StudentGroupsView.as_view()), name='student_groups'),
    path('numbers/', require_employee_perm('students_view')(views.StudentNumbersView.as_view()), name='stu_num'),
    path('student-type-choice/', require_employee_perm('students_create')(views.student_type_choice), name='student_type_choice'),
    
    # الإيصال الفوري
    path('student/<int:student_id>/quick-receipt/', require_employee_perm('students_receipt')(views.quick_receipt), name='quick_receipt'),
    path('<int:student_id>/refund/', require_employee_perm('students_withdraw')(views.refund_student), name='refund_student'),
    path('student/<int:student_id>/update_discount/', require_employee_perm('students_edit')(views.update_student_discount), name='update_student_discount'),
    
    # التخصيص التلقائي
    path('auto-assign-students/', require_employee_perm('students_edit')(views.auto_assign_students_to_years), name='auto_assign_students'),
    path('all-regular/<int:academic_year_id>/', require_employee_perm('students_view')(views.AllRegularStudentsView.as_view()), name='all_regular_students'),
    path('student-cards-print/', views.StudentCardsPrintView.as_view(), name='student_cards_print'),
    path('student-cards-print/pdf/', views.student_cards_print_pdf, name='student_cards_print_pdf'),
    path('student-cards-print/pdf-by-branch/', views.student_cards_print_pdf_by_branch, name='student_cards_print_pdf_by_branch'),
    path('student-cards-print/pdf-by-classroom/', views.student_cards_print_pdf_by_classroom, name='student_cards_print_pdf_by_classroom'),
]
