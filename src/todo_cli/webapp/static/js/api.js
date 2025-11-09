/**
 * API Wrapper for Todo CLI Web App
 * Provides consistent interface for all API calls with error handling and loading states
 */

class TodoAPI {
    constructor() {
        this.baseURL = '/api';
        this.defaultHeaders = {
            'Content-Type': 'application/json',
        };
    }

    /**
     * Generic request handler with error handling
     */
    async request(endpoint, options = {}) {
        const url = `${this.baseURL}${endpoint}`;
        const config = {
            ...options,
            headers: {
                ...this.defaultHeaders,
                ...options.headers,
            },
        };

        try {
            const response = await fetch(url, config);
            
            if (!response.ok) {
                const error = await response.json().catch(() => ({}));
                throw new Error(error.detail || `HTTP ${response.status}: ${response.statusText}`);
            }

            return await response.json();
        } catch (error) {
            console.error(`API Error [${options.method || 'GET'} ${endpoint}]:`, error);
            throw error;
        }
    }

    // ========================================================================
    // Task API Methods
    // ========================================================================

    /**
     * Get all tasks with optional filters
     */
    async getTasks(filters = {}) {
        const params = new URLSearchParams();
        if (filters.project) params.append('project', filters.project);
        if (filters.status) params.append('status', filters.status);
        if (filters.priority) params.append('priority', filters.priority);
        
        const query = params.toString();
        return this.request(`/tasks${query ? '?' + query : ''}`);
    }

    /**
     * Get single task by ID
     */
    async getTask(taskId) {
        return this.request(`/tasks/${taskId}`);
    }

    /**
     * Create new task
     */
    async createTask(taskData) {
        return this.request('/tasks', {
            method: 'POST',
            body: JSON.stringify(taskData),
        });
    }

    /**
     * Update existing task
     */
    async updateTask(taskId, updates) {
        return this.request(`/tasks/${taskId}`, {
            method: 'PUT',
            body: JSON.stringify(updates),
        });
    }

    /**
     * Delete task
     */
    async deleteTask(taskId) {
        return this.request(`/tasks/${taskId}`, {
            method: 'DELETE',
        });
    }

    /**
     * Toggle task completion status
     */
    async toggleTask(taskId) {
        return this.request(`/tasks/${taskId}/toggle`, {
            method: 'POST',
        });
    }

    // ========================================================================
    // Project API Methods
    // ========================================================================

    /**
     * Get all projects
     */
    async getProjects() {
        return this.request('/projects');
    }

    /**
     * Get single project by ID
     */
    async getProject(projectId) {
        return this.request(`/projects/${projectId}`);
    }

    /**
     * Create new project
     */
    async createProject(projectData) {
        return this.request('/projects', {
            method: 'POST',
            body: JSON.stringify(projectData),
        });
    }

    /**
     * Update existing project
     */
    async updateProject(projectId, updates) {
        return this.request(`/projects/${projectId}`, {
            method: 'PUT',
            body: JSON.stringify(updates),
        });
    }

    /**
     * Delete project
     */
    async deleteProject(projectId) {
        return this.request(`/projects/${projectId}`, {
            method: 'DELETE',
        });
    }
}

// ========================================================================
// Toast Notification System
// ========================================================================

class Toast {
    constructor() {
        this.container = this.createContainer();
        this.queue = [];
        this.isShowing = false;
    }

    createContainer() {
        let container = document.getElementById('toast-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'toast-container';
            container.style.cssText = `
                position: fixed;
                top: 20px;
                right: 20px;
                z-index: 10000;
                display: flex;
                flex-direction: column;
                gap: 10px;
                max-width: 400px;
            `;
            document.body.appendChild(container);
        }
        return container;
    }

