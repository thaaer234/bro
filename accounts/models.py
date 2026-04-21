from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.urls import reverse
from django.utils import timezone
from decimal import Decimal, InvalidOperation
from django.core.exceptions import ValidationError
from django.db.models import Sum, Q
from django.db.models.signals import pre_delete
from django.dispatch import receiver
import uuid


class NumberSequence(models.Model):
    """Track sequential numbers for various document types"""
    key = models.CharField(max_length=64, unique=True)
    last_value = models.BigIntegerField(default=0)

    @classmethod
    def next_value(cls, key):
        seq, created = cls.objects.get_or_create(key=key, defaults={'last_value': 0})
        seq.last_value += 1
        seq.save(update_fields=['last_value'])
        return seq.last_value


class Account(models.Model):
    ACCOUNT_TYPE_CHOICES = [
        ('ASSET', 'الأصول / Assets'),
        ('LIABILITY', 'الخصوم / Liabilities'),
        ('EQUITY', 'حقوق الملكية / Equity'),
        ('REVENUE', 'الإيرادات / Revenue'),
        ('EXPENSE', 'المصروفات / Expenses'),
    ]

    code = models.CharField(max_length=20, unique=True, verbose_name='رمز الحساب / Account Code')
    name = models.CharField(max_length=200, verbose_name='اسم الحساب / Account Name')
    name_ar = models.CharField(max_length=200, blank=True, verbose_name='الاسم بالعربية / Arabic Name')
    account_type = models.CharField(max_length=20, choices=ACCOUNT_TYPE_CHOICES, verbose_name='نوع الحساب / Account Type')
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children', verbose_name='الحساب الأب / Parent Account')
    description = models.TextField(blank=True, verbose_name='الوصف / Description')
    is_active = models.BooleanField(default=True, verbose_name='نشط / Active')
    balance = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='الرصيد / Balance')
    # ===========
    
    # إضافة حقل مركز الكلفة
    cost_center = models.ForeignKey(
        'CostCenter', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='accounts',
        verbose_name='مركز التكلفة / Cost Center'
    )
    academic_year = models.ForeignKey(
        'quick.AcademicYear',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='accounts_accounts',
        verbose_name='الفصل الدراسي / Academic Year',
    )
    
    # Special account flags
    is_course_account = models.BooleanField(default=False, verbose_name='حساب الدورة / Course Account')
    course_name = models.CharField(max_length=200, blank=True, verbose_name='اسم الدورة / Course Name')
    is_student_account = models.BooleanField(default=False, verbose_name='حساب الطالب / Student Account')
    student_name = models.CharField(max_length=200, blank=True, verbose_name='اسم الطالب / Student Name')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'الحساب / Account'
        verbose_name_plural = 'الحسابات / Accounts'
        ordering = ['code']

    def __str__(self):
        return f"{self.code} - {self.display_name}"

    @property
    def display_name(self):
        return self.name_ar if self.name_ar else self.name

    def get_absolute_url(self):
        return reverse('accounts:account_detail', kwargs={'pk': self.pk})

    def get_debit_balance(self):
        """Get total debit amount for this account"""
        return self.transactions.filter(is_debit=True).aggregate(
            total=Sum('amount'))['total'] or Decimal('0.00')

    def get_credit_balance(self):
        """Get total credit amount for this account"""
        return self.transactions.filter(is_debit=False).aggregate(
            total=Sum('amount'))['total'] or Decimal('0.00')

    def get_net_balance(self):
        """Calculate net balance based on account type"""
        debit_total = self.get_debit_balance()
        credit_total = self.get_credit_balance()
        
        if self.account_type in ['ASSET', 'EXPENSE']:
            return debit_total - credit_total
        else:  # LIABILITY, EQUITY, REVENUE
            return credit_total - debit_total

    @property
    def rollup_balance(self):
        """Get balance including children accounts (with recursion protection)"""
        return self._calculate_rollup_balance(set())
    
    def _calculate_rollup_balance(self, visited_ids):
        """Calculate rollup balance with recursion protection"""
        if self.id in visited_ids:
            return Decimal('0.00')  # Prevent infinite recursion
        
        visited_ids.add(self.id)
        own_balance = self.get_net_balance()
        children_balance = Decimal('0.00')
        
        for child in self.children.all():
            children_balance += child._calculate_rollup_balance(visited_ids.copy())
        
        return own_balance + children_balance

    def transactions_with_descendants(self):
        """Get all transactions for this account and its descendants"""
        account_ids = [self.id]
        
        def collect_children(account):
            for child in account.children.all():
                account_ids.append(child.id)
                collect_children(child)
        
        collect_children(self)
        return Transaction.objects.filter(account_id__in=account_ids)

    def recalculate_tree_balances(self):
        """Recalculate balances for this account and all its children"""
        # Recalculate children first (bottom-up)
        for child in self.children.all():
            child.recalculate_tree_balances()
        
        # Then recalculate this account
        self.balance = self.get_net_balance()
        self.save(update_fields=['balance'])

    @classmethod
    def rebuild_all_balances(cls):
        """Rebuild all account balances from transactions"""
        for account in cls.objects.all():
            account.balance = account.get_net_balance()
            account.save(update_fields=['balance'])

    @classmethod
    def get_or_create_student_ar_account(cls, student, course):
        """Get or create AR account for student; must be scoped to a course"""
        if not course:
            raise ValueError("Course is required for student AR account creation")
        
        # Ensure AR parent exists
        ar_parent, _ = cls.objects.get_or_create(
            code='1251',
            defaults={
                'name': 'Accounts Receivable - Students',
                'name_ar': 'ذمم الطلاب المدينة',
                'account_type': 'ASSET',
                'is_active': True,
            }
        )
        
        # Resolve student and course names
        student_name = getattr(student, 'full_name', None) or getattr(student, 'name', '') or getattr(student, 'student_name', '') or str(student)
        course_name = getattr(course, 'name', '')
        course_name_ar = getattr(course, 'name_ar', None) or course_name
        
        # Create or get course-level AR account first
        course_code = f"1251-{course.id:03d}"
        course_account, _ = cls.objects.get_or_create(
            code=course_code,
            defaults={
                'name': f"Accounts Receivable - {course_name}",
                'name_ar': f"ذمم طلاب دورة {course_name_ar}",
                'account_type': 'ASSET',
                'parent': ar_parent,
                'is_course_account': True,
                'course_name': course_name,
                'academic_year': getattr(course, 'academic_year', None),
                'is_active': True,
            }
        )
        
        # Create or get student-specific AR account under the course
        # التنسيق: 1251-الدورة-الطالب
        student_code = f"1251-{course.id:03d}-{student.id:03d}"
        student_account, created = cls.objects.get_or_create(
            code=student_code,
            defaults={
                'name': f"AR - {student_name} - {course_name}",
                'name_ar': f"ذمة {student_name} - {course_name_ar}",
                'account_type': 'ASSET',
                'parent': course_account,  # مرتبط بحساب الدورة
                'is_student_account': True,
                'student_name': student_name,
                'course_name': course_name,
                'academic_year': getattr(course, 'academic_year', None),
                'is_active': True,
            }
        )
        
        return student_account
    @classmethod
    def get_student_ar_account_for_course(cls, student, course):
        """Get student AR account for a specific course (without creating)"""
        if not course or not student:
            return None
        
        # بناء الكود المتوقع
        student_code = f"1251-{course.id:03d}-{student.id:03d}"
        
        try:
            # البحث عن الحساب
            account = cls.objects.get(
                code=student_code,
                is_student_account=True,
                is_active=True
            )
            return account
        except cls.DoesNotExist:
            return None

    @classmethod
    def get_or_create_course_deferred_account(cls, course):
        """Get or create deferred revenue account for course"""
        # Ensure deferred revenue parent exists
        deferred_parent, _ = cls.objects.get_or_create(
            code='21',
            defaults={
                'name': 'Deferred Revenue - Courses',
                'name_ar': 'إيرادات مؤجلة - الدورات',
                'account_type': 'LIABILITY',
                'is_active': True,
            }
        )
        # إنشاء حساب الإيرادات المؤجلة الخاص بالدورة
        course_code = f"21001-{course.id:03d}"
        account, created = cls.objects.get_or_create(
            code=course_code,
            defaults={
                'name': f"Deferred Revenue - {course.name}",
                'name_ar': f"إيرادات مؤجلة - {getattr(course, 'name_ar', None) or course.name}",
                'account_type': 'LIABILITY',
                'parent': deferred_parent,
                'is_course_account': True,
                'course_name': course.name,
                'academic_year': getattr(course, 'academic_year', None),
                'is_active': True,
            }
        )
        return account 

    @classmethod
    def get_or_create_course_account(cls, course):
        """Get or create revenue account for course"""
        Revenue, _ = cls.objects.get_or_create(
            code='4',
            defaults={
                'name': 'Revenue - Courses',
                'name_ar': 'إيرادات  - الدورات',
                'account_type': 'REVENUE',
                'is_active': True,
            }
        )

        # إنشاء حساب الإيرادات  الخاص بالدورة
        course_code = f"4101-{course.id:03d}"
        account, created = cls.objects.get_or_create(
            code=course_code,
            defaults={
                'name': f"Revenue - {course.name}",
                'name_ar': f"إيرادات دورة - {getattr(course, 'name_ar', None) or course.name}",
                'account_type': 'REVENUE',
                'parent': Revenue,
                'is_course_account': True,
                'course_name': course.name,
                'academic_year': getattr(course, 'academic_year', None),
                'is_active': True,
            }
        )
        return account
    # ==========================
    @classmethod
    def get_or_create_withdrawal_revenue_account(cls, student, course):
        """إنشاء أو جلب حساب إيرادات سحب الطالب"""
        # الحساب الرئيسي لإيرادات السحب (4201)
        parent_account, _ = cls.objects.get_or_create(
            code='4201',
            defaults={
                'name': 'Withdrawal Revenue - Students',
                'name_ar': 'إيرادات انسحاب طلاب',
                'account_type': 'REVENUE',
                'is_active': True,
            }
        )
        
        # حساب الطالب المحدد
        student_name = getattr(student, 'full_name', None) or getattr(student, 'name', '') or str(student)
        course_name = getattr(course, 'name', '') or str(course)
        
        account_code = f"4201-{course.id:03d}-{student.id:03d}"
        account, created = cls.objects.get_or_create(
            code=account_code,
            defaults={
                'name': f'Withdrawal Revenue - {student_name} - {course_name}',
                'name_ar': f'إيرادات انسحاب - {student_name} - {course_name}',
                'account_type': 'REVENUE',
                'parent': parent_account,
                'academic_year': getattr(course, 'academic_year', None),
                'is_active': True,
            }
        )
        return account

    @classmethod
    def get_or_create_followup_revenue_account(cls):
        """Get or create the external revenue account for follow-up students."""
        revenue_parent, _ = cls.objects.get_or_create(
            code='4',
            defaults={
                'name': 'Revenue',
                'name_ar': 'الإيرادات',
                'account_type': 'REVENUE',
                'is_active': True,
            }
        )
        account, _ = cls.objects.get_or_create(
            code='4199-FOLLOWUP',
            defaults={
                'name': 'Follow-up Students Revenue',
                'name_ar': 'إيراد طلاب المتابعة',
                'account_type': 'REVENUE',
                'parent': revenue_parent,
                'is_active': True,
            }
        )
        update_fields = []
        if account.parent_id != revenue_parent.id:
            account.parent = revenue_parent
            update_fields.append('parent')
        if account.account_type != 'REVENUE':
            account.account_type = 'REVENUE'
            update_fields.append('account_type')
        if not account.is_active:
            account.is_active = True
            update_fields.append('is_active')
        if update_fields:
            account.save(update_fields=update_fields)
        return account



