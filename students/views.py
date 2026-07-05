from django import forms 
from django.views.generic import ListView, CreateView, DeleteView, UpdateView
from django.views.generic.edit import FormView
from django.urls import reverse_lazy, reverse
from django.db.models import Q, Sum
from django.db import transaction as db_transaction
from django.db.models import ProtectedError
from django.contrib.auth import get_user_model
from attendance.models import Attendance
from classroom.models import Classroomenrollment
from django.http import JsonResponse, HttpResponse, HttpResponseForbidden
from django.utils import timezone
from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import View, TemplateView, ListView, DetailView
from .models import Student, StudentWarning
from django.contrib import messages
from django.utils.dateparse import parse_date
from .forms import StudentForm
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from django.views.decorators.http import require_POST
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from accounts.models import Transaction, StudentReceipt, Studentenrollment, JournalEntry, Account, get_user_cash_account
from classroom.models import Classroom
from django.contrib.auth.mixins import UserPassesTestMixin, LoginRequiredMixin
from django.contrib.auth.decorators import login_required, user_passes_test
from django.template.loader import render_to_string
from django.contrib.staticfiles import finders
from django.conf import settings
from xhtml2pdf import pisa
try:
    from weasyprint import HTML
    from weasyprint.urls import default_url_fetcher
    WEASYPRINT_AVAILABLE = True
except Exception:
    HTML = None
    default_url_fetcher = None
    WEASYPRINT_AVAILABLE = False
import os
import tempfile
import re
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.pdfmetrics import registerFontFamily
from urllib.parse import quote
import io
import zipfile
# في students/views.py - أضف في البداية
import traceback
# Import for course registration
from accounts.models import Course, CostCenter
User = get_user_model()

from academic_years.services.session import get_current_academic_year

def _current_academic_year(request):
    return getattr(request, "current_academic_year", None) or get_current_academic_year(request)

def _scope_queryset_to_current_year(queryset, request, field_name="academic_year", include_null=False):
    academic_year = _current_academic_year(request)
    if not academic_year:
        return queryset
    if include_null:
        return queryset.filter(Q(**{field_name: academic_year}) | Q(**{f"{field_name}__isnull": True}))
    return queryset.filter(**{field_name: academic_year})

def _parse_post_decimal(value, default='0'):
    if value is None:
        return Decimal(default)

    text = str(value).strip()
    if not text:
        return Decimal(default)

    text = (
        text.replace('\u200f', '')
        .replace('\u200e', '')
        .replace('\xa0', '')
        .replace(' ', '')
        .replace('٬', '')
        .replace('٫', '.')
    )

    if ',' in text and '.' not in text:
        parts = text.split(',')
        if len(parts) == 2 and len(parts[1]) <= 2:
            text = '.'.join(parts)
        else:
            text = ''.join(parts)
    else:
        text = text.replace(',', '')

    return Decimal(text)


def _arabic_score(text):
    return sum(1 for char in text if "\u0600" <= char <= "\u06FF")


def _repair_mojibake_text(value):
    if value in (None, ""):
        return value

    text = str(value)
    if not any(char in text for char in ("ط", "ظ", "Ø", "Ù")):
        return text

    for wrong_encoding in ("cp1256", "latin1"):
        try:
            repaired = text.encode(wrong_encoding).decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            continue

        if repaired != text and _arabic_score(repaired) > _arabic_score(text):
            return repaired

    return text


def _fix_mojibake_queryset(queryset, field_name):
    updated_count = 0

    for obj in queryset.only("id", field_name).iterator():
        original_value = getattr(obj, field_name, None)
        repaired_value = _repair_mojibake_text(original_value)

        if repaired_value != original_value:
            setattr(obj, field_name, repaired_value)
            obj.save(update_fields=[field_name])
            updated_count += 1

    return updated_count


@login_required
@user_passes_test(lambda u: u.is_superuser)
@require_POST
def fix_arabic_mojibake_records(request):
    next_url = request.POST.get('next') or reverse('students:student_list')

    with db_transaction.atomic():
        fixed_transactions = _fix_mojibake_queryset(Transaction.objects.all(), 'description')
        fixed_entries = _fix_mojibake_queryset(JournalEntry.objects.all(), 'description')
        fixed_accounts = _fix_mojibake_queryset(Account.objects.exclude(name_ar__isnull=True), 'name_ar')

    total_fixed = fixed_transactions + fixed_entries + fixed_accounts

    if total_fixed:
        messages.success(
            request,
            f'تم إصلاح {total_fixed} سجل بنجاح. المعاملات: {fixed_transactions}، القيود: {fixed_entries}، الحسابات: {fixed_accounts}.'
        )
    else:
        messages.info(request, 'لم يتم العثور على نصوص عربية معطوبة تحتاج إلى إصلاح.')

    return redirect(next_url)

class StudentProfileView(LoginRequiredMixin, View):
    template_name = 'students/student_profile.html'
    
    def get(self, request, *args, **kwargs):
        student_id = self.kwargs.get('student_id')
        student = get_object_or_404(Student, id=student_id)
        
        print(f"🎯 [DEBUG] جلب بيانات الطالب ID: {student_id}")
        
        # جلب التسجيلات النشطة
        enrollments = Studentenrollment.objects.filter(
            student=student, 
            is_completed=False
        ).select_related('course')
        
        print(f"🎯 [DEBUG] عدد التسجيلات في DB: {enrollments.count()}")
        
        active_enrollments_data = []
        total_paid = Decimal('0.00')
        total_due = Decimal('0.00')
        
        for enrollment in enrollments:
            print(f"🎯 [DEBUG] معالجة التسجيل: {enrollment.id} - {enrollment.course.name}")
            
            # حساب المبلغ المدفوع
            enrollment_paid = StudentReceipt.objects.filter(
                enrollment=enrollment
            ).aggregate(total=Sum('paid_amount'))['total'] or Decimal('0.00')
            
            net_amount = enrollment.net_amount if enrollment.net_amount is not None else (enrollment.total_amount or Decimal('0.00'))
            balance_due = max(Decimal('0.00'), net_amount - enrollment_paid)
            
            active_enrollments_data.append({
                'enrollment': enrollment,
                'total_paid': enrollment_paid,
                'balance_due': balance_due,
                'net_amount': net_amount,
            })
            
            total_paid += enrollment_paid
            total_due += net_amount
        
        # لا تدع المتبقي يصبح سالباً إذا كان هناك خصم كامل أو دفعات سابقة
        total_remaining = max(Decimal('0.00'), total_due - total_paid)
        
        # جلب الإيصالات
        receipts = StudentReceipt.objects.filter(
            student_profile=student
        ).select_related('course').order_by('-date', '-id')
        
        # جلب بيانات الأداء الأكاديمي
        try:
            from exams.models import ExamGrade
            from attendance.models import Attendance
            from django.db.models import Count, Q
            
            # آخر 5 اختبارات
            recent_exam_grades = ExamGrade.objects.filter(
                student=student
            ).select_related('exam', 'exam__subject').order_by('-exam__exam_date')[:5]
            
            # إحصائيات الحضور
            attendance_stats = Attendance.objects.filter(
                student=student
            ).aggregate(
                total_days=Count('id'),
                present_days=Count('id', filter=Q(status='present')),
                absent_days=Count('id', filter=Q(status='absent'))
            )
            
            # حساب نسبة الحضور
            total_days = attendance_stats['total_days'] or 0
            present_days = attendance_stats['present_days'] or 0
            attendance_rate = (present_days / total_days * 100) if total_days > 0 else 0
            
            # آخر 10 أيام حضور
            recent_attendance = Attendance.objects.filter(
                student=student
            ).select_related('classroom').order_by('-date')[:10]
            
            # حساب متوسط العلامات
            average_grade = 0
            if recent_exam_grades:
                total_percentage = 0
                valid_grades_count = 0
                for exam_grade in recent_exam_grades:
                    if exam_grade.grade is not None and exam_grade.exam.max_grade > 0:
                        percentage = (exam_grade.grade / exam_grade.exam.max_grade) * 100
                        total_percentage += percentage
                        valid_grades_count += 1
                average_grade = total_percentage / valid_grades_count if valid_grades_count > 0 else 0
            
            # تحديد إذا كان الطالب راسب
            is_failing = False
            for exam_grade in recent_exam_grades:
                if exam_grade.grade and exam_grade.exam.max_grade > 0:
                    percentage = (exam_grade.grade / exam_grade.exam.max_grade) * 100
                    if percentage < 50:
                        is_failing = True
                        break
                        
        except Exception as e:
            print(f"⚠️ [DEBUG] خطأ في بيانات الأداء: {str(e)}")
            recent_exam_grades = []
            attendance_stats = {}
            attendance_rate = 0
            recent_attendance = []
            average_grade = 0
            is_failing = False
        
        print(f"🎯 [DEBUG] البيانات النهائية:")
        print(f"🎯 [DEBUG] - active_enrollments_data: {len(active_enrollments_data)}")
        print(f"🎯 [DEBUG] - total_paid: {total_paid}")
        print(f"🎯 [DEBUG] - total_due: {total_due}")

        active_warnings = StudentWarning.objects.filter(
            student=student,
            is_active=True
        ).select_related('created_by').order_by('-created_at')
        try:
            from mobile.models import ListeningTestAssignment

            listening_assignments = (
                ListeningTestAssignment.objects.filter(
                    student=student,
                    is_listened=True
                )
                .select_related('test', 'test__teacher', 'test__classroom')
                .order_by('-test__created_at', '-created_at')
            )
        except Exception:
            listening_assignments = []
        
        context = {
            'student': student,
            'active_enrollments': active_enrollments_data,
            'total_paid': total_paid,
            'total_due': total_due,
            'total_remaining': total_remaining,
            'receipts': receipts,
            'has_active_enrollments': len(active_enrollments_data) > 0,
            'active_enrollments_count': len(active_enrollments_data),
            
            # بيانات الأداء الأكاديمي
            'recent_exam_grades': recent_exam_grades,
            'attendance_stats': attendance_stats,
            'attendance_rate': round(attendance_rate, 1),
            'recent_attendance': recent_attendance,
            'total_attendance_days': total_days,
            'average_grade': round(average_grade, 1),
            'is_failing': is_failing,
            'active_warnings': active_warnings,
            'warnings_count': active_warnings.count(),
            'listening_assignments': listening_assignments,
            'listening_count': listening_assignments.count() if hasattr(listening_assignments, 'count') else len(listening_assignments),
        }
        
        return render(request, self.template_name, context)
    

@login_required
@require_POST
def add_student_warning(request, student_id):
    student = get_object_or_404(Student, id=student_id)
    title = (request.POST.get('title') or '').strip()
    severity = (request.POST.get('severity') or StudentWarning.Severity.WARNING).strip()
    details = (request.POST.get('details') or '').strip()

    if not title:
        messages.error(request, 'يجب إضافة سبب واضح للإنذار.')
        return redirect('students:student_profile', student_id=student.id)

    if severity not in StudentWarning.Severity.values:
        severity = StudentWarning.Severity.WARNING

    StudentWarning.objects.create(
        student=student,
        title=title,
        severity=severity,
        details=details,
        created_by=request.user if request.user.is_authenticated else None
    )

    messages.success(request, 'تم تسجيل الإنذار الأكاديمي للطالب بنجاح.')
    return redirect('students:student_profile', student_id=student.id)
    
class StudentDetailedReportView(LoginRequiredMixin, DetailView):
    model = Student
    template_name = 'students/student_detailed_report.html'
    context_object_name = 'student'
    
    def get_object(self):
        return get_object_or_404(Student, id=self.kwargs.get('student_id'))
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        student = self.get_object()
        
        try:
            from exams.models import ExamGrade
            from attendance.models import Attendance
            from django.db.models import Avg, Count, Q
            from django.utils import timezone
            
            # جلب جميع العلامات
            all_exam_grades = ExamGrade.objects.filter(
                student=student
            ).select_related('exam', 'exam__subject').order_by('-exam__exam_date')
            
            # جلب جميع الحضور
            all_attendance = Attendance.objects.filter(
                student=student
            ).select_related('classroom').order_by('-date')
            
            # إحصائيات العلامات - محسنة
            exam_stats = all_exam_grades.aggregate(
                total_exams=Count('id'),
                average_grade=Avg('grade', filter=Q(grade__isnull=False)),
                completed_exams=Count('id', filter=Q(grade__isnull=False))
            )
            
            # حساب نسبة النجاح بشكل صحيح - إصلاح المشكلة
            completed_exams = exam_stats.get('completed_exams', 0)
            total_exams = exam_stats.get('total_exams', 0)
            
            if completed_exams > 0 and total_exams > 0:
                # حساب النسبة المئوية للنجاح بناءً على العلامات الفعلية
                passed_exams = all_exam_grades.filter(
                    grade__isnull=False
                ).filter(
                    # اعتبار الطالب ناجح إذا حصل على 60% أو أكثر
                    Q(grade__gte=40)  # إذا كانت العلامة 60 من 100
                ).count()
                
                success_rate = (passed_exams / completed_exams) * 100
            else:
                success_rate = 0
                
            exam_stats['success_rate'] = round(success_rate, 1)
            
            # إحصائيات الحضور الشهرية - محسنة
            from django.db.models.functions import TruncMonth
            monthly_attendance_raw = all_attendance.annotate(
                month=TruncMonth('date')
            ).values('month').annotate(
                total_days=Count('id'),
                present_days=Count('id', filter=Q(status='present')),
                absent_days=Count('id', filter=Q(status='absent'))
            ).order_by('-month')
            monthly_attendance = []
            for row in monthly_attendance_raw:
                total_days = row.get('total_days') or 0
                present_days = row.get('present_days') or 0
                percentage = round((present_days / total_days) * 100, 1) if total_days > 0 else 0
                if percentage >= 90:
                    status = 'ممتاز'
                elif percentage >= 80:
                    status = 'جيد جدا'
                elif percentage >= 70:
                    status = 'جيد'
                elif percentage >= 60:
                    status = 'مقبول'
                else:
                    status = 'ضعيف'
                monthly_attendance.append({
                    'month': row.get('month'),
                    'total_days': total_days,
                    'present_days': present_days,
                    'absent_days': row.get('absent_days') or 0,
                    'percentage': percentage,
                    'status': status,
                })

            active_warnings = StudentWarning.objects.filter(
                student=student,
                is_active=True
            ).select_related('created_by').order_by('-created_at')
            try:
                from mobile.models import ListeningTestAssignment

                listening_assignments = (
                    ListeningTestAssignment.objects.filter(
                        student=student,
                        is_listened=True
                    )
                    .select_related('test', 'test__teacher', 'test__classroom')
                    .order_by('-test__created_at', '-created_at')
                )
            except Exception:
                listening_assignments = []
            
            context.update({
                'all_exam_grades': all_exam_grades,
                'all_attendance': all_attendance,
                'exam_stats': exam_stats,
                'monthly_attendance': monthly_attendance,
                'report_date': timezone.now().date(),
                'active_warnings': active_warnings,
                'warnings_count': active_warnings.count(),
                'listening_assignments': listening_assignments,
                'listening_count': listening_assignments.count() if hasattr(listening_assignments, 'count') else len(listening_assignments),
            })
            
        except Exception as e:
            print(f"خطأ في تحميل التقرير التفصيلي: {str(e)}")
            # قيم افتراضية في حالة الخطأ
            context.update({
                'all_exam_grades': [],
                'all_attendance': [],
                'exam_stats': {
                    'total_exams': 0,
                    'average_grade': 0,
                    'completed_exams': 0,
                    'success_rate': 0
                },
                'monthly_attendance': [],
                'active_warnings': [],
                'warnings_count': 0,
                'listening_assignments': [],
                'listening_count': 0,
            })
        
        return context

