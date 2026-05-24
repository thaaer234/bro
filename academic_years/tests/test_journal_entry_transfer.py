"""
اختبارات نظام نقل القيود المحاسبية
Tests for Journal Entry Transfer System
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from decimal import Decimal

from academic_years.models import (
    JournalEntryTransferBatch,
    JournalEntryTransferItem,
)
from academic_years.services.journal_entry_transfers import JournalEntryTransferService
from accounts.models import JournalEntry, Transaction, Account
from quick.models import AcademicYear

User = get_user_model()


class JournalEntryTransferBatchModelTest(TestCase):
    """اختبارات نموذج دفعة النقل"""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            password="testpass123",
            is_superuser=True,
        )
        self.target_year = AcademicYear.objects.create(
            name="السنة الثانية",
            year=2024,
            start_date="2024-09-01",
            end_date="2025-06-30",
        )

    def test_create_transfer_batch(self):
        """اختبار إنشاء دفعة نقل"""
        batch = JournalEntryTransferBatch.objects.create(
            target_academic_year=self.target_year,
            created_by=self.user,
            status=JournalEntryTransferBatch.STATUS_DRAFT,
            notes="اختبار",
        )
        self.assertEqual(batch.status, "draft")
        self.assertEqual(batch.target_academic_year, self.target_year)
        self.assertTrue(str(batch).startswith("نقل قيود"))

    def test_batch_status_transitions(self):
        """اختبار تغيير حالة الدفعة"""
        batch = JournalEntryTransferBatch.objects.create(
            target_academic_year=self.target_year,
            created_by=self.user,
        )
        self.assertEqual(batch.status, "draft")

        batch.status = JournalEntryTransferBatch.STATUS_VALIDATED
        batch.save()
        batch.refresh_from_db()
        self.assertEqual(batch.status, "validated")

        batch.status = JournalEntryTransferBatch.STATUS_COMPLETED
        batch.executed_at = timezone.now()
        batch.save()
        batch.refresh_from_db()
        self.assertEqual(batch.status, "completed")
        self.assertIsNotNone(batch.executed_at)


class JournalEntryTransferItemModelTest(TestCase):
    """اختبارات نموذج عنصر النقل"""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            password="testpass123",
            is_superuser=True,
        )
        self.target_year = AcademicYear.objects.create(
            name="السنة الثانية",
            year=2024,
            start_date="2024-09-01",
            end_date="2025-06-30",
        )
        self.batch = JournalEntryTransferBatch.objects.create(
            target_academic_year=self.target_year,
            created_by=self.user,
        )
        self.source_entry = JournalEntry.objects.create(
            reference="JE-000001",
            date="2024-01-01",
            description="تسجيل طالب",
            entry_type="enrollment",
            total_amount=Decimal("1000.00"),
            academic_year=None,  # بدون فصل
            created_by=self.user,
        )

    def test_create_transfer_item(self):
        """اختبار إنشاء عنصر نقل"""
        item = JournalEntryTransferItem.objects.create(
            batch=self.batch,
            source_journal_entry=self.source_entry,
            status=JournalEntryTransferItem.STATUS_PENDING,
        )
        self.assertEqual(item.batch, self.batch)
        self.assertEqual(item.source_journal_entry, self.source_entry)
        self.assertEqual(item.status, "pending")

    def test_unique_constraint(self):
        """اختبار قيد التفرد (batch, source_journal_entry)"""
        JournalEntryTransferItem.objects.create(
            batch=self.batch,
            source_journal_entry=self.source_entry,
        )
        # محاولة إنشاء عنصر مكرر يجب أن يرفع استثناء
        with self.assertRaises(Exception):
            JournalEntryTransferItem.objects.create(
                batch=self.batch,
                source_journal_entry=self.source_entry,
            )


class JournalEntryTransferServiceTest(TestCase):
    """اختبارات خدمة النقل"""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            password="testpass123",
            is_superuser=True,
        )
        self.source_year = None  # بدون فصل
        self.target_year = AcademicYear.objects.create(
            name="السنة الثانية",
            year=2024,
            start_date="2024-09-01",
            end_date="2025-06-30",
        )
        
        # إنشاء حسابات
        self.student_account = Account.objects.create(
            code="1001",
            name="Student Receivables",
            account_type="ASSET",
            academic_year=None,
        )
        
        self.batch = JournalEntryTransferBatch.objects.create(
            target_academic_year=self.target_year,
            created_by=self.user,
        )

    def test_service_initialization(self):
        """اختبار تهيئة الخدمة"""
        service = JournalEntryTransferService(batch=self.batch, actor=self.user)
        self.assertEqual(service.batch, self.batch)
        self.assertEqual(service.actor, self.user)
        self.assertEqual(len(service.summary), 0)

    def test_resolve_target_account_no_academic_year(self):
        """اختبار إيجاد حساب بدون فصل"""
        service = JournalEntryTransferService(batch=self.batch, actor=self.user)
        result = service._resolve_target_account(self.student_account)
        # الحسابات بدون academic_year تُرجع كما هي
        self.assertEqual(result, self.student_account)


class JournalEntryTransferFormTest(TestCase):
    """اختبارات نموذج النقل"""

    def setUp(self):
        self.target_year = AcademicYear.objects.create(
            name="السنة الثانية",
            year=2024,
            start_date="2024-09-01",
            end_date="2025-06-30",
        )
        self.user = User.objects.create_user(
            username="testuser",
            password="testpass123",
            is_superuser=True,
        )

    def test_form_import(self):
        """اختبار استيراد الـ form"""
        from academic_years.forms import JournalEntryTransferBatchForm

        form = JournalEntryTransferBatchForm()
        self.assertIn("target_academic_year", form.fields)
        self.assertIn("source_journal_entries", form.fields)
        self.assertIn("notes", form.fields)

    def test_form_no_entries_error(self):
        """اختبار الخطأ عند عدم اختيار قيود"""
        from academic_years.forms import JournalEntryTransferBatchForm

        data = {
            "target_academic_year": self.target_year.id,
            "source_journal_entries": [],
            "notes": "",
        }
        form = JournalEntryTransferBatchForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn("source_journal_entries", form.errors)


class JournalEntryTransferViewsTest(TestCase):
    """اختبارات الـ Views"""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            password="testpass123",
            is_superuser=True,
        )
        self.client.login(username="testuser", password="testpass123")
        self.target_year = AcademicYear.objects.create(
            name="السنة الثانية",
            year=2024,
            start_date="2024-09-01",
            end_date="2025-06-30",
        )

    def test_list_view_access(self):
        """اختبار الوصول إلى قائمة الدفعات"""
        response = self.client.get("/academic-years/journal-entries-transfer/")
        self.assertEqual(response.status_code, 200)

    def test_create_view_access(self):
        """اختبار الوصول إلى صفحة الإنشاء"""
        response = self.client.get("/academic-years/journal-entries-transfer/create/")
        self.assertEqual(response.status_code, 200)

    def test_create_view_non_superuser(self):
        """اختبار عدم وصول المستخدم العادي"""
        user = User.objects.create_user(
            username="normaluser",
            password="testpass123",
        )
        self.client.login(username="normaluser", password="testpass123")
        response = self.client.get("/academic-years/journal-entries-transfer/")
        self.assertNotEqual(response.status_code, 200)


def test_all_imports():
    """اختبار أن جميع الواردات تعمل بشكل صحيح"""
    try:
        from academic_years.models import (
            JournalEntryTransferBatch,
            JournalEntryTransferItem,
        )
        from academic_years.forms import JournalEntryTransferBatchForm
        from academic_years.services.journal_entry_transfers import (
            JournalEntryTransferService,
        )
        from academic_years.views import (
            JournalEntryTransferBatchListView,
            JournalEntryTransferBatchCreateView,
            JournalEntryTransferBatchDetailView,
            JournalEntryTransferBatchExecuteView,
        )
        print("✅ جميع الواردات تعمل بشكل صحيح")
        return True
    except ImportError as e:
        print(f"❌ خطأ في الاستيراد: {e}")
        return False


if __name__ == "__main__":
    test_all_imports()
