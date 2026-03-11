from django.contrib.auth.forms import UserCreationForm
from django.views.generic import CreateView, UpdateView, DetailView, TemplateView, ListView
from django.contrib.auth.models import User
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy
from django.contrib import messages
from .models import UserProfile, PasswordResetRequest, PasswordChangeHistory
from .forms import UserProfileForm, PasswordResetRequestForm, PasswordResetConfirmForm
from django.utils import timezone
from datetime import timedelta

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
        profile, created = UserProfile.objects.get_or_create(user=self.request.user)
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
        profile, created = UserProfile.objects.get_or_create(user=self.request.user)
        print(f"جلب البروفايل: {profile}, تم الإنشاء: {created}")
        return profile

    def form_valid(self, form):
        print("بدء حفظ النموذج...")
        print(f"الملف المرفوع: {form.cleaned_data.get('profile_picture')}")
        response = super().form_valid(form)
        print("تم حفظ النموذج بنجاح")
        return response

class PasswordResetRequestView(LoginRequiredMixin, TemplateView):
    template_name = 'registration/password_reset_request.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = PasswordResetRequestForm()
        context['user_requests'] = PasswordResetRequest.objects.filter(
            user=self.request.user
        ).order_by('-created_at')[:5]
        return context
    
    def post(self, request, *args, **kwargs):
        form = PasswordResetRequestForm(request.POST)
        if form.is_valid():
            PasswordResetRequest.objects.create(
                user=request.user,
                reason=form.cleaned_data['reason']
            )
            
            messages.success(request, 'تم إرسال طلب تعديل كلمة المرور بنجاح. سيتم مراجعته من قبل المشرف.')
            return redirect('registration:profile')
        
        return render(request, self.template_name, {'form': form})

class SuperUserPasswordResetView(UserPassesTestMixin, TemplateView):
    template_name = 'registration/superuser_password_reset.html'
    
    def test_func(self):
        return self.request.user.is_superuser

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # إضافة البيانات للقوائم المختلفة
        context['pending_requests'] = PasswordResetRequest.objects.filter(
            is_approved=False
        ).select_related('user').order_by('created_at')
        
        context['approved_requests'] = PasswordResetRequest.objects.filter(
            is_approved=True,
            is_used=False,
            expires_at__gt=timezone.now()
        ).select_related('user').order_by('-approved_at')
        
        context['used_requests'] = PasswordResetRequest.objects.filter(
            is_used=True
        ).select_related('user').order_by('-created_at')[:10]
        
        # إضافة سجل تغييرات كلمات المرور
        context['password_history'] = PasswordChangeHistory.objects.select_related(
            'user', 'changed_by', 'reset_request'
        ).order_by('-changed_at')[:20]
        
        return context

    def post(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            messages.error(request, 'ليس لديك صلاحية للقيام بهذا الإجراء')
            return redirect('registration:profile')
            
        request_id = request.POST.get('request_id')
        action = request.POST.get('action')
        
        print(f"بيانات POST: {dict(request.POST)}")  # لرؤية جميع البيانات
        print(f"طلب ID: {request_id}, إجراء: {action}")
        
        if not request_id:
            messages.error(request, 'بيانات غير مكتملة - لم يتم تحديد الطلب')
            return redirect('registration:superuser_password_reset')
        
        if not action:
            messages.error(request, 'بيانات غير مكتملة - لم يتم تحديد الإجراء')
            return redirect('registration:superuser_password_reset')
        
        try:
            reset_request = PasswordResetRequest.objects.get(id=request_id)
            
            if action == 'approve':
                reset_request.is_approved = True
                reset_request.approved_by = request.user
                reset_request.approved_at = timezone.now()
                # سيتم إنشاء الكود تلقائياً في دالة save
                reset_request.save()
                
                messages.success(request, f'تم الموافقة على الطلب وإنشاء الكود: {reset_request.code}')
                
            elif action == 'reject':
                reset_request.delete()
                messages.success(request, 'تم رفض الطلب وحذفه')
            else:
                messages.error(request, 'إجراء غير معروف')
                
        except PasswordResetRequest.DoesNotExist:
            messages.error(request, 'الطلب غير موجود')
        except Exception as e:
            messages.error(request, f'حدث خطأ: {str(e)}')
        
        return redirect('registration:superuser_password_reset')

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
                    expires_at__gt=timezone.now()
                )
                
                # حفظ كلمة المرور القديمة قبل التغيير
                old_password = request.user.password
                
                # تحديث كلمة المرور
                request.user.set_password(new_password)
                request.user.save()
                
                # إنشاء سجل تغيير كلمة المرور
                PasswordChangeHistory.create_password_history(
                    user=request.user,
                    new_password=new_password,
                    changed_by=request.user,  # المستخدم نفسه قام بالتغيير
                    reset_request=reset_request
                )
                
                # تحديث الطلب كمستخدم
                reset_request.is_used = True
                reset_request.save()
                
                # إعادة تسجيل الدخول
                from django.contrib.auth import login
                login(request, request.user)
                
                messages.success(request, 'تم تعديل كلمة المرور بنجاح')
                return redirect('registration:profile')
                
            except PasswordResetRequest.DoesNotExist:
                messages.error(request, 'الكود غير صالح أو منتهي الصلاحية')
        
        return render(request, self.template_name, {'form': form})