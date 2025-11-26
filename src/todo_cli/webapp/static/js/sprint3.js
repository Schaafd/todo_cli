/**
 * Sprint 3: Polish Features
 * - Loading Skeleton Screens
 * - Micro-interactions & Animations
 * - Mobile Optimization
 * - Accessibility Features
 * - Dark Mode Support
 */

// ============================================================================
// SKELETON LOADING SCREENS
// ============================================================================

class SkeletonLoader {
    constructor() {
        this.templates = {
            task: this.createTaskSkeleton,
            project: this.createProjectSkeleton,
            stat: this.createStatSkeleton,
            list: this.createListSkeleton
        };
    }

    /**
     * Show skeleton in a container
     */
    show(container, type = 'task', count = 3) {
        if (typeof container === 'string') {
            container = document.querySelector(container);
        }
        if (!container) return;

        container.dataset.originalContent = container.innerHTML;
        container.classList.add('is-loading');

        let skeletonHTML = '';
        const templateFn = this.templates[type] || this.templates.task;

        for (let i = 0; i < count; i++) {
            skeletonHTML += templateFn.call(this);
        }

        container.innerHTML = skeletonHTML;
    }

    /**
     * Hide skeleton and restore content
     */
    hide(container) {
        if (typeof container === 'string') {
            container = document.querySelector(container);
        }
        if (!container) return;

        container.classList.remove('is-loading');

        if (container.dataset.originalContent) {
            container.innerHTML = container.dataset.originalContent;
            delete container.dataset.originalContent;
        }
    }

    /**
     * Replace skeleton with new content
     */
    replace(container, newContent) {
        if (typeof container === 'string') {
            container = document.querySelector(container);
        }
        if (!container) return;

        container.classList.remove('is-loading');
        container.innerHTML = newContent;
        delete container.dataset.originalContent;

        // Trigger stagger animation
        const items = container.querySelectorAll('.task-item, .project-card, .stat-card');
        items.forEach((item, index) => {
            item.classList.add('stagger-item');
            item.style.animationDelay = `${index * 0.05}s`;
        });
    }

    createTaskSkeleton() {
        return `
            <div class="skeleton-task">
                <div class="skeleton skeleton-task-checkbox"></div>
                <div class="skeleton-task-content">
                    <div class="skeleton skeleton-task-title"></div>
                    <div class="skeleton-task-meta">
                        <div class="skeleton skeleton-task-badge"></div>
                        <div class="skeleton skeleton-task-badge"></div>
                    </div>
                </div>
            </div>
        `;
    }

    createProjectSkeleton() {
        return `
            <div class="skeleton-project">
                <div class="skeleton-project-header">
                    <div class="skeleton skeleton-project-color"></div>
                    <div class="skeleton skeleton-project-title"></div>
                </div>
                <div class="skeleton skeleton-project-desc"></div>
                <div class="skeleton skeleton-project-desc" style="width: 80%;"></div>
                <div class="skeleton skeleton-project-progress"></div>
            </div>
        `;
    }

    createStatSkeleton() {
        return `
            <div class="skeleton-stat">
                <div class="skeleton skeleton-stat-value"></div>
                <div class="skeleton skeleton-stat-label"></div>
            </div>
        `;
    }

    createListSkeleton() {
        return `
            <div class="skeleton skeleton-text" style="width: 90%;"></div>
            <div class="skeleton skeleton-text" style="width: 75%;"></div>
            <div class="skeleton skeleton-text" style="width: 85%;"></div>
        `;
    }
}

// ============================================================================
// THEME MANAGER (Dark Mode Support)
// ============================================================================

class ThemeManager {
    constructor() {
        this.storageKey = 'todo_theme';
        this.themes = ['light', 'dark', 'auto'];
        this.currentTheme = this.loadTheme();
        this.mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');

        this.init();
    }

    init() {
        this.applyTheme(this.currentTheme);

        // Listen for system theme changes
        this.mediaQuery.addEventListener('change', (e) => {
            if (this.currentTheme === 'auto') {
                this.updateAutoTheme();
            }
        });
    }

    loadTheme() {
        return localStorage.getItem(this.storageKey) || 'dark';
    }

    saveTheme(theme) {
        localStorage.setItem(this.storageKey, theme);
    }

    applyTheme(theme) {
        this.currentTheme = theme;
        this.saveTheme(theme);

        if (theme === 'auto') {
            document.documentElement.classList.add('auto-theme');
            document.documentElement.removeAttribute('data-theme');
            this.updateAutoTheme();
        } else {
            document.documentElement.classList.remove('auto-theme');
            document.documentElement.setAttribute('data-theme', theme);
        }

        // Dispatch theme change event
        window.dispatchEvent(new CustomEvent('themechange', { detail: { theme } }));
    }

