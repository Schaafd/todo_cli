/**
 * Pomodoro/Focus Timer PWA Component
 *
 * Provides a circular progress timer with start/pause/stop controls,
 * session type display, task selector, and stats. Communicates with
 * the /api/pomodoro/* endpoints.
 */

class PomodoroTimer {
    constructor(containerSelector) {
        this.container = document.querySelector(containerSelector);
        if (!this.container) return;

        this.state = 'idle'; // idle | focus | short_break | long_break | paused
        this.remainingSeconds = 0;
        this.totalSeconds = 0;
        this.pollInterval = null;
        this.tickInterval = null;

        this._render();
        this._bindEvents();
        this.refreshStatus();
    }

    // ---- API helpers ----

    async _api(method, path, body) {
        const opts = { method, headers: { 'Content-Type': 'application/json' } };
        if (body) opts.body = JSON.stringify(body);
        const res = await fetch(path, opts);
        if (!res.ok) throw new Error(`API error ${res.status}`);
        return res.json();
    }

    // ---- Actions ----

    async start(taskId, taskText, duration) {
        const body = {};
        if (taskId) body.task_id = taskId;
        if (taskText) body.task_text = taskText;
        if (duration) body.duration = duration;
        const data = await this._api('POST', '/api/pomodoro/start', body);
        this.state = data.status === 'started' ? 'focus' : data.status;
        this.remainingSeconds = data.remaining_seconds || 0;
        this.totalSeconds = (data.session && data.session.planned_minutes * 60) || this.remainingSeconds;
        this._startTick();
        this._updateUI();
    }

    async stop() {
        const data = await this._api('POST', '/api/pomodoro/stop');
        this.state = 'idle';
        this.remainingSeconds = 0;
        this._stopTick();
        this._updateUI();
    }

    async pause() {
        await this._api('POST', '/api/pomodoro/pause');
        this.state = 'paused';
        this._stopTick();
        this._updateUI();
    }

    async resume() {
        await this._api('POST', '/api/pomodoro/resume');
        await this.refreshStatus();
        this._startTick();
    }

    async refreshStatus() {
        try {
            const data = await this._api('GET', '/api/pomodoro/status');
            this.state = data.state || 'idle';
            this.remainingSeconds = data.remaining_seconds || 0;
            if (data.current_session) {
                this.totalSeconds = data.current_session.planned_minutes * 60;
            }
            if (this.state !== 'idle' && this.state !== 'paused') {
                this._startTick();
            } else {
                this._stopTick();
            }
            this._updateUI();
        } catch (e) {
            console.error('Failed to refresh pomodoro status', e);
        }
    }

    async loadStats() {
        try {
            return await this._api('GET', '/api/pomodoro/stats');
        } catch (e) {
            console.error('Failed to load pomodoro stats', e);
            return null;
        }
    }

    // ---- Tick / countdown ----

    _startTick() {
        this._stopTick();
        this.tickInterval = setInterval(() => {
            if (this.remainingSeconds > 0) {
                this.remainingSeconds = Math.max(0, this.remainingSeconds - 1);
                this._updateUI();
            }
            if (this.remainingSeconds <= 0) {
                this._stopTick();
                this.state = 'idle';
                this._updateUI();
                this.refreshStatus();
            }
        }, 1000);
    }

    _stopTick() {
        if (this.tickInterval) {
            clearInterval(this.tickInterval);
            this.tickInterval = null;
        }
    }

    // ---- Rendering ----

