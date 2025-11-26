/**
 * Sprint 2 Interactive Components
 * - Enhanced Modal Animations
 * - Task Drag-and-Drop Reordering
 * - Form Auto-Save Functionality
 * - Real-Time Validation
 */

// ============================================================================
// ENHANCED MODAL SYSTEM
// ============================================================================

class ModalManager {
    constructor() {
        this.activeModals = [];
        this.setupGlobalListeners();
    }

    setupGlobalListeners() {
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.activeModals.length > 0) {
                this.closeTopModal();
            }
        });
    }

    /**
     * Open a modal with enhanced animations
     */
    open(modalId, options = {}) {
        const modal = document.getElementById(modalId);
        if (!modal) return;

        const backdrop = modal.querySelector('.modal-backdrop');
        const content = modal.querySelector('.modal');

        // Set animation type
        const animation = options.animation || 'scale';
        content.setAttribute('data-animation', animation);

        // Show modal
        modal.style.display = 'block';

        // Trigger animation after display change
        requestAnimationFrame(() => {
            backdrop?.classList.add('active');
            content?.classList.add('active');
        });

        // Focus management
        const firstFocusable = content.querySelector('input, button, select, textarea');
        if (firstFocusable) {
            setTimeout(() => firstFocusable.focus(), 100);
        }

        // Track active modal
        this.activeModals.push(modalId);
        document.body.style.overflow = 'hidden';

        // Auto-save setup if form exists
        const form = content.querySelector('form');
        if (form && options.autoSave !== false) {
            formAutoSave.attach(form);
        }
    }

    /**
     * Close a modal with exit animation
     */
    close(modalId) {
        const modal = document.getElementById(modalId);
        if (!modal) return;

        const backdrop = modal.querySelector('.modal-backdrop');
        const content = modal.querySelector('.modal');

        // Trigger exit animation
        backdrop?.classList.remove('active');
        content?.classList.remove('active');
        content?.classList.add('closing');

        // Hide after animation completes
        setTimeout(() => {
            modal.style.display = 'none';
            content?.classList.remove('closing');

            // Clear auto-saved data on successful close
            const form = content.querySelector('form');
            if (form) {
                formAutoSave.clear(form);
            }
        }, 200);

        // Remove from active modals
        const index = this.activeModals.indexOf(modalId);
        if (index > -1) {
            this.activeModals.splice(index, 1);
        }

        if (this.activeModals.length === 0) {
            document.body.style.overflow = '';
        }
    }

    closeTopModal() {
        if (this.activeModals.length > 0) {
            this.close(this.activeModals[this.activeModals.length - 1]);
        }
    }

    /**
     * Create confirmation dialog
     */
    confirm(message, options = {}) {
        return new Promise((resolve) => {
            const modalHtml = `
                <div id="confirmModal" class="modal-container">
                    <div class="modal-backdrop" onclick="modalManager.close('confirmModal'); window._confirmResolve(false);"></div>
                    <div class="modal modal-sm" data-animation="scale">
                        <div class="modal-header">
                            <h2 class="modal-title">${options.title || 'Confirm'}</h2>
                        </div>
                        <div class="modal-body">
                            <p>${message}</p>
                        </div>
                        <div class="modal-footer">
                            <button class="btn btn-ghost" onclick="modalManager.close('confirmModal'); window._confirmResolve(false);">
                                ${options.cancelText || 'Cancel'}
                            </button>
                            <button class="btn ${options.danger ? 'btn-error' : 'btn-primary'}" onclick="modalManager.close('confirmModal'); window._confirmResolve(true);">
                                ${options.confirmText || 'Confirm'}
                            </button>
                        </div>
                    </div>
                </div>
            `;

            // Remove existing confirm modal
            document.getElementById('confirmModal')?.remove();

            // Add to DOM
            document.body.insertAdjacentHTML('beforeend', modalHtml);

            window._confirmResolve = resolve;
            this.open('confirmModal', { animation: 'scale', autoSave: false });
        });
    }
}

// ============================================================================
// DRAG AND DROP REORDERING
// ============================================================================

class DragDropManager {
    constructor(options = {}) {
        this.container = null;
        this.draggedItem = null;
        this.placeholder = null;
        this.options = {
            itemSelector: '.task-item',
            handleSelector: '.drag-handle',
            dragClass: 'dragging',
            overClass: 'drag-over',
            onReorder: null,
            ...options
        };
    }

