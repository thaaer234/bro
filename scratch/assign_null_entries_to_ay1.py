"""
إصلاح القيود اليومية ذات academic_year = NULL:
إسنادها كلها للسنة الأولى (AY1 = 1)
"""
from accounts.models import JournalEntry, Transaction
from django.db import transaction

with transaction.atomic():
    null_entries = JournalEntry.objects.filter(academic_year__isnull=True)
    count = null_entries.count()
    print(f"Found {count} NULL journal entries -> Assigning to AY1...")
    updated = null_entries.update(academic_year_id=1)
    print(f"Updated {updated} journal entries to AY1.")

print("Done!")
