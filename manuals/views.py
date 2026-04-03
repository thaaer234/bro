from io import BytesIO
import base64
from pathlib import Path

import qrcode
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.templatetags.static import static
from django.views.generic import TemplateView

from .guide_data import USER_MANUAL_ERRORS, build_manuals_context, build_user_manual_context


def _qr_data_uri(value):
    qr = qrcode.QRCode(box_size=7, border=2)
    qr.add_data(value)
    qr.make(fit=True)
    image = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _build_closing_page_context(request):
    base_url = request.build_absolute_uri("/").rstrip("/")
    manual_url = request.build_absolute_uri("/manuals/handbook/")
    developer_site_url = "https://thaaer7426.space.z.ai/"
    return {
        "closing_brand_name": "نظام معهد اليمان",
        "closing_developer_name": "ثائر المصري",
        "closing_role": "Full-Stack Developer",
        "closing_stack": "Django / Web Systems",
        "closing_developer_phone": "0983232446",
        "closing_developer_email": "thaaer74@gmail.com",
        "closing_developer_site_url": developer_site_url,
        "closing_developer_site_qr": _qr_data_uri(developer_site_url),
        "closing_developer_photo": request.build_absolute_uri("/media/profile_pictures/IMG_4472_2.jpeg"),
        "closing_skills": ["البرمجة", "تطوير الويب", "قواعد البيانات"],
        "closing_site_url": base_url,
        "closing_manual_url": manual_url,
        "closing_site_qr": _qr_data_uri(base_url),
        "closing_manual_qr": _qr_data_uri(manual_url),
    }


def _manual_target_users(request_user):
    if request_user.is_superuser:
        users = User.objects.select_related("employee_profile").order_by("first_name", "last_name", "username")
    else:
        users = User.objects.filter(pk=request_user.pk).select_related("employee_profile")
    items = []
    for user in users:
        employee = getattr(user, "employee_profile", None)
        items.append(
            {
                "id": user.pk,
                "username": user.username,
                "full_name": user.get_full_name() or user.username,
                "position": employee.get_position_display() if employee else "مستخدم نظام",
            }
        )
    return items


def _selected_manual_user(request):
    selected_id = request.GET.get("user") or request.POST.get("user")
    users = _manual_target_users(request.user)
    if not users:
        return None, users
    if selected_id:
        for item in users:
            if str(item["id"]) == str(selected_id):
                return get_object_or_404(User, pk=item["id"]), users
    return get_object_or_404(User, pk=users[0]["id"]), users


def _build_user_manual_identity_context(request, target_user):
    employee = getattr(target_user, "employee_profile", None)
    system_url = "https://alyaman-institute.com"
    password_value = (request.GET.get("password") or request.POST.get("password") or "").strip()
    return {
        "manual_target_user": target_user,
        "manual_target_username": target_user.username,
        "manual_target_name": target_user.get_full_name() or target_user.username,
        "manual_target_position": employee.get_position_display() if employee else "مستخدم نظام",
        "manual_target_phone": getattr(employee, "phone_number", "") or "غير محدد",
        "manual_target_email": target_user.email or "غير محدد",
        "manual_target_password": password_value or "غير متاح في النظام",
        "manual_target_qr": _qr_data_uri(system_url),
        "manual_target_system_url": system_url,
        "manual_target_system_code": "ALYAMAN-INSTITUTE",
    }


