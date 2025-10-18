/**
 * Main Application for Todo CLI PWA
 * 
 * This module contains the main application logic and event handlers.
 */

class TodoApp {
    constructor() {
        this.currentContext = '';
        this.currentFilters = {};
        this.tasks = [];
        this.contexts = [];
        this.tags = [];
        this.isLoading = false;
        this.loadingStates = new Set();
        
        // Set up global error handling
        this.setupGlobalErrorHandling();
        
        this.init();
    }

    async init() {
        this.setupEventListeners();
        ui.setupKeyboardShortcuts();
        
        // Load initial data
        await this.loadInitialData();
        
        // Show default view
        ui.showView('list-view');
        
        console.log('Todo CLI PWA initialized');
    }

    async loadInitialData() {
        return this.withErrorHandling(async () => {
            this.setLoadingState('initial-load', true);
            
            try {
                // Use enhanced data loader if available, otherwise fallback to direct API
                if (typeof dataLoader !== 'undefined') {
                    const data = await dataLoader.loadInitialData();
                    this.tasks = data.tasks || [];
                    this.contexts = data.contexts || [];
                    this.tags = data.tags || [];
                    this.projects = data.projects || [];
                } else {
                    // Fallback to direct API calls
                    const [tasks, contexts, tags] = await Promise.allSettled([
                        api.getTasks(),
                        api.getContexts(),
                        api.getTags()
                    ]);
                    
                    this.tasks = tasks.status === 'fulfilled' ? (tasks.value || []) : [];
                    this.contexts = contexts.status === 'fulfilled' ? (contexts.value || []) : [];
                    this.tags = tags.status === 'fulfilled' ? (tags.value || []) : [];
                    
                    // Report any failed requests
                    [tasks, contexts, tags].forEach((result, index) => {
                        if (result.status === 'rejected') {
                            const names = ['tasks', 'contexts', 'tags'];
                            console.warn(`Failed to load ${names[index]}:`, result.reason);
                        }
                    });
                }
                
                // Filter out any null/invalid tasks
                this.tasks = Array.isArray(this.tasks) ? this.tasks.filter(task => task && task.id) : [];
                this.contexts = Array.isArray(this.contexts) ? this.contexts : [];
                this.tags = Array.isArray(this.tags) ? this.tags : [];
                
                // Update UI
                this.updateContextSelect();
                this.renderTasks();
                this.renderContexts();
                this.renderTags();
                
            } finally {
                this.setLoadingState('initial-load', false);
            }
        }, 'Initial Data Load')();
    }

