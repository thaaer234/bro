import os
import sys
import django

sys.path.append(r"c:\Users\THAAER\Desktop\project")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "alyaman.settings")
django.setup()

sys.stdout.reconfigure(encoding="utf-8")

from accounts.models import Course
try:
    c = Course.objects.get(id=31)
    print(f"Course ID: 31 | Name: {c.name} | AY: {c.academic_year_id}")
except Course.DoesNotExist:
    print("Course ID 31 does not exist")
