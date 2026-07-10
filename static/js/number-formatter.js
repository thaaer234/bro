/**
 * Number Formatting Plugin
 * Automatically adds commas to number inputs as user types
 * Usage: new NumberFormatter(element, options)
 */

class NumberFormatter {
    constructor(element, options = {}) {
        this.element = typeof element === 'string' ? document.querySelector(element) : element;
        this.options = {
            thousandSeparator: ',',
            decimalSeparator: '.',
            decimalPlaces: 2,
            allowNegative: true,
            prefix: '',
            suffix: '',
            autoFormat: true,
            ...options
        };
        
        this.init();
    }
    
    init() {
        if (!this.element) {
            console.error('NumberFormatter: Element not found');
            return;
        }
        
        // Store original value for calculations
        this.element.dataset.originalValue = this.element.value;
        
        // Add event listeners
        this.element.addEventListener('input', this.handleInput.bind(this));
        this.element.addEventListener('focus', this.handleFocus.bind(this));
        this.element.addEventListener('blur', this.handleBlur.bind(this));
        this.element.addEventListener('keydown', this.handleKeydown.bind(this));
        
        // Format initial value
        if (this.options.autoFormat && this.element.value) {
            this.formatValue();
        }
        
        // Add CSS class for styling
        this.element.classList.add('number-formatted');
    }
    
    handleInput(event) {
        const input = event.target;
        const cursorPosition = input.selectionStart;
        const originalValue = input.value;
        
        // Remove all non-numeric characters except decimal point and minus
        let cleanValue = originalValue.replace(/[^\d.-]/g, '');
        
        // Handle negative numbers
        if (this.options.allowNegative && cleanValue.startsWith('-')) {
            cleanValue = '-' + cleanValue.substring(1).replace(/[^\d.]/g, '');
        } else {
            cleanValue = cleanValue.replace(/[^\d.]/g, '');
        }
        
        // Ensure only one decimal point
        const decimalParts = cleanValue.split('.');
        if (decimalParts.length > 2) {
            cleanValue = decimalParts[0] + '.' + decimalParts.slice(1).join('');
        }
        
        // Limit decimal places
        if (decimalParts.length === 2 && decimalParts[1].length > this.options.decimalPlaces) {
            cleanValue = decimalParts[0] + '.' + decimalParts[1].substring(0, this.options.decimalPlaces);
        }
        
        // Store the numeric value
        input.dataset.originalValue = cleanValue;
        
        // Format the display value
        this.formatValue();
        
        // Restore cursor position
        this.restoreCursorPosition(cursorPosition, originalValue, input.value);
    }
    
    handleFocus(event) {
        const input = event.target;
        // Store cursor position for restoration
        input.dataset.cursorPosition = input.selectionStart;
    }
    
    handleBlur(event) {
        const input = event.target;
        // Final format on blur
        this.formatValue();
    }
    
    handleKeydown(event) {
        const input = event.target;
        const key = event.key;
        
        // Allow navigation keys
        const allowedKeys = [
            'Backspace', 'Delete', 'Tab', 'Escape', 'Enter',
            'ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown',
            'Home', 'End', 'PageUp', 'PageDown'
        ];
        
        if (allowedKeys.includes(key)) {
            return;
        }
        
        // Allow Ctrl+A, Ctrl+C, Ctrl+V, Ctrl+X
        if (event.ctrlKey && ['a', 'c', 'v', 'x'].includes(key.toLowerCase())) {
            return;
        }
        
        // Allow numeric keys, decimal point, and minus
        const allowedChars = /[\d.-]/;
        if (!allowedChars.test(key)) {
            event.preventDefault();
            return;
        }
        
        // Handle minus sign
        if (key === '-') {
            if (!this.options.allowNegative || input.selectionStart !== 0) {
                event.preventDefault();
                return;
            }
        }
        
        // Handle decimal point
        if (key === '.') {
            if (input.value.includes('.')) {
                event.preventDefault();
                return;
            }
        }
    }
    
    formatValue() {
        const input = this.element;
        const numericValue = input.dataset.originalValue || '';
        
        if (!numericValue) {
            input.value = '';
            return;
        }
        
        // Parse the numeric value
        const number = parseFloat(numericValue);
        
        if (isNaN(number)) {
            input.value = '';
            return;
        }
        
        // Format the number
        let formattedValue = this.formatNumber(number);
        
        // Add prefix and suffix
        if (this.options.prefix) {
            formattedValue = this.options.prefix + ' ' + formattedValue;
        }
        if (this.options.suffix) {
            formattedValue = formattedValue + ' ' + this.options.suffix;
        }
        
        input.value = formattedValue;
    }
    
