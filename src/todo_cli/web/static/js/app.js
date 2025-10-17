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
        try {
            ui.showLoading();
            
            // Load tasks, contexts, and tags in parallel
            const [tasks, contexts, tags] = await Promise.all([
                api.getTasks(),
                api.getContexts(),
                api.getTags()
            ]);
            
            this.tasks = tasks || [];
            this.contexts = contexts || [];
            this.tags = tags || [];
            
            // Update UI
            this.updateContextSelect();
            this.renderTasks();
            this.renderContexts();
            this.renderTags();
            
        } catch (error) {
            console.error('Failed to load initial data:', error);
            ui.showError('Failed to load data. Please refresh the page.');
        } finally {
            ui.hideLoading();
        }
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
            
            this.tasks = await api.getTasks(filters);
            this.renderTasks();
            
        } catch (error) {
            console.error('Failed to load tasks:', error);
            ui.showError('Failed to load tasks');
        }
    }

    async filterTasks() {
        await this.loadTasks();
    }

    renderTasks() {
        const taskList = document.getElementById('task-list');
        if (!taskList) return;

        taskList.innerHTML = '';

        if (this.tasks.length === 0) {
            taskList.innerHTML = '<p class="no-tasks">No tasks found. Create your first task!</p>';
            return;
        }

        this.tasks.forEach(task => {
            const taskElement = ui.renderTask(task);
            taskList.appendChild(taskElement);
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
        // Clear all columns
        const pendingColumn = document.getElementById('pending-tasks');
        const inProgressColumn = document.getElementById('in-progress-tasks');
        const completedColumn = document.getElementById('completed-tasks');

        if (pendingColumn) pendingColumn.innerHTML = '';
        if (inProgressColumn) inProgressColumn.innerHTML = '';
        if (completedColumn) completedColumn.innerHTML = '';

        // Distribute tasks to columns
        tasks.forEach(task => {
            const taskElement = ui.renderBoardTask(task);
            
            if (task.status === 'completed' && completedColumn) {
                completedColumn.appendChild(taskElement);
            } else if (task.status === 'blocked' && inProgressColumn) {
                inProgressColumn.appendChild(taskElement);
            } else if (pendingColumn) {
                pendingColumn.appendChild(taskElement);
            }
        });
    }

    async loadContextData() {
        try {
            this.contexts = await api.getContexts();
            this.renderContexts();
        } catch (error) {
            console.error('Failed to load contexts:', error);
            ui.showError('Failed to load contexts');
        }
    }

    renderContexts() {
        const contextsList = document.getElementById('contexts-list');
        if (!contextsList) return;

        contextsList.innerHTML = '';

        this.contexts.forEach(context => {
            const contextElement = document.createElement('div');
            contextElement.className = 'context-item';
            contextElement.innerHTML = `
                <span class="context-name">@${context.name}</span>
                <span class="context-count">${context.task_count} tasks</span>
            `;
            contextsList.appendChild(contextElement);
        });
    }

    async loadTagData() {
        try {
            this.tags = await api.getTags();
            this.renderTags();
        } catch (error) {
            console.error('Failed to load tags:', error);
            ui.showError('Failed to load tags');
        }
    }

    renderTags() {
        const tagsList = document.getElementById('tags-list');
        if (!tagsList) return;

        tagsList.innerHTML = '';

        this.tags.forEach(tag => {
            const tagElement = document.createElement('div');
            tagElement.className = 'tag-item';
            tagElement.innerHTML = `
                <span class="tag-name">#${tag.name}</span>
                <span class="tag-count">${tag.task_count} tasks</span>
            `;
            tagsList.appendChild(tagElement);
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
                const option = document.createElement('option');
                option.value = context.name;
                option.textContent = `@${context.name}`;
                select.appendChild(option);
            });
            
        } catch (error) {
            console.error('Failed to load contexts for select:', error);
        }
    }
}

// Initialize app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.app = new TodoApp();
});

// Export for potential module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { TodoApp };
}