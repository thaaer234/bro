import os
import sys
import django

sys.path.append(r"c:\Users\THAAER\Desktop\project")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "alyaman.settings")
django.setup()

sys.stdout.reconfigure(encoding="utf-8")

from accounts.models import Course, Studentenrollment, StudentReceipt, JournalEntry, Transaction, Account

# Mapping from Year 1 Course ID to Year 2 Course ID
mapping = {
    18: 30, # صيف علمي
    19: 28, # صيف ادبي
    20: 29, # صيف تاسع
    21: 27, # شتاء علمي
    22: 25, # شتاء ادبي
    23: 26, # شتاء تاسع
    24: 31, # شتاء تمهيدي
}

print("--- Comparing course data between Year 1 copies and Year 2 copies ---")
for y1_id, y2_id in mapping.items():
    try:
        c1 = Course.objects.get(id=y1_id)
        c2 = Course.objects.get(id=y2_id)
        
        # Check enrollments
        e1_students = set(Studentenrollment.objects.filter(course=c1).values_list('student__full_name', flat=True))
        e2_students = set(Studentenrollment.objects.filter(course=c2).values_list('student__full_name', flat=True))
        
        extra_in_y1 = e1_students - e2_students
        extra_in_y2 = e2_students - e1_students
        
        print(f"\nCourse: {c1.name}")
        print(f"  Year 1 (ID: {y1_id}) student count: {len(e1_students)}")
        print(f"  Year 2 (ID: {y2_id}) student count: {len(e2_students)}")
        print(f"  Extra in Year 1: {extra_in_y1}")
        print(f"  Extra in Year 2: {extra_in_y2}")
        
        # Check receipts
        r1_amounts = sorted(list(StudentReceipt.objects.filter(enrollment__course=c1).values_list('amount', flat=True)))
        r2_amounts = sorted(list(StudentReceipt.objects.filter(enrollment__course=c2).values_list('amount', flat=True)))
        print(f"  Year 1 receipt count: {len(r1_amounts)} | Year 2 receipt count: {len(r2_amounts)}")
        if r1_amounts != r2_amounts:
            print("  WARNING: Receipt amounts are different!")
            
    except Course.DoesNotExist as e:
        print(f"Error for mapping {y1_id} -> {y2_id}: {e}")
