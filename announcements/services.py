from dataclasses import dataclass

from django.contrib.auth.models import User
from django.utils import timezone

from employ.models import Teacher
from students.models import Student

from .models import Announcement, AnnouncementReceipt


class _SafeFormatDict(dict):
    def __missing__(self, key):
        return "{" + key + "}"


@dataclass
class RenderedAnnouncement:
    id: int
    title: str
    message: str
    action_label: str
    action_url: str
    created_at: object
    starts_at: object
    ends_at: object
    show_as_popup: bool
    audience_type: str
    source: Announcement


def render_announcement_for_user(announcement, user):
    context = _build_user_context(user)
    return _render_announcement(announcement, context)


def render_announcement_for_student(announcement, student):
    context = _build_student_context(student)
    return _render_announcement(announcement, context)


def render_announcement_for_parent(announcement, student, login_role=""):
    context = _build_parent_context(student, login_role)
    return _render_announcement(announcement, context)


def render_announcement_for_teacher(announcement, teacher):
    context = _build_teacher_context(teacher)
    return _render_announcement(announcement, context)


def get_active_announcements_for_user(user):
    announcements = Announcement.objects.active().filter(audience_type=Announcement.AUDIENCE_USER, show_as_popup=True)
    receipts = {
        receipt.announcement_id: receipt
        for receipt in AnnouncementReceipt.objects.filter(announcement__in=announcements, recipient_user=user)
    }
    visible = [announcement for announcement in announcements if not getattr(receipts.get(announcement.id), "dismissed_at", None)]
    return [render_announcement_for_user(announcement, user) for announcement in visible]


def mark_web_announcement_dismissed(announcement, user):
    now = timezone.now()
    receipt, _ = AnnouncementReceipt.objects.get_or_create(
        announcement=announcement,
        recipient_user=user,
        defaults={"first_seen_at": now},
    )
    if not receipt.first_seen_at:
        receipt.first_seen_at = now
    if not receipt.read_at:
        receipt.read_at = now
    receipt.dismissed_at = now
    receipt.save(update_fields=["first_seen_at", "read_at", "dismissed_at", "updated_at"])
    return receipt


def get_parent_announcements(student, login_role="", limit=None, mark_read=False):
    qs = Announcement.objects.active().filter(
        audience_type=Announcement.AUDIENCE_STUDENT if login_role == "student" else Announcement.AUDIENCE_PARENT
    )
    if limit:
        qs = qs[:limit]
    announcements = list(qs)
    if mark_read:
        _mark_student_announcements_read(announcements, student, login_role)
    renderer = render_announcement_for_student if login_role == "student" else lambda item, obj: render_announcement_for_parent(item, obj, login_role)
    return [renderer(announcement, student) for announcement in announcements]


def count_unread_parent_announcements(student, login_role=""):
    announcements = list(
        Announcement.objects.active().filter(
            audience_type=Announcement.AUDIENCE_STUDENT if login_role == "student" else Announcement.AUDIENCE_PARENT
        )
    )
    receipts = {
        receipt.announcement_id: receipt
        for receipt in AnnouncementReceipt.objects.filter(
            announcement__in=announcements,
            recipient_student=student,
            login_role=login_role or "",
        )
    }
    return sum(1 for announcement in announcements if not getattr(receipts.get(announcement.id), "read_at", None))


def get_teacher_announcements(teacher, limit=None, mark_read=False):
    qs = Announcement.objects.active().filter(audience_type=Announcement.AUDIENCE_TEACHER)
    if limit:
        qs = qs[:limit]
    announcements = list(qs)
    if mark_read:
        _mark_teacher_announcements_read(announcements, teacher)
    return [render_announcement_for_teacher(announcement, teacher) for announcement in announcements]


def build_announcement_previews(announcement, limit=3):
    if announcement.audience_type == Announcement.AUDIENCE_USER:
        users = User.objects.order_by("id")[:limit]
        previews = []
        for user in users:
            rendered = render_announcement_for_user(announcement, user)
            previews.append(
                {
                    "label": user.get_full_name() or user.get_username(),
                    "title": rendered.title,
                    "message": rendered.message,
                    "action_label": rendered.action_label,
                    "action_url": rendered.action_url,
                }
            )
        return previews
    if announcement.audience_type == Announcement.AUDIENCE_STUDENT:
        students = Student.objects.order_by("id")[:limit]
        previews = []
        for student in students:
            rendered = render_announcement_for_student(announcement, student)
            previews.append(
                {
                    "label": student.full_name,
                    "title": rendered.title,
                    "message": rendered.message,
                    "action_label": rendered.action_label,
                    "action_url": rendered.action_url,
                }
            )
        return previews
    if announcement.audience_type == Announcement.AUDIENCE_PARENT:
        students = Student.objects.order_by("id")[:limit]
        previews = []
        for student in students:
            rendered = render_announcement_for_parent(announcement, student, "father")
            previews.append(
                {
                    "label": student.father_name or student.mother_name or f"ولي أمر {student.full_name}",
                    "title": rendered.title,
                    "message": rendered.message,
                    "action_label": rendered.action_label,
                    "action_url": rendered.action_url,
                }
            )
        return previews
    teachers = Teacher.objects.order_by("id")[:limit]
    previews = []
    for teacher in teachers:
        rendered = render_announcement_for_teacher(announcement, teacher)
        previews.append(
            {
                "label": teacher.full_name,
                "title": rendered.title,
                "message": rendered.message,
                "action_label": rendered.action_label,
                "action_url": rendered.action_url,
            }
        )
    return previews


