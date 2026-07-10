
// student_profile.js
document.addEventListener('DOMContentLoaded', function() {
    console.log('تهيئة صفحة الطالب...');
    
    // تهيئة التبويبات
    initTabs();
    
    // تهيئة المودالات
    initModals();
    
    // ✅ تهيئة تنسيق الأرقام - يجب أن تكون في البداية
    setupNumberFormatting();
    
    // تهيئة الإيصال الفوري
    initQuickReceipt();
    
    // تهيئة الاسترداد
    initRefundStudent();
    
    // تهيئة سحب الطالب
    initWithdrawStudent();
    
    // تهيئة أزرار سحب الدورات الفردية
    initCourseWithdrawButtons();
    
    // تهيئة تحديث الخصم
    initDiscountUpdate();
    
    // تهيئة تحديث المواد المسجلة بالدورة
    initSubjectsUpdate();
});

// ✅ دالة محسنة لتنسيق الأرقام مع فواصل كل 3 خانات كـ "ملايين"
function formatNumber(number) {
    if (isNaN(number) || number === null || number === '') return '0';
    
    const num = parseFloat(number);
    if (isNaN(num)) return '0';
    
    // استخدام toLocaleString للتنسيق مع إزالة الكسور
    return num.toLocaleString('en-US', {
        maximumFractionDigits: 0,
        minimumFractionDigits: 0
    });
}

// ✅ تحويل الأرقام العربية/الفارسية إلى أرقام لاتينية
function normalizeDigits(value) {
    return (value || '').toString()
        .replace(/[٠-٩]/g, d => String('٠١٢٣٤٥٦٧٨٩'.indexOf(d)))
        .replace(/[۰-۹]/g, d => String('۰۱۲۳۴۵۶۷۸۹'.indexOf(d)));
}

// ✅ دالة محسنة لتحويل الأرقام المنسقة
function parseFormattedNumber(formattedNumber) {
    if (!formattedNumber) return 0;

    let cleanStr = normalizeDigits(formattedNumber);
    cleanStr = cleanStr.replace(/[,\s٬،]/g, '');
    cleanStr = cleanStr.replace(/[^\d]/g, '');

    const number = parseFloat(cleanStr);
    return isNaN(number) ? 0 : number;
}

// ✅ تهيئة تنسيق الأرقام المحسنة
function setupNumberFormatting() {
    document.querySelectorAll('.formatted-input').forEach(input => {
        // تنسيق أولي إذا كانت هناك قيمة
        if (input.value && input.value !== '0') {
            formatNumberInput(input);
        }
        
        input.addEventListener('focus', function() {
            // عند التركيز، نعرض الرقم بدون تنسيق للتحرير
            const rawValue = parseFormattedNumber(this.value);
            this.value = rawValue === 0 ? '' : rawValue.toString();
            this.select(); // تحديد النص بالكامل لتسهيل التعديل
        });
        
        input.addEventListener('blur', function() {
            // عند فقدان التركيز، نعيد التنسيق
            formatNumberInput(this);
        });
        
        input.addEventListener('input', function() {
            // أثناء الكتابة، نسمح بالأرقام (مع دعم الأرقام العربية/الفارسية)
            let normalized = normalizeDigits(this.value);
            normalized = normalized.replace(/[^\d]/g, '');
            this.value = normalized;
        });
    });
}

// ✅ دالة محسنة لتنسيق حقل الإدخال
function formatNumberInput(input) {
    let value = input.value;
    
    if (value === '' || value === '0') {
        input.value = '0';
        return;
    }
    
    // تنظيف القيمة من أي أحرف غير مرغوب فيها مع دعم الأرقام العربية/الفارسية
    value = normalizeDigits(value).replace(/[^\d]/g, '');
    
    // تحويل إلى رقم
    const number = parseFormattedNumber(value);
    
    // تنسيق الرقم بدون كسور
    input.value = formatNumber(number);
}

// تهيئة نظام التبويبات
function initTabs() {
    const tabButtons = document.querySelectorAll('.tab-btn');
    
    tabButtons.forEach(button => {
        button.addEventListener('click', function() {
            // إزالة النشاط من جميع الأزرار
            tabButtons.forEach(btn => btn.classList.remove('active'));
            
            // إضافة النشاط للزر المختار
            this.classList.add('active');
            
            // إخفاء جميع محتويات التبويبات
            const tabPanels = document.querySelectorAll('.tab-panel');
            tabPanels.forEach(panel => panel.classList.remove('active'));
            
            // إظهار المحتوى المطلوب
            const tabId = this.getAttribute('data-tab');
            const targetPanel = document.getElementById(tabId + '-tab');
            if (targetPanel) {
                targetPanel.classList.add('active');
            }
        });
    });
}

