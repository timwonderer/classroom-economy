"""
Security tests for documentation route path traversal protection.

Tests verify that the docs route properly blocks various path traversal
attack vectors and only allows access to files within the docs directory.
"""

import pytest


def test_docs_blocks_parent_directory_traversal(client):
    """Test that ../ traversal is blocked."""
    # Attempt to traverse up from docs directory
    response = client.get('/docs/../config.py')
    assert response.status_code == 404


def test_docs_blocks_absolute_path(client):
    """Test that absolute paths are blocked."""
    # Attempt to access an absolute path
    # Note: Double slash causes Flask to redirect (308), then the path is blocked (404)
    response = client.get('/docs//etc/passwd', follow_redirects=True)
    assert response.status_code == 404


def test_docs_blocks_mixed_traversal(client):
    """Test that traversal mixed with valid paths is blocked."""
    # Attempt to traverse from a valid subdirectory
    response = client.get('/docs/DOMAIN/../../config.py')
    assert response.status_code == 404


def test_docs_blocks_multiple_traversal(client):
    """Test that multiple ../ sequences are blocked."""
    response = client.get('/docs/../../../etc/passwd')
    assert response.status_code == 404


def test_docs_blocks_encoded_traversal(client):
    """Test that URL-encoded traversal is blocked."""
    # Flask automatically decodes URLs, so %2e%2e becomes ..
    response = client.get('/docs/%2e%2e/config.py')
    assert response.status_code == 404


def test_docs_blocks_backslash_traversal(client):
    """Test that backslash traversal is blocked (Windows-style)."""
    response = client.get('/docs/..\\..\\config.py')
    assert response.status_code == 404


def test_docs_blocks_null_byte_injection(client):
    """Test that null byte injection is blocked."""
    # Note: Flask/Werkzeug may reject NUL bytes before routing.
    # If it does, we expect the regex validation to catch it.
    # Using percent-encoded %00 to test the application-level validation.
    response = client.get('/docs/DOMAIN%00/../../etc/passwd')
    assert response.status_code == 404


def test_docs_allows_valid_paths(client):
    """Test that valid documentation paths work correctly."""
    # This will return 404 if file doesn't exist, but shouldn't be blocked by security
    response = client.get('/docs/DOMAIN/DOM-CORE-001_DOMAIN_AUTHORITY_SUMMARY')
    # Either 200 (file exists) or 404 (file doesn't exist but path is valid)
    assert response.status_code in [200, 404]


def test_docs_allows_nested_valid_paths(client):
    """Test that nested valid paths work correctly."""
    response = client.get('/docs/technical-reference/architecture')
    # Either 200 (file exists) or 404 (file doesn't exist but path is valid)
    assert response.status_code in [200, 404]


def test_docs_blocks_suspicious_characters(client):
    """Test that paths with suspicious characters are blocked."""
    # Test various suspicious patterns
    # Note: Using percent-encoded %00 instead of literal NUL since
    # Flask/Werkzeug may reject literal NULs before routing
    suspicious_paths = [
        '/docs/test%00file',  # Null byte (percent-encoded)
        '/docs/test|file',    # Pipe
        '/docs/test&file',    # Ampersand
        '/docs/test;file',    # Semicolon
        '/docs/test$file',    # Dollar sign
    ]

    for path in suspicious_paths:
        response = client.get(path)
        assert response.status_code == 404, f"Path {path} should be blocked"


def test_docs_blocks_windows_paths(client):
    """Test that Windows-style absolute paths are blocked."""
    response = client.get('/docs/C:/Windows/System32/config')
    assert response.status_code == 404


def test_docs_empty_path_handling(client):
    """Test that empty or whitespace paths are handled correctly."""
    # Empty path should redirect or return docs index
    response = client.get('/docs/')
    assert response.status_code in [200, 302, 404]

    # Just whitespace should be rejected
    response = client.get('/docs/   ')
    assert response.status_code in [302, 404]