class StudentStatementView(LoginRequiredMixin, DetailView):
    model = Student
    template_name = 'students/student_statement.html'
    context_object_name = 'student'
    
    def get_object(self):
        return get_object_or_404(Student, id=self.kwargs.get('student_id'))
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        student = self.get_object()

        try:
            # 1️⃣ جلب الإيصالات
            receipts = (StudentReceipt.objects
                        .filter(student_profile=student)
                        .select_related('course', 'created_by', 'journal_entry')
                        .order_by('-date', '-id'))

            # 2️⃣ حساب المدفوعات لكل دورة
            paid_by_course = defaultdict(Decimal)
            courses = {}
            for rcp in receipts:
                if rcp.course_id:
                    courses[rcp.course_id] = rcp.course
                    paid_by_course[rcp.course_id] += rcp.paid_amount or Decimal('0')

            # 3️⃣ جلب جميع حسابات الطالب (لكل دورة)
            student_accounts = Account.objects.filter(
                is_student_account=True,
                student_name__icontains=student.full_name
            ).order_by('code')
            
            # 4️⃣ إذا لم يوجد حسابات، إنشاء حسابات من الإيصالات الموجودة
            if not student_accounts.exists():
                for receipt in receipts:
                    if receipt.course and receipt.enrollment:
                        # إنشاء الحساب للدورة
                        account = Account.get_or_create_student_ar_account(
                            student, 
                            receipt.course
                        )
                        student_accounts = Account.objects.filter(
                            id=account.id
                        )  # تحديث الكويري سيت

            # 5️⃣ جلب جميع المعاملات لكل حسابات الطالب
            all_transactions = []
            if student_accounts.exists():
                account_ids = student_accounts.values_list('id', flat=True)
                all_transactions = Transaction.objects.filter(
                    account_id__in=account_ids
                ).select_related(
                    'journal_entry', 
                    'journal_entry__created_by',
                    'account'
                ).order_by('journal_entry__date', 'id')
            
            # 6️⃣ حساب الرصيد لكل حساب
            account_balances = {}
            running_balance = Decimal('0.00')
            
            # تهيئة الأرصدة
            for account in student_accounts:
                account_balances[account.id] = Decimal('0.00')
            
            # 7️⃣ إعداد صفوف العرض
            rows = []
            for txn in all_transactions:
                # تحديث الرصيد
                if txn.is_debit:
                    account_balances[txn.account_id] += txn.amount
                    running_balance += txn.amount
                else:
                    account_balances[txn.account_id] -= txn.amount
                    running_balance -= txn.amount
                
                rows.append({
                    'date': txn.journal_entry.date,
                    'ref': txn.journal_entry.reference,
                    'desc': f"{txn.description} - {txn.account.course_name if txn.account.course_name else ''}",
                    'debit': txn.amount if txn.is_debit else Decimal('0.00'),
                    'credit': txn.amount if not txn.is_debit else Decimal('0.00'),
                    'balance': account_balances[txn.account_id],
                    'created_by': txn.journal_entry.created_by.get_full_name() or txn.journal_entry.created_by.username,
                    'account_code': txn.account.code
                })
            
            # 8️⃣ حساب الرصيد الإجمالي
            total_balance = sum(account_balances.values())
            
            # 9️⃣ تحضير بيانات الدورات
            per_course = []
            for course_id, course in courses.items():
                # البحث عن الحساب الخاص بهذه الدورة
                course_account = None
                for account in student_accounts:
                    if account.course_name == course.name:
                        course_account = account
                        break
                
                # إذا لم يوجد حساب، أنشئه
                if not course_account:
                    course_account = Account.get_or_create_student_ar_account(student, course)
                
                # حساب المبالغ
                net_due = Decimal('0.00')
                enrollment = Studentenrollment.objects.filter(
                    student=student,
                    course=course,
                    is_completed=False
                ).first()
                
                if enrollment:
                    net_due = enrollment.net_amount if enrollment.net_amount is not None else (enrollment.total_amount or Decimal('0'))
                else:
                    net_due = course.price or Decimal('0')
                
                paid = paid_by_course.get(course_id, Decimal('0'))
                outstanding = max(Decimal('0'), net_due - paid)
                
                per_course.append({
                    'course': course,
                    'price': net_due,
                    'net_due': net_due,
                    'paid': paid,
                    'outstanding': outstanding,
                    'account': course_account
                })
            
            # 🔟 إعداد السياق
            context.update({
                'account': student_accounts.first() if student_accounts.exists() else None,
                'accounts': student_accounts,  # جميع حسابات الطالب
                'rows': rows,
                'balance': total_balance,
                'receipts': receipts,
                    'per_course': per_course,
                'has_accounts': student_accounts.exists(),
                'transactions_count': len(all_transactions)
            })
            
            # 🔟+١ إذا لم يكن هناك حسابات، إظهار رسالة
            if not student_accounts.exists():
                messages.warning(
                    self.request, 
                    'لا يوجد حسابات مالية للطالب. سيتم إنشاؤها تلقائياً عند الدفع القادم.'
                )
            
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            print(f"❌ [ERROR] خطأ في كشف الحساب: {str(e)}")
            print(f"تفاصيل: {error_details}")
            
            messages.error(self.request, f'حدث خطأ في تحميل كشف الحساب: {str(e)}')
            context.update({
                'account': None,
                'accounts': [],
                'rows': [],
                'balance': Decimal('0.00'),
                'receipts': [],
                'per_course': [],
                'has_accounts': False,
                'transactions_count': 0
            })
        
        return context

from django.views.generic import ListView, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q, Count
from django.shortcuts import get_object_or_404
from .models import Student

class StudentAccountingIssuesView(LoginRequiredMixin, TemplateView):
    template_name = 'students/accounting_issues.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        names_param = self.request.GET.get('names')
        if names_param:
            names = [n.strip() for n in names_param.split(',') if n.strip()]
        else:
            names = ['لامار عباس احمد غوراني', 'سامر قبي', 'قولي ياسر طهماز']
        
        students = Student.objects.filter(full_name__in=names).prefetch_related('enrollments', 'enrollments__course')
        issues = []
        
        for student in students:
            student_issues = []
            
            # Missing AR account
            if not hasattr(student, 'account') or not student.account:
                student_issues.append('⚠️ لا يوجد حساب ذمم للطالب')
            
            # Negative balance check
            try:
                # Assuming student.get_balance() or similar logic
                if hasattr(student, 'balance') and student.balance < 0:
                    student_issues.append('⚠️ رصيد سلبي')
            except Exception:
                pass
            # Discount consistency checks on active enrollments
            for enrollment in student.get_active_enrollments():
                total = enrollment.total_amount or 0
                expected = total - (total * enrollment.discount_percent / 100) - enrollment.discount_amount
                net = enrollment.net_amount if enrollment.net_amount is not None else total
                if round(expected, 2) != round(net, 2):
                    student_issues.append(f'⚠️ عدم توافق الحسم في دورة {enrollment.course.name}')
                # Journal entry posting status
                je = getattr(enrollment, 'enrollment_journal_entry', None)
                if je and not getattr(je, "is_posted", True):
                    student_issues.append(f'⚠️ قيد التسجيل غير منشور لدورة {enrollment.course.name}')
            if not student_issues:
                student_issues.append('✅ لا توجد مشاكل')
            issues.append({'student': student, 'issues': student_issues})
        context['accounting_issues'] = issues
        return context

class StudentListView(LoginRequiredMixin, TemplateView):
    template_name = 'students/student_list.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # 🔍 البحث عن الطلاب إذا كان هناك معايير بحث
        search_query = (self.request.GET.get('q', '') or '').strip()
        search_name = (self.request.GET.get('name', '') or '').strip()
        search_number = (self.request.GET.get('student_number', '') or '').strip()
        search_phone = (self.request.GET.get('phone', '') or '').strip()
        
        academic_year_id = self.request.GET.get('academic_year')
        current_year = getattr(self.request, 'current_academic_year', None)
        if current_year:
            academic_year_id = str(current_year.id)
        elif academic_year_id is None:
            academic_year_id = '0'
        branch_filter = self.request.GET.get('branch')
        type_filter = self.request.GET.get('type')
        show_all_students = search_query.lower() == 'all'
        
        students_list = []
        is_searching = show_all_students or search_query or search_name or search_number or search_phone or (academic_year_id and academic_year_id != '0') or branch_filter or type_filter
        
        # إذا كان هناك بحث، جلب النتائج
        if is_searching:
            # البحث في الطلاب النظاميين
            regular_students = _scope_queryset_to_current_year(Student.objects.filter(quick_student_profile__isnull=True), self.request).select_related('academic_year', 'added_by')
            
            # تطبيق الفلاتر
            if not show_all_students:
                if search_query:
                    regular_students = regular_students.filter(
                        Q(full_name__icontains=search_query) |
                        Q(student_number__icontains=search_query) |
                        Q(phone__icontains=search_query) |
                        Q(email__icontains=search_query) |
                        Q(father_phone__icontains=search_query)
                    )
                if search_name:
                    regular_students = regular_students.filter(full_name__icontains=search_name)
                if search_number:
                    regular_students = regular_students.filter(student_number__icontains=search_number)
                if search_phone:
                    regular_students = regular_students.filter(
                        Q(phone__icontains=search_phone) |
                        Q(father_phone__icontains=search_phone)
                    )
            
            if academic_year_id and academic_year_id != '0':
                regular_students = regular_students.filter(academic_year_id=academic_year_id)
            
            if branch_filter and branch_filter != '':
                regular_students = regular_students.filter(branch=branch_filter)
            
            if type_filter == 'regular':
                # فقط النظاميين
                pass
            elif type_filter == 'quick':
                # فقط السريعين - سنضيفهم لاحقاً
                regular_students = regular_students.none()
            
            regular_students = regular_students.order_by('full_name', 'id')
            
            # إعداد بيانات العرض
            for student in regular_students:
                student.is_quick = False
                student.student_type_display = 'نظامي'
                student.academic_year_display = student.academic_year.name if student.academic_year else "-"
                student.display_phone = student.get_display_phone()
                student.display_status = student.get_status_for_display()
                student.status_badge_class = student.get_status_badge_class()
                student.profile_url = reverse('students:student_profile', kwargs={'student_id': student.id})
                students_list.append(student)
            
            # 🔥 البحث في الطلاب السريعين إذا كان النوع "quick" أو "all"
            if type_filter != 'regular':
                try:
                    from quick.models import QuickStudent
                    quick_students = _scope_queryset_to_current_year(QuickStudent.objects.filter(is_active=True), self.request).select_related('academic_year')
                    
                    if not show_all_students:
                        if search_query:
                            quick_students = quick_students.filter(
                                Q(full_name__icontains=search_query) |
                                Q(phone__icontains=search_query)
                            )
                        if search_name:
                            quick_students = quick_students.filter(full_name__icontains=search_name)
                        if search_phone:
                            quick_students = quick_students.filter(phone__icontains=search_phone)
                        if search_number:
                            # الطلاب السريعون ليس لديهم رقم طالب بالعادة
                            quick_students = quick_students.filter(id=-1)
                    
                    if academic_year_id and academic_year_id != '0':
                        quick_students = quick_students.filter(academic_year_id=academic_year_id)
 
                    if branch_filter and branch_filter != '':
                        quick_students = quick_students.none()
 
                    quick_students = quick_students.order_by('full_name', 'id')
                    
                    for student in quick_students:
                        student.is_quick = True
                        student.student_type_display = 'سريع'
                        student.academic_year_display = student.academic_year.name if student.academic_year else "-"
                        student.display_phone = student.phone if student.phone else "-"
                        student.branch = ''
                        student.profile_url = reverse('quick:student_profile', kwargs={'student_id': student.id})
                        student.display_status = 'نشط' if student.is_active else 'غير نشط'
                        student.status_badge_class = 'badge-success' if student.is_active else 'badge-danger'
                        students_list.append(student)
                        
                except ImportError:
                    pass
 
            students_list.sort(
                key=lambda student: (
                    getattr(student, 'full_name', '') or '',
                    1 if getattr(student, 'is_quick', False) else 0,
                    getattr(student, 'id', 0),
                )
            )
        
        context['search_results'] = students_list
        context['has_search_results'] = len(students_list) > 0
        context['search_query'] = '' if show_all_students else search_query
        context['search_name'] = search_name
        context['search_number'] = search_number
        context['search_phone'] = search_phone
        context['current_filters'] = {
            'academic_year': academic_year_id,
            'branch': branch_filter,
            'type': type_filter,
            'name': search_name,
            'student_number': search_number,
            'phone': search_phone,
        }
        
        # الإحصائيات الحالية (الكود الأصلي)
        if current_year:
            context['students_count'] = Student.objects.filter(academic_year=current_year).count()
        else:
            context['students_count'] = Student.objects.count()
        
        try:
            from quick.models import AcademicYear, QuickStudent
            
            academic_years = AcademicYear.objects.all().order_by('-start_date')
            context['academic_years'] = academic_years
            
            # ... باقي كود الإحصائيات الأصلي
            academic_year_stats = {}
            academic_year_regular_stats = {}
            academic_year_quick_stats = {}
            
            for year in academic_years:
                regular_count = Student.objects.filter(academic_year=year).count()
                    
                try:
                    quick_count = QuickStudent.objects.filter(
                        academic_year=year,
                        is_active=True
                    ).count()
                except:
                    quick_count = 0
                
                academic_year_stats[year.id] = regular_count + quick_count
                academic_year_regular_stats[year.id] = regular_count
                academic_year_quick_stats[year.id] = quick_count
            
            context['academic_year_stats'] = academic_year_stats
            context['academic_year_regular_stats'] = academic_year_regular_stats
            context['academic_year_quick_stats'] = academic_year_quick_stats
            
            branch_stats = []
            for year in academic_years:
                branches = Student.objects.exclude(
                    branch__isnull=True
                ).exclude(
                    branch__exact=''
                ).filter(
                    academic_year=year
                ).values('branch').annotate(
                    regular_count=Count('id')
                ).filter(regular_count__gt=0)
                
                for branch in branches:
                    branch_stats.append({
                        'name': branch['branch'],
                        'regular_count': branch['regular_count'],
                        'academic_year_id': year.id
                    })
            
            context['branch_stats'] = branch_stats
            
        except ImportError:
            context['academic_years'] = []
            context['academic_year_stats'] = {}
            context['academic_year_regular_stats'] = {}
            context['academic_year_quick_stats'] = {}
            context['branch_stats'] = []
        
        return context


class StudentCardsPrintView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'students/student_cards_print.html'
    app_download_url = 'https://yaman2.pythonanywhere.com/'

    def test_func(self):
        return self.request.user.is_superuser

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        should_generate = self.request.GET.get('generate') == '1'
        student_ids_raw = self.request.GET.get('student_ids')
        classroom_id = (self.request.GET.get('classroom') or '').strip()
        students = []
        selected_classroom = None

        if should_generate:
            if student_ids_raw:
                try:
                    id_list = [int(x.replace('.', '').replace(',', '').strip()) for x in student_ids_raw.split(',') if x.replace('.', '').replace(',', '').strip().isdigit()]
                    students = list(Student.objects.filter(id__in=id_list).order_by('full_name'))
                except Exception:
                    students = []
            elif classroom_id:
                try:
                    selected_classroom = Classroom.objects.get(id=classroom_id)
                    students = list(_scope_queryset_to_current_year(selected_classroom.students, self.request).order_by('full_name'))
                except Classroom.DoesNotExist:
                    students = []
            else:
                students = list(
                    _scope_queryset_to_current_year(Student.objects.all(), self.request).order_by('full_name')
                )

        per_page = 8
        pages = [students[i:i + per_page] for i in range(0, len(students), per_page)]
        if should_generate and not pages:
            pages = [[]]

        classrooms = list(
            Classroom.objects.filter(is_active=True, class_type='study').order_by('name')
        )

        classrooms_with_course = []
        for classroom in classrooms:
            course_name = classroom.course.name if getattr(classroom, 'course', None) else 'دورة'
            classrooms_with_course.append({
                'id': classroom.id,
                'name': classroom.name,
                'course_name': course_name,
            })

        all_students = []
        if not should_generate:
            all_students = list(
                _scope_queryset_to_current_year(Student.objects.all(), self.request)
                .prefetch_related('classroom_enrollments__classroom')
                .order_by('full_name')
            )

        context.update({
            'should_generate': should_generate,
            'pages': pages,
            'students_total': len(students),
            'app_download_url': self.app_download_url,
            'app_qr_url': f"https://api.qrserver.com/v1/create-qr-code/?size=180x180&data={quote(self.app_download_url)}",
            'classrooms': classrooms,
            'classrooms_with_course': classrooms_with_course,
            'selected_classroom': selected_classroom,
            'all_students': all_students,
            'pdf': False,
        })
        return context


def _cards_pdf_link_callback(uri, rel):
    if uri.startswith('http://') or uri.startswith('https://'):
        return uri

    if uri.startswith(settings.MEDIA_URL):
        path = os.path.join(settings.MEDIA_ROOT, uri.replace(settings.MEDIA_URL, ''))
    elif uri.startswith(settings.STATIC_URL):
        path = finders.find(uri.replace(settings.STATIC_URL, ''))
    else:
        path = finders.find(uri)

    if not path:
        return uri

    if isinstance(path, (list, tuple)):
        path = path[0]
    return path


def _register_pdf_fonts():
    try:
        font_regular = finders.find('font/Cairo-400.ttf')
        font_bold = finders.find('font/Cairo-600.ttf') or font_regular
        font_black = finders.find('font/Cairo-800.ttf') or font_bold or font_regular

        if font_regular:
            pdfmetrics.registerFont(TTFont('Cairo', font_regular))
        if font_bold and font_bold != font_regular:
            pdfmetrics.registerFont(TTFont('Cairo-Bold', font_bold))
        if font_black and font_black not in (font_regular, font_bold):
            pdfmetrics.registerFont(TTFont('Cairo-Black', font_black))

        if font_regular:
            registerFontFamily(
                'Cairo',
                normal='Cairo',
                bold='Cairo-Bold' if font_bold else 'Cairo',
                italic='Cairo',
                boldItalic='Cairo-Bold' if font_bold else 'Cairo',
            )
    except Exception:
        # Fallback to default fonts if registration fails.
        pass


def _weasyprint_url_fetcher(url):
    if not default_url_fetcher:
        return None

    if url.startswith(settings.STATIC_URL):
        path = finders.find(url.replace(settings.STATIC_URL, ''))
    elif url.startswith(settings.MEDIA_URL):
        path = os.path.join(settings.MEDIA_ROOT, url.replace(settings.MEDIA_URL, ''))
    else:
        return default_url_fetcher(url)

    if not path:
        return default_url_fetcher(url)

    if isinstance(path, (list, tuple)):
        path = path[0]

    return default_url_fetcher(f'file://{path}')


