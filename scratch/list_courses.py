import os
import sys
import django

sys.path.append(r"c:\Users\THAAER\Desktop\project")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "alyaman.settings")
django.setup()

sys.stdout.reconfigure(encoding="utf-8")

from accounts.models import Course
from quick.models import QuickCourse, AcademicYear

print("--- Searching for courses matching the user request ---")
target_names = [
    "دورة صيف ادبي 2026-2027",
    "دورة صيف تاسع 2026-2027",
    "دورة صيف علمي 2026-2027",
    "دورة شتاء أدبي 2026-2027",
    "دورة شتاء علمي 2026-2027",
    "دورة شتاء تاسع 2026-2027",
]

for name in target_names:
    print(f"\nSearching for: '{name}'")
    # Search in AcademicYear
    ays = AcademicYear.objects.filter(name__icontains=name)
    print(f"  Found in AcademicYear: {[str(ay) for ay in ays]}")
    
    # Search in Course
    courses = Course.objects.filter(name__icontains=name) | Course.objects.filter(name_ar__icontains=name)
    print(f"  Found in regular Course: {[f'ID: {c.id}, Name: {c.name}, Year: {c.academic_year}' for c in courses]}")
    
    # Search in QuickCourse
    q_courses = QuickCourse.objects.filter(name__icontains=name) | QuickCourse.objects.filter(name_ar__icontains=name)
    print(f"  Found in QuickCourse: {[f'ID: {qc.id}, Name: {qc.name}, Year: {qc.academic_year}' for qc in q_courses]}")