    setupEventListeners() {
        // Navigation
        document.addEventListener('click', (e) => {
            if (e.target.matches('.nav-link')) {
                e.preventDefault();
                const view = e.target.dataset.view;
                if (view) {
                    this.showView(view);
                }
                ui.closeMobileMenu();
            }
        });

        // Mobile menu toggle
        const menuToggle = document.getElementById('menu-toggle');
        if (menuToggle) {
            menuToggle.addEventListener('click', () => {
                ui.toggleMobileMenu();
            });
        }

        // Quick capture
        const quickCaptureBtn = document.getElementById('quick-capture');
        if (quickCaptureBtn) {
            quickCaptureBtn.addEventListener('click', () => {
                ui.showModal('quick-capture-modal');
            });
        }

        // Context select
        const contextSelect = document.getElementById('context-select');
        if (contextSelect) {
            contextSelect.addEventListener('change', (e) => {
                this.currentContext = e.target.value;
                this.filterTasks();
            });
        }

        // Search and filters
        const searchInput = document.getElementById('search-input');
        if (searchInput) {
            const debouncedSearch = ui.debounce(() => {
                this.currentFilters.search = searchInput.value;
                this.filterTasks();
            }, 300);
            
            searchInput.addEventListener('input', debouncedSearch);
        }

        const filterStatus = document.getElementById('filter-status');
        if (filterStatus) {
            filterStatus.addEventListener('change', (e) => {
                this.currentFilters.status = e.target.value;
                this.filterTasks();
            });
        }

        // Quick capture form
        const quickCaptureForm = document.getElementById('quick-capture-save');
        if (quickCaptureForm) {
            quickCaptureForm.addEventListener('click', async () => {
                await this.handleQuickCapture();
            });
        }

        const quickCaptureCancel = document.getElementById('quick-capture-cancel');
        if (quickCaptureCancel) {
            quickCaptureCancel.addEventListener('click', () => {
                ui.hideModal('quick-capture-modal');
                this.clearQuickCapture();
            });
        }

        // Task edit form
        const taskEditForm = document.getElementById('task-edit-form');
        if (taskEditForm) {
            taskEditForm.addEventListener('submit', async (e) => {
                e.preventDefault();
                await this.handleTaskEdit();
            });
        }

        const taskEditCancel = document.getElementById('task-edit-cancel');
        if (taskEditCancel) {
            taskEditCancel.addEventListener('click', () => {
                ui.hideModal('task-edit-modal');
            });
        }

        const taskDeleteBtn = document.getElementById('task-delete');
        if (taskDeleteBtn) {
            taskDeleteBtn.addEventListener('click', async () => {
                await this.handleTaskDelete();
            });
        }

        // Task actions using event delegation
        const taskList = document.getElementById('task-list');
        if (taskList) {
            ui.delegate(taskList, 'click', '.toggle-task', async (e) => {
                const taskId = e.target.dataset.taskId;
                await this.toggleTask(taskId);
            });

            ui.delegate(taskList, 'click', '.edit-task', (e) => {
                const taskId = e.target.dataset.taskId;
                this.editTask(taskId);
            });

            ui.delegate(taskList, 'click', '.delete-task', async (e) => {
                const taskId = e.target.dataset.taskId;
                if (confirm('Are you sure you want to delete this task?')) {
                    await this.deleteTask(taskId);
                }
            });
        }

        // Backup actions
        const backupBtn = document.getElementById('backup-btn');
        if (backupBtn) {
            backupBtn.addEventListener('click', async () => {
                await this.createBackup();
            });
        }

        const restoreBtn = document.getElementById('restore-btn');
        if (restoreBtn) {
            restoreBtn.addEventListener('click', () => {
                this.showRestoreOptions();
            });
        }

        // Modal close buttons
        document.addEventListener('click', (e) => {
            if (e.target.matches('.modal-close')) {
                const modal = e.target.closest('.modal');
                if (modal) {
                    modal.classList.remove('show');
                }
            }
        });

        // Close modals when clicking outside
        document.addEventListener('click', (e) => {
            if (e.target.matches('.modal')) {
                e.target.classList.remove('show');
            }
        });
    }

    async showView(viewName) {
        const viewId = `${viewName}-view`;
        ui.showView(viewId);

        // Load data specific to the view
        switch (viewName) {
            case 'board':
                await this.loadBoardData();
                break;
            case 'contexts':
                await this.loadContextData();
                break;
            case 'tags':
                await this.loadTagData();
                break;
            case 'backup':
                await this.loadBackupData();
                break;
            default:
                // List view - already loaded
                break;
        }
    }

    async handleQuickCapture() {
        const input = document.getElementById('quick-capture-input');
        if (!input || !input.value.trim()) {
            ui.showWarning('Please enter a task title');
            return;
        }

        try {
            ui.showLoading();
            
            const taskData = {
                title: input.value.trim(),
                context: this.currentContext || null
            };

            await api.createTask(taskData);
            
            ui.hideModal('quick-capture-modal');
            this.clearQuickCapture();
            ui.showSuccess('Task created successfully');
            
            // Refresh task list
            await this.loadTasks();
            
        } catch (error) {
            console.error('Failed to create task:', error);
            ui.showError('Failed to create task: ' + error.message);
        } finally {
            ui.hideLoading();
        }
    }

    clearQuickCapture() {
        const input = document.getElementById('quick-capture-input');
        if (input) {
            input.value = '';
        }
    }

    async editTask(taskId) {
        try {
            const task = await api.getTask(taskId);
            
            // Populate form
            ui.setFormData('task-edit-form', {
                'task-id': task.id,
                'task-title': task.title,
                'task-description': task.description || '',
                'task-priority': task.priority || '',
                'task-tags': task.tags.join(', '),
                'task-context': task.context || ''
            });

            // Populate context options
            await this.populateContextOptions('task-context');
            
            ui.showModal('task-edit-modal');
            
        } catch (error) {
            console.error('Failed to load task:', error);
            ui.showError('Failed to load task details');
        }
    }

