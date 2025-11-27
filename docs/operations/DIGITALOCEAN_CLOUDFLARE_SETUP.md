# DigitalOcean Firewall Setup for Cloudflare Proxy

This guide explains how to configure DigitalOcean firewall rules to work with Cloudflare's proxy service (orange cloud enabled).

## Overview

When you enable Cloudflare's proxy for your domain:
- All HTTP/HTTPS traffic flows through Cloudflare's edge network first
- Your DigitalOcean droplet receives requests only from Cloudflare's IP addresses
- The real visitor IP is passed in the `CF-Connecting-IP` header
- Direct access to your origin server IP should be blocked for security

## Benefits

1. **DDoS Protection**: Cloudflare filters malicious traffic before it reaches your server
2. **Geographic Load Balancing**: Cloudflare's global network routes traffic efficiently
3. **Bot Mitigation**: Turnstile and bot management protect against automated attacks
4. **Origin IP Protection**: Your actual server IP is hidden from attackers
5. **Reduced Server Load**: Cloudflare caches static assets and filters attacks

## Prerequisites

- DigitalOcean account with a running droplet
- Domain managed by Cloudflare with proxy enabled (orange cloud icon)
- SSH access to your droplet

## Step 1: Create DigitalOcean Firewall

### 1.1 Navigate to Firewall Settings

