import os
import sys
import django

sys.path.append(r'c:\Users\THAAER\Desktop\project')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alyaman.settings')
django.setup()

sys.stdout.reconfigure(encoding='utf-8')

from accounts.models import Studentenrollment, Course
from students.models import Student
from classroom.models import Classroom

print("=== COURSES CONTAINING 'صيف' OR 'علمي' ===")
courses = Course.objects.filter(name__icontains="صيف") | Course.objects.filter(name__icontains="علمي")
for c in courses.distinct():
    enroll_count = Studentenrollment.objects.filter(course=c).count()
    print(f"ID={c.id} | Name={c.name} | Total Enrolled Students={enroll_count}")

print("\n=== SEARCHING ENROLLMENTS IN ALL 'صيف/علمي' COURSES ===")
search_names = ["عبد الكريم", "عبدالكريم", "لانا", "عجاج", "منجد"]
for c in courses.distinct():
    enrolls = Studentenrollment.objects.filter(course=c)
    matching_enrolls = []
    for e in enrolls:
        student_name = e.student.full_name
        if any(term in student_name for term in search_names):
            matching_enrolls.append(e)
            
    if matching_enrolls:
        print(f"\nCourse '{c.name}' (ID={c.id}) has matching students:")
        for e in matching_enrolls:
            print(f"  - Student ID={e.student.id} | Name={e.student.full_name} | is_active={e.student.is_active} | Enrollment ID={e.id}")

print("\n=== CHECKING IF WE HAVE ANY OTHER CLASSROOM WITH ID 25 ===")
for cl in Classroom.objects.filter(id=25):
    print(f"Classroom ID={cl.id} | Name={cl.name} | Type={cl.class_type} | Course={cl.course}")
