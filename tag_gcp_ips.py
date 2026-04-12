import csv
import json
import ipaddress
import urllib.request
import os
import sys
import argparse
import bisect

# URL for Google's published IP ranges
GCP_IP_RANGES_URL = "https://www.gstatic.com/ipranges/cloud.json"
CACHE_FILE = "gcp_ranges.json"

def fetch_gcp_ranges():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r') as f:
                data = json.load(f)
            return data
        except Exception:
            pass
            
    print("Fetching Google Cloud IP ranges...")
    try:
        req = urllib.request.Request(GCP_IP_RANGES_URL)
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            
        with open(CACHE_FILE, 'w') as f:
            json.dump(data, f)
            
        return data
    except Exception as e:
        print(f"Error fetching GCP ranges: {e}")
        sys.exit(1)

def build_ip_index(data):
    """
    Build a sorted list of IP ranges for fast bisect lookup.
    """
    ranges_list = []
    
    for prefix in data.get('prefixes', []):
        is_global = prefix.get('scope') == 'global'
        
        # We only handle IPv4 for simplicity in this script, or add IPv6 if needed
        if 'ipv4Prefix' in prefix:
            net = ipaddress.IPv4Network(prefix['ipv4Prefix'])
            ranges_list.append((int(net.network_address), int(net.broadcast_address), is_global))
            
    # Sort by start address
    ranges_list.sort(key=lambda x: x[0])
    
    # Pre-extract start addresses for bisect
    starts = [r[0] for r in ranges_list]
    
    return starts, ranges_list

def is_gcp_ip(ip_str, starts, ranges):
    """
    Returns (is_gcp, is_global)
    """
    if not ip_str:
        return False, False
    try:
        ip_int = int(ipaddress.IPv4Address(ip_str.strip()))
        
        # Find the rightmost range that starts <= ip_int
        idx = bisect.bisect_right(starts, ip_int) - 1
        
        if idx >= 0:
            range_start, range_end, is_global = ranges[idx]
            if range_start <= ip_int <= range_end:
                return True, is_global
        return False, False
    except ValueError:
        return False, False

def process_csv(input_file, output_file, ip_col='ip'):
    ranges_data = fetch_gcp_ranges()
    starts, ranges = build_ip_index(ranges_data)
    
    print(f"Reading from {input_file}...")
    try:
        header_row = None
        header_idx = -1
        col_idx = -1
        
        # Pass 1: find header
        with open(input_file, 'r', encoding='utf-8', newline='') as f_in:
            reader = csv.reader(f_in)
            for i, row in enumerate(reader):
                if not row:
                    continue
                try:
                    col_idx = row.index(ip_col)
                    header_row = row
                    header_idx = i
                    break
                except ValueError:
                    lower_row = [str(r).lower() for r in row]
                    if ip_col.lower() in lower_row:
                        col_idx = lower_row.index(ip_col.lower())
                        header_row = row
                        ip_col = header_row[col_idx]
                        header_idx = i
                        print(f"Warning: Exact column '{ip_col}' not found. Using '{header_row[col_idx]}' instead.")
                        break
                        
            if header_row is None:
                print(f"Error: Could not find '{ip_col}' column in the file.")
                sys.exit(1)
        
        # Pass 2: process
        with open(input_file, 'r', encoding='utf-8', newline='') as f_in, \
             open(output_file, 'w', encoding='utf-8', newline='') as f_out:
             
            reader = csv.reader(f_in)
            writer = csv.writer(f_out)
            
            # Skip until header
            for _ in range(header_idx):
                next(reader)
                
            header = next(reader)
            writer.writerow(header + ['is_gcp', 'is_global'])
            
            count = 0
            gcp_count = 0
            global_count = 0
            
            for row in reader:
                if not row:
                    continue
                    
                is_gcp = False
                is_global = False
                if len(row) > col_idx:
                    is_gcp, is_global = is_gcp_ip(row[col_idx], starts, ranges)
                
                writer.writerow(row + [str(is_gcp), str(is_global)])
                
                if is_gcp:
                    gcp_count += 1
                if is_global:
                    global_count += 1
                count += 1
                
                if count % 50000 == 0:
                    print(f"Processed {count} rows...", flush=True)
                    
        print(f"Done! Processed {count} rows. Found {gcp_count} GCP IPs ({global_count} Global).")
        print(f"Output written to {output_file}")
        
    except Exception as e:
        print(f"Error processing file: {e}")
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Check if IPs belong to Google Cloud.")
    parser.add_argument("input_file", help="Path to input CSV file")
    parser.add_argument("output_file", help="Path to output CSV file")
    parser.add_argument("--col", default="ip", help="Name of the column containing IPs (default: 'ip')")
    
    args = parser.parse_args()
    
    process_csv(args.input_file, args.output_file, args.col)
