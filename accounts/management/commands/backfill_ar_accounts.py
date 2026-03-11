from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q

class Command(BaseCommand):
    help = "Backfill AR accounts to the 1251 / 1251-CCC / 1251-CCC-SSS structure."

    def handle(self, *args, **options):
        from accounts.models import Account, Course, Student  # <-- غيّر المسارات
        try:
            from accounts.models import Enrollment
            enrollment_qs = Enrollment.objects.select_related('student', 'course')
            source = 'enrollment'
        except Exception:
            Enrollment = None
            enrollment_qs = []
            source = None

        with transaction.atomic():
            ar_parent, _ = Account.objects.get_or_create(
                code='1251',
                defaults={
                    'name': 'Accounts Receivable - Students',
                    'name_ar': 'ذمم الطلاب المدينة',
                    'account_type': 'ASSET',
                    'is_active': True,
                }
            )
            created_courses = 0
            created_students = 0

            # Courses
            courses = set(e.course for e in enrollment_qs) if source == 'enrollment' else Course.objects.all()
            for course in courses:
                course_code = f"1251-{course.id:03d}"
                acc, created = Account.objects.get_or_create(
                    code=course_code,
                    defaults={
                        'name': f"Accounts Receivable - {getattr(course, 'name', course.id)}",
                        'name_ar': f"ذمم طلاب دورة {getattr(course, 'name', course.id)}",
                        'account_type': 'ASSET',
                        'parent': ar_parent,
                        'is_course_account': True,
                        'course_name': getattr(course, 'name', None),
                        'is_active': True,
                    }
                )
                if created:
                    created_courses += 1
                else:
                    updates = {}
                    if acc.parent_id != ar_parent.id: updates['parent'] = ar_parent
                    if not getattr(acc, 'is_course_account', False): updates['is_course_account'] = True
                    if not getattr(acc, 'account_type', None): updates['account_type'] = 'ASSET'
                    if not getattr(acc, 'course_name', None) and hasattr(course, 'name'): updates['course_name'] = course.name
                    if updates:
                        for k, v in updates.items(): setattr(acc, k, v)
                        acc.save(update_fields=list(updates.keys()))

            # Students
            def ensure_student(student, course):
                nonlocal created_students
                course_code = f"1251-{course.id:03d}"
                student_code = f"1251-{course.id:03d}-{student.id:03d}"
                course_acc = Account.objects.get(code=course_code)
                acc, created = Account.objects.get_or_create(
                    code=student_code,
                    defaults={
                        'name': f"AR - {getattr(student, 'full_name', student.id)}",
                        'name_ar': f"ذمة {getattr(student, 'full_name', student.id)}",
                        'account_type': 'ASSET',
                        'parent': course_acc,
                        'is_student_account': True,
                        'student_name': getattr(student, 'full_name', None),
                        'is_active': True,
                    }
                )
                if created:
                    created_students += 1
                else:
                    updates = {}
                    if acc.parent_id != course_acc.id: updates['parent'] = course_acc
                    if not getattr(acc, 'is_student_account', False): updates['is_student_account'] = True
                    if not getattr(acc, 'account_type', None): updates['account_type'] = 'ASSET'
                    if not getattr(acc, 'student_name', None) and hasattr(student, 'full_name'): updates['student_name'] = student.full_name
                    if updates:
                        for k, v in updates.items(): setattr(acc, k, v)
                        acc.save(update_fields=list(updates.keys()))

            if source == 'enrollment':
                for e in enrollment_qs:
                    if getattr(e, 'student', None) and getattr(e, 'course', None):
                        ensure_student(e.student, e.course)
            else:
                if hasattr(Student, 'courses'):
                    for st in Student.objects.all().prefetch_related('courses'):
                        for crs in st.courses.all():
                            ensure_student(st, crs)

            # اختياري: تعطيل الحسابات المخالفة للنمط
            Account.objects.filter(
                Q(code__startswith='1251-') & ~Q(code__regex=r'^1251-\d{3}(-\d{3})?$')
            ).update(is_active=False)

            self.stdout.write(self.style.SUCCESS(
                f'Done. Created course accounts: {created_courses}, student accounts: {created_students}.'
            ))
