"""Lightweight FastAPI compatibility layer for environments without fastapi."""

from __future__ import annotations

import asyncio
import inspect
import json
import types
import sys
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Optional
from urllib.parse import parse_qs, urlsplit


class HTTPException(Exception):
    """Simplified HTTPException mirroring FastAPI's interface."""

    def __init__(self, status_code: int, detail: Any = None):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail or status_code)


class Request:
    """Minimal request object provided to endpoint handlers."""

    def __init__(self, method: str, url: str, json_body: Any = None,
                 query_params: Optional[Dict[str, List[str]]] = None,
                 path_params: Optional[Dict[str, str]] = None):
        self.method = method
        self.url = url
        self._json_body = json_body
        self.query_params = query_params or {}
        self.path_params = path_params or {}

    async def json(self):  # pragma: no cover - compatibility shim
        return self._json_body


class Depends:
    """Descriptor used to declare dependencies."""

    def __init__(self, dependency: Callable[..., Any]):
        self.dependency = dependency


@dataclass
class _Route:
    path: str
    methods: Iterable[str]
    endpoint: Callable[..., Any]


class FastAPI:
    """Very small subset of FastAPI used for testing and contract verification."""

    def __init__(self, title: str | None = None, description: str | None = None, version: str | None = None):
        self.title = title
        self.description = description
        self.version = version
        self.routes: List[_Route] = []
        self.dependency_overrides: Dict[Callable[..., Any], Callable[..., Any]] = {}
        self._mounted_apps: List[Any] = []
        self._middleware: List[Any] = []

    # Route registration helpers -------------------------------------------------
    def add_api_route(self, path: str, endpoint: Callable[..., Any], methods: Optional[List[str]] = None):
        methods = methods or ["GET"]
        self.routes.append(_Route(path=path, methods=[m.upper() for m in methods], endpoint=endpoint))

    def get(self, path: str, **_kwargs):
        return self._route_decorator(path, ["GET"])

    def post(self, path: str, **_kwargs):
        return self._route_decorator(path, ["POST"])

    def put(self, path: str, **_kwargs):
        return self._route_decorator(path, ["PUT"])

    def delete(self, path: str, **_kwargs):
        return self._route_decorator(path, ["DELETE"])

    def _route_decorator(self, path: str, methods: List[str]):
        def decorator(func: Callable[..., Any]):
            self.add_api_route(path, func, methods)
            return func

        return decorator

    # Middleware & mounting ------------------------------------------------------
    def add_middleware(self, middleware_class: type, **options: Any):  # pragma: no cover - not used in tests
        self._middleware.append((middleware_class, options))

    def mount(self, _path: str, app: Any, name: Optional[str] = None):  # pragma: no cover - compatibility shim
        self._mounted_apps.append((name, app))

    # Internal helpers -----------------------------------------------------------
    def _match_route(self, method: str, path: str) -> tuple[Optional[_Route], Dict[str, str]]:
        method = method.upper()
        for route in self.routes:
            params: Dict[str, str] = {}
            if method not in route.methods:
                continue

            if route.path == path:
                return route, params

            route_segments = route.path.strip("/").split("/")
            path_segments = path.strip("/").split("/")

            if len(route_segments) != len(path_segments):
                continue

            matched = True
            for pattern, actual in zip(route_segments, path_segments):
                if pattern.startswith("{") and pattern.endswith("}"):
                    params[pattern[1:-1]] = actual
                elif pattern != actual:
                    matched = False
                    break

            if matched:
                return route, params

        return None, {}

    def _has_route_for_path(self, path: str) -> bool:
        for route in self.routes:
            if route.path == path:
                return True

            route_segments = route.path.strip("/").split("/")
            path_segments = path.strip("/").split("/")
            if len(route_segments) != len(path_segments):
                continue
            if all(rs.startswith("{") and rs.endswith("}") or rs == ps
                   for rs, ps in zip(route_segments, path_segments)):
                return True
        return False

    def _resolve_dependency(self, dependency: Depends) -> Any:
        func = dependency.dependency
        if func in self.dependency_overrides:
            func = self.dependency_overrides[func]
        return func()

    def _invoke(
        self,
        endpoint: Callable[..., Any],
        method: str,
        path: str,
        json_body: Any = None,
        path_params: Optional[Dict[str, str]] = None,
        query_params: Optional[Dict[str, List[str]]] = None,
    ):
        sig = inspect.signature(endpoint)
        kwargs: Dict[str, Any] = {}
        path_params = path_params or {}
        query_params = query_params or {}
        request_obj = Request(method, path, json_body, query_params, path_params)
        body_consumed = False

        for name, param in sig.parameters.items():
            default = param.default
            annotation = param.annotation

            if isinstance(default, Depends):
                kwargs[name] = self._resolve_dependency(default)
            elif annotation is Request or annotation == Request:
                kwargs[name] = request_obj
            elif name == "request":  # Common naming convention
                kwargs[name] = request_obj
            elif name in path_params:
                kwargs[name] = path_params[name]
            elif name in query_params:
                values = query_params[name]
                kwargs[name] = values if len(values) > 1 else values[0]
            else:
                # Pass through body for parameters named 'data' or 'body'
                if json_body is not None:
                    if (
                        not body_consumed
                        and inspect.isclass(annotation)
                        and hasattr(annotation, "__annotations__")
                    ):
                        try:
                            kwargs[name] = annotation(**json_body)
                            body_consumed = True
                            continue
                        except Exception:
                            pass

                    if name in {"data", "body", "payload"}:
                        kwargs[name] = json_body
                        body_consumed = True
                    elif name in json_body:
                        kwargs[name] = json_body[name]

        result = endpoint(**kwargs)

        if inspect.iscoroutine(result):
            return asyncio.run(result)

        return result

    def _handle_request(self, method: str, path: str, json_body: Any = None):
        parts = urlsplit(path)
        pure_path = parts.path or "/"
        query_params = parse_qs(parts.query)

        route, path_params = self._match_route(method, pure_path)
        if route is None:
            if self._has_route_for_path(pure_path):
                return _Response(status_code=405, content={"detail": "Method Not Allowed"})
            return _Response(status_code=404, content={"detail": "Not found"})

        try:
            payload = self._invoke(
                route.endpoint,
                method,
                pure_path,
                json_body=json_body,
                path_params=path_params,
                query_params=query_params,
            )
        except HTTPException as exc:  # pragma: no cover - depends on code paths
            return _Response(status_code=exc.status_code, content={"detail": exc.detail})

        payload = _serialize_payload(payload)

        if isinstance(payload, JSONResponse):
            return _Response(status_code=payload.status_code, content=payload.content)
        if isinstance(payload, HTMLResponse):  # pragma: no cover - not exercised in tests
            return _Response(status_code=payload.status_code, text=payload.content)

        return _Response(status_code=200, content=payload)