## ====================
# الطلاب السريعين 
# ====================
# accounts/models.py - إضافة إلى نموذج Account

    # ... الكود الحالي ...
    
    @classmethod
    def get_or_create_quick_student_ar_account(cls, student):
        """إنشاء أو جلب حساب ذمم الطالب السريع"""
        # الحساب الرئيسي لذمم الطلاب السريعين
        ar_parent, _ = cls.objects.get_or_create(
            code='1252',
            defaults={
                'name': 'Accounts Receivable - Quick Students',
                'name_ar': 'ذمم الطلاب السريعين المدينة',
                'account_type': 'ASSET',
                'is_active': True,
            }
        )
        
        # حساب الطالب السريع المحدد
        student_code = f"1252-{student.id:03d}"
        account, created = cls.objects.get_or_create(
            code=student_code,
            defaults={
                'name': f"AR - Quick Student - {student.full_name}",
                'name_ar': f"ذمة طالب سريع - {student.full_name}",
                'account_type': 'ASSET',
                'parent': ar_parent,
                'is_student_account': True,
                'student_name': student.full_name,
                'is_active': True,
            }
        )
        return account
    
    @classmethod
    def get_or_create_quick_course_deferred_account(cls, course):
        """إنشاء أو جلب حساب الإيرادات المؤجلة للدورة السريعة"""
        # الحساب الرئيسي للإيرادات المؤجلة للدورات السريعة
        deferred_parent, _ = cls.objects.get_or_create(
            code='2151',
            defaults={
                'name': 'Deferred Revenue - Quick Courses',
                'name_ar': 'إيرادات مؤجلة - الدورات السريعة',
                'account_type': 'LIABILITY',
                'is_active': True,
            }
        )
        
        # حساب الدورة السريعة المحددة
        course_code = f"2151-{course.id:03d}"
        account, created = cls.objects.get_or_create(
            code=course_code,
            defaults={
                'name': f"Deferred Revenue - Quick Course - {course.name}",
                'name_ar': f"إيرادات مؤجلة - دورة سريعة - {course.name_ar or course.name}",
                'account_type': 'LIABILITY',
                'parent': deferred_parent,
                'is_course_account': True,
                'course_name': course.name,
                'is_active': True,
            }
        )
        return account
    
    @classmethod
    def get_or_create_quick_course_revenue_account(cls, course):
        """إنشاء أو جلب حساب إيرادات الدورة السريعة"""
        # الحساب الرئيسي لإيرادات الدورات السريعة
        revenue_parent, _ = cls.objects.get_or_create(
            code='4111',
            defaults={
                'name': 'Revenue - Quick Courses',
                'name_ar': 'إيرادات الدورات السريعة',
                'account_type': 'REVENUE',
                'is_active': True,
            }
        )
        
        # حساب الدورة السريعة المحددة
        course_code = f"4111-{course.id:03d}"
        account, created = cls.objects.get_or_create(
            code=course_code,
            defaults={
                'name': f"Revenue - Quick Course - {course.name}",
                'name_ar': f"إيرادات دورة سريعة - {course.name_ar or course.name}",
                'account_type': 'REVENUE',
                'parent': revenue_parent,
                'is_course_account': True,
                'course_name': course.name,
                'is_active': True,
            }
        )
        return account

   