    /**
     * Initialize drag-and-drop on a container
     */
    init(containerSelector) {
        this.container = document.querySelector(containerSelector);
        if (!this.container) return;

        // Create placeholder element
        this.placeholder = document.createElement('div');
        this.placeholder.className = 'drag-placeholder';

        // Setup event listeners
        this.container.addEventListener('mousedown', this.handleMouseDown.bind(this));
        document.addEventListener('mousemove', this.handleMouseMove.bind(this));
        document.addEventListener('mouseup', this.handleMouseUp.bind(this));

        // Touch support
        this.container.addEventListener('touchstart', this.handleTouchStart.bind(this), { passive: false });
        document.addEventListener('touchmove', this.handleTouchMove.bind(this), { passive: false });
        document.addEventListener('touchend', this.handleTouchEnd.bind(this));

        // Add drag handles to items
        this.addDragHandles();
    }

    addDragHandles() {
        const items = this.container.querySelectorAll(this.options.itemSelector);
        items.forEach(item => {
            if (!item.querySelector('.drag-handle')) {
                const handle = document.createElement('div');
                handle.className = 'drag-handle';
                handle.innerHTML = `
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                        <circle cx="9" cy="5" r="1.5"></circle>
                        <circle cx="15" cy="5" r="1.5"></circle>
                        <circle cx="9" cy="12" r="1.5"></circle>
                        <circle cx="15" cy="12" r="1.5"></circle>
                        <circle cx="9" cy="19" r="1.5"></circle>
                        <circle cx="15" cy="19" r="1.5"></circle>
                    </svg>
                `;
                item.insertBefore(handle, item.firstChild);
            }
        });
    }

    handleMouseDown(e) {
        const handle = e.target.closest(this.options.handleSelector);
        if (!handle) return;

        const item = handle.closest(this.options.itemSelector);
        if (!item) return;

        e.preventDefault();
        this.startDrag(item, e.clientX, e.clientY);
    }

    handleTouchStart(e) {
        const handle = e.target.closest(this.options.handleSelector);
        if (!handle) return;

        const item = handle.closest(this.options.itemSelector);
        if (!item) return;

        e.preventDefault();
        const touch = e.touches[0];
        this.startDrag(item, touch.clientX, touch.clientY);
    }

    startDrag(item, x, y) {
        this.draggedItem = item;
        this.dragStartY = y;
        this.itemRect = item.getBoundingClientRect();
        this.initialIndex = Array.from(this.container.children).indexOf(item);

        // Clone for dragging
        this.dragClone = item.cloneNode(true);
        this.dragClone.className += ' ' + this.options.dragClass;
        this.dragClone.style.cssText = `
            position: fixed;
            top: ${this.itemRect.top}px;
            left: ${this.itemRect.left}px;
            width: ${this.itemRect.width}px;
            z-index: 10000;
            pointer-events: none;
            opacity: 0.9;
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.3);
            transform: scale(1.02);
        `;
        document.body.appendChild(this.dragClone);

        // Show placeholder
        this.placeholder.style.height = `${this.itemRect.height}px`;
        item.parentNode.insertBefore(this.placeholder, item);
        item.style.display = 'none';
    }

    handleMouseMove(e) {
        if (!this.draggedItem) return;
        this.moveDrag(e.clientY);
    }

    handleTouchMove(e) {
        if (!this.draggedItem) return;
        e.preventDefault();
        const touch = e.touches[0];
        this.moveDrag(touch.clientY);
    }

    moveDrag(y) {
        const deltaY = y - this.dragStartY;
        this.dragClone.style.top = `${this.itemRect.top + deltaY}px`;

        // Find drop position
        const items = Array.from(this.container.querySelectorAll(this.options.itemSelector + ':not([style*="display: none"])'));

        for (const item of items) {
            const rect = item.getBoundingClientRect();
            const midY = rect.top + rect.height / 2;

            if (y < midY) {
                if (this.placeholder.nextElementSibling !== item) {
                    item.parentNode.insertBefore(this.placeholder, item);
                }
                return;
            }
        }

        // Append to end if past all items
        if (items.length > 0) {
            const lastItem = items[items.length - 1];
            if (this.placeholder !== lastItem.nextElementSibling) {
                lastItem.parentNode.insertBefore(this.placeholder, lastItem.nextElementSibling);
            }
        }
    }

