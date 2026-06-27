# -*- coding: utf-8 -*-
import os
import sys

# Setup path and environment
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alyaman.settings')
os.environ["DISABLE_BIOMETRIC_SCHEDULER"] = "true"

import django
django.setup()

from academic_years.models import AcademicYearTransferBatch
from accounts.models import Studentenrollment, StudentReceipt, JournalEntry, Transaction, Account
from students.models import Student as StudentProfile
from django.conf import settings

def main():
    print("🔄 البدء في إلغاء وتصفير دفعة الترحيل رقم 1 لتنظيف الفصل الجديد...")
    print(f"📍 مسار قاعدة البيانات المستخدم حالياً: {settings.DATABASES['default']['NAME']}")
    try:
        all_ids = list(AcademicYearTransferBatch.objects.values_list('id', flat=True))
        print(f"📋 معرفات دفعات الترحيل المتاحة في قاعدة البيانات هذه: {all_ids}")
        
        batch = AcademicYearTransferBatch.objects.get(id=1)
        target_ay = batch.target_academic_year
        print(f"الفصل المستهدف بالتنظيف: {target_ay}")
        
        # Get target courses
        target_course_ids = list(batch.course_items.values_list('target_course_id', flat=True))
        print(f"معرفات الدورات المستهدفة: {target_course_ids}")
        
        # Find enrollments in target academic year for these courses
        enrollments = list(Studentenrollment.objects.filter(
            course_id__in=target_course_ids,
            academic_year=target_ay
        ))
        print(f"عدد التسجيلات التي تم العثور عليها لحذفها: {len(enrollments)}")
        
        je_ids_to_delete = set()
        receipt_ids_to_delete = set()
        student_ids_to_delete = set()
        account_ids_to_delete = set()
        
        for en in enrollments:
            student_ids_to_delete.add(en.student_id)
            if en.enrollment_journal_entry_id:
                je_ids_to_delete.add(en.enrollment_journal_entry_id)
            if en.completion_journal_entry_id:
                je_ids_to_delete.add(en.completion_journal_entry_id)
                
            # Receipts
            receipts = StudentReceipt.objects.filter(enrollment=en)
            for re in receipts:
                receipt_ids_to_delete.add(re.id)
                if re.journal_entry_id:
                    je_ids_to_delete.add(re.journal_entry_id)
                    
        print(f"تجميع الكيانات المرتبطة بالحذف:")
        print(f" - الإيصالات: {len(receipt_ids_to_delete)}")
        print(f" - قيود اليومية: {len(je_ids_to_delete)}")
        print(f" - ملفات الطلاب التعريفية: {len(student_ids_to_delete)}")
        
        # Collect student accounts (both general 1251-000-xxxx and course-specific 1251-course-student)
        # for the students being deleted
        students = StudentProfile.objects.filter(id__in=list(student_ids_to_delete))
        student_names = list(students.values_list('full_name', flat=True))
        
        # Accounts to delete: student accounts in the target year matching these student names
        accounts = Account.objects.filter(
            is_student_account=True,
            academic_year=target_ay,
            student_name__in=student_names
        )
        for acc in accounts:
            account_ids_to_delete.add(acc.id)
            
        print(f" - حسابات ذمم الطلاب المراد حذفها: {len(account_ids_to_delete)}")
        
        # Start deletion inside transaction
        from django.db import transaction
        with transaction.atomic():
            # 1. Clear FKs on enrollments and receipts to avoid protect/restrict errors
            print("1. قطع ارتباط قيود اليومية...")
            Studentenrollment.objects.filter(id__in=[en.id for en in enrollments]).update(
                enrollment_journal_entry=None,
                completion_journal_entry=None
            )
            StudentReceipt.objects.filter(id__in=list(receipt_ids_to_delete)).update(journal_entry=None)
            
            # 2. Delete transactions
            print("2. حذف الحركات المحاسبية...")
            Transaction.objects.filter(journal_entry_id__in=list(je_ids_to_delete)).delete()
            
            # 3. Delete journal entries
            print("3. حذف قيود اليومية...")
            JournalEntry.objects.filter(id__in=list(je_ids_to_delete)).delete()
            
            # 4. Delete receipts
            print("4. حذف إيصالات القبض...")
            StudentReceipt.objects.filter(id__in=list(receipt_ids_to_delete)).delete()
            
            # 5. Delete enrollments
            print("5. حذف تسجيلات الطلاب...")
            Studentenrollment.objects.filter(id__in=[en.id for en in enrollments]).delete()
            
            # 6. Delete student accounts
            print("6. حذف حسابات ذمم الطلاب التلقائية...")
            Account.objects.filter(id__in=list(account_ids_to_delete)).delete()
            
            # 7. Delete student profiles
            print("7. حذف ملفات الطلاب المنسوخة...")
            students.delete()

            # 8. Delete all unused general student accounts (1251-000-xxxx) across the DB
            print("8. حذف كافة حسابات ذمم الطلاب العامة المكررة (1251-000-)...")
            general_accounts = Account.objects.filter(code__startswith='1251-000-', is_student_account=True)
            deleted_gen_count = 0
            for gen_acc in general_accounts:
                if Transaction.objects.filter(account=gen_acc).count() == 0:
                    gen_acc.delete()
                    deleted_gen_count += 1
            print(f"تم حذف {deleted_gen_count} حساب ذمة عامة غير مستخدم.")
            
            # 9. Reset batch
            print("9. إعادة حالة دفعة الترحيل إلى مسودة...")
            batch.status = 'draft'
            batch.failure_reason = ''
            batch.save()
            
            print("\n🎉 تم التنظيف بنجاح تام! تم تنظيف الفصل الجديد وإعادة دفعة الترحيل لحالة مسودة للبدء من جديد.")
            
    except Exception as e:
        import traceback
        print(f"Error during cleanup: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    main()
