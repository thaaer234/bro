# accounts/thaaer_reports_views.py
"""Thaaer Reports Views - Superuser only financial reports

Provides:
- Annual Budget Report
- Semester Budget Report
- Comprehensive Financial Report

All reports inherit from ThaaerReportsMixin for common utilities.
"""

from decimal import Decimal
from django.shortcuts import render
from django.db.models import Sum
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils.decorators import method_decorator
from django.views import View
from datetime import datetime, timedelta
from django.utils import timezone
from .models import CostCenter, Transaction, Course, Studentenrollment, Account, TeacherAdvance, EmployeeAdvance
try:
    from employ.models import Employee, Teacher
except ImportError:
    Employee = None
    Teacher = None

from .excel_utils import FinancialReportExporter, create_excel_response
from django.utils.dateparse import parse_date
from datetime import date
from django.shortcuts import get_object_or_404
from academic_years.services.session import get_current_academic_year

def _current_academic_year(request):
    return getattr(request, "current_academic_year", None) or get_current_academic_year(request)





def superuser_required(user):
    return user.is_active and user.is_superuser


class ThaaerReportsMixin:
    """Common utilities for Thaaer reports"""

    def get_date_range(self, request):
        """Extract start/end dates from request or default to current year"""
        start = request.GET.get("start_date")
        end = request.GET.get("end_date")
        if start:
            try:
                start = datetime.strptime(start, "%Y-%m-%d").date()
            except ValueError:
                start = None
        if end:
            try:
                end = datetime.strptime(end, "%Y-%m-%d").date()
            except ValueError:
                end = None
        # Default: whole current year
        if not start and not end:
            today = timezone.now().date()
            start = today.replace(month=1, day=1)
            end = today.replace(month=12, day=31)
        return start, end

    def format_currency(self, value):
        return f"{value:,.2f}" if value is not None else "0.00"


