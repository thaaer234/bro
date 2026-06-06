import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alyaman.settings')
django.setup()

from classroom.models import Classroom

print("=== ACTIVE STUDY CLASSROOMS ===")
classrooms = Classroom.objects.filter(is_active=True, class_type='study').order_by('name')
for c in classrooms:
    print(f"ID: {c.id} | Name: {c.name} | Branch: {c.branches} | Course: {c.course} | Is Active: {c.is_active}")
