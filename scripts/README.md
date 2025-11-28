# Scripts Directory

This directory contains utility scripts for development, operations, and maintenance of the Classroom Token Hub application.

## Operational Scripts

### Firewall Management

#### `setup-firewall-complete.sh`
Automated DigitalOcean firewall setup with Cloudflare and UptimeRobot IP ranges. Creates or updates firewall rules to allow traffic only from Cloudflare's proxy and UptimeRobot monitoring.

**Usage:**
```bash
# Create new firewall
./scripts/setup-firewall-complete.sh create <droplet-id> "<your-ssh-ip>"

# Update existing firewall
./scripts/setup-firewall-complete.sh update <firewall-id>
```

**Prerequisites:** `doctl` and `jq` installed and authenticated

#### `add-uptimerobot-to-firewall.sh`
Adds only UptimeRobot monitoring IPs to an existing firewall. Use this if you already have Cloudflare configured.

**Usage:**
```bash
./scripts/add-uptimerobot-to-firewall.sh <firewall-id>
```

#### `create-github-actions-firewall.py`
Creates a **separate firewall** for GitHub Actions SSH access. This is the recommended approach since GitHub has ~70 IP ranges, which would exceed DigitalOcean's 50-rule limit per firewall.

**Usage:**
```bash
python3 scripts/create-github-actions-firewall.py <droplet-id>
```

**Note:** Multiple firewalls can be applied to one droplet. This creates a dedicated firewall for GitHub Actions, keeping your main firewall clean.

#### `firewall-ips.json`
Reference file containing all Cloudflare and UptimeRobot IP ranges in JSON format. Use for manual setup or custom automation.

**Documentation:** [DigitalOcean & Cloudflare Setup Guide](../docs/operations/DIGITALOCEAN_CLOUDFLARE_SETUP.md)

---

### `cleanup_duplicates_flask.py`
Identifies and safely removes duplicate student records while preserving all related data (transactions, attendance, hall passes, etc.).

**Usage:**
```bash
python scripts/cleanup_duplicates_flask.py --list    # Preview duplicates
python scripts/cleanup_duplicates_flask.py --delete  # Remove duplicates
```

**Documentation:** [Cleanup Duplicates Guide](../docs/operations/CLEANUP_DUPLICATES.md)

### `cleanup_duplicates.py`
Legacy cleanup script (simpler version). Use `cleanup_duplicates_flask.py` for production as it properly handles data migration.

### `check_migration.py`
Checks the current Alembic migration version in the database and lists recent migration files.

**Usage:**
```bash
python scripts/check_migration.py
```

### `check_orphaned_insurance.py`
Finds insurance policies with NULL teacher_id that won't show up in any teacher's admin panel.

**Usage:**
```bash
python scripts/check_orphaned_insurance.py
```

## Development Scripts

### `setup-hooks.sh`
Installs git hooks for migration safety checks. **Run this after cloning the repository!**

**Usage:**
```bash
bash scripts/setup-hooks.sh
```

This prevents migration conflicts by checking for multiple migration heads before pushing.

### `check-migrations.sh`
Pre-push git hook that validates migration integrity. Installed by `setup-hooks.sh`.

### `update_packages.sh`
Updates Python package dependencies.

**Usage:**
```bash
bash scripts/update_packages.sh
```

## Development Utilities

The `dev-utilities/` subdirectory contains additional development tools. See its README for details.

## Adding New Scripts

When adding new scripts to this directory:

1. **Make scripts executable** if they should be run directly:
   ```bash
   chmod +x scripts/your_script.sh
   ```

2. **Add shebang** at the top of the file:
   - Python: `#!/usr/bin/env python3`
   - Bash: `#!/usr/bin/env bash`

3. **Document in this README** with:
   - Brief description
   - Usage example
   - Link to detailed documentation (if applicable)

4. **Import from app package** for Python scripts:
   ```python
   from app import create_app, db
   ```
   Scripts must be run from the repository root directory for proper module resolution.
   Avoid hardcoded paths like `/home/user/classroom-economy`

5. **Add error handling** and helpful error messages

## Related Documentation

- **[Operations Guides](../docs/operations/)** - Operational procedures using these scripts
- **[Contributing Guide](../CONTRIBUTING.md)** - Development workflow and git hooks
- **[Deployment Guide](../docs/DEPLOYMENT.md)** - Production deployment procedures

---

**Last Updated:** 2025-11-24
