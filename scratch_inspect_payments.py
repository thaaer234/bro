import os
import sys
import django

sys.path.append(r'c:\Users\THAAER\Desktop\project')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alyaman.settings')
django.setup()

from accounts.models import Student, Account, JournalEntry, Transaction, StudentReceipt

print("=== ALL STUDENT RECEIPTS ===")
receipts = StudentReceipt.objects.filter(student_id=501)
print(f"Receipts for Student 501: {receipts.count()}")
for r in receipts:
    print(f"  Receipt ID: {r.id} | Date: {r.date} | Amount: {r.amount} | Paid: {r.paid_amount} | JE: {r.journal_entry}")

receipts2 = StudentReceipt.objects.filter(student_id=794)
print(f"Receipts for Student 794: {receipts2.count()}")
for r in receipts2:
    print(f"  Receipt ID: {r.id} | Date: {r.date} | Amount: {r.amount} | Paid: {r.paid_amount} | JE: {r.journal_entry}")

print("\n=== ALL TRANSACTIONS FOR STUDENT 794 ACCOUNTS ===")
# Find all accounts for student 794
accounts = Account.objects.filter(code__contains="794")
for a in accounts:
    print(f"Account: {a.code} - {a.name_ar or a.name} | Balance: {a.balance}")
    txs = Transaction.objects.filter(account=a).select_related('journal_entry')
    for t in txs:
        print(f"  Tx: {t.id} | Date: {t.journal_entry.date} | JE: {t.journal_entry.reference} ({t.journal_entry.entry_type}) | Amount: {t.amount} | Is Debit: {t.is_debit} | Desc: {t.description}")
