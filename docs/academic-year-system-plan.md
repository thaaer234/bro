# Academic Year System Plan

هذا المستند مبني على الكود الحالي في المشروع، خصوصًا:

- [`quick/models.py`](../quick/models.py)
- [`students/models.py`](../students/models.py)
- [`accounts/models.py`](../accounts/models.py)
- [`alyaman/settings.py`](../alyaman/settings.py)
- [`alyaman/urls.py`](../alyaman/urls.py)

الهدف هو إضافة إدارة فصول دراسية متكاملة داخل النظام الحالي مع الحفاظ على البيانات القديمة، واستخدام `quick.AcademicYear` كأساس وحيد للفصل الدراسي.

## 1. قراءة الوضع الحالي

### الموجود بالفعل

- `quick.AcademicYear` موجود ويحتوي حاليًا على:
  - `is_active`
  - `is_closed`
  - `closed_by`
  - `closed_at`
- `students.Student` مرتبط أصلًا بـ `quick.AcademicYear`.
- `quick.QuickCourse` و`quick.QuickStudent` مرتبطان أصلًا بـ `AcademicYear`.
- `accounts.Course` و`accounts.Studentenrollment` و`accounts.StudentReceipt` و`accounts.JournalEntry` ما زالت تعمل دون عزل فصل كافٍ.
- `accounts.Account` هو دليل الحسابات الفعلي، ويجب إبقاؤه مشتركًا بين جميع الفصول.

### الفجوة الحالية

- مفهوم "إنشاء فصل" و"تفعيل فصل" و"إغلاق فصل" غير مفصول بشكل كافٍ.
- لا يوجد `current academic year` مركزي على مستوى النظام/الجلسة.
- لا يوجد `middleware` لحماية الفصول القديمة بكلمة سر.
- كثير من الاستعلامات في `accounts.views` و`students.views` تعتمد `objects.all()` أو `filter(is_active=True)` بدون فصل.
- بيانات النشاط الأكاديمي والمحاسبي تحتاج ربطًا أوضح بـ `AcademicYear`.

## 2. القرار المعماري

### اسم التطبيق المقترح

`academic_years`

السبب:

- واضح وظيفيًا.
- لا يتعارض مع `quick`.
- يسمح بإدارة الوصول، الجلسات، والتحويلات دون إعادة تعريف `AcademicYear`.

### مسؤوليات التطبيق الجديد

- إدارة الفصل النشط على مستوى النظام والجلسة.
- إدارة حماية الفصول القديمة بكلمة سر.
- فرض وضع القراءة فقط.
- توفير شاشة اختيار/فتح الفصل بعد تسجيل الدخول.
- توفير خدمة وواجهة ترحيل بين الفصول.
- تسجيل Logs لعمليات الوصول والترحيل وتغيير الحالة.

### ما لا يفعله التطبيق الجديد

- لا ينشئ موديل فصل جديد.
- لا ينقل النظام إلى قاعدة بيانات متعددة.
- لا يغيّر دليل الحسابات الأساسي.
- لا يغلق فصلًا تلقائيًا عند إنشاء فصل جديد.

## 3. فصل المفاهيم الأساسية

يجب فصل العمليات التالية تمامًا:

### إنشاء فصل جديد

- مجرد إنشاء سجل جديد في `quick.AcademicYear`.
- لا يؤدي إلى:
  - تفعيله تلقائيًا
  - إغلاق الفصل السابق
  - نقل أي بيانات تلقائيًا

### تفعيل فصل للعمل اليومي

- يتم من خلال إعداد مركزي في التطبيق الجديد.
- يحدد الفصل الافتراضي الذي يدخل عليه المستخدم بعد تسجيل الدخول.
- يمكن تغييره دون المساس بباقي الفصول.

### إغلاق فصل

- إجراء إداري مستقل.
- معناه إيقاف التعديل عليه أو تحويله لوضع protected/read-only.
- لا يعني حذف البيانات.
- لا يعني نقلها.

## 4. الموديلات المقترحة

### 4.1 ربط إضافي فوق `quick.AcademicYear`

