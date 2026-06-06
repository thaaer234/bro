import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alyaman.settings')
django.setup()

from classroom.models import Classroom

print("=== STUDY CLASSROOMS WITH COURSE STATUS ===")
classrooms = Classroom.objects.filter(is_active=True, class_type='study')
for c in classrooms:
    course_status = "No Course"
    if c.course:
        course_status = f"Course: {c.course.name} | Course Is Active: {c.course.is_active}"
    print(f"ID: {c.id} | Name: {c.name} | {course_status}")
