import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alyaman.settings')
django.setup()

from quick.models import QuickCourse

def main():
    print("--- Searching for Courses ---")
    courses = QuickCourse.objects.all()
    for c in courses:
        print(f"ID: {c.id} | Name: {c.name} | Price: {c.price} | Course Type: {c.course_type}")

if __name__ == '__main__':
    main()