ملف مقترح: `academic_years/models.py`

```python
from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.db import models


class AcademicYearAccess(models.Model):
    academic_year = models.OneToOneField(
        "quick.AcademicYear",
        on_delete=models.CASCADE,
        related_name="access_policy",
    )
    requires_password = models.BooleanField(default=False)
    password_hash = models.CharField(max_length=255, blank=True)
    is_read_only = models.BooleanField(default=False)
    is_archived = models.BooleanField(default=False)
    allow_reporting = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def set_password(self, raw_password: str):
        self.password_hash = make_password(raw_password)

    def check_password(self, raw_password: str) -> bool:
        if not self.password_hash:
            return False
        return check_password(raw_password, self.password_hash)
```

هذا الموديل لا يكرر بيانات الفصل، بل يضيف سياسات وصول فقط.

### 4.2 حالة النظام الحالية

```python
class AcademicYearSystemState(models.Model):
    singleton_key = models.CharField(max_length=20, unique=True, default="default")
    active_academic_year = models.ForeignKey(
        "quick.AcademicYear",
        on_delete=models.PROTECT,
        related_name="active_system_states",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    updated_at = models.DateTimeField(auto_now=True)
```

الفكرة:

- هذا هو "الفصل النشط" الذي يُستخدم بعد تسجيل الدخول.
- لا علاقة له بإنشاء فصل جديد.
- لا يفرض إغلاقًا على غيره.

### 4.3 تفضيل المستخدم

```python
class UserAcademicYearPreference(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    preferred_academic_year = models.ForeignKey(
        "quick.AcademicYear",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    updated_at = models.DateTimeField(auto_now=True)
```

يفيد إذا أردتم لاحقًا أن يدخل بعض المستخدمين على فصل مختلف عن الافتراضي، لكن يمكن البدء بدونه.

### 4.4 سجل تغيير الحالة

```python
class AcademicYearStateLog(models.Model):
    ACTION_CHOICES = [
        ("created", "Created"),
        ("activated", "Activated"),
        ("deactivated", "Deactivated"),
        ("closed", "Closed"),
        ("reopened", "Reopened"),
        ("password_enabled", "Password Enabled"),
        ("password_disabled", "Password Disabled"),
        ("read_only_enabled", "Read Only Enabled"),
        ("read_only_disabled", "Read Only Disabled"),
    ]

    academic_year = models.ForeignKey("quick.AcademicYear", on_delete=models.CASCADE)
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
```

### 4.5 سجل الترحيل بين الفصول

```python
class AcademicYearTransferBatch(models.Model):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("validated", "Validated"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    ]

    source_academic_year = models.ForeignKey(
        "quick.AcademicYear",
        on_delete=models.PROTECT,
        related_name="outgoing_transfer_batches",
    )
    target_academic_year = models.ForeignKey(
        "quick.AcademicYear",
        on_delete=models.PROTECT,
        related_name="incoming_transfer_batches",
    )
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    summary_json = models.JSONField(default=dict, blank=True)
    executed_at = models.DateTimeField(null=True, blank=True)
    failure_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
```

```python
class AcademicYearTransferCourseItem(models.Model):
    batch = models.ForeignKey(
        AcademicYearTransferBatch,
        on_delete=models.CASCADE,
        related_name="course_items",
    )
    source_course = models.ForeignKey("accounts.Course", on_delete=models.PROTECT)
    target_course = models.ForeignKey(
        "accounts.Course",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    student_count = models.PositiveIntegerField(default=0)
    enrollment_count = models.PositiveIntegerField(default=0)
    receipt_count = models.PositiveIntegerField(default=0)
    journal_entry_count = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, default="pending")
    notes = models.TextField(blank=True)
```

```python
class AcademicYearTransferLog(models.Model):
    batch = models.ForeignKey(
        AcademicYearTransferBatch,
        on_delete=models.CASCADE,
        related_name="logs",
    )
    level = models.CharField(max_length=20, default="info")
    message = models.TextField()
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
```

## 5. الحقول التي يجب ربطها بالفصل