    updateAutoTheme() {
        const isDark = this.mediaQuery.matches;
        document.documentElement.setAttribute('data-theme', isDark ? 'dark' : 'light');
    }

    toggle() {
        const currentIndex = this.themes.indexOf(this.currentTheme);
        const nextIndex = (currentIndex + 1) % this.themes.length;
        this.applyTheme(this.themes[nextIndex]);
        return this.currentTheme;
    }

    setTheme(theme) {
        if (this.themes.includes(theme)) {
            this.applyTheme(theme);
        }
    }

    getTheme() {
        return this.currentTheme;
    }

    getEffectiveTheme() {
        if (this.currentTheme === 'auto') {
            return this.mediaQuery.matches ? 'dark' : 'light';
        }
        return this.currentTheme;
    }
}

// ============================================================================
// ACCESSIBILITY MANAGER
// ============================================================================

class AccessibilityManager {
    constructor() {
        this.init();
    }

    init() {
        this.setupSkipLink();
        this.setupFocusTrap();
        this.setupKeyboardNavigation();
        this.setupLiveRegion();
        this.setupReducedMotion();
    }

    /**
     * Create skip to main content link
     */
    setupSkipLink() {
        if (document.querySelector('.skip-link')) return;

        const skipLink = document.createElement('a');
        skipLink.href = '#main-content';
        skipLink.className = 'skip-link';
        skipLink.textContent = 'Skip to main content';
        document.body.insertBefore(skipLink, document.body.firstChild);

        // Add id to main content if not present
        const main = document.querySelector('.main-content, main, [role="main"]');
        if (main && !main.id) {
            main.id = 'main-content';
        }
    }

    /**
     * Trap focus within modal dialogs
     */
    setupFocusTrap() {
        document.addEventListener('keydown', (e) => {
            if (e.key !== 'Tab') return;

            const modal = document.querySelector('.modal.active, .modal-container[style*="block"] .modal');
            if (!modal) return;

            const focusable = modal.querySelectorAll(
                'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
            );

            if (focusable.length === 0) return;

            const first = focusable[0];
            const last = focusable[focusable.length - 1];

            if (e.shiftKey && document.activeElement === first) {
                e.preventDefault();
                last.focus();
            } else if (!e.shiftKey && document.activeElement === last) {
                e.preventDefault();
                first.focus();
            }
        });
    }

    /**
     * Enhanced keyboard navigation
     */
    setupKeyboardNavigation() {
        document.addEventListener('keydown', (e) => {
            // Arrow key navigation for lists
            if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
                const focused = document.activeElement;
                const list = focused.closest('.task-list, .command-palette-results');

                if (list) {
                    e.preventDefault();
                    const items = list.querySelectorAll('.task-item, .command-palette-item');
                    const currentIndex = Array.from(items).indexOf(focused.closest('.task-item, .command-palette-item'));

                    let nextIndex;
                    if (e.key === 'ArrowDown') {
                        nextIndex = Math.min(currentIndex + 1, items.length - 1);
                    } else {
                        nextIndex = Math.max(currentIndex - 1, 0);
                    }

                    items[nextIndex]?.focus();
                }
            }

            // Enter/Space to activate
            if (e.key === 'Enter' || e.key === ' ') {
                const focused = document.activeElement;
                if (focused.classList.contains('task-item') || focused.classList.contains('project-card')) {
                    e.preventDefault();
                    focused.click();
                }
            }
        });

        // Make task items focusable
        document.querySelectorAll('.task-item, .project-card').forEach(item => {
            if (!item.hasAttribute('tabindex')) {
                item.setAttribute('tabindex', '0');
                item.setAttribute('role', 'button');
            }
        });
    }

    /**
     * Setup ARIA live region for announcements
     */
    setupLiveRegion() {
        if (document.getElementById('aria-live-region')) return;

        const liveRegion = document.createElement('div');
        liveRegion.id = 'aria-live-region';
        liveRegion.setAttribute('aria-live', 'polite');
        liveRegion.setAttribute('aria-atomic', 'true');
        liveRegion.className = 'sr-only';
        document.body.appendChild(liveRegion);
    }

    /**
     * Announce message to screen readers
     */
    announce(message, priority = 'polite') {
        const liveRegion = document.getElementById('aria-live-region');
        if (!liveRegion) return;

        liveRegion.setAttribute('aria-live', priority);
        liveRegion.textContent = '';

        // Use setTimeout to ensure announcement
        setTimeout(() => {
            liveRegion.textContent = message;
        }, 100);
    }

    /**
     * Respect reduced motion preference
     */
    setupReducedMotion() {
        const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)');

        const updateMotion = (e) => {
            if (e.matches) {
                document.documentElement.classList.add('reduce-motion');
            } else {
                document.documentElement.classList.remove('reduce-motion');
            }
        };

        updateMotion(mediaQuery);
        mediaQuery.addEventListener('change', updateMotion);
    }
}

