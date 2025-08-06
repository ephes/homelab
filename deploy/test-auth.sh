#!/bin/bash
# Test script for Traefik authentication setup

echo "=== Traefik Authentication Test Script ==="
echo ""
echo "This script will help you test the conditional authentication setup."
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

URL="https://home.wersdörfer.de"

echo -e "${BLUE}1. Testing from external IP (should require authentication):${NC}"
echo "   curl -I $URL"
curl -I "$URL" 2>/dev/null | head -n 1
echo ""

echo -e "${BLUE}2. Testing with basic auth credentials:${NC}"
echo "   curl -I -u admin:YOUR_PASSWORD $URL"
echo "   (Replace YOUR_PASSWORD with the actual password)"
echo ""

echo -e "${BLUE}3. To test from Tailscale (should bypass auth):${NC}"
echo "   - Connect via Tailscale VPN"
echo "   - Run: curl -I $URL"
echo "   - Should return 200 OK without authentication"
echo ""

echo -e "${GREEN}Configuration Summary:${NC}"
echo "- Tailscale IP range: 100.64.0.0/10"
echo "- Basic auth user: admin"
echo "- Password location: deploy/secrets.yml (encrypted)"
echo ""

echo -e "${GREEN}Deployment command:${NC}"
echo "ansible-playbook -i inventory/hosts.yml deploy-traefik.yml --ask-vault-pass"
echo ""

echo -e "${RED}Important:${NC}"
echo "1. Replace the dummy password in secrets.yml before deployment!"
echo "2. Use 'ansible-vault edit deploy/secrets.yml' to change the password"
echo "3. The password will be hashed with bcrypt during deployment"