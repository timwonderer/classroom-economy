#!/bin/bash
#
# Secure SSH for GitHub Actions Deployments
#
# This script hardens SSH configuration and sets up fail2ban to protect
# against brute force attacks while keeping SSH open for GitHub Actions.
#
# Usage:
#   sudo ./secure-ssh-for-github-actions.sh

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  Securing SSH for GitHub Actions Deployments              ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Error: This script must be run as root${NC}"
    echo "Run: sudo $0"
    exit 1
fi

# Backup SSH config
echo -e "${BLUE}Backing up SSH configuration...${NC}"
cp /etc/ssh/sshd_config /etc/ssh/sshd_config.backup.$(date +%Y%m%d-%H%M%S)
echo -e "${GREEN}✓ Backup created${NC}"

# Update SSH configuration
echo -e "${BLUE}Hardening SSH configuration...${NC}"

# Check and update SSH settings
update_ssh_config() {
    local setting="$1"
    local value="$2"

    if grep -q "^${setting}" /etc/ssh/sshd_config; then
        sed -i "s/^${setting}.*/${setting} ${value}/" /etc/ssh/sshd_config
    else
        echo "${setting} ${value}" >> /etc/ssh/sshd_config
    fi
}

# Apply secure settings
update_ssh_config "PasswordAuthentication" "no"
update_ssh_config "PubkeyAuthentication" "yes"
update_ssh_config "PermitRootLogin" "prohibit-password"
update_ssh_config "ChallengeResponseAuthentication" "no"
update_ssh_config "UsePAM" "yes"
update_ssh_config "X11Forwarding" "no"
update_ssh_config "MaxAuthTries" "3"
update_ssh_config "MaxSessions" "10"
update_ssh_config "ClientAliveInterval" "300"
update_ssh_config "ClientAliveCountMax" "2"

echo -e "${GREEN}✓ SSH configuration updated${NC}"

# Test SSH configuration
echo -e "${BLUE}Testing SSH configuration...${NC}"
if sshd -t; then
    echo -e "${GREEN}✓ SSH configuration is valid${NC}"
else
    echo -e "${RED}✗ SSH configuration has errors!${NC}"
    echo -e "${YELLOW}Restoring backup...${NC}"
    cp /etc/ssh/sshd_config.backup.* /etc/ssh/sshd_config
    exit 1
fi

# Install fail2ban
echo -e "${BLUE}Installing fail2ban...${NC}"
apt-get update -qq
apt-get install -y -qq fail2ban > /dev/null
echo -e "${GREEN}✓ fail2ban installed${NC}"

# Configure fail2ban
echo -e "${BLUE}Configuring fail2ban...${NC}"

cat > /etc/fail2ban/jail.local <<'EOF'
[DEFAULT]
# Ban hosts for 1 hour (3600 seconds)
bantime = 3600

# A host is banned if it has generated "maxretry" during the last "findtime"
findtime = 600
maxretry = 5

# Destination email for ban notifications (optional)
# destemail = your-email@example.com

[sshd]
enabled = true
port = 22
filter = sshd
logpath = /var/log/auth.log
maxretry = 3
bantime = 3600
EOF

echo -e "${GREEN}✓ fail2ban configured${NC}"

# Start and enable fail2ban
echo -e "${BLUE}Starting fail2ban...${NC}"
systemctl enable fail2ban
systemctl restart fail2ban
echo -e "${GREEN}✓ fail2ban is running${NC}"

# Restart SSH
echo -e "${BLUE}Restarting SSH service...${NC}"
systemctl restart sshd
echo -e "${GREEN}✓ SSH service restarted${NC}"

# Show current SSH connections
echo
echo -e "${YELLOW}════════════════════════════════════════════════════════════${NC}"
echo -e "${YELLOW}Current SSH Sessions:${NC}"
echo -e "${YELLOW}════════════════════════════════════════════════════════════${NC}"
who
echo

# Summary
echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  SSH Security Setup Complete!                              ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
echo
echo -e "${BLUE}Security measures applied:${NC}"
echo -e "  ✓ Password authentication disabled"
echo -e "  ✓ Only SSH key authentication allowed"
echo -e "  ✓ Root login restricted to keys only"
echo -e "  ✓ fail2ban installed and configured"
echo -e "  ✓ Auto-ban after 3 failed attempts in 10 minutes"
echo -e "  ✓ Banned IPs blocked for 1 hour"
echo
echo -e "${BLUE}Check fail2ban status:${NC}"
echo -e "  sudo fail2ban-client status"
echo -e "  sudo fail2ban-client status sshd"
echo
echo -e "${BLUE}View banned IPs:${NC}"
echo -e "  sudo fail2ban-client status sshd"
echo
echo -e "${BLUE}Unban an IP:${NC}"
echo -e "  sudo fail2ban-client set sshd unbanip <IP_ADDRESS>"
echo
echo -e "${YELLOW}⚠️  IMPORTANT: Test SSH in a new terminal BEFORE closing this one!${NC}"
echo -e "${YELLOW}    Make sure you can still connect with your SSH key.${NC}"
echo
echo -e "${GREEN}Your server is now secured for GitHub Actions deployments!${NC}"
