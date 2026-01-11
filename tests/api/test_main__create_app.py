"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/api/main.py
- Symbol: create_app
- Status: verified_in_sandbox
- Generated: 2026-01-11 00:47:08
"""

import pytest
from api.main import create_app

# Detected return type: FastAPI instance

def test_create_app_returns_fastapi_instance():
    app = create_app()
    # Check it's a FastAPI instance by verifying expected attributes
    assert hasattr(app, 'router')
    assert hasattr(app, 'version')
    assert app.title == "CORE - Self-Improving System Architect"
    assert app.version == "1.0.0"

def test_create_app_includes_knowledge_router():
    app = create_app()
    routes = [route for route in app.routes if hasattr(route, 'tags') and "Knowledge" in route.tags]
    assert len(routes) > 0

def test_create_app_includes_development_router():
    app = create_app()
    routes = [route for route in app.routes if hasattr(route, 'tags') and "Development" in route.tags]
    assert len(routes) > 0

def test_create_app_registers_health_endpoint():
    app = create_app()
    health_routes = [route for route in app.routes if hasattr(route, 'path') and route.path == "/health"]
    assert len(health_routes) == 1
    health_route = health_routes[0]
    assert health_route.methods == {"GET"}
