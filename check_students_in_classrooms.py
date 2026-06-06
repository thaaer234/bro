import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alyaman.settings')
django.setup()

from classroom.models import Classroom
from quick.models import AcademicYear
from students.models import Student

active_year = AcademicYear.objects.filter(is_active=True).first()
print(f"Active Academic Year: {active_year}")

classrooms = Classroom.objects.filter(is_active=True, class_type='study').order_by('name')
for c in classrooms:
    total_students = c.enrollments.count()
    if active_year:
        active_students = c.enrollments.filter(student__academic_year=active_year).count()
    else:
        active_students = 0
    print(f"ID: {c.id} | Name: {c.name} | Total Students: {total_students} | Active Year Students: {active_students}")
