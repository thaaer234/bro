import os
import django
from django.conf import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alyaman.settings')
django.setup()

print("Database Config:")
print(settings.DATABASES['default']['NAME'])

from quick.models import AcademicYear
from students.models import Student

for year in AcademicYear.objects.all():
    student_count = Student.objects.filter(academic_year=year).count()
    print(f"Academic Year: {year.name} (ID: {year.id}) | Total Students: {student_count}")
