from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from accounts.models import Studentenrollment, Account, JournalEntry, Transaction

class Command(BaseCommand):
    help = 'تحويل جميع القيود للإيرادات المؤجلة'

    def handle(self, *args, **options):
        user = User.objects.first()
        enrollments = Studentenrollment.objects.all()
        
        self.stdout.write(f"🔧 معالجة {enrollments.count()} تسجيل...")
        
        for enrollment in enrollments:
            try:
                # إذا فيه قيد قديم، حوله
                if enrollment.enrollment_journal_entry:
                    self.migrate_old_entry(enrollment, user)
                else:
                    # إذا مافيه قيد، أنشئ واحد جديد
                    self.create_new_entry(enrollment, user)
                    
            except Exception as e:
                self.stdout.write(f"✗ خطأ في {enrollment.id}: {e}")

        self.stdout.write("✅ اكتمل التحويل!")

    def migrate_old_entry(self, enrollment, user):
        """تحويل القيد القديم للإيرادات المؤجلة"""
        entry = enrollment.enrollment_journal_entry
        
        # احذف الحركات القديمة
        entry.transactions.all().delete()
        
        # الحسابات الجديدة
        student_ar_account = enrollment.student.ar_account
        course_deferred_account = Account.get_or_create_course_deferred_account(enrollment.course)
        
        # أنشئ الحركات الجديدة
        # مدين: ذمم الطالب
        Transaction.objects.create(
            journal_entry=entry,
            account=student_ar_account,
            amount=enrollment.net_amount,
            is_debit=True,
            description=f"تسجيل - {enrollment.student.full_name}"
        )
        
        # دائن: الإيرادات المؤجلة
        Transaction.objects.create(
            journal_entry=entry,
            account=course_deferred_account,
            amount=enrollment.net_amount,
            is_debit=False,
            description=f"إيرادات مؤجلة - {enrollment.course.name}"
        )
        
        # عدل وصف القيد
        entry.description = f"تسجيل طالب - {enrollment.student.full_name} في {enrollment.course.name}"
        entry.save()
        
        self.stdout.write(f"✅ تم تحويل قيد {enrollment.id}")

    def create_new_entry(self, enrollment, user):
        """إنشاء قيد جديد بالإيرادات المؤجلة"""
        # الحسابات الجديدة
        student_ar_account = enrollment.student.ar_account
        course_deferred_account = Account.get_or_create_course_deferred_account(enrollment.course)
        
        # أنشئ القيد
        entry = JournalEntry.objects.create(
            date=enrollment.enrollment_date,
            description=f"تسجيل طالب - {enrollment.student.full_name} في {enrollment.course.name}",
            entry_type='enrollment',
            total_amount=enrollment.net_amount,
            created_by=user
        )
        
        # مدين: ذمم الطالب
        Transaction.objects.create(
            journal_entry=entry,
            account=student_ar_account,
            amount=enrollment.net_amount,
            is_debit=True,
            description=f"تسجيل - {enrollment.student.full_name}"
        )
        
        # دائن: الإيرادات المؤجلة
        Transaction.objects.create(
            journal_entry=entry,
            account=course_deferred_account,
            amount=enrollment.net_amount,
            is_debit=False,
            description=f"إيرادات مؤجلة - {enrollment.course.name}"
        )
        
        # ربط القيد بالتسجيل
        enrollment.enrollment_journal_entry = entry
        enrollment.save()
        
        self.stdout.write(f"✅ تم إنشاء قيد جديد لـ {enrollment.id}")