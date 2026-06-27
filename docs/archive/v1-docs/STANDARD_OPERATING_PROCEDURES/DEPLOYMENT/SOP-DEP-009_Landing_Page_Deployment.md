# Landing Page Deployment Guide

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
|SOP-DEP-009| 1.1 | 2026-03-08 | 1.0 |Normative|

**Version:** 1.7.0
**Last Updated:** January 9, 2026

---

## I. Purpose

TBD
## II. Scope

TBD
## III. Authority Level
Normative. Subordinate to CORE invariant definitions.
## IV. Dependencies
None specified.
## V. Overview

The Classroom Token Hub landing page is hosted on **GitHub Pages** but served at the root of your custom domain `classroomtokenhub.com`. This setup provides:

- **High availability**: Landing page stays up even if Flask server goes down
- **Fast loading**: GitHub's CDN serves static content
- **Easy updates**: Push to `main` branch to update landing page
- **Clean URLs**: Users see `classroomtokenhub.com`, not `github.io`

---

## VI. Architecture

```
User visits classroomtokenhub.com
  ↓
[Web Server: Nginx/Apache]
  ↓
  ├─ / (root) → Proxy to GitHub Pages (landing page)
  ├─ /student/* → Proxy to Flask app
  ├─ /admin/* → Proxy to Flask app
  ├─ /sysadmin/* → Proxy to Flask app
  └─ /api/* → Proxy to Flask app
```

**GitHub Pages URL:** `https://timwonderer.github.io/classroom-economy/`
**Custom Domain:** `https://classroomtokenhub.com`
**Flask App:** Running on localhost or internal port

---

## VII. Option 1: Nginx Configuration (Recommended)

### Full Nginx Config

```nginx
server {
    listen 80;
    listen [::]:80;
    server_name classroomtokenhub.com www.classroomtokenhub.com;

    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name classroomtokenhub.com www.classroomtokenhub.com;

    # SSL Configuration
    ssl_certificate /etc/letsencrypt/live/classroomtokenhub.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/classroomtokenhub.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    # Root path - Proxy to GitHub Pages for landing page
    location = / {
        proxy_pass https://timwonderer.github.io/classroom-economy/;
        proxy_ssl_server_name on;
        proxy_set_header Host timwonderer.github.io;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Cache GitHub Pages content
        proxy_cache_valid 200 10m;
        proxy_cache_bypass $http_pragma;
    }

    # Flask app routes
    location ~ ^/(student|admin|sysadmin|api|health|privacy|terms|hall-pass|debug|switch-view) {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket support (if needed)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    # Static files for Flask app
    location /static {
        proxy_pass http://127.0.0.1:5000/static;
        proxy_set_header Host $host;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # Service worker
    location /sw.js {
        proxy_pass http://127.0.0.1:5000/sw.js;
        proxy_set_header Host $host;
        add_header Cache-Control "no-cache, no-store, must-revalidate";
    }

    # Logging
    access_log /var/log/nginx/classroomtokenhub_access.log;
    error_log /var/log/nginx/classroomtokenhub_error.log;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
}
```

### Testing Nginx Config

```bash
# Test configuration
sudo nginx -t

# Reload Nginx
sudo systemctl reload nginx

# Check status
sudo systemctl status nginx
```

---

## VIII. Option 2: Apache Configuration

### Apache VirtualHost Config

