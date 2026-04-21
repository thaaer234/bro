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
)
from .models import (
    AcademicYearStateLog,
    AcademicYearSystemState,
    AcademicYearTransferBatch,
    AcademicYearTransferCourseItem,
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
            batch.status = AcademicYearTransferBatch.STATUS_FAILED
            batch.failure_reason = str(exc)
            batch.save(update_fields=["status", "failure_reason", "updated_at"])
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
