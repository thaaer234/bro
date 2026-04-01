from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models
from django.db import transaction as db_transaction
from django.db.models.signals import pre_delete
from django.dispatch import receiver
from django.utils import timezone

from students.models import Student

class AcademicYear(models.Model):
    name = models.CharField(max_length=100, verbose_name='اسم الفصل')
    year = models.CharField(max_length=20, verbose_name='السنة الدراسية')
    start_date = models.DateField(verbose_name='تاريخ البدء')
    end_date = models.DateField(verbose_name='تاريخ الانتهاء', null=True, blank=True)  # اجعله اختياري
    is_active = models.BooleanField(default=True, verbose_name='نشط')
    is_closed = models.BooleanField(default=False, verbose_name='مقفول')
    closed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='مقفل بواسطة')
    closed_at = models.DateTimeField(null=True, blank=True, verbose_name='تاريخ الإقفال')
    is_open_ended = models.BooleanField(default=False, verbose_name='مفتوح غير مسكر') 
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'فصل دراسي'
        verbose_name_plural = 'فصول دراسية'
        ordering = ['-start_date']

    def __str__(self):
        return f"{self.name} - {self.year}"

class QuickCourse(models.Model):
    COURSE_TYPE_CHOICES = [
        ('INTENSIVE', 'مكثفة'),
        ('REGULAR', 'عادية'),
        ('WEEKEND', 'نهاية أسبوع'),
        ('EXAM', 'امتحانية'),
    ]
    
    name = models.CharField(max_length=200, verbose_name='اسم الدورة')
    name_ar = models.CharField(max_length=200, blank=True, verbose_name='الاسم بالعربية')
    course_type = models.CharField(max_length=20, choices=COURSE_TYPE_CHOICES, default='REGULAR', verbose_name='نوع الدورة')
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, verbose_name='الفصل الدراسي')
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='السعر')
    duration_weeks = models.PositiveIntegerField(default=4, verbose_name='المدة (أسابيع)')
    hours_per_week = models.PositiveIntegerField(default=6, verbose_name='ساعات أسبوعياً')
    description = models.TextField(blank=True, verbose_name='الوصف')
    cost_center = models.ForeignKey('accounts.CostCenter', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='مركز التكلفة')
    is_active = models.BooleanField(default=True, verbose_name='نشط')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='أنشئ بواسطة')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'دورة سريعة'
        verbose_name_plural = 'دورات سريعة'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} - {self.academic_year}"

    @property
    def active_sessions_count(self):
        return self.sessions.filter(is_active=True).count()

    @property
    def total_session_capacity(self):
        return sum(session.capacity for session in self.sessions.filter(is_active=True))

    @property
    def assigned_students_count(self):
        return QuickCourseSessionEnrollment.objects.filter(
            session__course=self,
            session__is_active=True,
            enrollment__is_completed=False,
            enrollment__student__is_active=True,
        ).count()


class QuickCourseTimeOption(models.Model):
    course = models.ForeignKey(QuickCourse, on_delete=models.CASCADE, related_name='time_options')
    title = models.CharField(max_length=200, verbose_name='اسم الخيار')
    start_date = models.DateField(verbose_name='تاريخ البداية')
    end_date = models.DateField(verbose_name='تاريخ النهاية')
    start_time = models.TimeField(verbose_name='وقت البداية')
    end_time = models.TimeField(null=True, blank=True, verbose_name='وقت النهاية')
    meeting_days = models.CharField(max_length=200, blank=True, verbose_name='أيام الدوام')
    min_capacity = models.PositiveIntegerField(default=1, verbose_name='الحد الأدنى')
    max_capacity = models.PositiveIntegerField(default=0, verbose_name='الحد الأقصى')
    preferred_room = models.ForeignKey(
        'classroom.Classroom',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='quick_time_options',
        verbose_name='القاعة المفضلة',
    )
    priority = models.PositiveIntegerField(default=1, verbose_name='الأولوية')
    is_active = models.BooleanField(default=True, verbose_name='نشط')
    notes = models.TextField(blank=True, verbose_name='ملاحظات')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_quick_time_options')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'وقت متاح للدورة السريعة'
        verbose_name_plural = 'الأوقات المتاحة للدورات السريعة'
        ordering = ['priority', 'start_date', 'start_time', 'id']

    def __str__(self):
        return f"{self.course.name} - {self.title}"

    def clean(self):
        if self.end_date < self.start_date:
            raise ValidationError('تاريخ النهاية يجب أن يكون بعد أو يساوي تاريخ البداية.')
        if self.end_time and self.end_time <= self.start_time:
            raise ValidationError('وقت النهاية يجب أن يكون بعد وقت البداية.')
        if self.max_capacity and self.min_capacity > self.max_capacity:
            raise ValidationError('الحد الأدنى لا يمكن أن يكون أكبر من الحد الأقصى.')

    @property
    def total_days(self):
        return ((self.end_date - self.start_date).days + 1) if self.end_date and self.start_date else 0


