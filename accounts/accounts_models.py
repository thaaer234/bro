from django.db import models, transaction, IntegrityError
import sqlite3
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from decimal import Decimal
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from django.db.models import Sum, Q
import uuid
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils.text import slugify


class DiscountRule(models.Model):
    reason = models.CharField(max_length=200, unique=True, verbose_name='سبب الخصم / Discount Reason')
    reason_ar = models.CharField(max_length=200, blank=True, verbose_name='السبب بالعربية / Reason in Arabic')
    discount_percent = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=Decimal('0'),
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))],
        verbose_name='نسبة الخصم % / Discount Percent'
    )
    discount_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=Decimal('0'),
        validators=[MinValueValidator(Decimal('0'))],
        verbose_name='قيمة الخصم الثابت / Fixed Discount Amount'
    )
    description = models.TextField(blank=True, verbose_name='الوصف / Description')
    is_active = models.BooleanField(default=True, verbose_name='نشط / Active')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    # Per-enrollment AR and revenue linkage (nullable for backfill; set on create)
    ar_account = models.ForeignKey('accounts.Account', null=True, blank=True, related_name='enrollment_ars', on_delete=models.SET_NULL)
    rev_account = models.ForeignKey('accounts.Account', null=True, blank=True, related_name='enrollment_revenues', on_delete=models.SET_NULL)

    # Opening accrual reference and lifecycle
    opened_journal_entry = models.ForeignKey('accounts.JournalEntry', null=True, blank=True, related_name='+', on_delete=models.SET_NULL)
    closed_at = models.DateTimeField(null=True, blank=True)
    is_withdrawn = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'قاعدة الحسم / Discount Rule'
        verbose_name_plural = 'قواعد الحسم / Discount Rules'
        ordering = ['reason']

    def __str__(self):
        return f"{self.reason} - {self.discount_percent}% + {self.discount_amount}"

    def get_absolute_url(self):
        return reverse('accounts:discount_rule_detail', kwargs={'pk': self.pk})

    def apply_discount(self, amount):
        """Apply this discount rule to an amount"""
        after_percent = amount - (amount * self.discount_percent / Decimal('100'))
        return max(Decimal('0'), after_percent - self.discount_amount)


class CostCenter(models.Model):
    code = models.CharField(max_length=20, unique=True, verbose_name='الرمز / Code')
    name = models.CharField(max_length=100, verbose_name='الاسم / Name')
    name_ar = models.CharField(max_length=100, blank=True, verbose_name='الاسم بالعربية / Arabic Name')
    description = models.TextField(blank=True, verbose_name='الوصف / Description')
    is_active = models.BooleanField(default=True, verbose_name='نشط / Active')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'مركز التكلفة / Cost Center'
        verbose_name_plural = 'مراكز التكلفة / Cost Centers'
        ordering = ['code']

    def __str__(self):
        return f"{self.code} - {self.name}"


class NumberSequence(models.Model):
    key = models.CharField(max_length=64, unique=True)
    last_value = models.BigIntegerField(default=0)

    def __str__(self):
        return f"{self.key}={self.last_value}"


def next_sequence_value(key: str) -> int:
    """Atomic increment for a named sequence key (robust under concurrency)."""
    with transaction.atomic():
        seq, _ = NumberSequence.objects.select_for_update().get_or_create(key=key)
        seq.last_value += 1
        seq.save(update_fields=['last_value'])
        return seq.last_value


def generate_receipt_number(date=None) -> str:
    """Generate a daily sequence-backed receipt number like RC-YYYYMMDD-0001."""
    d = (date or timezone.now().date()).strftime("%Y%m%d")
    n = next_sequence_value(f"studentreceipt-{d}")
    return f"RC-{d}-{n:04d}"


def _student_code(student) -> str:
    """
    Return a stable student code for receipt numbers.
    Prefers student_number or code; falls back to S<id>.
    """
    if not student:
        return "S000000"
    code = getattr(student, 'student_number', None) or getattr(student, 'code', None)
    if code:
        return str(code).strip().replace(' ', '').upper()
    sid = getattr(student, 'id', None) or 0
    try:
        return f"S{int(sid):06d}"
    except Exception:
        return "S000000"


def _next_seq(key: str) -> int:
    with transaction.atomic():
        seq, _ = NumberSequence.objects.select_for_update().get_or_create(key=key)
        seq.last_value += 1
        seq.save(update_fields=['last_value'])
        return seq.last_value


def generate_student_receipt_number(student, date=None) -> str:
    """
    Pattern: RC-<STUDENTCODE>-<YYYYMMDD>-<NNN>
    The sequence (NNN) is scoped by (student, day) to avoid collisions
    across students and days.
    """
    d = (date or timezone.now().date())
    ymd = d.strftime("%Y%m%d")
    scode = _student_code(student)
    n = _next_seq(f"studentreceipt:{scode}:{ymd}")
    return f"RC-{scode}-{ymd}-{n:03d}"


