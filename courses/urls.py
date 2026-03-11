from django.contrib import admin
from django.urls import path
from . import views
from employ.decorators import require_employee_perm

app_name = "courses"

urlpatterns = [
    path('courses/', require_employee_perm('courses_view')(views.courses.as_view()), name="courses"),
    path('subjects/', require_employee_perm('courses_view')(views.SubjectListView.as_view()), name='subject_list'),
    path('subjects/add/', require_employee_perm('courses_create')(views.SubjectCreateView.as_view()), name='subject_create'),
    path('subjects/<int:pk>/edit/', require_employee_perm('courses_edit')(views.SubjectUpdateView.as_view()), name='subject_update'),
    path('subjects/<int:pk>/delete/', require_employee_perm('courses_delete')(views.SubjectDeleteView.as_view()), name='subject_delete'),
]