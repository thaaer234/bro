"""
Django settings for alyaman project.
"""

from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent

# ==============================
# Security
# ==============================
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "django-insecure-change-me-in-production!")
BACKUP_KEY = os.getenv("BACKUP_KEY", "MY_SUPER_BACKUP_KEY_123")
DEBUG = False

ALLOWED_HOSTS = [
    'localhost',
    '127.0.0.1',
    'alyaman-institute.com',
    'www.alyaman-institute.com',
    '187.124.151.249',
]

CSRF_TRUSTED_ORIGINS = [
    'https://alyaman-institute.com',
    'https://www.alyaman-institute.com',
    'http://alyaman-institute.com',
    'http://www.alyaman-institute.com',
]

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
    "students",
    "employ",
    "attendance",
    "exams",
    "courses",
    "classroom",
    "registration",
    "api.apps.ApiConfig",
    "accounts",
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
CORS_ALLOWED_ORIGINS = [
    "https://alyaman-institute.com",
    "https://www.alyaman-institute.com",
]

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
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    
    # Custom middleware (temporarily disabled for debugging)
    # 'alyaman.middleware.RecursionProtectionMiddleware',
    
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
SESSION_SAVE_EVERY_REQUEST = True

# ==============================
# Security Settings (Production)
# ==============================
if not DEBUG:
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    # Set DJANGO_SSL_REDIRECT=1 after SSL is working.
    SECURE_SSL_REDIRECT = os.getenv("DJANGO_SSL_REDIRECT", "0") == "1"
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

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
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
DEFAULT_FROM_EMAIL = 'webmaster@alyaman.com'
EMAIL_HOST = 'localhost'
EMAIL_PORT = 25

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
