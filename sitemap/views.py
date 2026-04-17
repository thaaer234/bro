from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.urls import NoReverseMatch, reverse
from urllib.parse import urlencode

from employ.models import EmployeePermission
from manuals.guide_data import build_manuals_context, build_user_manual_context


SITEMAP_PERMISSION_GROUPS = [
    ("students_", "students", "الطلاب النظاميون", "fas fa-user-graduate"),
    ("quick_students_", "quick", "الطلاب السريعون", "fas fa-bolt"),
    ("attendance_", "attendance", "الحضور", "fas fa-calendar-check"),
    ("classroom_", "classroom", "الشعب الدراسية", "fas fa-school"),
    ("courses_", "courses", "المواد الدراسية", "fas fa-book-open"),
    ("exams_", "exams", "الاختبارات", "fas fa-square-poll-vertical"),
    ("teachers_", "employ", "المدرسون", "fas fa-chalkboard-user"),
    ("hr_", "employ", "الموارد البشرية", "fas fa-users-gear"),
    ("accounting_", "accounts", "المحاسبة", "fas fa-calculator"),
    ("course_accounting_", "accounts", "دورات المحاسبة", "fas fa-file-invoice-dollar"),
    ("reports_", "pages", "التقارير والتحليلات", "fas fa-chart-line"),
    ("admin_", "pages", "الإدارة العامة", "fas fa-shield-halved"),
]


def _safe_reverse(name, *args, **kwargs):
    try:
        return reverse(name, args=args, kwargs=kwargs)
    except NoReverseMatch:
        return ""


def _build_guide_url(path, *, target="@primary-action", title="", message="", duration=10000, modal=""):
    clean_path = (path or "").strip()
    if not clean_path:
        return ""
    separator = "&" if "?" in clean_path else "?"
    params = {
        "guide": "1",
        "guide_target": target or "@primary-action",
        "guide_title": title or "خطوة موجهة",
        "guide_message": message or "اتبع العنصر المضيء لإكمال هذه الخطوة.",
        "guide_duration": duration,
    }
    if modal:
        params["guide_modal"] = modal
    return f"{clean_path}{separator}{urlencode(params)}"


def _button_icon(label):
    text = (label or "").strip()
    rules = [
        (("قيد", "يومية"), "fas fa-book-medical"),
        (("إضافة", "جديد"), "fas fa-plus-circle"),
        (("طالب سريع",), "fas fa-bolt"),
        (("طالب",), "fas fa-user-graduate"),
        (("مدرس", "أستاذ"), "fas fa-chalkboard-user"),
        (("موظف",), "fas fa-id-badge"),
        (("بحث", "فلتر"), "fas fa-magnifying-glass"),
        (("حفظ", "اعتماد"), "fas fa-floppy-disk"),
        (("طباعة", "pdf"), "fas fa-print"),
        (("تقرير", "كشف", "ميزان"), "fas fa-chart-column"),
        (("عرض الطلاب", "عرض"), "fas fa-users"),
        (("سلفة", "دفعة", "صرف"), "fas fa-hand-holding-dollar"),
        (("حضور",), "fas fa-calendar-check"),
        (("دورة",), "fas fa-book-open"),
        (("إيصال", "إيصالات"), "fas fa-receipt"),
        (("متأخر", "تأخر"), "fas fa-user-clock"),
        (("تعارض",), "fas fa-triangle-exclamation"),
        (("برنامج", "جدول"), "fas fa-calendar-days"),
        (("ربط",), "fas fa-link"),
        (("دليل",), "fas fa-map"),
        (("لوحة",), "fas fa-gauge-high"),
        (("ربط",), "fas fa-link"),
        (("إعداد", "صلاح"), "fas fa-sliders"),
    ]
    for keywords, icon in rules:
        if any(keyword in text for keyword in keywords):
            return icon
    return "fas fa-circle-nodes"


