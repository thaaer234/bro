import os
import sys
import django

sys.path.append(r"c:\Users\THAAER\Desktop\project")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "alyaman.settings")
django.setup()

sys.stdout.reconfigure(encoding="utf-8")

from accounts.models import Course

for c in Course.objects.all().order_by('academic_year_id', 'id'):
    print(f"ID: {c.id} | Name: {c.name} | AY: {c.academic_year_id} | Active: {c.is_active}")
