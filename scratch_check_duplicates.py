import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alyaman.settings')
django.setup()

from classroom.models import Classroom, Classroomenrollment
from quick.models import AcademicYear
from students.models import Student

active_year = AcademicYear.objects.filter(is_active=True).first()
print(f"Active Academic Year: {active_year} (ID: {active_year.id if active_year else None})")

classroom = Classroom.objects.get(id=30)
enrollments = classroom.enrollments.all()

found_new = 0
not_found_new = 0

for env in enrollments:
    student = env.student
    # Try to find a student with the same name and phone but in the active academic year
    new_students = Student.objects.filter(
        full_name=student.full_name,
        phone=student.phone,
        academic_year=active_year
    )
    if new_students.exists():
        found_new += 1
        new_student = new_students.first()
        # print(f"Match for {student.full_name}: Old ID {student.id} -> New ID {new_student.id}")
    else:
        not_found_new += 1
        # print(f"No match for {student.full_name} | Old ID: {student.id}")

print(f"Total: {enrollments.count()}")
print(f"Found match in new year: {found_new}")
print(f"No match in new year: {not_found_new}")