def _inline_css_vars(html):
    css_vars = {
        'ink': '#0e1424',
        'muted': '#9fa6b6',
        'paper': '#ffffff',
        'line': '#d8e0ef',
        'purple': '#513996',
        'purple-dark': '#4f2f86',
        'purple-light': '#6b4aa7',
        'gold': '#f0a22b',
        'teal': '#0b6c8e',
        'grid': 'rgba(255, 255, 255, 0.08)',
        'card-width': '100mm',
        'card-height': '60mm',
    }

    for key, value in css_vars.items():
        html = html.replace(f'var(--{key})', value)
    return html


def _render_cards_pdf_bytes(request, students):
    per_page = 8
    pages = [students[i:i + per_page] for i in range(0, len(students), per_page)]
    if not pages:
        pages = [[]]

    app_download_url = 'https://expo.dev/artifacts/eas/fu5Voe8s6PSZcG6syBbbZQ.apk'
    context = {
        'should_generate': True,
        'pages': pages,
        'students_total': len(students),
        'app_download_url': app_download_url,
        'app_qr_url': f"https://api.qrserver.com/v1/create-qr-code/?size=180x180&data={quote(app_download_url)}",
        'classrooms': list(Classroom.objects.filter(is_active=True, class_type='study').order_by('name')),
        'pdf': True,
    }

    html = render_to_string('students/student_cards_print.html', context, request=request)

    if WEASYPRINT_AVAILABLE:
        return HTML(
            string=html,
            base_url=request.build_absolute_uri('/'),
            url_fetcher=_weasyprint_url_fetcher,
        ).write_pdf()

    _register_pdf_fonts()
    html = _inline_css_vars(html)
    out = io.BytesIO()
    pisa.CreatePDF(html, dest=out, link_callback=_cards_pdf_link_callback, encoding='UTF-8')
    return out.getvalue()


@login_required
@user_passes_test(lambda u: u.is_superuser)
def student_cards_print_pdf(request):
    should_generate = request.GET.get('generate') == '1'
    student_ids_raw = request.GET.get('student_ids')
    students = []

    if should_generate:
        if student_ids_raw:
            try:
                id_list = [int(x.replace('.', '').replace(',', '').strip()) for x in student_ids_raw.split(',') if x.replace('.', '').replace(',', '').strip().isdigit()]
                students = list(Student.objects.filter(id__in=id_list).order_by('full_name'))
            except Exception:
                students = []
        else:
            students = list(_scope_queryset_to_current_year(Student.objects.all(), request).order_by('full_name'))

    per_page = 8
    pages = [students[i:i + per_page] for i in range(0, len(students), per_page)]
    if should_generate and not pages:
        pages = [[]]

    app_download_url = 'https://expo.dev/artifacts/eas/fu5Voe8s6PSZcG6syBbbZQ.apk'
    context = {
        'should_generate': should_generate,
        'pages': pages,
        'students_total': len(students),
        'app_download_url': app_download_url,
        'app_qr_url': f"https://api.qrserver.com/v1/create-qr-code/?size=180x180&data={quote(app_download_url)}",
        'classrooms': list(Classroom.objects.filter(is_active=True, class_type='study').order_by('name')),
        'pdf': True,
    }

    html = render_to_string('students/student_cards_print.html', context, request=request)
    tmp_dir = os.path.join(settings.BASE_DIR, '_tmp_pdf')
    os.makedirs(tmp_dir, exist_ok=True)
    os.environ['TMP'] = tmp_dir
    os.environ['TEMP'] = tmp_dir
    tempfile.tempdir = tmp_dir

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename=\"student_cards.pdf\"'

    if WEASYPRINT_AVAILABLE:
        pdf_bytes = HTML(
            string=html,
            base_url=request.build_absolute_uri('/'),
            url_fetcher=_weasyprint_url_fetcher,
        ).write_pdf()
        response.write(pdf_bytes)
        return response

    _register_pdf_fonts()
    html = _inline_css_vars(html)
    pisa.CreatePDF(html, dest=response, link_callback=_cards_pdf_link_callback, encoding='UTF-8')
    return response


@login_required
@user_passes_test(lambda u: u.is_superuser)
def student_cards_print_pdf_by_branch(request):
    should_generate = request.GET.get('generate') == '1'
    if not should_generate:
        return HttpResponseForbidden('Missing generate=1')

    branch_param = (request.GET.get('branch') or '').strip()
    students_qs = _scope_queryset_to_current_year(Student.objects.all(), request).order_by('branch', 'full_name')

    if branch_param:
        branch_choices = dict(Student.Academic_Track.choices)
        label_to_value = {label: value for value, label in Student.Academic_Track.choices}
        branch_value = branch_choices.get(branch_param) or label_to_value.get(branch_param) or branch_param
        students_qs = students_qs.filter(branch=branch_value)

    students = list(students_qs)
    if not students:
        return HttpResponseForbidden('No students found')

    branch_map = defaultdict(list)
    for student in students:
        key = (student.branch or 'unknown', student.get_branch_display() if student.branch else 'غير محدد')
        branch_map[key].append(student)

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        for (branch_key, branch_label), branch_students in branch_map.items():
            pdf_bytes = _render_cards_pdf_bytes(request, branch_students)
            safe_name = re.sub(r'[^0-9A-Za-z\u0600-\u06FF_-]+', '_', branch_label).strip('_') or branch_key
            filename = f'student_cards_{safe_name}.pdf'
            zf.writestr(filename, pdf_bytes)

    zip_buffer.seek(0)
    response = HttpResponse(zip_buffer.getvalue(), content_type='application/zip')
    response['Content-Disposition'] = 'attachment; filename=\"student_cards_by_branch.zip\"'
    return response


@login_required
@user_passes_test(lambda u: u.is_superuser)
def student_cards_print_pdf_by_classroom(request):
    should_generate = request.GET.get('generate') == '1'
    classroom_id = (request.GET.get('classroom') or '').strip()
    if not should_generate:
        return HttpResponseForbidden('Missing generate=1')
    if not classroom_id:
        return HttpResponseForbidden('Missing classroom')

    classroom = get_object_or_404(Classroom, id=classroom_id)
    students = list(_scope_queryset_to_current_year(classroom.students, request).order_by('full_name'))
    if not students:
        return HttpResponseForbidden('No students found for classroom')

    pdf_bytes = _render_cards_pdf_bytes(request, students)
    safe_name = re.sub(r'[^0-9A-Za-z\u0600-\u06FF_-]+', '_', classroom.name).strip('_') or f'classroom_{classroom.id}'
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename=\"student_cards_{safe_name}.pdf\"'
    return response

class BranchStudentsView(LoginRequiredMixin, ListView):
    """عرض طلاب فرع معين - بدون ترقيم"""
    template_name = 'students/branch_students.html'
    context_object_name = 'students'
    paginate_by = None
    
    def get_queryset(self):
        academic_year_id = self.kwargs.get('academic_year_id')
        branch_name = self.kwargs.get('branch_name')
        
        # جلب الطلاب النظاميين للفرع المحدد
        queryset = Student.objects.filter(quick_student_profile__isnull=True).select_related('academic_year', 'added_by')
        
        # عزل البيانات بالفصل الدراسي النشط
        queryset = _scope_queryset_to_current_year(queryset, self.request)
        
        # فلترة حسب الفرع
        if branch_name and branch_name != '0':
            queryset = queryset.filter(branch=branch_name)
        
        # فلترة حسب الفصل الدراسي
        if academic_year_id and academic_year_id != '0':
            try:
                from quick.models import AcademicYear
                academic_year = AcademicYear.objects.get(id=academic_year_id)
                queryset = queryset.filter(academic_year=academic_year)
            except AcademicYear.DoesNotExist:
                pass
        
        # إضافة بيانات إضافية للعرض - نفس منطق البروفايل
        for student in queryset:
            student.display_phone = student.get_display_phone()
            student.display_status = student.get_status_for_display()
            student.status_badge_class = student.get_status_badge_class()
            student.academic_year_display = student.academic_year.name if student.academic_year else "-"
        
        return queryset.order_by('full_name')

class AllRegularStudentsView(LoginRequiredMixin, ListView):
    """عرض جميع الطلاب النظاميين - بدون ترقيم"""
    template_name = 'students/all_regular_students.html'
    context_object_name = 'students'
    paginate_by = None
    
    def get_queryset(self):
        academic_year_id = self.request.GET.get('academic_year') or self.kwargs.get('academic_year_id')
        
        # جلب الطلاب النظاميين
        queryset = Student.objects.filter(quick_student_profile__isnull=True).select_related('academic_year', 'added_by')
        
        # عزل البيانات بالفصل الدراسي النشط
        queryset = _scope_queryset_to_current_year(queryset, self.request)
        
        # فلترة حسب الفصل الدراسي إذا كان محدداً
        if academic_year_id and str(academic_year_id) != '0':
            try:
                from quick.models import AcademicYear
                academic_year = AcademicYear.objects.get(id=academic_year_id)
                queryset = queryset.filter(academic_year=academic_year)
            except AcademicYear.DoesNotExist:
                pass
        
        # إضافة بيانات إضافية للعرض - نفس منطق البروفايل
        for student in queryset:
            student.display_phone = student.get_display_phone()
            student.display_status = student.get_status_for_display()
            student.status_badge_class = student.get_status_badge_class()
            student.academic_year_display = student.academic_year.name if student.academic_year else "-"
        
        return queryset.order_by('full_name')
    
class QuickStudentsAllView(LoginRequiredMixin, ListView):
    """عرض جميع الطلاب السريعين"""
    template_name = 'students/quick_students.html'
    context_object_name = 'students'
    
    def get_queryset(self):
        try:
            from quick.models import QuickStudent
            
            # جلب جميع الطلاب السريعين
            quick_students = QuickStudent.objects.filter(is_active=True).select_related('academic_year')
            
            # عزل البيانات بالفصل الدراسي النشط
            quick_students = _scope_queryset_to_current_year(quick_students, self.request)
            
            # إضافة معلومات للعرض
            for student in quick_students:
                student.is_quick = True
                student.student_type_display = 'سريع'
                student.academic_year_display = student.academic_year.name if student.academic_year else "-"
            
            return quick_students
            
        except ImportError:
            return []
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['academic_year_id'] = None  # لأننا نعرض جميع الطلاب السريعين
        return context
class QuickStudentsView(LoginRequiredMixin, ListView):
    """عرض الطلاب السريعين لدورة معينة"""
    template_name = 'students/quick_students.html'
    context_object_name = 'students'
    paginate_by = None  # ✅ إزالة الترقيم
    
    def get_queryset(self):
        academic_year_id = self.kwargs.get('academic_year_id')
        course_id = self.kwargs.get('course_id')
        
        try:
            from quick.models import QuickStudent, QuickCourse
            
            # جلب الطلاب السريعين
            quick_students = QuickStudent.objects.filter(is_active=True).select_related('academic_year')
            
            # عزل البيانات بالفصل الدراسي النشط
            quick_students = _scope_queryset_to_current_year(quick_students, self.request)
            
            # فلترة حسب الفصل الدراسي
            if academic_year_id:
                quick_students = quick_students.filter(academic_year_id=academic_year_id)
            
            # فلترة حسب الدورة
            if course_id:
                quick_students = quick_students.filter(
                    enrollments__course_id=course_id,
                    enrollments__is_completed=False
                ).distinct()
            
            # إضافة معلومات للعرض
            for student in quick_students:
                student.is_quick = True
                student.student_type_display = 'سريع'
                student.academic_year_display = student.academic_year.name if student.academic_year else "-"
            
            return quick_students
            
        except ImportError:
            return []
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['academic_year_id'] = self.kwargs.get('academic_year_id')
        context['course_id'] = self.kwargs.get('course_id')
        
        # جلب معلومات الفصل الدراسي والدورة إذا كانت موجودة
        try:
            from quick.models import AcademicYear, QuickCourse
            
            if context['academic_year_id']:
                academic_year = get_object_or_404(AcademicYear, id=context['academic_year_id'])
                context['academic_year'] = academic_year
            
            if context['course_id']:
                course = get_object_or_404(QuickCourse, id=context['course_id'])
                context['course'] = course
                
        except:
            context['academic_year'] = None
            context['course'] = None
        
        return context

class StudentSearchView(LoginRequiredMixin, ListView):
    """صفحة البحث عن الطلاب - نسخة محسنة"""
    template_name = 'students/student_search.html'
    context_object_name = 'students'
    paginate_by = 50
    
    def get_queryset(self):
        search_query = self.request.GET.get('q', '')
        academic_year_id = self.request.GET.get('academic_year')
        current_year = getattr(self.request, 'current_academic_year', None)
        if current_year:
            academic_year_id = str(current_year.id)
        elif academic_year_id is None:
            academic_year_id = '0'
        
        students_list = []
        
        # ✅ الإصلاح: إذا كان هناك academic_year بدون search_query، نعرض جميع الطلاب
        if academic_year_id and not search_query.strip():
            # عرض جميع الطلاب النظاميين للفصل المحدد
            from quick.models import AcademicYear
            try:
                academic_year = AcademicYear.objects.get(id=academic_year_id)
                regular_students = _scope_queryset_to_current_year(Student.objects.filter(quick_student_profile__isnull=True), self.request).select_related('added_by').order_by('full_name')
                if academic_year_id and academic_year_id != '0':
                    regular_students = regular_students.filter(academic_year_id=academic_year_id)
                
                for student in regular_students:
                    student.is_quick = False
                    student.student_type_display = 'نظامي'
                    student.academic_year_display = student.academic_year.name if student.academic_year else "-"
                    students_list.append(student)
                    
                print(f"✅ [DEBUG] عرض جميع الطلاب النظاميين للفصل {academic_year.name}: {len(students_list)} طالب")
                
            except AcademicYear.DoesNotExist:
                pass
        
        # البحث العادي إذا كان هناك search_query
        elif search_query.strip():
            # البحث في الطلاب النظاميين
            regular_students = _scope_queryset_to_current_year(Student.objects.filter(quick_student_profile__isnull=True), self.request).filter(
                Q(full_name__icontains=search_query) |
                Q(student_number__icontains=search_query) |
                Q(phone__icontains=search_query) |
                Q(email__icontains=search_query) |
                Q(father_phone__icontains=search_query)
            ).select_related('added_by').order_by('full_name')
            
            # فلترة حسب الفصل الدراسي إذا كان محدداً
            if academic_year_id and academic_year_id != '0':
                regular_students = regular_students.filter(academic_year_id=academic_year_id)
            
            for student in regular_students:
                student.is_quick = False
                student.student_type_display = 'نظامي'
                student.academic_year_display = student.academic_year.name if student.academic_year else "-"
                students_list.append(student)
        
        return students_list
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('q', '')
        academic_year_id = self.request.GET.get('academic_year')
        current_year = getattr(self.request, 'current_academic_year', None)
        if current_year:
            academic_year_id = str(current_year.id)
        elif academic_year_id is None:
            academic_year_id = '0'
        context['academic_year_id'] = academic_year_id
        
        # جلب معلومات الفصل الدراسي إذا كان محدداً
        if context['academic_year_id'] and context['academic_year_id'] != '0':
            try:
                from quick.models import AcademicYear
                academic_year = AcademicYear.objects.get(id=context['academic_year_id'])
                context['academic_year'] = academic_year
                context['academic_year_name'] = academic_year.name
            except AcademicYear.DoesNotExist:
                context['academic_year'] = None
                context['academic_year_name'] = "غير محدد"
        
        return context
    
class DeactivateStudentView(LoginRequiredMixin, UpdateView):
    model = Student
    fields = ['is_active']
    template_name = 'students/deactivate_student.html'
    success_url = reverse_lazy('students:student')
    
    def form_valid(self, form):
        form.instance.is_active = False
        response = super().form_valid(form)
        messages.success(self.request, 'تم إلغاء تفعيل الطالب بنجاح')
        return response

class StudentGroupsView(LoginRequiredMixin, TemplateView):
    template_name = 'students/student_groups.html'

class examssView(LoginRequiredMixin, TemplateView):
    template_name = 'students/examss.html'
    
class CoursesView(LoginRequiredMixin, TemplateView):
    template_name = 'students/courses.html'
    
class CreateStudentView(LoginRequiredMixin, CreateView):
    model = Student
    form_class = StudentForm
    template_name = 'students/create_student.html'
    success_url = reverse_lazy('students:student')
    
    def form_valid(self, form):
        form.instance.added_by = self.request.user
        current_year = getattr(self.request, 'current_academic_year', None)
        if current_year:
            form.instance.academic_year = current_year
        
        response = super().form_valid(form)
        
        # رسالة تأكيد مع اسم الفصل الدراسي
        academic_year_name = self.object.academic_year.name if self.object.academic_year else "لم يتم التعيين"
        messages.success(self.request, f'تم إضافة الطالب بنجاح - الفصل: {academic_year_name}')
        return response
    
