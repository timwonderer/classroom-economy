# Production Infrastructure Audit

Audit date: 2026-07-01  
Host: `app-server`  
Scope: read-only snapshot of the current production environment before the Classroom Token Hub v2 migration.

## 1. Operating System

| Item | Value |
|---|---|
| Distribution | Ubuntu 22.04.5 LTS |
| Version | 22.04 (jammy) |
| Kernel | `5.15.0-174-generic` |
| Hostname | `app-server` |
| Uptime | 85 days, 2:32 |
| CPU | x86-64 on DigitalOcean Droplet VM |
| Memory | 3.8 GiB total, 1.0 GiB used, 2.5 GiB available |
| Disk layout | `/dev/vda1` 25G ext4 mounted at `/`; `/dev/vda15` 106M vfat mounted at `/boot/efi` |

## 2. Package Status

| Item | Value |
|---|---|
| Installed OS version | Ubuntu 22.04.5 LTS |
| Available package updates | Yes. Upgrades available include `grafana`, `loki`, `tempo`, `promtail`, `tailscale`, `cloud-init`, `snapd`, `ubuntu-pro-client`, `ubuntu-advantage-tools`, `netplan.io`, `iproute2`, `libnss3`, `libsqlite3-0`, and `alloy`. |
| Reboot required | Yes. `/var/run/reboot-required` is present. |

## 3. Filesystem

### Disk Utilization

| Mount | Size | Used | Avail | Use% |
|---|---:|---:|---:|---:|
| `/` | 25G | 11G | 14G | 44% |
| `/boot/efi` | 105M | 6.1M | 99M | 6% |

### Largest Directories

Reasonable-depth `du` sampling showed:

| Path | Size |
|---|---:|
| `/usr` | 3.7G |
| `/var` | 3.0G |
| `/root` | 2.4G |
| `/root/classroom-economy` | 288M |
| `/root/classroom-economy/venv` | 222M |
| `/var/lib` | 2.1G |
| `/var/log` | 720M |

No filesystem is close to capacity. `/var/log` is the largest notable sub-tree.

### Inode Usage

| Mount | Inodes | Used | Free | Use% |
|---|---:|---:|---:|---:|
| `/` | 3.1M | 232K | 2.9M | 8% |
| `/boot/efi` | n/a | n/a | n/a | n/a |

### Mounted Filesystems

Main mounts observed:

| Target | Source | Type |
|---|---|---|
| `/` | `/dev/vda1` | ext4 |
| `/boot/efi` | `/dev/vda15` | vfat |
| `/run`, `/dev/shm`, `/run/lock`, `/run/user/0` | tmpfs | tmpfs |
| `/snap/*` | loop devices | squashfs |

## 4. Running Services

### Failed Services

No failed systemd services were reported.

### Running Services of Interest

| Service | State | Notes |
|---|---|---|
| `nginx.service` | running | Reverse proxy and TLS termination |
| `gunicorn.service` | running | Classroom Token Hub app server |
| `postgresql@14-main.service` | running | PostgreSQL 14 cluster |
| `prometheus.service` | running | Metrics backend |
| `prometheus-node-exporter.service` | running | Host metrics exporter |
| `grafana-server.service` | running | Dashboard / alerting UI |
| `fail2ban.service` | running | SSH jail active |
| `unattended-upgrades.service` | running | Enabled, active |
| `redis-server.service` | running | Local Redis |
| `loki.service` | running | Log aggregation |
| `tempo.service` | running | Traces backend |
| `promtail.service` | running | Log shipping |
| `process-exporter.service` | running | Process metrics |
| `do-agent.service` | running | DigitalOcean monitoring |
| `droplet-agent.service` | running | DigitalOcean droplet agent |
| `alloy.service` | running | OpenTelemetry collector |
| `tailscaled.service` | running | Tailscale node agent |

### Enabled Services Relevant to CTH

