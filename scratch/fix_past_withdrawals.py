import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alyaman.settings')
django.setup()

from django.db import transaction as db_transaction
from django.db.models import Q
from django.contrib.auth.models import User
from quick.models import QuickEnrollment
from accounts.models import JournalEntry

def main():
    # Fetch admin user
    user = User.objects.filter(is_superuser=True, username='thaaer').first() or User.objects.filter(is_superuser=True).first()
    if not user:
        print("Error: No superuser found in database to authorize the reversals.")
        os._exit(1)
        
    print(f"Using superuser: {user.username} for reversals.")
    
    # Find all completed enrollments
    completed_enrollments = QuickEnrollment.objects.filter(is_completed=True)
    print(f"Total completed/withdrawn enrollments: {completed_enrollments.count()}")
    
    fixed_count = 0
    
    with db_transaction.atomic():
        for e in completed_enrollments:
            je = e.enrollment_journal_entry
            if not je:
                continue
                
            # Check if there is already a reversal entry
            reversal_ref = f"Reversal of QE-{e.id}"
            reversal_desc = f"QE-{e.id}"
            reversal_desc_ar = f"إلغاء تسجيل سريع"
            
            reversals = JournalEntry.objects.filter(
                Q(description__icontains=reversal_desc) |
                Q(description__icontains=reversal_ref) |
                (Q(description__icontains=reversal_desc_ar) & Q(description__icontains=e.student.full_name) & Q(description__icontains=e.course.name))
            )
            
            if not reversals.exists():
                print(f"Reversing unreversed withdrawn registration for Student: {e.student.full_name} | Course: {e.course.name} | Amount: {e.net_amount}")
                try:
                    je.reverse_entry(
                        user,
                        description=f"عكس قيد إلغاء تسجيل سريع (تلقائي) - {e.student.full_name} - {e.course.name}"
                    )
                    fixed_count += 1
                except Exception as exc:
                    print(f"  Failed to reverse entry {je.id}: {exc}")
                    
    print(f"\nSuccessfully reversed {fixed_count} withdrawn student registrations.")
    os._exit(0)

if __name__ == '__main__':
    main()
