from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.generic import DetailView, TemplateView
from django.views.decorators.http import require_POST

from .forms import AnnouncementForm
from .models import Announcement, AnnouncementReceipt
from .services import (
    build_announcement_previews,
    get_targeted_count,
    mark_web_announcement_dismissed,
)


class SuperuserRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_superuser


class AnnouncementDashboardView(SuperuserRequiredMixin, TemplateView):
    template_name = "announcements/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form"] = kwargs.get("form") or AnnouncementForm()
        context["announcements"] = Announcement.objects.select_related("created_by").prefetch_related("receipts")
        context["active_count"] = Announcement.objects.filter(is_active=True).count()
        context["receipts_count"] = AnnouncementReceipt.objects.count()
        return context

    def post(self, request, *args, **kwargs):
        preset = request.POST.get("preset")
        if preset == "password_reset_users":
            announcement = Announcement.objects.create(
                title="يرجى من المستخدمين تعديل كلمات المرور",
                message=(
                    "مرحباً {name}\n"
                    "يرجى تقديم طلب تعديل كلمة المرور الخاصة بحسابك عبر الرابط التالي.\n"
                    "بعد إرسال الطلب ستتم مراجعته ثم إرسال الكود إليك حسب الإجراء المعتمد."
                ),
                action_label="طلب تعديل كلمة المرور",
                action_url=request.build_absolute_uri(reverse("registration:password_reset_request")),
                audience_type=Announcement.AUDIENCE_USER,
                is_active=True,
                show_as_popup=True,
                created_by=request.user,
            )
            messages.success(request, "تم إنشاء تعميم تغيير كلمات المرور الجاهز.")
            return redirect("announcements:detail", pk=announcement.pk)

        form = AnnouncementForm(request.POST)
        if form.is_valid():
            announcement = form.save(commit=False)
            announcement.created_by = request.user
            announcement.save()
            messages.success(request, "تم إنشاء التعميم بنجاح.")
            return redirect("announcements:detail", pk=announcement.pk)
        messages.error(request, "تعذر حفظ التعميم. تحقق من الحقول المطلوبة.")
        return self.render_to_response(self.get_context_data(form=form))


class AnnouncementDetailView(SuperuserRequiredMixin, DetailView):
    template_name = "announcements/detail.html"
    model = Announcement
    context_object_name = "announcement"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        announcement = self.object
        context["receipts"] = announcement.receipts.select_related(
            "recipient_user",
            "recipient_student",
            "recipient_teacher",
        )
        context["previews"] = build_announcement_previews(announcement)
        context["targeted_count"] = get_targeted_count(announcement)
        return context


@login_required
@require_POST
def dismiss_web_announcement(request, announcement_id):
    announcement = get_object_or_404(
        Announcement.objects.active().filter(audience_type=Announcement.AUDIENCE_USER, show_as_popup=True),
        pk=announcement_id,
    )
    mark_web_announcement_dismissed(announcement, request.user)
    return JsonResponse({"status": "ok"})
