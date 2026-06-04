# -*- coding: utf-8 -*-
import sys, os
sys.stdout.reconfigure(encoding='utf-8')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alyaman.settings')
import django
django.setup()

from students.models import Student
from accounts.models import Studentenrollment, Account, JournalEntry, Transaction
from decimal import Decimal

# Find Mayas Haidar (مياس حيدر)
students = Student.objects.filter(full_name__contains='مياس حيدر')
for s in students:
    print(f"Student: ID={s.id}, Name={s.full_name}, Phone={getattr(s, 'father_phone', 'N/A') or getattr(s, 'phone', 'N/A')}")
    enrollments = Studentenrollment.objects.filter(student=s)
    for e in enrollments:
        print(f"  Enrollment: ID={e.id}, Course={e.course.name}, Total={e.total_amount}, Net={e.net_amount}, Completed={e.is_completed}")
        ar_account = Account.get_student_ar_account_for_course(s, e.course)
        if ar_account:
            print(f"    AR Account: ID={ar_account.id}, Code={ar_account.code}, Balance={ar_account.balance}")
            debit = ar_account.get_debit_balance() or Decimal('0')
            credit = ar_account.get_credit_balance() or Decimal('0')
            print(f"      Ledger Debit={debit}, Credit={credit}")
            
            # Check adjustments
            adjs = JournalEntry.objects.filter(
                entry_type='ADJUSTMENT',
                description__contains=s.full_name
            ).filter(description__contains=e.course.name)
            print(f"      Adjustment entries count={adjs.count()}")
            for adj in adjs:
                print(f"        Adj Entry: ID={adj.id}, Ref={adj.reference}, Amount={adj.total_amount}, Desc={adj.description}")
        else:
            print(f"    No AR Account found for this course!")
