# -*- coding: utf-8 -*-
"""
سكريبت تشخيصي: يحسب إجمالي الحركات مباشرة من جدول Transactions
لمعرفة هل قاعدة البيانات نفسها متوازنة أم لا
"""
import os, sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alyaman.settings')
os.environ["DISABLE_BIOMETRIC_SCHEDULER"] = "true"
import django
django.setup()

from django.db.models import Sum
from accounts.models import Transaction, JournalEntry
from decimal import Decimal

def main():
    print("=" * 60)
    print("🔍 تشخيص شامل لتوازن الحركات المحاسبية")
    print("=" * 60)

    # 1. إجمالي جميع الحركات في قاعدة البيانات (بدون أي فلتر)
    total_debit = Transaction.objects.filter(is_debit=True).aggregate(t=Sum('amount'))['t'] or Decimal('0')
    total_credit = Transaction.objects.filter(is_debit=False).aggregate(t=Sum('amount'))['t'] or Decimal('0')
    diff = total_debit - total_credit

    print(f"\n📊 إجمالي جميع الحركات (بدون فلتر):")
    print(f"   المدين : {total_debit:>20,.0f}")
    print(f"   الدائن : {total_credit:>20,.0f}")
    print(f"   الفرق  : {diff:>20,.0f} {'✅ متوازن' if diff == 0 else '❌ غير متوازن!'}")

    # 2. تحقق من كل سنة دراسية
    from quick.models import AcademicYear
    years = AcademicYear.objects.all().order_by('id')
    print(f"\n📅 تفاصيل حسب السنة الدراسية:")
    for year in years:
        d = Transaction.objects.filter(is_debit=True, journal_entry__academic_year=year).aggregate(t=Sum('amount'))['t'] or Decimal('0')
        c = Transaction.objects.filter(is_debit=False, journal_entry__academic_year=year).aggregate(t=Sum('amount'))['t'] or Decimal('0')
        diff_y = d - c
        status = '✅' if diff_y == 0 else '❌'
        print(f"   {year}: مدين={d:>15,.0f} | دائن={c:>15,.0f} | فرق={diff_y:>15,.0f} {status}")

    # 3. حركات بدون سنة دراسية
    d_null = Transaction.objects.filter(is_debit=True, journal_entry__academic_year__isnull=True).aggregate(t=Sum('amount'))['t'] or Decimal('0')
    c_null = Transaction.objects.filter(is_debit=False, journal_entry__academic_year__isnull=True).aggregate(t=Sum('amount'))['t'] or Decimal('0')
    diff_null = d_null - c_null
    status_null = '✅' if diff_null == 0 else '❌'
    print(f"   بدون سنة: مدين={d_null:>15,.0f} | دائن={c_null:>15,.0f} | فرق={diff_null:>15,.0f} {status_null}")

    # 4. القيود بدون حركات على الإطلاق
    no_txn_count = JournalEntry.objects.filter(transactions__isnull=True).count()
    print(f"\n⚠️ قيود يومية بدون حركات: {no_txn_count}")

    # 5. أكبر 10 حسابات تسبب عدم التوازن
    print(f"\n🔎 تحليل الحسابات: مقارنة الرصيد المخزن vs الحركات الفعلية:")
    from accounts.models import Account
    accounts = Account.objects.filter(is_active=True, balance__gt=0).order_by('-balance')[:20]
    print(f"{'الكود':<20} | {'الرصيد المخزن':>18} | {'مدين الحركات':>15} | {'دائن الحركات':>15} | {'فرق':>12}")
    print("-" * 90)
    mismatch_count = 0
    for acc in accounts:
        d = acc.transactions.filter(is_debit=True).aggregate(t=Sum('amount'))['t'] or Decimal('0')
        c = acc.transactions.filter(is_debit=False).aggregate(t=Sum('amount'))['t'] or Decimal('0')
        actual = d - c if acc.account_type in ['ASSET','EXPENSE'] else c - d
        gap = acc.balance - actual
        if abs(gap) > 1:
            mismatch_count += 1
            print(f"{acc.code:<20} | {acc.balance:>18,.0f} | {d:>15,.0f} | {c:>15,.0f} | {gap:>12,.0f} ❌")
    if mismatch_count == 0:
        print("✅ لا يوجد فرق بين الرصيد المخزن والحركات الفعلية")

if __name__ == "__main__":
    main()