class QuickCourseSession(models.Model):
    course = models.ForeignKey(QuickCourse, on_delete=models.CASCADE, related_name='sessions')
    time_option = models.ForeignKey(QuickCourseTimeOption, on_delete=models.SET_NULL, null=True, blank=True, related_name='generated_sessions')
    title = models.CharField(max_length=200, verbose_name='اسم الصف')
    code = models.CharField(max_length=40, blank=True, verbose_name='رمز الصف')
    min_capacity = models.PositiveIntegerField(default=1, verbose_name='الحد الأدنى للافتتاح')
    capacity = models.PositiveIntegerField(default=0, verbose_name='الحد الأقصى')
    start_date = models.DateField(verbose_name='تاريخ البداية')
    end_date = models.DateField(verbose_name='تاريخ النهاية')
    start_time = models.TimeField(verbose_name='وقت البداية')
    end_time = models.TimeField(null=True, blank=True, verbose_name='وقت النهاية')
    meeting_days = models.CharField(max_length=200, blank=True, verbose_name='أيام الدوام')
    room_name = models.CharField(max_length=120, blank=True, verbose_name='القاعة')
    room = models.ForeignKey(
        'classroom.Classroom',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='quick_sessions',
        verbose_name='القاعة',
    )
    notes = models.TextField(blank=True, verbose_name='ملاحظات')
    is_active = models.BooleanField(default=True, verbose_name='نشط')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_quick_sessions')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'كلاس دورة سريعة'
        verbose_name_plural = 'كلاسات الدورات السريعة'
        ordering = ['start_date', 'start_time', 'id']

    def __str__(self):
        return f"{self.course.name} - {self.title}"

    def clean(self):
        if self.end_time and self.end_time <= self.start_time:
            raise ValidationError('وقت النهاية يجب أن يكون بعد وقت البداية.')
        if self.end_date < self.start_date:
            raise ValidationError('تاريخ النهاية يجب أن يكون بعد أو يساوي تاريخ البداية.')
        if self.capacity and self.min_capacity and self.min_capacity > self.capacity:
            raise ValidationError('الحد الأدنى لا يمكن أن يكون أكبر من الحد الأقصى.')

    @property
    def total_days(self):
        return ((self.end_date - self.start_date).days + 1) if self.end_date and self.start_date else 0

    @property
    def enrolled_count(self):
        return self.session_enrollments.filter(
            enrollment__is_completed=False,
            enrollment__student__is_active=True,
        ).count()

    @property
    def available_seats(self):
        if not self.capacity:
            return 0
        return max(0, self.capacity - self.enrolled_count)

    @property
    def progress_days(self):
        today = timezone.localdate()
        if today < self.start_date:
            return 0
        return min(self.total_days, (today - self.start_date).days + 1)

    @property
    def meets_minimum_capacity(self):
        return self.enrolled_count >= self.min_capacity

    @property
    def is_upcoming(self):
        return timezone.localdate() < self.start_date

    @property
    def is_finished(self):
        return timezone.localdate() > self.end_date

    @property
    def is_attendance_open(self):
        today = timezone.localdate()
        return self.start_date <= today <= self.end_date and self.is_active

    @property
    def display_code(self):
        return self.code or f"S{self.pk or ''}"

    def get_day_number_for_date(self, attendance_date):
        if not attendance_date or attendance_date < self.start_date or attendance_date > self.end_date:
            return None
        return (attendance_date - self.start_date).days + 1