### الحقول الجديدة المطلوبة

يجب إضافة `academic_year` إلى الموديلات التالية على الأقل:

- `accounts.Course`
- `accounts.Studentenrollment`
- `accounts.StudentReceipt`
- `accounts.JournalEntry`
- `accounts.Transaction` اختياري تقنيًا، لكنه مفيد جدًا للأداء والتقارير
- أي موديل مالي أو تشغيلي يعتمد على دورة/طالب/قيد مرتبط بفصل

### توصية عملية مهمة

أقوى تصميم هنا هو:

- `Course.academic_year` أساسي
- `Studentenrollment.academic_year` أساسي
- `StudentReceipt.academic_year` أساسي
- `JournalEntry.academic_year` أساسي
- `Transaction.academic_year` اختياري مرحليًا، ثم يضاف لاحقًا لتحسين التقارير

السبب:

- الاعتماد على الربط غير المباشر فقط عبر `course` أو `enrollment` سيجعل التقارير والفلترة بطيئة ومعقدة.
- الحقل المباشر يسمح بفهارس واضحة واستعلامات مستقرة.

### مثال للربط في `accounts.Course`

```python
academic_year = models.ForeignKey(
    "quick.AcademicYear",
    on_delete=models.PROTECT,
    related_name="account_courses",
    null=True,
    blank=True,
    db_index=True,
)
```

### مثال للربط في `accounts.Studentenrollment`

```python
academic_year = models.ForeignKey(
    "quick.AcademicYear",
    on_delete=models.PROTECT,
    related_name="student_enrollments",
    null=True,
    blank=True,
    db_index=True,
)
```

ويجب في `save()` أو `clean()` فرض التوافق:

```python
def clean(self):
    if self.course_id and self.academic_year_id and self.course.academic_year_id != self.academic_year_id:
        raise ValidationError("Enrollment academic year must match course academic year.")
```

### مثال للربط في `accounts.StudentReceipt`

```python
academic_year = models.ForeignKey(
    "quick.AcademicYear",
    on_delete=models.PROTECT,
    related_name="student_receipts",
    null=True,
    blank=True,
    db_index=True,
)
```

أولوية التعيين:

- من `enrollment.academic_year`
- ثم `course.academic_year`
- ثم `student_profile.academic_year`

### مثال للربط في `accounts.JournalEntry`

```python
academic_year = models.ForeignKey(
    "quick.AcademicYear",
    on_delete=models.PROTECT,
    related_name="journal_entries",
    null=True,
    blank=True,
    db_index=True,
)
```

كل قيد ناتج عن تسجيل أو إيصال أو نقل يجب أن يحمل الفصل مباشرة.

## 6. ماذا نفعل مع `accounts.Account`

### القاعدة الأساسية

دليل الحسابات يبقى مشتركًا بين جميع الفصول.

### لكن

الحسابات التشغيلية المولدة تلقائيًا للطلاب والدورات يفضّل أن تحمل فصلًا اختياريًا:

```python
academic_year = models.ForeignKey(
    "quick.AcademicYear",
    on_delete=models.SET_NULL,
    null=True,
    blank=True,
    related_name="accounts",
)
```

الاستخدام:

- الحسابات الجذرية والثابتة: `academic_year = NULL`
- الحسابات المولدة لدورة أو طالب داخل فصل: تحمل `academic_year`

بهذا نحافظ على:

- دليل الحسابات ثابتًا ومشتركًا
- مع قدرة على عزل الحسابات الفرعية التشغيلية حسب الفصل

## 7. Session Flow المقترح

### مفاتيح الجلسة

```python
CURRENT_ACADEMIC_YEAR_SESSION_KEY = "current_academic_year_id"
UNLOCKED_ACADEMIC_YEARS_SESSION_KEY = "unlocked_academic_year_ids"
```

### التدفق بعد تسجيل الدخول

1. إذا كان في الجلسة `current_academic_year_id` صالحًا، نستخدمه.
2. إن لم يوجد:
   - نأخذ `AcademicYearSystemState.active_academic_year`