```apache
<VirtualHost *:80>
    ServerName classroomtokenhub.com
    ServerAlias www.classroomtokenhub.com

    # Redirect to HTTPS
    Redirect permanent / https://classroomtokenhub.com/
</VirtualHost>

<VirtualHost *:443>
    ServerName classroomtokenhub.com
    ServerAlias www.classroomtokenhub.com

    # SSL Configuration
    SSLEngine on
    SSLCertificateFile /etc/letsencrypt/live/classroomtokenhub.com/fullchain.pem
    SSLCertificateKeyFile /etc/letsencrypt/live/classroomtokenhub.com/privkey.pem

    # Enable proxy modules
    # Run: sudo a2enmod proxy proxy_http proxy_wstunnel headers rewrite ssl

    # Root path - Proxy to GitHub Pages
    <Location "/">
        ProxyPass https://timwonderer.github.io/classroom-economy/
        ProxyPassReverse https://timwonderer.github.io/classroom-economy/
        ProxyPreserveHost Off
        RequestHeader set Host "timwonderer.github.io"
    </Location>

    # Flask app routes
    ProxyPass /student http://127.0.0.1:5000/student
    ProxyPassReverse /student http://127.0.0.1:5000/student

    ProxyPass /admin http://127.0.0.1:5000/admin
    ProxyPassReverse /admin http://127.0.0.1:5000/admin

    ProxyPass /sysadmin http://127.0.0.1:5000/sysadmin
    ProxyPassReverse /sysadmin http://127.0.0.1:5000/sysadmin

    ProxyPass /api http://127.0.0.1:5000/api
    ProxyPassReverse /api http://127.0.0.1:5000/api

    ProxyPass /static http://127.0.0.1:5000/static
    ProxyPassReverse /static http://127.0.0.1:5000/static

    ProxyPass /health http://127.0.0.1:5000/health
    ProxyPassReverse /health http://127.0.0.1:5000/health

    # Logging
    ErrorLog ${APACHE_LOG_DIR}/classroomtokenhub_error.log
    CustomLog ${APACHE_LOG_DIR}/classroomtokenhub_access.log combined

    # Security headers
    Header always set X-Frame-Options "SAMEORIGIN"
    Header always set X-Content-Type-Options "nosniff"
    Header always set X-XSS-Protection "1; mode=block"
    Header always set Strict-Transport-Security "max-age=31536000; includeSubDomains"
</VirtualHost>
```

### Testing Apache Config

```bash
# Test configuration
sudo apache2ctl configtest

# Reload Apache
sudo systemctl reload apache2

# Check status
sudo systemctl status apache2
```

---

## IX. Option 3: Cloudflare Workers (Advanced)

If using Cloudflare, you can use Workers to route traffic:

```javascript
addEventListener('fetch', event => {
  event.respondWith(handleRequest(event.request))
})

async function handleRequest(request) {
  const url = new URL(request.url)

  // Root path - serve GitHub Pages
  if (url.pathname === '/') {
    return fetch('https://timwonderer.github.io/classroom-economy/', {
      headers: request.headers
    })
  }

  // App routes - proxy to Flask server
  if (url.pathname.startsWith('/student') ||
      url.pathname.startsWith('/admin') ||
      url.pathname.startsWith('/sysadmin') ||
      url.pathname.startsWith('/api') ||
      url.pathname.startsWith('/static')) {

    // Replace with your Flask server URL
    const flaskUrl = 'https://your-flask-server.com' + url.pathname + url.search
    return fetch(flaskUrl, {
      method: request.method,
      headers: request.headers,
      body: request.body
    })
  }

  // Default - pass through to Flask
  return fetch(request)
}
```

---

## X. Testing the Setup

### 1. Test Landing Page

Visit: `https://classroomtokenhub.com/`

**Expected:**

- ✅ Landing page loads
- ✅ Shows v1.7.0 version badge
- ✅ All sections visible (features, screenshots, sign-in)
- ✅ No console errors

### 2. Test Sign-In Links

Click "Sign In as Student":

**Expected:**

- ✅ Redirects to `/student/login`
- ✅ Flask app login page loads
- ✅ URL shows `classroomtokenhub.com/student/login`

Repeat for Teacher and Admin sign-in.

### 3. Test Direct Routes

Visit directly: `https://classroomtokenhub.com/student/login`

**Expected:**

- ✅ Flask login page loads
- ✅ Can log in successfully

### 4. Test Health Check

Visit: `https://classroomtokenhub.com/health`

**Expected:**

- ✅ Shows "ok"
- ✅ 200 status code

---

## XI. Troubleshooting

### Issue: Landing page shows 404

**Cause:** GitHub Pages not deployed or proxy misconfigured

**Fix:**

1. Verify GitHub Pages is enabled: `Settings` → `Pages` → Source: `main` branch, `/docs` folder
2. Check deployment: https://github.com/timwonderer/classroom-economy/actions
3. Test GitHub Pages directly: https://timwonderer.github.io/classroom-economy/
4. Check Nginx proxy_pass URL matches GitHub Pages URL

