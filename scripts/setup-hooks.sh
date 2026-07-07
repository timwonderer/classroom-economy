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

# Use versioned hooks directory so hooks are shared via git.
echo "📋 Configuring git to use versioned hooks/ directory..."
git config core.hooksPath hooks
echo -e "${GREEN}✓ core.hooksPath set to hooks${NC}"

# Summary
echo ""
echo -e "${GREEN}┌─────────────────────────────────────────────────┐${NC}"
echo -e "${GREEN}│            Setup Complete! ✓                    │${NC}"
echo -e "${GREEN}└─────────────────────────────────────────────────┘${NC}"
echo ""
echo "The following hooks have been installed:"
echo "  • post-checkout: Normalize DATABASE_URL to classroom_economy"
echo "  • pre-push: Checks for multiple migration heads"
echo ""
echo "These hooks will run automatically during git operations."
echo "Note: git push --no-verify bypasses pre-push checks (not recommended)."
echo ""
