import logging

from app import create_app


def test_unhandled_exception_logs_request_id_and_route(caplog):
    app = create_app()
    app.config.update(TESTING=True, PROPAGATE_EXCEPTIONS=False)

    @app.route("/_boom")
    def _boom():
        raise RuntimeError("boom")

    caplog.set_level(logging.ERROR, logger=app.logger.name)

    with app.test_client() as client:
        response = client.get("/_boom", headers={"X-Request-Id": "test-request-id"})

    assert response.status_code == 500
    assert response.headers.get("X-Request-Id") == "test-request-id"

    matching_records = [
        record
        for record in caplog.records
        if record.getMessage() == "Unhandled exception"
    ]
    assert matching_records, "Expected an Unhandled exception log entry."

    record = matching_records[0]
    assert getattr(record, "route", None) == "/_boom"
    assert getattr(record, "method", None) == "GET"
    assert getattr(record, "request_id", None) == "test-request-id"
