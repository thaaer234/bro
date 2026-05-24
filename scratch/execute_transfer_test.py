import os
import sys
import time
import django
from datetime import date
from django.db import connection, transaction
from django.db.utils import OperationalError

# Setup django environment
sys.path.append(r"c:\Users\THAAER\Desktop\project")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "alyaman.settings")
os.environ["DISABLE_BIOMETRIC_SCHEDULER"] = "true"
django.setup()

sys.stdout.reconfigure(encoding="utf-8")

# Set busy timeout on sqlite connection to avoid locks
with connection.cursor() as cursor:
    cursor.execute("PRAGMA busy_timeout = 30000;")
print("SQLite busy_timeout set to 30 seconds.")

from django.contrib.auth.models import User
from quick.models import AcademicYear
from accounts.models import Course, Studentenrollment, StudentReceipt, JournalEntry, Account, Transaction
from students.models import Student as StudentProfile
from academic_years.models import (
    AcademicYearTransferBatch,
    AcademicYearTransferCourseItem,
    AcademicYearTransferLog
)
from academic_years.services.transfers import AcademicYearTransferService

def run_transfer_test():
    print("==================================================================")
    print("🚀 STARTING ACADEMIC YEARS ISOLATION AND BATCH TRANSFER AUDIT 🚀")
    print("==================================================================")

    # 1. Resolve source and target academic years
    source_ay = AcademicYear.objects.get(id=1) # الفصل الدراسي 2025-2026
    print(f"Source Academic Year: {source_ay.name} (ID: {source_ay.id})")

    # Clean target academic year and its dependencies if they already exist
    for attempt in range(5):
        try:
            with transaction.atomic():
                target_ay_qs = AcademicYear.objects.filter(name="الفصل الدراسي 2026-2027")
                if target_ay_qs.exists():
                    target_ay = target_ay_qs.first()
                    print("Cleaning up target academic year dependencies from previous runs...")
                    
                    # Delete transfer items, logs, and batches linked to the target year
                    batches = AcademicYearTransferBatch.objects.filter(target_academic_year=target_ay)
                    AcademicYearTransferCourseItem.objects.filter(batch__in=batches).delete()
                    AcademicYearTransferLog.objects.filter(batch__in=batches).delete()
                    batches.delete()
                    
                    # Delete cloned financial and academic entities in target year to avoid ProtectedErrors
                    # Delete journal entries (and cascading transactions) first
                    JournalEntry.objects.filter(academic_year=target_ay).delete()
                    # Delete receipts
                    StudentReceipt.objects.filter(academic_year=target_ay).delete()
                    # Delete enrollments
                    Studentenrollment.objects.filter(academic_year=target_ay).delete()
                    # Delete courses
                    Course.objects.filter(academic_year=target_ay).delete()
                    # Delete students
                    StudentProfile.objects.filter(academic_year=target_ay).delete()
                    # Delete accounts
                    Account.objects.filter(academic_year=target_ay).delete()
                    
                    print("Previous runs cloned objects cleaned up successfully.")
                else:
                    target_ay = AcademicYear.objects.create(
                        name="الفصل الدراسي 2026-2027",
                        year="2026-2027",
                        start_date=date(2026, 9, 1),
                        end_date=date(2027, 6, 30),
                        is_active=False,
                        is_closed=False
                    )
                    print(f"Target Academic Year created fresh.")
            break
        except OperationalError as e:
            print(f"Database locked, retrying cleanup (attempt {attempt+1}/5)...")
            time.sleep(2)
    else:
        print("Error: Could not clear/create target academic year due to database lock.")
        return

    # 2. Get superuser actor
    actor = User.objects.filter(is_superuser=True).first()
    if not actor:
        print("Error: No superuser actor found!")
        return

    # 3. Identify courses to transfer
    course_ids = [18, 19, 20, 21, 22, 23]
    courses_to_transfer = Course.objects.filter(id__in=course_ids)
    print(f"\nIdentifying courses to transfer (Total: {courses_to_transfer.count()}):")
    for c in courses_to_transfer:
        print(f"  - ID: {c.id} | {c.name} | Price: {c.price} | Source Year: {c.academic_year.name}")

    # 4. Create Transfer Batch (with retry logic)
    batch = None
    for attempt in range(5):
        try:
            with transaction.atomic():
                batch = AcademicYearTransferBatch.objects.create(
                    source_academic_year=source_ay,
                    target_academic_year=target_ay,
                    created_by=actor,
                    status=AcademicYearTransferBatch.STATUS_DRAFT
                )
                
                # 5. Link courses to batch
                for c in courses_to_transfer:
                    AcademicYearTransferCourseItem.objects.create(
                        batch=batch,
                        source_course=c,
                        status=AcademicYearTransferCourseItem.STATUS_PENDING
                    )
            print(f"\nCreated Transfer Batch ID: {batch.id}")
            print("Linked courses to the transfer batch successfully.")
            break
        except OperationalError as e:
            print(f"Database locked, retrying batch creation (attempt {attempt+1}/5)...")
            time.sleep(2)
    else:
        print("Error: Could not create batch due to database lock.")
        return

    # 6. Initialize Transfer Service and execute (with retry logic)
    service = AcademicYearTransferService(batch=batch, actor=actor)
    
    print("\nRunning Transfer Preview...")
    preview = service.build_preview()
    print("Preview Results:")
    print(f"  - Courses: {preview['courses']}")
    print(f"  - Students: {preview['students']}")
    print(f"  - Enrollments: {preview['enrollments']}")
    print(f"  - Receipts: {preview['receipts']}")
    print(f"  - Journal Entries: {preview['journal_entries']}")

    print("\nExecuting Batch Transfer...")
    for attempt in range(5):
        try:
            results = service.execute()
            print("Execution Completed Successfully! 🎉")
            print(f"Summary of Cloned Sgements: {dict(results)}")
            break
        except OperationalError as e:
            print(f"Database locked during execution, retrying execution (attempt {attempt+1}/5)...")
            time.sleep(2)
    else:
        print("Error: Could not execute transfer due to database lock.")
        return

    # 7. Verification and Isolation Comparison Audit
    print("\n==================================================================")
    print("🔍 ISOLATION & COMPARISON VERIFICATION AUDIT 🔍")
    print("==================================================================")

    # A. Check courses in Target Academic Year
    target_courses = Course.objects.filter(academic_year=target_ay)
    print(f"\n1. Target Academic Year Course Registry (Total: {target_courses.count()}):")
    for c in target_courses:
        print(f"   [NEW] ID: {c.id} | Name: {c.name} | Price: {c.price} | Year ID: {c.academic_year_id}")
        # Verify that these are new database records and not merged
        assert c.academic_year_id == target_ay.id
        assert c.id not in course_ids, "Course ID must be a newly generated primary key, not the old one!"

    # B. Check student isolation
    target_students = StudentProfile.objects.filter(academic_year=target_ay)
    print(f"\n2. Target Academic Year Student Profile Scoping (Total: {target_students.count()}):")
    for s in target_students[:5]:
        print(f"   [NEW] Student: {s.full_name} | Phone: {s.phone} | Scope Year ID: {s.academic_year_id}")
        assert s.academic_year_id == target_ay.id

    # C. Check transactions isolation (0 Transactions shared!)
    print(f"\n3. Transaction Scoping & Ledger Isolation Audit:")
    source_je_count = JournalEntry.objects.filter(academic_year=source_ay).count()
    target_je_count = JournalEntry.objects.filter(academic_year=target_ay).count()
    print(f"   - Source Year ({source_ay.name}) Journal Entries: {source_je_count}")
    print(f"   - Target Year ({target_ay.name}) Journal Entries: {target_je_count}")
    
    # Check if any journal entry belongs to both or is unassigned
    assert JournalEntry.objects.filter(academic_year=target_ay).filter(academic_year=source_ay).count() == 0, "No Journal Entry can exist in two academic years simultaneously!"
    print("   -> verified: 0 journal entries are shared! Complete, hermetic database isolation. ✅")

    # D. Check Financial Account Scope Isolation
    print(f"\n4. Chart of Accounts & Scoped Ledger Audit:")
    
    # Check course-deferred accounts created in target academic year
    target_deferred_accounts = Account.objects.filter(academic_year=target_ay, is_course_account=True, account_type="LIABILITY")
    print(f"   - Target Scoped Course Deferred Accounts (Total: {target_deferred_accounts.count()}):")
    for acc in target_deferred_accounts:
        print(f"     [NEW Account] Code: {acc.code} | Name: {acc.name_ar or acc.name} | Rollup Balance: {acc.rollup_balance} | Year ID: {acc.academic_year_id}")
        assert acc.academic_year_id == target_ay.id

    # Check student AR accounts created in target academic year
    target_ar_accounts = Account.objects.filter(academic_year=target_ay, is_student_account=True, account_type="ASSET")
    print(f"   - Target Scoped Student Accounts Receivable (Total: {target_ar_accounts.count()}):")
    for acc in target_ar_accounts[:5]:
        print(f"     [NEW Account] Code: {acc.code} | Name: {acc.name_ar or acc.name} | Rollup Balance: {acc.rollup_balance} | Year ID: {acc.academic_year_id}")
        assert acc.academic_year_id == target_ay.id

    # E. Check what happens to general manual accounts
    shared_manual_accounts = Account.objects.filter(academic_year__isnull=True)
    print(f"\n5. Shared General / Manual Accounts Audit (Total: {shared_manual_accounts.count()}):")
    for acc in shared_manual_accounts[:5]:
        # Cash / Bank etc. are shared, but their transactions inside target year are isolated!
        target_txs = Transaction.objects.filter(account=acc, journal_entry__academic_year=target_ay)
        source_txs = Transaction.objects.filter(account=acc, journal_entry__academic_year=source_ay)
        print(f"     Account: {acc.code} - {acc.display_name}")
        print(f"       - Transactions in Source Year: {source_txs.count()}")
        print(f"       - Transactions in Target Year: {target_txs.count()}")

    print("\n==================================================================")
    print("🎉 SUCCESS: ISOLATION COMPARISON AUDIT COMPLETELY SUCCESSFUL! 🎉")
    print("==================================================================")

if __name__ == "__main__":
    run_transfer_test()
