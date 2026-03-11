from datetime import datetime, time, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.cache import cache
from django.db.models import Count, Sum, Q, F, Value, DecimalField, ExpressionWrapper
from django.db.models.functions import Coalesce, Greatest
from django.utils import timezone

from accounts.models import Account, Course, DiscountRule, Studentenrollment, StudentReceipt, ExpenseEntry, Transaction, JournalEntry
from attendance.models import Attendance, TeacherAttendance
from classroom.models import Classroom
from courses.models import Subject
from employ.models import Employee, EmployeePermission, Teacher
from students.models import Student
from quick.models import QuickCourse, QuickEnrollment, QuickStudent, QuickStudentReceipt

from .models import (
    ActivityLog,
    SystemReport,
    SystemReportActivityAction,
    SystemReportActivitySummary,
    SystemReportAttendanceStats,
    SystemReportClassroomStats,
    SystemReportCounts,
    SystemReportCourseStats,
    SystemReportDiscountPercent,
    SystemReportDiscountSummary,
    SystemReportDiscountRuleUsage,
    SystemReportTopAddress,
    SystemReportTransactionSummary,
    SystemReportUserCourseEnrollment,
    SystemReportUserCourseReceipt,
    SystemReportUserStats,
    UserClickEvent,
)

CACHE_TTL_SECONDS = 60 * 60 * 24
CACHE_VERSION = "v2"
DEFAULT_REPORT_SECTIONS = {
    "counts",
    "activity",
    "attendance",
    "transactions",
    "courses",
    "quick_courses",
    "outstanding_courses",
    "classrooms",
    "quick_students",
    "student_comparison",
    "users",
    "user_operations",
    "user_course_receipts",
    "user_course_quick_receipts",
    "user_course_enrollments",
    "user_course_quick_enrollments",
    "discounts",
    "expense_accounts",
    "top_addresses",
}


def _decimal_to_str(value):
    if value is None:
        return "0"
    try:
        if not isinstance(value, Decimal):
            value = Decimal(str(value).replace(",", "").strip())
        formatted = format(value, ",.2f")
        if "." in formatted:
            formatted = formatted.rstrip("0").rstrip(".")
        return formatted
    except Exception:
        return str(value)


def _sum_decimal(queryset, field):
    value = queryset.aggregate(total=Sum(field))["total"]
    return _decimal_to_str(value)


def _to_decimal(value, max_digits=12, decimal_places=2):
    if value in (None, ""):
        return Decimal("0")
    if isinstance(value, Decimal):
        decimal_value = value
    else:
        try:
            decimal_value = Decimal(str(value).replace(",", "").strip())
        except Exception:
            return Decimal("0")

    quant = Decimal("1").scaleb(-decimal_places)
    try:
        decimal_value = decimal_value.quantize(quant)
    except Exception:
        return Decimal("0")

    max_int_digits = max_digits - decimal_places
    max_str = "9" * max_int_digits
    if decimal_places:
        max_str = f"{max_str}.{'9' * decimal_places}"
    max_value = Decimal(max_str)
    if decimal_value.copy_abs() > max_value:
        return -max_value if decimal_value < 0 else max_value
    return decimal_value


def _format_duration(total_seconds):
    if not total_seconds:
        return "0 س 0 د"
    minutes = int(total_seconds // 60)
    hours = minutes // 60
    minutes = minutes % 60
    return f"{hours} س {minutes} د"


def _build_discount_rule_maps():
    rule_map = {}
    rule_description_map = {}
    for rule in DiscountRule.objects.filter(is_active=True):
        key = (rule.discount_percent or Decimal("0"), rule.discount_amount or Decimal("0"))
        rule_map[key] = (rule.reason_ar or rule.reason or "").strip()
        rule_description_map[key] = (rule.description or "").strip()
    return rule_map, rule_description_map


def _normalize_student_identity(name, phone):
    name_value = (name or "").strip()
    phone_value = (phone or "").strip()
    if not name_value or not phone_value or phone_value == "0":
        return None
    return (name_value, phone_value)


def _build_user_permissions_map():
    perms = (
        EmployeePermission.objects.filter(is_granted=True)
        .select_related("employee", "employee__user")
    )
    label_map = dict(EmployeePermission.PERMISSION_CHOICES)
    user_map = {}
    for perm in perms:
        user_id = perm.employee.user_id
        if not user_id:
            continue
        user_map.setdefault(user_id, []).append(label_map.get(perm.permission, perm.permission))
    return user_map


def _build_period_datetimes(period_start, period_end):
    tz = timezone.get_current_timezone()
    start_dt = timezone.make_aware(datetime.combine(period_start, time.min), tz)
    end_dt = timezone.make_aware(datetime.combine(period_end + timedelta(days=1), time.min), tz)
    return start_dt, end_dt


def _build_user_active_time_map(activity_qs, end_dt):
    logs = (
        activity_qs.filter(action__in=["login", "logout"], user__isnull=False)
        .values("user_id", "action", "timestamp")
        .order_by("user_id", "timestamp")
    )
    active_map = {}
    open_sessions = {}
    for row in logs:
        user_id = row["user_id"]
        action = row["action"]
        ts = row["timestamp"]
        if action == "login":
            open_sessions[user_id] = ts
        elif action == "logout":
            login_ts = open_sessions.pop(user_id, None)
            if login_ts:
                delta = (ts - login_ts).total_seconds()
                if delta > 0:
                    active_map[user_id] = active_map.get(user_id, 0) + int(delta)
    for user_id, login_ts in open_sessions.items():
        delta = (end_dt - login_ts).total_seconds()
        if delta > 0:
            active_map[user_id] = active_map.get(user_id, 0) + int(delta)
    return active_map


def _normalize_sections(sections):
    if not sections:
        return set(DEFAULT_REPORT_SECTIONS)
    if isinstance(sections, str):
        sections = [value.strip() for value in sections.split(",") if value.strip()]
    return set(sections) or set(DEFAULT_REPORT_SECTIONS)


def _get_report_cache_key(period_start, period_end, course_id, user_id, report_scope, sections):
    sections_key = ",".join(sorted(sections))
    return (
        f"system_report:{CACHE_VERSION}:"
        f"{period_start.isoformat()}:{period_end.isoformat()}:"
        f"{course_id or 'all'}:{user_id or 'all'}:{report_scope or 'all'}:{sections_key}"
    )


def _build_counts_snapshot(start_dt, end_dt):
    start_date = start_dt.date()
    end_date = end_dt.date()
    user_counts = User.objects.aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(is_active=True)),
        staff=Count("id", filter=Q(is_staff=True)),
        superusers=Count("id", filter=Q(is_superuser=True)),
        logged_in=Count("id", filter=Q(last_login__gte=start_dt, last_login__lt=end_dt)),
    )
    return {
        "students_total": Student.objects.count(),
        "students_period": Student.objects.filter(
            registration_date__gte=start_date,
            registration_date__lte=end_date,
        ).count(),
        "students_active": Student.objects.filter(is_active=True).count(),
        "quick_students_total": QuickStudent.objects.count(),
        "quick_students_period": QuickStudent.objects.filter(
            created_at__date__gte=start_date,
            created_at__date__lte=end_date,
        ).count(),
        "teachers_total": Teacher.objects.count(),
        "employees_total": Employee.objects.count(),
        "users_total": user_counts["total"] or 0,
        "users_new_period": User.objects.filter(
            date_joined__gte=start_dt,
            date_joined__lt=end_dt,
        ).count(),
        "users_active": user_counts["active"] or 0,
        "users_staff": user_counts["staff"] or 0,
        "users_superusers": user_counts["superusers"] or 0,
        "users_logged_in": user_counts["logged_in"] or 0,
        "classrooms_total": Classroom.objects.count(),
        "subjects_total": Subject.objects.count(),
        "courses_total": Course.objects.count(),
        "courses_period": Course.objects.filter(
            created_at__date__gte=start_date,
            created_at__date__lte=end_date,
        ).count(),
        "quick_courses_total": QuickCourse.objects.count(),
        "quick_courses_period": QuickCourse.objects.filter(
            created_at__date__gte=start_date,
            created_at__date__lte=end_date,
        ).count(),
    }