class QuickCourseSessionEnrollment(models.Model):
    session = models.ForeignKey(QuickCourseSession, on_delete=models.CASCADE, related_name='session_enrollments')
    enrollment = models.OneToOneField('QuickEnrollment', on_delete=models.CASCADE, related_name='session_assignment')
    assigned_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='quick_session_assignments')
    assigned_at = models.DateTimeField(auto_now_add=True)
    notes = models.CharField(max_length=255, blank=True, verbose_name='ملاحظات')

    class Meta:
        verbose_name = 'توزيع طالب على كلاس سريع'
        verbose_name_plural = 'توزيعات الطلاب على الصفوف السريعة'
        ordering = ['session__start_date', 'session__start_time', 'id']

    def __str__(self):
        return f"{self.enrollment.student.full_name} -> {self.session.title}"

    def clean(self):
        if self.session.course_id != self.enrollment.course_id:
            raise ValidationError('لا يمكن توزيع الطالب على كلاس تابع لدورة مختلفة.')

        if self.session.capacity and self.session.enrolled_count >= self.session.capacity:
            existing_session_id = getattr(self, 'pk', None)
            current_count = self.session.session_enrollments.exclude(pk=existing_session_id).count()
            if current_count >= self.session.capacity:
                raise ValidationError('هذا الصف وصل إلى السعة القصوى.')


class QuickCourseSessionAttendance(models.Model):
    STATUS_CHOICES = [
        ('present', 'حاضر'),
        ('absent', 'غائب'),
        ('late', 'متأخر'),
        ('excused', 'غياب مبرر'),
    ]

    session = models.ForeignKey(QuickCourseSession, on_delete=models.CASCADE, related_name='attendance_records')
    enrollment = models.ForeignKey('QuickEnrollment', on_delete=models.CASCADE, related_name='quick_session_attendance')
    attendance_date = models.DateField(verbose_name='تاريخ الحضور')
    day_number = models.PositiveIntegerField(default=1, verbose_name='رقم اليوم')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='present', verbose_name='الحالة')
    notes = models.CharField(max_length=255, blank=True, verbose_name='ملاحظات')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_quick_attendance')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'حضور كلاس سريع'
        verbose_name_plural = 'حضور الصفوف السريعة'
        ordering = ['-attendance_date', 'session__start_time', 'id']
        unique_together = ['session', 'enrollment', 'attendance_date']

    def __str__(self):
        return f"{self.session.title} - {self.enrollment.student.full_name} - {self.attendance_date}"

    def clean(self):
        if self.session.course_id != self.enrollment.course_id:
            raise ValidationError('سجل الحضور لا يطابق دورة التسجيل.')
        if self.attendance_date < self.session.start_date or self.attendance_date > self.session.end_date:
            raise ValidationError('تاريخ الحضور خارج مدة الصف.')
        if not self.day_number:
            self.day_number = self.session.get_day_number_for_date(self.attendance_date) or 1

