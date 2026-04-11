from django.http import Http404, HttpResponseForbidden, HttpResponseNotFound, JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.core.cache import cache
from django.conf import settings
from .models import ErrorLog, SecurityAlert, UserTracking
import user_agents
import requests
import time
import re
import socket
import subprocess
import platform
from datetime import datetime, timedelta
import json
import uuid

class AdvancedErrorTrackingMiddleware:
    """
    وسيط متقدم لتتبع وتسجيل جميع الأخطاء مع معلومات مفصلة
    """
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # بداية توقيت الاستجابة
        start_time = time.time()
        
        response = self.get_response(request)
        
        # حساب وقت الاستجابة
        response_time = time.time() - start_time
        
        # تسجيل الأخطاء
        if response.status_code >= 400:
            self.log_advanced_error(request, response.status_code, response_time)
        
        # تسجيل الاستجابات البطيئة
        elif response_time > 5:  # أكثر من 5 ثواني
            self.log_slow_response(request, response_time)
        
        # تحديث تتبع المستخدم للمستخدمين المسجلين
        if request.user.is_authenticated:
            self.update_user_tracking(request)
        
        return response
    
    def process_exception(self, request, exception):
        """
        معالجة الاستثناءات غير المتوقعة
        """
        import traceback
        
        error_message = str(exception)
        stack_trace = traceback.format_exc()
        
        if isinstance(exception, Http404):
            self.log_advanced_error(request, 404, 0, error_message, stack_trace)
        elif isinstance(exception, HttpResponseForbidden):
            self.log_advanced_error(request, 403, 0, error_message, stack_trace)
        else:
            self.log_advanced_error(request, 500, 0, error_message, stack_trace)
        
        return None
    
    def log_advanced_error(self, request, error_code, response_time=0, error_message="", stack_trace=""):
        """
        تسجيل خطأ متقدم مع معلومات مفصلة
        """
        try:
            user_agent_string = request.META.get('HTTP_USER_AGENT', '')
            ua = user_agents.parse(user_agent_string)
            
            # جمع معلومات متقدمة
            advanced_info = self.get_advanced_info(request, ua)
            location_info = self.get_advanced_location_info(request)
            network_info = self.get_network_info(request)
            
            # كشف التهديدات الأمنية
            security_threat = self.detect_advanced_security_threats(request, error_code)
            attempted_admin = self.detect_admin_attempt(request.path)
            
            # تحديد شدة الخطأ
            severity = self.determine_advanced_severity(error_code, attempted_admin, security_threat)
            
            # إنشاء سجل الخطأ المتقدم
            ErrorLog.objects.create(
                user=request.user if request.user.is_authenticated else None,
                ip_address=network_info.get('ip'),
                mac_address=network_info.get('mac', ''),
                hostname=network_info.get('hostname', ''),
                isp=location_info.get('isp', ''),
                timezone=location_info.get('timezone', ''),
                
                # معلومات الجهاز المتقدمة
                user_agent=user_agent_string,
                device_type=advanced_info.get('device_type', ''),
                browser=ua.browser.family,
                browser_version=ua.browser.version_string,
                os=ua.os.family,
                os_version=ua.os.version_string,
                device_brand=advanced_info.get('device_brand', ''),
                device_model=advanced_info.get('device_model', ''),
                is_bot=ua.is_bot,
                is_mobile=ua.is_mobile,
                is_tablet=ua.is_tablet,
                is_pc=ua.is_pc,
                
                # معلومات الخطأ
                path=request.path,
                method=request.method,
                error_code=error_code,
                error_message=error_message,
                stack_trace=stack_trace,
                attempted_admin=attempted_admin,
                attempted_path=request.path,
                
                # معلومات الموقع المتقدمة
                country=location_info.get('country', ''),
                country_code=location_info.get('countryCode', ''),
                city=location_info.get('city', ''),
                region=location_info.get('regionName', ''),
                latitude=location_info.get('lat'),
                longitude=location_info.get('lon'),
                postal_code=location_info.get('zip', ''),
                continent=location_info.get('continent', ''),
                
                # معلومات الشبكة
                asn=location_info.get('as', ''),
                organization=location_info.get('org', ''),
                reverse_dns=network_info.get('reverse_dns', ''),
                
                # معلومات إضافية
                severity=severity,
                response_time=response_time
            )
            
            # تحديث الإحصائيات
            self.update_advanced_analytics()
            
        except Exception as e:
            # تجنب حدوث أخطاء أثناء تسجيل الأخطاء
            print(f"Advanced error logging failed: {e}")
            pass
    
    def log_slow_response(self, request, response_time):
        """
        تسجيل الاستجابات البطيئة
        """
        try:
            ErrorLog.objects.create(
                user=request.user if request.user.is_authenticated else None,
                ip_address=self.get_client_ip(request),
                path=request.path,
                method=request.method,
                error_code=0,  # كود خاص للاستجابات البطيئة
                severity='medium',
                notes=f'استجابة بطيئة: {response_time:.2f} ثانية',
                response_time=response_time
            )
        except Exception as e:
            print(f"Slow response logging failed: {e}")
    
    def update_user_tracking(self, request):
        """
        تحديث تتبع المستخدم
        """
        try:
            ip = self.get_client_ip(request)
            user_agent_string = request.META.get('HTTP_USER_AGENT', '')
            location_info = self.get_advanced_location_info(request)
            network_info = self.get_network_info(request)
            
            tracking, created = UserTracking.objects.get_or_create(
                user=request.user,
                ip_address=ip,
                defaults={
                    'mac_address': network_info.get('mac', ''),
                    'user_agent': user_agent_string,
                    'location_data': location_info,
                    'device_info': self.get_advanced_info(request, user_agents.parse(user_agent_string)),
                }
            )
            
            if not created:
                tracking.last_seen = timezone.now()
                tracking.session_count += 1
                tracking.save()
                
        except Exception as e:
            print(f"User tracking failed: {e}")
    
    def get_advanced_info(self, request, ua):
        """
        جمع معلومات متقدمة عن الجهاز
        """
        info = {
            'device_type': self.get_device_type(ua),
            'device_brand': self.get_device_brand(ua),
            'device_model': self.get_device_model(ua),
        }
        return info
    
    def get_advanced_location_info(self, request):
        """
        الحصول على معلومات موقع متقدمة
        """
        monitoring = getattr(settings, 'SECURITY_MONITORING', {})
        if not monitoring.get('ENABLE_GEO_LOOKUPS', False):
            return {}
        try:
            ip = self.get_client_ip(request)
            
            if ip in ['127.0.0.1', 'localhost', '::1']:
                return {}
            
            # استخدام خدمة ip-api.com للحصول على معلومات مفصلة
            response = requests.get(f'http://ip-api.com/json/{ip}?fields=66846719', timeout=2)
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    return data
                    
        except Exception as e:
            print(f"Advanced location info failed: {e}")
        
        return {}
    
    def get_network_info(self, request):
        """
        جمع معلومات الشبكة المتقدمة
        """
        try:
            ip = self.get_client_ip(request)
            
            # الحصول على اسم المضيف
            try:
                hostname = socket.gethostbyaddr(ip)[0] if ip not in ['127.0.0.1', '::1'] else 'localhost'
            except:
                hostname = ''
            
            # الحصول على الـ MAC address (للاستخدام الداخلي فقط)
            mac_address = self.get_mac_address(ip)
            
            # الحصول على DNS العكسي
            try:
                reverse_dns = socket.gethostbyaddr(ip)[0] if ip not in ['127.0.0.1', '::1'] else 'localhost'
            except:
                reverse_dns = ''
            
            return {
                'ip': ip,
                'hostname': hostname,
                'mac': mac_address,
                'reverse_dns': reverse_dns
            }
            
        except Exception as e:
            print(f"Network info failed: {e}")
            return {'ip': self.get_client_ip(request)}
    
    def get_mac_address(self, ip):
        """
        محاولة الحصول على عنوان MAC (للاستخدام في الشبكات الداخلية)
        """
        try:
            if ip in ['127.0.0.1', '::1']:
                return '00:00:00:00:00:00'
            
            # هذا يعمل فقط في الشبكات المحلية
            if platform.system() == "Windows":
                result = subprocess.check_output(['arp', '-a', ip])
            else:
                result = subprocess.check_output(['arp', '-n', ip])
            
            mac_match = re.search(r'([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})', result.decode())
            if mac_match:
                return mac_match.group(0)
        except:
            pass
        
        return 'غير متوفر'
    
    def detect_admin_attempt(self, path):
        """
        كشف محاولات الدخول إلى لوحات التحكم
        """
        admin_keywords = [
            '/admin/', '/sham/', '/dashboard/', '/backend/', 
            '/administrator/', '/control/', '/manage/', '/panel/',
            '/cpanel/', '/webadmin/', '/phpmyadmin/', '/wp-admin/',
            '/administratie/', '/manager/', '/system/', '/config/',
            '/setup/', '/install/', '/debug/', '/test/'
        ]
        
        return any(keyword in path.lower() for keyword in admin_keywords)
    
    def detect_advanced_security_threats(self, request, error_code):
        """
        كشف الهجمات الأمنية المتقدمة
        """
        threat_detected = False
        request_data = self.get_request_data(request)
        
        # كشف هجمات SQL Injection
        if self.detect_sql_injection(request_data):
            self.create_security_alert(request, 'sql_injection', 'عالية')
            threat_detected = True
        
        # كشف هجمات XSS
        if self.detect_xss(request_data):
            self.create_security_alert(request, 'xss', 'عالية')
            threat_detected = True
        
        # كشف Directory Traversal
        if self.detect_directory_traversal(request_data):
            self.create_security_alert(request, 'directory_traversal', 'متوسطة')
            threat_detected = True
        
        # كشف هجمات القوة الغاشمة
        if self.detect_brute_force(request):
            self.create_security_alert(request, 'brute_force', 'عالية')
            threat_detected = True
        
        # كشف محاولات تضمين الملفات
        if self.detect_file_inclusion(request_data):
            self.create_security_alert(request, 'file_inclusion', 'عالية')
            threat_detected = True
        
        # كشف هجمات CSRF
        if self.detect_csrf(request):
            self.create_security_alert(request, 'csrf_attempt', 'عالية')
            threat_detected = True
        
        return threat_detected
    
    def detect_sql_injection(self, request_data):
        """
        كشف هجمات حقن SQL
        """
        sql_patterns = [
            r'union\s+select', r'select\s+\*\s+from', r'insert\s+into',
            r'drop\s+table', r'delete\s+from', r'update\s+\w+\s+set',
            r'or\s+1=1', r'or\s+1=2', r'exec\s*\(', r'xp_cmdshell',
            r';--', r'/\*', r'\*/', r'waitfor\s+delay'
        ]
        
        for pattern in sql_patterns:
            if re.search(pattern, request_data, re.IGNORECASE):
                return True
        return False
    
    def detect_xss(self, request_data):
        """
        كشف هجمات XSS
        """
        xss_patterns = [
            r'<script>', r'</script>', r'javascript:', r'onload=',
            r'onerror=', r'onclick=', r'alert\(', r'confirm\(',
            r'prompt\(', r'document\.cookie', r'window\.location',
            r'<iframe', r'</iframe>', r'<img src=', r'<svg onload'
        ]
        
        for pattern in xss_patterns:
            if re.search(pattern, request_data, re.IGNORECASE):
                return True
        return False
    
    def detect_directory_traversal(self, request_data):
        """
        كشف هجمات تجاوز الدليل
        """
        traversal_patterns = [
            r'\.\./', r'\.\.\\', r'etc/passwd', r'win\.ini',
            r'boot\.ini', r'\.htpasswd', r'\.htaccess',
            r'proc/self/environ', r'\.git/config'
        ]
        
        for pattern in traversal_patterns:
            if re.search(pattern, request_data, re.IGNORECASE):
                return True
        return False
    
    def detect_file_inclusion(self, request_data):
        """
        كشف محاولات تضمين الملفات
        """
        inclusion_patterns = [
            r'include\(', r'require\(', r'include_once\(', r'require_once\(',
            r'fopen\(', r'file_get_contents\(', r'readfile\(',
            r'\.php\?', r'\.asp\?', r'\.aspx\?', r'\.jsp\?'
        ]
        
        for pattern in inclusion_patterns:
            if re.search(pattern, request_data, re.IGNORECASE):
                return True
        return False
    
    def detect_csrf(self, request):
        """
        كشف محاولات CSRF
        """
        # تخطي فحص CSRF للـ API (تم تعطيله في الإعدادات)
        if request.path.startswith('/api/'):
            return False

        if request.method == 'POST':
            if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                referer = request.META.get('HTTP_REFERER', '')
                host = request.get_host()
                
                if referer and host not in referer:
                    return True
        return False
    
    def detect_brute_force(self, request):
        """
        كشف هجمات القوة الغاشمة على صفحات الدخول
        """
        if '/login/' in request.path or 'login' in request.path.lower():
            ip = self.get_client_ip(request)
            cache_key = f'login_attempts_{ip}'
            attempts = cache.get(cache_key, 0) + 1
            
            if attempts > 10:  # أكثر من 10 محاولة في 15 دقيقة
                cache.set(cache_key, attempts, 900)  # 15 دقيقة
                return True
            else:
                cache.set(cache_key, attempts, 900)
        
        return False
    
    def create_security_alert(self, request, alert_type, severity):
        """
        إنشاء تنبيه أمني
        """
        try:
            severity_map = {
                'منخفضة': 'low',
                'متوسطة': 'medium', 
                'عالية': 'high',
                'حرجة': 'critical'
            }
            
            alert_type_map = {
                'sql_injection': 'محاولة حقن SQL',
                'xss': 'هجوم XSS',
                'directory_traversal': 'محاولة تجاوز الدليل',
                'brute_force': 'هجوم القوة الغاشمة',
                'file_inclusion': 'محاولة تضمين ملف',
                'csrf_attempt': 'محاولة هجوم CSRF'
            }
            
            location_info = self.get_advanced_location_info(request)
            network_info = self.get_network_info(request)
            
            SecurityAlert.objects.create(
                alert_type=alert_type,
                ip_address=self.get_client_ip(request),
                mac_address=network_info.get('mac', ''),
                user=request.user if request.user.is_authenticated else None,
                description=f'{alert_type_map.get(alert_type, alert_type)} مكتشف من IP: {self.get_client_ip(request)}',
                severity=severity_map.get(severity, 'medium'),
                country=location_info.get('country', ''),
                city=location_info.get('city', ''),
                latitude=location_info.get('lat'),
                longitude=location_info.get('lon')
            )
        except Exception as e:
            print(f"Security alert creation failed: {e}")
    
    def get_request_data(self, request):
        """
        جمع جميع بيانات الطلب في سلسلة واحدة للفحص
        """
        data_parts = [
            request.path,
            str(request.GET),
            str(request.POST),
            request.META.get('HTTP_REFERER', ''),
            request.META.get('HTTP_USER_AGENT', '')
        ]
        
        return ' '.join(data_parts).lower()
    
    def determine_advanced_severity(self, error_code, attempted_admin, security_threat):
        """
        تحديد شدة الخطأ المتقدمة
        """
        if security_threat:
            return 'critical'
        elif attempted_admin:
            return 'high'
        elif error_code == 500:
            return 'high'
        elif error_code in [403, 404]:
            return 'medium'
        else:
            return 'low'
    
    def update_advanced_analytics(self):
        """
        تحديث الإحصائيات المتقدمة
        """
        try:
            from .models import ErrorAnalytics
            today = timezone.now().date()
            analytics, created = ErrorAnalytics.objects.get_or_create(date=today)
            
            today_errors = ErrorLog.objects.filter(timestamp__date=today)
            analytics.total_errors = today_errors.count()
            analytics.error_404_count = today_errors.filter(error_code=404).count()
            analytics.error_403_count = today_errors.filter(error_code=403).count()
            analytics.error_500_count = today_errors.filter(error_code=500).count()
            
            unique_ips = today_errors.values('ip_address').distinct().count()
            analytics.unique_visitors = unique_ips
            
            unique_countries = today_errors.filter(country__isnull=False).values('country').distinct().count()
            analytics.unique_countries = unique_countries
            
            # حساب متوسط وقت الاستجابة
            avg_response = today_errors.filter(response_time__isnull=False).aggregate(
                avg=models.Avg('response_time')
            )
            analytics.average_response_time = avg_response['avg'] or 0
            
            # المسار الأكثر طلباً
            from django.db.models import Count
            most_common = today_errors.values('path').annotate(count=Count('path')).order_by('-count').first()
            if most_common:
                analytics.most_common_path = most_common['path']
            
            # البلد الأكثر نشاطاً
            most_common_country = today_errors.filter(country__isnull=False).values('country').annotate(
                count=Count('country')
            ).order_by('-count').first()
            if most_common_country:
                analytics.most_common_country = most_common_country['country']
            
            analytics.save()
        except Exception as e:
            print(f"Advanced analytics update failed: {e}")
    
    def get_client_ip(self, request):
        """
        الحصول على IP العميل الحقيقي
        """
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def get_device_type(self, ua):
        """
        تحديد نوع الجهاز
        """
        if ua.is_mobile:
            return 'جوال'
        elif ua.is_tablet:
            return 'تابلت'
        elif ua.is_pc:
            return 'كمبيوتر'
        elif ua.is_bot:
            return 'بوت'
        else:
            return 'غير معروف'
    
    def get_device_brand(self, ua):
        """الحصول على ماركة الجهاز"""
        if ua.is_mobile:
            if 'iPhone' in ua.device.family:
                return 'Apple'
            elif 'Samsung' in ua.device.family:
                return 'Samsung'
            elif 'Huawei' in ua.device.family:
                return 'Huawei'
        return ua.device.brand or 'غير معروف'
    
    def get_device_model(self, ua):
        """الحصول على موديل الجهاز"""
        return ua.device.model or 'غير معروف'


