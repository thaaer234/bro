import logging
from datetime import date as date_type
from datetime import datetime as datetime_type

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils.dateparse import parse_date

from accounts.models import StudentReceipt
from attendance.models import Attendance
from exams.models import ExamGrade

from .notifications import notify_student_parents

logger = logging.getLogger(__name__)


def _normalize_date(value):
    if isinstance(value, datetime_type):
        return value.date()
    if isinstance(value, date_type):
        return value
    if isinstance(value, str):
        parsed = parse_date(value)
        return parsed if parsed else value
    return value


def _isoformat_date(value):
    normalized = _normalize_date(value)
    if hasattr(normalized, "isoformat"):
        return normalized.isoformat()
    if normalized is None:
        return ""
    return str(normalized)


@receiver(pre_save, sender=Attendance)
def _capture_attendance_status(sender, instance, **kwargs):
    instance.date = _normalize_date(instance.date)
    if not instance.pk:
        instance._previous_status = None
        return
    instance._previous_status = (
        sender.objects.filter(pk=instance.pk).values_list('status', flat=True).first()
    )


@receiver(pre_save, sender=ExamGrade)
def _capture_exam_grade(sender, instance, **kwargs):
    if not instance.pk:
        instance._previous_grade = None
        return
    instance._previous_grade = (
        sender.objects.filter(pk=instance.pk).values_list('grade', flat=True).first()
    )


@receiver(post_save, sender=Attendance)
def _notify_attendance_parents(sender, instance, created, **kwargs):
    status = instance.status
    if status not in {Attendance.Status.ABSENT, Attendance.Status.LATE}:
        return

    previous_status = getattr(instance, '_previous_status', None)
    if not created and previous_status == status:
        return

    student = instance.student
    title = f"تحديث حضور {student.full_name}"
    body = (
        f"تم تسجيل {instance.get_status_display()} بتاريخ {_isoformat_date(instance.date)} في "
        f"{instance.classroom.name}."
    )
    data = {
        'type': 'attendance',
        'student_id': student.id,
        'status': status,
        'classroom': instance.classroom.name,
        'date': _isoformat_date(instance.date)
    }
    sent = notify_student_parents(student, title, body, data=data)
    if sent:
        logger.debug('%s attendance notifications queued for student %s', sent, student.id)


@receiver(post_save, sender=ExamGrade)
def _notify_exam_grade_parents(sender, instance, created, **kwargs):
    if instance.grade is None:
        return

    previous_grade = getattr(instance, '_previous_grade', None)
    if not created and previous_grade == instance.grade:
        return

    student = instance.student
    exam = instance.exam
    grade_display = instance.grade_normalized or str(instance.grade)
    title = f"علامة جديدة لـ {student.full_name}"
    body = (
        f"تم تسجيل {grade_display} في {exam.name} ({exam.subject.name})."
    )
    data = {
        'type': 'grade',
        'student_id': student.id,
        'exam_id': exam.id,
        'grade': grade_display,
        'course': exam.subject.name,
        'date': exam.exam_date.isoformat()
    }
    sent = notify_student_parents(student, title, body, data=data)
    if sent:
        logger.debug('%s grade notifications queued for student %s', sent, student.id)


@receiver(post_save, sender=StudentReceipt)
def _notify_payment_parents(sender, instance, created, **kwargs):
    if not created:
        return

    student = instance.student or instance.student_profile
    if not student:
        return

    paid = instance.paid_amount
    title = "دفعة مالية جديدة"
    course_name = instance.course_name or getattr(instance.course, 'name', 'الدورة')
    body = (
        f"تم تسجيل دفعة بمقدار {paid} ليرة سورية لـ {student.full_name} ({course_name})."
    )
    data = {
        'type': 'payment',
        'student_id': student.id,
        'receipt_id': instance.id,
        'amount': str(paid),
        'course': course_name,
        'date': _isoformat_date(instance.date)
    }
    sent = notify_student_parents(student, title, body, data=data)
    if sent:
        logger.debug('%s payment notifications queued for student %s', sent, student.id)
