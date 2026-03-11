from django.db import models
from datetime import datetime
from decimal import Decimal
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.db import transaction as db_transaction
from django.dispatch import receiver
from django.utils import timezone
from datetime import date

class Student(models.Model):
    
    class Gender(models.TextChoices):
        MALE = 'male', 'ذكر'
        FEMALE = 'female', 'أنثى'
    
    class HowKnewUs(models.TextChoices):
        FRIEND = 'friend', 'صديق'
        SOCIAL = 'social', 'وسائل التواصل الاجتماعي'
        AD = 'ad', 'إعلان'
        ADS = 'ads', 'إعلانات طرقية'
        OTHER = 'other', 'أخرى'
    
    class Academic_Track(models.TextChoices):
        LITERARY = 'أدبي', 'الأدبي'
        SCIENTIFIC = 'علمي', 'العلمي'
        NINTH_exams = 'تاسع', 'الصف التاسع'
    
    # Basic Information
    full_name = models.CharField(max_length=200)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True)
    gender = models.CharField(max_length=6, choices=Gender.choices, blank=True)
    branch = models.CharField(max_length=10, choices=Academic_Track.choices, blank=True)
    birth_date = models.DateField(null=True, blank=True)
    student_number = models.CharField(max_length=20, blank=True) 
    nationality = models.CharField(max_length=50, blank=True)
    registration_date = models.DateField(default=datetime.now)
    tase3 = models.IntegerField(default=0, blank=True)
    disease = models.TextField(blank=True, default="none")
    is_active = models.BooleanField(default=True, verbose_name="نشط")
    
    # Father Information
    father_name = models.CharField(max_length=100, blank=True)
    father_job = models.CharField(max_length=100, blank=True)
    father_phone = models.CharField(max_length=20, blank=True)
    
    # Mother Information
    mother_name = models.CharField(max_length=100, blank=True)
    mother_job = models.CharField(max_length=100, blank=True)
    mother_phone = models.CharField(max_length=20, blank=True)
    
    # Address Information
    address = models.TextField(blank=True)
    home_phone = models.CharField(max_length=20, blank=True)
    
    # Previous Education
    previous_school = models.CharField(max_length=100, blank=True)
    elementary_school = models.CharField(max_length=100, blank=True)
    
    # Other Information
    how_knew_us = models.CharField(
        max_length=100, 
        choices=HowKnewUs.choices, 
        blank=True, 
        null=True
    )
    notes = models.TextField(blank=True)
    added_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        verbose_name="تم الإضافة بواسطة"
    )
    
    # Discount fields
    discount_percent = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=Decimal('0'),
        help_text="Percentage discount (0-100)",
        verbose_name='نسبة الحسم الافتراضي %'
    )
    discount_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=Decimal('0'),
        help_text="Fixed amount discount",
        verbose_name='قيمة الحسم الافتراضي'
    )
    discount_reason = models.CharField(
        max_length=200, 
        blank=True, 
        verbose_name='سبب الحسم'
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # ربط اختياري بحساب الذمم للطالب
    account = models.ForeignKey(
        'accounts.Account', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        verbose_name='حساب الطالب (ذمم)'
    )
    tudent_type = models.CharField(
        max_length=50, 
        blank=True, 
        verbose_name='نوع الطالب'
    )
    
    academic_level = models.CharField(
        max_length=50, 
        blank=True, 
        verbose_name='المستوى الأكاديمي'
    )
    
    registration_status = models.CharField(
        max_length=30, 
        blank=True, 
        verbose_name='الحالة التسجيلية'
    )

    academic_year = models.ForeignKey(
        'quick.AcademicYear',  # أو 'academic.AcademicYear' حسب التطبيق
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='الفصل الدراسي'
    )
    @property
    def student_id(self):
        """خاصية student_id كبديل للرقم التسلسلي"""
        return f"STU-{self.id:04d}"

    # الحقول الحالية...
    
    def get_auto_academic_year(self):
        """الحصول على الفصل الدراسي التلقائي - يفضل الفصول المفتوحة"""
        from quick.models import AcademicYear
        from django.db.models import Q
        
        print(f"🔍 [DEBUG] البحث عن فصل دراسي للطالب: {self.full_name}")
        print(f"📅 [DEBUG] تاريخ التسجيل: {self.registration_date}")
        
        if self.registration_date:
            try:
                # 🔥 الأفضلية للفصول المفتوحة (بدون تاريخ انتهاء)
                academic_year = AcademicYear.objects.filter(
                    Q(start_date__lte=self.registration_date) &
                    Q(end_date__isnull=True) &  # فصول مفتوحة
                    Q(is_active=True)
                ).first()
                
                # إذا لم يوجد فصول مفتوحة، ابحث عن فصول عادية
                if not academic_year:
                    academic_year = AcademicYear.objects.filter(
                        Q(start_date__lte=self.registration_date) &
                        Q(end_date__gte=self.registration_date) &
                        Q(is_active=True)
                    ).first()
                
                print(f"✅ [DEBUG] الفصل الموجود: {academic_year} (مفتوح: {academic_year and academic_year.end_date is None})")
                return academic_year
            except Exception as e:
                print(f"❌ [DEBUG] خطأ في البحث: {e}")
                return None
        
        print("❌ [DEBUG] لا يوجد تاريخ تسجيل")
        return None
    
   
    
    def save(self, *args, **kwargs):
        # تعيين الفصل الدراسي تلقائياً إذا لم يكن محدداً
        if not self.academic_year and self.registration_date:
            auto_year = self.get_auto_academic_year()
            if auto_year:
                self.academic_year = auto_year
        
        super().save(*args, **kwargs)

    def has_active_enrollments(self):
        """التحقق مما إذا كان لدى الطالب تسجيلات نشطة"""
        return Studentenrollment.objects.filter(
            student=self, 
            is_completed=False
        ).exists()
    
    def get_active_enrollments(self):
        """جلب جميع التسجيلات النشطة"""
        return Studentenrollment.objects.filter(
            student=self, 
            is_completed=False
        ).select_related('course')
   
    
# ====================
    # students/models.py - إضافة دالة مساعدة
   
    # الحقول الحالية...
    
    
    # الحقول الحالية... 
    def get_display_phone(self):
        """إرجاع رقم الهاتف للعرض في الجداول - نسخة محسنة"""
        # قائمة بجميع حقول الهاتف المحتملة
        phone_fields = [
            ('phone', 'الهاتف الشخصي'),
            ('father_phone', 'هاتف الأب'),
            ('mother_phone', 'هاتف الأم'), 
            ('home_phone', 'هاتف المنزل')
        ]
        
        for field_name, field_label in phone_fields:
            phone_value = getattr(self, field_name)
            if phone_value and str(phone_value).strip() and str(phone_value) != '0':
                # تنظيف الرقم وإرجاعه
                clean_phone = str(phone_value).strip()
                if clean_phone and clean_phone != '0':
                    return clean_phone
        
        return "-"
    
    def get_status_for_display(self):
        """إرجاع حالة الطالب متطابقة مع البروفايل"""
        try:
            from accounts.models import Studentenrollment
            has_active = Studentenrollment.objects.filter(
                student=self, 
                is_completed=False
            ).exists()
            
            return "نشط" if has_active else "غير نشط"
        except:
            return "نشط" if self.is_active else "غير نشط"
    
    def get_status_badge_class(self):
        """إرجاع كلاس البادج حسب الحالة"""
        try:
            from accounts.models import Studentenrollment
            has_active = Studentenrollment.objects.filter(
                student=self, 
                is_completed=False
            ).exists()
            
            return "badge-success" if has_active else "badge-danger"
        except:
            return "badge-success" if self.is_active else "badge-danger"
    
    def get_academic_year(self):
        """إرجاع الفصل الدراسي للطالب حسب تاريخ التسجيل"""
        from quick.models import AcademicYear
        if self.registration_date:
            try:
                return AcademicYear.objects.filter(
                    start_date__lte=self.registration_date,
                    end_date__gte=self.registration_date,
                    is_active=True
                ).first()
            except:
                return None
        return None
    
    @property
    def academic_year_name(self):
        """اسم الفصل الدراسي للعرض"""
        academic_year = self.get_academic_year()
        return academic_year.name if academic_year else "لم يتم تحديد الفصل"
   
    def update_enrollment_discounts(self, user):
        """تحديث جميع تسجيلات الطالب النشطة بناءً على الحسم الجديد"""
        from accounts.models import Studentenrollment, JournalEntry, Transaction
        
        with db_transaction.atomic():
            active_enrollments = Studentenrollment.objects.filter(
                student=self, 
                is_completed=False
            )
            
            for enrollment in active_enrollments:
                # حفظ القيم القديمة للمقارنة
                old_discount_percent = enrollment.discount_percent
                old_discount_amount = enrollment.discount_amount
                old_net_amount = enrollment.net_amount
                
                print(f"التسجيل: {enrollment.course.name}")
                print(f"الخصم القديم: {old_discount_percent}% / {old_discount_amount}")
                print(f"المبلغ الصافي القديم: {old_net_amount}")
                
                # تحديث قيم الحسم في التسجيل
                enrollment.discount_percent = self.discount_percent
                enrollment.discount_amount = self.discount_amount
                enrollment.save()
                
                new_net_amount = enrollment.net_amount
                print(f"الخصم الجديد: {enrollment.discount_percent}% / {enrollment.discount_amount}")
                print(f"المبلغ الصافي الجديد: {new_net_amount}")
                
                # إذا تغير المبلغ الصافي، قم بتحديث القيد المحاسبي
                if old_net_amount != new_net_amount and enrollment.enrollment_journal_entry:
                    print(f"سيتم تعديل القيد: الفرق {new_net_amount - old_net_amount}")
                    self._update_enrollment_journal_entry(enrollment, user, old_net_amount, new_net_amount)
                else:
                    print("لا يوجد فرق في المبلغ الصافي أو لا يوجد قيد")
    
    def _update_enrollment_journal_entry(self, enrollment, user, old_amount, new_amount):
        """تحديث قيد التسجيل المحاسبي بناءً على الفرق في المبلغ"""
        from accounts.models import JournalEntry, Transaction, Account
        
        journal_entry = enrollment.enrollment_journal_entry
        
        if not journal_entry:
            print("لا يوجد قيد تسجيل للتحرير")
            return
        
        # حساب الفرق في المبلغ
        amount_diff = new_amount - old_amount
        
        if amount_diff == 0:
            print("لا يوجد فرق في المبلغ")
            return
        
        print(f"فرق المبلغ: {amount_diff}")
        
        # الحصول على الحسابات من القيد الأصلي
        student_ar_account = None
        course_deferred_account = None
        
        original_transactions = journal_entry.transactions.all()
        for transaction in original_transactions:
            if transaction.is_debit:
                student_ar_account = transaction.account
            else:
                course_deferred_account = transaction.account
        
        if not student_ar_account or not course_deferred_account:
            print("لم يتم العثور على الحسابات في القيد الأصلي")
            return
        
        print(f"حساب ذمة الطالب: {student_ar_account}")
        print(f"حساب الإيرادات المؤجلة: {course_deferred_account}")
        
        # استخدام date.today() بدلاً من timezone.now().date()
        adjustment_entry = JournalEntry.objects.create(
            date=date.today(),  # ← تم التصحيح هنا
            description=f"تعديل حسم - {self.full_name} - {enrollment.course.name}",
            entry_type='ADJUSTMENT',
            total_amount=abs(amount_diff),
            created_by=user
        )
        
        if amount_diff > 0:
            # زيادة المبلغ - نفس اتجاه القيد الأصلي
            print("زيادة في المبلغ")
            # مدين: ذمة الطالب
            Transaction.objects.create(
                journal_entry=adjustment_entry,
                account=student_ar_account,
                amount=amount_diff,
                is_debit=True,
                description=f"تعديل زيادة حسم - {enrollment.course.name}"
            )
            # دائن: الإيرادات المؤجلة
            Transaction.objects.create(
                journal_entry=adjustment_entry,
                account=course_deferred_account,
                amount=amount_diff,
                is_debit=False,
                description=f"تعديل زيادة حسم - {self.full_name}"
            )
        else:
            # تخفيض المبلغ - عكس اتجاه القيد الأصلي
            amount_abs = abs(amount_diff)
            print(f"تخفيض في المبلغ: {amount_abs}")
            # مدين: الإيرادات المؤجلة
            Transaction.objects.create(
                journal_entry=adjustment_entry,
                account=course_deferred_account,
                amount=amount_abs,
                is_debit=True,
                description=f"تعديل تخفيض حسم - {self.full_name}"
            )
            # دائن: ذمة الطالب
            Transaction.objects.create(
                journal_entry=adjustment_entry,
                account=student_ar_account,
                amount=amount_abs,
                is_debit=False,
                description=f"تعديل تخفيض حسم - {enrollment.course.name}"
            )
        
        # ترحيل قيد التسوية
        try:
            adjustment_entry.post_entry(user)
            print("تم ترحيل قيد التسوية بنجاح")
        except Exception as e:
            print(f"خطأ في ترحيل القيد: {e}")

    class Meta:
        ordering = ['full_name']
        verbose_name = 'طالب'
        verbose_name_plural = 'الطلاب'

    def __str__(self):
        return self.full_name

    @property
    def ar_account(self):
        """Get or create the AR account for this student"""
        if self.account:
            return self.account
        
        # Create AR account if it doesn't exist
        from accounts.models import Account
        account = Account.get_or_create_student_ar_account(self)
        
        # Link the account to the student
        self.account = account
        self.save(update_fields=['account'])
        
        return account

    @property
    def has_account_link(self):
        """Check if student has an associated account"""
        return self.account is not None

    @property
    def examss(self):
        """جميع علامات الطالب"""
        return getattr(self, 'exams_set', None)
    
    @property
    def balance(self):
        """Calculate current AR balance for this student"""
        try:
            if not self.account:
                return Decimal('0')
            return self.account.get_net_balance()
        except Exception:
            return Decimal('0')

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)


