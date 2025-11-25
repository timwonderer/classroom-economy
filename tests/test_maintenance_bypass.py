import os
import pytest
from app import create_app

REQUIRED_ENV = {
    'SECRET_KEY': 'test-secret',
    'DATABASE_URL': 'sqlite:///:memory:',
    'FLASK_ENV': 'testing',
    'ENCRYPTION_KEY': 'x' * 32,
    'PEPPER_KEY': 'y' * 32,
}


def make_app(monkeypatch, extra_env=None):
    env = {**REQUIRED_ENV, **(extra_env or {})}
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    app = create_app()
    app.config['TESTING'] = True
    return app


def test_maintenance_normal(monkeypatch):
    app = make_app(monkeypatch, {'MAINTENANCE_MODE': 'true'})
    with app.test_client() as client:
        resp = client.get('/')
        assert resp.status_code == 503, 'Expected maintenance page (503) when active without bypass.'


def test_sysadmin_bypass(monkeypatch):
    app = make_app(monkeypatch, {
        'MAINTENANCE_MODE': 'true',
        'MAINTENANCE_SYSADMIN_BYPASS': 'true'
    })
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess['is_system_admin'] = True
        resp = client.get('/')
        assert resp.status_code != 503, 'Sysadmin bypass should allow normal access.'


def test_token_bypass(monkeypatch):
    token = 'abc123'
    app = make_app(monkeypatch, {
        'MAINTENANCE_MODE': 'true',
        'MAINTENANCE_BYPASS_TOKEN': token
    })
    with app.test_client() as client:
        resp = client.get(f'/?maintenance_bypass={token}')
        assert resp.status_code != 503, 'Token bypass should allow normal access.'


def test_invalid_token(monkeypatch):
    app = make_app(monkeypatch, {
        'MAINTENANCE_MODE': 'true',
        'MAINTENANCE_BYPASS_TOKEN': 'expected'
    })
    with app.test_client() as client:
        resp = client.get('/?maintenance_bypass=wrong')
        assert resp.status_code == 503, 'Invalid token should NOT bypass maintenance.'
