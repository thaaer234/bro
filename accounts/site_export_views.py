"""
Comprehensive Site-wide Excel Export Views
Exports all site content to Excel with proper formatting
"""

from django.shortcuts import render
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, Q
from django.utils import timezone
from datetime import datetime, date, timedelta
from decimal import Decimal

from .models import (
    CostCenter, Transaction, JournalEntry, Account, 
    Studentenrollment, ExpenseEntry, TeacherAdvance, EmployeeAdvance,
    Course, CourseTeacherAssignment, StudentReceipt
)
from .excel_utils import FinancialReportExporter, create_excel_response, format_number_with_commas
from employ.models import Teacher, Employee
from students.models import Student


@login_required
def comprehensive_site_export(request):
    """Export all site content to comprehensive Excel report"""
    
    # Get date range
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
    
    # Create comprehensive Excel workbook
    exporter = FinancialReportExporter()
    
    # Remove default sheet
    exporter.workbook.remove(exporter.workbook.active)
    
    # 1. Cost Center Analysis Sheet
    cost_centers = CostCenter.objects.filter(is_active=True).order_by('code')
    analysis_data = []
    for cc in cost_centers:
        data = {
            'code': cc.code,
            'name': cc.name_ar if cc.name_ar else cc.name,
            'total_expenses': cc.get_total_expenses(start_date, end_date),
            'teacher_salaries': cc.get_teacher_salaries(start_date, end_date),
            'other_expenses': cc.get_other_expenses(start_date, end_date),
            'total_revenue': cc.get_total_revenue(start_date, end_date),
            'course_count': cc.get_course_count(),
        }
        analysis_data.append(data)
    
    analysis_sheet = exporter.workbook.create_sheet("Cost Center Analysis")
    exporter.create_cost_center_analysis_report(analysis_data, start_date, end_date)
    
    # 2. Cash Flow Analysis Sheet
    cash_flow_data = []
    for cc in cost_centers:
        data = {
            'code': cc.code,
            'name': cc.name_ar if cc.name_ar else cc.name,
            'inflow': cc.get_cash_inflow(start_date, end_date),
            'outflow': cc.get_cash_outflow(start_date, end_date),
            'opening_balance': cc.get_opening_balance(start_date),
        }
        cash_flow_data.append(data)
    
    cash_flow_sheet = exporter.workbook.create_sheet("Cash Flow Analysis")
    exporter.create_cost_center_cash_flow_report(cash_flow_data, start_date, end_date)
    
    # 3. Courses and Teachers Sheet
    courses_sheet = exporter.workbook.create_sheet("Courses & Teachers")
    exporter.formatter = exporter.formatter.__class__(exporter.workbook)
    
    # Courses and Teachers headers
    exporter.formatter.format_header(courses_sheet, 1, 1, 8, 
                                   "الدورات والمعلمين - Courses & Teachers")
    
    # Period information
    if start_date and end_date:
        period_text = f"الفترة من {start_date} إلى {end_date} - Period: {start_date} to {end_date}"
        exporter.formatter.format_subheader(courses_sheet, 3, 1, 8, period_text)
    
    # Column headers
    headers = [
        "رمز الدورة", "اسم الدورة", "مركز التكلفة", "السعر",
        "المدرس", "أجر الساعة", "الراتب الشهري", "إجمالي الراتب"
    ]
    
    for col, header in enumerate(headers, 1):
        exporter.formatter.format_subheader(courses_sheet, 5, col, col, header)
    
    # Data rows
    current_row = 6
    courses = Course.objects.filter(is_active=True).prefetch_related('assigned_teachers', 'cost_center')
    
    for course in courses:
        assignments = course.courseteacherassignment_set.filter(is_active=True)
        
        if assignments.exists():
            for assignment in assignments:
                exporter.formatter.format_data_cell(courses_sheet, current_row, 1, course.id)
                exporter.formatter.format_data_cell(courses_sheet, current_row, 2, course.name_ar or course.name)
                exporter.formatter.format_data_cell(courses_sheet, current_row, 3, 
                                                  course.cost_center.name_ar if course.cost_center else "غير محدد")
                exporter.formatter.format_currency_cell(courses_sheet, current_row, 4, course.price)
                exporter.formatter.format_data_cell(courses_sheet, current_row, 5, assignment.teacher.full_name)
                exporter.formatter.format_currency_cell(courses_sheet, current_row, 6, assignment.hourly_rate or 0)
                exporter.formatter.format_currency_cell(courses_sheet, current_row, 7, assignment.monthly_rate or 0)
                exporter.formatter.format_currency_cell(courses_sheet, current_row, 8, assignment.calculate_total_salary())
                current_row += 1
        else:
            # Course without teacher assignments
            exporter.formatter.format_data_cell(courses_sheet, current_row, 1, course.id)
            exporter.formatter.format_data_cell(courses_sheet, current_row, 2, course.name_ar or course.name)
            exporter.formatter.format_data_cell(courses_sheet, current_row, 3, 
                                              course.cost_center.name_ar if course.cost_center else "غير محدد")
            exporter.formatter.format_currency_cell(courses_sheet, current_row, 4, course.price)
            exporter.formatter.format_data_cell(courses_sheet, current_row, 5, "غير محدد")
            exporter.formatter.format_currency_cell(courses_sheet, current_row, 6, 0)
            exporter.formatter.format_currency_cell(courses_sheet, current_row, 7, 0)
            exporter.formatter.format_currency_cell(courses_sheet, current_row, 8, 0)
            current_row += 1
    
    exporter.formatter.auto_adjust_columns(courses_sheet)
    
    # 4. Students and enrollments Sheet
    students_sheet = exporter.workbook.create_sheet("Students & enrollments")
    
    # Students and enrollments headers
    exporter.formatter.format_header(students_sheet, 1, 1, 7, 
                                   "الطلاب والتسجيلات - Students & enrollments")
    
    # Period information
    if start_date and end_date:
        period_text = f"الفترة من {start_date} إلى {end_date} - Period: {start_date} to {end_date}"
        exporter.formatter.format_subheader(students_sheet, 3, 1, 7, period_text)
    
    # Column headers
    headers = [
        "رقم الطالب", "اسم الطالب", "الدورة", "تاريخ التسجيل",
        "المبلغ الإجمالي", "المبلغ المدفوع", "المتبقي"
    ]
    
    for col, header in enumerate(headers, 1):
        exporter.formatter.format_subheader(students_sheet, 5, col, col, header)
    
    # Data rows
    current_row = 6
    enrollments = Studentenrollment.objects.filter(
        enrollment_date__gte=start_date,
        enrollment_date__lte=end_date
    ).select_related('student', 'course')
    
    for enrollment in enrollments:
        exporter.formatter.format_data_cell(students_sheet, current_row, 1, enrollment.student.student_id)
        exporter.formatter.format_data_cell(students_sheet, current_row, 2, getattr(enrollment.student, 'full_name', 'غير محدد'))
        exporter.formatter.format_data_cell(students_sheet, current_row, 3, enrollment.course.name_ar or enrollment.course.name)
        exporter.formatter.format_data_cell(students_sheet, current_row, 4, enrollment.enrollment_date.strftime('%Y-%m-%d'))
        exporter.formatter.format_currency_cell(students_sheet, current_row, 5, enrollment.total_amount)
        exporter.formatter.format_currency_cell(students_sheet, current_row, 6, enrollment.amount_paid)
        exporter.formatter.format_currency_cell(students_sheet, current_row, 7, enrollment.balance_due)
        current_row += 1
    
    exporter.formatter.auto_adjust_columns(students_sheet)
    
    # 5. Financial Transactions Sheet
    transactions_sheet = exporter.workbook.create_sheet("Financial Transactions")
    
    # Financial Transactions headers
    exporter.formatter.format_header(transactions_sheet, 1, 1, 8, 
                                   "المعاملات المالية - Financial Transactions")
    
    # Period information
    if start_date and end_date:
        period_text = f"الفترة من {start_date} إلى {end_date} - Period: {start_date} to {end_date}"
        exporter.formatter.format_subheader(transactions_sheet, 3, 1, 8, period_text)
    
    # Column headers
    headers = [
        "التاريخ", "المرجع", "الحساب", "الوصف", "المبلغ",
        "نوع القيد", "مركز التكلفة", "نوع المعاملة"
    ]
    
    for col, header in enumerate(headers, 1):
        exporter.formatter.format_subheader(transactions_sheet, 5, col, col, header)
    
    # Data rows
    current_row = 6
    transactions = Transaction.objects.filter(
        journal_entry__date__gte=start_date,
        journal_entry__date__lte=end_date
    ).select_related('journal_entry', 'account', 'cost_center')
    
    for transaction in transactions:
        exporter.formatter.format_data_cell(transactions_sheet, current_row, 1, transaction.journal_entry.date.strftime('%Y-%m-%d'))
        exporter.formatter.format_data_cell(transactions_sheet, current_row, 2, transaction.journal_entry.reference)
        exporter.formatter.format_data_cell(transactions_sheet, current_row, 3, transaction.account.name_ar or transaction.account.name)
        exporter.formatter.format_data_cell(transactions_sheet, current_row, 4, transaction.description)
        exporter.formatter.format_currency_cell(transactions_sheet, current_row, 5, transaction.amount)
        exporter.formatter.format_data_cell(transactions_sheet, current_row, 6, "مدين" if transaction.is_debit else "دائن")
        exporter.formatter.format_data_cell(transactions_sheet, current_row, 7, 
                                          transaction.cost_center.name_ar if transaction.cost_center else "غير محدد")
        exporter.formatter.format_data_cell(transactions_sheet, current_row, 8, transaction.journal_entry.get_entry_type_display())
        current_row += 1
    
    exporter.formatter.auto_adjust_columns(transactions_sheet)
    
    # Generate filename
    filename = f"comprehensive_site_export_{start_date}_{end_date}.xlsx" if start_date and end_date else "comprehensive_site_export.xlsx"
    
    return create_excel_response(exporter.workbook, filename)


@login_required
def site_export_dashboard(request):
    """Dashboard for site-wide export options"""
    
    # Get summary statistics
    total_students = Student.objects.filter(is_active=True).count()
    total_teachers = Teacher.objects.count()
    total_courses = Course.objects.filter(is_active=True).count()
    total_cost_centers = CostCenter.objects.filter(is_active=True).count()
    total_transactions = Transaction.objects.count()
    
    # Get recent activity
    recent_enrollments = Studentenrollment.objects.order_by('-enrollment_date')[:10]
    recent_transactions = Transaction.objects.order_by('-created_at')[:10]
    
    context = {
        'total_students': total_students,
        'total_teachers': total_teachers,
        'total_courses': total_courses,
        'total_cost_centers': total_cost_centers,
        'total_transactions': total_transactions,
        'recent_enrollments': recent_enrollments,
        'recent_transactions': recent_transactions,
    }
    
    return render(request, 'accounts/reports/site_export_dashboard.html', context)
