from django.db import models
from django.contrib.auth.models import User
import uuid
from django.utils import timezone
from datetime import timedelta
import socket
import subprocess
import platform
import re
from django.urls import reverse

class ErrorLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    # معلومات الشبكة المتقدمة
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    mac_address = models.CharField(max_length=100, blank=True)
    hostname = models.CharField(max_length=255, blank=True)
    isp = models.CharField(max_length=255, blank=True)
    timezone = models.CharField(max_length=100, blank=True)
    
    # معلومات الجهاز المتقدمة
    user_agent = models.TextField(null=True, blank=True)
    device_type = models.CharField(max_length=100, blank=True)
    browser = models.CharField(max_length=100, blank=True)
    browser_version = models.CharField(max_length=50, blank=True)
    os = models.CharField(max_length=100, blank=True)
    os_version = models.CharField(max_length=50, blank=True)
    device_brand = models.CharField(max_length=100, blank=True)
    device_model = models.CharField(max_length=100, blank=True)
    is_bot = models.BooleanField(default=False)
    is_mobile = models.BooleanField(default=False)
    is_tablet = models.BooleanField(default=False)
    is_pc = models.BooleanField(default=False)
    
    # معلومات الخطأ
    path = models.CharField(max_length=500)
    method = models.CharField(max_length=10)
    error_code = models.IntegerField()
    error_message = models.TextField(blank=True)
    stack_trace = models.TextField(blank=True)
    attempted_admin = models.BooleanField(default=False)
    attempted_path = models.CharField(max_length=500, blank=True)
    
    # معلومات الموقع المتقدمة
    country = models.CharField(max_length=100, blank=True)
    country_code = models.CharField(max_length=10, blank=True)
    city = models.CharField(max_length=100, blank=True)
    region = models.CharField(max_length=100, blank=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    continent = models.CharField(max_length=50, blank=True)
    
    # معلومات الشبكة
    asn = models.CharField(max_length=100, blank=True)
    organization = models.CharField(max_length=255, blank=True)
    reverse_dns = models.CharField(max_length=255, blank=True)
    
    # معلومات إضافية
    resolved = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='resolved_errors')
    notes = models.TextField(blank=True)
    severity = models.CharField(max_length=20, choices=[
        ('low', 'منخفض'),
        ('medium', 'متوسط'),
        ('high', 'عالي'),
        ('critical', 'حرج')
    ], default='medium')
    
    # توقيتات متقدمة
    timestamp = models.DateTimeField(auto_now_add=True)
    response_time = models.FloatField(null=True, blank=True)  # وقت الاستجابة بالثواني
    
    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'سجل خطأ'
        verbose_name_plural = 'سجلات الأخطاء'
        indexes = [
            models.Index(fields=['error_code', 'timestamp']),
            models.Index(fields=['ip_address', 'timestamp']),
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['country', 'timestamp']),
            models.Index(fields=['severity', 'timestamp']),
        ]
    
    def __str__(self):
        return f"{self.error_code} - {self.path} - {self.timestamp.strftime('%Y-%m-%d %H:%M')}"
    
    def get_advanced_device_info(self):
        return {
            'device': self.device_type,
            'device_brand': self.device_brand,
            'device_model': self.device_model,
            'browser': f"{self.browser} {self.browser_version}",
            'os': f"{self.os} {self.os_version}",
            'ip': self.ip_address,
            'mac': self.mac_address,
            'hostname': self.hostname,
            'isp': self.isp,
            'is_bot': self.is_bot,
            'is_mobile': self.is_mobile,
            'is_tablet': self.is_tablet,
            'is_pc': self.is_pc
        }
    
    def get_location_info(self):
        return {
            'country': f"{self.country} ({self.country_code})",
            'city': self.city,
            'region': self.region,
            'continent': self.continent,
            'postal_code': self.postal_code,
            'coordinates': f"{self.latitude}, {self.longitude}",
            'timezone': self.timezone,
            'organization': self.organization,
            'asn': self.asn
        }
    
    def get_advanced_network_info(self):
        """جمع معلومات شبكة متقدمة"""
        try:
            if self.ip_address and self.ip_address not in ['127.0.0.1', '::1']:
                import requests
                response = requests.get(f'http://ip-api.com/json/{self.ip_address}?fields=66846719', timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    if data.get('status') == 'success':
                        return {
                            'asn': data.get('as', ''),
                            'isp': data.get('isp', ''),
                            'org': data.get('org', ''),
                            'reverse': data.get('reverse', ''),
                            'mobile': data.get('mobile', False),
                            'proxy': data.get('proxy', False),
                            'hosting': data.get('hosting', False),
                            'country_code': data.get('countryCode', ''),
                            'region_name': data.get('regionName', ''),
                        }
        except:
            pass
        return {}
    
    def detect_suspicious_activity(self):
        """كشف النشاط المشبوه"""
        suspicious_patterns = [
            r'union.*select', r'select.*from', r'insert.*into',
            r'drop.*table', r'script.*alert', r'\.\./', 
            r'etc/passwd', r'win\.ini', r'\.htaccess',
            r'\.\.\\', r'cmd\.exe', r'/bin/bash',
            r'<script', r'javascript:', r'onload=',
            r'alert\(', r'confirm\(', r'prompt\('
        ]
        
        request_data = f"{self.path} {self.error_message} {self.user_agent}".lower()
        for pattern in suspicious_patterns:
            if re.search(pattern, request_data, re.IGNORECASE):
                return True
        return False
    
    def get_threat_level(self):
        """تحديد مستوى التهديد"""
        if self.detect_suspicious_activity():
            return 'high'
        elif self.attempted_admin:
            return 'medium'
        else:
            return 'low'
    
    def mark_resolved(self, user, notes=""):
        self.resolved = True
        self.resolved_at = timezone.now()
        self.resolved_by = user
        self.notes = notes
        self.save()
    
    def is_recent(self):
        return self.timestamp > timezone.now() - timedelta(hours=24)

class SecurityAlert(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    alert_type = models.CharField(max_length=50, choices=[
        ('suspicious_login', 'تسجيل دخول مشبوه'),
        ('brute_force', 'هجوم القوة الغاشمة'),
        ('sql_injection', 'محاولة حقن SQL'),
        ('xss', 'هجوم XSS'),
        ('file_inclusion', 'محاولة تضمين ملف'),
        ('directory_traversal', 'محاولة تجاوز الدليل'),
        ('malware_detected', 'برنامج ضار مكتشف'),
        ('data_breach_attempt', 'محاولة اختراق بيانات'),
    ])
    ip_address = models.GenericIPAddressField()
    mac_address = models.CharField(max_length=100, blank=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    description = models.TextField()
    severity = models.CharField(max_length=20, choices=[
        ('low', 'منخفض'),
        ('medium', 'متوسط'),
        ('high', 'عالي'),
        ('critical', 'حرج')
    ], default='medium')
    
    # معلومات الموقع
    country = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100, blank=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    
    resolved = models.BooleanField(default=False)
    resolved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='resolved_alerts')
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_notes = models.TextField(blank=True)
    
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'تنبيه أمني'
        verbose_name_plural = 'التنبيهات الأمنية'
    
    def __str__(self):
        return f"{self.alert_type} - {self.ip_address} - {self.timestamp.strftime('%Y-%m-%d %H:%M')}"
    
    def get_network_info(self):
        """الحصول على معلومات الشبكة"""
        try:
            if self.ip_address not in ['127.0.0.1', '::1']:
                import requests
                response = requests.get(f'http://ip-api.com/json/{self.ip_address}', timeout=3)
                if response.status_code == 200:
                    data = response.json()
                    if data.get('status') == 'success':
                        return {
                            'isp': data.get('isp', ''),
                            'org': data.get('org', ''),
                            'as': data.get('as', ''),
                        }
        except:
            pass
        return {}

class ErrorAnalytics(models.Model):
    date = models.DateField(unique=True)
    total_errors = models.IntegerField(default=0)
    error_404_count = models.IntegerField(default=0)
    error_403_count = models.IntegerField(default=0)
    error_500_count = models.IntegerField(default=0)
    unique_visitors = models.IntegerField(default=0)
    unique_countries = models.IntegerField(default=0)
    most_common_path = models.CharField(max_length=500, blank=True)
    most_common_country = models.CharField(max_length=100, blank=True)
    average_response_time = models.FloatField(default=0)
    
    class Meta:
        ordering = ['-date']
        verbose_name = 'تحليل الأخطاء'
        verbose_name_plural = 'تحليلات الأخطاء'
    
    def __str__(self):
        return f"تحليل الأخطاء - {self.date}"

class UserTracking(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    ip_address = models.GenericIPAddressField()
    mac_address = models.CharField(max_length=100, blank=True)
    user_agent = models.TextField()
    location_data = models.JSONField(default=dict)
    device_info = models.JSONField(default=dict)
    first_seen = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(auto_now=True)
    session_count = models.IntegerField(default=1)
    
    class Meta:
        verbose_name = 'تتبع مستخدم'
        verbose_name_plural = 'تتبع المستخدمين'
        unique_together = ['user', 'ip_address']
    
    def __str__(self):
        return f"{self.user.username} - {self.ip_address}"
    
    def get_network_details(self):
        """الحصول على تفاصيل الشبكة"""
        try:
            if self.ip_address not in ['127.0.0.1', '::1']:
                import requests
                response = requests.get(f'http://ip-api.com/json/{self.ip_address}', timeout=3)
                if response.status_code == 200:
                    data = response.json()
                    if data.get('status') == 'success':
                        return {
                            'isp': data.get('isp', 'غير معروف'),
                            'organization': data.get('org', 'غير معروف'),
                            'asn': data.get('as', ''),
                            'country': data.get('country', ''),
                            'city': data.get('city', ''),
                            'timezone': data.get('timezone', ''),
                        }
        except:
            pass
        return {'isp': 'غير معروف', 'organization': 'غير معروف'}

class SecurityIncident(models.Model):
    SEVERITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('investigating', 'Investigating'),
        ('contained', 'Contained'),
        ('closed', 'Closed'),
    ]
    SOURCE_CHOICES = [
        ('middleware', 'Middleware'),
        ('frontend', 'Frontend Telemetry'),
        ('manual', 'Manual'),
        ('report', 'Report'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    detected_at = models.DateTimeField(default=timezone.now)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default='middleware')
    category = models.CharField(max_length=64)
    title = models.CharField(max_length=255)
    summary = models.TextField(blank=True)
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default='medium')
    threat_score = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    username_snapshot = models.CharField(max_length=150, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    fingerprint_hash = models.CharField(max_length=64, blank=True, db_index=True)
    user_agent = models.TextField(blank=True)
    method = models.CharField(max_length=10, blank=True)
    path = models.CharField(max_length=500, blank=True)
    referer = models.CharField(max_length=500, blank=True)
    request_id = models.CharField(max_length=64, blank=True, db_index=True)
    country = models.CharField(max_length=128, blank=True)
    city = models.CharField(max_length=128, blank=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    attack_tool = models.CharField(max_length=64, blank=True)
    is_known_bot = models.BooleanField(default=False)
    is_new_ip_for_user = models.BooleanField(default=False)
    is_blocked = models.BooleanField(default=False)
    html_snapshot = models.TextField(blank=True)
    request_headers = models.JSONField(default=dict, blank=True)
    request_query = models.JSONField(default=dict, blank=True)
    request_post = models.JSONField(default=dict, blank=True)
    forensic_context = models.JSONField(default=dict, blank=True)
    first_seen_at = models.DateTimeField(default=timezone.now)
    last_seen_at = models.DateTimeField(default=timezone.now)
    event_count = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ['-detected_at']
        indexes = [
            models.Index(fields=['status', 'severity', 'detected_at']),
            models.Index(fields=['ip_address', 'detected_at']),
            models.Index(fields=['category', 'detected_at']),
        ]

    def __str__(self):
        return f"{self.category} [{self.severity}] {self.ip_address or '-'}"

    def get_absolute_url(self):
        return reverse('security_dashboard') + f'?incident={self.pk}'


class SecurityArtifact(models.Model):
    ARTIFACT_CHOICES = [
        ('html', 'HTML Snapshot'),
        ('upload_metadata', 'Upload Metadata'),
        ('frontend_telemetry', 'Frontend Telemetry'),
        ('screenshot', 'Screenshot'),
        ('headers', 'Headers'),
        ('note', 'Note'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    incident = models.ForeignKey(SecurityIncident, on_delete=models.CASCADE, related_name='artifacts')
    artifact_type = models.CharField(max_length=32, choices=ARTIFACT_CHOICES)
    label = models.CharField(max_length=255)
    content = models.JSONField(default=dict, blank=True)
    text_content = models.TextField(blank=True)
    file = models.FileField(upload_to='security_artifacts/%Y/%m/%d/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.artifact_type} - {self.label}"


class SecurityBlocklist(models.Model):
    TARGET_CHOICES = [
        ('ip', 'IP Address'),
        ('fingerprint', 'Fingerprint'),
        ('user', 'User'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    target_type = models.CharField(max_length=20, choices=TARGET_CHOICES)
    value = models.CharField(max_length=255, db_index=True)
    reason = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_security_blocks')
    expires_at = models.DateTimeField(null=True, blank=True)
    last_match_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = ['target_type', 'value']

    def __str__(self):
        return f"{self.target_type}:{self.value}"

    @property
    def is_expired(self):
        return bool(self.expires_at and self.expires_at <= timezone.now())


class SecurityEvent(models.Model):
    incident = models.ForeignKey(SecurityIncident, on_delete=models.CASCADE, related_name='events', null=True, blank=True)
    event_type = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    fingerprint_hash = models.CharField(max_length=64, blank=True)
    path = models.CharField(max_length=500, blank=True)
    payload = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['event_type', 'created_at']),
            models.Index(fields=['ip_address', 'created_at']),
        ]

    def __str__(self):
        return f"{self.event_type} @ {self.created_at:%Y-%m-%d %H:%M}"


class SecurityBranding(models.Model):
    brand_name = models.CharField(max_length=255, default='مركز الأمن - معهد اليمان')
    brand_short = models.CharField(max_length=120, default='مركز الأمن')
    sender_name = models.CharField(max_length=255, default='مركز الأمن - معهد اليمان')
    support_email = models.EmailField(default='mhmadwerc8@gmail.com')
    alert_recipient = models.EmailField(default='thaaeralmasre98@gmail.com')
    dashboard_url = models.URLField(blank=True, default='http://127.0.0.1:8000/security/')
    logo_url = models.URLField(blank=True)
    subject_prefix = models.CharField(max_length=120, default='[مركز الأمن] ')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'هوية البريد الأمني'
        verbose_name_plural = 'هويات البريد الأمني'

    def __str__(self):
        return self.brand_name