Enabled units include `nginx`, `gunicorn`, `postgresql`, `prometheus`, `prometheus-node-exporter`, `grafana-server`, `fail2ban`, `unattended-upgrades`, `redis-server`, `loki`, `tempo`, `promtail`, `process-exporter`, `tailscaled`, and `do-agent` / `droplet-agent`.

## 5. Network

### Listening Ports

| Port | Service |
|---|---|
| `22` | `sshd` |
| `80`, `443` | `nginx` |
| `8000` | `gunicorn` |
| `3000` | `grafana` |
| `5432` | `postgres` |
| `6379` | `redis-server` |
| `9090` | `prometheus` |
| `9100` | `prometheus-node-exporter` |
| `3100` | `loki` |
| `3200` | `tempo` |
| `9080` | `promtail` |
| `9256` | `process-exporter` |
| `4317`, `4318` | `tempo` OTLP listeners |
| `12345` | `alloy` |
| `41641` | `tailscaled` |

### Firewall

| Item | Value |
|---|---|
| UFW status | inactive |
| Active firewall | No UFW policy active on the host; SSH is protected by key-only auth and Fail2Ban jail for `sshd`. |

### Reverse Proxy Summary

nginx listens on `80` and `443` for `app.classroomtokenhub.com`, redirects HTTP to HTTPS, and proxies:

| Path | Upstream |
|---|---|
| App routes | `http://127.0.0.1:8000` |
| Grafana proxy paths | `http://127.0.0.1:3000` |

## 6. Nginx

| Item | Value |
|---|---|
| Version | `nginx/1.18.0 (Ubuntu)` |
| Enabled sites | `classroom` |
| Server names | `app.classroomtokenhub.com` |
| SSL configuration | Uses Let’s Encrypt certs from `/etc/letsencrypt/live/app.classroomtokenhub.com/` and includes `options-ssl-nginx.conf` plus `ssl-dhparams.pem` |
| Redirects | HTTP `80` redirects to HTTPS |
| Proxy configuration | App traffic to `127.0.0.1:8000`; Grafana proxied under `/sysadmin/grafana/` with websocket handling and auth request checks |

Notes:

* nginx uses JSON access logging.
* The config includes a Grafana websocket map and auth-request flow.
* The site config exposes `/sysadmin/login`, `/sysadmin/grafana/auth-check`, and Grafana proxy paths.

## 7. SSL

| Certificate | Source | Expiration | Notes |
|---|---|---|---|
| `app.classroomtokenhub.com` | Let’s Encrypt | 2026-08-08 15:41:25 UTC | RSA key, valid at audit time |

No Cloudflare Origin certificate was observed on the host. The active certificate source is Let’s Encrypt.

## 8. PostgreSQL

| Item | Value |
|---|---|
| Version | PostgreSQL 14.23 |
| Running status | Active and running |
| Database size | `classroom_db` 98 MB; `classroom_economy` 9 MB; template databases ~8 MB each |
| Existing databases | `classroom_db`, `classroom_economy`, `postgres`, `template0`, `template1` |
| Extensions installed | `plpgsql` |

Notes:

* The cluster is `14-main`.
* Live application connections were present from the public IP used by the app tier.
* No application table inspection was performed.

## 9. Python Environment

| Item | Value |
|---|---|
| Python version | 3.10.12 |
| Virtual environment | `/root/classroom-economy/venv` |
| Gunicorn version | 25.3.0 |
| Installed application requirements | Observed key packages include `Flask 3.1.3`, `SQLAlchemy 2.0.49`, and `psycopg2-binary 2.9.12` |

## 10. Scheduled Tasks

### systemd Timers

Active timers include:

| Timer | Purpose |
|---|---|
| `apt-daily.timer` | apt metadata refresh |
| `apt-daily-upgrade.timer` | unattended package upgrades |
| `certbot.timer` | certificate renewal |
| `logrotate.timer` | log rotation |
| `dpkg-db-backup.timer` | dpkg database backup |
| `fstrim.timer` | filesystem trim |
| `prometheus-node-exporter-apt.timer` | exporter package checks |
| `droplet-agent-update.timer` | DigitalOcean agent updates |
| `cth-gh-pages-cutover.timer` | custom CTH job |
| `ua-timer.timer` | Ubuntu Advantage maintenance |

