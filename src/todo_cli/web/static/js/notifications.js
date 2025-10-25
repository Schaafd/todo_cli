/**
 * Notification System for Todo CLI PWA
 * 
 * Provides toast and banner notifications with actionable controls
 * for errors, warnings, success messages, and offline states.
 */

class NotificationSystem {
    constructor() {
        this.container = null;
        this.notificationQueue = [];
        this.currentNotifications = new Map();
        this.notificationId = 0;
        this.maxNotifications = 3;
        
        this.init();
    }

    init() {
        // Create notification container if it doesn't exist
        this.container = document.getElementById('notification-container');
        if (!this.container) {
            this.container = document.createElement('div');
            this.container.id = 'notification-container';
            this.container.className = 'notification-container';
            document.body.appendChild(this.container);
        }
    }

    /**
     * Show a notification with various options
     * @param {Object} options - Notification configuration
     * @param {string} options.message - The message to display
     * @param {string} options.type - Notification type: 'success', 'error', 'warning', 'info'
     * @param {number} options.duration - Duration in ms (0 = persistent)
     * @param {boolean} options.dismissible - Whether user can dismiss
     * @param {Object} options.action - Optional action button {text, callback}
     * @param {string} options.icon - Optional icon HTML/emoji
     * @returns {number} Notification ID
     */
    show(options) {
        const notification = {
            id: ++this.notificationId,
            message: options.message || '',
            type: options.type || 'info',
            duration: options.duration !== undefined ? options.duration : 5000,
            dismissible: options.dismissible !== undefined ? options.dismissible : true,
            action: options.action || null,
            icon: options.icon || this.getDefaultIcon(options.type),
            timestamp: Date.now()
        };

        // Check if we're at max capacity
        if (this.currentNotifications.size >= this.maxNotifications) {
            this.notificationQueue.push(notification);
        } else {
            this.renderNotification(notification);
        }

        return notification.id;
    }

    getDefaultIcon(type) {
        const icons = {
            success: '✓',
            error: '✕',
            warning: '⚠',
            info: 'ℹ'
        };
        return icons[type] || icons.info;
    }

    renderNotification(notification) {
        const element = document.createElement('div');
        element.className = `notification toast ${notification.type}`;
        element.setAttribute('data-notification-id', notification.id);
        element.setAttribute('role', 'alert');
        element.setAttribute('aria-live', notification.type === 'error' ? 'assertive' : 'polite');

        // Build notification content
        const iconHtml = notification.icon ? `<span class="notification-icon">${notification.icon}</span>` : '';
        const messageHtml = `<div class="notification-message">${this.escapeHtml(notification.message)}</div>`;
        
        let actionsHtml = '';
        if (notification.action || notification.dismissible) {
            actionsHtml = '<div class="notification-actions">';
            
            if (notification.action) {
                actionsHtml += `
                    <button class="notification-action-btn" data-action="custom">
                        ${this.escapeHtml(notification.action.text)}
                    </button>
                `;
            }
            
            if (notification.dismissible) {
                actionsHtml += `
                    <button class="notification-close" data-action="close" aria-label="Close notification">
                        ×
                    </button>
                `;
            }
            
            actionsHtml += '</div>';
        }

        element.innerHTML = `
            <div class="notification-content">
                ${iconHtml}
                <div class="notification-body">
                    ${messageHtml}
                </div>
                ${actionsHtml}
            </div>
        `;

        // Add event listeners
        const closeBtn = element.querySelector('[data-action="close"]');
        if (closeBtn) {
            closeBtn.addEventListener('click', () => this.dismiss(notification.id));
        }

        const actionBtn = element.querySelector('[data-action="custom"]');
        if (actionBtn && notification.action) {
            actionBtn.addEventListener('click', async () => {
                try {
                    if (notification.action.callback) {
                        await notification.action.callback();
                    }
                    this.dismiss(notification.id);
                } catch (error) {
                    console.error('Notification action failed:', error);
                }
            });
        }

        // Add to container with animation
        this.container.appendChild(element);
        
        // Trigger reflow for animation
        void element.offsetWidth;
        element.classList.add('show');

        // Store notification reference
        this.currentNotifications.set(notification.id, {
            ...notification,
            element
        });

        // Auto-dismiss if duration is set
        if (notification.duration > 0) {
            setTimeout(() => this.dismiss(notification.id), notification.duration);
        }
    }

