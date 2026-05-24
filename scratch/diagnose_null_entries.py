"""
تشخيص القيود اليومية ذات academic_year = NULL
"""
from accounts.models import JournalEntry, Transaction
from quick.models import AcademicYear
from django.db.models import Count, Sum
from datetime import date

# جلب السنوات الدراسية
years = list(AcademicYear.objects.all().order_by('id'))
for y in years:
    print(f"AY{y.id}: {y.name} | start={y.start_date} end={y.end_date}")

print()
print("=" * 80)

null_entries = JournalEntry.objects.filter(academic_year__isnull=True)
print(f"Total NULL academic_year journal entries: {null_entries.count()}")

# توزيع حسب الشهر
from django.db.models.functions import TruncMonth
monthly = null_entries.annotate(month=TruncMonth('date')).values('month').annotate(count=Count('id')).order_by('month')
print("\nDistribution by month:")
for m in monthly:
    print(f"  {m['month'].strftime('%Y-%m') if m['month'] else 'None'}: {m['count']} entries")

print()
print("Sample descriptions of NULL entries (types):")
samples = null_entries.values('description').annotate(count=Count('id')).order_by('-count')[:20]
for s in samples:
    desc = (s['description'] or 'N/A')[:70]
    print(f"  [{s['count']:>4}] {desc}")

print()
print("=" * 80)
print("Are NULL entries touching cashboxes?")
null_cashbox_txns = Transaction.objects.filter(
    journal_entry__academic_year__isnull=True,
    account__code__startswith='121-'
)
print(f"Transactions in cashboxes with NULL AY: {null_cashbox_txns.count()}")
by_cashbox = null_cashbox_txns.values('account__code').annotate(count=Count('id')).order_by('-count')
for row in by_cashbox:
    print(f"  {row['account__code']}: {row['count']} transactions")
