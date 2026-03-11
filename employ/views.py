from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import View, TemplateView, ListView, DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy, reverse
from django.contrib import messages
from django.http import JsonResponse, HttpResponseRedirect, HttpResponse, HttpResponseForbidden
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils import timezone
from django.db import transaction
from django.db.models import Sum, Count
from django.core.exceptions import FieldDoesNotExist
from django.template.loader import render_to_string 
from django.contrib.staticfiles import finders
from django.conf import settings

from accounts.models import ExpenseEntry, EmployeeAdvance, Account, TeacherAdvance, get_or_create_employee_cash_account
from accounts.forms import EmployeeAdvanceForm
from attendance.models import TeacherAttendance

from .models import Teacher, Employee, Vacation, EmployeePermission, ManualTeacherSalary
from .forms import TeacherForm, EmployeeRegistrationForm, AdminVacationForm
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
import io
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.pdfmetrics import registerFontFamily
from urllib.parse import quote


# -----------------------------
# أدوات مساعدة
# -----------------------------
def _employee_full_name(employee):
    """إرجاع اسم الموظف للعرض بأولوية: Employee.full_name -> User.get_full_name -> username"""
    if not employee:
        return ''
    name_attr = getattr(employee, 'full_name', None)
    if name_attr:
        return name_attr
    user = getattr(employee, 'user', None)
    if user:
        full_name = user.get_full_name()
        return full_name if full_name else user.get_username()
    return str(employee)


# خريطة المجموعات بحسب بادئة كود الصلاحية
GROUP_PREFIXES = {
    'students_': 'students',
    'teachers_': 'teachers',
    'attendance_': 'attendance',
    'classroom_': 'classroom',
    'quick_students_': 'quick_students',
    'exams_': 'exams',
    'errors_': 'errors',
    'registration_': 'registration',
    'courses_': 'courses',
    'accounting_': 'accounting',
    'hr_': 'hr',
    'admin_': 'admin',
    'reports_': 'reports',
    'course_accounting_': 'course_accounting',
    'inventory_': 'inventory',
    'assets_': 'inventory',
    'marketing_': 'marketing',
    'quality_': 'quality',
}


def _empty_permission_groups():
    """نضمن وجود جميع المفاتيح دائماً (حتى لو كانت القوائم فارغة)."""
    return {
        'students': [],
        'teachers': [],
        'attendance': [],
        'classroom': [],
        'quick_students': [],
        'exams': [],
        'errors': [],
        'pages': [],
        'registration': [],
        'courses': [],
        'accounting': [],
        'hr': [],
        'admin': [],
        'reports': [],
        'course_accounting': [],
        'inventory': [],
        'marketing': [],
        'quality': [],
    }


def _group_for_code(code: str):
    """استخرج اسم المجموعة من بادئة كود الصلاحية."""
    for prefix, group in GROUP_PREFIXES.items():
        if code.startswith(prefix):
            return group
    return None


# -----------------------------
# إدارة صلاحيات الموظف
# -----------------------------
class EmployeePermissionsView(LoginRequiredMixin, View):
    template_name = 'employ/employee_permissions.html'

    def get(self, request, pk):
        employee = get_object_or_404(Employee, pk=pk)

        # الصلاحيات الممنوحة حاليًا
        granted = set(
            employee.permissions.filter(is_granted=True).values_list('permission', flat=True)
        )

        # بناء القوائم
        permission_groups = _empty_permission_groups()

        for code, label in EmployeePermission.PERMISSION_CHOICES:
            group = _group_for_code(code)
            if not group:
                continue
            permission_groups[group].append({
                'code': code,
                'label': label,
                'is_granted': code in granted
            })

        cash_account = employee.get_cash_account()
        cash_account_balance = cash_account.get_net_balance() if cash_account else Decimal('0.00')

        return render(request, self.template_name, {
            'employee': employee,
            'permission_groups': permission_groups,
            'cash_account': cash_account,
            'cash_account_balance': cash_account_balance
        })




    @transaction.atomic
    def post(self, request, pk):
        employee = get_object_or_404(Employee, pk=pk)

        # الصلاحيات المختارة
        selected_codes = set(request.POST.getlist('permissions'))

        # ببساطة: فعّل ما تم تحديده، وعطّل الباقي
        existing = {ep.permission: ep for ep in employee.permissions.all()}

        for code, _label in EmployeePermission.PERMISSION_CHOICES:
            should_grant = code in selected_codes
            if code in existing:
                ep = existing[code]
                if ep.is_granted != should_grant:
                    ep.is_granted = should_grant
                    ep.granted_by = request.user if should_grant else ep.granted_by
                    ep.save(update_fields=['is_granted', 'granted_by'])
            else:
                if should_grant:
                    EmployeePermission.objects.create(
                        employee=employee,
                        permission=code,
                        is_granted=True,
                        granted_by=request.user
                    )

        messages.success(request, f'تم تحديث صلاحيات الموظف { _employee_full_name(employee) } بنجاح.')
        return redirect('employ:employee_permissions', pk=pk)


class CreateEmployeeCashAccountView(LoginRequiredMixin, View):
    def post(self, request, pk):
        employee = get_object_or_404(Employee, pk=pk)
        employee_name = _employee_full_name(employee) or employee.user.get_username()

        try:
            account, created = get_or_create_employee_cash_account(employee)
            if created:
                messages.success(
                    request,
                    f'Created cash account {account.code} for {employee_name}.'
                )
            else:
                messages.info(
                    request,
                    f'Cash account {account.code} for {employee_name} already exists.'
                )
        except Exception as exc:
            messages.error(
                request,
                f'Failed to create cash account: {exc}'
            )

        return redirect('employ:employee_permissions', pk=employee.pk)


# -----------------------------
# سلف الموظفين
# -----------------------------
class EmployeeAdvanceListView(LoginRequiredMixin, ListView):
    model = EmployeeAdvance
    template_name = 'employ/employee_advance_list.html'
    context_object_name = 'advances'

    def get_queryset(self):
        return EmployeeAdvance.objects.select_related('employee__user', 'created_by').order_by('-date')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        advances = self.get_queryset()
        context['total_advances'] = advances.count()
        context['outstanding_advances'] = advances.filter(is_repaid=False).count()
        context['total_outstanding_amount'] = sum(adv.outstanding_amount for adv in advances.filter(is_repaid=False))
        context['total_advance_amount'] = sum(adv.amount for adv in advances)
        return context


