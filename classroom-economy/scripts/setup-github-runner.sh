#!/bin/bash
#
# Setup GitHub Actions Self-Hosted Runner
#
# This sets up a self-hosted runner on your DigitalOcean droplet,
# eliminating the need to whitelist GitHub's 5000+ IP addresses.
#
# Usage:
#   ./setup-github-runner.sh
#
# You'll need a GitHub Personal Access Token with repo permissions.

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  GitHub Actions Self-Hosted Runner Setup                  ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    echo -e "${YELLOW}Warning: Running as root. Will create 'github-runner' user.${NC}"
    CREATE_USER=true
else
    CREATE_USER=false
fi

# Create github-runner user if running as root
if [ "$CREATE_USER" = true ]; then
    if ! id "github-runner" &>/dev/null; then
        echo -e "${BLUE}Creating github-runner user...${NC}"
        useradd -m -s /bin/bash github-runner
        usermod -aG docker github-runner 2>/dev/null || true
        echo -e "${GREEN}✓ User created${NC}"
    fi
    RUNNER_USER="github-runner"
    RUNNER_HOME="/home/github-runner"
else
    RUNNER_USER=$(whoami)
    RUNNER_HOME="$HOME"
fi

echo
echo -e "${BLUE}Runner will be installed for user: ${RUNNER_USER}${NC}"
echo -e "${BLUE}Installation directory: ${RUNNER_HOME}/actions-runner${NC}"
echo

# Install dependencies
echo -e "${BLUE}Installing dependencies...${NC}"
apt-get update -qq
apt-get install -y -qq curl jq tar > /dev/null
echo -e "${GREEN}✓ Dependencies installed${NC}"

# Get latest runner version
echo -e "${BLUE}Fetching latest GitHub runner version...${NC}"
RUNNER_VERSION=$(curl -s https://api.github.com/repos/actions/runner/releases/latest | jq -r '.tag_name' | sed 's/v//')
echo -e "${GREEN}✓ Latest version: ${RUNNER_VERSION}${NC}"

# Download and extract runner
RUNNER_DIR="${RUNNER_HOME}/actions-runner"
echo -e "${BLUE}Downloading GitHub Actions Runner...${NC}"

if [ "$CREATE_USER" = true ]; then
    sudo -u github-runner mkdir -p "$RUNNER_DIR"
    cd "$RUNNER_DIR"
    sudo -u github-runner curl -sL "https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz" | \
        sudo -u github-runner tar xz
else
    mkdir -p "$RUNNER_DIR"
    cd "$RUNNER_DIR"
    curl -sL "https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz" | tar xz
fi

echo -e "${GREEN}✓ Runner downloaded and extracted${NC}"

echo
echo -e "${YELLOW}════════════════════════════════════════════════════════════${NC}"
echo -e "${YELLOW}Next Steps:${NC}"
echo -e "${YELLOW}════════════════════════════════════════════════════════════${NC}"
echo
echo -e "1. Go to your GitHub repository:"
echo -e "   ${BLUE}https://github.com/timwonderer/classroom-economy/settings/actions/runners/new${NC}"
echo
echo -e "2. Copy the registration token shown on that page"
echo
echo -e "3. Run the configuration:"
if [ "$CREATE_USER" = true ]; then
    echo -e "   ${GREEN}sudo -u github-runner /home/github-runner/actions-runner/config.sh \\${NC}"
else
    echo -e "   ${GREEN}cd ${RUNNER_DIR}${NC}"
    echo -e "   ${GREEN}./config.sh \\${NC}"
fi
echo -e "   ${GREEN}  --url https://github.com/timwonderer/classroom-economy \\${NC}"
echo -e "   ${GREEN}  --token YOUR_REGISTRATION_TOKEN${NC}"
echo
echo -e "4. Install as a service:"
if [ "$CREATE_USER" = true ]; then
    echo -e "   ${GREEN}sudo /home/github-runner/actions-runner/svc.sh install github-runner${NC}"
    echo -e "   ${GREEN}sudo /home/github-runner/actions-runner/svc.sh start${NC}"
else
    echo -e "   ${GREEN}sudo ./svc.sh install${NC}"
    echo -e "   ${GREEN}sudo ./svc.sh start${NC}"
fi
echo
echo -e "5. Update your GitHub Actions workflow to use:"
echo -e "   ${GREEN}runs-on: self-hosted${NC}"
echo
echo -e "${YELLOW}════════════════════════════════════════════════════════════${NC}"
