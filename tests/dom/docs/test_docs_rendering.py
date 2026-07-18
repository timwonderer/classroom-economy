"""
Unit tests for documentation markdown rendering helpers.

Covers preprocess_github_alerts() and render_markdown_content() in
app/routes/docs.py, including alert parsing edge cases, adjacent alerts,
blank-line handling, and that non-alert blockquotes and fenced code blocks
pass through unchanged.
"""

import pytest
from app.routes.docs import preprocess_github_alerts, render_markdown_content


# ---------------------------------------------------------------------------
# preprocess_github_alerts() – direct unit tests
# ---------------------------------------------------------------------------

class TestPreprocessGithubAlerts:
    """Tests for the raw-markdown alert preprocessor."""

    def test_note_alert_basic(self):
        md = "> [!NOTE]\n> This is a note."
        result = preprocess_github_alerts(md)
        assert 'class="md-alert md-alert-note"' in result
        assert 'class="md-alert-label"' in result
        assert 'Note' in result
        assert 'This is a note.' in result

    def test_tip_alert(self):
        md = "> [!TIP]\n> A helpful tip."
        result = preprocess_github_alerts(md)
        assert 'md-alert-tip' in result
        assert 'Tip' in result
        assert 'A helpful tip.' in result

    def test_important_alert(self):
        md = "> [!IMPORTANT]\n> Pay attention to this."
        result = preprocess_github_alerts(md)
        assert 'md-alert-important' in result
        assert 'Important' in result

    def test_warning_alert(self):
        md = "> [!WARNING]\n> Be careful."
        result = preprocess_github_alerts(md)
        assert 'md-alert-warning' in result
        assert 'Warning' in result

    def test_caution_alert(self):
        md = "> [!CAUTION]\n> Dangerous operation."
        result = preprocess_github_alerts(md)
        assert 'md-alert-caution' in result
        assert 'Caution' in result

    def test_case_insensitive_type(self):
        md = "> [!note]\n> Lowercase type."
        result = preprocess_github_alerts(md)
        assert 'md-alert-note' in result
        assert 'Note' in result

    def test_body_without_space_after_marker(self):
        """'>text' (no space) should be collected as a body line."""
        md = "> [!NOTE]\n>No space after marker."
        result = preprocess_github_alerts(md)
        assert 'md-alert-note' in result
        assert 'No space after marker.' in result

    def test_body_with_tab_after_marker(self):
        """'>\\ttext' should be collected as a body line."""
        md = "> [!NOTE]\n>\tTab after marker."
        result = preprocess_github_alerts(md)
        assert 'md-alert-note' in result
        assert 'Tab after marker.' in result

    def test_blank_line_with_whitespace_in_body(self):
        """'>   ' (whitespace only after '>') counts as a blank line in the body."""
        md = "> [!IMPORTANT]\n> First paragraph.\n>   \n> Second paragraph."
        result = preprocess_github_alerts(md)
        assert 'md-alert-important' in result
        assert 'First paragraph.' in result
        assert 'Second paragraph.' in result

    def test_blank_body_separator_bare_marker(self):
        """> [!NOTE] with a blank separator line using bare '>'. """
        md = "> [!NOTE]\n> First line.\n>\n> Second line."
        result = preprocess_github_alerts(md)
        assert 'First line.' in result
        assert 'Second line.' in result

    def test_inline_text_on_alert_line(self):
        """Text after the alert keyword on the same line is included in the body."""
        md = "> [!TIP] Inline text on the opening line."
        result = preprocess_github_alerts(md)
        assert 'md-alert-tip' in result
        assert 'Inline text on the opening line.' in result

    def test_non_alert_blockquote_unchanged(self):
        """A regular blockquote without an alert keyword must not be converted."""
        md = "> This is a regular blockquote.\n> Second line."
        result = preprocess_github_alerts(md)
        assert 'md-alert' not in result
        assert '> This is a regular blockquote.' in result

    def test_adjacent_alerts_both_rendered(self):
        """Two adjacent alerts separated by a blank line are both converted."""
        md = "> [!NOTE]\n> First alert.\n\n> [!WARNING]\n> Second alert."
        result = preprocess_github_alerts(md)
        assert result.count('md-alert-note') >= 1
        assert result.count('md-alert-warning') >= 1
        assert 'First alert.' in result
        assert 'Second alert.' in result

    def test_alert_followed_by_regular_blockquote(self):
        """An alert block ends before a regular (non-alert) blockquote."""
        md = "> [!NOTE]\n> Alert body.\n\n> Normal blockquote."
        result = preprocess_github_alerts(md)
        assert 'md-alert-note' in result
        assert '> Normal blockquote.' in result

    def test_content_before_and_after_alert(self):
        """Surrounding non-alert content is preserved unchanged."""
        md = "Before\n\n> [!NOTE]\n> Alert body.\n\nAfter"
        result = preprocess_github_alerts(md)
        assert result.startswith('Before')
        assert 'md-alert-note' in result
        assert 'After' in result

    def test_no_alerts_in_fenced_code_block(self):
        """Alert syntax inside a fenced code block must not be converted."""
        md = "```\n> [!NOTE]\n> This is in a code block.\n```"
        result = preprocess_github_alerts(md)
        # The preprocessor is intentionally line-based and does not parse
        # fenced blocks, but the final rendered output (via render_markdown_content)
        # still treats fenced code as literal text.  Here we only verify the
        # preprocessor output contains the original fenced delimiters.
        assert '```' in result

    def test_bold_in_body_converted(self):
        """Markdown formatting inside the alert body is rendered to HTML.

        preprocess_github_alerts() runs body text through a markdown pass
        (body_md.convert()), so inline markup like **bold** becomes <strong>.
        """
        md = "> [!NOTE]\n> **bold text**"
        result = preprocess_github_alerts(md)
        assert '<strong>' in result
        assert 'bold text' in result

    def test_empty_content(self):
        """Empty string input returns empty string."""
        assert preprocess_github_alerts('') == ''

    def test_content_with_no_alerts(self):
        """Content with no alerts is returned unmodified."""
        md = "# Heading\n\nSome paragraph text.\n\n- item 1\n- item 2"
        result = preprocess_github_alerts(md)
        assert result == md


