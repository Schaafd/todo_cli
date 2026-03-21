"""Comprehensive tests for the collaboration service."""

import asyncio
import json
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from todo_cli.services.collaboration import (
    ActivityEntry,
    ActivityType,
    CollaborationDB,
    CollaborationManager,
    ProjectMember,
    ProjectRole,
    SharedProject,
    TaskComment,
)
from todo_cli.services.realtime import RealtimeManager, WebSocketClient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "test_collab.db"


@pytest.fixture
def db(db_path):
    return CollaborationDB(db_path=db_path)


@pytest.fixture
def manager(db):
    return CollaborationManager(db=db)


@pytest.fixture
def realtime():
    return RealtimeManager()


# ---------------------------------------------------------------------------
# CollaborationDB: shared projects CRUD
# ---------------------------------------------------------------------------

class TestCollaborationDBProjects:
    def test_create_shared_project(self, db):
        project = db.create_shared_project("my-project", "user-1", "A test project")
        assert project.name == "my-project"
        assert project.owner_id == "user-1"
        assert project.description == "A test project"
        assert project.is_active is True
        assert len(project.id) > 0
        # Owner should be added as a member automatically
        assert len(project.members) == 1
        assert project.members[0].role == ProjectRole.OWNER

    def test_get_shared_project(self, db):
        created = db.create_shared_project("proj", "owner1")
        fetched = db.get_shared_project(created.id)
        assert fetched is not None
        assert fetched.id == created.id
        assert fetched.name == "proj"
        assert fetched.owner_id == "owner1"

    def test_get_shared_project_not_found(self, db):
        assert db.get_shared_project("nonexistent") is None

    def test_list_user_projects(self, db):
        db.create_shared_project("p1", "user-a")
        db.create_shared_project("p2", "user-a")
        db.create_shared_project("p3", "user-b")
        projects = db.list_user_projects("user-a")
        assert len(projects) == 2
        names = {p.name for p in projects}
        assert names == {"p1", "p2"}

    def test_list_user_projects_empty(self, db):
        projects = db.list_user_projects("nobody")
        assert projects == []

    def test_delete_shared_project(self, db):
        project = db.create_shared_project("deleteme", "owner")
        assert db.delete_shared_project(project.id, "owner") is True
        # After deletion the project should be inactive
        fetched = db.get_shared_project(project.id)
        assert fetched is not None
        assert fetched.is_active is False
        # Should not appear in user's active project list
        assert db.list_user_projects("owner") == []

    def test_delete_shared_project_wrong_owner(self, db):
        project = db.create_shared_project("proj", "owner")
        assert db.delete_shared_project(project.id, "not-owner") is False

    def test_delete_nonexistent_project(self, db):
        assert db.delete_shared_project("fake-id", "user") is False


# ---------------------------------------------------------------------------
# CollaborationDB: member management
# ---------------------------------------------------------------------------

