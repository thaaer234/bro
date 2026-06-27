from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import FormView, ListView, TemplateView

from quick.models import AcademicYear

from .forms import (
    AcademicYearAccessPolicyForm,
    AcademicYearSelectionForm,
    AcademicYearTransferBatchForm,
    AcademicYearUnlockForm,
    JournalEntryTransferBatchForm,
)
from .models import (
    AcademicYearStateLog,
    AcademicYearSystemState,
    AcademicYearTransferBatch,
    AcademicYearTransferCourseItem,
    JournalEntryTransferBatch,
    JournalEntryTransferItem,
)
from .services.session import (
    academic_year_requires_unlock,
    get_available_academic_years,
    get_or_create_access_policy,
    get_unlocked_academic_year_ids,
    set_current_academic_year,
    unlock_academic_year,
)
from .services.transfers import AcademicYearTransferService
from .services.journal_entry_transfers import JournalEntryTransferService


class SuperuserRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_superuser


class AcademicYearSelectView(LoginRequiredMixin, FormView):
    template_name = "academic_years/select_current.html"
    form_class = AcademicYearSelectionForm
    success_url = reverse_lazy("root")

    def _ordered_academic_years(self):
        return get_available_academic_years()

    def _pick_default_academic_year(self, academic_years):
        if not academic_years:
            return None

        current_academic_year = getattr(self.request, "current_academic_year", None)
        if current_academic_year and any(year.pk == current_academic_year.pk for year in academic_years):
            return current_academic_year

        system_state = AcademicYearSystemState.load()
        if system_state and any(year.pk == system_state.active_academic_year_id for year in academic_years):
            return system_state.active_academic_year

        open_year = next((year for year in academic_years if not year.is_closed), None)
        return open_year or academic_years[0]

    def dispatch(self, request, *args, **kwargs):
        academic_years = self._ordered_academic_years()
        self.available_academic_years = academic_years
        self.default_academic_year = self._pick_default_academic_year(academic_years)
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["available_years"] = AcademicYear.objects.filter(
            pk__in=[academic_year.pk for academic_year in self.available_academic_years]
        )
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        if getattr(self, "default_academic_year", None):
            initial["academic_year"] = self.default_academic_year.pk
        return initial

    def form_valid(self, form):
        academic_year = form.cleaned_data["academic_year"]
        set_current_academic_year(self.request, academic_year)
        if academic_year_requires_unlock(academic_year):
            messages.info(self.request, f"تم اختيار الفصل: {academic_year}. أدخل كلمة السر للمتابعة.")
            return redirect("academic_years:unlock", pk=academic_year.pk)
        messages.success(self.request, f"تم تعيين الفصل الحالي إلى: {academic_year}")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["system_state"] = AcademicYearSystemState.load()
        context["academic_years"] = self.available_academic_years
        context["default_academic_year"] = getattr(self, "default_academic_year", None)
        context["unlocked_ids"] = get_unlocked_academic_year_ids(self.request)
        return context


class AcademicYearUnlockView(LoginRequiredMixin, FormView):
    template_name = "academic_years/unlock.html"
    form_class = AcademicYearUnlockForm

    def dispatch(self, request, *args, **kwargs):
        self.academic_year = get_object_or_404(AcademicYear, pk=kwargs["pk"])
        set_current_academic_year(request, self.academic_year)
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        policy = get_or_create_access_policy(self.academic_year)
        password = form.cleaned_data["password"]
        if not academic_year_requires_unlock(self.academic_year):
            unlock_academic_year(self.request, self.academic_year)
            messages.info(self.request, "هذا الفصل لا يحتاج كلمة سر.")
            return redirect("root")

        if not policy.password_hash:
            form.add_error("password", "هذا الفصل مغلق لكن لم يتم تعيين كلمة سر له بعد. راجع الإدارة.")
            return self.form_invalid(form)

        if not policy.check_password(password):
            form.add_error("password", "كلمة السر غير صحيحة.")
            return self.form_invalid(form)

        unlock_academic_year(self.request, self.academic_year)
        AcademicYearStateLog.objects.create(
            academic_year=self.academic_year,
            action=AcademicYearStateLog.ACTION_UNLOCKED,
            performed_by=self.request.user,
            notes="تم فتح الفصل من شاشة الحماية.",
        )
        messages.success(self.request, f"تم فتح الفصل: {self.academic_year}")
        return redirect("root")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["academic_year"] = self.academic_year
        context["policy"] = get_or_create_access_policy(self.academic_year)
        return context


