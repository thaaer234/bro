// JavaScript للنظام
document.addEventListener('DOMContentLoaded', function() {
    const tabs = document.querySelectorAll('.tab');
    const tabContents = document.querySelectorAll('.tab-content');

    tabs.forEach(function(tab) {
        tab.setAttribute('role', 'tab');
        tab.setAttribute('aria-selected', tab.classList.contains('active') ? 'true' : 'false');
        tab.addEventListener('click', function() {
            tabs.forEach(function(t) {
                t.classList.remove('active');
                t.setAttribute('aria-selected', 'false');
            });
            tabContents.forEach(function(content) {
                content.classList.remove('active');
            });

            this.classList.add('active');
            this.setAttribute('aria-selected', 'true');
            const targetTab = this.getAttribute('data-tab');
            const targetContent = document.getElementById(targetTab + '-tab');
            if (targetContent) {
                targetContent.classList.add('active');
            }
        });
    });

    const modals = document.querySelectorAll('.modal');
    const closeButtons = document.querySelectorAll('.close');

    closeButtons.forEach(function(button) {
        button.addEventListener('click', function() {
            const modal = this.closest('.modal');
            if (modal) {
                modal.style.display = 'none';
            }
        });
    });

    window.addEventListener('click', function(event) {
        modals.forEach(function(modal) {
            if (event.target === modal) {
                modal.style.display = 'none';
            }
        });
    });

    const buttons = document.querySelectorAll('.btn');
    buttons.forEach(function(button) {
        button.addEventListener('click', function() {
            this.style.transform = 'scale(0.95)';
            setTimeout(() => {
                this.style.transform = 'scale(1)';
            }, 150);
        });
    });
});

function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `alert alert-${type}`;
    notification.textContent = message;
    notification.style.position = 'fixed';
    notification.style.top = '20px';
    notification.style.right = '20px';
    notification.style.zIndex = '9999';
    notification.style.minWidth = '300px';

    document.body.appendChild(notification);

    setTimeout(() => {
        notification.remove();
    }, 3000);
}

function togglePassword(inputId) {
    const input = document.getElementById(inputId);
    if (!input) {
        return;
    }

    const control = input.parentElement.querySelector('.toggle-password, .password-toggle');
    const icon = control ? control.querySelector('i') || control : null;

    if (input.type === 'password') {
        input.type = 'text';
        if (icon && icon.classList) {
            icon.classList.remove('fa-eye');
            icon.classList.add('fa-eye-slash');
        }
        if (control) {
            control.setAttribute('aria-label', 'إخفاء كلمة المرور');
            control.setAttribute('aria-pressed', 'true');
        }
    } else {
        input.type = 'password';
        if (icon && icon.classList) {
            icon.classList.remove('fa-eye-slash');
            icon.classList.add('fa-eye');
        }
        if (control) {
            control.setAttribute('aria-label', 'إظهار كلمة المرور');
            control.setAttribute('aria-pressed', 'false');
        }
    }
}
