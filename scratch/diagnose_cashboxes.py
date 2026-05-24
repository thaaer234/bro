import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alyaman.settings')
django.setup()

from accounts.models import Account, Transaction, JournalEntry
from django.db.models import Sum

def get_net(account, ay_id=None, ay_null=False):
    qs = Transaction.objects.filter(account=account)
    if ay_null:
        qs = qs.filter(journal_entry__academic_year__isnull=True)
    elif ay_id is not None:
        qs = qs.filter(journal_entry__academic_year_id=ay_id)
    debit = qs.filter(is_debit=True).aggregate(s=Sum('amount'))['s'] or 0
    credit = qs.filter(is_debit=False).aggregate(s=Sum('amount'))['s'] or 0
    return debit, credit, debit - credit

print("=" * 80)
print("CASHBOX ACCOUNTS ANALYSIS (121-xxxx)")
print("=" * 80)

cashboxes = Account.objects.filter(code__startswith='121-0').order_by('code')
for a in cashboxes:
    d1, c1, n1 = get_net(a, ay_id=1)
    d2, c2, n2 = get_net(a, ay_id=2)
    dn, cn, nn = get_net(a, ay_null=True)
    total = n1 + n2 + nn
    print(f"\n  {a.code} - {a.name}")
    print(f"    AY1: debit={d1:>15,.0f}  credit={c1:>15,.0f}  net={n1:>15,.0f}")
    print(f"    AY2: debit={d2:>15,.0f}  credit={c2:>15,.0f}  net={n2:>15,.0f}")
    print(f"    NULL:debit={dn:>15,.0f}  credit={cn:>15,.0f}  net={nn:>15,.0f}")
    print(f"    TOTAL:                                            net={total:>15,.0f}")

print("\n" + "=" * 80)
print("JOURNAL ENTRIES IN AY1 TOUCHING CASHBOXES (sample of 121-0008)")
print("=" * 80)

a = Account.objects.get(code='121-0008')
ay1_txns = Transaction.objects.filter(account=a, journal_entry__academic_year_id=1).select_related('journal_entry').order_by('-journal_entry__date')[:20]
for t in ay1_txns:
    je = t.journal_entry
    side = "DEBIT " if t.is_debit else "CREDIT"
    print(f"  {je.date} | {side} {t.amount:>12,.0f} | JE#{je.id} | {je.description[:50] if je.description else 'N/A'}")

print("\n" + "=" * 80)
print("JOURNAL ENTRIES IN AY2 TOUCHING CASHBOX 121-0008 (first 20 debits)")
print("=" * 80)

ay2_txns = Transaction.objects.filter(account=a, journal_entry__academic_year_id=2, is_debit=True).select_related('journal_entry').order_by('-journal_entry__date')[:20]
for t in ay2_txns:
    je = t.journal_entry
    print(f"  {je.date} | DEBIT  {t.amount:>12,.0f} | JE#{je.id} | {je.description[:50] if je.description else 'N/A'}")