// ============================================================================
// MOBILE OPTIMIZATION
// ============================================================================

class MobileOptimizer {
    constructor() {
        this.isTouchDevice = this.detectTouch();
        this.init();
    }

    detectTouch() {
        return 'ontouchstart' in window ||
            navigator.maxTouchPoints > 0 ||
            navigator.msMaxTouchPoints > 0;
    }

    init() {
        if (this.isTouchDevice) {
            document.documentElement.classList.add('touch-device');
        }

        this.setupSwipeGestures();
        this.setupPullToRefresh();
        this.optimizeTouchTargets();
        this.setupViewportFix();
    }

    /**
     * Swipe gestures for task actions
     */
    setupSwipeGestures() {
        if (!this.isTouchDevice) return;

        let startX, startY, currentX;
        const threshold = 100;

        document.addEventListener('touchstart', (e) => {
            const taskItem = e.target.closest('.task-item');
            if (!taskItem) return;

            startX = e.touches[0].clientX;
            startY = e.touches[0].clientY;
            taskItem.dataset.swiping = 'true';
        }, { passive: true });

        document.addEventListener('touchmove', (e) => {
            const taskItem = document.querySelector('.task-item[data-swiping="true"]');
            if (!taskItem) return;

            currentX = e.touches[0].clientX;
            const diffX = currentX - startX;
            const diffY = e.touches[0].clientY - startY;

            // Only allow horizontal swipe
            if (Math.abs(diffX) > Math.abs(diffY)) {
                taskItem.style.transform = `translateX(${Math.max(-100, Math.min(100, diffX))}px)`;
                taskItem.style.transition = 'none';
            }
        }, { passive: true });

        document.addEventListener('touchend', (e) => {
            const taskItem = document.querySelector('.task-item[data-swiping="true"]');
            if (!taskItem) return;

            delete taskItem.dataset.swiping;
            taskItem.style.transition = 'transform 0.3s ease';

            const diffX = currentX - startX;

            if (diffX > threshold) {
                // Swipe right - complete task
                const taskId = taskItem.dataset.taskId;
                if (taskId && typeof toggleTask === 'function') {
                    toggleTask(taskId);
                }
            } else if (diffX < -threshold) {
                // Swipe left - delete task
                const taskId = taskItem.dataset.taskId;
                if (taskId && typeof deleteTask === 'function') {
                    deleteTask(taskId);
                }
            }

            taskItem.style.transform = '';
        });
    }

    /**
     * Pull to refresh
     */
    setupPullToRefresh() {
        if (!this.isTouchDevice) return;

        let startY, currentY;
        const threshold = 150;
        let refreshing = false;

        const mainContent = document.querySelector('.main-content');
        if (!mainContent) return;

        mainContent.addEventListener('touchstart', (e) => {
            if (mainContent.scrollTop === 0) {
                startY = e.touches[0].clientY;
            }
        }, { passive: true });

        mainContent.addEventListener('touchmove', (e) => {
            if (startY === undefined) return;

            currentY = e.touches[0].clientY;
            const pull = currentY - startY;

            if (pull > 0 && pull < threshold * 2 && mainContent.scrollTop === 0) {
                mainContent.style.transform = `translateY(${Math.min(pull / 2, threshold)}px)`;
            }
        }, { passive: true });

        mainContent.addEventListener('touchend', () => {
            if (startY === undefined) return;

            const pull = currentY - startY;
            mainContent.style.transition = 'transform 0.3s ease';
            mainContent.style.transform = '';

            if (pull > threshold && !refreshing) {
                refreshing = true;
                location.reload();
            }

            startY = undefined;
            setTimeout(() => {
                mainContent.style.transition = '';
            }, 300);
        });
    }

    /**
     * Ensure touch targets are large enough
     */
    optimizeTouchTargets() {
        if (!this.isTouchDevice) return;

        // Add touch-friendly class
        document.querySelectorAll('.btn-sm, .btn-icon.btn-sm').forEach(btn => {
            btn.classList.add('touch-target');
        });
    }

    /**
     * Fix mobile viewport height issues
     */
    setupViewportFix() {
        const setVH = () => {
            const vh = window.innerHeight * 0.01;
            document.documentElement.style.setProperty('--vh', `${vh}px`);
        };

        setVH();
        window.addEventListener('resize', setVH);
    }
}

// ============================================================================
// MICRO-INTERACTIONS
// ============================================================================

class MicroInteractions {
    constructor() {
        this.init();
    }

