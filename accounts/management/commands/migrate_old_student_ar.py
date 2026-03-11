from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q
from django.apps import apps
import re

class Command(BaseCommand):
    help = "Auto-migrate legacy student AR accounts to 1251 / 1251-CCC / 1251-CCC-SSS, fixing parent & code."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Show changes without saving")

    def handle(self, *args, **opts):
        DRY = opts["dry_run"]

        # === عدّل أسماء الموديلات لو مختلفة ===
        Account = apps.get_model('accounts', 'Account')   # <-- اسم التطبيق/الموديل
        Student = apps.get_model('students', 'Student')
        Course  = apps.get_model('accounts', 'Course')

        # موديل قيود يومية (اختياري للدمج)
        JournalLine = None
        for label, model in apps.all_models.items():
            for m in model.values():
                if m.__name__.lower() in {"journalline", "journalentryline", "accountingline"}:
                    JournalLine = m

        # اكتشاف موديلات فيها student & course
        sc_models = []
        for model in apps.get_models():
            flds = {f.name for f in model._meta.get_fields()}
            if {"student", "course"}.issubset(flds):
                sc_models.append(model)

        def ensure_ar_parent():
            ar, _ = Account.objects.get_or_create(
                code="1251",
                defaults={
                    "name": "Accounts Receivable - Students",
                    "name_ar": "ذمم الطلاب المدينة",
                    "account_type": "ASSET",
                    "is_active": True,
                },
            )
            return ar

        def ensure_course_acc(ar_parent, course):
            code = f"1251-{course.id:03d}"
            acc, _ = Account.objects.get_or_create(
                code=code,
                defaults={
                    "name": f"Accounts Receivable - {getattr(course, 'name', course.id)}",
                    "name_ar": f"ذمم طلاب دورة {getattr(course, 'name', course.id)}",
                    "account_type": "ASSET",
                    "parent": ar_parent,
                    "is_course_account": True,
                    "course_name": getattr(course, "name", None),
                    "is_active": True,
                },
            )
            updates = {}
            if acc.parent_id != ar_parent.id: updates["parent"] = ar_parent
            if not getattr(acc, "is_course_account", False): updates["is_course_account"] = True
            if not getattr(acc, "account_type", None): updates["account_type"] = "ASSET"
            if not getattr(acc, "course_name", None) and hasattr(course, "name"): updates["course_name"] = course.name
            if updates and not DRY:
                for k, v in updates.items(): setattr(acc, k, v)
                acc.save(update_fields=list(updates.keys()))
            return acc

        code_new_pat = re.compile(r"^1251-(\d{3})-(\d{3})$")
        code_course_pat = re.compile(r"^1251-(\d{3})$")

        def get_student_accounts(student):
            # كل الحسابات المُحتملة للطالب
            qs = Account.objects.filter(
                Q(is_student_account=True, student_name=getattr(student, "full_name", None))
                | Q(name__icontains=str(getattr(student, "full_name", student.id)))
                | Q(name_ar__icontains=str(getattr(student, "full_name", student.id)))
                | Q(code__endswith=f"-{student.id:03d}")
            )
            return list(qs.order_by("id"))

        def guess_course_for_student(student, acc_candidates):
            # 1) Student.course FK
            if hasattr(student, "course_id") and getattr(student, "course_id", None):
                try: return Course.objects.get(id=student.course_id)
                except Course.DoesNotExist: pass

            # 2) Student.courses M2M (نختار أحدث/أعلى id)
            if hasattr(student, "courses"):
                try:
                    crs = student.courses.all().order_by("-id").first()
                    if crs: return crs
                except Exception:
                    pass

            # 3) من الكود الجديد إن وجد
            for acc in acc_candidates:
                m = code_new_pat.match(acc.code or "")
                if m:
                    c_id = int(m.group(1))
                    try: return Course.objects.get(id=c_id)
                    except Course.DoesNotExist: pass

            # 4) من الأب إن كان حساب دورة
            for acc in acc_candidates:
                if acc.parent and acc.parent.code:
                    m = code_course_pat.match(acc.parent.code)
                    if m:
                        c_id = int(m.group(1))
                        try: return Course.objects.get(id=c_id)
                        except Course.DoesNotExist: pass

            # 5) من أي موديل (student, course) مكتشف — أحدث سجل
            for M in sc_models:
                try:
                    row = M.objects.filter(student_id=student.id).order_by("-id").select_related("course").first()
                    if row and getattr(row, "course_id", None):
                        return row.course
                except Exception:
                    continue

            return None

        def migrate_student(student, course, ar_parent):
            course_acc = ensure_course_acc(ar_parent, course)
            target_code = f"1251-{course.id:03d}-{student.id:03d}"
            target_name = f"AR - {getattr(student, 'full_name', student.id)}"
            target_name_ar = f"ذمة {getattr(student, 'full_name', student.id)}"

            target = Account.objects.filter(code=target_code).first()

            # اجمع كل حسابات الطالب (قديمة/جديدة)
            cand = get_student_accounts(student)

            # لو موجود هدف نهائي
            if target:
                updates = {}
                if target.parent_id != course_acc.id: updates["parent"] = course_acc
                if not getattr(target, "is_student_account", False): updates["is_student_account"] = True
                if not getattr(target, "student_name", None) and hasattr(student, "full_name"): updates["student_name"] = student.full_name
                if updates and not DRY:
                    for k, v in updates.items(): setattr(target, k, v)
                    target.save(update_fields=list(updates.keys()))
                # دمج أي قديم عليه قيود ثم تعطيل القديم
                for acc in cand:
                    if acc.id == target.id: continue
                    if JournalLine:
                        if not DRY:
                            JournalLine.objects.filter(account_id=acc.id).update(account_id=target.id)
                    if not DRY:
                        acc.is_active = False
                        acc.save(update_fields=["is_active"])
                return "exists_aligned", target

            # لو ما في هدف: جرّب إعادة تسمية حساب قديم مناسب
            for acc in cand:
                # إذا كان acc له parent دورة صحيحة أو اسمه يخص الطالب
                if not DRY:
                    acc.code = target_code
                    acc.parent = course_acc
                    acc.account_type = "ASSET"
                    acc.is_student_account = True
                    if hasattr(acc, "student_name") and hasattr(student, "full_name") and not acc.student_name:
                        acc.student_name = student.full_name
                    acc.name = target_name
                    acc.name_ar = target_name_ar
                    acc.is_active = True
                    acc.save()
                return "renamed_reparented", acc

            # لو ما لقينا أي حساب سابق → أنشئ جديد
            if not DRY:
                target = Account.objects.create(
                    code=target_code,
                    name=target_name,
                    name_ar=target_name_ar,
                    account_type="ASSET",
                    parent=course_acc,
                    is_student_account=True,
                    student_name=getattr(student, "full_name", None),
                    is_active=True,
                )
            return "created", target

        with transaction.atomic():
            ar_parent = ensure_ar_parent()

            stats = {"created":0, "renamed_reparented":0, "exists_aligned":0, "skipped_no_course":0}

            # نمشي على كل الطلاب ونحاول تحديد دورتهم
            for st in Student.objects.all():
                acc_candidates = get_student_accounts(st)
                course = guess_course_for_student(st, acc_candidates)
                if not course:
                    self.stdout.write(self.style.WARNING(
                        f"[SKIP] ما قدرت أحدد دورة للطالب: {getattr(st,'full_name',st.id)} (اكمله يدويًا أو زوّد مصدر ربط)."
                    ))
                    stats["skipped_no_course"] += 1
                    continue
                state, acc = migrate_student(st, course, ar_parent)
                stats[state] += 1
                self.stdout.write(f"[{state}] student={getattr(st,'full_name',st.id)} course={getattr(course,'name',course.id)} -> {getattr(acc,'code',None)}")

            # (اختياري) تعطيل أي حسابات 1251-* غير مطابقة للنمط الجديد
            Account.objects.filter(
                Q(code__startswith='1251-') & ~Q(code__regex=r'^1251-\d{3}(-\d{3})?$')
            ).update(is_active=False)

            msg = f"Done. created={stats['created']}, renamed={stats['renamed_reparented']}, aligned={stats['exists_aligned']}, skipped_no_course={stats['skipped_no_course']}"
            if DRY:
                self.stdout.write(self.style.WARNING(msg + " [DRY RUN — لا تغيير على القاعدة]"))
            else:
                self.stdout.write(self.style.SUCCESS(msg))