def _decorate_button(screen, button):
    label = (button.get("label") or "").strip()
    screen_slug = screen.get("slug", "")
    screen_path = screen.get("path", "") if str(screen.get("path", "")).startswith("/") else ""

    target_path = screen_path
    guide_target = "@primary-action"
    guide_title = f"تنقل مباشر: {label}"
    guide_message = f'انتقلت الآن إلى المكان الأنسب لتنفيذ إجراء "{label}". اتبع العنصر المضيء لإكمال الخطوة.'

    if "قيد" in label and "جديد" in label:
        target_path = _safe_reverse("accounts:journal_entry_create")
        guide_target = "@first-field"
    elif "إضافة طالب سريع" in label:
        target_path = _safe_reverse("quick:student_create")
        guide_target = "@first-field"
    elif "لوحة التحكم" in label:
        target_path = _safe_reverse("pages:index")
    elif "دليل المستخدم" in label:
        target_path = _safe_reverse("manuals:home")
        guide_target = "@search"
    elif "دليل التشغيل" in label:
        target_path = _safe_reverse("manuals:handbook")
        guide_target = "@search"
    elif "مجموعة الطلاب" in label:
        target_path = _safe_reverse("students:student_list")
        guide_target = '[data-guide-key="students-create"]'
    elif "المحاسبة" in label:
        target_path = _safe_reverse("accounts:dashboard")
        guide_target = '[data-guide-key="accounts-journal-create"]'
    elif "إضافة طالب" in label or "طالب جديد" in label:
        target_path = _safe_reverse("students:student_type_choice") or _safe_reverse("students:create_student")
    elif "الأسماء المكررة" in label:
        target_path = _safe_reverse("quick:duplicate_students_report")
        guide_target = "@search"
    elif "الطلاب المشتركون" in label:
        target_path = _safe_reverse("quick:student_intersections")
        guide_target = "@search"
    elif "فرز شبه يدوي" in label:
        target_path = _safe_reverse("quick:manual_sorting")
    elif "ربط تلقائي" in label:
        target_path = _safe_reverse("quick:student_list")
        guide_target = '[data-guide-key="quick-auto-assign-years"]'
        guide_message = "هذه الأداة تنفذ الربط التلقائي. راجع البيانات ثم استخدم الزر المضيء لإتمام الربط."
    elif "دورة جديدة" in label:
        target_path = _safe_reverse("quick:course_create")
        guide_target = "@first-field"
    elif "حضور الدورات السريعة" in label:
        target_path = _safe_reverse("quick:quick_course_attendance")
    elif "تعارض الطلاب" in label:
        target_path = _safe_reverse("quick:quick_course_conflicts_report")
        guide_target = "@search"
    elif "توليد برنامج لكل الدورات" in label:
        target_path = _safe_reverse("quick:course_list")
    elif "برنامج الصفوف" in label:
        target_path = _safe_reverse("quick:quick_course_schedule_print")
        guide_target = "@search"
    elif "حساب جديد" in label:
        target_path = _safe_reverse("accounts:account_create")
        guide_target = "@first-field"
    elif "الإيصالات والمصاريف" in label:
        target_path = _safe_reverse("accounts:receipts_expenses")
    elif "التقارير" in label:
        target_path = _safe_reverse("accounts:reports")
    elif "المتأخرون عن السداد" in label:
        target_path = _safe_reverse("quick:late_payment_courses")
        guide_target = "@search"
    elif screen_slug == "quick-outstanding-courses" and "عرض الطلاب" in label:
        target_path = (_safe_reverse("quick:outstanding_courses") or "") + "?course_type=INTENSIVE"
        guide_target = '[data-guide-key="quick-outstanding-show-students"]'
        guide_message = 'اختر الدورة المطلوبة ثم استخدم زر "عرض الطلاب" المضيء للوصول إلى تفاصيل غير المسددين.'
    elif screen_slug == "quick-outstanding-courses" and "طباعة" in label:
        target_path = (_safe_reverse("quick:outstanding_courses") or "") + "?course_type=INTENSIVE"
        guide_target = '[data-guide-key="quick-outstanding-print-intensive"]'
    elif screen_slug == "accounts-outstanding-courses" and "عرض حسب الشعب" in label:
        target_path = _safe_reverse("accounts:outstanding_students_by_classroom")
        guide_target = "@search"
    elif screen_slug == "accounts-outstanding-courses" and "الطلاب المنسحبين" in label:
        target_path = _safe_reverse("accounts:withdrawn_students")
        guide_target = "@search"
    elif screen_slug == "accounts-outstanding-courses" and "عرض الطلاب" in label:
        target_path = _safe_reverse("accounts:outstanding_courses")
        guide_target = '[data-guide-key="accounts-outstanding-show-students"]'
    elif "دفعات الأستاذ" in label or "دفعة للأستاذ" in label:
        target_path = (_safe_reverse("quick:outstanding_courses") or "") + "?course_type=INTENSIVE"
        guide_target = '[data-guide-key="quick-teacher-payout"]'
        guide_message = 'أنت الآن في قسم المتبقي للدورات السريعة. استخدم زر "دفعات الأستاذ" المضيء داخل صف الدورة المطلوبة.'
    elif "سلفة موظف" in label:
        target_path = _safe_reverse("employ:employee_advance_create")
        guide_target = "@first-field"
    elif "سلفة مدرس" in label:
        target_path = _safe_reverse("employ:teachers")
        guide_target = "@table-action"
    elif "مدرس جديد" in label or ("مدرس" in label and "جديد" in label):
        target_path = _safe_reverse("employ:create")
        guide_target = "@first-field"
    elif "حفظ" in label:
        guide_target = "button[type='submit'], .btn-success"
    elif "بحث" in label:
        guide_target = "@search"

    return {
        **button,
        "icon": _button_icon(label),
        "action_url": _build_guide_url(
            target_path,
            target=guide_target,
            title=guide_title,
            message=guide_message,
            duration=10000,
        ) if target_path else "",
        "action_target": guide_target,
    }