class EmployeeAdvanceCreateView(LoginRequiredMixin, CreateView):
    model = EmployeeAdvance
    form_class = EmployeeAdvanceForm
    template_name = 'employ/employee_advance_form.html'
    success_url = reverse_lazy('employ:employee_advance_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        response = super().form_valid(form)
        # قيد محاسبي
        try:
            self.object.create_advance_journal_entry(self.request.user)
            messages.success(
                self.request,
                f'تم إنشاء سلفة للموظف {self.object.employee.user.get_full_name()} بمبلغ {self.object.amount} ل.س'
            )
        except Exception as e:
            messages.error(self.request, f'خطأ في إنشاء القيد المحاسبي: {e}')
        return response


class EmployeeAdvanceDetailView(LoginRequiredMixin, DetailView):
    model = EmployeeAdvance
    template_name = 'employ/employee_advance_detail.html'
    context_object_name = 'advance'


class EmployeeAdvanceRepayView(LoginRequiredMixin, View):
    def post(self, request, pk):
        advance = get_object_or_404(EmployeeAdvance, pk=pk)
        display_name = advance.employee.user.get_full_name() or advance.employee.user.get_username()

        try:
            repayment_amount = Decimal(str(request.POST.get('repayment_amount', '0')))
        except (ValueError, InvalidOperation):
            repayment_amount = Decimal('0')

        if repayment_amount <= 0:
            messages.error(request, 'يجب إدخال مبلغ سداد صحيح.')
            return redirect('employ:employee_advance_detail', pk=pk)

        if repayment_amount > advance.outstanding_amount:
            messages.error(request, 'مبلغ السداد أكبر من المبلغ المتبقي.')
            return redirect('employ:employee_advance_detail', pk=pk)

        try:
            advance.create_repayment_entry(repayment_amount, request.user)
            messages.success(request, f'تم تسجيل سداد سلفة {display_name} بنجاح.')
        except Exception as e:
            messages.error(request, f'تعذر تسجيل السداد: {e}')

        return redirect('employ:employee_advance_detail', pk=pk)


# -----------------------------
# المدرّسون
# -----------------------------
class teachers(LoginRequiredMixin, ListView):
    model = Teacher
    template_name = 'employ/teachers.html'
    context_object_name = 'teachers'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        teachers = context.get('teachers') or context.get('object_list') or Teacher.objects.all()

        today = timezone.now().date()
        current_year = today.year
        current_month = today.month

        # فترة الراتب الافتراضية
        if today.day >= 25:
            period_date = today
        else:
            period_date = today.replace(day=1) - timedelta(days=1)

        salary_year = period_date.year
        salary_month = period_date.month

        teachers_data = []
        paid_count = 0
        unpaid_count = 0

        for teacher in teachers:
            monthly_sessions = teacher.get_monthly_sessions(salary_year, salary_month)
            salary_amount = teacher.calculate_monthly_salary(salary_year, salary_month)
            
            # التحقق من الرواتب اليدوية المدفوعة
            salary_status = ManualTeacherSalary.objects.filter(
                teacher=teacher,
                year=salary_year,
                month=salary_month,
                is_paid=True
            ).exists()

            paid_count += 1 if salary_status else 0
            unpaid_count += 0 if salary_status else 1

            teachers_data.append({
                'teacher': teacher,
                'monthly_sessions': monthly_sessions,
                'calculated_salary': salary_amount,
                'salary_status': salary_status,
            })

        today_sessions = (TeacherAttendance.objects
                          .filter(date=today, status='present')
                          .aggregate(total=Sum('session_count'))['total'] or 0)

        context.update({
            'today': today,
            'salary_year': salary_year,
            'salary_month': salary_month,
            'salary_period_label': f"{salary_year}/{salary_month:02d}",
            'salary_period_is_current': (salary_year == current_year and salary_month == current_month),
            'teachers_data': teachers_data,
            'paid_count': paid_count,
            'unpaid_count': unpaid_count,
            'today_sessions': today_sessions,
        })
        return context


def _prepare_teacher_cards(teachers):
    for teacher in teachers:
        try:
            teacher.branch_display = teacher.get_branch_display()
        except Exception:
            teacher.branch_display = getattr(teacher, 'branch', '')


def _teacher_cards_pdf_link_callback(uri, rel):
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
        pass


def _teacher_weasyprint_url_fetcher(url):
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


class TeacherCardsPrintView(LoginRequiredMixin, TemplateView):
    template_name = 'employ/teacher_cards_print.html'
    app_download_url = 'https://yaman2.pythonanywhere.com/'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        should_generate = self.request.GET.get('generate') == '1'
        teachers = []

        if should_generate:
            teachers = list(Teacher.objects.all().order_by('full_name'))

        _prepare_teacher_cards(teachers)

        per_page = 8
        pages = [teachers[i:i + per_page] for i in range(0, len(teachers), per_page)]
        if should_generate and not pages:
            pages = [[]]

        context.update({
            'should_generate': should_generate,
            'pages': pages,
            'teachers_total': len(teachers),
            'app_download_url': self.app_download_url,
            'app_qr_url': f"https://api.qrserver.com/v1/create-qr-code/?size=180x180&data={quote(self.app_download_url)}",
            'pdf': False,
        })
        return context


def teacher_cards_print_pdf(request):
    should_generate = request.GET.get('generate') == '1'
    teachers = []

    if should_generate:
        teachers = list(Teacher.objects.all().order_by('full_name'))

    _prepare_teacher_cards(teachers)

    per_page = 8
    pages = [teachers[i:i + per_page] for i in range(0, len(teachers), per_page)]
    if should_generate and not pages:
        pages = [[]]

    app_download_url = 'https://yaman2.pythonanywhere.com/'
    context = {
        'should_generate': should_generate,
        'pages': pages,
        'teachers_total': len(teachers),
        'app_download_url': app_download_url,
        'app_qr_url': f"https://api.qrserver.com/v1/create-qr-code/?size=180x180&data={quote(app_download_url)}",
        'pdf': True,
    }

    html = render_to_string('employ/teacher_cards_print.html', context, request=request)
    tmp_dir = os.path.join(settings.BASE_DIR, '_tmp_pdf')
    os.makedirs(tmp_dir, exist_ok=True)
    os.environ['TMP'] = tmp_dir
    os.environ['TEMP'] = tmp_dir
    tempfile.tempdir = tmp_dir

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename=\"teacher_cards.pdf\"'

    if WEASYPRINT_AVAILABLE:
        pdf_bytes = HTML(
            string=html,
            base_url=request.build_absolute_uri('/'),
            url_fetcher=_teacher_weasyprint_url_fetcher,
        ).write_pdf()
        response.write(pdf_bytes)
        return response

    _register_pdf_fonts()
    html = _inline_css_vars(html)
    pisa.CreatePDF(html, dest=response, link_callback=_teacher_cards_pdf_link_callback, encoding='UTF-8')
    return response


class CreateTeacherView(LoginRequiredMixin, CreateView):
    model = Teacher
    form_class = TeacherForm
    template_name = 'employ/teacher_form.html'
    success_url = reverse_lazy('employ:teachers')

    def form_valid(self, form):
        messages.success(self.request, 'تم إنشاء بيانات المعلم بنجاح.')
        return super().form_valid(form)

class TeacherUpdateView(LoginRequiredMixin, UpdateView):
    model = Teacher
    form_class = TeacherForm
    template_name = 'employ/teacher_form.html'
    success_url = reverse_lazy('employ:teachers')

    def form_valid(self, form):
        messages.success(self.request, 'تم تحديث بيانات المعلم بنجاح.')
        return super().form_valid(form)


# -----------------------------
# الموارد البشرية (قائمة الموظفين)
# -----------------------------
class hr(ListView):
    template_name = 'employ/hr.html'
    model = Employee
    context_object_name = 'employees'

    def get_queryset(self):
        queryset = Employee.objects.select_related('user').all()
        position = self.request.GET.get('position')
        search = self.request.GET.get('search')

        if position:
            queryset = queryset.filter(position=position)

        if search:
            queryset = queryset.filter(user__first_name__icontains=search) | queryset.filter(
                user__last_name__icontains=search
            )

        return queryset


class EmployeeCreateView(CreateView):
    form_class = EmployeeRegistrationForm
    template_name = 'employ/employee_form.html'
    success_url = reverse_lazy('employ:hr')

    def form_valid(self, form):
        response = super().form_valid(form)  # self.object = created User
        messages.success(self.request, f'تم تسجيل الموظف {self.object.get_full_name() or self.object.username} بنجاح.')
        return response


class EmployeeUpdateView(UpdateView):
    model = Employee
    fields = ['position', 'phone_number', 'salary']
    template_name = 'employ/employee_update.html'
    success_url = reverse_lazy('employ:hr')

    def get_context_data(self, **kwargs):
        from django.contrib.auth.forms import SetPasswordForm
        context = super().get_context_data(**kwargs)
        context['password_form'] = SetPasswordForm(self.object.user)
        return context

    def form_valid(self, form):
        # تغيير كلمة المرور إن طُلب
        if 'change_password' in self.request.POST:
            from django.contrib.auth.forms import SetPasswordForm
            password_form = SetPasswordForm(self.object.user, self.request.POST)
            if password_form.is_valid():
                password_form.save()
                messages.success(self.request, 'تم تغيير كلمة المرور بنجاح.')
            else:
                messages.error(self.request, 'خطأ في تغيير كلمة المرور.')
            return redirect(self.success_url)

        # تحديث بيانات المستخدم
        user = self.object.user
        user.username = self.request.POST.get('username', user.username)
        user.first_name = self.request.POST.get('first_name', user.first_name)
        user.last_name = self.request.POST.get('last_name', user.last_name)
        user.email = self.request.POST.get('email', user.email)
        user.save()

        response = super().form_valid(form)
        messages.success(self.request, 'تم تحديث بيانات الموظف بنجاح.')
        return response


class EmployeeDeleteView(DeleteView):
    model = Employee
    success_url = reverse_lazy('employ:hr')

    def delete(self, request, *args, **kwargs):
        employee = self.get_object()
        employee_name = employee.user.get_full_name() or employee.user.get_username()

        # حذف المستخدم سيحذف الموظف (on_delete=CASCADE)
        employee.user.delete()

        messages.success(request, f'تم حذف الموظف {employee_name} بنجاح.')
        return HttpResponseRedirect(self.success_url)


def select_employee(request):
    if request.method == 'POST':
        employee_id = request.POST.get('employee_id')
        return redirect('employ:employee_update', pk=employee_id)

    employees = Employee.objects.select_related('user').all()
    return render(request, 'employ/select_employee.html', {'employees': employees})


class EmployeeProfileView(LoginRequiredMixin, DetailView):
    model = Employee
    template_name = 'employ/employee_profile.html'
    context_object_name = 'employee'

    def _get_period_from_request(self):
        today = timezone.now().date()
        year_param = self.request.GET.get('year')
        month_param = self.request.GET.get('month')

        def sanitize(value, default, low=1, high=12):
            try:
                ivalue = int(value)
                if low <= ivalue <= high:
                    return ivalue
            except (TypeError, ValueError):
                pass
            return default

        if year_param is not None or month_param is not None:
            year = sanitize(year_param, today.year, low=1900, high=2100)
            month = sanitize(month_param, today.month)
            period_date = today.replace(year=year, month=month, day=1)
        else:
            period_date = today
            year = today.year
            month = today.month
        return today, period_date, year, month

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        employee = context['employee']
        today, period_date, salary_year, salary_month = self._get_period_from_request()

        # التحقق من وجود حقل employee في ExpenseEntry قبل استخدامه
        try:
            # التحقق من وجود الحقل أولاً
            ExpenseEntry._meta.get_field('employee')
            salary_qs = ExpenseEntry.objects.filter(employee=employee).select_related(
                'journal_entry'
            ).prefetch_related('journal_entry__transactions__account').order_by('-date', '-created_at')
            period_salary_qs = salary_qs.filter(date__year=salary_year, date__month=salary_month)
        except FieldDoesNotExist:
            # إذا لم يكن الحقل موجوداً، نستخدم فلتر بديل أو نعيد queryset فارغ
            salary_qs = ExpenseEntry.objects.none()
            period_salary_qs = ExpenseEntry.objects.none()

        salary_amount = employee.salary or Decimal('0')
        period_paid_total = period_salary_qs.aggregate(total=Sum('amount'))['total'] or Decimal('0')

        period_advances = list(EmployeeAdvance.objects.filter(
            employee=employee,
            is_repaid=False,
            date__year=salary_year,
            date__month=salary_month
        ))
        period_advance_outstanding = sum((adv.outstanding_amount for adv in period_advances), Decimal('0'))
        period_paid_total += period_advance_outstanding

        salary_status = period_salary_qs.exists() or (salary_amount > 0 and period_advance_outstanding >= salary_amount)
        salary_total_paid = salary_qs.aggregate(total=Sum('amount'))['total'] or Decimal('0')
        last_salary_payment = salary_qs.first()

        period_remaining_amount = salary_amount - period_paid_total
        if period_remaining_amount < Decimal('0'):
            period_remaining_amount = Decimal('0')

        salary_entries = []
        for payment in salary_qs[:10]:
            debit_account = None
            if payment.journal_entry:
                try:
                    debit_tx = payment.journal_entry.transactions.filter(is_debit=True).select_related('account').first()
                    if debit_tx and hasattr(debit_tx, 'account'):
                        debit_account = debit_tx.account
                except Exception:
                    debit_account = None
            salary_entries.append({
                'entry': payment,
                'debit_account': debit_account,
            })

        salary_account_code = f"501-{employee.pk:04d}"
        salary_account = Account.objects.filter(code=salary_account_code).first()

        vacations_qs = Vacation.objects.filter(employee=employee).order_by('-start_date')
        status_totals = dict(vacations_qs.values('status').annotate(total=Count('id')).values_list('status', 'total'))
        vacations_list = list(vacations_qs)
        vacation_status_breakdown = [
            {'code': code, 'label': label, 'count': status_totals.get(code, 0)}
            for code, label in Vacation.STATUS_CHOICES
        ]
        vacations_total = len(vacations_list)
        vacations_current_year = sum(1 for vac in vacations_list if vac.start_date.year == today.year)
        upcoming_vacations = [vac for vac in vacations_list if vac.start_date >= today][:5]
        pending_status = Vacation.STATUS_CHOICES[0][0] if Vacation.STATUS_CHOICES else None
        pending_vacations_count = status_totals.get(pending_status, 0) if pending_status else 0

        advances_qs = EmployeeAdvance.objects.filter(employee=employee).order_by('-date')
        advances_list = list(advances_qs)
        advance_outstanding_total = sum((adv.outstanding_amount for adv in advances_list), Decimal('0'))
        outstanding_advances = [adv for adv in advances_list if not adv.is_repaid]

        months = [
            (1, 'كانون الثاني'), (2, 'شباط'), (3, 'آذار'), (4, 'نيسان'),
            (5, 'أيار'), (6, 'حزيران'), (7, 'تموز'), (8, 'آب'),
            (9, 'أيلول'), (10, 'تشرين الأول'), (11, 'تشرين الثاني'), (12, 'كانون الأول')
        ]

        context.update({
            'salary_year': salary_year,
            'salary_month': salary_month,
            'salary_period_label': f"{salary_year}/{salary_month:02d}",
            'salary_period_is_current': (salary_year == today.year and salary_month == today.month),
            'salary_amount': salary_amount,
            'salary_status': salary_status,
            'salary_total_paid': salary_total_paid,
            'salary_period_paid_total': period_paid_total,
            'salary_period_remaining': period_remaining_amount,
            'salary_period_advance_outstanding': period_advance_outstanding,
            'salary_entries': salary_entries,
            'last_salary_payment': last_salary_payment,
            'salary_account': salary_account,
            'salary_account_code': salary_account_code,
            'vacations': vacations_list,
            'salary_period_advances': period_advances,
            'display_name': _employee_full_name(employee),
            'vacations_total': vacations_total,
            'vacations_current_year': vacations_current_year,
            'vacation_status_breakdown': vacation_status_breakdown,
            'vacation_pending_count': pending_vacations_count,
            'upcoming_vacations': upcoming_vacations,
            'advances': advances_list,
            'advances_total': len(advances_list),
            'advance_outstanding_total': advance_outstanding_total,
            'outstanding_advances_count': len(outstanding_advances),
            'months': months,
            'today': today,
        })
        return context


# -----------------------------
# الإجازات
# -----------------------------
class VacationListView(ListView):
    model = Vacation
    template_name = 'employ/vacation_list.html'
    context_object_name = 'vacations'

    def get_queryset(self):
        queryset = Vacation.objects.select_related('employee__user').all()

        # فلاتر
        employee_name = self.request.GET.get('employee_name')
        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')

        if employee_name:
            queryset = queryset.filter(employee__user__first_name__icontains=employee_name) | queryset.filter(
                employee__user__last_name__icontains=employee_name
            )

        if start_date:
            queryset = queryset.filter(start_date__gte=start_date)

        if end_date:
            queryset = queryset.filter(end_date__lte=end_date)

        return queryset.order_by('-start_date')


class VacationCreateView(CreateView):
    model = Vacation
    form_class = AdminVacationForm
    template_name = 'employ/vacation_form.html'
    success_url = reverse_lazy('employ:vacation_list')

    def get_initial(self):
        initial = super().get_initial()
        employee_id = self.request.GET.get('employee')
        if employee_id:
            try:
                initial['employee'] = Employee.objects.get(pk=employee_id)
            except Employee.DoesNotExist:
                pass
        return initial

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, 'تم تسجيل الإجازة بنجاح.')
        return response