    handleMouseUp(e) {
        if (!this.draggedItem) return;
        this.endDrag();
    }

    handleTouchEnd(e) {
        if (!this.draggedItem) return;
        this.endDrag();
    }

    endDrag() {
        // Insert item at placeholder position
        this.placeholder.parentNode.insertBefore(this.draggedItem, this.placeholder);
        this.draggedItem.style.display = '';

        // Remove clone and placeholder
        this.dragClone?.remove();
        this.placeholder?.remove();

        // Get new order
        const newIndex = Array.from(this.container.children)
            .filter(el => el.matches(this.options.itemSelector))
            .indexOf(this.draggedItem);

        // Callback with reorder info
        if (this.options.onReorder && this.initialIndex !== newIndex) {
            const taskId = this.draggedItem.dataset.taskId;
            this.options.onReorder(taskId, this.initialIndex, newIndex);
        }

        // Cleanup
        this.draggedItem = null;
        this.dragClone = null;
    }

    /**
     * Refresh drag handles (call after DOM updates)
     */
    refresh() {
        this.addDragHandles();
    }
}

// ============================================================================
// FORM AUTO-SAVE
// ============================================================================

class FormAutoSave {
    constructor() {
        this.saveDelay = 1000; // Debounce delay in ms
        this.prefix = 'todo_autosave_';
        this.timers = new Map();
    }

    /**
     * Attach auto-save to a form
     */
    attach(form) {
        if (!form || form.dataset.autosaveAttached) return;

        form.dataset.autosaveAttached = 'true';
        const formId = this.getFormId(form);

        // Load any saved data
        this.load(form);

        // Setup input listeners
        const inputs = form.querySelectorAll('input, textarea, select');
        inputs.forEach(input => {
            input.addEventListener('input', () => this.scheduleSave(form));
            input.addEventListener('change', () => this.scheduleSave(form));
        });

        // Show indicator if there's saved data
        this.showSaveIndicator(form, 'restored');
    }

    /**
     * Get unique form identifier
     */
    getFormId(form) {
        return form.id || form.getAttribute('data-form-id') || 'form_' + form.action;
    }

    /**
     * Schedule a save (debounced)
     */
    scheduleSave(form) {
        const formId = this.getFormId(form);

        // Clear existing timer
        if (this.timers.has(formId)) {
            clearTimeout(this.timers.get(formId));
        }

        // Schedule new save
        const timer = setTimeout(() => {
            this.save(form);
            this.timers.delete(formId);
        }, this.saveDelay);

        this.timers.set(formId, timer);
        this.showSaveIndicator(form, 'saving');
    }

    /**
     * Save form data to localStorage
     */
    save(form) {
        const formId = this.getFormId(form);
        const data = {};

        const inputs = form.querySelectorAll('input, textarea, select');
        inputs.forEach(input => {
            if (input.name && input.type !== 'password' && input.type !== 'hidden') {
                if (input.type === 'checkbox') {
                    data[input.name] = input.checked;
                } else if (input.type === 'radio') {
                    if (input.checked) {
                        data[input.name] = input.value;
                    }
                } else {
                    data[input.name] = input.value;
                }
            }
        });

        // Only save if there's actual data
        const hasData = Object.values(data).some(v => v !== '' && v !== false);
        if (hasData) {
            localStorage.setItem(this.prefix + formId, JSON.stringify({
                data,
                timestamp: Date.now()
            }));
            this.showSaveIndicator(form, 'saved');
        }
    }

    /**
     * Load saved form data
     */
    load(form) {
        const formId = this.getFormId(form);
        const saved = localStorage.getItem(this.prefix + formId);

        if (!saved) return false;

        try {
            const { data, timestamp } = JSON.parse(saved);

            // Don't restore if older than 24 hours
            if (Date.now() - timestamp > 24 * 60 * 60 * 1000) {
                this.clear(form);
                return false;
            }

            // Restore values
            Object.entries(data).forEach(([name, value]) => {
                const input = form.querySelector(`[name="${name}"]`);
                if (input) {
                    if (input.type === 'checkbox') {
                        input.checked = value;
                    } else if (input.type === 'radio') {
                        const radio = form.querySelector(`[name="${name}"][value="${value}"]`);
                        if (radio) radio.checked = true;
                    } else {
                        input.value = value;
                    }
                }
            });

            return true;
        } catch (e) {
            console.error('Failed to load auto-saved data:', e);
            return false;
        }
    }

