"""Collaboration service for shared projects and real-time task updates.

Provides multi-user project sharing, role-based access, activity tracking,
and real-time change notifications.
"""

import json
import sqlite3
import uuid
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any
from pathlib import Path


class ProjectRole(Enum):
    OWNER = "owner"
    ADMIN = "admin"
    EDITOR = "editor"
    VIEWER = "viewer"


class ActivityType(Enum):
    TASK_CREATED = "task_created"
    TASK_COMPLETED = "task_completed"
    TASK_UPDATED = "task_updated"
    TASK_DELETED = "task_deleted"
    TASK_ASSIGNED = "task_assigned"
    TASK_COMMENTED = "task_commented"
    PROJECT_SHARED = "project_shared"
    MEMBER_JOINED = "member_joined"
    MEMBER_LEFT = "member_left"


@dataclass
class ProjectMember:
    user_id: str
    username: str
    role: ProjectRole
    joined_at: datetime
    invited_by: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "username": self.username,
            "role": self.role.value,
            "joined_at": self.joined_at.isoformat(),
            "invited_by": self.invited_by,
        }


@dataclass
class SharedProject:
    id: str
    name: str
    owner_id: str
    description: str = ""
    members: List[ProjectMember] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    is_active: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "owner_id": self.owner_id,
            "description": self.description,
            "members": [m.to_dict() for m in self.members],
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "is_active": self.is_active,
        }


