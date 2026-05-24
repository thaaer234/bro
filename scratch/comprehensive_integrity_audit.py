import os
import sys
import django
from decimal import Decimal

# Setup django environment
sys.path.append(r"c:\Users\THAAER\Desktop\project")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "alyaman.settings")
django.setup()

sys.stdout.reconfigure(encoding="utf-8")

from quick.models import AcademicYear
from accounts.models import Course, Studentenrollment, StudentReceipt, JournalEntry, Account, Transaction
from students.models import Student as StudentProfile

def run_comprehensive_audit():
    print("==================================================================")
    print("🔍 RUNNING COMPREHENSIVE FINANCIAL & OPERATIONAL INTEGRITY AUDIT 🔍")
    print("==================================================================")

    # 1. Resolve active and target academic years
    target_ay_qs = AcademicYear.objects.filter(name="الفصل الدراسي 2026-2027")
    if not target_ay_qs.exists():
        print("❌ Error: Target Academic Year 'الفصل الدراسي 2026-2027' does not exist in DB!")
        return
    
    target_ay = target_ay_qs.first()
    print(f"Auditing Target Academic Year: {target_ay.name} (ID: {target_ay.id})")

    # Audit Flag
    has_errors = False

    # A. JOURNAL ENTRY BALANCE INTEGRITY AUDIT
    print("\n--- A. JOURNAL ENTRY BALANCE INTEGRITY AUDIT ---")
    jes = JournalEntry.objects.filter(academic_year=target_ay)
    print(f"Total Journal Entries to audit in target year: {jes.count()}")
    
    unbalanced_jes = 0
    for je in jes:
        txs = je.transactions.all()
        debits = sum(t.amount for t in txs if t.is_debit)
        credits = sum(t.amount for t in txs if not t.is_debit)
        difference = abs(debits - credits)
        if difference > Decimal("0.01"):
            print(f"  ❌ Unbalanced JE: {je.reference} | Date: {je.date} | Debits: {debits} | Credits: {credits} | Diff: {difference}")
            unbalanced_jes += 1
            has_errors = True
            
    if unbalanced_jes == 0:
        print("  ✅ All cloned journal entries are perfectly balanced (Debits == Credits)! Balance integrity score: 100%")
    else:
        print(f"  ❌ Found {unbalanced_jes} unbalanced journal entries!")

    # B. ACCOUNT LINKING INTEGRITY AUDIT (Strict Isolation Check)
    print("\n--- B. ACCOUNT LINKING INTEGRITY AUDIT (Strict Isolation Check) ---")
    txs_in_target_year = Transaction.objects.filter(journal_entry__academic_year=target_ay)
    print(f"Total Transactions to audit in target year: {txs_in_target_year.count()}")
    
    polluted_accounts = 0
    for tx in txs_in_target_year:
        acc = tx.account
        if acc.academic_year_id is not None and acc.academic_year_id != target_ay.id:
            print(f"  ❌ Isolation Breach! Transaction {tx.id} under JE {tx.journal_entry.reference} points to Account {acc.code} belonging to Year ID: {acc.academic_year_id}!")
            polluted_accounts += 1
            has_errors = True
            
    if polluted_accounts == 0:
        print("  ✅ Complete isolation verified! Zero (0) transactions inside target year leak/point to old year's accounts.")
    else:
        print(f"  ❌ Found {polluted_accounts} isolation breaches!")

    # C. CLONED COURSE & ENROLLMENT SCOPING AUDIT
    print("\n--- C. CLONED COURSE & ENROLLMENT SCOPING AUDIT ---")
    enrollments = Studentenrollment.objects.filter(academic_year=target_ay)
    print(f"Total Enrollments in target year: {enrollments.count()}")
    
    scoping_errors = 0
    for enr in enrollments:
        if enr.course.academic_year_id != target_ay.id:
            print(f"  ❌ Scoping Error: Enrollment {enr.id} for student {enr.student.full_name} points to Course {enr.course.name} of Year ID: {enr.course.academic_year_id}!")
            scoping_errors += 1
            has_errors = True
            
    if scoping_errors == 0:
        print("  ✅ All student enrollments are correctly bound to courses inside the target academic year.")
    else:
        print(f"  ❌ Found {scoping_errors} course scoping errors!")

    # D. RECEIPT SCOPING & ISOLATION AUDIT
    print("\n--- D. RECEIPT SCOPING & ISOLATION AUDIT ---")
    receipts = StudentReceipt.objects.filter(academic_year=target_ay)
    print(f"Total Receipts in target year: {receipts.count()}")
    
    receipt_errors = 0
    for rc in receipts:
        if rc.enrollment.academic_year_id != target_ay.id:
            print(f"  ❌ Receipt Error: Receipt {rc.reference} points to Enrollment {rc.enrollment.id} belonging to Year ID: {rc.enrollment.academic_year_id}!")
            receipt_errors += 1
            has_errors = True
            
    if receipt_errors == 0:
        print("  ✅ All student receipts point exclusively to enrollments within the target academic year.")
    else:
        print(f"  ❌ Found {receipt_errors} receipt scoping errors!")

    # E. GENERAL RECONCILIATION SUMMARY
    print("\n==================================================================")
    if not has_errors:
        print("🏆 AUDIT RESULT: 100% PERFECT STATUS. NO ERRORS DETECTED! 🏆")
    else:
        print("⚠️ AUDIT RESULT: DISCREPANCIES DETECTED. PLEASE RESOLVE ISSUES. ⚠️")
    print("==================================================================")

if __name__ == "__main__":
    run_comprehensive_audit()
