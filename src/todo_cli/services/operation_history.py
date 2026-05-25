"""Operation history for safe CLI undo."""

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from ..config import ConfigModel
from ..core.errors import StorageError, TaskNotFoundError, TodoCliError, ValidationError
from ..domain import Todo
from ..storage import Storage


MAX_HISTORY_RECORDS = 100


@dataclass
class OperationRecord:
    """A reversible CLI operation."""

    id: str
    operation: str
    timestamp: str
    todo_id: int
    before: Optional[dict[str, Any]] = None
    after: Optional[dict[str, Any]] = None
    before_project: Optional[str] = None
    after_project: Optional[str] = None

    @classmethod
    def create(
        cls,
        operation: str,
        *,
        todo_id: int,
        before: Optional[Todo] = None,
        after: Optional[Todo] = None,
        before_project: Optional[str] = None,
        after_project: Optional[str] = None,
    ) -> "OperationRecord":
        return cls(
            id=uuid4().hex,
            operation=operation,
            timestamp=datetime.now(timezone.utc).isoformat(),
            todo_id=todo_id,
            before=before.to_dict() if before else None,
            after=after.to_dict() if after else None,
            before_project=before_project or (before.project if before else None),
            after_project=after_project or (after.project if after else None),
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "OperationRecord":
        return cls(
            id=data["id"],
            operation=data["operation"],
            timestamp=data["timestamp"],
            todo_id=int(data["todo_id"]),
            before=data.get("before"),
            after=data.get("after"),
            before_project=data.get("before_project"),
            after_project=data.get("after_project"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "operation": self.operation,
            "timestamp": self.timestamp,
            "todo_id": self.todo_id,
            "before": self.before,
            "after": self.after,
            "before_project": self.before_project,
            "after_project": self.after_project,
        }


class OperationHistory:
    """Persist and replay reversible operations."""

    def __init__(self, config: ConfigModel):
        self.path = Path(config.data_dir) / "operation_history.json"

    def append(self, record: OperationRecord) -> None:
        records = self.list_records()
        records.append(record)
        self._write_records(records[-MAX_HISTORY_RECORDS:])

    def list_records(self) -> list[OperationRecord]:
        if not self.path.exists():
            return []

        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return [OperationRecord.from_dict(item) for item in data.get("records", [])]
        except Exception as e:
            raise StorageError(
                f"Could not read operation history: {e}",
                suggestion="Check the operation_history.json file or move it aside.",
            ) from e

    def undo_last(self, storage: Storage) -> OperationRecord:
        records = self.list_records()
        if not records:
            raise ValidationError("Nothing to undo.")

        record = records[-1]
        self._undo_record(record, storage)
        self._write_records(records[:-1])
        return record

    def _write_records(self, records: list[OperationRecord]) -> None:
        payload = {
            "version": 1,
            "records": [record.to_dict() for record in records],
        }
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = self.path.with_name(f".{self.path.name}.tmp")
            tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
            tmp_path.replace(self.path)
        except Exception as e:
            raise StorageError(
                f"Could not write operation history: {e}",
                suggestion="Check data directory permissions and available disk space.",
            ) from e

    def _undo_record(self, record: OperationRecord, storage: Storage) -> None:
        if record.operation == "add":
            self._undo_add(record, storage)
        elif record.operation in {"done", "edit"}:
            self._restore_before(record, storage)
        elif record.operation == "delete":
            self._restore_deleted(record, storage)
        else:
            raise TodoCliError(f"Cannot undo operation '{record.operation}'.")

    def _undo_add(self, record: OperationRecord, storage: Storage) -> None:
        project_name = record.after_project
        if not project_name:
            raise TodoCliError("Cannot undo add because the project is missing from history.")

        project, todos = storage.load_project(project_name)
        assert project is not None
        remaining = [todo for todo in todos if todo.id != record.todo_id]
        if len(remaining) == len(todos):
            raise TaskNotFoundError(record.todo_id, project=project_name)
        storage.save_project(project, remaining)

    def _restore_before(self, record: OperationRecord, storage: Storage) -> None:
        if not record.before or not record.before_project:
            raise TodoCliError("Cannot undo operation because prior task state is missing.")

        before_todo = Todo.from_dict(record.before)
        before_todo.project = record.before_project
        self._remove_task(record.todo_id, record.after_project or record.before_project, storage)
        self._upsert_task(before_todo, record.before_project, storage)

    def _restore_deleted(self, record: OperationRecord, storage: Storage) -> None:
        if not record.before or not record.before_project:
            raise TodoCliError("Cannot undo delete because deleted task state is missing.")

        existing = storage.get_todo(record.todo_id)
        if existing is not None:
            raise TodoCliError(
                f"Cannot restore task {record.todo_id} because that ID already exists.",
                suggestion="Resolve the duplicate task ID before retrying undo.",
            )

        todo = Todo.from_dict(record.before)
        todo.project = record.before_project
        self._upsert_task(todo, record.before_project, storage)

    def _remove_task(self, todo_id: int, project_name: str, storage: Storage) -> None:
        project, todos = storage.load_project(project_name)
        assert project is not None
        remaining = [todo for todo in todos if todo.id != todo_id]
        if len(remaining) != len(todos):
            storage.save_project(project, remaining)

    def _upsert_task(self, todo: Todo, project_name: str, storage: Storage) -> None:
        project, todos = storage.load_project(project_name)
        assert project is not None
        for index, existing in enumerate(todos):
            if existing.id == todo.id:
                todos[index] = todo
                break
        else:
            todos.append(todo)
        storage.save_project(project, todos)
