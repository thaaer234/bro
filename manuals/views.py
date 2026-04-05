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
                        "purpose": "جهز اسم الصفحة واسم العملية ووقت الخطأ ثم ارفعها للدعم أو للإدارة التقنية.",
                        "result": "يصل البلاغ واضحًا وقابلًا للمعالجة السريعة دون ضياع التفاصيل.",
                    },
                ],
            }
        )
    return pages


def _chunk_items(items, size):
    if size <= 0:
        return [items]
    return [items[index:index + size] for index in range(0, len(items), size)]


def _continuation_title(title, chunk_index, chunk_total):
    return title


def _text_weight(value, base=1, ratio=220):
    text = str(value or "").strip()
    return base + max(0, len(text) // ratio)


def _chunk_weighted(items, max_weight, weight_fn):
    if max_weight <= 0:
        return [items]
    chunks = []
    current = []
    current_weight = 0
    for item in items:
        item_weight = max(1, weight_fn(item))
        if current and (current_weight + item_weight) > max_weight:
            chunks.append(current)
            current = [item]
            current_weight = item_weight
        else:
            current.append(item)
            current_weight += item_weight
    if current:
        chunks.append(current)
    return chunks


def _chunk_weighted_progressive(items, first_weight, continuation_weight, weight_fn):
    if not items:
        return []
    first_chunk = _chunk_weighted(items, first_weight, weight_fn)
    if len(first_chunk) <= 1:
        return first_chunk

    chunks = [first_chunk[0]]
    remaining = items[len(first_chunk[0]):]
    if remaining:
        chunks.extend(_chunk_weighted(remaining, continuation_weight, weight_fn))
    return chunks


def _workflow_step_weight(step):
    return _text_weight(step, base=3, ratio=140)


def _action_weight(item):
    return (
        _text_weight(item.get("label"), base=1, ratio=80)
        + _text_weight(item.get("location"), base=2, ratio=120)
        + _text_weight(item.get("used_by"), base=1, ratio=120)
        + _text_weight(item.get("when"), base=2, ratio=120)
        + _text_weight(item.get("purpose"), base=2, ratio=120)
        + _text_weight(item.get("result"), base=2, ratio=120)
    )


def _page_status_label(chunk_index, chunk_total):
    if chunk_total <= 1:
        return "مكتملة"
    if chunk_index == 1:
        return "بداية القسم"
    if chunk_index == chunk_total:
        return "ختام القسم"
    return "متابعة"


def _build_user_handbook_content_pages(manual_workflows, manual_screens, manual_error_pages):
    pages = []

    for workflow_index, workflow in enumerate(manual_workflows, start=1):
        step_chunks = _chunk_weighted_progressive(workflow["steps"], 26, 34, _workflow_step_weight)
        step_counter = 1
        for chunk_index, steps in enumerate(step_chunks, start=1):
            pages.append(
                {
                    "type": "workflow",
                    "title": _continuation_title(workflow["title"], chunk_index, len(step_chunks)),
                    "toc_title": workflow["title"],
                    "toc_kind": "مرحلة",
                    "toc_include": chunk_index == 1,
                    "eyebrow": f"مرحلة {workflow_index}",
                    "intro": workflow["intro"] if chunk_index == 1 else "استكمال الخطوات التنفيذية لنفس المرحلة مع الحفاظ على نفس التسلسل العملي.",
                    "image_title": workflow["screenshot"]["title"],
                    "image_path": workflow["screenshot"]["path"],
                    "image_caption": workflow["screenshot"]["caption"],
                    "show_image": chunk_index == 1,
                    "image_mode": "hero" if chunk_index == 1 and len(steps) <= 4 else "full",
                    "items": [
                        {"index": step_counter + offset, "text": step}
                        for offset, step in enumerate(steps)
                    ],
                    "continued": chunk_index > 1,
                }
            )
            step_counter += len(steps)

    for screen in manual_screens:
        button_chunks = _chunk_weighted_progressive(screen["buttons"], 64, 88, _action_weight)
        button_counter = 1
        for chunk_index, buttons in enumerate(button_chunks, start=1):
            pages.append(
                {
                    "type": "screen",
                    "title": _continuation_title(screen["title"], chunk_index, len(button_chunks)),
                    "toc_title": screen["title"],
                    "toc_kind": screen["group"],
                    "toc_include": chunk_index == 1,
                    "eyebrow": screen["group"],
                    "intro": screen["goal"] if chunk_index == 1 else "متابعة عناصر الشاشة نفسها بعد توزيع المحتوى على صفحة إضافية.",
                    "used_by": screen["used_by"],
                    "path": screen["path"],
                    "image_title": screen["screenshot"]["title"],
                    "image_path": screen["screenshot"]["path"],
                    "image_caption": screen["screenshot"]["caption"],
                    "show_image": chunk_index == 1,
                    "image_mode": "hero" if chunk_index == 1 and len(buttons) <= 4 else "full",
                    "items": [
                        {
                            **button,
                            "index": button_counter + offset,
                        }
                        for offset, button in enumerate(buttons)
                    ],
                    "continued": chunk_index > 1,
                }
            )
            button_counter += len(buttons)

    for error_page in manual_error_pages:
        button_chunks = _chunk_weighted_progressive(error_page["buttons"], 62, 86, _action_weight)
        button_counter = 1
        for chunk_index, buttons in enumerate(button_chunks, start=1):
            pages.append(
                {
                    "type": "error",
                    "title": _continuation_title(error_page["title"], chunk_index, len(button_chunks)),
                    "toc_title": error_page["title"],
                    "toc_kind": "خطأ",
                    "toc_include": chunk_index == 1,
                    "eyebrow": error_page["group"],
                    "intro": error_page["goal"] if chunk_index == 1 else "استكمال عناصر التعامل مع الخطأ نفسه في صفحة إضافية أوضح للطباعة.",
                    "used_by": error_page["used_by"],
                    "path": error_page["path"],
                    "image_title": error_page["screenshot"]["title"],
                    "image_path": error_page["screenshot"]["path"],
                    "image_caption": error_page["screenshot"]["caption"],
                    "show_image": chunk_index == 1,
                    "image_mode": "hero" if chunk_index == 1 and len(buttons) <= 4 else "full",
                    "items": [
                        {
                            **button,
                            "index": button_counter + offset,
                        }
                        for offset, button in enumerate(buttons)
                    ],
                    "continued": chunk_index > 1,
                }
            )
            button_counter += len(buttons)

    return pages


def _build_user_handbook_toc_pages(content_pages):
    toc_page_size = 22
    toc_entries = [
        {"title": "مقدمة الدليل", "kind": "تمهيد", "page": 1},
        {"title": "بطاقة المستخدم والوصول", "kind": "وصول", "page": 2},
        {"title": "الفهرس", "kind": "تنقل", "page": 3},
    ]
    content_entries = [{"title": "بطاقة الوصول وبيانات المستخدم", "kind": "وصول"}]
    content_entries.extend(
        {
            "title": page["toc_title"],
            "kind": page["toc_kind"],
        }
        for page in content_pages
        if page.get("toc_include")
    )

    toc_pages = _chunk_items(toc_entries, toc_page_size)
    while True:
        recalculated_entries = list(toc_entries)
        page_number = 3 + len(toc_pages)

        for page in content_pages:
            if page.get("toc_include"):
                recalculated_entries.append(
                    {
                        "title": page["toc_title"],
                        "kind": page["toc_kind"],
                        "page": page_number,
                    }
                )
            page_number += 1

        recalculated_entries.extend(
            [
                {"title": "ملاحظات وتشغيل آمن", "kind": "تنبيهات", "page": page_number},
                {"title": "الأسئلة الشائعة", "kind": "FAQ", "page": page_number + 1},
                {"title": "خاتمة الدليل", "kind": "ختام", "page": page_number + 2},
            ]
        )
        new_toc_pages = _chunk_items(recalculated_entries, toc_page_size)
        if len(new_toc_pages) == len(toc_pages):
            return [
                {
                    "entries": page_entries,
                    "toc_page_number": 3 + index,
                }
                for index, page_entries in enumerate(new_toc_pages)
            ]
        toc_pages = new_toc_pages


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
        context["manual_content_pages"] = _build_user_handbook_content_pages(
            context["manual_workflows"],
            context["manual_screens"],
            context["manual_error_pages"],
        )
        context["manual_toc_pages"] = _build_user_handbook_toc_pages(context["manual_content_pages"])
        context["manual_print_mode"] = False
        context["manual_print_url"] = self.request.build_absolute_uri()
        context.update(_build_closing_page_context(self.request))
        return context


class ManualsUserHandbookPrintView(ManualsUserHandbookView):
    template_name = "manuals/user_handbook_print.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["manual_print_mode"] = True
        context["manual_print_url"] = self.request.build_absolute_uri()
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