class CostCenter(models.Model):
    COST_CENTER_TYPE_CHOICES = [
        ('ACADEMIC', 'أكاديمي / Academic'),
        ('ADMINISTRATIVE', 'إداري / Administrative'),
        ('OPERATIONAL', 'تشغيلي / Operational'),
        ('SUPPORT', 'دعم / Support'),
        ('MARKETING', 'تسويقي / Marketing'),
    ]
    
    code = models.CharField(max_length=20, unique=True, verbose_name='الرمز / Code')
    name = models.CharField(max_length=100, verbose_name='الاسم / Name')
    name_ar = models.CharField(max_length=100, blank=True, verbose_name='الاسم بالعربية / Arabic Name')
    description = models.TextField(blank=True, verbose_name='الوصف / Description')
    cost_center_type = models.CharField(max_length=20, choices=COST_CENTER_TYPE_CHOICES, default='ACADEMIC', verbose_name='نوع مركز التكلفة / Cost Center Type')
    is_active = models.BooleanField(default=True, verbose_name='نشط / Active')
    
    # Manager information
    manager_name = models.CharField(max_length=200, blank=True, verbose_name='اسم المدير / Manager Name')
    manager_phone = models.CharField(max_length=20, blank=True, verbose_name='هاتف المدير / Manager Phone')
    manager_email = models.EmailField(blank=True, verbose_name='بريد المدير / Manager Email')
    
    # Budget information
    annual_budget = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='الميزانية السنوية / Annual Budget')
    monthly_budget = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='الميزانية الشهرية / Monthly Budget')
    actual_annual_spent = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='المصروف الفعلي السنوي / Actual Annual Spent')
    actual_monthly_spent = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='المصروف الفعلي الشهري / Actual Monthly Spent')
    
    # Performance metrics
    target_revenue = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='الإيراد المستهدف / Target Revenue')
    target_profit_margin = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name='هامش الربح المستهدف % / Target Profit Margin %')
    opening_balance = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="رصيد الافتتاح")
    # Dates
    start_date = models.DateField(null=True, blank=True, verbose_name='تاريخ البدء / Start Date')
    end_date = models.DateField(null=True, blank=True, verbose_name='تاريخ الانتهاء / End Date')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'مركز التكلفة / Cost Center'
        verbose_name_plural = 'مراكز التكلفة / Cost Centers'
        ordering = ['code']
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['cost_center_type']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return f"{self.code} - {self.name_ar if self.name_ar else self.name}"
    
    def get_absolute_url(self):
        return reverse('accounts:cost_center_detail', kwargs={'pk': self.pk})
    
    # ===== REVENUE METHODS =====

    def get_other_expenses(self, start_date, end_date):
        """
        حساب إجمالي المصاريف الأخرى لفترة محددة
        """
        try:
            from .models import OtherExpense  # تأكد من المسار الصحيح
            total = OtherExpense.objects.filter(
                cost_center=self,
                date__range=[start_date, end_date]
            ).aggregate(total=Sum('amount'))['total']
            return total if total else 0
        except Exception as e:
            return 0



    # الحقول الموجودة لديك...
    
    def get_opening_balance(self, start_date=None, end_date=None):
        """رصيد الافتتاح - مع معالجة القيم الافتراضية"""
        try:
            # إذا ما بدك تستخدم التواريخ، ممكن ترجع قيمة ثابتة
            return self.opening_balance or 0
        except:
            return 0

    def get_cash_inflow(self, start_date, end_date):
        """إجمالي التدفقات النقدية الداخلة"""
        try:
            total = self.cashinflow_set.filter(
                date__range=[start_date, end_date]
            ).aggregate(total=Sum('amount'))['total']
            return total or 0
        except:
            return 0

    def get_cash_outflow(self, start_date, end_date):
        """إجمالي التدفقات النقدية الخارجة"""
        try:
            total = self.cashoutflow_set.filter(
                date__range=[start_date, end_date]
            ).aggregate(total=Sum('amount'))['total']
            return total or 0
        except:
            return 0

    def get_other_expenses(self, start_date, end_date):
        """المصاريف الأخرى"""
        try:
            total = self.otherexpense_set.filter(
                date__range=[start_date, end_date]
            ).aggregate(total=Sum('amount'))['total']
            return total or 0
        except:
            return 0

    def get_salary_expenses(self, start_date, end_date):
        """مصاريف الرواتب"""
        try:
            total = self.salary_set.filter(
                date__range=[start_date, end_date]
            ).aggregate(total=Sum('amount'))['total']
            return total or 0
        except:
            return 0

    def get_operational_expenses(self, start_date, end_date):
        """المصاريف التشغيلية"""
        try:
            total = self.operationalexpense_set.filter(
                date__range=[start_date, end_date]
            ).aggregate(total=Sum('amount'))['total']
            return total or 0
        except:
            return 0

    def get_closing_balance(self, start_date, end_date):
        """رصيد الإغلاق"""
        try:
            opening = self.get_opening_balance(start_date, end_date)
            inflow = self.get_cash_inflow(start_date, end_date)
            outflow = self.get_cash_outflow(start_date, end_date)
            return opening + inflow - outflow
        except:
            return 0

 

    def get_total_expenses(self, start_date, end_date):
        """إجمالي المصاريف"""
        salary = self.get_salary_expenses(start_date, end_date)
        operational = self.get_operational_expenses(start_date, end_date)
        other = self.get_other_expenses(start_date, end_date)
        return salary + operational + other

    def get_net_income(self, start_date, end_date):
        """صافي الدخل"""
        revenue = self.get_total_revenue(start_date, end_date)
        expenses = self.get_total_expenses(start_date, end_date)
        return revenue - expenses
    # الحقول الموجودة لديك...
    
    def get_cash_inflow(self, start_date, end_date):
        """احصل على إجمالي التدفقات النقدية الداخلة"""
        try:
            # استبدل بنموذجك الفعلي
            total = self.cash_inflows.filter(
                date__range=[start_date, end_date]
            ).aggregate(total=Sum('amount'))['total']
            return total or 0
        except:
            return 0

    def get_cash_outflow(self, start_date, end_date):
        """احصل على إجمالي التدفقات النقدية الخارجة"""
        try:
            # استبدل بنموذجك الفعلي
            total = self.cash_outflows.filter(
                date__range=[start_date, end_date]
            ).aggregate(total=Sum('amount'))['total']
            return total or 0
        except:
            return 0

    def get_other_expenses(self, start_date, end_date):
        """احصل على إجمالي المصاريف الأخرى"""
        try:
            total = self.other_expenses.filter(
                date__range=[start_date, end_date]
            ).aggregate(total=Sum('amount'))['total']
            return total or 0
        except:
            return 0

    def get_salary_expenses(self, start_date, end_date):
        """احصل على إجمالي مصاريف الرواتب"""
        try:
            total = self.salaries.filter(
                date__range=[start_date, end_date]
            ).aggregate(total=Sum('amount'))['total']
            return total or 0
        except:
            return 0

    def get_operational_expenses(self, start_date, end_date):
        """احصل على إجمالي المصاريف التشغيلية"""
        try:
            total = self.operational_expenses.filter(
                date__range=[start_date, end_date]
            ).aggregate(total=Sum('amount'))['total']
            return total or 0
        except:
            return 0

    # دوال إضافية قد تحتاجها


    def get_total_expenses(self, start_date, end_date):
        """إجمالي المصاريف (يمكن أن يكون مجموع عدة أنواع)"""
        salary = self.get_salary_expenses(start_date, end_date)
        operational = self.get_operational_expenses(start_date, end_date)
        other = self.get_other_expenses(start_date, end_date)
        return salary + operational + other

    # الحقول الموجودة لديك...
    
    def get_cash_inflow(self, start_date, end_date):
        """
        حساب إجمالي التدفقات النقدية الداخلة
        """
        try:
            # استبدل CashInflow بنموذج التدفقات النقدية الفعلي لديك
            from .models import CashInflow
            total = CashInflow.objects.filter(
                cost_center=self,
                date__range=[start_date, end_date]
            ).aggregate(total=Sum('amount'))['total']
            return total if total else 0
        except Exception as e:
            return 0

    def get_other_expenses(self, start_date, end_date):
        """
        حساب إجمالي المصاريف الأخرى
        """
        try:
            from .models import OtherExpense
            total = OtherExpense.objects.filter(
                cost_center=self,
                date__range=[start_date, end_date]
            ).aggregate(total=Sum('amount'))['total']
            return total if total else 0
        except Exception as e:
            return 0

    def get_salary_expenses(self, start_date, end_date):
        """
        حساب إجمالي مصاريف الرواتب
        """
        try:
            from employ.models import Salary  # أو من أي app آخر
            total = Salary.objects.filter(
                cost_center=self,
                date__range=[start_date, end_date]
            ).aggregate(total=Sum('amount'))['total']
            return total if total else 0
        except Exception as e:
            return 0

    def get_operational_expenses(self, start_date, end_date):
        """
        حساب إجمالي المصاريف التشغيلية
        """
        try:
            from .models import OperationalExpense
            total = OperationalExpense.objects.filter(
                cost_center=self,
                date__range=[start_date, end_date]
            ).aggregate(total=Sum('amount'))['total']
            return total if total else 0
        except Exception as e:
            return 0
    def get_revenue_by_course(self, start_date=None, end_date=None):
        """تفصيل الإيرادات حسب الدورة"""
        revenue_data = []
        
        for course in self.courses.filter(is_active=True):
            course_revenue_account = Account.objects.filter(
                code=f'4101-{course.id:03d}'
            ).first()
            
            if course_revenue_account:
                revenue = course_revenue_account.get_net_balance()
                if revenue > 0:
                    revenue_data.append({
                        'course': course,
                        'revenue': revenue,
                        'enrollments': course.get_enrollment_count(start_date, end_date),
                        'course_price': course.price
                    })
        
        return revenue_data
    def get_total_revenue(self, start_date=None, end_date=None):
        """إجمالي الإيرادات مع معالجة القيم الافتراضية"""
        try:
            # استخدام القيم الافتراضية إذا لم يتم توفيرها
            if not start_date or not end_date:
                # آخر 30 يوم كقيمة افتراضية
                end_date = timezone.now().date()
                start_date = end_date - timedelta(days=30)
            
            # البحث في المعاملات المرتبطة بمركز التكلفة
            total = self.transactions.filter(
                journal_entry__date__range=[start_date, end_date],
                is_debit=False  # الإيرادات بتكون دائن
            ).aggregate(total=Sum('amount'))['total']
            
            return total if total else 0
        except Exception as e:
            print(f"Error in get_total_revenue: {e}")
            return 0
    # ===== TEACHER SALARIES METHODS =====
    def get_teacher_salaries(self, start_date=None, end_date=None):
        """رواتب جميع مدرسي مركز التكلفة"""
        from django.db.models import Sum
        total_salaries = Decimal('0.00')
        
        # جميع المدرسين المرتبطين بدورات مركز التكلفة
        for teacher in self.get_teacher_list():
            # راتب المدرس من الحساب 501 (رواتب المدرسين)
            teacher_salary_account = Account.objects.filter(
                code=f'501-{teacher.id:03d}'
            ).first()
            
            if teacher_salary_account:
                salary = teacher_salary_account.get_net_balance()
                total_salaries += salary
        
        return total_salaries
    
    def get_teacher_count(self):
        """عدد المدرسين في مركز التكلفة"""
        return len(self.get_teacher_list())
    
    def get_teacher_list(self):
        """قائمة جميع المدرسين في مركز التكلفة"""
        teachers = []
        
        for course in self.courses.filter(is_active=True):
            assignments = course.courseteacherassignment_set.filter(is_active=True)
            for assignment in assignments:
                if assignment.teacher and assignment.teacher not in teachers:
                    teachers.append(assignment.teacher)
        
        return teachers
    
    def get_teacher_data(self):
        """بيانات مفصلة عن المدرسين"""
        teacher_data = []
        
        for teacher in self.get_teacher_list():
            # حساب راتب المدرس
            teacher_salary_account = Account.objects.filter(
                code=f'501-{teacher.id:03d}'
            ).first()
            salary = teacher_salary_account.get_net_balance() if teacher_salary_account else Decimal('0.00')
            
            # الدورات التي يدرسها في هذا المركز
            teacher_courses = teacher.assigned_courses.filter(cost_center=self)
            
            teacher_data.append({
                'teacher': teacher,
                'salary': salary,
                'courses': teacher_courses,
                'courses_count': teacher_courses.count()
            })
        
        return teacher_data
    
    # ===== EXPENSE METHODS =====
    def get_total_expenses(self, start_date=None, end_date=None):
        """إجمالي مصروفات مركز التكلفة"""
        teacher_salaries = self.get_teacher_salaries(start_date, end_date)
        operational_expenses = self.get_operational_expenses(start_date, end_date)
        return teacher_salaries + operational_expenses
    
    def get_operational_expenses(self, start_date=None, end_date=None):
        """المصاريف التشغيلية لمركز التكلفة"""
        from django.db.models import Sum
        
        # جميع المصاريف المرتبطة بمركز التكلفة (من جدول Transaction)
        expenses = Transaction.objects.filter(
            cost_center=self,
            is_debit=True  # المصاريف بتكون مدين
        )
        
        if start_date:
            expenses = expenses.filter(journal_entry__date__gte=start_date)
        if end_date:
            expenses = expenses.filter(journal_entry__date__lte=end_date)
        
        return expenses.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    
    def get_expenses_by_category(self, start_date=None, end_date=None):
        """تفصيل المصروفات حسب النوع"""
        expenses = {}
        
        # رواتب المدرسين
        expenses['teacher_salaries'] = self.get_teacher_salaries(start_date, end_date)
        
        # مصاريف تشغيلية
        expenses['operational'] = self.get_operational_expenses(start_date, end_date)
        
        return expenses
    
    # ===== PROFITABILITY METHODS =====
    def get_net_income(self, start_date=None, end_date=None):
        """صافي الدخل (الإيرادات - المصروفات)"""
        revenue = self.get_total_revenue(start_date, end_date)
        expenses = self.get_total_expenses(start_date, end_date)
        return revenue - expenses
    
    def get_profit_margin(self, start_date=None, end_date=None):
        """هامش الربح"""
        revenue = self.get_total_revenue(start_date, end_date)
        net_income = self.get_net_income(start_date, end_date)
        
        if revenue > 0:
            return (net_income / revenue) * 100
        return Decimal('0.00')
    
    def get_budget_utilization(self, start_date=None, end_date=None):
        """نسبة استخدام الميزانية"""
        if self.monthly_budget > 0:
            expenses = self.get_total_expenses(start_date, end_date)
            return (expenses / self.monthly_budget) * 100
        return Decimal('0.00')
    
    def get_budget_variance(self, start_date=None, end_date=None):
        """الانحراف عن الميزانية"""
        budgeted = self.monthly_budget
        actual = self.get_total_expenses(start_date, end_date)
        return actual - budgeted
    
    # ===== COURSE MANAGEMENT METHODS =====
    def get_course_count(self):
        """عدد الدورات المرتبطة"""
        return self.courses.filter(is_active=True).count()
    
    def get_active_courses(self):
        """الدورات النشطة"""
        return self.courses.filter(is_active=True)
    
    def get_course_performance(self, course):
        """أداء دورة محددة"""
        course_revenue_account = Account.objects.filter(
            code=f'4101-{course.id:03d}'
        ).first()
        revenue = course_revenue_account.get_net_balance() if course_revenue_account else Decimal('0.00')
        
        expenses = self.get_course_expenses(course)
        net_income = revenue - expenses
        enrollments = course.get_enrollment_count()
        
        return {
            'course': course,
            'revenue': revenue,
            'expenses': expenses,
            'net_income': net_income,
            'enrollments': enrollments,
            'revenue_per_student': revenue / enrollments if enrollments > 0 else Decimal('0.00'),
            'profit_margin': (net_income / revenue * 100) if revenue > 0 else Decimal('0.00')
        }
    
    def get_course_expenses(self, course, start_date=None, end_date=None):
        """تكاليف دورة محددة"""
        # رواتب مدرسي هذه الدورة
        teacher_salaries = Decimal('0.00')
        assignments = course.courseteacherassignment_set.filter(is_active=True)
        
        for assignment in assignments:
            teacher = assignment.teacher
            teacher_salary_account = Account.objects.filter(
                code=f'501-{teacher.id:03d}'
            ).first()
            if teacher_salary_account:
                teacher_salaries += teacher_salary_account.get_net_balance()
        
        # مصاريف تشغيلية مرتبطة بالدورة
        operational_expenses = Transaction.objects.filter(
            cost_center=self,
            journal_entry__description__icontains=course.name,
            is_debit=True
        )
        
        if start_date:
            operational_expenses = operational_expenses.filter(journal_entry__date__gte=start_date)
        if end_date:
            operational_expenses = operational_expenses.filter(journal_entry__date__lte=end_date)
            
        operational_total = operational_expenses.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        return teacher_salaries + operational_total
    
    # ===== COMPREHENSIVE REPORTING METHODS =====
    def get_financial_summary(self, start_date=None, end_date=None):
        """ملخص مالي شامل"""
        return {
            'total_revenue': self.get_total_revenue(start_date, end_date),
            'total_expenses': self.get_total_expenses(start_date, end_date),
            'teacher_salaries': self.get_teacher_salaries(start_date, end_date),
            'operational_expenses': self.get_operational_expenses(start_date, end_date),
            'net_income': self.get_net_income(start_date, end_date),
            'profit_margin': self.get_profit_margin(start_date, end_date),
            'budget_utilization': self.get_budget_utilization(start_date, end_date),
            'course_count': self.get_course_count(),
            'teacher_count': self.get_teacher_count()
        }
    
    def get_detailed_financial_report(self, start_date=None, end_date=None):
        """تقرير مالي مفصل"""
        financial_summary = self.get_financial_summary(start_date, end_date)
        
        # إضافة تفاصيل إضافية
        financial_summary.update({
            'revenue_by_course': self.get_revenue_by_course(start_date, end_date),
            'expenses_by_category': self.get_expenses_by_category(start_date, end_date),
            'teacher_data': self.get_teacher_data()
        })
        
        return financial_summary
    
    # ===== SAFE METHODS (with error handling) =====
   
    
    def get_teacher_salaries_safe(self, start_date=None, end_date=None):
        try:
            return self.get_teacher_salaries(start_date, end_date)
        except:
            return Decimal('0.00')
    
    def get_operational_expenses_safe(self, start_date=None, end_date=None):
        try:
            return self.get_operational_expenses(start_date, end_date)
        except:
            return Decimal('0.00')
    
    def get_total_expenses_safe(self, start_date=None, end_date=None):
        try:
            return self.get_total_expenses(start_date, end_date)
        except:
            return Decimal('0.00')
    
    def get_net_income_safe(self, start_date=None, end_date=None):
        try:
            return self.get_net_income(start_date, end_date)
        except:
            return Decimal('0.00')
    
    # ===== VALIDATION METHODS =====
    def clean(self):
        """التحقق من صحة البيانات"""
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValidationError({
                'end_date': 'تاريخ الانتهاء يجب أن يكون بعد تاريخ البدء'
            })
        
        if self.monthly_budget < 0:
            raise ValidationError({
                'monthly_budget': 'الميزانية الشهرية لا يمكن أن تكون سالبة'
            })
    
    def save(self, *args, **kwargs):
        """حفظ مع التحقق"""
        self.clean()
        super().save(*args, **kwargs)
    
    def get_courses_summary(self):
        """ملخص الدورات المرتبطة بمركز التكلفة"""
        try:
            courses = self.courses.filter(is_active=True)
            total_enrollments = 0
            total_course_revenue = Decimal('0.00')
            
            for course in courses:
                total_enrollments += course.get_enrollment_count()
                
                # حساب إيرادات الدورة من الحساب 4101
                course_revenue_account = Account.objects.filter(
                    code=f'4101-{course.id:03d}'
                ).first()
                if course_revenue_account:
                    total_course_revenue += course_revenue_account.get_net_balance()
            
            return {
                'total_courses': courses.count(),
                'active_courses': courses.filter(is_active=True).count(),
                'total_enrollments': total_enrollments,
                'total_course_revenue': total_course_revenue
            }
        except Exception as e:
            print(f"Error in get_courses_summary: {e}")
            return {
                'total_courses': 0,
                'active_courses': 0,
                'total_enrollments': 0,
                'total_course_revenue': Decimal('0.00')
            }
    
    def get_revenue_account(self):
        """الحصول على حساب إيرادات الدورة"""
        try:
            return Account.objects.get(code=f'4101-{self.id:03d}')
        except Account.DoesNotExist:
            return None
    
    def get_teacher_assignments(self):
        """الحصول على تعيينات المدرسين المرتبطة بمركز التكلفة"""
        try:
            from .models import CourseTeacherAssignment
            assignments = []
            for course in self.courses.filter(is_active=True):
                course_assignments = CourseTeacherAssignment.objects.filter(
                    course=course, 
                    is_active=True
                )
                assignments.extend(course_assignments)
            return assignments
        except:
            return []
    
    def get_transaction_history(self, limit=50):
        """سجل المعاملات المرتبطة بمركز التكلفة"""
        try:
            return Transaction.objects.filter(cost_center=self).select_related(
                'journal_entry', 'account'
            ).order_by('-journal_entry__date')[:limit]
        except:
            return []
    
    def get_accounts(self):
        """الحصول على جميع الحسابات المرتبطة بمركز التكلفة"""
        try:
            return self.accounts.all()
        except:
            return []
        


