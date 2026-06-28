# -*- coding: utf-8 -*-
import sys, os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alyaman.settings')
os.environ["DISABLE_BIOMETRIC_SCHEDULER"] = "true"
import django
django.setup()

from students.models import Student as StudentProfile
from accounts.models import Studentenrollment, StudentReceipt, JournalEntry, Transaction, Account

# Find student profiles matching the name
students = StudentProfile.objects.filter(full_name__icontains="ريان محروس")
print(f"Found {students.count()} student profiles:")
for s in students:
    print(f"\nStudent Profile: ID={s.id}, Name={s.full_name}, Year={s.academic_year}")
    
    # Accounts for this student
    accounts = Account.objects.filter(is_student_account=True, student_name=s.full_name)
    print(f"Accounts associated with name '{s.full_name}':")
    for acc in accounts:
        print(f"  - Account ID={acc.id}, Code={acc.code}, Name={acc.name_ar or acc.name}, Balance={acc.balance}")
        
        # Transactions for this account
        txs = Transaction.objects.filter(account=acc).select_related('journal_entry', 'journal_entry__academic_year')
        print(f"    Transactions ({txs.count()}):")
        for tx in txs:
            je = tx.journal_entry
            print(f"      * TX ID={tx.id}, Amount={tx.amount}, IsDebit={tx.is_debit}, JE ID={je.id}, Date={je.date}, Year={je.academic_year}, Posted={je.is_posted}")
            
    # Enrollments for this student
    enrollments = Studentenrollment.objects.filter(student=s)
    print(f"Enrollments ({enrollments.count()}):")
    for en in enrollments:
        print(f"  - Enrollment ID={en.id}, Course={en.course}, Year={en.academic_year}, Total={en.total_amount}")
        if en.enrollment_journal_entry:
            je = en.enrollment_journal_entry
            print(f"    * Enrollment JE ID={je.id}, Year={je.academic_year}, Posted={je.is_posted}")
            for tx in je.transactions.filter(account__student_name=s.full_name):
                print(f"      tx: {tx.id}, amount={tx.amount}, is_debit={tx.is_debit}")
        else:
            print("    * No Enrollment JE linked")
            
        if en.completion_journal_entry:
            je = en.completion_journal_entry
            print(f"    * Completion JE ID={je.id}, Year={je.academic_year}, Posted={je.is_posted}")
            for tx in je.transactions.filter(account__student_name=s.full_name):
                print(f"      tx: {tx.id}, amount={tx.amount}, is_debit={tx.is_debit}")
        else:
            print("    * No Completion JE linked")
            
        # Receipts
        receipts = StudentReceipt.objects.filter(enrollment=en)
        print(f"  - Receipts ({receipts.count()}):")
        for re in receipts:
            print(f"    * Receipt ID={re.id}, Paid={re.paid_amount}, Date={re.date}")
            if re.journal_entry:
                je = re.journal_entry
                print(f"      Receipt JE ID={je.id}, Year={je.academic_year}, Posted={je.is_posted}")
                for tx in je.transactions.filter(account__student_name=s.full_name):
                    print(f"        tx: {tx.id}, amount={tx.amount}, is_debit={tx.is_debit}")
            else:
                print("      No Receipt JE linked")
