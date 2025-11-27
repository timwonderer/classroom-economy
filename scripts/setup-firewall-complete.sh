#!/bin/bash
#
# Complete DigitalOcean Firewall Setup for Cloudflare + UptimeRobot
#
# This script creates or updates a DigitalOcean firewall with all necessary
# rules for Cloudflare proxy and UptimeRobot monitoring.
#
# Prerequisites:
#   - doctl installed and authenticated
#   - jq installed (for JSON processing)
#
# Usage:
#   # Create new firewall
#   ./setup-firewall-complete.sh create <droplet-id> <ssh-ip>
#
#   # Update existing firewall
#   ./setup-firewall-complete.sh update <firewall-id>
#
# Examples:
#   ./setup-firewall-complete.sh create 123456789 "203.0.113.50"
#   ./setup-firewall-complete.sh update abc12345-6789-0def-1234-56789abcdef0

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Source IPs from the JSON file
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
CLOUDFLARE_IPV4=($(jq -r '.cloudflare.ipv4[]' "$SCRIPT_DIR/firewall-ips.json"))
CLOUDFLARE_IPV6=($(jq -r '.cloudflare.ipv6[]' "$SCRIPT_DIR/firewall-ips.json"))
UPTIMEROBOT_IPS=($(jq -r '.uptimerobot.ipv4[]' "$SCRIPT_DIR/firewall-ips.json"))

# Function to check prerequisites
check_prerequisites() {
    echo -e "${BLUE}Checking prerequisites...${NC}"

    # Check doctl
    if ! command -v doctl &> /dev/null; then
        echo -e "${RED}Error: doctl is not installed${NC}"
        echo "Install: https://docs.digitalocean.com/reference/doctl/how-to/install/"
        exit 1
    fi

    # Check jq
    if ! command -v jq &> /dev/null; then
        echo -e "${RED}Error: jq is not installed${NC}"
        echo "Install: sudo apt-get install jq  (or brew install jq on macOS)"
        exit 1
    fi

    # Check authentication
    if ! doctl account get &> /dev/null; then
        echo -e "${RED}Error: doctl not authenticated${NC}"
        echo "Run: doctl auth init"
        exit 1
    fi

    echo -e "${GREEN}✓ All prerequisites met${NC}\n"
}

# Function to build inbound rules JSON
build_inbound_rules() {
    local SSH_IP="$1"
    local RULES="["

    # Add SSH rule if IP provided
    if [ -n "$SSH_IP" ]; then
        RULES+="{\"protocol\":\"tcp\",\"ports\":\"22\",\"sources\":{\"addresses\":[\"$SSH_IP\"]}},"
    fi

    # Add Cloudflare HTTP rules (IPv4)
    for IP in "${CLOUDFLARE_IPV4[@]}"; do
        RULES+="{\"protocol\":\"tcp\",\"ports\":\"80\",\"sources\":{\"addresses\":[\"$IP\"]}},"
    done

    # Add Cloudflare HTTPS rules (IPv4)
    for IP in "${CLOUDFLARE_IPV4[@]}"; do
        RULES+="{\"protocol\":\"tcp\",\"ports\":\"443\",\"sources\":{\"addresses\":[\"$IP\"]}},"
    done

    # Add Cloudflare HTTP rules (IPv6)
    for IP in "${CLOUDFLARE_IPV6[@]}"; do
        RULES+="{\"protocol\":\"tcp\",\"ports\":\"80\",\"sources\":{\"addresses\":[\"$IP\"]}},"
    done

    # Add Cloudflare HTTPS rules (IPv6)
    for IP in "${CLOUDFLARE_IPV6[@]}"; do
        RULES+="{\"protocol\":\"tcp\",\"ports\":\"443\",\"sources\":{\"addresses\":[\"$IP\"]}},"
    done

    # Add UptimeRobot HTTPS rules
    for IP in "${UPTIMEROBOT_IPS[@]}"; do
        RULES+="{\"protocol\":\"tcp\",\"ports\":\"443\",\"sources\":{\"addresses\":[\"$IP\"]}},"
    done

    # Remove trailing comma and close array
    RULES="${RULES%,}]"

    echo "$RULES"
}

