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


@receiver(post_save, sender=MobileDeviceToken)
def sync_mobile_user_on_token_save(sender, instance, **kwargs):
    """مزامنة مستخدم الموبايل عند حفظ التوكن الخاص بالجهاز"""
    u_type = instance.user_type
    u_id = instance.user_id
    if not u_type or not u_id:
        return
        
    from api.models import MobileUser
    from students.models import Student
    from employ.models import Teacher
    
    try:
        if u_type == 'parent':
            exists = MobileUser.objects.filter(student_id=u_id, user_type='parent').exists()
            if not exists:
                student = Student.objects.filter(id=u_id).first()
                if student:
                    MobileUser.objects.create(
                        student=student,
                        username=f"parent_{student.id}_{student.phone or student.student_number or u_id}",
                        phone_number=student.phone or student.student_number or "",
                        user_type='parent',
                        is_active=True,
                        is_verified=True
                    )
        elif u_type == 'student':
            exists = MobileUser.objects.filter(student_id=u_id, user_type='student').exists()
            if not exists:
                student = Student.objects.filter(id=u_id).first()
                if student:
                    MobileUser.objects.create(
                        student=student,
                        username=f"student_{student.id}_{student.phone or student.student_number or u_id}",
                        phone_number=student.phone or student.student_number or "",
                        user_type='student',
                        is_active=True,
                        is_verified=True
                    )
        elif u_type == 'teacher':
            exists = MobileUser.objects.filter(teacher_id=u_id, user_type='teacher').exists()
            if not exists:
                teacher = Teacher.objects.filter(id=u_id).first()
                if teacher:
                    MobileUser.objects.create(
                        teacher=teacher,
                        username=f"teacher_{teacher.id}_{teacher.phone_number or u_id}",
                        phone_number=teacher.phone_number or "",
                        user_type='teacher',
                        is_active=True,
                        is_verified=True
                    )
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Error in sync_mobile_user_on_token_save: {e}")

