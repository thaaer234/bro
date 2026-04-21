"""
Django settings for alyaman project.
"""

from pathlib import Path
import os
import sys

BASE_DIR = Path(__file__).resolve().parent.parent

# ==============================
# Security
# ==============================
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "django-insecure-change-me-in-production!")
BACKUP_KEY = os.getenv("BACKUP_KEY", "MY_SUPER_BACKUP_KEY_123")


def env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_int(name, default=0):
    value = os.getenv(name)
    if value is None or value == "":
        return default
    try:
        return int(value, 0)
    except (TypeError, ValueError):
        return default


def env_list(name, default=None):
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return list(default or [])
    return [item.strip() for item in value.split(",") if item.strip()]


RUNNING_LOCAL_SERVER = 'runserver' in sys.argv
DEBUG = env_bool("DJANGO_DEBUG", RUNNING_LOCAL_SERVER)

DEFAULT_ALLOWED_HOSTS = [
    'localhost',
    '127.0.0.1',
    '0.0.0.0',
    'alyaman-institute.com',
    'www.alyaman-institute.com',
    '187.124.151.249',
]
if DEBUG:
    DEFAULT_ALLOWED_HOSTS.extend([
        '.ngrok-free.dev',
    ])

DEFAULT_CSRF_TRUSTED_ORIGINS = [
    'http://alyaman-institute.com',
    'https://alyaman-institute.com',
    'http://www.alyaman-institute.com',
    'https://www.alyaman-institute.com',
    'http://187.124.151.249',
    'https://187.124.151.249',
    'http://*.ngrok-free.dev',
    'https://*.ngrok-free.dev',
]
if DEBUG:
    DEFAULT_CSRF_TRUSTED_ORIGINS.extend([
        'http://localhost:8000',
        'http://127.0.0.1:8000',
        'http://0.0.0.0:8000',
    ])

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", DEFAULT_ALLOWED_HOSTS)
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS", DEFAULT_CSRF_TRUSTED_ORIGINS)


# ==============================
# Applications
# ==============================
INSTALLED_APPS = [
    # Django defaults
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    
    # Third-party libraries
    'import_export',
    'rangefilter',
    'django_user_agents',
    'imagekit',
    
    # Project apps
    "pages.apps.PagesConfig",
    "sitemap.apps.SitemapConfig",
    "manuals.apps.ManualsConfig",
    "students",
    "employ",
    "attendance",
    "exams",
    "courses",
    "classroom.apps.ClassroomConfig",
    "registration",
    "announcements.apps.AnnouncementsConfig",
    "api.apps.ApiConfig",
    "accounts",
    "academic_years.apps.AcademicYearsConfig",
    "mobile.apps.MobileConfig",
    "errors",
    'quick',
    
    # Additional third-party apps
    "mptt",
    "crispy_forms",
    "widget_tweaks",
    "crispy_bootstrap4",
    "rest_framework",
    "rest_framework.authtoken",
    "corsheaders",
]

# ==============================
# CORS Settings
# ==============================
DEFAULT_CORS_ALLOWED_ORIGINS = [
    "https://alyaman-institute.com",
    "https://www.alyaman-institute.com",
]
if DEBUG:
    DEFAULT_CORS_ALLOWED_ORIGINS.extend([
        "http://127.0.0.1:8000",
        "http://localhost:8000",
    ])

CORS_ALLOWED_ORIGINS = env_list("DJANGO_CORS_ALLOWED_ORIGINS", DEFAULT_CORS_ALLOWED_ORIGINS)

CORS_ALLOW_HEADERS = [
    "accept",
    "accept-encoding",
    "authorization",
    "content-type",
    "dnt",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
    "token",
]

CORS_ALLOW_CREDENTIALS = True

# ==============================
# REST Framework
# ==============================
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
}

