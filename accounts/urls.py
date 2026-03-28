from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import api_views
from . import views
from . import financial_reports_views
from . import site_export_views
from .views import OutstandingStudentsByClassroomView
from employ.decorators import require_employee_perm

app_name = 'accounts'

urlpatterns = [
    # Dashboard
    path('', require_employee_perm('accounting_dashboard')(views.DashboardView.as_view()), name='dashboard'),
    
    # Chart of Accounts
    path('chart/', require_employee_perm('accounting_accounts')(views.ChartOfAccountsView.as_view()), name='chart_of_accounts'),
    path('accounts/create/', require_employee_perm('accounting_accounts_create')(views.AccountCreateView.as_view()), name='account_create'),
    path('accounts/<int:pk>/', require_employee_perm('accounting_accounts')(views.AccountDetailView.as_view()), name='account_detail'),
    path('accounts/<int:pk>/update/', require_employee_perm('accounting_accounts_create')(views.AccountUpdateView.as_view()), name='account_update'),
    path('accounts/<int:pk>/delete/', require_employee_perm('accounting_accounts_create')(views.AccountDeleteView.as_view()), name='account_delete'),
    path('enrollments/<int:student_id>/withdraw/', require_employee_perm('accounting_entries')(views.enrollmentWithdrawView.as_view()), name='enrollment_withdraw'),
    
    # Journal Entries
    path('journal/', require_employee_perm('accounting_entries')(views.JournalEntryListView.as_view()), name='journal_entry_list'),
    path('journal/create/', require_employee_perm('accounting_entries')(views.JournalEntryCreateView.as_view()), name='journal_entry_create'),
    path('journal/<int:pk>/', require_employee_perm('accounting_entries')(views.JournalEntryDetailView.as_view()), name='journal_entry_detail'),
    path('journal/<int:pk>/update/', require_employee_perm('accounting_entries')(views.JournalEntryUpdateView.as_view()), name='journal_entry_update'),
    path('journal/<int:pk>/post/', require_employee_perm('accounting_entries_post')(views.PostJournalEntryView.as_view()), name='journal_entry_post'),
    path('journal/<int:pk>/reverse/', require_employee_perm('accounting_entries')(views.ReverseJournalEntryView.as_view()), name='journal_entry_reverse'),
    path('journal/<int:pk>/delete/', require_employee_perm('accounting_entries')(views.delete_journal_entry), name='journal_entry_delete'),
    path('journal/fix-mojibake/', require_employee_perm('accounting_entries')(views.fix_journal_mojibake_records), name='fix_journal_mojibake'),
    path('journal/<int:pk>/fix-mojibake/', require_employee_perm('accounting_entries')(views.fix_single_journal_mojibake), name='fix_single_journal_mojibake'),
    
    # Reports
    path('reports/', require_employee_perm('accounting_reports')(views.ReportsView.as_view()), name='reports'),
    path('reports/trial-balance/', require_employee_perm('accounting_trial_balance')(views.TrialBalanceView.as_view()), name='trial_balance'),
    path('reports/income-statement/', require_employee_perm('accounting_income_statement')(views.IncomeStatementView.as_view()), name='income_statement'),
    path('reports/balance-sheet/', require_employee_perm('accounting_balance_sheet')(views.BalanceSheetView.as_view()), name='balance_sheet'),
    path('reports/ledger/<int:account_id>/', require_employee_perm('accounting_ledger')(views.LedgerView.as_view()), name='ledger'),
    path('reports/account-statement/', require_employee_perm('accounting_reports')(views.AccountStatementView.as_view()), name='account_statement'),
    path('trial-balance/export-excel/', require_employee_perm('accounting_export')(views.TrialBalanceExportExcelView.as_view()), name='trial_balance_export_excel'),
    
    # Exports
    path('reports/trial-balance/export/xlsx/', require_employee_perm('accounting_export')(views.TrialBalanceExportExcelView.as_view()), name='trial_balance_export'),
    path('reports/income-statement/export/xlsx/', require_employee_perm('accounting_export')(views.IncomeStatementExportExcelView.as_view()), name='income_statement_export'),
    path('reports/balance-sheet/export/xlsx/', require_employee_perm('accounting_export')(views.BalanceSheetExportExcelView.as_view()), name='balance_sheet_export'),
    path('reports/ledger/<int:account_id>/export/xlsx/', require_employee_perm('accounting_export')(views.LedgerExportExcelView.as_view()), name='ledger_export'),
    path('reports/account-statement/export/', require_employee_perm('accounting_export')(views.AccountStatementExportView.as_view()), name='account_statement_export'),
    path('reports/outstanding/export/', require_employee_perm('accounting_export')(views.OutstandingReportsExportView.as_view()), name='export_outstanding_reports'),
    
    # Student Receipts
    path('receipts/create/', require_employee_perm('accounting_receipts_create')(views.StudentReceiptCreateView.as_view()), name='student_receipt_create'),
    path('receipts/<int:pk>/', require_employee_perm('accounting_receipts')(views.StudentReceiptDetailView.as_view()), name='student_receipt_detail'),
    path('receipts/<int:pk>/print/', require_employee_perm('accounting_receipts')(views.student_receipt_print), name='student_receipt_print'),

    # Mobile API (accounts scope)
    path('api/student/finance/', api_views.get_student_finance_profile, name='student_finance_profile_api'),

    # Expenses
    path('expenses/create/', require_employee_perm('accounting_expenses_create')(views.ExpenseCreateView.as_view()), name='expense_create'),
    path('expenses/<int:pk>/', require_employee_perm('accounting_expenses')(views.ExpenseDetailView.as_view()), name='expense_detail'),
    
    # Courses
    path('courses/', require_employee_perm('courses_view')(views.CourseListView.as_view()), name='course_list'),
    path('courses/create/', require_employee_perm('courses_create')(views.CourseCreateView.as_view()), name='course_create'),
    path('courses/<int:pk>/', require_employee_perm('courses_view')(views.CourseDetailView.as_view()), name='course_detail'),
    path('courses/<int:pk>/update/', require_employee_perm('courses_edit')(views.CourseUpdateView.as_view()), name='course_update'),
    
    # Employee Advances
    path('advances/', require_employee_perm('hr_advances')(views.EmployeeAdvanceListView.as_view()), name='advance_list'),
    path('advances/create/', require_employee_perm('hr_advances_create')(views.EmployeeAdvanceCreateView.as_view()), name='advance_create'),
    path('advances/<int:pk>/', require_employee_perm('hr_advances')(views.EmployeeAdvanceDetailView.as_view()), name='advance_detail'),
    
    # Employee Financial Profiles
    path('employees/financial/', require_employee_perm('hr_salary')(views.EmployeeFinancialOverviewView.as_view()), name='employee_financial_overview'),
    path('employees/financial/<str:entity_type>/<int:pk>/', require_employee_perm('hr_salary')(views.EmployeeFinancialProfileView.as_view()), name='employee_financial_profile'),

    # Outstanding Reports
    path('reports/outstanding-courses/', require_employee_perm('accounting_outstanding')(views.OutstandingCoursesView.as_view()), name='outstanding_courses'),
    path('reports/outstanding-courses/<int:course_id>/students/', require_employee_perm('accounting_outstanding')(views.OutstandingCourseStudentsView.as_view()), name='outstanding_course_students'),
    
    # Budget Management
    path('budgets/', require_employee_perm('accounting_budgets')(views.BudgetListView.as_view()), name='budget_list'),
    path('budgets/create/', require_employee_perm('accounting_budgets')(views.BudgetCreateView.as_view()), name='budget_create'),
    path('budgets/<int:pk>/', require_employee_perm('accounting_budgets')(views.BudgetDetailView.as_view()), name='budget_detail'),
    path('budgets/<int:pk>/update/', require_employee_perm('accounting_budgets')(views.BudgetUpdateView.as_view()), name='budget_update'),
    
    # Accounting Periods
    path('periods/', require_employee_perm('accounting_periods')(views.AccountingPeriodListView.as_view()), name='period_list'),
    path('periods/create/', require_employee_perm('accounting_periods')(views.AccountingPeriodCreateView.as_view()), name='period_create'),
    path('periods/<int:pk>/', require_employee_perm('accounting_periods')(views.AccountingPeriodDetailView.as_view()), name='period_detail'),
    path('periods/<int:pk>/update/', require_employee_perm('accounting_periods')(views.AccountingPeriodUpdateView.as_view()), name='period_update'),
    path('periods/<int:pk>/close/', require_employee_perm('accounting_periods')(views.ClosePeriodView.as_view()), name='period_close'),
    
    # Receipts and Expenses
    path('receipts-expenses/', require_employee_perm('accounting_receipts')(views.ReceiptsExpensesView.as_view()), name='receipts_expenses'),
    
    # Cost Centers
    path('cost-centers/', require_employee_perm('accounting_cost_centers')(views.CostCenterListView.as_view()), name='cost_center_list'),
    path('cost-centers/create/', require_employee_perm('accounting_cost_centers')(views.CostCenterCreateView.as_view()), name='cost_center_create'),
    path('cost-centers/<int:pk>/update/', require_employee_perm('accounting_cost_centers')(views.CostCenterUpdateView.as_view()), name='cost_center_update'),
    
    # AJAX endpoints
    path('ajax/course/<int:pk>/price/', require_employee_perm('accounting_receipts_create')(views.ajax_course_price), name='ajax_course_price'),
    
    # Discount Rules
    path('discount-rules/', require_employee_perm('accounting_receipts')(views.DiscountRuleListView.as_view()), name='discount_rule_list'),
    path('discount-rules/create/', require_employee_perm('accounting_receipts')(views.DiscountRuleCreateView.as_view()), name='discount_rule_create'),
    path('discount-rules/<int:pk>/', require_employee_perm('accounting_receipts')(views.DiscountRuleDetailView.as_view()), name='discount_rule_detail'),
    path('discount-rules/<int:pk>/update/', require_employee_perm('accounting_receipts')(views.DiscountRuleUpdateView.as_view()), name='discount_rule_update'),
    path('discount-rules/<int:pk>/delete/', require_employee_perm('accounting_receipts')(views.DiscountRuleDeleteView.as_view()), name='discount_rule_delete'),
    
    # AJAX endpoints for discounts
    path('ajax/discount-rule/<str:reason>/', require_employee_perm('accounting_receipts_create')(views.ajax_discount_rule), name='ajax_discount_rule'),
    
    # Financial Reports URLs
    path('reports/financial/', require_employee_perm('accounting_reports')(financial_reports_views.financial_reports_dashboard), name='financial_reports_dashboard'),
    path('reports/cost-center-analysis/', require_employee_perm('accounting_reports')(financial_reports_views.CostCenterAnalysisReportView.as_view()), name='cost_center_analysis'),
    path('reports/cost-center-cash-flow/', require_employee_perm('accounting_reports')(financial_reports_views.CostCenterCashFlowReportView.as_view()), name='cost_center_cash_flow'),
    path('reports/comprehensive/', require_employee_perm('accounting_reports')(financial_reports_views.ComprehensiveFinancialReportView.as_view()), name='comprehensive_financial'),
    path('reports/cost-center/<int:cost_center_id>/', require_employee_perm('accounting_reports')(financial_reports_views.cost_center_detail_report), name='cost_center_detail'),
    
    # AJAX endpoints for financial reports
    path('ajax/cost-center-data/', require_employee_perm('accounting_reports')(financial_reports_views.get_cost_center_data), name='ajax_cost_center_data'),
    
    # Site-wide Export URLs
    path('reports/site-export/', require_employee_perm('accounting_export')(site_export_views.site_export_dashboard), name='site_export_dashboard'),
    path('reports/site-export/comprehensive/', require_employee_perm('accounting_export')(site_export_views.comprehensive_site_export), name='comprehensive_site_export'),
    
    # Number Formatter Demo
    path('reports/number-formatter-demo/', require_employee_perm('accounting_reports')(views.number_formatter_demo), name='number_formatter_demo'),
    
    # الإيصال الفوري
    path('student/<int:student_id>/quick-receipt/', require_employee_perm('accounting_receipts_create')(views.quick_receipt), name='quick_receipt'),
    
    # سحب الطالب
    path('student/<int:student_id>/withdraw/', require_employee_perm('students_withdraw')(views.student_withdraw_view), name='student_withdraw'),
    path('enrollment/<int:enrollment_id>/withdraw-process/', require_employee_perm('students_withdraw')(views.process_withdraw), name='process_withdraw'),
    path('outstanding-students/classroom/', require_employee_perm('accounting_outstanding')(OutstandingStudentsByClassroomView.as_view()),  name='outstanding_students_by_classroom'),
    path('withdrawn-students/', require_employee_perm('students_view')(views.WithdrawnStudentsView.as_view()), name='withdrawn_students'),
    path('classroom/<int:classroom_id>/', require_employee_perm('classroom_view')(views.ClassroomDetailView.as_view()), name='classroom_detail'),
    
    # Cost Center URLs
    path('cost-centers/', require_employee_perm('accounting_cost_centers')(views.CostCenterListView.as_view()), name='cost_center_list'),
    path('cost-centers/create/', require_employee_perm('accounting_cost_centers')(views.CostCenterCreateView.as_view()), name='cost_center_create'),
    path('cost-centers/<int:pk>/', require_employee_perm('accounting_cost_centers')(views.CostCenterDetailView.as_view()), name='cost_center_detail'),
    path('cost-centers/<int:pk>/update/', require_employee_perm('accounting_cost_centers')(views.CostCenterUpdateView.as_view()), name='cost_center_update'),
    path('cost-centers/<int:pk>/financial-report/', require_employee_perm('accounting_reports')(views.CostCenterFinancialReportView.as_view()), name='cost_center_financial_report'),
    path('cost-center/<int:pk>/detailed-report/', require_employee_perm('accounting_reports')(views.CostCenterDetailedReportView.as_view()), name='cost_center_detailed_report'),
]