def _get_student_receipts_queryset(student):
    return StudentReceipt.objects.filter(
        Q(student_profile=student) | Q(student=student) | Q(enrollment__student=student)
    ).distinct()


def _get_student_related_accounts(student):
    account_ids = set()

    if student.account_id:
        account_ids.add(student.account_id)

    for enrollment in Studentenrollment.objects.filter(student=student).select_related('course'):
        try:
            account = Account.get_student_ar_account_for_course(student, enrollment.course)
        except Exception:
            account = None
        if account:
            account_ids.add(account.id)

    if not account_ids:
        return Account.objects.none()

    return Account.objects.filter(id__in=account_ids)


def _get_student_related_journal_entries(student):
    receipt_entry_ids = _get_student_receipts_queryset(student).exclude(
        journal_entry__isnull=True
    ).values_list('journal_entry_id', flat=True)

    enrollment_entry_ids = Studentenrollment.objects.filter(student=student).values_list(
        'enrollment_journal_entry_id', flat=True
    )
    completion_entry_ids = Studentenrollment.objects.filter(student=student).values_list(
        'completion_journal_entry_id', flat=True
    )

    account_entry_ids = Transaction.objects.filter(
        account__in=_get_student_related_accounts(student)
    ).values_list('journal_entry_id', flat=True)

    entry_ids = {
        entry_id for entry_id in list(receipt_entry_ids) + list(enrollment_entry_ids) + list(completion_entry_ids) + list(account_entry_ids)
        if entry_id
    }

    if not entry_ids:
        return JournalEntry.objects.none()

    return JournalEntry.objects.filter(id__in=entry_ids).distinct()


def _get_student_delete_summary(student):
    enrollments_count = Studentenrollment.objects.filter(student=student).count()
    receipts_count = _get_student_receipts_queryset(student).count()
    journal_entries = _get_student_related_journal_entries(student)
    journal_entries_count = journal_entries.count()
    transactions_count = Transaction.objects.filter(journal_entry__in=journal_entries).count()
    related_accounts = list(_get_student_related_accounts(student).values_list('code', flat=True))

    return {
        'enrollments_count': enrollments_count,
        'receipts_count': receipts_count,
        'journal_entries_count': journal_entries_count,
        'transactions_count': transactions_count,
        'account_codes': related_accounts,
        'account_codes_display': '، '.join(related_accounts) if related_accounts else '-',
    }


def _delete_student_with_related_data(student):
    receipts = list(_get_student_receipts_queryset(student))
    enrollments = list(Studentenrollment.objects.filter(student=student))
    journal_entries = list(_get_student_related_journal_entries(student))
    related_accounts = list(_get_student_related_accounts(student))
    student_name = student.full_name

    with db_transaction.atomic():
        if receipts:
            StudentReceipt.objects.filter(id__in=[receipt.id for receipt in receipts]).delete()

        if journal_entries:
            JournalEntry.objects.filter(id__in=[entry.id for entry in journal_entries]).delete()

        if enrollments:
            Studentenrollment.objects.filter(id__in=[enrollment.id for enrollment in enrollments]).delete()

        student.delete()

        for account in related_accounts:
            if not Transaction.objects.filter(account=account).exists():
                account.delete()

    Account.rebuild_all_balances()
    return student_name


class StudentDeleteView(LoginRequiredMixin, View):
    def get_object(self):
        return get_object_or_404(Student, pk=self.kwargs['pk'])

    def get(self, request, *args, **kwargs):
        student = self.get_object()
        summary = _get_student_delete_summary(student)
        return JsonResponse({
            'success': True,
            'student_name': student.full_name,
            'summary': summary,
        })

    def _handle_delete(self, request):
        student = self.get_object()

        try:
            student_name = _delete_student_with_related_data(student)
        except ProtectedError:
            return JsonResponse({
                'success': False,
                'error': 'تعذر حذف الطالب لأن هناك بيانات محمية ما زالت مرتبطة به.',
            }, status=400)
        except Exception as exc:
            return JsonResponse({
                'success': False,
                'error': str(exc) or 'حدث خطأ غير متوقع أثناء حذف الطالب.',
            }, status=400)

        return JsonResponse({
            'success': True,
            'message': f'تم حذف الطالب "{student_name}" مع كل البيانات المرتبطة به.',
        })

    def post(self, request, *args, **kwargs):
        return self._handle_delete(request)

    def delete(self, request, *args, **kwargs):
        return self._handle_delete(request)
    
class UpdateStudentView(LoginRequiredMixin, UpdateView):
    model = Student
    form_class = StudentForm
    template_name = 'students/update_student.html'
    
    def get_success_url(self):
        # ✅ التصحيح: إرجاع رابط بروفايل الطالب بعد التعديل
        return reverse_lazy('students:student_profile', kwargs={'student_id': self.object.id})
    
    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, 'تم تعديل بيانات الطالب بنجاح')
        return response
    def form_invalid(self, form):
        student = self.get_object()
        updated = False

        for name, field in form.fields.items():
            if name == 'added_by':
                continue

            if name in self.request.FILES:
                try:
                    setattr(student, name, self.request.FILES[name])
                    updated = True
                except Exception:
                    pass
                continue

            if name not in self.request.POST:
                continue

            raw_value = self.request.POST.get(name)

            if raw_value in (None, ''):
                if isinstance(field, forms.ModelChoiceField):
                    setattr(student, name, None)
                    updated = True
                elif isinstance(field, (forms.CharField, forms.EmailField)):
                    setattr(student, name, '')
                    updated = True
                continue

            if isinstance(field, forms.ModelChoiceField):
                if raw_value in (None, ''):
                    setattr(student, name, None)
                    updated = True
                    continue
                try:
                    obj = field.queryset.filter(pk=raw_value).first()
                except Exception:
                    obj = None
                if obj is not None:
                    setattr(student, name, obj)
                    updated = True
                continue

            try:
                value = field.to_python(raw_value)
            except Exception:
                continue

            setattr(student, name, value)
            updated = True

        if updated:
            student.save()

        self.object = student

        messages.success(self.request, 'تم حفظ تعديل البيانات')
        return redirect(self.get_success_url())

    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # جلب الحسابات المالية المتاحة
        from accounts.models import Account
        context['available_accounts'] = Account.objects.filter(
            account_type='ASSET',  # أو أي فلتر مناسب
            is_active=True
        ).order_by('code')
        return context
    
    def get_success_url(self):
        return reverse_lazy('students:student_profile', kwargs={'student_id': self.object.id})

@require_POST
def update_student_discount(request, student_id):
    """تحديث حسم دورة محددة - اختيار الدورة ضروري"""
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'error': 'يجب تسجيل الدخول'})

    student = get_object_or_404(Student, id=student_id)

    try:
        from decimal import Decimal
        from django.db import transaction as db_transaction
        from accounts.models import Studentenrollment

        enrollment_id = request.POST.get('enrollment_id')
        if enrollment_id:
            enrollment_id = str(enrollment_id).replace('.', '').replace(',', '').strip()
        discount_percent = _parse_post_decimal(request.POST.get('discount_percent', '0'))
        discount_amount = _parse_post_decimal(request.POST.get('discount_amount', '0'))
        discount_reason = request.POST.get('discount_reason', '')

        if not enrollment_id:
            return JsonResponse({
                'success': False,
                'error': 'يجب اختيار الدورة المراد تعديل حسمها'
            })

        # التحقق من وجود التسجيل
        enrollment = Studentenrollment.objects.filter(
            id=enrollment_id,
            student=student,
            is_completed=False
        ).first()

        if not enrollment:
            return JsonResponse({
                'success': False,
                'error': 'لم يتم العثور على التسجيل'
            })

        print(f"تحديث حسم الدورة: {enrollment.course.name}")
        print(f"الحسم الجديد: {discount_percent}% / {discount_amount}")
        print(f"السبب: {discount_reason}")

        # تحديث حسم الدورة المحددة فقط
        student.update_enrollment_discount(
            enrollment,
            discount_percent,
            discount_amount,
            discount_reason,
            request.user
        )

        subjects_note = request.POST.get('subjects_note')
        if subjects_note is not None:
            enrollment.subjects_note = subjects_note.strip() or 'كامل المواد'
            enrollment.save(update_fields=['subjects_note'])

        return JsonResponse({
            'success': True,
            'message': f'تم تحديث الحسم للدورة {enrollment.course.name} بنجاح'
        })

    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"حدث خطأ في update_student_discount: {str(e)}")
        print(f"تفاصيل الخطأ: {error_details}")

        return JsonResponse({
            'success': False,
            'error': f'حدث خطأ: {str(e)}'
        })

@require_POST
@login_required
def update_enrollment_subjects(request, student_id):
    """تعديل المواد المسجلة للدورة المحددة"""
    student = get_object_or_404(Student, id=student_id)
    enrollment_id = request.POST.get('enrollment_id')
    if enrollment_id:
        enrollment_id = str(enrollment_id).replace('.', '').replace(',', '').strip()
    subjects_note = request.POST.get('subjects_note', 'كامل المواد')

    if not enrollment_id:
        return JsonResponse({
            'success': False,
            'error': 'لم يتم تحديد الدورة'
        })

    from accounts.models import Studentenrollment
    enrollment = Studentenrollment.objects.filter(
        id=enrollment_id,
        student=student,
        is_completed=False
    ).first()

    if not enrollment:
        return JsonResponse({
            'success': False,
            'error': 'التسجيل غير موجود'
        })

    enrollment.subjects_note = subjects_note.strip() or 'كامل المواد'
    enrollment.save(update_fields=['subjects_note'])

    return JsonResponse({
        'success': True,
        'message': f'تم تحديث المواد المسجلة للدورة {enrollment.course.name} بنجاح'
    })
    
class StudentNumbersView(LoginRequiredMixin, TemplateView):
    template_name = 'students/stunum.html'    
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        try:
            current_year = getattr(self.request, 'current_academic_year', None)
            qs = Student.objects.all()
            if current_year:
                qs = qs.filter(academic_year=current_year)
            context['students_count'] = qs.count()
            context['male_count'] = qs.filter(gender='male').count()
            context['female_count'] = qs.filter(gender='female').count()
            context['scientific_count'] = qs.filter(branch='علمي').count()
            context['literary_count'] = qs.filter(branch='أدبي').count()
            context['ninth_exams_count'] = qs.filter(branch='تاسع').count()
        except:
            context.update({
                'students_count': 0,
                'male_count': 0,
                'female_count': 0,
                'scientific_count': 0,
                'literary_count': 0,
                'ninth_exams_count': 0,
            })
        
        return context

@require_POST
def quick_receipt(request, student_id):
    """إنشاء إيصال فوري مع حساب المتبقي بشكل صحيح"""
    from decimal import Decimal
    from accounts.models import StudentReceipt, Course, Studentenrollment
    from django.db.models import Sum
    
    if not request.user.is_authenticated:
        return JsonResponse({'ok': False, 'error': 'يجب تسجيل الدخول'})
    
    student = get_object_or_404(Student, id=student_id)
    
    try:
        # Parse inputs
        course_id = request.POST.get('course_id')
        enrollment_id = request.POST.get('enrollment_id')
        
        # تنظيف معرفات الكورس والتسجيل من فواصل الآلاف المضافة بالتنسيق المحلي
        if course_id:
            course_id = str(course_id).replace('.', '').replace(',', '').strip()
        if enrollment_id:
            enrollment_id = str(enrollment_id).replace('.', '').replace(',', '').strip()
            
        amount = Decimal(request.POST.get('amount', '0'))
        paid_amount = Decimal(request.POST.get('paid_amount', '0'))
        discount_percent = Decimal(request.POST.get('discount_percent', str(student.discount_percent or 0)))
        discount_amount = Decimal(request.POST.get('discount_amount', str(student.discount_amount or 0)))
        is_free = str(request.POST.get('is_free', '')).lower() == 'true'
        receipt_date_str = request.POST.get('receipt_date')
        
        # معالجة تاريخ الإيصال
        if receipt_date_str:
            receipt_date = parse_date(receipt_date_str)
            if not receipt_date:
                return JsonResponse({'ok': False, 'error': 'صيغة التاريخ غير صحيحة'})
        else:
            receipt_date = timezone.now().date()
            
    except (ValueError, TypeError, InvalidOperation) as e:
        return JsonResponse({'ok': False, 'error': f'خطأ في تنسيق الأرقام: {str(e)}'})
    
    course = None
    remaining_amount = Decimal('0.00')
    enrollment = None
    enrollment_paid = Decimal('0.00')
    target_student = student
    
    try:
        if enrollment_id:
            # We first try to get the enrollment with the correct target student if we can find it
            enrollment = Studentenrollment.objects.filter(pk=enrollment_id).first()
            if enrollment:
                target_student = enrollment.student
            else:
                return JsonResponse({'ok': False, 'error': 'التسجيل غير موجود'})
            
            # ✅ الإصلاح: التحقق من أن التسجيل نشط
            if enrollment.is_completed:
                return JsonResponse({'ok': False, 'error': 'لا يمكن قطع إيصال لدورة مسحوبة'})
                
            course = enrollment.course
            
            if amount == 0 and not is_free:
                amount = enrollment.net_amount if enrollment.net_amount is not None else (enrollment.total_amount or Decimal('0.00'))
            
            # ✅ الإصلاح: حساب المتبقي بشكل صحيح
            total_paid = StudentReceipt.objects.filter(
                enrollment=enrollment
            ).aggregate(total=Sum('paid_amount'))['total'] or Decimal('0.00')
            enrollment_paid = total_paid
            
            net_amount = enrollment.net_amount if enrollment.net_amount is not None else (enrollment.total_amount or Decimal('0.00'))
            remaining_amount = max(Decimal('0.00'), net_amount - total_paid)
            
        elif course_id:
            course = Course.objects.get(pk=course_id)
            
            # --- NEW LOGIC FOR SEMESTER SEPARATION ---
            if course.academic_year and student.academic_year != course.academic_year:
                target_student = Student.objects.filter(
                    full_name=student.full_name,
                    academic_year=course.academic_year
                ).first()
                if not target_student:
                    target_student = Student.objects.create(
                        full_name=student.full_name,
                        email=student.email,
                        phone=student.phone,
                        gender=student.gender,
                        branch=student.branch,
                        birth_date=student.birth_date,
                        student_number=student.student_number,
                        nationality=student.nationality,
                        registration_date=receipt_date,
                        tase3=student.tase3,
                        disease=student.disease,
                        father_name=student.father_name,
                        father_job=student.father_job,
                        father_phone=student.father_phone,
                        mother_name=student.mother_name,
                        mother_job=student.mother_job,
                        mother_phone=student.mother_phone,
                        address=student.address,
                        home_phone=student.home_phone,
                        previous_school=student.previous_school,
                        elementary_school=student.elementary_school,
                        how_knew_us=student.how_knew_us,
                        notes=student.notes,
                        discount_percent=student.discount_percent,
                        discount_amount=student.discount_amount,
                        discount_reason=student.discount_reason,
                        tudent_type=student.tudent_type,
                        academic_level=student.academic_level,
                        registration_status=student.registration_status,
                        academic_year=course.academic_year,
                        added_by=request.user
                    )
            # ----------------------------------------
            
            if amount == 0 and not is_free:
                amount = course.price or Decimal('0.00')
                
            # البحث عن enrollment لهذه الدورة
            enrollment = Studentenrollment.objects.filter(
                student=target_student, 
                course=course,
                is_completed=False  # ✅ فقط التسجيلات النشطة
            ).first()
            
            if enrollment:
                # ✅ الإصلاح: حساب المتبقي بشكل صحيح
                total_paid = StudentReceipt.objects.filter(
                    enrollment=enrollment
                ).aggregate(total=Sum('paid_amount'))['total'] or Decimal('0.00')
                enrollment_paid = total_paid
                net_amount = enrollment.net_amount if enrollment.net_amount is not None else (enrollment.total_amount or Decimal('0.00'))
                remaining_amount = max(Decimal('0.00'), net_amount - total_paid)
            else:
                remaining_amount = course.price or Decimal('0.00')
                
    except (Studentenrollment.DoesNotExist, Course.DoesNotExist) as e:
        return JsonResponse({'ok': False, 'error': 'الدورة أو التسجيل غير موجود'})
    
    # السماح بدفع 0 ل.س (خصم 100%)
    if paid_amount < 0:
        return JsonResponse({'ok': False, 'error': 'المبلغ المدفوع غير صالح'})
    
    if is_free:
        amount = Decimal('0.00')
        paid_amount = Decimal('0.00')
        discount_percent = Decimal('0.00')
        discount_amount = Decimal('0.00')
        remaining_amount = Decimal('0.00')
        if enrollment:
            # ضبط إجمالي الدورة ليعكس المدفوع فقط (أو صفر) لتصفير المتبقي
            new_total = max(enrollment_paid, Decimal('0.00'))
            enrollment.total_amount = new_total
            enrollment.discount_percent = Decimal('0.00')
            enrollment.discount_amount = Decimal('0.00')
            enrollment.save(update_fields=['total_amount', 'discount_percent', 'discount_amount'])
    
    # ✅ الإصلاح: التأكد من أن المبلغ المدفوع لا يتجاوز المتبقي
    if paid_amount > remaining_amount:
        return JsonResponse({'ok': False, 'error': f'المبلغ المدفوع ({paid_amount}) يتجاوز المبلغ المتبقي ({remaining_amount})'})
    
    # Create receipt
    try:
        actual_student = enrollment.student if enrollment else target_student
        receipt = StudentReceipt.objects.create(
            date=receipt_date,
            student_profile=actual_student,
            student_name=actual_student.full_name,
            course=course,
            course_name=(course.name if course else ''),
            enrollment=enrollment,
            amount=amount,
            paid_amount=paid_amount,
            discount_percent=discount_percent,
            discount_amount=discount_amount,
            payment_method='CASH',
            created_by=request.user,
        )
    except Exception as e:
        return JsonResponse({'ok': False, 'error': f'فشل في إنشاء الإيصال: {str(e)}'})
    
    journal_warning = None
    try:
        # إنشاء القيد المحاسبي
        receipt.create_accrual_journal_entry(request.user)
    except Exception as e:
        journal_warning = f"خطأ في القيد المحاسبي: {e}"
    
    # ✅ الإصلاح: حساب المتبقي الجديد بشكل صحيح
    new_remaining_amount = Decimal('0.00') if is_free else max(Decimal('0.00'), remaining_amount - paid_amount)
    
    from django.urls import reverse
    print_url = reverse('accounts:student_receipt_print', args=[receipt.id])
    return JsonResponse({
        'ok': True, 
        'receipt_id': receipt.id, 
        'print_url': print_url,
        'remaining_amount': float(new_remaining_amount),
        'warning': journal_warning
    })