# ===========
    def get_teachers_by_branch(self):
        """جلب المدرسين حسب تخصص مركز التكلفة"""
        # تحديد تخصص مركز التكلفة من الاسم
        cost_center_name = self.name_ar or self.name
        
        if 'علمي' in cost_center_name:
            target_branch = 'SCIENCE'
        elif 'أدبي' in cost_center_name:
            target_branch = 'LITERARY'
        elif 'تاسع' in cost_center_name:
            target_branch = 'NINTH'
        elif 'تمهيدي' in cost_center_name:
            target_branch = 'PREPARATORY'
        else:
            target_branch = None
        
        if target_branch:
            # جلب المدرسين من هذا التخصص
            from employ.models import Teacher
            return Teacher.objects.filter(branch=target_branch)
        return Teacher.objects.none()
    
    def auto_assign_teachers_to_courses(self):
        """تعيين المدرسين تلقائياً للدورات المناسبة"""
        teachers = self.get_teachers_by_branch()
        courses = self.courses.filter(is_active=True)
        
        assigned_count = 0
        
        for teacher in teachers:
            for course in courses:
                # تحقق إذا المدرس مش معين أصلاً للدورة
                assignment_exists = CourseTeacherAssignment.objects.filter(
                    teacher=teacher,
                    course=course
                ).exists()
                
                if not assignment_exists:
                    # إنشاء تعيين جديد
                    CourseTeacherAssignment.objects.create(
                        teacher=teacher,
                        course=course,
                        start_date=timezone.now().date(),
                        is_active=True,
                        notes=f"تعيين تلقائي - تخصص {teacher.get_branch_display()}"
                    )
                    assigned_count += 1
        
        return assigned_count
    
    def get_auto_assigned_teachers(self):
        """جلب المدرسين المعينين تلقائياً"""
        teachers_data = []
        
        # جلب المدرسين حسب التخصص
        teachers = self.get_teachers_by_branch()
        
        for teacher in teachers:
            # حساب راتب المدرس
            teacher_salary_account = Account.objects.filter(
                code=f'501-{teacher.id:03d}'
            ).first()
            salary = teacher_salary_account.get_net_balance() if teacher_salary_account else Decimal('0.00')
            
            # الدورات التي يدرسها في هذا المركز
            teacher_courses = teacher.assigned_courses.filter(cost_center=self)
            
            teachers_data.append({
                'teacher': teacher,
                'salary': salary,
                'courses': teacher_courses,
                'courses_count': teacher_courses.count(),
                'branch': teacher.get_branch_display(),
                'is_auto_assigned': True
            })
        
        return teachers_data
    
    def get_branch_type(self):
        """تحديد نوع مركز التكلفة (علمي، أدبي، إلخ)"""
        cost_center_name = self.name_ar or self.name
        
        if 'علمي' in cost_center_name:
            return 'SCIENCE'
        elif 'أدبي' in cost_center_name:
            return 'LITERARY'
        elif 'تاسع' in cost_center_name:
            return 'NINTH'
        elif 'تمهيدي' in cost_center_name:
            return 'PREPARATORY'
        else:
            return 'OTHER'
        
    def get_teacher_count(self):
        """عدد المدرسين المرتبطين بمركز التكلفة"""
        try:
            # المدرسين من خلال التعيينات في الدورات
            teacher_ids = set()
            for course in self.courses.filter(is_active=True):
                assignments = course.courseteacherassignment_set.filter(is_active=True)
                for assignment in assignments:
                    if assignment.teacher:
                        teacher_ids.add(assignment.teacher.id)
            return len(teacher_ids)
        except:
            return 0
    
    def get_account_count(self):
        """عدد الحسابات المرتبطة بمركز التكلفة"""
        try:
            return self.accounts.count()
        except:
            return 0
    
    def get_student_count(self):
        """عدد الطلاب المرتبطين بمركز التكلفة"""
        try:
            from students.models import Student
            student_ids = set()
            for course in self.courses.filter(is_active=True):
                enrollments = course.enrollments.filter(is_completed=False)
                for enrollment in enrollments:
                    if enrollment.student:
                        student_ids.add(enrollment.student.id)
            return len(student_ids)
        except:
            return 0
    
    def get_transaction_count(self):
        """عدد المعاملات المرتبطة بمركز التكلفة"""
        try:
            return self.transaction_set.count()
        except:
            return 0
    
    def get_course_count(self):
        """عدد الدورات المرتبطة"""
        try:
            return self.courses.filter(is_active=True).count()
        except:
            return 0
    
    def get_enrollment_count(self):
        """عدد التسجيلات في دورات المركز"""
        try:
            total = 0
            for course in self.courses.filter(is_active=True):
                total += course.get_enrollment_count()
            return total
        except:
            return 0
    
    def get_detailed_statistics(self):
        """إحصائيات مفصلة لمركز التكلفة"""
        return {
            'teachers': self.get_teacher_count(),
            'accounts': self.get_account_count(),
            'students': self.get_student_count(),
            'transactions': self.get_transaction_count(),
            'courses': self.get_course_count(),
            'enrollments': self.get_enrollment_count(),
        }

class AccountingPeriod(models.Model):
    name = models.CharField(max_length=100, verbose_name='اسم الفترة / Period Name')
    start_date = models.DateField(verbose_name='تاريخ البداية / Start Date')
    end_date = models.DateField(verbose_name='تاريخ النهاية / End Date')
    academic_year = models.ForeignKey('quick.AcademicYear', on_delete=models.PROTECT, null=True, blank=True, related_name='accounts_periods', verbose_name='Academic Year')
    is_closed = models.BooleanField(default=False, verbose_name='مقفلة / Closed')
    closed_at = models.DateTimeField(null=True, blank=True, verbose_name='تاريخ الإقفال / Closed At')
    closed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='closed_periods', verbose_name='أُقفل بواسطة / Closed By')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'الفترة المحاسبية / Accounting Period'
        verbose_name_plural = 'الفترات المحاسبية / Accounting Periods'
        ordering = ['-start_date']

    def __str__(self):
        return self.name

    @property
    def is_current(self):
        today = timezone.now().date()
        return self.start_date <= today <= self.end_date


class JournalEntry(models.Model):
    ENTRY_TYPE_CHOICES = [
        ('MANUAL', 'يدوي / Manual'),
        ('enrollment', 'تسجيل / enrollment'),
        ('PAYMENT', 'دفع / Payment'),
        ('COMPLETION', 'إكمال / Completion'),
        ('EXPENSE', 'مصروف / Expense'),
        ('SALARY', 'راتب / Salary'),
        ('ADVANCE', 'سلفة / Advance'),
        ('ADJUSTMENT', 'تسوية / Adjustment'),
    ]

    reference = models.CharField(max_length=50, unique=True, verbose_name='المرجع / Reference')
    date = models.DateField(verbose_name='التاريخ / Date')
    description = models.TextField(verbose_name='الوصف / Description')
    entry_type = models.CharField(max_length=20, choices=ENTRY_TYPE_CHOICES, default='MANUAL', verbose_name='نوع القيد / Entry Type')
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='المبلغ الإجمالي / Total Amount')
    academic_year = models.ForeignKey(
        'quick.AcademicYear',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='accounts_journal_entries',
        verbose_name='الفصل الدراسي / Academic Year',
    )
    is_posted = models.BooleanField(default=False, verbose_name='مُرحل / Posted')
    posted_at = models.DateTimeField(null=True, blank=True, verbose_name='تاريخ الترحيل / Posted At')
    posted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='posted_entries', verbose_name='مُرحل بواسطة / Posted By')
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, verbose_name='أُنشئ بواسطة / Created By')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'قيد اليومية / Journal Entry'
        verbose_name_plural = 'قيود اليومية / Journal Entries'
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.reference} - {self.date}"

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = f"JE-{NumberSequence.next_value('journal_entry'):06d}"
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('accounts:journal_entry_detail', kwargs={'pk': self.pk})

    def get_total_debits(self):
        return self.transactions.filter(is_debit=True).aggregate(
            total=Sum('amount'))['total'] or Decimal('0.00')

    def get_total_credits(self):
        return self.transactions.filter(is_debit=False).aggregate(
            total=Sum('amount'))['total'] or Decimal('0.00')

    @property
    def is_balanced(self):
        return abs(self.get_total_debits() - self.get_total_credits()) < Decimal('0.01')

    def post_entry(self, user):
        """Post the journal entry and update account balances"""
        if self.is_posted:
            raise ValueError("Entry is already posted")
        
        if not self.is_balanced:
            raise ValueError("Entry is not balanced")
        
        self.is_posted = True
        self.posted_at = timezone.now()
        self.posted_by = user
        self.save(update_fields=['is_posted', 'posted_at', 'posted_by'])
        
        # Update account balances
        for transaction in self.transactions.all():
            transaction.account.recalculate_tree_balances()

    def reverse_entry(self, user, description=None):
        """Create a reversing journal entry"""
        if not self.is_posted:
            raise ValueError("Cannot reverse unposted entry")
        
        reversing_entry = JournalEntry.objects.create(
            date=timezone.now().date(),
            description=description or f"Reversal of {self.reference}",
            entry_type='ADJUSTMENT',
            total_amount=self.total_amount,
            academic_year=self.academic_year,
            created_by=user
        )
        
        # Create reversing transactions
        for transaction in self.transactions.all():
            Transaction.objects.create(
                journal_entry=reversing_entry,
                account=transaction.account,
                amount=transaction.amount,
                is_debit=not transaction.is_debit,  # Reverse the debit/credit
                description=f"Reversal: {transaction.description}",
                cost_center=transaction.cost_center
            )
        
        # Post the reversing entry
        reversing_entry.post_entry(user)
        return reversing_entry


class Transaction(models.Model):
    journal_entry = models.ForeignKey(JournalEntry, on_delete=models.CASCADE, related_name='transactions', verbose_name='قيد اليومية / Journal Entry')
    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name='transactions', verbose_name='الحساب / Account')
    amount = models.DecimalField(max_digits=15, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))], verbose_name='المبلغ / Amount')
    is_debit = models.BooleanField(verbose_name='مدين / Debit')
    description = models.CharField(max_length=500, blank=True, verbose_name='الوصف / Description')
    cost_center = models.ForeignKey(CostCenter, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='مركز التكلفة / Cost Center')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'المعاملة / Transaction'
        verbose_name_plural = 'المعاملات / Transactions'

    def __str__(self):
        return f"{self.account.code} - {self.amount} ({'Dr' if self.is_debit else 'Cr'})"

    @property
    def debit_amount(self):
        return self.amount if self.is_debit else Decimal('0.00')

    @property
    def credit_amount(self):
        return self.amount if not self.is_debit else Decimal('0.00')


