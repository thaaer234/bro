from django.db import models
from django.db.models import Q
from django.contrib.auth.hashers import make_password, check_password
from django.utils import timezone
import uuid
import jwt
from django.conf import settings
from datetime import datetime, timedelta
import base64
import json
import hmac
import hashlib
from rest_framework.exceptions import AuthenticationFailed
import logging

logger = logging.getLogger(__name__)

class MobileUser(models.Model):
    USER_TYPES = [
        ('parent', 'ولي أمر'),
        ('teacher', 'مدرس'),
        ('student', 'طالب'),
    ]
    
    # معلومات المصادقة
    username = models.CharField(max_length=100, unique=True, verbose_name='اسم المستخدم')
    password_hash = models.CharField(max_length=128, verbose_name='كلمة المرور المشفرة')
    phone_number = models.CharField(max_length=20, verbose_name='رقم الهاتف')
    user_type = models.CharField(max_length=10, choices=USER_TYPES, default='parent')
    
    # ربط بالمستخدمين الحاليين
    django_user = models.OneToOneField(
        'auth.User', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='mobile_profile'
    )
    student = models.ForeignKey(
        'students.Student', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='mobile_users'
    )
    teacher = models.ForeignKey(
        'employ.Teacher', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='mobile_users'
    )
    
    # معلومات إضافية
    device_token = models.CharField(max_length=255, blank=True, null=True)
    last_login = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    is_verified = models.BooleanField(default=False, verbose_name='تم التحقق')
    verification_code = models.CharField(max_length=6, blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'مستخدم الموبايل'
        verbose_name_plural = 'مستخدمي الموبايل'
    
    def __str__(self):
        return f"{self.username} - {self.get_user_type_display()}"
    
    def set_password(self, raw_password):
        """تشفير كلمة المرور"""
        self.password_hash = make_password(raw_password)
    
    def check_password(self, raw_password):
        """التحقق من كلمة المرور"""
        return check_password(raw_password, self.password_hash)
    
    def generate_jwt_token(self):
        """توليد JWT token"""
        exp_dt = datetime.utcnow() + timedelta(days=30)
        payload = {
            'user_id': self.id,
            'username': self.username,
            'user_type': self.user_type,
            'exp': int(exp_dt.timestamp()),
            'iat': int(datetime.utcnow().timestamp()),
            'jti': str(uuid.uuid4()),  # Unique token identifier
        }

        # استخدم PyJWT إن وُجد، وإلا fallback يدوي
        try:
            if hasattr(jwt, 'encode'):
                logger.info(f"Generating JWT for user {self.id} with secret key: {settings.SECRET_KEY[:10]}...")
                token = jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')
                # PyJWT 1.x يعيد bytes، 2.x يعيد str
                if isinstance(token, bytes):
                    token = token.decode('utf-8')
                logger.info(f"JWT generated successfully for user {self.id}")
                return token
        except Exception as e:
            logger.error(f"Error generating JWT: {e}")
            raise
        
        return self._manual_jwt_encode(payload, settings.SECRET_KEY)

    @staticmethod
    def _manual_jwt_encode(payload, secret):
        logger.warning("Using manual JWT encoding (fallback)")
        header = {'alg': 'HS256', 'typ': 'JWT'}
        def b64(data):
            return base64.urlsafe_b64encode(json.dumps(data, default=str).encode()).rstrip(b'=')
        signing_input = b'.'.join([b64(header), b64(payload)])
        signature = hmac.new(str(secret).encode(), signing_input, hashlib.sha256).digest()
        return b'.'.join([signing_input, base64.urlsafe_b64encode(signature).rstrip(b'=')]).decode()

    @staticmethod
    def _manual_jwt_decode(token, secret):
        try:
            header_b64, payload_b64, sig_b64 = token.split('.')
            signing_input = f"{header_b64}.{payload_b64}".encode()
            expected_sig = hmac.new(str(secret).encode(), signing_input, hashlib.sha256).digest()
            if base64.urlsafe_b64encode(expected_sig).rstrip(b'=') != sig_b64.encode():
                logger.error("JWT signature verification failed")
                return None
            padded_payload = payload_b64 + '=' * (-len(payload_b64) % 4)
            payload = json.loads(base64.urlsafe_b64decode(padded_payload).decode())
            # تحقق من انتهاء الصلاحية
            exp = payload.get('exp')
            if exp and datetime.utcfromtimestamp(exp) < datetime.utcnow():
                logger.warning(f"Token expired at {datetime.utcfromtimestamp(exp)}")
                return None
            return payload
        except Exception as e:
            logger.error(f"Manual JWT decode error: {e}")
            return None
    
    @classmethod
    def authenticate_with_name_phone(cls, name, phone):
        """المصادقة باستخدام الاسم ورقم الهاتف"""
        try:
            # 1. البحث عن طريق الطالب
            from students.models import Student
            students = Student.objects.filter(
                Q(full_name__icontains=name) |
                Q(student_number__icontains=name)
            )
            
            for student in students:
                # التحقق من أي رقم هاتف للطالب
                phone_fields = [
                    student.phone,
                    student.father_phone,
                    student.mother_phone,
                    student.home_phone
                ]
                
                for field in phone_fields:
                    if field and str(field).strip() and str(field) == phone:
                        # العثور على طالب متطابق
                        mobile_user = cls.objects.filter(student=student).first()
                        if not mobile_user:
                            # إنشاء مستخدم جديد
                            mobile_user = cls.objects.create(
                                username=f"parent_{student.id}_{phone}",
                                phone_number=phone,
                                user_type='parent',
                                student=student,
                                is_active=True,
                                is_verified=True
                            )
                            mobile_user.set_password(phone)
                            mobile_user.save()
                        return mobile_user
            
            # 2. البحث عن طريق المدرس
            from employ.models import Teacher
            teachers = Teacher.objects.filter(
                Q(full_name__icontains=name) |
                Q(phone_number__icontains=name)
            )
            
            for teacher in teachers:
                if teacher.phone_number and str(teacher.phone_number).strip() == phone:
                    mobile_user = cls.objects.filter(teacher=teacher).first()
                    if not mobile_user:
                        mobile_user = cls.objects.create(
                            username=f"teacher_{teacher.id}_{phone}",
                            phone_number=phone,
                            user_type='teacher',
                            teacher=teacher,
                            is_active=True,
                            is_verified=True
                        )
                        mobile_user.set_password(phone)
                        mobile_user.save()
                    return mobile_user
            
            return None
            
        except Exception as e:
            logger.error(f"Auth error: {e}")
            return None
    
    @classmethod
    def verify_jwt_token(cls, token):
        """التحقق من JWT token - الإصدار المصحح"""
        logger.info(f"Starting JWT verification for token: {token[:30]}...")
        
        # تنظيف التوكن أولاً
        def _clean_token(token_val):
            if not token_val:
                return None
            
            token_str = str(token_val).strip()
            logger.debug(f"Raw token: {token_str}")
            
            # إزالة أي بادئات أو لواحق غير مرغوب فيها
            prefixes_to_remove = ["b'", 'b"', "'", '"', 'Bearer ', 'Token ', 'bearer ', 'token ']
            for prefix in prefixes_to_remove:
                if token_str.startswith(prefix):
                    token_str = token_str[len(prefix):]
                    logger.debug(f"Removed prefix '{prefix}', remaining: {token_str}")
            
            # إزالة أي أجزاء زائدة في النهاية
            if "'" in token_str and token_str.endswith("'"):
                token_str = token_str[:-1]
            if '"' in token_str and token_str.endswith('"'):
                token_str = token_str[:-1]
                
            cleaned = token_str.strip()
            logger.debug(f"Cleaned token: {cleaned[:30]}...")
            return cleaned
        
        try:
            # تنظيف التوكن الوارد
            clean_token = _clean_token(token)
            if not clean_token:
                logger.error("Token is empty after cleaning")
                raise AuthenticationFailed('Token is empty after cleaning')
            
            logger.info(f"🔐 Verifying cleaned JWT token: {clean_token[:30]}...")
            
            # التحقق من SECRET_KEY
            if not settings.SECRET_KEY:
                logger.error("SECRET_KEY is not set in settings")
                raise AuthenticationFailed('Server configuration error')
            
            logger.debug(f"Using SECRET_KEY: {settings.SECRET_KEY[:10]}...")
            
            # استخدام PyJWT للتحقق
            if hasattr(jwt, 'decode'):
                try:
                    # مهم: تحقق من أن التوكن يحتوي على 3 أجزاء
                    if clean_token.count('.') != 2:
                        logger.error(f"Invalid JWT format, expected 2 dots, got {clean_token.count('.')}")
                        raise AuthenticationFailed('Invalid token format')
                    
                    # اختبار أولاً بدون التحقق من الصلاحية للتصحيح
                    try:
                        payload_unverified = jwt.decode(clean_token, options={"verify_signature": False})
                        logger.info(f"Token payload (unverified): {payload_unverified}")
                    except Exception as e:
                        logger.warning(f"Could not decode token even without verification: {e}")
                    
                    # الآن التحقق الكامل
                    payload = jwt.decode(
                        clean_token, 
                        settings.SECRET_KEY, 
                        algorithms=['HS256'],
                        options={'verify_exp': True}
                    )
                    
                    logger.info(f"✅ JWT decoded successfully. Payload: {payload}")
                    
                    # التحقق من الحقول المطلوبة
                    user_id = payload.get('user_id')
                    if not user_id:
                        logger.error("No user_id in token payload")
                        raise AuthenticationFailed('No user_id in token')
                    
                    username = payload.get('username')
                    exp = payload.get('exp')
                    
                    logger.info(f"Token details - user_id: {user_id}, username: {username}, exp: {exp}")
                    
                    # الحصول على المستخدم
                    try:
                        user = cls.objects.get(id=user_id, is_active=True)
                        logger.info(f"✅ User found: {user.username} (ID: {user.id}, type: {user.user_type})")
                        return user
                    except cls.DoesNotExist:
                        logger.error(f"❌ MobileUser not found for id: {user_id}")
                        raise AuthenticationFailed('MobileUser not found or inactive')
                    
                except jwt.ExpiredSignatureError:
                    logger.warning("❌ Token expired")
                    raise AuthenticationFailed('Token expired, please login again')
                except jwt.InvalidSignatureError:
                    logger.error("❌ Invalid token signature")
                    raise AuthenticationFailed('Token signature is invalid')
                except jwt.InvalidTokenError as e:
                    logger.error(f"❌ Invalid token error: {e}")
                    raise AuthenticationFailed(f'Token is invalid: {str(e)}')
                except Exception as e:
                    logger.error(f"❌ JWT decode error: {e}")
                    raise AuthenticationFailed(f'JWT decode failed: {str(e)}')
            else:
                # Fallback to manual decode
                logger.warning("⚠️ Using manual JWT decode (fallback)")
                payload = cls._manual_jwt_decode(clean_token, settings.SECRET_KEY)
                if not payload:
                    logger.error("Manual JWT decode failed")
                    raise AuthenticationFailed('Manual JWT decode failed')
                
                user_id = payload.get('user_id')
                if not user_id:
                    raise AuthenticationFailed('No user_id in token')
                
                user = cls.objects.get(id=user_id, is_active=True)
                logger.info(f"✅ User found via manual decode: {user.username}")
                return user
                
        except AuthenticationFailed:
            raise  # إعادة رمي الخطأ
        except Exception as e:
            logger.error(f"❌ Unexpected error in verify_jwt_token: {e}", exc_info=True)
            raise AuthenticationFailed(f'Authentication failed: {str(e)}')
    
    def login(self):
        """تسجيل الدخول"""
        self.last_login = timezone.now()
        self.save()
        return self.generate_jwt_token()
    
    @classmethod
    def authenticate(cls, identifier, password):
        """المصادقة باستخدام أي معرف"""
        try:
            # 1. البحث برقم الهاتف
            user = cls.objects.filter(phone_number=identifier, is_active=True).first()
            if user and user.check_password(password):
                return user
            
            # 2. البحث باسم المستخدم
            user = cls.objects.filter(username=identifier, is_active=True).first()
            if user and user.check_password(password):
                return user
            
            # 3. البحث عن طريق الطالب
            from students.models import Student
            student = Student.objects.filter(full_name__iexact=identifier).first()
            if student:
                user = cls.objects.filter(student=student, is_active=True).first()
                if user and user.check_password(password):
                    return user
            
            # 4. البحث عن طريق المدرس
            from employ.models import Teacher
            teacher = Teacher.objects.filter(full_name__iexact=identifier).first()
            if teacher:
                user = cls.objects.filter(teacher=teacher, is_active=True).first()
                if user and user.check_password(password):
                    return user
                
        except Exception as e:
            logger.error(f"Authentication error: {e}")
        
        return None

class EmergencyAlert(models.Model):
    """تنبيهات الطوارئ"""
    ALERT_TYPES = [
        ('emergency', 'حالة طارئة'),
        ('medical', 'طبي'),
        ('security', 'أمني'),
        ('general', 'عام'),
    ]
    
    user = models.ForeignKey(
        MobileUser, 
        on_delete=models.CASCADE, 
        related_name='alerts',
        verbose_name='المستخدم'
    )
    alert_type = models.CharField(max_length=20, choices=ALERT_TYPES, default='emergency')
    message = models.TextField(verbose_name='الرسالة')
    location = models.CharField(max_length=255, blank=True, null=True, verbose_name='الموقع')
    latitude = models.FloatField(blank=True, null=True, verbose_name='خط العرض')
    longitude = models.FloatField(blank=True, null=True, verbose_name='خط الطول')
    
    # حالة التنبيه
    STATUS_CHOICES = [
        ('pending', 'معلق'),
        ('active', 'نشط'),
        ('resolved', 'تم الحل'),
        ('cancelled', 'ملغي'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # رد الإدارة (اختياري)
    admin_response = models.TextField(blank=True, null=True, verbose_name='رد الإدارة')
    responded_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='تم الرد بواسطة'
    )
    
    # معلومات الوقت
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    responded_at = models.DateTimeField(blank=True, null=True)
    
    class Meta:
        verbose_name = 'تنبيه طوارئ'
        verbose_name_plural = 'تنبيهات الطوارئ'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.get_alert_type_display()} - {self.user.username} ({self.status})"
    
    def mark_as_resolved(self, response=None, responder=None):
        """تحديد التنبيه على أنه تم حله"""
        self.status = 'resolved'
        self.admin_response = response
        self.responded_by = responder
        self.responded_at = timezone.now()
        self.save()

class Announcement(models.Model):
    """إعلانات المدرسة"""
    TARGET_AUDIENCE = [
        ('all', 'الجميع'),
        ('parents', 'أولياء الأمور'),
        ('students', 'الطلاب'),
        ('teachers', 'المعلمين'),
        ('specific_class', 'صف محدد'),
    ]
    
    title = models.CharField(max_length=200, verbose_name='العنوان')
    content = models.TextField(verbose_name='المحتوى')
    target_audience = models.CharField(max_length=20, choices=TARGET_AUDIENCE, default='all')
    
    # ربط بالصف (إذا كان محدداً)
    classroom = models.ForeignKey(
        'classroom.Classroom',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='الصف'
    )
    
    # مرفقات (اختياري)
    attachment = models.FileField(upload_to='announcements/', blank=True, null=True, verbose_name='مرفق')
    
    # معلومات النشر
    created_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        verbose_name='أنشأ بواسطة'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    publish_date = models.DateTimeField(default=timezone.now, verbose_name='تاريخ النشر')
    expiration_date = models.DateTimeField(blank=True, null=True, verbose_name='تاريخ الانتهاء')
    
    # حالة الإعلان
    is_active = models.BooleanField(default=True, verbose_name='نشط')
    is_important = models.BooleanField(default=False, verbose_name='مهم')
    is_published = models.BooleanField(default=True, verbose_name='منشور')
    
    class Meta:
        verbose_name = 'إعلان'
        verbose_name_plural = 'الإعلانات'
        ordering = ['-publish_date']
    
    def __str__(self):
        return self.title
    
    @property
    def is_expired(self):
        """التحقق من انتهاء صلاحية الإعلان"""
        if self.expiration_date:
            return timezone.now() > self.expiration_date
        return False
    
    def save(self, *args, **kwargs):
        """تحديث حالة النشاط"""
        if self.is_expired:
            self.is_active = False
        super().save(*args, **kwargs)