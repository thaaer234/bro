import os
import sys
import django

# Setup Django environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alyaman.settings')
django.setup()

from accounts.models import Account, Course, StudentReceipt, JournalEntry, Transaction

def audit_transactions():
    print("=== START Transaction Audit ===")
    
    # 1. جلب كافة القيود في الفصل الجديد (2026-2027)
    target_entries = JournalEntry.objects.filter(
        academic_year__name__icontains='2026-2027'
    ).prefetch_related('transactions__account')
    
    print(f"Found {target_entries.count()} journal entries in the target academic year.")
    
    wrong_count = 0
    for je in target_entries:
        # البحث عن القيود التي لها علاقة بالدفع (PAYMENT)
        if je.entry_type == 'PAYMENT' or 'AYXFER' in (je.description or ''):
            debit_txs = je.transactions.filter(is_debit=True)
            for tx in debit_txs:
                # إذا كان القيد دفع (PAYMENT) والمدين (Debit) هو حساب طالب وليس صندوق، فهذا خطأ!
                if not tx.account.code.startswith('121'):
                    wrong_count += 1
                    print(f"\nWrong Payment Entry: ID={je.id}, Ref={je.reference}, Desc='{je.description}'")
                    print(f"  Debit Account: {tx.account.code} ({tx.account.name_ar or tx.account.name})")
                    
                    # طباعة الحسابات الدائنة في نفس القيد
                    credit_txs = je.transactions.filter(is_debit=False)
                    for ctx in credit_txs:
                        print(f"  Credit Account: {ctx.account.code} ({ctx.account.name_ar or ctx.account.name})")
                        
    print(f"\n=== AUDIT COMPLETED ===")
    print(f"Total wrong transactions found: {wrong_count}")

if __name__ == '__main__':
    audit_transactions()