class VacationUpdateView(UpdateView):
    model = Vacation
    form_class = AdminVacationForm
    template_name = 'employ/vacation_form.html'
    success_url = reverse_lazy('employ:vacation_list')

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, 'تم تحديث الإجازة بنجاح.')
        return response


# -----------------------------
# إدارة رواتب المدرسين (عرض)
# -----------------------------
class SalaryManagementView(TemplateView):
    template_name = 'employ/salary_management.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        selected_year = int(self.request.GET.get('year', timezone.now().year))
        selected_month = int(self.request.GET.get('month', timezone.now().month))

        months = [
            (1, 'كانون الثاني'), (2, 'شباط'), (3, 'آذار'), (4, 'نيسان'),
            (5, 'أيار'), (6, 'حزيران'), (7, 'تموز'), (8, 'آب'),
            (9, 'أيلول'), (10, 'تشرين الأول'), (11, 'تشرين الثاني'), (12, 'كانون الأول')
        ]

        teachers = Teacher.objects.all()
        teachers_salary_data = []
        total_calculated_amount = Decimal('0.00')
        paid_count = 0
        unpaid_count = 0

        for teacher in teachers:
            monthly_sessions = teacher.get_monthly_sessions(selected_year, selected_month)
            calculated_salary = teacher.calculate_monthly_salary(selected_year, selected_month)
            
            # التحقق من الرواتب اليدوية المدفوعة
            salary_status = ManualTeacherSalary.objects.filter(
                teacher=teacher,
                year=selected_year,
                month=selected_month,
                is_paid=True
            ).exists()

            teachers_salary_data.append({
                'teacher': teacher,
                'monthly_sessions': monthly_sessions,
                'calculated_salary': calculated_salary,
                'salary_status': salary_status
            })

            total_calculated_amount += calculated_salary
            if salary_status:
                paid_count += 1
            else:
                unpaid_count += 1

        context.update({
            'teachers_salary_data': teachers_salary_data,
            'selected_year': selected_year,
            'selected_month': selected_month,
            'months': months,
            'total_calculated_amount': total_calculated_amount,
            'paid_count': paid_count,
            'unpaid_count': unpaid_count,
            'today': timezone.now().date()
        })

        return context


