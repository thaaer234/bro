import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alyaman.settings')
django.setup()

from classroom.models import Classroom
from quick.models import AcademicYear

active_year = AcademicYear.objects.filter(is_active=True).first()
print(f"Active Academic Year: {active_year} (ID: {active_year.id if active_year else None})")

classrooms = Classroom.objects.filter(is_visible=True)
print(f"Total visible classrooms: {classrooms.count()}")

for c in classrooms:
    course = c.course
    course_year = course.academic_year if course else None
    print(f"Classroom ID: {c.id} | Name: {c.name} | Course: {course} | Course Year: {course_year} (ID: {course_year.id if course_year else None})")