    async handleTaskEdit() {
        try {
            ui.showLoading();
            
            const formData = ui.getFormData('task-edit-form');
            const taskId = document.getElementById('task-id').value;
            
            const taskData = {
                title: formData['task-title'],
                description: formData['task-description'] || null,
                priority: formData['task-priority'] || null,
                tags: formData['task-tags'] ? formData['task-tags'].split(',').map(t => t.trim()) : [],
                context: formData['task-context'] || null
            };

            await api.updateTask(taskId, taskData);
            
            ui.hideModal('task-edit-modal');
            ui.showSuccess('Task updated successfully');
            
            // Refresh task list
            await this.loadTasks();
            
        } catch (error) {
            console.error('Failed to update task:', error);
            ui.showError('Failed to update task: ' + error.message);
        } finally {
            ui.hideLoading();
        }
    }

    async handleTaskDelete() {
        const taskId = document.getElementById('task-id').value;
        
        if (!confirm('Are you sure you want to delete this task?')) {
            return;
        }

        try {
            ui.showLoading();
            
            await api.deleteTask(taskId);
            
            ui.hideModal('task-edit-modal');
            ui.showSuccess('Task deleted successfully');
            
            // Refresh task list
            await this.loadTasks();
            
        } catch (error) {
            console.error('Failed to delete task:', error);
            ui.showError('Failed to delete task: ' + error.message);
        } finally {
            ui.hideLoading();
        }
    }

    async toggleTask(taskId) {
        try {
            await api.toggleTask(taskId);
            ui.showSuccess('Task status updated');
            
            // Refresh task list
            await this.loadTasks();
            
        } catch (error) {
            console.error('Failed to toggle task:', error);
            ui.showError('Failed to update task: ' + error.message);
        }
    }

    async deleteTask(taskId) {
        try {
            ui.showLoading();
            
            await api.deleteTask(taskId);
            ui.showSuccess('Task deleted successfully');
            
            // Refresh task list
            await this.loadTasks();
            
        } catch (error) {
            console.error('Failed to delete task:', error);
            ui.showError('Failed to delete task: ' + error.message);
        } finally {
            ui.hideLoading();
        }
    }

    async loadTasks() {
        try {
            const filters = {
                ...this.currentFilters,
                context: this.currentContext || undefined
            };
            
            // Use enhanced data loader if available
            if (typeof dataLoader !== 'undefined') {
                this.tasks = await dataLoader.loadTasks(filters);
            } else {
                this.tasks = await api.getTasks(filters);
            }
            
            // Filter out any null/invalid tasks
            this.tasks = this.tasks.filter(task => task && task.id);
            this.renderTasks();
            
        } catch (error) {
            console.error('Failed to load tasks:', error);
            const errorMsg = error.isNetworkError ? 
                'Unable to connect to server. Please check your connection.' :
                'Failed to load tasks. Please try again.';
            ui.showError(errorMsg);
        }
    }

    async filterTasks() {
        await this.loadTasks();
    }

    renderTasks() {
        const taskList = document.getElementById('task-list');
        if (!taskList) return;

        taskList.innerHTML = '';

        // Handle empty state with helpful messages
        if (!Array.isArray(this.tasks) || this.tasks.length === 0) {
            const hasFilters = this.currentContext || Object.keys(this.currentFilters).some(key => this.currentFilters[key]);
            const emptyMessage = hasFilters ? 
                'No tasks match your current filters. Try adjusting your search criteria.' :
                'No tasks found. Create your first task using the + Quick Add button!';
            
            taskList.innerHTML = `
                <div class="empty-state">
                    <p class="no-tasks">${emptyMessage}</p>
                    ${!hasFilters ? '<button class="btn btn-primary" onclick="ui.showModal(\'quick-capture-modal\')">Create Your First Task</button>' : ''}
                </div>
            `;
            return;
        }

        // Filter out any invalid tasks and render valid ones
        const validTasks = this.tasks.filter(task => task && task.id && task.title);
        
        if (validTasks.length === 0) {
            taskList.innerHTML = '<div class="empty-state"><p class="no-tasks">No valid tasks to display.</p></div>';
            return;
        }

        validTasks.forEach(task => {
            try {
                const taskElement = ui.renderTask(task);
                if (taskElement) {
                    taskList.appendChild(taskElement);
                }
            } catch (error) {
                console.warn('Failed to render task:', task.id, error);
            }
        });
    }

