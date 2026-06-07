import os
import sys
import django

sys.path.append(r'c:\Users\THAAER\Desktop\project')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alyaman.settings')
django.setup()

sys.stdout.reconfigure(encoding='utf-8')

from accounts.models import JournalEntry, Transaction

print("=== INSPECTING PAYMENT TRANSACTION ACCOUNTS ===")
je = JournalEntry.objects.filter(entry_type='PAYMENT').first()
if je:
    print(f"Payment JE: {je.reference}")
    txs = Transaction.objects.filter(journal_entry=je)
    for t in txs:
        print(f"  Account: {t.account.code} - {t.account.name_ar or t.account.name} | Is Debit: {t.is_debit}")
else:
    # Try searching for receipts
    je2 = JournalEntry.objects.filter(reference__startswith="SR").first()
    if je2:
        print(f"Receipt JE: {je2.reference}")
        txs = Transaction.objects.filter(journal_entry=je2)
        for t in txs:
            print(f"  Account: {t.account.code} - {t.account.name_ar or t.account.name} | Is Debit: {t.is_debit}")
