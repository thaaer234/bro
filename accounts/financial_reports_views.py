"""
Financial Reports Views
Comprehensive financial reporting system with Excel export capabilities
"""

from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, Q, Count
from django.utils import timezone
from django.core.paginator import Paginator
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views.generic import View
from datetime import datetime, date, timedelta
from decimal import Decimal
import json

from .models import (
    CostCenter, Transaction, JournalEntry, Account, 
    Studentenrollment, ExpenseEntry, TeacherAdvance, EmployeeAdvance
)
from .excel_utils import FinancialReportExporter, create_excel_response, format_number_with_commas
from employ.models import Teacher, Employee
from students.models import Student


class FinancialReportsMixin:
    """Mixin for common financial report functionality"""
    
    def get_date_range(self, request):
        """Extract date range from request parameters"""
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        
        if start_date:
            try:
                start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            except ValueError:
                start_date = None
        
        if end_date:
            try:
                end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
            except ValueError:
                end_date = None
        
        # Default to current month if no dates provided
        if not start_date and not end_date:
            today = timezone.now().date()
            start_date = today.replace(day=1)
            next_month = start_date.replace(day=28) + timedelta(days=4)
            end_date = next_month - timedelta(days=next_month.day)
        
        return start_date, end_date
    
    def format_currency(self, value):
        """Format currency value with commas"""
        return format_number_with_commas(value)


@method_decorator(login_required, name='dispatch')
class CostCenterAnalysisReportView(FinancialReportsMixin, View):
    """Cost Center Analysis Report View"""
    
    template_name = 'accounts/reports/cost_center_analysis.html'
    
    def get(self, request):
        """Display cost center analysis report"""
        start_date, end_date = self.get_date_range(request)
        
        # Get all active cost centers
        cost_centers = CostCenter.objects.filter(is_active=True).order_by('code')
        
        # Prepare data for each cost center
        cost_centers_data = []
        for cost_center in cost_centers:
            data = {
                'id': cost_center.id,
                'code': cost_center.code,
                'name': cost_center.name_ar if cost_center.name_ar else cost_center.name,
                'type': cost_center.get_cost_center_type_display(),
                'total_expenses': cost_center.get_total_expenses(start_date, end_date),
                'teacher_salaries': cost_center.get_teacher_salaries(start_date, end_date),
                'other_expenses': cost_center.get_other_expenses(start_date, end_date),
                'total_revenue': cost_center.get_total_revenue(start_date, end_date),
                'course_count': cost_center.get_course_count(),
                'profit_loss': cost_center.get_total_revenue(start_date, end_date) - cost_center.get_total_expenses(start_date, end_date),
                'budget_variance': cost_center.monthly_budget - cost_center.get_total_expenses(start_date, end_date) if cost_center.monthly_budget else Decimal('0'),
            }
            cost_centers_data.append(data)
        
        # Calculate totals
        totals = {
            'total_expenses': sum(cc['total_expenses'] for cc in cost_centers_data),
            'total_teacher_salaries': sum(cc['teacher_salaries'] for cc in cost_centers_data),
            'total_other_expenses': sum(cc['other_expenses'] for cc in cost_centers_data),
            'total_revenue': sum(cc['total_revenue'] for cc in cost_centers_data),
            'total_profit_loss': sum(cc['profit_loss'] for cc in cost_centers_data),
            'total_courses': sum(cc['course_count'] for cc in cost_centers_data),
        }
        
        context = {
            'cost_centers_data': cost_centers_data,
            'totals': totals,
            'start_date': start_date,
            'end_date': end_date,
            'period_display': f"{start_date} - {end_date}" if start_date and end_date else "جميع الفترات",
        }
        
        return render(request, self.template_name, context)
    
    def post(self, request):
        """Export cost center analysis to Excel"""
        start_date, end_date = self.get_date_range(request)
        
        # Get all active cost centers
        cost_centers = CostCenter.objects.filter(is_active=True).order_by('code')
        
        # Prepare data for Excel export
        cost_centers_data = []
        for cost_center in cost_centers:
            data = {
                'code': cost_center.code,
                'name': cost_center.name_ar if cost_center.name_ar else cost_center.name,
                'total_expenses': cost_center.get_total_expenses(start_date, end_date),
                'teacher_salaries': cost_center.get_teacher_salaries(start_date, end_date),
                'other_expenses': cost_center.get_other_expenses(start_date, end_date),
                'total_revenue': cost_center.get_total_revenue(start_date, end_date),
                'course_count': cost_center.get_course_count(),
            }
            cost_centers_data.append(data)
        
        # Create Excel report
        exporter = FinancialReportExporter()
        workbook = exporter.create_cost_center_analysis_report(
            cost_centers_data, start_date, end_date
        )
        
        # Generate filename
        filename = f"cost_center_analysis_{start_date}_{end_date}.xlsx" if start_date and end_date else "cost_center_analysis.xlsx"
        
        return create_excel_response(workbook, filename)