class AdminProtectionMiddleware:
    """
    وسيط لحماية المسارات الإدارية
    """
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # المسارات المحظورة
        blocked_paths = [
            '/admin/', '/administrator/', '/backend/', 
            '/control/', '/manage/', '/panel/', '/wp-admin/',
            '/cpanel/', '/webadmin/', '/phpmyadmin/',
            '/administratie/', '/manager/', '/system/',
            '/config/', '/setup/', '/install/', '/debug/'
        ]
        
        # التحقق من المسار
        if any(request.path.startswith(path) for path in blocked_paths):
            # تسجيل محاولة الوصول
            self.log_admin_attempt(request)
            return self.get_admin_block_response(request)
        
        return self.get_response(request)
    
    def get_admin_block_response(self, request):
        """
        إرجاع استجابة منع الوصول
        """
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'error': 'الوصوع غير مسموح',
                'message': 'الرجاء استخدام الرابط السري للوصول إلى لوحة التحكم.'
            }, status=403)
        
        context = {
            'attempted_path': request.path,
            'client_ip': self.get_client_ip(request),
            'timestamp': timezone.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        return HttpResponseForbidden(
            render(request, 'errors/403.html', context)
        )
    
    def log_admin_attempt(self, request):
        """
        تسجيل محاولة الوصول إلى المسارات الإدارية
        """
        try:
            user_agent_string = request.META.get('HTTP_USER_AGENT', '')
            ua = user_agents.parse(user_agent_string)
            location_info = self.get_location_info(request)
            network_info = self.get_network_info(request)
            
            ErrorLog.objects.create(
                user=request.user if request.user.is_authenticated else None,
                ip_address=self.get_client_ip(request),
                mac_address=network_info.get('mac', ''),
                hostname=network_info.get('hostname', ''),
                user_agent=user_agent_string,
                device_type=self.get_device_type(ua),
                browser=ua.browser.family,
                browser_version=ua.browser.version_string,
                os=ua.os.family,
                os_version=ua.os.version_string,
                device_brand=self.get_device_brand(ua),
                device_model=self.get_device_model(ua),
                is_bot=ua.is_bot,
                is_mobile=ua.is_mobile,
                is_tablet=ua.is_tablet,
                is_pc=ua.is_pc,
                path=request.path,
                method=request.method,
                error_code=403,
                attempted_admin=True,
                attempted_path=request.path,
                country=location_info.get('country', ''),
                city=location_info.get('city', ''),
                latitude=location_info.get('lat'),
                longitude=location_info.get('lon'),
                severity='high'
            )
        except Exception as e:
            print(f"Admin attempt logging failed: {e}")
    
    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def get_device_type(self, ua):
        if ua.is_mobile:
            return 'جوال'
        elif ua.is_tablet:
            return 'تابلت'
        elif ua.is_pc:
            return 'كمبيوتر'
        elif ua.is_bot:
            return 'بوت'
        else:
            return 'غير معروف'
    
    def get_device_brand(self, ua):
        if ua.is_mobile:
            if 'iPhone' in ua.device.family:
                return 'Apple'
            elif 'Samsung' in ua.device.family:
                return 'Samsung'
            elif 'Huawei' in ua.device.family:
                return 'Huawei'
        return ua.device.brand or 'غير معروف'
    
    def get_device_model(self, ua):
        return ua.device.model or 'غير معروف'
    
    def get_location_info(self, request):
        try:
            ip = self.get_client_ip(request)
            if ip and ip not in ['127.0.0.1', 'localhost', '::1']:
                response = requests.get(f'http://ip-api.com/json/{ip}', timeout=3)
                if response.status_code == 200:
                    data = response.json()
                    if data.get('status') == 'success':
                        return {
                            'country': data.get('country', ''),
                            'city': data.get('city', ''),
                            'lat': data.get('lat'),
                            'lon': data.get('lon')
                        }
        except:
            pass
        return {}
    
    def get_network_info(self, request):
        try:
            ip = self.get_client_ip(request)
            return {'ip': ip, 'mac': '', 'hostname': ''}
        except:
            return {'ip': self.get_client_ip(request)}


class Universal404Middleware:
    """
    وسيط لتسجيل جميع أخطاء 404
    """
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        response = self.get_response(request)
        
        # إذا كان الرد 404، سجله
        if response.status_code == 404:
            self.log_404_error(request)
        
        return response
    
    def log_404_error(self, request):
        """
        تسجيل أخطاء 404
        """
        try:
            user_agent_string = request.META.get('HTTP_USER_AGENT', '')
            ua = user_agents.parse(user_agent_string)
            location_info = self.get_location_info(request)
            network_info = self.get_network_info(request)
            
            # تحديد إذا كانت محاولة دخول لوحة تحكم
            attempted_admin = any(keyword in request.path.lower() for keyword in [
                'admin', 'sham', 'dashboard', 'backend', 'administrator', 
                'control', 'manage', 'panel', 'cpanel', 'webadmin'
            ])
            
            ErrorLog.objects.create(
                user=request.user if request.user.is_authenticated else None,
                ip_address=self.get_client_ip(request),
                mac_address=network_info.get('mac', ''),
                hostname=network_info.get('hostname', ''),
                user_agent=user_agent_string,
                device_type=self.get_device_type(ua),
                browser=ua.browser.family,
                browser_version=ua.browser.version_string,
                os=ua.os.family,
                os_version=ua.os.version_string,
                device_brand=self.get_device_brand(ua),
                device_model=self.get_device_model(ua),
                is_bot=ua.is_bot,
                is_mobile=ua.is_mobile,
                is_tablet=ua.is_tablet,
                is_pc=ua.is_pc,
                path=request.path,
                method=request.method,
                error_code=404,
                attempted_admin=attempted_admin,
                attempted_path=request.path,
                country=location_info.get('country', ''),
                city=location_info.get('city', ''),
                latitude=location_info.get('lat'),
                longitude=location_info.get('lon'),
                severity='medium' if attempted_admin else 'low'
            )
        except Exception as e:
            print(f"404 logging failed: {e}")
    
    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def get_device_type(self, ua):
        if ua.is_mobile:
            return 'جوال'
        elif ua.is_tablet:
            return 'تابلت'
        elif ua.is_pc:
            return 'كمبيوتر'
        elif ua.is_bot:
            return 'بوت'
        else:
            return 'غير معروف'
    
    def get_device_brand(self, ua):
        if ua.is_mobile:
            if 'iPhone' in ua.device.family:
                return 'Apple'
            elif 'Samsung' in ua.device.family:
                return 'Samsung'
            elif 'Huawei' in ua.device.family:
                return 'Huawei'
        return ua.device.brand or 'غير معروف'
    
    def get_device_model(self, ua):
        return ua.device.model or 'غير معروف'
    
    def get_location_info(self, request):
        try:
            ip = self.get_client_ip(request)
            if ip and ip not in ['127.0.0.1', 'localhost', '::1']:
                response = requests.get(f'http://ip-api.com/json/{ip}', timeout=3)
                if response.status_code == 200:
                    data = response.json()
                    if data.get('status') == 'success':
                        return {
                            'country': data.get('country', ''),
                            'city': data.get('city', ''),
                            'lat': data.get('lat'),
                            'lon': data.get('lon')
                        }
        except:
            pass
        return {}
    
    def get_network_info(self, request):
        try:
            ip = self.get_client_ip(request)
            return {'ip': ip, 'mac': '', 'hostname': ''}
        except:
            return {'ip': self.get_client_ip(request)}


class RateLimitMiddleware:
    """
    وسيط للحد من الطلبات للوقاية من الهجمات
    """
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # التحقق من الحد الأقصى للطلبات
        if self.is_rate_limited(request):
            return self.get_rate_limit_response(request)
        
        response = self.get_response(request)
        return response
    
    def is_rate_limited(self, request):
        """
        التحقق إذا تجاوز العميل الحد الأقصى للطلبات
        """
        ip = self.get_client_ip(request)
        path = request.path
        
        # تجاهل بعض المسارات
        if any(path.startswith(p) for p in ['/static/', '/media/', '/favicon.ico']):
            return False
        
        # مفتاح التخزين المؤقت
        cache_key = f'rate_limit_{ip}_{path}'
        requests_count = cache.get(cache_key, 0)
        
        # الحد الأقصى: 100 طلب في الدقيقة
        if requests_count > 100:
            return True
        
        # زيادة العداد
        cache.set(cache_key, requests_count + 1, 60)  # 60 ثانية
        return False
    
    def get_rate_limit_response(self, request):
        """
        إرجاع استجابة تجاوز الحد الأقصى
        """
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'error': 'تم تجاوز الحد الأقصى للطلبات',
                'message': 'الرجاء المحاولة مرة أخرى بعد دقيقة.'
            }, status=429)
        
        context = {
            'message': 'تم تجاوز الحد الأقصى للطلبات. الرجاء المحاولة مرة أخرى بعد دقيقة.',
            'client_ip': self.get_client_ip(request),
            'retry_after': 60
        }
        
        return JsonResponse(context, status=429)
    
    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class SecurityHeadersMiddleware:
    """
    وسيط لإضافة رؤوس أمان إضافية
    """
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        response = self.get_response(request)
        
        # إضافة رؤوس الأمان
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['X-XSS-Protection'] = '1; mode=block'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        if request.is_secure():
            response['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        else:
            if 'Strict-Transport-Security' in response:
                del response['Strict-Transport-Security']
        
        # إضافة رأس Content Security Policy مبسط
        csp = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "script-src-elem 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com; "
            "style-src-elem 'self' 'unsafe-inline' https://cdnjs.cloudflare.com; "
            "img-src 'self' data: https:; "
            "font-src 'self' data: https://cdnjs.cloudflare.com;"
        )
        response['Content-Security-Policy'] = csp
        
        return response