# -----------------------------
# Teacher Profile View
# -----------------------------
class TeacherProfileView(DetailView):
    model = Teacher
    template_name = 'employ/teacher_profile.html'
    context_object_name = 'teacher'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        teacher = self.get_object()
        today = timezone.now().date()
        latest_attendance_date = (TeacherAttendance.objects.filter(teacher=teacher)
                                  .order_by('-date')
                                  .values_list('date', flat=True)
                                  .first())
        attendance_date = latest_attendance_date or today
        
        # الحضور اليومي
        daily_attendance_entries = TeacherAttendance.objects.filter(
            teacher=teacher, 
            date=attendance_date
        ).order_by('branch')
        
        # الحضور الشهري (هذا الشهر)
        monthly_attendance = TeacherAttendance.objects.filter(
            teacher=teacher,
            date__year=attendance_date.year,
            date__month=attendance_date.month
        )
        
        # الحضور السنوي (هذه السنة)
        yearly_attendance = TeacherAttendance.objects.filter(
            teacher=teacher,
            date__year=attendance_date.year
        )
        
        # إحصائيات شهرية مفصلة
        monthly_present = monthly_attendance.filter(status='present')
        monthly_present_days = monthly_present.count()
        monthly_total_sessions = sum(att.total_sessions for att in monthly_present)
        
        # إحصائيات سنوية مفصلة
        yearly_present = yearly_attendance.filter(status='present')
        yearly_present_days = yearly_present.count()
        yearly_total_sessions = sum(att.total_sessions for att in yearly_present)
        
        # حساب متوسط الجلسات اليومية
        avg_daily_sessions_monthly = 0
        if monthly_present_days > 0:
            avg_daily_sessions_monthly = monthly_total_sessions / monthly_present_days
        
        avg_daily_sessions_yearly = 0
        if yearly_present_days > 0:
            avg_daily_sessions_yearly = yearly_total_sessions / yearly_present_days
        
        # حساب نسبة الحضور
        attendance_rate_monthly = 0
        if monthly_attendance.count() > 0:
            attendance_rate_monthly = (monthly_present_days / monthly_attendance.count()) * 100
        
        attendance_rate_yearly = 0
        if yearly_attendance.count() > 0:
            attendance_rate_yearly = (yearly_present_days / yearly_attendance.count()) * 100
        
        context.update({
            'today': today,
            'daily_attendance_date': attendance_date,
            'daily_attendance_entries': daily_attendance_entries,
            'labels': self._get_labels(),
            
            # إحصائيات شهرية مفصلة
            'monthly_stats': {
                'total_days': monthly_attendance.count(),
                'present_days': monthly_present_days,
                'absent_days': monthly_attendance.filter(status='absent').count(),
                'late_days': monthly_attendance.filter(status='late').count(),
                'total_sessions': monthly_total_sessions,
                'avg_daily_sessions': round(avg_daily_sessions_monthly, 1),
                'attendance_rate': round(attendance_rate_monthly, 1),
            },
            
            # إحصائيات سنوية مفصلة
            'yearly_stats': {
                'total_days': yearly_attendance.count(),
                'present_days': yearly_present_days,
                'absent_days': yearly_attendance.filter(status='absent').count(),
                'late_days': yearly_attendance.filter(status='late').count(),
                'total_sessions': yearly_total_sessions,
                'avg_daily_sessions': round(avg_daily_sessions_yearly, 1),
                'attendance_rate': round(attendance_rate_yearly, 1),
            },
            
            # قائمة الحضور الأخيرة (10 أيام)
            'recent_attendance': TeacherAttendance.objects.filter(
                teacher=teacher
            ).order_by('-date')[:10],
            
            # جلب جميع أيام الحضور للسنة الحالية
            'all_attendance_days': TeacherAttendance.objects.filter(
                teacher=teacher,
                date__year=today.year
            ).order_by('-date'),
            
            # إحصائيات الحضور حسب الشهور
            'monthly_attendance_stats': self.get_monthly_attendance_stats(teacher, today.year),
        })
        
        # الرواتب اليدوية
        selected_year = self.request.GET.get('year', attendance_date.year)
        try:
            selected_year = int(selected_year)
        except:
            selected_year = attendance_date.year

        branch_monthly_tables = self.get_branch_monthly_tables(teacher)
        branch_hourly_rates = self.get_branch_hourly_rates(teacher)
        advance_account = teacher.get_teacher_advance_account()
        advance_account_balance = advance_account.get_net_balance() if advance_account else Decimal('0.00')
        
        manual_salaries = ManualTeacherSalary.objects.filter(
            teacher=teacher,
            year=selected_year
        ).order_by('-month')
        
        # حساب الإجماليات
        total_gross_year = sum(s.gross_salary for s in manual_salaries)
        total_advances_year = sum(s.advance_deduction for s in manual_salaries)
        total_net_year = sum(s.net_salary for s in manual_salaries)
        
        # الرواتب المدفوعة
        paid_salaries = manual_salaries.filter(is_paid=True)
        total_paid_year = sum(s.net_salary for s in paid_salaries)
        paid_count_year = paid_salaries.count()
        
        # المتبقي للدفع
        total_remaining = total_net_year - total_paid_year
        
        # السلف المعلقة
        total_advances_outstanding = teacher.get_total_advances()
        
        # نطاق السنوات
        current_year = today.year
        years_range = range(current_year - 5, current_year + 2)
        
        # إضافة بيانات الرواتب
        context.update({
            'manual_salaries': manual_salaries,
            'selected_year': selected_year,
            'years_range': years_range,
            'total_gross_year': total_gross_year,
            'total_advances_year': total_advances_year,
            'total_net_year': total_net_year,
            'total_paid_year': total_paid_year,
            'paid_count_year': paid_count_year,
            'total_remaining': total_remaining,
            'total_advances_outstanding': total_advances_outstanding,
            'branch_monthly_tables': branch_monthly_tables,
            'branch_hourly_rates': branch_hourly_rates,
            'advance_account': advance_account,
            'advance_account_balance': advance_account_balance,
        })
        
        return context
    
    def get_monthly_attendance_stats(self, teacher, year):
        """الحصول على إحصائيات الحضور لكل شهر في السنة"""
        from django.db.models import Count, Sum
        from django.db.models.functions import ExtractMonth
        
        stats = []
        month_names = {
            1: 'كانون الثاني', 2: 'شباط', 3: 'آذار', 4: 'نيسان',
            5: 'أيار', 6: 'حزيران', 7: 'تموز', 8: 'آب',
            9: 'أيلول', 10: 'تشرين الأول', 11: 'تشرين الثاني', 12: 'كانون الأول'
        }
        
        for month_num in range(1, 13):
            monthly_data = TeacherAttendance.objects.filter(
                teacher=teacher,
                date__year=year,
                date__month=month_num
            )
            
            present_days = monthly_data.filter(status='present').count()
            total_days = monthly_data.count()
            
            if total_days > 0:
                attendance_rate = (present_days / total_days) * 100
                total_sessions = sum(att.total_sessions for att in monthly_data.filter(status='present'))
                
                stats.append({
                    'month': month_num,
                    'month_name': month_names.get(month_num, f'شهر {month_num}'),
                    'present_days': present_days,
                    'total_days': total_days,
                    'attendance_rate': round(attendance_rate, 1),
                    'total_sessions': total_sessions,
                    'avg_sessions': round(total_sessions / present_days, 1) if present_days > 0 else 0,
                })
        
        return stats

    def _get_teacher_branches(self, teacher):
        branches = teacher.get_branches_list()
        return branches or [Teacher.BranchChoices.SCIENTIFIC]

    def _get_attendance_branches(self, teacher, year=None):
        qs = TeacherAttendance.objects.filter(teacher=teacher)
        if year is not None:
            qs = qs.filter(date__year=year)
        branches = list(qs.values_list('branch', flat=True).distinct())
        return branches

    def _branch_label(self, branch):
        try:
            return Teacher.BranchChoices(branch).label
        except Exception:
            return branch

    def _branch_title(self, branch):
        title_map = {
            Teacher.BranchChoices.SCIENTIFIC: 'البكالوريا العلمي',
            Teacher.BranchChoices.LITERARY: 'البكالوريا الأدبي',
            Teacher.BranchChoices.NINTH_GRADE: 'التاسع',
            Teacher.BranchChoices.PREPARATORY: 'التمهيدي',
        }
        return title_map.get(branch, self._branch_label(branch))

    def _get_labels(self):
        return {
            'profile_title': '\u0645\u0644\u0641 \u0627\u0644\u0623\u0633\u062a\u0627\u0630',
            'attendance_button': '\u062d\u0636\u0648\u0631 \u0627\u0644\u0623\u0633\u062a\u0627\u0630',
            'advance_button': '\u0633\u0644\u0641\u0629 \u062c\u062f\u064a\u062f\u0629',
            'salary_button': '\u0625\u0636\u0627\u0641\u0629 \u0631\u0627\u062a\u0628',
            'basic_info': '\u0627\u0644\u0628\u064a\u0627\u0646\u0627\u062a \u0627\u0644\u0623\u0633\u0627\u0633\u064a\u0629',
            'phone_number': '\u0631\u0642\u0645 \u0627\u0644\u0647\u0627\u062a\u0641',
            'not_set': '\u063a\u064a\u0631 \u0645\u062d\u062f\u062f',
            'hire_date': '\u062a\u0627\u0631\u064a\u062e \u0627\u0644\u062a\u0639\u064a\u064a\u0646',
            'salary_type': '\u0646\u0648\u0639 \u0627\u0644\u0631\u0627\u062a\u0628',
            'hourly_rate_general': '\u0627\u0644\u0633\u0627\u0639\u0629 \u0627\u0644\u0639\u0627\u0645\u0629',
            'notes': '\u0645\u0644\u0627\u062d\u0638\u0627\u062a',
            'hourly_rate_by_branch': '\u0633\u0639\u0631 \u0627\u0644\u0633\u0627\u0639\u0629 \u062d\u0633\u0628 \u0627\u0644\u0641\u0631\u0639',
            'no_branches': '\u0644\u0627 \u064a\u0648\u062c\u062f \u0641\u0631\u0648\u0639 \u0645\u062d\u062f\u062f\u0629',
            'daily_attendance': '\u0627\u0644\u062d\u0636\u0648\u0631 \u0627\u0644\u064a\u0648\u0645\u064a',
            'course_or_branch': '\u0646\u0648\u0639 \u0627\u0644\u062f\u0648\u0631\u0629/\u0627\u0644\u0641\u0631\u0639',
            'status': '\u0627\u0644\u062d\u0627\u0644\u0629',
            'session_count': '\u0639\u062f\u062f \u0627\u0644\u062c\u0644\u0633\u0627\u062a',
            'half_sessions': '\u0623\u0646\u0635\u0627\u0641 \u062c\u0644\u0633\u0627\u062a',
            'total': '\u0627\u0644\u0625\u062c\u0645\u0627\u0644\u064a',
            'wage': '\u0627\u0644\u0623\u062c\u0631',
            'no_daily_attendance': '\u0644\u0627 \u064a\u0648\u062c\u062f \u062d\u0636\u0648\u0631 \u0645\u0633\u062c\u0644 \u0644\u0647\u0630\u0627 \u0627\u0644\u064a\u0648\u0645.',
            'monthly_attendance_by_branch': '\u0627\u0644\u062d\u0636\u0648\u0631 \u0627\u0644\u0634\u0647\u0631\u064a \u062d\u0633\u0628 \u0627\u0644\u0641\u0631\u0639',
            'year': '\u0627\u0644\u0633\u0646\u0629',
            'hourly_rate': '\u0633\u0639\u0631 \u0627\u0644\u0633\u0627\u0639\u0629',
            'month': '\u0627\u0644\u0634\u0647\u0631',
            'due_amount': '\u0627\u0644\u0623\u062c\u0631 \u0627\u0644\u0645\u0633\u062a\u062d\u0642',
            'no_monthly_attendance': '\u0644\u0627 \u064a\u0648\u062c\u062f \u062d\u0636\u0648\u0631 \u0634\u0647\u0631\u064a \u0645\u0633\u062c\u0644 \u0644\u0647\u0630\u0647 \u0627\u0644\u0633\u0646\u0629.',
            'monthly_formula': '\u0627\u0644\u0623\u062c\u0631 \u0627\u0644\u0645\u0633\u062a\u062d\u0642 = \u0639\u062f\u062f \u0627\u0644\u062c\u0644\u0633\u0627\u062a \u00d7 \u0633\u0639\u0631 \u0627\u0644\u0633\u0627\u0639\u0629',
            'advance_balance_title': '\u0631\u0635\u064a\u062f \u0633\u0644\u0641 \u0627\u0644\u0645\u062f\u0631\u0633 (\u0645\u0646 \u0645\u064a\u0632\u0627\u0646 \u0627\u0644\u0645\u0631\u0627\u062c\u0639\u0629)',
            'account': '\u0627\u0644\u062d\u0633\u0627\u0628',
            'balance': '\u0627\u0644\u0631\u0635\u064a\u062f',
            'no_advance_account': '\u0644\u0627 \u064a\u0648\u062c\u062f \u062d\u0633\u0627\u0628 \u0633\u0644\u0641\u0629 \u0644\u0647\u0630\u0627 \u0627\u0644\u0645\u062f\u0631\u0633.',
            'currency': '\u0644.\u0633',
        }

    def get_branch_monthly_tables(self, teacher, year=None):
        month_names = dict(ManualTeacherSalary.MONTH_CHOICES)
        tables = []
        branches = self._get_attendance_branches(teacher, year) or self._get_teacher_branches(teacher)
        for branch in branches:
            hourly_rate = teacher.get_hourly_rate_for_branch(branch)
            rows = []
            monthly_qs = TeacherAttendance.objects.filter(
                teacher=teacher,
                branch=branch,
                status='present'
            )
            if year:
                monthly_qs = monthly_qs.filter(date__year=year)

            monthly_totals = {}
            for att in monthly_qs:
                key = (att.date.year, att.date.month)
                monthly_totals[key] = monthly_totals.get(key, Decimal('0.00')) + att.total_sessions

            for (year_num, month_num) in sorted(monthly_totals.keys()):
                total_sessions = monthly_totals[(year_num, month_num)]
                if total_sessions <= 0:
                    continue
                total_salary = total_sessions * (hourly_rate or Decimal('0.00'))
                month_name = month_names.get(month_num, str(month_num))
                rows.append({
                    'month': month_num,
                    'month_name': month_name,
                    'month_label': f"{month_name} - {year_num}",
                    'total_sessions': total_sessions,
                    'total_salary': total_salary,
                })
            if rows:
                tables.append({
                    'branch': branch,
                    'branch_label': self._branch_label(branch),
                    'branch_title': self._branch_title(branch),
                    'hourly_rate': hourly_rate,
                    'rows': rows,
                })
        return tables

    def get_branch_hourly_rates(self, teacher):
        items = []
        branches = self._get_teacher_branches(teacher)
        for branch in branches:
            items.append({
                'branch': branch,
                'branch_label': self._branch_label(branch),
                'branch_title': self._branch_title(branch),
                'hourly_rate': teacher.get_hourly_rate_for_branch(branch),
            })
        return items


