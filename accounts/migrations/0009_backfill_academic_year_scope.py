from collections import Counter
import re

from django.db import migrations


def _pick_single_year_id(candidates):
    cleaned = [candidate for candidate in candidates if candidate]
    if not cleaned:
        return None
    counts = Counter(cleaned)
    if len(counts) == 1:
        return cleaned[0]
    top_year_id, top_count = counts.most_common(1)[0]
    tied = [year_id for year_id, count in counts.items() if count == top_count]
    if len(tied) == 1:
        return top_year_id
    return None


def backfill_academic_year_scope(apps, schema_editor):
    Course = apps.get_model("accounts", "Course")
    Account = apps.get_model("accounts", "Account")
    JournalEntry = apps.get_model("accounts", "JournalEntry")
    Studentenrollment = apps.get_model("accounts", "Studentenrollment")
    StudentReceipt = apps.get_model("accounts", "StudentReceipt")

    # 1) Courses
    for course in Course.objects.filter(academic_year__isnull=True):
        enrollment_years = list(
            Studentenrollment.objects.filter(course_id=course.pk, academic_year__isnull=False)
            .values_list("academic_year_id", flat=True)
        )
        if not enrollment_years:
            enrollment_years = list(
                Studentenrollment.objects.filter(course_id=course.pk, student__academic_year__isnull=False)
                .values_list("student__academic_year_id", flat=True)
            )
        if not enrollment_years:
            enrollment_years = list(
                StudentReceipt.objects.filter(course_id=course.pk, academic_year__isnull=False)
                .values_list("academic_year_id", flat=True)
            )

        picked_year_id = _pick_single_year_id(enrollment_years)
        if picked_year_id:
            course.academic_year_id = picked_year_id
            course.save(update_fields=["academic_year"])

    # 2) Enrollments
    for enrollment in Studentenrollment.objects.filter(academic_year__isnull=True):
        picked_year_id = enrollment.course.academic_year_id or getattr(enrollment.student, "academic_year_id", None)
        if picked_year_id:
            enrollment.academic_year_id = picked_year_id
            enrollment.save(update_fields=["academic_year"])

    # 3) Receipts
    for receipt in StudentReceipt.objects.filter(academic_year__isnull=True):
        picked_year_id = None
        if receipt.enrollment_id:
            picked_year_id = receipt.enrollment.academic_year_id
        if not picked_year_id and receipt.course_id:
            picked_year_id = receipt.course.academic_year_id
        if not picked_year_id and receipt.student_profile_id:
            picked_year_id = getattr(receipt.student_profile, "academic_year_id", None)
        if picked_year_id:
            receipt.academic_year_id = picked_year_id
            receipt.save(update_fields=["academic_year"])

    # 4) Journal entries
    for entry in JournalEntry.objects.filter(academic_year__isnull=True):
        candidate_years = list(entry.enrollments.exclude(academic_year__isnull=True).values_list("academic_year_id", flat=True))
        candidate_years += list(entry.completions.exclude(academic_year__isnull=True).values_list("academic_year_id", flat=True))
        candidate_years += list(entry.receipts.exclude(academic_year__isnull=True).values_list("academic_year_id", flat=True))
        picked_year_id = _pick_single_year_id(candidate_years)
        if picked_year_id:
            entry.academic_year_id = picked_year_id
            entry.save(update_fields=["academic_year"])

    # 5) Accounts
    course_ids = {
        course.pk: course.academic_year_id
        for course in Course.objects.exclude(academic_year__isnull=True).only("id", "academic_year")
    }

    code_patterns = [
        re.compile(r"^1251-(?P<course_id>\d+)$"),
        re.compile(r"^1251-(?P<course_id>\d+)-\d+$"),
        re.compile(r"^21001-(?P<course_id>\d+)$"),
        re.compile(r"^4101-(?P<course_id>\d+)$"),
        re.compile(r"^4201-(?P<course_id>\d+)-\d+$"),
    ]

    for account in Account.objects.filter(academic_year__isnull=True):
        picked_year_id = None
        if account.parent_id and getattr(account.parent, "academic_year_id", None):
            picked_year_id = account.parent.academic_year_id
        if not picked_year_id and account.code:
            for pattern in code_patterns:
                match = pattern.match(account.code)
                if match:
                    picked_year_id = course_ids.get(int(match.group("course_id")))
                    if picked_year_id:
                        break
        if picked_year_id:
            account.academic_year_id = picked_year_id
            account.save(update_fields=["academic_year"])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0008_add_academic_year_scope"),
    ]

    operations = [
        migrations.RunPython(backfill_academic_year_scope, noop_reverse),
    ]

