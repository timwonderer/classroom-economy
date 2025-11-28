#!/bin/bash
#
# PostgreSQL Database Restore Script
#
# This script restores a database backup created by backup-database.sh
#
# ⚠️  WARNING: This will DROP and recreate the database!
# ⚠️  Make sure you have a current backup before restoring!
#
# Usage:
#   ./scripts/restore-database.sh backup_20251128_020000.sql.gz
#   ./scripts/restore-database.sh latest
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
BACKUP_DIR="/root/backups/postgresql"

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  PostgreSQL Database Restore                               ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo

# Check if backup file specified
if [ -z "$1" ]; then
    echo -e "${RED}Error: No backup file specified${NC}"
    echo
    echo "Usage:"
    echo "  $0 <backup_file.sql.gz>"
    echo "  $0 latest"
    echo
    echo "Available backups:"
    ls -lh "$BACKUP_DIR"/backup_*.sql.gz 2>/dev/null || echo "  No backups found"
    exit 1
fi

# Determine backup file
if [ "$1" = "latest" ]; then
    BACKUP_FILE=$(ls -t "$BACKUP_DIR"/backup_*.sql.gz 2>/dev/null | head -1)
    if [ -z "$BACKUP_FILE" ]; then
        echo -e "${RED}Error: No backups found in $BACKUP_DIR${NC}"
        exit 1
    fi
    echo -e "${YELLOW}Using latest backup: $(basename "$BACKUP_FILE")${NC}"
elif [ -f "$1" ]; then
    BACKUP_FILE="$1"
elif [ -f "$BACKUP_DIR/$1" ]; then
    BACKUP_FILE="$BACKUP_DIR/$1"
else
    echo -e "${RED}Error: Backup file not found: $1${NC}"
    exit 1
fi

# Verify backup file
echo -e "${BLUE}Verifying backup file integrity...${NC}"
if ! gunzip -t "$BACKUP_FILE" 2>/dev/null; then
    echo -e "${RED}Error: Backup file is corrupted!${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Backup file is valid${NC}"

# Load DATABASE_URL from environment
if [ -f /root/classroom-economy/.env ]; then
    export $(grep "^DATABASE_URL=" /root/classroom-economy/.env | xargs)
fi

if [ -z "$DATABASE_URL" ]; then
    echo -e "${RED}ERROR: DATABASE_URL not found in .env file${NC}"
    exit 1
fi

# Show backup info
BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
BACKUP_DATE=$(stat -c %y "$BACKUP_FILE" | cut -d' ' -f1,2 | cut -d'.' -f1)
echo
echo -e "${BLUE}Restore Information:${NC}"
echo "  Backup file: $BACKUP_FILE"
echo "  File size: $BACKUP_SIZE"
echo "  Created: $BACKUP_DATE"
echo

# Confirmation prompt
echo -e "${RED}⚠️  WARNING: This will REPLACE the current database!${NC}"
echo -e "${RED}⚠️  All current data will be LOST!${NC}"
echo
read -p "Are you sure you want to continue? (type 'YES' to confirm): " CONFIRM

if [ "$CONFIRM" != "YES" ]; then
    echo "Restore cancelled."
    exit 0
fi

echo
echo -e "${BLUE}Starting database restore...${NC}"

# Stop application server to prevent connections during restore
echo "Stopping Gunicorn..."
sudo systemctl stop gunicorn || true

# Terminate active connections (recommended)
echo "Terminating active connections to the database..."
psql "$DATABASE_URL" -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = current_database() AND pid <> pg_backend_pid();" || true
# Restore database
echo "Restoring database..."
gunzip -c "$BACKUP_FILE" | psql "$DATABASE_URL"

echo -e "${GREEN}✓ Database restored successfully${NC}"

# Restart application server
echo "Starting Gunicorn..."
sudo systemctl start gunicorn

echo
echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  Database restore completed successfully!                  ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
echo
echo "Next steps:"
echo "  1. Verify application is running: sudo systemctl status gunicorn"
echo "  2. Test login and basic functionality"
echo "  3. Check application logs: tail -f /var/log/classroom-token-hub/app.log"
echo

exit 0
