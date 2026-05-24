import os
import sys
import django

sys.path.append(r"c:\Users\THAAER\Desktop\project")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "alyaman.settings")
django.setup()

sys.stdout.reconfigure(encoding="utf-8")

from accounts.models import Studentenrollment, Course
from django.db.models import Count

print("--- Inspecting Studentenrollment by Academic Year ---")
for row in Studentenrollment.objects.values('academic_year_id', 'course_id', 'course__name').annotate(count=Count('id')).order_by('academic_year_id', 'course_id'):
    print(f"AY ID: {row['academic_year_id']} | Course ID: {row['course_id']} | Course Name: {row['course__name']} | Count: {row['count']}")
