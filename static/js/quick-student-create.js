document.addEventListener('DOMContentLoaded', function () {
    const form = document.getElementById('quick-student-create-form');
    if (!form) return;

    const existsUrl = form.dataset.existsUrl;
    const fullNameInput = document.getElementById('id_full_name');
    const phoneInput = document.getElementById('id_phone');
    const arabicDigitsMap = {
        '\u0660': '0', '\u0661': '1', '\u0662': '2', '\u0663': '3', '\u0664': '4',
        '\u0665': '5', '\u0666': '6', '\u0667': '7', '\u0668': '8', '\u0669': '9',
        '\u06F0': '0', '\u06F1': '1', '\u06F2': '2', '\u06F3': '3', '\u06F4': '4',
        '\u06F5': '5', '\u06F6': '6', '\u06F7': '7', '\u06F8': '8', '\u06F9': '9'
    };

    function normalizePhoneDigits(value) {
        return Array.from(value || '').map((char) => arabicDigitsMap[char] || char).join('');
    }

    function getStatusBox(fieldName) {
        return form.querySelector(`.js-status-${fieldName}`);
    }

    function setStatus(fieldName, message, state) {
        const box = getStatusBox(fieldName);
        if (!box) return;
        box.textContent = message;
        box.classList.remove('is-checking', 'is-valid', 'is-invalid');
        if (state) box.classList.add(state);
    }

    function getInlineErrorBox(input) {
        const field = input ? input.closest('.quick-student-create-field') : null;
        if (!field) return null;
        let box = field.querySelector('.js-inline-error');
        if (!box) {
            box = document.createElement('div');
            box.className = 'field__error js-inline-error';
            field.appendChild(box);
        }
        return box;
    }

    function showInlineError(input, message) {
        const box = getInlineErrorBox(input);
        if (!box) return;
        box.textContent = message;
    }

    function clearInlineError(input) {
        const field = input ? input.closest('.quick-student-create-field') : null;
        const box = field ? field.querySelector('.js-inline-error') : null;
        if (box) box.remove();
    }

    async function checkExists(field, value) {
        const url = `${existsUrl}?field=${encodeURIComponent(field)}&value=${encodeURIComponent(value)}`;
        const response = await fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } });
        if (!response.ok) {
            return { exists: false };
        }
        return response.json();
    }

    async function validateFullName() {
        if (!fullNameInput) return false;
        const value = fullNameInput.value.trim();
        if (!value) {
            clearInlineError(fullNameInput);
            setStatus('full_name', 'اكتب الاسم الكامل كما تريد ظهوره في الملف.', '');
            return false;
        }

        setStatus('full_name', 'جارٍ التحقق من الاسم...', 'is-checking');
        const result = await checkExists('full_name', value);
        if (result.exists) {
            const message = `الاسم موجود مسبقًا للطالب: ${result.full_name}`;
            showInlineError(fullNameInput, message);
            setStatus('full_name', message, 'is-invalid');
            return true;
        }

        clearInlineError(fullNameInput);
        setStatus('full_name', 'الاسم غير مكرر حاليًا ويمكن المتابعة.', 'is-valid');
        return false;
    }

    async function validatePhone() {
        if (!phoneInput) return false;
        phoneInput.value = normalizePhoneDigits(phoneInput.value);
        const value = phoneInput.value.trim();
        if (!value) {
            clearInlineError(phoneInput);
            setStatus('phone', 'سيتم حفظ الهاتف دائمًا بالأرقام الإنجليزية فقط.', '');
            return false;
        }

        setStatus('phone', 'جارٍ التحقق من رقم الهاتف...', 'is-checking');
        const result = await checkExists('phone', value);
        if (result.exists) {
            const message = `رقم الهاتف مستخدم مسبقًا للطالب: ${result.full_name}`;
            showInlineError(phoneInput, message);
            setStatus('phone', message, 'is-invalid');
            return true;
        }

        clearInlineError(phoneInput);
        setStatus('phone', 'رقم الهاتف متاح ولم يتم العثور على تكرار.', 'is-valid');
        return false;
    }

    if (fullNameInput) {
        fullNameInput.addEventListener('blur', validateFullName);
    }

    if (phoneInput) {
        phoneInput.addEventListener('input', function () {
            const normalized = normalizePhoneDigits(phoneInput.value);
            if (phoneInput.value !== normalized) {
                phoneInput.value = normalized;
            }
        });
        phoneInput.addEventListener('paste', function () {
            setTimeout(function () {
                phoneInput.value = normalizePhoneDigits(phoneInput.value);
            }, 0);
        });
        phoneInput.addEventListener('blur', validatePhone);
    }

    form.addEventListener('submit', async function (event) {
        if (phoneInput) {
            phoneInput.value = normalizePhoneDigits(phoneInput.value);
        }

        const [nameExists, phoneExists] = await Promise.all([
            validateFullName(),
            validatePhone()
        ]);

        if (nameExists || phoneExists) {
            event.preventDefault();
        }
    });
});
