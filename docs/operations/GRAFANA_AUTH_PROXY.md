# Grafana Auth Proxy Troubleshooting

Use this checklist when Grafana behind Nginx starts returning redirects or `ERR_CONNECTION_REFUSED` from the system admin dashboard.

## Expected Flow

- Nginx protects `/sysadmin/grafana/` with `auth_request /sysadmin/auth-check;`.
- `auth-check` returns **204** and sets `X-Auth-User` when the sysadmin session is valid.
- Grafana receives the upstream user header (`X-WEBAUTH-USER`) and the role header (`X-WEBAUTH-ROLE`) from Nginx.

## Quick Checks

1. **Session validity**  
   - Call `curl -I https://<host>/sysadmin/auth-check` with a logged-in sysadmin cookie.  
   - Expect `204` and an `X-Auth-User` header.  
   - If you see `401`, re-authenticate; stale sessions are cleared automatically.

2. **Grafana probe**  
   - Call `curl -I https://<host>/sysadmin/grafana/auth-check` with the same cookie.  
   - Expect `200 OK` and `X-Auth-User`.

3. **Nginx headers**  
   - Ensure the Grafana location block forwards `X-Auth-User` as `X-WEBAUTH-USER` and sets `X-WEBAUTH-ROLE Admin`.

4. **Grafana `grafana.ini`**  
   - `root_url` should point to the subpath (e.g., `https://<host>/sysadmin/grafana/`).  
   - `serve_from_sub_path = true` and `auth.proxy` is enabled with `header_name = X-WEBAUTH-USER`.

## Common Fixes

- If redirects loop: confirm `root_url` and `serve_from_sub_path` match the Nginx subpath and that the auth probe returns `204/200` with `X-Auth-User`.
- If requests fail after inactivity: log back in; the auth probe intentionally clears stale sessions to avoid forwarding expired credentials.

## Verification

- Open the sysadmin dashboard and click **Grafana**.  
- Network tab should show `GET /sysadmin/grafana/` → `301` (redirect to subpath) → `200` without repeats.