def register_course(request, student_id):
    from accounts.models import Course, Studentenrollment
    if not request.user.is_authenticated:
        return redirect('login')

    student = get_object_or_404(Student, pk=student_id)

    if request.method == 'POST':
        course_id = request.POST.get('course_id')
        enrollment_date_str = request.POST.get('enrollment_date')
        apply_discount = request.POST.get('apply_discount', 'false').lower() == 'true'

        if course_id:
            try:
                course = get_object_or_404(Course, pk=course_id)

                # معالجة تاريخ التسجيل
                if enrollment_date_str:
                    enrollment_date = parse_date(enrollment_date_str)
                    if not enrollment_date:
                        enrollment_date = timezone.now().date()
                else:
                    enrollment_date = timezone.now().date()

                # --- NEW LOGIC: Separate Profile Per Semester/Academic Year ---
                target_student = student
                if course.academic_year and student.academic_year != course.academic_year:
                    # Search for an existing profile of this student in the target academic year
                    target_student = Student.objects.filter(
                        full_name=student.full_name,
                        academic_year=course.academic_year
                    ).first()
                    
                    if not target_student:
                        # Clone/Copy student profile to the new academic year
                        target_student = Student.objects.create(
                            full_name=student.full_name,
                            email=student.email,
                            phone=student.phone,
                            gender=student.gender,
                            branch=student.branch,
                            birth_date=student.birth_date,
                            student_number=student.student_number,
                            nationality=student.nationality,
                            registration_date=enrollment_date,
                            tase3=student.tase3,
                            disease=student.disease,
                            father_name=student.father_name,
                            father_job=student.father_job,
                            father_phone=student.father_phone,
                            mother_name=student.mother_name,
                            mother_job=student.mother_job,
                            mother_phone=student.mother_phone,
                            address=student.address,
                            home_phone=student.home_phone,
                            previous_school=student.previous_school,
                            elementary_school=student.elementary_school,
                            how_knew_us=student.how_knew_us,
                            notes=student.notes,
                            discount_percent=student.discount_percent,
                            discount_amount=student.discount_amount,
                            discount_reason=student.discount_reason,
                            tudent_type=student.tudent_type,
                            academic_level=student.academic_level,
                            registration_status=student.registration_status,
                            academic_year=course.academic_year,
                            added_by=request.user
                        )
                        messages.info(request, f'تم إنشاء ملف تعريفي جديد للطالب في الفصل: {course.academic_year.name}')
                    else:
                        messages.info(request, f'تم ربط التسجيل بملف الطالب الحالي في الفصل: {course.academic_year.name}')
                # -------------------------------------------------------------

                # Check if student is already enrolled in this course
                existing_enrollment = Studentenrollment.objects.filter(
                    student=target_student,
                    course=course,
                    is_completed=False
                ).first()

                if existing_enrollment:
                    messages.warning(request, f'الطالب مسجل بالفعل في دورة {course.name}')
                else:
                    # Check if this is the first enrollment
                    is_first_enrollment = not Studentenrollment.objects.filter(
                        student=target_student,
                        is_completed=False
                    ).exists()

                    # Determine discount values
                    discount_percent = Decimal('0')
                    discount_amount = Decimal('0')
                    discount_reason = ''

                    if apply_discount:
                        discount_percent = _parse_post_decimal(request.POST.get('discount_percent', '0'))
                        discount_amount = _parse_post_decimal(request.POST.get('discount_amount', '0'))
                        discount_reason = request.POST.get('discount_reason', '') or 'حسم مطبق عند التسجيل'

                    # Determine enrolled subjects
                    subjects_choice = request.POST.get('subjects_choice', 'all')
                    if subjects_choice == 'custom':
                        subjects_note = request.POST.get('subjects_custom_text', '').strip() or 'كامل المواد'
                    else:
                        subjects_note = 'كامل المواد'

                    # Create new enrollment
                    enrollment = Studentenrollment.objects.create(
                        student=target_student,
                        course=course,
                        enrollment_date=enrollment_date,
                        total_amount=course.price,
                        discount_percent=discount_percent,
                        discount_amount=discount_amount,
                        discount_reason=discount_reason,
                        payment_method='CASH',
                        subjects_note=subjects_note
                    )

                    # Create enrollment journal entry
                    try:
                        enrollment.create_accrual_enrollment_entry(request.user)
                        discount_msg = ''
                        if apply_discount:
                            if discount_percent > 0 or discount_amount > 0:
                                discount_msg = f" مع حسم {discount_percent}% / {discount_amount}"
                        messages.success(request, f'تم تسجيل الطالب في دورة {course.name}{discount_msg} وإنشاء الحسابات بنجاح.')
                    except Exception as e:
                        messages.warning(request, f'تم التسجيل ولكن فشل في إنشاء القيد المحاسبي: {str(e)}')

            except Exception as e:
                messages.error(request, f'حدث خطأ في التسجيل: {str(e)}')
        else:
            messages.error(request, 'يجب اختيار دورة للتسجيل')

        return redirect('students:student_profile', student_id=target_student.id)

    # GET request - show registration form
    available_courses = _scope_queryset_to_current_year(Course.objects.filter(is_active=True), request).order_by('name')

    # Check if this is first enrollment
    is_first_enrollment = not Studentenrollment.objects.filter(
        student=student,
        is_completed=False
    ).exists()

    return render(request, 'students/register_course.html', {
        'student': student,
        'available_courses': available_courses,
        'is_first_enrollment': is_first_enrollment,
        'student_discount_percent': student.discount_percent or Decimal('0'),
        'student_discount_amount': student.discount_amount or Decimal('0'),
    })

# في students/views.py - استبدل دالة withdraw_student بهذا الكود
# في students/views.py - استبدل الدالة الحالية بهذا الكود الكامل
# في students/views.py - استبدل دالة withdraw_student بالكود الجديد
# في students/views.py - استبدل دالة withdraw_student بهذا الكود المعدل
# في students/views.py - استبدل دالة withdraw_student
# في students/views.py - استبدل الدالة كاملة
@require_POST
@login_required
def withdraw_student(request, student_id):
    """سحب الطالب - النسخة المضمونة"""
    print("\n" + "="*80)
    print("🚀🚀🚀 بدء عملية سحب الطالب - النسخة النهائية 🚀🚀🚀")
    print("="*80)
    
    try:
        # 1. طباعة جميع البيانات الواردة
        print("📋 البيانات الواردة من النموذج:")
        for key, value in request.POST.items():
            print(f"   {key}: {value}")
        
        # 2. جلب الطالب
        print("\n🔍 جلب بيانات الطالب...")
        student = Student.objects.get(id=student_id)
        print(f"✅ الطالب: {student.full_name}")
        
        # 3. جلب التسجيل
        enrollment_id = request.POST.get('enrollment_id')
        if enrollment_id:
            enrollment_id = str(enrollment_id).replace('.', '').replace(',', '').strip()
        print(f"📌 enrollment_id: {enrollment_id}")
        
        if not enrollment_id:
            messages.error(request, '❌ يجب اختيار دورة')
            return redirect('students:student_profile', student_id=student_id)
        
        enrollment = Studentenrollment.objects.get(id=enrollment_id, student=student)
        print(f"✅ التسجيل: {enrollment.course.name}")
        
        # 4. حساب المبالغ
        print("\n💰 حساب المبالغ...")
        total_paid = StudentReceipt.objects.filter(
            enrollment=enrollment
        ).aggregate(total=Sum('paid_amount'))['total'] or Decimal('0')
        print(f"💵 المبلغ المدفوع: {total_paid}")
        
        # 5. تحقق إذا كان المبلغ المدفوع صفر
        if total_paid == 0:
            print("⚠️ المبلغ المدفوع صفر - سيتم إنشاء قيد العكس فقط")
        
        # 6. المبلغ المسترد
        refund_amount = Decimal(request.POST.get('refund_amount', '0'))
        print(f"💰 المبلغ المسترد المدخل: {refund_amount}")
        
        # إذا كان صفر، اجعله يساوي المدفوع (استرداد كامل)
        if refund_amount == 0 and total_paid > 0:
            refund_amount = total_paid
            print(f"🔄 تعديل المبلغ المسترد ليكون: {refund_amount}")
        
        today = timezone.now().date()
        
        # 7. القيد الأول: استرداد النقدية - فقط إذا كان هناك استرداد
        if refund_amount > 0:
            print("\n" + "-"*50)
            print("🔹🔹🔹 إنشاء القيد الأول: استرداد النقدية 🔹🔹🔹")
            print("-"*50)
            
            try:
                # 7.1 البحث عن حساب 4201 - بدون get_or_create
                print("🔍 البحث عن حساب 4201...")
                account_4201 = Account.objects.filter(code='4201').first()
                
                if not account_4201:
                    print("❌ حساب 4201 غير موجود! سيتم إنشاؤه...")
                    # إنشاء الحساب الرئيسي أولاً
                    parent_account = Account.objects.filter(code='4200').first()
                    if not parent_account:
                        parent_account = Account.objects.create(
                            code='4200',
                            name='Other Revenues',
                            name_ar='إيرادات أخرى',
                            account_type='REVENUE',
                            is_active=True
                        )
                    
                    account_4201 = Account.objects.create(
                        code='4201',
                        name='Student Withdrawal Revenue',
                        name_ar='إيرادات انسحاب طلاب',
                        account_type='REVENUE',
                        is_active=True,
                        parent=parent_account,
                        description='إيرادات من سحب الطلاب'
                    )
                    print(f"✅ تم إنشاء حساب 4201 جديد (ID: {account_4201.id})")
                else:
                    print(f"✅ حساب 4201 موجود (ID: {account_4201.id})")
                
                # 7.2 البحث عن حساب 121
                cash_account = get_user_cash_account(request.user, fallback_code='121')
                print(f'Cash account for user: {cash_account.code}')

                # 7.3 إنشاء قيد اليومية
                print("📝 إنشاء قيد اليومية...")
                entry_data = {
                    'reference': f"WD-{enrollment.id}-{today.strftime('%Y%m%d')}",
                    'date': today,
                    'description': f"استرداد نقدي لسحب {student.full_name} من {enrollment.course.name}",
                    'entry_type': 'WITHDRAWAL',
                    'total_amount': refund_amount,
                    'created_by': request.user,
                    'is_posted': False
                }
                
                print(f"📋 بيانات القيد: {entry_data}")
                
                entry1 = JournalEntry.objects.create(**entry_data)
                print(f"🎉 تم إنشاء قيد اليومية بنجاح! (ID: {entry1.id})")
                
                # 7.4 إنشاء المعاملات
                print("🔧 إنشاء المعاملات...")
                
                # المعاملة الأولى: مدين - 4201
                txn1 = Transaction.objects.create(
                    journal_entry=entry1,
                    account=account_4201,
                    amount=refund_amount,
                    is_debit=True,
                    description=f"إيرادات سحب: {student.full_name} - {enrollment.course.name}"
                )
                print(f"✅ معاملة 1: مدين {account_4201.code} - {refund_amount}")
                
                # المعاملة الثانية: دائن - 121
                txn2 = Transaction.objects.create(
                    journal_entry=entry1,
                    account=cash_account,
                    amount=refund_amount,
                    is_debit=False,
                    description=f"استرداد نقدي: {student.full_name}"
                )
                print(f"✅ معاملة 2: دائن {cash_account.code} - {refund_amount}")
                
                # 7.5 التحقق من المعاملات
                transaction_count = Transaction.objects.filter(journal_entry=entry1).count()
                print(f"📊 عدد المعاملات في القيد: {transaction_count}")
                
                if transaction_count == 2:
                    print("✅ جميع المعاملات تم إنشاؤها بنجاح!")
                else:
                    print(f"⚠️ عدد المعاملات غير متوقع: {transaction_count}")
                
                # 7.6 ترحيل القيد
                print("📤 ترحيل القيد...")
                entry1.is_posted = True
                entry1.posted_by = request.user
                entry1.posted_at = timezone.now()
                entry1.save()
                print("✅ تم ترحيل القيد بنجاح!")
                
                messages.success(request, f'✅ تم إنشاء قيد استرداد {refund_amount:,.0f} ل.س')
                
            except Exception as e:
                print(f"❌ خطأ في إنشاء القيد الأول: {str(e)}")
                print("📋 تفاصيل الخطأ:")
                traceback.print_exc()
                messages.error(request, f'❌ خطأ في قيد الاسترداد: {str(e)}')
                return redirect('students:student_profile', student_id=student_id)
        
        # 8. القيد الثاني: عكس الإيرادات المؤجلة (إذا كان هناك مبلغ غير مدفوع)
        print("\n" + "-"*50)
        print("🔹🔹🔹 إنشاء القيد الثاني: عكس الإيرادات المؤجلة 🔹🔹🔹")
        print("-"*50)
        
        try:
            net_amount = enrollment.net_amount if enrollment.net_amount is not None else (enrollment.total_amount or Decimal('0'))
            unpaid_amount = max(Decimal('0'), net_amount - total_paid)
            
            if unpaid_amount > 0:
                print(f"💰 المبلغ غير المدفوع: {unpaid_amount}")
                
                # 8.1 حساب ذمة الطالب
                print("🔍 البحث عن حساب الطالب...")
                course = enrollment.course  # أضف هذا السطر
                student_account_code = f"1251-{course.id:03d}-{student.id:03d}"
                student_account = Account.objects.filter(code=student_account_code).first()
                
                if not student_account:
                    print(f"❌ حساب الطالب {student_account_code} غير موجود! سيتم إنشاؤه...")
                    student_account = Account.objects.create(
                        code=student_account_code,
                        name=f'AR - {student.full_name}',
                        name_ar=f'ذمم مدينة - {student.full_name}',
                        account_type='ASSET',
                        is_active=True
                    )
                    print(f"✅ تم إنشاء حساب الطالب (ID: {student_account.id})")
                
                # 8.2 حساب الإيرادات المؤجلة
                print("🔍 البحث عن حساب الإيرادات المؤجلة...")
                deferred_code = f"21001-{enrollment.course.id:03d}"
                deferred_account = Account.objects.filter(code=deferred_code).first()
                
                if not deferred_account:
                    print(f"❌ حساب الإيرادات المؤجلة {deferred_code} غير موجود! سيتم إنشاؤه...")
                    deferred_account = Account.objects.create(
                        code=deferred_code,
                        name=f'Deferred Revenue - {enrollment.course.name}',
                        name_ar=f'إيرادات مؤجلة - {enrollment.course.name}',
                        account_type= 'LIABILITY',  # ✅ صحيح
                        is_active=True
                    )
                    print(f"✅ تم إنشاء حساب الإيرادات المؤجلة (ID: {deferred_account.id})")
                
                # 8.3 إنشاء القيد
                entry2 = JournalEntry.objects.create(
                    reference=f"WD-REV-{enrollment.id}-{today.strftime('%Y%m%d')}",
                    date=today,
                    description=f"عكس إيرادات مؤجلة لسحب {student.full_name}",
                    entry_type='REVERSAL',
                    total_amount=unpaid_amount,
                    created_by=request.user,
                    is_posted=False
                )
                print(f"✅ تم إنشاء قيد العكس (ID: {entry2.id})")
                
                # 8.4 المعاملات
                # مدين: الإيرادات المؤجلة
                Transaction.objects.create(
                    journal_entry=entry2,
                    account=deferred_account,
                    amount=unpaid_amount,
                    is_debit=True,
                    description=f"عكس إيرادات مؤجلة - {student.full_name}"
                )
                
                # دائن: ذمة الطالب
                Transaction.objects.create(
                    journal_entry=entry2,
                    account=student_account,
                    amount=unpaid_amount,
                    is_debit=False,
                    description=f"تصفية ذمة - {enrollment.course.name}"
                )
                
                # 8.5 ترحيل القيد
                entry2.is_posted = True
                entry2.posted_by = request.user
                entry2.posted_at = timezone.now()
                entry2.save()
                
                messages.success(request, f'✅ تم إنشاء قيد عكس إيرادات {unpaid_amount:,.0f} ل.س')
            else:
                print("💰 لا يوجد مبلغ غير مدفوع - لا حاجة لقيد العكس")
                
        except Exception as e:
            print(f"⚠️ تحذير في القيد الثاني: {str(e)}")
            messages.warning(request, f'⚠️ ملاحظة: لم يتم إنشاء قيد العكس: {str(e)}')
        
        # 9. تحديث حالة التسجيل
        print("\n📝 تحديث حالة التسجيل...")
        enrollment.is_completed = True
        enrollment.completion_date = today
        enrollment.withdrawal_reason = request.POST.get('withdrawal_reason', '')
        enrollment.save()
        print("✅ تم تحديث حالة التسجيل")
        
        messages.success(request, f'✅ تم سحب الطالب {student.full_name} بنجاح')
        
        print("\n" + "="*80)
        print("🎉🎉🎉 عملية السحب اكتملت بنجاح! 🎉🎉🎉")
        print("="*80)
        
        return redirect('students:student_profile', student_id=student_id)
        
    except Exception as e:
        print(f"\n❌❌❌ خطأ عام في السحب: {str(e)} ❌❌❌")
        traceback.print_exc()
        messages.error(request, f'❌ حدث خطأ: {str(e)}')
        return redirect('students:student_profile', student_id=student_id)
        