    init() {
        this.setupRippleEffect();
        this.setupHoverEffects();
        this.setupSuccessAnimations();
    }

    /**
     * Add ripple effect to buttons
     */
    setupRippleEffect() {
        document.addEventListener('click', (e) => {
            const btn = e.target.closest('.btn-primary, .btn-secondary');
            if (!btn || btn.classList.contains('ripple')) return;

            const rect = btn.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;

            const ripple = document.createElement('span');
            ripple.className = 'ripple-effect';
            ripple.style.cssText = `
                position: absolute;
                top: ${y}px;
                left: ${x}px;
                width: 0;
                height: 0;
                background: rgba(255, 255, 255, 0.3);
                border-radius: 50%;
                transform: translate(-50%, -50%);
                pointer-events: none;
                animation: rippleExpand 0.6s ease-out forwards;
            `;

            btn.style.position = 'relative';
            btn.style.overflow = 'hidden';
            btn.appendChild(ripple);

            setTimeout(() => ripple.remove(), 600);
        });

        // Add ripple keyframe if not exists
        if (!document.getElementById('ripple-styles')) {
            const style = document.createElement('style');
            style.id = 'ripple-styles';
            style.textContent = `
                @keyframes rippleExpand {
                    to {
                        width: 400px;
                        height: 400px;
                        opacity: 0;
                    }
                }
            `;
            document.head.appendChild(style);
        }
    }

    /**
     * Enhanced hover effects
     */
    setupHoverEffects() {
        // Card tilt effect on hover
        document.querySelectorAll('.project-card, .stat-card').forEach(card => {
            card.addEventListener('mousemove', (e) => {
                const rect = card.getBoundingClientRect();
                const x = e.clientX - rect.left;
                const y = e.clientY - rect.top;
                const centerX = rect.width / 2;
                const centerY = rect.height / 2;

                const rotateX = (y - centerY) / 20;
                const rotateY = (centerX - x) / 20;

                card.style.transform = `perspective(1000px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) translateY(-4px)`;
            });

            card.addEventListener('mouseleave', () => {
                card.style.transform = '';
            });
        });
    }

    /**
     * Success/completion animations
     */
    setupSuccessAnimations() {
        // Listen for task completion
        document.addEventListener('click', (e) => {
            const checkbox = e.target.closest('.task-checkbox');
            if (!checkbox) return;

            // Add burst effect
            if (!checkbox.classList.contains('checked')) {
                this.createBurstEffect(checkbox);
            }
        });
    }

    createBurstEffect(element) {
        const rect = element.getBoundingClientRect();
        const x = rect.left + rect.width / 2;
        const y = rect.top + rect.height / 2;

        for (let i = 0; i < 8; i++) {
            const particle = document.createElement('div');
            particle.style.cssText = `
                position: fixed;
                top: ${y}px;
                left: ${x}px;
                width: 6px;
                height: 6px;
                background: var(--color-success);
                border-radius: 50%;
                pointer-events: none;
                z-index: 9999;
                animation: particleBurst 0.6s ease-out forwards;
                --angle: ${(i * 45)}deg;
            `;
            document.body.appendChild(particle);

            setTimeout(() => particle.remove(), 600);
        }

        // Add burst keyframe if not exists
        if (!document.getElementById('burst-styles')) {
            const style = document.createElement('style');
            style.id = 'burst-styles';
            style.textContent = `
                @keyframes particleBurst {
                    0% {
                        transform: translate(-50%, -50%) rotate(var(--angle)) translateX(0);
                        opacity: 1;
                    }
                    100% {
                        transform: translate(-50%, -50%) rotate(var(--angle)) translateX(40px);
                        opacity: 0;
                    }
                }
            `;
            document.head.appendChild(style);
        }
    }
}

// ============================================================================
// GLOBAL INSTANCES & INITIALIZATION
// ============================================================================

const skeleton = new SkeletonLoader();
const themeManager = new ThemeManager();
const a11y = new AccessibilityManager();
const mobileOptimizer = new MobileOptimizer();
const microInteractions = new MicroInteractions();

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', () => {
    // Add tabindex to interactive elements
    document.querySelectorAll('.task-item, .project-card').forEach(item => {
        item.setAttribute('tabindex', '0');
    });

    // Setup theme toggle if button exists
    const themeToggle = document.querySelector('.theme-toggle');
    if (themeToggle) {
        themeToggle.addEventListener('click', () => {
            const newTheme = themeManager.toggle();
            a11y.announce(`Theme changed to ${newTheme}`);
        });
    }
});

// Export for global use
window.skeleton = skeleton;
window.themeManager = themeManager;
window.a11y = a11y;
window.mobileOptimizer = mobileOptimizer;
window.microInteractions = microInteractions;
