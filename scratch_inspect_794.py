import os
import sys
import django
from decimal import Decimal

sys.path.append(r'c:\Users\THAAER\Desktop\project')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alyaman.settings')
django.setup()

from accounts.models import Studentenrollment, Course, JournalEntry, Transaction

print("=== IN-DEPTH INSPECTION FOR STUDENT 794 ===")

course = Course.objects.get(id=18)
print(f"Course: {course.name} ({course.name_ar}) | Price: {course.price}")

enrollment = Studentenrollment.objects.get(id=564)
print(f"Enrollment 564: Total Amount: {enrollment.total_amount} | Discount %: {enrollment.discount_percent} | Discount Amt: {enrollment.discount_amount} | Net: {enrollment.net_amount}")

je_ids = [6954, 10845, 11899]
for je_id in je_ids:
    try:
        je = JournalEntry.objects.get(id=je_id)
        print(f"\nJournal Entry ID: {je.id} ({je.reference})")
        print(f"  Date: {je.date} | Type: {je.entry_type} | Total: {je.total_amount} | Description: {je.description}")
        print(f"  Is Posted: {je.is_posted}")
        txs = Transaction.objects.filter(journal_entry=je)
        for t in txs:
            print(f"    Account: {t.account.code} ({t.account.name_ar or t.account.name}) | Amount: {t.amount} | Is Debit: {t.is_debit} | Desc: {t.description}")
    except JournalEntry.DoesNotExist:
        print(f"\nJournal Entry ID {je_id} does not exist.")
