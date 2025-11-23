#!/bin/bash
#
# Setup script to install git hooks for the Classroom Token Hub project
# Run this script after cloning the repository to enable automated checks
#

set -e  # Exit on error

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}┌─────────────────────────────────────────────────┐${NC}"
echo -e "${BLUE}│   Classroom Token Hub - Git Hooks Setup        │${NC}"
echo -e "${BLUE}└─────────────────────────────────────────────────┘${NC}"
echo ""

# Get the root directory of the git repository
GIT_ROOT=$(git rev-parse --show-toplevel 2>/dev/null)

if [ -z "$GIT_ROOT" ]; then
    echo -e "${YELLOW}⚠️  Error: Not in a git repository${NC}"
    exit 1
fi

cd "$GIT_ROOT"

# Check if hooks directory exists
if [ ! -d "hooks" ]; then
    echo -e "${YELLOW}⚠️  Error: hooks/ directory not found${NC}"
    echo "   Make sure you're running this from the project root"
    exit 1
fi

# Install pre-push hook
echo "📋 Installing pre-push hook..."
if [ -f "hooks/pre-push" ]; then
    cp hooks/pre-push .git/hooks/pre-push
    chmod +x .git/hooks/pre-push
    echo -e "${GREEN}✓ Pre-push hook installed${NC}"
else
    echo -e "${YELLOW}⚠️  Warning: hooks/pre-push not found, skipping${NC}"
fi

# Summary
echo ""
echo -e "${GREEN}┌─────────────────────────────────────────────────┐${NC}"
echo -e "${GREEN}│            Setup Complete! ✓                    │${NC}"
echo -e "${GREEN}└─────────────────────────────────────────────────┘${NC}"
echo ""
echo "The following hooks have been installed:"
echo "  • pre-push: Checks for multiple migration heads"
echo ""
echo "These hooks will run automatically during git operations."
echo "To bypass a hook, use the --no-verify flag (not recommended)."
echo ""