3. إذا كان الفصل يتطلب كلمة سر:
   - إن كان موجودًا ضمن `unlocked_academic_year_ids` نسمح
   - وإلا نعيد التوجيه إلى شاشة `unlock`
4. إذا كان الفصل في وضع `read_only`:
   - نسمح بالقراءة
   - نمنع `POST/PUT/PATCH/DELETE` إلا للمخولين أو لشاشات إدارية محددة

### خدمة مقترحة

ملف: `academic_years/services/session.py`

```python
def set_current_academic_year(request, academic_year):
    request.session[CURRENT_ACADEMIC_YEAR_SESSION_KEY] = academic_year.pk


def get_current_academic_year(request):
    academic_year_id = request.session.get(CURRENT_ACADEMIC_YEAR_SESSION_KEY)
    if academic_year_id:
        return AcademicYear.objects.filter(pk=academic_year_id).first()
    system_state = AcademicYearSystemState.objects.select_related("active_academic_year").first()
    return system_state.active_academic_year if system_state else None


def unlock_academic_year(request, academic_year):
    unlocked = set(request.session.get(UNLOCKED_ACADEMIC_YEARS_SESSION_KEY, []))
    unlocked.add(academic_year.pk)
    request.session[UNLOCKED_ACADEMIC_YEARS_SESSION_KEY] = list(unlocked)
```

## 8. Middleware المطلوب

ملف: `academic_years/middleware.py`

```python
from django.http import HttpResponseForbidden
from django.shortcuts import redirect
from django.urls import reverse

from .services.session import get_current_academic_year


class AcademicYearAccessMiddleware:
    SAFE_PREFIXES = (
        "/login/",
        "/logout/",
        "/academic-years/unlock/",
        "/admin/",
        "/static/",
        "/media/",
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.user.is_authenticated:
            return self.get_response(request)

        if request.path.startswith(self.SAFE_PREFIXES):
            return self.get_response(request)

        academic_year = get_current_academic_year(request)
        request.current_academic_year = academic_year

        if not academic_year:
            return redirect("academic_years:select_current")

        policy = getattr(academic_year, "access_policy", None)
        if policy and policy.requires_password:
            unlocked_ids = set(request.session.get("unlocked_academic_year_ids", []))
            if academic_year.pk not in unlocked_ids:
                return redirect(
                    reverse("academic_years:unlock", kwargs={"pk": academic_year.pk})
                )

        if (
            policy
            and policy.is_read_only
            and request.method in {"POST", "PUT", "PATCH", "DELETE"}
            and not request.user.is_superuser
        ):
            return HttpResponseForbidden("This academic year is read-only.")

        return self.get_response(request)
```

### مكان الإضافة في `MIDDLEWARE`

في [`alyaman/settings.py`](../alyaman/settings.py) يضاف بعد:

- `AuthenticationMiddleware`
- وقبل middleware الصلاحيات الخاصة بالتطبيقات

الموضع المقترح:

```python
"django.contrib.auth.middleware.AuthenticationMiddleware",
"academic_years.middleware.AcademicYearAccessMiddleware",
"django.contrib.messages.middleware.MessageMiddleware",
```

## 9. صلاحيات الوصول

### الصلاحيات المقترحة

- `academic_years.view_academic_year`
- `academic_years.manage_academic_year_state`
- `academic_years.unlock_protected_academic_year`
- `academic_years.transfer_academic_year_data`
- `academic_years.override_read_only`

### منطق الصلاحيات

- المستخدم العادي:
  - يدخل على الفصل النشط
  - يستطيع فتح فصل قديم إذا عُرفت كلمة السر وسمحت السياسات
- الأدمن:
  - يحدد الفصل النشط
  - يفعّل الحماية بكلمة سر
  - يجعل الفصل قراءة فقط
  - يغلق الفصل أو يعيد فتحه
  - ينفذ الترحيل بين الفصول
- السوبر يوزر:
  - يتجاوز قيود القراءة فقط عند الحاجة
  - يظل بحاجة audit log لكل عملية حساسة

