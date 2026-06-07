import os
import sys
import django

sys.path.append(r'c:\Users\THAAER\Desktop\project')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alyaman.settings')
django.setup()

sys.stdout.reconfigure(encoding='utf-8')

from accounts.models import StudentReceipt

print("=== SEARCHING RECEIPTS BY student_profile_id ===")
for r in StudentReceipt.objects.filter(student_profile_id=501):
    print(f"Receipt for Student 501: ID={r.id} | No={r.receipt_number} | Amount={r.paid_amount} | Date={r.date} | JE={r.journal_entry.reference if r.journal_entry else 'None'}")

for r in StudentReceipt.objects.filter(student_profile_id=794):
    print(f"Receipt for Student 794: ID={r.id} | No={r.receipt_number} | Amount={r.paid_amount} | Date={r.date} | JE={r.journal_entry.reference if r.journal_entry else 'None'}")
