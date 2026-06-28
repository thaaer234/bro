# -*- coding: utf-8 -*-
import sys, os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alyaman.settings')
os.environ["DISABLE_BIOMETRIC_SCHEDULER"] = "true"
import django
django.setup()

from accounts.models import Account, Transaction

codes = ['1251-000-2197', '1251-000-2198', '1251-000-2208', '1251-000-2210']

for code in codes:
    try:
        account = Account.objects.get(code=code)
        print("="*60)
        print(f"الكود: {account.code} | الاسم: {account.name_ar or account.name}")
        print(f"معرف الحساب (Account ID): {account.id}")
        
        # Transactions
        txs = Transaction.objects.filter(account=account).select_related('journal_entry', 'journal_entry__academic_year')
        print(f"عدد الحركات المسجلة على هذا الحساب: {txs.count()}")
        for tx in txs:
            je = tx.journal_entry
            print(f" - حركة رقم {tx.id}: مدين={tx.is_debit} | مبلغ={tx.amount} | وصف القيد={je.description} | وصف الحركة={tx.description} | العام الدراسي للجرنال={je.academic_year} | تاريخ القيد={je.date}")
            
    except Account.DoesNotExist:
        print(f"الحساب ذو الكود {code} غير موجود بقاعدة البيانات المحلية.")
    except Exception as e:
        print(f"حدث خطأ أثناء فحص الحساب {code}: {e}")
