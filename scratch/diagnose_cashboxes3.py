"""
فحص معمق للقيود في AY1 و AY2 التي تمس صندوق 121-0008 بعد الإصلاح
"""
from accounts.models import Account, Transaction, JournalEntry
from django.db.models import Sum

a = Account.objects.get(code='121-0008')

print("=== AY2 DEBITS (should be receipts from Year2 courses) ===")
ay2_debits = Transaction.objects.filter(
    account=a, journal_entry__academic_year_id=2, is_debit=True
).select_related('journal_entry').order_by('journal_entry__date')[:20]
for t in ay2_debits:
    je = t.journal_entry
    print(f"  {je.date} | +{t.amount:>12,.0f} | JE#{je.id} | {(je.description or 'N/A')[:70]}")

print()
print("=== AY1 CREDITS (expensive outflows in Year1) ===")
ay1_credits = Transaction.objects.filter(
    account=a, journal_entry__academic_year_id=1, is_debit=False
).select_related('journal_entry').order_by('-journal_entry__date')[:20]
for t in ay1_credits:
    je = t.journal_entry
    print(f"  {je.date} | -{t.amount:>12,.0f} | JE#{je.id} | {(je.description or 'N/A')[:70]}")

print()
# هل AY2 debit entries - هل جميعها كانت NULL قبل (وأصبحت AY1 بعد التحويل)؟
print("=== Are AY2 debits on cashbox 121-0008 NEW Year2 receipts or old ones? ===")
ay2_debit_je_ids = list(
    Transaction.objects.filter(account=a, journal_entry__academic_year_id=2, is_debit=True)
    .values_list('journal_entry_id', flat=True)
)
print(f"Total AY2 debit JE IDs: {len(ay2_debit_je_ids)}")
if ay2_debit_je_ids:
    sample_je = JournalEntry.objects.filter(id__in=ay2_debit_je_ids[:5])
    for je in sample_je:
        print(f"  JE#{je.id} | {je.date} | AY:{je.academic_year_id} | {(je.description or 'N/A')[:60]}")

print()
print("=== Summary: AY1 vs AY2 on 121-0008 ===")
d1 = Transaction.objects.filter(account=a, journal_entry__academic_year_id=1, is_debit=True).aggregate(s=Sum('amount'))['s'] or 0
c1 = Transaction.objects.filter(account=a, journal_entry__academic_year_id=1, is_debit=False).aggregate(s=Sum('amount'))['s'] or 0
d2 = Transaction.objects.filter(account=a, journal_entry__academic_year_id=2, is_debit=True).aggregate(s=Sum('amount'))['s'] or 0
c2 = Transaction.objects.filter(account=a, journal_entry__academic_year_id=2, is_debit=False).aggregate(s=Sum('amount'))['s'] or 0
dn = Transaction.objects.filter(account=a, journal_entry__academic_year__isnull=True, is_debit=True).aggregate(s=Sum('amount'))['s'] or 0
cn = Transaction.objects.filter(account=a, journal_entry__academic_year__isnull=True, is_debit=False).aggregate(s=Sum('amount'))['s'] or 0
print(f"AY1: debit={d1:,.0f}  credit={c1:,.0f}  net={d1-c1:,.0f}")
print(f"AY2: debit={d2:,.0f}  credit={c2:,.0f}  net={d2-c2:,.0f}")
print(f"NULL: debit={dn:,.0f}  credit={cn:,.0f}  net={dn-cn:,.0f}")
print(f"Total NET: {d1-c1+d2-c2+dn-cn:,.0f}")