class Course(models.Model):
    name = models.CharField(max_length=200, verbose_name='اسم الدورة / Course Name')
    name_ar = models.CharField(max_length=200, blank=True, verbose_name='الاسم بالعربية / Arabic Name')
    description = models.TextField(blank=True, verbose_name='الوصف / Description')
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='السعر / Price')
    duration_hours = models.PositiveIntegerField(null=True, blank=True, verbose_name='المدة بالساعات / Duration (Hours)')
    academic_year = models.ForeignKey(
        'quick.AcademicYear',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='accounts_courses',
        verbose_name='الفصل الدراسي / Academic Year',
    )
    
    # Cost center relationship
    cost_center = models.ForeignKey(CostCenter, on_delete=models.SET_NULL, null=True, blank=True, 
                                   related_name='courses', verbose_name='مركز التكلفة / Cost Center')
    
    # Teacher assignments
    assigned_teachers = models.ManyToManyField('employ.Teacher', through='CourseTeacherAssignment',
                                             related_name='assigned_courses', blank=True,
                                             verbose_name='المدرسون المعينون / Assigned Teachers')
    
    is_active = models.BooleanField(default=True, verbose_name='نشط / Active')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'الدورة / Course'
        verbose_name_plural = 'الدورات / Courses'
        ordering = ['name']

    def __str__(self):
        return self.name_ar if self.name_ar else self.name

    def get_absolute_url(self):
        return reverse('accounts:course_detail', kwargs={'pk': self.pk})

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        # Create deferred revenue account for new courses
        if is_new:
            Account.get_or_create_course_deferred_account(self)
    
    def get_total_teacher_salaries(self, start_date=None, end_date=None):
        """Get total teacher salaries for this course"""
        from django.db.models import Sum
        assignments = self.courseteacherassignment_set.all()
        
        if start_date:
            assignments = assignments.filter(start_date__gte=start_date)
        if end_date:
            assignments = assignments.filter(start_date__lte=end_date)
        
        total_salary = Decimal('0.00')
        for assignment in assignments:
            total_salary += assignment.calculate_total_salary()
        
        return total_salary
    
    def get_enrollment_count(self, start_date=None, end_date=None):
        """Get number of enrollments for this course"""
        enrollments = self.enrollments.all()
        
        if start_date:
            enrollments = enrollments.filter(enrollment_date__gte=start_date)
        if end_date:
            enrollments = enrollments.filter(enrollment_date__lte=end_date)
        
        return enrollments.count()
    
    def get_total_revenue(self, start_date=None, end_date=None):
        """Get total revenue from this course"""
        from django.db.models import Sum
        enrollments = self.enrollments.all()
        
        if start_date:
            enrollments = enrollments.filter(enrollment_date__gte=start_date)
        if end_date:
            enrollments = enrollments.filter(enrollment_date__lte=end_date)
        
        return enrollments.aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
    # الحقول الحالية...
    
    def auto_determine_cost_center(self):
        """تحديد مركز التكلفة تلقائياً من الاسم"""
        course_name = (self.name_ar or self.name).lower()
        
        keyword_mapping = {
            'علمي': ['علمي', 'العلمي', 'scientific', 'science', 'اساس', 'أساس'],
            'أدبي': ['أدبي', 'الأدبي', 'literary', 'literature'],
            'تاسع': ['تاسع', 'التاسع', 'ninth', 'grade9'],
            'تمهيدي': ['تمهيدي', 'التمهيدي', 'preparatory', 'prep'],
        }
        
        for branch_type, keywords in keyword_mapping.items():
            for keyword in keywords:
                if keyword.lower() in course_name:
                    # البحث عن مركز التكلفة المناسب
                    cost_center = CostCenter.objects.filter(
                        Q(name_ar__icontains=keyword) | Q(name__icontains=keyword)
                    ).first()
                    return cost_center
        
        return None
    
    def save(self, *args, **kwargs):
        """تحديث الحفظ لربط مركز التكلفة تلقائياً"""
        is_new = self.pk is None
        
        # إذا لم يكن هناك مركز تكلفة محدد، حاول تحديده تلقائياً
        if not self.cost_center:
            auto_cost_center = self.auto_determine_cost_center()
            if auto_cost_center:
                self.cost_center = auto_cost_center
        
        super().save(*args, **kwargs)
        
        # بعد الحفظ، تأكد من تعيين المدرسين المناسبين
        if is_new and self.cost_center:
            self.auto_assign_teachers()
    
    def auto_assign_teachers(self):
        """التعيين التلقائي للمدرسين بعد إنشاء الدورة"""
        from employ.models import Teacher
        
        if not self.cost_center:
            return
        
        cost_center_name = (self.cost_center.name_ar or self.cost_center.name).lower()
        
        branch_keywords = {
            'SCIENCE': ['علمي', 'العلمي', 'scientific', 'science', 'اساس', 'أساس'],
            'LITERARY': ['أدبي', 'الأدبي', 'literary', 'literature'],
            'NINTH': ['تاسع', 'التاسع', 'ninth', 'grade9'],
            'PREPARATORY': ['تمهيدي', 'التمهيدي', 'preparatory', 'prep'],
        }
        
        # تحديد التخصص من اسم مركز التكلفة
        target_branch = None
        for branch, keywords in branch_keywords.items():
            for keyword in keywords:
                if keyword.lower() in cost_center_name:
                    target_branch = branch
                    break
            if target_branch:
                break
        
        if target_branch:
            # البحث عن المدرسين المناسبين
            matching_teachers = Teacher.objects.filter(branches__contains=[target_branch])
            
            for teacher in matching_teachers:
                CourseTeacherAssignment.objects.get_or_create(
                    teacher=teacher,
                    course=self,
                    defaults={
                        'start_date': timezone.now().date(),
                        'is_active': True,
                        'notes': f"تعيين تلقائي - تخصص {target_branch}"
                    }
                )


# ================
    # الحقول الحالية...
    
    def create_auto_cost_center(self):
        """إنشاء مركز كلفة تلقائي بنفس اسم الدورة"""
        from .models import CostCenter
        
        if self.cost_center:
            return self.cost_center
        
        course_name = self.name_ar or self.name
        course_code = f"CRS-{self.id:03d}"
        
        cost_center = CostCenter.objects.create(
            code=course_code,
            name=self.name,
            name_ar=self.name_ar or self.name,
            cost_center_type='ACADEMIC',
            is_active=True,
            description=f"مركز كلفة للدورة: {course_name}"
        )
        
        self.cost_center = cost_center
        self.save()
        
        return cost_center
    
    def save(self, *args, **kwargs):
        """تحديث الحفظ لإنشاء مركز كلفة تلقائي"""
        is_new = self.pk is None
        
        super().save(*args, **kwargs)
        
        # بعد إنشاء الدورة، إنشاء مركز كلفة تلقائي
        if is_new and not self.cost_center:
            self.create_auto_cost_center()
        if is_new:
            Account.get_or_create_course_deferred_account(self)
            Account.get_or_create_course_account(self)

class CourseTeacherAssignment(models.Model):
    """Model to track teacher assignments to courses with salary details"""
    course = models.ForeignKey(Course, on_delete=models.CASCADE, verbose_name='الدورة / Course')
    teacher = models.ForeignKey('employ.Teacher', on_delete=models.CASCADE, verbose_name='المدرس / Teacher')
    
    # Assignment details
    start_date = models.DateField(verbose_name='تاريخ البداية / Start Date')
    end_date = models.DateField(null=True, blank=True, verbose_name='تاريخ النهاية / End Date')
    
    # Salary details for this course
    hourly_rate = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, 
                                    verbose_name='أجر الساعة / Hourly Rate')
    monthly_rate = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                     verbose_name='الراتب الشهري / Monthly Rate')
    total_hours = models.PositiveIntegerField(null=True, blank=True, 
                                            verbose_name='إجمالي الساعات / Total Hours')
    
    # Assignment status
    is_active = models.BooleanField(default=True, verbose_name='نشط / Active')
    notes = models.TextField(blank=True, verbose_name='ملاحظات / Notes')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'تعيين مدرس للدورة / Course Teacher Assignment'
        verbose_name_plural = 'تعيينات المدرسين للدورات / Course Teacher Assignments'
        unique_together = ('course', 'teacher', 'start_date')

    def __str__(self):
        teacher_name = getattr(self.teacher, 'full_name', None) or getattr(self.teacher, 'name', '') or str(self.teacher)
        return f"{teacher_name} - {self.course.name_ar or self.course.name}"

    def calculate_total_salary(self):
        """Calculate total salary for this assignment"""
        if self.hourly_rate and self.total_hours:
            return self.hourly_rate * self.total_hours
        elif self.monthly_rate:
            return self.monthly_rate
        return Decimal('0.00')

    def get_cost_center(self):
        """Get the cost center for this assignment"""
        return self.course.cost_center if self.course.cost_center else None


class Student(models.Model):
    student_id = models.CharField(max_length=20, unique=True, verbose_name='رقم الطالب / Student ID')
    name = models.CharField(max_length=200, verbose_name='الاسم / Name')
    email = models.EmailField(blank=True, verbose_name='البريد الإلكتروني / Email')
    phone = models.CharField(max_length=20, blank=True, verbose_name='الهاتف / Phone')
    address = models.TextField(blank=True, verbose_name='العنوان / Address')
    is_active = models.BooleanField(default=True, verbose_name='نشط / Active')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'الطالب / Student'
        verbose_name_plural = 'الطلاب / Students'
        ordering = ['name']

    def __str__(self):
        return f"{self.student_id} - {self.name}"

    def get_ar_account(self, course=None):
        """Return/create student's AR account. If course provided, scope to that course."""
        return Account.get_or_create_student_ar_account(self, course)

    @property
    def ar_account(self):
        """Backward-compatible: generic (non-course) AR account."""
        return self.get_ar_account(course=None)
    
def get_remaining_balance_for_course(self, course):
    """حساب المبلغ المتبقي في ذمة الطالب لدورة محددة - نسخة مبسطة"""
    try:
        enrollment = Studentenrollment.objects.get(student=self, course=course)
        if not enrollment.enrollment_journal_entry:
            return 0
        
        # البحث عن حساب ذمة الطالب من القيد الأصلي
        student_debit_transaction = enrollment.enrollment_journal_entry.transactions.filter(
            is_debit=True
        ).first()
        
        if not student_debit_transaction:
            return 0
            
        student_account = student_debit_transaction.account
        
        # حساب الرصيد الحالي
        from django.db.models import Sum
        
        debit_sum = Transaction.objects.filter(
            account=student_account, 
            is_debit=True
        ).aggregate(Sum('amount'))['amount__sum'] or 0
        
        credit_sum = Transaction.objects.filter(
            account=student_account, 
            is_debit=False
        ).aggregate(Sum('amount'))['amount__sum'] or 0
        
        balance = debit_sum - credit_sum
        print(f"Account: {student_account.name}, Debit: {debit_sum}, Credit: {credit_sum}, Balance: {balance}")  # DEBUG
        
        return max(balance, 0)
        
    except Exception as e:
        print(f"Error in get_remaining_balance: {e}")
        return 0
from students.models import Student as StudentProfile 
class Studentenrollment(models.Model):
    PAYMENT_METHOD_CHOICES = [
        ('CASH', 'نقد / Cash'),
        ('BANK', 'بنك / Bank'),
        ('CARD', 'بطاقة / Card'),
        ('TRANSFER', 'تحويل / Transfer'),
    ]

    student = models.ForeignKey('students.Student', on_delete=models.PROTECT, related_name='enrollments', verbose_name='الطالب / Student')
    course = models.ForeignKey(Course, on_delete=models.PROTECT, related_name='enrollments', verbose_name='الدورة / Course')
    academic_year = models.ForeignKey(
        'quick.AcademicYear',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='accounts_enrollments',
        verbose_name='الفصل الدراسي / Academic Year',
    )
    enrollment_date = models.DateField(verbose_name='تاريخ التسجيل / enrollment Date')
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='المبلغ الإجمالي / Total Amount')
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name='نسبة الخصم % / Discount Percent')
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='قيمة الخصم / Discount Amount')
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default='CASH', verbose_name='طريقة الدفع / Payment Method')
    notes = models.TextField(blank=True, verbose_name='ملاحظات / Notes')
    is_completed = models.BooleanField(default=False, verbose_name='مكتمل / Completed')
    completion_date = models.DateField(null=True, blank=True, verbose_name='تاريخ الإكمال / Completion Date')
    
    # Journal entry references
    enrollment_journal_entry = models.ForeignKey(JournalEntry, on_delete=models.SET_NULL, null=True, blank=True, related_name='enrollments', verbose_name='قيد التسجيل / enrollment Entry')
    completion_journal_entry = models.ForeignKey(JournalEntry, on_delete=models.SET_NULL, null=True, blank=True, related_name='completions', verbose_name='قيد الإكمال / Completion Entry')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'تسجيل الطالب / Student enrollment'
        verbose_name_plural = 'تسجيلات الطلاب / Student enrollments'
        ordering = ['-enrollment_date']
        unique_together = ('student', 'course')

    def __str__(self):
        student_display = getattr(self.student, 'full_name', None) or getattr(self.student, 'name', '') or str(self.student)
        return f"{student_display} - {self.course.name}"

    def clean(self):
        if self.course_id and self.academic_year_id and self.course.academic_year_id != self.academic_year_id:
            raise ValidationError("Enrollment academic year must match course academic year.")

    def save(self, *args, **kwargs):
        if self.course_id and not self.academic_year_id:
            self.academic_year = self.course.academic_year
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def net_amount(self):
        """Calculate net amount after discounts"""
        after_percent = self.total_amount - (self.total_amount * self.discount_percent / Decimal('100'))
        return max(Decimal('0'), after_percent - self.discount_amount)

    @property
    def amount_paid(self):
        """Total amount paid for this enrollment"""
        return self.payments.aggregate(total=Sum('paid_amount'))['total'] or Decimal('0.00')

    @property
    def balance_due(self):
        """Remaining balance due"""
        return max(Decimal('0'), self.net_amount - self.amount_paid)

    def create_accrual_enrollment_entry(self, user):
        """Create enrollment accrual entry: DR Student AR, CR Deferred Revenue"""
        if self.enrollment_journal_entry:
            return self.enrollment_journal_entry
        
        net_amount = self.net_amount
        if net_amount <= 0:
            return None
        
        # Get accounts (pass course to scope AR under course)
        student_ar_account = Account.get_or_create_student_ar_account(self.student, self.course)
        course_deferred_account = Account.get_or_create_course_deferred_account(self.course)
        
        # Create journal entry
        student_name = getattr(self.student, 'full_name', None) or getattr(self.student, 'name', '') or str(self.student)
        entry = JournalEntry.objects.create(
            date=self.enrollment_date,
            description=f"Student enrollment - {student_name} in {self.course.name}",
            entry_type='enrollment',
            total_amount=net_amount,
            academic_year=self.academic_year or self.course.academic_year,
            created_by=user
        )
        
        # DR: Student AR
        Transaction.objects.create(
            journal_entry=entry,
            account=student_ar_account,
            amount=net_amount,
            is_debit=True,
            description=f"enrollment - {student_name}"
        )
        
        # CR: Deferred Revenue
        Transaction.objects.create(
            journal_entry=entry,
            account=course_deferred_account,
            amount=net_amount,
            is_debit=False,
            description=f"Deferred revenue - {self.course.name}"
        )
        
        # Post the entry
        entry.post_entry(user)
        
        # Link to enrollment
        self.enrollment_journal_entry = entry
        self.save(update_fields=['enrollment_journal_entry'])
        
        return entry


