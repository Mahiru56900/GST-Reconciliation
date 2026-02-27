"""Minimal FastAPI-compatible shim for offline environments.

Implements only symbols used by this repository.
"""

from __future__ import annotations


class HTTPException(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def Query(default=None, **_kwargs):
    return default


class FastAPI:
    def __init__(self, title: str = "App", version: str = "0.0.0"):
        self.title = title
        self.version = version
        self.routes = []

    def get(self, path: str):
        def decorator(func):
            self.routes.append(("GET", path, func.__name__))
            return func

        return decorator