    async loadBoardData() {
        try {
            const tasks = await api.getTasks(this.currentFilters);
            this.renderBoard(tasks);
        } catch (error) {
            console.error('Failed to load board data:', error);
            ui.showError('Failed to load board view');
        }
    }

    renderBoard(tasks) {
        // Get all board columns with defensive checks
        const pendingColumn = document.getElementById('pending-tasks');
        const inProgressColumn = document.getElementById('in-progress-tasks');
        const completedColumn = document.getElementById('completed-tasks');

        // Clear all columns safely
        const columns = { pendingColumn, inProgressColumn, completedColumn };
        Object.values(columns).forEach(column => {
            if (column) column.innerHTML = '';
        });

        // Validate tasks input
        if (!Array.isArray(tasks)) {
            console.warn('Invalid tasks array for board rendering:', tasks);
            this.renderBoardEmptyState();
            return;
        }

        const validTasks = tasks.filter(task => task && task.id && task.title);
        
        if (validTasks.length === 0) {
            this.renderBoardEmptyState();
            return;
        }

        // Track tasks per column for empty state handling
        const columnCounts = { pending: 0, inProgress: 0, completed: 0 };

        // Distribute tasks to columns with error handling
        validTasks.forEach(task => {
            try {
                const taskElement = ui.renderBoardTask(task);
                if (!taskElement) return; // Skip invalid renders
                
                const status = task.status || 'pending';
                
                if (status === 'completed' && completedColumn) {
                    completedColumn.appendChild(taskElement);
                    columnCounts.completed++;
                } else if ((status === 'in-progress' || status === 'blocked') && inProgressColumn) {
                    inProgressColumn.appendChild(taskElement);
                    columnCounts.inProgress++;
                } else if (pendingColumn) {
                    pendingColumn.appendChild(taskElement);
                    columnCounts.pending++;
                }
            } catch (error) {
                console.warn('Failed to render board task:', task.id, error);
            }
        });

        // Add empty state messages to empty columns
        this.addEmptyColumnStates(columns, columnCounts);
    }

    renderBoardEmptyState() {
        const columns = {
            pendingColumn: document.getElementById('pending-tasks'),
            inProgressColumn: document.getElementById('in-progress-tasks'),
            completedColumn: document.getElementById('completed-tasks')
        };
        
        Object.values(columns).forEach(column => {
            if (column) {
                column.innerHTML = `
                    <div class="board-empty-state">
                        <p>No tasks found. Create your first task!</p>
                        <button class="btn btn-sm btn-primary" onclick="ui.showModal('quick-capture-modal')">
                            + Add Task
                        </button>
                    </div>
                `;
            }
        });
    }

    addEmptyColumnStates(columns, columnCounts) {
        const { pendingColumn, inProgressColumn, completedColumn } = columns;
        
        if (pendingColumn && columnCounts.pending === 0) {
            const emptyDiv = document.createElement('div');
            emptyDiv.className = 'column-empty-state';
            emptyDiv.innerHTML = '<p class="empty-message">Drop tasks here or create new ones</p>';
            pendingColumn.appendChild(emptyDiv);
        }
        
        if (inProgressColumn && columnCounts.inProgress === 0) {
            const emptyDiv = document.createElement('div');
            emptyDiv.className = 'column-empty-state';
            emptyDiv.innerHTML = '<p class="empty-message">Tasks in progress will appear here</p>';
            inProgressColumn.appendChild(emptyDiv);
        }
        
        if (completedColumn && columnCounts.completed === 0) {
            const emptyDiv = document.createElement('div');
            emptyDiv.className = 'column-empty-state';
            emptyDiv.innerHTML = '<p class="empty-message">Completed tasks will appear here</p>';
            completedColumn.appendChild(emptyDiv);
        }
    }

    async loadContextData() {
        try {
            // Use enhanced data loader if available
            if (typeof dataLoader !== 'undefined') {
                this.contexts = await dataLoader.loadContexts({ forceRefresh: true });
            } else {
                this.contexts = await api.getContexts();
            }
            this.renderContexts();
        } catch (error) {
            console.error('Failed to load contexts:', error);
            const errorMsg = error.isNetworkError ? 
                'Unable to connect to server. Please check your connection.' :
                'Failed to load contexts. Please try again.';
            ui.showError(errorMsg);
        }
    }