## 10. فلترة الاستعلامات حسب الفصل

### الهدف

بدل تعديل كل `queryset` بشكل يدوي من أول يوم، نبدأ بطبقة خدمية ومكسنات:

- `AcademicYearAwareMixin`
- `for_current_academic_year(request)`
- `filter_by_academic_year(queryset, request, field_name="academic_year")`

### مثال

ملف: `academic_years/query.py`

```python
def filter_by_current_academic_year(queryset, request, field_name="academic_year"):
    academic_year = getattr(request, "current_academic_year", None)
    if not academic_year:
        return queryset.none()
    return queryset.filter(**{field_name: academic_year})
```

### تطبيق تدريجي

ابدأ أولًا بهذه الشاشات:

1. قوائم الدورات
2. التسجيلات
3. الإيصالات
4. القيود اليومية
5. تقارير الذمم والملخصات المالية

### أمثلة استبدال مباشرة

بدل:

```python
Course.objects.filter(is_active=True)
```

استخدم:

```python
filter_by_current_academic_year(
    Course.objects.filter(is_active=True),
    request,
)
```

وبدل:

```python
Studentenrollment.objects.filter(course=course, is_completed=False)
```

استخدم:

```python
Studentenrollment.objects.filter(
    course=course,
    academic_year=request.current_academic_year,
    is_completed=False,
)
```

## 11. منطق إنشاء الفصل وتفعيله وإغلاقه

### إنشاء فصل

- يتم عبر `quick.AcademicYear` كما هو.
- يضاف له تلقائيًا سجل `AcademicYearAccess`.
- لا يغيّر `AcademicYearSystemState`.

### تفعيل فصل

- يتم من شاشة داخل التطبيق الجديد.
- مجرد تحديث `AcademicYearSystemState.active_academic_year`.
- يمكن أن يكون الفصل الجديد غير مفعل لأيام أو أسابيع بعد إنشائه.

### إغلاق فصل

الإغلاق الإداري يجب أن يكون واضحًا في السياسات:

- `quick.AcademicYear.is_closed = True`
- `AcademicYearAccess.is_read_only = True`
- `AcademicYearAccess.requires_password = True` اختياري حسب قرار الأدمن

بهذا يكون الإغلاق قرارًا مستقلًا، وليس أثرًا جانبيًا لإنشاء فصل جديد.

## 12. منطق الترحيل بين الفصول

### المبدأ

الترحيل ليس "نقل كل الفصل"، بل "نقل مجموعة محددة من الدورات مع كل ما يرتبط بها".

### ما الذي ينتقل

عند اختيار دورة أو أكثر من فصل مصدر إلى فصل هدف:

- الطلاب المرتبطون بهذه الدورات
- تسجيلاتهم
- إيصالاتهم
- القيود اليومية المرتبطة بهم
- الحسابات التشغيلية الفرعية المتعلقة بهم
- أي علاقات تشغيلية أو مالية مرتبطة بهذه الدورة وهؤلاء الطلاب

### ما الذي لا ينتقل

- دليل الحسابات الجذري
- الحسابات العامة المشتركة
- بيانات فصول أخرى

### قرار مهم جدًا

الترحيل هنا الأفضل أن يكون **نسخًا مضبوطًا إلى الفصل الجديد** وليس "نقلًا حذفًا من المصدر".

السبب:

- طلبك يشدد على أن بيانات الفصل القديم تبقى كما كانت.
- أي حذف من المصدر سيكسر هذا الشرط.

إذًا التنفيذ الصحيح:

- `source` يبقى كما هو
- `target` يأخذ نسخًا جديدة مرتبطة بالفصل الجديد
- مع حفظ `origin/reference fields` لتتبع الأصل

## 13. الحقول المساعدة للنسخ الآمن

يفضّل إضافة حقول مرجعية للموديلات المرحّلة:

```python
source_academic_year = models.ForeignKey(
    "quick.AcademicYear",
    on_delete=models.SET_NULL,
    null=True,
    blank=True,
    related_name="+",
)
source_object_id = models.PositiveBigIntegerField(null=True, blank=True)
transfer_batch = models.ForeignKey(
    "academic_years.AcademicYearTransferBatch",
    on_delete=models.SET_NULL,
    null=True,
    blank=True,
)
```

