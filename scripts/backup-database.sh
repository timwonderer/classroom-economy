#!/bin/bash
#
# Automated PostgreSQL Database Backup Script
#
# This script creates daily compressed backups of the PostgreSQL database
# with automatic rotation (keeps last 30 days).
#
# Setup:
#   1. Make executable: chmod +x scripts/backup-database.sh
#   2. Add to crontab: crontab -e
#   3. Add line: 0 2 * * * /root/classroom-economy/scripts/backup-database.sh
#      (runs daily at 2 AM)
#
# Usage:
#   ./scripts/backup-database.sh
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
DATE=$(date +%Y%m%d_%H%M%S)
RETENTION_DAYS=30
LOG_FILE="/var/log/db-backup.log"

# Ensure backup directory exists
mkdir -p "$BACKUP_DIR"

# Log function
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

log "Starting database backup..."

# Load DATABASE_URL from environment
if [ -f /root/classroom-economy/.env ]; then
    DATABASE_URL=$(grep "^DATABASE_URL=" /root/classroom-economy/.env | cut -d'=' -f2-)
    export DATABASE_URL
fi

if [ -z "$DATABASE_URL" ]; then
    log "${RED}ERROR: DATABASE_URL not found in .env file${NC}"
    exit 1
fi

# Create backup filename
BACKUP_FILE="$BACKUP_DIR/backup_$DATE.sql.gz"

# Perform backup with compression
log "Creating backup: $BACKUP_FILE"
if pg_dump "$DATABASE_URL" | gzip > "$BACKUP_FILE"; then
    BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    log "${GREEN}✓ Backup completed successfully${NC}"
    log "  File: $BACKUP_FILE"
    log "  Size: $BACKUP_SIZE"
else
    log "${RED}✗ Backup failed!${NC}"
    exit 1
fi

# Verify backup integrity
log "Verifying backup integrity..."
if gunzip -t "$BACKUP_FILE" 2>/dev/null; then
    log "${GREEN}✓ Backup file integrity verified${NC}"
else
    log "${RED}✗ Backup file is corrupted!${NC}"
    exit 1
fi

# Clean up old backups (keep last 30 days)
log "Cleaning up old backups (retention: $RETENTION_DAYS days)..."
DELETED_COUNT=$(find "$BACKUP_DIR" -name "backup_*.sql.gz" -mtime +$RETENTION_DAYS -delete -print | wc -l)
if [ "$DELETED_COUNT" -gt 0 ]; then
    log "  Deleted $DELETED_COUNT old backup(s)"
else
    log "  No old backups to delete"
fi

# Show current backups
TOTAL_BACKUPS=$(ls -1 "$BACKUP_DIR"/backup_*.sql.gz 2>/dev/null | wc -l)
TOTAL_SIZE=$(du -sh "$BACKUP_DIR" | cut -f1)
log "Current backup status:"
log "  Total backups: $TOTAL_BACKUPS"
log "  Total size: $TOTAL_SIZE"

log "${GREEN}Backup process completed successfully${NC}"

# Optional: Upload to remote storage (uncomment if using)
# Example for DigitalOcean Spaces (requires s3cmd or aws cli)
# log "Uploading to remote storage..."
# s3cmd put "$BACKUP_FILE" s3://your-bucket/backups/
# log "✓ Remote upload completed"

exit 0
