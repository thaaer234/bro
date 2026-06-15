import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alyaman.settings')
django.setup()

from django.db.models import Q
from quick.models import QuickCourse, QuickEnrollment
from accounts.models import JournalEntry

def main():
    print("Scanning completed enrollments for unreversed entries...")
    # Find all completed enrollments
    completed_enrollments = QuickEnrollment.objects.filter(is_completed=True)
    print(f"Total completed/withdrawn enrollments in database: {completed_enrollments.count()}")
    
    unreversed_count = 0
    with open('scratch/unreversed_report.txt', 'w', encoding='utf-8') as f:
        f.write("Unreversed Withdrawn Student Registrations:\n\n")
        
        for e in completed_enrollments:
            je = e.enrollment_journal_entry
            if not je:
                # No registration entry existed, nothing to reverse
                continue
                
            # Check if there is a reversal entry
            reversal_ref = f"Reversal of QE-{e.id}"
            reversal_desc = f"QE-{e.id}"
            reversal_desc_ar = f"إلغاء تسجيل سريع"
            
            # Look for reversing entries
            reversals = JournalEntry.objects.filter(
                Q(description__icontains=reversal_desc) |
                Q(description__icontains=reversal_ref) |
                (Q(description__icontains=reversal_desc_ar) & Q(description__icontains=e.student.full_name) & Q(description__icontains=e.course.name))
            )
            
            if not reversals.exists():
                unreversed_count += 1
                f.write(f"Enrollment ID: {e.id} | Student: {e.student.full_name} | Course: {e.course.name} | Price: {e.net_amount}\n")
                f.write(f"  Registration JE: {je.id} | Ref: {je.reference} | Date: {je.date} | Total Amount: {je.total_amount}\n")
                f.write("-" * 80 + "\n")
                
    print(f"Found {unreversed_count} unreversed withdrawn registrations.")
    os._exit(0)

if __name__ == '__main__':
    main()
