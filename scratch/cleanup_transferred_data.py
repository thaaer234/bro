import os
import sys
import django
from decimal import Decimal

# Setup Django environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alyaman.settings')
django.setup()

from django.db import transaction
from accounts.models import Account, Course, Studentenrollment, StudentReceipt, JournalEntry, Transaction
from academic_years.models import AcademicYearTransferCourseItem

def cleanup_transferred_data():
    print("=== START Retroactive Cleanup ===")
    
    # 1. جلب كافة عناصر الدورات التي تم ترحيلها بنجاح في دفعات ترحيل مكتملة
    transfer_items = AcademicYearTransferCourseItem.objects.filter(
        batch__status='completed',
        status='completed'
    ).select_related('source_course', 'target_course', 'batch')
    
    print(f"Found {transfer_items.count()} transferred courses.")
    
    touched_accounts = set()
    deleted_enrollments_count = 0
    deleted_receipts_count = 0
    deleted_je_count = 0
    
    with transaction.atomic():
        for item in transfer_items:
            source_course = item.source_course
            target_course = item.target_course
            
            print(f"\nProcessing Course: {source_course.name} (Source: {source_course.academic_year}) -> {target_course.name} (Target: {target_course.academic_year})")
            
            # جلب كافة التسجيلات في الدورة المصدر
            source_enrollments = Studentenrollment.objects.filter(course=source_course)
            
            for source_enrollment in source_enrollments:
                student = source_enrollment.student
                
                # التحقق مما إذا كان الطالب يملك تسجيلاً في الدورة الهدف (الفصل الجديد)
                # للـتأكد من أنه تم نقله بنجاح
                target_enrollment_exists = Studentenrollment.objects.filter(
                    student__full_name=student.full_name,
                    student__phone=student.phone,
                    course=target_course
                ).exists()
                
                if target_enrollment_exists:
                    print(f"  + Transferred student: {student.full_name}")
                    
                    # أ. جلب إيصالات الدفع المرتبطة بالتسجيل المصدري وتجميع معرفات قيود الدفع
                    receipts = list(StudentReceipt.objects.filter(enrollment=source_enrollment))
                    receipt_je_ids = [r.journal_entry_id for r in receipts if r.journal_entry_id]
                    
                    # ب. حذف إيصالات الدفع المصدرية أولاً (لتجنب قيود ForeignKey)
                    for receipt in receipts:
                        try:
                            receipt_id = receipt.id
                            receipt.delete()
                            deleted_receipts_count += 1
                            print(f"    - Deleted receipt: {receipt_id}")
                        except Exception as e:
                            print(f"    - Error deleting receipt {receipt.id}: {e}")
                            
                    # ج. حذف قيود اليومية المرتبطة بالإيصالات المذكورة
                    for je_id in receipt_je_ids:
                        try:
                            je = JournalEntry.objects.get(pk=je_id)
                            for tx in je.transactions.all():
                                touched_accounts.add(tx.account)
                            je.transactions.all().delete()
                            je.delete()
                            deleted_je_count += 1
                            print(f"    - Deleted receipt journal entry: {je_id}")
                        except JournalEntry.DoesNotExist:
                            pass
                        except Exception as e:
                            print(f"    - Error deleting receipt journal entry {je_id}: {e}")
                            
                    # د. تجميع معرف قيد التسجيل المصدري
                    enrollment_je_id = source_enrollment.enrollment_journal_entry_id
                    
                    # هـ. حذف سجل التسجيل المصدري نفسه
                    try:
                        source_enrollment_id = source_enrollment.id
                        source_enrollment.delete()
                        deleted_enrollments_count += 1
                        print(f"    - Deleted enrollment for student: {student.full_name}")
                    except Exception as e:
                        print(f"    - Error deleting enrollment: {e}")
                        
                    # و. حذف قيد التسجيل المصدري
                    if enrollment_je_id:
                        try:
                            je = JournalEntry.objects.get(pk=enrollment_je_id)
                            for tx in je.transactions.all():
                                touched_accounts.add(tx.account)
                            je.transactions.all().delete()
                            je.delete()
                            deleted_je_count += 1
                            print(f"    - Deleted enrollment journal entry: {enrollment_je_id}")
                        except JournalEntry.DoesNotExist:
                            pass
                        except Exception as e:
                            print(f"    - Error deleting enrollment journal entry {enrollment_je_id}: {e}")
                else:
                    print(f"  - Student {student.full_name} is in source course but not target course (not transferred).")
                    
        # 4. إعادة حساب الأرصدة للحسابات المتأثرة
        print(f"\nRecalculating balances for {len(touched_accounts)} accounts...")
        for account in touched_accounts:
            try:
                account.recalculate_tree_balances()
                print(f"  - Recalculated account: {account.code} ({account.name})")
            except Exception as e:
                print(f"  - Error updating account {account.code}: {e}")
                
    print(f"\n=== CLEANUP COMPLETED ===")
    print(f"Total deleted enrollments: {deleted_enrollments_count}")
    print(f"Total deleted receipts: {deleted_receipts_count}")
    print(f"Total deleted journal entries: {deleted_je_count}")

if __name__ == '__main__':
    cleanup_transferred_data()