class Account(models.Model):
    # Normal balance sides for signed calculations
    NORMAL_DEBIT_TYPES = ['ASSET', 'EXPENSE']
    NORMAL_CREDIT_TYPES = ['LIABILITY', 'EQUITY', 'REVENUE']
    ACCOUNT_TYPES = [
        ('ASSET', 'الأصول / Assets'),
        ('LIABILITY', 'الخصوم / Liabilities'),
        ('EQUITY', 'حقوق الملكية / Equity'),
        ('REVENUE', 'الإيرادات / Revenue'),
        ('EXPENSE', 'المصروفات / Expenses'),
    ]

    code = models.CharField(max_length=20, unique=True, verbose_name='رمز الحساب / Account Code')
    name = models.CharField(max_length=200, verbose_name='اسم الحساب / Account Name')
    name_ar = models.CharField(max_length=200, blank=True, verbose_name='الاسم بالعربية / Arabic Name')
    account_type = models.CharField(max_length=20, choices=ACCOUNT_TYPES, verbose_name='نوع الحساب / Account Type')
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, 
                              related_name='children', verbose_name='الحساب الأب / Parent Account')
    description = models.TextField(blank=True, verbose_name='الوصف / Description')
    is_active = models.BooleanField(default=True, verbose_name='نشط / Active')
    balance = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='الرصيد / Balance')
    
    # Course-specific fields for accrual accounting
    is_course_account = models.BooleanField(default=False, verbose_name='حساب الدورة / Course Account')
    course_name = models.CharField(max_length=200, blank=True, verbose_name='اسم الدورة / Course Name')
    
    # Student-specific fields for AR accounts
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

    def has_children(self) -> bool:
        """Return True if this account has child accounts."""
        return self.children.exists()

    def get_debit_balance(self):
        """Get total debit amount for this account"""
        return self.transaction_set.filter(is_debit=True).aggregate(
            total=Sum('amount'))['total'] or Decimal('0.00')

    def get_credit_balance(self):
        """Get total credit amount for this account"""
        return self.transaction_set.filter(is_debit=False).aggregate(
            total=Sum('amount'))['total'] or Decimal('0.00')

    def get_net_balance(self):
        """Calculate net balance based on account type"""
        debit_total = self.get_debit_balance()
        credit_total = self.get_credit_balance()
        
        if self.account_type in ['ASSET', 'EXPENSE']:
            return debit_total - credit_total
        else:  # LIABILITY, EQUITY, REVENUE
            return credit_total - debit_total

    def recalculate_balance(self):
        """Recalculate and update the balance field"""
        self.balance = self.get_net_balance()
        self.save(update_fields=['balance'])

    def recalculate_tree_balances(self):
        """Recalculate balances for this account and all children"""
        self.recalculate_balance()
        for child in self.children.all():
            child.recalculate_tree_balances()

    def apply_effective_amount(self, is_debit: bool, amount: Decimal):
        """
        Compute signed delta for this account per normal balance rules and
        add the same delta to this account and all ancestors.
        """
        if is_debit:
            delta = amount if self.account_type in self.NORMAL_DEBIT_TYPES else -amount
        else:
            delta = amount if self.account_type in self.NORMAL_CREDIT_TYPES else -amount

        node = self
        while node is not None:
            node.balance = (node.balance or Decimal('0')) + delta
            node.save(update_fields=['balance'])
            node = node.parent

    def recalc_balance_tree(self):
        """
        Recalculate this node's own net balance (from transactions),
        then set parent balances as sum of their own net + children balances.
        Use from leaves upward for full consistency.
        """
        # Own net:
        own = self.get_net_balance()
        # Children:
        total_children = sum((child.recalc_balance_tree() for child in self.children.all()), Decimal('0'))
        self.balance = own + total_children
        self.save(update_fields=['balance'])
        return self.balance

    def descendant_ids(self):
        """Return [self.id] + all descendant account IDs (DFS), cycle-safe."""
        ids = []
        seen = set()
        stack = [self]
        while stack:
            node = stack.pop()
            if not node or node.id in seen:
                continue
            seen.add(node.id)
            ids.append(node.id)
            for c in node.children.all():
                if c.id not in seen:
                    stack.append(c)
        return ids

    def transactions_with_descendants(self):
        """Queryset of transactions for this account and all descendants (for ledger/reports)."""
        return Transaction.objects.filter(account_id__in=self.descendant_ids())

    def own_net_balance(self) -> Decimal:
        """Net of this account from its OWN transactions only (no children)."""
        debit_sum = Transaction.objects.filter(account=self, is_debit=True).aggregate(s=Sum('amount'))['s'] or Decimal('0')
        credit_sum = Transaction.objects.filter(account=self, is_debit=False).aggregate(s=Sum('amount'))['s'] or Decimal('0')
        if self.account_type in self.NORMAL_DEBIT_TYPES:
            return debit_sum - credit_sum
        return credit_sum - debit_sum

    @property
    def rollup_balance(self) -> Decimal:
        """
        Cycle-safe roll-up for UI: own net + sum(all descendants' own nets).
        Avoids recursion errors if there is an accidental parent/child cycle.
        """
        total = Decimal('0')
        seen = set()
        stack = [self]
        while stack:
            node = stack.pop()
            if not node or node.id in seen:
                continue
            seen.add(node.id)
            total += node.own_net_balance()
            for c in node.children.all():
                if c.id not in seen:
                    stack.append(c)
        return total


# ---- Helper functions for account discovery/creation ----
def get_root_ar_parent():
    """Return the root Accounts Receivable parent, e.g., code '1120'."""
    return Account.objects.filter(code='1120').first()


def get_revenue_parent():
    """Return the root Revenue parent '4100', ensuring its parent is cash '121'."""
    cash, _ = Account.objects.get_or_create(
        code='121',
        defaults=dict(name='Cash', name_ar='الصندوق', account_type='ASSET', is_active=True),
    )
    revenue, _ = Account.objects.get_or_create(
        code='4100',
        defaults=dict(name='Revenue', name_ar='الإيرادات', account_type='REVENUE', is_active=True, parent=cash),
    )
    if revenue.parent_id != cash.id:
        revenue.parent = cash
        revenue.save(update_fields=['parent'])
    return revenue


def get_returns_parent():
    """Return the Revenue Returns parent, defaulting to Revenue parent if missing."""
    return Account.objects.filter(code='4190').first() or get_revenue_parent()


def get_or_create_course_revenue(course):
    """Get or create revenue account per course (idempotent)."""
    parent = get_revenue_parent()
    code = f"4100-{course.id:04d}"
    acc, _ = Account.objects.get_or_create(
        code=code,
        defaults=dict(
            name=f"Course Revenue - {getattr(course, 'name', course.id)}",
            name_ar=f"إيرادات الدورة - {getattr(course, 'name', course.id)}",
            account_type='REVENUE',
            is_active=True,
            parent=parent,
        )
    )
    return acc


def get_or_create_enrollment_ar(student, course):
    """Exactly one AR account per (student, course)."""
    parent = get_root_ar_parent()
    code = f"1120-{course.id:04d}-{getattr(student, 'id', 0):06d}"
    student_name = getattr(student, 'full_name', None) or getattr(student, 'name', None) or str(student)
    course_name = getattr(course, 'name', None) or str(course)
    acc, _ = Account.objects.get_or_create(
        code=code,
        defaults=dict(
            name=f"AR - {student_name} / {course_name}",
            name_ar=f"ذمم - {student_name} / {course_name}",
            account_type='ASSET',
            is_active=True,
            parent=parent,
        )
    )
    return acc

    def recalc_with_children(self) -> Decimal:
        """
        Rebuild 'balance' as own net + sum(children balances). Must be called bottom-up.
        """
        own = self.own_net_balance()
        total_children = sum((c.recalc_with_children() for c in self.children.all()), Decimal('0'))
        self.balance = own + total_children
        self.save(update_fields=['balance'])
        return self.balance

    @classmethod
    def rebuild_all_balances(cls):
        """Full rebuild using recalc_with_children from leaves to roots."""
        def depth(a):
            d, p = 0, a.parent
            while p:
                d += 1
                p = p.parent
            return d
        accs = list(cls.objects.all())
        for a in sorted(accs, key=depth, reverse=True):
            a.recalc_with_children()

    @classmethod
    def get_or_create_student_ar_account(cls, student):
        """Get or create AR account for a specific student"""
        account_code = f"1120-{student.id:04d}"
        
        # Try to get existing account first
        try:
            return cls.objects.get(code=account_code)
        except cls.DoesNotExist:
            pass
        
        # Get or create parent AR account
        parent_ar_account, created = cls.objects.get_or_create(
            code='1120',
            defaults={
                'name': 'Accounts Receivable',
                'name_ar': 'ذمم مدينة',
                'account_type': 'ASSET',
                'is_active': True
            }
        )
        
        # Create student-specific AR account
        account, created = cls.objects.get_or_create(
            code=account_code,
            defaults={
                'name': f"Accounts Receivable - {student.full_name}",
                'name_ar': f"ذمم مدينة - {student.full_name}",
                'account_type': 'ASSET',
                'is_student_account': True,
                'student_name': student.full_name,
                'is_active': True,
                'parent': parent_ar_account
            }
        )
        
        print(f"Student AR Account: {account.code} - {account.name} (Created: {created})")
        return account

    @classmethod
    def get_or_create_course_deferred_account(cls, course):
        """Get or create deferred revenue account for a specific course"""
        account_code = f"2150-{course.id:04d}"
        account, created = cls.objects.get_or_create(
            code=account_code,
            defaults={
                'name': f"Deferred Revenue - {course.name}",
                'name_ar': f"إيرادات مؤجلة - {course.name}",
                'account_type': 'LIABILITY',
                'is_course_account': True,
                'course_name': course.name,
                'is_active': True,
                'parent': cls.objects.filter(code='2150').first()  # Main Deferred Revenue account
            }
        )
        return account


