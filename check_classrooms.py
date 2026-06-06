import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alyaman.settings')
django.setup()

from classroom.models import Classroom

print("Classrooms in database:")
for c in Classroom.objects.all():
    print(f"ID: {c.id}, Name: {c.name}, Is Active: {c.is_active}")
