
def test_csp_header(client):
    """Verify that Content-Security-Policy header is correctly set with new directives."""
    response = client.get('/')
    assert 'Content-Security-Policy' in response.headers
    csp = response.headers['Content-Security-Policy']

    # Check for new directives
    # connect-src should contain cdn.jsdelivr.net
    assert "connect-src" in csp
    assert "https://cdn.jsdelivr.net" in csp

    # script-src should contain static.cloudflareinsights.com
    assert "script-src" in csp
    assert "https://static.cloudflareinsights.com" in csp