def student_detail(request, student_id):
    student = get_object_or_404(Student, id=student_id)
    
    # ✅ الإصلاح: الحصول على التسجيلات النشطة فقط
    active_enrollments = Studentenrollment.objects.filter(
        student=student, 
        is_completed=False  # فقط التسجيلات النشطة
    ).select_related('course')
    
    # الحسابات المالية - ✅ الإصلاح: حساب المبالغ بشكل صحيح
    total_paid = Decimal('0.00')
    total_due = Decimal('0.00')
    
    for enrollment in active_enrollments:
        # حساب المبلغ المدفوع لكل تسجيل
        enrollment_total_paid = StudentReceipt.objects.filter(
            enrollment=enrollment
        ).aggregate(total=Sum('paid_amount'))['total'] or Decimal('0.00')
        
        enrollment_net_amount = enrollment.net_amount if enrollment.net_amount is not None else (enrollment.total_amount or Decimal('0.00'))
        
        total_paid += enrollment_total_paid
        total_due += enrollment_net_amount
    
    total_remaining = total_due - total_paid
    
    # الإيصالات
    receipts = StudentReceipt.objects.filter(student_profile=student).select_related('course')
    
    context = {
        'student': student,
        'active_enrollments': active_enrollments,
        'total_paid': total_paid,
        'total_due': total_due,
        'total_remaining': total_remaining,
        'receipts': receipts,
    }
    return render(request, 'students/student_detail.html', context)

# ✅ إزالة الدالة المكررة في النهاية - هذه هي المشكلة الرئيسية
# ================
# تم إزالة الدالة المكررة quick_receipt من هنا
# ================
@require_POST
def refund_student(request, student_id):
    """استرداد مبلغ - ينقص المدفوع ويزيد المطلوب"""
    if not request.user.is_authenticated:
        return JsonResponse({'ok': False, 'error': 'يجب تسجيل الدخول'}, status=401)
    
    student = get_object_or_404(Student, pk=student_id)
    
    try:
        enrollment_id = request.POST.get('enrollment_id')
        if enrollment_id:
            enrollment_id = str(enrollment_id).replace('.', '').replace(',', '').strip()
        refund_amount = Decimal(request.POST.get('refund_amount', '0'))
        refund_reason = request.POST.get('refund_reason', '')
        
        if not enrollment_id:
            return JsonResponse({'ok': False, 'error': 'لم يتم تحديد التسجيل'}, status=400)
        
        enrollment = get_object_or_404(Studentenrollment, pk=enrollment_id, student=student)
        
        if enrollment.is_completed:
            return JsonResponse({'ok': False, 'error': 'لا يمكن استرداد مبلغ لدورة مسحوبة'}, status=400)
        
        # حساب المبلغ المدفوع الحالي
        total_paid = StudentReceipt.objects.filter(
            enrollment=enrollment
        ).aggregate(total=Sum('paid_amount'))['total'] or Decimal('0')
        
        net_amount = enrollment.net_amount if enrollment.net_amount is not None else (enrollment.total_amount or Decimal('0.00'))
        current_balance = max(Decimal('0.00'), net_amount - total_paid)
        
        if refund_amount <= 0:
            return JsonResponse({'ok': False, 'error': 'المبلغ المسترد يجب أن يكون أكبر من الصفر'}, status=400)
        
        if refund_amount > total_paid:
            return JsonResponse({'ok': False, 'error': f'المبلغ المسترد ({refund_amount}) لا يمكن أن يكون أكبر من المبلغ المدفوع ({total_paid})'}, status=400)

        today = timezone.now().date()
        remaining_refund = refund_amount
        
        # ✅ البحث عن إيصالات هذا التسجيل من الأحدث للأقدم
        receipts = StudentReceipt.objects.filter(
            enrollment=enrollment
        ).order_by('-date', '-id')
        
        # ✅ تحديث الإيصالات القديمة
        for receipt in receipts:
            if remaining_refund <= 0:
                break
                
            # كم يمكننا الاسترداد من هذا الإيصال
            available_refund = min(remaining_refund, receipt.paid_amount)
            
            if available_refund > 0:
                # ✅ ننقص المبلغ المدفوع في الإيصال
                receipt.paid_amount -= available_refund
                receipt.save()
                
                print(f"تم تخفيض الإيصال {receipt.id} بمبلغ {available_refund}")
                
                # ✅ ننقص المبلغ المتبقي للاسترداد
                remaining_refund -= available_refund
        
        # ✅ إنشاء قيد الاسترداد
        refund_entry = JournalEntry.objects.create(
            date=today,
            description=f"استرداد مبلغ - {student.full_name} من {enrollment.course.name}" + 
                       (f" - {refund_reason}" if refund_reason else ""),
            entry_type='ADJUSTMENT',
            total_amount=refund_amount,
            created_by=request.user  # ✅ تم التصحيح هنا
        )

        # القيد الصحيح للاسترداد:
        # 1. مدين: ذمة الطالب (تخفيض الذمة - زيادة المدين)
        Transaction.objects.create(
            journal_entry=refund_entry,
            account=Account.get_or_create_student_ar_account(student, enrollment.course),
            amount=refund_amount,
            is_debit=True,
            description=f"استرداد مبلغ - {enrollment.course.name}"
        )

        # 2. دائن: النقدية (خروج النقود)
        cash_account = get_user_cash_account(request.user, fallback_code='121')
        if not cash_account:
            return JsonResponse({'ok': False, 'error': 'حساب النقدية غير موجود'}, status=400)
            
        Transaction.objects.create(
            journal_entry=refund_entry,
            account=cash_account,
            amount=refund_amount,
            is_debit=False,
            description=f"مرتجع نقدي - {student.full_name}"
        )

        # ترحيل القيد
        refund_entry.post_entry(request.user)  # ✅ تم التصحيح هنا
        
        # ✅ إعادة حساب المبالغ بعد التحديث
        new_total_paid = StudentReceipt.objects.filter(
            enrollment=enrollment
        ).aggregate(total=Sum('paid_amount'))['total'] or Decimal('0')
        
        new_balance = max(Decimal('0.00'), net_amount - new_total_paid)
        
        return JsonResponse({
            'ok': True, 
            'message': f'تم استرداد {refund_amount:,.0f} ل.س بنجاح',
            'new_balance': float(new_balance),
            'previous_balance': float(current_balance),
            'new_paid': float(new_total_paid),
            'previous_paid': float(total_paid)
        })

    except Exception as e:
        import traceback
        print(f"خطأ في الاسترداد: {str(e)}")
        print(traceback.format_exc())
        return JsonResponse({'ok': False, 'error': f'حدث خطأ في الاسترداد: {str(e)}'}, status=500)


        
# ====================
# الطلاب السريعين 
# ====================
# students/views.py - إضافة إلى الملف الحالي

# students/views.py
def student_type_choice(request):
    """صفحة اختيار نوع الطالب"""
    return render(request, 'students/student_type_choice.html')

from django.contrib.auth.decorators import login_required
# في students/views.py
@login_required
def auto_assign_students_to_years(request):
    """ربط جميع الطلاب النظاميين تلقائياً بالفصول الدراسية"""
    from quick.models import AcademicYear
    
    students = Student.objects.all()
    assigned_count = 0
    
    for student in students:
        if student.registration_date:
            academic_year = AcademicYear.objects.filter(
                start_date__lte=student.registration_date,
                end_date__gte=student.registration_date,
                is_active=True
            ).first()
            
            if academic_year:
                # إذا كان لديك حقل academic_year في نموذج Student
                # student.academic_year = academic_year
                # student.save()
                assigned_count += 1
    
    messages.success(request, f'تم ربط {assigned_count} طالب نظامي تلقائياً بالفصول الدراسية')
    return redirect('students:student_list')



class AllRegularStudentsView(LoginRequiredMixin, ListView):
    """عرض جميع الطلاب النظاميين لفصل دراسي معين"""
    template_name = 'students/all_regular_students.html'
    context_object_name = 'students'
    paginate_by = None  # ✅ إزالة الترقيم
    
    def get_queryset(self):
        academic_year_id = self.request.GET.get('academic_year') or self.kwargs.get('academic_year_id')
        
        print(f"🎯 [DEBUG] جلب جميع الطلاب النظاميين: academic_year_id={academic_year_id}")
        
        # البدء بجميع الطلاب النظاميين
        queryset = Student.objects.filter(quick_student_profile__isnull=True).select_related('academic_year', 'added_by')
        
        # فلترة حسب الفصل الدراسي إذا كان محدداً
        if academic_year_id and str(academic_year_id) != '0':
            try:
                from quick.models import AcademicYear
                academic_year = AcademicYear.objects.get(id=academic_year_id)
                queryset = queryset.filter(academic_year=academic_year)
                print(f"✅ [DEBUG] تم الفلترة حسب الفصل: {academic_year.name}")
            except (AcademicYear.DoesNotExist, ValueError) as e:
                print(f"❌ [DEBUG] خطأ في الفصل الدراسي: {e}")
        
        # ترتيب النتائج
        queryset = queryset.order_by('full_name')
        
        print(f"📊 [DEBUG] عدد الطلاب المسترجعة: {queryset.count()}")
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        academic_year_id = self.request.GET.get('academic_year') or self.kwargs.get('academic_year_id')
        
        # جلب معلومات الفصل الدراسي
        if academic_year_id and str(academic_year_id) != '0':
            try:
                from quick.models import AcademicYear
                academic_year = AcademicYear.objects.get(id=academic_year_id)
                context['academic_year'] = academic_year
                context['academic_year_name'] = academic_year.name
            except (AcademicYear.DoesNotExist, ValueError):
                context['academic_year'] = None
                context['academic_year_name'] = "غير محدد"
        else:
            context['academic_year'] = None
            context['academic_year_name'] = "جميع الفصول"
        
        context['students_count'] = self.get_queryset().count()
        return context
    


def get_student_display_data(student):
    """إرجاع بيانات الطالب بشكل موحد للعرض في الجداول"""
    return {
        'id': student.id,
        'full_name': student.full_name,
        'student_number': student.student_number,
        'phone': student.phone,
        'branch': student.branch,
        'academic_year': student.academic_year.name if student.academic_year else None,
        'is_active': student.is_active,
        'has_active_enrollments': student.has_active_enrollments(),  # تحتاج لإنشاء هذه الدالة
        'status_display': student.get_status_display(),  # تحتاج لإنشاء هذه الدالة
    }

from django.views.generic import UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.contrib import messages
from students.models import Student  # تأكد من المسار الصحيح
from students.forms import StudentForm  # تأكد من المسار الصحيح

class StudentUpdateView(LoginRequiredMixin, UpdateView):
    model = Student  # ✅ تأكد أن هذا هو الموديل الصحيح
    form_class = StudentForm  # ✅ تأكد أن هذا هو النموذج الصحيح
    template_name = 'update_student.html'
    context_object_name = 'student'  # ✅ هذا مهم
    
    def get_success_url(self):
        # تأكد من أن اسم الرابط صحيح
        return reverse_lazy('students:student_profile', kwargs={'pk': self.object.pk})
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # ✅ إضافة معلومات إضافية للتصحيح
        context['debug_info'] = {
            'student_id': self.object.id,
            'student_name': self.object.full_name,
            'form_initial': self.get_initial()
        }
        return context
    
    def form_valid(self, form):
        messages.success(self.request, 'تم تحديث بيانات الطالب بنجاح')
        return super().form_valid(form)


class CourseAuditView(LoginRequiredMixin, TemplateView):
    template_name = 'students/course_audit.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # جلب الدورات النظامية
        courses = Course.objects.all().order_by('-id')
        courses_data = [
            {'id': c.id, 'name': c.name, 'academic_year': c.academic_year.name if c.academic_year else ''}
            for c in courses
        ]
        
        # جلب الدورات السريعة
        from quick.models import QuickCourse
        quick_courses = QuickCourse.objects.all().order_by('-id')
        quick_courses_data = [
            {'id': qc.id, 'name': qc.name, 'academic_year': qc.academic_year.name if qc.academic_year else ''}
            for qc in quick_courses
        ]
        
        import json
        context['courses_json'] = json.dumps(courses_data)
        context['quick_courses_json'] = json.dumps(quick_courses_data)
        return context

def recalculate_account_balances(*accounts):
    """إعادة احتساب وتحديث الأرصدة المخزنة (الكاش) في الحسابات وآبائها بالكامل من واقع المعاملات الفعلية"""
    for acc in accounts:
        if acc:
            curr = acc
            while curr:
                curr.balance = curr.get_net_balance()
                curr.save(update_fields=['balance'])
                curr = curr.parent

