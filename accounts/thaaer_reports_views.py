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
from .models import CostCenter, Transaction
from .excel_utils import FinancialReportExporter, create_excel_response


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

        context = {
            "start_date": start,
            "end_date": end,
            "total_expenses": expenses_val,
            "total_revenue": revenue_val,
            "net_profit": net_profit,
            "expense_percentage": expense_percentage,
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

        context = {
            "start_date": start,
            "end_date": end,
            "total_expenses": expenses_val,
            "total_revenue": revenue_val,
            "net_profit": net_profit,
            "expense_percentage": expense_percentage,
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
        for cc in cost_centers:
            expenses = cc.get_total_expenses(start, end) or 0
            revenue = cc.get_total_revenue(start, end) or 0
            profit_loss = revenue - expenses

            analysis_data.append({
                "code": cc.code,
                "name": cc.name_ar if cc.name_ar else cc.name,
                "total_expenses": expenses,
                "teacher_salaries": cc.get_teacher_salaries(start, end) or 0,
                "other_expenses": cc.get_other_expenses(start, end) or 0,
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
        context = {
            "start_date": start,
            "end_date": end,
            "analysis_data": analysis_data,
            "cash_flow_data": cash_flow_data,
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
                "other_expenses": cc.get_other_expenses(start, end) or 0,
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