class StudentWarning(models.Model):
    class Severity(models.TextChoices):
        NOTICE = 'notice', 'تنبيه'
        WARNING = 'warning', 'إنذار'
        CRITICAL = 'critical', 'إنذار نهائي'

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name='warnings',
        verbose_name='الطالب'
    )
    title = models.CharField(max_length=255, verbose_name='عنوان الإنذار')
    details = models.TextField(blank=True, verbose_name='تفاصيل الإنذار')
    severity = models.CharField(
        max_length=20,
        choices=Severity.choices,
        default=Severity.WARNING,
        verbose_name='درجة الإنذار'
    )
    is_active = models.BooleanField(default=True, verbose_name='مفعّل')
    created_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name='أضيف بواسطة'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'إنذار أكاديمي'
        verbose_name_plural = 'إنذارات أكاديمية'

    def __str__(self):
        return f"{self.student.full_name} - {self.get_severity_display()}"


# Signals: ensure AR account exists on create
from accounts.models import Account  # imported here to avoid circular during app loading


@receiver(post_save, sender=Student)
def ensure_student_ar_account(sender, instance, created, **kwargs):
    if created and not instance.account_id:
        try:
            ar = Account.get_or_create_student_ar_account(instance)
            instance.account_id = ar.id
            instance.save(update_fields=['account'])
        except Exception:
            pass



