"""Tests for the Slack integration plugin."""

import json
from unittest.mock import patch, MagicMock, PropertyMock
from types import SimpleNamespace

import pytest
import httpx

from todo_cli.services.integrations.slack_plugin import (
    SlackClient,
    SlackPlugin,
    SLACK_API_BASE,
)
from todo_cli.services.plugins import PluginAPI, PluginType


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_response(data: dict, status_code: int = 200) -> httpx.Response:
    """Build a fake httpx.Response that .json() returns *data*."""
    resp = httpx.Response(
        status_code=status_code,
        json=data,
        request=httpx.Request("POST", "https://slack.com/api/test"),
    )
    return resp


def _make_plugin(config: dict | None = None) -> SlackPlugin:
    """Create a SlackPlugin with a mocked PluginAPI."""
    api = MagicMock(spec=PluginAPI)
    plugin = SlackPlugin(api)
    plugin.config = config or {
        "bot_token": "xoxb-test-token",
        "channel": "C12345",
        "notify_on_complete": True,
        "notify_on_create": False,
        "daily_summary": True,
    }
    return plugin


def _fake_todo(text: str, completed: bool = False, overdue: bool = False):
    """Return a lightweight object that quacks like a Todo."""
    obj = SimpleNamespace(text=text, completed=completed)
    if overdue:
        obj.is_overdue = lambda: True
    else:
        obj.is_overdue = lambda: False
    return obj


# ---------------------------------------------------------------------------
# SlackClient tests
# ---------------------------------------------------------------------------

class TestSlackClient:
    """Tests for the low-level SlackClient wrapper."""

    def test_test_auth_success(self):
        client = SlackClient("xoxb-test")
        mock_resp = _mock_response({"ok": True, "user": "botuser"})
        with patch("httpx.Client") as MockClient:
            MockClient.return_value.__enter__ = lambda s: s
            MockClient.return_value.__exit__ = MagicMock(return_value=False)
            MockClient.return_value.post.return_value = mock_resp

            result = client.test_auth()

        assert result["ok"] is True
        assert result["user"] == "botuser"

    def test_test_auth_failure(self):
        client = SlackClient("xoxb-bad")
        mock_resp = _mock_response({"ok": False, "error": "invalid_auth"})
        with patch("httpx.Client") as MockClient:
            MockClient.return_value.__enter__ = lambda s: s
            MockClient.return_value.__exit__ = MagicMock(return_value=False)
            MockClient.return_value.post.return_value = mock_resp

            result = client.test_auth()

        assert result["ok"] is False
        assert result["error"] == "invalid_auth"

    def test_post_message_without_blocks(self):
        client = SlackClient("xoxb-test")
        mock_resp = _mock_response({"ok": True, "ts": "1234567890.123456"})
        with patch("httpx.Client") as MockClient:
            MockClient.return_value.__enter__ = lambda s: s
            MockClient.return_value.__exit__ = MagicMock(return_value=False)
            MockClient.return_value.post.return_value = mock_resp

            result = client.post_message("C12345", "hello")

        assert result["ok"] is True
        # Verify the payload sent
        call_kwargs = MockClient.return_value.post.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert payload["channel"] == "C12345"
        assert payload["text"] == "hello"
        assert "blocks" not in payload

    def test_post_message_with_blocks(self):
        client = SlackClient("xoxb-test")
        mock_resp = _mock_response({"ok": True})
        blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": "hi"}}]
        with patch("httpx.Client") as MockClient:
            MockClient.return_value.__enter__ = lambda s: s
            MockClient.return_value.__exit__ = MagicMock(return_value=False)
            MockClient.return_value.post.return_value = mock_resp

            result = client.post_message("C12345", "fallback", blocks)

        call_kwargs = MockClient.return_value.post.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert payload["blocks"] == blocks

    def test_get_channels(self):
        client = SlackClient("xoxb-test")
        channels_data = [{"id": "C1", "name": "general"}, {"id": "C2", "name": "random"}]
        mock_resp = _mock_response({"ok": True, "channels": channels_data})
        with patch("httpx.Client") as MockClient:
            MockClient.return_value.__enter__ = lambda s: s
            MockClient.return_value.__exit__ = MagicMock(return_value=False)
            MockClient.return_value.get.return_value = mock_resp

            result = client.get_channels()

        assert len(result) == 2
        assert result[0]["name"] == "general"


# ---------------------------------------------------------------------------
# SlackPlugin initialisation tests
# ---------------------------------------------------------------------------

class TestSlackPluginInit:

    def test_plugin_info(self):
        plugin = _make_plugin()
        info = plugin.get_info()
        assert info.id == "slack-integration"
        assert info.plugin_type == PluginType.INTEGRATION

    def test_initialize_success(self):
        plugin = _make_plugin()
        mock_resp = _mock_response({"ok": True, "user": "bot"})
        with patch("httpx.Client") as MockClient:
            MockClient.return_value.__enter__ = lambda s: s
            MockClient.return_value.__exit__ = MagicMock(return_value=False)
            MockClient.return_value.post.return_value = mock_resp

            assert plugin.initialize() is True
            assert plugin.client is not None

    def test_initialize_no_token(self):
        plugin = _make_plugin(config={"channel": "C12345"})
        assert plugin.initialize() is False
        assert plugin.client is None

    def test_initialize_auth_fails(self):
        plugin = _make_plugin()
        mock_resp = _mock_response({"ok": False, "error": "invalid_auth"})
        with patch("httpx.Client") as MockClient:
            MockClient.return_value.__enter__ = lambda s: s
            MockClient.return_value.__exit__ = MagicMock(return_value=False)
            MockClient.return_value.post.return_value = mock_resp

            assert plugin.initialize() is False

    def test_initialize_connection_error(self):
        plugin = _make_plugin()
        with patch("httpx.Client") as MockClient:
            MockClient.return_value.__enter__ = lambda s: s
            MockClient.return_value.__exit__ = MagicMock(return_value=False)
            MockClient.return_value.post.side_effect = httpx.ConnectError("timeout")

            assert plugin.initialize() is False

    def test_cleanup(self):
        plugin = _make_plugin()
        plugin.client = SlackClient("xoxb-test")
        plugin.cleanup()
        assert plugin.client is None


