# نقل قيود الطلاب بدون فصول (Journal Entry Transfer System)

## المشكلة المعالجة ✅

عند وجود قيود محاسبية (قيود التسجيل والدفع) بدون فصل محدد، كان يصعب:
1. **عرضها** - لا توجد طريقة سهلة للبحث عن القيود بدون فصول
2. **نقلها** - نقل كامل قيود التسجيل والدفع للطالب فقط إلى فصل جديد

## الحل المُنفذ 🎯

### 1. نماذج جديدة (Models)

**`JournalEntryTransferBatch`** - دفعة نقل القيود
- تخزين معلومات دفعة النقل
- تتبع الفصل الهدف والحالة والسجلات

**`JournalEntryTransferItem`** - عنصر في دفعة النقل
- تمثيل كل قيد تم اختياره للنقل
- تتبع حالة القيد وقيد الهدف المُنشأ

### 2. خدمة النقل (Service)

**`JournalEntryTransferService`** - معالج النقل الرئيسي
- `build_preview()` - معاينة القيود المراد نقلها
- `execute()` - تنفيذ النقل الفعلي
- `_transfer_journal_entry()` - نقل قيد واحد
- `_resolve_target_account()` - إيجاد/إنشاء الحساب المقابل

### 3. النماذج (Forms)

**`JournalEntryTransferBatchForm`**
- اختيار الفصل الهدف
- عرض قيود التسجيل والدفع فقط التي بدون فصول
- التحقق من البيانات

### 4. الـ Views

```
JournalEntryTransferBatchListView
  ↓ (عرض قائمة دفعات النقل)

JournalEntryTransferBatchCreateView
  ↓ (إنشاء دفعة جديدة)

JournalEntryTransferBatchDetailView
  ↓ (عرض التفاصيل والمعاينة)

JournalEntryTransferBatchExecuteView
  ↓ (تنفيذ النقل الفعلي)
```

### 5. URLs الجديدة

```python
# نقل القيود بدون فصول
path("journal-entries-transfer/", ...)                          # قائمة
path("journal-entries-transfer/create/", ...)                   # إنشاء
path("journal-entries-transfer/<int:pk>/", ...)                 # تفاصيل
path("journal-entries-transfer/<int:pk>/execute/", ...)         # تنفيذ
```

## طريقة الاستخدام 📝

### خطوة 1: إنشاء دفعة نقل
1. اذهب إلى `/academic-years/journal-entries-transfer/create/`
2. اختر **الفصل الهدف** (الفصل الذي تريد نقل القيود إليه)
3. اختر **القيود المراد نقلها** (سيظهر فقط قيود التسجيل والدفع بدون فصل)
4. أضف ملاحظات إذا أردت
5. اضغط **"إنشاء المعاينة"**

### خطوة 2: معاينة
- سيتم عرض:
  - عدد القيود المختارة
  - عدد المعاملات (transactions)
  - الإجمالي المالي
- يمكنك العودة وتعديل الاختيارات

### خطوة 3: التنفيذ
1. اضغط زر **"تنفيذ النقل"**
2. سيتم:
   - نسخ كل قيد إلى الفصل الجديد
   - نسخ جميع المعاملات (transactions)
   - إيجاد/إنشاء الحسابات المقابلة
   - ترحيل القيد إذا كان مرحل في الأصل
3. سيظهر سجل بالعمليات المنفذة

## البيانات المنقولة 📦

### ✅ ينقل:
- **قيود التسجيل** (enrollment journal entries)
- **قيود الدفع** (payment journal entries)
- **جميع المعاملات** المرتبطة بهذه القيود
- **حالة الترحيل** (posted/unposted)
- **الأرصدة والحسابات** المطابقة

### ❌ لا ينقل:
- القيود الأخرى (يدوية، تسويات، إلخ)
- أي بيانات غير مرتبطة بالطالب مباشرة

## السجلات والتتبع 📊

كل عملية نقل تُسجل مع:
- **التاريخ والوقت**
- **المستخدم الذي نفذ العملية**
- **نوع السجل** (معلومة، تحذير، خطأ)
- **التفاصيل والبيانات** (JSON)

## الأمان والتحقق ✔️

- **تحقق من البيانات** قبل الحفظ
- **حماية القيم الفارغة** والقيم غير الصحيحة
- **إعادة المحاولة** في حالة الفشل
- **معاينة آمنة** قبل التنفيذ الفعلي
- **تسجيل مفصل** لجميع العمليات

## المتطلبات 🔧

### في Database:
```sql
-- النماذج الجديدة سيتم إنشاؤها عند تطبيق migrations
python manage.py migrate academic_years
```

### الاستثناءات المتعلقة بـ ForeignKey:
```python
from accounts.models import JournalEntry, Transaction, Account
```

## أمثلة من السجلات 📋

```
INFO - بدء تنفيذ نقل القيود.
INFO - نتيجة المعاينة قبل التنفيذ.
INFO - تم نقل القيد JE-000123
INFO - اكتمل تنفيذ نقل القيود بنجاح.
```

## Troubleshooting 🔍

### إذا لم تظهر قيود في الخيارات:
✓ تأكد من وجود قيود بـ `academic_year IS NULL`
✓ تأكد من أن القيود من نوع `enrollment` أو `PAYMENT`
✓ تأكد من أن الفصل الهدف موجود

### إذا فشل النقل:
✓ تحقق من السجلات للبحث عن رسالة الخطأ
✓ تأكد من صحة الحسابات
✓ تأكد من أن الفصل الهدف صحيح

## ملفات معدلة ✏️

1. **models.py** - إضافة JournalEntryTransferBatch و JournalEntryTransferItem
2. **forms.py** - إضافة JournalEntryTransferBatchForm
3. **views.py** - إضافة 4 views جديدة
4. **urls.py** - إضافة 4 URLs جديدة
5. **admin.py** - تسجيل النماذج الجديدة في الإدارة

## ملفات جديدة ✨

1. **services/journal_entry_transfers.py** - خدمة النقل
2. **templates/academic_years/journal_entry_transfer_list.html** - قائمة الدفعات
3. **templates/academic_years/journal_entry_transfer_create.html** - نموذج الإنشاء
4. **templates/academic_years/journal_entry_transfer_detail.html** - عرض التفاصيل

---

## التطبيق 🚀

لتطبيق الحل:
1. تطبيق migrations: `python manage.py migrate`
2. اختبار النموذج عبر واجهة الإدارة
3. استخدام الـ views الجديدة

---

**آخر تحديث:** 21 مايو 2026
