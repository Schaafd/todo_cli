"""Slack integration plugin for Todo CLI.

Posts task updates to Slack channels, creates tasks from Slack messages,
and provides daily summaries.
"""

import httpx
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional

from ..plugins import BasePlugin, PluginAPI, PluginInfo, PluginType

logger = logging.getLogger(__name__)

SLACK_API_BASE = "https://slack.com/api"


class SlackClient:
    """Simple Slack Web API client using httpx."""

    def __init__(self, bot_token: str):
        self.bot_token = bot_token
        self.headers = {
            "Authorization": f"Bearer {bot_token}",
            "Content-Type": "application/json; charset=utf-8",
        }

    def post_message(
        self, channel: str, text: str, blocks: Optional[List[Dict]] = None
    ) -> Dict:
        """Post a message to a Slack channel."""
        with httpx.Client(timeout=10.0) as client:
            payload: Dict[str, Any] = {"channel": channel, "text": text}
            if blocks:
                payload["blocks"] = blocks
            response = client.post(
                f"{SLACK_API_BASE}/chat.postMessage",
                headers=self.headers,
                json=payload,
            )
            return response.json()

    def test_auth(self) -> Dict:
        """Test the bot token."""
        with httpx.Client(timeout=10.0) as client:
            response = client.post(
                f"{SLACK_API_BASE}/auth.test",
                headers=self.headers,
            )
            return response.json()

    def get_channels(self) -> List[Dict]:
        """List channels the bot is in."""
        with httpx.Client(timeout=10.0) as client:
            response = client.get(
                f"{SLACK_API_BASE}/conversations.list",
                headers=self.headers,
                params={"types": "public_channel,private_channel", "limit": 100},
            )
            data = response.json()
            return data.get("channels", [])


class SlackPlugin(BasePlugin):
    """Slack integration for Todo CLI."""

    def __init__(self, api: PluginAPI):
        super().__init__(api)
        self.info = PluginInfo(
            id="slack-integration",
            name="Slack Integration",
            version="1.0.0",
            author="Todo CLI",
            description="Post task updates to Slack and create tasks from Slack messages",
            plugin_type=PluginType.INTEGRATION,
            config_schema={
                "bot_token": {
                    "type": "string",
                    "required": True,
                    "description": "Slack Bot Token",
                },
                "channel": {
                    "type": "string",
                    "required": True,
                    "description": "Default channel ID",
                },
                "notify_on_complete": {"type": "boolean", "default": True},
                "notify_on_create": {"type": "boolean", "default": False},
                "daily_summary": {"type": "boolean", "default": True},
                "daily_summary_time": {"type": "string", "default": "09:00"},
            },
        )
        self.client: Optional[SlackClient] = None

    def initialize(self) -> bool:
        """Initialize the Slack plugin."""
        bot_token = self.config.get("bot_token")
        if not bot_token:
            logger.error("Slack bot token not configured")
            return False

        self.client = SlackClient(bot_token)

        # Test connection
        try:
            result = self.client.test_auth()
            if not result.get("ok"):
                logger.error(f"Slack auth failed: {result.get('error')}")
                return False
            logger.info(f"Slack connected as {result.get('user')}")
            return True
        except Exception as e:
            logger.error(f"Slack connection failed: {e}")
            return False

    def cleanup(self):
        """Clean up Slack resources."""
        self.client = None

    def on_event(self, event_type: str, data: Any):
        """Handle events -- post to Slack on task changes."""
        if not self.client:
            return

        channel = self.config.get("channel")
        if not channel:
            return

        if event_type == "task_completed" and self.config.get(
            "notify_on_complete", True
        ):
            task = data.get("task") if isinstance(data, dict) else data
            text = f":white_check_mark: Task completed: *{getattr(task, 'text', str(task))}*"
            self.client.post_message(channel, text)

        elif event_type == "task_created" and self.config.get(
            "notify_on_create", False
        ):
            task = data.get("task") if isinstance(data, dict) else data
            text = f":memo: New task: *{getattr(task, 'text', str(task))}*"
            self.client.post_message(channel, text)

    def post_daily_summary(self, todos: list) -> bool:
        """Post a daily task summary to Slack."""
        if not self.client:
            return False

        channel = self.config.get("channel")
        if not channel:
            return False

        total = len(todos)
        completed = len([t for t in todos if getattr(t, "completed", False)])
        pending = total - completed
        overdue = len(
            [
                t
                for t in todos
                if hasattr(t, "is_overdue")
                and t.is_overdue()
                and not getattr(t, "completed", False)
            ]
        )

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f":clipboard: Daily Task Summary - {datetime.now().strftime('%B %d, %Y')}",
                },
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Total Tasks:*\n{total}"},
                    {"type": "mrkdwn", "text": f"*Completed:*\n{completed}"},
                    {"type": "mrkdwn", "text": f"*Pending:*\n{pending}"},
                    {"type": "mrkdwn", "text": f"*Overdue:*\n{overdue}"},
                ],
            },
        ]

        # Add top pending tasks
        pending_todos = [
            t for t in todos if not getattr(t, "completed", False)
        ][:5]
        if pending_todos:
            task_list = "\n".join(
                [f"\u2022 {getattr(t, 'text', str(t))}" for t in pending_todos]
            )
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Top Pending Tasks:*\n{task_list}",
                    },
                }
            )

        text = f"Daily Summary: {pending} pending, {completed} completed, {overdue} overdue"
        result = self.client.post_message(channel, text, blocks)
        return result.get("ok", False)

    def create_task_from_message(self, message_text: str) -> Optional[Dict]:
        """Parse a Slack message into task data for creation."""
        # Strip Slack-specific formatting
        text = message_text.strip()
        if text == "/todo" or text.startswith("/todo "):
            text = text[5:].strip()

        if not text:
            return None

        return {"text": text, "source": "slack"}