class QuickStudent(models.Model):
    STUDENT_TYPE_CHOICES = [
        ('QUICK', 'سريع'),
        ('REGULAR', 'نظامي'),
    ]
    COURSE_TRACK_CHOICES = [
        ('INTENSIVE', 'مكثفات'),
        ('EXAM', 'امتحانية'),
    ]
    
    student = models.OneToOneField(Student, on_delete=models.CASCADE, related_name='quick_student_profile')
    full_name = models.CharField(max_length=200, verbose_name='الاسم الكامل')
    phone = models.CharField(max_length=20, verbose_name='رقم الهاتف')
    email = models.EmailField(blank=True, verbose_name='البريد الإلكتروني')
    student_type = models.CharField(max_length=20, choices=STUDENT_TYPE_CHOICES, default='QUICK', verbose_name='نوع الطالب')
    course_track = models.CharField(max_length=20, choices=COURSE_TRACK_CHOICES, default='INTENSIVE', verbose_name='نوع الدورة')
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, verbose_name='الفصل الدراسي')
    notes = models.TextField(blank=True, verbose_name='ملاحظات')
    is_active = models.BooleanField(default=True, verbose_name='نشط')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='أنشئ بواسطة')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'طالب سريع'
        verbose_name_plural = 'طلاب سريعين'
        ordering = ['-created_at']

    def __str__(self):
        return self.full_name
    

    # ==================
    # الحقول المضافة...
    # الحقول الحالية...
    
    @property
    def auto_academic_year(self):
        """الفصل الدراسي التلقائي بناءً على تاريخ الإنشاء"""
        from .models import AcademicYear
        if self.created_at:
            try:
                return AcademicYear.objects.filter(
                    start_date__lte=self.created_at.date(),
                    end_date__gte=self.created_at.date(),
                    is_active=True
                ).first()
            except:
                return None
        return None
    
    @property
    def ar_account(self):
        """Get or create the AR account for this quick student"""
        from accounts.models import Account
        return Account.get_or_create_quick_student_ar_account(self)

    @property
    def balance(self):
        """Calculate current AR balance for this quick student"""
        try:
            return self.ar_account.get_net_balance()
        except Exception:
            return Decimal('0')

    def update_enrollment_discounts(self, user):
        """تحديث جميع تسجيلات الطالب السريع النشطة بناءً على الحسم الجديد"""
        from accounts.models import JournalEntry, Transaction
        
        with db_transaction.atomic():
            active_enrollments = QuickEnrollment.objects.filter(
                student=self, 
                is_completed=False
            )
            
            for enrollment in active_enrollments:
                # حفظ القيم القديمة للمقارنة
                old_net_amount = enrollment.calculated_net_amount
                
                # تحديث قيم الحسم في التسجيل
                enrollment.save()  # سيتم حساب net_amount تلقائياً في save
                
                new_net_amount = enrollment.calculated_net_amount
                
                # إذا تغير المبلغ الصافي، قم بتحديث القيد المحاسبي
                if old_net_amount != new_net_amount and hasattr(enrollment, 'enrollment_journal_entry'):
                    self._update_enrollment_journal_entry(enrollment, user, old_net_amount, new_net_amount)

    def _update_enrollment_journal_entry(self, enrollment, user, old_amount, new_amount):
        """تحديث قيد التسجيل المحاسبي بناءً على الفرق في المبلغ"""
        from accounts.models import JournalEntry, Transaction, Account, get_user_cash_account
        
        journal_entry = getattr(enrollment, 'enrollment_journal_entry', None)
        
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
        from datetime import date
        adjustment_entry = JournalEntry.objects.create(
            date=date.today(),
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


from django.db.models.signals import pre_save

@receiver(pre_save, sender=QuickStudent)
def set_auto_academic_year(sender, instance, **kwargs):
    """تعيين الفصل الدراسي تلقائياً للطالب السريع"""
    if not instance.academic_year_id and instance.auto_academic_year:
        instance.academic_year = instance.auto_academic_year

class QuickEnrollment(models.Model):
    PAYMENT_METHOD_CHOICES = [
        ('CASH', 'نقدي'),
        ('BANK', 'تحويل بنكي'),
        ('CREDIT', 'بطاقة ائتمان'),
    ]
    
    student = models.ForeignKey(QuickStudent, on_delete=models.CASCADE, related_name='enrollments')
    course = models.ForeignKey(QuickCourse, on_delete=models.CASCADE, related_name='enrollments')
    enrollment_date = models.DateField(default=timezone.now, verbose_name='تاريخ التسجيل')
    
    # الحقول المالية
    net_amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='المبلغ الصافي', default=0)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='المبلغ الإجمالي', default=0)
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name='نسبة الخصم %')
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='قيمة الخصم')
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default='CASH', verbose_name='طريقة الدفع')
    
    is_completed = models.BooleanField(default=False, verbose_name='مكتمل')
    completion_date = models.DateField(null=True, blank=True, verbose_name='تاريخ الإكمال')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'تسجيل سريع'
        verbose_name_plural = 'تسجيلات سريعة'
        unique_together = ['student', 'course']

    def __str__(self):
        return f"{self.student.full_name} - {self.course.name}"

    @property
    def enrollment_reference(self):
        return f"QE-{self.id}" if self.id else None

    @property
    def enrollment_journal_entry(self):
        reference = self.enrollment_reference
        if not reference:
            return None
        from accounts.models import JournalEntry
        return JournalEntry.objects.filter(reference=reference).first()

    @property
    def calculated_net_amount(self):
        """حساب المبلغ الصافي بعد الخصم (خاصية محسوبة)"""
        total = self.total_amount or Decimal('0')
        discount_from_percent = total * (self.discount_percent / Decimal('100'))
        discount_from_amount = self.discount_amount or Decimal('0')
        return max(Decimal('0'), total - discount_from_percent - discount_from_amount)

    def save(self, *args, **kwargs):
        # حساب net_amount تلقائياً عند الحفظ إذا كان صفراً
        if self.net_amount == 0 and self.course:
            self.net_amount = self.course.price
            self.total_amount = self.course.price
        
        # أو حساب net_amount من الخصم إذا كانت هناك قيم خصم
        if self.discount_percent > 0 or self.discount_amount > 0:
            calculated_net = self.calculated_net_amount
            if calculated_net > 0:
                self.net_amount = calculated_net
        
        super().save(*args, **kwargs)

    def create_accrual_enrollment_entry(self, user):
        """إنشاء قيد محاسبي للتسجيل السريع"""
        from accounts.models import Account, JournalEntry, Transaction

        existing_entry = self.enrollment_journal_entry
        if existing_entry:
            return existing_entry
        
        # الحسابات الخاصة بالطلاب السريعين
        student_ar_account = Account.get_or_create_quick_student_ar_account(self.student)
        deferred_account = Account.get_or_create_quick_course_deferred_account(self.course)
        
        # إنشاء قيد اليومية
        entry = JournalEntry.objects.create(
            reference=f"QE-{self.id}",
            date=self.enrollment_date,
            description=f"تسجيل سريع - {self.student.full_name} في {self.course.name}",
            entry_type='enrollment',
            total_amount=self.net_amount,
            created_by=user
        )
        
        # مدين: ذمم الطالب السريع
        Transaction.objects.create(
            journal_entry=entry,
            account=student_ar_account,
            amount=self.net_amount,
            is_debit=True,
            description=f"تسجيل سريع - {self.student.full_name}"
        )
        
        # دائن: إيرادات مؤجلة للدورة السريعة
        Transaction.objects.create(
            journal_entry=entry,
            account=deferred_account,
            amount=self.net_amount,
            is_debit=False,
            description=f"إيرادات مؤجلة - {self.course.name}"
        )
        
        # ترحيل القيد
        entry.post_entry(user)

        return entry