// تهيئة نظام المودالات
function initModals() {
    // إغلاق المودال عند النقر خارج المحتوى
    document.addEventListener('click', function(e) {
        if (e.target.classList.contains('modal-overlay')) {
            closeAllModals();
        }
    });
    
    // إغلاق المودال عند النقر على زر الإغلاق
    document.querySelectorAll('.close-btn, [data-close]').forEach(btn => {
        btn.addEventListener('click', function() {
            const modal = this.closest('.modal');
            if (modal) {
                closeModal(modal);
            }
        });
    });
    
    // إغلاق المودال عند الضغط على زر Escape
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            closeAllModals();
        }
    });
}

// فتح مودال
function openModal(modal) {
    if (modal) {
        modal.style.display = 'flex';
        document.body.style.overflow = 'hidden';
    }
}

// إغلاق مودال
function closeModal(modal) {
    if (modal) {
        modal.style.display = 'none';
        document.body.style.overflow = '';
    }
}

// إغلاق جميع المودالات
function closeAllModals() {
    document.querySelectorAll('.modal').forEach(modal => {
        closeModal(modal);
    });
}

// تهيئة نظام الإيصال الفوري
function initQuickReceipt() {
    const quickReceiptBtn = document.getElementById('quick-receipt-btn');
    const quickReceiptModal = document.getElementById('quickReceiptModal');
    
    if (!quickReceiptBtn || !quickReceiptModal) {
        console.error('لم يتم العثور على عناصر الإيصال الفوري');
        return;
    }
    
    // فتح مودال الإيصال الفوري
    quickReceiptBtn.addEventListener('click', function(e) {
        e.preventDefault();
        console.log('فتح مودال الإيصال الفوري');
        openModal(quickReceiptModal);
        initReceiptCalculations();
        setupNumberFormatting(); // ✅ إضافة هذا السطر
    });
    
    // معالجة حفظ الإيصال
    const saveBtn = document.getElementById('qr-save');
    if (saveBtn) {
        saveBtn.addEventListener('click', processQuickReceipt);
    }
    
    // إلغاء العملية
    const cancelBtn = document.getElementById('qr-cancel');
    if (cancelBtn) {
        cancelBtn.addEventListener('click', function() {
            closeModal(quickReceiptModal);
        });
    }
}

// ✅ تهيئة الحسابات التلقائية للإيصال المحسنة
function initReceiptCalculations() {
    const courseSelect = document.getElementById('qr-course');
    const amountInput = document.getElementById('qr-amount');
    const discPctInput = document.getElementById('qr-disc-pct');
    const discAmtInput = document.getElementById('qr-disc-amt');
    const paidInput = document.getElementById('qr-paid');
    const freeToggle = document.getElementById('qr-free-toggle');
    
    if (!courseSelect) return;
    
    // إعادة تعيين القيم
    if (paidInput) paidInput.value = '0';
    if (discAmtInput) discAmtInput.value = '0';
    
    // عند تغيير الدورة
    courseSelect.addEventListener('change', function() {
        const selectedOption = this.options[this.selectedIndex];
        
        if (selectedOption && selectedOption.value) {
            const price = parseFloat(selectedOption.getAttribute('data-price')) || 0;
            const remaining = parseFloat(selectedOption.getAttribute('data-remaining')) || 0;
            
            console.log('سعر الدورة:', price, 'المتبقي:', remaining);

            if (amountInput) {
                amountInput.value = formatNumber(price);
            }
            
            if (paidInput) {
                paidInput.value = '0';
            }
            
            if (discAmtInput) {
                discAmtInput.value = '0';
            }
            
            // ✅ تحديث عرض المبلغ الصافي
            updateNetAmountDisplay();
            
            // ✅ إزالة أي قيود على المبلغ المدفوع
            if (paidInput) {
                paidInput.removeAttribute('data-max');
                paidInput.removeAttribute('title');
            }
        } else if (amountInput) {
            amountInput.value = '0';
        }
    });
    
    // تحديث الحسابات عند تغيير القيم
    [discPctInput, discAmtInput, paidInput].forEach(input => {
        if (input) {
            input.addEventListener('input', function() {
                // ✅ تحديث فوري للحسابات
                updateNetAmountDisplay();
            });
        }
    });
    
    // ✅ إضافة تنسيق لحقول الخصم والمبلغ المدفوع
    [discAmtInput, paidInput].forEach(input => {
        if (input) {
            input.addEventListener('blur', function() {
                formatNumberInput(this);
            });
        }
    });

    if (freeToggle) {
        freeToggle.addEventListener('change', applyFreeToggleState);
    }
    applyFreeToggleState();
    
    // تشغيل حدث التغيير لأول مرة إذا كانت هناك دورة محددة
    if (courseSelect.options.length > 1 && courseSelect.options[1].value) {
        courseSelect.selectedIndex = 1;
        const event = new Event('change');
        courseSelect.dispatchEvent(event);
    }
}

