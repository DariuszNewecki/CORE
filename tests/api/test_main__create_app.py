"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/api/main.py
- Symbol: create_app
- Status: 7 tests passed, some failed
- Passing tests: test_create_app_returns_fastapi_instance, test_create_app_includes_knowledge_routes, test_create_app_includes_development_routes, test_create_app_has_health_endpoint, test_create_app_exception_handlers_registered, test_create_app_multiple_calls_create_independent_instances, test_create_app_route_tags
- Generated: 2026-01-11 10:38:25
"""

import pytest
from api.main import create_app

def test_create_app_returns_fastapi_instance():
    """Test that create_app returns a FastAPI application instance."""
    app = create_app()
    assert app.title == 'CORE - Self-Improving System Architect'
    assert app.version == '1.0.0'
    assert hasattr(app, 'router')

def test_create_app_includes_knowledge_routes():
    """Test that knowledge routes are included with correct prefix and tags."""
    app = create_app()
    route_paths = [route.path for route in app.routes]
    knowledge_route_found = any((route.path.startswith('/v1') and 'knowledge' in str(route).lower() for route in app.routes))
    assert knowledge_route_found == True

def test_create_app_includes_development_routes():
    """Test that development routes are included with correct prefix and tags."""
    app = create_app()
    development_route_found = any((route.path.startswith('/v1') and 'development' in str(route).lower() for route in app.routes))
    assert development_route_found == True

def test_create_app_has_health_endpoint():
    """Test that the health check endpoint is properly registered."""
    app = create_app()
    health_route = None
    for route in app.routes:
        if hasattr(route, 'path') and route.path == '/health':
            health_route = route
            break
    assert health_route is not None
    assert health_route.methods == {'GET'}
    health_check_func = health_route.endpoint
    response = health_check_func()
    assert response == {'status': 'ok'}

def test_create_app_exception_handlers_registered():
    """Test that exception handlers are registered on the app."""
    app = create_app()
    assert hasattr(app, 'exception_handlers')

def test_create_app_multiple_calls_create_independent_instances():
    """Test that calling create_app multiple times returns independent instances."""
    app1 = create_app()
    app2 = create_app()
    assert app1 is not app2
    assert app1.title == app2.title
    assert app1.version == app2.version

def test_create_app_route_tags():
    """Test that routes have correct tags assigned."""
    app = create_app()
    knowledge_tag_found = False
    development_tag_found = False
    for route in app.routes:
        if hasattr(route, 'tags'):
            if 'Knowledge' in route.tags:
                knowledge_tag_found = True
            if 'Development' in route.tags:
                development_tag_found = True
    assert knowledge_tag_found == True
    assert development_tag_found == True