class AcademicYearManageView(LoginRequiredMixin, SuperuserRequiredMixin, TemplateView):
    template_name = "academic_years/manage.html"

    def get(self, request, *args, **kwargs):
        self.academic_year = get_object_or_404(AcademicYear, pk=kwargs["pk"])
        policy = get_or_create_access_policy(self.academic_year)
        form = AcademicYearAccessPolicyForm(
            initial={
                "requires_password": policy.requires_password,
                "is_read_only": policy.is_read_only,
                "is_archived": policy.is_archived,
                "allow_reporting": policy.allow_reporting,
            }
        )
        form.policy_has_password = bool(policy.password_hash)
        context = self.get_context_data(form=form)
        return self.render_to_response(context)

    def post(self, request, *args, **kwargs):
        self.academic_year = get_object_or_404(AcademicYear, pk=kwargs["pk"])
        policy = get_or_create_access_policy(self.academic_year)
        form = AcademicYearAccessPolicyForm(request.POST)
        form.policy_has_password = bool(policy.password_hash)
        if not form.is_valid():
            return self.render_to_response(self.get_context_data(form=form))

        previous_requires_password = policy.requires_password
        previous_is_read_only = policy.is_read_only

        policy.requires_password = form.cleaned_data["requires_password"]
        policy.is_read_only = form.cleaned_data["is_read_only"]
        policy.is_archived = form.cleaned_data["is_archived"]
        policy.allow_reporting = form.cleaned_data["allow_reporting"]

        new_password = form.cleaned_data.get("password")
        if policy.requires_password and new_password:
            policy.set_password(new_password)
        elif not policy.requires_password:
            policy.clear_password()

        policy.full_clean()
        policy.save()

        if previous_requires_password != policy.requires_password:
            AcademicYearStateLog.objects.create(
                academic_year=self.academic_year,
                action=(
                    AcademicYearStateLog.ACTION_PASSWORD_ENABLED
                    if policy.requires_password
                    else AcademicYearStateLog.ACTION_PASSWORD_DISABLED
                ),
                performed_by=request.user,
            )

        if previous_is_read_only != policy.is_read_only:
            AcademicYearStateLog.objects.create(
                academic_year=self.academic_year,
                action=(
                    AcademicYearStateLog.ACTION_READ_ONLY_ENABLED
                    if policy.is_read_only
                    else AcademicYearStateLog.ACTION_READ_ONLY_DISABLED
                ),
                performed_by=request.user,
            )

        messages.success(request, "تم تحديث سياسات الفصل بنجاح.")
        return redirect("academic_years:manage", pk=self.academic_year.pk)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["academic_year"] = self.academic_year
        context["system_state"] = AcademicYearSystemState.load()
        context["unlocked_ids"] = get_unlocked_academic_year_ids(self.request)
        return context


