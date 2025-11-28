#!/usr/bin/env python3
"""
Security Headers Implementation Guide

This script provides the code to add HTTP security headers to the Flask application.
Copy the relevant sections to app/__init__.py as instructed below.

Run this script to see the recommended configuration:
    python scripts/add-security-headers.py

To test headers after implementation:
    curl -I https://yourdomain.com | grep -E "Strict-Transport|X-Frame|Content-Security"
"""

SECURITY_HEADERS_CODE = '''
# -------------------- SECURITY HEADERS --------------------
@app.after_request
def set_security_headers(response):
    """
    Add security headers to all HTTP responses.

    These headers protect against common web vulnerabilities:
    - HSTS: Force HTTPS connections
    - X-Frame-Options: Prevent clickjacking
    - X-Content-Type-Options: Prevent MIME sniffing attacks
    - CSP: Mitigate XSS attacks
    - Referrer-Policy: Control referrer information leakage

    See: https://owasp.org/www-project-secure-headers/
    """
    # Skip for static files (already have caching headers)
    if request.path.startswith('/static/'):
        return response

    # HTTPS Enforcement (HSTS)
    # Forces browsers to use HTTPS for 1 year, including subdomains
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'

    # Clickjacking Protection
    # Allows framing only from same origin (prevents iframe attacks)
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'

    # MIME Sniffing Protection
    # Prevents browsers from interpreting files as a different MIME type
    response.headers['X-Content-Type-Options'] = 'nosniff'

    # XSS Protection (legacy, but still useful for older browsers)
    # Enables browser's built-in XSS filter
    response.headers['X-XSS-Protection'] = '1; mode=block'

    # Referrer Policy
    # Only send full URL to same origin, origin only to other HTTPS sites
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'

    # Content Security Policy (CSP)
    # Restricts resource loading to prevent XSS attacks
    # Adjust based on your application's needs
    csp_directives = [
        "default-src 'self'",
        "script-src 'self' 'unsafe-inline' https://challenges.cloudflare.com",
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com",
        "font-src 'self' https://fonts.gstatic.com",
        "img-src 'self' data: https:",
        "connect-src 'self' https://challenges.cloudflare.com",
        "frame-src https://challenges.cloudflare.com",
        "base-uri 'self'",
        "form-action 'self'",
    ]
    response.headers['Content-Security-Policy'] = "; ".join(csp_directives)

    # Permissions Policy (formerly Feature-Policy)
    # Disable browser features not needed by the application
    permissions = [
        "geolocation=()",
        "microphone=()",
        "camera=()",
        "payment=()",
        "usb=()",
        "magnetometer=()",
    ]
    response.headers['Permissions-Policy'] = ", ".join(permissions)

    return response
'''

CSP_TROUBLESHOOTING = """
CSP Troubleshooting Guide
=========================

If you see console errors about Content Security Policy violations:

1. Check browser console for CSP violation reports
2. Adjust the CSP directives based on what resources your app loads
3. Common adjustments needed:

   For inline scripts (avoid if possible):
   script-src 'self' 'unsafe-inline'

   For inline styles (avoid if possible):
   style-src 'self' 'unsafe-inline'

   For external images:
   img-src 'self' https: data:

   For Google Fonts:
   style-src 'self' https://fonts.googleapis.com
   font-src 'self' https://fonts.gstatic.com

4. Test in development first, then gradually tighten in production

CSP Report-Only Mode (for testing):
    Use 'Content-Security-Policy-Report-Only' instead of 'Content-Security-Policy'
    This logs violations without blocking resources
"""

IMPLEMENTATION_STEPS = """
Implementation Steps
====================

1. Open app/__init__.py

2. Find the section after blueprint registration (around line 390-400)
   Look for: "# -------------------- BLUEPRINTS --------------------"

3. Add the security headers code AFTER the blueprints are registered
   but BEFORE "return app"

4. Test locally:
   flask run
   curl -I http://localhost:5000 | grep -E "Strict-Transport|X-Frame|Content-Security"

5. Deploy to production:
   git add app/__init__.py
   git commit -m "Add HTTP security headers for XSS and clickjacking protection"
   git push origin main

6. Verify in production:
   curl -I https://yourdomain.com | grep -E "Strict-Transport|X-Frame|Content-Security"

7. Check browser console for any CSP violations and adjust if needed

Security Checklist After Implementation:
-----------------------------------------
[ ] Strict-Transport-Security header present
[ ] X-Frame-Options header present
[ ] X-Content-Type-Options header present
[ ] Content-Security-Policy header present
[ ] No console errors from CSP violations
[ ] Application functions normally (forms, AJAX, etc.)
"""

def main():
    print("=" * 70)
    print("HTTP Security Headers Implementation")
    print("=" * 70)
    print()
    print("Copy the following code to app/__init__.py:")
    print()
    print(SECURITY_HEADERS_CODE)
    print()
    print(IMPLEMENTATION_STEPS)
    print()
    print(CSP_TROUBLESHOOTING)
    print()
    print("=" * 70)
    print("For more information:")
    print("  - OWASP Secure Headers: https://owasp.org/www-project-secure-headers/")
    print("  - CSP Guide: https://developer.mozilla.org/en-US/docs/Web/HTTP/CSP")
    print("=" * 70)

if __name__ == "__main__":
    main()
