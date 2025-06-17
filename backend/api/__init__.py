"""
API module for Maximo OAuth.
"""
from backend.api.routes import init_api
from backend.api.sync_routes import init_sync_routes

__all__ = ['init_api', 'init_sync_routes']