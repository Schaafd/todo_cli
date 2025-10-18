/**
 * API Client for Todo CLI PWA
 * 
 * This module provides a JavaScript client for interacting with the Todo CLI REST API.
 */

class TodoAPI {
    constructor(baseURL = '') {
        // Use configuration if available, otherwise default to current origin
        this.baseURL = baseURL || (typeof ENV !== 'undefined' ? ENV.API_BASE_URL : window.location.origin);
        this.config = typeof ENV !== 'undefined' ? ENV.API : {
            TIMEOUT: 10000,
            RETRY_ATTEMPTS: 3,
            RETRY_DELAY: 1000
        };
        this.headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        };
        
        if (typeof ENV !== 'undefined' && ENV.DEBUG) {
            console.log('TodoAPI initialized with base URL:', this.baseURL);
        }
    }

    async request(endpoint, options = {}, retryCount = 0) {
        const url = `${this.baseURL}${endpoint}`;
        const config = {
            headers: this.headers,
            timeout: this.config.TIMEOUT,
            ...options
        };

        if (typeof ENV !== 'undefined' && ENV.DEBUG) {
            console.log(`API Request: ${options.method || 'GET'} ${url}`, config);
        }

        try {
            // Create abort controller for timeout
            const abortController = new AbortController();
            const timeoutId = setTimeout(() => abortController.abort(), this.config.TIMEOUT);
            
            const response = await fetch(url, {
                ...config,
                signal: abortController.signal
            });
            
            clearTimeout(timeoutId);
            
            if (!response.ok) {
                const errorData = await response.json().catch(() => null);
                const error = new Error(errorData?.detail || `HTTP ${response.status}: ${response.statusText}`);
                error.status = response.status;
                error.response = errorData;
                throw error;
            }

            // Handle empty responses (like DELETE)
            const contentType = response.headers.get('content-type');
            if (contentType && contentType.includes('application/json')) {
                const data = await response.json();
                if (typeof ENV !== 'undefined' && ENV.DEBUG) {
                    console.log(`API Response: ${url}`, data);
                }
                return data;
            }
            
            return null;
        } catch (error) {
            if (typeof ENV !== 'undefined' && ENV.DEBUG) {
                console.error('API Request failed:', { url, error, retryCount });
            }
            
            // Retry logic for network errors
            if (retryCount < this.config.RETRY_ATTEMPTS && this.shouldRetry(error)) {
                await this.delay(this.config.RETRY_DELAY * (retryCount + 1));
                return this.request(endpoint, options, retryCount + 1);
            }
            
            // Enhance error with additional context
            if (!error.status) {
                error.isNetworkError = true;
                error.message = 'Network error - please check your connection';
            }
            
            throw error;
        }
    }
    
    shouldRetry(error) {
        // Retry on network errors or 5xx server errors
        return error.name === 'AbortError' || 
               error.name === 'TypeError' || 
               (error.status >= 500 && error.status < 600);
    }
    
    delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    // Task endpoints
    async getTasks(filters = {}) {
        const params = new URLSearchParams();
        
        if (filters.context) params.append('context', filters.context);
        if (filters.project) params.append('project', filters.project);
        if (filters.status) params.append('status', filters.status);
        if (filters.search) params.append('search', filters.search);

        const queryString = params.toString();
        const endpoint = `/api/tasks${queryString ? `?${queryString}` : ''}`;
        
        return this.request(endpoint);
    }

    async getTask(taskId) {
        return this.request(`/api/tasks/${taskId}`);
    }

    async createTask(taskData) {
        return this.request('/api/tasks', {
            method: 'POST',
            body: JSON.stringify(taskData)
        });
    }

    async updateTask(taskId, taskData) {
        return this.request(`/api/tasks/${taskId}`, {
            method: 'PUT',
            body: JSON.stringify(taskData)
        });
    }

    async deleteTask(taskId) {
        return this.request(`/api/tasks/${taskId}`, {
            method: 'DELETE'
        });
    }

    async toggleTask(taskId) {
        const task = await this.getTask(taskId);
        const newStatus = task.status === 'completed' ? 'pending' : 'completed';
        
        return this.updateTask(taskId, { status: newStatus });
    }

    // Context endpoints
    async getContexts() {
        return this.request('/api/contexts');
    }

    // Tag endpoints
    async getTags() {
        return this.request('/api/tags');
    }

    // Backup endpoints
    async getBackups() {
        return this.request('/api/backups');
    }

    async createBackup() {
        return this.request('/api/backups', {
            method: 'POST'
        });
    }

    async restoreBackup(filename) {
        return this.request(`/api/backups/${filename}/restore`, {
            method: 'POST'
        });
    }

    // Project endpoints
    async getProjects() {
        return this.request('/api/projects');
    }

    // Health check
    async healthCheck() {
        return this.request('/health');
    }
}

// Create global API instance
const api = new TodoAPI();

// Export for potential module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { TodoAPI, api };
}