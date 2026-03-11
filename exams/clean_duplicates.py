# exams/clean_duplicates.py
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'your_project.settings')
django.setup()

from exams.models import exams
from django.db.models import Count

def clean_exams_duplicates():
    """حذف البيانات المكررة في جدول العلامات"""
    
    # العثور على السجلات المكررة
    duplicates = exams.objects.values('student', 'subject', 'exam_type').annotate(
        count=Count('id')
    ).filter(count__gt=1)
    
    print(f"تم العثور على {duplicates.count()} مجموعة مكررة")
    
    for dup in duplicates:
        student_id = dup['student']
        subject_id = dup['subject']
        exam_type = dup['exam_type']
        
        # الحصول على جميع السجلات المكررة
        duplicate_examss = exams.objects.filter(
            student_id=student_id,
            subject_id=subject_id,
            exam_type=exam_type
        ).order_by('-date')  # نأخذ أحدث سجل
        
        # الاحتفاظ بأحدث سجل وحذف الباقي
        keep_exams = duplicate_examss.first()
        delete_examss = duplicate_examss.exclude(id=keep_exams.id)
        
        print(f"حذف {delete_examss.count()} سجل مكرر للطالب {keep_exams.student.full_name}")
        delete_examss.delete()
    
    print("تم تنظيف البيانات المكررة بنجاح")

if __name__ == "__main__":
    clean_exams_duplicates()