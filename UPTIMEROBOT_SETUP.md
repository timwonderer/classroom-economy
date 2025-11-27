# UptimeRobot Setup Guide for Classroom Economy

This guide explains how to set up UptimeRobot monitoring for your Classroom Economy app.

## Why UptimeRobot?

Your app already has public health check endpoints that don't require authentication. UptimeRobot can monitor these endpoints and provide:
- **Uptime monitoring** - Get alerted when your app goes down
- **Public status page** - Users can check status even when your app is down
- **Response time tracking** - Monitor app performance over time
- **Incident history** - Track outages and uptime percentage

## Available Health Endpoints

### 1. Basic Health Check (Recommended for UptimeRobot)
- **URL:** `https://yourdomain.com/health`
- **Auth Required:** No
- **Response:** `"ok"` (200 status)
- **Checks:** Database connectivity
- **Use case:** Simple uptime monitoring

### 2. Deep Health Check (Advanced)
- **URL:** `https://yourdomain.com/health/deep`
- **Auth Required:** No
- **Response:** JSON with detailed component status
- **Checks:**
  - Database connectivity
  - Students table accessibility
  - Admins table accessibility
  - Hall passes table accessibility
- **Use case:** Detailed system monitoring

Example response:
```json
{
  "status": "ok",
  "checks": {
    "database": "connected",
    "students_table": "accessible",
    "student_count": 150,
    "admins_table": "accessible",
    "admin_count": 5,
    "hall_passes_table": "accessible"
  }
}
```

## UptimeRobot Setup Steps

### Step 1: Create a Monitor

1. **Log in to UptimeRobot** (you already have an account)
2. **Click "Add New Monitor"**
3. **Configure the monitor:**

   | Setting | Value |
   |---------|-------|
   | Monitor Type | HTTP(s) |
   | Friendly Name | Classroom Economy - Main |
   | URL | `https://yourdomain.com/health` |
   | Monitoring Interval | 5 minutes (free) or 1 minute (paid) |
   | Monitor Timeout | 30 seconds |
   | HTTP Method | GET |
   | Expected Status Code | 200 |

4. **Optional: Add keyword monitoring**
   - Enable "Keyword Exists"
   - Keyword: `ok`
   - This ensures the response body is correct, not just the status code

5. **Click "Create Monitor"**

### Step 2: Add Alert Contacts

1. **Go to "My Settings" → "Alert Contacts"**
2. **Add email alerts:**
   - Your email address
   - Any team members
3. **Optional: Add other integrations:**
   - SMS (if available on your plan)
   - Slack webhook
   - Discord webhook
   - PagerDuty
   - etc.

### Step 3: Create a Public Status Page

This is **critical** - the status page is hosted by UptimeRobot, so it works even when your app is down!

1. **Go to "Public Status Pages"**
2. **Click "Add Public Status Page"**
3. **Configure:**

   | Setting | Recommended Value |
   |---------|-------------------|
   | Page Type | Public Status Page |
   | Status Page URL | Choose a subdomain (e.g., `classroom-economy`) |
   | Page Title | Classroom Economy Status |
   | Logo | Upload your app logo (optional) |
   | Monitors | Select your health check monitor(s) |
   | Show Uptime | ✓ Yes (90 days) |
   | Show Response Times | ✓ Yes |
   | Show Incidents | ✓ Yes |

4. **Your status page will be available at:**
   `https://stats.uptimerobot.com/your-subdomain`

5. **Optional: Custom Domain**
   - Point `status.yourdomain.com` to UptimeRobot
   - Follow UptimeRobot's custom domain setup guide

### Step 4: Configure Your App

Set the `STATUS_PAGE_URL` environment variable so error pages can link to your status page:

```bash
# In your .env file or deployment platform
STATUS_PAGE_URL=https://stats.uptimerobot.com/your-subdomain
```

Or if using a custom domain:
```bash
STATUS_PAGE_URL=https://status.yourdomain.com
```

**Without this variable:** Error pages work normally, just without the status page link.

**With this variable:** Error pages show a "Check System Status" button that links to your status page.

## Testing Your Setup

### Test Locally

Run the included test script:

```bash
# Test local development server
./test_monitoring.sh http://localhost:5000

# Test production server
./test_monitoring.sh https://yourdomain.com
```

### Test in UptimeRobot

1. **Go to your monitor** in UptimeRobot dashboard
2. **Click "View Details"**
3. **Check the latest response:**
   - Should show 200 status
   - Response time should be reasonable (< 1000ms typically)

4. **Simulate downtime:**
   - Stop your app temporarily
   - Wait 5 minutes for UptimeRobot to detect it
   - Check that you receive an alert
   - Check that status page shows "Down"

