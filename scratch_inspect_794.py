import os
import sys
import django
from decimal import Decimal

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alyaman.settings')
django.setup()

sys.stdout.reconfigure(encoding='utf-8')

from students.models import Student
from accounts.models import Studentenrollment, Account, JournalEntry, Transaction, StudentReceipt

try:
    student = Student.objects.get(id=794)
    print(f"Student: {student.full_name} (ID: {student.id})")
    
    enrollments = Studentenrollment.objects.filter(student=student)
    print(f"Enrollments count: {enrollments.count()}")
    for e in enrollments:
        print(f"\nEnrollment ID: {e.id}")
        print(f"  Course: {e.course.name} (ID: {e.course.id})")
        print(f"  Total Amount: {e.total_amount}")
        print(f"  Discount Percent: {e.discount_percent}%")
        print(f"  Discount Amount: {e.discount_amount}")
        print(f"  Net Amount Property: {e.net_amount}")
        print(f"  Enrollment Journal Entry: {e.enrollment_journal_entry}")
        
        ar_account = Account.get_student_ar_account_for_course(student, e.course)
        if ar_account:
            print(f"  AR Account: {ar_account.name_ar} ({ar_account.code}) | Balance: {ar_account.balance}")
            txs = Transaction.objects.filter(account=ar_account).select_related('journal_entry')
            print(f"  Transactions count: {txs.count()}")
            for t in txs:
                print(f"    Tx ID: {t.id} | JE: {t.journal_entry.reference} ({t.journal_entry.entry_type}) | Amount: {t.amount} | Debit: {t.is_debit} | Date: {t.journal_entry.date} | Desc: {t.description}")
        else:
            print("  No AR Account!")
            
except Exception as e:
    print(f"Error: {e}")
