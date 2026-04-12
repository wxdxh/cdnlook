import json
import ipaddress
import urllib.request
import os
import bisect
import ssl
import threading
import time

import certifi

# URLs for IP ranges
GOOGLE_IP_RANGES_URL = "https://www.gstatic.com/ipranges/cloud.json"
GOOGLE_SERVICES_URL = "https://www.gstatic.com/ipranges/goog.json"
AWS_IP_RANGES_URL = "https://ip-ranges.amazonaws.com/ip-ranges.json"
CLOUDFLARE_IPV4_URL = "https://www.cloudflare.com/ips-v4"
CLOUDFLARE_IPV6_URL = "https://www.cloudflare.com/ips-v6"

# Global indices
ipv4_starts = []
ipv4_ranges = [] # List of (start, end, provider, detail)
ipv6_starts = []
ipv6_ranges = []
provider_ranges_loaded = False
last_refresh_attempt = 0.0
refresh_lock = threading.Lock()
REFRESH_RETRY_SECONDS = int(os.environ.get('PROVIDER_RANGE_REFRESH_RETRY_SECONDS', '300'))


def build_ssl_context():
    return ssl.create_default_context(cafile=certifi.where())

def fetch_json(url):
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, context=build_ssl_context(), timeout=10) as response:
            return json.loads(response.read().decode())
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None

def fetch_text(url):
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, context=build_ssl_context(), timeout=10) as response:
            return response.read().decode().splitlines()
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return []

def refresh_provider_ranges(force=False):
    global ipv4_starts, ipv4_ranges, ipv6_starts, ipv6_ranges
    global provider_ranges_loaded, last_refresh_attempt

    with refresh_lock:
        now = time.monotonic()
        if not force:
            if provider_ranges_loaded:
                return
            if last_refresh_attempt and now - last_refresh_attempt < REFRESH_RETRY_SECONDS:
                return

        last_refresh_attempt = now
    
        all_ipv4 = []
        all_ipv6 = []
        
        # 1. Google
        print("Loading Google ranges...")
        google_data = fetch_json(GOOGLE_IP_RANGES_URL)
        if google_data:
            for prefix in google_data.get('prefixes', []):
                is_global = prefix.get('scope') == 'global'
                detail = "Global" if is_global else prefix.get('scope', 'Regional')
                
                if 'ipv4Prefix' in prefix:
                    net = ipaddress.IPv4Network(prefix['ipv4Prefix'])
                    all_ipv4.append((int(net.network_address), int(net.broadcast_address), "Google Cloud", detail))
                elif 'ipv6Prefix' in prefix:
                    net = ipaddress.IPv6Network(prefix['ipv6Prefix'])
                    all_ipv6.append((int(net.network_address), int(net.broadcast_address), "Google Cloud", detail))

        # 1.5 Google Services
        print("Loading Google Services ranges...")
        goog_data = fetch_json(GOOGLE_SERVICES_URL)
        if goog_data:
            for prefix in goog_data.get('prefixes', []):
                detail = "Global"
                
                if 'ipv4Prefix' in prefix:
                    net = ipaddress.IPv4Network(prefix['ipv4Prefix'])
                    all_ipv4.append((int(net.network_address), int(net.broadcast_address), "Google", detail))
                elif 'ipv6Prefix' in prefix:
                    net = ipaddress.IPv6Network(prefix['ipv6Prefix'])
                    all_ipv6.append((int(net.network_address), int(net.broadcast_address), "Google", detail))

        # 2. AWS
        print("Loading AWS ranges...")
        aws_data = fetch_json(AWS_IP_RANGES_URL)
        if aws_data:
            for prefix in aws_data.get('prefixes', []):
                region = prefix.get('region', '')
                detail = "Global" if region == "GLOBAL" else region
                
                if 'ip_prefix' in prefix:
                    net = ipaddress.IPv4Network(prefix['ip_prefix'])
                    all_ipv4.append((int(net.network_address), int(net.broadcast_address), "AWS", detail))
                elif 'ipv6_prefix' in prefix:
                    net = ipaddress.IPv6Network(prefix['ipv6_prefix'])
                    all_ipv6.append((int(net.network_address), int(net.broadcast_address), "AWS", detail))

        # 3. Cloudflare
        print("Loading Cloudflare ranges...")
        cf_ipv4 = fetch_text(CLOUDFLARE_IPV4_URL)
        for cidr in cf_ipv4:
            if cidr.strip():
                net = ipaddress.IPv4Network(cidr.strip())
                all_ipv4.append((int(net.network_address), int(net.broadcast_address), "Cloudflare", ""))
                
        cf_ipv6 = fetch_text(CLOUDFLARE_IPV6_URL)
        for cidr in cf_ipv6:
            if cidr.strip():
                net = ipaddress.IPv6Network(cidr.strip())
                all_ipv6.append((int(net.network_address), int(net.broadcast_address), "Cloudflare", ""))

        # 4. Azure (Static list fallback)
        print("Loading Azure ranges (static)...")
        azure_static = [
            "13.64.0.0/11",
            "20.33.0.0/16",
            "23.96.0.0/13",
            "40.64.0.0/10",
            "52.145.0.0/16",
            "104.40.0.0/13"
        ]
        for cidr in azure_static:
            net = ipaddress.IPv4Network(cidr)
            all_ipv4.append((int(net.network_address), int(net.broadcast_address), "Azure", ""))

        # Build indices only after all fetches complete so readers always see a consistent snapshot.
        all_ipv4.sort(key=lambda x: x[0])
        all_ipv6.sort(key=lambda x: x[0])
        ipv4_ranges = all_ipv4
        ipv4_starts = [r[0] for r in all_ipv4]
        ipv6_ranges = all_ipv6
        ipv6_starts = [r[0] for r in all_ipv6]
        provider_ranges_loaded = bool(ipv4_ranges or ipv6_ranges)

        print(f"Loaded {len(ipv4_ranges)} IPv4 and {len(ipv6_ranges)} IPv6 ranges.")


def ensure_provider_ranges_loaded():
    if provider_ranges_loaded:
        return
    refresh_provider_ranges()

def detect_provider(ip_str):
    ensure_provider_ranges_loaded()

    if not ip_str:
        return None, None
        
    try:
        ip = ipaddress.ip_address(ip_str.strip())
        ip_int = int(ip)
        
        if ip.version == 4:
            starts = ipv4_starts
            ranges = ipv4_ranges
        else:
            starts = ipv6_starts
            ranges = ipv6_ranges
            
        if not starts:
            return None, None
            
        # Find the rightmost range that starts <= ip_int
        idx = bisect.bisect_right(starts, ip_int) - 1
        
        if idx >= 0:
            range_start, range_end, provider, detail = ranges[idx]
            if range_start <= ip_int <= range_end:
                return provider, detail
                
        return None, None
    except ValueError:
        return None, None
