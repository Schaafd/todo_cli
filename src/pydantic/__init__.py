"""Minimal subset of Pydantic used for testing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Callable
import copy


class BaseModel:
    """Very small emulation of pydantic.BaseModel."""

    def __init__(self, **data: Any):
        annotations = getattr(self.__class__, "__annotations__", {})
        for field in annotations:
            default = getattr(self.__class__, field, None)
            if isinstance(default, (list, dict, set)):
                default = copy.deepcopy(default)
            if not hasattr(self, field):
                setattr(self, field, default)

        for key, value in data.items():
            setattr(self, key, value)

    def model_dump(self) -> Dict[str, Any]:
        return {key: value for key, value in self.__dict__.items() if not key.startswith("_")}

    def dict(self) -> Dict[str, Any]:  # pragma: no cover - compatibility alias
        return self.model_dump()


def Field(default: Any = None, **_kwargs: Any) -> Any:
    """Return default value; metadata is ignored in this lightweight shim."""

    return default


def validator(*_args: Any, **_kwargs: Any):  # pragma: no cover - compatibility shim
    def decorator(func: Callable[..., Any]):
        return func

    return decorator


__all__ = ["BaseModel", "Field", "validator"]
