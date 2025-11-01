"""Minimal httpx compatibility layer for testing."""

from __future__ import annotations

from typing import Any, Dict, Optional


class RequestError(Exception):
    """Raised when a request fails."""


class TimeoutException(RequestError):
    """Raised when a request times out."""


class Response:
    def __init__(self, status_code: int = 200, json_data: Optional[Any] = None, text: str = ""):
        self.status_code = status_code
        self._json_data = json_data if json_data is not None else {}
        self.text = text or ""

    def json(self) -> Any:
        return self._json_data


class AsyncClient:
    """Simplified async HTTP client that returns empty responses."""

    def __init__(self, timeout: float = 30.0):
        self.timeout = timeout
        self._closed = False

    async def get(self, *_args: Any, **_kwargs: Any) -> Response:
        return Response()

    async def post(self, *_args: Any, **_kwargs: Any) -> Response:
        return Response()

    async def put(self, *_args: Any, **_kwargs: Any) -> Response:
        return Response()

    async def delete(self, *_args: Any, **_kwargs: Any) -> Response:
        return Response(status_code=204)

    async def aclose(self) -> None:
        self._closed = True


__all__ = [
    "AsyncClient",
    "Response",
    "RequestError",
    "TimeoutException",
]
