from app.routes.admin import _sanitize_roster_text


def test_DOM_CLASS_001__roster_text_sanitizer_strips_markup():
    assert _sanitize_roster_text("  <b>Safe</b> <script>alert(1)</script>  ") == "Safe alert(1)"


def test_DOM_CLASS_001__roster_text_sanitizer_preserves_special_name_characters():
    assert _sanitize_roster_text("O'Connor-Ana María & Co.") == "O'Connor-Ana María & Co."
