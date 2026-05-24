"""Storage hardening tests."""

import pytest

from todo_cli.config import ConfigModel
from todo_cli.core.errors import StorageError
from todo_cli.domain import Project, Todo
from todo_cli.storage import Storage


def test_save_project_uses_atomic_write_and_preserves_existing_file_on_replace_failure(tmp_path, monkeypatch):
    config = ConfigModel(data_dir=str(tmp_path / "data"), backup_dir=str(tmp_path / "backups"))
    storage = Storage(config)
    project = Project(name="inbox")

    assert storage.save_project(project, [Todo(id=1, text="Original task", project="inbox")])
    project_path = config.get_project_path("inbox")
    original_content = project_path.read_text(encoding="utf-8")

    def fail_replace(self, target):
        raise OSError("simulated replace failure")

    monkeypatch.setattr("pathlib.Path.replace", fail_replace)

    with pytest.raises(StorageError, match="Could not save project"):
        storage.save_project(project, [Todo(id=2, text="New task", project="inbox")])

    assert project_path.read_text(encoding="utf-8") == original_content


def test_save_project_rejects_duplicate_ids(tmp_path):
    config = ConfigModel(data_dir=str(tmp_path / "data"), backup_dir=str(tmp_path / "backups"))
    storage = Storage(config)
    project = Project(name="inbox")

    with pytest.raises(ValueError, match="Duplicate todo IDs"):
        storage.save_project(
            project,
            [
                Todo(id=1, text="First task", project="inbox"),
                Todo(id=1, text="Second task", project="inbox"),
            ],
        )


def test_delete_project_creates_backup_before_removing_file(tmp_path):
    config = ConfigModel(data_dir=str(tmp_path / "data"), backup_dir=str(tmp_path / "backups"))
    storage = Storage(config)
    project = Project(name="inbox")
    todo = Todo(id=1, text="Task to preserve", project="inbox")

    storage.save_project(project, [todo])

    assert storage.delete_project("inbox") is True

    assert not config.get_project_path("inbox").exists()
    backups = list((tmp_path / "backups").glob("*/inbox.md"))
    assert len(backups) == 1
    assert "Task to preserve" in backups[0].read_text(encoding="utf-8")


def test_load_project_raises_storage_error_for_corrupted_markdown(tmp_path):
    config = ConfigModel(data_dir=str(tmp_path / "data"), backup_dir=str(tmp_path / "backups"))
    storage = Storage(config)
    project_path = config.get_project_path("broken")
    project_path.write_text("---\nname: [unterminated\n---\n# Broken\n", encoding="utf-8")

    with pytest.raises(StorageError, match="Could not load project 'broken'"):
        storage.load_project("broken")


def test_load_missing_project_returns_empty_project(tmp_path):
    config = ConfigModel(data_dir=str(tmp_path / "data"), backup_dir=str(tmp_path / "backups"))
    storage = Storage(config)

    project, todos = storage.load_project("missing")

    assert project.name == "missing"
    assert todos == []
    assert not config.get_project_path("missing").exists()