# Signals: ensure AR account exists on create
from accounts.models import Account

from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=QuickStudent)
def ensure_quick_student_ar_account(sender, instance, created, **kwargs):
    if created:
        try:
            ar = Account.get_or_create_quick_student_ar_account(instance)
            # لا حاجة لحفظ لأنها خاصية محسوبة
        except Exception as e:
            print(f"Error creating AR account for quick student: {e}")

class QuickStudentReceipt(models.Model):
    PAYMENT_METHOD_CHOICES = [
        ('CASH', 'نقدي'),
        ('BANK', 'تحويل بنكي'),
        ('CREDIT', 'بطاقة ائتمان'),
    ]
    
    date = models.DateField(default=timezone.now, verbose_name='التاريخ')
    quick_student = models.ForeignKey(
        'QuickStudent',
        on_delete=models.CASCADE, 
        verbose_name='الطالب السريع'
    )
    student_name = models.CharField(max_length=200, verbose_name='اسم الطالب')
    
    course = models.ForeignKey(
        'QuickCourse',
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        verbose_name='الدورة السريعة'
    )
    course_name = models.CharField(max_length=200, blank=True, verbose_name='اسم الدورة')
    
    quick_enrollment = models.ForeignKey(
        'QuickEnrollment',
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        verbose_name='التسجيل السريع'
    )
    
    # ✅ تصحيح: تغيير decimal_places من 2 إلى 0
    amount = models.DecimalField(max_digits=10, decimal_places=0, verbose_name='المبلغ')
    paid_amount = models.DecimalField(max_digits=10, decimal_places=0, verbose_name='المبلغ المدفوع')
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name='نسبة الخصم %')
    discount_amount = models.DecimalField(max_digits=10, decimal_places=0, default=0, verbose_name='قيمة الخصم')
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default='CASH', verbose_name='طريقة الدفع')
    
    receipt_number = models.CharField(max_length=50, blank=True, verbose_name='رقم الإيصال')
    is_printed = models.BooleanField(default=False, verbose_name='تم الطباعة')
    notes = models.TextField(blank=True, verbose_name='ملاحظات')
    
    journal_entry = models.ForeignKey(
        'accounts.JournalEntry', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        verbose_name='قيد اليومية'
    )
    
    created_by = models.ForeignKey('auth.User', on_delete=models.CASCADE, verbose_name='تم الإنشاء بواسطة')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'إيصال طالب سريع'
        verbose_name_plural = 'إيصالات الطلاب السريعين'
        ordering = ['-date', '-id']

    def __str__(self):
        return f"إيصال سريع {self.student_name} - {self.paid_amount}"

    def generate_receipt_number(self):
        """توليد رقم إيصال تلقائي"""
        if not self.receipt_number:
            date_str = self.date.strftime('%Y%m%d')
            last_receipt = QuickStudentReceipt.objects.filter(
                receipt_number__startswith=f'QS{date_str}'
            ).order_by('-receipt_number').first()
            
            if last_receipt and last_receipt.receipt_number:
                last_num = int(last_receipt.receipt_number[-4:])
                new_num = last_num + 1
            else:
                new_num = 1
                
            self.receipt_number = f'QS{date_str}{new_num:04d}'
        
        return self.receipt_number

    def save(self, *args, **kwargs):
        # توليد رقم الإيصال تلقائياً
        if not self.receipt_number:
            self.generate_receipt_number()
        
        # حفظ اسم الدورة تلقائياً
        if self.course and not self.course_name:
            self.course_name = self.course.name
            
        # حفظ اسم الطالب تلقائياً
        if self.quick_student and not self.student_name:
            self.student_name = self.quick_student.full_name
            
        super().save(*args, **kwargs)

    def create_accrual_journal_entry(self, user):
        """إنشاء قيد محاسبي للإيصال السريع"""
        from accounts.models import JournalEntry, Transaction, Account, get_user_cash_account
        
        # الحسابات الخاصة بالطلاب السريعين
        student_ar_account = Account.get_or_create_quick_student_ar_account(self.quick_student)
        
        # حساب النقدية
        cash_account = get_user_cash_account(user, fallback_code='121')
        
        # إنشاء قيد اليومية
        entry = JournalEntry.objects.create(
            reference=self.receipt_number,
            date=self.date,
            description=f"إيصال سريع - {self.student_name} - {self.course_name}",
            entry_type='receipt',
            total_amount=self.paid_amount,
            created_by=user
        )
        
        # مدين: النقدية
        Transaction.objects.create(
            journal_entry=entry,
            account=cash_account,
            amount=self.paid_amount,
            is_debit=True,
            description=f"إيصال سريع - {self.student_name}"
        )
        
        # دائن: ذمم الطالب السريع
        Transaction.objects.create(
            journal_entry=entry,
            account=student_ar_account,
            amount=self.paid_amount,
            is_debit=False,
            description=f"تسديد ذمم - {self.course_name}"
        )
        
        # ترحيل القيد
        entry.post_entry(user)
        
        # حفظ المرجع للقيد المحاسبي
        self.journal_entry = entry
        self.save(update_fields=['journal_entry'])
        
        return entry

    def get_linked_journal_entries(self):
        return [entry for entry in [self.journal_entry] if entry]


