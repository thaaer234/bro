import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alyaman.settings')
django.setup()

from django.db import transaction as db_transaction
from django.utils import timezone
from quick.models import QuickEnrollment, QuickStudentReceipt
from accounts.models import JournalEntry

def main():
    print("Finding the enrollment completed today...")
    today = timezone.localdate()
    # Find enrollment completed today
    enrollment = QuickEnrollment.objects.filter(is_completed=True, completion_date=today).first()
    if not enrollment:
        print("No enrollment completed today found.")
        os._exit(0)
        
    print(f"Found enrollment: Student {enrollment.student.full_name} | Course {enrollment.course.name}")
    
    with db_transaction.atomic():
        # Re-activate enrollment
        enrollment.is_completed = False
        enrollment.completion_date = None
        enrollment.save(update_fields=['is_completed', 'completion_date'])
        print("Set enrollment is_completed = False")
        
        # Find and delete the reversal journal entry
        reversal_ref = f"Reversal of QE-{enrollment.id}"
        reversal_desc = f"QE-{enrollment.id}"
        reversal_desc_ar = f"إلغاء تسجيل سريع"
        
        reversal_je = JournalEntry.objects.filter(
            date=today,
            entry_type='ADJUSTMENT'
        ).filter(
            django.db.models.Q(description__icontains=reversal_desc) |
            django.db.models.Q(description__icontains=reversal_ref) |
            django.db.models.Q(description__icontains=reversal_desc_ar)
        ).first()
        
        if reversal_je:
            print(f"Deleting reversal journal entry: {reversal_je.id} | {reversal_je.description}")
            # Delete transactions first
            reversal_je.transactions.all().delete()
            reversal_je.delete()
        else:
            print("No reversal journal entry found to delete.")
            
    print("Restore complete.")
    sys.stdout.flush()
    os._exit(0)

if __name__ == '__main__':
    main()
