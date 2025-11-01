"""Minimal stub of uvicorn for testing environments."""

from __future__ import annotations

from typing import Any


def run(app: Any, host: str = "127.0.0.1", port: int = 8000, **_kwargs: Any) -> None:  # pragma: no cover - helper stub
    print(f"uvicorn.run called for {app} on {host}:{port}")


__all__ = ["run"]