def audit_course_api(request):
    """API لتدقيق الحسابات والقيود على مستوى دورة معينة أو فحص طالب بالكامل"""
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'error': 'غير مصرح'})
        
    student_search = request.GET.get('student_search')
    if student_search:
        from students.models import Student
        from quick.models import QuickStudent, QuickEnrollment
        from accounts.models import Studentenrollment, Account, JournalEntry, Transaction
        from django.db.models import Sum, Q
        
        # تحسين البحث عن الطالب ليدعم الاسم، الهاتف، هاتف الأب، البريد، والرقم الجامعي
        students = Student.objects.filter(
            Q(full_name__icontains=student_search) |
            Q(student_number__icontains=student_search) |
            Q(phone__icontains=student_search) |
            Q(email__icontains=student_search) |
            Q(father_phone__icontains=student_search)
        ).distinct()
        
        quick_students = QuickStudent.objects.filter(
            Q(full_name__icontains=student_search) |
            Q(phone__icontains=student_search)
        ).distinct()
        
        results = []
        
        # 1. Regular Students
        for s in students:
            student_data = {
                'student_id': s.id,
                'student_name': s.full_name,
                'student_phone': s.father_phone or s.phone or 'بلا هاتف',
                'type': 'REGULAR',
                'enrollments': []
            }
            
            enrollments = Studentenrollment.objects.filter(student=s).select_related('course', 'enrollment_journal_entry')
            for e in enrollments:
                ar_account = Account.get_student_ar_account_for_course(s, e.course)
                ledger_debit = Decimal('0')
                ledger_credit = Decimal('0')
                if ar_account:
                    ledger_debit = ar_account.get_debit_balance() or Decimal('0')
                    ledger_credit = ar_account.get_credit_balance() or Decimal('0')
                
                computed_net = max(Decimal('0'), e.total_amount - (e.total_amount * e.discount_percent / Decimal('100')) - e.discount_amount)
                ledger_balance = ledger_debit - ledger_credit
                
                # Check for errors
                errors = []
                warnings = []
                if computed_net > 0 and not e.enrollment_journal_entry:
                    errors.append('قيد تسجيل مفقود')
                elif abs(ledger_debit - computed_net) > Decimal('0.01'):
                    errors.append(f'خلل أرصدة: الصافي المحسوب {computed_net} ل.س بينما المدين الدفتري هو {ledger_debit} ل.س')
                
                # 🔍 تشخيص أسباب رصيد الحساب السالب
                if ledger_balance < 0:
                    if not e.enrollment_journal_entry:
                        warnings.append("رصيد ذمة الطالب سالب لأن قيد التسجيل الأصلي مفقود أو غير مسجل (مدين بقيمة 0)، وأي دفعات محصلة تجعل الحساب دائناً بالكامل.")
                    elif ledger_credit > computed_net:
                        warnings.append(f"رصيد الحساب سالب بسبب تسديد زائد: إجمالي المدفوعات المستلمة ({ledger_credit} ل.س) يتجاوز صافي قيمة الدورة المطلوبة بعد الحسم ({computed_net} ل.س). قد يكون هناك حسم تم منحه بعد تسديد القيمة أو دفعة زائدة.")
                    else:
                        warnings.append("رصيد الحساب سالب نتيجة وجود تسويات دائنة (ADJUSTMENT) أو دفعات إضافية خفضت الرصيد مدينياً.")

                # 🔍 تشخيص القيود المكررة أو الزائدة عن اللازم
                if ar_account:
                    # قيود تسجيل مكررة لنفس الدورة والطالب
                    enrollment_jes = JournalEntry.objects.filter(
                        entry_type='enrollment',
                        transactions__account=ar_account,
                        transactions__is_debit=True
                    ).distinct()
                    if enrollment_jes.count() > 1:
                        warnings.append(f"يوجد {enrollment_jes.count()} قيود تسجيل مكررة (من نوع enrollment) لهذا الكورس (معرفات القيود: {', '.join(str(je.id) for je in enrollment_jes)}). هذا التكرار يضخم الأرصدة المدنية ويحتاج لحذف المكرر.")
                    
                    # قيود حسم/تسوية مكررة لنفس الدورة والطالب
                    adj_jes = JournalEntry.objects.filter(
                        entry_type='ADJUSTMENT',
                        transactions__account=ar_account
                    ).distinct()
                    if adj_jes.count() > 1:
                        warnings.append(f"يوجد {adj_jes.count()} قيود تسوية/حسومات مكررة (ADJUSTMENT) لنفس الكورس (معرفات القيود: {', '.join(str(je.id) for je in adj_jes)}).")
                    
                    # مقبوضات/دفعات مكررة بنفس القيمة والتاريخ
                    payment_trans = Transaction.objects.filter(
                        account=ar_account,
                        journal_entry__entry_type='PAYMENT',
                        is_debit=False
                    ).select_related('journal_entry')
                    from collections import defaultdict
                    seen_payments = defaultdict(list)
                    for p in payment_trans:
                        seen_payments[(p.amount, p.journal_entry.date)].append(p.journal_entry.id)
                    for (amount, date), je_ids in seen_payments.items():
                        if len(je_ids) > 1:
                            warnings.append(f"تنبيه: يوجد دفعات مكررة بنفس القيمة ({amount} ل.س) وتاريخ ({date}) (معرفات القيود: {', '.join(str(id) for id in je_ids)}). قد يكون هذا قيد دفع تم إدخاله مرتين بالخطأ ويحتاج لحذف المكرر.")

                # Get linked entries
                linked_entries = []
                if e.enrollment_journal_entry:
                    linked_entries.append({
                        'id': e.enrollment_journal_entry.id,
                        'reference': e.enrollment_journal_entry.reference or f'JE-{e.enrollment_journal_entry.id}',
                        'type': 'enrollment',
                        'amount': e.enrollment_journal_entry.total_amount,
                        'date': str(e.enrollment_journal_entry.date),
                        'description': e.enrollment_journal_entry.description
                    })
                
                # Adjustments
                if ar_account:
                    adjustments = JournalEntry.objects.filter(
                        entry_type='ADJUSTMENT',
                        transactions__account=ar_account
                    ).distinct()
                    for adj in adjustments:
                        linked_entries.append({
                            'id': adj.id,
                            'reference': adj.reference or f'JE-{adj.id}',
                            'type': 'ADJUSTMENT',
                            'amount': adj.total_amount,
                            'date': str(adj.date),
                            'description': adj.description
                        })
                        
                student_data['enrollments'].append({
                    'enrollment_id': e.id,
                    'course_name': e.course.name,
                    'academic_year': e.academic_year.name if e.academic_year else '',
                    'total_amount': e.total_amount,
                    'discount_percent': e.discount_percent,
                    'discount_amount': e.discount_amount,
                    'net_amount': computed_net,
                    'ledger_debit': ledger_debit,
                    'ledger_credit': ledger_credit,
                    'ledger_balance': ledger_balance,
                    'is_completed': e.is_completed,
                    'errors': errors,
                    'warnings': warnings,
                    'linked_entries': linked_entries
                })
            results.append(student_data)
            
        # 2. Quick Students
        for qs in quick_students:
            student_data = {
                'student_id': qs.id,
                'student_name': qs.full_name,
                'student_phone': qs.phone or 'بلا هاتف',
                'type': 'QUICK',
                'enrollments': []
            }
            
            enrollments = QuickEnrollment.objects.filter(student=qs).select_related('course')
            for e in enrollments:
                computed_net = e.calculated_net_amount
                
                student_ar_account = Account.get_or_create_quick_student_ar_account(qs)
                ledger_debit = student_ar_account.get_debit_balance() if student_ar_account else Decimal('0')
                ledger_credit = student_ar_account.get_credit_balance() if student_ar_account else Decimal('0')
                ledger_balance = ledger_debit - ledger_credit
                
                # Check for errors
                errors = []
                warnings = []
                je = e.enrollment_journal_entry
                if computed_net > 0 and not je:
                    errors.append('قيد تسجيل مفقود')
                elif je and abs(je.total_amount - e.total_amount) > Decimal('0.01'):
                    errors.append(f'خلل أرصدة: قيمة القيد {je.total_amount} ل.س بينما الإجمالي هو {e.total_amount} ل.س')
                
                # 🔍 تشخيص أسباب رصيد الحساب السالب للطلاب السريعين
                if ledger_balance < 0:
                    if not je:
                        warnings.append("رصيد ذمة الطالب السريع سالب لأن قيد التسجيل مفقود أو غير مسجل.")
                    elif ledger_credit > computed_net:
                        warnings.append(f"رصيد الحساب سالب لأن إجمالي المقبوضات يتجاوز صافي قيمة هذه الدورة المطلوبة ({computed_net} ل.س).")
                    else:
                        warnings.append("رصيد الحساب سالب بسبب مقبوضات زائدة أو تسويات خفضت الذمة.")
                        
                # 🔍 تشخيص القيود المكررة أو الزائدة عن اللازم للطلاب السريعين
                reference = e.enrollment_reference
                if reference:
                    duplicate_jes = JournalEntry.objects.filter(reference=reference)
                    if duplicate_jes.count() > 1:
                        warnings.append(f"يوجد قيود تسجيل مكررة بالمرجع {reference} (عدد القيود: {duplicate_jes.count()}).")
                
                discount_jes = JournalEntry.objects.filter(
                    entry_type='ADJUSTMENT',
                    description__icontains=f'[QUICK_DISCOUNT #{e.id}]'
                )
                if discount_jes.count() > 1:
                    warnings.append(f"يوجد {discount_jes.count()} قيود خصم مكررة (ADJUSTMENT) لنفس التسجيل السريع (معرفات القيود: {', '.join(str(je.id) for je in discount_jes)}).")

                # Fetch linked entries
                linked_entries = []
                if je:
                    linked_entries.append({
                        'id': je.id,
                        'reference': je.reference or f'JE-{je.id}',
                        'type': 'enrollment',
                        'amount': je.total_amount,
                        'date': str(je.date),
                        'description': je.description
                    })
                
                student_data['enrollments'].append({
                    'enrollment_id': e.id,
                    'course_name': e.course.name,
                    'academic_year': e.course.academic_year.name if e.course.academic_year else '',
                    'total_amount': e.total_amount,
                    'discount_percent': e.discount_percent,
                    'discount_amount': e.discount_amount,
                    'net_amount': computed_net,
                    'ledger_debit': ledger_debit,
                    'ledger_credit': ledger_credit,
                    'ledger_balance': ledger_balance,
                    'is_completed': e.is_completed,
                    'errors': errors,
                    'warnings': warnings,
                    'linked_entries': linked_entries
                })
            results.append(student_data)
            
        return JsonResponse({'success': True, 'results': results, 'is_search': True})

    course_id = request.GET.get('course_id')
    course_type = request.GET.get('type', 'REGULAR')
    if not course_id:
        return JsonResponse({'success': False, 'error': 'لم يتم اختيار الدورة'})

    errors = []
    
    if course_type == 'QUICK':
        from quick.models import QuickCourse, QuickEnrollment
        if course_id == 'all':
            enrollments = QuickEnrollment.objects.all().select_related('student', 'course')
        else:
            course = get_object_or_404(QuickCourse, id=course_id)
            enrollments = QuickEnrollment.objects.filter(course=course).select_related('student', 'course')
        
        stats = {
            'total_students': enrollments.count(),
            'total_errors': 0,
            'missing_entries': 0,
            'mismatches': 0
        }

        for e in enrollments:
            student = e.student
            student_name = student.full_name
            course = e.course
            
            # احتساب المبلغ الصافي
            computed_net = e.calculated_net_amount
            
            # جلب قيد التسجيل وقيد الخصم الخاصين بهذا التسجيل تحديداً لتفادي الخلط مع دورات سريعة أخرى لنفس الطالب
            enrollment_entry = e.enrollment_journal_entry
            discount_entry = JournalEntry.objects.filter(
                entry_type='ADJUSTMENT',
                description__icontains=f'[QUICK_DISCOUNT #{e.id}]'
            ).first()
            
            gross_ledger = enrollment_entry.total_amount if enrollment_entry else Decimal('0')
            discount_ledger = discount_entry.total_amount if discount_entry else Decimal('0')
            
            # الصافي الدفتري الخاص بهذا التسجيل
            actual_net_debit = gross_ledger - discount_ledger
            
            student_ar_account = Account.get_or_create_quick_student_ar_account(student)
            ledger_debit = student_ar_account.get_debit_balance() if student_ar_account else Decimal('0')
            ledger_credit = student_ar_account.get_credit_balance() if student_ar_account else Decimal('0')
            ledger_balance = ledger_debit - ledger_credit
            
            warnings = []
            
            # 🔍 تشخيص أسباب رصيد الحساب السالب للطلاب السريعين
            if ledger_balance < 0:
                if not enrollment_entry:
                    warnings.append("رصيد ذمة الطالب السريع سالب لأن قيد التسجيل مفقود أو غير مسجل.")
                elif ledger_credit > computed_net:
                    warnings.append(f"رصيد الحساب سالب لأن إجمالي المقبوضات يتجاوز صافي قيمة هذه الدورة المطلوبة ({computed_net} ل.س).")
                else:
                    warnings.append("رصيد الحساب سالب بسبب مقبوضات زائدة أو تسويات خفضت الذمة.")
            
            # 🔍 تشخيص القيود المكررة للطلاب السريعين
            reference = e.enrollment_reference
            if reference:
                duplicate_jes = JournalEntry.objects.filter(reference=reference)
                if duplicate_jes.count() > 1:
                    warnings.append(f"يوجد قيود تسجيل مكررة بالمرجع {reference} (عدد القيود: {duplicate_jes.count()}).")
            
            discount_jes = JournalEntry.objects.filter(
                entry_type='ADJUSTMENT',
                description__icontains=f'[QUICK_DISCOUNT #{e.id}]'
            )
            if discount_jes.count() > 1:
                warnings.append(f"يوجد {discount_jes.count()} قيود خصم مكررة (ADJUSTMENT) لنفس التسجيل السريع (معرفات القيود: {', '.join(str(je.id) for je in discount_jes)}).")
            
            # فحص القيود المفقودة
            if computed_net > 0 and not enrollment_entry:
                stats['total_errors'] += 1
                stats['missing_entries'] += 1
                errors.append({
                    'enrollment_id': e.id,
                    'student_id': student.id,
                    'student_name': student_name,
                    'student_phone': student.phone or 'بلا هاتف',
                    'total_amount': e.total_amount,
                    'discount_percent': e.discount_percent,
                    'discount_amount': e.discount_amount,
                    'discount_reason': 'تسجيل سريع',
                    'net_amount': computed_net,
                    'ledger_balance': actual_net_debit,
                    'type': 'missing_entry',
                    'type_display': 'قيد تسجيل مفقود',
                    'description': 'الطالب مسجل بنجاح في دورة سريعة ولكن لا يوجد قيد محاسبي للتسجيل.',
                    'suggestion': 'إنشاء قيد التسجيل المحاسبي للدورة السريعة بقيمة إجمالية ' + str(e.total_amount) + ' ل.س.',
                    'warnings': warnings
                })
            # فحص خلل الأرصدة
            elif abs(actual_net_debit - computed_net) > Decimal('0.01'):
                stats['total_errors'] += 1
                stats['mismatches'] += 1
                errors.append({
                    'enrollment_id': e.id,
                    'student_id': student.id,
                    'student_name': student_name,
                    'student_phone': student.phone or 'بلا هاتف',
                    'total_amount': e.total_amount,
                    'discount_percent': e.discount_percent,
                    'discount_amount': e.discount_amount,
                    'discount_reason': 'تسجيل سريع',
                    'net_amount': computed_net,
                    'ledger_balance': actual_net_debit,
                    'type': 'mismatch',
                    'type_display': 'خلل في أرصدة القيود',
                    'description': f'صافي التسجيل السريع المحسوب هو {computed_net} ل.س بينما الرصيد الدفتري الحالي هو {actual_net_debit} ل.س (بسبب خلل في قيد التسجيل أو التسوية).',
                    'suggestion': 'حذف قيود التسوية المكررة وإعادة بناء قيد الحسم وقيد التسجيل الأصلي بالقيم الصحيحة.',
                    'warnings': warnings
                })
    else:
        # الدورات النظامية
        if course_id == 'all':
            enrollments = Studentenrollment.objects.all().select_related('student', 'course', 'enrollment_journal_entry')
        else:
            course = get_object_or_404(Course, id=course_id)
            enrollments = Studentenrollment.objects.filter(course=course).select_related('student', 'course', 'enrollment_journal_entry')

        stats = {
            'total_students': enrollments.count(),
            'total_errors': 0,
            'missing_entries': 0,
            'mismatches': 0
        }

        for e in enrollments:
            student = e.student
            student_name = getattr(student, 'full_name', None) or getattr(student, 'name', '') or str(student)
            course = e.course
            
            # الربط المحاسبي التلقائي وتنظيف القيود المكررة للتسجيل من المحاولات السابقة
            ar_account = Account.get_student_ar_account_for_course(student, course)
            if ar_account:
                enrollment_jes = JournalEntry.objects.filter(
                    entry_type='enrollment',
                    transactions__account=ar_account,
                    transactions__is_debit=True
                ).distinct().order_by('id')
                
                if enrollment_jes.exists():
                    if not e.enrollment_journal_entry or e.enrollment_journal_entry not in enrollment_jes:
                        e.enrollment_journal_entry = enrollment_jes[0]
                        e.save(update_fields=['enrollment_journal_entry'])
                    
                    if enrollment_jes.count() > 1:
                        for duplicate_je in enrollment_jes:
                            if duplicate_je.id != e.enrollment_journal_entry.id:
                                duplicate_je._skip_linked_cleanup = True
                                duplicate_je.transactions.all().delete()
                                duplicate_je.delete()
                        recalculate_account_balances(ar_account)
                                
            # احتساب المبلغ الصافي رياضياً
            computed_net = max(Decimal('0'), e.total_amount - (e.total_amount * e.discount_percent / Decimal('100')) - e.discount_amount)
            
            # جلب الحساب الجاري والقيود
            ar_account = Account.get_student_ar_account_for_course(student, course)
            
            ledger_debit = Decimal('0')
            ledger_credit = Decimal('0')
            
            if ar_account:
                ledger_debit = ar_account.get_debit_balance() or Decimal('0')
                ledger_credit = ar_account.get_credit_balance() or Decimal('0')
                
            # إجمالي قيود الخصم/التسوية الدائنة والمدينة
            adjustments_credit = Transaction.objects.filter(
                account=ar_account, 
                journal_entry__entry_type='ADJUSTMENT', 
                is_debit=False
            ).aggregate(s=Sum('amount'))['s'] or Decimal('0')
            
            adjustments_debit = Transaction.objects.filter(
                account=ar_account, 
                journal_entry__entry_type='ADJUSTMENT', 
                is_debit=True
            ).aggregate(s=Sum('amount'))['s'] or Decimal('0')

            # الصافي الدفتري قبل المدفوعات (المدين الأصلي مطروحاً منه الخصومات)
            actual_net_debit = ledger_debit - adjustments_credit + adjustments_debit
            
            ledger_balance = ledger_debit - ledger_credit
            warnings = []
            
            # 🔍 تشخيص أسباب رصيد الحساب السالب للطلاب النظاميين
            if ledger_balance < 0:
                if not e.enrollment_journal_entry:
                    warnings.append("رصيد ذمة الطالب سالب لأن قيد التسجيل الأصلي مفقود أو غير مسجل (مدين بقيمة 0)، وأي دفعات محصلة تجعل الحساب دائناً بالكامل.")
                elif ledger_credit > computed_net:
                    warnings.append(f"رصيد الحساب سالب بسبب تسديد زائد: إجمالي المدفوعات المستلمة ({ledger_credit} ل.س) يتجاوز صافي قيمة الدورة المطلوبة بعد الحسم ({computed_net} ل.س). قد يكون هناك حسم تم منحه بعد تسديد القيمة أو دفعة زائدة.")
                else:
                    warnings.append("رصيد الحساب سالب نتيجة وجود تسويات دائنة (ADJUSTMENT) أو دفعات إضافية خفضت الرصيد مدينياً.")

            # 🔍 تشخيص القيود المكررة للطلاب النظاميين
            if ar_account:
                enrollment_jes = JournalEntry.objects.filter(
                    entry_type='enrollment',
                    transactions__account=ar_account,
                    transactions__is_debit=True
                ).distinct()
                if enrollment_jes.count() > 1:
                    warnings.append(f"يوجد {enrollment_jes.count()} قيود تسجيل مكررة (من نوع enrollment) لهذا الكورس (معرفات القيود: {', '.join(str(je.id) for je in enrollment_jes)}).")
                
                adj_jes = JournalEntry.objects.filter(
                    entry_type='ADJUSTMENT',
                    transactions__account=ar_account
                ).distinct()
                if adj_jes.count() > 1:
                    warnings.append(f"يوجد {adj_jes.count()} قيود تسوية/حسومات مكررة (ADJUSTMENT) لنفس الكورس (معرفات القيود: {', '.join(str(je.id) for je in adj_jes)}).")
                
                payment_trans = Transaction.objects.filter(
                    account=ar_account,
                    journal_entry__entry_type='PAYMENT',
                    is_debit=False
                ).select_related('journal_entry')
                from collections import defaultdict
                seen_payments = defaultdict(list)
                for p in payment_trans:
                    seen_payments[(p.amount, p.journal_entry.date)].append(p.journal_entry.id)
                for (amount, date), je_ids in seen_payments.items():
                    if len(je_ids) > 1:
                        warnings.append(f"تنبيه: يوجد دفعات مكررة بنفس القيمة ({amount} ل.س) وتاريخ ({date}) (معرفات القيود: {', '.join(str(id) for id in je_ids)}). قد يكون هذا إدخال مكرر.")

            # فحص القيود المفقودة
            if computed_net > 0 and not e.enrollment_journal_entry:
                stats['total_errors'] += 1
                stats['missing_entries'] += 1
                errors.append({
                    'enrollment_id': e.id,
                    'student_id': student.id,
                    'student_name': student_name,
                    'student_phone': student.father_phone or 'بلا هاتف',
                    'total_amount': e.total_amount,
                    'discount_percent': e.discount_percent,
                    'discount_amount': e.discount_amount,
                    'discount_reason': e.discount_reason,
                    'net_amount': computed_net,
                    'ledger_balance': actual_net_debit,
                    'type': 'missing_entry',
                    'type_display': 'قيد تسجيل مفقود',
                    'description': 'الطالب مسجل بنجاح وله ذمة مالية ولكن لا يوجد قيد محاسبي للتسجيل.',
                    'suggestion': 'إنشاء قيد التسجيل المحاسبي (DR ذمة الطالب / CR إيرادات مؤجلة) بمبلغ ' + str(computed_net) + ' ل.س.',
                    'warnings': warnings
                })
                
            # فحص خلل الأرصدة بسبب قيود الحسم المزدوجة
            elif abs(actual_net_debit - computed_net) > Decimal('0.01'):
                stats['total_errors'] += 1
                stats['mismatches'] += 1
                errors.append({
                    'enrollment_id': e.id,
                    'student_id': student.id,
                    'student_name': student_name,
                    'student_phone': student.father_phone or 'بلا هاتف',
                    'total_amount': e.total_amount,
                    'discount_percent': e.discount_percent,
                    'discount_amount': e.discount_amount,
                    'discount_reason': e.discount_reason,
                    'net_amount': computed_net,
                    'ledger_balance': actual_net_debit,
                    'type': 'mismatch',
                    'type_display': 'خلل في أرصدة القيود',
                    'description': f'صافي التسجيل المحسوب هو {computed_net} ل.س بينما الرصيد الدفتري الحالي هو {actual_net_debit} ل.س (بسبب قيود تسوية مكررة أو خاطئة).',
                    'suggestion': 'إلغاء قيود التسوية (ADJUSTMENT) الخاطئة وتحديث قيمة القيد الأصلي ليعبر بدقة عن الصافي.',
                    'warnings': warnings
                })

    return JsonResponse({
        'success': True,
        'errors': errors,
        'stats': stats
    })