class AcademicYearActivateView(LoginRequiredMixin, SuperuserRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        academic_year = get_object_or_404(AcademicYear, pk=kwargs["pk"])
        system_state = AcademicYearSystemState.load()
        if system_state:
            system_state.active_academic_year = academic_year
            system_state.updated_by = request.user
            system_state.save(update_fields=["active_academic_year", "updated_by", "updated_at"])
        else:
            AcademicYearSystemState.objects.create(
                singleton_key="default",
                active_academic_year=academic_year,
                updated_by=request.user,
            )
        set_current_academic_year(request, academic_year)
        AcademicYearStateLog.objects.create(
            academic_year=academic_year,
            action=AcademicYearStateLog.ACTION_ACTIVATED,
            performed_by=request.user,
            notes="تم تفعيل الفصل كفصل العمل اليومي.",
        )
        messages.success(request, f"تم تفعيل الفصل: {academic_year}")
        next_url = request.POST.get("next") or reverse("academic_years:select_current")
        return redirect(next_url)


class AcademicYearTransferBatchListView(LoginRequiredMixin, SuperuserRequiredMixin, ListView):
    model = AcademicYearTransferBatch
    template_name = "academic_years/transfer_list.html"
    context_object_name = "batches"
    paginate_by = 20

    def get_queryset(self):
        return (
            AcademicYearTransferBatch.objects.select_related(
                "source_academic_year",
                "target_academic_year",
                "created_by",
            )
            .prefetch_related("course_items")
            .order_by("-created_at", "-id")
        )


class AcademicYearTransferBatchCreateView(LoginRequiredMixin, SuperuserRequiredMixin, FormView):
    template_name = "academic_years/transfer_create.html"
    form_class = AcademicYearTransferBatchForm

    def form_valid(self, form):
        batch = form.save(commit=False)
        batch.created_by = self.request.user
        batch.status = AcademicYearTransferBatch.STATUS_DRAFT
        batch.save()
        for source_course in form.cleaned_data["source_courses"]:
            AcademicYearTransferCourseItem.objects.create(
                batch=batch,
                source_course=source_course,
            )

        service = AcademicYearTransferService(batch=batch, actor=self.request.user)
        preview = service.build_preview()
        messages.success(self.request, f"تم إنشاء دفعة الترحيل ومعاينتها. عدد الدورات: {preview['courses']}")
        return redirect("academic_years:transfer_detail", pk=batch.pk)


class AcademicYearTransferBatchDetailView(LoginRequiredMixin, SuperuserRequiredMixin, TemplateView):
    template_name = "academic_years/transfer_detail.html"

    def dispatch(self, request, *args, **kwargs):
        self.batch = get_object_or_404(
            AcademicYearTransferBatch.objects.select_related(
                "source_academic_year",
                "target_academic_year",
                "created_by",
            ),
            pk=kwargs["pk"],
        )
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["batch"] = self.batch
        context["course_items"] = self.batch.course_items.select_related("source_course", "target_course").order_by("id")
        context["logs"] = self.batch.logs.order_by("-created_at", "-id")[:100]
        return context


class AcademicYearTransferBatchExecuteView(LoginRequiredMixin, SuperuserRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        batch = get_object_or_404(AcademicYearTransferBatch, pk=kwargs["pk"])
        if batch.status == AcademicYearTransferBatch.STATUS_COMPLETED:
            messages.info(request, "تم تنفيذ هذه الدفعة سابقًا.")
            return redirect("academic_years:transfer_detail", pk=batch.pk)

        service = AcademicYearTransferService(batch=batch, actor=request.user)
        try:
            summary = service.execute()
        except Exception as exc:
            try:
                batch.status = AcademicYearTransferBatch.STATUS_FAILED
                batch.failure_reason = str(exc)
                batch.save(update_fields=["status", "failure_reason", "updated_at"])
            except Exception:
                # Ignore database write failures when connection is in rollback-only state
                pass
            messages.error(request, f"فشل تنفيذ الترحيل: {exc}")
            return redirect("academic_years:transfer_detail", pk=batch.pk)

        messages.success(
            request,
            (
                f"اكتمل الترحيل بنجاح. "
                f"دورات: {summary.get('courses', 0)}، "
                f"تسجيلات: {summary.get('enrollments', 0)}، "
                f"إيصالات: {summary.get('receipts', 0)}، "
                f"قيود: {summary.get('journal_entries', 0)}"
            ),
        )
        return redirect("academic_years:transfer_detail", pk=batch.pk)


# ============================================
# نقل القيود المحاسبية بدون فصول
# ============================================


class JournalEntryTransferBatchListView(LoginRequiredMixin, SuperuserRequiredMixin, ListView):
    """عرض قائمة دفعات نقل القيود"""
    model = JournalEntryTransferBatch
    template_name = "academic_years/journal_entry_transfer_list.html"
    context_object_name = "batches"
    paginate_by = 20

    def get_queryset(self):
        return (
            JournalEntryTransferBatch.objects
            .select_related(
                "target_academic_year",
                "created_by",
            )
            .prefetch_related("journal_entry_items")
            .order_by("-created_at", "-id")
        )


class JournalEntryTransferBatchCreateView(LoginRequiredMixin, SuperuserRequiredMixin, FormView):
    """إنشاء دفعة جديدة لنقل القيود"""
    template_name = "academic_years/journal_entry_transfer_create.html"
    form_class = JournalEntryTransferBatchForm
    success_url = reverse_lazy("academic_years:journal_entry_transfer_list")

    def form_valid(self, form):
        batch = form.save(commit=False)
        batch.created_by = self.request.user
        batch.status = JournalEntryTransferBatch.STATUS_DRAFT
        batch.save()
        
        # إضافة القيود المختارة إلى الدفعة
        for source_entry in form.cleaned_data["source_journal_entries"]:
            JournalEntryTransferItem.objects.create(
                batch=batch,
                source_journal_entry=source_entry,
            )

        # بناء معاينة
        service = JournalEntryTransferService(batch=batch, actor=self.request.user)
        preview = service.build_preview()
        
        messages.success(
            self.request, 
            f"تم إنشاء دفعة نقل القيود ومعاينتها. عدد القيود: {preview['journal_entries']}"
        )
        return redirect("academic_years:journal_entry_transfer_detail", pk=batch.pk)


class JournalEntryTransferBatchDetailView(LoginRequiredMixin, SuperuserRequiredMixin, TemplateView):
    """عرض تفاصيل دفعة نقل القيود"""
    template_name = "academic_years/journal_entry_transfer_detail.html"

    def dispatch(self, request, *args, **kwargs):
        self.batch = get_object_or_404(
            JournalEntryTransferBatch.objects.select_related(
                "target_academic_year",
                "created_by",
            ),
            pk=kwargs["pk"],
        )
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["batch"] = self.batch
        context["journal_entry_items"] = (
            self.batch.journal_entry_items
            .select_related("source_journal_entry", "target_journal_entry")
            .order_by("id")
        )
        context["logs"] = self.batch.logs.order_by("-created_at", "-id")[:100]
        return context


class JournalEntryTransferBatchExecuteView(LoginRequiredMixin, SuperuserRequiredMixin, View):
    """تنفيذ نقل القيود"""
    def post(self, request, *args, **kwargs):
        batch = get_object_or_404(JournalEntryTransferBatch, pk=kwargs["pk"])
        
        if batch.status == JournalEntryTransferBatch.STATUS_COMPLETED:
            messages.info(request, "تم تنفيذ هذه الدفعة سابقًا.")
            return redirect("academic_years:journal_entry_transfer_detail", pk=batch.pk)

        service = JournalEntryTransferService(batch=batch, actor=request.user)
        try:
            summary = service.execute()
        except Exception as exc:
            batch.status = JournalEntryTransferBatch.STATUS_FAILED
            batch.failure_reason = str(exc)
            batch.save(update_fields=["status", "failure_reason", "updated_at"])
            messages.error(request, f"فشل نقل القيود: {exc}")
            return redirect("academic_years:journal_entry_transfer_detail", pk=batch.pk)

        messages.success(
            request,
            (
                f"اكتمل نقل القيود بنجاح. "
                f"قيود: {summary.get('journal_entries', 0)}، "
                f"معاملات: {summary.get('transactions', 0)}"
            ),
        )
        return redirect("academic_years:journal_entry_transfer_detail", pk=batch.pk)


class JournalEntryRecognitionView(LoginRequiredMixin, SuperuserRequiredMixin, TemplateView):
    """الاعتراف بالقيود التي لا تحمل فصل دراسي"""
    template_name = "academic_years/recognize_entries.html"

    def get(self, request, *args, **kwargs):
        from django.db.models import Q
        from accounts.models import JournalEntry
        from quick.models import AcademicYear
        
        search_query = request.GET.get("q", "")
        entry_type = request.GET.get("type", "")
        
        # Base query for unassigned entries
        queryset = JournalEntry.objects.filter(academic_year__isnull=True).select_related("created_by")
        
        if search_query:
            queryset = queryset.filter(
                Q(reference__icontains=search_query) |
                Q(description__icontains=search_query)
            )
            
        if entry_type:
            queryset = queryset.filter(entry_type=entry_type)
            
        entries = queryset.order_by("-date", "-id")[:5000]
        
        academic_years = AcademicYear.objects.order_by("-start_date", "-id")
        entry_types = JournalEntry.ENTRY_TYPE_CHOICES
        
        context = self.get_context_data(**kwargs)
        context.update({
            "entries": entries,
            "academic_years": academic_years,
            "search_query": search_query,
            "entry_type": entry_type,
            "entry_types": entry_types,
        })
        return self.render_to_response(context)

    def post(self, request, *args, **kwargs):
        from django.db import transaction
        from accounts.models import JournalEntry
        from quick.models import AcademicYear
        
        raw_entry_ids = request.POST.getlist("entry_ids")
        raw_academic_year_id = request.POST.get("academic_year")
        
        def clean_id_to_int(val):
            if not val:
                return None
            # Remove localized thousands separators (dots/commas)
            cleaned = str(val).replace(".", "").replace(",", "").strip()
            try:
                return int(cleaned)
            except ValueError:
                return None
                
        entry_ids = [clean_id_to_int(eid) for eid in raw_entry_ids if clean_id_to_int(eid) is not None]
        academic_year_id = clean_id_to_int(raw_academic_year_id)
        
        if not entry_ids:
            messages.error(request, "لم تقم بتحديد أي قيود للاعتراف بها. يرجى تحديد قيد واحد على الأقل.")
            return redirect("academic_years:recognize_entries")
            
        if not academic_year_id:
            messages.error(request, "يرجى تحديد الفصل الدراسي الهدف.")
            return redirect("academic_years:recognize_entries")
            
        try:
            with transaction.atomic():
                academic_year = get_object_or_404(AcademicYear, pk=academic_year_id)
                updated_count = JournalEntry.objects.filter(
                    id__in=entry_ids,
                    academic_year__isnull=True
                ).update(academic_year=academic_year)
                
                messages.success(
                    request,
                    f"تم بنجاح الاعتراف بـ {updated_count} قيد/قيود ونسبتها إلى الفصل: {academic_year.name}."
                )
        except Exception as e:
            messages.error(request, f"حدث خطأ أثناء عملية الاعتراف: {str(e)}")
            
        return redirect("academic_years:transfer_list")


class AccountRecognitionView(LoginRequiredMixin, SuperuserRequiredMixin, TemplateView):
    """الاعتراف بالحسابات وتعيين الفصول أو جعلها مشتركة بكل الفصول"""
    template_name = "academic_years/recognize_accounts.html"

    def get(self, request, *args, **kwargs):
        from django.db.models import Q
        from accounts.models import Account
        from quick.models import AcademicYear
        
        search_query = request.GET.get("q", "")
        account_type = request.GET.get("type", "")
        academic_year_filter = request.GET.get("academic_year_filter", "shared")
        
        # Determine the base query based on filter
        if academic_year_filter == "shared":
            queryset = Account.objects.filter(academic_year__isnull=True)
        elif academic_year_filter == "all":
            queryset = Account.objects.all()
        else:
            try:
                ay_id = int(academic_year_filter)
                queryset = Account.objects.filter(academic_year_id=ay_id)
            except ValueError:
                queryset = Account.objects.filter(academic_year__isnull=True)
        
        if search_query:
            queryset = queryset.filter(
                Q(code__icontains=search_query) |
                Q(name__icontains=search_query) |
                Q(name_ar__icontains=search_query)
            )
            
        if account_type:
            queryset = queryset.filter(account_type=account_type)
            
        accounts = queryset.order_by("code")[:2000]
        
        academic_years = AcademicYear.objects.order_by("-start_date", "-id")
        account_types = Account.ACCOUNT_TYPE_CHOICES
        
        context = self.get_context_data(**kwargs)
        context.update({
            "accounts": accounts,
            "academic_years": academic_years,
            "search_query": search_query,
            "account_type": account_type,
            "academic_year_filter": academic_year_filter,
            "account_types": account_types,
        })
        return self.render_to_response(context)

    def post(self, request, *args, **kwargs):
        from django.db import transaction
        from accounts.models import Account
        from quick.models import AcademicYear
        
        raw_account_ids = request.POST.getlist("account_ids")
        action = request.POST.get("action", "assign")
        raw_academic_year_id = request.POST.get("academic_year")
        
        def clean_id_to_int(val):
            if not val:
                return None
            cleaned = str(val).replace(".", "").replace(",", "").strip()
            try:
                return int(cleaned)
            except ValueError:
                return None
                
        account_ids = [clean_id_to_int(aid) for aid in raw_account_ids if clean_id_to_int(aid) is not None]
        
        if not account_ids:
            messages.error(request, "لم تقم بتحديد أي حسابات لتعديلها. يرجى تحديد حساب واحد على الأقل.")
            return redirect("academic_years:recognize_accounts")
            
        if action == "make_shared":
            try:
                with transaction.atomic():
                    updated_count = Account.objects.filter(id__in=account_ids).update(academic_year=None)
                    messages.success(
                        request,
                        f"تم بنجاح جعل {updated_count} حساب/حسابات مشتركة بكل الفصول الدراسية (تصفير ربط الفصل) ✅."
                    )
            except Exception as e:
                messages.error(request, f"حدث خطأ أثناء جعل الحسابات مشتركة: {str(e)}")
        else: # assign
            academic_year_id = clean_id_to_int(raw_academic_year_id)
            if not academic_year_id:
                messages.error(request, "يرجى تحديد الفصل الدراسي الهدف للاعتراف بالحسابات ونسبها إليه.")
                return redirect("academic_years:recognize_accounts")
                
            try:
                with transaction.atomic():
                    academic_year = get_object_or_404(AcademicYear, pk=academic_year_id)
                    updated_count = Account.objects.filter(id__in=account_ids).update(academic_year=academic_year)
                    messages.success(
                        request,
                        f"تم بنجاح الاعتراف بـ {updated_count} حساب/حسابات ونسبتها إلى الفصل: {academic_year.name}."
                    )
            except Exception as e:
                messages.error(request, f"حدث خطأ أثناء عملية الاعتراف: {str(e)}")
                
        return redirect("academic_years:recognize_accounts")