def _build_manual_error_pages():
    error_visuals = {
        "خطأ عدم الصلاحية": static("img/manual-center/error-permission-screen.svg"),
        "انتهاء الجلسة أو تسجيل الخروج التلقائي": static("img/manual-center/error-session-screen.svg"),
        "فشل التحقق من الحقول": static("img/manual-center/error-validation-screen.svg"),
        "العنصر غير موجود أو تم حذفه": static("img/manual-center/error-missing-screen.svg"),
        "تعارض أو تكرار بيانات": static("img/manual-center/error-conflict-screen.svg"),
        "فشل الشبكة أو بطء التحميل": static("img/manual-center/error-network-screen.svg"),
        "فشل الطباعة أو التصدير": static("img/manual-center/error-print-screen.svg"),
        "خطأ داخلي غير متوقع": static("img/manual-center/error-internal-screen.svg"),
    }
    pages = []
    for item in USER_MANUAL_ERRORS:
        screenshot_path = error_visuals.get(item["title"], static("img/manual-center/error-internal-screen.svg"))
        pages.append(
            {
                "title": item["title"],
                "group": "الأخطاء والتصرف الصحيح",
                "goal": "هذه الصفحة تشرح هذا الخطأ بطريقة تشغيلية: متى يظهر، كيف تكتشف سببه، وما هو التصرف الصحيح قبل تصعيده للدعم.",
                "used_by": "كل المستخدمين بحسب الصلاحيات",
                "path": "قد يظهر في أكثر من صفحة حسب نوع العملية",
                "screenshot": {
                    "title": item["title"],
                    "path": screenshot_path,
                    "caption": "لقطة مرجعية لهذا النوع من رسائل الخطأ داخل النظام حتى تتعرف على شكله العام قبل التعامل معه.",
                },
                "buttons": [
                    {
                        "label": "متى يظهر هذا الخطأ",
                        "location": "أثناء تنفيذ العملية الحالية أو عند فتح صفحة لا تستوفي الشروط المطلوبة.",
                        "used_by": "أي مستخدم قد يمر بنفس الحالة.",
                        "when": "فور ظهور الرسالة أو فشل الحفظ أو إعادة التوجيه غير المتوقعة.",
                        "purpose": item["when"],
                        "result": "تفهم سبب ظهور الخطأ قبل إعادة المحاولة بشكل عشوائي.",
                    },
                    {
                        "label": "التحقق الأولي",
                        "location": "في نفس الصفحة وقبل تكرار العملية.",
                        "used_by": "المستخدم الذي ظهرت له المشكلة.",
                        "when": "مباشرة بعد ظهور الخطأ.",
                        "purpose": "راجع الحقول، الصلاحيات، السجل المستهدف، والاتصال قبل أي إعادة تنفيذ.",
                        "result": "تحدد بسرعة هل المشكلة من البيانات أو الصلاحيات أو الشبكة أو من السجل نفسه.",
                    },
                    {
                        "label": "طريقة التصرف الصحيحة",
                        "location": "الخطوة التالية بعد فهم السبب.",
                        "used_by": "صاحب العملية الحالية.",
                        "when": "بعد التحقق الأولي مباشرة.",
                        "purpose": item["action"],
                        "result": "تعالج الخطأ بالطريقة الصحيحة أو تمنع تكراره عند المتابعة.",
                    },
                    {
                        "label": "متى ترفع للدعم",
                        "location": "بعد فشل المعالجة المباشرة أو تكرر الخطأ.",
                        "used_by": "أي مستخدم لا يستطيع إكمال العمل بعد المحاولة الصحيحة.",
                        "when": "إذا تكرر الخطأ بعد إعادة التنفيذ مرة واحدة فقط.",
                        "purpose": "جهّز اسم الصفحة واسم العملية ووقت الخطأ ثم ارفعها للدعم أو للإدارة التقنية.",
                        "result": "يصل البلاغ واضحًا وقابلًا للمعالجة السريعة دون ضياع التفاصيل.",
                    },
                ],
            }
        )
    return pages


def _build_user_handbook_toc(manual_workflows, manual_screens, manual_error_pages):
    entries = []
    page_number = 1
    entries.append({"title": "بطاقة الوصول وبيانات المستخدم", "page": page_number, "kind": "وصول"})
    page_number += 1
    entries.append({"title": "فهرس الدفتر", "page": page_number, "kind": "فهرس"})
    page_number += 1
    for workflow in manual_workflows:
        entries.append({"title": workflow["title"], "page": page_number, "kind": "مرحلة"})
        page_number += 1
    for screen in manual_screens:
        entries.append({"title": screen["title"], "page": page_number, "kind": screen["group"]})
        page_number += 1
    for item in manual_error_pages:
        entries.append({"title": item["title"], "page": page_number, "kind": "خطأ"})
        page_number += 1
    return entries


class ManualsHomeView(LoginRequiredMixin, TemplateView):
    template_name = "manuals/home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            build_manuals_context(
                query=(self.request.GET.get("q") or "").strip().lower(),
                selected_group=(self.request.GET.get("group") or "").strip(),
            )
        )
        context.update(_build_closing_page_context(self.request))
        return context


class ManualsHandbookView(LoginRequiredMixin, TemplateView):
    template_name = "manuals/handbook.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            build_manuals_context(
                query=(self.request.GET.get("q") or "").strip().lower(),
                selected_group=(self.request.GET.get("group") or "").strip(),
            )
        )
        context.update(_build_closing_page_context(self.request))
        return context


class ManualsUserGuideSelectView(LoginRequiredMixin, TemplateView):
    template_name = "manuals/user_select.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        selected_user, users = _selected_manual_user(self.request)
        context["manual_target_users"] = users
        context["manual_selected_user"] = selected_user
        context["manual_selected_password"] = (self.request.GET.get("password") or "").strip()
        return context


class ManualsUserHandbookView(LoginRequiredMixin, TemplateView):
    template_name = "manuals/user_handbook.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        target_user, users = _selected_manual_user(self.request)
        context["manual_target_users"] = users
        context["manual_selected_user"] = target_user
        context.update(
            build_user_manual_context(
                target_user,
                query=(self.request.GET.get("q") or "").strip().lower(),
                selected_group=(self.request.GET.get("group") or "").strip(),
            )
        )
        context.update(_build_user_manual_identity_context(self.request, target_user))
        context["manual_error_pages"] = _build_manual_error_pages()
        context["manual_toc_entries"] = _build_user_handbook_toc(
            context["manual_workflows"],
            context["manual_screens"],
            context["manual_error_pages"],
        )
        context.update(_build_closing_page_context(self.request))
        return context


class ManualsMarkdownDownloadView(LoginRequiredMixin, TemplateView):
    def get(self, request, *args, **kwargs):
        file_path = Path("docs/user-guide.md")
        return FileResponse(
            file_path.open("rb"),
            as_attachment=True,
            filename="user-guide.md",
            content_type="text/markdown; charset=utf-8",
        )
