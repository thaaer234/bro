import os
import sys
import django

sys.path.append(r'c:\Users\THAAER\Desktop\project')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alyaman.settings')
django.setup()

sys.stdout.reconfigure(encoding='utf-8')

from classroom.models import Classroom, Classroomenrollment
from students.models import Student
from accounts.models import Studentenrollment, Course
from quick.models import QuickCourse, QuickEnrollment

print("=== ALL COURSES (accounts.Course) ===")
for c in Course.objects.all():
    print(f"ID={c.id} | Name={c.name} | Active={c.is_active if hasattr(c, 'is_active') else 'N/A'}")

print("\n=== ALL QUICK COURSES (quick.QuickCourse) ===")
for c in QuickCourse.objects.all():
    print(f"ID={c.id} | Name={c.name} | Active={c.is_active}")

print("\n=== SEARCHING FOR ALL ENROLLMENTS OF 'لانا عجاج' ===")
for s in Student.objects.filter(full_name__icontains="لانا").filter(full_name__icontains="عجاج"):
    print(f"\nStudent ID={s.id} | Name={s.full_name} | is_active={s.is_active}")
    print("  - Studentenrollment:")
    for se in Studentenrollment.objects.filter(student=s):
        print(f"    * Course: {se.course} (ID={se.course.id}) | Completed: {se.is_completed if hasattr(se, 'is_completed') else 'N/A'}")
    print("  - Classroomenrollment:")
    for cle in Classroomenrollment.objects.filter(student=s):
        print(f"    * Classroom: {cle.classroom.name} (ID={cle.classroom.id}) | Course: {cle.classroom.course}")
    print("  - QuickEnrollment:")
    if hasattr(s, 'quick_student_profile'):
        try:
            for qe in QuickEnrollment.objects.filter(student=s.quick_student_profile):
                print(f"    * Quick Course: {qe.course} (ID={qe.course.id})")
        except Exception as e:
            print(f"    * Error querying QuickEnrollment: {e}")

print("\n=== SEARCHING FOR ALL ENROLLMENTS OF STUDENTS WITH 'عبد الكريم' ===")
for s in Student.objects.filter(full_name__icontains="عبد الكريم") | Student.objects.filter(full_name__icontains="عبدالبريم") | Student.objects.filter(full_name__icontains="عبدالكريم"):
    print(f"\nStudent ID={s.id} | Name={s.full_name} | is_active={s.is_active}")
    print("  - Studentenrollment:")
    for se in Studentenrollment.objects.filter(student=s):
        print(f"    * Course: {se.course} (ID={se.course.id})")
    print("  - Classroomenrollment:")
    for cle in Classroomenrollment.objects.filter(student=s):
        print(f"    * Classroom: {cle.classroom.name} (ID={cle.classroom.id}) | Course: {cle.classroom.course}")
    print("  - QuickEnrollment:")
    if hasattr(s, 'quick_student_profile'):
        try:
            for qe in QuickEnrollment.objects.filter(student=s.quick_student_profile):
                print(f"    * Quick Course: {qe.course} (ID={qe.course.id})")
        except Exception as e:
            print(f"    * Error querying QuickEnrollment: {e}")