def _build_activity_section(activity_qs, selected_sections):
    total = activity_qs.count()
    by_action = {}
    if "activity" in selected_sections:
        by_action = {
            row["action"]: row["count"]
            for row in activity_qs.values("action").annotate(count=Count("id"))
        }
    return {
        "total": total,
        "by_action": by_action,
    }


def _build_attendance_section(period_start, period_end):
    return {
        "students_records": Attendance.objects.filter(
            date__gte=period_start,
            date__lte=period_end,
        ).count(),
        "teachers_records": TeacherAttendance.objects.filter(
            date__gte=period_start,
            date__lte=period_end,
        ).count(),
    }


def _build_transactions_section(start_dt, end_dt):
    summary = Transaction.objects.filter(
        created_at__gte=start_dt,
        created_at__lt=end_dt,
    ).aggregate(
        count=Count("id"),
        debit_total=Sum("amount", filter=Q(is_debit=True)),
        credit_total=Sum("amount", filter=Q(is_debit=False)),
    )
    return {
        "count": summary.get("count") or 0,
        "debit_total": _decimal_to_str(summary.get("debit_total")),
        "credit_total": _decimal_to_str(summary.get("credit_total")),
    }


def _build_course_account_map(include_regular, include_quick):
    course_account_map = {}
    if include_quick or include_regular:
        for account in Account.objects.filter(is_course_account=True, is_active=True):
            label = (account.course_name or "").strip()
            if not label:
                continue
            course_account_map[label.lower()] = account.rollup_balance
    return course_account_map


def _build_course_stats(
    courses_qs,
    period_start,
    period_end,
    enrollments_relation,
    receipts_relation,
):
    net_expr = ExpressionWrapper(
        F(f"{enrollments_relation}__total_amount")
        - (F(f"{enrollments_relation}__total_amount") * F(f"{enrollments_relation}__discount_percent") / Value(Decimal("100")))
        - F(f"{enrollments_relation}__discount_amount"),
        output_field=DecimalField(max_digits=12, decimal_places=2),
    )
    return courses_qs.annotate(
        enrollments_count=Count(
            enrollments_relation,
            filter=Q(
                **{
                    f"{enrollments_relation}__enrollment_date__gte": period_start,
                    f"{enrollments_relation}__enrollment_date__lte": period_end,
                }
            ),
            distinct=True,
        ),
        receipts_count=Count(
            receipts_relation,
            filter=Q(
                **{
                    f"{receipts_relation}__date__gte": period_start,
                    f"{receipts_relation}__date__lte": period_end,
                }
            ),
            distinct=True,
        ),
        receipts_amount=Sum(
            f"{receipts_relation}__paid_amount",
            filter=Q(
                **{
                    f"{receipts_relation}__date__gte": period_start,
                    f"{receipts_relation}__date__lte": period_end,
                }
            ),
        ),
        expected_amount=Sum(
            Greatest(net_expr, Value(0, output_field=DecimalField(max_digits=12, decimal_places=2))),
            filter=Q(
                **{
                    f"{enrollments_relation}__enrollment_date__gte": period_start,
                    f"{enrollments_relation}__enrollment_date__lte": period_end,
                }
            ),
        ),
    ).order_by("name")


def _build_discounts_section(regular_receipts, quick_receipts, regular_enrollments, quick_enrollments):
    student_receipts_discounted = regular_receipts.filter(
        Q(discount_percent__gt=0) | Q(discount_amount__gt=0)
    )
    quick_receipts_discounted = quick_receipts.filter(
        Q(discount_percent__gt=0) | Q(discount_amount__gt=0)
    )
    enrollments_discounted = regular_enrollments.filter(
        Q(discount_percent__gt=0) | Q(discount_amount__gt=0)
    )
    quick_enrollments_discounted = quick_enrollments.filter(
        Q(discount_percent__gt=0) | Q(discount_amount__gt=0)
    )

    discounts_summary = {
        "student_receipts_count": student_receipts_discounted.count(),
        "student_receipts_discount_amount": _sum_decimal(student_receipts_discounted, "discount_amount"),
        "student_receipts_discount_percent_count": student_receipts_discounted.filter(discount_percent__gt=0).count(),
        "quick_receipts_count": quick_receipts_discounted.count(),
        "quick_receipts_discount_amount": _sum_decimal(quick_receipts_discounted, "discount_amount"),
        "quick_receipts_discount_percent_count": quick_receipts_discounted.filter(discount_percent__gt=0).count(),
        "enrollments_count": enrollments_discounted.count(),
        "enrollments_discount_amount": _sum_decimal(enrollments_discounted, "discount_amount"),
        "enrollments_discount_percent_count": enrollments_discounted.filter(discount_percent__gt=0).count(),
        "quick_enrollments_count": quick_enrollments_discounted.count(),
        "quick_enrollments_discount_amount": _sum_decimal(quick_enrollments_discounted, "discount_amount"),
        "quick_enrollments_discount_percent_count": quick_enrollments_discounted.filter(discount_percent__gt=0).count(),
    }

    rule_map, rule_description_map = _build_discount_rule_maps()

    rule_usage = {}

    def _accumulate_rule_usage(queryset, base_amount_expr, source_label):
        discount_value_expr = ExpressionWrapper(
            (base_amount_expr * F("discount_percent") / Value(Decimal("100"))) + F("discount_amount"),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        )
        for row in queryset.annotate(discount_value=discount_value_expr).values(
            "discount_percent", "discount_amount"
        ).annotate(
            count=Count("id"),
            total=Sum("discount_value"),
        ):
            percent = row["discount_percent"] or Decimal("0")
            amount = row["discount_amount"] or Decimal("0")
            key = (percent, amount)
            payload = rule_usage.setdefault(key, {"count": 0, "total": Decimal("0"), "sources": set()})
            payload["count"] += row["count"]
            payload["total"] += row["total"] or Decimal("0")
            payload["sources"].add(source_label)

    _accumulate_rule_usage(
        student_receipts_discounted,
        Coalesce("amount", "paid_amount", Value(Decimal("0"))),
        "student_receipt",
    )
    _accumulate_rule_usage(
        quick_receipts_discounted,
        Coalesce("amount", "paid_amount", Value(Decimal("0"))),
        "quick_receipt",
    )
    _accumulate_rule_usage(
        enrollments_discounted,
        Coalesce("total_amount", Value(Decimal("0"))),
        "enrollment",
    )
    _accumulate_rule_usage(
        quick_enrollments_discounted,
        Coalesce("total_amount", Value(Decimal("0"))),
        "quick_enrollment",
    )

    source_labels = {
        "student_receipt": "\u0625\u064a\u0635\u0627\u0644\u0627\u062a \u0646\u0638\u0627\u0645\u064a\u0629",
        "quick_receipt": "\u0625\u064a\u0635\u0627\u0644\u0627\u062a \u0633\u0631\u064a\u0639\u0629",
        "enrollment": "\u062a\u0633\u062c\u064a\u0644\u0627\u062a \u0646\u0638\u0627\u0645\u064a\u0629",
        "quick_enrollment": "\u062a\u0633\u062c\u064a\u0644\u0627\u062a \u0633\u0631\u064a\u0639\u0629",
    }

    discounts_by_rule = []
    for (percent, amount), payload in sorted(
        rule_usage.items(), key=lambda item: item[1]["count"], reverse=True
    ):
        rule_name = rule_map.get((percent, amount)) or rule_description_map.get((percent, amount)) or ""
        rule_description = rule_description_map.get((percent, amount)) or ""
        if not rule_name:
            if percent and amount:
                rule_name = f"\u062e\u0635\u0645 {percent}% + {_decimal_to_str(amount)}"
            elif percent:
                rule_name = f"\u062e\u0635\u0645 \u0628\u0646\u0633\u0628\u0629 {percent}%"
            elif amount:
                rule_name = f"\u062e\u0635\u0645 \u0628\u0645\u0628\u0644\u063a {_decimal_to_str(amount)}"
            else:
                rule_name = "\u062e\u0635\u0645 \u063a\u064a\u0631 \u0645\u0633\u0645\u0649"
        if percent and amount:
            type_label = "\u0646\u0633\u0628\u0629 + \u0645\u0628\u0644\u063a"
        elif percent:
            type_label = "\u0646\u0633\u0628\u0629"
        elif amount:
            type_label = "\u0645\u0628\u0644\u063a"
        else:
            type_label = "\u063a\u064a\u0631 \u0645\u062a\u0648\u0641\u0631"
        discounts_by_rule.append({
            "rule_name": rule_name,
            "rule_description": rule_description,
            "percent": str(percent),
            "amount": _decimal_to_str(amount),
            "count": payload["count"],
            "total_value": _decimal_to_str(payload["total"]),
            "type_label": type_label,
            "sources": ", ".join(sorted(source_labels.get(label, label) for label in payload["sources"])),
        })

    discounts_by_percent = []
    for row in student_receipts_discounted.exclude(discount_percent=0).values("discount_percent").annotate(
        count=Count("id")
    ).order_by("-count", "-discount_percent"):
        discounts_by_percent.append({
            "source": "student_receipt",
            "percent": str(row["discount_percent"]),
            "count": row["count"],
        })
    for row in quick_receipts_discounted.exclude(discount_percent=0).values("discount_percent").annotate(
        count=Count("id")
    ).order_by("-count", "-discount_percent"):
        discounts_by_percent.append({
            "source": "quick_receipt",
            "percent": str(row["discount_percent"]),
            "count": row["count"],
        })
    for row in enrollments_discounted.exclude(discount_percent=0).values("discount_percent").annotate(
        count=Count("id")
    ).order_by("-count", "-discount_percent"):
        discounts_by_percent.append({
            "source": "enrollment",
            "percent": str(row["discount_percent"]),
            "count": row["count"],
        })
    for row in quick_enrollments_discounted.exclude(discount_percent=0).values("discount_percent").annotate(
        count=Count("id")
    ).order_by("-count", "-discount_percent"):
        discounts_by_percent.append({
            "source": "quick_enrollment",
            "percent": str(row["discount_percent"]),
            "count": row["count"],
        })

    return discounts_summary, discounts_by_percent, discounts_by_rule