class TeacherDeleteView(LoginRequiredMixin, DeleteView):
    model = Teacher
    template_name = 'employ/teacher_confirm_delete.html'
    success_url = reverse_lazy('employ:teachers')

    def delete(self, request, *args, **kwargs):
        teacher = self.get_object()
        messages.success(request, f'تم حذف بيانات المعلم {teacher.full_name}.')
        return super().delete(request, *args, **kwargs)


# -----------------------------
# سلف المدرس
# -----------------------------
class TeacherAdvanceCreateView(LoginRequiredMixin, CreateView):
    model = TeacherAdvance
    template_name = 'employ/teacher_advance_form.html'
    fields = ['date', 'amount', 'purpose']
    
    def get_queryset(self):
        return TeacherAdvance.objects.none()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['teacher'] = get_object_or_404(Teacher, pk=self.kwargs['teacher_id'])
        context['advance'] = None
        return context

    def form_valid(self, form):
        teacher = get_object_or_404(Teacher, pk=self.kwargs['teacher_id'])
        
        advance = form.save(commit=False)
        advance.teacher = teacher
        advance.created_by = self.request.user
        advance.save()

        try:
            advance.create_advance_journal_entry(self.request.user)
            messages.success(self.request, f'تم إنشاء سلفة للمدرس {teacher.full_name} بمبلغ {advance.amount} ل.س')
        except Exception as e:
            messages.error(self.request, f'خطأ في إنشاء القيد المحاسبي: {e}')

        return redirect('employ:teacher_profile', pk=teacher.pk)


