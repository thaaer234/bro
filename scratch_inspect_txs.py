import os
import sys
import django

sys.path.append(r'c:\Users\THAAER\Desktop\project')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alyaman.settings')
django.setup()

from accounts.models import Transaction, JournalEntry, Course, Studentenrollment

print("=== IN-DEPTH INSPECTION BY TX IDS ===")

tx_ids = [16426, 35533, 44961]
for tx_id in tx_ids:
    try:
        t = Transaction.objects.select_related('journal_entry', 'account').get(id=tx_id)
        je = t.journal_entry
        print(f"\nTransaction ID: {t.id} | Amount: {t.amount} | Is Debit: {t.is_debit}")
        print(f"  Account: {t.account.code} - {t.account.name_ar or t.account.name}")
        print(f"  Journal Entry ID: {je.id} | Reference: {je.reference} | Type: {je.entry_type} | Total: {je.total_amount}")
        print(f"  JE Description: {je.description}")
        
        # Print all transactions of this journal entry
        print("  All transactions in this JE:")
        all_txs = Transaction.objects.filter(journal_entry=je).select_related('account')
        for at in all_txs:
            print(f"    - Account: {at.account.code} ({at.account.name_ar or at.account.name}) | Amount: {at.amount} | Is Debit: {at.is_debit} | Desc: {at.description}")
    except Transaction.DoesNotExist:
        print(f"Transaction ID {tx_id} does not exist.")