def _build_regular_outstanding_courses():
    """Match the outstanding courses report logic for regular enrollments."""
    courses = list(Course.objects.filter(is_active=True).order_by("name"))
    if not courses:
        return [], {
            "total_courses": 0,
            "total_students": 0,
            "total_fully_paid": 0,
            "total_not_fully_paid": 0,
            "total_net_due": _decimal_to_str(Decimal("0")),
            "total_paid": _decimal_to_str(Decimal("0")),
            "total_outstanding": _decimal_to_str(Decimal("0")),
        }

    enrollments = list(
        Studentenrollment.objects.filter(course__in=courses, is_completed=False)
        .select_related("course", "student")
    )
    student_ids = {enrollment.student_id for enrollment in enrollments if enrollment.student_id}
    receipt_totals = {
        (row["student_profile_id"], row["course_id"]): row["total"] or Decimal("0")
        for row in StudentReceipt.objects.filter(
            course__in=courses,
            student_profile_id__in=student_ids,
        ).values("student_profile_id", "course_id").annotate(total=Sum("paid_amount"))
    }

    course_map = {}
    for course in courses:
        course_map[course.id] = {
            "course_id": course.id,
            "course_name": course.name_ar or course.name,
            "students_count": 0,
            "fully_paid": 0,
            "not_fully_paid": 0,
            "net_due_total": Decimal("0"),
            "paid_total": Decimal("0"),
            "outstanding_total": Decimal("0"),
        }

    for enrollment in enrollments:
        course_row = course_map.get(enrollment.course_id)
        if not course_row:
            continue
        course_price = enrollment.course.price if enrollment.course and enrollment.course.price is not None else Decimal("0")
        discount_percent = enrollment.discount_percent or Decimal("0")
        discount_amount = enrollment.discount_amount or Decimal("0")
        if discount_percent > 0:
            discount_value = course_price * (discount_percent / Decimal("100"))
            net_due = course_price - discount_value - discount_amount
        else:
            net_due = course_price - discount_amount
        net_due = max(Decimal("0"), net_due)
        paid_total = receipt_totals.get((enrollment.student_id, enrollment.course_id), Decimal("0"))
        remaining = max(Decimal("0"), net_due - paid_total)

        course_row["students_count"] += 1
        course_row["net_due_total"] += net_due
        course_row["paid_total"] += paid_total
        if remaining > 0:
            course_row["not_fully_paid"] += 1
            course_row["outstanding_total"] += remaining
        else:
            course_row["fully_paid"] += 1

    rows = []
    totals = {
        "total_courses": len(courses),
        "total_students": 0,
        "total_fully_paid": 0,
        "total_not_fully_paid": 0,
        "total_net_due": Decimal("0"),
        "total_paid": Decimal("0"),
        "total_outstanding": Decimal("0"),
    }

    for course in courses:
        row = course_map.get(course.id)
        if not row:
            continue
        totals["total_students"] += row["students_count"]
        totals["total_fully_paid"] += row["fully_paid"]
        totals["total_not_fully_paid"] += row["not_fully_paid"]
        totals["total_net_due"] += row["net_due_total"]
        totals["total_paid"] += row["paid_total"]
        totals["total_outstanding"] += row["outstanding_total"]
        rows.append({
            "course_id": row["course_id"],
            "course_name": row["course_name"],
            "students_count": row["students_count"],
            "fully_paid": row["fully_paid"],
            "not_fully_paid": row["not_fully_paid"],
            "net_due_total": _decimal_to_str(row["net_due_total"]),
            "paid_total": _decimal_to_str(row["paid_total"]),
            "outstanding_total": _decimal_to_str(row["outstanding_total"]),
        })

    totals_formatted = {
        "total_courses": totals["total_courses"],
        "total_students": totals["total_students"],
        "total_fully_paid": totals["total_fully_paid"],
        "total_not_fully_paid": totals["total_not_fully_paid"],
        "total_net_due": _decimal_to_str(totals["total_net_due"]),
        "total_paid": _decimal_to_str(totals["total_paid"]),
        "total_outstanding": _decimal_to_str(totals["total_outstanding"]),
    }

    return rows, totals_formatted


def _build_user_journal_maps(start_dt, end_dt):
    """Aggregate refund/withdraw operations per user."""
    refund_qs = Transaction.objects.filter(
        created_at__gte=start_dt,
        created_at__lt=end_dt,
        is_debit=True,
    ).filter(
        Q(description__icontains="\u0627\u0633\u062a\u0631\u062f\u0627\u062f") | Q(description__icontains="refund")
    )
    withdrawal_qs = JournalEntry.objects.filter(
        created_at__gte=start_dt,
        created_at__lt=end_dt,
    ).filter(
        Q(description__icontains="\u0633\u062d\u0628")
        | Q(description__icontains="\u0625\u0644\u063a\u0627\u0621 \u062a\u0633\u062c\u064a\u0644")
        | Q(description__icontains="withdraw")
    )
    refund_map = {
        row["journal_entry__created_by_id"]: row
        for row in refund_qs.values("journal_entry__created_by_id").annotate(
            count=Count("id"),
            amount=Sum("amount"),
        )
    }
    withdrawal_map = {
        row["created_by_id"]: row
        for row in withdrawal_qs.values("created_by_id").annotate(
            count=Count("id"),
            amount=Sum("total_amount"),
        )
    }
    return refund_map, withdrawal_map


