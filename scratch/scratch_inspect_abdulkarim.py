import os
import sys
import django

sys.path.append(r'c:\Users\THAAER\Desktop\project')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alyaman.settings')
django.setup()

sys.stdout.reconfigure(encoding='utf-8')

from students.models import Student
from accounts.models import Studentenrollment

print("=== INSPECTING STUDENTS CONTAINING 'عبد الكريم' OR 'عبدالكريم' OR 'المنجد' ===")
for s in Student.objects.filter(full_name__icontains="عبد الكريم") | Student.objects.filter(full_name__icontains="عبدالكريم") | Student.objects.filter(full_name__icontains="المنجد"):
    print(f"\nID={s.id} | student_id={s.student_id}")
    print(f"  Name: {s.full_name}")
    print(f"  Father: {s.father_name} | Mother: {s.mother_name}")
    print(f"  Phone: {s.phone} | Father Phone: {s.father_phone} | Mother Phone: {s.mother_phone}")
    print(f"  Is Active: {s.is_active} | Branch: {s.branch}")
    print(f"  Registration Date: {s.registration_date} | Academic Year: {s.academic_year}")
    print(f"  Created At: {s.created_at}")
    
    # Enrollments
    course_enrolls = Studentenrollment.objects.filter(student=s)
    print("  Course Enrollments:")
    for ce in course_enrolls:
        print(f"    * Course: {ce.course} (ID={ce.course.id})")
