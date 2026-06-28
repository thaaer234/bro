from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q
from decimal import Decimal
from accounts.models import Studentenrollment, StudentReceipt, JournalEntry, Transaction, Account
from students.models import Student as SProfile
from .models import TechnicalReport
from .forms import TechnicalReportStep1Form, TechnicalReportStep2Form
from .utils import generate_ai_prompt


def staff_member_required(view_func):
    """
    Decorator that requires the user to be logged in and is_staff or is_superuser.
    """
    actual_decorator = user_passes_test(
        lambda u: u.is_active and (u.is_staff or u.is_superuser),
        login_url='login'
    )
    return actual_decorator(view_func)


@login_required
@staff_member_required
def report_list(request):
    """
    Dashboard list view showing all logged issues and completed technical reports.
    """
    reports = TechnicalReport.objects.all()
    
    # Simple search/filter
    query = request.GET.get('q', '').strip()
    if query:
        reports = reports.filter(
            Q(report_number__icontains=query) |
            Q(employee__first_name__icontains=query) |
            Q(employee__last_name__icontains=query) |
            Q(employee__username__icontains=query) |
            Q(issue_description__icontains=query) |
            Q(department__icontains=query)
        )
        
    status_filter = request.GET.get('status', '')
    if status_filter == 'resolved':
        reports = reports.filter(is_resolved=True)
    elif status_filter == 'unresolved':
        reports = reports.filter(is_resolved=False)
        
    # Calculate overall statistics
    total_count = TechnicalReport.objects.count()
    resolved_count = TechnicalReport.objects.filter(is_resolved=True).count()
    pending_count = TechnicalReport.objects.filter(is_resolved=False).count()

    context = {
        'reports': reports,
        'query': query,
        'status_filter': status_filter,
        'total_count': total_count,
        'resolved_count': resolved_count,
        'pending_count': pending_count,
    }
    return render(request, 'technical_services/report_list.html', context)


@login_required
@staff_member_required
def report_create(request):
    """
    Step 1: Create a technical report instance and log initial issue description.
    """
    if request.method == 'POST':
        form = TechnicalReportStep1Form(request.POST)
        if form.is_valid():
            report = form.save(commit=False)
            report.is_resolved = False
            report.save()
            messages.success(request, "تم تسجيل بلاغ المشكلة بنجاح. يرجى متابعة الخطوة الثانية لتوليد الحل التقني.")
            return redirect('technical_services:report_process', pk=report.pk)
    else:
        # Prepopulate with defaults if appropriate
        form = TechnicalReportStep1Form(initial={'incident_date': timezone.now().date()})
        
    context = {
        'form': form,
        'step': 1,
    }
    return render(request, 'technical_services/report_create.html', context)


@login_required
@staff_member_required
def report_process(request, pk):
    """
    Step 2: Generate the AI prompt and input the AI-generated resolution fields.
    """
    report = get_object_or_404(TechnicalReport, pk=pk)
    
    if request.method == 'POST':
        form = TechnicalReportStep2Form(request.POST, instance=report)
        if form.is_valid():
            report = form.save(commit=False)
            report.is_resolved = True
            
            # Step 3: Generate unique report number: REP-YYYYMMDD-ID
            # Only generate if it doesn't already have one
            if not report.report_number:
                date_str = timezone.now().strftime('%Y%m%d')
                report.report_number = f"REP-{date_str}-{report.id}"
                
            report.save()
            messages.success(request, f"تم اعتماد وحفظ التقرير التقني بنجاح بالرقم: {report.report_number}")
            return redirect('technical_services:report_detail', pk=report.pk)
    else:
        form = TechnicalReportStep2Form(instance=report)
        
    ai_prompt = generate_ai_prompt(report)
    
    context = {
        'report': report,
        'form': form,
        'ai_prompt': ai_prompt,
        'step': 2,
    }
    return render(request, 'technical_services/report_process.html', context)


