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
print(f"Classroom {classroom.name} (ID: {classroom.id})")
enrollments = classroom.enrollments.all()
print(f"Total enrollments: {enrollments.count()}")

for i, env in enumerate(enrollments[:10]):
    student = env.student
    print(f"  Student {i+1}: {student.full_name} | ID: {student.id} | Student Academic Year: {student.academic_year} (ID: {student.academic_year_id if student.academic_year else None})")
