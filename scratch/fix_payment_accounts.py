import os
import sys
import django

# Setup Django environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alyaman.settings')
django.setup()

from django.db import transaction
from accounts.models import Account, Course, StudentReceipt, JournalEntry, Transaction

def fix_payment_accounts():
    print("=== START Fixing Payment Accounts ===")
    
    # 1. جلب كافة إيصالات الطلاب في الفصل الجديد (2026-2027)
    target_receipts = StudentReceipt.objects.filter(
        academic_year__name__icontains='2026-2027'
    ).select_related('journal_entry')
    
    print(f"Found {target_receipts.count()} receipts in the target academic year.")
    
    fixed_count = 0
    touched_accounts = set()
    
    # جلب الحساب النقدي الرئيسي كاحتياطي
    default_cash_account = Account.objects.filter(code='121').first()
    
    with transaction.atomic():
        for target_receipt in target_receipts:
            je = target_receipt.journal_entry
            if not je:
                continue
                
            # البحث عن المعاملة المدونة كـ Debit (التي يجب أن تكون الصندوق)
            debit_tx = je.transactions.filter(is_debit=True).first()
            if not debit_tx:
                continue
                
            # إذا كان حساب المدين ليس حساب صندوق (لا يبدأ بـ 121) فهذا هو الخطأ!
            if not debit_tx.account.code.startswith('121'):
                print(f"\nFound wrong debit transaction in Journal Entry {je.id} (Receipt: {target_receipt.id}):")
                print(f"  Current wrong account: {debit_tx.account.code} ({debit_tx.account.name_ar or debit_tx.account.name})")
                
                # البحث عن الإيصال الأصلي في الفصل الأول (2025-2026) لمطابقة الصندوق الصحيح
                source_receipt = StudentReceipt.objects.filter(
                    receipt_number=target_receipt.receipt_number,
                    academic_year__name__icontains='2025-2026'
                ).select_related('journal_entry').first()
                
                correct_cash_account = None
                if source_receipt and source_receipt.journal_entry:
                    # جلب حساب الصندوق الأصلي من قيد الإيصال المصدري
                    source_debit_tx = source_receipt.journal_entry.transactions.filter(is_debit=True).first()
                    if source_debit_tx and source_debit_tx.account.code.startswith('121'):
                        correct_cash_account = source_debit_tx.account
                        print(f"  -> Found correct source cash account: {correct_cash_account.code} ({correct_cash_account.name_ar or correct_cash_account.name})")
                
                # إذا لم نجد الإيصال الأصلي أو لم يملك صندوقاً، نستخدم الصندوق الافتراضي 121
                if not correct_cash_account:
                    correct_cash_account = default_cash_account
                    print(f"  -> Using default cash account: {correct_cash_account.code}")
                
                if correct_cash_account:
                    # تعديل الحساب في المعاملة الخاطئة إلى حساب الصندوق الصحيح
                    old_account = debit_tx.account
                    debit_tx.account = correct_cash_account
                    debit_tx.save(update_fields=['account'])
                    
                    touched_accounts.add(old_account)
                    touched_accounts.add(correct_cash_account)
                    fixed_count += 1
                    print(f"  ✓ Fixed successfully!")
                    
        # إعادة حساب أرصدة الحسابات المتأثرة
        print(f"\nRecalculating balances for {len(touched_accounts)} accounts...")
        for account in touched_accounts:
            try:
                account.recalculate_tree_balances()
                print(f"  - Updated balance for account: {account.code}")
            except Exception as e:
                print(f"  - Error updating account {account.code}: {e}")
                
    print(f"\n=== FIX COMPLETED ===")
    print(f"Total fixed transactions: {fixed_count}")

if __name__ == '__main__':
    fix_payment_accounts()
