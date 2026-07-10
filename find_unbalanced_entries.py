# -*- coding: utf-8 -*-
"""
سكريبت لإيجاد القيود اليومية الغير متوازنة (مدين ≠ دائن)
"""
import os, sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alyaman.settings')
os.environ["DISABLE_BIOMETRIC_SCHEDULER"] = "true"
import django
django.setup()

from django.db.models import Sum, F, Value, DecimalField
from django.db.models.functions import Coalesce
from accounts.models import JournalEntry, Transaction
from decimal import Decimal

def main():
    print("🔍 البحث عن القيود اليومية الغير متوازنة...")

    entries = JournalEntry.objects.all()
    total = entries.count()
    print(f"   إجمالي القيود: {total}")

    unbalanced = []
    total_imbalance = Decimal('0')

    for je in entries.prefetch_related('transactions'):
        txns = je.transactions.all()
        debit = sum(t.amount for t in txns if t.is_debit)
        credit = sum(t.amount for t in txns if not t.is_debit)
        diff = debit - credit
        if diff != 0:
            unbalanced.append({
                'id': je.id,
                'ref': je.reference,
                'date': je.date,
                'desc': je.description[:50] if je.description else '',
                'debit': debit,
                'credit': credit,
                'diff': diff,
            })
            total_imbalance += diff

    print(f"\n📊 عدد القيود الغير متوازنة: {len(unbalanced)}")
    print(f"📊 إجمالي الفرق التراكمي: {total_imbalance:,.0f}")
    print()

    if unbalanced:
        print("=" * 90)
        print(f"{'ID':>6} | {'التاريخ':<12} | {'المرجع':<20} | {'مدين':>15} | {'دائن':>15} | {'فرق':>15}")
        print("=" * 90)
        for r in sorted(unbalanced, key=lambda x: abs(x['diff']), reverse=True)[:30]:
            print(f"{r['id']:>6} | {str(r['date']):<12} | {r['ref']:<20} | {r['debit']:>15,.0f} | {r['credit']:>15,.0f} | {r['diff']:>15,.0f}")
        print("=" * 90)
        if len(unbalanced) > 30:
            print(f"... وغيرها {len(unbalanced)-30} قيد")
    else:
        print("✅ جميع القيود متوازنة! المشكلة في طريقة عرض الميزان.")

if __name__ == "__main__":
    main()
