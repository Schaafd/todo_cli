"""Notification CLI command group."""

import click
from rich.console import Console

from ..config import get_config
from ..storage import Storage
from ..theme import get_themed_console


def get_console() -> Console:
    """Get a themed console that reflects current configuration."""
    return get_themed_console()


def get_storage() -> Storage:
    """Get initialized storage instance."""
    return Storage(get_config())


@click.group()
def notify() -> None:
    """Manage notifications and notification settings."""


@notify.command()
@click.option("--test", is_flag=True, help="Test notification delivery")
def status(test: bool) -> None:
    """Show notification system status and availability."""
    from ..services import NotificationManager

    notification_manager = NotificationManager()

    get_console().print("[header]🔔 Notification System Status[/header]\n")

    prefs = notification_manager.preferences
    enabled_icon = "✅" if prefs.enabled else "❌"
    get_console().print(f"{enabled_icon} [bold]Notifications:[/bold] {'Enabled' if prefs.enabled else 'Disabled'}")

    availability = notification_manager.is_available()

    desktop_icon = "✅" if availability["desktop"] else "❌"
    desktop_enabled = "✅" if prefs.desktop_enabled else "❌"
    get_console().print(
        f"{desktop_icon} [bold]Desktop:[/bold] {'Available' if availability['desktop'] else 'Not Available'} | "
        f"{desktop_enabled} {'Enabled' if prefs.desktop_enabled else 'Disabled'}"
    )

    email_icon = "✅" if availability["email"] else "❌"
    email_enabled = "✅" if prefs.email_enabled else "❌"
    get_console().print(
        f"{email_icon} [bold]Email:[/bold] {'Available' if availability['email'] else 'Not Available'} | "
        f"{email_enabled} {'Enabled' if prefs.email_enabled else 'Disabled'}"
    )

    get_console().print("\n[subheader]Notification Types:[/subheader]")
    type_status = [
        ("Due Soon", prefs.notify_due_soon, f"{prefs.due_soon_hours}h before"),
        ("Overdue", prefs.notify_overdue, f"Every {prefs.overdue_reminder_hours}h"),
        ("Recurring Tasks", prefs.notify_recurring, "When generated"),
        ("Daily Summary", prefs.notify_daily_summary, "Once per day"),
        ("Weekly Summary", prefs.notify_weekly_summary, "Once per week"),
    ]

    for name, enabled, timing in type_status:
        icon = "✅" if enabled else "❌"
        get_console().print(f"  {icon} {name}: {timing if enabled else 'Disabled'}")

    if prefs.quiet_enabled:
        get_console().print(f"\n[muted]😴 Quiet hours: {prefs.quiet_start:02d}:00 - {prefs.quiet_end:02d}:00[/muted]")

    if test:
        get_console().print("\n[primary]📨 Testing notifications...[/primary]")
        test_results = notification_manager.test_notifications()

        for method, success in test_results.items():
            icon = "✅" if success else "❌"
            status_text = "Success" if success else "Failed"
            get_console().print(f"  {icon} {method.title()}: {status_text}")


@notify.command()
@click.option("--enabled/--disabled", default=None, help="Enable or disable notifications")
@click.option("--desktop/--no-desktop", default=None, help="Enable or disable desktop notifications")
@click.option("--email/--no-email", default=None, help="Enable or disable email notifications")
@click.option("--due-soon-hours", type=int, help="Hours before due date to notify")
@click.option("--overdue-hours", type=int, help="Hours between overdue reminders")
@click.option("--quiet-start", type=int, help="Quiet hours start (24-hour format)")
@click.option("--quiet-end", type=int, help="Quiet hours end (24-hour format)")
@click.option("--quiet/--no-quiet", default=None, help="Enable or disable quiet hours")
@click.option("--email-address", help="Email address for notifications")
@click.option("--smtp-server", help="SMTP server hostname")
@click.option("--smtp-port", type=int, help="SMTP server port")
@click.option("--smtp-username", help="SMTP username")
@click.option("--smtp-password", help="SMTP password (use with caution)")
def config(
    enabled: bool | None,
    desktop: bool | None,
    email: bool | None,
    due_soon_hours: int | None,
    overdue_hours: int | None,
    quiet_start: int | None,
    quiet_end: int | None,
    quiet: bool | None,
    email_address: str | None,
    smtp_server: str | None,
    smtp_port: int | None,
    smtp_username: str | None,
    smtp_password: str | None,
) -> None:
    """Configure notification preferences."""
    from ..services import NotificationManager

    notification_manager = NotificationManager()
    prefs = notification_manager.preferences
    changes_made = False

    if enabled is not None:
        prefs.enabled = enabled
        changes_made = True

    if desktop is not None:
        prefs.desktop_enabled = desktop
        changes_made = True

    if email is not None:
        prefs.email_enabled = email
        changes_made = True

    if due_soon_hours is not None:
        prefs.due_soon_hours = due_soon_hours
        changes_made = True

    if overdue_hours is not None:
        prefs.overdue_reminder_hours = overdue_hours
        changes_made = True

    if quiet_start is not None:
        prefs.quiet_start = quiet_start
        changes_made = True

    if quiet_end is not None:
        prefs.quiet_end = quiet_end
        changes_made = True

    if quiet is not None:
        prefs.quiet_enabled = quiet
        changes_made = True

    if email_address:
        prefs.email_address = email_address
        changes_made = True

    if smtp_server:
        prefs.smtp_server = smtp_server
        changes_made = True

    if smtp_port is not None:
        prefs.smtp_port = smtp_port
        changes_made = True

    if smtp_username:
        prefs.smtp_username = smtp_username
        changes_made = True

    if smtp_password:
        get_console().print(
            "[warning]⚠️  Warning: Passwords are stored in plain text. Consider using app-specific passwords.[/warning]"
        )
        prefs.smtp_password = smtp_password
        changes_made = True

    if changes_made:
        notification_manager.save_preferences()
        get_console().print("[success]✅ Notification preferences updated[/success]")
    else:
        get_console().print("[yellow]No changes specified. Use --help to see available options.[/yellow]")