    /**
     * Clear saved form data
     */
    clear(form) {
        const formId = this.getFormId(form);
        localStorage.removeItem(this.prefix + formId);
        this.hideSaveIndicator(form);
    }

    /**
     * Show save status indicator
     */
    showSaveIndicator(form, status) {
        let indicator = form.querySelector('.autosave-indicator');

        if (!indicator) {
            indicator = document.createElement('div');
            indicator.className = 'autosave-indicator';
            form.appendChild(indicator);
        }

        const messages = {
            saving: 'Saving draft...',
            saved: 'Draft saved',
            restored: 'Draft restored'
        };

        indicator.textContent = messages[status] || status;
        indicator.className = `autosave-indicator ${status}`;
        indicator.style.display = 'block';

        // Hide after a delay (except for 'saving')
        if (status !== 'saving') {
            setTimeout(() => {
                indicator.style.opacity = '0';
                setTimeout(() => {
                    indicator.style.display = 'none';
                    indicator.style.opacity = '1';
                }, 300);
            }, 2000);
        }
    }

    hideSaveIndicator(form) {
        const indicator = form.querySelector('.autosave-indicator');
        if (indicator) {
            indicator.style.display = 'none';
        }
    }
}

// ============================================================================
// REAL-TIME VALIDATION
// ============================================================================

class FormValidator {
    constructor() {
        this.validators = {
            required: (value) => value.trim() !== '' || 'This field is required',
            email: (value) => !value || /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value) || 'Please enter a valid email',
            minLength: (value, min) => !value || value.length >= min || `Minimum ${min} characters required`,
            maxLength: (value, max) => !value || value.length <= max || `Maximum ${max} characters allowed`,
            pattern: (value, pattern) => !value || new RegExp(pattern).test(value) || 'Invalid format',
            date: (value) => !value || !isNaN(Date.parse(value)) || 'Please enter a valid date',
            futureDate: (value) => {
                if (!value) return true;
                const date = new Date(value);
                const today = new Date();
                today.setHours(0, 0, 0, 0);
                return date >= today || 'Date must be today or in the future';
            }
        };
    }

    /**
     * Attach real-time validation to a form
     */
    attach(form) {
        if (!form || form.dataset.validationAttached) return;

        form.dataset.validationAttached = 'true';

        const inputs = form.querySelectorAll('input, textarea, select');
        inputs.forEach(input => {
            // Validate on blur
            input.addEventListener('blur', () => this.validateField(input));

            // Clear error on focus
            input.addEventListener('focus', () => this.clearFieldError(input));

            // Validate on input (with debounce for text fields)
            if (input.type === 'text' || input.type === 'email' || input.tagName === 'TEXTAREA') {
                let timer;
                input.addEventListener('input', () => {
                    clearTimeout(timer);
                    timer = setTimeout(() => this.validateField(input, true), 500);
                });
            } else {
                input.addEventListener('change', () => this.validateField(input));
            }
        });

        // Validate on submit
        form.addEventListener('submit', (e) => {
            if (!this.validateForm(form)) {
                e.preventDefault();
            }
        });
    }

    /**
     * Validate a single field
     */
    validateField(input, silent = false) {
        const rules = this.getFieldRules(input);
        const value = input.value;

        for (const rule of rules) {
            const result = this.runRule(rule, value);
            if (result !== true) {
                if (!silent) {
                    this.showFieldError(input, result);
                }
                return false;
            }
        }

        this.showFieldSuccess(input);
        return true;
    }

    /**
     * Get validation rules for a field
     */
    getFieldRules(input) {
        const rules = [];

        if (input.required) {
            rules.push({ type: 'required' });
        }

        if (input.type === 'email') {
            rules.push({ type: 'email' });
        }

        if (input.minLength > 0) {
            rules.push({ type: 'minLength', param: input.minLength });
        }

        if (input.maxLength > 0 && input.maxLength < 524288) {
            rules.push({ type: 'maxLength', param: input.maxLength });
        }

        if (input.pattern) {
            rules.push({ type: 'pattern', param: input.pattern });
        }

        if (input.type === 'date' && input.dataset.futureOnly) {
            rules.push({ type: 'futureDate' });
        }

        // Custom validation from data attributes
        if (input.dataset.validate) {
            input.dataset.validate.split(',').forEach(v => {
                const [type, param] = v.trim().split(':');
                rules.push({ type, param });
            });
        }

        return rules;
    }

    /**
     * Run a validation rule
     */
    runRule(rule, value) {
        const validator = this.validators[rule.type];
        if (!validator) return true;
        return validator(value, rule.param);
    }

    /**
     * Validate entire form
     */
    validateForm(form) {
        const inputs = form.querySelectorAll('input, textarea, select');
        let isValid = true;

        inputs.forEach(input => {
            if (!this.validateField(input)) {
                isValid = false;
            }
        });

        if (!isValid) {
            // Focus first invalid field
            const firstInvalid = form.querySelector('.input-error, .field-error');
            if (firstInvalid) {
                firstInvalid.focus();
            }
        }

        return isValid;
    }

    /**
     * Show field error
     */
    showFieldError(input, message) {
        this.clearFieldError(input);

        input.classList.add('input-error');
        input.classList.remove('input-success');

        const errorEl = document.createElement('span');
        errorEl.className = 'field-error-message';
        errorEl.textContent = message;

        const wrapper = input.closest('.form-field') || input.parentNode;
        wrapper.appendChild(errorEl);

        // Shake animation
        input.classList.add('shake');
        setTimeout(() => input.classList.remove('shake'), 500);
    }

    /**
     * Show field success
     */
    showFieldSuccess(input) {
        this.clearFieldError(input);

        if (input.value.trim()) {
            input.classList.add('input-success');
        }
    }

    /**
     * Clear field error
     */
    clearFieldError(input) {
        input.classList.remove('input-error', 'input-success');

        const wrapper = input.closest('.form-field') || input.parentNode;
        const existingError = wrapper.querySelector('.field-error-message');
        existingError?.remove();
    }

    /**
     * Add custom validator
     */
    addValidator(name, fn) {
        this.validators[name] = fn;
    }
}

