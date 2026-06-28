import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alyaman.settings')
django.setup()

from accounts.models import Course
from quick.models import AcademicYear

for year in AcademicYear.objects.all():
    print(f"Academic Year: {year.name} (ID: {year.id})")
    courses = Course.objects.filter(academic_year=year)
    print(f"  Total courses: {courses.count()}")
    for c in courses:
        print(f"    Course ID: {c.id} | Name: {c.name} | Active: {c.is_active}")
