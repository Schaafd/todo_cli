/**
 * Data Loader for Todo CLI PWA
 * 
 * This module provides enhanced data loading with:
 * - Data transformation and normalization  
 * - Error handling and retry logic
 * - Loading states and caching
 * - Field mapping between API and UI expectations
 */

class DataLoader {
    constructor(apiClient) {
        this.api = apiClient;
        this.cache = new Map();
        this.loadingStates = new Map();
        this.config = typeof ENV !== 'undefined' ? ENV : {};
        
        // Configure cache TTL (time to live) in milliseconds
        this.cacheTTL = {
            tasks: 30000,      // 30 seconds
            projects: 60000,   // 1 minute
            contexts: 60000,   // 1 minute  
            tags: 60000,       // 1 minute
            health: 10000      // 10 seconds
        };
    }
    
    /**
     * Load tasks with enhanced error handling and data transformation
     */
    async loadTasks(filters = {}, options = {}) {
        const cacheKey = `tasks:${JSON.stringify(filters)}`;
        const { forceRefresh = false, showLoading = true } = options;
        
        try {
            // Check cache first
            if (!forceRefresh && this.isCached(cacheKey, 'tasks')) {
                return this.getFromCache(cacheKey);
            }
            
            // Avoid duplicate requests  
            if (this.loadingStates.has(cacheKey)) {
                return await this.loadingStates.get(cacheKey);
            }
            
            if (showLoading && typeof ui !== 'undefined') {
                ui.showLoading();
            }
            
            const loadPromise = this._loadTasksInternal(filters);
            this.loadingStates.set(cacheKey, loadPromise);
            
            const tasks = await loadPromise;
            const normalizedTasks = this.normalizeTasks(tasks);
            
            // Cache the result
            this.setCache(cacheKey, normalizedTasks);
            this.loadingStates.delete(cacheKey);
            
            return normalizedTasks;
            
        } catch (error) {
            this.loadingStates.delete(cacheKey);
            throw this.enhanceError(error, 'Failed to load tasks');
        } finally {
            if (showLoading && typeof ui !== 'undefined') {
                ui.hideLoading();
            }
        }
    }
    
    async _loadTasksInternal(filters) {
        // Clean filters - remove empty/undefined values
        const cleanFilters = this.cleanFilters(filters);
        
        if (this.config.DEBUG) {
            console.log('Loading tasks with filters:', cleanFilters);
        }
        
        return await this.api.getTasks(cleanFilters);
    }
    
    /**
     * Normalize task data from API response
     */
    normalizeTasks(tasks) {
        if (!Array.isArray(tasks)) {
            console.warn('Expected tasks array, got:', typeof tasks, tasks);
            return [];
        }
        
        return tasks.map(task => this.normalizeTask(task));
    }
    
    normalizeTask(task) {
        if (!task || typeof task !== 'object') {
            console.warn('Invalid task object:', task);
            return null;
        }
        
        // Ensure required fields exist
        const normalized = {
            id: String(task.id || ''),
            title: String(task.title || ''),
            description: task.description || '',
            status: this.normalizeStatus(task.status),
            priority: this.normalizePriority(task.priority),
            tags: Array.isArray(task.tags) ? task.tags : [],
            context: this.normalizeContext(task.context),
            project: task.project || null,
            due_date: this.normalizeDate(task.due_date),
            created_at: this.normalizeDate(task.created_at),
            updated_at: this.normalizeDate(task.updated_at),
            is_blocked: Boolean(task.is_blocked),
            dependencies: Array.isArray(task.dependencies) ? task.dependencies : []
        };
        
        // Validate normalized task
        if (!normalized.id || !normalized.title) {
            console.warn('Task missing required fields:', normalized);
            return null;
        }
        
        return normalized;
    }
    
    normalizeStatus(status) {
        const validStatuses = ['pending', 'completed', 'blocked'];
        return validStatuses.includes(status) ? status : 'pending';
    }
    
    normalizePriority(priority) {
        const validPriorities = ['low', 'medium', 'high', 'urgent'];
        return validPriorities.includes(priority) ? priority : null;
    }
    
    normalizeContext(context) {
        // Handle context as string or array (take first if array)
        if (Array.isArray(context)) {
            return context.length > 0 ? context[0] : null;
        }
        return context || null;
    }
    
    normalizeDate(dateStr) {
        if (!dateStr) return null;
        try {
            return new Date(dateStr).toISOString();
        } catch (error) {
            console.warn('Invalid date:', dateStr);
            return null;
        }
    }
    
    /**
     * Load contexts with normalization
     */
    async loadContexts(options = {}) {
        const cacheKey = 'contexts';
        const { forceRefresh = false } = options;
        
        try {
            if (!forceRefresh && this.isCached(cacheKey, 'contexts')) {
                return this.getFromCache(cacheKey);
            }
            
            const contexts = await this.api.getContexts();
            const normalized = this.normalizeContexts(contexts);
            
            this.setCache(cacheKey, normalized);
            return normalized;
            
        } catch (error) {
            throw this.enhanceError(error, 'Failed to load contexts');
        }
    }
    
    normalizeContexts(contexts) {
        if (!Array.isArray(contexts)) {
            console.warn('Expected contexts array, got:', typeof contexts, contexts);
            return [];
        }
        
        return contexts.map(context => ({
            name: String(context.name || ''),
            task_count: Number(context.task_count || 0)
        })).filter(context => context.name);
    }
    