class StudentReceipt(models.Model):
    PAYMENT_METHOD_CHOICES = [
        ('CASH', 'نقد / Cash'),
        ('BANK', 'بنك / Bank'),
        ('CARD', 'بطاقة / Card'),
        ('TRANSFER', 'تحويل / Transfer'),
    ]

    receipt_number = models.CharField(max_length=50, unique=True, verbose_name='رقم الإيصال / Receipt Number')
    date = models.DateField(verbose_name='التاريخ / Date')
    student_name = models.CharField(max_length=200, verbose_name='اسم الطالب / Student Name')
    course_name = models.CharField(max_length=200, blank=True, verbose_name='اسم الدورة / Course Name')
    
    # Foreign key relationships
    student_profile = models.ForeignKey('students.Student', on_delete=models.PROTECT, null=True, blank=True, related_name='receipts', verbose_name='ملف الطالب / Student Profile')
    student = models.ForeignKey(Student, on_delete=models.PROTECT, null=True, blank=True, related_name='receipts', verbose_name='الطالب / Student')
    course = models.ForeignKey(Course, on_delete=models.PROTECT, null=True, blank=True, related_name='receipts', verbose_name='الدورة / Course')
    enrollment = models.ForeignKey(Studentenrollment, on_delete=models.PROTECT, null=True, blank=True, related_name='payments', verbose_name='التسجيل / enrollment')
    academic_year = models.ForeignKey(
        'quick.AcademicYear',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='accounts_receipts',
        verbose_name='الفصل الدراسي / Academic Year',
    )
    
    # Financial fields
    amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name='المبلغ / Amount')
    paid_amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='المبلغ المدفوع / Paid Amount')
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name='نسبة الخصم % / Discount Percent')
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='قيمة الخصم / Discount Amount')
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default='CASH', verbose_name='طريقة الدفع / Payment Method')
    notes = models.TextField(blank=True, verbose_name='ملاحظات / Notes')
    is_printed = models.BooleanField(default=False, verbose_name='مطبوع / Printed')
    
    # Journal entry reference
    journal_entry = models.ForeignKey(JournalEntry, on_delete=models.SET_NULL, null=True, blank=True, related_name='receipts', verbose_name='قيد اليومية / Journal Entry')
    
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, verbose_name='أُنشئ بواسطة / Created By')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'إيصال الطالب / Student Receipt'
        verbose_name_plural = 'إيصالات الطلاب / Student Receipts'
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.receipt_number} - {self.student_name}"

    def save(self, *args, **kwargs):
        if not self.receipt_number:
            self.receipt_number = f"SR-{NumberSequence.next_value('student_receipt'):06d}"
        if self.enrollment_id and not self.academic_year_id:
            self.academic_year = self.enrollment.academic_year
        elif self.course_id and not self.academic_year_id:
            self.academic_year = self.course.academic_year
        elif self.student_profile_id and not self.academic_year_id:
            self.academic_year = self.student_profile.academic_year
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('accounts:student_receipt_detail', kwargs={'pk': self.pk})

    @property
    def net_amount(self):
        """Calculate net amount after discounts"""
        base_amount = self.amount or self.paid_amount or Decimal('0')
        after_percent = base_amount - (base_amount * self.discount_percent / Decimal('100'))
        return max(Decimal('0'), after_percent - self.discount_amount)

    def get_student_name(self):
        if self.enrollment and self.enrollment.student:
            return getattr(self.enrollment.student, 'full_name', None) or getattr(self.enrollment.student, 'name', '') or self.student_name
        if self.student_profile:
            return getattr(self.student_profile, 'full_name', None) or getattr(self.student_profile, 'name', '') or self.student_name
        if self.student:
            return getattr(self.student, 'full_name', None) or getattr(self.student, 'name', '') or self.student_name
        return self.student_name

    def get_course_name(self):
        if self.enrollment and self.enrollment.course:
            c = self.enrollment.course
            return getattr(c, 'name_ar', None) or c.name
        if self.course:
            return getattr(self.course, 'name_ar', None) or self.course.name
        return self.course_name

    def create_accrual_journal_entry(self, user):
        """Create journal entry for student payment: DR Cash, CR Student AR"""
        if self.journal_entry:
            return self.journal_entry
        
        paid_amount = self.paid_amount or Decimal('0')
        if paid_amount <= 0:
            return None
        
        cash_account = get_user_cash_account(user, fallback_code='121')

        # Determine course context if available
        course_ctx = None
        if self.enrollment and self.enrollment.course:
            course_ctx = self.enrollment.course
        elif self.course:
            course_ctx = self.course
        
        # Resolve student object and AR account
        student_obj = None
        if self.enrollment and self.enrollment.student:
            student_obj = self.enrollment.student
        elif self.student_profile:
            student_obj = self.student_profile
        elif self.student:
            student_obj = self.student

        if not student_obj:
            raise ValueError("No student provided")

        student_ar_account = Account.get_or_create_student_ar_account(student_obj, course_ctx)
        
        # Create journal entry
        entry = JournalEntry.objects.create(
            date=self.date,
            description=f"Student payment - {self.get_student_name()} for {self.get_course_name()}",
            entry_type='PAYMENT',
            total_amount=paid_amount,
            academic_year=self.academic_year or getattr(course_ctx, 'academic_year', None),
            created_by=user
        )
        
        # DR: Cash
        Transaction.objects.create(
            journal_entry=entry,
            account=cash_account,
            amount=paid_amount,
            is_debit=True,
            description=f"Cash received - {self.get_student_name()}"
        )
        
        # CR: Student AR
        Transaction.objects.create(
            journal_entry=entry,
            account=student_ar_account,
            amount=paid_amount,
            is_debit=False,
            description=f"Payment received - {self.get_course_name()}"
        )
        
        # Post the entry
        entry.post_entry(user)
        
        # Link to receipt
        self.journal_entry = entry
        self.save(update_fields=['journal_entry'])
        
        return entry

    def get_linked_journal_entries(self):
        return [entry for entry in [self.journal_entry] if entry]


    # إضافة العلاقة الجديدة للتسجيلات السريعة
    quick_enrollment = models.ForeignKey(
        'quick.QuickEnrollment', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        verbose_name='التسجيل السريع'
    )

class Category(models.Model):
    code = models.CharField(max_length=20, unique=True, verbose_name='الرمز / Code')
    name = models.CharField(max_length=100, verbose_name='الاسم / Name')
    name_ar = models.CharField(max_length=100, blank=True, verbose_name='الاسم بالعربية / Arabic Name')
    is_active = models.BooleanField(default=True, verbose_name='نشط / Active')

    class Meta:
        verbose_name = 'التصنيف / Category'
        verbose_name_plural = 'التصنيفات / Categories'
        ordering = ['code']

    def __str__(self):
        return self.name_ar if self.name_ar else self.name


class ExpenseEntry(models.Model):
    ENTRY_KIND_CHOICES = [
        ('EXPENSE', 'مصروف'),
        ('FOLLOWUP_REVENUE', 'إيراد طلاب المتابعة'),
    ]

    account = models.ForeignKey(Account, on_delete=models.CASCADE)
        
    cost_center = models.ForeignKey(
        'CostCenter', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        verbose_name='مركز التكلفة / Cost Center'
    )

    PAYMENT_METHOD_CHOICES = [
        ('CASH', 'نقد / Cash'),
        ('BANK', 'بنك / Bank'),
        ('CARD', 'بطاقة / Card'),
        ('TRANSFER', 'تحويل / Transfer'),
    ]
    # category = models.ForeignKey('Category', on_delete=models.CASCADE, null=True, blank=True)
    entry_kind = models.CharField(max_length=30, choices=ENTRY_KIND_CHOICES, default='EXPENSE', verbose_name='نوع الحركة / Entry Kind')
    reference = models.CharField(max_length=50, unique=True, verbose_name='المرجع / Reference')
    date = models.DateField(verbose_name='التاريخ / Date')
    description = models.CharField(max_length=500, verbose_name='الوصف / Description')
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='المبلغ / Amount')
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default='CASH', verbose_name='طريقة الدفع / Payment Method')
    # receipt_number = models.CharField(max_length=100, blank=True, verbose_name='رقم الإيصال / Receipt Number')
    notes = models.TextField(blank=True, verbose_name='ملاحظات / Notes')
    
    # Foreign key relationships
    journal_entry = models.ForeignKey(JournalEntry, on_delete=models.SET_NULL, null=True, blank=True, related_name='expenses', verbose_name='قيد اليومية / Journal Entry')
    academic_year = models.ForeignKey('quick.AcademicYear', on_delete=models.PROTECT, null=True, blank=True, related_name='accounts_expenses', verbose_name='Academic Year')
    
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, verbose_name='أُنشئ بواسطة / Created By')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'قيد المصروف / Expense Entry'
        verbose_name_plural = 'قيود المصروفات / Expense Entries'
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.reference} - {self.description}"

    def save(self, *args, **kwargs):
        if not self.reference:
            sequence_key = 'expense' if self.entry_kind == 'EXPENSE' else 'followup_revenue'
            prefix = 'EX' if self.entry_kind == 'EXPENSE' else 'FR'
            self.reference = f"{prefix}-{NumberSequence.next_value(sequence_key):06d}"
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('accounts:expense_detail', kwargs={'pk': self.pk})

    @property
    def expense_number(self):
        return self.reference

    @property
    def entry_kind_label(self):
        return self.get_entry_kind_display()

    @property
    def is_followup_revenue(self):
        return self.entry_kind == 'FOLLOWUP_REVENUE'

    def create_journal_entry(self, user):
        """Create journal entry for expense or follow-up revenue."""
        if self.journal_entry:
            return self.journal_entry

        payment_account = self.get_payment_account(user=user)
        entry = JournalEntry.objects.create(
            date=self.date,
            description=(
                f"إيراد طلاب المتابعة - {self.description}"
                if self.is_followup_revenue
                else f"Expense - {self.description}"
            ),
            entry_type='ADJUSTMENT' if self.is_followup_revenue else 'EXPENSE',
            total_amount=self.amount,
            academic_year=self.academic_year,
            created_by=user
        )

        if self.is_followup_revenue:
            Transaction.objects.create(
                journal_entry=entry,
                account=payment_account,
                amount=self.amount,
                is_debit=True,
                description=f"قبض إيراد متابعة - {self.get_payment_method_display()}",
                cost_center=self.cost_center
            )
            Transaction.objects.create(
                journal_entry=entry,
                account=self.account,
                amount=self.amount,
                is_debit=False,
                description=self.description or 'إيراد طلاب المتابعة',
                cost_center=self.cost_center
            )
        else:
            Transaction.objects.create(
                journal_entry=entry,
                account=self.account,
                amount=self.amount,
                is_debit=True,
                description=self.description,
                cost_center=self.cost_center
            )
            Transaction.objects.create(
                journal_entry=entry,
                account=payment_account,
                amount=self.amount,
                is_debit=False,
                description=f"Payment - {self.get_payment_method_display()}",
                cost_center=self.cost_center
            )

        entry.post_entry(user)
        self.journal_entry = entry
        self.save(update_fields=['journal_entry'])
        return entry
    @property
    def category_name(self):
        """Get category name from account"""
        if self.is_followup_revenue:
            return 'إيراد طلاب المتابعة'
        if self.account and self.account.code:
            try:
                account_code = int(self.account.code)
                if 503 <= account_code <= 599:
                    return self.account.display_name
            except (ValueError, TypeError):
                pass
        return self.account.display_name if self.account_id else "مصاريف أخرى / Other Expenses"

    def get_category_display(self):
        """Display category name"""
        return self.category_name

    def get_payment_account(self, user=None):
        """Return the account used to pay this expense."""
        method = (self.payment_method or '').upper()
        if method == 'CASH':
            return get_user_cash_account(user, fallback_code='121')

        account_mapping = {
            'BANK': ('1120', 'Bank Account', 'حساب البنك'),
            'CARD': ('1120', 'Bank Account', 'حساب البنك'),
            'TRANSFER': ('1120', 'Bank Account', 'حساب البنك'),
        }

        code, name, name_ar = account_mapping.get(method, account_mapping['BANK'])
        account, _ = Account.objects.get_or_create(
            code=code,
            defaults={
                'name': name,
                'name_ar': name_ar,
                'account_type': 'ASSET',
                'is_active': True,
            }
        )

        return account

