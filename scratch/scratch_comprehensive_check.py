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

classroom_id = 25
classroom = Classroom.objects.get(id=classroom_id)
course = classroom.course

print(f"Course ID for '{course}': {course.id if course else 'None'}")

print("\n=== Students Enrolled in this Course ===")
course_enrollments = Studentenrollment.objects.filter(course=course)
print(f"Total enrollments in '{course}': {course_enrollments.count()}")
for ce in course_enrollments[:50]: # print first 50
    print(f"  - Enrollment ID={ce.id} | Student: ID={ce.student.id} | Name={ce.student.full_name} | is_active={ce.student.is_active}")

print("\n=== Details of 'لانا شادي عجاج' (ID=2046) ===")
try:
    s2046 = Student.objects.get(id=2046)
    print(f"ID={s2046.id} | Name={s2046.full_name} | is_active={s2046.is_active}")
    print("Enrollments:")
    for ce in Studentenrollment.objects.filter(student=s2046):
        print(f"  * Course: {ce.course} (ID={ce.course.id})")
    for cle in Classroomenrollment.objects.filter(student=s2046):
        print(f"  * Classroom: {cle.classroom.name} (ID={cle.classroom.id}) | Course: {cle.classroom.course}")
except Student.DoesNotExist:
    print("Student ID 2046 does not exist.")

print("\n=== Details of 'لانا عجاج' (ID=304) ===")
try:
    s304 = Student.objects.get(id=304)
    print(f"ID={s304.id} | Name={s304.full_name} | is_active={s304.is_active}")
    print("Enrollments:")
    for ce in Studentenrollment.objects.filter(student=s304):
        print(f"  * Course: {ce.course} (ID={ce.course.id})")
    for cle in Classroomenrollment.objects.filter(student=s304):
        print(f"  * Classroom: {cle.classroom.name} (ID={cle.classroom.id}) | Course: {cle.classroom.course}")
except Student.DoesNotExist:
    print("Student ID 304 does not exist.")

print("\n=== Searching for any student with first name containing 'عبد' and last name containing 'منجد' ===")
all_students = Student.objects.all()
matches = []
for s in all_students:
    name_lower = s.full_name.lower()
    if "منجد" in name_lower or "عجاج" in name_lower:
        matches.append(s)
print(f"Found {len(matches)} students with 'منجد' or 'عجاج' in their name:")
for s in matches:
    print(f"  - Student: ID={s.id} | Name={s.full_name} | is_active={s.is_active}")
    print("    Course Enrollments:")
    for ce in Studentenrollment.objects.filter(student=s):
        print(f"      * Course: {ce.course} (ID={ce.course.id})")
    print("    Classroom Enrollments:")
    for cle in Classroomenrollment.objects.filter(student=s):
        print(f"      * Classroom: {cle.classroom.name} (ID={cle.classroom.id})")

print("\n=== Let's search for any Student whose name contains 'عبد' and has 'المنجد' in their profile or father/mother fields ===")
for s in Student.objects.filter(full_name__icontains="عبد"):
    if "منجد" in s.father_name or "منجد" in s.mother_name or "منجد" in getattr(s, 'notes', ''):
        print(f"Student ID={s.id} | Name={s.full_name} | Father={s.father_name} | Mother={s.mother_name}")