def _decorate_screens(screens):
    decorated = []
    for screen in screens:
        decorated.append(
            {
                **screen,
                "buttons": [_decorate_button(screen, button) for button in screen.get("buttons", [])],
            }
        )
    return decorated


def _build_template_control_groups(manual_template_groups, allowed_group_keys):
    allowed = set(allowed_group_keys or [])
    groups = []

    for group in manual_template_groups:
        if allowed and group.get("title") not in allowed:
            continue

        templates = []
        for template in group.get("templates", []):
            seen = set()
            controls = []
            for control in template.get("controls", []):
                if control.get("kind") not in {"رابط", "زر", "إدخال"}:
                    continue
                label = (control.get("label") or "").strip()
                if not label or label in {"form", "button"}:
                    continue
                dedupe_key = (control.get("kind"), label)
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)

                decorated = _decorate_button(
                    {
                        "slug": "",
                        "path": "",
                        "group": group.get("display_title") or group.get("title"),
                    },
                    control,
                )
                controls.append(
                    {
                        **decorated,
                        "kind": control.get("kind"),
                    }
                )

            if not controls:
                continue

            templates.append(
                {
                    "label": template.get("label"),
                    "path": template.get("path"),
                    "controls": controls,
                    "control_count": len(controls),
                }
            )

        if not templates:
            continue

        groups.append(
            {
                "title": group.get("display_title") or group.get("title"),
                "key": group.get("title"),
                "template_count": len(templates),
                "control_count": sum(item["control_count"] for item in templates),
                "templates": templates,
            }
        )

    return groups


def _build_permission_summary(user):
    granted_codes = set()
    if getattr(user, "is_authenticated", False):
        if getattr(user, "is_superuser", False):
            granted_codes = {code for code, _label in EmployeePermission.PERMISSION_CHOICES}
        else:
            employee = getattr(user, "employee_profile", None)
            if employee:
                granted_codes = set(
                    employee.permissions.filter(is_granted=True).values_list("permission", flat=True)
                )

    summaries = []
    for prefix, group_key, title, icon in SITEMAP_PERMISSION_GROUPS:
        items = [
            {"code": code, "label": label}
            for code, label in EmployeePermission.PERMISSION_CHOICES
            if code.startswith(prefix)
        ]
        if not items:
            continue
        granted_count = sum(1 for item in items if item["code"] in granted_codes)
        summaries.append(
            {
                "key": group_key,
                "title": title,
                "icon": icon,
                "total_count": len(items),
                "granted_count": granted_count,
                "items": items,
            }
        )
    return summaries, len(granted_codes)


@login_required
def index(request):
    manuals_context = build_manuals_context()
    user_manual_context = build_user_manual_context(request.user)
    permission_groups, granted_permissions_count = _build_permission_summary(request.user)
    manual_user_screens = _decorate_screens(user_manual_context.get("manual_screens", []))
    template_control_groups = _build_template_control_groups(
        manuals_context.get("manual_template_groups", []),
        user_manual_context.get("manual_user_allowed_group_keys", []),
    )

    context = {}
    context.update(manuals_context)
    context.update(
        {
            "manual_user_allowed_group_keys": user_manual_context.get("manual_user_allowed_group_keys", []),
            "manual_user_departments": user_manual_context.get("manual_user_departments", []),
            "manual_user_screen_total": len(manual_user_screens),
            "manual_user_screens": manual_user_screens,
            "sitemap_permission_groups": permission_groups,
            "sitemap_total_permissions": len(EmployeePermission.PERMISSION_CHOICES),
            "sitemap_granted_permissions_count": granted_permissions_count,
            "sitemap_template_control_groups": template_control_groups,
            "sitemap_template_control_total": sum(group["control_count"] for group in template_control_groups),
        }
    )
    return render(request, "sitemap/index.html", context)
