from collections import defaultdict

from django.db import transaction
from django.utils import timezone

from accounts.models import Account, Course, JournalEntry, StudentReceipt, Studentenrollment, Transaction
from students.models import Student as StudentProfile

from academic_years.models import (
    AcademicYearTransferBatch,
    AcademicYearTransferCourseItem,
    AcademicYearTransferLog,
)


class AcademicYearTransferService:
    def __init__(self, *, batch, actor):
        self.batch = batch
        self.actor = actor
        self.student_map = {}
        self.course_map = {}
        self.entry_map = {}
        self.created_student_ids = set()
        self.summary = defaultdict(int)

    def log(self, message, *, level=AcademicYearTransferLog.LEVEL_INFO, payload=None):
        AcademicYearTransferLog.objects.create(
            batch=self.batch,
            level=level,
            message=message,
            payload=payload or {},
        )

    def build_preview(self):
        summary = {
            "courses": self.batch.course_items.count(),
            "students": 0,
            "enrollments": 0,
            "receipts": 0,
            "journal_entries": 0,
        }
        seen_student_ids = set()
        for item in self.batch.course_items.select_related("source_course"):
            source_course = item.source_course
            enrollments = Studentenrollment.objects.filter(course=source_course).select_related("student", "course")
            receipts = StudentReceipt.objects.filter(enrollment__course=source_course).distinct()
            entry_ids = set(enrollments.exclude(enrollment_journal_entry__isnull=True).values_list("enrollment_journal_entry_id", flat=True))
            entry_ids.update(enrollments.exclude(completion_journal_entry__isnull=True).values_list("completion_journal_entry_id", flat=True))
            entry_ids.update(receipts.exclude(journal_entry__isnull=True).values_list("journal_entry_id", flat=True))

            item.student_count = enrollments.values("student_id").distinct().count()
            item.enrollment_count = enrollments.count()
            item.receipt_count = receipts.count()
            item.journal_entry_count = len([entry_id for entry_id in entry_ids if entry_id])
            item.status = AcademicYearTransferCourseItem.STATUS_PREVIEWED
            item.save(
                update_fields=[
                    "student_count",
                    "enrollment_count",
                    "receipt_count",
                    "journal_entry_count",
                    "status",
                ]
            )

            seen_student_ids.update(enrollments.values_list("student_id", flat=True))
            summary["enrollments"] += item.enrollment_count
            summary["receipts"] += item.receipt_count
            summary["journal_entries"] += item.journal_entry_count

        summary["students"] = len(seen_student_ids)
        self.batch.summary_json = summary
        self.batch.status = AcademicYearTransferBatch.STATUS_VALIDATED
        self.batch.save(update_fields=["summary_json", "status", "updated_at"])
        return summary

    def execute(self):
        with transaction.atomic():
            self.log("بدء تنفيذ الترحيل.", payload={"batch_id": self.batch.pk})
            preview = self.build_preview()
            self.log("نتيجة المعاينة قبل التنفيذ.", payload=preview)
            for item in self.batch.course_items.select_related("source_course").order_by("id"):
                self._transfer_course_item(item)
            self.batch.status = AcademicYearTransferBatch.STATUS_COMPLETED
            self.batch.executed_at = timezone.now()
            self.batch.failure_reason = ""
            self.batch.summary_json = dict(self.summary)
            self.batch.save(update_fields=["status", "executed_at", "failure_reason", "summary_json", "updated_at"])
            self.log("اكتمل تنفيذ الترحيل بنجاح.", payload=self.batch.summary_json)
            return self.batch.summary_json

    def _transfer_course_item(self, item):
        source_course = item.source_course
        target_course = self._get_or_create_target_course(source_course)
        item.target_course = target_course
        item.status = AcademicYearTransferCourseItem.STATUS_COMPLETED
        item.save(update_fields=["target_course", "status"])

        self.summary["courses"] += 1
        enrollments = list(
            Studentenrollment.objects.filter(course=source_course)
            .select_related("student", "course", "enrollment_journal_entry", "completion_journal_entry")
            .order_by("id")
        )
        for enrollment in enrollments:
            target_student = self._get_or_create_target_student(enrollment.student)
            target_enrollment = self._get_or_create_target_enrollment(enrollment, target_student, target_course)

            # Find the student's AR account in the source academic year
            source_student_ar_account = Account.get_student_ar_account_for_course(enrollment.student, enrollment.course)

            # Gather all journal entries that belong to this student for this course (including discounts, settlements, etc.)
            journal_entries_to_transfer = set()

            # 1. Gather via transactions on the student's AR account (Discounts, Settlements, etc.)
            if source_student_ar_account:
                tx_entries = JournalEntry.objects.filter(
                    transactions__account=source_student_ar_account
                ).distinct()
                journal_entries_to_transfer.update(tx_entries)

            # 2. Gather via enrollment fields
            if enrollment.enrollment_journal_entry:
                journal_entries_to_transfer.add(enrollment.enrollment_journal_entry)
            if enrollment.completion_journal_entry:
                journal_entries_to_transfer.add(enrollment.completion_journal_entry)

            # 3. Gather via student receipts
            receipts = list(StudentReceipt.objects.filter(enrollment=enrollment).select_related("journal_entry"))
            for receipt in receipts:
                if receipt.journal_entry:
                    journal_entries_to_transfer.add(receipt.journal_entry)

            # Clone all of these gathered journal entries to the target year
            entry_map_local = {}
            for source_entry in journal_entries_to_transfer:
                target_entry = self._clone_journal_entry(
                    source_entry,
                    target_student=target_student,
                    target_course=target_course,
                    is_receipt=any(r.journal_entry_id == source_entry.id for r in receipts),
                    source_student=enrollment.student,
                    source_course=enrollment.course,
                )
                entry_map_local[source_entry.id] = target_entry

            # Link cloned journal entries to target enrollment
            if enrollment.enrollment_journal_entry_id in entry_map_local:
                target_enrollment.enrollment_journal_entry = entry_map_local[enrollment.enrollment_journal_entry_id]
            if enrollment.completion_journal_entry_id in entry_map_local:
                target_enrollment.completion_journal_entry = entry_map_local[enrollment.completion_journal_entry_id]
            target_enrollment.save(update_fields=["enrollment_journal_entry", "completion_journal_entry"])

            # Link cloned journal entries to target receipts and save them
            self._clone_receipts_for_enrollment_with_map(enrollment, target_enrollment, target_student, target_course, receipts, entry_map_local)

            # Deletion: Delete source student, source course enrollment, and all their related journal entries from the source year
            self._delete_source_entities_and_entries(enrollment, receipts, journal_entries_to_transfer, source_student_ar_account)

        self.log(
            "اكتمل ترحيل دورة.",
            payload={
                "source_course_id": source_course.pk,
                "target_course_id": target_course.pk,
                "source_course": str(source_course),
                "target_course": str(target_course),
            },
        )

    def _delete_source_entities_and_entries(self, enrollment, receipts, journal_entries_to_transfer, source_student_ar_account):
        touched_accounts = set()
        source_student = enrollment.student

        # Collect touched accounts from all transferred journal entries
        for je in journal_entries_to_transfer:
            for tx in je.transactions.all():
                touched_accounts.add(tx.account)

        try:
            # 1. Delete all transferred journal entries (this also deletes their transactions)
            for je in journal_entries_to_transfer:
                je.transactions.all().delete()
                je._skip_linked_cleanup = True
                je.delete()

            # 2. Delete source StudentReceipts
            for receipt in receipts:
                receipt._skip_linked_cleanup = True
                receipt.delete()

            # 3. Delete source enrollment itself
            enrollment._skip_linked_cleanup = True
            enrollment.delete()

            # 4. Delete the student's specific AR account from the source year if it exists and has no remaining transactions
            if source_student_ar_account:
                if not Transaction.objects.filter(account=source_student_ar_account).exists():
                    source_student_ar_account.delete()

            # 5. Delete the source student profile from the source year if they have no other enrollments left
            if source_student:
                from accounts.models import Studentenrollment
                if not Studentenrollment.objects.filter(student=source_student).exists():
                    source_student._skip_linked_cleanup = True
                    source_student.delete()

            # 6. Recalculate tree balances for all touched accounts that still exist
            for account in touched_accounts:
                if Account.objects.filter(pk=account.pk).exists():
                    try:
                        account.recalculate_tree_balances()
                    except Exception:
                        pass

        except Exception as e:
            import sys
            sys.stderr.write(f"\n❌ [AcademicYearTransferService Error] Failed to delete source entities for enrollment {enrollment.id}: {str(e)}\n")
            raise e

    def _get_or_create_target_course(self, source_course):
        if source_course.pk in self.course_map:
            return self.course_map[source_course.pk]

        target_course, _ = Course.objects.get_or_create(
            academic_year=self.batch.target_academic_year,
            name=source_course.name,
            name_ar=source_course.name_ar,
            defaults={
                "description": source_course.description,
                "price": source_course.price,
                "duration_hours": source_course.duration_hours,
                "is_active": source_course.is_active,
                "cost_center": source_course.cost_center,
            },
        )
        self.course_map[source_course.pk] = target_course
        return target_course

    def _get_or_create_target_student(self, source_student):
        if source_student.pk in self.student_map:
            return self.student_map[source_student.pk]

        lookup = {
            "full_name": source_student.full_name,
            "phone": source_student.phone,
            "academic_year": self.batch.target_academic_year,
        }
        defaults = {
            "email": source_student.email,
            "gender": source_student.gender,
            "branch": source_student.branch,
            "birth_date": source_student.birth_date,
            "student_number": source_student.student_number,
            "nationality": source_student.nationality,
            "registration_date": source_student.registration_date,
            "tase3": source_student.tase3,
            "disease": source_student.disease,
            "is_active": source_student.is_active,
            "father_name": source_student.father_name,
            "father_job": source_student.father_job,
            "father_phone": source_student.father_phone,
            "mother_name": source_student.mother_name,
            "mother_job": source_student.mother_job,
            "mother_phone": source_student.mother_phone,
            "address": source_student.address,
            "home_phone": source_student.home_phone,
            "previous_school": source_student.previous_school,
            "elementary_school": source_student.elementary_school,
            "how_knew_us": source_student.how_knew_us,
            "notes": source_student.notes,
            "added_by": self.actor,
            "discount_percent": source_student.discount_percent,
            "discount_amount": source_student.discount_amount,
            "discount_reason": source_student.discount_reason,
            "tudent_type": source_student.tudent_type,
            "academic_level": source_student.academic_level,
            "registration_status": source_student.registration_status,
            "account_id": source_student.account_id,
        }
        target_student, _ = StudentProfile.objects.get_or_create(**lookup, defaults=defaults)
        self.student_map[source_student.pk] = target_student
        return target_student

    def _get_or_create_target_enrollment(self, source_enrollment, target_student, target_course):
        target_enrollment, created = Studentenrollment.objects.get_or_create(
            student=target_student,
            course=target_course,
            defaults={
                "academic_year": self.batch.target_academic_year,
                "enrollment_date": source_enrollment.enrollment_date,
                "total_amount": source_enrollment.total_amount,
                "discount_percent": source_enrollment.discount_percent,
                "discount_amount": source_enrollment.discount_amount,
                "payment_method": source_enrollment.payment_method,
                "notes": source_enrollment.notes,
                "is_completed": source_enrollment.is_completed,
                "completion_date": source_enrollment.completion_date,
            },
        )
        if created:
            self.summary["enrollments"] += 1
        if target_student.pk not in self.created_student_ids:
            self.created_student_ids.add(target_student.pk)
            self.summary["students"] += 1
        return target_enrollment

    def _clone_receipts_for_enrollment_with_map(self, source_enrollment, target_enrollment, target_student, target_course, receipts, entry_map_local):
        for source_receipt in receipts:
            target_receipt, created = StudentReceipt.objects.get_or_create(
                enrollment=target_enrollment,
                date=source_receipt.date,
                paid_amount=source_receipt.paid_amount,
                payment_method=source_receipt.payment_method,
                notes=source_receipt.notes,
                defaults={
                    "student_name": source_receipt.student_name or target_student.full_name,
                    "course_name": source_receipt.course_name or target_course.name,
                    "student_profile": target_student,
                    "course": target_course,
                    "student": source_receipt.student,
                    "amount": source_receipt.amount,
                    "discount_percent": source_receipt.discount_percent,
                    "discount_amount": source_receipt.discount_amount,
                    "is_printed": source_receipt.is_printed,
                    "academic_year": self.batch.target_academic_year,
                    "created_by": self.actor,
                },
            )
            if created:
                self.summary["receipts"] += 1
            if source_receipt.journal_entry_id:
                target_entry = entry_map_local.get(source_receipt.journal_entry_id)
                if target_entry:
                    target_receipt.journal_entry = target_entry
                    target_receipt.save(update_fields=["journal_entry"])

    def _clone_enrollment_entries(self, source_enrollment, target_enrollment, target_student, target_course):
        if source_enrollment.enrollment_journal_entry_id and not target_enrollment.enrollment_journal_entry_id:
            target_entry = self._clone_journal_entry(
                source_enrollment.enrollment_journal_entry,
                target_student=target_student,
                target_course=target_course,
                source_student=source_enrollment.student,
                source_course=source_enrollment.course,
            )
            target_enrollment.enrollment_journal_entry = target_entry
        if source_enrollment.completion_journal_entry_id and not target_enrollment.completion_journal_entry_id:
            target_entry = self._clone_journal_entry(
                source_enrollment.completion_journal_entry,
                target_student=target_student,
                target_course=target_course,
                source_student=source_enrollment.student,
                source_course=source_enrollment.course,
            )
            target_enrollment.completion_journal_entry = target_entry
        target_enrollment.save(update_fields=["enrollment_journal_entry", "completion_journal_entry"])

    def _clone_journal_entry(self, source_entry, *, target_student, target_course, is_receipt=False, source_student=None, source_course=None):
        if source_entry.pk in self.entry_map:
            return self.entry_map[source_entry.pk]

        target_entry = JournalEntry.objects.create(
            date=source_entry.date,
            description=source_entry.description,
            entry_type=source_entry.entry_type,
            total_amount=source_entry.total_amount,
            academic_year=self.batch.target_academic_year,
            created_by=source_entry.created_by or self.actor,
        )

        for source_tx in source_entry.transactions.select_related("account", "cost_center").all():
            target_account = self._resolve_target_account(
                source_tx.account,
                target_student=target_student,
                target_course=target_course,
                is_receipt=is_receipt,
                source_student=source_student,
                source_course=source_course,
            )
            Transaction.objects.create(
                journal_entry=target_entry,
                account=target_account,
                amount=source_tx.amount,
                is_debit=source_tx.is_debit,
                description=source_tx.description,
                cost_center=target_course.cost_center if source_tx.cost_center_id == target_course.cost_center_id else source_tx.cost_center,
            )

        if source_entry.is_posted:
            target_entry.post_entry(source_entry.posted_by or source_entry.created_by or self.actor)

        self.entry_map[source_entry.pk] = target_entry
        self.summary["journal_entries"] += 1
        return target_entry

    def _resolve_target_account(self, source_account, *, target_student, target_course, is_receipt=False, source_student=None, source_course=None):
        if not source_account:
            raise ValueError("Source account is required to clone transactions.")

        # 1. If it doesn't belong to any academic year (shared/global account like Cash, Bank), return it directly
        if not source_account.academic_year:
            return source_account

        # 2. If it's a student AR account (receivable), resolve/create the target student's AR account under the new course
        if source_account.is_student_account:
            return Account.get_or_create_student_ar_account(target_student, target_course)

        # 3. If it's a course account (e.g., Course Deferred Revenue or Course Revenue)
        if source_account.is_course_account:
            if source_account.account_type == 'LIABILITY':
                # Deferred Revenue (21001-xxx)
                return Account.get_or_create_course_deferred_account(target_course)
            elif source_account.account_type == 'REVENUE':
                # Course Revenue (4101-xxx)
                return Account.get_or_create_course_account(target_course)

        # 4. Fallback: general year-scoped accounts, find/create corresponding account in the target year
        target_year = self.batch.target_academic_year
        code = source_account.code

        if source_course and target_course:
            source_course_id_str = f"{source_course.id:03d}"
            target_course_id_str = f"{target_course.id:03d}"
            if source_course_id_str in code:
                code = code.replace(source_course_id_str, target_course_id_str)

        target_parent = None
        if source_account.parent:
            target_parent = self._resolve_target_account(
                source_account.parent,
                target_student=target_student,
                target_course=target_course,
                source_student=source_student,
                source_course=source_course
            )

        target_account, created = Account.objects.get_or_create(
            code=code,
            defaults={
                'name': source_account.name,
                'name_ar': source_account.name_ar,
                'account_type': source_account.account_type,
                'parent': target_parent,
                'is_course_account': source_account.is_course_account,
                'course_name': source_account.course_name,
                'is_student_account': source_account.is_student_account,
                'student_name': source_account.student_name,
                'academic_year': target_year,
                'is_active': source_account.is_active,
            }
        )
        return target_account