## Advanced Monitoring Options

### Multiple Monitors

Consider creating additional monitors for:

1. **Main health check:** `/health`
2. **Deep health check:** `/health/deep` (checks all tables)
3. **Public pages:** `/` or `/privacy` (checks if web server serves pages)
4. **Login page:** `/student/login` (checks if login form loads)

### Maintenance Windows

Before deploying updates:

1. **Go to your monitor** in UptimeRobot
2. **Click "Maintenance Windows"**
3. **Schedule maintenance:**
   - Start time
   - Duration
   - Reason (shown on status page)
4. **Deploy your updates** during this window
5. **UptimeRobot won't send alerts** during maintenance

### Alert Thresholds

Configure when you get notified:

1. **Go to monitor settings**
2. **Alert contacts** section
3. **Set threshold:**
   - "Alert when down" (immediate)
   - "Alert when down for X minutes" (reduces false alarms)

## How Authentication Works

### Why `/health` endpoints don't require sign-in:

**Purpose:** Monitoring tools (like UptimeRobot) can't sign in - they need public endpoints.

**Security:** The endpoints only expose:
- Database connectivity status
- Table row counts (not actual data)
- No student information
- No admin credentials
- No sensitive business logic

**What they don't expose:**
- Student names, balances, or PINs
- Admin accounts or TOTP secrets
- Transaction details
- Hall pass data
- Any personally identifiable information (PII)

### For monitoring sign-in flows:

If you want to monitor that authentication works:

**Option 1:** Monitor the login page loads (no actual login)
- Monitor `/student/login` endpoint
- Check for 200 status
- Verifies web server + template rendering work

**Option 2:** Synthetic monitoring (paid services)
- Services like Pingdom, Uptime.com
- Actually fill in forms and test login
- ~$10-50/month depending on features

## Status Page Best Practices

### Share your status page:

1. **Add to error pages** (already done via `STATUS_PAGE_URL`)
2. **Link from your main site footer**
3. **Bookmark for quick access**
4. **Share with your users/team**

### Post updates during incidents:

1. **When you get an alert** → Investigate
2. **Update status page** with incident details
3. **Post updates** as you work on fixes
4. **Mark as resolved** when fixed

### Example incident update:

> **Database Connection Issues**
> Investigating: We're experiencing intermittent database connectivity issues. Working on a fix.
> *Posted: 2:15 PM*
>
> Update: Identified the issue with connection pool. Restarting database.
> *Posted: 2:25 PM*
>
> Resolved: All systems operational. Monitoring for stability.
> *Posted: 2:40 PM*

## Troubleshooting

### Monitor shows "Down" but app works fine

**Possible causes:**
- Firewall blocking UptimeRobot IPs
- Rate limiting on your server
- SSL certificate issues
- Slow response (timeout set too low)

**Fix - Option 1: Automated (Recommended)**
```bash
# Add all UptimeRobot IPs to your firewall automatically
./scripts/add-uptimerobot-to-firewall.sh <firewall-id>

# Or create/update complete firewall with Cloudflare + UptimeRobot
./scripts/setup-firewall-complete.sh update <firewall-id>
```

**Fix - Option 2: Manual**
- Get your firewall ID: `doctl compute firewall list`
- Add each UptimeRobot IP from `scripts/firewall-ips.json`
- Or follow the instructions in `docs/operations/DIGITALOCEAN_CLOUDFLARE_SETUP.md`
- Increase timeout to 30 seconds
- Verify SSL certificate is valid

**Verify fix:**
```bash
# Check if UptimeRobot IPs are allowed
doctl compute firewall get <firewall-id> | grep -E "46.137|52.62|54.79"
```

### Health check fails with 500 error

**Possible causes:**
- Database connection issues
- Missing environment variables
- Table doesn't exist (migrations not run)

**Fix:**
- Check application logs
- Verify database is running
- Run migrations: `flask db upgrade`

### Status page not updating

**Possible causes:**
- Monitor is paused
- Status page not linked to monitor
- Cache delay (can take 1-2 minutes)

**Fix:**
- Verify monitor is active in dashboard
- Check "Public Status Pages" → your page → ensure monitors are selected
- Wait a few minutes for cache to clear

## Quick Reference

| What | URL |
|------|-----|
| Basic health check | `https://yourdomain.com/health` |
| Deep health check | `https://yourdomain.com/health/deep` |
| Status page (default) | `https://stats.uptimerobot.com/your-subdomain` |
| Test script | `./test_monitoring.sh https://yourdomain.com` |

## Need Help?

- **UptimeRobot Docs:** https://uptimerobot.com/help/
- **UptimeRobot Support:** support@uptimerobot.com
- **App Support:** timothy.cs.chang@gmail.com
