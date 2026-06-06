import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alyaman.settings')
django.setup()

from classroom.models import Classroom
from accounts.models import Course

print("=== COURSES AND THEIR YEARS ===")
for course in Course.objects.all():
    year_name = course.academic_year.name if course.academic_year else "No Year"
    print(f"ID: {course.id} | Name: {course.name} | Year: {year_name} | Is Active: {course.is_active}")