class TeacherAdvanceUpdateView(LoginRequiredMixin, UpdateView):
    model = TeacherAdvance
    template_name = 'employ/teacher_advance_form.html'
    fields = ['date', 'amount', 'purpose']

    def get_queryset(self):
        teacher = get_object_or_404(Teacher, pk=self.kwargs['teacher_id'])
        return TeacherAdvance.objects.filter(teacher=teacher)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['teacher'] = self.object.teacher
        context['advance'] = self.object
        return context

    def form_valid(self, form):
        advance = form.save()
        try:
            advance.sync_advance_journal_entry(self.request.user)
            messages.success(
                self.request,
                f'تم تحديث سلفة المدرس {advance.teacher.full_name} إلى {advance.amount} ل.س.'
            )
        except Exception as exc:
            messages.error(self.request, f'حدث خطأ أثناء تحديث القيد المحاسبي: {exc}')

        return redirect('employ:teacher_advance_list', teacher_id=advance.teacher.pk)


class TeacherAdvanceListView(LoginRequiredMixin, ListView):
    template_name = 'employ/teacher_advance_list.html'
    context_object_name = 'advances'

    def get_queryset(self):
        from accounts.models import TeacherAdvance
        teacher = get_object_or_404(Teacher, pk=self.kwargs['teacher_id'])
        return (TeacherAdvance.objects
                .filter(teacher=teacher)
                .select_related('teacher')
                .order_by('-date', '-created_at'))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        teacher = get_object_or_404(Teacher, pk=self.kwargs['teacher_id'])
        advances = context['advances']
        context.update({
            'teacher': teacher,
            'total_advances': advances.count(),
            'outstanding_count': advances.filter(is_repaid=False).count(),
            'total_amount': sum(a.amount for a in advances),
            'total_outstanding_amount': sum(a.outstanding_amount for a in advances if not a.is_repaid),
        })
        return context


