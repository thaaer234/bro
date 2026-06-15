import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alyaman.settings')
django.setup()

sys.stdout.reconfigure(encoding='utf-8')

from accounts.models import JournalEntry, Transaction

je_refs = ["JE-006954", "JE-010845"]
for ref in je_refs:
    try:
        je = JournalEntry.objects.get(reference=ref)
        print(f"\nJournal Entry: {je.reference}")
        print(f"  Date: {je.date}")
        print(f"  Academic Year: {je.academic_year.name if je.academic_year else 'None'} (ID: {je.academic_year.id if je.academic_year else 'None'})")
        print(f"  Transactions:")
        for t in je.transactions.all():
            print(f"    Account: {t.account.code} ({t.account.name_ar}) | Amount: {t.amount} | Debit: {t.is_debit}")
    except JournalEntry.DoesNotExist:
        print(f"Journal Entry {ref} not found.")
