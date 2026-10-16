"""ASGI entry point: the FastAPI app from cofire.api, served by uvicorn as cofire.api.main:app."""

from cofire.api import app

__all__ = ["app"]
