"""PWA backup utilities and API coverage tests."""

import json
import os
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from todo_cli.web import server
from todo_cli.web.server import (
    app,
    build_backup_payload,
    get_todo_storage,
    list_backup_files,
    restore_backup,
    sanitize_backup_filename,
)
from todo_cli.domain.project import Project
from todo_cli.domain.todo import Todo


@pytest.fixture()
def backup_dir(tmp_path, monkeypatch) -> Path:
    """Point backup operations at an isolated directory."""
    path = tmp_path / "backups"
    monkeypatch.setattr(server, "BACKUP_DIR", path)
    server.ensure_backup_dir()
    return path


def test_sanitize_backup_filename_validation():
    """Ensure backup filename validation rejects unsafe or invalid values."""
    assert sanitize_backup_filename("valid.json") == "valid.json"

    with pytest.raises(HTTPException):
        sanitize_backup_filename("")

    with pytest.raises(HTTPException):
        sanitize_backup_filename("../../secrets.json")

    with pytest.raises(HTTPException):
        sanitize_backup_filename("backup.txt")


def test_build_backup_payload_includes_projects(monkeypatch):
    """Backup payload should include configured defaults and project data."""
    fake_config = SimpleNamespace(default_project="inbox")
    monkeypatch.setattr(server, "get_config", lambda: fake_config)

    project = Project(name="team")
    todo = Todo(id=1, text="Ship feature", project="team")
    storage = SimpleNamespace(
        list_projects=lambda: [project.name],
        load_project=lambda name: (project, [todo]),
    )

    payload = build_backup_payload(storage)

    assert payload["config"]["default_project"] == "inbox"
    assert payload["projects"][project.name]["project"]["name"] == project.name
    assert payload["projects"][project.name]["todos"][0]["text"] == todo.text
    assert "created_at" in payload["metadata"]


def test_list_backup_files_prefers_metadata_timestamp(backup_dir):
    """Listing backups should preserve metadata timestamps when available."""
    first = backup_dir / "older.json"
    first.write_text(json.dumps({"backup_metadata": {"timestamp": "2024-01-01T00:00:00Z"}}))
    second = backup_dir / "newer.json"
    second.write_text(json.dumps({}))

    first_time = 1_000
    second_time = 2_000
    for path, ts in ((first, first_time), (second, second_time)):
        os.utime(path, (ts, ts))

    backups = list_backup_files()

    assert [b.filename for b in backups] == ["newer.json", "older.json"]
    assert backups[1].created_at == "2024-01-01T00:00:00Z"
    expected_mtime = datetime.fromtimestamp(second_time).isoformat() + "Z"
    assert backups[0].created_at == expected_mtime


def test_restore_backup_writes_to_storage(backup_dir):
    """Restore logic should validate paths and persist loaded data."""
    backup_payload = {
        "projects": {
            "inbox": {
                "project": {"name": "inbox"},
                "todos": [
                    {
                        "id": 1,
                        "text": "Task",
                        "status": "pending",
                        "priority": "medium",
                        "project": "inbox",
                    }
                ],
            }
        }
    }

    backup_path = backup_dir / "backup.json"
    backup_path.write_text(json.dumps(backup_payload))

    storage = Mock()

    restore_backup(storage, "backup.json")

    storage.save_project.assert_called_once()
    project_arg, todos_arg = storage.save_project.call_args[0]
    assert project_arg.name == "inbox"
    assert len(todos_arg) == 1


def test_backup_routes_use_isolated_directory(backup_dir):
    """API routes should honor the configured backup directory and validation."""
    valid_backup = backup_dir / "latest.json"
    valid_backup.write_text(json.dumps({"backup_metadata": {"timestamp": "2025-01-01T00:00:00Z"}}))

    client = TestClient(app)
    response = client.get("/api/backups")

    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["filename"] == "latest.json"
    assert payload[0]["created_at"] == "2025-01-01T00:00:00Z"


def test_restore_route_rejects_traversal_and_restores(backup_dir):
    """Restore API should reject traversal attempts and process valid backups."""
    backup_payload = {
        "projects": {
            "work": {
                "project": {"name": "work"},
                "todos": [
                    {
                        "id": 1,
                        "text": "Do it",
                        "status": "pending",
                        "priority": "medium",
                        "project": "work",
                    }
                ],
            }
        }
    }

    (backup_dir / "work.json").write_text(json.dumps(backup_payload))

    storage = Mock()
    app.dependency_overrides[get_todo_storage] = lambda: storage
    client = TestClient(app)

    try:
        bad = client.post("/api/backups/invalid.txt/restore")
        assert bad.status_code == 400

        response = client.post("/api/backups/work.json/restore")
        assert response.status_code == 200
        storage.save_project.assert_called_once()
    finally:
        app.dependency_overrides.clear()