    dismiss(notificationId) {
        const notification = this.currentNotifications.get(notificationId);
        if (!notification) return;

        const element = notification.element;
        
        // Animate out
        element.classList.remove('show');
        element.classList.add('hide');

        setTimeout(() => {
            if (element.parentNode) {
                element.parentNode.removeChild(element);
            }
            this.currentNotifications.delete(notificationId);

            // Process queue
            if (this.notificationQueue.length > 0) {
                const next = this.notificationQueue.shift();
                this.renderNotification(next);
            }
        }, 300);
    }

    dismissAll() {
        this.currentNotifications.forEach((_, id) => this.dismiss(id));
        this.notificationQueue = [];
    }

    // Convenience methods
    success(message, duration = 5000, action = null) {
        return this.show({ message, type: 'success', duration, action });
    }

    error(message, duration = 10000, action = null) {
        return this.show({ message, type: 'error', duration, action });
    }

    warning(message, duration = 7000, action = null) {
        return this.show({ message, type: 'warning', duration, action });
    }

    info(message, duration = 5000, action = null) {
        return this.show({ message, type: 'info', duration, action });
    }

    // Error-specific notifications with actionable responses
    showNetworkError(retryCallback) {
        return this.error(
            'Unable to connect to server. Please check your connection.',
            0, // Persistent
            {
                text: 'Retry',
                callback: retryCallback
            }
        );
    }

    showApiError(endpoint, error, retryCallback) {
        const message = error.status === 404 
            ? `Resource not found: ${endpoint}`
            : error.status === 403
            ? 'Access denied. Please check your permissions.'
            : error.status >= 500
            ? 'Server error. Please try again later.'
            : `API Error: ${error.message}`;

        return this.error(
            message,
            retryCallback ? 0 : 10000,
            retryCallback ? {
                text: 'Retry',
                callback: retryCallback
            } : null
        );
    }

    showJsonParseError(refreshCallback) {
        return this.error(
            'Failed to parse server response. The data may be corrupted.',
            0,
            {
                text: 'Refresh',
                callback: refreshCallback || (() => window.location.reload())
            }
        );
    }

    showNoDataWarning(context = 'items', addCallback = null) {
        const message = `No ${context} found. ${addCallback ? 'Would you like to add one?' : 'Try adding one via CLI or the app.'}`;
        
        return this.warning(
            message,
            addCallback ? 0 : 7000,
            addCallback ? {
                text: 'Add Now',
                callback: addCallback
            } : null
        );
    }

    showOfflineNotice(syncCallback) {
        return this.warning(
            'You are currently offline. Changes will sync when connection is restored.',
            0,
            syncCallback ? {
                text: 'Try Sync',
                callback: syncCallback
            } : null
        );
    }

    showValidationError(fields) {
        const fieldList = Array.isArray(fields) ? fields.join(', ') : fields;
        return this.error(
            `Validation failed: ${fieldList}`,
            7000
        );
    }

    showRateLimitWarning(retryAfter) {
        const message = retryAfter 
            ? `Rate limit exceeded. Please try again in ${retryAfter} seconds.`
            : 'Rate limit exceeded. Please try again later.';
        
        return this.warning(message, 10000);
    }

    showDataSyncSuccess(itemCount) {
        return this.success(
            `Successfully synced ${itemCount} item${itemCount !== 1 ? 's' : ''}.`,
            3000
        );
    }

    showOperationSuccess(operation, itemName = null) {
        const message = itemName 
            ? `${operation} "${itemName}" successfully.`
            : `${operation} completed successfully.`;
        
        return this.success(message, 3000);
    }

    showOperationFailure(operation, error) {
        return this.error(
            `Failed to ${operation.toLowerCase()}: ${error.message || 'Unknown error'}`,
            10000
        );
    }

    // Utility methods
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // Debug mode logging (only in development)
    logError(context, error) {
        if (typeof ENV !== 'undefined' && ENV.DEBUG) {
            console.error(`[Notifications] ${context}:`, error);
        }
        
        // Optional: Send to external error tracking service
        // this.sendToErrorTracking(context, error);
    }

    // Placeholder for production error tracking integration
    sendToErrorTracking(context, error) {
        // TODO: Integrate with Sentry, Rollbar, or similar service
        // Only in production, respecting secrets policy
        /*
        if (typeof Sentry !== 'undefined' && ENV.ENVIRONMENT === 'production') {
            Sentry.captureException(error, {
                tags: { context },
                level: 'error'
            });
        }
        */
    }
}

// Create global notification system instance
const notifications = new NotificationSystem();

// Export for potential module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { NotificationSystem, notifications };
}