    _render() {
        this.container.innerHTML = `
        <div class="pomodoro-widget">
            <div class="pomodoro-circle">
                <svg viewBox="0 0 120 120" class="pomodoro-svg">
                    <circle class="pomodoro-bg" cx="60" cy="60" r="54"
                        stroke="#333" stroke-width="8" fill="none"/>
                    <circle class="pomodoro-progress" cx="60" cy="60" r="54"
                        stroke="#4caf50" stroke-width="8" fill="none"
                        stroke-dasharray="339.292" stroke-dashoffset="0"
                        stroke-linecap="round"
                        transform="rotate(-90 60 60)"/>
                </svg>
                <div class="pomodoro-time">00:00</div>
                <div class="pomodoro-label">Idle</div>
            </div>
            <div class="pomodoro-controls">
                <button class="pomo-btn pomo-start" title="Start">&#9654;</button>
                <button class="pomo-btn pomo-pause" title="Pause" style="display:none">&#10074;&#10074;</button>
                <button class="pomo-btn pomo-resume" title="Resume" style="display:none">&#9654;</button>
                <button class="pomo-btn pomo-stop" title="Stop" style="display:none">&#9632;</button>
            </div>
            <div class="pomodoro-stats-summary"></div>
        </div>
        <style>
            .pomodoro-widget { text-align: center; padding: 1rem; }
            .pomodoro-circle { position: relative; width: 160px; height: 160px; margin: 0 auto; }
            .pomodoro-svg { width: 100%; height: 100%; }
            .pomodoro-time {
                position: absolute; top: 50%; left: 50%;
                transform: translate(-50%, -60%);
                font-size: 1.6rem; font-weight: bold; color: #eee;
            }
            .pomodoro-label {
                position: absolute; top: 50%; left: 50%;
                transform: translate(-50%, 40%);
                font-size: 0.85rem; color: #aaa; text-transform: uppercase;
            }
            .pomodoro-controls { margin-top: 1rem; display: flex; gap: 0.5rem; justify-content: center; }
            .pomo-btn {
                width: 40px; height: 40px; border-radius: 50%; border: none;
                background: #333; color: #eee; font-size: 1rem; cursor: pointer;
            }
            .pomo-btn:hover { background: #555; }
            .pomodoro-stats-summary { margin-top: 0.75rem; font-size: 0.8rem; color: #999; }
        </style>`;

        // Cache DOM refs
        this._progress = this.container.querySelector('.pomodoro-progress');
        this._timeEl = this.container.querySelector('.pomodoro-time');
        this._labelEl = this.container.querySelector('.pomodoro-label');
        this._btnStart = this.container.querySelector('.pomo-start');
        this._btnPause = this.container.querySelector('.pomo-pause');
        this._btnResume = this.container.querySelector('.pomo-resume');
        this._btnStop = this.container.querySelector('.pomo-stop');
        this._statsEl = this.container.querySelector('.pomodoro-stats-summary');
    }

    _bindEvents() {
        this._btnStart.addEventListener('click', () => this.start());
        this._btnPause.addEventListener('click', () => this.pause());
        this._btnResume.addEventListener('click', () => this.resume());
        this._btnStop.addEventListener('click', () => this.stop());
    }

    _updateUI() {
        // Time display
        const mins = Math.floor(this.remainingSeconds / 60);
        const secs = Math.floor(this.remainingSeconds % 60);
        this._timeEl.textContent = `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;

        // Progress ring
        const circumference = 339.292; // 2 * PI * 54
        const fraction = this.totalSeconds > 0 ? this.remainingSeconds / this.totalSeconds : 0;
        this._progress.setAttribute('stroke-dashoffset', circumference * (1 - fraction));

        // Colors by state
        const colors = { focus: '#4caf50', short_break: '#2196f3', long_break: '#9c27b0', paused: '#ff9800', idle: '#666' };
        this._progress.setAttribute('stroke', colors[this.state] || '#666');

        // Label
        const labels = { focus: 'Focus', short_break: 'Short Break', long_break: 'Long Break', paused: 'Paused', idle: 'Idle' };
        this._labelEl.textContent = labels[this.state] || 'Idle';

        // Button visibility
        const isActive = ['focus', 'short_break', 'long_break'].includes(this.state);
        this._btnStart.style.display = this.state === 'idle' ? '' : 'none';
        this._btnPause.style.display = isActive ? '' : 'none';
        this._btnResume.style.display = this.state === 'paused' ? '' : 'none';
        this._btnStop.style.display = (isActive || this.state === 'paused') ? '' : 'none';

        // Stats summary (async, fire and forget)
        this._refreshStatsSummary();
    }

    async _refreshStatsSummary() {
        const stats = await this.loadStats();
        if (stats && this._statsEl) {
            this._statsEl.textContent =
                `Today: ${stats.sessions_today} sessions / ${Math.round(stats.focus_minutes_today)} min focus | Streak: ${stats.current_streak}`;
        }
    }
}

// Auto-init if container exists on page
document.addEventListener('DOMContentLoaded', () => {
    if (document.querySelector('#pomodoro-container')) {
        window.pomodoroTimer = new PomodoroTimer('#pomodoro-container');
    }
});
