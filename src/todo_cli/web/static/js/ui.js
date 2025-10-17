/**
 * UI Utilities for Todo CLI PWA
 * 
 * This module provides utility functions for managing UI interactions and state.
 */

class UIUtils {
    constructor() {
        this.loadingElement = document.getElementById('loading');
        this.toastContainer = document.getElementById('toast-container');
    }

    // Loading indicator
    showLoading() {
        if (this.loadingElement) {
            this.loadingElement.classList.add('show');
        }
    }

    hideLoading() {
        if (this.loadingElement) {
            this.loadingElement.classList.remove('show');
        }
    }

    // Toast notifications
    showToast(message, type = 'info', duration = 5000) {
        if (!this.toastContainer) return;

        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.textContent = message;

        this.toastContainer.appendChild(toast);

        // Auto-remove after duration
        setTimeout(() => {
            if (toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
        }, duration);

        return toast;
    }

    showSuccess(message, duration) {
        return this.showToast(message, 'success', duration);
    }

    showError(message, duration) {
        return this.showToast(message, 'error', duration);
    }

    showWarning(message, duration) {
        return this.showToast(message, 'warning', duration);
    }

    // Modal management
    showModal(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.classList.add('show');
            
            // Focus first input if available
            const firstInput = modal.querySelector('input, textarea, select');
            if (firstInput) {
                firstInput.focus();
            }
        }
    }

    hideModal(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.classList.remove('show');
        }
    }

    hideAllModals() {
        const modals = document.querySelectorAll('.modal.show');
        modals.forEach(modal => modal.classList.remove('show'));
    }

    // View management
    showView(viewId) {
        // Hide all views
        const views = document.querySelectorAll('.view');
        views.forEach(view => view.classList.remove('active'));

        // Show target view
        const targetView = document.getElementById(viewId);
        if (targetView) {
            targetView.classList.add('active');
        }

        // Update navigation
        this.updateNavigation(viewId);
    }

    updateNavigation(activeView) {
        const navLinks = document.querySelectorAll('.nav-link');
        navLinks.forEach(link => {
            link.classList.remove('active');
            if (link.dataset.view === activeView.replace('-view', '')) {
                link.classList.add('active');
            }
        });
    }

    // Form utilities
    getFormData(formId) {
        const form = document.getElementById(formId);
        if (!form) return null;

        const formData = new FormData(form);
        const data = {};

        for (const [key, value] of formData.entries()) {
            data[key] = value;
        }

        return data;
    }

    setFormData(formId, data) {
        const form = document.getElementById(formId);
        if (!form) return;

        Object.keys(data).forEach(key => {
            const element = form.querySelector(`[name="${key}"], #${key}`);
            if (element) {
                if (element.type === 'checkbox') {
                    element.checked = !!data[key];
                } else {
                    element.value = data[key] || '';
                }
            }
        });
    }

    clearForm(formId) {
        const form = document.getElementById(formId);
        if (form) {
            form.reset();
        }
    }

    // Task rendering utilities
    renderTask(task) {
        const taskElement = document.createElement('div');
        taskElement.className = `task-item ${task.status}`;
        taskElement.dataset.taskId = task.id;

        const priorityClass = task.priority ? `task-priority ${task.priority}` : '';
        const tagsHtml = task.tags.map(tag => `<span class="task-tag">${tag}</span>`).join('');

        taskElement.innerHTML = `
            <div class="task-header">
                <h3 class="task-title ${task.status}">${task.title}</h3>
                <div class="task-actions">
                    <button class="btn btn-sm toggle-task" data-task-id="${task.id}">
                        ${task.status === 'completed' ? '↶' : '✓'}
                    </button>
                    <button class="btn btn-sm edit-task" data-task-id="${task.id}">✎</button>
                    <button class="btn btn-sm btn-danger delete-task" data-task-id="${task.id}">✕</button>
                </div>
            </div>
            ${task.description ? `<p class="task-description">${task.description}</p>` : ''}
            <div class="task-meta">
                ${task.priority ? `<span class="${priorityClass}">${task.priority.toUpperCase()}</span>` : ''}
                ${task.context ? `<span class="task-context">@${task.context}</span>` : ''}
                ${task.project ? `<span class="task-project">#${task.project}</span>` : ''}
                ${task.due_date ? `<span class="task-due-date">Due: ${new Date(task.due_date).toLocaleDateString()}</span>` : ''}
                <div class="task-tags">${tagsHtml}</div>
            </div>
        `;

        return taskElement;
    }

    renderBoardTask(task) {
        const taskElement = document.createElement('div');
        taskElement.className = 'board-task';
        taskElement.dataset.taskId = task.id;

        const priorityClass = task.priority ? `task-priority ${task.priority}` : '';
        const tagsHtml = task.tags.map(tag => `<span class="task-tag">${tag}</span>`).join('');

        taskElement.innerHTML = `
            <div class="board-task-header">
                <h4 class="board-task-title">${task.title}</h4>
                ${task.priority ? `<span class="${priorityClass}">${task.priority.charAt(0).toUpperCase()}</span>` : ''}
            </div>
            ${task.description ? `<p class="board-task-description">${task.description}</p>` : ''}
            <div class="board-task-meta">
                ${task.context ? `<span class="task-context">@${task.context}</span>` : ''}
                <div class="task-tags">${tagsHtml}</div>
            </div>
        `;

        // Add click handler to edit task
        taskElement.addEventListener('click', () => {
            app.editTask(task.id);
        });

        return taskElement;
    }

    // Utility functions
    formatDate(dateString) {
        if (!dateString) return '';
        return new Date(dateString).toLocaleDateString();
    }

    formatDateTime(dateString) {
        if (!dateString) return '';
        return new Date(dateString).toLocaleString();
    }

    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }

    // Event delegation helper
    delegate(element, eventType, selector, handler) {
        element.addEventListener(eventType, (event) => {
            if (event.target.matches(selector) || event.target.closest(selector)) {
                const target = event.target.matches(selector) ? event.target : event.target.closest(selector);
                handler.call(target, event);
            }
        });
    }

    // Mobile menu toggle
    toggleMobileMenu() {
        const nav = document.getElementById('nav');
        const menuToggle = document.getElementById('menu-toggle');
        
        if (nav && menuToggle) {
            nav.classList.toggle('show');
        }
    }

    closeMobileMenu() {
        const nav = document.getElementById('nav');
        if (nav) {
            nav.classList.remove('show');
        }
    }

    // Keyboard shortcuts
    setupKeyboardShortcuts() {
        document.addEventListener('keydown', (e) => {
            // Escape key closes modals
            if (e.key === 'Escape') {
                this.hideAllModals();
            }

            // Ctrl/Cmd + K for quick capture
            if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
                e.preventDefault();
                this.showModal('quick-capture-modal');
            }

            // Ctrl/Cmd + Enter in forms submits them
            if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
                const form = e.target.closest('form');
                if (form) {
                    e.preventDefault();
                    form.requestSubmit();
                }
            }
        });
    }
}

// Create global UI utilities instance
const ui = new UIUtils();

// Export for potential module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { UIUtils, ui };
}