# -*- coding: utf-8 -*-
import os
import sys

# Setup path and environment
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alyaman.settings')
os.environ["DISABLE_BIOMETRIC_SCHEDULER"] = "true"

import django
django.setup()

from accounts.models import Account, Transaction

def main():
    code = "1251-031-2587"
    print(f"🔍 Searching for account: {code}...")
    try:
        account = Account.objects.get(code=code)
        print(f"Account ID: {account.id}")
        print(f"Account Code: {account.code}")
        print(f"Account Name: {account.name_ar or account.name}")
        print(f"Account Type: {account.account_type}")
        print(f"Is Student Account: {account.is_student_account}")
        print(f"Student Name: {account.student_name}")
        print(f"Stored Balance Field: {account.balance}")
        
        # Transactions of this exact account
        txs = Transaction.objects.filter(account=account).select_related('journal_entry', 'journal_entry__academic_year')
        print(f"\nTransactions for this account ({txs.count()}):")
        for tx in txs:
            je = tx.journal_entry
            print(f" - TX ID: {tx.id} | Amount: {tx.amount} | IsDebit: {tx.is_debit} | JE ID: {je.id} | Date: {je.date} | Year: {je.academic_year}")
            
        # Grouped student accounts
        if account.is_student_account and account.student_name:
            all_accounts = Account.objects.filter(is_student_account=True, student_name=account.student_name)
            print(f"\nAll student accounts matching name '{account.student_name}':")
            for sa in all_accounts:
                print(f" * Account ID: {sa.id} | Code: {sa.code} | Name: {sa.name_ar or sa.name} | Stored Balance: {sa.balance}")
                sa_txs = Transaction.objects.filter(account=sa).select_related('journal_entry', 'journal_entry__academic_year')
                for tx in sa_txs:
                    je = tx.journal_entry
                    print(f"   - TX ID: {tx.id} | Amount: {tx.amount} | IsDebit: {tx.is_debit} | JE ID: {je.id} | Date: {je.date} | Year: {je.academic_year}")
                    
    except Account.DoesNotExist:
        print(f"❌ Account with code '{code}' does not exist.")
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
