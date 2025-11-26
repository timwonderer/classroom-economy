#!/bin/bash
#
# UptimeRobot Monitoring Test Script
# Tests the health check endpoints to verify they work correctly
#

set -e  # Exit on error

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
BASE_URL="${1:-http://localhost:5000}"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}   UptimeRobot Monitoring Test${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "Testing endpoint: ${YELLOW}${BASE_URL}${NC}"
echo ""

# Test 1: Basic health check
echo -e "${BLUE}Test 1: Basic Health Check (/health)${NC}"
echo "Testing: ${BASE_URL}/health"
RESPONSE=$(curl -s -w "\n%{http_code}" "${BASE_URL}/health")
HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | head -n-1)

if [ "$HTTP_CODE" = "200" ] && [ "$BODY" = "ok" ]; then
    echo -e "${GREEN}✓ PASSED${NC} - Health check returned 200 OK"
    echo "  Response: $BODY"
else
    echo -e "${RED}✗ FAILED${NC} - Expected 200 'ok', got $HTTP_CODE '$BODY'"
    exit 1
fi
echo ""

# Test 2: Deep health check
echo -e "${BLUE}Test 2: Deep Health Check (/health/deep)${NC}"
echo "Testing: ${BASE_URL}/health/deep"
RESPONSE=$(curl -s -w "\n%{http_code}" "${BASE_URL}/health/deep")
HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | head -n-1)

if [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}✓ PASSED${NC} - Deep health check returned 200 OK"
    echo "  Response preview:"
    echo "$BODY" | head -c 200
    echo "..."

    # Check if JSON contains expected fields
    if echo "$BODY" | grep -q '"status"' && echo "$BODY" | grep -q '"checks"'; then
        echo -e "${GREEN}✓${NC} Response contains expected JSON structure"
    else
        echo -e "${YELLOW}⚠${NC} Warning: Response may not have expected structure"
    fi
else
    echo -e "${RED}✗ FAILED${NC} - Expected 200, got $HTTP_CODE"
    echo "  Response: $BODY"
    exit 1
fi
echo ""

# Test 3: Verify public accessibility (no auth required)
echo -e "${BLUE}Test 3: Public Accessibility${NC}"
echo "Verifying endpoints don't require authentication..."

# Test with explicit no-credentials
RESPONSE=$(curl -s -w "\n%{http_code}" -H "Cookie: " "${BASE_URL}/health")
HTTP_CODE=$(echo "$RESPONSE" | tail -n1)

if [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}✓ PASSED${NC} - /health is publicly accessible (no auth required)"
else
    echo -e "${RED}✗ FAILED${NC} - Endpoint may require authentication"
    exit 1
fi
echo ""

# Summary and UptimeRobot Configuration
echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}All tests passed!${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "${YELLOW}UptimeRobot Configuration Guide:${NC}"
echo ""
echo "1. Basic Monitoring (Recommended):"
echo "   URL: ${BASE_URL}/health"
echo "   Expected Response: 'ok'"
echo "   Expected Status: 200"
echo ""
echo "2. Advanced Monitoring (Optional):"
echo "   URL: ${BASE_URL}/health/deep"
echo "   Expected Response: Contains 'status': 'ok'"
echo "   Expected Status: 200"
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo "1. Add monitor in UptimeRobot dashboard"
echo "2. Set monitoring interval (5 minutes recommended)"
echo "3. Create public status page"
echo "4. Set STATUS_PAGE_URL environment variable"
echo "   Example: export STATUS_PAGE_URL='https://stats.uptimerobot.com/your-page'"
echo ""
echo -e "${BLUE}========================================${NC}"
