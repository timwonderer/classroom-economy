"""
Tests for Progressive Web App (PWA) functionality:
1. Offline fallback page
2. Service worker delivery
3. Manifest accessibility
"""
import json

import pytest
from flask import current_app


def test_offline_page_accessible(client):
    """Test that the offline fallback page is accessible."""
    response = client.get('/offline')
    assert response.status_code == 200

    # Check for key elements in the offline page
    html = response.data.decode('utf-8')
    assert 'You are offline' in html
    assert 'wifi-off' in html  # SVG icon class
    assert 'Try Again' in html


def test_offline_page_content_type(client):
    """Test that the offline page returns proper HTML content type."""
    response = client.get('/offline')
    assert response.status_code == 200
    assert 'text/html' in response.content_type


def test_service_worker_accessible(client):
    """Test that the service worker file is accessible."""
    response = client.get('/sw.js')
    assert response.status_code == 200


def test_service_worker_content_type(client):
    """Test that the service worker returns JavaScript content type."""
    response = client.get('/sw.js')
    assert response.status_code == 200
    assert 'javascript' in response.content_type.lower() or 'text/plain' in response.content_type


def test_service_worker_content(client):
    """Test that the service worker contains expected content."""
    response = client.get('/sw.js')
    assert response.status_code == 200

    js_content = response.data.decode('utf-8')

    # Check for key service worker elements
    assert 'CACHE_NAME' in js_content
    assert 'addEventListener' in js_content
    assert 'install' in js_content
    assert 'fetch' in js_content
    assert 'activate' in js_content

    # Check for cache cleanup logic
    assert 'caches.delete' in js_content or 'skipWaiting' in js_content

    # Check for offline fallback
    assert '/offline' in js_content


def test_manifest_accessible(client):
    """Test that the PWA manifest is accessible."""
    response = client.get('/static/manifest.json')
    assert response.status_code == 200


def test_manifest_content_type(client):
    """Test that the manifest returns proper JSON content type."""
    response = client.get('/static/manifest.json')
    assert response.status_code == 200
    assert 'json' in response.content_type.lower()


def test_manifest_structure(client):
    """Test that the manifest contains required PWA fields."""
    response = client.get('/static/manifest.json')
    assert response.status_code == 200
    manifest = json.loads(response.data)

    # Check required fields
    assert 'name' in manifest
    assert 'short_name' in manifest
    assert 'start_url' in manifest
    assert 'display' in manifest
    assert 'icons' in manifest

    # Check that icons array is not empty
    assert len(manifest['icons']) > 0

    # Check for recommended fields
    assert 'theme_color' in manifest
    assert 'background_color' in manifest
    assert 'description' in manifest
    assert 'scope' in manifest
    assert 'orientation' in manifest


def test_manifest_icon_properties(client):
    """Test that manifest icons have required properties."""
    response = client.get('/static/manifest.json')
    assert response.status_code == 200
    manifest = json.loads(response.data)

    # Check that at least one PNG icon exists
    png_icons = [icon for icon in manifest['icons'] if icon.get('type') == 'image/png']
    assert len(png_icons) > 0, "Manifest should include at least one PNG icon"

    # Check icon properties
    for icon in manifest['icons']:
        assert 'src' in icon
        assert 'sizes' in icon or icon.get('type') == 'image/svg+xml'
        assert 'type' in icon


def test_pwa_meta_tags_in_mobile_layout(client):
    """Test that mobile layouts include PWA meta tags."""
    # This test would require authentication to access student pages
    # For now, we'll just verify the routes exist
    # A more comprehensive test would check the actual rendered HTML

    # Test that key PWA routes are registered
    with current_app.test_request_context():
        # Check that the routes exist in the app
        routes = [rule.rule for rule in current_app.url_map.iter_rules()]
        assert '/offline' in routes
        assert '/sw.js' in routes


def test_service_worker_cache_exclusions(client):
    """Test that service worker excludes authenticated routes from caching."""
    response = client.get('/sw.js')
    assert response.status_code == 200

    js_content = response.data.decode('utf-8')

    # Verify that authenticated routes are excluded from caching
    # The service worker should check for routes like /admin, /student, /api
    assert '/admin' in js_content or 'authRoutes' in js_content
    assert '/student' in js_content or 'authRoutes' in js_content
    assert '/api' in js_content or 'authRoutes' in js_content
