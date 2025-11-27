#!/bin/bash
#
# Add UptimeRobot IPs to DigitalOcean Firewall
#
# This script automatically fetches UptimeRobot's monitoring IPs and adds them
# to your DigitalOcean firewall, allowing health check monitoring while keeping
# your server protected behind Cloudflare.
#
# Prerequisites:
#   - doctl installed and authenticated
#   - Firewall already created (get ID with: doctl compute firewall list)
#
# Usage:
#   ./add-uptimerobot-to-firewall.sh <firewall-id>
#
# Example:
#   ./add-uptimerobot-to-firewall.sh abc12345-6789-0def-1234-56789abcdef0

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# UptimeRobot IPv4 addresses sourced from firewall-ips.json
# Source: https://uptimerobot.com/help/locations/
if ! command -v jq &> /dev/null; then
    echo -e "${RED}Error: jq is not installed. It's required to read IP addresses from firewall-ips.json.${NC}"
    echo "Install: sudo apt-get install jq (or brew install jq on macOS)"
    exit 1
fi
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
UPTIMEROBOT_IPS=($(jq -r '.uptimerobot.ipv4[]' "$SCRIPT_DIR/firewall-ips.json"))

# Check if firewall ID is provided
if [ -z "$1" ]; then
    echo -e "${RED}Error: Firewall ID required${NC}"
    echo ""
    echo "Usage: $0 <firewall-id>"
    echo ""
    echo "To find your firewall ID, run:"
    echo "  doctl compute firewall list"
    echo ""
    echo "Example:"
    echo "  $0 abc12345-6789-0def-1234-56789abcdef0"
    exit 1
fi

FIREWALL_ID="$1"

# Check if doctl is installed
if ! command -v doctl &> /dev/null; then
    echo -e "${RED}Error: doctl is not installed${NC}"
    echo ""
    echo "Install doctl:"
    echo "  https://docs.digitalocean.com/reference/doctl/how-to/install/"
    echo ""
    echo "macOS:"
    echo "  brew install doctl"
    echo ""
    echo "Linux:"
    echo "  cd ~"
    echo "  wget https://github.com/digitalocean/doctl/releases/download/v1.104.0/doctl-1.104.0-linux-amd64.tar.gz"
    echo "  tar xf doctl-1.104.0-linux-amd64.tar.gz"
    echo "  sudo mv doctl /usr/local/bin"
    exit 1
fi

# Check if authenticated
if ! doctl account get &> /dev/null; then
    echo -e "${RED}Error: doctl not authenticated${NC}"
    echo ""
    echo "Authenticate doctl:"
    echo "  doctl auth init"
    echo ""
    echo "You'll need a DigitalOcean API token from:"
    echo "  https://cloud.digitalocean.com/account/api/tokens"
    exit 1
fi

# Verify firewall exists
if ! doctl compute firewall get "$FIREWALL_ID" &> /dev/null; then
    echo -e "${RED}Error: Firewall '$FIREWALL_ID' not found${NC}"
    echo ""
    echo "Available firewalls:"
    doctl compute firewall list --format ID,Name,Status
    exit 1
fi

echo -e "${GREEN}Adding UptimeRobot IPs to firewall: $FIREWALL_ID${NC}"
echo ""

# Get current firewall rules
FIREWALL_NAME=$(doctl compute firewall get "$FIREWALL_ID" --format Name --no-header)
echo "Firewall name: $FIREWALL_NAME"
echo ""

# Add each UptimeRobot IP to the firewall
echo "Adding ${#UPTIMEROBOT_IPS[@]} UptimeRobot IP addresses..."
echo ""

SUCCESS_COUNT=0
SKIP_COUNT=0
ERROR_COUNT=0

for IP in "${UPTIMEROBOT_IPS[@]}"; do
    echo -n "Adding $IP ... "

    # Add rule for HTTPS (443) - health checks use HTTPS
    if doctl compute firewall add-rules "$FIREWALL_ID" \
        --inbound-rules "protocol:tcp,ports:443,address:$IP" &> /dev/null; then
        echo -e "${GREEN}✓${NC}"
        ((SUCCESS_COUNT++))
    else
        # Check if it already exists (doctl returns error if rule already exists)
        if doctl compute firewall get "$FIREWALL_ID" --format InboundRules --no-header | grep -q "$IP"; then
            echo -e "${YELLOW}(already exists)${NC}"
            ((SKIP_COUNT++))
        else
            echo -e "${RED}✗ failed${NC}"
            ((ERROR_COUNT++))
        fi
    fi
done

echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}Summary:${NC}"
echo -e "  Added:          ${GREEN}$SUCCESS_COUNT${NC}"
echo -e "  Already exists: ${YELLOW}$SKIP_COUNT${NC}"
echo -e "  Failed:         ${RED}$ERROR_COUNT${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

if [ $ERROR_COUNT -gt 0 ]; then
    echo -e "${YELLOW}Warning: Some IPs failed to add. Check the output above.${NC}"
    exit 1
fi

echo -e "${GREEN}✓ UptimeRobot IPs successfully added to firewall!${NC}"
echo ""
echo "Next steps:"
echo "  1. Verify rules: doctl compute firewall get $FIREWALL_ID"
echo "  2. Test UptimeRobot monitoring"
echo "  3. Check app logs for successful health checks"