    renderContexts() {
        const contextsList = document.getElementById('contexts-list');
        if (!contextsList) return;

        contextsList.innerHTML = '';

        if (!Array.isArray(this.contexts) || this.contexts.length === 0) {
            contextsList.innerHTML = `
                <div class="empty-state">
                    <p class="no-items">No contexts found. Contexts appear when you add tasks with @context.</p>
                </div>
            `;
            return;
        }

        // Filter and render valid contexts
        const validContexts = this.contexts.filter(context => context && context.name);
        
        validContexts.forEach(context => {
            try {
                const contextElement = document.createElement('div');
                contextElement.className = 'context-item';
                contextElement.innerHTML = `
                    <span class="context-name">@${ui.escapeHtml(context.name)}</span>
                    <span class="context-count">${Number(context.task_count) || 0} tasks</span>
                `;
                contextsList.appendChild(contextElement);
            } catch (error) {
                console.warn('Failed to render context:', context.name, error);
            }
        });
    }
    async loadTagData() {
        try {
            // Use enhanced data loader if available
            if (typeof dataLoader !== 'undefined') {
                this.tags = await dataLoader.loadTags({ forceRefresh: true });
            } else {
                this.tags = await api.getTags();
            }
            this.renderTags();
        } catch (error) {
            console.error('Failed to load tags:', error);
            const errorMsg = error.isNetworkError ? 
                'Unable to connect to server. Please check your connection.' :
                'Failed to load tags. Please try again.';
            ui.showError(errorMsg);
        }
    }

    renderTags() {
        const tagsList = document.getElementById('tags-list');
        if (!tagsList) return;

        tagsList.innerHTML = '';

        if (!Array.isArray(this.tags) || this.tags.length === 0) {
            tagsList.innerHTML = `
                <div class="empty-state">
                    <p class="no-items">No tags found. Tags appear when you add tasks with #hashtags.</p>
                </div>
            `;
            return;
        }

        // Filter and render valid tags
        const validTags = this.tags.filter(tag => tag && tag.name);
        
        validTags.forEach(tag => {
            try {
                const tagElement = document.createElement('div');
                tagElement.className = 'tag-item';
                tagElement.innerHTML = `
                    <span class="tag-name">#${ui.escapeHtml(tag.name)}</span>
                    <span class="tag-count">${Number(tag.task_count) || 0} tasks</span>
                `;
                tagsList.appendChild(tagElement);
            } catch (error) {
                console.warn('Failed to render tag:', tag.name, error);
            }
        });
    }

    async loadBackupData() {
        try {
            const backups = await api.getBackups();
            this.renderBackups(backups);
        } catch (error) {
            console.error('Failed to load backups:', error);
            ui.showError('Failed to load backup list');
        }
    }

    renderBackups(backups) {
        const backupList = document.getElementById('backup-list');
        if (!backupList) return;

        backupList.innerHTML = '';

        if (backups.length === 0) {
            backupList.innerHTML = '<p class="no-backups">No backups found. Create your first backup!</p>';
            return;
        }

        backups.forEach(backup => {
            const backupElement = document.createElement('div');
            backupElement.className = 'backup-item';
            backupElement.innerHTML = `
                <div class="backup-info">
                    <strong>${backup.filename}</strong>
                    <p>Created: ${ui.formatDateTime(backup.created_at)} | Size: ${(backup.size / 1024).toFixed(1)} KB</p>
                </div>
                <div class="backup-actions">
                    <button class="btn btn-sm restore-backup" data-filename="${backup.filename}">Restore</button>
                </div>
            `;

            // Add restore button handler
            const restoreBtn = backupElement.querySelector('.restore-backup');
            restoreBtn.addEventListener('click', async () => {
                if (confirm(`Are you sure you want to restore from ${backup.filename}? This will overwrite current data.`)) {
                    await this.restoreFromBackup(backup.filename);
                }
            });

            backupList.appendChild(backupElement);
        });
    }

    async createBackup() {
        try {
            ui.showLoading();
            
            const result = await api.createBackup();
            ui.showSuccess(`Backup created: ${result.filename}`);
            
            // Refresh backup list if we're on backup view
            const backupView = document.getElementById('backup-view');
            if (backupView && backupView.classList.contains('active')) {
                await this.loadBackupData();
            }
            
        } catch (error) {
            console.error('Failed to create backup:', error);
            ui.showError('Failed to create backup: ' + error.message);
        } finally {
            ui.hideLoading();
        }
    }