# ==============================
# Middleware
# ==============================
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'alyaman.middleware.NoIndexMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'academic_years.middleware.AcademicYearAccessMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    
    # Custom middleware (temporarily disabled for debugging)
    # 'alyaman.middleware.RecursionProtectionMiddleware',
    
    'errors.security_middleware.SecurityIntelligenceMiddleware',
    'errors.middleware.SecurityHeadersMiddleware',
    'errors.middleware.Universal404Middleware',
    
    # Other middleware
    'django_user_agents.middleware.UserAgentMiddleware',
    'employ.middleware.EmployeePermissionsMiddleware',
]

# ==============================
# Error Handlers
# ==============================
handler404 = 'errors.views.error_404_view'
handler403 = 'errors.views.error_403_view'
handler500 = 'errors.views.error_500_view'

USER_AGENTS_CACHE = 'default'

ROOT_URLCONF = "alyaman.urls"

# ==============================
# Templates
# ==============================
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [os.path.join(BASE_DIR, "templates")],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                'employ.context_processors.employee_permissions',
                'academic_years.context_processors.academic_year_context',
                'announcements.context_processors.web_announcements',
                'django.template.context_processors.media',
            ],
            "libraries": {
                "humanize": "django.contrib.humanize.templatetags.humanize",
                "formatting": "accounts.templatetags.formatting",
                "site_formatting": "accounts.templatetags.site_formatting",
                "number_formatter_tags": "accounts.templatetags.number_formatter_tags",
            },
        },
    },
]

WSGI_APPLICATION = "alyaman.wsgi.application"

# ==============================
# Database
# ==============================
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
        "OPTIONS": {
            "timeout": 30,
        },
    }
}

# ==============================
# Password Validation
# ==============================
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# ==============================
# Internationalization
# ==============================
LANGUAGE_CODE = "ar"
TIME_ZONE = "Asia/Riyadh"
USE_I18N = True
USE_L10N = True
USE_TZ = True

LOCALE_PATHS = [
    os.path.join(BASE_DIR, 'locale'),
]

# ==============================
# Static & Media Files
# ==============================
STATIC_URL = "/static/"
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, "static"),
]

STATICFILES_FINDERS = [
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
]

MEDIA_URL = "/media/"
MEDIA_ROOT = os.path.join(BASE_DIR, "media")

FILE_UPLOAD_MAX_MEMORY_SIZE = 5242880  # 5MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 5242880  # 5MB
DATA_UPLOAD_MAX_NUMBER_FIELDS = 50000

IMAGE_COMPRESSION_QUALITY = 80
IMAGE_MAX_SIZE = (800, 800)

# ==============================
# Quick Receipt Printer
# ==============================
QUICK_RECEIPT_PRINTER_ENABLED = env_bool("QUICK_RECEIPT_PRINTER_ENABLED", False)
QUICK_RECEIPT_PRINTER_BACKEND = os.getenv("QUICK_RECEIPT_PRINTER_BACKEND", "usb").strip().lower()
QUICK_RECEIPT_PRINTER_VENDOR_ID = env_int("QUICK_RECEIPT_PRINTER_VENDOR_ID", 0)
QUICK_RECEIPT_PRINTER_PRODUCT_ID = env_int("QUICK_RECEIPT_PRINTER_PRODUCT_ID", 0)
QUICK_RECEIPT_PRINTER_USB_INTERFACE = env_int("QUICK_RECEIPT_PRINTER_USB_INTERFACE", 0)
QUICK_RECEIPT_PRINTER_IN_EP = env_int("QUICK_RECEIPT_PRINTER_IN_EP", 0x82)
QUICK_RECEIPT_PRINTER_OUT_EP = env_int("QUICK_RECEIPT_PRINTER_OUT_EP", 0x01)
QUICK_RECEIPT_PRINTER_TIMEOUT = env_int("QUICK_RECEIPT_PRINTER_TIMEOUT", 0)
QUICK_RECEIPT_PRINTER_PROFILE = os.getenv("QUICK_RECEIPT_PRINTER_PROFILE", "").strip()
QUICK_RECEIPT_PRINTER_NETWORK_HOST = os.getenv("QUICK_RECEIPT_PRINTER_NETWORK_HOST", "").strip()
QUICK_RECEIPT_PRINTER_NETWORK_PORT = env_int("QUICK_RECEIPT_PRINTER_NETWORK_PORT", 9100)
QUICK_RECEIPT_PRINTER_DUMMY = env_bool("QUICK_RECEIPT_PRINTER_DUMMY", False)
QUICK_RECEIPT_PRINTER_CHARS_PER_LINE = env_int("QUICK_RECEIPT_PRINTER_CHARS_PER_LINE", 32)
QUICK_RECEIPT_PRINTER_FEED_LINES = env_int("QUICK_RECEIPT_PRINTER_FEED_LINES", 3)
QUICK_RECEIPT_PRINTER_TITLE = os.getenv("QUICK_RECEIPT_PRINTER_TITLE", "معهد اليمان").strip()
QUICK_LOCAL_AGENT_URL = os.getenv("QUICK_LOCAL_AGENT_URL", "http://127.0.0.1:8765/print").strip()
QUICK_PRINT_AGENT_TOKEN = os.getenv("QUICK_PRINT_AGENT_TOKEN", "").strip()