class TestCollaborationDBMembers:
    def test_add_member(self, db):
        project = db.create_shared_project("proj", "owner")
        member = db.add_member(project.id, "user-2", "alice", ProjectRole.EDITOR, "owner")
        assert member.user_id == "user-2"
        assert member.username == "alice"
        assert member.role == ProjectRole.EDITOR
        assert member.invited_by == "owner"

    def test_get_project_members(self, db):
        project = db.create_shared_project("proj", "owner")
        db.add_member(project.id, "u2", "bob", ProjectRole.EDITOR, "owner")
        db.add_member(project.id, "u3", "carol", ProjectRole.VIEWER, "owner")
        members = db.get_project_members(project.id)
        assert len(members) == 3  # owner + 2 added
        roles = {m.user_id: m.role for m in members}
        assert roles["owner"] == ProjectRole.OWNER
        assert roles["u2"] == ProjectRole.EDITOR
        assert roles["u3"] == ProjectRole.VIEWER

    def test_remove_member(self, db):
        project = db.create_shared_project("proj", "owner")
        db.add_member(project.id, "u2", "bob", ProjectRole.EDITOR, "owner")
        assert db.remove_member(project.id, "u2") is True
        members = db.get_project_members(project.id)
        assert len(members) == 1  # only owner remains

    def test_remove_owner_fails(self, db):
        project = db.create_shared_project("proj", "owner")
        assert db.remove_member(project.id, "owner") is False

    def test_update_member_role(self, db):
        project = db.create_shared_project("proj", "owner")
        db.add_member(project.id, "u2", "bob", ProjectRole.VIEWER, "owner")
        assert db.update_member_role(project.id, "u2", ProjectRole.ADMIN) is True
        role = db.get_user_role(project.id, "u2")
        assert role == ProjectRole.ADMIN

    def test_update_to_owner_fails(self, db):
        project = db.create_shared_project("proj", "owner")
        db.add_member(project.id, "u2", "bob", ProjectRole.EDITOR, "owner")
        assert db.update_member_role(project.id, "u2", ProjectRole.OWNER) is False

    def test_get_user_role(self, db):
        project = db.create_shared_project("proj", "owner")
        assert db.get_user_role(project.id, "owner") == ProjectRole.OWNER
        assert db.get_user_role(project.id, "nonexistent") is None


# ---------------------------------------------------------------------------
# CollaborationDB: activity feed
# ---------------------------------------------------------------------------

class TestCollaborationDBActivity:
    def test_log_and_get_activity(self, db):
        project = db.create_shared_project("proj", "owner")
        entry = db.log_activity(
            project.id, "owner", "owner",
            ActivityType.TASK_CREATED, "Created a task",
            task_id="t1", metadata={"key": "value"},
        )
        assert entry.id is not None
        assert entry.activity_type == ActivityType.TASK_CREATED

        feed = db.get_activity_feed(project.id)
        assert len(feed) == 1
        assert feed[0].description == "Created a task"
        assert feed[0].metadata == {"key": "value"}

    def test_get_user_activity(self, db):
        p1 = db.create_shared_project("p1", "owner")
        p2 = db.create_shared_project("p2", "owner")
        db.log_activity(p1.id, "owner", "owner", ActivityType.TASK_CREATED, "task in p1")
        db.log_activity(p2.id, "owner", "owner", ActivityType.TASK_COMPLETED, "task in p2")
        entries = db.get_user_activity("owner")
        assert len(entries) == 2

    def test_activity_feed_limit(self, db):
        project = db.create_shared_project("proj", "owner")
        for i in range(10):
            db.log_activity(project.id, "owner", "owner",
                            ActivityType.TASK_UPDATED, f"update {i}")
        feed = db.get_activity_feed(project.id, limit=5)
        assert len(feed) == 5

    def test_activity_feed_ordering(self, db):
        project = db.create_shared_project("proj", "owner")
        db.log_activity(project.id, "owner", "owner", ActivityType.TASK_CREATED, "first")
        db.log_activity(project.id, "owner", "owner", ActivityType.TASK_COMPLETED, "second")
        feed = db.get_activity_feed(project.id)
        # Most recent first
        assert feed[0].description == "second"
        assert feed[1].description == "first"


# ---------------------------------------------------------------------------
# CollaborationDB: comments
# ---------------------------------------------------------------------------

class TestCollaborationDBComments:
    def test_add_and_get_comments(self, db):
        comment = db.add_comment("task-1", "user-1", "alice", "Great work!")
        assert comment.id is not None
        assert comment.content == "Great work!"

        comments = db.get_comments("task-1")
        assert len(comments) == 1
        assert comments[0].username == "alice"

    def test_multiple_comments(self, db):
        db.add_comment("task-1", "u1", "alice", "First")
        db.add_comment("task-1", "u2", "bob", "Second")
        comments = db.get_comments("task-1")
        assert len(comments) == 2
        # Ordered by creation time
        assert comments[0].content == "First"
        assert comments[1].content == "Second"

    def test_delete_comment(self, db):
        comment = db.add_comment("task-1", "u1", "alice", "delete me")
        assert db.delete_comment(comment.id, "u1") is True
        assert db.get_comments("task-1") == []

    def test_delete_comment_wrong_user(self, db):
        comment = db.add_comment("task-1", "u1", "alice", "mine")
        assert db.delete_comment(comment.id, "u2") is False
        assert len(db.get_comments("task-1")) == 1

    def test_get_comments_empty(self, db):
        assert db.get_comments("no-task") == []