@notify.command()
@click.option("--limit", "-l", type=int, default=20, help="Number of notifications to show")
@click.option(
    "--type",
    "notification_type",
    type=click.Choice(["due_soon", "overdue", "recurring_generated", "daily_summary"]),
    help="Filter by notification type",
)
def history(limit: int, notification_type: str | None) -> None:
    """Show notification history."""
    from ..services import NotificationManager, NotificationType

    notification_manager = NotificationManager()

    filter_type = NotificationType(notification_type) if notification_type else None
    notifications = notification_manager.get_notification_history(
        limit=limit,
        notification_type=filter_type,
    )

    if not notifications:
        get_console().print("[yellow]No notifications found in history.[/yellow]")
        return

    get_console().print(f"[header]📜 Notification History ({len(notifications)} recent)[/header]\n")

    for notification in notifications:
        time_str = notification.created_at.strftime("%m-%d %H:%M")
        type_icons = {
            NotificationType.DUE_SOON: "⏰",
            NotificationType.OVERDUE: "🔥",
            NotificationType.RECURRING_GENERATED: "🔄",
            NotificationType.DAILY_SUMMARY: "📈",
            NotificationType.WEEKLY_SUMMARY: "📈",
            NotificationType.MILESTONE: "🎆",
        }
        icon = type_icons.get(notification.type, "🔔")
        status_text = "✅" if notification.sent_at else "⏸️"

        get_console().print(f"{icon} {status_text} [{time_str}] [bold]{notification.title}[/bold]")
        get_console().print(f"    [muted]{notification.message}[/muted]")

        if notification.todo_id:
            get_console().print(f"    [muted]Task ID: {notification.todo_id}[/muted]")

        get_console().print()


@notify.command()
@click.option("--title", "-t", default="Test Notification", help="Test notification title")
@click.option("--message", "-m", default="This is a test from Todo CLI", help="Test notification message")
def test(title: str, message: str) -> None:
    """Send a test notification."""
    from ..services import NotificationManager

    notification_manager = NotificationManager()

    if not notification_manager.preferences.enabled:
        get_console().print("[error]❌ Notifications are disabled. Enable with: todo notify config --enabled[/error]")
        return

    get_console().print("[primary]📨 Sending test notification...[/primary]")

    results = {}
    if notification_manager.preferences.desktop_enabled:
        results["desktop"] = notification_manager.scheduler.test_notification(title, message)

    if notification_manager.preferences.email_enabled:
        results["email"] = notification_manager.scheduler.email_delivery.is_available()

    success_count = 0
    for method, success in results.items():
        icon = "✅" if success else "❌"
        status_text = "Success" if success else "Failed"
        get_console().print(f"  {icon} {method.title()}: {status_text}")
        if success:
            success_count += 1

    if success_count > 0:
        get_console().print(f"\n[success]✅ Sent test notification via {success_count} method(s)[/success]")
    else:
        get_console().print("\n[error]❌ No test notifications could be sent[/error]")
        get_console().print("[muted]Check your notification settings with: todo notify status[/muted]")


@notify.command()
def check() -> None:
    """Check for due and overdue tasks and send notifications."""
    from ..services import NotificationManager

    storage = get_storage()
    config_data = get_config()
    notification_manager = NotificationManager()

    if not notification_manager.preferences.enabled:
        get_console().print("[yellow]Notifications are disabled. Enable with: todo notify config --enabled[/yellow]")
        return

    all_todos = []
    projects = storage.list_projects()
    if not projects:
        projects = [config_data.default_project]

    for project_name in projects:
        _, todos = storage.load_project(project_name)
        if todos:
            all_todos.extend(todos)

    get_console().print("[primary]🔍 Checking for due and overdue tasks...[/primary]")

    notifications_sent = notification_manager.check_and_send_notifications(all_todos)

    if notifications_sent > 0:
        get_console().print(f"[success]✅ Sent {notifications_sent} notification(s)[/success]")
    else:
        get_console().print("[muted]😴 No notifications needed at this time[/muted]")
