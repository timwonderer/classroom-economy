#!/usr/bin/env python3
"""
Create a separate firewall for GitHub Actions deployment access.

Since DigitalOcean limits firewalls to 50 inbound rules and GitHub has ~70 IPs,
we create a dedicated firewall. Multiple firewalls can be applied to one droplet.

Usage:
    python3 scripts/create-github-actions-firewall.py <droplet-id>
"""

import json
import subprocess
import sys
import urllib.request

# ANSI colors
GREEN = '\033[0;32m'
RED = '\033[0;31m'
YELLOW = '\033[1;33m'
BLUE = '\033[0;34m'
NC = '\033[0m'

def run_command(cmd, capture=True):
    """Run a shell command."""
    if capture:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return result.returncode == 0, result.stdout, result.stderr
    else:
        result = subprocess.run(cmd, shell=True)
        return result.returncode == 0, "", ""

def fetch_github_ips():
    """Fetch GitHub Actions IP ranges from GitHub API."""
    print(f"{BLUE}Fetching GitHub Actions IP ranges from api.github.com...{NC}")

    try:
        with urllib.request.urlopen('https://api.github.com/meta', timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))

        actions_ips = data.get('actions', [])
        if not actions_ips:
            actions_ips = data.get('hooks', [])

        return actions_ips
    except Exception as e:
        print(f"{RED}Error fetching GitHub IPs: {e}{NC}")
        return None

def create_firewall_with_rules(droplet_id, github_ips):
    """Create firewall using doctl with rules in batches."""

    firewall_name = "github-actions-ssh"

    print(f"\n{BLUE}Creating firewall: {firewall_name}{NC}")

    # Split IPs into batches of 50 (doctl limit per rule add operation)
    batch_size = 50
    batches = [github_ips[i:i + batch_size] for i in range(0, len(github_ips), batch_size)]

    print(f"Processing {len(github_ips)} IPs in {len(batches)} batch(es)...")

    # Build inbound rules JSON for first batch (used during creation)
    first_batch = batches[0]
    inbound_rules = []

    for ip in first_batch:
        inbound_rules.append({
            "protocol": "tcp",
            "ports": "22",
            "sources": {
                "addresses": [ip]
            }
        })

    inbound_rules_json = json.dumps(inbound_rules)

    # Create firewall with first batch of rules
    create_cmd = f"""doctl compute firewall create \
        --name "{firewall_name}" \
        --inbound-rules '{inbound_rules_json}' \
        --outbound-rules '[{{"protocol":"tcp","ports":"all","destinations":{{"addresses":["0.0.0.0/0","::/0"]}}}},{{"protocol":"udp","ports":"all","destinations":{{"addresses":["0.0.0.0/0","::/0"]}}}},{{"protocol":"icmp","destinations":{{"addresses":["0.0.0.0/0","::/0"]}}}}]' \
        --droplet-ids {droplet_id} \
        --format ID \
        --no-header"""

    success, firewall_id, error = run_command(create_cmd)

    if not success:
        print(f"{RED}Failed to create firewall{NC}")
        print(f"Error: {error}")
        return None

    firewall_id = firewall_id.strip()
    print(f"{GREEN}✓ Firewall created: {firewall_id}{NC}")
    print(f"  Added {len(first_batch)} rules in initial batch")

    # Add remaining batches
    if len(batches) > 1:
        for i, batch in enumerate(batches[1:], start=2):
            print(f"\n{BLUE}Adding batch {i}/{len(batches)} ({len(batch)} IPs)...{NC}")

            for ip in batch:
                cmd = f'doctl compute firewall add-rules {firewall_id} --inbound-rules "protocol:tcp,ports:22,address:{ip}" 2>&1'
                success, _, error = run_command(cmd)

                if not success and "already exists" not in error.lower():
                    print(f"{YELLOW}Warning: Failed to add {ip}: {error.strip()}{NC}")

            print(f"{GREEN}✓ Batch {i} complete{NC}")

    return firewall_id

def main():
    if len(sys.argv) != 2:
        print(f"{RED}Error: Droplet ID required{NC}")
        print("\nUsage:")
        print(f"  python3 {sys.argv[0]} <droplet-id>")
        print("\nExample:")
        print(f"  python3 {sys.argv[0]} 487710074")
        print("\nGet your droplet ID:")
        print("  doctl compute droplet list")
        sys.exit(1)

    droplet_id = sys.argv[1]

    # Verify doctl
    success, _, _ = run_command('doctl version > /dev/null 2>&1')
    if not success:
        print(f"{RED}Error: doctl not installed{NC}")
        sys.exit(1)

    # Verify droplet exists
    success, _, _ = run_command(f'doctl compute droplet get {droplet_id} > /dev/null 2>&1')
    if not success:
        print(f"{RED}Error: Droplet '{droplet_id}' not found{NC}")
        print("\nAvailable droplets:")
        run_command('doctl compute droplet list', capture=False)
        sys.exit(1)

    # Check if firewall already exists
    success, output, _ = run_command('doctl compute firewall list --format ID,Name --no-header')
    if success and 'github-actions-ssh' in output:
        print(f"{YELLOW}Warning: Firewall 'github-actions-ssh' already exists{NC}")
        print("Delete it first with:")
        for line in output.strip().split('\n'):
            if 'github-actions-ssh' in line:
                fw_id = line.split()[0]
                print(f"  doctl compute firewall delete {fw_id}")
        sys.exit(1)

    # Fetch GitHub IPs
    github_ips = fetch_github_ips()
    if not github_ips:
        print(f"{RED}Failed to fetch GitHub Actions IPs{NC}")
        sys.exit(1)

    print(f"{GREEN}Found {len(github_ips)} GitHub Actions IP ranges{NC}")

    if len(github_ips) > 50:
        print(f"{YELLOW}Note: GitHub has {len(github_ips)} IPs, which exceeds DO's 50-rule limit{NC}")
        print(f"{YELLOW}We'll create the firewall and add as many as possible{NC}")

    # Create firewall
    firewall_id = create_firewall_with_rules(droplet_id, github_ips)

    if not firewall_id:
        sys.exit(1)

    print()
    print(f"{GREEN}{'=' * 60}{NC}")
    print(f"{GREEN}✓ GitHub Actions firewall created successfully!{NC}")
    print(f"{GREEN}{'=' * 60}{NC}")
    print()
    print(f"Firewall ID: {firewall_id}")
    print(f"Firewall Name: github-actions-ssh")
    print(f"Applied to Droplet: {droplet_id}")
    print()
    print(f"{BLUE}View firewall:{NC}")
    print(f"  doctl compute firewall get {firewall_id}")
    print()
    print(f"{BLUE}List all firewalls on droplet:{NC}")
    print(f"  doctl compute firewall list --format ID,Name,DropletIDs")
    print()
    print(f"{YELLOW}Note: Multiple firewalls are active on your droplet.{NC}")
    print(f"{YELLOW}All rules from all firewalls apply.{NC}")

if __name__ == '__main__':
    main()
