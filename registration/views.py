from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.models import User
from django.core import signing
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, DetailView, TemplateView, UpdateView

from .forms import PasswordResetConfirmForm, PasswordResetRequestForm, UserProfileForm
from .models import PasswordChangeHistory, PasswordResetRequest, UserProfile
from .services import (
    build_whatsapp_send_url,
    load_signed_reset_action_token,
    send_reset_request_approval_email,
)


class registerview(CreateView):
    template_name = 'registration/signup.html'
    model = User
    form_class = UserCreationForm
    success_url = reverse_lazy('login')


class ProfileView(LoginRequiredMixin, DetailView):
    model = UserProfile
    template_name = 'registration/profile.html'
    context_object_name = 'profile'

    def get_object(self):
        profile, _ = UserProfile.objects.get_or_create(user=self.request.user)
        return profile

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['optimized_picture'] = self.object.get_optimized_picture_url()
        return context


class ProfileUpdateView(LoginRequiredMixin, UpdateView):
    model = UserProfile
    form_class = UserProfileForm
    template_name = 'registration/profile_edit.html'
    success_url = reverse_lazy('registration:profile')

    def get_object(self):
        profile, _ = UserProfile.objects.get_or_create(user=self.request.user)
        return profile


def process_reset_request_action(reset_request, action, actor=None, via_email=False):
    if action == 'reject':
        if reset_request.is_approved:
            return False, 'لا يمكن رفض طلب تمت الموافقة عليه مسبقاً.', ''
        reset_request.delete()
        return True, 'تم رفض طلب إعادة ضبط كلمة المرور.', ''

    if action != 'approve':
        return False, 'الإجراء المطلوب غير معروف.', ''

    if reset_request.is_approved:
        try:
            whatsapp_url = build_whatsapp_send_url(reset_request)
        except Exception:
            whatsapp_url = ''
        return True, f'الطلب موافق عليه مسبقاً، والكود الحالي هو: {reset_request.code}', whatsapp_url

    reset_request.is_approved = True
    reset_request.approved_at = timezone.now()
    reset_request.approved_by = actor
    reset_request.whatsapp_delivery_status = 'ready_for_manual_send'
    if via_email:
        reset_request.approved_via_email_at = timezone.now()
    reset_request.save()

    try:
        whatsapp_url = build_whatsapp_send_url(reset_request)
        reset_request.last_notification_error = ''
        reset_request.save(update_fields=['last_notification_error'])
        return True, f'تمت الموافقة على الطلب وإنشاء الكود {reset_request.code}. افتح رابط واتساب الجاهز لإرساله من رقمك.', whatsapp_url
    except Exception as exc:
        reset_request.whatsapp_delivery_status = 'phone_missing'
        reset_request.last_notification_error = str(exc)
        reset_request.save(update_fields=['whatsapp_delivery_status', 'last_notification_error'])
        return True, f'تمت الموافقة على الطلب وإنشاء الكود {reset_request.code} لكن تعذر تجهيز رابط واتساب: {exc}', ''


class PasswordResetRequestView(LoginRequiredMixin, TemplateView):
    template_name = 'registration/password_reset_request.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = PasswordResetRequestForm()
        context['user_requests'] = PasswordResetRequest.objects.filter(user=self.request.user).order_by('-created_at')[:5]
        return context

    def post(self, request, *args, **kwargs):
        form = PasswordResetRequestForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {'form': form, 'user_requests': self.get_context_data()['user_requests']})

        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        whatsapp_phone = (profile.phone or '').strip()
        if not whatsapp_phone:
            form.add_error(None, 'لا يمكن إرسال الكود عبر واتساب قبل إضافة رقم الهاتف في ملفك الشخصي.')
            return render(request, self.template_name, {'form': form, 'user_requests': self.get_context_data()['user_requests']})

        reset_request = PasswordResetRequest.objects.create(
            user=request.user,
            reason=form.cleaned_data['reason'],
            whatsapp_phone=whatsapp_phone,
        )

        try:
            send_reset_request_approval_email(reset_request, request)
            messages.success(request, 'تم إرسال الطلب، ووصل بريد موافقة إلى الإدارة. بعد الموافقة سيصل الكود إلى واتساب المستخدم.')
        except Exception as exc:
            reset_request.last_notification_error = str(exc)
            reset_request.save(update_fields=['last_notification_error'])
            messages.warning(request, f'تم حفظ الطلب لكن فشل إرسال بريد الموافقة: {exc}')

        return redirect('registration:profile')