# ---------------------------------------------------------------------------
# CollaborationDB: assignments
# ---------------------------------------------------------------------------

class TestCollaborationDBAssignments:
    def test_assign_task(self, db):
        assert db.assign_task("task-1", "user-a", "owner") is True
        assignments = db.get_task_assignments("task-1")
        assert len(assignments) == 1
        assert assignments[0]["user_id"] == "user-a"
        assert assignments[0]["assigned_by"] == "owner"

    def test_unassign_task(self, db):
        db.assign_task("task-1", "user-a", "owner")
        assert db.unassign_task("task-1", "user-a") is True
        assert db.get_task_assignments("task-1") == []

    def test_unassign_nonexistent(self, db):
        assert db.unassign_task("fake", "fake") is False

    def test_get_user_assignments(self, db):
        db.assign_task("t1", "user-a", "owner")
        db.assign_task("t2", "user-a", "owner")
        db.assign_task("t3", "user-b", "owner")
        tasks = db.get_user_assignments("user-a")
        assert set(tasks) == {"t1", "t2"}

    def test_reassign_task(self, db):
        db.assign_task("task-1", "user-a", "owner")
        db.assign_task("task-1", "user-a", "admin")  # re-assign updates
        assignments = db.get_task_assignments("task-1")
        assert len(assignments) == 1
        assert assignments[0]["assigned_by"] == "admin"


# ---------------------------------------------------------------------------
# CollaborationManager: permission checking
# ---------------------------------------------------------------------------

class TestCollaborationManager:
    def test_share_project(self, manager):
        project = manager.share_project("test-proj", "owner-1", "desc")
        assert project.name == "test-proj"
        assert project.owner_id == "owner-1"
        # Activity should be logged
        feed = manager.db.get_activity_feed(project.id)
        assert len(feed) == 1
        assert feed[0].activity_type == ActivityType.PROJECT_SHARED

    def test_invite_member_as_owner(self, manager):
        project = manager.share_project("proj", "owner")
        member = manager.invite_member(project.id, "owner", "user-2", "alice", ProjectRole.EDITOR)
        assert member is not None
        assert member.role == ProjectRole.EDITOR

    def test_invite_member_as_admin(self, manager):
        project = manager.share_project("proj", "owner")
        manager.db.add_member(project.id, "admin-user", "admin", ProjectRole.ADMIN, "owner")
        member = manager.invite_member(project.id, "admin-user", "user-3", "carol", ProjectRole.VIEWER)
        assert member is not None

    def test_invite_member_as_editor_fails(self, manager):
        project = manager.share_project("proj", "owner")
        manager.db.add_member(project.id, "editor-user", "editor", ProjectRole.EDITOR, "owner")
        member = manager.invite_member(project.id, "editor-user", "user-3", "carol", ProjectRole.VIEWER)
        assert member is None

    def test_invite_member_as_viewer_fails(self, manager):
        project = manager.share_project("proj", "owner")
        manager.db.add_member(project.id, "viewer-user", "viewer", ProjectRole.VIEWER, "owner")
        member = manager.invite_member(project.id, "viewer-user", "user-3", "carol")
        assert member is None

    def test_check_permission_owner(self, manager):
        project = manager.share_project("proj", "owner")
        assert manager.check_permission(project.id, "owner", ProjectRole.OWNER) is True
        assert manager.check_permission(project.id, "owner", ProjectRole.ADMIN) is True
        assert manager.check_permission(project.id, "owner", ProjectRole.EDITOR) is True
        assert manager.check_permission(project.id, "owner", ProjectRole.VIEWER) is True

    def test_check_permission_editor(self, manager):
        project = manager.share_project("proj", "owner")
        manager.db.add_member(project.id, "editor", "editor", ProjectRole.EDITOR, "owner")
        assert manager.check_permission(project.id, "editor", ProjectRole.EDITOR) is True
        assert manager.check_permission(project.id, "editor", ProjectRole.VIEWER) is True
        assert manager.check_permission(project.id, "editor", ProjectRole.ADMIN) is False
        assert manager.check_permission(project.id, "editor", ProjectRole.OWNER) is False

    def test_check_permission_nonmember(self, manager):
        project = manager.share_project("proj", "owner")
        assert manager.check_permission(project.id, "outsider") is False

    def test_log_task_activity(self, manager):
        project = manager.share_project("proj", "owner")
        manager.log_task_activity(
            project.id, "owner", "owner",
            ActivityType.TASK_CREATED, "Buy milk", task_id="t1",
        )
        feed = manager.db.get_activity_feed(project.id)
        # 1 from share_project + 1 from log_task_activity
        assert len(feed) == 2
        task_entry = [e for e in feed if e.activity_type == ActivityType.TASK_CREATED][0]
        assert "Buy milk" in task_entry.description