### Issue: Sign-in links don't work

**Cause:** Flask app routes not proxied correctly

**Fix:**

1. Check Flask app is running: `systemctl status classroom-economy`
2. Test Flask directly: `curl http://127.0.0.1:5000/student/login`
3. Check Nginx location blocks match all Flask routes
4. Check firewall allows port 5000

### Issue: CSS/images not loading

**Cause:** Static files not proxied

**Fix:**

1. Check `/static` location block in Nginx
2. Verify Flask static folder exists
3. Check file permissions: `ls -la app/static/`

### Issue: Mixed content warnings (HTTP/HTTPS)

**Cause:** Some resources loaded over HTTP

**Fix:**

1. Ensure all internal links use relative paths (`/path` not `http://domain/path`)
2. Check `proxy_set_header X-Forwarded-Proto $scheme;` in Nginx config
3. Verify Flask respects `X-Forwarded-Proto` header

---

## XII. Updating the Landing Page

When you want to update the landing page:

1. **Edit:** `docs/index.html`
2. **Commit:** `git add docs/index.html && git commit -m "Update landing page"`
3. **Push:** `git push origin main`
4. **Wait:** GitHub Actions deploys automatically (2-3 minutes)
5. **Verify:** Visit `classroomtokenhub.com` to see changes

**No server restart needed** - GitHub Pages updates automatically!

---

## XIII. Alternative: Simple Nginx Landing Page Fallback

If GitHub Pages proxying doesn't work, you can copy `index.html` to your server:

```nginx
server {
    listen 443 ssl http2;
    server_name classroomtokenhub.com;

    # Serve local copy of landing page
    root /var/www/landing;
    index index.html;

    location = / {
        try_files /index.html =404;
    }

    # Flask routes (same as before)
    location ~ ^/(student|admin|sysadmin|api) {
        proxy_pass http://127.0.0.1:5000;
        # ... proxy config
    }
}
```

**Setup:**
```bash
sudo mkdir -p /var/www/landing
sudo cp docs/index.html /var/www/landing/
sudo cp -r static /var/www/landing/
sudo chown -R www-data:www-data /var/www/landing
```

**Note:** You'll need to manually update this when landing page changes.

---

## XIV. Security Considerations

### 1. Rate Limiting

Add to Nginx:

```nginx
limit_req_zone $binary_remote_addr zone=landing:10m rate=10r/s;

location = / {
    limit_req zone=landing burst=20 nodelay;
    # ... proxy config
}
```

### 2. DDoS Protection

Use Cloudflare:

- Enable "Under Attack Mode" if needed
- Set up rate limiting rules
- Enable bot protection

### 3. HTTPS Only

Ensure all HTTP traffic redirects to HTTPS (shown in configs above).

---

## XV. Monitoring

### Check Landing Page Availability

```bash
# Test landing page
curl -I https://classroomtokenhub.com/

# Should return:
# HTTP/2 200
# content-type: text/html
```

### Check Flask App Routes

```bash
# Test student login
curl -I https://classroomtokenhub.com/student/login

# Should return:
# HTTP/2 200
# content-type: text/html
```

### Monitor Logs

```bash
# Nginx access logs
tail -f /var/log/nginx/classroomtokenhub_access.log

# Nginx error logs
tail -f /var/log/nginx/classroomtokenhub_error.log

# Flask app logs
journalctl -u classroom-economy -f
```

---

## XVI. Summary

**Landing Page:** GitHub Pages at root of `classroomtokenhub.com`
**Flask App:** All login and app routes on same domain
**Updates:** Push to `main` branch to update landing page
**High Availability:** Landing page stays up even if Flask goes down
**Configuration:** Nginx reverse proxy routes traffic appropriately

---

**Questions or Issues?**

- Check the troubleshooting section above
- Review Nginx error logs: `/var/log/nginx/classroomtokenhub_error.log`
- Verify GitHub Pages deployment: https://github.com/timwonderer/classroom-economy/actions
- Test each component individually before testing the full flow

**Last Updated:** January 9, 2026
**Version:** 1.7.0
## XVII. Amendment
Revisions to this document require incrementing the version number, updating the Effective Date, and populating the Supersedes field. Subordinate to CORE changes.
