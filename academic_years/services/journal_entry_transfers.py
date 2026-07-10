"""
خدمة نقل القيود المحاسبية من دون فصول إلى فصول محددة
- تنقل قيود التسجيل والدفع فقط للطالب
- لا تنقل باقي القيود
"""
from collections import defaultdict
from django.db import transaction
from django.utils import timezone

from accounts.models import JournalEntry, Transaction, Account
from academic_years.models import (
    JournalEntryTransferBatch,
    JournalEntryTransferItem,
    AcademicYearTransferLog,
)


class JournalEntryTransferService:
    """خدمة نقل القيود المحاسبية"""
    
    def __init__(self, *, batch, actor):
        self.batch = batch
        self.actor = actor
        self.summary = defaultdict(int)
        self.account_map = {}

    def log(self, message, *, level=AcademicYearTransferLog.LEVEL_INFO, payload=None):
        """تسجيل رسالة في سجلات الترحيل"""
        AcademicYearTransferLog.objects.create(
            batch=self.batch,
            level=level,
            message=message,
            payload=payload or {},
        )

    def build_preview(self):
        """بناء معاينة للقيود المراد نقلها"""
        summary = {
            "journal_entries": 0,
            "transactions": 0,
            "total_amount": 0,
        }
        
        for item in self.batch.journal_entry_items.select_related("source_journal_entry").order_by("id"):
            source_entry = item.source_journal_entry
            
            # العد
            summary["journal_entries"] += 1
            summary["transactions"] += source_entry.transactions.count()
            summary["total_amount"] += float(source_entry.total_amount or 0)
            
            item.status = JournalEntryTransferItem.STATUS_PREVIEWED
            item.save(update_fields=["status"])

        self.batch.summary_json = summary
        self.batch.status = JournalEntryTransferBatch.STATUS_VALIDATED
        self.batch.save(update_fields=["summary_json", "status", "updated_at"])
        
        return summary

    def execute(self):
        """تنفيذ نقل القيود"""
        with transaction.atomic():
            self.log("بدء تنفيذ نقل القيود.", payload={"batch_id": self.batch.pk})
            
            preview = self.build_preview()
            self.log("نتيجة المعاينة قبل التنفيذ.", payload=preview)
            
            for item in self.batch.journal_entry_items.select_related("source_journal_entry").order_by("id"):
                try:
                    self._transfer_journal_entry(item)
                except Exception as e:
                    item.status = JournalEntryTransferItem.STATUS_FAILED
                    item.notes = str(e)
                    item.save(update_fields=["status", "notes"])
                    self.log(
                        f"فشل نقل القيد {item.source_journal_entry.reference}",
                        level=AcademicYearTransferLog.LEVEL_ERROR,
                        payload={"error": str(e), "entry_id": item.source_journal_entry.pk}
                    )

            self.batch.status = JournalEntryTransferBatch.STATUS_COMPLETED
            self.batch.executed_at = timezone.now()
            self.batch.failure_reason = ""
            self.batch.summary_json = dict(self.summary)
            self.batch.save(update_fields=[
                "status", "executed_at", "failure_reason", "summary_json", "updated_at"
            ])
            
            self.log("اكتمل تنفيذ نقل القيود بنجاح.", payload=self.batch.summary_json)
            return self.batch.summary_json

    def _transfer_journal_entry(self, item):
        """نقل قيد واحد من القيود"""
        source_entry = item.source_journal_entry
        
        # إنشاء قيد جديد بنفس البيانات لكن مع الفصل الجديد
        target_entry = JournalEntry.objects.create(
            date=source_entry.date,
            description=source_entry.description,
            entry_type=source_entry.entry_type,
            total_amount=source_entry.total_amount,
            academic_year=self.batch.target_academic_year,  # تعيين الفصل الجديد
            created_by=source_entry.created_by or self.actor,
        )

        # نسخ جميع المعاملات من القيد الأصلي
        for source_tx in source_entry.transactions.select_related("account", "cost_center").all():
            # الحصول على الحساب المقابل في الفصل الجديد
            target_account = self._resolve_target_account(source_tx.account)
            
            Transaction.objects.create(
                journal_entry=target_entry,
                account=target_account,
                amount=source_tx.amount,
                is_debit=source_tx.is_debit,
                description=source_tx.description,
                cost_center=source_tx.cost_center,
            )

        # ترحيل القيد إذا كان الأصلي مرحل
        if source_entry.is_posted:
            target_entry.post_entry(source_entry.posted_by or source_entry.created_by or self.actor)

        item.target_journal_entry = target_entry
        item.status = JournalEntryTransferItem.STATUS_COMPLETED
        item.save(update_fields=["target_journal_entry", "status"])

        self.summary["journal_entries"] += 1
        self.summary["transactions"] += source_entry.transactions.count()
        self.summary["total_amount"] += float(source_entry.total_amount or 0)

        self.log(
            f"تم نقل القيد {source_entry.reference}",
            payload={
                "source_entry_id": source_entry.pk,
                "target_entry_id": target_entry.pk,
                "source_entry_ref": source_entry.reference,
                "target_entry_ref": target_entry.reference,
            }
        )

    def _resolve_target_account(self, source_account):
        """الحصول على الحساب المقابل في الفصل الجديد"""
        if not source_account:
            raise ValueError("Source account is required to clone transactions.")

        # الحسابات بدون فصل تُستخدم كما هي
        if source_account.academic_year_id is None:
            return source_account

        # إذا كانت الحسابات مرتبطة بالفصل، ننشئ حساب جديد أو نبحث عنه
        if source_account.academic_year_id != self.batch.target_academic_year.pk:
            # البحث عن حساب مماثل في الفصل الجديد
            target_account, _ = Account.objects.get_or_create(
                academic_year=self.batch.target_academic_year,
                code=source_account.code,
                defaults={
                    "name": source_account.name,
                    "name_ar": source_account.name_ar,
                    "account_type": source_account.account_type,
                    "is_active": source_account.is_active,
                    "is_student_account": source_account.is_student_account,
                    "is_course_account": source_account.is_course_account,
                }
            )
            return target_account

        return source_account