// حساب المبلغ الصافي
function calculateNetAmount() {
    const freeToggle = document.getElementById('qr-free-toggle');
    if (freeToggle && freeToggle.checked) {
        return 0;
    }

    const courseSelect = document.getElementById('qr-course');
    const discPctInput = document.getElementById('qr-disc-pct');
    const discAmtInput = document.getElementById('qr-disc-amt');
    
    const selectedOption = courseSelect?.options[courseSelect.selectedIndex];
    const price = selectedOption ? parseFloat(selectedOption.getAttribute('data-price')) || 0 : 0;
    const discPct = parseFloat(discPctInput?.value) || 0;
    const discAmt = parseFormattedNumber(discAmtInput?.value) || 0;
    
    const discountFromPercentage = price * (discPct / 100);
    const netAmount = Math.max(0, price - discountFromPercentage - discAmt);
    
    return netAmount;
}

function isFreeReceipt() {
    const freeToggle = document.getElementById('qr-free-toggle');
    if (freeToggle && freeToggle.checked) {
        return true;
    }

    const courseSelect = document.getElementById('qr-course');
    const selectedOption = courseSelect?.options[courseSelect.selectedIndex];
    const price = selectedOption ? parseFloat(selectedOption.getAttribute('data-price')) || 0 : 0;
    const discPctInput = document.getElementById('qr-disc-pct');
    const discAmtInput = document.getElementById('qr-disc-amt');
    const discPct = parseFloat(discPctInput?.value) || 0;
    const discAmt = parseFormattedNumber(discAmtInput?.value) || 0;
    const netAmount = Math.max(0, price - (price * (discPct / 100)) - discAmt);

    return price > 0 && netAmount <= 0;
}

function applyFreeToggleState() {
    const freeToggle = document.getElementById('qr-free-toggle');
    const discPctInput = document.getElementById('qr-disc-pct');
    const discAmtInput = document.getElementById('qr-disc-amt');
    const paidInput = document.getElementById('qr-paid');
    const isFree = isFreeReceipt();

    [discPctInput, discAmtInput, paidInput].forEach(input => {
        if (!input) return;
        if (isFree) {
            input.value = '0';
            input.setAttribute('readonly', 'readonly');
        } else {
            input.removeAttribute('readonly');
        }
    });

    updateNetAmountDisplay();
}

// ✅ تحديث عرض المبلغ الصافي المحسن
function updateNetAmountDisplay() {
    const netAmountDiv = document.getElementById('qr-net');
    const netValueSpan = document.getElementById('qr-net-value');
    const courseSelect = document.getElementById('qr-course');
    const isFree = isFreeReceipt();
    
    if (!netAmountDiv || !netValueSpan || !courseSelect) return;
    
    const selectedOption = courseSelect.options[courseSelect.selectedIndex];
    const price = selectedOption ? parseFloat(selectedOption.getAttribute('data-price')) || 0 : 0;
    
    if (!isFree && price <= 0) {
        netAmountDiv.style.display = 'none';
        return;
    }
    
    const netAmount = calculateNetAmount();
    netAmountDiv.style.display = 'block';
    netValueSpan.textContent = formatNumber(netAmount);
    
    // تلوين النتيجة
    if (netAmount <= 0) {
        netAmountDiv.style.color = '#dc3545';
        netAmountDiv.style.background = '#f8d7da';
    } else {
        netAmountDiv.style.color = '#155724';
        netAmountDiv.style.background = '#d4edda';
    }
}

