"""Minimal stub for pydantic-settings BaseSettings."""

from __future__ import annotations

from typing import Any


class BaseSettings:
    """Basic configuration container."""

    def __init__(self, **data: Any):
        for key, value in data.items():
            setattr(self, key, value)


__all__ = ["BaseSettings"]