# ---------------------------------------------------------------------------
# Dataclass to_dict methods
# ---------------------------------------------------------------------------

class TestDataclassSerialization:
    def test_project_member_to_dict(self):
        m = ProjectMember(
            user_id="u1", username="alice", role=ProjectRole.EDITOR,
            joined_at=datetime(2025, 1, 1), invited_by="owner",
        )
        d = m.to_dict()
        assert d["user_id"] == "u1"
        assert d["role"] == "editor"
        assert d["invited_by"] == "owner"

    def test_shared_project_to_dict(self):
        p = SharedProject(
            id="pid", name="proj", owner_id="o1",
            created_at=datetime(2025, 1, 1), updated_at=datetime(2025, 1, 2),
        )
        d = p.to_dict()
        assert d["id"] == "pid"
        assert d["name"] == "proj"
        assert d["members"] == []

    def test_activity_entry_to_dict(self):
        e = ActivityEntry(
            id="aid", project_id="pid", user_id="u1", username="alice",
            activity_type=ActivityType.TASK_CREATED, description="test",
            created_at=datetime(2025, 1, 1),
        )
        d = e.to_dict()
        assert d["activity_type"] == "task_created"

    def test_task_comment_to_dict(self):
        c = TaskComment(
            id="cid", task_id="t1", user_id="u1", username="alice",
            content="Hello", created_at=datetime(2025, 1, 1),
        )
        d = c.to_dict()
        assert d["content"] == "Hello"
        assert d["updated_at"] is None


# ---------------------------------------------------------------------------
# RealtimeManager
# ---------------------------------------------------------------------------