class AccountingPeriod(models.Model):
    name = models.CharField(max_length=100, verbose_name='اسم الفترة / Period Name')
    start_date = models.DateField(verbose_name='تاريخ البداية / Start Date')
    end_date = models.DateField(verbose_name='تاريخ النهاية / End Date')
    is_closed = models.BooleanField(default=False, verbose_name='مقفلة / Closed')
    closed_at = models.DateTimeField(null=True, blank=True, verbose_name='تاريخ الإقفال / Closed At')
    closed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name='closed_periods', verbose_name='أُقفل بواسطة / Closed By')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'الفترة المحاسبية / Accounting Period'
        verbose_name_plural = 'الفترات المحاسبية / Accounting Periods'
        ordering = ['-start_date']

    def __str__(self):
        return f"{self.name} ({self.start_date} - {self.end_date})"

    @property
    def is_current(self):
        today = timezone.now().date()
        return self.start_date <= today <= self.end_date and not self.is_closed


class JournalEntry(models.Model):
    ENTRY_TYPES = [
        ('MANUAL', 'يدوي / Manual'),
        ('enrollment', 'تسجيل / enrollment'),
        ('PAYMENT', 'دفع / Payment'),
        ('COMPLETION', 'إكمال / Completion'),
        ('EXPENSE', 'مصروف / Expense'),
        ('ADJUSTMENT', 'تسوية / Adjustment'),
    ]

    reference = models.CharField(max_length=50, unique=True, verbose_name='المرجع / Reference')
    date = models.DateField(verbose_name='التاريخ / Date')
    description = models.TextField(verbose_name='الوصف / Description')
    entry_type = models.CharField(max_length=20, choices=ENTRY_TYPES, default='MANUAL',
                                 verbose_name='نوع القيد / Entry Type')
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='المبلغ الإجمالي / Total Amount')
    is_posted = models.BooleanField(default=False, verbose_name='مُرحل / Posted')
    posted_at = models.DateTimeField(null=True, blank=True, verbose_name='تاريخ الترحيل / Posted At')
    posted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name='posted_entries', verbose_name='مُرحل بواسطة / Posted By')
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, verbose_name='أُنشئ بواسطة / Created By')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'قيد اليومية / Journal Entry'
        verbose_name_plural = 'قيود اليومية / Journal Entries'
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.reference} - {self.date}"

    def get_absolute_url(self):
        return reverse('accounts:journal_entry_detail', kwargs={'pk': self.pk})

    def clean(self):
        # Validate that debits equal credits
        if self.pk:
            total_debits = self.transactions.filter(is_debit=True).aggregate(
                total=Sum('amount'))['total'] or Decimal('0.00')
            total_credits = self.transactions.filter(is_debit=False).aggregate(
                total=Sum('amount'))['total'] or Decimal('0.00')
            
            if total_debits != total_credits:
                raise ValidationError('إجمالي المدين يجب أن يساوي إجمالي الدائن / Total debits must equal total credits')

    def post_entry(self, user=None):
        """Post the journal entry to update account balances"""
        if self.is_posted:
            raise ValueError('القيد مرحل بالفعل / Entry is already posted')
        
        # Update account balances (propagate to parents)
        for t in self.transactions.select_related('account__parent'):
            t.account.apply_effective_amount(t.is_debit, t.amount)
        
        # Mark as posted
        self.is_posted = True
        self.posted_at = timezone.now()
        self.posted_by = user
        self.save(update_fields=['is_posted', 'posted_at', 'posted_by'])

    def reverse_entry(self, user, description=None):
        """Create a reversing journal entry"""
        if not self.is_posted:
            raise ValueError('لا يمكن عكس قيد غير مرحل / Cannot reverse unposted entry')
        
        # Create reversing entry
        reversing_entry = JournalEntry.objects.create(
            reference=f"REV-{self.reference}",
            date=timezone.now().date(),
            description=description or f"Reversal of {self.reference}",
            entry_type='ADJUSTMENT',
            total_amount=self.total_amount,
            created_by=user
        )
        
        # Create reversing transactions
        for transaction in self.transactions.all():
            Transaction.objects.create(
                journal_entry=reversing_entry,
                account=transaction.account,
                amount=transaction.amount,
                is_debit=not transaction.is_debit,  # Reverse the debit/credit
                description=f"Reversal of {transaction.description}",
                cost_center=transaction.cost_center
            )
        
        # Auto-post the reversing entry
        reversing_entry.post_entry(user)
        
        return reversing_entry

    def save(self, *args, **kwargs):
        if not self.reference:
            # Auto-generate reference
            today = timezone.now().date()
            count = JournalEntry.objects.filter(date=today).count() + 1
            self.reference = f"JE-{today.strftime('%Y%m%d')}-{count:03d}"
        super().save(*args, **kwargs)


class Transaction(models.Model):
    journal_entry = models.ForeignKey(JournalEntry, on_delete=models.CASCADE, 
                                     related_name='transactions', verbose_name='قيد اليومية / Journal Entry')
    account = models.ForeignKey(Account, on_delete=models.PROTECT, verbose_name='الحساب / Account')
    amount = models.DecimalField(max_digits=15, decimal_places=2, 
                                validators=[MinValueValidator(Decimal('0.00'))],
                                verbose_name='المبلغ / Amount')
    dollar_amount = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, verbose_name='مبلغ الدولار / Dollar Amount')
    is_debit = models.BooleanField(verbose_name='مدين / Debit')
    description = models.CharField(max_length=500, blank=True, verbose_name='الوصف / Description')
    cost_center = models.ForeignKey(CostCenter, on_delete=models.SET_NULL, null=True, blank=True,
                                   verbose_name='مركز التكلفة / Cost Center')
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

    @property
    def deferred_revenue_account(self):
        """Get or create the deferred revenue account for this course"""
        return Account.get_or_create_course_deferred_account(self)

    @property
    def earned_revenue_account(self):
        """Get or create the earned revenue account for this course"""
        account_code = f"4100-{self.id:04d}"
        account, created = Account.objects.get_or_create(
            code=account_code,
            defaults={
                'name': f"Course Revenue - {self.name}",
                'name_ar': f"إيرادات الدورة - {self.name}",
                'account_type': 'REVENUE',
                'is_course_account': True,
                'course_name': self.name,
                'is_active': True,
                'parent': Account.objects.filter(code='4100').first()  # Main Revenue account
            }
        )
        return account


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

    @property
    def ar_account(self):
        """Get or create the AR account for this student"""
        return Account.get_or_create_student_ar_account(self)

    def get_balance(self):
        """Get current AR balance for this student"""
        return self.ar_account.get_net_balance()


