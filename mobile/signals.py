from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from accounts.models import StudentReceipt
from attendance.models import Attendance
from exams.models import ExamGrade
from students.models import StudentWarning

from .models import ListeningTestAssignment, MobileDeviceToken, MobileNotification
from .utils_notifications import build_attendance_notification
from .utils_push import send_expo_message

try:
    from api.notifications import _get_parent_device_tokens
except Exception:
    _get_parent_device_tokens = None


def _create_notification(student, notification_type, title, message, teacher=None):
    if not student:
        return
    notification = MobileNotification.objects.create(
        student=student,
        teacher=teacher,
        notification_type=notification_type,
        title=title,
        message=message,
    )
    tokens = set(
        MobileDeviceToken.objects.filter(user_type="parent", user_id=student.id)
        .values_list("token", flat=True)
    )
    if _get_parent_device_tokens:
        try:
            tokens.update(_get_parent_device_tokens(student))
        except Exception:
            pass
    if not tokens:
        return
    data = {"type": notification_type, "notification_id": notification.id}
    for token in tokens:
        try:
            send_expo_message(
                token,
                title=title,
                body=message,
                data=data,
            )
        except Exception:
            continue


@receiver(post_save, sender=Attendance)
def attendance_notification(sender, instance, created, **kwargs):
    if not created:
        return
    title, message = build_attendance_notification(instance)
    _create_notification(
        student=instance.student,
        notification_type="attendance",
        title=title,
        message=message,
    )


@receiver(post_save, sender=StudentReceipt)
def payment_notification(sender, instance, created, **kwargs):
    if not created:
        return
    student = instance.student_profile or instance.student
    if not student:
        return
    _create_notification(
        student=student,
        notification_type="payment",
        title="دفعة مالية",
        message=f"تم تسجيل دفع {instance.paid_amount} ريال بتاريخ {instance.date}",
    )


@receiver(post_save, sender=ExamGrade)
def exam_grade_notification(sender, instance, created, **kwargs):
    if not instance.grade:
        return
    _create_notification(
        student=instance.student,
        notification_type="exam",
        title="تم إدخال علامة",
        message=f"{instance.exam.name} - {instance.grade}/{instance.exam.max_grade}",
    )


@receiver(post_save, sender=StudentWarning)
def warning_notification(sender, instance, created, **kwargs):
    if not created:
        return
    creator_teacher = getattr(instance.created_by, "teacher", None)
    _create_notification(
        student=instance.student,
        teacher=creator_teacher,
        notification_type="warning",
        title="إنذار جديد",
        message=f"{instance.title} - {instance.get_severity_display()}",
    )


@receiver(pre_save, sender=ListeningTestAssignment)
def listening_assignment_pre_save(sender, instance, **kwargs):
    if instance.pk:
        instance._previous_is_listened = sender.objects.filter(
            pk=instance.pk
        ).values_list("is_listened", flat=True).first() or False
    else:
        instance._previous_is_listened = False


@receiver(post_save, sender=ListeningTestAssignment)
def listening_assignment_notification(sender, instance, created, **kwargs):
    if created:
        if instance.is_listened:
            grade_info = f"علامة {instance.grade}" if instance.grade is not None else "تم التسميع"
        else:
            grade_info = instance.note or "لم يتم التسميع"
        _create_notification(
            student=instance.student,
            teacher=instance.test.teacher,
            notification_type="test_assignment",
            title="تم إضافتك إلى تسميع",
            message=f"{instance.test.title} - {grade_info}",
        )
        return

    previous = getattr(instance, "_previous_is_listened", False)
    if not previous and instance.is_listened:
        grade_info = f"علامة {instance.grade}" if instance.grade is not None else "تم التسميع"
        _create_notification(
            student=instance.student,
            teacher=instance.test.teacher,
            notification_type="test_assignment",
            title="تم تسجيل التسميع",
            message=f"{instance.test.title} - {grade_info}",
        )
