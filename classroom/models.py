from django.core.exceptions import ValidationError
from django.db import models

from courses.models import Subject
from students.models import Student


class Classroom(models.Model):
    class BranchChoices(models.TextChoices):
        LITERARY = 'أدبي', 'الأدبي'
        SCIENTIFIC = 'علمي', 'العلمي'
        NINTH_GRADE = 'تاسع', 'الصف التاسع'

    CLASS_TYPE_CHOICES = [
        ('study', 'شعبة دراسية'),
        ('course', 'دورة'),
    ]

    name = models.CharField(max_length=50, verbose_name='اسم الشعبة', default='الشعبة 1')
    class_type = models.CharField(
        max_length=10,
        choices=CLASS_TYPE_CHOICES,
        verbose_name='نوع الشعبة',
        default='study',
    )
    branches = models.CharField(
        max_length=100,
        choices=BranchChoices.choices,
        verbose_name='الفرع',
        blank=True,
        null=True,
    )
    min_capacity = models.PositiveIntegerField(default=1, verbose_name='الحد الأدنى', null=True, blank=True)
    max_capacity = models.PositiveIntegerField(default=0, verbose_name='الحد الأقصى', null=True, blank=True)
    is_active = models.BooleanField(default=True, verbose_name='نشطة')

    def clean(self):
        if self.class_type == 'study' and not self.branches:
            raise ValidationError('يجب تحديد الفرع للشعبة الدراسية')
        if self.class_type == 'course' and self.branches:
            self.branches = None
        if self.class_type == 'course' and self.max_capacity and self.min_capacity and self.min_capacity > self.max_capacity:
            raise ValidationError('الحد الأدنى للكلاس لا يمكن أن يكون أكبر من الحد الأقصى.')

    @property
    def students(self):
        return Student.objects.filter(classroom_enrollments__classroom=self).distinct()

    def __str__(self):
        if self.class_type == 'study':
            return f'{self.name} - {self.get_branches_display()}'
        return f'{self.name} (دورة)'

    class Meta:
        verbose_name = 'شعبة'
        verbose_name_plural = 'شعب'


class Classroomenrollment(models.Model):
    classroom = models.ForeignKey(Classroom, on_delete=models.CASCADE, related_name='enrollments')
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name='classroom_enrollments',
        null=True,
        blank=True,
    )
    enrolled_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('classroom', 'student')

    def clean(self):
        if self.classroom.class_type == 'study':
            existing_study_enrollment = Classroomenrollment.objects.filter(
                student=self.student,
                classroom__class_type='study',
            ).exclude(classroom=self.classroom).exists()

            if existing_study_enrollment:
                raise ValidationError('الطالب مسجل بالفعل في شعبة دراسية أخرى')

    def __str__(self):
        return f'{self.student} في {self.classroom}'


class ClassroomSubject(models.Model):
    classroom = models.ForeignKey(Classroom, on_delete=models.CASCADE, verbose_name='الشعبة')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, verbose_name='المادة')

    class Meta:
        unique_together = ('classroom', 'subject')
        verbose_name = 'مادة الشعبة'
        verbose_name_plural = 'مواد الشعب'

    def __str__(self):
        return f'{self.classroom.name} - {self.subject.name}'