class TestRealtimeManager:
    async def test_connect_and_disconnect(self, realtime):
        ws = AsyncMock()
        conn_id = await realtime.connect(ws, "user-1", "alice")
        assert conn_id in realtime.clients
        assert realtime.clients[conn_id].user_id == "user-1"

        await realtime.disconnect(conn_id)
        assert conn_id not in realtime.clients

    async def test_subscribe_project(self, realtime):
        ws = AsyncMock()
        conn_id = await realtime.connect(ws, "user-1", "alice")
        await realtime.subscribe_project(conn_id, "proj-1")
        assert "proj-1" in realtime.clients[conn_id].subscribed_projects
        assert conn_id in realtime.project_subscribers["proj-1"]

    async def test_unsubscribe_project(self, realtime):
        ws = AsyncMock()
        conn_id = await realtime.connect(ws, "user-1", "alice")
        await realtime.subscribe_project(conn_id, "proj-1")
        await realtime.unsubscribe_project(conn_id, "proj-1")
        assert "proj-1" not in realtime.clients[conn_id].subscribed_projects
        assert "proj-1" not in realtime.project_subscribers

    async def test_broadcast_to_project(self, realtime):
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        c1 = await realtime.connect(ws1, "user-1", "alice")
        c2 = await realtime.connect(ws2, "user-2", "bob")
        await realtime.subscribe_project(c1, "proj-1")
        await realtime.subscribe_project(c2, "proj-1")

        await realtime.broadcast_to_project("proj-1", "task_update", {"task": "test"})
        ws1.send_text.assert_called_once()
        ws2.send_text.assert_called_once()

        msg1 = json.loads(ws1.send_text.call_args[0][0])
        assert msg1["type"] == "task_update"
        assert msg1["data"]["task"] == "test"

    async def test_broadcast_exclude_user(self, realtime):
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        c1 = await realtime.connect(ws1, "user-1", "alice")
        c2 = await realtime.connect(ws2, "user-2", "bob")
        await realtime.subscribe_project(c1, "proj-1")
        await realtime.subscribe_project(c2, "proj-1")

        await realtime.broadcast_to_project("proj-1", "update", {}, exclude_user="user-1")
        ws1.send_text.assert_not_called()
        ws2.send_text.assert_called_once()

    async def test_send_to_user(self, realtime):
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        await realtime.connect(ws1, "user-1", "alice")
        await realtime.connect(ws2, "user-2", "bob")

        await realtime.send_to_user("user-1", "notification", {"msg": "hello"})
        ws1.send_text.assert_called_once()
        ws2.send_text.assert_not_called()

    async def test_get_online_users(self, realtime):
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        c1 = await realtime.connect(ws1, "user-1", "alice")
        c2 = await realtime.connect(ws2, "user-2", "bob")
        await realtime.subscribe_project(c1, "proj-1")

        all_users = realtime.get_online_users()
        assert len(all_users) == 2

        proj_users = realtime.get_online_users("proj-1")
        assert len(proj_users) == 1
        assert proj_users[0]["user_id"] == "user-1"

    async def test_get_online_users_empty(self, realtime):
        assert realtime.get_online_users() == []

    async def test_disconnect_cleans_subscriptions(self, realtime):
        ws = AsyncMock()
        conn_id = await realtime.connect(ws, "user-1", "alice")
        await realtime.subscribe_project(conn_id, "proj-1")
        await realtime.subscribe_project(conn_id, "proj-2")

        await realtime.disconnect(conn_id)
        assert "proj-1" not in realtime.project_subscribers
        assert "proj-2" not in realtime.project_subscribers

    async def test_broadcast_handles_send_failure(self, realtime):
        ws_good = AsyncMock()
        ws_bad = AsyncMock()
        ws_bad.send_text.side_effect = Exception("Connection lost")

        c1 = await realtime.connect(ws_good, "user-1", "alice")
        c2 = await realtime.connect(ws_bad, "user-2", "bob")
        await realtime.subscribe_project(c1, "proj-1")
        await realtime.subscribe_project(c2, "proj-1")

        await realtime.broadcast_to_project("proj-1", "test", {"a": 1})
        # Good client still receives
        ws_good.send_text.assert_called_once()
        # Bad client should be disconnected
        assert c2 not in realtime.clients

    async def test_subscribe_nonexistent_connection(self, realtime):
        # Should not raise
        await realtime.subscribe_project("fake-conn", "proj-1")
        assert "proj-1" not in realtime.project_subscribers


class TestWebSocketClient:
    def test_default_fields(self):
        ws = MagicMock()
        client = WebSocketClient(user_id="u1", username="alice", websocket=ws)
        assert client.subscribed_projects == set()
        assert isinstance(client.connected_at, datetime)