def _build_expense_accounts_top(period_start, period_end):
    """Return top expense accounts under code 5 (excluding salary-related accounts)."""
    exclude_filters = (
        Q(account__code__startswith="501")
        | Q(account__name__icontains="salary")
        | Q(account__name__icontains="wage")
        | Q(account__name_ar__icontains="\u0631\u0627\u062a\u0628")
        | Q(account__name_ar__icontains="\u0631\u0648\u0627\u062a\u0628")
        | Q(account__name_ar__icontains="\u0623\u062c\u0648\u0631")
    )
    expense_rows = ExpenseEntry.objects.filter(
        date__gte=period_start,
        date__lte=period_end,
        account__code__startswith="5",
        account__is_active=True,
    ).exclude(
        exclude_filters
    ).values(
        "account_id",
        "account__code",
        "account__name",
        "account__name_ar",
    ).annotate(
        total=Sum("amount"),
        count=Count("id"),
    ).order_by("-total", "account__code")
    top_accounts = []
    for row in expense_rows[:5]:
        account_name = row["account__name_ar"] or row["account__name"]
        top_accounts.append({
            "code": row["account__code"],
            "name": account_name,
            "balance": _decimal_to_str(row["total"]),
            "count": row["count"],
        })
    top_account = top_accounts[0] if top_accounts else None
    return top_accounts, top_account