class Studentenrollment(models.Model):
    PAYMENT_METHODS = [
        ('CASH', 'نقد / Cash'),
        ('BANK', 'بنك / Bank'),
        ('CARD', 'بطاقة / Card'),
        ('TRANSFER', 'تحويل / Transfer'),
    ]

    student = models.ForeignKey('students.Student', on_delete=models.PROTECT, 
                               related_name='enrollments', verbose_name='الطالب / Student')
    course = models.ForeignKey(Course, on_delete=models.PROTECT, 
                              related_name='enrollments', verbose_name='الدورة / Course')
    enrollment_date = models.DateField(verbose_name='تاريخ التسجيل / enrollment Date')
    
    # Accrual accounting fields
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='المبلغ الإجمالي / Total Amount')
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0,
                                          verbose_name='نسبة الخصم % / Discount Percent')
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                         verbose_name='قيمة الخصم / Discount Amount')
    
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS, default='CASH',
                                     verbose_name='طريقة الدفع / Payment Method')
    notes = models.TextField(blank=True, verbose_name='ملاحظات / Notes')
    subjects_note = models.CharField(max_length=255, default='كامل المواد', verbose_name='المواد المسجلة / Registered Subjects')
    is_completed = models.BooleanField(default=False, verbose_name='مكتمل / Completed')
    completion_date = models.DateField(null=True, blank=True, verbose_name='تاريخ الإكمال / Completion Date')
    
    # Journal entry links
    enrollment_journal_entry = models.ForeignKey(JournalEntry, on_delete=models.SET_NULL, null=True, blank=True,
                                                 related_name='enrollments', verbose_name='قيد التسجيل / enrollment Entry')
    completion_journal_entry = models.ForeignKey(JournalEntry, on_delete=models.SET_NULL, null=True, blank=True,
                                                related_name='completions', verbose_name='قيد الإكمال / Completion Entry')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'تسجيل الطالب / Student enrollment'
        verbose_name_plural = 'تسجيلات الطلاب / Student enrollments'
        unique_together = ['student', 'course']
        ordering = ['-enrollment_date']

    def __str__(self):
        return f"{self.student.full_name} - {self.course.name}"

    @property
    def is_active(self):
        """Check if the enrollment is active (i.e., not completed or withdrawn)"""
        return not self.is_completed

    @property
    def net_amount(self):
        """Calculate net amount after discounts"""
        after_percent = self.total_amount - (self.total_amount * self.discount_percent / Decimal('100'))
        return max(Decimal('0'), after_percent - self.discount_amount)

    @property
    def amount_paid(self):
        """Calculate total amount paid for this enrollment"""
        return self.payments.aggregate(total=Sum('paid_amount'))['total'] or Decimal('0')

    @property
    def balance_due(self):
        """Calculate remaining balance due from accounting ledger balance (AR account)"""
        student_ar_account = Account.get_student_ar_account_for_course(self.student, self.course)
        if student_ar_account:
            return max(Decimal('0.00'), student_ar_account.get_net_balance())
        return max(Decimal('0.00'), self.net_amount - self.amount_paid)

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        super().save(*args, **kwargs)
        # On first save, ensure per-enrollment accounts and opening entry
        if is_new:
            try:
                self.ensure_enrollment_accounts()
                # Create the opening accrual entry if not already created
                if not self.enrollment_journal_entry_id and self.net_amount > 0:
                    self.post_opening_entry(getattr(self, '_created_by', None))
            except Exception:
                # Avoid hard failure; UI can message
                pass

    def create_accrual_enrollment_entry(self, user):
        """Create proper accrual accounting entry for student enrollment

        This creates the fundamental accrual entry:
        Dr. Accounts Receivable - Student
        Cr. Course Revenue - Earned

        This recognizes the obligation to provide service and the right to collect payment.
        """
        # Delegate to unified opening entry implementation
        return self.post_opening_entry(user)
        if self.enrollment_journal_entry:
            return self.enrollment_journal_entry
        # Delegate to unified opening entry that books Dr AR / Cr Revenue
        return self.post_opening_entry(user)
        
        print(f"Creating enrollment entry for {self.student.full_name} - {self.course.name}")
        
        # Ensure student has an AR account
        try:
            student_ar_account = self.student.ar_account
            print(f"Student AR account: {student_ar_account.code}")
        except Exception as e:
            raise ValueError(f'Could not get AR account for student: {str(e)}')
        
        # Get or create deferred revenue account for this course
        deferred_account, created = Account.objects.get_or_create(
            code=f'2150-{self.course.id:04d}',
            defaults={
                'name': f'Deferred Revenue - {self.course.name}',
                'name_ar': f'إيرادات مؤجلة - {self.course.name}',
                'account_type': 'LIABILITY',
                'is_course_account': True,
                'course_name': self.course.name,
                'is_active': True,
                'parent': Account.objects.filter(code='2150').first()
            }
        )
        print(f"Deferred revenue account: {deferred_account.code}")
        
        # Create journal entry
        entry = JournalEntry.objects.create(
            reference=f"ENR-{self.student.id}-{self.course.id}",
            date=self.enrollment_date,
            description=f"Student enrollment: {self.student.full_name} - {self.course.name}",
            entry_type='enrollment',
            total_amount=self.net_amount,
            created_by=user
        )
        print(f"Created enrollment journal entry: {entry.reference}")
        
        # Dr. Accounts Receivable - Student
        Transaction.objects.create(
            journal_entry=entry,
            account=student_ar_account,
            amount=self.net_amount,
            is_debit=True,
            description=f"AR for {self.course.name} enrollment"
        )
        
        # Cr. Deferred Revenue - Course
        Transaction.objects.create(
            journal_entry=entry,
            account=deferred_account,
            amount=self.net_amount,
            is_debit=False,
            description=f"Deferred revenue for {self.course.name}"
        )
        
        # Auto-post the entry
        entry.post_entry(user)
        print(f"Posted enrollment entry: {entry.reference}")
        
        # Link to enrollment
        self.enrollment_journal_entry = entry
        self.save(update_fields=['enrollment_journal_entry'])
        
        return entry

    def create_completion_entry(self, user):
        """Create journal entry for course completion (Revenue Recognition)
        
        This converts deferred revenue to earned revenue:
        Dr. Deferred Revenue - Course
        Cr. Course Revenue - Earned
        
        This recognizes that the service has been provided and revenue is now earned.
        """
        if self.completion_journal_entry or not self.is_completed:
            return self.completion_journal_entry
        
        # Create journal entry
        entry = JournalEntry.objects.create(
            reference=f"COMP-{self.student.student_number}-{self.course.id}",
            date=self.completion_date or timezone.now().date(),
            description=f"Course completion: {self.student.full_name} - {self.course.name}",
            entry_type='COMPLETION',
            total_amount=self.net_amount,
            created_by=user
        )
        
        # Dr. Deferred Revenue - Course
        Transaction.objects.create(
            journal_entry=entry,
            account=self.course.deferred_revenue_account,
            amount=self.net_amount,
            is_debit=True,
            description=f"Earned revenue for {self.course.name}"
        )
        
        # Cr. Course Revenue - Earned
        Transaction.objects.create(
            journal_entry=entry,
            account=self.course.earned_revenue_account,
            amount=self.net_amount,
            is_debit=False,
            description=f"Revenue earned from {self.course.name}"
        )
        
        # Auto-post the entry
        entry.post_entry(user)
        
        # Link to enrollment
        self.completion_journal_entry = entry
        self.save(update_fields=['completion_journal_entry'])
        
        return entry

    def complete_course(self, user, completion_date=None):
        """Mark course as completed and create revenue recognition entry"""
        if self.is_completed:
            return
        
        self.is_completed = True
        self.completion_date = completion_date or timezone.now().date()
        self.save(update_fields=['is_completed', 'completion_date'])
        
        # Create completion journal entry
        self.create_completion_entry(user)

    @property
    def net_tuition(self) -> Decimal:
        """Net tuition alias for clarity."""
        return (self.net_amount or Decimal('0')).quantize(Decimal('0.01'))

    def ensure_enrollment_accounts(self):
        """Ensure the per-enrollment AR and revenue accounts exist (idempotent)."""
        get_or_create_course_revenue(self.course)
        get_or_create_enrollment_ar(self.student, self.course)

    @property
    def ar_account(self):
        """AR account for this enrollment (computed)."""
        return get_or_create_enrollment_ar(self.student, self.course)

    @property
    def rev_account(self):
        """Course revenue account (computed)."""
        return get_or_create_course_revenue(self.course)

    def post_opening_entry(self, user):
        """Opening: Dr AR(enrollment) / Cr Course Revenue for net_tuition (once)."""
        if self.enrollment_journal_entry_id:
            return self.enrollment_journal_entry

        amt = self.net_tuition
        if amt <= 0:
            return None

        from .models import JournalEntry, Transaction
        from django.contrib.auth.models import User as AuthUser
        creator = user or getattr(self.student, 'added_by', None) or \
                  AuthUser.objects.filter(is_superuser=True).first() or \
                  AuthUser.objects.order_by('id').first()
        if not creator:
            raise ValueError('No available user for creating journal entry')
        with transaction.atomic():
            je = JournalEntry.objects.create(
                reference=f"ENR-{self.student.id}-{self.course.id}",
                date=self.enrollment_date,
                description=f"Opening accrual for {getattr(self.student, 'full_name', self.student)} in {self.course}",
                entry_type='enrollment',
                total_amount=amt,
                created_by=creator
            )
            Transaction.objects.create(journal_entry=je, account=self.ar_account,  is_debit=True,  amount=amt, description="enrollment receivable")
            Transaction.objects.create(journal_entry=je, account=self.rev_account, is_debit=False, amount=amt, description="Course revenue")
            je.post_entry(creator)
            self.enrollment_journal_entry = je
            self.save(update_fields=['enrollment_journal_entry'])
            return je

    def ar_balance(self) -> Decimal:
        """Live AR balance for this enrollment account (includes all payments)."""
        from .models import Transaction
        a = self.ar_account
        if not a:
            return Decimal('0')
        debit = Transaction.objects.filter(account=a, is_debit=True).aggregate(s=Sum('amount'))['s'] or Decimal('0')
        credit = Transaction.objects.filter(account=a, is_debit=False).aggregate(s=Sum('amount'))['s'] or Decimal('0')
        return (debit - credit).quantize(Decimal('0.01'))

    def check_and_close_if_paid(self):
        """Close the per-enrollment AR when fully paid (balance <= 0)."""
        if self.ar_account and self.ar_balance() <= Decimal('0.00'):
            if not self.closed_at:
                self.closed_at = timezone.now()
                self.save(update_fields=['closed_at'])

    def withdraw(self, user, refund_amount: Decimal = None):
        """Withdraw with refund and receivable reversal; logs audit."""
        from .models import JournalEntry, Transaction
        paid_total = (self.net_tuition - self.ar_balance()).quantize(Decimal('0.01'))
        refund_amt = paid_total if refund_amount is None else Decimal(refund_amount).quantize(Decimal('0.01'))

        returns_parent = get_returns_parent()
        returns_acc, _ = Account.objects.get_or_create(
            code=f'4190-{self.course.id:04d}',
            defaults=dict(
                name=f"Revenue Returns - {getattr(self.course, 'name', self.course)}",
                name_ar=f"مرتجعات الإيرادات - {getattr(self.course, 'name', self.course)}",
                account_type='REVENUE',
                is_active=True,
                parent=returns_parent
            )
        )
        cash = Account.objects.filter(code='121').first()

        with transaction.atomic():
            je = JournalEntry.objects.create(
                reference=f"WDR-{self.student.id}-{self.course.id}",
                date=timezone.now().date(),
                description=f"Withdraw {getattr(self.student, 'full_name', self.student)} from {self.course}",
                entry_type='ADJUSTMENT',
                total_amount=refund_amt,
                created_by=user
            )
            # Refund paid portion
            if refund_amt > 0 and cash:
                Transaction.objects.create(journal_entry=je, account=returns_acc, is_debit=True,  amount=refund_amt, description="Refund paid amount")
                Transaction.objects.create(journal_entry=je, account=cash,        is_debit=False, amount=refund_amt, description="Cash/Bank out")

            # Reverse remaining receivable
            remaining_ar = self.ar_balance()
            if remaining_ar > 0:
                Transaction.objects.create(journal_entry=je, account=returns_acc,   is_debit=True,  amount=remaining_ar, description="Reverse outstanding receivable")
                Transaction.objects.create(journal_entry=je, account=self.ar_account, is_debit=False, amount=remaining_ar, description="Close AR")

            je.post_entry(user)

            # Audit log
            StudentWithdrawal.objects.create(enrollment=self, performed_by=user, refunded_amount=refund_amt)

            # Mark enrollment closed/completed to indicate withdrawal
            self.is_completed = True
            self.closed_at = timezone.now()
            self.save(update_fields=['is_completed', 'closed_at'])

            return je