// ✅ معالجة حفظ الإيصال الفوري المحسنة
function processQuickReceipt() {
    const courseSelect = document.getElementById('qr-course');
    const discPctInput = document.getElementById('qr-disc-pct');
    const discAmtInput = document.getElementById('qr-disc-amt');
    const paidInput = document.getElementById('qr-paid');
    const dateInput = document.getElementById('qr-date');
    const saveBtn = document.getElementById('qr-save');
    const isFree = isFreeReceipt();
    
    // ✅ التأكد من تنسيق جميع الحقول قبل الإرسال
    [discAmtInput, paidInput].forEach(input => {
        if (input) formatNumberInput(input);
    });
    
    // التحقق من الحقول المطلوبة
    if (!courseSelect || !courseSelect.value) {
        alert('يرجى اختيار دورة');
        return;
    }
    
    const selectedOption = courseSelect.options[courseSelect.selectedIndex];
    const courseId = selectedOption.value;
    const enrollmentId = selectedOption.getAttribute('data-enrollment-id');
    const courseName = selectedOption.getAttribute('data-course-name');
    const price = parseFloat(selectedOption.getAttribute('data-price')) || 0;
    const discPct = parseFloat(discPctInput?.value) || 0;
    const discAmt = parseFormattedNumber(discAmtInput?.value) || 0;
    const netAmount = calculateNetAmount();
    const paid = isFree ? 0 : (parseFormattedNumber(paidInput?.value) || 0);
    const date = dateInput?.value;
    
    if (!isFree && price <= 0) {
        alert('يرجى اختيار دورة صحيحة');
        return;
    }
    
    if (!isFree && netAmount > 0 && paid <= 0) {
        alert('يرجى إدخال مبلغ مدفوع صحيح');
        return;
    }
    
    // ✅ إزالة التحقق من أن المبلغ المدفوع لا يتجاوز المبلغ الصافي
    // يمكن للمستخدم الآن إدخال أي مبلغ يريده
    
    // تأكيد العملية
    const confirmMessage = isFree
        ? `سيتم إنشاء إيصال مجاني (0 ل.س) للدورة "${courseName}" دون تعديل الرصيد. هل تريد المتابعة؟`
        : `هل تريد قطع إيصال بقيمة ${formatNumber(paid)} ل.س لدورة "${courseName}"؟`;
    if (!confirm(confirmMessage)) {
        return;
    }
    
    // تعطيل زر الحفظ أثناء المعالجة
    if (saveBtn) {
        saveBtn.disabled = true;
        saveBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> جاري الحفظ...';
    }
    
    // إرسال البيانات إلى الخادم
    const formData = new FormData();
    formData.append('course_id', courseId);
    formData.append('enrollment_id', enrollmentId);
    formData.append('amount', isFree ? 0 : netAmount); // استخدام السعر بعد الخصم أو صفر في حالة المجاني
    formData.append('discount_percent', discPct);
    formData.append('discount_amount', discAmt);
    formData.append('paid_amount', paid);
    formData.append('receipt_date', date);
    formData.append('is_free', isFree ? 'true' : 'false');
    
    fetch('"django_tag"', {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCSRFToken(),
        },
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.ok) {
            alert('تم حفظ الإيصال بنجاح');
            closeModal(document.getElementById('quickReceiptModal'));
            
            // ✅ التحويل إلى صفحة طباعة الإيصال
            if (data.receipt_id) {
                window.open('"django_tag"'.replace('0', data.receipt_id), '_blank');
            }
            
            // إعادة تحميل الصفحة لتحديث البيانات
            window.location.reload();
        } else {
            alert('حدث خطأ: ' + (data.error || 'يرجى المحاولة مرة أخرى'));
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('حدث خطأ في الاتصال بالخادم');
    })
    .finally(() => {
        // إعادة تمكين زر الحفظ
        if (saveBtn) {
            saveBtn.disabled = false;
            saveBtn.innerHTML = '<i class="fas fa-save"></i> حفظ الإيصال';
        }
    });
}

// تهيئة نظام الاسترداد
function initRefundStudent() {
    const refundBtn = document.getElementById('refund-student-btn');
    const refundModal = document.getElementById('refundModal');
    
    if (!refundBtn || !refundModal) {
        console.error('لم يتم العثور على عناصر الاسترداد');
        return;
    }
    
    // فتح مودال الاسترداد
    refundBtn.addEventListener('click', function(e) {
        e.preventDefault();
        console.log('فتح مودال الاسترداد');
        openModal(refundModal);
        initRefundCalculations();
    });
    
    // معالجة تأكيد الاسترداد
    const confirmBtn = document.getElementById('refund-confirm');
    if (confirmBtn) {
        confirmBtn.addEventListener('click', processRefund);
    }
    
    // إلغاء العملية
    const cancelBtn = document.getElementById('refund-cancel');
    if (cancelBtn) {
        cancelBtn.addEventListener('click', function() {
            closeModal(refundModal);
        });
    }
}

// تهيئة الحسابات التلقائية للاسترداد
function initRefundCalculations() {
    const courseSelect = document.getElementById('refund-course');
    const refundInput = document.getElementById('refund-amount');
    
    if (!courseSelect) return;
    
    // إعادة تعيين القيم
    if (refundInput) refundInput.value = '0';
    
    // عند تغيير الدورة
    courseSelect.addEventListener('change', function() {
        const selectedOption = this.options[this.selectedIndex];
        
        if (selectedOption && selectedOption.value) {
            const paid = parseFloat(selectedOption.getAttribute('data-paid')) || 0;
            const courseName = selectedOption.getAttribute('data-course-name');
            
            if (refundInput) {
                refundInput.value = '0';
            }
            
            updateRefundWarning(selectedOption);
        }
    });
    
    // التحقق من مبلغ الاسترداد
    if (refundInput) {
        refundInput.addEventListener('input', function() {
            const selectedOption = courseSelect.options[courseSelect.selectedIndex];
            updateRefundWarning(selectedOption);
        });
    }
}

