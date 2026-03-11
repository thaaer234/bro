from django.urls import path
from . import views
from employ.decorators import require_employee_perm

app_name = 'exams'

urlpatterns = [
    path('', require_employee_perm('exams_view')(views.exams_dashboard), name='dashboard'),
    
    # مسارات الاختبارات
    path('<int:classroom_id>/exams/', require_employee_perm('exams_view')(views.exam_list), name='exam_list'),
    path('exam/<int:exam_id>/', require_employee_perm('exams_view')(views.exam_detail), name='exam_detail'),
    path('<int:classroom_id>/exams/create/', require_employee_perm('exams_edit')(views.create_exam), name='create_exam'),
    path('exam/<int:exam_id>/edit/', require_employee_perm('exams_edit')(views.edit_exam), name='edit_exam'),
    path('exam/<int:exam_id>/grades/', require_employee_perm('exams_view')(views.view_exam_grades), name='view_exam_grades'),
    path('exam/<int:exam_id>/grades/edit/', require_employee_perm('exams_edit')(views.edit_exam_grades), name='edit_exam_grades'),
    path('exam/<int:exam_id>/export/', require_employee_perm('exams_export')(views.export_exam_grades), name='export_exam_grades'),
    path('exam/<int:exam_id>/print/', require_employee_perm('exams_print')(views.print_exam_grades), name='print_exam_grades'),
    path('exam/<int:exam_id>/stats/', require_employee_perm('exams_view')(views.exam_stats), name='exam_stats'),
    path('exam/<int:exam_id>/delete/', require_employee_perm('exams_edit')(views.delete_exam), name='delete_exam'),
]
