from django.contrib import admin
from .models import Exam, ExamGrade

@admin.register(Exam)
class ExamAdmin(admin.ModelAdmin):
    list_display = ['name', 'classroom', 'subject', 'exam_date', 'max_grade', 'created_at']
    list_filter = ['classroom', 'subject', 'exam_date']
    search_fields = ['name', 'classroom__name', 'subject__name']

@admin.register(ExamGrade)
class ExamGradeAdmin(admin.ModelAdmin):
    list_display = ['exam', 'student', 'grade', 'entered_at']
    list_filter = ['exam', 'entered_at']
    search_fields = ['student__full_name', 'exam__name']