// تحديث التحذيرات في نموذج الاسترداد
function updateRefundWarning(selectedOption) {
    const warningDiv = document.getElementById('refund-warning');
    const warningText = document.getElementById('refund-warning-text');
    const refundInput = document.getElementById('refund-amount');
    
    if (!warningDiv || !warningText || !refundInput) return;
    
    const refund = parseFormattedNumber(refundInput.value) || 0;
    const courseName = selectedOption ? selectedOption.getAttribute('data-course-name') : '';
    
    if (refund > 0) {
        warningDiv.style.display = 'block';
        warningText.textContent = `سيتم استرداد ${formatNumber(refund)} ل.س للطالب من دورة "${courseName}"`;
        warningDiv.className = 'alert alert-warning';
    } else {
        warningDiv.style.display = 'none';
    }
}

// معالجة استرداد المبلغ
function processRefund() {
    const courseSelect = document.getElementById('refund-course');
    const reasonInput = document.getElementById('refund-reason');
    const refundInput = document.getElementById('refund-amount');
    const confirmBtn = document.getElementById('refund-confirm');
    
    if (!courseSelect || !courseSelect.value) {
        alert('يرجى اختيار دورة');
        return;
    }
    
    const selectedOption = courseSelect.options[courseSelect.selectedIndex];
    const enrollmentId = selectedOption.value;
    const courseName = selectedOption.getAttribute('data-course-name');
    const reason = reasonInput?.value || '';
    const refund = parseFormattedNumber(refundInput?.value) || 0;
    
    if (refund <= 0) {
        alert('يرجى إدخال مبلغ استرداد صحيح');
        return;
    }
    
    if (!confirm(`هل تريد استرداد ${formatNumber(refund)} ل.س للطالب من دورة "${courseName}"؟`)) {
        return;
    }
    
    // تعطيل زر التأكيد أثناء المعالجة
    if (confirmBtn) {
        confirmBtn.disabled = true;
        confirmBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> جاري الاسترداد...';
    }
    
    // إرسال البيانات إلى الخادم
    const formData = new FormData();
    formData.append('enrollment_id', enrollmentId);
    formData.append('refund_reason', reason);
    formData.append('refund_amount', refund);
    
    fetch('"django_tag"', {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCSRFToken(),
        },
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.ok) {
            alert(data.message || 'تم استرداد المبلغ بنجاح');
            closeModal(document.getElementById('refundModal'));
            window.location.reload();
        } else {
            alert('حدث خطأ: ' + (data.error || 'يرجى المحاولة مرة أخرى'));
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('حدث خطأ في الاتصال بالخادم');
    })
    .finally(() => {
        if (confirmBtn) {
            confirmBtn.disabled = false;
            confirmBtn.innerHTML = '<i class="fas fa-money-bill-wave"></i> تأكيد الاسترداد';
        }
    });
}

// تهيئة نظام سحب الطالب
function initWithdrawStudent() {
    const withdrawBtn = document.getElementById('withdraw-student-btn');
    const withdrawModal = document.getElementById('withdrawModal');
    
    if (!withdrawBtn || !withdrawModal) {
        console.error('لم يتم العثور على عناصر السحب');
        return;
    }
    
    // فتح مودال السحب
    withdrawBtn.addEventListener('click', function(e) {
        e.preventDefault();
        console.log('فتح مودال السحب');
        openModal(withdrawModal);
        initWithdrawCalculations();
    });
    
    // معالجة تأكيد السحب
    const confirmBtn = document.getElementById('withdraw-confirm');
    if (confirmBtn) {
        confirmBtn.addEventListener('click', processWithdraw);
    }
    
    // إلغاء العملية
    const cancelBtn = document.getElementById('withdraw-cancel');
    if (cancelBtn) {
        cancelBtn.addEventListener('click', function() {
            closeModal(withdrawModal);
        });
    }
}

// تهيئة الحسابات التلقائية للسحب
function initWithdrawCalculations() {
    const courseSelect = document.getElementById('withdraw-course');
    const refundInput = document.getElementById('withdraw-refund');
    
    if (!courseSelect) {
        console.error('لم يتم العثور على قائمة الدورات للسحب');
        return;
    }
    
    console.log('عدد الدورات المتاحة للسحب:', courseSelect.options.length);
    
    // إعادة تعيين القيم
    if (refundInput) refundInput.value = '0';
    
    // عند تغيير الدورة
    courseSelect.addEventListener('change', function() {
        const selectedOption = this.options[this.selectedIndex];
        console.log('تم اختيار دورة للسحب:', selectedOption.text);
        
        if (selectedOption && selectedOption.value) {
            const paid = parseFloat(selectedOption.getAttribute('data-paid')) || 0;
            const courseName = selectedOption.getAttribute('data-course-name');
            
            if (refundInput) {
                refundInput.value = '0';
            }
            
            updateWithdrawWarning(selectedOption);
        }
    });
    
    // التحقق من مبلغ الإرجاع
    if (refundInput) {
        refundInput.addEventListener('input', function() {
            const selectedOption = courseSelect.options[courseSelect.selectedIndex];
            updateWithdrawWarning(selectedOption);
        });
    }
    
    // تشغيل حدث التغيير لأول مرة إذا كانت هناك دورة محددة
    if (courseSelect.options.length > 1 && courseSelect.options[1].value) {
        courseSelect.selectedIndex = 1;
        const event = new Event('change');
        courseSelect.dispatchEvent(event);
    }
}

