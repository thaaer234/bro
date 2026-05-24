"""
تشخيص معمق لمشكلة الصناديق:
- لماذا debits في AY1 لكن credits في NULL؟
"""
from accounts.models import Account, Transaction, JournalEntry
from django.db.models import Sum

a = Account.objects.get(code='121-0008')

# فحص طبيعة معاملات AY1 - هل هي receipts أم expenses؟
ay1_debits = Transaction.objects.filter(
    account=a, journal_entry__academic_year_id=1, is_debit=True
).select_related('journal_entry').order_by('journal_entry__date')

print("=== AY1 DEBITS (Credits incoming to cashbox) ===")
for t in ay1_debits[:30]:
    je = t.journal_entry
    print(f"  {je.date} | +{t.amount:>12,.0f} | JE#{je.id} | {(je.description or 'N/A')[:60]}")

print()
ay1_credits = Transaction.objects.filter(
    account=a, journal_entry__academic_year_id=1, is_debit=False
).select_related('journal_entry').order_by('journal_entry__date')

print("=== AY1 CREDITS (Cash going out from cashbox) ===")
for t in ay1_credits[:30]:
    je = t.journal_entry
    print(f"  {je.date} | -{t.amount:>12,.0f} | JE#{je.id} | {(je.description or 'N/A')[:60]}")

print()
print("=== NULL CREDITS SAMPLE (Cash going out, stored as NULL AY) ===")
null_credits = Transaction.objects.filter(
    account=a, journal_entry__academic_year__isnull=True, is_debit=False
).select_related('journal_entry').order_by('-journal_entry__date')

for t in null_credits[:20]:
    je = t.journal_entry
    print(f"  {je.date} | -{t.amount:>12,.0f} | JE#{je.id} | {(je.description or 'N/A')[:60]}")

print()
print("=== NULL DEBITS SAMPLE ===")
null_debits = Transaction.objects.filter(
    account=a, journal_entry__academic_year__isnull=True, is_debit=True
).select_related('journal_entry').order_by('-journal_entry__date')

for t in null_debits[:20]:
    je = t.journal_entry
    print(f"  {je.date} | +{t.amount:>12,.0f} | JE#{je.id} | {(je.description or 'N/A')[:60]}")