class StudentReceipt(models.Model):
    PAYMENT_METHODS = [
        ('CASH', 'نقد / Cash'),
        ('BANK', 'بنك / Bank'),
        ('CARD', 'بطاقة / Card'),
        ('TRANSFER', 'تحويل / Transfer'),
    ]

    receipt_number = models.CharField(max_length=50, unique=True, verbose_name='رقم الإيصال / Receipt Number')
    date = models.DateField(verbose_name='التاريخ / Date')
    
    # Student information
    student_profile = models.ForeignKey('students.Student', on_delete=models.PROTECT, null=True, blank=True,
                                       related_name='receipts', verbose_name='ملف الطالب / Student Profile')
    student = models.ForeignKey(Student, on_delete=models.PROTECT, null=True, blank=True,
                               related_name='receipts', verbose_name='الطالب / Student')
    student_name = models.CharField(max_length=200, verbose_name='اسم الطالب / Student Name')
    
    # Course information
    course = models.ForeignKey(Course, on_delete=models.PROTECT, null=True, blank=True,
                              related_name='receipts', verbose_name='الدورة / Course')
    course_name = models.CharField(max_length=200, blank=True, verbose_name='اسم الدورة / Course Name')
    
    # enrollment link for accrual accounting
    enrollment = models.ForeignKey(Studentenrollment, on_delete=models.PROTECT, null=True, blank=True,
                                  related_name='payments', verbose_name='التسجيل / enrollment')
    
    # Payment amounts
    amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                verbose_name='المبلغ / Amount')
    paid_amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='المبلغ المدفوع / Paid Amount')
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0,
                                          verbose_name='نسبة الخصم % / Discount Percent')
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                         verbose_name='قيمة الخصم / Discount Amount')
    
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS, default='CASH',
                                     verbose_name='طريقة الدفع / Payment Method')
    notes = models.TextField(blank=True, verbose_name='ملاحظات / Notes')
    is_printed = models.BooleanField(default=False, verbose_name='مطبوع / Printed')
    
    # Journal entry link
    journal_entry = models.ForeignKey(JournalEntry, on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='receipts', verbose_name='قيد اليومية / Journal Entry')
    
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, verbose_name='أُنشئ بواسطة / Created By')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'إيصال الطالب / Student Receipt'
        verbose_name_plural = 'إيصالات الطلاب / Student Receipts'
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.receipt_number} - {self.student_name}"

    def get_absolute_url(self):
        return reverse('accounts:student_receipt_detail', kwargs={'pk': self.pk})

    def clean(self):
            """Validate receipt not to exceed net due.
            - If linked to an enrollment: use enrollment.net_amount minus prior payments.
            - Else: compute from amount or course price, adjusted by this receipt's own discounts.
            """
            # Determine net due
            net_due = Decimal('0')
            if getattr(self, 'enrollment', None):
                try:
                    net_due = (self.enrollment.net_amount or Decimal('0'))
                except Exception:
                    net_due = Decimal('0')
                # Sum previous payments for the same enrollment, excluding this instance
                previous = StudentReceipt.objects.filter(enrollment=self.enrollment).exclude(pk=self.pk)                         .aggregate(total=Sum('paid_amount'))['total'] or Decimal('0')
            else:
                # Fallback compute from explicit amount or course price
                base = (self.amount or (getattr(self, 'course', None) and self.course.price) or Decimal('0')) or Decimal('0')
                # Apply this-receipt discounts (not global student-level)
                try:
                    pct = self.discount_percent or Decimal('0')
                except Exception:
                    pct = Decimal('0')
                try:
                    disc = self.discount_amount or Decimal('0')
                except Exception:
                    disc = Decimal('0')
                after_percent = base - (base * pct / Decimal('100'))
                net_due = max(Decimal('0'), after_percent - disc)
                # Sum previous payments by student+course
                q = StudentReceipt.objects.none()
                if getattr(self, 'student_profile', None) and getattr(self, 'course', None):
                    q = StudentReceipt.objects.filter(student_profile=self.student_profile, course=self.course)
                elif getattr(self, 'student', None) and getattr(self, 'course', None):
                    q = StudentReceipt.objects.filter(student=self.student, course=self.course)
                previous = q.exclude(pk=self.pk).aggregate(total=Sum('paid_amount'))['total'] or Decimal('0')

            total_with_this = previous + (self.paid_amount or Decimal('0'))
            if total_with_this > net_due:
                raise ValidationError({'paid_amount': f'المدفوع ({total_with_this}) يتجاوز الصافي المطلوب ({net_due}) بعد الحسم.'})

    def create_accrual_journal_entry(self, user):
            """Create cash collection journal entry:
            Dr Cash (121)
            Cr Accounts Receivable (student/enrollment)
            """
            if self.journal_entry:
                return self.journal_entry

            # Cash account 121
            cash_account, _ = Account.objects.get_or_create(
                code='121',
                defaults={'name': 'Cash', 'name_ar': 'النقدية', 'account_type': 'ASSET', 'is_active': True}
            )

            # AR account preference: enrollment AR -> student AR
            ar_account = None
            if getattr(self, 'enrollment', None) and getattr(self.enrollment, 'ar_account', None):
                ar_account = self.enrollment.ar_account
            elif getattr(self, 'student_profile', None):
                ar_account = self.student_profile.ar_account
            elif getattr(self, 'student', None):
                ar_account = self.student.ar_account
            if not ar_account:
                raise ValidationError('لا يوجد حساب ذمم للطالب')

            amount = self.paid_amount or Decimal('0')
            if amount <= 0:
                raise ValidationError('المبلغ المدفوع يجب أن يكون أكبر من صفر')

            with transaction.atomic():
                entry = JournalEntry.objects.create(
                    reference=f"PAY-{self.receipt_number}",
                    description=f"تحصيل إيصال {self.receipt_number} للطالب {getattr(self, 'student_name', '')}",
                    created_by=user,
                    date=getattr(self, 'date', timezone.now().date())
                )
                # Dr Cash
                Transaction.objects.create(
                    entry=entry,
                    account=cash_account,
                    amount=amount,
                    is_debit=True,
                    description=f"تحصيل {getattr(self, 'course', None) and self.course.name or ''}",
                )
                # Cr AR
                Transaction.objects.create(
                    entry=entry,
                    account=ar_account,
                    amount=amount,
                    is_debit=False,
                    description=f"تحصيل {getattr(self, 'course', None) and self.course.name or ''}",
                )
                entry.post_entry(user)

                self.journal_entry = entry
                super(StudentReceipt, self).save(update_fields=['journal_entry'])

                # Attempt auto-close enrollment if fully paid
                try:
                    if getattr(self, 'enrollment', None):
                        self.enrollment.check_and_close_if_paid()
                except Exception:
                    pass

                return entry
    @property
    def is_active(self):
        """Check if the enrollment is active (i.e., not completed or withdrawn)"""
        return not self.is_completed

    @property
    def net_amount(self):
        """Calculate net amount after discounts"""
        if self.amount:
            after_percent = self.amount - (self.amount * self.discount_percent / Decimal('100'))
            return max(Decimal('0'), after_percent - self.discount_amount)
        return self.paid_amount or Decimal('0')

    def get_student_name(self):
        """Get student name from various sources"""
        if self.student_profile:
            return self.student_profile.full_name
        elif self.student:
            return self.student.name
        return self.student_name

    def get_course_name(self):
        """Get course name from various sources"""
        if self.course:
            return self.course.name
        return self.course_name


