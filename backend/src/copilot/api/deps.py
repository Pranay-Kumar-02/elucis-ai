"""Shared FastAPI dependencies."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from copilot.core.config import Settings


def get_app_settings(request: Request) -> Settings:
    """The settings the running app was created with (``create_app(settings)``).

    Routes use this instead of the global ``get_settings()`` so tests and tools can run an
    app with explicit settings without touching the environment.
    """
    settings: Settings = request.app.state.settings
    return settings


SettingsDep = Annotated[Settings, Depends(get_app_settings)]