لا يلزم في كل الموديلات من اليوم الأول، لكنه مفيد جدًا في:

- `Course`
- `Studentenrollment`
- `StudentReceipt`
- `JournalEntry`
- `Account` للحسابات المولدة فقط

## 14. التحقق قبل الترحيل

قبل التنفيذ يجب بناء preview يحتوي على:

- عدد الدورات
- عدد الطلاب
- عدد التسجيلات
- عدد الإيصالات
- عدد القيود
- عدد الحسابات التي ستنشأ
- التعارضات المحتملة

### قواعد منع التكرار

- الطالب نفسه لا ينسخ مرتين داخل نفس batch.
- إذا كان للطالب نسخة سابقة في الفصل الهدف بسبب ترحيل سابق:
  - نعيد استخدام السجل الموجود إن كان مطابقًا منطقيًا
  - أو نوقف العملية ونطلب قرارًا من الأدمن
- الحسابات المولدة يعاد ربطها أو إنشاؤها حسب خريطة mapping داخل batch.
- القيود لا تنسخ مباشرة بدون mapping واضح للحسابات الجديدة.

## 15. خدمة الترحيل المقترحة

ملف: `academic_years/services/transfers.py`

```python
from django.db import transaction


class AcademicYearTransferService:
    def __init__(self, *, batch, actor):
        self.batch = batch
        self.actor = actor
        self.student_map = {}
        self.course_map = {}
        self.account_map = {}
        self.entry_map = {}

    @transaction.atomic
    def execute(self):
        self.validate_batch()
        self.clone_courses()
        self.clone_students_and_enrollments()
        self.clone_accounts()
        self.clone_journal_entries_and_receipts()
        self.mark_batch_completed()

    def validate_batch(self):
        if self.batch.source_academic_year_id == self.batch.target_academic_year_id:
            raise ValueError("Source and target academic years must be different.")

    def clone_courses(self):
        ...

    def clone_students_and_enrollments(self):
        ...

    def clone_accounts(self):
        ...

    def clone_journal_entries_and_receipts(self):
        ...
```

### الترتيب الصحيح للتنفيذ

1. التحقق من batch
2. نسخ/إنشاء الدورات في الفصل الهدف
3. تجهيز خريطة الطلاب
4. نسخ التسجيلات
5. إنشاء أو ربط الحسابات الفرعية
6. نسخ القيود اليومية مع إعادة ربط الحسابات
7. نسخ الإيصالات وربطها بالقيود الجديدة
8. تسجيل log نهائي

### لماذا هذا الترتيب

- لأن `JournalEntry` و`StudentReceipt` يعتمدان على:
  - course
  - enrollment
  - account mapping

## 16. الواجهة المقترحة للترحيل

مسارات مقترحة:

- `academic-years/transfers/`
- `academic-years/transfers/create/`
- `academic-years/transfers/<id>/preview/`
- `academic-years/transfers/<id>/execute/`
- `academic-years/transfers/<id>/detail/`

### شاشة الإنشاء

تحتوي:

- الفصل المصدر
- الفصل الهدف
- اختيار دورة أو أكثر
- زر Preview

### شاشة المعاينة

تعرض:

- عدد الطلاب
- عدد التسجيلات
- عدد الإيصالات
- عدد القيود
- عدد الحسابات الجديدة المتوقع إنشاؤها
- التعارضات
- التحذيرات

### شاشة التنفيذ

- تأكيد نهائي
- تنفيذ Transactional بالكامل
- صفحة نتيجة مع log واضح

## 17. Migration Plan آمنة

### المرحلة 1

إنشاء التطبيق الجديد فقط:

- `academic_years`
- موديلات الوصول والحالة واللوج
- middleware
- اختيار الفصل النشط

بدون لمس `accounts` بعد.

### المرحلة 2

إضافة `academic_year` إلى:

