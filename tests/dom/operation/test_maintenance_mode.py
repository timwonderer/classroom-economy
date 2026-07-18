import os


def test_health_allowed_during_maintenance(client, monkeypatch):
    monkeypatch.setenv("MAINTENANCE_MODE", "1")
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_data(as_text=True) == "ok"


def test_requests_show_maintenance_page(client, monkeypatch):
    monkeypatch.setenv("MAINTENANCE_MODE", "true")
    monkeypatch.setenv("MAINTENANCE_MESSAGE", "Routine upgrade in progress")
    monkeypatch.setenv("MAINTENANCE_EXPECTED_END", "Back at 2pm PT")
    response = client.get("/")
    assert response.status_code == 503
    body = response.get_data(as_text=True)
    assert "Scheduled Maintenance" in body
    assert "Routine upgrade in progress" in body
    assert "Back at 2pm PT" in body


def test_static_assets_not_blocked(client, monkeypatch):
    monkeypatch.setenv("MAINTENANCE_MODE", "yes")
    response = client.get("/static/favicon.ico")
    assert response.status_code in {200, 404}


def test_maintenance_badge_type_default(client, monkeypatch):
    """Test that badge_type defaults to 'maintenance' when not set."""
    monkeypatch.setenv("MAINTENANCE_MODE", "true")
    response = client.get("/")
    assert response.status_code == 503
    body = response.get_data(as_text=True)
    # Check that the default badge type is maintenance
    assert 'const badgeType = "maintenance"' in body


def test_maintenance_badge_type_bug(client, monkeypatch):
    """Test that badge_type 'bug' is rendered correctly."""
    monkeypatch.setenv("MAINTENANCE_MODE", "true")
    monkeypatch.setenv("MAINTENANCE_BADGE_TYPE", "bug")
    response = client.get("/")
    assert response.status_code == 503
    body = response.get_data(as_text=True)
    # Check that badge type is set correctly
    assert 'const badgeType = "bug"' in body
    # Verify badge config exists for bug
    assert "'bug_report'" in body or "bug_report" in body
    assert "'BUG FIX IN PROGRESS'" in body or "BUG FIX IN PROGRESS" in body


def test_maintenance_badge_type_security(client, monkeypatch):
    """Test that badge_type 'security' is rendered correctly."""
    monkeypatch.setenv("MAINTENANCE_MODE", "true")
    monkeypatch.setenv("MAINTENANCE_BADGE_TYPE", "security")
    response = client.get("/")
    assert response.status_code == 503
    body = response.get_data(as_text=True)
    # Check that badge type is set correctly
    assert 'const badgeType = "security"' in body
    # Verify badge config exists for security
    assert "'shield'" in body or "shield" in body
    assert "'SECURITY PATCH'" in body or "SECURITY PATCH" in body


def test_maintenance_badge_type_update(client, monkeypatch):
    """Test that badge_type 'update' is rendered correctly."""
    monkeypatch.setenv("MAINTENANCE_MODE", "true")
    monkeypatch.setenv("MAINTENANCE_BADGE_TYPE", "update")
    response = client.get("/")
    assert response.status_code == 503
    body = response.get_data(as_text=True)
    # Check that badge type is set correctly
    assert 'const badgeType = "update"' in body
    # Verify badge config exists for update
    assert "'system_update'" in body or "system_update" in body
    assert "'SYSTEM UPDATE'" in body or "SYSTEM UPDATE" in body


def test_maintenance_badge_type_feature(client, monkeypatch):
    """Test that badge_type 'feature' is rendered correctly."""
    monkeypatch.setenv("MAINTENANCE_MODE", "true")
    monkeypatch.setenv("MAINTENANCE_BADGE_TYPE", "feature")
    response = client.get("/")
    assert response.status_code == 503
    body = response.get_data(as_text=True)
    # Check that badge type is set correctly
    assert 'const badgeType = "feature"' in body
    # Verify badge config exists for feature
    assert "'new_releases'" in body or "new_releases" in body
    assert "'NEW FEATURE DEPLOYMENT'" in body or "NEW FEATURE DEPLOYMENT" in body


def test_maintenance_badge_type_unavailable(client, monkeypatch):
    """Test that badge_type 'unavailable' is rendered correctly."""
    monkeypatch.setenv("MAINTENANCE_MODE", "true")
    monkeypatch.setenv("MAINTENANCE_BADGE_TYPE", "unavailable")
    response = client.get("/")
    assert response.status_code == 503
    body = response.get_data(as_text=True)
    # Check that badge type is set correctly
    assert 'const badgeType = "unavailable"' in body
    # Verify badge config exists for unavailable
    assert "'cloud_off'" in body or "cloud_off" in body
    assert "'SERVER UNAVAILABLE'" in body or "SERVER UNAVAILABLE" in body


def test_maintenance_badge_type_error(client, monkeypatch):
    """Test that badge_type 'error' is rendered correctly."""
    monkeypatch.setenv("MAINTENANCE_MODE", "true")
    monkeypatch.setenv("MAINTENANCE_BADGE_TYPE", "error")
    response = client.get("/")
    assert response.status_code == 503
    body = response.get_data(as_text=True)
    # Check that badge type is set correctly
    assert 'const badgeType = "error"' in body
    # Verify badge config exists for error
    assert "'error'" in body
    assert "'UNEXPECTED ERROR'" in body or "UNEXPECTED ERROR" in body


def test_maintenance_badge_type_invalid_falls_back(client, monkeypatch):
    """Test that an invalid badge_type falls back to maintenance config in JavaScript."""
    monkeypatch.setenv("MAINTENANCE_MODE", "true")
    monkeypatch.setenv("MAINTENANCE_BADGE_TYPE", "invalid_type")
    response = client.get("/")
    assert response.status_code == 503
    body = response.get_data(as_text=True)
    # The invalid type should still be rendered but JS will fall back
    assert 'const badgeType = "invalid_type"' in body
    # Verify the fallback logic exists in JS
    assert "badgeConfig[badgeType] || badgeConfig.maintenance" in body