def no_permission(request):
    return render(request, "503.html", status=503)


def require_employee_perm(permission_code):
    def decorator(view_func):
        def wrapper(request, *args, **kwargs):
            # تنفيذ الكود الخاص بالصلاحية
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


# -----------------------------
# إدارة حسابات السلف للأساتذة
# -----------------------------
class CreateTeacherAdvanceAccountView(View):
    """إنشاء حساب سلفة للمدرس يدوياً فقط"""
    
    def post(self, request, pk):
        teacher = get_object_or_404(Teacher, pk=pk)
        
        # التحقق إذا كان الحساب موجوداً
        existing_account = teacher.get_teacher_advance_account()
        if existing_account:
            messages.info(request, f'حساب السلفة للمدرس {teacher.full_name} موجود بالفعل')
            return redirect('employ:teacher_profile', pk=teacher.pk)
        
        # إنشاء الحساب يدوياً
        from accounts.models import Account
        try:
            # كود الحساب: 121-5XXX حيث XXX هو ID المدرس
            account_code = f"121-5{teacher.pk:03d}"
            
            account, created = Account.objects.get_or_create(
                code=account_code,
                defaults={
                    'name': f'Teacher Advance - {teacher.full_name}',
                    'name_ar': f'سلف أستاذ - {teacher.full_name}',
                    'account_type': 'ASSET',
                    'is_active': True,
                }
            )
            
            if created:
                messages.success(request, f'تم إنشاء حساب سلفة للمدرس {teacher.full_name}: {account.code}')
            else:
                messages.info(request, f'حساب السلفة موجود مسبقاً: {account.code}')
                
        except Exception as e:
            messages.error(request, f'خطأ في إنشاء حساب السلفة: {e}')
        
        return redirect('employ:teacher_profile', pk=teacher.pk)

