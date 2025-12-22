#!/bin/bash
#
# SSH Security Setup Script
#
# This script helps you set up SSH host key verification for GitHub Actions
# by generating the KNOWN_HOSTS content that needs to be added to GitHub Secrets.
#
# Usage:
#   ./scripts/setup-ssh-security.sh <production-server-ip>
#
# Example:
#   ./scripts/setup-ssh-security.sh 142.93.123.45
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_header() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
}

# Check if server IP was provided
if [ -z "$1" ]; then
    print_error "Production server IP not provided"
    echo ""
    echo "Usage: $0 <production-server-ip>"
    echo "Example: $0 142.93.123.45"
    echo ""
    exit 1
fi

SERVER_IP="$1"
KNOWN_HOSTS_FILE="known_hosts_github_secret.txt"

print_header "SSH Security Setup for GitHub Actions"

print_info "Production Server IP: $SERVER_IP"
echo ""

# Step 1: Get SSH host keys
print_info "Step 1: Retrieving SSH host keys from production server..."
echo ""

if ! command -v ssh-keyscan &> /dev/null; then
    print_error "ssh-keyscan command not found"
    print_info "Please install OpenSSH client"
    exit 1
fi

# Scan for host keys
print_info "Running: ssh-keyscan -H $SERVER_IP"
if ssh-keyscan -H "$SERVER_IP" > "$KNOWN_HOSTS_FILE" 2>/dev/null; then
    print_success "Successfully retrieved SSH host keys"
else
    print_error "Failed to retrieve SSH host keys"
    print_warning "Make sure the server is reachable and SSH port 22 is open"
    exit 1
fi

# Check if file is not empty
if [ ! -s "$KNOWN_HOSTS_FILE" ]; then
    print_error "No host keys were retrieved"
    print_warning "This could mean:"
    print_warning "  1. The server is not reachable"
    print_warning "  2. SSH is not running on port 22"
    print_warning "  3. A firewall is blocking the connection"
    rm -f "$KNOWN_HOSTS_FILE"
    exit 1
fi

# Step 2: Display the contents
print_header "Step 2: Host Keys Retrieved"

print_success "Host keys saved to: $KNOWN_HOSTS_FILE"
echo ""
print_info "File contents:"
echo "----------------------------------------"
cat "$KNOWN_HOSTS_FILE"
echo "----------------------------------------"
echo ""

# Step 3: Count the keys
KEY_COUNT=$(wc -l < "$KNOWN_HOSTS_FILE")
print_info "Retrieved $KEY_COUNT host key(s)"
echo ""

# Step 4: Instructions for GitHub
print_header "Step 3: Add to GitHub Secrets"

echo "1. Go to your GitHub repository"
echo "2. Navigate to: Settings → Secrets and variables → Actions"
echo "3. Click 'New repository secret'"
echo "4. Name: ${GREEN}KNOWN_HOSTS${NC}"
echo "5. Value: Copy the ENTIRE contents shown above"
echo "   (or run: ${YELLOW}cat $KNOWN_HOSTS_FILE | pbcopy${NC} on macOS)"
echo "   (or run: ${YELLOW}cat $KNOWN_HOSTS_FILE | xclip -selection clipboard${NC} on Linux)"
echo "6. Click 'Add secret'"
echo ""

# Step 5: Workflow update instructions
print_header "Step 4: Update GitHub Actions Workflows"

echo "The following workflow files need to be updated:"
echo ""
echo "1. ${YELLOW}.github/workflows/deploy.yml${NC}"
echo "   - Replace with: ${GREEN}.github/workflows/deploy.yml.FIXED${NC}"
echo ""
echo "2. ${YELLOW}.github/workflows/toggle-maintenance.yml${NC}"
echo "   - Replace with: ${GREEN}.github/workflows/toggle-maintenance.yml.FIXED${NC}"
echo ""
print_info "Or run the following commands:"
echo ""
echo "  ${YELLOW}cp .github/workflows/deploy.yml.FIXED .github/workflows/deploy.yml${NC}"
echo "  ${YELLOW}cp .github/workflows/toggle-maintenance.yml.FIXED .github/workflows/toggle-maintenance.yml${NC}"
echo ""

# Step 6: Verification
print_header "Step 5: Verification"

echo "After updating workflows and adding the secret:"
echo ""
echo "1. Commit and push your workflow changes:"
echo "   ${YELLOW}git add .github/workflows/${NC}"
echo "   ${YELLOW}git commit -m 'SECURITY: Enable SSH host key verification'${NC}"
echo "   ${YELLOW}git push${NC}"
echo ""
echo "2. Trigger a test deployment (or wait for next commit to main)"
echo ""
echo "3. Check GitHub Actions logs for:"
echo "   ${GREEN}✓ SSH host key verification enabled${NC}"
echo "   ${GREEN}✓ Secure .env permissions (600)${NC}"
echo ""
echo "4. Verify no errors about unknown hosts"
echo ""

# Step 7: Security notes
print_header "Security Notes"

print_warning "Important Security Information:"
echo ""
echo "• The host keys are now hashed (you'll see |1|abc...)"
echo "• This makes them harder to use for host scanning attacks"
echo "• Keep the ${YELLOW}$KNOWN_HOSTS_FILE${NC} file secure"
echo "• You can delete it after adding to GitHub Secrets"
echo "• If your server is recreated, you'll need to update this secret"
echo ""

print_info "What this protects against:"
echo "  ✓ Man-in-the-Middle (MITM) attacks during deployment"
echo "  ✓ DNS spoofing attacks"
echo "  ✓ Rogue server impersonation"
echo "  ✓ Secret theft during deployment"
echo ""

# Step 8: Cleanup option
print_header "Cleanup"

read -p "Do you want to delete $KNOWN_HOSTS_FILE now? (y/n): " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    rm -f "$KNOWN_HOSTS_FILE"
    print_success "Deleted $KNOWN_HOSTS_FILE"
    print_info "Make sure you've copied the contents to GitHub Secrets first!"
else
    print_info "Keeping $KNOWN_HOSTS_FILE"
    print_warning "Remember to delete it after adding to GitHub Secrets"
fi

echo ""
print_success "Setup complete!"
echo ""
print_info "Next steps:"
echo "  1. Add KNOWN_HOSTS to GitHub Secrets"
echo "  2. Update workflow files"
echo "  3. Test deployment"
echo ""
print_info "For detailed instructions, see:"
echo "  ${YELLOW}docs/security/SECURITY_REMEDIATION_GUIDE.md${NC}"
echo ""
