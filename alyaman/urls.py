# alyaman/urls.py
from django.contrib import admin
from django.urls import path, include, reverse
from django.contrib.auth.views import LoginView, LogoutView
from django.views.decorators.csrf import ensure_csrf_cookie
from django.utils.decorators import method_decorator
from django.shortcuts import redirect
from django.http import HttpResponseForbidden
from django.conf.urls import handler404, handler403, handler500
from django.conf import settings
from django.conf.urls.static import static
from core.views import secure_backup
from errors import security_views
from errors.security import capture_login_event
# from . import views
def root(request):
    if not request.user.is_authenticated:
        return redirect('login')
    for name in ('pages:welcome', 'students:student', 'accounts:dashboard'):
        try:
            reverse(name)
            return redirect(name)
        except Exception:
            continue
    return redirect('/sham/thaaer7426/')

# منع الوصول إلى admin العادي
def admin_block(request, path=None):
    return HttpResponseForbidden("الوصوع غير مسموح. الرجاء استخدام الرابط السري.")

# معالج 404 مخصص لجميع المسارات غير المعروفة
def catch_all_404(request, unknown_path=None):
    from django.http import HttpResponseNotFound
    from django.template import loader
    template = loader.get_template('errors/404.html')
    return HttpResponseNotFound(template.render({}, request))

# أضف في الأعلى
from errors.admin import admin_site

@method_decorator(ensure_csrf_cookie, name='dispatch')
class SafeLoginView(LoginView):
    def form_valid(self, form):
        response = super().form_valid(form)
        try:
            capture_login_event(
                self.request,
                success=True,
                username=form.get_user().get_username(),
            )
        except Exception:
            pass
        return response

    def form_invalid(self, form):
        try:
            username = self.request.POST.get('username', '')
            error_text = ' | '.join(form.errors.get('__all__', [])) if hasattr(form, 'errors') else ''
            capture_login_event(
                self.request,
                success=False,
                username=username,
                failure_reason=error_text or 'اسم المستخدم أو كلمة المرور غير صحيحة',
            )
        except Exception:
            pass
        return super().form_invalid(form)

urlpatterns = [
    path('login/', SafeLoginView.as_view(
            template_name='registration/login.html',
        redirect_authenticated_user=True
    ), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),

    # منع admin العادي تماماً
    path('admin/', admin_block),
    path('admin/<path:path>/', admin_block),
    
    # الرابط السري للإدارة
    # path('sham/thaaer7426/', admin.site.urls),
    path('sham/thaaer7426/', admin.site.urls, name='admin'),
    path('', root, name='root'),

    # التطبيقات الأخرى - يجب أن تكون قبل المسار العام
    path('pages/', include('pages.urls')),
    path('students/', include('students.urls')),
    path('employ/', include('employ.urls')),
    path('attendance/', include('attendance.urls')),
    path('exams/', include('exams.urls')),
    path('courses/', include('courses.urls')),
    path('classroom/', include('classroom.urls')),
    path('registration/', include('registration.urls')),
    path('announcements/', include('announcements.urls')),
    path('accounts/', include('accounts.urls')),
    path('errors/', include('errors.urls')),
    path('quick/', include('quick.urls')),
    # API endpoints (v1 and legacy)
    path('api/', include('api.urls')),   # legacy prefix
    path('api/v1/', include('api.urls')),
    path('mobile/', include('mobile.urls')),
    path('secure-backup/', secure_backup),
    path('security/', security_views.security_dashboard, name='security_dashboard'),
    path('security/api/telemetry/', security_views.security_telemetry_api, name='security_telemetry_api'),
    path('security/block/', security_views.block_indicator, name='security_block_indicator'),
    path('security/branding/', security_views.update_security_branding, name='security_update_branding'),
    path('security/unblock/<uuid:rule_id>/', security_views.unblock_indicator, name='security_unblock_indicator'),
    path('security/send-report/', security_views.send_security_report_now, name='security_send_report'),

    # مسار عام لأي كلمة - يجب أن يكون الأخير
    path('<path:unknown_path>/', catch_all_404),

]
# هذا السطر مهم جداً لخدمة ملفات الـ media والـ static محلياً
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
# معالجات الأخطاء
handler404 = 'errors.views.error_404_view'
handler403 = 'errors.views.error_403_view'
handler500 = 'errors.views.error_500_view'

