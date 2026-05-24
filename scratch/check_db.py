import os
import sys
import django

# Setup django environment
sys.path.append(r"c:\Users\THAAER\Desktop\project")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "alyaman.settings")
os.environ["DISABLE_BIOMETRIC_SCHEDULER"] = "true"
django.setup()

from quick.models import AcademicYear
from accounts.models import Course, Studentenrollment, StudentReceipt, JournalEntry, Account, Transaction

print("=== DB COUNTS ===")
print("Academic Years:", AcademicYear.objects.count())
print("Courses:", Course.objects.count())
print("Student Enrollments:", Studentenrollment.objects.count())
print("Student Receipts:", StudentReceipt.objects.count())
print("Journal Entries:", JournalEntry.objects.count())
print("Accounts:", Account.objects.count())
print("Transactions:", Transaction.objects.count())