class JSONResponse:
    """Simplified JSON response."""

    def __init__(self, content: Any, status_code: int = 200):
        self.content = content
        self.status_code = status_code


class HTMLResponse:  # pragma: no cover - present for completeness
    def __init__(self, content: str, status_code: int = 200):
        self.content = content
        self.status_code = status_code


class StaticFiles:  # pragma: no cover - compatibility shim
    def __init__(self, directory: str, html: bool = False):
        self.directory = directory
        self.html = html


class Jinja2Templates:  # pragma: no cover - compatibility shim
    def __init__(self, directory: str):
        self.directory = directory

    def TemplateResponse(self, _name: str, context: Dict[str, Any]):
        return HTMLResponse(context.get("content", ""))


class CORSMiddleware:  # pragma: no cover - compatibility shim
    def __init__(self, *args, **kwargs):
        self.options = kwargs


class _Response:
    def __init__(self, status_code: int, content: Any = None, text: Optional[str] = None):
        self.status_code = status_code
        self._content = content
        if text is not None:
            self._text = text
        elif isinstance(content, (dict, list)):
            self._text = json.dumps(content)
        elif content is None:
            self._text = ""
        else:
            self._text = str(content)

    def json(self):
        if isinstance(self._content, (dict, list)):
            return self._content
        try:
            return json.loads(self._text)
        except json.JSONDecodeError:
            raise ValueError("Response content is not valid JSON")

    @property
    def text(self):
        return self._text