# ==============================
# Crispy Forms  
# ==============================
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap4"
CRISPY_TEMPLATE_PACK = "bootstrap4"

# ==============================
# Authentication & Session
# ==============================
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/login/'
LOGOUT_URL = "/logout/"

SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_AGE = 1209600  # 2 weeks in seconds
SESSION_SAVE_EVERY_REQUEST = env_bool("DJANGO_SESSION_SAVE_EVERY_REQUEST", False)
SESSION_COOKIE_SAMESITE = os.getenv("DJANGO_SESSION_COOKIE_SAMESITE", "Lax")
CSRF_COOKIE_SAMESITE = os.getenv("DJANGO_CSRF_COOKIE_SAMESITE", "Lax")

# ==============================
# Security Settings (Production)
# ==============================
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = env_bool("DJANGO_USE_X_FORWARDED_HOST", True)
USE_X_FORWARDED_PORT = env_bool("DJANGO_USE_X_FORWARDED_PORT", True)
SECURE_SSL_REDIRECT = env_bool("DJANGO_SSL_REDIRECT", False)
HTTPS_SECURITY_ENABLED = env_bool(
    "DJANGO_HTTPS_ENABLED",
    not DEBUG and SECURE_SSL_REDIRECT,
)

SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SESSION_COOKIE_SECURE = env_bool("DJANGO_SESSION_COOKIE_SECURE", HTTPS_SECURITY_ENABLED)
CSRF_COOKIE_SECURE = env_bool("DJANGO_CSRF_COOKIE_SECURE", HTTPS_SECURITY_ENABLED)
SECURE_HSTS_SECONDS = env_int(
    "DJANGO_SECURE_HSTS_SECONDS",
    31536000 if HTTPS_SECURITY_ENABLED else 0,
)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool(
    "DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS",
    HTTPS_SECURITY_ENABLED,
)
SECURE_HSTS_PRELOAD = env_bool("DJANGO_SECURE_HSTS_PRELOAD", HTTPS_SECURITY_ENABLED)
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin" if HTTPS_SECURITY_ENABLED or DEBUG else None

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ==============================
# Number Formatting
# ==============================
USE_THOUSAND_SEPARATOR = True
THOUSAND_SEPARATOR = ","
NUMBER_GROUPING = 3
DECIMAL_SEPARATOR = "."