// تحديث التحذيرات في نموذج السحب
function updateWithdrawWarning(selectedOption) {
    const warningDiv = document.getElementById('withdraw-warning');
    const warningText = document.getElementById('warning-text');
    const refundInput = document.getElementById('withdraw-refund');
    
    if (!warningDiv || !warningText || !refundInput) return;
    
    const refund = parseFormattedNumber(refundInput.value) || 0;
    const courseName = selectedOption ? selectedOption.getAttribute('data-course-name') : '';
    
    if (refund > 0) {
        warningDiv.style.display = 'block';
        warningText.textContent = `سيتم استرداد ${formatNumber(refund)} ل.س للطالب من دورة "${courseName}"`;
        warningDiv.className = 'alert alert-warning';
    } else {
        warningDiv.style.display = 'none';
    }
}

// معالجة سحب الطالب
function processWithdraw() {
    const courseSelect = document.getElementById('withdraw-course');
    const reasonInput = document.getElementById('withdraw-reason');
    const refundInput = document.getElementById('withdraw-refund');
    const confirmBtn = document.getElementById('withdraw-confirm');
    
    // التحقق من الحقول المطلوبة
    if (!courseSelect || !courseSelect.value) {
        alert('يرجى اختيار دورة');
        return;
    }
    
    const selectedOption = courseSelect.options[courseSelect.selectedIndex];
    const enrollmentId = selectedOption.value;
    const courseName = selectedOption.getAttribute('data-course-name');
    const reason = reasonInput?.value || '';
    const refund = parseFormattedNumber(refundInput?.value) || 0;
    
    // تأكيد العملية
    const confirmMessage = refund > 0 
        ? `هل أنت متأكد من سحب الطالب من "${courseName}" واسترداد ${formatNumber(refund)} ل.س؟`
        : `هل أنت متأكد من سحب الطالب من "${courseName}"؟`;
    
    if (!confirm(confirmMessage)) {
        return;
    }
    
    // تعطيل زر التأكيد أثناء المعالجة
    if (confirmBtn) {
        confirmBtn.disabled = true;
        confirmBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> جاري السحب...';
    }
    
    // إرسال البيانات إلى الخادم
    const formData = new FormData();
    formData.append('enrollment_id', enrollmentId);
    formData.append('withdrawal_reason', reason);
    formData.append('refund_amount', refund);
    
    fetch('"django_tag"', {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCSRFToken(),
        },
        body: formData
    })
    .then(response => {
        if (response.redirected) {
            window.location.href = response.url;
            return;
        }
        return response.json();
    })
    .then(data => {
        if (data && data.success === false) {
            alert('حدث خطأ: ' + (data.error || 'يرجى المحاولة مرة أخرى'));
        } else {
            alert('تم سحب الطالب بنجاح');
            closeModal(document.getElementById('withdrawModal'));
            window.location.reload();
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('حدث خطأ في الاتصال بالخادم');
    })
    .finally(() => {
        // إعادة تمكين زر التأكيد
        if (confirmBtn) {
            confirmBtn.disabled = false;
            confirmBtn.innerHTML = '<i class="fas fa-user-minus"></i> تأكيد السحب';
        }
    });
}

// تهيئة أزرار سحب الدورات الفردية
function initCourseWithdrawButtons() {
    const withdrawButtons = document.querySelectorAll('.withdraw-course-btn');
    
    withdrawButtons.forEach(button => {
        button.addEventListener('click', function() {
            const enrollmentId = this.getAttribute('data-enrollment-id');
            const courseName = this.getAttribute('data-course-name');
            
            console.log('سحب دورة فردية:', courseName, enrollmentId);
            
            // فتح مودال السحب وتعيين القيم
            const withdrawModal = document.getElementById('withdrawModal');
            const courseSelect = document.getElementById('withdraw-course');
            
            if (withdrawModal && courseSelect) {
                openModal(withdrawModal);
                
                // تعيين الدورة المحددة
                courseSelect.value = enrollmentId;
                
                // تشغيل حدث التغيير لتحديث القيم
                const event = new Event('change');
                courseSelect.dispatchEvent(event);
            }
        });
    });
}