class TestClient:
    """Minimal test client mirroring fastapi.testclient.TestClient."""

    def __init__(self, app: FastAPI):
        self.app = app

    def get(self, path: str):
        return self.app._handle_request("GET", path)

    def post(self, path: str, json: Any = None):
        return self.app._handle_request("POST", path, json_body=json)

    def put(self, path: str, json: Any = None):
        return self.app._handle_request("PUT", path, json_body=json)

    def delete(self, path: str):
        return self.app._handle_request("DELETE", path)

    def options(self, path: str):
        return self.app._handle_request("OPTIONS", path)


# Serialization helper ---------------------------------------------------------
def _serialize_payload(payload: Any) -> Any:
    if isinstance(payload, JSONResponse):
        return payload

    if isinstance(payload, list):
        return [_serialize_payload(item) for item in payload]

    if hasattr(payload, "model_dump") or (hasattr(payload, "dict") and callable(payload.dict)):
        if hasattr(payload, "model_dump"):
            data = payload.model_dump()
        else:
            data = payload.dict()

        annotations = getattr(payload.__class__, "__annotations__", {})
        for field in annotations:
            if field not in data and hasattr(payload, field):
                data[field] = getattr(payload, field)
        return data

    return payload


# status pseudo-module -----------------------------------------------------------
status_module = types.SimpleNamespace(
    HTTP_200_OK=200,
    HTTP_201_CREATED=201,
    HTTP_204_NO_CONTENT=204,
    HTTP_400_BAD_REQUEST=400,
    HTTP_404_NOT_FOUND=404,
    HTTP_422_UNPROCESSABLE_ENTITY=422,
    HTTP_500_INTERNAL_SERVER_ERROR=500,
)


# Expose nested modules used in the project -------------------------------------
responses_module = types.ModuleType("fastapi.responses")
responses_module.HTMLResponse = HTMLResponse
responses_module.JSONResponse = JSONResponse

staticfiles_module = types.ModuleType("fastapi.staticfiles")
staticfiles_module.StaticFiles = StaticFiles

templating_module = types.ModuleType("fastapi.templating")
templating_module.Jinja2Templates = Jinja2Templates

middleware_module = types.ModuleType("fastapi.middleware")
cors_module = types.ModuleType("fastapi.middleware.cors")
cors_module.CORSMiddleware = CORSMiddleware
middleware_module.cors = cors_module

testclient_module = types.ModuleType("fastapi.testclient")
testclient_module.TestClient = TestClient

status_wrapper_module = types.ModuleType("fastapi.status")
for attr, value in vars(status_module).items():
    setattr(status_wrapper_module, attr, value)


sys.modules.setdefault("fastapi.responses", responses_module)
sys.modules.setdefault("fastapi.staticfiles", staticfiles_module)
sys.modules.setdefault("fastapi.templating", templating_module)
sys.modules.setdefault("fastapi.middleware", middleware_module)
sys.modules.setdefault("fastapi.middleware.cors", cors_module)
sys.modules.setdefault("fastapi.testclient", testclient_module)
sys.modules.setdefault("fastapi.status", status_wrapper_module)


__all__ = [
    "FastAPI",
    "Depends",
    "HTTPException",
    "Request",
    "JSONResponse",
    "HTMLResponse",
    "StaticFiles",
    "Jinja2Templates",
    "CORSMiddleware",
    "status",
    "TestClient",
]

# Provide a 'status' attribute mirroring FastAPI's layout
status = status_wrapper_module