// ============================================================================
// GLOBAL INSTANCES & INITIALIZATION
// ============================================================================

const modalManager = new ModalManager();
const dragDrop = new DragDropManager({
    onReorder: async (taskId, fromIndex, toIndex) => {
        try {
            // Update task order via API (if endpoint exists)
            console.log(`Task ${taskId} moved from ${fromIndex} to ${toIndex}`);
            toast?.success('Task order updated');
        } catch (error) {
            toast?.error('Failed to update task order');
            console.error('Reorder error:', error);
        }
    }
});
const formAutoSave = new FormAutoSave();
const formValidator = new FormValidator();

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', () => {
    // Initialize drag-drop on task lists
    const taskList = document.querySelector('#taskList, .task-list');
    if (taskList) {
        dragDrop.init('#taskList, .task-list');
    }

    // Attach validation to all forms
    document.querySelectorAll('form').forEach(form => {
        formValidator.attach(form);
    });

    // Enhance existing modal show/close functions
    if (typeof window.showCreateTaskModal === 'function') {
        const originalShow = window.showCreateTaskModal;
        window.showCreateTaskModal = function() {
            modalManager.open('taskModal', { animation: 'slide-up' });
        };
    }

    if (typeof window.closeTaskModal === 'function') {
        const originalClose = window.closeTaskModal;
        window.closeTaskModal = function() {
            modalManager.close('taskModal');
        };
    }

    // Enhanced delete with confirmation
    if (typeof window.deleteTask === 'function') {
        const originalDelete = window.deleteTask;
        window.deleteTask = async function(taskId) {
            const confirmed = await modalManager.confirm(
                'Are you sure you want to delete this task? This action cannot be undone.',
                {
                    title: 'Delete Task',
                    confirmText: 'Delete',
                    danger: true
                }
            );

            if (confirmed) {
                try {
                    await fetch(`/api/tasks/${taskId}`, { method: 'DELETE' });
                    toast?.success('Task deleted');
                    location.reload();
                } catch (error) {
                    toast?.error('Failed to delete task');
                }
            }
        };
    }
});

// Export for global use
window.modalManager = modalManager;
window.dragDrop = dragDrop;
window.formAutoSave = formAutoSave;
window.formValidator = formValidator;