class MaintenanceModeMiddleware:
    """
    وسيط لوضع الصيانة
    """
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # التحقق إذا كان وضع الصيانة مفعل
        if self.is_maintenance_mode(request):
            return self.get_maintenance_response(request)
        
        return self.get_response(request)
    
    def is_maintenance_mode(self, request):
        """
        التحقق إذا كان وضع الصيانة مفعل
        """
        # يمكن تفعيل هذا من خلال متغير بيئة أو إعداد في قاعدة البيانات
        maintenance_mode = cache.get('maintenance_mode', False)
        
        # استثناء المسارات المهمة
        excluded_paths = ['/admin/', '/sham/', '/login/', '/static/', '/media/']
        if any(request.path.startswith(path) for path in excluded_paths):
            return False
        
        return maintenance_mode
    
    def get_maintenance_response(self, request):
        """
        إرجاع استجابة وضع الصيانة
        """
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'error': 'الخدمة غير متاحة',
                'message': 'النظام قيد الصيانة حالياً. الرجاء المحاولة لاحقاً.'
            }, status=503)
        
        context = {
            'message': 'النظام قيد الصيانة حالياً',
            'estimated_time': '30 دقيقة',
            'contact_info': '00966500000000'
        }
        
        from django.shortcuts import render
        from django.http import HttpResponseServerError
        return HttpResponseServerError(
            render(request, 'errors/503.html', context)
        )
