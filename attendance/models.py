from django.db import models
from django.utils import timezone
from classroom.models import Classroom
from students.models import Student
from employ.models import Teacher

from decimal import Decimal

class Attendance(models.Model):
    class Status(models.TextChoices):
        PRESENT = 'present', 'حاضر'
        ABSENT = 'absent', 'غائب'
        LATE = 'late', 'متأخر'
    
    student = models.ForeignKey(Student, on_delete=models.CASCADE, verbose_name='الطالب')
    classroom = models.ForeignKey(Classroom, on_delete=models.CASCADE, verbose_name='الشعبة')
    date = models.DateField(default=timezone.now, verbose_name='التاريخ')
    status = models.CharField(max_length=10, choices=Status.choices, default='absent', verbose_name='الحالة')
    notes = models.TextField(blank=True, null=True, verbose_name='ملاحظات')
    
    class Meta:
        verbose_name = 'حضور'
        verbose_name_plural = 'سجل الحضور'
        unique_together = ('student', 'date')  # منع تكرار تسجيل نفس الطالب في نفس اليوم
    
    def __str__(self):
        return f"{self.student.full_name} - {self.date} - {self.get_status_display()}"

class TeacherAttendance(models.Model):
    branch = models.CharField(
        max_length=20,
        choices=Teacher.BranchChoices.choices,
        default=Teacher.BranchChoices.SCIENTIFIC,
        verbose_name='Branch'
    )
    class Status(models.TextChoices):
        PRESENT = 'present', 'حاضر'
        NO_DUTY = 'no_duty', 'ليس لديه دوام اليوم'
    
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, verbose_name='المدرس')
    date = models.DateField(default=timezone.now, verbose_name='التاريخ')
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.NO_DUTY, verbose_name='الحالة')
    session_count = models.PositiveIntegerField(default=0, verbose_name='عدد الجلسات الكاملة')
    half_session_count = models.PositiveIntegerField(
        default=0, 
        verbose_name='عدد أنصاف الجلسات',
        help_text='عدد أنصاف الجلسات (كل نصف جلسة = 0.5 جلسة)'
    )
    notes = models.TextField(blank=True, null=True, verbose_name='ملاحظات')
    
    class Meta:
        verbose_name = 'حضور مدرس'
        verbose_name_plural = 'سجل حضور المدرسين'
        unique_together = ('teacher', 'date', 'branch')
    
    def __str__(self):
        return f"{self.teacher.full_name} - {self.branch} - {self.date} - {self.get_status_display()} - {self.get_total_sessions_display()}"

    @property
    def total_sessions(self):
        """إجمالي الجلسات (جلسات كاملة + أنصاف جلسات)"""
        if self.half_session_count > 0:
            return Decimal(str(self.session_count)) + (Decimal(str(self.half_session_count)) * Decimal('0.5'))
        return Decimal(str(self.session_count))
    
    def get_total_sessions_display(self):
        """عرض إجمالي الجلسات بشكل مفهوم"""
        if self.half_session_count > 0:
            return f"{self.session_count}.{self.half_session_count} جلسة ({self.total_sessions:.1f})"
        return f"{self.session_count} جلسة"
    
    def get_daily_salary_amount(self):
        """الحصول على مبلغ الراتب اليومي"""
        try:
            if (self.status == 'present' and 
                (self.session_count > 0 or self.half_session_count > 0) and 
                self.teacher.get_hourly_rate_for_branch(self.branch)):
                
                hourly_rate = self.teacher.get_hourly_rate_for_branch(self.branch) or Decimal('0')
                return hourly_rate * self.total_sessions
            return Decimal('0.00')
        except Exception:
            return Decimal('0.00')
    
    def save(self, *args, **kwargs):
        """حفظ الحضور بدون قيود محاسبية"""
        
        # إذا كانت الحالة "ليس لديه دوام اليوم" نضع عدد الجلسات = 0
        if self.status == 'no_duty':
            self.session_count = 0
            self.half_session_count = 0
        
        # منع التكرار قبل الحفظ
        if not self.pk:
            if TeacherAttendance.objects.filter(teacher=self.teacher, date=self.date, branch=self.branch).exists():
                from django.db import IntegrityError
                raise IntegrityError(f'يوجد بالفعل تسجيل حضور للمدرس {self.teacher.full_name} في تاريخ {self.date}')
        
        # حفظ الأساسي فقط
        super().save(*args, **kwargs)
    
    def delete(self, *args, **kwargs):
        """حذف الحضور فقط - لا توجد قيود محاسبية لحذفها"""
        super().delete(*args, **kwargs)

    @classmethod
    def delete_daily_attendance(cls, date):
        """حذف جميع سجلات حضور يوم معين"""
        try:
            # منع حذف التواريخ المستقبلية
            if date > timezone.now().date():
                raise ValueError("لا يمكن حذف حضور لتاريخ مستقبلي")
                
            daily_attendances = cls.objects.filter(date=date)
            count = daily_attendances.count()
            
            if count == 0:
                return 0
            
            # حذف جميع السجلات
            deleted_count, _ = daily_attendances.delete()
            return deleted_count
            
        except Exception as e:
            print(f"خطأ في حذف حضور اليوم: {e}")
            raise

    def has_salary_data(self):
        """التحقق من وجود بيانات راتب يمكن حسابها"""
        return (self.status == 'present' and 
                (self.session_count > 0 or self.half_session_count > 0) and 
                self.teacher.get_hourly_rate_for_branch(self.branch) is not None)