def fix_student_enrollment_error(request):
    """إجراء لتصحيح الأخطاء تلقائياً وبأمان أو تنفيذ خيارات تحكم متقدمة"""
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'error': 'غير مصرح'})
        
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'طلب غير صالح'})

    try:
        import json
        data = json.loads(request.body)
        enrollment_id = data.get('enrollment_id')
        error_type = data.get('error_type')
        course_type = data.get('course_type', 'REGULAR')
        
        if not enrollment_id or not error_type:
            return JsonResponse({'success': False, 'error': 'معطيات ناقصة'})

        from django.db import transaction as db_transaction
        
        with db_transaction.atomic():
            if course_type == 'QUICK':
                from quick.models import QuickEnrollment
                enrollment = get_object_or_404(QuickEnrollment, id=enrollment_id)
                student = enrollment.student
                course = enrollment.course
                
                computed_net = enrollment.calculated_net_amount
                
                if error_type == 'advanced_action':
                    action_type = data.get('action_type')
                    if action_type == 'recalculate_balance':
                        student_ar_account = Account.get_or_create_quick_student_ar_account(student)
                        deferred_account = Account.get_or_create_quick_course_deferred_account(course)
                        recalculate_account_balances(student_ar_account, deferred_account)
                    elif action_type == 'toggle_completed':
                        enrollment.is_completed = not enrollment.is_completed
                        if enrollment.is_completed:
                            from django.utils import timezone
                            enrollment.completion_date = timezone.now().date()
                        else:
                            enrollment.completion_date = None
                        enrollment.save(update_fields=['is_completed', 'completion_date'])
                    elif action_type == 'delete_adjustments':
                        adjustments = JournalEntry.objects.filter(
                            entry_type='ADJUSTMENT',
                            description__contains=student.full_name
                        ).filter(description__contains=course.name)
                        adjustments = adjustments | JournalEntry.objects.filter(
                            entry_type='ADJUSTMENT',
                            description__icontains=f'[QUICK_DISCOUNT #{enrollment.id}]'
                        )
                        for adj in adjustments:
                            adj._skip_linked_cleanup = True
                            adj.transactions.all().delete()
                            adj.delete()
                        student_ar_account = Account.get_or_create_quick_student_ar_account(student)
                        deferred_account = Account.get_or_create_quick_course_deferred_account(course)
                        recalculate_account_balances(student_ar_account, deferred_account)
                    elif action_type == 'update_net_amount':
                        custom_net_amount = data.get('custom_net_amount')
                        if custom_net_amount is None:
                            return JsonResponse({'success': False, 'error': 'لم يتم تحديد المبلغ الجديد'})
                        custom_net = Decimal(str(custom_net_amount))
                        
                        enrollment.total_amount = custom_net
                        enrollment.discount_percent = Decimal('0')
                        enrollment.discount_amount = Decimal('0')
                        enrollment.net_amount = custom_net
                        enrollment.save()
                        
                        adjustments = JournalEntry.objects.filter(
                            entry_type='ADJUSTMENT',
                            description__contains=student.full_name
                        ).filter(description__contains=course.name)
                        adjustments = adjustments | JournalEntry.objects.filter(
                            entry_type='ADJUSTMENT',
                            description__icontains=f'[QUICK_DISCOUNT #{enrollment.id}]'
                        )
                        for adj in adjustments:
                            adj._skip_linked_cleanup = True
                            adj.transactions.all().delete()
                            adj.delete()
                        
                        je = enrollment.enrollment_journal_entry
                        if je:
                            je.total_amount = custom_net
                            je.save(update_fields=['total_amount'])
                            debit_trans = je.transactions.filter(is_debit=True).first()
                            credit_trans = je.transactions.filter(is_debit=False).first()
                            if debit_trans:
                                debit_trans.amount = custom_net
                                debit_trans.save(update_fields=['amount'])
                            if credit_trans:
                                credit_trans.amount = custom_net
                                credit_trans.save(update_fields=['amount'])
                        else:
                            enrollment.create_accrual_enrollment_entry(request.user)
                            
                        student_ar_account = Account.get_or_create_quick_student_ar_account(student)
                        deferred_account = Account.get_or_create_quick_course_deferred_account(course)
                        recalculate_account_balances(student_ar_account, deferred_account)
                
                elif error_type == 'missing_entry':
                    enrollment.create_accrual_enrollment_entry(request.user)
                elif error_type == 'mismatch':
                    # 1. حذف قيود الحسم/التسوية
                    adjustments = JournalEntry.objects.filter(
                        entry_type='ADJUSTMENT',
                        description__contains=student.full_name
                    ).filter(description__contains=course.name)
                    if enrollment.enrollment_journal_entry:
                        adjustments = adjustments.exclude(id=enrollment.enrollment_journal_entry.id)
                    for adj in adjustments:
                        adj._skip_linked_cleanup = True
                        adj.transactions.all().delete()
                        adj.delete()
                        
                    # 2. تحديث قيد التسجيل الأصلي للصافي/الإجمالي الصحيح
                    je = enrollment.enrollment_journal_entry
                    if je:
                        je.total_amount = enrollment.gross_amount
                        je.save(update_fields=['total_amount'])
                        
                        debit_trans = je.transactions.filter(is_debit=True).first()
                        credit_trans = je.transactions.filter(is_debit=False).first()
                        if debit_trans:
                            debit_trans.amount = enrollment.gross_amount
                            debit_trans.save(update_fields=['amount'])
                        if credit_trans:
                            credit_trans.amount = enrollment.gross_amount
                            credit_trans.save(update_fields=['amount'])
                    else:
                        enrollment.create_accrual_enrollment_entry(request.user)
                        
                    # 3. إعادة إنشاء قيد الحسم
                    if enrollment.discount_value > 0:
                        enrollment.create_discount_adjustment_entry(request.user)
                        
                    # 4. تحديث الأرصدة المخزنة للحسابات محاسبياً بالكامل
                    student_ar_account = Account.get_or_create_quick_student_ar_account(enrollment.student)
                    deferred_account = Account.get_or_create_quick_course_deferred_account(enrollment.course)
                    recalculate_account_balances(student_ar_account, deferred_account)
            else:
                enrollment = get_object_or_404(Studentenrollment, id=enrollment_id)
                student = enrollment.student
                course = enrollment.course
                
                # الربط المحاسبي التلقائي وتنظيف القيود المكررة للتسجيل من المحاولات السابقة
                ar_account = Account.get_student_ar_account_for_course(student, course)
                if ar_account:
                    enrollment_jes = JournalEntry.objects.filter(
                        entry_type='enrollment',
                        transactions__account=ar_account,
                        transactions__is_debit=True
                    ).distinct().order_by('id')
                    
                    if enrollment_jes.exists():
                        if not enrollment.enrollment_journal_entry or enrollment.enrollment_journal_entry not in enrollment_jes:
                            enrollment.enrollment_journal_entry = enrollment_jes[0]
                            enrollment.save(update_fields=['enrollment_journal_entry'])
                        
                        if enrollment_jes.count() > 1:
                            for duplicate_je in enrollment_jes:
                                if duplicate_je.id != enrollment.enrollment_journal_entry.id:
                                    duplicate_je._skip_linked_cleanup = True
                                    duplicate_je.transactions.all().delete()
                                    duplicate_je.delete()
                
                computed_net = max(Decimal('0'), enrollment.total_amount - (enrollment.total_amount * enrollment.discount_percent / Decimal('100')) - enrollment.discount_amount)

                if error_type == 'advanced_action':
                    action_type = data.get('action_type')
                    if action_type == 'recalculate_balance':
                        student_ar_account = Account.get_student_ar_account_for_course(student, course)
                        course_deferred_account = Account.get_or_create_course_deferred_account(course)
                        recalculate_account_balances(student_ar_account, course_deferred_account)
                    elif action_type == 'toggle_completed':
                        enrollment.is_completed = not enrollment.is_completed
                        if enrollment.is_completed:
                            from django.utils import timezone
                            enrollment.completion_date = timezone.now().date()
                        else:
                            enrollment.completion_date = None
                        enrollment.save(update_fields=['is_completed', 'completion_date'])
                    elif action_type == 'delete_adjustments':
                        adjustments = JournalEntry.objects.filter(
                            entry_type='ADJUSTMENT',
                            description__contains=student.full_name
                        ).filter(description__contains=course.name)
                        for adj in adjustments:
                            adj._skip_linked_cleanup = True
                            adj.transactions.all().delete()
                            adj.delete()
                        student_ar_account = Account.get_student_ar_account_for_course(student, course)
                        course_deferred_account = Account.get_or_create_course_deferred_account(course)
                        recalculate_account_balances(student_ar_account, course_deferred_account)
                    elif action_type == 'update_net_amount':
                        custom_net_amount = data.get('custom_net_amount')
                        if custom_net_amount is None:
                            return JsonResponse({'success': False, 'error': 'لم يتم تحديد المبلغ الجديد'})
                        custom_net = Decimal(str(custom_net_amount))
                        
                        enrollment.total_amount = custom_net
                        enrollment.discount_percent = Decimal('0')
                        enrollment.discount_amount = Decimal('0')
                        enrollment.save()
                        
                        adjustments = JournalEntry.objects.filter(
                            entry_type='ADJUSTMENT',
                            description__contains=student.full_name
                        ).filter(description__contains=course.name)
                        for adj in adjustments:
                            adj._skip_linked_cleanup = True
                            adj.transactions.all().delete()
                            adj.delete()
                            
                        je = enrollment.enrollment_journal_entry
                        if je:
                            je.total_amount = custom_net
                            je.save(update_fields=['total_amount'])
                            debit_trans = je.transactions.filter(is_debit=True).first()
                            credit_trans = je.transactions.filter(is_debit=False).first()
                            if debit_trans:
                                debit_trans.amount = custom_net
                                debit_trans.save(update_fields=['amount'])
                            if credit_trans:
                                credit_trans.amount = custom_net
                                credit_trans.save(update_fields=['amount'])
                        else:
                            enrollment.create_accrual_enrollment_entry(request.user)
                            
                        student_ar_account = Account.get_student_ar_account_for_course(student, course)
                        course_deferred_account = Account.get_or_create_course_deferred_account(course)
                        recalculate_account_balances(student_ar_account, course_deferred_account)
                
                elif error_type == 'missing_entry':
                    if computed_net > 0:
                        enrollment.create_accrual_enrollment_entry(request.user)
                        
                elif error_type == 'mismatch':
                    adjustments = JournalEntry.objects.filter(
                        entry_type='ADJUSTMENT',
                        description__contains=student.full_name
                    ).filter(description__contains=course.name)
                    if enrollment.enrollment_journal_entry:
                        adjustments = adjustments.exclude(id=enrollment.enrollment_journal_entry.id)
                    
                    for adj in adjustments:
                        adj._skip_linked_cleanup = True
                        adj.transactions.all().delete()
                        adj.delete()
                    
                    if enrollment.enrollment_journal_entry:
                        je = enrollment.enrollment_journal_entry
                        if computed_net == 0:
                            je._skip_linked_cleanup = True
                            je.transactions.all().delete()
                            je.delete()
                            enrollment.enrollment_journal_entry = None
                            enrollment.save(update_fields=['enrollment_journal_entry'])
                        else:
                            je.total_amount = computed_net
                            je.save(update_fields=['total_amount'])
                            
                            debit_trans = je.transactions.filter(is_debit=True).first()
                            credit_trans = je.transactions.filter(is_debit=False).first()
                            
                            if debit_trans:
                                debit_trans.amount = computed_net
                                debit_trans.save(update_fields=['amount'])
                            if credit_trans:
                                credit_trans.amount = computed_net
                                credit_trans.save(update_fields=['amount'])
                    else:
                        if computed_net > 0:
                            enrollment.create_accrual_enrollment_entry(request.user)
                            
                    # تحديث الأرصدة المخزنة للحسابات محاسبياً بالكامل
                    student_ar_account = Account.get_student_ar_account_for_course(student, course)
                    course_deferred_account = Account.get_or_create_course_deferred_account(course)
                    recalculate_account_balances(student_ar_account, course_deferred_account)

        return JsonResponse({'success': True, 'message': 'تم تنفيذ الإجراء بنجاح'})

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


from django.views.decorators.http import require_GET
from django.contrib.auth.decorators import login_required

@require_GET
@login_required
def check_student_exists(request):
    full_name = request.GET.get('full_name', '').strip()
    student_number = request.GET.get('student_number', '').strip()
    student_id = request.GET.get('student_id')  # للتحويل في حالة التعديل

    current_year = getattr(request, 'current_academic_year', None)
    if not current_year:
        return JsonResponse({'exists': False})

    queryset = Student.objects.filter(academic_year=current_year, quick_student_profile__isnull=True)
    if student_id and student_id.isdigit():
        queryset = queryset.exclude(pk=int(student_id))

    if full_name:
        match = queryset.filter(full_name__iexact=full_name).first()
        if match:
            return JsonResponse({'exists': True, 'student_number': match.student_number})

    if student_number:
        match = queryset.filter(student_number=student_number).first()
        if match:
            return JsonResponse({'exists': True, 'full_name': match.full_name})

    return JsonResponse({'exists': False})


    
