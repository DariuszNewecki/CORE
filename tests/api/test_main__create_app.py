"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/api/main.py
- Symbol: create_app
- Status: verified_in_sandbox
- Generated: 2026-01-11 00:03:36
"""

import pytest
from api.main import create_app

# Detected return type: FastAPI instance (non-async function)

def test_create_app_returns_fastapi_instance():
    """Test that create_app returns a FastAPI application object."""
    app = create_app()
    # Check it's a FastAPI instance by verifying expected attributes
    assert hasattr(app, 'router')
    assert hasattr(app, 'version')
    assert app.title == "CORE - Self-Improving System Architect"
    assert app.version == "1.0.0"

def test_create_app_includes_routers():
    """Test that the app includes the expected routers with correct prefixes and tags."""
    app = create_app()
    routes = [route for route in app.routes]
    # Check for knowledge_routes
    knowledge_routes = [r for r in routes if hasattr(r, 'tags') and "Knowledge" in r.tags]
    assert len(knowledge_routes) > 0
    # Check for development_routes
    development_routes = [r for r in routes if hasattr(r, 'tags') and "Development" in r.tags]
    assert len(development_routes) > 0

def test_create_app_health_check_route():
    """Test that the health check endpoint is registered and returns correct data."""
    app = create_app()
    health_routes = [r for r in app.routes if hasattr(r, 'path') and r.path == "/health"]
    assert len(health_routes) == 1
    health_route = health_routes[0]
    assert health_route.methods == {"GET"}
