from django.urls import path
from . import views
from employ.decorators import require_employee_perm


app_name = "classroom"

urlpatterns = [
    path('classroom/', require_employee_perm('classroom_view')(views.ClassroomListView.as_view()), name="classroom"),
    path('classroom-cards-print/', require_employee_perm('classroom_view')(views.ClassroomCardsPrintView.as_view()), name="classroom_cards_print"),
    path('classroom-cards-print/pdf/', require_employee_perm('classroom_view')(views.classroom_cards_print_pdf), name="classroom_cards_print_pdf"),
    path('create_classroom/', require_employee_perm('classroom_create')(views.CreateClassroomView.as_view()), name="create_classroom"),
    path('assign-students/<int:classroom_id>/', require_employee_perm('classroom_assign')(views.AssignStudentsView.as_view()), name='assign_students'),
    path('assign-students/<int:classroom_id>/remove/<int:student_id>/', require_employee_perm('classroom_assign')(views.UnassignStudentView.as_view()), name='unassign_student'),
    path('classroom/<int:classroom_id>/students/', require_employee_perm('classroom_students')(views.ClassroomStudentsView.as_view()), name='classroom_students'),
    path('classroom/<int:classroom_id>/delete/', require_employee_perm('classroom_delete')(views.DeleteClassroomView.as_view()), name='delete_classroom'),
    path('classroom/<int:classroom_id>/subjects/', require_employee_perm('classroom_subjects')(views.ClassroomSubjectListView.as_view()), name='classroom_subject_list'),
    path('classroom/<int:classroom_id>/subjects/add/', require_employee_perm('classroom_subjects')(views.ClassroomSubjectCreateView.as_view()), name='classroom_subject_create'),
    path('classroom/<int:classroom_id>/students/export/', require_employee_perm('classroom_export')(views.export_classroom_students_to_excel), name='export_classroom_students'),
    path('classrooms/', require_employee_perm('classroom_view')(views.ClassroomListView.as_view()), name='classroom_list'),
    path('<int:classroom_id>/assign-students/', require_employee_perm('classroom_assign')(views.AssignStudentsView.as_view()), name='assign_students'),
    path('<int:classroom_id>/edit/', require_employee_perm('classroom_edit')(views.UpdateClassroomView.as_view()), name='edit_classroom'),
    path('<int:classroom_id>/subjects/<int:pk>/edit/', require_employee_perm('classroom_subjects')(views.ClassroomSubjectUpdateView.as_view()), name='classroom_subject_edit'),
    path('classroom/<int:classroom_id>/subjects/<int:pk>/delete/', require_employee_perm('classroom_subjects')(views.ClassroomSubjectDeleteView.as_view()), name='classroom_subject_delete'),
]