@dataclass
class ActivityEntry:
    id: str
    project_id: str
    user_id: str
    username: str
    activity_type: ActivityType
    description: str
    task_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "user_id": self.user_id,
            "username": self.username,
            "activity_type": self.activity_type.value,
            "description": self.description,
            "task_id": self.task_id,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class TaskComment:
    id: str
    task_id: str
    user_id: str
    username: str
    content: str
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "task_id": self.task_id,
            "user_id": self.user_id,
            "username": self.username,
            "content": self.content,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class CollaborationDB:
    """SQLite database for collaboration data."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or Path.home() / ".todo" / "collaboration.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Create tables if they don't exist."""
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS shared_projects (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    owner_id TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    is_active INTEGER DEFAULT 1
                );
                CREATE TABLE IF NOT EXISTS project_members (
                    project_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    username TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'viewer',
                    joined_at TEXT NOT NULL,
                    invited_by TEXT,
                    PRIMARY KEY (project_id, user_id),
                    FOREIGN KEY (project_id) REFERENCES shared_projects(id)
                );
                CREATE TABLE IF NOT EXISTS activity_feed (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    username TEXT NOT NULL,
                    activity_type TEXT NOT NULL,
                    description TEXT NOT NULL,
                    task_id TEXT,
                    metadata TEXT DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (project_id) REFERENCES shared_projects(id)
                );
                CREATE TABLE IF NOT EXISTS task_comments (
                    id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    username TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT
                );
                CREATE TABLE IF NOT EXISTS task_assignments (
                    task_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    assigned_by TEXT NOT NULL,
                    assigned_at TEXT NOT NULL,
                    PRIMARY KEY (task_id, user_id)
                );
            """)

    def _connect(self):
        return sqlite3.connect(str(self.db_path))

    # ---- CRUD for shared projects ----

    def create_shared_project(self, name: str, owner_id: str, description: str = "") -> SharedProject:
        now = datetime.now()
        project_id = str(uuid.uuid4())
        project = SharedProject(
            id=project_id,
            name=name,
            owner_id=owner_id,
            description=description,
            created_at=now,
            updated_at=now,
            is_active=True,
        )
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO shared_projects (id, name, owner_id, description, created_at, updated_at, is_active) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (project.id, project.name, project.owner_id, project.description,
                 project.created_at.isoformat(), project.updated_at.isoformat(), 1),
            )
            # Add owner as a member with OWNER role
            conn.execute(
                "INSERT INTO project_members (project_id, user_id, username, role, joined_at, invited_by) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (project.id, owner_id, owner_id, ProjectRole.OWNER.value, now.isoformat(), None),
            )
        owner_member = ProjectMember(
            user_id=owner_id, username=owner_id, role=ProjectRole.OWNER,
            joined_at=now, invited_by=None,
        )
        project.members = [owner_member]
        return project

    def get_shared_project(self, project_id: str) -> Optional[SharedProject]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id, name, owner_id, description, created_at, updated_at, is_active "
                "FROM shared_projects WHERE id = ?",
                (project_id,),
            ).fetchone()
        if not row:
            return None
        project = SharedProject(
            id=row[0], name=row[1], owner_id=row[2], description=row[3],
            created_at=datetime.fromisoformat(row[4]),
            updated_at=datetime.fromisoformat(row[5]),
            is_active=bool(row[6]),
        )
        project.members = self.get_project_members(project_id)
        return project

    def list_user_projects(self, user_id: str) -> List[SharedProject]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT DISTINCT sp.id FROM shared_projects sp "
                "JOIN project_members pm ON sp.id = pm.project_id "
                "WHERE pm.user_id = ? AND sp.is_active = 1",
                (user_id,),
            ).fetchall()
        projects = []
        for (pid,) in rows:
            proj = self.get_shared_project(pid)
            if proj:
                projects.append(proj)
        return projects

    def delete_shared_project(self, project_id: str, user_id: str) -> bool:
        project = self.get_shared_project(project_id)
        if not project or project.owner_id != user_id:
            return False
        with self._connect() as conn:
            conn.execute(
                "UPDATE shared_projects SET is_active = 0, updated_at = ? WHERE id = ?",
                (datetime.now().isoformat(), project_id),
            )
        return True

    # ---- Member management ----

    def add_member(self, project_id: str, user_id: str, username: str,
                   role: ProjectRole, invited_by: str) -> ProjectMember:
        now = datetime.now()
        member = ProjectMember(
            user_id=user_id, username=username, role=role,
            joined_at=now, invited_by=invited_by,
        )
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO project_members "
                "(project_id, user_id, username, role, joined_at, invited_by) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (project_id, user_id, username, role.value, now.isoformat(), invited_by),
            )
        return member

    def remove_member(self, project_id: str, user_id: str) -> bool:
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM project_members WHERE project_id = ? AND user_id = ? AND role != ?",
                (project_id, user_id, ProjectRole.OWNER.value),
            )
        return cursor.rowcount > 0

    def update_member_role(self, project_id: str, user_id: str, new_role: ProjectRole) -> bool:
        if new_role == ProjectRole.OWNER:
            return False
        with self._connect() as conn:
            cursor = conn.execute(
                "UPDATE project_members SET role = ? WHERE project_id = ? AND user_id = ? AND role != ?",
                (new_role.value, project_id, user_id, ProjectRole.OWNER.value),
            )
        return cursor.rowcount > 0

    def get_project_members(self, project_id: str) -> List[ProjectMember]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT user_id, username, role, joined_at, invited_by "
                "FROM project_members WHERE project_id = ?",
                (project_id,),
            ).fetchall()
        members = []
        for row in rows:
            members.append(ProjectMember(
                user_id=row[0], username=row[1], role=ProjectRole(row[2]),
                joined_at=datetime.fromisoformat(row[3]), invited_by=row[4],
            ))
        return members

    def get_user_role(self, project_id: str, user_id: str) -> Optional[ProjectRole]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT role FROM project_members WHERE project_id = ? AND user_id = ?",
                (project_id, user_id),
            ).fetchone()
        if not row:
            return None
        return ProjectRole(row[0])

    # ---- Activity feed ----

    def log_activity(self, project_id: str, user_id: str, username: str,
                     activity_type: ActivityType, description: str,
                     task_id: Optional[str] = None,
                     metadata: Optional[Dict[str, Any]] = None) -> ActivityEntry:
        now = datetime.now()
        entry_id = str(uuid.uuid4())
        entry = ActivityEntry(
            id=entry_id, project_id=project_id, user_id=user_id,
            username=username, activity_type=activity_type,
            description=description, task_id=task_id,
            metadata=metadata or {}, created_at=now,
        )
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO activity_feed "
                "(id, project_id, user_id, username, activity_type, description, task_id, metadata, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (entry.id, entry.project_id, entry.user_id, entry.username,
                 entry.activity_type.value, entry.description, entry.task_id,
                 json.dumps(entry.metadata), entry.created_at.isoformat()),
            )
        return entry

    def get_activity_feed(self, project_id: str, limit: int = 50) -> List[ActivityEntry]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, project_id, user_id, username, activity_type, description, "
                "task_id, metadata, created_at "
                "FROM activity_feed WHERE project_id = ? ORDER BY created_at DESC LIMIT ?",
                (project_id, limit),
            ).fetchall()
        return [self._row_to_activity(r) for r in rows]

    def get_user_activity(self, user_id: str, limit: int = 50) -> List[ActivityEntry]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, project_id, user_id, username, activity_type, description, "
                "task_id, metadata, created_at "
                "FROM activity_feed WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
                (user_id, limit),
            ).fetchall()
        return [self._row_to_activity(r) for r in rows]

    def _row_to_activity(self, row) -> ActivityEntry:
        return ActivityEntry(
            id=row[0], project_id=row[1], user_id=row[2], username=row[3],
            activity_type=ActivityType(row[4]), description=row[5],
            task_id=row[6], metadata=json.loads(row[7]) if row[7] else {},
            created_at=datetime.fromisoformat(row[8]),
        )

    # ---- Comments ----

    def add_comment(self, task_id: str, user_id: str, username: str,
                    content: str) -> TaskComment:
        now = datetime.now()
        comment_id = str(uuid.uuid4())
        comment = TaskComment(
            id=comment_id, task_id=task_id, user_id=user_id,
            username=username, content=content, created_at=now,
        )
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO task_comments (id, task_id, user_id, username, content, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (comment.id, comment.task_id, comment.user_id, comment.username,
                 comment.content, comment.created_at.isoformat(), None),
            )
        return comment

    def get_comments(self, task_id: str) -> List[TaskComment]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, task_id, user_id, username, content, created_at, updated_at "
                "FROM task_comments WHERE task_id = ? ORDER BY created_at ASC",
                (task_id,),
            ).fetchall()
        comments = []
        for row in rows:
            comments.append(TaskComment(
                id=row[0], task_id=row[1], user_id=row[2], username=row[3],
                content=row[4], created_at=datetime.fromisoformat(row[5]),
                updated_at=datetime.fromisoformat(row[6]) if row[6] else None,
            ))
        return comments

    def delete_comment(self, comment_id: str, user_id: str) -> bool:
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM task_comments WHERE id = ? AND user_id = ?",
                (comment_id, user_id),
            )
        return cursor.rowcount > 0

    # ---- Assignments ----

    def assign_task(self, task_id: str, user_id: str, assigned_by: str) -> bool:
        now = datetime.now()
        with self._connect() as conn:
            try:
                conn.execute(
                    "INSERT OR REPLACE INTO task_assignments (task_id, user_id, assigned_by, assigned_at) "
                    "VALUES (?, ?, ?, ?)",
                    (task_id, user_id, assigned_by, now.isoformat()),
                )
                return True
            except sqlite3.Error:
                return False

    def unassign_task(self, task_id: str, user_id: str) -> bool:
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM task_assignments WHERE task_id = ? AND user_id = ?",
                (task_id, user_id),
            )
        return cursor.rowcount > 0

    def get_task_assignments(self, task_id: str) -> List[Dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT task_id, user_id, assigned_by, assigned_at "
                "FROM task_assignments WHERE task_id = ?",
                (task_id,),
            ).fetchall()
        return [
            {"task_id": r[0], "user_id": r[1], "assigned_by": r[2],
             "assigned_at": r[3]}
            for r in rows
        ]

    def get_user_assignments(self, user_id: str) -> List[str]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT task_id FROM task_assignments WHERE user_id = ?",
                (user_id,),
            ).fetchall()
        return [r[0] for r in rows]


class CollaborationManager:
    """High-level collaboration operations with permission checking."""

    ROLE_HIERARCHY = {
        ProjectRole.OWNER: 4,
        ProjectRole.ADMIN: 3,
        ProjectRole.EDITOR: 2,
        ProjectRole.VIEWER: 1,
    }

    def __init__(self, db: Optional[CollaborationDB] = None):
        self.db = db or CollaborationDB()

    def share_project(self, project_name: str, owner_id: str,
                      description: str = "") -> SharedProject:
        """Create a shared project."""
        project = self.db.create_shared_project(project_name, owner_id, description)
        self.db.log_activity(
            project_id=project.id, user_id=owner_id, username=owner_id,
            activity_type=ActivityType.PROJECT_SHARED,
            description=f"Created shared project '{project_name}'",
        )
        return project

    def invite_member(self, project_id: str, inviter_id: str,
                      user_id: str, username: str,
                      role: ProjectRole = ProjectRole.EDITOR) -> Optional[ProjectMember]:
        """Invite a member, checking inviter permissions."""
        if not self.check_permission(project_id, inviter_id, ProjectRole.ADMIN):
            return None
        member = self.db.add_member(project_id, user_id, username, role, inviter_id)
        self.db.log_activity(
            project_id=project_id, user_id=inviter_id, username=inviter_id,
            activity_type=ActivityType.MEMBER_JOINED,
            description=f"Invited {username} as {role.value}",
        )
        return member

    def check_permission(self, project_id: str, user_id: str,
                         required_role: ProjectRole = ProjectRole.VIEWER) -> bool:
        """Check if user has at least the required role."""
        user_role = self.db.get_user_role(project_id, user_id)
        if not user_role:
            return False
        return self.ROLE_HIERARCHY.get(user_role, 0) >= self.ROLE_HIERARCHY.get(required_role, 0)

    def log_task_activity(self, project_id: str, user_id: str, username: str,
                          activity_type: ActivityType, task_text: str,
                          task_id: Optional[str] = None):
        """Log a task-related activity."""
        description_map = {
            ActivityType.TASK_CREATED: f"Created task: {task_text}",
            ActivityType.TASK_COMPLETED: f"Completed task: {task_text}",
            ActivityType.TASK_UPDATED: f"Updated task: {task_text}",
            ActivityType.TASK_DELETED: f"Deleted task: {task_text}",
            ActivityType.TASK_ASSIGNED: f"Assigned task: {task_text}",
            ActivityType.TASK_COMMENTED: f"Commented on task: {task_text}",
        }
        description = description_map.get(activity_type, f"Activity on task: {task_text}")
        self.db.log_activity(
            project_id=project_id, user_id=user_id, username=username,
            activity_type=activity_type, description=description,
            task_id=task_id,
        )