### Cron Jobs

Observed cron entries:

| Location | Entries |
|---|---|
| `/etc/cron.d` | `certbot`, `e2scrub_all`, `sysstat` |
| `/etc/cron.daily` | `apport`, `apt-compat`, `do-agent`, `dpkg`, `logrotate`, `man-db`, `sysstat` |
| `/etc/cron.weekly` | `man-db` |

No per-user crontab entries were observed for root.

## 11. Logs

### Recent Critical Errors

No recent `journalctl -p err` entries were returned in the sampled window.

### Notable Repeating Warnings / Informational Items

* Grafana repeatedly logged `No last resource version found, starting from scratch`.
* The monitoring stack is actively querying `/health`, `/health/deep`, and `/health/invariants`.
* Journald output noted rotation for some units, so history was incomplete in the live sample.

### Failed Services

No failed services were present at the time of the snapshot.

## 12. Security

| Item | Value |
|---|---|
| SSH configuration summary | `PermitRootLogin prohibit-password`; `PasswordAuthentication no`; `PubkeyAuthentication yes` |
| Fail2Ban status | Running with one jail: `sshd` |
| Firewall status | UFW inactive |
| Users with sudo | `root` can run `ALL` commands; `/etc/sudoers` grants `root` passwordless `ALL` |
| Root login status | Root login via password is disabled; key-based root login is allowed by `prohibit-password` |
| Password authentication status | Disabled for SSH |

## 13. Cloudflare / Deployment Notes

| Item | Value |
|---|---|
| Deployment directory | `/root/classroom-economy` |
| Release layout | No separate release tree was observed; the live app runs directly from the checked-out directory |
| Environment variables | Present in `/root/classroom-economy/.env`; secrets are redacted in this report |
| Current deployment strategy | `gunicorn.service` starts Gunicorn directly from `/root/classroom-economy/venv/bin/gunicorn` and nginx reverse proxies to it |

Relevant env values observed:

* `FLASK_ENV=production`
* `MAINTENANCE_MODE=false`
* `OTEL_TRACES_ENABLED=true`
* `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=http://127.0.0.1:4318/v1/traces`
* `OTEL_SERVICE_NAME=classroom-token-hub-web`

## 14. Health Assessment

### Critical

| Finding | Assessment |
|---|---|
| Reboot required | The host reports `*** System restart required ***`, so the kernel/userspace state is not fully refreshed after package activity. |
| OS age | The host has been up for 85 days; this is not inherently wrong, but it increases the chance of drift versus recent package/kernel updates. |

### Recommended

| Finding | Assessment |
|---|---|
| Pending package updates | Several monitoring and platform packages have updates available, including Grafana, Loki, Tempo, Promtail, Tailscale, Snapd, and Ubuntu client tooling. |
| Kernel refresh | A reboot should be scheduled before or during the v2 migration window so the current kernel is aligned with the installed packages. |
| UFW absence | UFW is inactive; security currently relies on provider/network controls, nginx, SSH key auth, and Fail2Ban. |

### Informational

| Finding | Assessment |
|---|---|
| Monitoring stack is healthy | Prometheus, Grafana, Loki, Tempo, Promtail, and exporters are all active. |
| App service is healthy | Gunicorn is running and recent `/health` and `/health/invariants` checks are returning `200` with passing invariant logs. |
| Storage headroom is good | Root filesystem is at 44% and inode usage is low. |
| TLS posture is clear | The host uses a Let’s Encrypt certificate for `app.classroomtokenhub.com`, expiring 2026-08-08 UTC. |
| Deployment is direct-from-checkout | The app runs from `/root/classroom-economy` rather than a release symlink tree. |

### Overall Assessment

The production host appears operational and moderately well-instrumented. The main pre-migration concerns are the required reboot, accumulated package updates in the observability stack, and the fact that nginx/UFW/firewall posture should be reviewed in the context of the planned v2 migration.

