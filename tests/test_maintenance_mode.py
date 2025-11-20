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