    async restoreFromBackup(filename) {
        try {
            ui.showLoading();
            
            await api.restoreBackup(filename);
            ui.showSuccess('Data restored successfully');
            
            // Refresh all data
            await this.loadInitialData();
            
        } catch (error) {
            console.error('Failed to restore backup:', error);
            ui.showError('Failed to restore backup: ' + error.message);
        } finally {
            ui.hideLoading();
        }
    }

    updateContextSelect() {
        const contextSelect = document.getElementById('context-select');
        if (!contextSelect) return;

        // Clear existing options except "All Contexts"
        const allOption = contextSelect.querySelector('option[value=""]');
        contextSelect.innerHTML = '';
        contextSelect.appendChild(allOption);

        // Add context options
        this.contexts.forEach(context => {
            const option = document.createElement('option');
            option.value = context.name;
            option.textContent = `@${context.name} (${context.task_count})`;
            contextSelect.appendChild(option);
        });

        // Restore selected context
        contextSelect.value = this.currentContext;
    }

    async populateContextOptions(selectId) {
        const select = document.getElementById(selectId);
        if (!select) return;

        try {
            const contexts = await api.getContexts();
            
            // Clear existing options except first one
            const firstOption = select.querySelector('option');
            select.innerHTML = '';
            select.appendChild(firstOption);
            
            // Add context options
            contexts.forEach(context => {
                if (context && context.name) {
                    const option = document.createElement('option');
                    option.value = context.name;
                    option.textContent = `@${context.name}`;
                    select.appendChild(option);
                }
            });
            
        } catch (error) {
            console.error('Failed to load contexts for select:', error);
        }
    }
    
    /**
     * Utility functions
     */
    
    setupGlobalErrorHandling() {
        // Catch unhandled JavaScript errors
        window.addEventListener('error', (event) => {
            console.error('Global error caught:', event.error);
            this.handleGlobalError(event.error, 'JavaScript Error');
        });

        // Catch unhandled promise rejections
        window.addEventListener('unhandledrejection', (event) => {
            console.error('Unhandled promise rejection:', event.reason);
            this.handleGlobalError(event.reason, 'Promise Rejection');
        });
    }

    handleGlobalError(error, context = 'Unknown Error') {
        const errorMessage = error?.message || String(error) || 'An unexpected error occurred';
        
        // Show user-friendly error message
        ui.showError(`${context}: ${errorMessage}`, 10000);
        
        // Attempt to recover by reloading data if it seems like a data-related issue
        if (errorMessage.includes('fetch') || errorMessage.includes('network') || errorMessage.includes('API')) {
            setTimeout(() => {
                if (confirm('Would you like to retry loading data?')) {
                    this.handleRetry();
                }
            }, 2000);
        }
    }

    async handleRetry() {
        try {
            await this.loadInitialData();
            ui.showSuccess('Data reloaded successfully');
        } catch (error) {
            console.error('Retry failed:', error);
            ui.showError('Retry failed. Please refresh the page.');
        }
    }

    setLoadingState(operation, isLoading) {
        if (isLoading) {
            this.loadingStates.add(operation);
        } else {
            this.loadingStates.delete(operation);
        }
        
        const shouldShowGlobalLoading = this.loadingStates.size > 0;
        
        if (shouldShowGlobalLoading && !this.isLoading) {
            this.isLoading = true;
            ui.showLoading();
        } else if (!shouldShowGlobalLoading && this.isLoading) {
            this.isLoading = false;
            ui.hideLoading();
        }
    }

    withErrorHandling(asyncFn, errorContext = 'Operation') {
        return async (...args) => {
            try {
                return await asyncFn.apply(this, args);
            } catch (error) {
                console.error(`${errorContext} failed:`, error);
                this.handleGlobalError(error, errorContext);
                throw error; // Re-throw for calling code to handle if needed
            }
        };
    }

    /**
     * Utility functions
     */
}

// Initialize app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    try {
        window.app = new TodoApp();
    } catch (error) {
        console.error('Failed to initialize TodoApp:', error);
        document.body.innerHTML = `
            <div class="error-boundary">
                <h1>Application Error</h1>
                <p>Failed to initialize the Todo application.</p>
                <button onclick="location.reload()">Reload Page</button>
            </div>
        `;
    }
});
// Export for potential module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { TodoApp };
}