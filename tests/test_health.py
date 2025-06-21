import pytest
from sqlalchemy.exc import SQLAlchemyError
from app import db


def test_health_ok(client):
    resp = client.get('/health')
    assert resp.status_code == 200
    assert resp.data == b'ok'


def test_health_db_error(monkeypatch, client):
    def raise_error(*args, **kwargs):
        raise SQLAlchemyError("fail")
    monkeypatch.setattr(db.session, 'execute', raise_error)
    resp = client.get('/health')
    assert resp.status_code == 500
    assert resp.is_json
    assert resp.json['error'] == 'Database error'