    formatNumber(number) {
        const isNegative = number < 0;
        const absoluteNumber = Math.abs(number);
        
        // Split into integer and decimal parts
        const parts = absoluteNumber.toFixed(this.options.decimalPlaces).split('.');
        const integerPart = parts[0];
        const decimalPart = parts[1];
        
        // Add thousand separators to integer part
        const formattedInteger = integerPart.replace(/\B(?=(\d{3})+(?!\d))/g, this.options.thousandSeparator);
        
        // Combine parts
        let result = formattedInteger;
        if (decimalPart && this.options.decimalPlaces > 0) {
            result += this.options.decimalSeparator + decimalPart;
        }
        
        // Add negative sign
        if (isNegative) {
            result = '-' + result;
        }
        
        return result;
    }
    
    restoreCursorPosition(originalPosition, originalValue, newValue) {
        const input = this.element;
        
        // Calculate new cursor position
        let newPosition = originalPosition;
        
        // Adjust for added/removed characters
        const originalLength = originalValue.length;
        const newLength = newValue.length;
        const lengthDiff = newLength - originalLength;
        
        if (lengthDiff > 0) {
            // Characters were added (commas)
            newPosition += lengthDiff;
        } else if (lengthDiff < 0) {
            // Characters were removed
            newPosition = Math.max(0, newPosition + lengthDiff);
        }
        
        // Ensure cursor position is within bounds
        newPosition = Math.min(newPosition, newValue.length);
        
        // Set cursor position
        setTimeout(() => {
            input.setSelectionRange(newPosition, newPosition);
        }, 0);
    }
    
    // Public methods
    getValue() {
        return this.element.dataset.originalValue || '';
    }
    
    setValue(value) {
        this.element.dataset.originalValue = value.toString();
        this.formatValue();
    }
    
    destroy() {
        this.element.removeEventListener('input', this.handleInput.bind(this));
        this.element.removeEventListener('focus', this.handleFocus.bind(this));
        this.element.removeEventListener('blur', this.handleBlur.bind(this));
        this.element.removeEventListener('keydown', this.handleKeydown.bind(this));
        this.element.classList.remove('number-formatted');
    }
}

/**
 * Auto-initialize number formatters for elements with data-number-format attribute
 */
document.addEventListener('DOMContentLoaded', function() {
    // Initialize all elements with data-number-format attribute
    const elements = document.querySelectorAll('[data-number-format]');
    
    elements.forEach(element => {
        const options = {};
        
        // Parse options from data attributes
        if (element.dataset.thousandSeparator) {
            options.thousandSeparator = element.dataset.thousandSeparator;
        }
        if (element.dataset.decimalSeparator) {
            options.decimalSeparator = element.dataset.decimalSeparator;
        }
        if (element.dataset.decimalPlaces) {
            options.decimalPlaces = parseInt(element.dataset.decimalPlaces);
        }
        if (element.dataset.allowNegative) {
            options.allowNegative = element.dataset.allowNegative === 'true';
        }
        if (element.dataset.prefix) {
            options.prefix = element.dataset.prefix;
        }
        if (element.dataset.suffix) {
            options.suffix = element.dataset.suffix;
        }
        
        // Initialize formatter
        new NumberFormatter(element, options);
    });
});

/**
 * Utility functions for manual initialization
 */
window.NumberFormatter = {
    // Initialize single element
    init: function(element, options = {}) {
        return new NumberFormatter(element, options);
    },
    
    // Initialize multiple elements
    initAll: function(selector, options = {}) {
        const elements = document.querySelectorAll(selector);
        return Array.from(elements).map(element => new NumberFormatter(element, options));
    },
    
    // Initialize all number inputs
    initNumberInputs: function(options = {}) {
        const elements = document.querySelectorAll('input[type="number"], input.number-input');
        return Array.from(elements).map(element => new NumberFormatter(element, options));
    },
    
    // Initialize all currency inputs
    initCurrencyInputs: function(currency = 'ريال', options = {}) {
        const elements = document.querySelectorAll('input.currency-input, input[data-currency]');
        const currencyOptions = {
            prefix: currency,
            decimalPlaces: 2,
            ...options
        };
        return Array.from(elements).map(element => new NumberFormatter(element, currencyOptions));
    }
};

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = NumberFormatter;
}
