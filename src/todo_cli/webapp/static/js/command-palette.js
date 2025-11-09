/**
 * Command Palette Implementation
 * Provides quick access to actions and navigation throughout the app
 */

class CommandPalette {
    constructor() {
        this.commands = [];
        this.recentItems = [];
        this.selectedIndex = 0;
        this.filteredCommands = [];
        this.isInitialized = false;
    }

    init() {
        if (this.isInitialized) return;
        
        this.registerCommands();
        this.loadRecentItems();
        this.setupEventListeners();
        this.isInitialized = true;
    }

    registerCommands() {
        this.commands = [
            // Task commands
            {
                id: 'create-task',
                title: 'Create new task',
                subtitle: 'Add a new task to your list',
                icon: '➕',
                action: () => {
                    this.close();
                    if (typeof showCreateTaskModal === 'function') {
                        showCreateTaskModal();
                    } else {
                        window.location.href = '/tasks';
                    }
                },
                keywords: ['new', 'add', 'create', 'task', 'todo'],
            },
            {
                id: 'view-tasks',
                title: 'View all tasks',
                subtitle: 'See your complete task list',
                icon: '📋',
                action: () => {
                    this.close();
                    window.location.href = '/tasks';
                },
                keywords: ['tasks', 'list', 'all', 'view'],
            },
            {
                id: 'today-tasks',
                title: 'Today\'s tasks',
                subtitle: 'View tasks due today',
                icon: '📅',
                action: () => {
                    this.close();
                    window.location.href = '/tasks/today';
                },
                keywords: ['today', 'due', 'tasks'],
            },
            {
                id: 'upcoming-tasks',
                title: 'Upcoming tasks',
                subtitle: 'View tasks due soon',
                icon: '🔜',
                action: () => {
                    this.close();
                    window.location.href = '/tasks/upcoming';
                },
                keywords: ['upcoming', 'soon', 'future', 'tasks'],
            },
            
            // Project commands
            {
                id: 'create-project',
                title: 'Create new project',
                subtitle: 'Organize tasks into a new project',
                icon: '📁',
                action: () => {
                    this.close();
                    if (typeof showCreateProjectModal === 'function') {
                        showCreateProjectModal();
                    } else {
                        window.location.href = '/projects';
                    }
                },
                keywords: ['new', 'add', 'create', 'project', 'folder'],
            },
            {
                id: 'view-projects',
                title: 'View all projects',
                subtitle: 'See all your projects',
                icon: '📂',
                action: () => {
                    this.close();
                    window.location.href = '/projects';
                },
                keywords: ['projects', 'list', 'all', 'view'],
            },
            
            // Navigation commands
            {
                id: 'dashboard',
                title: 'Go to Dashboard',
                subtitle: 'View your overview',
                icon: '🏠',
                action: () => {
                    this.close();
                    window.location.href = '/dashboard';
                },
                keywords: ['dashboard', 'home', 'overview'],
            },
            {
                id: 'analytics',
                title: 'View Analytics',
                subtitle: 'Track your productivity',
                icon: '📊',
                action: () => {
                    this.close();
                    window.location.href = '/analytics';
                },
                keywords: ['analytics', 'stats', 'metrics', 'productivity'],
            },
            
            // Settings commands
            {
                id: 'logout',
                title: 'Logout',
                subtitle: 'Sign out of your account',
                icon: '🚪',
                action: () => {
                    this.close();
                    window.location.href = '/logout';
                },
                keywords: ['logout', 'sign out', 'exit'],
            },
        ];
    }

    setupEventListeners() {
        const input = document.querySelector('.command-palette-input');
        if (!input) return;

        input.addEventListener('input', (e) => {
            this.search(e.target.value);
        });

        input.addEventListener('keydown', (e) => {
            if (e.key === 'ArrowDown') {
                e.preventDefault();
                this.selectNext();
            } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                this.selectPrevious();
            } else if (e.key === 'Enter') {
                e.preventDefault();
                this.executeSelected();
            }
        });
    }

    search(query) {
        if (!query || query.trim() === '') {
            this.filteredCommands = this.commands;
        } else {
            const lowerQuery = query.toLowerCase();
            this.filteredCommands = this.commands.filter(cmd => {
                const titleMatch = cmd.title.toLowerCase().includes(lowerQuery);
                const subtitleMatch = cmd.subtitle.toLowerCase().includes(lowerQuery);
                const keywordMatch = cmd.keywords.some(k => k.includes(lowerQuery));
                return titleMatch || subtitleMatch || keywordMatch;
            });
        }

        this.selectedIndex = 0;
        this.render();
    }

    selectNext() {
        this.selectedIndex = Math.min(this.selectedIndex + 1, this.filteredCommands.length - 1);
        this.render();
    }

    selectPrevious() {
        this.selectedIndex = Math.max(this.selectedIndex - 1, 0);
        this.render();
    }

    executeSelected() {
        const command = this.filteredCommands[this.selectedIndex];
        if (command) {
            this.addToRecent(command);
            command.action();
        }
    }

    render() {
        const resultsContainer = document.querySelector('.command-palette-results');
        if (!resultsContainer) return;

        if (this.filteredCommands.length === 0) {
            resultsContainer.innerHTML = `
                <div style="padding: 40px; text-align: center; color: var(--color-text-muted);">
                    No commands found
                </div>
            `;
            return;
        }

        resultsContainer.innerHTML = this.filteredCommands.map((cmd, index) => `
            <div class="command-palette-item ${index === this.selectedIndex ? 'selected' : ''}"
                 onclick="commandPalette.executeCommand('${cmd.id}')">
                <div class="command-palette-item-icon" style="font-size: 20px;">${cmd.icon}</div>
                <div class="command-palette-item-content">
                    <div class="command-palette-item-title">${cmd.title}</div>
                    <div class="command-palette-item-subtitle">${cmd.subtitle}</div>
                </div>
            </div>
        `).join('');
    }

    executeCommand(commandId) {
        const command = this.commands.find(c => c.id === commandId);
        if (command) {
            this.addToRecent(command);
            command.action();
        }
    }

    addToRecent(command) {
        this.recentItems = this.recentItems.filter(id => id !== command.id);
        this.recentItems.unshift(command.id);
        this.recentItems = this.recentItems.slice(0, 5);
        this.saveRecentItems();
    }

    saveRecentItems() {
        try {
            localStorage.setItem('commandPaletteRecent', JSON.stringify(this.recentItems));
        } catch (e) {
            // LocalStorage not available
        }
    }

    loadRecentItems() {
        try {
            const stored = localStorage.getItem('commandPaletteRecent');
            if (stored) {
                this.recentItems = JSON.parse(stored);
            }
        } catch (e) {
            // LocalStorage not available
        }
    }

    open() {
        this.init();
        const input = document.querySelector('.command-palette-input');
        if (input) {
            input.value = '';
            this.search('');
            setTimeout(() => input.focus(), 100);
        }
    }

    close() {
        const input = document.querySelector('.command-palette-input');
        if (input) {
            input.value = '';
        }
    }
}

// Create global instance
const commandPalette = new CommandPalette();

// Initialize when Alpine is ready
document.addEventListener('alpine:init', () => {
    commandPalette.init();
});

// Also initialize on DOM ready as fallback
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        setTimeout(() => commandPalette.init(), 100);
    });
} else {
    setTimeout(() => commandPalette.init(), 100);
}

// Listen for command palette open event
document.addEventListener('keydown', (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        commandPalette.open();
    }
});
