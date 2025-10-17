/**
 * API Client for Todo CLI PWA
 * 
 * This module provides a JavaScript client for interacting with the Todo CLI REST API.
 */

class TodoAPI {
    constructor(baseURL = '') {
        this.baseURL = baseURL;
        this.headers = {
            'Content-Type': 'application/json'
        };
    }

    async request(endpoint, options = {}) {
        const url = `${this.baseURL}${endpoint}`;
        const config = {
            headers: this.headers,
            ...options
        };

        try {
            const response = await fetch(url, config);
            
            if (!response.ok) {
                const errorData = await response.json().catch(() => null);
                throw new Error(errorData?.detail || `HTTP ${response.status}: ${response.statusText}`);
            }

            // Handle empty responses (like DELETE)
            const contentType = response.headers.get('content-type');
            if (contentType && contentType.includes('application/json')) {
                return await response.json();
            }
            
            return null;
        } catch (error) {
            console.error('API Request failed:', error);
            throw error;
        }
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

    // Health check
    async healthCheck() {
        return this.request('/api/health');
    }
}

// Create global API instance
const api = new TodoAPI();

// Export for potential module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { TodoAPI, api };
}