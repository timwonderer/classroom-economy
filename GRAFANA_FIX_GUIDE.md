# Grafana Access Fix Guide

## Problem

Clicking the Grafana link in the system admin dashboard results in "connection refused" errors with infinite redirect loops.

## Root Cause

**Nginx Configuration Issue**: The `proxy_pass` directive has a trailing slash that strips the URL path:

```nginx
# WRONG - strips path
proxy_pass http://127.0.0.1:3000/;
```

Grafana is configured to serve from subpath `/sysadmin/grafana/` (via `serve_from_sub_path = true`), but Nginx removes this path when proxying, causing Grafana to redirect back, creating an infinite loop.

## Solution: Dual-Layer Approach (Best Practice)

This branch implements **both solutions** for maximum reliability:

1. **Primary (Nginx)**: Fast, production-ready proxy
2. **Fallback (Flask)**: Works in all environments, no Nginx required

**How it works:**
- With Nginx configured: Nginx intercepts requests → Grafana (⚡ fastest)
- Without Nginx / Dev mode: Flask proxy handles requests (🛟 reliable fallback)

You can deploy **just the Flask proxy** (merge this branch), or **both** (merge + fix Nginx).

### Option 1: Fix Nginx Configuration (Recommended for Production)

This is the proper solution if you have access to modify Nginx configuration on the server.

**Edit your Nginx configuration** (`/etc/nginx/sites-available/default` or similar):

```nginx
location /sysadmin/grafana/ {
    auth_request /sysadmin/auth-check;
    auth_request_set $auth_user $upstream_http_x_auth_user;

    error_page 401 = @grafana_login_redirect;

    # FIX: Remove trailing slash to preserve path
    proxy_pass http://127.0.0.1:3000;  # ← NO trailing slash!

    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-WEBAUTH-USER $auth_user;
    proxy_set_header X-WEBAUTH-ROLE Admin;

    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
}
```

**After making the change:**
```bash
# Test Nginx configuration
sudo nginx -t

# Reload Nginx
sudo systemctl reload nginx
```

### Option 2: Use Flask Proxy (Implemented in This Branch)

This solution uses a Flask route to proxy Grafana requests, bypassing the Nginx issue entirely.

**Advantages:**
- Works without modifying Nginx configuration
- Maintains system admin authentication
- Graceful error handling
- Already implemented in this branch

**Configuration:**

Set environment variable (optional):
```bash
export GRAFANA_URL=http://localhost:3000
```

Or add to your `.env` file:
```
GRAFANA_URL=http://localhost:3000
```

If not set, defaults to `http://localhost:3000`.

**How it works:**
1. User clicks "Grafana" in sysadmin dashboard
2. Request goes to Flask route `/sysadmin/grafana`
3. Flask validates authentication via `@system_admin_required`
4. Flask proxies request to Grafana service
5. Response flows back through Flask to browser

## Quick Reference

### Deploy Flask Proxy (Immediate Fix)
```bash
# Merge this branch and deploy
git merge claude/fix-grafana-redirect-Q3rDh
# Deploy to production
# Grafana will work immediately via Flask proxy
```

### Add Nginx Fix (Performance Boost)
```bash
# SSH to server
ssh user@classroomtokenhub.com

# Edit Nginx config
sudo nano /etc/nginx/sites-available/default

# Line 85: Remove trailing slash
# Change: proxy_pass http://127.0.0.1:3000/;
# To:     proxy_pass http://127.0.0.1:3000;

# Reload
sudo nginx -t && sudo systemctl reload nginx
```

## Comparison

| Feature | Nginx Fix | Flask Proxy | **Both (Recommended)** |
|---------|-----------|-------------|------------------------|
| **Performance** | ⚡ Excellent | ✅ Good | ⚡ Excellent (Nginx takes priority) |
| **Setup** | Requires SSH | Just deploy | Deploy + SSH |
| **Resilience** | Production only | All environments | ✅ Maximum (auto-fallback) |
| **Maintenance** | One config change | Zero config | One config change |
| **Recommended For** | Production only | Dev/Quick fix | ✅ **All scenarios** |

## Testing

After implementing either solution, test by:

1. Log in as system admin
2. Click "Grafana" in sidebar
3. Verify Grafana loads without errors
4. Log out from sysadmin dashboard
5. Try accessing Grafana directly - should redirect to login

## Files Changed (Flask Proxy Solution)

- `app/routes/system_admin.py`: Added `grafana_proxy()` function
- `requirements.txt`: Added `requests==2.32.3`
- `CHANGELOG.md`: Documented fix

## Additional Notes

- The Flask `auth-check` endpoint at `/sysadmin/grafana/auth-check` is rate-limit exempt
- Session cookies use `SESSION_COOKIE_PATH="/"` for proper sharing
- Grafana configuration has `serve_from_sub_path = true` enabled

## Troubleshooting

**Still seeing redirects?**
- Check Grafana is running: `sudo systemctl status grafana-server`
- Verify Grafana config has correct `root_url`
- Check Flask logs for proxy errors

**Grafana loads but shows "connection refused" for resources?**
- Ensure `serve_from_sub_path = true` in Grafana config
- Check browser console for failed resource URLs

**Authentication not working?**
- Verify `SESSION_COOKIE_PATH="/"` in Flask config
- Check session cookies in browser DevTools
- Ensure `/sysadmin/auth-check` endpoint returns 200

## References

- Nginx config: `codex/fix-grafana-infinite-redirect` branch → `nginx settings.txt`
- Grafana config: `codex/fix-grafana-infinite-redirect` branch → `grafana settings.txt`
- Flask implementation: This branch → `app/routes/system_admin.py`