    show(message, type = 'info', duration = 3000) {
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        
        const colors = {
            success: '#10b981',
            error: '#ef4444',
            warning: '#f59e0b',
            info: '#3b82f6',
        };

        const icons = {
            success: '✓',
            error: '✕',
            warning: '⚠',
            info: 'ℹ',
        };

        toast.style.cssText = `
            background: ${colors[type] || colors.info};
            color: white;
            padding: 12px 20px;
            border-radius: 8px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            display: flex;
            align-items: center;
            gap: 10px;
            font-size: 14px;
            font-weight: 500;
            animation: slideInRight 0.3s ease-out;
            cursor: pointer;
        `;

        toast.innerHTML = `
            <span style="font-size: 18px; font-weight: bold;">${icons[type] || icons.info}</span>
            <span>${message}</span>
        `;

        toast.addEventListener('click', () => this.hide(toast));

        this.container.appendChild(toast);

        setTimeout(() => {
            this.hide(toast);
        }, duration);
    }

    hide(toast) {
        toast.style.animation = 'slideOutRight 0.3s ease-out';
        setTimeout(() => {
            if (toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
        }, 300);
    }

    success(message, duration) {
        this.show(message, 'success', duration);
    }

    error(message, duration) {
        this.show(message, 'error', duration);
    }

    warning(message, duration) {
        this.show(message, 'warning', duration);
    }

    info(message, duration) {
        this.show(message, 'info', duration);
    }
}

// ========================================================================
// Loading Indicator
// ========================================================================

class LoadingIndicator {
    constructor() {
        this.overlay = null;
        this.count = 0;
    }

    show(message = 'Loading...') {
        this.count++;
        
        if (!this.overlay) {
            this.overlay = document.createElement('div');
            this.overlay.id = 'loading-overlay';
            this.overlay.style.cssText = `
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: rgba(0, 0, 0, 0.5);
                display: flex;
                align-items: center;
                justify-content: center;
                z-index: 9999;
                animation: fadeIn 0.2s ease-out;
            `;

            this.overlay.innerHTML = `
                <div style="
                    background: white;
                    padding: 30px 40px;
                    border-radius: 12px;
                    box-shadow: 0 10px 25px rgba(0, 0, 0, 0.2);
                    text-align: center;
                ">
                    <div style="
                        width: 40px;
                        height: 40px;
                        border: 4px solid #e5e7eb;
                        border-top-color: #3b82f6;
                        border-radius: 50%;
                        animation: spin 1s linear infinite;
                        margin: 0 auto 15px;
                    "></div>
                    <div id="loading-message" style="
                        color: #374151;
                        font-size: 16px;
                        font-weight: 500;
                    ">${message}</div>
                </div>
            `;

            document.body.appendChild(this.overlay);
        }
    }

    hide() {
        this.count = Math.max(0, this.count - 1);
        
        if (this.count === 0 && this.overlay) {
            this.overlay.style.animation = 'fadeOut 0.2s ease-out';
            setTimeout(() => {
                if (this.overlay && this.overlay.parentNode) {
                    this.overlay.parentNode.removeChild(this.overlay);
                    this.overlay = null;
                }
            }, 200);
        }
    }

    updateMessage(message) {
        if (this.overlay) {
            const messageEl = this.overlay.querySelector('#loading-message');
            if (messageEl) {
                messageEl.textContent = message;
            }
        }
    }
}

// ========================================================================
// Global Instances
// ========================================================================

// Create global instances
const api = new TodoAPI();
const toast = new Toast();
const loading = new LoadingIndicator();

// Add animations to document
if (!document.getElementById('app-animations')) {
    const style = document.createElement('style');
    style.id = 'app-animations';
    style.textContent = `
        @keyframes slideInRight {
            from {
                transform: translateX(100%);
                opacity: 0;
            }
            to {
                transform: translateX(0);
                opacity: 1;
            }
        }

        @keyframes slideOutRight {
            from {
                transform: translateX(0);
                opacity: 1;
            }
            to {
                transform: translateX(100%);
                opacity: 0;
            }
        }

        @keyframes fadeIn {
            from { opacity: 0; }
            to { opacity: 1; }
        }

        @keyframes fadeOut {
            from { opacity: 1; }
            to { opacity: 0; }
        }

        @keyframes spin {
            to { transform: rotate(360deg); }
        }
    `;
    document.head.appendChild(style);
}

// Export for use in other scripts
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { TodoAPI, Toast, LoadingIndicator, api, toast, loading };
}