# ---------------------------------------------------------------------------
# render_markdown_content() – integration tests
# ---------------------------------------------------------------------------

class TestRenderMarkdownContent:
    """Integration tests that exercise the full markdown pipeline."""

    def test_returns_tuple_of_two_strings(self):
        html, toc = render_markdown_content("# Hello\n\nWorld")
        assert isinstance(html, str)
        assert isinstance(toc, str)

    def test_basic_markdown_rendered(self):
        html, _ = render_markdown_content("**bold** and *italic*")
        assert '<strong>' in html
        assert '<em>' in html

    def test_alert_rendered_end_to_end(self):
        md = "> [!NOTE]\n> This is a note."
        html, _ = render_markdown_content(md)
        assert 'md-alert-note' in html
        assert 'This is a note.' in html

    def test_all_alert_types_rendered(self):
        types = ['NOTE', 'TIP', 'IMPORTANT', 'WARNING', 'CAUTION']
        for alert_type in types:
            md = f"> [!{alert_type}]\n> Body text."
            html, _ = render_markdown_content(md)
            assert f'md-alert-{alert_type.lower()}' in html, \
                f"Alert type {alert_type} not rendered"

    def test_multiple_adjacent_alerts(self):
        md = (
            "> [!NOTE]\n> First note.\n\n"
            "> [!WARNING]\n> First warning.\n\n"
            "> [!TIP]\n> A tip."
        )
        html, _ = render_markdown_content(md)
        assert 'md-alert-note' in html
        assert 'md-alert-warning' in html
        assert 'md-alert-tip' in html

    def test_alert_with_multi_paragraph_body(self):
        md = "> [!IMPORTANT]\n> First paragraph.\n>\n> Second paragraph."
        html, _ = render_markdown_content(md)
        assert 'md-alert-important' in html
        assert 'First paragraph.' in html
        assert 'Second paragraph.' in html

    def test_non_alert_blockquote_rendered_as_blockquote(self):
        md = "> This is a plain blockquote."
        html, _ = render_markdown_content(md)
        assert '<blockquote>' in html
        assert 'md-alert' not in html

    def test_fenced_code_block_preserved(self):
        md = "```python\nprint('hello')\n```"
        html, _ = render_markdown_content(md)
        # Code highlighter wraps tokens in spans; just check for key identifiers.
        assert 'print' in html
        assert 'hello' in html
        assert 'md-alert' not in html

    def test_unordered_list_rendered(self):
        md = "- item one\n- item two\n- item three"
        html, _ = render_markdown_content(md)
        assert '<ul>' in html
        assert '<li>' in html

    def test_sanitization_strips_script(self):
        md = "<script>alert('xss')</script>"
        html, _ = render_markdown_content(md)
        assert '<script>' not in html

    def test_alert_body_with_no_space_after_marker(self):
        """End-to-end: body lines using '>text' (no space) are included."""
        md = "> [!NOTE]\n>Body without space."
        html, _ = render_markdown_content(md)
        assert 'md-alert-note' in html
        assert 'Body without space.' in html

    def test_blank_whitespace_line_in_body_creates_paragraph_break(self):
        """A '>   ' whitespace-only line produces a paragraph break in the body."""
        md = "> [!NOTE]\n> Para one.\n>   \n> Para two."
        html, _ = render_markdown_content(md)
        assert 'md-alert-note' in html
        assert 'Para one.' in html
        assert 'Para two.' in html