import re
from decimal import Decimal, InvalidOperation
# -----------------------------
# إدارة الرواتب اليدوية
# -----------------------------
class AddManualSalaryView(LoginRequiredMixin, View):
    """إضافة راتب يدوي للمدرس"""
    
    template_name = 'employ/add_manual_salary.html'
    
    def get(self, request, pk):
        teacher = get_object_or_404(Teacher, pk=pk)
        
        # حساب السلف غير المسددة
        total_advances = teacher.get_total_advances()
        
        # الشهور المتاحة
        current_year = date.today().year
        years_range = range(current_year - 5, current_year + 2)
        selected_year = request.GET.get('year')
        selected_month = request.GET.get('month')
        try:
            selected_year = int(selected_year) if selected_year else date.today().year
        except (TypeError, ValueError):
            selected_year = date.today().year
        try:
            selected_month = int(selected_month) if selected_month else date.today().month
        except (TypeError, ValueError):
            selected_month = date.today().month
        if selected_month < 1 or selected_month > 12:
            selected_month = date.today().month
        auto_gross_salary = teacher.calculate_monthly_salary(selected_year, selected_month)
        
        context = {
            'teacher': teacher,
            'total_advances': total_advances,
            'years_range': years_range,
            'today': date.today(),
            'selected_year': selected_year,
            'selected_month': selected_month,
            'auto_gross_salary': auto_gross_salary,
        }
        return render(request, self.template_name, context)
    
    def post(self, request, pk):
        teacher = get_object_or_404(Teacher, pk=pk)
        
        # **1. تحقق من السنة والشهر بشكل آمن**
        try:
            year_str = request.POST.get('year', '').strip()
            month_str = request.POST.get('month', '').strip()
            
            # إذا كانت فارغة، استخدم القيم الحالية
            if not year_str or not year_str.isdigit():
                year = date.today().year
            else:
                year = int(year_str)
            
            if not month_str or not month_str.isdigit():
                month = date.today().month
            else:
                month = int(month_str)
                
            # تأكد من أن الشهر بين 1 و 12
            if month < 1 or month > 12:
                month = date.today().month
                
        except:
            # إذا فشل كل شيء، استخدم التاريخ الحالي
            today = date.today()
            year = today.year
            month = today.month
        
        # **2. الحصول على القيم المالية**
        gross_salary_str = request.POST.get('gross_salary', '').strip()
        advance_deduction_str = request.POST.get('advance_deduction', '0').strip()
        notes = request.POST.get('notes', '')
        auto_salary = request.POST.get('auto_salary') == '1'
        
        # **3. التحقق من وجود راتب لنفس الشهر**
        existing = ManualTeacherSalary.objects.filter(
            teacher=teacher, year=year, month=month
        ).exists()
        
        if existing:
            messages.error(request, f'❌ تم إضافة راتب لهذا الشهر مسبقاً!')
            return redirect('employ:add_manual_salary', pk=teacher.pk)
        
        # **4. التحقق من الراتب الإجمالي**
        if auto_salary:
            gross_salary = teacher.calculate_monthly_salary(year, month)
        elif not gross_salary_str:
            messages.error(request, '❌ يجب إدخال قيمة للراتب الإجمالي')
            return redirect('employ:add_manual_salary', pk=teacher.pk)
        else:
            gross_salary = None
        
        # **5. محاولة تحويل الراتب إلى رقم**
        try:
            # تنظيف النص
            advance_clean = advance_deduction_str.replace(',', '').replace(' ', '')
            
            # تحويل إلى Decimal
            if gross_salary is None:
                gross_clean = gross_salary_str.replace(',', '').replace(' ', '')
                gross_salary = Decimal(gross_clean)
            advance_deduction = Decimal(advance_clean) if advance_clean else Decimal('0')
            
        except:
            messages.error(request, '❌ قيمة الراتب غير صحيحة. استخدم أرقاماً فقط')
            return redirect('employ:add_manual_salary', pk=teacher.pk)
        
        # **6. التحقق من أن الراتب أكبر من الصفر**
        if gross_salary <= 0:
            messages.error(request, '❌ يجب أن يكون الراتب أكبر من صفر')
            return redirect('employ:add_manual_salary', pk=teacher.pk)
        
        # **7. حساب الصافي وإنشاء الراتب**
        net_salary = gross_salary - advance_deduction
        
        try:
            salary = ManualTeacherSalary.objects.create(
                teacher=teacher,
                year=year,
                month=month,
                gross_salary=gross_salary,
                advance_deduction=advance_deduction,
                net_salary=net_salary,
                notes=notes,
                created_by=request.user
            )
            
            messages.success(request, f'✅ تم إضافة راتب شهر {month}/{year} للمدرس {teacher.full_name}')
            return redirect('employ:teacher_profile', pk=teacher.pk)
            
        except Exception as e:
            messages.error(request, f'❌ خطأ في الحفظ: {str(e)}')
            return redirect('employ:add_manual_salary', pk=teacher.pk)
        
class EditManualSalaryView(LoginRequiredMixin, View):
    """تعديل راتب يدوي"""
    
    template_name = 'employ/edit_manual_salary.html'
    
    def get(self, request, pk):
        salary = get_object_or_404(ManualTeacherSalary, pk=pk)
        
        # التحقق من صلاحية التعديل (غير مدفوع)
        if salary.is_paid:
            messages.error(request, 'لا يمكن تعديل راتب تم دفعه')
            return redirect('employ:teacher_profile', pk=salary.teacher.pk)
        
        # حساب السلف غير المسددة
        total_advances = salary.teacher.get_total_advances(salary.year, salary.month)
        
        context = {
            'salary': salary,
            'teacher': salary.teacher,
            'total_advances': total_advances,
        }
        return render(request, self.template_name, context)
    
    def post(self, request, pk):
        salary = get_object_or_404(ManualTeacherSalary, pk=pk)
        
        # التحقق من صلاحية التعديل
        if salary.is_paid:
            messages.error(request, 'لا يمكن تعديل راتب تم دفعه')
            return redirect('employ:teacher_profile', pk=salary.teacher.pk)
        
        try:
            gross_salary = Decimal(request.POST.get('gross_salary', '0'))
            advance_deduction = Decimal(request.POST.get('advance_deduction', '0'))
            notes = request.POST.get('notes', '')
            
            # التحقق من عدم تجاوز خصم السلف
            if advance_deduction > gross_salary:
                messages.error(request, 'لا يمكن أن يتجاوز خصم السلف قيمة الراتب الإجمالي')
                return redirect('employ:edit_manual_salary', pk=salary.pk)
            
            # تحديث الراتب
            salary.gross_salary = gross_salary
            salary.advance_deduction = advance_deduction
            salary.notes = notes
            salary.save()
            
            messages.success(request, 'تم تعديل الراتب بنجاح')
            return redirect('employ:teacher_profile', pk=salary.teacher.pk)
            
        except Exception as e:
            messages.error(request, f'خطأ في تعديل الراتب: {e}')
            return redirect('employ:edit_manual_salary', pk=salary.pk)


class PayManualSalaryView(LoginRequiredMixin, View):
    """دفع راتب يدوي"""
    
    def post(self, request, pk):
        salary = get_object_or_404(ManualTeacherSalary, pk=pk)
        
        # التحقق من عدم دفعه مسبقاً
        if salary.is_paid:
            messages.warning(request, 'هذا الراتب مدفوع مسبقاً')
            return redirect('employ:teacher_profile', pk=salary.teacher.pk)
        
        try:
            # تسجيل الدفع فقط
            salary.is_paid = True
            salary.paid_date = timezone.now().date()
            salary.save()
            
            # تحديث حالة السلف إذا كان هناك خصم
            if salary.advance_deduction > 0:
                from accounts.models import TeacherAdvance
                # تحديث السلف القديمة لهذا الشهر
                advances = TeacherAdvance.objects.filter(
                    teacher=salary.teacher,
                    date__year=salary.year,
                    date__month=salary.month,
                    is_repaid=False
                ).order_by('date')
                
                remaining_deduction = salary.advance_deduction
                for advance in advances:
                    if remaining_deduction <= 0:
                        break
                    
                    if advance.outstanding_amount <= remaining_deduction:
                        advance.is_repaid = True
                        advance.repaid_amount = advance.outstanding_amount
                        remaining_deduction -= advance.outstanding_amount
                    else:
                        advance.repaid_amount += remaining_deduction
                        remaining_deduction = Decimal('0')
                    
                    advance.save()
            
            messages.success(request, f'تم دفع راتب شهر {salary.get_month_display()} {salary.year} للمدرس {salary.teacher.full_name}')
            
        except Exception as e:
            messages.error(request, f'خطأ في عملية الدفع: {e}')
        
        return redirect('employ:teacher_profile', pk=salary.teacher.pk)


class ViewManualSalaryView(LoginRequiredMixin, DetailView):
    """عرض تفاصيل راتب يدوي"""
    
    model = ManualTeacherSalary
    template_name = 'employ/view_manual_salary.html'
    context_object_name = 'salary'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['teacher'] = self.object.teacher
        return context
