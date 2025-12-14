from flask import render_template_string


def test_static_url_available(app):
    """static_url should be accessible in all rendered templates."""
    with app.test_request_context():
        rendered = render_template_string("{{ static_url('css/style.css') }}")

    assert "/static/css/style.css" in rendered