- `accounts.Course`
- `accounts.Studentenrollment`
- `accounts.StudentReceipt`
- `accounts.JournalEntry`

في البداية:

- `null=True`
- مع migration backfill

### المرحلة 3

Backfill البيانات القديمة:

- `Course.academic_year`
  - منطق التعيين:
    - من الطلاب المسجلين إن وجد توافق واضح
    - أو من تاريخ الإنشاء/النشاط
    - أو من فصل النظام النشط في فترة التشغيل القديمة
    - أو يترك `NULL` مع تقرير مراجعة يدوي
- `Studentenrollment.academic_year`
  - من `course.academic_year`
  - وإلا من `student.academic_year`
- `StudentReceipt.academic_year`
  - من `enrollment.academic_year`
  - وإلا من `course.academic_year`
- `JournalEntry.academic_year`
  - من `receipt.academic_year`
  - أو `enrollment.academic_year`
  - أو من الحساب/الوصف/المصدر إن أمكن

### المرحلة 4

بعد نجاح الـ backfill:

- تحويل الحقول الحرجة إلى `null=False` حيث يمكن
- إضافة `indexes`
- تحديث الاستعلامات الرئيسية

### المرحلة 5

إضافة الترحيل بين الفصول.

## 18. أمثلة Migration للربط

ملف مقترح: `accounts/migrations/0008_add_academic_year_scope.py`

```python
migrations.AddField(
    model_name="course",
    name="academic_year",
    field=models.ForeignKey(
        blank=True,
        null=True,
        on_delete=django.db.models.deletion.PROTECT,
        related_name="account_courses",
        to="quick.academicyear",
    ),
),
```

ومثله لباقي الموديلات.

### Migration backfill

ملف مقترح:

`accounts/migrations/0009_backfill_academic_year_scope.py`

يحتوي `RunPython` مع منطق متدرج، ولا يحذف شيئًا، ويكتب تقريرًا في log أو stdout عن السجلات التي لم يمكن حسم فصلها.

## 19. تعديلات مهمة على الكود الحالي

### `students.models.Student`

حاليًا هناك تعيين تلقائي للفصل عند الحفظ. هذا السلوك يجب تخفيفه حتى لا يخرّب الفصل النشط عند الانتقال إلى النظام الجديد.

التعديل المقترح:

- في الإدخال الجديد:
  - إن لم يحدد الفصل يدويًا، يستخدم الفصل الحالي من الجلسة أو النظام
- لا يعتمد فقط على التاريخ

### `accounts.Course`

يجب أن يصبح الفصل جزءًا أساسيًا من تعريف الدورة.

### `accounts.Studentenrollment`

يجب أن يأخذ الفصل من الدورة تلقائيًا.

### `accounts.StudentReceipt`

يجب أن يأخذ الفصل من التسجيل أو الدورة تلقائيًا.

### `accounts.JournalEntry`

أي قيد ناتج عن:

- تسجيل
- دفعة
- إكمال
- تسوية

يجب أن يرث `academic_year` من المصدر.

## 20. هيكل الملفات المقترح

```text
academic_years/
  __init__.py
  apps.py
  admin.py
  urls.py
  forms.py
  models.py
  middleware.py
  context_processors.py
  services/
    __init__.py
    session.py
    activation.py
    access.py
    transfers.py
    preview.py
  selectors.py
  permissions.py
  views.py
  migrations/
```

### قوالب مقترحة

```text
templates/academic_years/
  select_current.html
  unlock.html
  manage.html
  transfer_create.html
  transfer_preview.html
  transfer_detail.html
```

## 21. ترتيب التنفيذ العملي

### Sprint 1

- إنشاء `academic_years`
- إضافة `AcademicYearAccess`
- إضافة `AcademicYearSystemState`
- إضافة شاشة اختيار/تغيير الفصل الحالي
- إضافة middleware الحماية والقراءة فقط

### Sprint 2

- إضافة `academic_year` إلى الموديلات المالية الأساسية
- تنفيذ backfill آمن
- تحديث أهم القوائم والتقارير

### Sprint 3