// تهيئة تحديث الخصم
function initDiscountUpdate() {
    const updateDiscountBtn = document.getElementById('updateDiscountBtn');
    const updateDiscountModal = document.getElementById('updateDiscountModal');
    const confirmUpdateDiscount = document.getElementById('confirmUpdateDiscount');
    const enrollmentSelect = document.getElementById('enrollment_select');
    const discountPercentInput = document.getElementById('update_discount_percent');
    const discountAmountInput = document.getElementById('update_discount_amount');
    const discountReasonInput = document.getElementById('update_discount_reason');

    if (updateDiscountBtn) {
        updateDiscountBtn.addEventListener('click', function() {
            openModal(updateDiscountModal);
            setupNumberFormatting();
        });
    }

    // عند اختيار دورة، حمل قيم الحسم الحالية
    if (enrollmentSelect) {
        enrollmentSelect.addEventListener('change', function() {
            if (this.value) {
                const selectedOption = this.options[this.selectedIndex];
                discountPercentInput.value = selectedOption.dataset.discountPercent || '0';
                discountAmountInput.value = selectedOption.dataset.discountAmount || '0';
                discountReasonInput.value = selectedOption.dataset.discountReason || '';
                
                document.getElementById('discount-impact').style.display = 'block';
            } else {
                document.getElementById('discount-impact').style.display = 'none';
            }
        });
    }

    if (confirmUpdateDiscount) {
        confirmUpdateDiscount.addEventListener('click', function() {
            updateStudentDiscount();
        });
    }

    // تحديث حساب الحسم عند تغيير القيم
    if (discountPercentInput && discountAmountInput) {
        discountPercentInput.addEventListener('input', function() {
            validateDiscountInput(this);
        });
        discountAmountInput.addEventListener('input', function() {
            validateDiscountInput(this);
        });
    }
}

// تحديث خصم الدورة المحددة
function updateStudentDiscount() {
    const enrollmentId = document.getElementById('enrollment_select').value;
    const discountPercent = document.getElementById('update_discount_percent').value;
    const discountAmount = parseFormattedNumber(document.getElementById('update_discount_amount').value);
    const discountReason = document.getElementById('update_discount_reason').value;
    const confirmBtn = document.getElementById('confirmUpdateDiscount');

    if (!enrollmentId) {
        alert('يجب اختيار الدورة أولاً');
        return;
    }

    if (confirmBtn) {
        confirmBtn.disabled = true;
        confirmBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> جاري التحديث...';
    }

    const formData = new FormData();
    formData.append('enrollment_id', enrollmentId);
    formData.append('discount_percent', discountPercent);
    formData.append('discount_amount', discountAmount);
    formData.append('discount_reason', discountReason);

    fetch(`"django_tag"`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCSRFToken(),
        },
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert(data.message || 'تم تحديث الحسم بنجاح');
            closeModal(document.getElementById('updateDiscountModal'));
            window.location.reload();
        } else {
            alert('حدث خطأ: ' + data.error);
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('حدث خطأ في الاتصال بالخادم');
    })
    .finally(() => {
        if (confirmBtn) {
            confirmBtn.disabled = false;
            confirmBtn.innerHTML = '<i class="fas fa-sync-alt"></i> تحديث الحسم';
        }
    });
}

// تهيئة تعديل المواد المسجلة بالدورة
function initSubjectsUpdate() {
    const editBtn = document.getElementById('editCourseSubjectsBtn');
    const modal = document.getElementById('editCourseSubjectsModal');
    const confirmBtn = document.getElementById('confirmUpdateSubjects');
    const enrollmentSelect = document.getElementById('subjects_enrollment_select');
    const customContainer = document.getElementById('modal-custom-subjects-container');
    const customInput = document.getElementById('modal_subjects_custom_text');
    const allRadio = document.getElementById('modal_subjects_all');
    const customRadio = document.getElementById('modal_subjects_custom');

    if (editBtn) {
        editBtn.addEventListener('click', function() {
            // فتح المودال وتصفير القيم
            openModal(modal);
            if (enrollmentSelect) enrollmentSelect.value = '';
            if (allRadio) allRadio.checked = true;
            if (customContainer) customContainer.style.display = 'none';
            if (customInput) customInput.value = '';
        });
    }

    // أزرار الإغلاق
    const closeBtns = document.querySelectorAll('[data-close-subjects-modal]');
    closeBtns.forEach(btn => {
        btn.addEventListener('click', function() {
            closeModal(modal);
        });
    });

    // عند اختيار دورة، تحميل المواد المسجلة الحالية
    if (enrollmentSelect) {
        enrollmentSelect.addEventListener('change', function() {
            if (this.value) {
                const selectedOption = this.options[this.selectedIndex];
                const subjectsNote = selectedOption.dataset.subjectsNote || 'كامل المواد';
                if (subjectsNote === 'كامل المواد') {
                    if (allRadio) allRadio.checked = true;
                    if (customContainer) customContainer.style.display = 'none';
                    if (customInput) customInput.value = '';
                } else {
                    if (customRadio) customRadio.checked = true;
                    if (customContainer) customContainer.style.display = 'block';
                    if (customInput) customInput.value = subjectsNote;
                }
            } else {
                if (allRadio) allRadio.checked = true;
                if (customContainer) customContainer.style.display = 'none';
                if (customInput) customInput.value = '';
            }
        });
    }

    // إظهار/إخفاء حقل المواد المخصصة
    function toggleSubjectsInput() {
        if (customRadio && customRadio.checked) {
            if (customContainer) customContainer.style.display = 'block';
            if (customInput) customInput.focus();
        } else {
            if (customContainer) customContainer.style.display = 'none';
            if (customInput) customInput.value = '';
        }
    }

    if (allRadio && customRadio) {
        allRadio.addEventListener('change', toggleSubjectsInput);
        customRadio.addEventListener('change', toggleSubjectsInput);
    }

    if (confirmBtn) {
        confirmBtn.addEventListener('click', function() {
            updateEnrollmentSubjects();
        });
    }
}