def build_system_report_summary(
    period_start,
    period_end,
    course_id=None,
    user_id=None,
    report_scope=None,
    sections=None,
    use_cache=True,
):
    start_dt, end_dt = _build_period_datetimes(period_start, period_end)
    selected_sections = _normalize_sections(sections)
    cache_key = _get_report_cache_key(period_start, period_end, course_id, user_id, report_scope, selected_sections)
    if use_cache:
        cached = cache.get(cache_key)
        if cached:
            return cached

    counts_snapshot = _build_counts_snapshot(start_dt, end_dt)
    activity_qs = ActivityLog.objects.filter(timestamp__gte=start_dt, timestamp__lt=end_dt)
    if user_id:
        activity_qs = activity_qs.filter(user_id=user_id)
    clicks_qs = UserClickEvent.objects.filter(
        timestamp__gte=start_dt,
        timestamp__lt=end_dt,
        is_trusted=True,
    )
    if user_id:
        clicks_qs = clicks_qs.filter(user_id=user_id)
    activity_section = _build_activity_section(activity_qs, selected_sections)
    attendance_section = _build_attendance_section(period_start, period_end)
    transactions_section = _build_transactions_section(start_dt, end_dt)

    include_regular = report_scope in (None, "", "all", "regular")
    include_quick = report_scope in (None, "", "all", "quick")

    course_account_map = _build_course_account_map(include_regular, include_quick)
    needs_user_stats = True
    needs_regular_enrollments = include_regular and (
        needs_user_stats or {"courses", "discounts", "user_course_enrollments"} & selected_sections
    )
    needs_regular_receipts = include_regular and (
        needs_user_stats or {"courses", "discounts", "user_course_receipts"} & selected_sections
    )
    needs_quick_enrollments = include_quick and (
        needs_user_stats or {"quick_courses", "discounts", "user_course_quick_enrollments"} & selected_sections
    )
    needs_quick_receipts = include_quick and (
        needs_user_stats or {"quick_courses", "discounts", "user_course_quick_receipts"} & selected_sections
    )

    regular_enrollments = Studentenrollment.objects.none()
    regular_receipts = StudentReceipt.objects.none()
    course_stats = []
    if needs_regular_enrollments:
        regular_enrollments = Studentenrollment.objects.filter(
            enrollment_date__gte=period_start,
            enrollment_date__lte=period_end,
        ).select_related("course")
    if needs_regular_receipts:
        regular_receipts = StudentReceipt.objects.filter(
            date__gte=period_start,
            date__lte=period_end,
        ).select_related("course", "created_by")
    if include_regular and "courses" in selected_sections:
        total_enrollment_map = {
            row["course_id"]: row["count"]
            for row in Studentenrollment.objects.values("course_id").annotate(count=Count("id"))
        }
        courses_qs = Course.objects.all()
        if course_id:
            courses_qs = courses_qs.filter(id=course_id)
        courses_qs = _build_course_stats(
            courses_qs,
            period_start,
            period_end,
            enrollments_relation="enrollments",
            receipts_relation="receipts",
        )
        course_stats = [
            {
                "course_id": course.id,
                "course_name": course.name_ar or course.name,
                "enrollments_count": course.enrollments_count or 0,
                "enrollments_total": total_enrollment_map.get(course.id, 0),
                "receipts_count": course.receipts_count or 0,
                "receipts_amount": _decimal_to_str(course.receipts_amount),
                "expected_amount": _decimal_to_str(course.expected_amount),
                "received_amount": _decimal_to_str(course.receipts_amount),
                "remaining_amount": _decimal_to_str(
                    max(Decimal("0"), _to_decimal(course.expected_amount) - _to_decimal(course.receipts_amount))
                ),
                "account_balance": _decimal_to_str(
                    course_account_map.get((course.name_ar or course.name).strip().lower(), Decimal("0"))
                ),
            }
            for course in courses_qs
        ]

    quick_enrollments = QuickEnrollment.objects.none()
    quick_receipts = QuickStudentReceipt.objects.none()
    quick_course_stats = []
    if needs_quick_enrollments:
        quick_enrollments = QuickEnrollment.objects.filter(
            enrollment_date__gte=period_start,
            enrollment_date__lte=period_end,
        ).select_related("course")
    if needs_quick_receipts:
        quick_receipts = QuickStudentReceipt.objects.filter(
            date__gte=period_start,
            date__lte=period_end,
        ).select_related("course", "created_by")
    quick_enrollment_discount_counts = {}
    quick_receipt_discount_counts = {}
    if include_quick and needs_quick_enrollments:   
        quick_enrollment_discount_counts = {
            row["course_id"]: row["count"]
            for row in quick_enrollments.filter(
                Q(discount_percent__gt=0) | Q(discount_amount__gt=0)
            ).values("course_id").annotate(count=Count("id"))
        }
    if include_quick and needs_quick_receipts:
        quick_receipt_discount_counts = {
            row["course_id"]: row["count"]
            for row in quick_receipts.filter(
                Q(discount_percent__gt=0) | Q(discount_amount__gt=0)
            ).values("course_id").annotate(count=Count("id"))
        }
    if include_quick and "quick_courses" in selected_sections:
        quick_total_enrollment_map = {
            row["course_id"]: row["count"]
            for row in QuickEnrollment.objects.values("course_id").annotate(count=Count("id"))
        }
        quick_courses_qs = QuickCourse.objects.all()
        if course_id and report_scope == "quick":
            quick_courses_qs = quick_courses_qs.filter(id=course_id)
        quick_courses_qs = _build_course_stats(
            quick_courses_qs,
            period_start,
            period_end,
            enrollments_relation="enrollments",
            receipts_relation="quickstudentreceipt",
        )
        quick_course_stats = []
        for course in quick_courses_qs:
            total_discounts = (
                quick_enrollment_discount_counts.get(course.id, 0)
                + quick_receipt_discount_counts.get(course.id, 0)
            )
            quick_course_stats.append({
                "course_id": course.id,
                "course_name": course.name_ar or course.name,
                "course_type": course.course_type,
                "course_type_label": (
                    course.get_course_type_display()
                    if hasattr(course, "get_course_type_display")
                    else course.course_type
                ),
                "enrollments_count": course.enrollments_count or 0,
                "enrollments_total": quick_total_enrollment_map.get(course.id, 0),
                "receipts_count": course.receipts_count or 0,
                "receipts_amount": _decimal_to_str(course.receipts_amount),
                "expected_amount": _decimal_to_str(course.expected_amount),
                "received_amount": _decimal_to_str(course.receipts_amount),
                "remaining_amount": _decimal_to_str(
                    max(Decimal("0"), _to_decimal(course.expected_amount) - _to_decimal(course.receipts_amount))
                ),
                "account_balance": _decimal_to_str(
                    course_account_map.get((course.name_ar or course.name).strip().lower(), Decimal("0"))
                ),
                "discounted_enrollments_count": quick_enrollment_discount_counts.get(course.id, 0),
                "discounted_receipts_count": quick_receipt_discount_counts.get(course.id, 0),
                "discount_note": (
                    f"\u062e\u0635\u0648\u0645\u0627\u062a: {quick_enrollment_discount_counts.get(course.id, 0)} \u062a\u0633\u062c\u064a\u0644\u060c "
                    f"{quick_receipt_discount_counts.get(course.id, 0)} \u0625\u064a\u0635\u0627\u0644"
                    if total_discounts > 0
                    else ""
                ),
            })
        quick_course_stats.sort(
            key=lambda item: _to_decimal(item.get("account_balance")),
            reverse=True,
        )

    quick_course_discounts = []
    if include_quick and "quick_courses" in selected_sections:
        quick_course_remaining_map = {
            item["course_id"]: item.get("remaining_amount") for item in quick_course_stats
        }
        rule_map, rule_description_map = _build_discount_rule_maps()

        def _resolve_discount_meta(percent_value, amount_value):
            key = (percent_value or Decimal("0"), amount_value or Decimal("0"))
            rule_name = rule_map.get(key) or rule_description_map.get(key) or ""
            rule_reason = rule_description_map.get(key) or ""
            if not rule_name:
                if percent_value and amount_value:
                    rule_name = f"\u062e\u0635\u0645 {percent_value}% + {_decimal_to_str(amount_value)}"
                elif percent_value:
                    rule_name = f"\u062e\u0635\u0645 \u0628\u0646\u0633\u0628\u0629 {percent_value}%"
                elif amount_value:
                    rule_name = f"\u062e\u0635\u0645 \u0628\u0645\u0628\u0644\u063a {_decimal_to_str(amount_value)}"
                else:
                    rule_name = "\u063a\u064a\u0631 \u0645\u062a\u0648\u0641\u0631"
            if not rule_reason:
                rule_reason = "\u063a\u064a\u0631 \u0645\u062a\u0648\u0641\u0631"
            return rule_name, rule_reason

        for enrollment in quick_enrollments.filter(
            Q(discount_percent__gt=0) | Q(discount_amount__gt=0)
        ).select_related("course", "student"):
            course_obj = enrollment.course
            course_name = course_obj.name_ar or course_obj.name if course_obj else "\u063a\u064a\u0631 \u0645\u062a\u0648\u0641\u0631"
            course_id_value = enrollment.course_id
            student_obj = enrollment.student
            student_name = (
                getattr(student_obj, "full_name", None)
                or getattr(student_obj, "name", None)
                or "\u063a\u064a\u0631 \u0645\u062a\u0648\u0641\u0631"
            )
            percent_value = enrollment.discount_percent or Decimal("0")
            amount_value = enrollment.discount_amount or Decimal("0")
            rule_name, rule_reason = _resolve_discount_meta(percent_value, amount_value)
            quick_course_discounts.append({
                "course_id": course_id_value,
                "course_name": course_name or "\u063a\u064a\u0631 \u0645\u062a\u0648\u0641\u0631",
                "student_name": student_name,
                "discount_name": rule_name,
                "discount_reason": rule_reason,
                "discount_percent": str(percent_value),
                "discount_amount": _decimal_to_str(amount_value),
                "source": "\u062a\u0633\u062c\u064a\u0644",
                "course_remaining_amount": quick_course_remaining_map.get(course_id_value) or "\u063a\u064a\u0631 \u0645\u062a\u0648\u0641\u0631",
            })

        for receipt in quick_receipts.filter(
            Q(discount_percent__gt=0) | Q(discount_amount__gt=0)
        ).select_related("course", "quick_student"):
            course_obj = receipt.course
            course_name = course_obj.name_ar or course_obj.name if course_obj else receipt.course_name
            course_id_value = receipt.course_id
            student_obj = receipt.quick_student
            student_name = (
                getattr(student_obj, "full_name", None)
                or getattr(student_obj, "name", None)
                or receipt.student_name
                or "\u063a\u064a\u0631 \u0645\u062a\u0648\u0641\u0631"
            )
            percent_value = receipt.discount_percent or Decimal("0")
            amount_value = receipt.discount_amount or Decimal("0")
            rule_name, rule_reason = _resolve_discount_meta(percent_value, amount_value)
            quick_course_discounts.append({
                "course_id": course_id_value,
                "course_name": course_name or "\u063a\u064a\u0631 \u0645\u062a\u0648\u0641\u0631",
                "student_name": student_name,
                "discount_name": rule_name,
                "discount_reason": rule_reason,
                "discount_percent": str(percent_value),
                "discount_amount": _decimal_to_str(amount_value),
                "source": "\u0625\u064a\u0635\u0627\u0644",
                "course_remaining_amount": quick_course_remaining_map.get(course_id_value) or "\u063a\u064a\u0631 \u0645\u062a\u0648\u0641\u0631",
            })

    intensive_quick_courses = [
        item for item in quick_course_stats if item["course_type"] == "INTENSIVE"
    ]
    intensive_quick_courses.sort(key=lambda item: item["enrollments_count"], reverse=True)

    classroom_stats = []
    if "classrooms" in selected_sections:
        classroom_qs = Classroom.objects.annotate(
            students_total=Count("enrollments", distinct=True),
            students_in_period=Count(
                "enrollments",
                filter=Q(
                    enrollments__enrolled_at__date__gte=period_start,
                    enrollments__enrolled_at__date__lte=period_end,
                ),
                distinct=True,
            ),
        ).order_by("name")
        classroom_stats = [
            {
                "classroom_id": classroom.id,
                "classroom_name": str(classroom),
                "students_total": classroom.students_total or 0,
                "students_in_period": classroom.students_in_period or 0,
            }
            for classroom in classroom_qs
        ]

    quick_students_period = QuickStudent.objects.filter(
        created_at__gte=start_dt,
        created_at__lt=end_dt,
    ).count() if "quick_students" in selected_sections else 0

    discounts_summary = {}
    discounts_by_percent = []
    discounts_by_rule = []
    if "discounts" in selected_sections:
        discounts_summary, discounts_by_percent, discounts_by_rule = _build_discounts_section(
            regular_receipts,
            quick_receipts,
            regular_enrollments,
            quick_enrollments,
        )

    regular_outstanding_courses = []
    regular_outstanding_totals = {}
    if include_regular and "outstanding_courses" in selected_sections:
        regular_outstanding_courses, regular_outstanding_totals = _build_regular_outstanding_courses()

    student_comparison = {}
    if "student_comparison" in selected_sections:
        quick_students_qs = QuickStudent.objects.all()
        quick_students_total = quick_students_qs.count()
        quick_students_period_qs = QuickStudent.objects.filter(
            created_at__date__gte=period_start,
            created_at__date__lte=period_end,
        )
        quick_students_period = quick_students_period_qs.count()
        regular_students_qs = Student.objects.exclude(quick_student_profile__isnull=False)
        regular_students_total = regular_students_qs.count()
        regular_students_period_qs = Student.objects.exclude(
            quick_student_profile__isnull=False
        ).filter(
            registration_date__gte=period_start,
            registration_date__lte=period_end,
        )
        regular_students_period = regular_students_period_qs.count()
        institute_identities = {
            identity
            for identity in (
                _normalize_student_identity(row["full_name"], row["phone"])
                for row in regular_students_qs.values("full_name", "phone")
            )
            if identity
        }
        external_regular_count = sum(
            1
            for row in regular_students_qs.values("full_name", "phone")
            if not _normalize_student_identity(row["full_name"], row["phone"])
        )
        external_regular_period_count = sum(
            1
            for row in regular_students_period_qs.values("full_name", "phone")
            if not _normalize_student_identity(row["full_name"], row["phone"])
        )
        external_quick_count = sum(
            1
            for row in quick_students_qs.values("full_name", "phone")
            if not _normalize_student_identity(row["full_name"], row["phone"])
            or _normalize_student_identity(row["full_name"], row["phone"]) not in institute_identities
        )
        external_quick_period_count = sum(
            1
            for row in quick_students_period_qs.values("full_name", "phone")
            if not _normalize_student_identity(row["full_name"], row["phone"])
            or _normalize_student_identity(row["full_name"], row["phone"]) not in institute_identities
        )
        external_pct = Decimal("0")
        if regular_students_total:
            external_pct = (Decimal(external_regular_count) / Decimal(regular_students_total)) * Decimal("100")
        external_quick_pct = Decimal("0")
        if quick_students_total:
            external_quick_pct = (Decimal(external_quick_count) / Decimal(quick_students_total)) * Decimal("100")
        external_total_count = external_regular_count + external_quick_count
        external_total_period_count = external_regular_period_count + external_quick_period_count
        overall_total = regular_students_total + quick_students_total
        external_total_pct = Decimal("0")
        if overall_total:
            external_total_pct = (Decimal(external_total_count) / Decimal(overall_total)) * Decimal("100")
        student_comparison = {
            "regular_students_total": regular_students_total,
            "quick_students_total": quick_students_total,
            "regular_students_period": regular_students_period,
            "quick_students_period": quick_students_period,
            "external_regular_count": external_regular_count,
            "external_regular_percent": _decimal_to_str(external_pct),
            "external_regular_period_count": external_regular_period_count,
            "external_quick_count": external_quick_count,
            "external_quick_percent": _decimal_to_str(external_quick_pct),
            "external_quick_period_count": external_quick_period_count,
            "external_total_count": external_total_count,
            "external_total_percent": _decimal_to_str(external_total_pct),
            "external_total_period_count": external_total_period_count,
        }

    expense_accounts_top = []
    expense_top_account = None
    expenses_summary = {}
    if "expense_accounts" in selected_sections:
        expense_accounts_top, expense_top_account = _build_expense_accounts_top(period_start, period_end)
        expenses_summary = {
            "total_count": ExpenseEntry.objects.filter(
                date__gte=period_start,
                date__lte=period_end,
            ).count(),
            "total_amount": _sum_decimal(
                ExpenseEntry.objects.filter(
                    date__gte=period_start,
                    date__lte=period_end,
                ),
                "amount",
            ),
        }

    address_stats = []
    if "top_addresses" in selected_sections:
        address_qs = Student.objects.exclude(address__isnull=True).exclude(address__exact="").values("address").annotate(
            count=Count("id")
        ).order_by("-count", "address")
        for row in address_qs[:15]:
            address_stats.append({
                "address": row["address"],
                "count": row["count"],
            })

    # Pre-aggregate per-user metrics to avoid per-user queries.
    permissions_map = _build_user_permissions_map()
    users = User.objects.filter(is_superuser=False).exclude(username__iexact="thaaer")
    if user_id:
        users = users.filter(id=user_id)
    user_map = {user.id: user for user in users}
    course_map = {course.id: course for course in Course.objects.all()}
    quick_course_map = {course.id: course for course in QuickCourse.objects.all()}
    receipts_student_map = {
        row["created_by_id"]: row
        for row in regular_receipts.values("created_by_id").annotate(
            count=Count("id"),
            amount=Sum("paid_amount"),
        )
    }
    receipts_quick_map = {
        row["created_by_id"]: row
        for row in quick_receipts.values("created_by_id").annotate(
            count=Count("id"),
            amount=Sum("paid_amount"),
        )
    }
    expenses_map = {
        row["created_by_id"]: row
        for row in ExpenseEntry.objects.filter(
            date__gte=period_start,
            date__lte=period_end,
        ).values("created_by_id").annotate(
            count=Count("id"),
            amount=Sum("amount"),
        )
    }
    refund_map = {}
    withdrawal_map = {}
    if "user_operations" in selected_sections:
        refund_map, withdrawal_map = _build_user_journal_maps(start_dt, end_dt)
    # Build activity-derived counts once for deterministic reporting.
    activity_totals = {
        row["user_id"]: row["count"]
        for row in activity_qs.values("user_id").annotate(count=Count("id"))
    }
    activity_logins = {
        row["user_id"]: row["count"]
        for row in activity_qs.filter(action="login").values("user_id").annotate(count=Count("id"))
    }
    click_totals = {
        row["user_id"]: row["count"]
        for row in clicks_qs.values("user_id").annotate(count=Count("id"))
    }
    activity_create_counts = {
        (row["user_id"], row["content_type"]): row["count"]
        for row in activity_qs.filter(action="create").values("user_id", "content_type").annotate(count=Count("id"))
    }
    active_time_map = _build_user_active_time_map(activity_qs, end_dt)
    teacher_attendance_user_map = {}
    for row in activity_qs.filter(action="create", content_type="TeacherAttendance").values_list("user_id", "object_id"):
        if row[0] and row[1]:
            teacher_attendance_user_map.setdefault(row[0], set()).add(row[1])
    teacher_attendance_ids = {entry for ids in teacher_attendance_user_map.values() for entry in ids}
    teacher_attendance_totals = {}
    teacher_half_totals = {}
    if teacher_attendance_ids:
        for record in TeacherAttendance.objects.filter(id__in=teacher_attendance_ids).values(
            "id", "session_count", "half_session_count"
        ):
            teacher_attendance_totals[record["id"]] = record["session_count"] or Decimal("0")
            teacher_half_totals[record["id"]] = record["half_session_count"] or Decimal("0")
    user_stats = []
    for user in users:
        receipt_student_data = receipts_student_map.get(user.id, {"count": 0, "amount": Decimal("0")})
        receipt_quick_data = receipts_quick_map.get(user.id, {"count": 0, "amount": Decimal("0")})
        expenses_data = expenses_map.get(user.id, {"count": 0, "amount": Decimal("0")})
        refunds_data = refund_map.get(user.id, {"count": 0, "amount": Decimal("0")})
        withdrawals_data = withdrawal_map.get(user.id, {"count": 0, "amount": Decimal("0")})
        enrollment_count = activity_create_counts.get((user.id, "Studentenrollment"), 0)
        quick_enrollment_count = activity_create_counts.get((user.id, "QuickEnrollment"), 0)
        attendance_count = activity_create_counts.get((user.id, "Attendance"), 0)
        teacher_attendance_count = activity_create_counts.get((user.id, "TeacherAttendance"), 0)
        created_students_count = activity_create_counts.get((user.id, "Student"), 0)
        created_quick_students_count = activity_create_counts.get((user.id, "QuickStudent"), 0)
        active_seconds = active_time_map.get(user.id, 0)
        active_hours = Decimal(active_seconds) / Decimal("3600")
        receipts_total = _to_decimal(receipt_student_data.get("amount")) + _to_decimal(receipt_quick_data.get("amount"))
        expenses_total = _to_decimal(expenses_data.get("amount"))
        refunds_total = _to_decimal(refunds_data.get("amount"))
        withdrawals_total = _to_decimal(withdrawals_data.get("amount"))
        net_balance = receipts_total - expenses_total - refunds_total - withdrawals_total
        session_total = Decimal("0")
        half_total = Decimal("0")
        for attendance_id in teacher_attendance_user_map.get(user.id, set()):
            session_total += teacher_attendance_totals.get(attendance_id, Decimal("0"))
            half_total += teacher_half_totals.get(attendance_id, Decimal("0"))
        teacher_sessions_total = session_total + (half_total * Decimal("0.5"))

        user_stats.append({
            "user_id": user.id,
            "username": user.get_username(),
            "full_name": user.get_full_name() or user.get_username(),
            "is_superuser": user.is_superuser,
            "is_staff": user.is_staff,
            "permissions": permissions_map.get(user.id, []),
            "receipts_students_count": receipt_student_data["count"] or 0,
            "receipts_students_amount": _decimal_to_str(receipt_student_data["amount"]),
            "receipts_quick_count": receipt_quick_data["count"] or 0,
            "receipts_quick_amount": _decimal_to_str(receipt_quick_data["amount"]),
            "expenses_count": expenses_data["count"] or 0,
            "expenses_amount": _decimal_to_str(expenses_data["amount"]),
            "refunds_count": refunds_data["count"] or 0,
            "refunds_amount": _decimal_to_str(refunds_data["amount"]),
            "withdrawals_count": withdrawals_data["count"] or 0,
            "withdrawals_amount": _decimal_to_str(withdrawals_data["amount"]),
            "enrollments_students_count": enrollment_count,
            "enrollments_quick_count": quick_enrollment_count,
            "attendance_students_count": attendance_count,
            "attendance_teachers_count": teacher_attendance_count,
            "created_students_count": created_students_count,
            "created_quick_students_count": created_quick_students_count,
            "active_seconds": active_seconds,
            "active_hours": _decimal_to_str(active_hours),
            "active_time_label": _format_duration(active_seconds),
            "teacher_sessions_count": _decimal_to_str(teacher_sessions_total),
            "teacher_half_sessions_count": _decimal_to_str(half_total),
            "activity_total": activity_totals.get(user.id, 0),
            "logins": activity_logins.get(user.id, 0),
            "clicks_count": click_totals.get(user.id, 0),
            "net_balance": _decimal_to_str(net_balance),
        })

    user_course_receipts = []
    if "user_course_receipts" in selected_sections:
        for row in regular_receipts.values("created_by_id", "course_id").annotate(
            count=Count("id"),
            amount=Sum("paid_amount"),
        ):
            user_obj = user_map.get(row["created_by_id"])
            course_obj = course_map.get(row["course_id"])
            if not user_obj or not course_obj:
                continue
            user_course_receipts.append({
                "user_id": user_obj.id,
                "user_name": user_obj.get_full_name() or user_obj.get_username(),
                "course_id": course_obj.id,
                "course_name": course_obj.name_ar or course_obj.name,
                "count": row["count"],
                "amount": _decimal_to_str(row["amount"]),
            })

    user_course_quick_receipts = []
    if "user_course_quick_receipts" in selected_sections:
        for row in quick_receipts.values("created_by_id", "course_id").annotate(
            count=Count("id"),
            amount=Sum("paid_amount"),
        ):
            user_obj = user_map.get(row["created_by_id"])
            course_obj = quick_course_map.get(row["course_id"])
            if not user_obj or not course_obj:
                continue
            user_course_quick_receipts.append({
                "user_id": user_obj.id,
                "user_name": user_obj.get_full_name() or user_obj.get_username(),
                "course_id": course_obj.id,
                "course_name": course_obj.name_ar or course_obj.name,
                "count": row["count"],
                "amount": _decimal_to_str(row["amount"]),
            })

    user_course_enrollments = []
    if "user_course_enrollments" in selected_sections:
        enrollment_logs = activity_qs.filter(
            action="create",
            content_type="Studentenrollment",
            user__isnull=False,
        ).values_list("user_id", "object_id")
        enrollment_ids = {obj_id for _, obj_id in enrollment_logs if obj_id}
        enrollment_map = {
            enrollment.id: enrollment.course
            for enrollment in Studentenrollment.objects.filter(id__in=enrollment_ids).select_related("course")
        }
        enrollment_counts = {}
        for user_id_value, obj_id in enrollment_logs:
            course = enrollment_map.get(obj_id)
            if not course:
                continue
            key = (user_id_value, course.id)
            enrollment_counts[key] = enrollment_counts.get(key, 0) + 1
        for (user_id_value, course_id_value), count in enrollment_counts.items():
            user_obj = user_map.get(user_id_value)
            course_obj = course_map.get(course_id_value)
            if not user_obj or not course_obj:
                continue
            user_course_enrollments.append({
                "user_id": user_obj.id,
                "user_name": user_obj.get_full_name() or user_obj.get_username(),
                "course_id": course_obj.id,
                "course_name": course_obj.name_ar or course_obj.name,
                "count": count,
            })

    user_course_quick_enrollments = []
    if "user_course_quick_enrollments" in selected_sections:
        quick_enrollment_logs = activity_qs.filter(
            action="create",
            content_type="QuickEnrollment",
            user__isnull=False,
        ).values_list("user_id", "object_id")
        quick_enrollment_ids = {obj_id for _, obj_id in quick_enrollment_logs if obj_id}
        quick_enrollment_map = {
            enrollment.id: enrollment.course
            for enrollment in QuickEnrollment.objects.filter(id__in=quick_enrollment_ids).select_related("course")
        }
        quick_enrollment_counts = {}
        for user_id_value, obj_id in quick_enrollment_logs:
            course = quick_enrollment_map.get(obj_id)
            if not course:
                continue
            key = (user_id_value, course.id)
            quick_enrollment_counts[key] = quick_enrollment_counts.get(key, 0) + 1
        for (user_id_value, course_id_value), count in quick_enrollment_counts.items():
            user_obj = user_map.get(user_id_value)
            course_obj = quick_course_map.get(course_id_value)
            if not user_obj or not course_obj:
                continue
            user_course_quick_enrollments.append({
                "user_id": user_obj.id,
                "user_name": user_obj.get_full_name() or user_obj.get_username(),
                "course_id": course_obj.id,
                "course_name": course_obj.name_ar or course_obj.name,
                "count": count,
            })

    account_qs = Account.objects.filter(
        Q(code__startswith="121")
        | Q(code__startswith="122")
        | Q(code__startswith="123")
    ).order_by("code")
    account_balances = [
        {
            "code": account.code,
            "name": account.display_name,
            "balance": _decimal_to_str(account.rollup_balance),
        }
        for account in account_qs
    ]

    # Keep numeric values as strings in the summary for stable export formatting.
    summary = {
        "period": {
            "start": period_start.isoformat(),
            "end": period_end.isoformat(),
        },
        "generated_at": timezone.now().isoformat(),
        "filters": {
            "course_id": course_id,
            "user_id": user_id,
            "scope": report_scope or "all",
            "sections": sorted(selected_sections),
        },
        "counts": counts_snapshot,
        "activity": activity_section,
        "attendance": attendance_section,
        "transactions": transactions_section,
        "details": {
            "courses": course_stats,
            "quick_courses": quick_course_stats,
            "intensive_quick_courses_top": intensive_quick_courses[:20],
            "regular_outstanding_courses": regular_outstanding_courses,
            "regular_outstanding_totals": regular_outstanding_totals,
            "classrooms": classroom_stats,
            "quick_students_period": quick_students_period,
            "student_comparison": student_comparison,
            "users": user_stats,
            "clicks_total": sum(click_totals.values()),
            "user_course_receipts": user_course_receipts,
            "user_course_quick_receipts": user_course_quick_receipts,
            "user_course_enrollments": user_course_enrollments,
            "user_course_quick_enrollments": user_course_quick_enrollments,
            "discounts_summary": discounts_summary,
            "discounts_by_percent": discounts_by_percent,
            "discounts_by_rule": discounts_by_rule,
            "quick_course_discounts": quick_course_discounts,
            "top_addresses": address_stats,
            "account_balances": account_balances,
            "expense_accounts_top": expense_accounts_top,
            "expense_top_account": expense_top_account,
            "expenses_summary": expenses_summary,
        },
    }

    if use_cache:
        cache.set(cache_key, summary, CACHE_TTL_SECONDS)

    return summary