# Override StudentReceipt.save at import-time to enforce student-scoped numbering
def _studentreceipt_save_override(self, *args, **kwargs):
    if not getattr(self, 'receipt_number', None):
        student_obj = getattr(self, 'student_profile', None) or getattr(self, 'student', None)
        d = getattr(self, 'date', None) or timezone.now().date()
        # Retry a few times to handle edge collisions
        for _ in range(5):
            try:
                try:
                    self.receipt_number = generate_student_receipt_number(student_obj, d)
                except Exception:
                    # Fallback if sequence table is missing
                    scode = _student_code(student_obj)
                    ymd = d.strftime('%Y%m%d')
                    prefix = f"RC-{scode}-{ymd}-"
                    # Next available number
                    for i in range(1, 5000):
                        cand = f"{prefix}{i:03d}"
                        if not StudentReceipt.objects.filter(receipt_number=cand).exists():
                            self.receipt_number = cand
                            break
                break
            except IntegrityError:
                try:
                    transaction.set_rollback(True)
                except Exception:
                    pass
                continue
    # Call base model save to avoid the original method logic
    return models.Model.save(self, *args, **kwargs)


# Apply monkey patch
try:
    original_sr_save = StudentReceipt.save
    StudentReceipt.save = _studentreceipt_save_override
except Exception:
    pass


# Signals: ensure course accounts created on creation
@receiver(post_save, sender=Course)
def ensure_course_accounts(sender, instance, created, **kwargs):
    if not created:
        return
    # Revenue account under 4100
    Account.objects.get_or_create(
        code=f'4100-{instance.id:04d}',
        defaults={
            'name': f"Course Revenue - {instance.name}",
            'name_ar': f"إيرادات الدورة - {instance.name}",
            'account_type': 'REVENUE',
            'is_course_account': True,
            'course_name': instance.name,
            'is_active': True,
            'parent': Account.objects.filter(code='4100').first()
        }
    )
    # Deferred revenue account under 2150
    Account.objects.get_or_create(
        code=f'2150-{instance.id:04d}',
        defaults={
            'name': f"Deferred Revenue - {instance.name}",
            'name_ar': f"إيرادات مؤجلة - {instance.name}",
            'account_type': 'LIABILITY',
            'is_course_account': True,
            'course_name': instance.name,
            'is_active': True,
            'parent': Account.objects.filter(code='2150').first()
        }
    )


@receiver(post_save, sender=Course)
def enforce_course_account_parents(sender, instance, **kwargs):
    """Ensure course revenue account is under revenue parent, whose parent is cash."""
    try:
        parent = get_revenue_parent()
        code = f'4100-{instance.id:04d}'
        acc = Account.objects.filter(code=code).first()
        if acc and acc.parent_id != parent.id:
            acc.parent = parent
            acc.save(update_fields=['parent'])
    except Exception:
        pass


