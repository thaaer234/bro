import os
import sys
import django

sys.path.append(r'c:\Users\THAAER\Desktop\project')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alyaman.settings')
django.setup()

sys.stdout.reconfigure(encoding='utf-8')

from classroom.models import Classroom, Classroomenrollment
from students.models import Student
from accounts.models import Studentenrollment

classroom_id = 25
classroom = Classroom.objects.get(id=classroom_id)
course = classroom.course

print(f"Associated Course: {course} (ID={course.id})")

course_enrollments = Studentenrollment.objects.filter(course=course)
print(f"Total enrollments in course: {course_enrollments.count()}")

search_terms = ["عبد الكريم", "عبدالكريم", "كريم", "منجد", "عجاج", "لانا"]

print("\nSearching for enrolled students matching search terms:")
found_any = False
for ce in course_enrollments:
    student = ce.student
    name = student.full_name
    matched_terms = [t for t in search_terms if t in name]
    if matched_terms:
        found_any = True
        print(f"  - Student: ID={student.id} | Name={name} | is_active={student.is_active} | Enrollment ID={ce.id} | Matched: {matched_terms}")
        # Check if already assigned to a classroom for this course
        class_enroll = Classroomenrollment.objects.filter(student=student, classroom__course=course).first()
        if class_enroll:
            print(f"    * Already assigned to Classroom: {class_enroll.classroom.name} (ID={class_enroll.classroom.id})")
        else:
            print(f"    * Not assigned to any classroom for this course")

if not found_any:
    print("No enrolled students matched the search terms.")