def persist_system_report_sections(report, summary):
    counts = summary.get("counts", {})
    counts_fields = {
        field.name
        for field in SystemReportCounts._meta.fields
        if field.name not in ("id", "report")
    }
    counts_defaults = {
        key: value for key, value in counts.items() if key in counts_fields
    }
    SystemReportCounts.objects.update_or_create(
        report=report,
        defaults=counts_defaults,
    )
    activity_summary = summary.get("activity", {})
    SystemReportActivitySummary.objects.update_or_create(
        report=report,
        defaults={"total": activity_summary.get("total", 0)},
    )
    SystemReportActivityAction.objects.filter(report=report).delete()
    SystemReportActivityAction.objects.bulk_create([
        SystemReportActivityAction(report=report, action=action, count=count)
        for action, count in activity_summary.get("by_action", {}).items()
    ])
    attendance = summary.get("attendance", {})
    SystemReportAttendanceStats.objects.update_or_create(
        report=report,
        defaults=attendance,
    )
    transactions = summary.get("transactions", {})
    SystemReportTransactionSummary.objects.update_or_create(
        report=report,
        defaults={
            "count": transactions.get("count", 0),
            "debit_total": _to_decimal(transactions.get("debit_total", 0)),
            "credit_total": _to_decimal(transactions.get("credit_total", 0)),
        },
    )

    SystemReportCourseStats.objects.filter(report=report).delete()
    SystemReportCourseStats.objects.bulk_create([
        SystemReportCourseStats(
            report=report,
            course_id=item.get("course_id"),
            is_quick=False,
            enrollments_count=item.get("enrollments_count", 0),
            receipts_count=item.get("receipts_count", 0),
            receipts_amount=_to_decimal(item.get("receipts_amount")),
            expected_amount=_to_decimal(item.get("expected_amount")),
            received_amount=_to_decimal(item.get("received_amount")),
            remaining_amount=_to_decimal(item.get("remaining_amount")),
            account_balance=_to_decimal(item.get("account_balance")),
        )
        for item in summary.get("details", {}).get("courses", [])
    ])
    SystemReportCourseStats.objects.bulk_create([
        SystemReportCourseStats(
            report=report,
            quick_course_id=item.get("course_id"),
            course_type=item.get("course_type", ""),
            is_quick=True,
            enrollments_count=item.get("enrollments_count", 0),
            receipts_count=item.get("receipts_count", 0),
            receipts_amount=_to_decimal(item.get("receipts_amount")),
            expected_amount=_to_decimal(item.get("expected_amount")),
            received_amount=_to_decimal(item.get("received_amount")),
            remaining_amount=_to_decimal(item.get("remaining_amount")),
            account_balance=_to_decimal(item.get("account_balance")),
        )
        for item in summary.get("details", {}).get("quick_courses", [])
    ])

    SystemReportClassroomStats.objects.filter(report=report).delete()
    SystemReportClassroomStats.objects.bulk_create([
        SystemReportClassroomStats(
            report=report,
            classroom_id=item.get("classroom_id"),
            students_total=item.get("students_total", 0),
            students_in_period=item.get("students_in_period", 0),
        )
        for item in summary.get("details", {}).get("classrooms", [])
    ])

    SystemReportUserStats.objects.filter(report=report).delete()
    SystemReportUserStats.objects.bulk_create([
        SystemReportUserStats(
            report=report,
            user_id=item.get("user_id"),
            full_name=item.get("full_name", ""),
            username=item.get("username", ""),
            is_superuser=item.get("is_superuser", False),
            is_staff=item.get("is_staff", False),
            permissions=item.get("permissions", []),
            receipts_students_count=item.get("receipts_students_count", 0),
            receipts_students_amount=_to_decimal(item.get("receipts_students_amount")),
            receipts_quick_count=item.get("receipts_quick_count", 0),
            receipts_quick_amount=_to_decimal(item.get("receipts_quick_amount")),
            expenses_count=item.get("expenses_count", 0),
            expenses_amount=_to_decimal(item.get("expenses_amount")),
            enrollments_students_count=item.get("enrollments_students_count", 0),
            enrollments_quick_count=item.get("enrollments_quick_count", 0),
            attendance_students_count=item.get("attendance_students_count", 0),
                attendance_teachers_count=item.get("attendance_teachers_count", 0),
            created_students_count=item.get("created_students_count", 0),
            created_quick_students_count=item.get("created_quick_students_count", 0),
            active_seconds=item.get("active_seconds", 0),
            active_hours=_to_decimal(item.get("active_hours")),
            teacher_sessions_count=_to_decimal(item.get("teacher_sessions_count")),
            teacher_half_sessions_count=_to_decimal(item.get("teacher_half_sessions_count")),
            activity_total=item.get("activity_total", 0),
            logins=item.get("logins", 0),
        )
        for item in summary.get("details", {}).get("users", [])
    ])

    SystemReportUserCourseReceipt.objects.filter(report=report).delete()
    SystemReportUserCourseReceipt.objects.bulk_create([
        SystemReportUserCourseReceipt(
            report=report,
            user_id=item.get("user_id"),
            course_id=item.get("course_id"),
            count=item.get("count", 0),
            amount=_to_decimal(item.get("amount")),
            is_quick=False,
        )
        for item in summary.get("details", {}).get("user_course_receipts", [])
    ])
    SystemReportUserCourseReceipt.objects.bulk_create([
        SystemReportUserCourseReceipt(
            report=report,
            user_id=item.get("user_id"),
            quick_course_id=item.get("course_id"),
            count=item.get("count", 0),
            amount=_to_decimal(item.get("amount")),
            is_quick=True,
        )
        for item in summary.get("details", {}).get("user_course_quick_receipts", [])
    ])

    SystemReportUserCourseEnrollment.objects.filter(report=report).delete()
    SystemReportUserCourseEnrollment.objects.bulk_create([
        SystemReportUserCourseEnrollment(
            report=report,
            user_id=item.get("user_id"),
            course_id=item.get("course_id"),
            count=item.get("count", 0),
            is_quick=False,
        )
        for item in summary.get("details", {}).get("user_course_enrollments", [])
    ])
    SystemReportUserCourseEnrollment.objects.bulk_create([
        SystemReportUserCourseEnrollment(
            report=report,
            user_id=item.get("user_id"),
            quick_course_id=item.get("course_id"),
            count=item.get("count", 0),
            is_quick=True,
        )
        for item in summary.get("details", {}).get("user_course_quick_enrollments", [])
    ])

    discounts_summary = summary.get("details", {}).get("discounts_summary", {})
    if discounts_summary:
        SystemReportDiscountSummary.objects.update_or_create(
            report=report,
            defaults={
                "student_receipts_count": discounts_summary.get("student_receipts_count", 0),
                "student_receipts_discount_amount": _to_decimal(discounts_summary.get("student_receipts_discount_amount")),
                "student_receipts_discount_percent_count": discounts_summary.get("student_receipts_discount_percent_count", 0),
                "quick_receipts_count": discounts_summary.get("quick_receipts_count", 0),
                "quick_receipts_discount_amount": _to_decimal(discounts_summary.get("quick_receipts_discount_amount")),
                "quick_receipts_discount_percent_count": discounts_summary.get("quick_receipts_discount_percent_count", 0),
                "enrollments_count": discounts_summary.get("enrollments_count", 0),
                "enrollments_discount_amount": _to_decimal(discounts_summary.get("enrollments_discount_amount")),
                "enrollments_discount_percent_count": discounts_summary.get("enrollments_discount_percent_count", 0),
                "quick_enrollments_count": discounts_summary.get("quick_enrollments_count", 0),
                "quick_enrollments_discount_amount": _to_decimal(discounts_summary.get("quick_enrollments_discount_amount")),
                "quick_enrollments_discount_percent_count": discounts_summary.get("quick_enrollments_discount_percent_count", 0),
            },
        )

    SystemReportDiscountPercent.objects.filter(report=report).delete()
    SystemReportDiscountPercent.objects.bulk_create([
        SystemReportDiscountPercent(
            report=report,
            source=item.get("source", ""),
            percent=_to_decimal(item.get("percent"), max_digits=6, decimal_places=2),
            count=item.get("count", 0),
        )
        for item in summary.get("details", {}).get("discounts_by_percent", [])
    ])

    SystemReportDiscountRuleUsage.objects.filter(report=report).delete()
    SystemReportDiscountRuleUsage.objects.bulk_create([
        SystemReportDiscountRuleUsage(
            report=report,
            source=item.get("source", ""),
            rule_name=item.get("rule_name", ""),
            percent=_to_decimal(item.get("percent"), max_digits=6, decimal_places=2),
            amount=_to_decimal(item.get("amount")),
            count=item.get("count", 0),
        )
        for item in summary.get("details", {}).get("discounts_by_rule", [])
    ])

    SystemReportTopAddress.objects.filter(report=report).delete()
    SystemReportTopAddress.objects.bulk_create([
        SystemReportTopAddress(report=report, address=item.get("address", ""), count=item.get("count", 0))
        for item in summary.get("details", {}).get("top_addresses", [])
    ])


def create_system_report(
    period_start,
    period_end,
    report_type="manual",
    created_by=None,
    course_id=None,
    user_id=None,
    report_scope=None,
    sections=None,
):
    summary = build_system_report_summary(
        period_start=period_start,
        period_end=period_end,
        course_id=course_id,
        user_id=user_id,
        report_scope=report_scope,
        sections=sections,
    )
    report = SystemReport.objects.create(
        created_by=created_by,
        period_start=period_start,
        period_end=period_end,
        report_type=report_type,
        summary=summary,
    )
    persist_system_report_sections(report, summary)
    return report