# Function to create new firewall
create_firewall() {
    local DROPLET_ID="$1"
    local SSH_IP="$2"

    if [ -z "$DROPLET_ID" ]; then
        echo -e "${RED}Error: Droplet ID required${NC}"
        echo "Usage: $0 create <droplet-id> <ssh-ip>"
        echo ""
        echo "Find your droplet ID:"
        echo "  doctl compute droplet list"
        exit 1
    fi

    if [ -z "$SSH_IP" ]; then
        echo -e "${YELLOW}Warning: No SSH IP provided. You won't be able to SSH!${NC}"
        echo -e "${YELLOW}Press Ctrl+C to cancel, or Enter to continue...${NC}"
        read
    fi

    echo -e "${BLUE}Creating firewall...${NC}\n"

    # Build rules JSON
    INBOUND_RULES=$(build_inbound_rules "$SSH_IP")

    # Create firewall
    FIREWALL_NAME="cloudflare-uptimerobot-firewall"

    echo "Firewall configuration:"
    echo "  Name: $FIREWALL_NAME"
    echo "  Cloudflare IPv4 ranges: ${#CLOUDFLARE_IPV4[@]}"
    echo "  Cloudflare IPv6 ranges: ${#CLOUDFLARE_IPV6[@]}"
    echo "  UptimeRobot IPs: ${#UPTIMEROBOT_IPS[@]}"
    echo "  SSH IP: ${SSH_IP:-none}"
    echo "  Total inbound rules: $(echo "$INBOUND_RULES" | jq '. | length')"
    echo ""

    # Create via doctl
    FIREWALL_ID=$(doctl compute firewall create \
        --name "$FIREWALL_NAME" \
        --inbound-rules "$INBOUND_RULES" \
        --outbound-rules '[{"protocol":"tcp","ports":"all","destinations":{"addresses":["0.0.0.0/0","::/0"]}},{"protocol":"udp","ports":"all","destinations":{"addresses":["0.0.0.0/0","::/0"]}},{"protocol":"icmp","destinations":{"addresses":["0.0.0.0/0","::/0"]}}]' \
        --droplet-ids "$DROPLET_ID" \
        --format ID \
        --no-header)

    echo -e "${GREEN}✓ Firewall created: $FIREWALL_ID${NC}\n"

    # Show summary
    doctl compute firewall get "$FIREWALL_ID"

    echo ""
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}Firewall setup complete!${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. Test your website through Cloudflare (should work)"
    echo "  2. Try accessing droplet IP directly (should timeout)"
    echo "  3. Test UptimeRobot monitoring"
    echo "  4. Verify SSH access works from $SSH_IP"
}

# Function to update existing firewall
update_firewall() {
    local FIREWALL_ID="$1"

    if [ -z "$FIREWALL_ID" ]; then
        echo -e "${RED}Error: Firewall ID required${NC}"
        echo "Usage: $0 update <firewall-id>"
        echo ""
        echo "Find your firewall ID:"
        echo "  doctl compute firewall list"
        exit 1
    fi

    # Verify firewall exists
    if ! doctl compute firewall get "$FIREWALL_ID" &> /dev/null; then
        echo -e "${RED}Error: Firewall not found${NC}"
        echo ""
        echo "Available firewalls:"
        doctl compute firewall list
        exit 1
    fi

    echo -e "${BLUE}Updating firewall: $FIREWALL_ID${NC}\n"

    # Add Cloudflare IPs
    echo "Adding Cloudflare IP ranges..."
    ADD_COUNT=0

    for IP in "${CLOUDFLARE_IPV4[@]}"; do
        if doctl compute firewall add-rules "$FIREWALL_ID" \
            --inbound-rules "protocol:tcp,ports:80,address:$IP" &> /dev/null; then
            ((ADD_COUNT++))
        fi
        if doctl compute firewall add-rules "$FIREWALL_ID" \
            --inbound-rules "protocol:tcp,ports:443,address:$IP" &> /dev/null; then
            ((ADD_COUNT++))
        fi
    done

    for IP in "${CLOUDFLARE_IPV6[@]}"; do
        if doctl compute firewall add-rules "$FIREWALL_ID" \
            --inbound-rules "protocol:tcp,ports:80,address:$IP" &> /dev/null; then
            ((ADD_COUNT++))
        fi
        if doctl compute firewall add-rules "$FIREWALL_ID" \
            --inbound-rules "protocol:tcp,ports:443,address:$IP" &> /dev/null; then
            ((ADD_COUNT++))
        fi
    done

    echo "  Added $ADD_COUNT Cloudflare rules"

    # Add UptimeRobot IPs
    echo "Adding UptimeRobot IP addresses..."
    ROBOT_COUNT=0

    for IP in "${UPTIMEROBOT_IPS[@]}"; do
        if doctl compute firewall add-rules "$FIREWALL_ID" \
            --inbound-rules "protocol:tcp,ports:443,address:$IP" &> /dev/null; then
            ((ROBOT_COUNT++))
        fi
    done

    echo "  Added $ROBOT_COUNT UptimeRobot rules"
    echo ""
    echo -e "${GREEN}✓ Firewall updated successfully!${NC}"
}

# Main script
COMMAND="$1"

case "$COMMAND" in
    create)
        check_prerequisites
        create_firewall "$2" "$3"
        ;;
    update)
        check_prerequisites
        update_firewall "$2"
        ;;
    *)
        echo "Usage:"
        echo "  $0 create <droplet-id> [ssh-ip]    # Create new firewall"
        echo "  $0 update <firewall-id>             # Update existing firewall"
        echo ""
        echo "Examples:"
        echo "  $0 create 123456789 \"203.0.113.50\""
        echo "  $0 update abc12345-6789-0def-1234-56789abcdef0"
        echo ""
        echo "Get droplet ID:"
        echo "  doctl compute droplet list"
        echo ""
        echo "Get firewall ID:"
        echo "  doctl compute firewall list"
        exit 1
        ;;
esac
