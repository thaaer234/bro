# -*- coding: utf-8 -*-
import sys, os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alyaman.settings')
import django
django.setup()

from accounts.models import Course
from classroom.models import Classroom, Classroomenrollment

print("=== Course Fields ===")
for field in Course._meta.get_fields():
    print(f"{field.name}: {type(field).__name__}")

print("\n=== Classroom Fields ===")
for field in Classroom._meta.get_fields():
    print(f"{field.name}: {type(field).__name__}")