# Auto-assign a unique, student-scoped receipt number before saving receipts
@receiver(pre_save, sender=StudentReceipt)
def ensure_receipt_number(sender, instance, **kwargs):
    try:
        if not getattr(instance, 'receipt_number', None):
            student_obj = getattr(instance, 'student_profile', None) or getattr(instance, 'student', None)
            instance.receipt_number = generate_student_receipt_number(student_obj, getattr(instance, 'date', None))
    except Exception:
        pass
    # Bind as method on the model

class ExpenseEntry(models.Model):
    EXPENSE_CATEGORIES = [
        ('SALARY', 'راتب / Salary'),
        ('TEACHER_SALARY', 'راتب مدرس / Teacher Salary'),
        ('RENT', 'إيجار / Rent'),
        ('UTILITIES', 'مرافق / Utilities'),
        ('SUPPLIES', 'مستلزمات / Supplies'),
        ('MARKETING', 'تسويق / Marketing'),
        ('MAINTENANCE', 'صيانة / Maintenance'),
        ('SALARY', 'راتب / Salary'),
        ('OTHER', 'أخرى / Other'),
    ]

    PAYMENT_METHODS = [
        ('CASH', 'نقد / Cash'),
        ('BANK', 'بنك / Bank'),
        ('CARD', 'بطاقة / Card'),
        ('TRANSFER', 'تحويل / Transfer'),
    ]

    reference = models.CharField(max_length=50, unique=True, verbose_name='المرجع / Reference')
    date = models.DateField(verbose_name='التاريخ / Date')
    description = models.CharField(max_length=500, verbose_name='الوصف / Description')
    category = models.CharField(max_length=20, choices=EXPENSE_CATEGORIES, verbose_name='الفئة / Category')
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='المبلغ / Amount')
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS, default='CASH',
                                     verbose_name='طريقة الدفع / Payment Method')
    vendor = models.CharField(max_length=200, blank=True, verbose_name='المورد / Vendor')
    receipt_number = models.CharField(max_length=100, blank=True, verbose_name='رقم الإيصال / Receipt Number')
    notes = models.TextField(blank=True, verbose_name='ملاحظات / Notes')
    
    # Journal entry link
    journal_entry = models.ForeignKey(JournalEntry, on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='expenses', verbose_name='قيد اليومية / Journal Entry')
    
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, verbose_name='أُنشئ بواسطة / Created By')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'قيد المصروف / Expense Entry'
        verbose_name_plural = 'قيود المصروفات / Expense Entries'
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.reference} - {self.description}"

    def get_absolute_url(self):
        return reverse('accounts:expense_detail', kwargs={'pk': self.pk})

    def create_journal_entry(self, user):
        """Create journal entry for expense (Expense Dr, Cash Cr)"""
        if self.journal_entry:
            return self.journal_entry
        
        # Determine expense account based on category
        expense_account_codes = {
            'SALARY': '501',
            'TEACHER_SALARY': '5101',
            'RENT': '5200',
            'UTILITIES': '5300',
            'SUPPLIES': '5400',
            'MARKETING': '5500',
            'MAINTENANCE': '502',
            'OTHER': '5900',
        }

        exp_code = expense_account_codes.get(self.category, '5900')
        expense_account = Account.objects.filter(code=exp_code).first()

        # Auto-create missing expense accounts under their likely parents when needed
        if not expense_account:
            parent_code = exp_code[:-1] + '0' if len(exp_code) == 4 else exp_code
            parent = Account.objects.filter(code=parent_code).first()
            if not parent and len(exp_code) == 4:
                # Create or get parent (e.g., 501 for 5101)
                parent, _ = Account.objects.get_or_create(
                    code=parent_code,
                    defaults=dict(
                        name='Expenses',
                        name_ar='المصروفات',
                        account_type='EXPENSE',
                        is_active=True,
                    ),
                )
            expense_account, _ = Account.objects.get_or_create(
                code=exp_code,
                defaults=dict(
                    name=(
                        'Teacher Salary' if self.category == 'TEACHER_SALARY' else
                        'Salary' if self.category == 'SALARY' else
                        f'Expense {self.category}'
                    ),
                    name_ar=(
                        'راتب مدرس' if self.category == 'TEACHER_SALARY' else
                        'راتب' if self.category == 'SALARY' else
                        f'مصروف {self.category}'
                    ),
                    account_type='EXPENSE',
                    is_active=True,
                    parent=parent,
                ),
            )
            # Ensure parent linkage is correct
            if parent and expense_account.parent_id != parent.id:
                expense_account.parent = parent
                expense_account.save(update_fields=['parent'])
        
        # Determine cash account
        cash_account, _ = Account.objects.get_or_create(
            code='121',
            defaults=dict(name='Cash', name_ar='الصندوق', account_type='ASSET', is_active=True),
        )
        
        # Create journal entry
        entry = JournalEntry.objects.create(
            reference=f"EXP-{self.reference}",
            date=self.date,
            description=f"Expense: {self.description}",
            entry_type='EXPENSE',
            total_amount=self.amount,
            created_by=user
        )
        
        # Dr. Expense Account
        Transaction.objects.create(
            journal_entry=entry,
            account=expense_account,
            amount=self.amount,
            is_debit=True,
            description=self.description
        )
        
        # Cr. Cash
        Transaction.objects.create(
            journal_entry=entry,
            account=cash_account,
            amount=self.amount,
            is_debit=False,
            description=f"Cash paid for {self.description}"
        )
        
        # Auto-post the entry
        entry.post_entry(user)
        
        # Link to expense
        self.journal_entry = entry
        self.save(update_fields=['journal_entry'])
        
        return entry

    def save(self, *args, **kwargs):
        if not self.reference:
            # Auto-generate reference
            today = timezone.now().date()
            count = ExpenseEntry.objects.filter(date=today).count() + 1
            self.reference = f"EXP-{today.strftime('%Y%m%d')}-{count:03d}"
        super().save(*args, **kwargs)


