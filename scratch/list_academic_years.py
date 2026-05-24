import os
import sys
import django

sys.path.append(r"c:\Users\THAAER\Desktop\project")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "alyaman.settings")
django.setup()

sys.stdout.reconfigure(encoding="utf-8")

from quick.models import AcademicYear

for ay in AcademicYear.objects.all():
    print(f"ID: {ay.id} | Name: {ay.name} | Year: {ay.year} | Active: {ay.is_active} | Closed: {ay.is_closed}")
