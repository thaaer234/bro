from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q
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