def get_targeted_count(announcement):
    if announcement.audience_type == Announcement.AUDIENCE_USER:
        return User.objects.count()
    if announcement.audience_type == Announcement.AUDIENCE_STUDENT:
        return Student.objects.count()
    if announcement.audience_type == Announcement.AUDIENCE_PARENT:
        return Student.objects.count()
    if announcement.audience_type == Announcement.AUDIENCE_TEACHER:
        return Teacher.objects.count()
    return 0


def _render_announcement(announcement, context):
    safe_context = _SafeFormatDict(context)
    return RenderedAnnouncement(
        id=announcement.id,
        title=(announcement.title or "").format_map(safe_context),
        message=(announcement.message or "").format_map(safe_context),
        action_label=(announcement.action_label or "").format_map(safe_context),
        action_url=(announcement.action_url or "").format_map(safe_context),
        created_at=announcement.created_at,
        starts_at=announcement.starts_at,
        ends_at=announcement.ends_at,
        show_as_popup=announcement.show_as_popup,
        audience_type=announcement.audience_type,
        source=announcement,
    )


def _build_user_context(user):
    return {
        "name": user.get_full_name() or user.get_username(),
        "username": user.get_username(),
        "email": user.email or "",
        "first_name": user.first_name or "",
        "last_name": user.last_name or "",
    }


def _build_student_context(student):
    return {
        "name": student.full_name,
        "student_name": student.full_name,
        "student_number": student.student_number or student.student_id,
        "student_phone": student.phone or student.get_display_phone(),
        "branch": getattr(student, "get_branch_display", lambda: "")() or student.branch or "",
    }


def _build_parent_context(student, login_role=""):
    parent_role = {
        "father": "الأب",
        "mother": "الأم",
    }.get(login_role, "ولي الأمر")
    if login_role == "father":
        parent_name = student.father_name or f"ولي أمر {student.full_name}"
    elif login_role == "mother":
        parent_name = student.mother_name or f"ولي أمر {student.full_name}"
    else:
        parent_name = student.father_name or student.mother_name or f"ولي أمر {student.full_name}"
    return {
        "name": parent_name,
        "parent_name": parent_name,
        "father_name": student.father_name or "",
        "mother_name": student.mother_name or "",
        "student_name": student.full_name,
        "parent_role": parent_role,
    }


def _build_teacher_context(teacher):
    return {
        "name": teacher.full_name,
        "teacher_name": teacher.full_name,
        "phone_number": teacher.phone_number or "",
    }


def _mark_student_announcements_read(announcements, student, login_role=""):
    now = timezone.now()
    for announcement in announcements:
        receipt, _ = AnnouncementReceipt.objects.get_or_create(
            announcement=announcement,
            recipient_student=student,
            login_role=login_role or "",
            defaults={"first_seen_at": now, "read_at": now},
        )
        updated_fields = []
        if not receipt.first_seen_at:
            receipt.first_seen_at = now
            updated_fields.append("first_seen_at")
        if not receipt.read_at:
            receipt.read_at = now
            updated_fields.append("read_at")
        if updated_fields:
            updated_fields.append("updated_at")
            receipt.save(update_fields=updated_fields)


def _mark_teacher_announcements_read(announcements, teacher):
    now = timezone.now()
    for announcement in announcements:
        receipt, _ = AnnouncementReceipt.objects.get_or_create(
            announcement=announcement,
            recipient_teacher=teacher,
            defaults={"first_seen_at": now, "read_at": now},
        )
        updated_fields = []
        if not receipt.first_seen_at:
            receipt.first_seen_at = now
            updated_fields.append("first_seen_at")
        if not receipt.read_at:
            receipt.read_at = now
            updated_fields.append("read_at")
        if updated_fields:
            updated_fields.append("updated_at")
            receipt.save(update_fields=updated_fields)