# ==============================
# Logging
# ==============================
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'DEBUG',
            'class': 'logging.FileHandler',
            'filename': os.path.join(BASE_DIR, 'debug.log'),
            'formatter': 'verbose'
        },
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'simple'
        },
        'error_file': {
            'level': 'ERROR',
            'class': 'logging.FileHandler',
            'filename': os.path.join(BASE_DIR, 'error.log'),
            'formatter': 'verbose'
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': True,
        },
        'employ': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': True,
        },
        'accounts': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': True,
        },
        'errors': {
            'handlers': ['file', 'console', 'error_file'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}

# ==============================
# Email Settings
# ==============================
EMAIL_BACKEND = os.getenv(
    'EMAIL_BACKEND',
    'django.core.mail.backends.smtp.EmailBackend'
)
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', f"مركز الأمن - معهد اليمان <{os.getenv('EMAIL_HOST_USER', 'mhmadwerc8@gmail.com')}>")
SERVER_EMAIL = os.getenv('SERVER_EMAIL', DEFAULT_FROM_EMAIL)
EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', '587'))
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', 'mhmadwerc8@gmail.com')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', 'eyft acyj dccx qjvl')
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', '1') == '1'
EMAIL_USE_SSL = os.getenv('EMAIL_USE_SSL', '0') == '1'
EMAIL_TIMEOUT = int(os.getenv('EMAIL_TIMEOUT', '5'))
EMAIL_SSL_CERTFILE = os.getenv('EMAIL_SSL_CERTFILE') or None
EMAIL_SSL_KEYFILE = os.getenv('EMAIL_SSL_KEYFILE') or None
EMAIL_SUBJECT_PREFIX = os.getenv('EMAIL_SUBJECT_PREFIX', '[مركز الأمن] ')
SECURITY_ALERT_EMAILS = [item.strip() for item in os.getenv('SECURITY_ALERT_EMAILS', 'thaaeralmasre98@gmail.com').split(',') if item.strip()]
SECURITY_REPORT_EMAILS = [item.strip() for item in os.getenv('SECURITY_REPORT_EMAILS', 'thaaeralmasre98@gmail.com').split(',') if item.strip()]

SECURITY_BRAND_NAME = os.getenv('SECURITY_BRAND_NAME', 'مركز الأمن - معهد اليمان')
SECURITY_BRAND_SHORT = os.getenv('SECURITY_BRAND_SHORT', 'مركز الأمن')
SECURITY_SUPPORT_EMAIL = os.getenv('SECURITY_SUPPORT_EMAIL', 'mhmadwerc8@gmail.com')
SECURITY_DASHBOARD_URL = os.getenv('SECURITY_DASHBOARD_URL', 'http://127.0.0.1:8000/security/')
SECURITY_LOGO_URL = os.getenv('SECURITY_LOGO_URL', '')
PASSWORD_RESET_APPROVAL_EMAILS = [item.strip() for item in os.getenv('PASSWORD_RESET_APPROVAL_EMAILS', ','.join(SECURITY_ALERT_EMAILS) if SECURITY_ALERT_EMAILS else EMAIL_HOST_USER).split(',') if item.strip()]
PASSWORD_RESET_APPROVAL_MAX_AGE_SECONDS = int(os.getenv('PASSWORD_RESET_APPROVAL_MAX_AGE_SECONDS', '172800'))
PASSWORD_RESET_BASE_URL = os.getenv('PASSWORD_RESET_BASE_URL', '')
WHATSAPP_ENABLED = os.getenv('WHATSAPP_ENABLED', '0') == '1'
WHATSAPP_PROVIDER = os.getenv('WHATSAPP_PROVIDER', 'meta_cloud').strip().lower()
WHATSAPP_API_URL = os.getenv('WHATSAPP_API_URL', 'https://graph.facebook.com/v22.0')
WHATSAPP_PHONE_NUMBER_ID = os.getenv('WHATSAPP_PHONE_NUMBER_ID', '')
WHATSAPP_ACCESS_TOKEN = os.getenv('WHATSAPP_ACCESS_TOKEN', '')
WHATSAPP_DEFAULT_COUNTRY_CODE = os.getenv('WHATSAPP_DEFAULT_COUNTRY_CODE', '963')

# ==============================
# Custom Application Settings
# ==============================
ERROR_TRACKING = {
    'ENABLE_ADVANCED_TRACKING': False,
    'CAPTURE_MAC_ADDRESS': False,
    'CAPTURE_LOCATION': False,
    'ENABLE_SECURITY_SCANNING': False,
    'RATE_LIMITING': {
        'ENABLED': False,
    },
    'MAP_PROVIDER': 'openstreetmap',
    'ENABLE_USER_TRACKING': False,
    'LOG_SLOW_RESPONSES': True,
    'SLOW_RESPONSE_THRESHOLD': 5.0,
}

