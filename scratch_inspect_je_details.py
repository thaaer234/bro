import os
import sys
import django

sys.path.append(r'c:\Users\THAAER\Desktop\project')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alyaman.settings')
django.setup()

sys.stdout.reconfigure(encoding='utf-8')

from accounts.models import JournalEntry, Transaction

print("=== IN-DEPTH JOURNAL ENTRIES FOR 794 ===")
je_refs = ["JE-006954", "JE-010845", "JE-011899"]
for ref in je_refs:
    try:
        je = JournalEntry.objects.get(reference=ref)
        print(f"\nJournal Entry: ID={je.id} | Reference={je.reference} | Type={je.entry_type}")
        print(f"  Description: {je.description}")
        print(f"  Total Amount: {je.total_amount}")
        txs = Transaction.objects.filter(journal_entry=je)
        for t in txs:
            print(f"    Account: {t.account.code} ({t.account.name_ar or t.account.name}) | Amount: {t.amount} | Is Debit: {t.is_debit} | Desc: {t.description}")
    except JournalEntry.DoesNotExist:
        print(f"Journal Entry {ref} not found.")
