import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alyaman.settings')
django.setup()

from quick.models import AcademicYear
from students.models import Student

for year in AcademicYear.objects.all():
    student_count = Student.objects.filter(academic_year=year).count()
    print(f"Academic Year: {year.name} (ID: {year.id}) | Total Students: {student_count}")

# Check if there are students with academic_year IS NULL
null_students = Student.objects.filter(academic_year__isnull=True).count()
print(f"Students with NULL Academic Year: {null_students}")