# ---------------------------------------------------------------------------
# on_event tests
# ---------------------------------------------------------------------------

class TestSlackPluginOnEvent:

    def test_task_completed_posts_message(self):
        plugin = _make_plugin()
        plugin.client = MagicMock(spec=SlackClient)
        task = _fake_todo("Buy milk", completed=True)

        plugin.on_event("task_completed", {"task": task})

        plugin.client.post_message.assert_called_once()
        args = plugin.client.post_message.call_args
        assert "C12345" == args[0][0]
        assert "Buy milk" in args[0][1]

    def test_task_completed_notify_disabled(self):
        plugin = _make_plugin()
        plugin.config["notify_on_complete"] = False
        plugin.client = MagicMock(spec=SlackClient)

        plugin.on_event("task_completed", {"task": _fake_todo("x")})

        plugin.client.post_message.assert_not_called()

    def test_task_created_posts_when_enabled(self):
        plugin = _make_plugin()
        plugin.config["notify_on_create"] = True
        plugin.client = MagicMock(spec=SlackClient)
        task = _fake_todo("New task")

        plugin.on_event("task_created", {"task": task})

        plugin.client.post_message.assert_called_once()
        assert "New task" in plugin.client.post_message.call_args[0][1]

    def test_task_created_no_post_when_disabled(self):
        plugin = _make_plugin()
        plugin.config["notify_on_create"] = False
        plugin.client = MagicMock(spec=SlackClient)

        plugin.on_event("task_created", {"task": _fake_todo("x")})

        plugin.client.post_message.assert_not_called()

    def test_no_client_does_nothing(self):
        plugin = _make_plugin()
        plugin.client = None
        # Should not raise
        plugin.on_event("task_completed", {"task": _fake_todo("x")})

    def test_no_channel_does_nothing(self):
        plugin = _make_plugin()
        plugin.config["channel"] = None
        plugin.client = MagicMock(spec=SlackClient)

        plugin.on_event("task_completed", {"task": _fake_todo("x")})

        plugin.client.post_message.assert_not_called()

    def test_unknown_event_ignored(self):
        plugin = _make_plugin()
        plugin.client = MagicMock(spec=SlackClient)

        plugin.on_event("unknown_event", {})

        plugin.client.post_message.assert_not_called()


# ---------------------------------------------------------------------------
# post_daily_summary tests
# ---------------------------------------------------------------------------

class TestSlackPluginDailySummary:

    def test_daily_summary_success(self):
        plugin = _make_plugin()
        plugin.client = MagicMock(spec=SlackClient)
        plugin.client.post_message.return_value = {"ok": True}

        todos = [
            _fake_todo("Task A", completed=False, overdue=True),
            _fake_todo("Task B", completed=True),
            _fake_todo("Task C", completed=False),
        ]

        assert plugin.post_daily_summary(todos) is True
        plugin.client.post_message.assert_called_once()

        args = plugin.client.post_message.call_args
        text = args[0][1]
        blocks = args[0][2]

        # Summary text
        assert "2 pending" in text
        assert "1 completed" in text
        assert "1 overdue" in text

        # Blocks structure
        assert blocks[0]["type"] == "header"
        assert blocks[1]["type"] == "section"
        # Pending tasks block
        assert len(blocks) == 3
        assert "Task A" in blocks[2]["text"]["text"]

    def test_daily_summary_no_client(self):
        plugin = _make_plugin()
        plugin.client = None
        assert plugin.post_daily_summary([]) is False

    def test_daily_summary_no_channel(self):
        plugin = _make_plugin()
        plugin.config["channel"] = None
        plugin.client = MagicMock(spec=SlackClient)
        assert plugin.post_daily_summary([]) is False

    def test_daily_summary_empty_todos(self):
        plugin = _make_plugin()
        plugin.client = MagicMock(spec=SlackClient)
        plugin.client.post_message.return_value = {"ok": True}

        assert plugin.post_daily_summary([]) is True

        args = plugin.client.post_message.call_args
        text = args[0][1]
        assert "0 pending" in text
        # Only header + stats blocks, no pending tasks block
        blocks = args[0][2]
        assert len(blocks) == 2


# ---------------------------------------------------------------------------
# create_task_from_message tests
# ---------------------------------------------------------------------------

class TestSlackPluginCreateTask:

    def test_parse_slash_command(self):
        plugin = _make_plugin()
        result = plugin.create_task_from_message("/todo Buy groceries")
        assert result is not None
        assert result["text"] == "Buy groceries"
        assert result["source"] == "slack"

    def test_parse_plain_text(self):
        plugin = _make_plugin()
        result = plugin.create_task_from_message("Fix the bug in login")
        assert result is not None
        assert result["text"] == "Fix the bug in login"

    def test_empty_message_returns_none(self):
        plugin = _make_plugin()
        assert plugin.create_task_from_message("") is None
        assert plugin.create_task_from_message("   ") is None

    def test_slash_command_empty_after_strip(self):
        plugin = _make_plugin()
        assert plugin.create_task_from_message("/todo ") is None
        assert plugin.create_task_from_message("/todo   ") is None

    def test_whitespace_handling(self):
        plugin = _make_plugin()
        result = plugin.create_task_from_message("  hello world  ")
        assert result["text"] == "hello world"