MAX_FILE_UPLOAD_SIZE = 5242880  # 5MB
ALLOWED_IMAGE_EXTENSIONS = ['jpg', 'jpeg', 'png', 'gif', 'bmp']

EMPLOYEE_SESSION_TIMEOUT = 3600

REPORTS_PER_PAGE = 50
MAX_EXPORT_RECORDS = 10000

# ==============================
# Push Notifications (FCM)
# ==============================
# FCM_SERVER_KEY = os.getenv("FCM_SERVER_KEY", "")
# FIREBASE_SERVICE_ACCOUNT = os.getenv(
#     "FIREBASE_SERVICE_ACCOUNT",
#     os.path.join(BASE_DIR, "serviceAccountKey.json"),
# )

# ==============================
# Cache
# ==============================
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',
    }
}

# ==============================
# Additional Security Headers
# ==============================
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'
X_FRAME_OPTIONS = 'DENY'

# ==============================
# Admin Site Customization
# ==============================
from django.utils.translation import gettext_lazy as _
ADMIN_SITE_HEADER = _("نظام مراقبة الأخطاء المتقدم - معهد اليمان")
ADMIN_SITE_TITLE = _("نظام المراقبة المتقدم")
ADMIN_INDEX_TITLE = _("لوحة التحكم الرئيسية - المراقبة الشاملة")

# ==============================
# Application-Specific Settings
# ==============================
# Student settings
STUDENT_UPLOAD_DIR = 'students/uploads/'
STUDENT_IMAGE_DIR = 'students/images/'

# Employee settings
EMPLOYEE_UPLOAD_DIR = 'employees/uploads/'
EMPLOYEE_IMAGE_DIR = 'employees/images/'

# Course settings
COURSE_UPLOAD_DIR = 'courses/uploads/'
COURSE_IMAGE_DIR = 'courses/images/'

# Exam settings
EXAM_UPLOAD_DIR = 'exams/uploads/'
EXAM_RESULT_DIR = 'exams/results/'

# Attendance settings
ATTENDANCE_REPORT_DIR = 'attendance/reports/'

# ==============================
# API Settings
# ==============================
API_VERSION = 'v1'
API_DEFAULT_RESPONSE_FORMAT = 'json'
API_MAX_PAGE_SIZE = 100

# ==============================
# Debug Settings (Development Only)
# ==============================
if DEBUG:
    # Show SQL queries in console
    LOGGING['loggers']['django.db.backends'] = {
        'handlers': ['console'],
        'level': 'DEBUG',
        'propagate': False,
    }
    
    # Add debug toolbar if installed
    try:
        import debug_toolbar
        INSTALLED_APPS += ['debug_toolbar']
        MIDDLEWARE.insert(0, 'debug_toolbar.middleware.DebugToolbarMiddleware')
        INTERNAL_IPS = ['127.0.0.1', 'localhost']
    except ImportError:
        pass

SECURITY_MONITORING = {
    'ENABLED': True,
    'ALERT_EMAILS': SECURITY_ALERT_EMAILS,
    'DAILY_REPORT_EMAILS': SECURITY_REPORT_EMAILS or SECURITY_ALERT_EMAILS,
    'MAX_HTML_CAPTURE': 20000,
    'MAX_BODY_CAPTURE': 2000,
    'BRUTE_FORCE_WINDOW_SECONDS': 900,
    'BRUTE_FORCE_THRESHOLD': 8,
    'REPORT_INCLUDE_ARTIFACTS': True,
    'ENABLE_GEO_LOOKUPS': env_bool('SECURITY_GEO_LOOKUPS_ENABLED', False),
    'ENABLE_EMAIL_ALERTS': env_bool('SECURITY_EMAIL_ALERTS_ENABLED', False),
    'ENABLE_LOGIN_EVENT_EMAILS': env_bool('SECURITY_LOGIN_EVENT_EMAILS_ENABLED', False),
}