1. Log in to your [DigitalOcean Dashboard](https://cloud.digitalocean.com/)
2. Click **Networking** in the left sidebar
3. Click the **Firewalls** tab
4. Click **Create Firewall**

### 1.2 Name Your Firewall

Give it a descriptive name like `cloudflare-proxy-firewall`

## Step 2: Configure Inbound Rules

### 2.1 Remove Default HTTP/HTTPS Rules

Delete any existing rules that allow HTTP (80) and HTTPS (443) from all sources.

### 2.2 Add Cloudflare IPv4 Rules

For **each** of the following Cloudflare IPv4 ranges, create TWO rules (HTTP and HTTPS):

```
173.245.48.0/20
103.21.244.0/22
103.22.200.0/22
103.31.4.0/22
141.101.64.0/18
108.162.192.0/18
190.93.240.0/20
188.114.96.0/20
197.234.240.0/22
198.41.128.0/17
162.158.0.0/15
104.16.0.0/13
104.24.0.0/14
172.64.0.0/13
131.0.72.0/22
```

**For each IP range:**
- Type: Custom
- Protocol: TCP
- Port Range: 80 (for HTTP)
- Sources: Enter the CIDR range (e.g., `173.245.48.0/20`)

Repeat for port 443 (HTTPS).

### 2.3 Add Cloudflare IPv6 Rules

For **each** of the following Cloudflare IPv6 ranges, create TWO rules (HTTP and HTTPS):

```
2400:cb00::/32
2606:4700::/32
2803:f800::/32
2405:b500::/32
2405:8100::/32
2a06:98c0::/29
2c0f:f248::/32
```

**For each IPv6 range:**
- Type: Custom
- Protocol: TCP
- Port Range: 80 (for HTTP)
- Sources: Enter the IPv6 CIDR range (e.g., `2400:cb00::/32`)

Repeat for port 443 (HTTPS).

### 2.4 Add SSH Access Rule

Add a rule to allow SSH access from your management IP:

- Type: SSH
- Protocol: TCP
- Port Range: 22
- Sources: Your office/home IP address (e.g., `203.0.113.50/32`)

**Security Tip**: Use a specific IP address or VPN IP range, not "All IPv4" or "All IPv6".

### 2.5 (Optional) Add Additional Services

If you run other services (e.g., database, monitoring), add rules for those ports as needed.

## Step 3: Configure Outbound Rules

### 3.1 Default Outbound Rules

By default, DigitalOcean allows all outbound traffic. This is usually fine for web applications.

If you need to restrict outbound traffic:
- ICMP for ping
- TCP/UDP port 53 for DNS
- TCP port 80/443 for HTTP/HTTPS (API calls, package updates)
- TCP port 5432 if using external PostgreSQL

## Step 4: Apply Firewall to Droplets

1. In the **Apply to Droplets** section, search for and select your droplet
2. Click **Create Firewall**

## Step 5: Verify Configuration

### 5.1 Test Cloudflare Access

1. Visit your domain in a browser (e.g., `https://yourdomain.com`)
2. Verify the site loads correctly
3. Check that Cloudflare headers are present (see Testing section below)

### 5.2 Test Direct IP Access

1. Find your droplet's IP address in the DigitalOcean dashboard
2. Try accessing `http://YOUR_DROPLET_IP` directly in a browser
3. **Expected result**: Connection timeout or refused (this is good - direct access is blocked)

### 5.3 Check Application Logs

SSH into your droplet and check logs:

```bash
# View application logs
tail -f /var/log/classroom-token-hub/app.log

# Look for warnings about non-Cloudflare IPs (should not appear in production)
grep "Request not from Cloudflare IP" /var/log/classroom-token-hub/app.log
```

## Step 6: Application Configuration

The Classroom Token Hub application automatically detects and extracts real visitor IPs from Cloudflare headers.

### How It Works

The application uses the `app/utils/ip_handler.py` module:

1. **Real IP Extraction**: Reads `CF-Connecting-IP` header (Cloudflare's real client IP)
2. **Fallback**: Uses `X-Forwarded-For` if CF header is missing
3. **Validation**: Verifies requests come from Cloudflare IP ranges
4. **Logging**: Warns if production traffic doesn't come from Cloudflare

### Implementation Details

The `get_real_ip()` function is used throughout the application:

- **Error Logging** (`wsgi.py:206`): Captures real IP in error reports
- **Turnstile Verification** (`student.py:1784`): Passes real IP to Cloudflare CAPTCHA API
- **Bug Reports** (`student.py:2037`, `admin.py:3935`): Stores real IP for analysis
- **Security Middleware** (`app/__init__.py:322`): Validates Cloudflare traffic

No manual configuration is needed - the application handles this automatically.

## Updating Cloudflare IP Ranges

Cloudflare occasionally updates their IP ranges. The application automatically fetches updated ranges from Cloudflare's API every 24 hours.

### Manual Update (if needed)

To manually verify current ranges:

```bash
# IPv4 ranges
curl https://www.cloudflare.com/ips-v4

# IPv6 ranges
curl https://www.cloudflare.com/ips-v6
```

### Update Firewall Rules

If Cloudflare adds new IP ranges:

1. Add the new CIDR ranges to your DigitalOcean firewall
2. The application will automatically pick up the changes within 24 hours
3. Consider setting up monitoring to alert when Cloudflare publishes IP changes

## Security Best Practices

### 1. Restore Visitor IP Addresses

The application automatically extracts real visitor IPs from the `CF-Connecting-IP` header. This ensures:
- Accurate logging and analytics
- Proper rate limiting and abuse detection
- Correct geolocation data

### 2. Validate Cloudflare Requests

The middleware (`app/__init__.py:306`) validates that production requests come from Cloudflare IPs. In production, warnings are logged for non-Cloudflare traffic.

### 3. SSL/TLS Configuration

In your Cloudflare dashboard:

1. Go to **SSL/TLS** settings
2. Set encryption mode to **Full (strict)**
3. This ensures end-to-end encryption from visitor → Cloudflare → origin

### 4. Authenticated Origin Pulls (Optional)

For additional security, enable Authenticated Origin Pulls:

1. In Cloudflare: **SSL/TLS** → **Origin Server**
2. Enable **Authenticated Origin Pulls**
3. Upload Cloudflare's certificate to your origin server
4. Configure your web server to require the client certificate

This prevents anyone with Cloudflare IPs from directly accessing your origin.

### 5. Rate Limiting

Use Cloudflare's rate limiting instead of application-level rate limiting:
- Cloudflare blocks excessive requests before they reach your server
- Configure in: **Security** → **WAF** → **Rate limiting rules**

### 6. Monitor Firewall Logs

Regularly review logs for:
- Blocked connection attempts
- Non-Cloudflare traffic reaching your server
- Unusual traffic patterns

## Cloudflare Dashboard Settings

### Recommended Security Settings

1. **SSL/TLS**:
   - Encryption mode: Full (strict)
   - Minimum TLS Version: 1.2
   - TLS 1.3: Enabled

2. **Security**:
   - Security Level: Medium or High
   - Challenge Passage: 30 minutes
   - Browser Integrity Check: Enabled

3. **Speed**:
   - Auto Minify: HTML, CSS, JavaScript
   - Brotli: Enabled

4. **Caching**:
   - Caching Level: Standard
   - Browser Cache TTL: Respect Existing Headers

5. **Page Rules** (optional):
   - Cache everything for static assets
   - Bypass cache for admin/student dashboards

## Testing

### Test Real IP Detection

Create a test endpoint to verify IP extraction works:

```python
from flask import request
from app.utils.ip_handler import get_real_ip, get_request_info

@app.route('/test-ip')
def test_ip():
    info = get_request_info()
    return {
        'real_ip': get_real_ip(),
        'remote_addr': request.remote_addr,
        'cloudflare_verified': info['cloudflare_verified'],
        'country': info['country'],
        'ray_id': info['ray_id']
    }
```

Access `https://yourdomain.com/test-ip` and verify:
- `real_ip` shows your actual IP
- `remote_addr` shows a Cloudflare IP (173.245.x.x, 104.16.x.x, etc.)
- `cloudflare_verified` is `true`

### Test Firewall Rules

1. **From browser**: Access should work normally
2. **Direct IP access**: Should fail/timeout
3. **From different locations**: Use a VPN to test from different countries

### Monitor Cloudflare Analytics

In Cloudflare dashboard → **Analytics & Logs**:
- View request count, bandwidth, threats blocked
- Check cache hit rate
- Review security events

## Troubleshooting

### Site Not Loading

1. Check Cloudflare proxy is enabled (orange cloud)
2. Verify DNS records point to Cloudflare
3. Check firewall rules include all Cloudflare IP ranges
4. Review Cloudflare's SSL/TLS settings

### Direct IP Access Not Blocked

1. Verify firewall is applied to correct droplet
2. Check inbound rules only allow Cloudflare IPs on ports 80/443
3. Wait a few minutes for firewall rules to propagate

### Real IP Not Showing

1. Check `CF-Connecting-IP` header is present
2. Verify `get_real_ip()` function is imported correctly
3. Review application logs for errors

### Cloudflare IP Warnings in Logs

If you see "Request not from Cloudflare IP" warnings in production:

1. Verify the request isn't coming from a different source (health check, direct access)
2. Check if Cloudflare updated their IP ranges
3. Update firewall rules if needed

## Emergency Procedures

### Disable Cloudflare Proxy (Emergency Only)

If you need to bypass Cloudflare temporarily:

1. In Cloudflare DNS settings, click the orange cloud icon to turn it gray
2. Wait for DNS propagation (5-30 minutes)
3. Your droplet will receive direct traffic
4. **Important**: Update firewall to allow all IPs on ports 80/443, or your site will be unreachable

### Restore Firewall After Cloudflare Disable

If you disabled Cloudflare and allowed all traffic:

1. Re-enable Cloudflare proxy (orange cloud)
2. Wait for DNS propagation
3. Remove the "all sources" rule for ports 80/443
4. Verify Cloudflare IPs are still in the firewall rules

## Related Documentation

- [Cloudflare IP Ranges](https://www.cloudflare.com/ips/)
- [DigitalOcean Firewall Documentation](https://docs.digitalocean.com/products/networking/firewalls/)
- [Cloudflare SSL/TLS Documentation](https://developers.cloudflare.com/ssl/)
- [Authenticated Origin Pulls](https://developers.cloudflare.com/ssl/origin-configuration/authenticated-origin-pull/)

## Additional Resources

- Application IP Handler: `app/utils/ip_handler.py`
- Middleware Implementation: `app/__init__.py:306-330`
- Turnstile Integration: `app/utils/turnstile.py`
- Security Documentation: `docs/security/`

## Summary Checklist

- [ ] Create DigitalOcean firewall with Cloudflare IP ranges
- [ ] Add SSH access rule for management IP
- [ ] Apply firewall to droplet
- [ ] Test site loads through Cloudflare
- [ ] Verify direct IP access is blocked
- [ ] Check application logs show no non-Cloudflare warnings
- [ ] Configure Cloudflare SSL to "Full (strict)"
- [ ] Set up Cloudflare security settings
- [ ] Test real IP detection endpoint
- [ ] Monitor Cloudflare analytics for normal traffic patterns
- [ ] Document emergency procedures for your team
- [ ] Set calendar reminder to review Cloudflare IP ranges quarterly
