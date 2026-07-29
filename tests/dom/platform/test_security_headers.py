"""
Tests for security headers including Content Security Policy (CSP).
"""

def test_DOM_OPS_001__csp_header(client):
    """Verify that Content-Security-Policy header is correctly set with new directives."""
    response = client.get('/')
    assert 'Content-Security-Policy' in response.headers
    csp = response.headers['Content-Security-Policy']

    # Check for new directives by parsing CSP header
    csp_directives = {
        part.split()[0]: ' '.join(part.split()[1:])
        for part in csp.split(';')
        if part.strip()
    }

    # connect-src should contain cdn.jsdelivr.net
    assert 'connect-src' in csp_directives
    assert 'https://cdn.jsdelivr.net' in csp_directives['connect-src']

    # script-src should contain static.cloudflareinsights.com
    assert 'script-src' in csp_directives
    assert 'https://static.cloudflareinsights.com' in csp_directives['script-src']