// إرسال تحديث المواد عبر AJAX
function updateEnrollmentSubjects() {
    const enrollmentSelect = document.getElementById('subjects_enrollment_select');
    const allRadio = document.getElementById('modal_subjects_all');
    const customText = document.getElementById('modal_subjects_custom_text');
    const confirmBtn = document.getElementById('confirmUpdateSubjects');

    if (!enrollmentSelect || !enrollmentSelect.value) {
        alert('يجب اختيار الدورة أولاً');
        return;
    }

    const enrollmentId = enrollmentSelect.value;
    let subjectsNote = 'كامل المواد';
    if (allRadio && !allRadio.checked) {
        subjectsNote = customText.value.trim() || 'كامل المواد';
    }

    if (confirmBtn) {
        confirmBtn.disabled = true;
        confirmBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> جاري الحفظ...';
    }

    const formData = new FormData();
    formData.append('enrollment_id', enrollmentId);
    formData.append('subjects_note', subjectsNote);

    fetch(`"django_tag"`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCSRFToken(),
        },
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert(data.message || 'تم تحديث المواد بنجاح');
            closeModal(document.getElementById('editCourseSubjectsModal'));
            window.location.reload();
        } else {
            alert('حدث خطأ: ' + data.error);
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('حدث خطأ في الاتصال بالخادم');
    })
    .finally(() => {
        if (confirmBtn) {
            confirmBtn.disabled = false;
            confirmBtn.innerHTML = '<i class="fas fa-save"></i> حفظ التغييرات';
        }
    });
}



// التحقق من صحة مدخلات الحسم
function validateDiscountInput(input) {
    if (input.id === 'update_discount_percent') {
        const value = parseFloat(input.value) || 0;
        if (value < 0 || value > 100) {
            input.value = Math.max(0, Math.min(100, value));
        }
    }
}

// تحديث خصم الدورة المحددة
function updateStudentDiscount() {
    const enrollmentId = document.getElementById('enrollment_select').value;
    const discountPercent = document.getElementById('update_discount_percent').value;
    const discountAmount = parseFormattedNumber(document.getElementById('update_discount_amount').value);
    const discountReason = document.getElementById('update_discount_reason').value;
    const confirmBtn = document.getElementById('confirmUpdateDiscount');

    if (!enrollmentId) {
        alert('يجب اختيار الدورة أولاً');
        return;
    }

    if (confirmBtn) {
        confirmBtn.disabled = true;
        confirmBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> جاري التحديث...';
    }

    let subjectsNote = 'كامل المواد';
    const updateSubjectsCustom = document.getElementById('update_subjects_custom');
    if (updateSubjectsCustom && updateSubjectsCustom.checked) {
        subjectsNote = document.getElementById('update_subjects_custom_text').value.trim() || 'كامل المواد';
    }

    const formData = new FormData();
    formData.append('enrollment_id', enrollmentId);
    formData.append('discount_percent', discountPercent);
    formData.append('discount_amount', discountAmount);
    formData.append('discount_reason', discountReason);
    formData.append('subjects_note', subjectsNote);

    fetch(`"django_tag"`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCSRFToken(),
        },
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert(data.message || 'تم تحديث الحسم بنجاح');
            closeModal(document.getElementById('updateDiscountModal'));
            window.location.reload();
        } else {
            alert('حدث خطأ: ' + data.error);
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('حدث خطأ في الاتصال بالخادم');
    })
    .finally(() => {
        if (confirmBtn) {
            confirmBtn.disabled = false;
            confirmBtn.innerHTML = '<i class="fas fa-sync-alt"></i> تحديث الحسم';
        }
    });
}

// الحصول على CSRF Token
function getCSRFToken() {
    const name = 'csrftoken';
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}