@method_decorator(login_required, name='dispatch')
class CostCenterCashFlowReportView(FinancialReportsMixin, View):
    """Cost Center Cash Flow Report View"""
    
    template_name = 'accounts/reports/cost_center_cash_flow.html'
    
    def get(self, request):
        """Display cost center cash flow report"""
        start_date, end_date = self.get_date_range(request)
        
        # Get all active cost centers
        cost_centers = CostCenter.objects.filter(is_active=True).order_by('code')
        
        # Prepare data for each cost center
        cash_flow_data = []
        for cost_center in cost_centers:
            data = {
                'id': cost_center.id,
                'code': cost_center.code,
                'name': cost_center.name_ar if cost_center.name_ar else cost_center.name,
                'type': cost_center.get_cost_center_type_display(),
                'inflow': cost_center.get_cash_inflow(start_date, end_date),
                'outflow': cost_center.get_cash_outflow(start_date, end_date),
                'opening_balance': cost_center.get_opening_balance(start_date),
                'closing_balance': cost_center.get_closing_balance(start_date, end_date),
                'net_cash_flow': cost_center.get_cash_inflow(start_date, end_date) - cost_center.get_cash_outflow(start_date, end_date),
            }
            cash_flow_data.append(data)
        
        # Calculate totals
        totals = {
            'total_inflow': sum(cc['inflow'] for cc in cash_flow_data),
            'total_outflow': sum(cc['outflow'] for cc in cash_flow_data),
            'total_opening_balance': sum(cc['opening_balance'] for cc in cash_flow_data),
            'total_closing_balance': sum(cc['closing_balance'] for cc in cash_flow_data),
            'total_net_cash_flow': sum(cc['net_cash_flow'] for cc in cash_flow_data),
        }
        
        context = {
            'cash_flow_data': cash_flow_data,
            'totals': totals,
            'start_date': start_date,
            'end_date': end_date,
            'period_display': f"{start_date} - {end_date}" if start_date and end_date else "جميع الفترات",
        }
        
        return render(request, self.template_name, context)
    
    def post(self, request):
        """Export cost center cash flow to Excel"""
        start_date, end_date = self.get_date_range(request)
        
        # Get all active cost centers
        cost_centers = CostCenter.objects.filter(is_active=True).order_by('code')
        
        # Prepare data for Excel export
        cash_flow_data = []
        for cost_center in cost_centers:
            data = {
                'code': cost_center.code,
                'name': cost_center.name_ar if cost_center.name_ar else cost_center.name,
                'inflow': cost_center.get_cash_inflow(start_date, end_date),
                'outflow': cost_center.get_cash_outflow(start_date, end_date),
                'opening_balance': cost_center.get_opening_balance(start_date),
            }
            cash_flow_data.append(data)
        
        # Create Excel report
        exporter = FinancialReportExporter()
        workbook = exporter.create_cost_center_cash_flow_report(
            cash_flow_data, start_date, end_date
        )
        
        # Generate filename
        filename = f"cost_center_cash_flow_{start_date}_{end_date}.xlsx" if start_date and end_date else "cost_center_cash_flow.xlsx"
        
        return create_excel_response(workbook, filename)


@method_decorator(login_required, name='dispatch')
class ComprehensiveFinancialReportView(FinancialReportsMixin, View):
    """Comprehensive Financial Report View with multiple sheets"""
    
    template_name = 'accounts/reports/comprehensive_financial.html'
    
    def get(self, request):
        """Display comprehensive financial report options"""
        start_date, end_date = self.get_date_range(request)
        
        # Get summary statistics
        cost_centers_count = CostCenter.objects.filter(is_active=True).count()
        total_transactions = Transaction.objects.filter(
            journal_entry__date__gte=start_date,
            journal_entry__date__lte=end_date
        ).count() if start_date and end_date else Transaction.objects.count()
        
        context = {
            'start_date': start_date,
            'end_date': end_date,
            'period_display': f"{start_date} - {end_date}" if start_date and end_date else "جميع الفترات",
            'cost_centers_count': cost_centers_count,
            'total_transactions': total_transactions,
        }
        
        return render(request, self.template_name, context)
    
    def post(self, request):
        """Export comprehensive financial report to Excel"""
        start_date, end_date = self.get_date_range(request)
        
        # Get cost center analysis data
        cost_centers = CostCenter.objects.filter(is_active=True).order_by('code')
        analysis_data = []
        for cost_center in cost_centers:
            data = {
                'code': cost_center.code,
                'name': cost_center.name_ar if cost_center.name_ar else cost_center.name,
                'total_expenses': cost_center.get_total_expenses(start_date, end_date),
                'teacher_salaries': cost_center.get_teacher_salaries(start_date, end_date),
                'other_expenses': cost_center.get_other_expenses(start_date, end_date),
                'total_revenue': cost_center.get_total_revenue(start_date, end_date),
                'course_count': cost_center.get_course_count(),
            }
            analysis_data.append(data)
        
        # Get cash flow data
        cash_flow_data = []
        for cost_center in cost_centers:
            data = {
                'code': cost_center.code,
                'name': cost_center.name_ar if cost_center.name_ar else cost_center.name,
                'inflow': cost_center.get_cash_inflow(start_date, end_date),
                'outflow': cost_center.get_cash_outflow(start_date, end_date),
                'opening_balance': cost_center.get_opening_balance(start_date),
            }
            cash_flow_data.append(data)
        
        # Create comprehensive Excel report
        exporter = FinancialReportExporter()
        workbook = exporter.create_comprehensive_financial_report(
            analysis_data, cash_flow_data, start_date, end_date
        )
        
        # Generate filename
        filename = f"comprehensive_financial_report_{start_date}_{end_date}.xlsx" if start_date and end_date else "comprehensive_financial_report.xlsx"
        
        return create_excel_response(workbook, filename)