class StudentWithdrawal(models.Model):
    enrollment = models.ForeignKey('accounts.Studentenrollment', on_delete=models.CASCADE, related_name='withdraw_logs')
    performed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    refunded_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class EmployeeAdvance(models.Model):
    employee_name = models.CharField(max_length=200, verbose_name='اسم الموظف / Employee Name')
    date = models.DateField(verbose_name='التاريخ / Date')
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='المبلغ / Amount')
    purpose = models.CharField(max_length=500, verbose_name='الغرض / Purpose')
    repayment_date = models.DateField(null=True, blank=True, verbose_name='تاريخ السداد / Repayment Date')
    is_repaid = models.BooleanField(default=False, verbose_name='مسدد / Repaid')
    repaid_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                       verbose_name='المبلغ المسدد / Repaid Amount')
    reference = models.CharField(max_length=50, unique=True, verbose_name='المرجع / Reference')
    
    # Journal entry link
    journal_entry = models.ForeignKey(JournalEntry, on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='advances', verbose_name='قيد اليومية / Journal Entry')
    
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, verbose_name='أُنشئ بواسطة / Created By')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'سلفة الموظف / Employee Advance'
        verbose_name_plural = 'سلف الموظفين / Employee Advances'
        ordering = ['-date']

    def __str__(self):
        return f"{self.employee_name} - {self.amount}"

    def get_absolute_url(self):
        return reverse('accounts:advance_detail', kwargs={'pk': self.pk})

    @property
    def outstanding_amount(self):
        """Calculate outstanding advance amount"""
        return max(Decimal('0'), self.amount - self.repaid_amount)

    def create_advance_entry(self, user):
        """Create journal entry for employee advance (Advance Dr, Cash Cr)"""
        if self.journal_entry:
            return self.journal_entry
        
        # Get employee advances account
        advance_account = Account.objects.filter(code='1160').first()
        if not advance_account:
            # Auto-create 1160 under Assets if missing
            assets_parent = Account.objects.filter(code='1100').first()
            advance_account, _ = Account.objects.get_or_create(
                code='1160',
                defaults=dict(
                    name='Employee Advances',
                    name_ar='سلف الموظفين',
                    account_type='ASSET',
                    is_active=True,
                    parent=assets_parent,
                ),
            )
        
        # Get cash account
        cash_account, _ = Account.objects.get_or_create(
            code='121',
            defaults=dict(name='Cash', name_ar='الصندوق', account_type='ASSET', is_active=True),
        )
        
        # Create journal entry
        entry = JournalEntry.objects.create(
            reference=f"ADV-{self.reference}",
            date=self.date,
            description=f"Employee advance: {self.employee_name} - {self.purpose}",
            entry_type='EXPENSE',
            total_amount=self.amount,
            created_by=user
        )
        
        # Dr. Employee Advances
        Transaction.objects.create(
            journal_entry=entry,
            account=advance_account,
            amount=self.amount,
            is_debit=True,
            description=f"Advance to {self.employee_name}"
        )
        
        # Cr. Cash
        Transaction.objects.create(
            journal_entry=entry,
            account=cash_account,
            amount=self.amount,
            is_debit=False,
            description=f"Cash advance paid to {self.employee_name}"
        )
        
        # Auto-post the entry
        entry.post_entry(user)
        
        # Link to advance
        self.journal_entry = entry
        self.save(update_fields=['journal_entry'])
        
        return entry

    def save(self, *args, **kwargs):
        if not self.reference:
            # Auto-generate reference
            today = timezone.now().date()
            count = EmployeeAdvance.objects.filter(date=today).count() + 1
            self.reference = f"ADV-{today.strftime('%Y%m%d')}-{count:03d}"
        super().save(*args, **kwargs)


class Budget(models.Model):
    account = models.ForeignKey(Account, on_delete=models.CASCADE, verbose_name='الحساب / Account')
    period = models.ForeignKey(AccountingPeriod, on_delete=models.CASCADE, verbose_name='الفترة / Period')
    budgeted_amount = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='المبلغ المخطط / Budgeted Amount')
    actual_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0,
                                       verbose_name='المبلغ الفعلي / Actual Amount')
    notes = models.TextField(blank=True, verbose_name='ملاحظات / Notes')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'الميزانية / Budget'
        verbose_name_plural = 'الميزانيات / Budgets'
        unique_together = ['account', 'period']

    def __str__(self):
        return f"{self.account.name} - {self.period.name}"

    @property
    def variance(self):
        """Calculate budget variance"""
        return self.actual_amount - self.budgeted_amount

    def calculate_variance(self):
        """Calculate and return variance"""
        return self.variance


class StudentAccountLink(models.Model):
    """Link between students app Student and accounts app Account for AR tracking"""
    student = models.OneToOneField('students.Student', on_delete=models.CASCADE, 
                                  related_name='account_link', verbose_name='الطالب / Student')
    account = models.OneToOneField(Account, on_delete=models.CASCADE, 
                                  related_name='student_link', verbose_name='الحساب / Account')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'ربط حساب الطالب / Student Account Link'
        verbose_name_plural = 'روابط حسابات الطلاب / Student Account Links'

    def __str__(self):
        return f"{self.student.full_name} -> {self.account.code}"

    @classmethod
    def get_or_create_for_student(cls, student):
        """Get or create account link for a student"""
        try:
            return cls.objects.get(student=student)
        except cls.DoesNotExist:
            # Create AR account for student
            account = Account.objects.create(
                code=f"1120-{student.id:04d}",
                name=f"AR - {student.full_name}",
                name_ar=f"ذمم مدينة - {student.full_name}",
                account_type='ASSET',
                is_student_account=True,
                student_name=student.full_name,
                parent=Account.objects.filter(code='1120').first()
            )
            
            return cls.objects.create(student=student, account=account)


# ---- Partner payment helper ----
def create_partner_payment_entry(partner_name: str, amount: Decimal, user: User, date=None) -> 'JournalEntry':
    """
    Pay partners' account: Dr Partners' Capital (Equity 301) / Cr Cash (121).
    Creates accounts if missing. Returns the posted JournalEntry.
    """
    if amount is None or Decimal(amount) <= 0:
        raise ValueError('Amount must be greater than zero')
    amt = Decimal(amount).quantize(Decimal('0.01'))
    d = date or timezone.now().date()

    cash, _ = Account.objects.get_or_create(
        code='121',
        defaults=dict(name='Cash', name_ar='الصندوق', account_type='ASSET', is_active=True),
    )
    partners_capital, _ = Account.objects.get_or_create(
        code='301',
        defaults=dict(name="Partners' Capital", name_ar='رأس مال الشركاء', account_type='EQUITY', is_active=True),
    )

    # Numbered reference per day
    ref = f"PRT-{d.strftime('%Y%m%d')}-{next_sequence_value(f'partnerpay-{d:%Y%m%d}'):03d}"

    je = JournalEntry.objects.create(
        reference=ref,
        date=d,
        description=f"Partner payment to {partner_name}",
        entry_type='EXPENSE',
        total_amount=amt,
        created_by=user,
    )
    # Dr Equity (reduces equity) / Cr Cash
    Transaction.objects.create(journal_entry=je, account=partners_capital, amount=amt, is_debit=True, description=f"Distribution to {partner_name}")
    Transaction.objects.create(journal_entry=je, account=cash,             amount=amt, is_debit=False, description=f"Cash out to {partner_name}")
    je.post_entry(user)
    return je

# =============
def create_proper_enrollment_entry(self, user):
    """إنشاء قيد محاسبي صحيح لتسجيل الطالب"""
    if self.enrollment_journal_entry:
        return self.enrollment_journal_entry
    
    # الحسابات المطلوبة
    student_ar_account = self.student.ar_account
    course_revenue_account = self.course.earned_revenue_account
    
    # إنشاء قيد اليومية
    entry = JournalEntry.objects.create(
        reference=f"ENR-{self.student.id}-{self.course.id}-{timezone.now().timestamp()}",
        date=self.enrollment_date,
        description=f"تسجيل الطالب {self.student.full_name} في دورة {self.course.name}",
        entry_type='enrollment',
        total_amount=self.net_amount,
        created_by=user
    )
    
    # المدين: ذمم الطالب
    Transaction.objects.create(
        journal_entry=entry,
        account=student_ar_account,
        amount=self.net_amount,
        is_debit=True,
        description=f"ذمم مدينة - {self.course.name}"
    )
    
    # الدائن: إيراد الدورات
    Transaction.objects.create(
        journal_entry=entry,
        account=course_revenue_account,
        amount=self.net_amount,
        is_debit=False,
        description=f"إيراد دورة - {self.course.name}"
    )
    
    # ترحيل القيد
    entry.post_entry(user)
    
    # ربط القيد بالتسجيل
    self.enrollment_journal_entry = entry
    self.save(update_fields=['enrollment_journal_entry'])
    
    return entry