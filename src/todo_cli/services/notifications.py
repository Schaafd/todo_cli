"""Notification system for Todo CLI.

Provides desktop notifications, email alerts, and smart scheduling for task reminders.
Supports macOS, Windows, and Linux with configurable notification preferences.
"""

import os
import sys
import json
import smtplib
import subprocess
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass, field
from pathlib import Path
from enum import Enum

from ..domain import Todo
from ..config import get_config


class NotificationType(Enum):
    """Types of notifications"""
    DUE_SOON = "due_soon"
    OVERDUE = "overdue"
    RECURRING_GENERATED = "recurring_generated"
    MILESTONE = "milestone"
    DAILY_SUMMARY = "daily_summary"
    WEEKLY_SUMMARY = "weekly_summary"


class NotificationPriority(Enum):
    """Notification priority levels"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class NotificationPreferences:
    """User preferences for notifications"""
    enabled: bool = True
    
    # Desktop notifications
    desktop_enabled: bool = True
    desktop_sound: bool = True
    
    # Email notifications
    email_enabled: bool = False
    email_address: Optional[str] = None
    smtp_server: Optional[str] = None
    smtp_port: int = 587
    smtp_username: Optional[str] = None
    smtp_password: Optional[str] = None  # Should be encrypted in real implementation
    smtp_use_tls: bool = True
    
    # Notification timing
    due_soon_hours: int = 24  # Hours before due date to notify
    overdue_reminder_hours: int = 24  # Hours between overdue reminders
    
    # Notification types enabled
    notify_due_soon: bool = True
    notify_overdue: bool = True
    notify_recurring: bool = True
    notify_milestones: bool = True
    notify_daily_summary: bool = False
    notify_weekly_summary: bool = False
    
    # Quiet hours (24-hour format)
    quiet_start: int = 22  # 10 PM
    quiet_end: int = 8     # 8 AM
    quiet_enabled: bool = True
    
    # Days to send notifications (0=Monday, 6=Sunday)
    notification_days: List[int] = field(default_factory=lambda: list(range(7)))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert preferences to dictionary"""
        return {
            'enabled': self.enabled,
            'desktop_enabled': self.desktop_enabled,
            'desktop_sound': self.desktop_sound,
            'email_enabled': self.email_enabled,
            'email_address': self.email_address,
            'smtp_server': self.smtp_server,
            'smtp_port': self.smtp_port,
            'smtp_username': self.smtp_username,
            'smtp_password': self.smtp_password,
            'smtp_use_tls': self.smtp_use_tls,
            'due_soon_hours': self.due_soon_hours,
            'overdue_reminder_hours': self.overdue_reminder_hours,
            'notify_due_soon': self.notify_due_soon,
            'notify_overdue': self.notify_overdue,
            'notify_recurring': self.notify_recurring,
            'notify_milestones': self.notify_milestones,
            'notify_daily_summary': self.notify_daily_summary,
            'notify_weekly_summary': self.notify_weekly_summary,
            'quiet_start': self.quiet_start,
            'quiet_end': self.quiet_end,
            'quiet_enabled': self.quiet_enabled,
            'notification_days': self.notification_days
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'NotificationPreferences':
        """Create preferences from dictionary"""
        return cls(**data)


@dataclass
class Notification:
    """A notification instance"""
    id: str
    type: NotificationType
    priority: NotificationPriority
    title: str
    message: str
    todo_id: Optional[int] = None
    project: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    scheduled_for: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    delivery_method: str = "desktop"  # desktop, email, both
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert notification to dictionary"""
        return {
            'id': self.id,
            'type': self.type.value,
            'priority': self.priority.value,
            'title': self.title,
            'message': self.message,
            'todo_id': self.todo_id,
            'project': self.project,
            'created_at': self.created_at.isoformat(),
            'scheduled_for': self.scheduled_for.isoformat() if self.scheduled_for else None,
            'sent_at': self.sent_at.isoformat() if self.sent_at else None,
            'delivery_method': self.delivery_method
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Notification':
        """Create notification from dictionary"""
        return cls(
            id=data['id'],
            type=NotificationType(data['type']),
            priority=NotificationPriority(data['priority']),
            title=data['title'],
            message=data['message'],
            todo_id=data.get('todo_id'),
            project=data.get('project'),
            created_at=datetime.fromisoformat(data['created_at']),
            scheduled_for=datetime.fromisoformat(data['scheduled_for']) if data.get('scheduled_for') else None,
            sent_at=datetime.fromisoformat(data['sent_at']) if data.get('sent_at') else None,
            delivery_method=data.get('delivery_method', 'desktop')
        )


class NotificationDelivery(ABC):
    """Abstract base class for notification delivery methods"""
    
    @abstractmethod
    def send(self, notification: Notification) -> bool:
        """Send a notification. Returns True if successful."""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if this delivery method is available on the current system."""
        pass


class DesktopNotificationDelivery(NotificationDelivery):
    """Desktop notification delivery using native OS notifications"""
    
    def __init__(self):
        self.platform = sys.platform.lower()
    
    def is_available(self) -> bool:
        """Check if desktop notifications are available"""
        if self.platform == "darwin":  # macOS
            return True
        elif self.platform.startswith("win"):  # Windows
            try:
                import win10toast
                return True
            except ImportError:
                return False
        else:  # Linux and others
            return subprocess.run(["which", "notify-send"], capture_output=True).returncode == 0
    
    def send(self, notification: Notification) -> bool:
        """Send desktop notification"""
        try:
            if self.platform == "darwin":  # macOS
                return self._send_macos(notification)
            elif self.platform.startswith("win"):  # Windows
                return self._send_windows(notification)
            else:  # Linux
                return self._send_linux(notification)
        except Exception as e:
            print(f"Desktop notification failed: {e}")
            return False
    
    def _send_macos(self, notification: Notification) -> bool:
        """Send macOS notification using osascript"""
        try:
            # Use subprocess arguments directly to avoid shell escaping issues
            title = notification.title or ""
            message = notification.message or ""
            cmd = [
                "osascript",
                "-e",
                "on run argv",
                "-e",
                "display notification (item 2 of argv) with title (item 1 of argv) sound name (item 3 of argv)",
                "-e",
                "end run",
                str(title),
                str(message),
                "Glass",
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                return True
            else:
                # For debugging - will be removed later
                print(f"osascript returned {result.returncode}")
                if result.stderr:
                    print(f"stderr: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            print("macOS notification timed out")
            return False
        except Exception as e:
            print(f"macOS notification error: {e}")
            return False
    
    def _send_windows(self, notification: Notification) -> bool:
        """Send Windows notification using win10toast"""
        try:
            import win10toast
            toaster = win10toast.ToastNotifier()
            toaster.show_toast(
                title=notification.title,
                msg=notification.message,
                duration=10,
                threaded=True
            )
            return True
        except ImportError:
            return False
    
    def _send_linux(self, notification: Notification) -> bool:
        """Send Linux notification using notify-send"""
        try:
            urgency_map = {
                NotificationPriority.LOW: "low",
                NotificationPriority.NORMAL: "normal", 
                NotificationPriority.HIGH: "normal",
                NotificationPriority.CRITICAL: "critical"
            }
            urgency = urgency_map.get(notification.priority, "normal")
            
            subprocess.run([
                "notify-send",
                "--urgency", urgency,
                "--app-name", "Todo CLI",
                notification.title,
                notification.message
            ], check=True)
            return True
        except subprocess.CalledProcessError:
            return False


class EmailNotificationDelivery(NotificationDelivery):
    """Email notification delivery using SMTP"""
    
    def __init__(self, preferences: NotificationPreferences):
        self.preferences = preferences
    
    def is_available(self) -> bool:
        """Check if email notifications are configured"""
        return (
            self.preferences.email_enabled and
            self.preferences.email_address and
            self.preferences.smtp_server and
            self.preferences.smtp_username and
            self.preferences.smtp_password
        )
    
    def send(self, notification: Notification) -> bool:
        """Send email notification"""
        if not self.is_available():
            return False
        
        try:
            # Import email modules only when needed
            from email.mime.text import MimeText
            from email.mime.multipart import MimeMultipart
            
            msg = MimeMultipart()
            msg['From'] = self.preferences.smtp_username
            msg['To'] = self.preferences.email_address
            msg['Subject'] = f"[Todo CLI] {notification.title}"
            
            # Create email body
            body = self._create_email_body(notification)
            msg.attach(MimeText(body, 'html'))
            
            # Send email
            server = smtplib.SMTP(self.preferences.smtp_server, self.preferences.smtp_port)
            
            if self.preferences.smtp_use_tls:
                server.starttls()
            
            server.login(self.preferences.smtp_username, self.preferences.smtp_password)
            server.send_message(msg)
            server.quit()
            
            return True
        
        except Exception as e:
            print(f"Email notification failed: {e}")
            return False
    
    def _create_email_body(self, notification: Notification) -> str:
        """Create HTML email body"""
        return f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background: #f8f9fa; padding: 20px; border-radius: 8px;">
                <h2 style="color: #333; margin-top: 0;">{notification.title}</h2>
                <p style="color: #555; font-size: 16px; line-height: 1.6;">{notification.message}</p>
                
                {f'<p style="color: #666;"><strong>Task ID:</strong> {notification.todo_id}</p>' if notification.todo_id else ''}
                {f'<p style="color: #666;"><strong>Project:</strong> {notification.project}</p>' if notification.project else ''}
                
                <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
                <p style="color: #888; font-size: 12px;">
                    Sent by Todo CLI at {notification.created_at.strftime('%Y-%m-%d %H:%M')}
                </p>
            </div>
        </body>
        </html>
        """


class NotificationScheduler:
    """Manages scheduling and delivery of notifications"""
    
    def __init__(self, preferences: NotificationPreferences):
        self.preferences = preferences
        self.desktop_delivery = DesktopNotificationDelivery()
        self.email_delivery = EmailNotificationDelivery(preferences)
        
        # Get notifications storage path
        config = get_config()
        self.notifications_file = Path(config.data_dir) / "notifications.json"
        self.history = self._load_notification_history()
    
    def _load_notification_history(self) -> List[Notification]:
        """Load notification history from file"""
        if not self.notifications_file.exists():
            return []
        
        try:
            with open(self.notifications_file, 'r') as f:
                data = json.load(f)
                return [Notification.from_dict(item) for item in data]
        except (json.JSONDecodeError, KeyError):
            return []
    
    def _save_notification_history(self):
        """Save notification history to file"""
        self.notifications_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Keep only last 1000 notifications
        recent_history = self.history[-1000:] if len(self.history) > 1000 else self.history
        
        with open(self.notifications_file, 'w') as f:
            json.dump([n.to_dict() for n in recent_history], f, indent=2)
    
    def should_send_notification(self, notification: Notification) -> bool:
        """Check if a notification should be sent based on preferences"""
        if not self.preferences.enabled:
            return False
        
        # Check notification type preferences
        type_checks = {
            NotificationType.DUE_SOON: self.preferences.notify_due_soon,
            NotificationType.OVERDUE: self.preferences.notify_overdue,
            NotificationType.RECURRING_GENERATED: self.preferences.notify_recurring,
            NotificationType.MILESTONE: self.preferences.notify_milestones,
            NotificationType.DAILY_SUMMARY: self.preferences.notify_daily_summary,
            NotificationType.WEEKLY_SUMMARY: self.preferences.notify_weekly_summary,
        }
        
        if not type_checks.get(notification.type, True):
            return False
        
        # Check quiet hours
        if self.preferences.quiet_enabled:
            current_hour = datetime.now().hour
            if self.preferences.quiet_start > self.preferences.quiet_end:
                # Quiet hours span midnight
                if current_hour >= self.preferences.quiet_start or current_hour <= self.preferences.quiet_end:
                    return False
            else:
                # Normal quiet hours
                if self.preferences.quiet_start <= current_hour <= self.preferences.quiet_end:
                    return False
        
        # Check notification days
        current_weekday = datetime.now().weekday()
        if current_weekday not in self.preferences.notification_days:
            return False
        
        return True
    
    def send_notification(self, notification: Notification) -> bool:
        """Send a notification using configured delivery methods"""
        if not self.should_send_notification(notification):
            return False
        
        success = False
        
        # Send desktop notification
        if self.preferences.desktop_enabled and self.desktop_delivery.is_available():
            if notification.delivery_method in ["desktop", "both"]:
                if self.desktop_delivery.send(notification):
                    success = True
        
        # Send email notification
        if self.preferences.email_enabled and self.email_delivery.is_available():
            if notification.delivery_method in ["email", "both"]:
                if self.email_delivery.send(notification):
                    success = True
        
        if success:
            notification.sent_at = datetime.now()
            self.history.append(notification)
            self._save_notification_history()
        
        return success
    
    def create_due_soon_notifications(self, todos: List[Todo]) -> List[Notification]:
        """Create notifications for tasks due soon"""
        notifications = []
        cutoff_time = datetime.now() + timedelta(hours=self.preferences.due_soon_hours)
        
        for todo in todos:
            if (todo.due_date and 
                not todo.completed and 
                todo.due_date <= cutoff_time and
                todo.due_date > datetime.now()):
                
                # Check if we've already sent a due soon notification recently
                recent_notifications = [
                    n for n in self.history 
                    if (n.todo_id == todo.id and 
                        n.type == NotificationType.DUE_SOON and
                        n.sent_at and
                        n.sent_at > datetime.now() - timedelta(hours=12))
                ]
                
                if not recent_notifications:
                    time_until_due = todo.due_date - datetime.now()
                    hours_until = int(time_until_due.total_seconds() / 3600)
                    
                    notification = Notification(
                        id=f"due_soon_{todo.id}_{datetime.now().isoformat()}",
                        type=NotificationType.DUE_SOON,
                        priority=NotificationPriority.HIGH if hours_until < 6 else NotificationPriority.NORMAL,
                        title=f"Task Due {self._format_time_until(time_until_due)}",
                        message=f"'{todo.text}' is due {todo.due_date.strftime('%Y-%m-%d at %H:%M')}",
                        todo_id=todo.id,
                        project=todo.project
                    )
                    notifications.append(notification)
        
        return notifications
    
    def create_overdue_notifications(self, todos: List[Todo]) -> List[Notification]:
        """Create notifications for overdue tasks"""
        notifications = []
        
        for todo in todos:
            if todo.is_overdue():
                # Check if we've sent an overdue notification recently
                recent_notifications = [
                    n for n in self.history 
                    if (n.todo_id == todo.id and 
                        n.type == NotificationType.OVERDUE and
                        n.sent_at and
                        n.sent_at > datetime.now() - timedelta(hours=self.preferences.overdue_reminder_hours))
                ]
                
                if not recent_notifications:
                    overdue_time = datetime.now() - todo.due_date
                    
                    notification = Notification(
                        id=f"overdue_{todo.id}_{datetime.now().isoformat()}",
                        type=NotificationType.OVERDUE,
                        priority=NotificationPriority.CRITICAL,
                        title=f"Task Overdue by {self._format_time_until(overdue_time)}",
                        message=f"'{todo.text}' was due {todo.due_date.strftime('%Y-%m-%d at %H:%M')}",
                        todo_id=todo.id,
                        project=todo.project
                    )
                    notifications.append(notification)
        
        return notifications
    
    def create_recurring_notification(self, count: int, project: str = None) -> Notification:
        """Create notification for generated recurring tasks"""
        return Notification(
            id=f"recurring_{datetime.now().isoformat()}",
            type=NotificationType.RECURRING_GENERATED,
            priority=NotificationPriority.NORMAL,
            title=f"Generated {count} Recurring Tasks",
            message=f"Generated {count} new tasks from recurring templates" + (f" in {project}" if project else ""),
            project=project
        )
    
    def create_daily_summary(self, todos: List[Todo]) -> Notification:
        """Create daily summary notification"""
        active_count = sum(1 for t in todos if t.is_active())
        due_today_count = sum(1 for t in todos if t.due_date and t.due_date.date() == datetime.now().date() and not t.completed)
        overdue_count = sum(1 for t in todos if t.is_overdue())
        
        message = f"You have {active_count} active tasks"
        if due_today_count > 0:
            message += f", {due_today_count} due today"
        if overdue_count > 0:
            message += f", {overdue_count} overdue"
        
        return Notification(
            id=f"daily_summary_{datetime.now().date().isoformat()}",
            type=NotificationType.DAILY_SUMMARY,
            priority=NotificationPriority.LOW,
            title="Daily Task Summary",
            message=message
        )
    
    def _format_time_until(self, time_delta: timedelta) -> str:
        """Format time delta as human readable string"""
        total_seconds = int(time_delta.total_seconds())
        
        if total_seconds < 0:
            total_seconds = abs(total_seconds)
            prefix = ""
        else:
            prefix = "in "
        
        days = total_seconds // 86400
        hours = (total_seconds % 86400) // 3600
        minutes = (total_seconds % 3600) // 60
        
        if days > 0:
            return f"{prefix}{days}d {hours}h"
        elif hours > 0:
            return f"{prefix}{hours}h {minutes}m"
        else:
            return f"{prefix}{minutes}m"
    
    def get_notification_history(self, limit: int = 50, notification_type: Optional[NotificationType] = None) -> List[Notification]:
        """Get notification history with optional filtering"""
        filtered_history = self.history
        
        if notification_type:
            filtered_history = [n for n in filtered_history if n.type == notification_type]
        
        # Sort by created_at descending and limit
        return sorted(filtered_history, key=lambda n: n.created_at, reverse=True)[:limit]
    
    def test_notification(self, title: str = "Test Notification", message: str = "This is a test notification from Todo CLI") -> bool:
        """Send a test notification"""
        test_notification = Notification(
            id=f"test_{datetime.now().isoformat()}",
            type=NotificationType.MILESTONE,  # Use milestone as neutral type
            priority=NotificationPriority.NORMAL,
            title=title,
            message=message
        )
        
        return self.send_notification(test_notification)


class NotificationManager:
    """Main interface for managing notifications"""
    
    def __init__(self):
        self.preferences = self._load_preferences()
        self.scheduler = NotificationScheduler(self.preferences)
    
    def _load_preferences(self) -> NotificationPreferences:
        """Load notification preferences from config"""
        config = get_config()
        prefs_file = Path(config.data_dir) / "notification_preferences.json"
        
        if prefs_file.exists():
            try:
                with open(prefs_file, 'r') as f:
                    data = json.load(f)
                    return NotificationPreferences.from_dict(data)
            except (json.JSONDecodeError, KeyError):
                pass
        
        # Return default preferences
        return NotificationPreferences()
    
    def save_preferences(self):
        """Save notification preferences to config"""
        config = get_config()
        prefs_file = Path(config.data_dir) / "notification_preferences.json"
        prefs_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(prefs_file, 'w') as f:
            json.dump(self.preferences.to_dict(), f, indent=2)
        
        # Update scheduler with new preferences
        self.scheduler = NotificationScheduler(self.preferences)
    
    def check_and_send_notifications(self, todos: List[Todo]) -> int:
        """Check todos and send appropriate notifications. Returns count of notifications sent."""
        if not self.preferences.enabled:
            return 0
        
        notifications_sent = 0
        
        # Create due soon notifications
        due_soon_notifications = self.scheduler.create_due_soon_notifications(todos)
        for notification in due_soon_notifications:
            if self.scheduler.send_notification(notification):
                notifications_sent += 1
        
        # Create overdue notifications
        overdue_notifications = self.scheduler.create_overdue_notifications(todos)
        for notification in overdue_notifications:
            if self.scheduler.send_notification(notification):
                notifications_sent += 1
        
        return notifications_sent
    
    def send_recurring_notification(self, count: int, project: str = None) -> bool:
        """Send notification about generated recurring tasks"""
        notification = self.scheduler.create_recurring_notification(count, project)
        return self.scheduler.send_notification(notification)
    
    def send_daily_summary(self, todos: List[Todo]) -> bool:
        """Send daily summary notification"""
        notification = self.scheduler.create_daily_summary(todos)
        return self.scheduler.send_notification(notification)
    
    def test_notifications(self) -> Dict[str, bool]:
        """Test all available notification methods"""
        results = {}
        
        # Test desktop notifications
        if self.preferences.desktop_enabled:
            results['desktop'] = self.scheduler.test_notification("Desktop Test", "Desktop notifications are working!")
        
        # Test email notifications
        if self.preferences.email_enabled:
            results['email'] = self.scheduler.test_notification("Email Test", "Email notifications are working!")
        
        return results
    
    def get_notification_history(self, **kwargs) -> List[Notification]:
        """Get notification history"""
        return self.scheduler.get_notification_history(**kwargs)
    
    def is_available(self) -> Dict[str, bool]:
        """Check availability of notification methods"""
        return {
            'desktop': self.scheduler.desktop_delivery.is_available(),
            'email': self.scheduler.email_delivery.is_available(),
        }