class EmployeeAdvance(models.Model):
    employee = models.ForeignKey('employ.Employee', on_delete=models.SET_NULL, null=True, blank=True, related_name='advances', verbose_name='الموظف / Employee')
    employee_name = models.CharField(max_length=200, verbose_name='اسم الموظف / Employee Name')
    date = models.DateField(verbose_name='التاريخ / Date')
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='المبلغ / Amount')
    purpose = models.CharField(max_length=500, verbose_name='الغرض / Purpose')
    repayment_date = models.DateField(null=True, blank=True, verbose_name='تاريخ السداد / Repayment Date')
    is_repaid = models.BooleanField(default=False, verbose_name='مسدد / Repaid')
    repaid_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='المبلغ المسدد / Repaid Amount')
    reference = models.CharField(max_length=50, unique=True, verbose_name='المرجع / Reference')
    academic_year = models.ForeignKey('quick.AcademicYear', on_delete=models.PROTECT, null=True, blank=True, related_name='accounts_advances', verbose_name='Academic Year')
    
    # Journal entry reference
    journal_entry = models.ForeignKey(JournalEntry, on_delete=models.SET_NULL, null=True, blank=True, related_name='advances', verbose_name='قيد اليومية / Journal Entry')
    
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, verbose_name='أُنشئ بواسطة / Created By')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'سلفة الموظف / Employee Advance'
        verbose_name_plural = 'سلف الموظفين / Employee Advances'
        ordering = ['-date']

    def __str__(self):
        return f"{self.reference} - {self.employee_name}"

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = f"ADV-{NumberSequence.next_value('advance'):06d}"
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('accounts:advance_detail', kwargs={'pk': self.pk})

    @property
    def advance_number(self):
        return self.reference

    @property
    def outstanding_amount(self):
        """Calculate outstanding amount"""
        return max(Decimal('0'), self.amount - self.repaid_amount)

    def create_advance_entry(self, user):
        """Create advance journal entry: DR Employee Advance, CR Cash"""
        if self.journal_entry:
            return self.journal_entry
        
        # Get accounts
        advance_account = get_or_create_employee_advance_account(self.employee)
        cash_account = get_user_cash_account(user, fallback_code='121')
        
        # Create journal entry
        entry = JournalEntry.objects.create(
            date=self.date,
            description=f"Employee advance - {self.employee_name}",
            entry_type='ADVANCE',
            total_amount=self.amount,
            academic_year=self.academic_year,
            created_by=user
        )
        
        # DR: Employee Advance
        Transaction.objects.create(
            journal_entry=entry,
            account=advance_account,
            amount=self.amount,
            is_debit=True,
            description=f"Advance - {self.employee_name}"
        )
        
        # CR: Cash
        Transaction.objects.create(
            journal_entry=entry,
            account=cash_account,
            amount=self.amount,
            is_debit=False,
            description=f"Cash advance payment"
        )
        
        # Post the entry
        entry.post_entry(user)
        
        # Link to advance
        self.journal_entry = entry
        self.save(update_fields=['journal_entry'])
        
        return entry

    def create_advance_journal_entry(self, user):
        """Alias for create_advance_entry for compatibility"""
        return self.create_advance_entry(user)


class TeacherAdvance(models.Model):
    teacher = models.ForeignKey('employ.Teacher', on_delete=models.CASCADE, related_name='advances', verbose_name='المعلم / Teacher')
    date = models.DateField(verbose_name='التاريخ / Date')
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='المبلغ / Amount')
    purpose = models.CharField(max_length=500, verbose_name='الغرض / Purpose')
    is_repaid = models.BooleanField(default=False, verbose_name='مسدد / Repaid')
    repaid_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='المبلغ المسدد / Repaid Amount')
    
    # Journal entry reference
    journal_entry = models.ForeignKey(JournalEntry, on_delete=models.SET_NULL, null=True, blank=True, related_name='teacher_advances', verbose_name='قيد اليومية / Journal Entry')
    
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, verbose_name='أُنشئ بواسطة / Created By')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'سلفة المعلم / Teacher Advance'
        verbose_name_plural = 'سلف المعلمين / Teacher Advances'
        ordering = ['-date']

    def __str__(self):
        teacher_name = getattr(self.teacher, 'full_name', None) or getattr(self.teacher, 'name', '') or str(self.teacher)
        return f"Advance - {teacher_name} - {self.amount}"

    @property
    def outstanding_amount(self):
        """Calculate outstanding amount"""
        return max(Decimal('0'), self.amount - self.repaid_amount)

    def create_advance_journal_entry(self, user):
        """Create advance journal entry: DR Teacher Advance, CR Cash"""
        if self.journal_entry:
            return self.journal_entry
        
        # Get accounts
        advance_account = get_or_create_teacher_advance_account(self.teacher)
        cash_account = get_user_cash_account(user, fallback_code='121-1')
        
        # Create journal entry
        teacher_name = getattr(self.teacher, 'full_name', None) or getattr(self.teacher, 'name', '') or str(self.teacher)
        entry = JournalEntry.objects.create(
            date=self.date,
            description=f"Teacher advance - {teacher_name}",
            entry_type='ADVANCE',
            total_amount=self.amount,
            created_by=user
        )
        
        # DR: Teacher Advance
        Transaction.objects.create(
            journal_entry=entry,
            account=advance_account,
            amount=self.amount,
            is_debit=True,
            description=f"Advance - {teacher_name}"
        )
        
        # CR: Cash
        Transaction.objects.create(
            journal_entry=entry,
            account=cash_account,
            amount=self.amount,
            is_debit=False,
            description=f"Cash advance payment"
        )
        
        # Post the entry
        entry.post_entry(user)
        
        # Link to advance
        self.journal_entry = entry
        self.save(update_fields=['journal_entry'])
        
        return entry

    def sync_advance_journal_entry(self, user):
        """Ensure the linked journal entry matches the current advance values."""
        teacher_name = getattr(self.teacher, 'full_name', None) or getattr(self.teacher, 'name', '') or str(self.teacher)

        if not self.journal_entry:
            return self.create_advance_journal_entry(user)

        advance_account = get_or_create_teacher_advance_account(self.teacher)
        cash_account = get_user_cash_account(user, fallback_code='121-1')

        entry = self.journal_entry
        entry.date = self.date
        entry.description = f"Teacher advance - {teacher_name}"
        entry.total_amount = self.amount
        entry.save(update_fields=['date', 'description', 'total_amount'])

        debit_txn = entry.transactions.filter(is_debit=True).first()
        credit_txn = entry.transactions.filter(is_debit=False).first()

        if not debit_txn or not credit_txn:
            entry.transactions.all().delete()
            self.journal_entry = None
            self.save(update_fields=['journal_entry'])
            return self.create_advance_journal_entry(user)

        debit_txn.account = advance_account
        debit_txn.amount = self.amount
        debit_txn.description = f"Advance - {teacher_name}"
        debit_txn.save(update_fields=['account', 'amount', 'description'])

        credit_txn.account = cash_account
        credit_txn.amount = self.amount
        credit_txn.description = "Cash advance payment"
        credit_txn.save(update_fields=['account', 'amount', 'description'])

        entry.is_posted = False
        entry.posted_at = None
        entry.posted_by = None
        entry.save(update_fields=['is_posted', 'posted_at', 'posted_by'])

        entry.post_entry(user)
        return entry


class Budget(models.Model):
    account = models.ForeignKey(Account, on_delete=models.CASCADE, verbose_name='الحساب / Account')
    period = models.ForeignKey(AccountingPeriod, on_delete=models.CASCADE, verbose_name='الفترة / Period')
    budgeted_amount = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='المبلغ المخطط / Budgeted Amount')
    actual_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='المبلغ الفعلي / Actual Amount')
    notes = models.TextField(blank=True, verbose_name='ملاحظات / Notes')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'الميزانية / Budget'
        verbose_name_plural = 'الميزانيات / Budgets'
        unique_together = ('account', 'period')

    def __str__(self):
        return f"{self.account.code} - {self.period.name}"

    @property
    def variance(self):
        return self.actual_amount - self.budgeted_amount

    @property
    def variance_percentage(self):
        if self.budgeted_amount > 0:
            return (self.variance / self.budgeted_amount) * 100
        return Decimal('0')

    def calculate_variance(self):
        return self.variance


class DiscountRule(models.Model):
    reason = models.CharField(max_length=200, unique=True, verbose_name='سبب الخصم / Discount Reason')
    reason_ar = models.CharField(max_length=200, blank=True, verbose_name='السبب بالعربية / Reason in Arabic')
    discount_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('0'),
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))],
        verbose_name='نسبة الخصم % / Discount Percent'
    )
    discount_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0'),
        validators=[MinValueValidator(Decimal('0'))],
        verbose_name='قيمة الخصم الثابت / Fixed Discount Amount'
    )
    description = models.TextField(blank=True, verbose_name='الوصف / Description')
    is_active = models.BooleanField(default=True, verbose_name='نشط / Active')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'قاعدة الخصم / Discount Rule'
        verbose_name_plural = 'قواعد الخصم / Discount Rules'
        ordering = ['reason']

    def __str__(self):
        return self.reason


class StudentAccountLink(models.Model):
    student = models.OneToOneField('students.Student', on_delete=models.CASCADE, related_name='account_link', verbose_name='الطالب / Student')
    account = models.OneToOneField(Account, on_delete=models.CASCADE, related_name='student_link', verbose_name='الحساب / Account')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'ربط حساب الطالب / Student Account Link'
        verbose_name_plural = 'روابط حسابات الطلاب / Student Account Links'

    def __str__(self):
        student_name = getattr(self.student, 'full_name', None) or getattr(self.student, 'name', '') or str(self.student)
        return f"{student_name} - {self.account.code}"


# Helper functions for account creation
def get_or_create_teacher_salary_account(teacher):
    """Get or create salary expense account for teacher"""
    # Ensure parent account exists
    parent_account, _ = Account.objects.get_or_create(
        code='501',
        defaults={
            'name': 'Teacher Salaries',
            'name_ar': 'رواتب المدرسين',
            'account_type': 'EXPENSE',
            'is_active': True,
        }
    )
    
    # Create teacher-specific salary account
    teacher_code = f"501-{teacher.id:03d}"
    account, created = Account.objects.get_or_create(
        code=teacher_code,
        defaults={
            'name': f"Salary Expense - {getattr(teacher, 'full_name', None) or getattr(teacher, 'name', '')}",
            'name_ar': f"راتب - {getattr(teacher, 'full_name', None) or getattr(teacher, 'name', '')}",
            'account_type': 'EXPENSE',
            'parent': parent_account,
            'is_active': True,
        }
    )
    return account


