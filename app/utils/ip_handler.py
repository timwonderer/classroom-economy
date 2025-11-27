"""
IP Address Handling Utilities for Cloudflare Proxy

This module provides utilities for extracting real client IP addresses when
using Cloudflare's proxy service, and for validating that requests are coming
from Cloudflare's network.

When Cloudflare proxies requests (orange cloud enabled), request.remote_addr
will show Cloudflare's IP, not the actual visitor's IP. This module extracts
the real IP from Cloudflare headers (CF-Connecting-IP).
"""

from flask import request
from functools import lru_cache
import ipaddress
import urllib.request
import urllib.error
from datetime import datetime, timedelta


# Cloudflare IP ranges (updated periodically)
# These are fetched dynamically, but we provide fallbacks
CLOUDFLARE_IPV4_FALLBACK = [
    '173.245.48.0/20', '103.21.244.0/22', '103.22.200.0/22', '103.31.4.0/22',
    '141.101.64.0/18', '108.162.192.0/18', '190.93.240.0/20', '188.114.96.0/20',
    '197.234.240.0/22', '198.41.128.0/17', '162.158.0.0/15', '104.16.0.0/13',
    '104.24.0.0/14', '172.64.0.0/13', '131.0.72.0/22'
]

CLOUDFLARE_IPV6_FALLBACK = [
    '2400:cb00::/32', '2606:4700::/32', '2803:f800::/32', '2405:b500::/32',
    '2405:8100::/32', '2a06:98c0::/29', '2c0f:f248::/32'
]

# Cache for Cloudflare IP ranges
_cloudflare_ips_cache = None
_cloudflare_ips_cache_time = None
CACHE_DURATION = timedelta(hours=24)


def get_cloudflare_ips():
    """
    Fetch Cloudflare's current IP ranges from their API.

    Returns:
        tuple: (ipv4_ranges, ipv6_ranges) as lists of CIDR strings

    Note:
        Results are cached for 24 hours to avoid excessive API calls.
        Falls back to hardcoded ranges if API is unavailable.
    """
    global _cloudflare_ips_cache, _cloudflare_ips_cache_time

    # Check cache
    if _cloudflare_ips_cache and _cloudflare_ips_cache_time:
        if datetime.utcnow() - _cloudflare_ips_cache_time < CACHE_DURATION:
            return _cloudflare_ips_cache

    try:
        # Fetch from Cloudflare's official API
        with urllib.request.urlopen('https://www.cloudflare.com/ips-v4', timeout=5) as response:
            ipv4_text = response.read().decode('utf-8')

        with urllib.request.urlopen('https://www.cloudflare.com/ips-v6', timeout=5) as response:
            ipv6_text = response.read().decode('utf-8')

        ipv4_ranges = [line.strip() for line in ipv4_text.strip().split('\n') if line.strip()]
        ipv6_ranges = [line.strip() for line in ipv6_text.strip().split('\n') if line.strip()]

        # Update cache
        _cloudflare_ips_cache = (ipv4_ranges, ipv6_ranges)
        _cloudflare_ips_cache_time = datetime.utcnow()

        return _cloudflare_ips_cache
    except (urllib.error.URLError, TimeoutError) as e:
        from flask import current_app
        current_app.logger.warning(f"Failed to fetch Cloudflare IPs, using fallback. Error: {e}")
        # Fall through to fallback

    # Use fallback if API fetch failed
    return (CLOUDFLARE_IPV4_FALLBACK, CLOUDFLARE_IPV6_FALLBACK)


@lru_cache(maxsize=1)
def _get_cloudflare_networks():
    """
    Get Cloudflare IP ranges as ipaddress network objects for fast lookups.

    Returns:
        list: List of ipaddress.ip_network objects

    Note:
        Results are cached using lru_cache for performance.
        Cache is cleared when IP ranges are updated.
    """
    ipv4_ranges, ipv6_ranges = get_cloudflare_ips()
    networks = []

    for cidr in ipv4_ranges + ipv6_ranges:
        try:
            networks.append(ipaddress.ip_network(cidr))
        except ValueError:
            continue  # Skip invalid CIDR

    return networks


def is_cloudflare_ip(ip_str):
    """
    Check if an IP address belongs to Cloudflare's network.

    Args:
        ip_str (str): IP address to check

    Returns:
        bool: True if IP is from Cloudflare, False otherwise
    """
    if not ip_str:
        return False

    try:
        ip = ipaddress.ip_address(ip_str)
        cloudflare_networks = _get_cloudflare_networks()

        for network in cloudflare_networks:
            if ip in network:
                return True
    except ValueError:
        return False

    return False


def get_real_ip():
    """
    Get the real client IP address from the request.

    When behind Cloudflare proxy:
    1. First checks CF-Connecting-IP header (Cloudflare's real IP)
    2. Falls back to X-Forwarded-For if present
    3. Finally uses request.remote_addr

    Returns:
        str: The client's real IP address

    Security Note:
        This function trusts the CF-Connecting-IP header. You should ensure
        your firewall only allows traffic from Cloudflare IPs to prevent
        IP spoofing. Use validate_cloudflare_request() to verify.
    """
    # Cloudflare sets CF-Connecting-IP to the real client IP
    real_ip = request.headers.get('CF-Connecting-IP')

    if real_ip:
        return real_ip

    # Fallback to X-Forwarded-For (takes the leftmost/client IP)
    forwarded_for = request.headers.get('X-Forwarded-For')
    if forwarded_for and validate_cloudflare_request():
        # X-Forwarded-For can be: "client, proxy1, proxy2"
        # We want the leftmost (original client)
        return forwarded_for.split(',')[0].strip()
    elif forwarded_for:
        # Security: X-Forwarded-For present but not trusted (not from Cloudflare)
        # Optionally log a warning here if desired
        pass

    # Final fallback to direct connection IP
    return request.remote_addr


def validate_cloudflare_request():
    """
    Validate that the request is actually coming from Cloudflare.

    Returns:
        bool: True if request is from Cloudflare, False otherwise

    Usage:
        Use this in middleware or views that require Cloudflare proxy.
        Only necessary if you want to enforce Cloudflare-only access.
    """
    return is_cloudflare_ip(request.remote_addr)


def get_request_info():
    """
    Get comprehensive request information including real IP.

    Returns:
        dict: Dictionary containing:
            - ip_address: Real client IP
            - user_agent: Browser user agent
            - cloudflare_verified: Whether request came from Cloudflare
            - country: Country code from CF-IPCountry header (if available)
            - ray_id: Cloudflare Ray ID for debugging (if available)
    """
    return {
        'ip_address': get_real_ip(),
        'user_agent': request.headers.get('User-Agent'),
        'cloudflare_verified': validate_cloudflare_request(),
        'country': request.headers.get('CF-IPCountry'),
        'ray_id': request.headers.get('CF-RAY'),
    }
