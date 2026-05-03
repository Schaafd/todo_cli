"""Tests for refactor foundations (config + application layer)."""

import pytest

from todo_cli.application.task_commands import add_task_from_input
from todo_cli.config import ConfigModel
from todo_cli.core.errors import ValidationError
from todo_cli.storage import Storage


def test_config_round_trip_includes_refactor_flags(tmp_path):
    config = ConfigModel(
        data_dir=str(tmp_path / "data"),
        backup_dir=str(tmp_path / "backups"),
        strict_validation=True,
        log_level="DEBUG",
    )

    serialized = config.to_yaml()
    restored = ConfigModel.from_yaml(serialized)

    assert restored.strict_validation is True
    assert restored.log_level == "DEBUG"


def test_add_task_from_input_raises_validation_error_for_invalid_input(tmp_path):
    config = ConfigModel(data_dir=str(tmp_path / "data"), backup_dir=str(tmp_path / "backups"))
    storage = Storage(config)

    with pytest.raises(ValidationError):
        add_task_from_input(
            storage=storage,
            config=config,
            input_text="Broken priority example ~totallyinvalid",
            project="inbox",
        )
