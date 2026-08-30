"""
Tests for security headers including Content Security Policy (CSP).
"""

def test_DOM_OPS_001__csp_header(client):
    """Verify that Content-Security-Policy header is correctly set with new directives."""
    response = client.get('/')
    assert 'Content-Security-Policy' in response.headers
    csp = response.headers['Content-Security-Policy']

    # Check for new directives by parsing CSP header
    csp_directives = {}
    for part in csp.split(';'):
        if part.strip():
            parts = part.strip().split()
            directive = parts[0]
            sources = parts[1:]
            csp_directives[directive] = sources

    # connect-src should contain cdn.jsdelivr.net
    assert 'connect-src' in csp_directives
    cdn_url = 'https://cdn.jsdelivr.net'
    assert cdn_url in csp_directives['connect-src']

    # script-src should contain static.cloudflareinsights.com
    assert 'script-src' in csp_directives
    insights_url = 'https://static.cloudflareinsights.com'
    assert insights_url in csp_directives['script-src']


def test_landing_page_uses_csp_compatible_local_fonts(client):
    """Verify the landing page does not request fonts blocked by its CSP."""
    response = client.get('/gh/landing.html')

    assert response.status_code == 200
    assert b'/static/css/fonts.css' in response.data
    assert b'fonts.googleapis.com' not in response.data
    assert b'fonts.gstatic.com' not in response.data