@method_decorator([login_required, user_passes_test(superuser_required)], name="dispatch")
class ThaaerAnnualBudgetReportView(ThaaerReportsMixin, View):
    template_name = "accounts/reports/thaaer/annual_budget.html"

    def get(self, request):
        start, end = self.get_date_range(request)
        # Aggregate expenses (debits - credits)
        expense_debits = Transaction.objects.filter(
            journal_entry__date__gte=start,
            journal_entry__date__lte=end,
            is_debit=True,
            account__account_type="EXPENSE",
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

        expense_credits = Transaction.objects.filter(
            journal_entry__date__gte=start,
            journal_entry__date__lte=end,
            is_debit=False,
            account__account_type="EXPENSE",
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

        expenses_val = expense_debits - expense_credits

        # Aggregate revenues (credits - debits)
        revenue_credits = Transaction.objects.filter(
            journal_entry__date__gte=start,
            journal_entry__date__lte=end,
            is_debit=False,
            account__account_type="REVENUE",
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

        revenue_debits = Transaction.objects.filter(
            journal_entry__date__gte=start,
            journal_entry__date__lte=end,
            is_debit=True,
            account__account_type="REVENUE",
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

        revenue_val = revenue_credits - revenue_debits

        net_profit = revenue_val - expenses_val
        expense_percentage = (expenses_val / revenue_val * 100) if revenue_val else 0

        # Detailed sub-accounts under Revenue (credits - debits)
        revenue_details = []
        for acc in Account.objects.filter(account_type='REVENUE', is_active=True).order_by('code'):
            debits = Transaction.objects.filter(
                account=acc,
                is_debit=True,
                journal_entry__date__gte=start,
                journal_entry__date__lte=end
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            credits = Transaction.objects.filter(
                account=acc,
                is_debit=False,
                journal_entry__date__gte=start,
                journal_entry__date__lte=end
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            net = credits - debits
            if net != 0:
                revenue_details.append({
                    "code": acc.code,
                    "name": acc.name_ar if acc.name_ar else acc.name,
                    "balance": net
                })

        # Detailed sub-accounts under Expense (debits - credits)
        expense_details = []
        for acc in Account.objects.filter(account_type='EXPENSE', is_active=True).order_by('code'):
            debits = Transaction.objects.filter(
                account=acc,
                is_debit=True,
                journal_entry__date__gte=start,
                journal_entry__date__lte=end
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            credits = Transaction.objects.filter(
                account=acc,
                is_debit=False,
                journal_entry__date__gte=start,
                journal_entry__date__lte=end
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            net = debits - credits
            if net != 0:
                expense_details.append({
                    "code": acc.code,
                    "name": acc.name_ar if acc.name_ar else acc.name,
                    "balance": net
                })

        context = {
            "start_date": start,
            "end_date": end,
            "total_expenses": expenses_val,
            "total_revenue": revenue_val,
            "net_profit": net_profit,
            "expense_percentage": expense_percentage,
            "revenue_details": revenue_details,
            "expense_details": expense_details,
        }
        return render(request, self.template_name, context)


    def post(self, request):
        # Export to Excel
        start, end = self.get_date_range(request)
        
        expense_debits = Transaction.objects.filter(
            journal_entry__date__gte=start,
            journal_entry__date__lte=end,
            is_debit=True,
            account__account_type="EXPENSE",
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

        expense_credits = Transaction.objects.filter(
            journal_entry__date__gte=start,
            journal_entry__date__lte=end,
            is_debit=False,
            account__account_type="EXPENSE",
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

        expenses_val = expense_debits - expense_credits

        revenue_credits = Transaction.objects.filter(
            journal_entry__date__gte=start,
            journal_entry__date__lte=end,
            is_debit=False,
            account__account_type="REVENUE",
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

        revenue_debits = Transaction.objects.filter(
            journal_entry__date__gte=start,
            journal_entry__date__lte=end,
            is_debit=True,
            account__account_type="REVENUE",
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

        revenue_val = revenue_credits - revenue_debits

        data = [{
            "code": "ANNUAL",
            "name": "الميزانية السنوية الشاملة",
            "total_expenses": expenses_val,
            "teacher_salaries": Decimal('0.00'),
            "other_expenses": expenses_val,
            "course_count": 0,
            "total_revenue": revenue_val,
            "profit_loss": revenue_val - expenses_val,
        }]

        exporter = FinancialReportExporter()
        workbook = exporter.create_cost_center_analysis_report(data, start, end)
        filename = f"annual_budget_{start}_{end}.xlsx"
        return create_excel_response(workbook, filename)


@method_decorator([login_required, user_passes_test(superuser_required)], name="dispatch")
class ThaaerSemesterBudgetReportView(ThaaerReportsMixin, View):
    template_name = "accounts/reports/thaaer/semester_budget.html"

    def get(self, request):
        start, end = self.get_date_range(request)
        # For semester, we limit to first or second half of the year based on month
        today = timezone.now().date()
        if today.month <= 6:
            start = start.replace(month=1, day=1)
            end = start.replace(month=6, day=30)
        else:
            start = start.replace(month=7, day=1)
            end = start.replace(month=12, day=31)
            
        # Aggregate expenses (debits - credits)
        expense_debits = Transaction.objects.filter(
            journal_entry__date__gte=start,
            journal_entry__date__lte=end,
            is_debit=True,
            account__account_type="EXPENSE",
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

        expense_credits = Transaction.objects.filter(
            journal_entry__date__gte=start,
            journal_entry__date__lte=end,
            is_debit=False,
            account__account_type="EXPENSE",
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

        expenses_val = expense_debits - expense_credits

        # Aggregate revenues (credits - debits)
        revenue_credits = Transaction.objects.filter(
            journal_entry__date__gte=start,
            journal_entry__date__lte=end,
            is_debit=False,
            account__account_type="REVENUE",
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

        revenue_debits = Transaction.objects.filter(
            journal_entry__date__gte=start,
            journal_entry__date__lte=end,
            is_debit=True,
            account__account_type="REVENUE",
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

        revenue_val = revenue_credits - revenue_debits

        net_profit = revenue_val - expenses_val
        expense_percentage = (expenses_val / revenue_val * 100) if revenue_val else 0

        # Detailed sub-accounts under Revenue (credits - debits)
        revenue_details = []
        for acc in Account.objects.filter(account_type='REVENUE', is_active=True).order_by('code'):
            debits = Transaction.objects.filter(
                account=acc,
                is_debit=True,
                journal_entry__date__gte=start,
                journal_entry__date__lte=end
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            credits = Transaction.objects.filter(
                account=acc,
                is_debit=False,
                journal_entry__date__gte=start,
                journal_entry__date__lte=end
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            net = credits - debits
            if net != 0:
                revenue_details.append({
                    "code": acc.code,
                    "name": acc.name_ar if acc.name_ar else acc.name,
                    "balance": net
                })

        # Detailed sub-accounts under Expense (debits - credits)
        expense_details = []
        for acc in Account.objects.filter(account_type='EXPENSE', is_active=True).order_by('code'):
            debits = Transaction.objects.filter(
                account=acc,
                is_debit=True,
                journal_entry__date__gte=start,
                journal_entry__date__lte=end
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            credits = Transaction.objects.filter(
                account=acc,
                is_debit=False,
                journal_entry__date__gte=start,
                journal_entry__date__lte=end
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            net = debits - credits
            if net != 0:
                expense_details.append({
                    "code": acc.code,
                    "name": acc.name_ar if acc.name_ar else acc.name,
                    "balance": net
                })

        context = {
            "start_date": start,
            "end_date": end,
            "total_expenses": expenses_val,
            "total_revenue": revenue_val,
            "net_profit": net_profit,
            "expense_percentage": expense_percentage,
            "revenue_details": revenue_details,
            "expense_details": expense_details,
        }
        return render(request, self.template_name, context)


    def post(self, request):
        start, end = self.get_date_range(request)
        # For semester, we limit to first or second half of the year based on month
        today = timezone.now().date()
        if today.month <= 6:
            start = start.replace(month=1, day=1)
            end = start.replace(month=6, day=30)
        else:
            start = start.replace(month=7, day=1)
            end = start.replace(month=12, day=31)

        expense_debits = Transaction.objects.filter(
            journal_entry__date__gte=start,
            journal_entry__date__lte=end,
            is_debit=True,
            account__account_type="EXPENSE",
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

        expense_credits = Transaction.objects.filter(
            journal_entry__date__gte=start,
            journal_entry__date__lte=end,
            is_debit=False,
            account__account_type="EXPENSE",
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

        expenses_val = expense_debits - expense_credits

        revenue_credits = Transaction.objects.filter(
            journal_entry__date__gte=start,
            journal_entry__date__lte=end,
            is_debit=False,
            account__account_type="REVENUE",
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

        revenue_debits = Transaction.objects.filter(
            journal_entry__date__gte=start,
            journal_entry__date__lte=end,
            is_debit=True,
            account__account_type="REVENUE",
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

        revenue_val = revenue_credits - revenue_debits

        data = [{
            "code": "SEMESTER",
            "name": "ميزانية الفصل الدراسي",
            "total_expenses": expenses_val,
            "teacher_salaries": Decimal('0.00'),
            "other_expenses": expenses_val,
            "course_count": 0,
            "total_revenue": revenue_val,
            "profit_loss": revenue_val - expenses_val,
        }]

        exporter = FinancialReportExporter()
        workbook = exporter.create_cost_center_analysis_report(data, start, end)
        filename = f"semester_budget_{start}_{end}.xlsx"
        return create_excel_response(workbook, filename)


@method_decorator([login_required, user_passes_test(superuser_required)], name="dispatch")
class ThaaerComprehensiveReportView(ThaaerReportsMixin, View):
    template_name = "accounts/reports/thaaer/comprehensive.html"

    def get(self, request):
        start, end = self.get_date_range(request)
        # Gather data similar to existing comprehensive view
        cost_centers = CostCenter.objects.filter(is_active=True)
        analysis_data = []
        cash_flow_data = []
        
        total_expenses_all = Decimal('0.00')
        total_revenue_all = Decimal('0.00')
        total_profit_loss_all = Decimal('0.00')
        total_teacher_salaries_all = Decimal('0.00')
        total_other_expenses_all = Decimal('0.00')
        total_inflow_all = Decimal('0.00')
        total_outflow_all = Decimal('0.00')
        total_opening_balance_all = Decimal('0.00')
        total_closing_balance_all = Decimal('0.00')

        for cc in cost_centers:
            expenses = cc.get_total_expenses(start, end) or Decimal('0.00')
            revenue = cc.get_total_revenue(start, end) or Decimal('0.00')
            profit_loss = revenue - expenses
            teacher_salaries = cc.get_teacher_salaries(start, end) or Decimal('0.00')
            other_expenses = cc.get_operational_expenses(start, end) or Decimal('0.00') # Use operational expense for CC other expense

            total_expenses_all += Decimal(str(expenses))
            total_revenue_all += Decimal(str(revenue))
            total_profit_loss_all += Decimal(str(profit_loss))
            total_teacher_salaries_all += Decimal(str(teacher_salaries))
            total_other_expenses_all += Decimal(str(other_expenses))

            analysis_data.append({
                "code": cc.code,
                "name": cc.name_ar if cc.name_ar else cc.name,
                "total_expenses": expenses,
                "teacher_salaries": teacher_salaries,
                "other_expenses": other_expenses,
                "total_revenue": revenue,
                "course_count": cc.get_course_count(),
                "profit_loss": profit_loss,
            })

            inflow = cc.get_cash_inflow(start, end) or Decimal('0.00')
            outflow = cc.get_cash_outflow(start, end) or Decimal('0.00')
            opening = cc.get_opening_balance(start) or Decimal('0.00')
            closing = opening + inflow - outflow

            total_inflow_all += Decimal(str(inflow))
            total_outflow_all += Decimal(str(outflow))
            total_opening_balance_all += Decimal(str(opening))
            total_closing_balance_all += Decimal(str(closing))

            cash_flow_data.append({
                "code": cc.code,
                "name": cc.name_ar if cc.name_ar else cc.name,
                "inflow": inflow,
                "outflow": outflow,
                "opening_balance": opening,
                "closing_balance": closing,
            })

        context = {
            "start_date": start,
            "end_date": end,
            "analysis_data": analysis_data,
            "cash_flow_data": cash_flow_data,
            "total_expenses_all": total_expenses_all,
            "total_revenue_all": total_revenue_all,
            "total_profit_loss_all": total_profit_loss_all,
            "total_teacher_salaries_all": total_teacher_salaries_all,
            "total_other_expenses_all": total_other_expenses_all,
            "total_inflow_all": total_inflow_all,
            "total_outflow_all": total_outflow_all,
            "total_opening_balance_all": total_opening_balance_all,
            "total_closing_balance_all": total_closing_balance_all,
        }
        return render(request, self.template_name, context)

    def post(self, request):
        start, end = self.get_date_range(request)
        cost_centers = CostCenter.objects.filter(is_active=True)
        analysis_data = []
        cash_flow_data = []
        for cc in cost_centers:
            expenses = cc.get_total_expenses(start, end) or 0
            revenue = cc.get_total_revenue(start, end) or 0
            profit_loss = revenue - expenses

            analysis_data.append({
                "code": cc.code,
                "name": cc.name_ar if cc.name_ar else cc.name,
                "total_expenses": expenses,
                "teacher_salaries": cc.get_teacher_salaries(start, end) or 0,
                "other_expenses": cc.get_operational_expenses(start, end) or 0,
                "total_revenue": revenue,
                "course_count": cc.get_course_count(),
                "profit_loss": profit_loss,
            })

            inflow = cc.get_cash_inflow(start, end) or 0
            outflow = cc.get_cash_outflow(start, end) or 0
            opening = cc.get_opening_balance(start) or 0
            closing = opening + inflow - outflow

            cash_flow_data.append({
                "code": cc.code,
                "name": cc.name_ar if cc.name_ar else cc.name,
                "inflow": inflow,
                "outflow": outflow,
                "opening_balance": opening,
                "closing_balance": closing,
            })
        exporter = FinancialReportExporter()
        workbook = exporter.create_comprehensive_financial_report(
            analysis_data, cash_flow_data, start, end
        )
        filename = f"comprehensive_report_{start}_{end}.xlsx"
        return create_excel_response(workbook, filename)


@method_decorator([login_required, user_passes_test(superuser_required)], name="dispatch")
class ThaaerStrategicDecisionView(ThaaerReportsMixin, View):
    template_name = "accounts/reports/thaaer/strategic_decision.html"

    def get(self, request):
        start, end = self.get_date_range(request)
        
        # 1. Outstanding Student Debt (Current Asset Component)
        total_outstanding = Decimal('0.00')
        cost_centers = CostCenter.objects.filter(is_active=True)
        
        # Calculate overall student debt first
        for cc in cost_centers:
            for crs in cc.courses.all():
                for enrollment in crs.enrollments.all():
                    total_outstanding += enrollment.balance_due

        # 2. Profitability & Smart Analysis per Cost Center
        cc_analysis = []
        for cc in cost_centers:
            # Use model methods that do smart account-code-suffix matching
            teacher_salaries_val = cc.get_teacher_salaries(start, end) or Decimal('0.00')
            employee_salaries_val = cc.get_salary_expenses(start, end) or Decimal('0.00')
            operational_val = cc.get_operational_expenses(start, end) or Decimal('0.00')

            expenses = cc.get_total_expenses(start, end) or Decimal('0.00')
            revenue = cc.get_total_revenue(start, end) or Decimal('0.00')
            profit = revenue - expenses
            margin = (profit / revenue * 100) if revenue else Decimal('0.00')
            
            # Sum outstanding student debt specifically for this cost center
            cc_outstanding = Decimal('0.00')
            for crs in cc.courses.all():
                for enrollment in crs.enrollments.all():
                    cc_outstanding += enrollment.balance_due
            
            target_margin = getattr(cc, 'target_profit_margin', Decimal('0.00')) or Decimal('0.00')

            # Smart Cost Center Relationships:
            # A) Linked Sub-Accounts explicitly configured with this cost center
            cc_sub_accounts = []
            for acc in cc.accounts.filter(is_active=True):
                cc_sub_accounts.append({
                    "code": acc.code,
                    "name": acc.name_ar if acc.name_ar else acc.name,
                    "type": acc.get_account_type_display(),
                    "balance": acc.get_net_balance(),
                })

            # B) Linked Teachers (teachers assigned to courses under this CC)
            cc_teachers = []
            for t_data in cc.get_teacher_data():
                cc_teachers.append({
                    "name": getattr(t_data['teacher'], 'full_name', None) or getattr(t_data['teacher'], 'name', '') or str(t_data['teacher']),
                    "salary": t_data['salary'],
                    "courses_count": t_data['courses_count'],
                })

            # C) Linked Employees (dynamically identified from salary postings matching CC code suffix)
            cleaned_cc_code = cc.code.lstrip('0') if cc.code.isdigit() else cc.code
            
            # Find 502-xxx accounts where suffix matches this CC code
            emp_accounts = Account.objects.filter(
                code__startswith='502',
                is_active=True
            )
            
            cc_employees = []
            for emp_acc in emp_accounts:
                code = emp_acc.code
                suffix = code.split('-')[-1].strip() if '-' in code else ''
                if not suffix:
                    continue
                
                cleaned_suffix = suffix.lstrip('0') if suffix.isdigit() else suffix
                if cleaned_suffix != cleaned_cc_code and suffix != cc.code:
                    continue
                
                emp_name = emp_acc.name_ar or emp_acc.name
                job_title = "موظف"
                
                try:
                    emp_id = int(suffix)
                    if Employee:
                        emp = Employee.objects.filter(id=emp_id).first()
                        if emp:
                            emp_name = emp.full_name
                            job_title = emp.job_title.name if emp.job_title else emp.get_position_display()
                except Exception:
                    pass

                cc_emp_debits = Transaction.objects.filter(
                    account__code=code,
                    is_debit=True,
                    journal_entry__date__gte=start,
                    journal_entry__date__lte=end
                ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
                cc_emp_credits = Transaction.objects.filter(
                    account__code=code,
                    is_debit=False,
                    journal_entry__date__gte=start,
                    journal_entry__date__lte=end
                ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
                net_paid = cc_emp_debits - cc_emp_credits

                if net_paid != 0:
                    cc_employees.append({
                        "name": emp_name,
                        "job_title": job_title,
                        "net_paid": net_paid
                    })

            # D) Courses linked to this cost center
            cc_courses = []
            for crs in cc.courses.filter(is_active=True):
                cc_courses.append({
                    "name": crs.name_ar if crs.name_ar else crs.name,
                    "price": crs.price,
                    "students_count": crs.get_enrollment_count(start, end),
                    "revenue": crs.get_total_revenue(start, end) or Decimal('0.00'),
                })
            
            cc_analysis.append({
                "code": cc.code,
                "name": cc.name_ar if cc.name_ar else cc.name,
                "revenue": revenue,
                "expenses": expenses,
                "teacher_salaries": teacher_salaries_val,
                "employee_salaries": employee_salaries_val,
                "operational_expenses": operational_val,
                "profit": profit,
                "margin": margin,
                "target_margin": target_margin,
                "margin_variance": margin - target_margin,
                "outstanding_debt": cc_outstanding,
                "teachers": cc_teachers,
                "employees": cc_employees,
                "sub_accounts": cc_sub_accounts,
                "courses": cc_courses,
            })
            
        # 3. Teacher Salaries Detailed Register with ROI & Advances
        detailed_teachers = []
        if Teacher:
            teachers_qs = Teacher.objects.filter(is_active=True) if hasattr(Teacher.objects.first(), 'is_active') else Teacher.objects.all()
            for teacher in teachers_qs:
                # Total courses taught
                t_courses_qs = teacher.assigned_courses.filter(is_active=True)
                courses_count = t_courses_qs.count()
                
                # Student count & revenue generated
                students_count = 0
                revenue_generated = Decimal('0.00')
                for crs in t_courses_qs:
                    students_count += crs.get_enrollment_count(start, end)
                    revenue_generated += crs.get_total_revenue(start, end) or Decimal('0.00')
                
                # Actual salary paid (from transactions on 501-{teacher.id:03d})
                t_code = f"501-{teacher.id:03d}"
                t_debits = Transaction.objects.filter(
                    account__code=t_code,
                    is_debit=True,
                    journal_entry__date__gte=start,
                    journal_entry__date__lte=end
                ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
                t_credits = Transaction.objects.filter(
                    account__code=t_code,
                    is_debit=False,
                    journal_entry__date__gte=start,
                    journal_entry__date__lte=end
                ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
                salary_paid = t_debits - t_credits
                
                # Advances in the period
                advances_sum = TeacherAdvance.objects.filter(
                    teacher=teacher,
                    date__gte=start,
                    date__lte=end
                ).aggregate(
                    total=Sum('amount'),
                    repaid=Sum('repaid_amount')
                )
                adv_amt = advances_sum['total'] or Decimal('0.00')
                adv_repaid = advances_sum['repaid'] or Decimal('0.00')
                adv_outstanding = adv_amt - adv_repaid
                
                # ROI margin
                roi = ((revenue_generated - salary_paid) / revenue_generated * 100) if revenue_generated else Decimal('0.00')
                
                detailed_teachers.append({
                    "name": getattr(teacher, 'full_name', '') or getattr(teacher, 'name', '') or str(teacher),
                    "courses_count": courses_count,
                    "students_count": students_count,
                    "revenue": revenue_generated,
                    "salary_paid": salary_paid,
                    "advances_total": adv_amt,
                    "advances_outstanding": adv_outstanding,
                    "roi": roi
                })

        # 4. Employee Salaries Detailed Register
        detailed_employees = []
        if Employee:
            employees_qs = Employee.objects.filter(employment_status='active') if hasattr(Employee.objects.first(), 'employment_status') else Employee.objects.all()
            for emp in employees_qs:
                dept_name = emp.department.name if emp.department else "غير محدد"
                job_title_name = emp.job_title.name if emp.job_title else emp.get_position_display()
                
                # Base contract salary
                contract_salary = emp.salary or Decimal('0.00')
                
                # Actual salary paid (from transactions on 502-{employee.id:03d})
                e_code = f"502-{emp.id:03d}"
                e_debits = Transaction.objects.filter(
                    account__code=e_code,
                    is_debit=True,
                    journal_entry__date__gte=start,
                    journal_entry__date__lte=end
                ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
                e_credits = Transaction.objects.filter(
                    account__code=e_code,
                    is_debit=False,
                    journal_entry__date__gte=start,
                    journal_entry__date__lte=end
                ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
                salary_paid = e_debits - e_credits
                
                # Advances in the period
                advances_sum = EmployeeAdvance.objects.filter(
                    employee=emp,
                    date__gte=start,
                    date__lte=end
                ).aggregate(
                    total=Sum('amount'),
                    repaid=Sum('repaid_amount')
                )
                adv_amt = advances_sum['total'] or Decimal('0.00')
                adv_repaid = advances_sum['repaid'] or Decimal('0.00')
                adv_outstanding = adv_amt - adv_repaid
                
                detailed_employees.append({
                    "name": emp.full_name,
                    "employee_code": emp.employee_code or f"EMP-{emp.pk:04d}",
                    "department": dept_name,
                    "job_title": job_title_name,
                    "contract_salary": contract_salary,
                    "salary_paid": salary_paid,
                    "advances_total": adv_amt,
                    "advances_outstanding": adv_outstanding,
                    "payroll_method": emp.get_payroll_method_display() if hasattr(emp, 'get_payroll_method_display') else emp.payroll_method,
                    "contract_type": emp.get_contract_type_display() if hasattr(emp, 'get_contract_type_display') else emp.contract_type,
                })

        # 5. Course Feasibility and ROI Analysis
        all_courses = Course.objects.filter(is_active=True)
        course_roi = []
        for crs in all_courses:
            revenue = crs.get_total_revenue(start, end) or Decimal('0.00')
            teacher_cost = crs.get_total_teacher_salaries(start, end) or Decimal('0.00')
            profit = revenue - teacher_cost
            margin = (profit / revenue * 100) if revenue else Decimal('0.00')
            enrollments = crs.get_enrollment_count(start, end)
            
            course_roi.append({
                "name": crs.name_ar if crs.name_ar else crs.name,
                "cost_center": crs.cost_center.name_ar if crs.cost_center else "غير محدد",
                "enrollments": enrollments,
                "revenue": revenue,
                "teacher_cost": teacher_cost,
                "profit": profit,
                "margin": margin,
            })
            
        course_roi = sorted(course_roi, key=lambda x: x['profit'], reverse=True)

        # 6. Monthly Financial Trend Analysis (Last 6 Months)
        monthly_trends = []
        today = timezone.now().date()
        for i in range(6):
            month_date = today.replace(day=1) - timedelta(days=30 * i)
            m_start = month_date.replace(day=1)
            next_m = (m_start + timedelta(days=32)).replace(day=1)
            m_end = next_m - timedelta(days=1)
            
            expense_debits = Transaction.objects.filter(
                journal_entry__date__gte=m_start,
                journal_entry__date__lte=m_end,
                is_debit=True,
                account__account_type="EXPENSE",
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

            expense_credits = Transaction.objects.filter(
                journal_entry__date__gte=m_start,
                journal_entry__date__lte=m_end,
                is_debit=False,
                account__account_type="EXPENSE",
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

            m_expenses = expense_debits - expense_credits

            revenue_credits = Transaction.objects.filter(
                journal_entry__date__gte=m_start,
                journal_entry__date__lte=m_end,
                is_debit=False,
                account__account_type="REVENUE",
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

            revenue_debits = Transaction.objects.filter(
                journal_entry__date__gte=m_start,
                journal_entry__date__lte=m_end,
                is_debit=True,
                account__account_type="REVENUE",
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

            m_revenue = revenue_credits - revenue_debits
            
            monthly_trends.append({
                "month": m_start.strftime("%Y/%m"),
                "revenue": m_revenue,
                "expenses": m_expenses,
                "profit": m_revenue - m_expenses,
            })

        # 7. Split Assets & Properties (فصلي الاصول والموجودات)
        asset_accounts = Account.objects.filter(
            account_type='ASSET',
            is_active=True
        ).order_by('code')
        
        current_assets = []
        fixed_assets = []
        total_current_assets = Decimal('0.00')
        total_fixed_assets = Decimal('0.00')
        
        # Categorize active asset accounts
        for acc in asset_accounts:
            balance = acc.get_net_balance()
            if balance == 0:
                continue
                
            name = (acc.name_ar or acc.name).lower()
            code = acc.code
            
            # Check if it meets criteria for fixed asset/property
            is_fixed = False
            fixed_keywords = ['ثابت', 'عقار', 'ممتلك', 'موجودات', 'سيار', 'أثاث', 'أجهزة', 'كمبيوتر', 'معدات', 'أرض', 'أراضي', 'مباني', 'آلات']
            if any(keyword in name for keyword in fixed_keywords) or code.startswith('11'):
                is_fixed = True
                
            asset_data = {
                "code": acc.code,
                "name": acc.name_ar if acc.name_ar else acc.name,
                "parent": acc.parent.display_name if acc.parent else "حساب رئيسي",
                "balance": balance,
            }
            
            if is_fixed:
                fixed_assets.append(asset_data)
                total_fixed_assets += balance
            else:
                current_assets.append(asset_data)
                total_current_assets += balance

        # Explicitly append Student Tuition Outstanding as a Current Asset (Receivable)
        if total_outstanding > 0:
            current_assets.append({
                "code": "REC-STUD",
                "name": "الذمم المستحقة على الطلاب (رسوم معلقة)",
                "parent": "حسابات مدينين",
                "balance": total_outstanding,
            })
            total_current_assets += total_outstanding
            
        total_assets_val = total_current_assets + total_fixed_assets
            
        context = {
            "start_date": start,
            "end_date": end,
            "cc_analysis": cc_analysis,
            "detailed_teachers": detailed_teachers,
            "detailed_employees": detailed_employees,
            "course_roi": course_roi,
            "monthly_trends": monthly_trends,
            "total_outstanding": total_outstanding,
            "current_assets": current_assets,
            "fixed_assets": fixed_assets,
            "total_current_assets": total_current_assets,
            "total_fixed_assets": total_fixed_assets,
            "total_assets_val": total_assets_val,
        }
        return render(request, self.template_name, context)


@method_decorator([login_required, user_passes_test(superuser_required)], name="dispatch")
class ThaaerTrialBalanceReportView(ThaaerReportsMixin, View):
    template_name = "accounts/reports/thaaer/trial_balance.html"

    def get(self, request):
        start, end = self.get_date_range(request)
        academic_year = _current_academic_year(request)

        # Get settings from request
        account_type = (request.GET.get('account_type') or '').strip().upper()
        hierarchy_mode = (request.GET.get('hierarchy_mode') or 'all').strip().lower()
        sort_by = (request.GET.get('sort_by') or 'code').strip().lower()
        show_zero_balances = request.GET.get('show_zero') in {'1', 'true', 'yes', 'on'}
        full_report = request.GET.get('full_report') in {'1', 'true', 'yes', 'on'}

        if full_report:
            start = None
            end = None
            show_zero_balances = True

        trial_balance_data = []
        total_debits = Decimal('0.00')
        total_credits = Decimal('0.00')

        accounts = Account.objects.filter(is_active=True)
        if account_type:
            accounts = accounts.filter(account_type=account_type)

        if hierarchy_mode == 'main_only':
            accounts = accounts.filter(parent__isnull=True)
        elif hierarchy_mode == 'leaf_only':
            accounts = accounts.filter(children__isnull=True)

        order_field = 'code' if sort_by == 'code' else 'name_ar'
        accounts = accounts.order_by(order_field, 'code').distinct()

        for account in accounts:
            transactions = account.transactions.all()
            if academic_year:
                transactions = transactions.filter(journal_entry__academic_year=academic_year)
            if start:
                transactions = transactions.filter(journal_entry__date__gte=start)
            if end:
                transactions = transactions.filter(journal_entry__date__lte=end)

            debit_total = transactions.filter(is_debit=True).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            credit_total = transactions.filter(is_debit=False).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

            if account.account_type in ['ASSET', 'EXPENSE']:
                net_balance = debit_total - credit_total
            else:
                net_balance = credit_total - debit_total

            debit_amount = Decimal('0.00')
            credit_amount = Decimal('0.00')

            if net_balance > 0:
                if account.account_type in ['ASSET', 'EXPENSE']:
                    debit_amount = net_balance
                else:
                    credit_amount = net_balance
            elif net_balance < 0:
                if account.account_type in ['ASSET', 'EXPENSE']:
                    credit_amount = abs(net_balance)
                else:
                    debit_amount = abs(net_balance)

            include_account = full_report or show_zero_balances or debit_amount > 0 or credit_amount > 0
            if not include_account:
                continue

            trial_balance_data.append({
                'account': account,
                'debit_amount': debit_amount,
                'credit_amount': credit_amount,
                'net_balance': net_balance,
                'debit_total': debit_total,
                'credit_total': credit_total,
            })
            total_debits += debit_amount
            total_credits += credit_amount

        difference = total_debits - total_credits
        is_balanced = total_debits == total_credits

        context = {
            'report_generated_at': timezone.now(),
            'start_date': start,
            'end_date': end,
            'account_type': account_type,
            'hierarchy_mode': hierarchy_mode,
            'sort_by': sort_by,
            'show_zero_balances': show_zero_balances,
            'full_report': full_report,
            'trial_balance_data': trial_balance_data,
            'total_debits': total_debits,
            'total_credits': total_credits,
            'difference': difference,
            'is_balanced': is_balanced,
            'account_count': len(trial_balance_data),
            'trial_account_type_options': [
                ('', 'كل الأنواع'),
                ('ASSET', 'الأصول'),
                ('LIABILITY', 'الالتزامات'),
                ('EQUITY', 'حقوق الملكية'),
                ('REVENUE', 'الإيرادات'),
                ('EXPENSE', 'المصاريف'),
            ],
        }
        return render(request, self.template_name, context)


@method_decorator([login_required, user_passes_test(superuser_required)], name="dispatch")
class ThaaerIncomeStatementReportView(ThaaerReportsMixin, View):
    template_name = "accounts/reports/thaaer/income_statement.html"

    def get(self, request):
        start, end = self.get_date_range(request)
        academic_year = _current_academic_year(request)

        # Get revenue and expense accounts
        revenue_accounts_qs = Account.objects.filter(account_type='REVENUE', is_active=True).order_by('code')
        expense_accounts_qs = Account.objects.filter(account_type='EXPENSE', is_active=True).order_by('code')

        revenue_accounts = []
        expense_accounts = []
        total_revenue = Decimal('0.00')
        total_expenses = Decimal('0.00')

        # Dynamically calculate net balance within selected dates
        for acc in revenue_accounts_qs:
            tx = acc.transactions.all()
            if academic_year:
                tx = tx.filter(journal_entry__academic_year=academic_year)
            if start:
                tx = tx.filter(journal_entry__date__gte=start)
            if end:
                tx = tx.filter(journal_entry__date__lte=end)

            debits = tx.filter(is_debit=True).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            credits = tx.filter(is_debit=False).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            net = credits - debits # Natural credit balance for Revenue
            if net != 0:
                revenue_accounts.append({
                    'code': acc.code,
                    'name': acc.name_ar if acc.name_ar else acc.name,
                    'balance': net
                })
                total_revenue += net

        for acc in expense_accounts_qs:
            tx = acc.transactions.all()
            if academic_year:
                tx = tx.filter(journal_entry__academic_year=academic_year)
            if start:
                tx = tx.filter(journal_entry__date__gte=start)
            if end:
                tx = tx.filter(journal_entry__date__lte=end)

            debits = tx.filter(is_debit=True).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            credits = tx.filter(is_debit=False).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            net = debits - credits # Natural debit balance for Expense
            if net != 0:
                expense_accounts.append({
                    'code': acc.code,
                    'name': acc.name_ar if acc.name_ar else acc.name,
                    'balance': net
                })
                total_expenses += net

        net_income = total_revenue - total_expenses
        margin = (net_income / total_revenue * 100) if total_revenue else Decimal('0.00')

        context = {
            'start_date': start,
            'end_date': end,
            'revenue_accounts': revenue_accounts,
            'expense_accounts': expense_accounts,
            'total_revenue': total_revenue,
            'total_expenses': total_expenses,
            'net_income': net_income,
            'margin': margin,
        }
        return render(request, self.template_name, context)


@method_decorator([login_required, user_passes_test(superuser_required)], name="dispatch")
class ThaaerBalanceSheetReportView(ThaaerReportsMixin, View):
    template_name = "accounts/reports/thaaer/balance_sheet.html"

    def get(self, request):
        start, end = self.get_date_range(request)
        academic_year = _current_academic_year(request)

        asset_accounts_qs = Account.objects.filter(account_type='ASSET', is_active=True).order_by('code')
        liability_accounts_qs = Account.objects.filter(account_type='LIABILITY', is_active=True).order_by('code')
        equity_accounts_qs = Account.objects.filter(account_type='EQUITY', is_active=True).order_by('code')

        asset_accounts = []
        liability_accounts = []
        equity_accounts = []

        total_assets = Decimal('0.00')
        total_liabilities = Decimal('0.00')
        total_equity = Decimal('0.00')

        # Helper method for dynamic net balance
        def get_acc_balance(acc, start_date, end_date, ac_year):
            tx = acc.transactions.all()
            if ac_year:
                tx = tx.filter(journal_entry__academic_year=ac_year)
            # Balance sheet is cumulative: filter up to end_date
            if end_date:
                tx = tx.filter(journal_entry__date__lte=end_date)
            
            debits = tx.filter(is_debit=True).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            credits = tx.filter(is_debit=False).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            
            if acc.account_type in ['ASSET', 'EXPENSE']:
                return debits - credits
            else:
                return credits - debits

        for acc in asset_accounts_qs:
            bal = get_acc_balance(acc, start, end, academic_year)
            if bal != 0:
                asset_accounts.append({
                    'code': acc.code,
                    'name': acc.name_ar if acc.name_ar else acc.name,
                    'balance': bal
                })
                total_assets += bal

        for acc in liability_accounts_qs:
            bal = get_acc_balance(acc, start, end, academic_year)
            if bal != 0:
                liability_accounts.append({
                    'code': acc.code,
                    'name': acc.name_ar if acc.name_ar else acc.name,
                    'balance': bal
                })
                total_liabilities += bal

        for acc in equity_accounts_qs:
            bal = get_acc_balance(acc, start, end, academic_year)
            if bal != 0:
                equity_accounts.append({
                    'code': acc.code,
                    'name': acc.name_ar if acc.name_ar else acc.name,
                    'balance': bal
                })
                total_equity += bal

        # Inject dynamic Student outstanding debt to current assets
        total_outstanding = Decimal('0.00')
        cost_centers = CostCenter.objects.filter(is_active=True)
        for cc in cost_centers:
            for crs in cc.courses.all():
                for enrollment in crs.enrollments.all():
                    total_outstanding += enrollment.balance_due

        if total_outstanding > 0:
            asset_accounts.append({
                'code': 'REC-STUD',
                'name': 'الذمم المستحقة على الطلاب (رسوم معلقة)',
                'balance': total_outstanding
            })
            total_assets += total_outstanding

        difference = total_assets - (total_liabilities + total_equity)
        is_balanced = (difference == 0)

        context = {
            'start_date': start,
            'end_date': end,
            'asset_accounts': asset_accounts,
            'liability_accounts': liability_accounts,
            'equity_accounts': equity_accounts,
            'total_assets': total_assets,
            'total_liabilities': total_liabilities,
            'total_equity': total_equity,
            'difference': difference,
            'is_balanced': is_balanced,
            'total_outstanding_student': total_outstanding
        }
        return render(request, self.template_name, context)


@method_decorator([login_required, user_passes_test(superuser_required)], name="dispatch")
class ThaaerLedgerReportView(ThaaerReportsMixin, View):
    template_name = "accounts/reports/thaaer/ledger.html"

    def _signed_amount(self, transaction):
        acc_type = transaction.account.account_type
        is_natural_debit = acc_type in ['ASSET', 'EXPENSE']
        return transaction.amount if (transaction.is_debit and is_natural_debit) or (not transaction.is_debit and not is_natural_debit) else -transaction.amount

    def get(self, request):
        start, end = self.get_date_range(request)
        academic_year = _current_academic_year(request)
        account_code = request.GET.get('account_code') or ''

        accounts_list = Account.objects.filter(is_active=True).order_by('code')
        statement_data = None
        account_obj = None

        if account_code:
            account_obj = get_object_or_404(Account, code=account_code)
            
            # Opening balance from all transactions before start (if provided)
            prior_qs = account_obj.transactions_with_descendants(academic_year=academic_year)
            if start:
                prior_qs = prior_qs.filter(journal_entry__date__lt=start)
            opening_balance = sum(self._signed_amount(tx) for tx in prior_qs.select_related('journal_entry', 'account'))

            # Current period transactions
            tx_qs = account_obj.transactions_with_descendants(academic_year=academic_year).select_related('journal_entry', 'account').order_by('journal_entry__date', 'journal_entry__created_at', 'id')
            if start:
                tx_qs = tx_qs.filter(journal_entry__date__gte=start)
            if end:
                tx_qs = tx_qs.filter(journal_entry__date__lte=end)

            running_balance = opening_balance
            rows = []
            total_debit = Decimal('0.00')
            total_credit = Decimal('0.00')

            for tx in tx_qs:
                signed = self._signed_amount(tx)
                running_balance += signed
                if tx.is_debit:
                    total_debit += tx.amount
                else:
                    total_credit += tx.amount
                rows.append({
                    'transaction': tx,
                    'running_balance': running_balance,
                    'account_code': tx.account.code,
                    'account_name': tx.account.display_name,
                })

            statement_data = {
                'opening_balance': opening_balance,
                'closing_balance': running_balance,
                'total_debit': total_debit,
                'total_credit': total_credit,
                'rows': rows,
            }

        context = {
            'accounts_list': accounts_list,
            'account_code': account_code,
            'account_obj': account_obj,
            'start_date': start,
            'end_date': end,
            'statement_data': statement_data,
        }
        return render(request, self.template_name, context)