@login_required
def financial_reports_dashboard(request):
    """Financial Reports Dashboard"""
    # Get recent activity
    recent_transactions = Transaction.objects.select_related(
        'journal_entry', 'account', 'cost_center'
    ).order_by('-created_at')[:10]
    
    # Get cost center summary
    cost_centers = CostCenter.objects.filter(is_active=True)
    cost_center_summary = []
    
    for cc in cost_centers:
        summary = {
            'name': cc.name_ar if cc.name_ar else cc.name,
            'code': cc.code,
            'total_expenses': cc.get_total_expenses(),
            'total_revenue': cc.get_total_revenue(),
            'profit_loss': cc.get_total_revenue() - cc.get_total_expenses(),
        }
        cost_center_summary.append(summary)
    
    # Get monthly trends (last 6 months)
    monthly_trends = []
    for i in range(6):
        month_date = timezone.now().date().replace(day=1) - timedelta(days=30*i)
        month_start = month_date.replace(day=1)
        month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        
        total_expenses = Transaction.objects.filter(
            journal_entry__date__gte=month_start,
            journal_entry__date__lte=month_end,
            is_debit=True,
            account__account_type='EXPENSE'
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        
        total_revenue = Transaction.objects.filter(
            journal_entry__date__gte=month_start,
            journal_entry__date__lte=month_end,
            is_debit=False,
            account__account_type='REVENUE'
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        
        monthly_trends.append({
            'month': month_start.strftime('%Y-%m'),
            'expenses': total_expenses,
            'revenue': total_revenue,
            'profit_loss': total_revenue - total_expenses,
        })
    
    context = {
        'recent_transactions': recent_transactions,
        'cost_center_summary': cost_center_summary,
        'monthly_trends': monthly_trends,
    }
    
    return render(request, 'accounts/reports/dashboard.html', context)


@login_required
@require_http_methods(["GET"])
def cost_center_detail_report(request, cost_center_id):
    """Detailed report for a specific cost center"""
    cost_center = get_object_or_404(CostCenter, id=cost_center_id)
    start_date, end_date = FinancialReportsMixin().get_date_range(request)
    
    # Get detailed transactions for this cost center
    transactions = Transaction.objects.filter(
        cost_center=cost_center,
        journal_entry__date__gte=start_date,
        journal_entry__date__lte=end_date
    ).select_related('journal_entry', 'account').order_by('-journal_entry__date')
    
    # Get teacher assignments (if any)
    teachers = Teacher.objects.all()  # This would need to be filtered based on cost center assignments
    
    # Get course information
    courses = []  # This would need to be implemented based on course-cost center relationships
    
    context = {
        'cost_center': cost_center,
        'transactions': transactions,
        'teachers': teachers,
        'courses': courses,
        'start_date': start_date,
        'end_date': end_date,
        'period_display': f"{start_date} - {end_date}" if start_date and end_date else "جميع الفترات",
    }
    
    return render(request, 'accounts/reports/cost_center_detail.html', context)


# AJAX endpoints for dynamic data
@login_required
@csrf_exempt
def get_cost_center_data(request):
    """AJAX endpoint to get cost center data"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        data = json.loads(request.body)
        cost_center_id = data.get('cost_center_id')
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        
        if start_date:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        if end_date:
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        cost_center = get_object_or_404(CostCenter, id=cost_center_id)
        
        response_data = {
            'code': cost_center.code,
            'name': cost_center.name_ar if cost_center.name_ar else cost_center.name,
            'total_expenses': float(cost_center.get_total_expenses(start_date, end_date)),
            'teacher_salaries': float(cost_center.get_teacher_salaries(start_date, end_date)),
            'other_expenses': float(cost_center.get_other_expenses(start_date, end_date)),
            'total_revenue': float(cost_center.get_total_revenue(start_date, end_date)),
            'profit_loss': float(cost_center.get_total_revenue(start_date, end_date) - cost_center.get_total_expenses(start_date, end_date)),
            'inflow': float(cost_center.get_cash_inflow(start_date, end_date)),
            'outflow': float(cost_center.get_cash_outflow(start_date, end_date)),
            'opening_balance': float(cost_center.get_opening_balance(start_date)),
            'closing_balance': float(cost_center.get_closing_balance(start_date, end_date)),
        }
        
        return JsonResponse(response_data)
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
