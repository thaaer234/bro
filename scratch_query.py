# -*- coding: utf-8 -*-
import sys, os
sys.stdout.reconfigure(encoding='utf-8')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alyaman.settings')
import django
django.setup()

from students.models import Student
from accounts.models import Studentenrollment, Account, JournalEntry, Transaction
from decimal import Decimal
from students.views import recalculate_account_balances

with django.db.transaction.atomic():
    student = Student.objects.get(id=117)
    
    # 1. Clean up old enrollment (ID: 109)
    e109 = Studentenrollment.objects.get(id=109)
    print(f"Old Enrollment 109 before: Gross={e109.total_amount}, Disc%={e109.discount_percent}, Net={e109.net_amount}, Completed={e109.is_completed}")
    
    # Set discount back to 0 because student paid full 7.5M
    e109.discount_percent = Decimal('0.00')
    e109.discount_amount = Decimal('0.00')
    e109.is_completed = True
    e109.save()
    print("Updated Enrollment 109 discount to 0 and marked is_completed=True")
    
    # Delete the incorrect Adjustment entry JE-011609 (ID: 21108)
    adj_109 = JournalEntry.objects.filter(id=21108)
    if adj_109.exists():
        adj = adj_109.first()
        print(f"Deleting incorrect adjustment: {adj.reference} - {adj.description}")
        adj._skip_linked_cleanup = True
        adj.transactions.all().delete()
        adj.delete()
        
    # Recalculate account 276
    acc276 = Account.objects.get(id=276)
    
    # 2. Clean up new enrollment (ID: 750)
    e750 = Studentenrollment.objects.get(id=750)
    print(f"New Enrollment 750 before: Gross={e750.total_amount}, Disc%={e750.discount_percent}, Net={e750.net_amount}")
    
    # Delete adjustments for course 2026-2027 (JE-011608 and JE-011947)
    adjs_750 = JournalEntry.objects.filter(
        entry_type='ADJUSTMENT',
        description__contains=student.full_name
    ).filter(description__contains=e750.course.name)
    for adj in adjs_750:
        print(f"Deleting duplicate/incorrect adjustment for new course: {adj.reference} - {adj.description}")
        adj._skip_linked_cleanup = True
        adj.transactions.all().delete()
        adj.delete()
        
    # Ensure main enrollment entry is set to correct net (7,600,000.00)
    je_750 = e750.enrollment_journal_entry
    if je_750:
        print(f"Updating main enrollment entry {je_750.reference} to Net 7,600,000.00")
        je_750.total_amount = Decimal('7600000.00')
        je_750.save(update_fields=['total_amount'])
        for t in je_750.transactions.all():
            t.amount = Decimal('7600000.00')
            t.save(update_fields=['amount'])
            
    acc2842 = Account.objects.get(id=2842)
    
    # Recalculate balances
    recalculate_account_balances(acc276, acc2842)
    
    print("\nAfter Fixes:")
    acc276.refresh_from_db()
    acc2842.refresh_from_db()
    print(f"Account 276 (Old course) Balance: {acc276.balance}")
    print(f"Account 2842 (New course) Balance: {acc2842.balance}")
