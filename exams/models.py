from django.db import models
from courses.models import Subject
from students.models import Student
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.translation import gettext_lazy as _

class Exam(models.Model):
    name = models.CharField(max_length=200, verbose_name=_('اسم الاختبار'))
    classroom = models.ForeignKey('classroom.Classroom', on_delete=models.CASCADE, verbose_name="الشعبة")
    subject = models.ForeignKey('courses.Subject', on_delete=models.CASCADE, verbose_name=_('المادة'))
    exam_date = models.DateField(verbose_name=_('تاريخ الاختبار'))
    max_grade = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=100,
        verbose_name=_('العلامة القصوى')
    )
    notes = models.TextField(blank=True, null=True, verbose_name=_('ملاحظات عامة'))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_('تاريخ الإنشاء'))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_('تاريخ التحديث'))
    
    class Meta:
        verbose_name = _('اختبار')
        verbose_name_plural = _('الاختبارات')
        ordering = ['-exam_date', 'name']
    
    def __str__(self):
        return f"{self.name} - {self.classroom.name} - {self.subject.name}"

class ExamGrade(models.Model):
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, verbose_name=_('الاختبار'))
    student = models.ForeignKey('students.Student', on_delete=models.CASCADE, verbose_name=_('الطالب'))
    grade = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        verbose_name=_('العلامة'),
        validators=[MinValueValidator(0)],
        null=True,
        blank=True
    )
    notes = models.TextField(blank=True, null=True, verbose_name=_('ملاحظات'))
    entered_at = models.DateTimeField(auto_now_add=True, verbose_name=_('تاريخ الإدخال'))
    
    class Meta:
        unique_together = ('exam', 'student')
        verbose_name = _('علامة اختبار')
        verbose_name_plural = _('علامات الاختبارات')
        ordering = ['student__full_name']
    
    def __str__(self):
        return f"{self.student.full_name} - {self.exam.name}: {self.grade}"
    @property
    def grade_normalized(self):
        """عرض العلامة بدون أصفار عشرية غير ضرورية"""
        if self.grade is None:
            return None
        # تحويل إلى float ثم إزالة الأصفار الزائدة
        grade_float = float(self.grade)
        if grade_float == 0:
            return "0"  # إرجاع 0 كسلسلة نصية
        elif grade_float.is_integer():
            return str(int(grade_float))
        else:
            # إزالة الأصفار غير الضرورية
            return ('%f' % grade_float).rstrip('0').rstrip('.')
class ExamType(models.Model):
    """نوع اختبار مخصص لكل مادة"""
    name = models.CharField(max_length=100, verbose_name=_('اسم الاختبار'))
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, verbose_name=_('المادة'))
    order = models.IntegerField(default=0, verbose_name=_('ترتيب الظهور'))
    max_grade = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=100,
        verbose_name=_('العلامة القصوى')
    )
    
    class Meta:
        unique_together = ('name', 'subject')
        verbose_name = _('نوع اختبار')
        verbose_name_plural = _('أنواع الاختبارات')
        ordering = ['order', 'name']
    
    def __str__(self):
        return f"{self.name} - {self.subject.name}"

class StudentExam(models.Model):
    EXAM_TYPE_CHOICES = [
        ('activity', 'نشاط'),
        ('monthly', 'شهري'), 
        ('midterm', 'نصفي'),
        ('final', 'نهائي'),
    ]
    
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="student_exams")
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, verbose_name=_('المادة'))
    exam_type = models.CharField(
        max_length=20,
        choices=EXAM_TYPE_CHOICES,
        verbose_name=_('نوع الامتحان')
    )
    grade = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        verbose_name=_('العلامة'),
        validators=[MinValueValidator(0)],
        null=True,
        blank=True
    )
    date = models.DateField(auto_now_add=True, verbose_name=_('تاريخ التسجيل'))
    notes = models.TextField(blank=True, null=True, verbose_name=_('ملاحظات'))
    classroom = models.ForeignKey(
        'classroom.Classroom', 
        on_delete=models.CASCADE,
        verbose_name="الشعبة",
        null=True
    )
    
    class Meta:
        unique_together = ('student', 'subject', 'exam_type')
        verbose_name = _('علامة')
        verbose_name_plural = _('العلامات')
        ordering = ['-date', 'student__full_name']
    
    def __str__(self):
        return f"{self.student.full_name} - {self.subject.name} - {self.get_exam_type_display()}: {self.grade}"