document.addEventListener('DOMContentLoaded', function() {
    console.log('تهيئة صفحة الطالب...');
    
    // تهيئة التبويبات
    initTabs();
    
    // تهيئة المودالات
    initModals();
    
    // تهيئة الإيصال الفوري
    initQuickReceipt();
    
    // تهيئة سحب الطالب
    initWithdrawStudent();
    
    // تهيئة أزرار سحب الدورات الفردية
    initCourseWithdrawButtons();
});

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

// تهيئة الحسابات التلقائية للإيصال
function initReceiptCalculations() {
    const courseSelect = document.getElementById('qr-course');
    const amountInput = document.getElementById('qr-amount');
    const discPctInput = document.getElementById('qr-disc-pct');
    const discAmtInput = document.getElementById('qr-disc-amt');
    const paidInput = document.getElementById('qr-paid');
    
    if (!courseSelect) {
        console.error('لم يتم العثور على قائمة الدورات');
        return;
    }
    
    console.log('عدد الدورات المتاحة:', courseSelect.options.length);
    
    // إعادة تعيين القيم
    if (amountInput) amountInput.value = '';
    if (paidInput) paidInput.value = '0';
    
    // عند تغيير الدورة
    courseSelect.addEventListener('change', function() {
        const selectedOption = this.options[this.selectedIndex];
        console.log('تم اختيار دورة:', selectedOption.text);
        
        if (selectedOption && selectedOption.value) {
            const price = parseFloat(selectedOption.getAttribute('data-price')) || 0;
            const remaining = parseFloat(selectedOption.getAttribute('data-remaining')) || 0;
            
            console.log('سعر الدورة:', price, 'المتبقي:', remaining);
            
            if (amountInput) {
                amountInput.value = price.toFixed(2);
            }
            
            if (paidInput) {
                const suggestedAmount = Math.min(price, Math.max(0, remaining));
                paidInput.value = (suggestedAmount > 0 ? suggestedAmount : 0).toFixed(2);
            }
            
            updateNetAmountDisplay();
        }
    });
    
    // تحديث الحسابات عند تغيير القيم
    [amountInput, discPctInput, discAmtInput, paidInput].forEach(input => {
        if (input) {
            input.addEventListener('input', updateNetAmountDisplay);
        }
    });
    
    // تشغيل حدث التغيير لأول مرة إذا كانت هناك دورة محددة
    if (courseSelect.options.length > 1 && courseSelect.options[1].value) {
        courseSelect.selectedIndex = 1;
        const event = new Event('change');
        courseSelect.dispatchEvent(event);
    }
}

// حساب المبلغ الصافي
function calculateNetAmount() {
    const amountInput = document.getElementById('qr-amount');
    const discPctInput = document.getElementById('qr-disc-pct');
    const discAmtInput = document.getElementById('qr-disc-amt');
    
    const amount = parseFloat(amountInput?.value) || 0;
    const discPct = parseFloat(discPctInput?.value) || 0;
    const discAmt = parseFloat(discAmtInput?.value) || 0;
    
    const discountFromPercentage = amount * (discPct / 100);
    const netAmount = Math.max(0, amount - discountFromPercentage - discAmt);
    
    return netAmount;
}

// تحديث عرض المبلغ الصافي
function updateNetAmountDisplay() {
    const netAmountDiv = document.getElementById('qr-net');
    const netValueSpan = document.getElementById('qr-net-value');
    const amountInput = document.getElementById('qr-amount');
    
    if (!netAmountDiv || !netValueSpan || !amountInput) return;
    
    const amount = parseFloat(amountInput.value) || 0;
    
    if (amount <= 0) {
        netAmountDiv.style.display = 'none';
        return;
    }
    
    const netAmount = calculateNetAmount();
    netAmountDiv.style.display = 'block';
    netValueSpan.textContent = netAmount.toFixed(2);
    
    // تلوين النتيجة
    if (netAmount <= 0) {
        netAmountDiv.style.color = '#dc3545';
        netAmountDiv.style.background = '#f8d7da';
    } else {
        netAmountDiv.style.color = '#155724';
        netAmountDiv.style.background = '#d4edda';
    }
}

