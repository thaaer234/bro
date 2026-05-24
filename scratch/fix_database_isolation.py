import os
import django
from django.db import transaction

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alyaman.settings')
django.setup()

from accounts.models import Course, Studentenrollment, StudentReceipt, Account, JournalEntry, Transaction
from quick.models import AcademicYear, QuickStudent, QuickEnrollment, QuickStudentReceipt, QuickCourse
from academic_years.models import AcademicYearTransferCourseItem

def run_fix():
    print("=== STARTING DATABASE ISOLATION AND REPAIR SCRIPT ===")
    
    with transaction.atomic():
        # =====================================================================
        # 1. DELETE DUPLICATE YEAR 1 DATA (COURSES 18, 19, 20, 21, 22, 23)
        # =====================================================================
        courses_to_delete_ids = [18, 19, 20, 21, 22, 23]
        courses_to_delete = Course.objects.filter(id__in=courses_to_delete_ids)
        print(f"\n[1] Deleting duplicate courses: {list(courses_to_delete_ids)}")
        
        # Let's count them first
        enrollments = Studentenrollment.objects.filter(course__in=courses_to_delete)
        receipts = StudentReceipt.objects.filter(course__in=courses_to_delete)
        
        print(f"-> Found {courses_to_delete.count()} course(s) to delete.")
        print(f"-> Found {enrollments.count()} enrollment(s) to delete.")
        print(f"-> Found {receipts.count()} receipt(s) to delete.")
        
        # To avoid ProtectedError (since StudentReceipt.enrollment has on_delete=models.PROTECT),
        # we must delete the StudentReceipt records first.
        # Calling receipt.delete() will trigger the pre_delete signal which automatically
        # deletes the linked JournalEntry and its Transactions cleanly.
        for receipt in receipts:
            receipt.delete()
        print("-> Cleaned up all receipts via cascade signals.")
        
        # Now we can safely delete the Studentenrollment records.
        # Calling enrollment.delete() will trigger the pre_delete signal which automatically
        # deletes enrollment journal entries, completion journal entries, and their transactions.
        for enrollment in enrollments:
            enrollment.delete()
        print("-> Cleaned up all enrollments via cascade signals.")
        
        # Delete AcademicYearTransferCourseItem records referencing duplicate courses to avoid ProtectedError
        transfer_items = AcademicYearTransferCourseItem.objects.filter(source_course__in=courses_to_delete)
        print(f"-> Found {transfer_items.count()} transfer course items referencing duplicate courses. Deleting...")
        transfer_items.delete()
        
        # Now, identify the course-specific accounts
        accounts_to_delete = Account.objects.filter(
            code__regex=r'^(1251|21001|4101)-0(18|19|20|21|22|23)'
        )
        print(f"-> Found {accounts_to_delete.count()} course-specific accounts to delete.")
        
        # If there are any dangling transactions on these accounts
        dangling_transactions = Transaction.objects.filter(account__in=accounts_to_delete)
        if dangling_transactions.exists():
            print(f"-> Found {dangling_transactions.count()} dangling transactions on these accounts. Deleting their journal entries...")
            dangling_entries = set(t.journal_entry for t in dangling_transactions if t.journal_entry)
            for entry in dangling_entries:
                entry._skip_linked_cleanup = True
                entry.transactions.all().delete()
                entry.delete()
                
        # Delete the accounts
        accounts_to_delete.delete()
        print("-> Deleted all duplicate course-specific accounts.")
        
        # Delete the course objects themselves
        courses_to_delete.delete()
        print("-> Deleted duplicate Course objects.")
        
        # =====================================================================
        # 2. MIGRATE COURSE 24 (دورة شتاء تمهيدي2026-2027) TO ACADEMIC YEAR 2
        # =====================================================================
        print("\n[2] Migrating Course 24 to Academic Year 2")
        course_24 = Course.objects.filter(id=24).first()
        if course_24:
            print(f"-> Course 24 found: '{course_24.name}' (current AY: {course_24.academic_year_id})")
            
            # Update course academic year
            course_24.academic_year_id = 2
            course_24.save()
            print("-> Updated course academic year to 2.")
            
            # Migrate student enrollments
            enrollments_24 = Studentenrollment.objects.filter(course=course_24)
            for enrollment in enrollments_24:
                enrollment.academic_year_id = 2
                enrollment.save()
                
                # Migrate linked journal entries
                if enrollment.enrollment_journal_entry:
                    enrollment.enrollment_journal_entry.academic_year_id = 2
                    enrollment.enrollment_journal_entry.save()
                if enrollment.completion_journal_entry:
                    enrollment.completion_journal_entry.academic_year_id = 2
                    enrollment.completion_journal_entry.save()
            print(f"-> Migrated {enrollments_24.count()} enrollments to Academic Year 2.")
            
            # Migrate student receipts
            receipts_24 = StudentReceipt.objects.filter(course=course_24)
            for receipt in receipts_24:
                receipt.academic_year_id = 2
                receipt.save()
                
                # Migrate linked journal entries
                if receipt.journal_entry:
                    receipt.journal_entry.academic_year_id = 2
                    receipt.journal_entry.save()
            print(f"-> Migrated {receipts_24.count()} receipts to Academic Year 2.")
            
            # Migrate course-specific accounts
            accounts_24 = Account.objects.filter(code__regex=r'^(1251|21001|4101)-024')
            for account in accounts_24:
                account.academic_year_id = 2
                account.save()
            print(f"-> Migrated {accounts_24.count()} related accounts to Academic Year 2.")
        else:
            print("-> Warning: Course 24 not found.")
            
        # =====================================================================
        # 3. REPAIR NULL QUICK ACCOUNTS (1252-xxx, 2151-xxx, 4111-xxx)
        # =====================================================================
        print("\n[3] Repairing NULL Quick Accounts")
        
        # 1252-xxx (Quick Students Accounts Receivable)
        null_student_accounts = Account.objects.filter(code__startswith='1252-', academic_year__isnull=True)
        print(f"-> Found {null_student_accounts.count()} student accounts with NULL academic year.")
        repaired_students = 0
        for account in null_student_accounts:
            try:
                # Extract student ID from code e.g. "1252-020" -> 20
                student_id_str = account.code.split('-')[1]
                student_id = int(student_id_str)
                student = QuickStudent.objects.filter(id=student_id).first()
                if student and student.academic_year:
                    account.academic_year = student.academic_year
                    account.save()
                    repaired_students += 1
                else:
                    account.academic_year_id = 1  # Fallback to Year 1
                    account.save()
                    repaired_students += 1
            except Exception as e:
                print(f"   ! Error repairing student account {account.code}: {e}")
        print(f"-> Successfully repaired {repaired_students} student accounts.")
        
        # 2151-xxx and 4111-xxx (Quick Course Accounts)
        null_course_accounts = Account.objects.filter(code__regex=r'^(2151|4111)-', academic_year__isnull=True)
        print(f"-> Found {null_course_accounts.count()} quick course accounts with NULL academic year.")
        repaired_courses = 0
        for account in null_course_accounts:
            try:
                # Extract course ID from code e.g. "2151-018" -> 18
                course_id_str = account.code.split('-')[1]
                course_id = int(course_id_str)
                course = QuickCourse.objects.filter(id=course_id).first()
                if course and course.academic_year:
                    account.academic_year = course.academic_year
                    account.save()
                    repaired_courses += 1
                else:
                    account.academic_year_id = 1  # Fallback to Year 1
                    account.save()
                    repaired_courses += 1
            except Exception as e:
                print(f"   ! Error repairing quick course account {account.code}: {e}")
        print(f"-> Successfully repaired {repaired_courses} quick course accounts.")
        
        # =====================================================================
        # 4. REBUILD ALL ACCOUNT BALANCES
        # =====================================================================
        print("\n[4] Rebuilding all account balances...")
        Account.rebuild_all_balances()
        print("-> All account balances successfully rebuilt.")
        print("\n=== DATABASE ISOLATION AND REPAIR COMPLETED SUCCESSFULLY ===")

if __name__ == '__main__':
    run_fix()
