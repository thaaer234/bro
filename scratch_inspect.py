import os
import sys
import django
from decimal import Decimal


os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alyaman.settings')
django.setup()

from students.models import Student
from accounts.models import Studentenrollment, Account, JournalEntry, Transaction
from quick.models import QuickStudent, QuickEnrollment

print("=== INSPECTING AHMED GHOURANI ===")

# Search for both students
students = Student.objects.filter(full_name__icontains="أحمد غوراني") | Student.objects.filter(full_name__icontains="احمد غوراني")
for s in students.distinct():
    print(f"\nStudent: {s.full_name} (ID: {s.id})")
    print(f"Phone: {s.phone}, Father Phone: {s.father_phone}")
    
    # Enrollments
    enrollments = Studentenrollment.objects.filter(student=s)
    print(f"Enrollments count: {enrollments.count()}")
    for e in enrollments:
        print(f"  Enrollment ID: {e.id}")
        print(f"    Course: {e.course.name} (ID: {e.course.id})")
        print(f"    Academic Year: {e.academic_year.name if e.academic_year else 'None'}")
        print(f"    Total Amount: {e.total_amount}")
        print(f"    Discount Percent: {e.discount_percent}%")
        print(f"    Discount Amount: {e.discount_amount}")
        print(f"    Net Amount Property: {e.net_amount}")
        print(f"    Enrollment Journal Entry: {e.enrollment_journal_entry}")
        
        ar_account = Account.get_student_ar_account_for_course(s, e.course)
        if ar_account:
            print(f"    AR Account: {ar_account.name_ar} ({ar_account.code})")
            print(f"      Balance: {ar_account.balance}")
            print(f"      Debit Balance: {ar_account.get_debit_balance()}")
            print(f"      Credit Balance: {ar_account.get_credit_balance()}")
            
            # Transactions
            txs = Transaction.objects.filter(account=ar_account).select_related('journal_entry')
            print(f"      Transactions count: {txs.count()}")
            for t in txs:
                print(f"        Tx ID: {t.id} | JE: {t.journal_entry.reference} ({t.journal_entry.entry_type}) | Amount: {t.amount} | Debit: {t.is_debit} | Date: {t.journal_entry.date} | Desc: {t.description}")
        else:
            print("    No AR Account found!")