class QuickReceiptPrintJob(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_PROCESSING = 'processing'
    STATUS_COMPLETED = 'completed'
    STATUS_FAILED = 'failed'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'قيد الانتظار'),
        (STATUS_PROCESSING, 'قيد المعالجة'),
        (STATUS_COMPLETED, 'تمت الطباعة'),
        (STATUS_FAILED, 'فشلت الطباعة'),
    ]

    created_by = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='quick_print_jobs')
    quick_student = models.ForeignKey('QuickStudent', on_delete=models.CASCADE, related_name='print_jobs')
    payload = models.JSONField(default=dict)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    error_message = models.TextField(blank=True)
    picked_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'مهمة طباعة إيصالات سريعة'
        verbose_name_plural = 'مهام طباعة الإيصالات السريعة'
        ordering = ['status', 'created_at']

    def __str__(self):
        return f"Quick print job #{self.pk} - {self.quick_student.full_name}"


@receiver(pre_delete, sender=QuickEnrollment)
def delete_quick_entry_when_enrollment_deleted(sender, instance, **kwargs):
    if getattr(instance, '_skip_linked_cleanup', False):
        return

    entry = instance.enrollment_journal_entry
    if entry:
        entry._skip_linked_cleanup = True
        entry.delete()


@receiver(pre_delete, sender=QuickStudentReceipt)
def delete_quick_entry_when_receipt_deleted(sender, instance, **kwargs):
    if getattr(instance, '_skip_linked_cleanup', False):
        return

    for entry in instance.get_linked_journal_entries():
        entry._skip_linked_cleanup = True
        entry.delete()
