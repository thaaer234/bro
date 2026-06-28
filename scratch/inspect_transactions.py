# -*- coding: utf-8 -*-
import sys, os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alyaman.settings')
os.environ["DISABLE_BIOMETRIC_SCHEDULER"] = "true"
import django
django.setup()

from accounts.models import Account, Transaction

account_id = 4256
try:
    account = Account.objects.get(id=account_id)
    print(f"Account ID: {account.id}")
    print(f"Account Code: {account.code}")
    print(f"Account Name: {account.name_ar or account.name}")
    print(f"Account Type: {account.account_type}")
    print(f"Is Student Account: {account.is_student_account}")
    print(f"Student Name: {account.student_name}")
    
    # Let's see transactions for this exact account
    txs = Transaction.objects.filter(account=account).select_related('journal_entry', 'journal_entry__academic_year')
    print(f"\nTransactions count for exact account: {txs.count()}")
    for tx in txs:
        je = tx.journal_entry
        print(f" - TX ID: {tx.id}, Amount: {tx.amount}, IsDebit: {tx.is_debit}, JE ID: {je.id}, JE Date: {je.date}, JE Year: {je.academic_year}")

    # Let's see transactions for all student accounts of the same student
    if account.is_student_account and account.student_name:
        student_accounts = Account.objects.filter(is_student_account=True, student_name=account.student_name)
        print(f"\nAll student accounts for student name '{account.student_name}':")
        for sa in student_accounts:
            print(f" - Account ID: {sa.id}, Code: {sa.code}, Name: {sa.name_ar or sa.name}")
            sa_txs = Transaction.objects.filter(account=sa).select_related('journal_entry', 'journal_entry__academic_year')
            print(f"   TXs count: {sa_txs.count()}")
            for tx in sa_txs:
                je = tx.journal_entry
                print(f"     TX ID: {tx.id}, Amount: {tx.amount}, IsDebit: {tx.is_debit}, JE ID: {je.id}, JE Date: {je.date}, JE Year: {je.academic_year}")

except Exception as e:
    print(f"Error: {e}")