class SuperUserPasswordResetView(UserPassesTestMixin, TemplateView):
    template_name = 'registration/superuser_password_reset.html'

    def test_func(self):
        return self.request.user.is_superuser

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['pending_requests'] = PasswordResetRequest.objects.filter(is_approved=False).select_related('user').order_by('created_at')
        context['approved_requests'] = PasswordResetRequest.objects.filter(
            is_approved=True,
            is_used=False,
            expires_at__gt=timezone.now(),
        ).select_related('user').order_by('-approved_at')
        context['used_requests'] = PasswordResetRequest.objects.filter(is_used=True).select_related('user').order_by('-created_at')[:10]
        context['password_history'] = PasswordChangeHistory.objects.select_related('user', 'changed_by', 'reset_request').order_by('-changed_at')[:20]
        return context

    def post(self, request, *args, **kwargs):
        request_id = request.POST.get('request_id')
        action = request.POST.get('action')
        if not request_id or not action:
            messages.error(request, 'بيانات الطلب غير مكتملة.')
            return redirect('registration:superuser_password_reset')

        try:
            reset_request = PasswordResetRequest.objects.get(id=request_id)
        except PasswordResetRequest.DoesNotExist:
            messages.error(request, 'الطلب غير موجود.')
            return redirect('registration:superuser_password_reset')

        ok, message, whatsapp_url = process_reset_request_action(reset_request, action, actor=request.user, via_email=False)
        if ok:
            messages.success(request, message)
        else:
            messages.error(request, message)
        context = self.get_context_data()
        context['manual_whatsapp_url'] = whatsapp_url
        context['manual_reset_request'] = reset_request if whatsapp_url else None
        if ok and whatsapp_url:
            context['manual_whatsapp_message'] = 'اضغط زر واتساب لإرسال الكود من رقمك.'
            return render(request, self.template_name, context)
        return redirect('registration:superuser_password_reset')


class PasswordResetEmailActionView(TemplateView):
    template_name = 'registration/password_reset_email_action_result.html'

    def get(self, request, *args, **kwargs):
        token = kwargs.get('token')
        title = 'نتيجة معالجة الطلب'
        try:
            payload = load_signed_reset_action_token(token)
            reset_request = PasswordResetRequest.objects.get(id=payload['request_id'])
            ok, message, whatsapp_url = process_reset_request_action(reset_request, payload['action'], actor=None, via_email=True)
            if not ok:
                title = 'تعذر تنفيذ الطلب'
                whatsapp_url = ''
        except signing.SignatureExpired:
            title = 'انتهت صلاحية الرابط'
            message = 'رابط الموافقة أو الرفض منتهي الصلاحية. اطلب إنشاء طلب جديد.'
            whatsapp_url = ''
        except signing.BadSignature:
            title = 'رابط غير صالح'
            message = 'تعذر التحقق من رابط الموافقة.'
            whatsapp_url = ''
        except PasswordResetRequest.DoesNotExist:
            title = 'الطلب غير موجود'
            message = 'هذا الطلب لم يعد موجوداً أو تمت معالجته مسبقاً.'
            whatsapp_url = ''
        return render(request, self.template_name, {'title': title, 'message': message, 'whatsapp_url': whatsapp_url})


class PasswordResetConfirmView(LoginRequiredMixin, TemplateView):
    template_name = 'registration/password_reset_confirm.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = PasswordResetConfirmForm()
        return context

    def post(self, request, *args, **kwargs):
        form = PasswordResetConfirmForm(request.POST)
        if form.is_valid():
            code = form.cleaned_data['code'].upper()
            new_password = form.cleaned_data['new_password']

            try:
                reset_request = PasswordResetRequest.objects.get(
                    code=code,
                    user=request.user,
                    is_approved=True,
                    is_used=False,
                    expires_at__gt=timezone.now(),
                )

                request.user.set_password(new_password)
                request.user.save()

                PasswordChangeHistory.create_password_history(
                    user=request.user,
                    new_password=new_password,
                    changed_by=request.user,
                    reset_request=reset_request,
                )

                reset_request.is_used = True
                reset_request.save(update_fields=['is_used'])

                login(request, request.user)
                messages.success(request, 'تم تعديل كلمة المرور بنجاح.')
                return redirect('registration:profile')
            except PasswordResetRequest.DoesNotExist:
                messages.error(request, 'الكود غير صالح أو منتهي الصلاحية.')

        return render(request, self.template_name, {'form': form})
