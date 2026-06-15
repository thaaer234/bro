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

print(f"Checking for Classroom ID={classroom.id} ({classroom.name}) linked to Course ID={course.id} ({course.name})")

# 1. Students enrolled in this course
course_student_ids = Studentenrollment.objects.filter(
    course=course
).values_list('student__id', flat=True)

# 2. Students already assigned to a classroom for this course
assigned_student_ids = Classroomenrollment.objects.filter(
    classroom__course=course
).values_list('student__id', flat=True)

# 3. Available students (enrolled but not assigned)
available_students = Student.objects.filter(
    id__in=course_student_ids
).exclude(
    id__in=assigned_student_ids
).distinct()

print(f"\nTotal students enrolled in course: {len(course_student_ids)}")
print(f"Total students already assigned to classrooms for this course: {len(assigned_student_ids)}")
print(f"Total available (unassigned) students: {available_students.count()}")

print("\nList of all Available Students (these SHOULD show up in the select list):")
for s in available_students.order_by('full_name'):
    print(f"  - Student ID={s.id} | Name={s.full_name} | is_active={s.is_active}")

print("\nList of all Assigned Students for this course:")
assigned_students_list = Student.objects.filter(id__in=assigned_student_ids).distinct()
for s in assigned_students_list.order_by('full_name'):
    # Find which classroom they are assigned to
    cle = Classroomenrollment.objects.filter(student=s, classroom__course=course).first()
    print(f"  - Student ID={s.id} | Name={s.full_name} | Assigned to: {cle.classroom.name} (ID={cle.classroom.id})")