# ====================
# الطلاب السريعين 
# ====================

from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.utils import timezone

@receiver(pre_save, sender=Student)
def set_auto_academic_year(sender, instance, **kwargs):
    """تعيين الفصل الدراسي تلقائياً بناءً على تاريخ الإنشاء - نسخة مفتوحة"""
    print(f"🎯 [DEBUG] set_auto_academic_year called for: {instance.full_name}")
    
    if not instance.academic_year_id:
        from quick.models import AcademicYear
        from django.db.models import Q
        
        # استخدام تاريخ التسجيل إذا كان موجوداً، وإلا تاريخ اليوم
        target_date = instance.registration_date or timezone.now().date()
        print(f"📅 [DEBUG] استخدام التاريخ: {target_date}")
        
        # 🔥 البحث عن الفصول المفتوحة (بدون تاريخ انتهاء) أولاً
        academic_year = AcademicYear.objects.filter(
            Q(start_date__lte=target_date) &
            Q(end_date__isnull=True) &  # فقط الفصول المفتوحة
            Q(is_active=True)
        ).first()
        
        # إذا لم يوجد فصول مفتوحة، ابحث عن الفصول النشطة العادية
        if not academic_year:
            academic_year = AcademicYear.objects.filter(
                Q(start_date__lte=target_date) &
                Q(end_date__gte=target_date) &
                Q(is_active=True)
            ).first()
            print(f"🔍 [DEBUG] الفصل المغلق الموجود: {academic_year}")
        else:
            print(f"🔍 [DEBUG] الفصل المفتوح الموجود: {academic_year}")
        
        if academic_year:
            instance.academic_year = academic_year
            print(f"✅ [DEBUG] تم تعيين الفصل: {academic_year.name} (مفتوح: {academic_year.end_date is None})")
        else:
            print("❌ [DEBUG] لا يوجد فصل دراسي مناسب")