def get_or_create_teacher_dues_account(teacher):
    """Get or create teacher dues liability account"""
    # Ensure parent account exists
    parent_account, _ = Account.objects.get_or_create(
        code='22',
        defaults={
            'name': 'Teacher Dues',
            'name_ar': 'مستحقات المدرسين',
            'account_type': 'LIABILITY',
            'is_active': True,
        }
    )
    
    # Create teacher-specific dues account
    teacher_code = f"22-{teacher.id:03d}"
    account, created = Account.objects.get_or_create(
        code=teacher_code,
        defaults={
            'name': f"Teacher Dues - {getattr(teacher, 'full_name', None) or getattr(teacher, 'name', '')}",
            'name_ar': f"مستحقات - {getattr(teacher, 'full_name', None) or getattr(teacher, 'name', '')}",
            'account_type': 'LIABILITY',
            'parent': parent_account,
            'is_active': True,
        }
    )
    return account


def get_or_create_teacher_advance_account(teacher):
    """Get or create teacher advance asset account"""
    # Ensure parent account exists
    parent_account, _ = Account.objects.get_or_create(
        code='1242',
        defaults={
            'name': 'Teacher Advances',
            'name_ar': 'سلف المدرسين',
            'account_type': 'ASSET',
            'is_active': True,
        }
    )
    
    # Create teacher-specific advance account
    teacher_code = f"1242-{teacher.id:03d}"
    account, created = Account.objects.get_or_create(
        code=teacher_code,
        defaults={
            'name': f"Teacher Advance - {getattr(teacher, 'full_name', None) or getattr(teacher, 'name', '')}",
            'name_ar': f"سلفة - {getattr(teacher, 'full_name', None) or getattr(teacher, 'name', '')}",
            'account_type': 'ASSET',
            'parent': parent_account,
            'is_active': True,
        }
    )
    return account


def get_or_create_employee_salary_account(employee):
    """Get or create salary expense account for employee"""
    # Ensure parent account exists
    parent_account, _ = Account.objects.get_or_create(
        code='502',
        defaults={
            'name': 'Employee Salaries',
            'name_ar': 'رواتب الموظفين',
            'account_type': 'EXPENSE',
            'is_active': True,
        }
    )
    
    # Create employee-specific salary account
    employee_code = f"502-{employee.id:03d}"
    account, created = Account.objects.get_or_create(
        code=employee_code,
        defaults={
            'name': f"Salary Expense - {getattr(employee, 'full_name', None) or getattr(employee, 'name', '')}",
            'name_ar': f"راتب - {getattr(employee, 'full_name', None) or getattr(employee, 'name', '')}",
            'account_type': 'EXPENSE',
            'parent': parent_account,
            'is_active': True,
        }
    )
    return account


def get_or_create_employee_advance_account(employee):
    """Get or create employee advance asset account"""
    # Ensure parent account exists
    parent_account, _ = Account.objects.get_or_create(
        code='1241',
        defaults={
            'name': 'Employee Advances',
            'name_ar': 'سلف الموظفين',
            'account_type': 'ASSET',
            'is_active': True,
        }
    )
    
    # Create employee-specific advance account
    employee_code = f"1241-{employee.id:03d}"
    account, created = Account.objects.get_or_create(
        code=employee_code,
        defaults={
            'name': f"Employee Advance - {getattr(employee, 'full_name', None) or getattr(employee, 'name', '')}",
            'name_ar': f"سلفة - {getattr(employee, 'full_name', None) or getattr(employee, 'name', '')}",
            'account_type': 'ASSET',
            'parent': parent_account,
            'is_active': True,
        }
    )
    return account


def get_or_create_employee_cash_account(employee):
    """Ensure a dedicated cash account exists for an employee."""
    cash_parent, _ = Account.objects.get_or_create(
        code='121',
        defaults={
            'name': 'Cash',
            'name_ar': 'النقدية',
            'account_type': 'ASSET',
            'is_active': True,
        }
    )

    employee_name = employee.full_name or (employee.user.get_full_name() if employee.user_id else '')
    if not employee_name:
        employee_name = employee.user.get_username() if employee.user_id else 'Employee'

    employee_code = f"121-{employee.pk:04d}"
    account, created = Account.objects.get_or_create(
        code=employee_code,
        defaults={
            'name': f'Employee Cash - {employee_name}',
            'name_ar': f'رصيد صندوق {employee_name}',
            'account_type': 'ASSET',
            'parent': cash_parent,
            'is_active': True,
        }
    )
    return account, created
# 


def get_user_cash_account(user, fallback_code='121', fallback_defaults=None):
    """Return the cash account associated with the logged-in employee, or fallback to a default."""
    if fallback_defaults is None:
        fallback_defaults = {
            'name': 'Cash',
            'name_ar': 'النقدية',
            'account_type': 'ASSET',
            'is_active': True,
        }

    if user and getattr(user, 'is_authenticated', False):
        employee = getattr(user, 'employee_profile', None)
        if employee:
            account = employee.get_cash_account()
            if account:
                return account
            account, _ = get_or_create_employee_cash_account(employee)
            return account

    account, _ = Account.objects.get_or_create(code=fallback_code, defaults=fallback_defaults)
    return account
# 




# ==========================
@classmethod
def get_or_create_course_revenue_account(cls, course):
    """إنشاء أو جلب حساب إيرادات لدورة محددة"""
    # جلب الحساب الرئيسي للإيرادات
    revenue_parent = cls.objects.filter(code='4110').first() or cls.objects.filter(code='4').first()
    
    if not revenue_parent:
        # إذا ما في حساب رئيسي، أنشئ واحد
        revenue_parent, _ = cls.objects.get_or_create(
            code='4',
            defaults={
                'name': 'Revenue',
                'name_ar': 'الإيرادات',
                'account_type': 'REVENUE',
                'is_active': True
            }
        )
    
    # # إنشاء أو جلب حساب الدورة المحددة
    # account, created = cls.objects.get_or_create(
    #     code=f'4110-{Student.id:04d}',
    #     defaults={
    #         'name': f'Course Revenue - {Student.name}',
    #         'name_ar': f'إيرادات الدورة - {Student.name}',
    #         'account_type': 'REVENUE',
    #         'is_active': True,
    #         'parent': revenue_parent
    #     }
    # )
    return account




# ====================
# الطلاب السريعين 
# ====================
# accounts/models.py - إضافة النماذج المحاسبية للطلاب السريعين

class QuickStudentAccounting(models.Model):
    """النموذج المحاسبي للطلاب السريعين"""
    student = models.OneToOneField('quick.QuickStudent', on_delete=models.CASCADE, verbose_name='الطالب السريع')
    ar_account = models.ForeignKey(Account, on_delete=models.CASCADE, verbose_name='حساب الذمم')
    total_enrollments = models.PositiveIntegerField(default=0, verbose_name='إجمالي التسجيلات')
    total_revenue = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='إجمالي الإيرادات')
    total_collected = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='إجمالي المحصل')
    outstanding_balance = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='الرصيد المتبقي')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'محاسبة طالب سريع'
        verbose_name_plural = 'محاسبة الطلاب السريعين'
    
    def __str__(self):
        return f"محاسبة - {self.student.full_name}"

class QuickCourseAccounting(models.Model):
    """النموذج المحاسبي للدورات السريعة"""
    course = models.OneToOneField('quick.QuickCourse', on_delete=models.CASCADE, verbose_name='الدورة السريعة')
    deferred_account = models.ForeignKey(Account, on_delete=models.CASCADE, verbose_name='حساب الإيرادات المؤجلة')
    revenue_account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='quick_revenue', verbose_name='حساب الإيرادات')
    total_enrollments = models.PositiveIntegerField(default=0, verbose_name='إجمالي التسجيلات')
    total_revenue = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='إجمالي الإيرادات')
    total_collected = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='إجمالي المحصل')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'محاسبة دورة سريعة'
        verbose_name_plural = 'محاسبة الدورات السريعة'
    
    def __str__(self):
        return f"محاسبة - {self.course.name}"

from datetime import datetime, timedelta

def comprehensive_site_export(request):
    # معالجة التواريخ
    end_date = request.GET.get('end_date')
    start_date = request.GET.get('start_date')
    
    if not end_date:
        end_date = datetime.now().date()
    else:
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    
    if not start_date:
        start_date = end_date - timedelta(days=30)  # آخر 30 يوم
    else:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    
    # ... باقي الكود


    # في accounts/models.py - أضف في نهاية الملف داخل class Account
# في accounts/models.py - داخل class Account
@classmethod
def get_withdrawal_revenue_account(cls, student=None, course=None):
    """
    الحصول على حساب إيرادات انسحاب الطلاب (4201) - النسخة المؤكدة
    """
    try:
        print(f"🔍 [DEBUG] جلب حساب 4201 للطالب: {student.full_name if student else 'لا يوجد'}")
        
        # التأكد من وجود الحساب الرئيسي 4200
        parent_account, created = cls.objects.get_or_create(
            code='4200',
            defaults={
                'name': 'Other Operating Revenues',
                'name_ar': 'إيرادات تشغيل أخرى',
                'account_type': 'REVENUE',
                'is_active': True,
                'description': 'الإيرادات الأخرى من الأنشطة التشغيلية'
            }
        )
        
        if created:
            print(f"✅ تم إنشاء الحساب الرئيسي 4200")
        
        # إعداد اسم الحساب
        account_name_ar = 'إيرادات انسحاب طلاب'
        if student and course:
            account_name_ar = f'إيرادات سحب - {student.full_name} - {course.name}'
        
        # الحصول على أو إنشاء حساب 4201
        withdrawal_account, created = cls.objects.get_or_create(
            code='4201',
            defaults={
                'name': 'Student Withdrawal Revenues',
                'name_ar': account_name_ar,
                'account_type': 'REVENUE',
                'is_active': True,
                'parent': parent_account,
                'description': 'الإيرادات الناتجة عن سحب الطلاب من الدورات الدراسية'
            }
        )
        
        if created:
            print(f"✅ تم إنشاء حساب 4201: {withdrawal_account.code} - {withdrawal_account.name_ar}")
        else:
            print(f"✅ تم العثور على حساب 4201 موجود: {withdrawal_account.code} - {withdrawal_account.name_ar}")
            # تحديث الاسم إذا تم تمرير بيانات
            if student or course:
                withdrawal_account.name_ar = account_name_ar
                withdrawal_account.save(update_fields=['name_ar'])
        
        return withdrawal_account
        
    except Exception as e:
        print(f"❌ خطأ في get_withdrawal_revenue_account: {e}")
        # إنشاء حساب احتياطي في حالة الخطأ
        return cls.objects.filter(code='4201').first() or cls.objects.create(
            code='4201',
            name='Student Withdrawal Revenues',
            name_ar='إيرادات انسحاب طلاب',
            account_type='REVENUE',
            is_active=True
        )
def _delete_linked_instance(instance):
    if not instance or getattr(instance, '_skip_linked_cleanup', False):
        return
    instance._skip_linked_cleanup = True
    instance.delete()


@receiver(pre_delete, sender=JournalEntry)
def delete_student_operation_when_entry_deleted(sender, instance, **kwargs):
    if getattr(instance, '_skip_linked_cleanup', False):
        return

    linked_objects = []
    linked_objects.extend(instance.receipts.all())
    linked_objects.extend(instance.enrollments.all())

    from quick.models import QuickEnrollment, QuickStudentReceipt

    linked_objects.extend(QuickStudentReceipt.objects.filter(journal_entry=instance))

    if instance.reference and instance.reference.startswith('QE-'):
        try:
            enrollment_id = int(instance.reference.split('-', 1)[1])
        except (TypeError, ValueError):
            enrollment_id = None
        if enrollment_id:
            linked_objects.extend(QuickEnrollment.objects.filter(id=enrollment_id))

    seen = set()
    for obj in linked_objects:
        key = (obj.__class__, obj.pk)
        if obj.pk and key in seen:
            continue
        seen.add(key)
        _delete_linked_instance(obj)


@receiver(pre_delete, sender=Studentenrollment)
def delete_student_entry_when_enrollment_deleted(sender, instance, **kwargs):
    if getattr(instance, '_skip_linked_cleanup', False):
        return

    for entry in [instance.enrollment_journal_entry, instance.completion_journal_entry]:
        if not entry:
            continue
        entry._skip_linked_cleanup = True
        entry.delete()


@receiver(pre_delete, sender=StudentReceipt)
def delete_student_entry_when_receipt_deleted(sender, instance, **kwargs):
    if getattr(instance, '_skip_linked_cleanup', False):
        return

    for entry in instance.get_linked_journal_entries():
        entry._skip_linked_cleanup = True
        entry.delete()