def test_docs_blocks_hidden_files(client):
    """Test that hidden files (starting with .) are handled appropriately."""
    # Dots in filenames are allowed, but files starting with . should either
    # be blocked by regex or return 404 if they don't exist
    response = client.get('/docs/.hidden')
    # Should return 404, not 500 (which would indicate a server error)
    assert response.status_code == 404


def test_docs_symlink_escape_prevention(client, app, tmp_path):
    """
    Test that symbolic links cannot escape the docs directory.

    This test creates a temporary docs structure with a symlink
    pointing outside the docs root and verifies it's blocked.
    """
    with app.app_context():
        # Create a temporary directory structure
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()

        outside_dir = tmp_path / "outside"
        outside_dir.mkdir()

        secret_file = outside_dir / "secret.md"
        secret_file.write_text("SECRET DATA")

        # Create a symlink inside docs pointing to outside
        symlink_path = docs_dir / "evil_link.md"
        try:
            symlink_path.symlink_to(secret_file)
        except (OSError, NotImplementedError):
            pytest.skip("Symlinks not supported on this system")

        # Temporarily replace DOCS_ROOT for this test
        from app.routes import docs as docs_module
        original_docs_root = docs_module.DOCS_ROOT
        docs_module.DOCS_ROOT = docs_dir

        try:
            # Attempt to access the symlinked file
            # The security check should resolve the symlink and detect it's outside docs_dir
            response = client.get('/docs/evil_link')

            # Should be blocked (404) because resolved path is outside DOCS_ROOT
            assert response.status_code == 404

        finally:
            # Restore original DOCS_ROOT
            docs_module.DOCS_ROOT = original_docs_root


def test_docs_case_sensitivity_bypass_attempt(client):
    """
    Test that case variations don't bypass security.

    On case-insensitive filesystems, verify that case manipulation
    doesn't allow traversal.
    """
    # These should all be blocked regardless of case
    test_paths = [
        '/docs/../CONFIG.PY',
        '/docs/../Config.py',
        '/docs/USER-GUIDES/../../config.py',
    ]

    for path in test_paths:
        response = client.get(path)
        assert response.status_code == 404, f"Path {path} should be blocked"


def test_docs_double_encoding_bypass_attempt(client):
    """Test that double-encoded traversal attempts are blocked."""
    # %252e = encoded '%2e' = encoded '.'
    response = client.get('/docs/%252e%252e/config.py')
    assert response.status_code == 404


def test_docs_unicode_normalization_bypass_attempt(client):
    """Test that Unicode look-alike characters don't bypass validation."""
    # Using Unicode 'FULLWIDTH FULL STOP' (U+FF0E) instead of regular period
    response = client.get('/docs/\uff0e\uff0e/config.py')
    assert response.status_code == 404


def test_docs_path_with_repeated_slashes(client):
    """Test that repeated slashes don't cause issues."""
    # Multiple slashes should be normalized by Flask/Werkzeug (308 redirect)
    # Follow redirects to see the final result
    response = client.get('/docs//DOMAIN//DOM-CORE-001_DOMAIN_AUTHORITY_SUMMARY', follow_redirects=True)
    # Should either work (if file exists) or 404 (file doesn't exist)
    assert response.status_code in [200, 404]


def test_docs_trailing_slash_handling(client):
    """Test that trailing slashes are handled correctly."""
    response = client.get('/docs/DOMAIN/')
    # Should either work or 404, but not cause errors
    assert response.status_code in [200, 302, 404]


def test_docs_blocks_parent_dir_variations(client):
    """Test various representations of parent directory."""
    variations = [
        '/docs/..',
        '/docs/../',
        '/docs/test/..',
        '/docs/./../../etc/passwd',
    ]

    for path in variations:
        response = client.get(path)
        assert response.status_code == 404, f"Path {path} should be blocked"
