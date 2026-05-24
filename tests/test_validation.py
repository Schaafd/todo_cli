"""Input validation tests."""

import pytest

from todo_cli.config import ConfigModel
from todo_cli.core.errors import ValidationError
from todo_cli.domain import Todo
from todo_cli.storage import Storage
from todo_cli.validation import (
    MAX_TASK_TEXT_LENGTH,
    validate_name_tokens,
    validate_project_name,
    validate_task_text,
    validate_todo_id,
)


def test_validate_task_text_rejects_empty_text():
    with pytest.raises(ValidationError, match="Task text cannot be empty"):
        validate_task_text("   ")


def test_validate_task_text_rejects_overlong_text():
    with pytest.raises(ValidationError, match="Task text is too long"):
        validate_task_text("x" * (MAX_TASK_TEXT_LENGTH + 1))


def test_validate_project_name_rejects_path_traversal():
    with pytest.raises(ValidationError, match="Invalid project name"):
        validate_project_name("../outside")


def test_validate_name_tokens_rejects_whitespace():
    with pytest.raises(ValidationError, match="Invalid tag"):
        validate_name_tokens(["needs review"], field_name="tag")


def test_validate_todo_id_requires_positive_integer():
    with pytest.raises(ValidationError, match="must be a positive integer"):
        validate_todo_id(0)


def test_storage_rejects_invalid_project_name_before_path_use(tmp_path):
    config = ConfigModel(data_dir=str(tmp_path / "data"), backup_dir=str(tmp_path / "backups"))
    storage = Storage(config)

    with pytest.raises(ValidationError, match="Invalid project name"):
        storage.load_project("../outside")


def test_todo_datetime_validation_method_is_available():
    todo = Todo(id=1, text="Check datetime validation")

    result = todo.validate_datetimes()

    assert result["valid"] is True