    /**
     * Load tags with normalization
     */
    async loadTags(options = {}) {
        const cacheKey = 'tags';
        const { forceRefresh = false } = options;
        
        try {
            if (!forceRefresh && this.isCached(cacheKey, 'tags')) {
                return this.getFromCache(cacheKey);
            }
            
            const tags = await this.api.getTags();
            const normalized = this.normalizeTags(tags);
            
            this.setCache(cacheKey, normalized);
            return normalized;
            
        } catch (error) {
            throw this.enhanceError(error, 'Failed to load tags');
        }
    }
    
    normalizeTags(tags) {
        if (!Array.isArray(tags)) {
            console.warn('Expected tags array, got:', typeof tags, tags);
            return [];
        }
        
        return tags.map(tag => ({
            name: String(tag.name || ''),
            task_count: Number(tag.task_count || 0)
        })).filter(tag => tag.name);
    }
    
    /**
     * Load projects with normalization
     */
    async loadProjects(options = {}) {
        const cacheKey = 'projects';
        const { forceRefresh = false } = options;
        
        try {
            if (!forceRefresh && this.isCached(cacheKey, 'projects')) {
                return this.getFromCache(cacheKey);
            }
            
            const projects = await this.api.getProjects();
            const normalized = this.normalizeProjects(projects);
            
            this.setCache(cacheKey, normalized);
            return normalized;
            
        } catch (error) {
            throw this.enhanceError(error, 'Failed to load projects');
        }
    }
    
    normalizeProjects(projects) {
        if (!Array.isArray(projects)) {
            console.warn('Expected projects array, got:', typeof projects, projects);
            return [];
        }
        
        return projects.map(project => ({
            name: String(project.name || ''),
            display_name: String(project.display_name || project.name || ''),
            description: project.description || '',
            task_count: Number(project.task_count || 0),
            completed_tasks: Number(project.completed_tasks || 0),
            active: Boolean(project.active),
            created_at: this.normalizeDate(project.created_at),
            color: project.color || null
        })).filter(project => project.name);
    }
    
    /**
     * Load all data needed for initialization
     */
    async loadInitialData() {
        try {
            if (this.config.DEBUG) {
                console.log('Loading initial data...');
            }
            
            // Load all data in parallel
            const [tasks, contexts, tags, projects] = await Promise.allSettled([
                this.loadTasks({}, { showLoading: false }),
                this.loadContexts(),
                this.loadTags(),
                this.loadProjects()
            ]);
            
            const result = {
                tasks: tasks.status === 'fulfilled' ? tasks.value : [],
                contexts: contexts.status === 'fulfilled' ? contexts.value : [],
                tags: tags.status === 'fulfilled' ? tags.value : [],
                projects: projects.status === 'fulfilled' ? projects.value : []
            };
            
            // Log any failures
            if (tasks.status === 'rejected') console.error('Failed to load tasks:', tasks.reason);
            if (contexts.status === 'rejected') console.error('Failed to load contexts:', contexts.reason);
            if (tags.status === 'rejected') console.error('Failed to load tags:', tags.reason);
            if (projects.status === 'rejected') console.error('Failed to load projects:', projects.reason);
            
            return result;
            
        } catch (error) {
            throw this.enhanceError(error, 'Failed to load initial data');
        }
    }
    
    /**
     * Health check with caching
     */
    async checkHealth() {
        const cacheKey = 'health';
        
        try {
            if (this.isCached(cacheKey, 'health')) {
                return this.getFromCache(cacheKey);
            }
            
            const health = await this.api.healthCheck();
            this.setCache(cacheKey, health);
            return health;
            
        } catch (error) {
            throw this.enhanceError(error, 'Health check failed');
        }
    }
    
    /**
     * Clean filters by removing empty/undefined values
     */
    cleanFilters(filters) {
        const cleaned = {};
        
        Object.keys(filters).forEach(key => {
            const value = filters[key];
            if (value !== null && value !== undefined && value !== '') {
                cleaned[key] = value;
            }
        });
        
        return cleaned;
    }
    
    /**
     * Cache management
     */
    isCached(key, type) {
        const cached = this.cache.get(key);
        if (!cached) return false;
        
        const ttl = this.cacheTTL[type] || 30000;
        return (Date.now() - cached.timestamp) < ttl;
    }
    
    getFromCache(key) {
        const cached = this.cache.get(key);
        return cached ? cached.data : null;
    }
    
    setCache(key, data) {
        this.cache.set(key, {
            data,
            timestamp: Date.now()
        });
    }
    
    invalidateCache(pattern = null) {
        if (pattern) {
            // Clear specific cache entries matching pattern
            for (const key of this.cache.keys()) {
                if (key.includes(pattern)) {
                    this.cache.delete(key);
                }
            }
        } else {
            // Clear all cache
            this.cache.clear();
        }
    }
    
    /**
     * Error enhancement with context
     */
    enhanceError(error, context = '') {
        const enhanced = new Error(`${context}: ${error.message}`);
        enhanced.originalError = error;
        enhanced.context = context;
        enhanced.timestamp = Date.now();
        
        // Preserve important error properties
        if (error.status) enhanced.status = error.status;
        if (error.response) enhanced.response = error.response;
        if (error.isNetworkError) enhanced.isNetworkError = error.isNetworkError;
        
        return enhanced;
    }
    
    /**
     * Get loading state for a cache key
     */
    isLoading(key) {
        return this.loadingStates.has(key);
    }
}

// Create global instance
if (typeof window !== 'undefined') {
    // Wait for api to be available
    document.addEventListener('DOMContentLoaded', () => {
        if (typeof api !== 'undefined') {
            window.dataLoader = new DataLoader(api);
        }
    });
}

// Export for potential module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { DataLoader };
}