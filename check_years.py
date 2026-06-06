import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alyaman.settings')
django.setup()

from quick.models import AcademicYear

print("=== ACADEMIC YEARS ===")
for ay in AcademicYear.objects.all():
    print(f"ID: {ay.id} | Name: {ay.name} | Start: {ay.start_date} | End: {ay.end_date} | Is Active: {ay.is_active}")