# @login_required
# @staff_member_required
def report_detail(request, pk):
    """
    Step 3 / Detail: Render the completed high-fidelity printable technical report.
    """
    report = get_object_or_404(TechnicalReport, pk=pk)
    context = {
        'report': report,
        'step': 3,
    }
    return render(request, 'technical_services/report_detail.html', context)


@login_required
@staff_member_required
def report_delete(request, pk):
    """
    Delete a report.
    """
    report = get_object_or_404(TechnicalReport, pk=pk)
    if request.method == 'POST':
        report_number = report.report_number or f"بلاغ رقم {report.id}"
        report.delete()
        messages.success(request, f"تم حذف {report_number} بنجاح.")
        return redirect('technical_services:report_list')
    return render(request, 'technical_services/report_confirm_delete.html', {'report': report})


@login_required
@staff_member_required
def student_lifecycle_report(request, student_id=None):
    """
    تقرير ذكي يوضح الخط الزمني والدورة المستندية والقيود المالية التفصيلية التي تتم على الطالب.
    يدعم عرض بيانات طالب حقيقي أو تشغيل مثال محاكاة تجريبي (Demo).
    """
    demo_mode = request.GET.get('demo', 'false').lower() == 'true' or student_id is None
    
    from django.contrib.auth.models import User
    employee_user = User.objects.filter(Q(username__icontains='raneem') | Q(first_name__icontains='رنيم') | Q(last_name__icontains='مرعشلي')).first()
    if not employee_user:
        employee_user = request.user

    if demo_mode:
        student_info = {
            'id': 1055,
            'full_name': 'ابتسام الملقي',
            'branch': 'علمي',
            'student_number': 'STU-1055',
            'registration_date': '2026-04-02',
            'phone': 'N/A',
        }
        
        course_info = {
            'name': 'دورة صيف علمي 2026-2027',
            'price': Decimal("6000000.00"),
            'discount_percent': Decimal("20.00"),
            'discount_amount': Decimal("1200000.00"),
            'net_price': Decimal("4800000.00"),
            'amount_paid': Decimal("0.00"),
            'refund_amount': Decimal("4800000.00"),
            'kept_amount': Decimal("0.00"),
            'remaining_due': Decimal("0.00"),
        }
        
        steps = [
            {
                'number': 1,
                'title': '1. تسجيل الطالب بالدورة (مرحلة الاستحقاق)',
                'badge_class': 'badge-enrollment',
                'type_text': 'تسجيل / ENROLLMENT',
                'desc': 'Student enrollment - ابتسام الملقي in دورة صيف علمي 2026-2027',
                'ref': 'JE-007875',
                'date': '2026-04-02',
                'transactions': [
                    {'code': '1251-018-1055', 'name': 'ذمة ابتسام الملقي - دورة صيف علمي 2026-2027', 'debit': Decimal('5100000.00'), 'credit': Decimal('0.00'), 'desc': 'enrollment - ابتسام الملقي'},
                    {'code': '21001-018', 'name': 'إيرادات مؤجلة - دورة صيف علمي 2026-2027', 'debit': Decimal('0.00'), 'credit': Decimal('5100000.00'), 'desc': 'Deferred revenue - دورة صيف علمي 2026-2027'},
                ]
            },
            {
                'number': 2,
                'title': '2. المقبوضات النقدية (إيصالات القبض)',
                'badge_class': 'badge-payment',
                'type_text': 'دفعة / PAYMENT',
                'desc': 'دفعات نقدية مقبوضة بالصناديق من الطالبة ابتسام الملقي',
                'ref': 'JE-007876 / JE-011369 / JE-012235',
                'date': '2026-06-10',
                'transactions': [
                    {'code': '121-0007', 'name': 'صندوق سارة الساسة', 'debit': Decimal('2100000.00'), 'credit': Decimal('0.00'), 'desc': 'Cash received - ابتسام الملقي'},
                    {'code': '121-0008', 'name': 'صندوق رنيم مرعشلي', 'debit': Decimal('2700000.00'), 'credit': Decimal('0.00'), 'desc': 'Cash received - ابتسام الملقي'},
                    {'code': '1251-018-1055', 'name': 'ذمة ابتسام الملقي - دورة صيف علمي 2026-2027', 'debit': Decimal('0.00'), 'credit': Decimal('4800000.00'), 'desc': 'Payment received - دورة صيف علمي 2026-2027'},
                ]
            },
            {
                'number': 3,
                'title': '3. تعديل استحقاق / تطبيق حسم',
                'badge_class': 'badge-adjustment',
                'type_text': 'حسم / DISCOUNT',
                'desc': 'تعديل حسم - ابتسام الملقي - دورة صيف علمي 2026-2027',
                'ref': 'JE-012666',
                'date': '2026-06-24',
                'transactions': [
                    {'code': '21001-018', 'name': 'إيرادات مؤجلة - دورة صيف علمي 2026-2027', 'debit': Decimal('300000.00'), 'credit': Decimal('0.00'), 'desc': 'تعديل تخفيض حسم - ابتسام الملقي'},
                    {'code': '1251-018-1055', 'name': 'ذمة ابتسام الملقي - دورة صيف علمي 2026-2027', 'debit': Decimal('0.00'), 'credit': Decimal('300000.00'), 'desc': 'تعديل تخفيض حسم - دورة صيف علمي 2026-2027'},
                ]
            },
            {
                'number': 4,
                'title': '4. انسحاب الطالب وتسوية الحسابات (إلغاء واسترداد كامل)',
                'badge_class': 'badge-withdrawal',
                'type_text': 'انسحاب / WITHDRAWAL',
                'desc': 'استرداد كامل المبالغ المدفوعة وعكس الإيرادات المؤجلة وتصفير ذمة الطالب بالكامل.',
                'ref': 'JE-012809 / WD-622 / WD-REV-622',
                'date': '2026-06-28',
                'transactions': [
                    {'code': '1251-018-1055', 'name': 'ذمة ابتسام الملقي - دورة صيف علمي 2026-2027', 'debit': Decimal('3800000.00'), 'credit': Decimal('0.00'), 'desc': 'استرداد مبلغ - دورة صيف علمي 2026-2027'},
                    {'code': '121', 'name': 'النقدية', 'debit': Decimal('0.00'), 'credit': Decimal('3800000.00'), 'desc': 'مرتجع نقدي - ابتسام الملقي'},
                    {'code': '4201', 'name': 'إيرادات انسحاب طلاب', 'debit': Decimal('1000000.00'), 'credit': Decimal('0.00'), 'desc': 'إيرادات سحب: ابتسام الملقي - دورة صيف علمي 2026-2027'},
                    {'code': '121', 'name': 'النقدية', 'debit': Decimal('0.00'), 'credit': Decimal('1000000.00'), 'desc': 'استرداد نقدي: ابتسام الملقي'},
                    {'code': '21001-018', 'name': 'إيرادات مؤجلة - دورة صيف علمي 2026-2027', 'debit': Decimal('3800000.00'), 'credit': Decimal('0.00'), 'desc': 'عكس إيرادات مؤجلة - ابتسام الملقي'},
                    {'code': '1251-018-1055', 'name': 'ذمة ابتسام الملقي - دورة صيف علمي 2026-2027', 'debit': Decimal('0.00'), 'credit': Decimal('3800000.00'), 'desc': 'تصفية ذمة - دورة صيف علمي 2026-2027'},
                ]
            }
        ]
        
        context = {
            'demo_mode': True,
            'student': student_info,
            'course': course_info,
            'steps': steps,
            'report_date': timezone.now().date(),
            'employee': employee_user,
        }
    else:
        student = get_object_or_404(SProfile, id=student_id)
        enrollments = Studentenrollment.objects.filter(student=student).select_related('course', 'academic_year')
        
        real_enrollments = []
        for enrollment in enrollments:
            course = enrollment.course
            student_code = f"1251-{course.id:03d}-{student.id:03d}"
            ar_account = Account.objects.filter(code=student_code).first()
            
            receipts = StudentReceipt.objects.filter(enrollment=enrollment).select_related('journal_entry')
            withdrawals = JournalEntry.objects.filter(reference__startswith=f"WD-{enrollment.id}-")
            
            steps = []
            step_idx = 1
            
            if enrollment.enrollment_journal_entry:
                je = enrollment.enrollment_journal_entry
                tx_items = []
                for tx in je.transactions.all().select_related('account'):
                    tx_items.append({
                        'code': tx.account.code,
                        'name': tx.account.name_ar or tx.account.name,
                        'debit': tx.amount if tx.is_debit else Decimal('0'),
                        'credit': tx.amount if not tx.is_debit else Decimal('0'),
                        'desc': tx.description or ''
                    })
                steps.append({
                    'number': step_idx,
                    'title': f'{step_idx}. قيد تسجيل الطالب (إثبات الاستحقاق)',
                    'badge_class': 'badge-enrollment',
                    'type_text': 'تسجيل / ENROLLMENT',
                    'desc': je.description,
                    'ref': je.reference or f'JE-{je.id}',
                    'date': je.date,
                    'transactions': tx_items
                })
                step_idx += 1
            
            for r in receipts:
                if r.journal_entry:
                    je = r.journal_entry
                    tx_items = []
                    for tx in je.transactions.all().select_related('account'):
                        tx_items.append({
                            'code': tx.account.code,
                            'name': tx.account.name_ar or tx.account.name,
                            'debit': tx.amount if tx.is_debit else Decimal('0'),
                            'credit': tx.amount if not tx.is_debit else Decimal('0'),
                            'desc': tx.description or ''
                        })
                    steps.append({
                        'number': step_idx,
                        'title': f'{step_idx}. قبض مالي - إيصال رقم {r.receipt_number}',
                        'badge_class': 'badge-payment',
                        'type_text': 'إيصال قبض / PAYMENT',
                        'desc': je.description,
                        'ref': je.reference or f'JE-{je.id}',
                        'date': je.date,
                        'transactions': tx_items
                    })
                    step_idx += 1
            
            for w in withdrawals:
                tx_items = []
                for tx in w.transactions.all().select_related('account'):
                    tx_items.append({
                        'code': tx.account.code,
                        'name': tx.account.name_ar or tx.account.name,
                        'debit': tx.amount if tx.is_debit else Decimal('0'),
                        'credit': tx.amount if not tx.is_debit else Decimal('0'),
                        'desc': tx.description or ''
                    })
                steps.append({
                    'number': step_idx,
                    'title': f'{step_idx}. تسوية وانسحاب من الدورة',
                    'badge_class': 'badge-withdrawal',
                    'type_text': 'انسحاب / WITHDRAWAL',
                    'desc': w.description,
                    'ref': w.reference or f'JE-{w.id}',
                    'date': w.date,
                    'transactions': tx_items
                })
                step_idx += 1

            real_enrollments.append({
                'enrollment': enrollment,
                'course': {
                    'name': course.name_ar or course.name,
                    'price': enrollment.total_amount,
                    'discount_percent': enrollment.discount_percent,
                    'discount_amount': enrollment.discount_amount,
                    'net_price': enrollment.net_amount,
                    'amount_paid': enrollment.amount_paid,
                    'remaining_due': enrollment.balance_due,
                },
                'steps': steps
            })

        context = {
            'demo_mode': False,
            'student': student,
            'enrollments_data': real_enrollments,
            'report_date': timezone.now().date(),
            'employee': employee_user,
        }
        
    return render(request, 'technical_services/student_lifecycle_report.html', context)