- بناء preview للترحيل
- بناء transfer batch + logs
- تنفيذ transactional clone آمن

### Sprint 4

- توسيع الفلترة على جميع التقارير
- إضافة اختبارات تكامل
- تحسين الأداء والفهارس

## 22. الفهارس والأداء

أضف فهارس على:

- `Course(academic_year, is_active)`
- `Studentenrollment(academic_year, student, course)`
- `StudentReceipt(academic_year, date)`
- `JournalEntry(academic_year, date, entry_type)`
- `Transaction(journal_entry, account)`

وأي شاشة تقارير ثقيلة يجب أن تستخدم:

- `select_related`
- `prefetch_related`
- `annotate`

بدل حلقة استعلامات داخلية.

## 23. الاختبارات المطلوبة

### وصول

- مستخدم يدخل بعد login فيُحمّل الفصل النشط تلقائيًا.
- فصل قديم محمي يطلب كلمة سر.
- بعد فك القفل يبقى متاحًا ضمن الجلسة.
- فصل read-only يمنع `POST`.

### بيانات

- الدورة الجديدة ترتبط بالفصل الحالي.
- التسجيل يأخذ فصل الدورة.
- الإيصال يأخذ فصل التسجيل.
- القيد يأخذ فصل المصدر.

### ترحيل

- preview يحسب الأعداد الصحيحة.
- إذا حصل conflict تتوقف العملية.
- إذا فشل جزء من التنفيذ يتم rollback كامل.
- logs تُسجل المستخدم، المصدر، الهدف، العناصر، والتوقيت.

## 24. نقاط الحذر داخل مشروعكم الحالي

### 1. الاستعلامات المباشرة كثيرة

لذلك لا أنصح بتعديل كل شيء دفعة واحدة. ابدأ بالشاشات الحرجة ثم وسّع.

### 2. `students.Student` مرتبط أصلًا بالفصل

هذا جيد، لكن لا يكفي وحده لعزل المحاسبة.

### 3. `Account` فيه حسابات مولدة حسب الدورة والطالب

لذلك يجب تمييز الحسابات الثابتة عن الحسابات التشغيلية، لا فصلها إلى جداول مختلفة.

### 4. بعض السلوك الحالي تلقائي جدًا

خصوصًا تعيين الفصل من التاريخ أو فتح/إغلاق ضمنيًا. هذا يجب استبداله بسلوك صريح يعتمد على:

- الفصل الحالي
- قرار الأدمن
- الخدمة المركزية

## 25. التوصية النهائية

أفضل تصميم متوازن لمشروعكم هو:

- الاستمرار باستخدام `quick.AcademicYear` كمصدر الحقيقة للفصل.
- إنشاء تطبيق جديد `academic_years` مسؤول عن:
  - الوصول
  - التفعيل
  - الحماية
  - الجلسة
  - الترحيل
- إضافة `academic_year` إلى الموديلات الأكاديمية والمحاسبية الأساسية.
- إبقاء `Account` كدليل حسابات مشترك، مع فصل اختياري فقط للحسابات التشغيلية الفرعية.
- تنفيذ الترحيل كـ transactional clone مضبوط، لا كحذف من الفصل القديم.

## 26. ماذا أنفذ أولًا داخل الكود

الأولوية العملية:

1. إنشاء تطبيق `academic_years`
2. إضافة `AcademicYearAccess` و`AcademicYearSystemState`
3. إضافة session flow + middleware
4. إضافة `academic_year` إلى `accounts.Course`
5. إضافة `academic_year` إلى `Studentenrollment` و`StudentReceipt` و`JournalEntry`
6. كتابة migration/backfill آمنة
7. تعديل أهم القوائم والتقارير
8. بناء transfer preview
9. بناء transfer execute مع `transaction.atomic()`

إذا أردنا البدء بالتنفيذ الفعلي في المرحلة التالية، فأفضل نقطة انطلاق هي:

- scaffold تطبيق `academic_years`
- ربطه بـ `settings.py` و`urls.py`
- ثم تنفيذ الطبقة الأولى: `system state + session + middleware`