// معالجة حفظ الإيصال الفوري
function processQuickReceipt() {
    const courseSelect = document.getElementById('qr-course');
    const amountInput = document.getElementById('qr-amount');
    const discPctInput = document.getElementById('qr-disc-pct');
    const discAmtInput = document.getElementById('qr-disc-amt');
    const paidInput = document.getElementById('qr-paid');
    const dateInput = document.getElementById('qr-date');
    const saveBtn = document.getElementById('qr-save');
    
    // التحقق من الحقول المطلوبة
    if (!courseSelect || !courseSelect.value) {
        alert('يرجى اختيار دورة');
        return;
    }
    
    const selectedOption = courseSelect.options[courseSelect.selectedIndex];
    const courseId = selectedOption.value;
    const enrollmentId = selectedOption.getAttribute('data-enrollment-id');
    const courseName = selectedOption.getAttribute('data-course-name');
    const amount = parseFloat(amountInput?.value) || 0;
    const discPct = parseFloat(discPctInput?.value) || 0;
    const discAmt = parseFloat(discAmtInput?.value) || 0;
    const netAmount = calculateNetAmount();
    const isFree = netAmount <= 0;
    const paid = isFree ? 0 : (parseFloat(paidInput?.value) || 0);
    const date = dateInput?.value;
    
    if (!isFree && amount <= 0) {
        alert('يرجى إدخال قيمة صحيحة للدورة');
        return;
    }
    
    if (!isFree && netAmount > 0 && paid <= 0) {
        alert('يرجى إدخال مبلغ مدفوع صحيح');
        return;
    }
    
    if (paid > netAmount) {
        alert('المبلغ المدفوع لا يمكن أن يكون أكبر من المبلغ الصافي');
        return;
    }
    
    // تأكيد العملية
    if (!confirm(`هل تريد قطع إيصال بقيمة ${(isFree ? 0 : paid).toFixed(2)} ل.س لدورة "${courseName}"؟`)) {
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
    formData.append('amount', isFree ? 0 : amount);
    formData.append('discount_percent', discPct);
    formData.append('discount_amount', discAmt);
    formData.append('paid_amount', paid);
    formData.append('receipt_date', date);
    formData.append('is_free', isFree ? 'true' : 'false');
    
    fetch('{% url "students:quick_receipt" student.id %}', {
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
    const paidInput = document.getElementById('withdraw-paid');
    const refundInput = document.getElementById('withdraw-refund');
    
    if (!courseSelect) {
        console.error('لم يتم العثور على قائمة الدورات للسحب');
        return;
    }
    
    console.log('عدد الدورات المتاحة للسحب:', courseSelect.options.length);
    
    // إعادة تعيين القيم
    if (paidInput) paidInput.value = '0';
    if (refundInput) refundInput.value = '0';
    
    // عند تغيير الدورة
    courseSelect.addEventListener('change', function() {
        const selectedOption = this.options[this.selectedIndex];
        console.log('تم اختيار دورة للسحب:', selectedOption.text);
        
        if (selectedOption && selectedOption.value) {
            const paid = parseFloat(selectedOption.getAttribute('data-paid')) || 0;
            const courseName = selectedOption.getAttribute('data-course-name');
            
            if (paidInput) {
                paidInput.value = paid.toFixed(2);
            }
            
            if (refundInput) {
                refundInput.value = '0';
                refundInput.max = paid;
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
    const paidInput = document.getElementById('withdraw-paid');
    const refundInput = document.getElementById('withdraw-refund');
    
    if (!warningDiv || !warningText || !paidInput || !refundInput) return;
    
    const paid = parseFloat(paidInput.value) || 0;
    const refund = parseFloat(refundInput.value) || 0;
    const courseName = selectedOption ? selectedOption.getAttribute('data-course-name') : '';
    
    if (refund > paid) {
        warningDiv.style.display = 'block';
        warningText.textContent = 'تحذير: مبلغ الإرجاع أكبر من المبلغ المدفوع!';
        warningDiv.className = 'alert alert-danger';
    } else if (refund > 0 && refund <= paid) {
        warningDiv.style.display = 'block';
        warningText.textContent = `سيتم استرداد ${refund.toFixed(2)} ل.س للطالب من دورة "${courseName}"`;
        warningDiv.className = 'alert alert-warning';
    } else if (paid > 0 && refund === 0) {
        warningDiv.style.display = 'block';
        warningText.textContent = `انتباه: لن يتم استرداد أي مبلغ للطالب رغم وجود مدفوعات في دورة "${courseName}"`;
        warningDiv.className = 'alert alert-info';
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
    const refund = parseFloat(refundInput?.value) || 0;
    const paid = parseFloat(document.getElementById('withdraw-paid')?.value) || 0;
    
    // التحقق من مبلغ الإرجاع
    if (refund > paid) {
        alert('مبلغ الإرجاع لا يمكن أن يكون أكبر من المبلغ المدفوع');
        return;
    }
    
    // تأكيد العملية
    const confirmMessage = refund > 0 
        ? `هل أنت متأكد من سحب الطالب من "${courseName}" واسترداد ${refund.toFixed(2)} ل.س؟`
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
    
    fetch('{% url "students:withdraw_student" student.id %}', {
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
