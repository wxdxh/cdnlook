import csv
import socket
import argparse
import sys
import os
import time
from concurrent.futures import ThreadPoolExecutor

# A DNS cache to avoid duplicate lookups
dns_cache = {}

def resolve_host(host):
    # Same as original
    host_str = str(host).strip()
    if not host_str:
        return ''
        
    if host_str in dns_cache:
        return dns_cache[host_str]
        
    try:
        ip = socket.gethostbyname(host_str)
        dns_cache[host_str] = ip
        return ip
    except Exception:
        dns_cache[host_str] = ''
        return ''

def process_csv(input_file, output_file, host_col='host', workers=50):
    print(f"Reading from {input_file} (using ThreadPoolExecutor)...")
    start_time = time.time()
    
    try:
        # 1. First pass to find header row (ignoring empty/invalid rows before it)
        header_row = None
        header_idx = -1
        col_idx = -1
        
        with open(input_file, 'r', encoding='utf-8', newline='') as f_in:
            reader = csv.reader(f_in)
            for i, row in enumerate(reader):
                if not row:
                    continue
                try:
                    col_idx = row.index(host_col)
                    header_row = row
                    header_idx = i
                    break
                except ValueError:
                    lower_row = [str(r).lower() for r in row]
                    if host_col.lower() in lower_row:
                        col_idx = lower_row.index(host_col.lower())
                        header_row = row
                        host_col = header_row[col_idx]
                        header_idx = i
                        print(f"Warning: Exact column '{host_col}' not found. Using '{header_row[col_idx]}' instead.")
                        break
                        
            if header_row is None:
                print(f"Error: Could not find '{host_col}' column in the file.")
                sys.exit(1)
                
        # 2. Second pass to actually process the data
        with open(input_file, 'r', encoding='utf-8', newline='') as f_in, \
             open(output_file, 'w', encoding='utf-8', newline='') as f_out:
             
            reader = csv.reader(f_in)
            writer = csv.writer(f_out)
            
            # Skip rows before header
            for _ in range(header_idx):
                next(reader)
                
            # Read header
            header = next(reader)
            writer.writerow(header + ['ip'])
            
            # Process in batches
            BATCH_SIZE = 1000
            total_processed = 0
            
            with ThreadPoolExecutor(max_workers=workers) as executor:
                while True:
                    batch = []
                    for _ in range(BATCH_SIZE):
                        try:
                            row = next(reader)
                            if not row:
                                continue
                            batch.append(row)
                        except StopIteration:
                            break
                            
                    if not batch:
                        break
                        
                    # Submit batch
                    futures = []
                    for row in batch:
                        if len(row) > col_idx:
                            host = row[col_idx]
                            futures.append(executor.submit(resolve_host, host))
                        else:
                            futures.append(executor.submit(lambda: ''))
                    
                    # Collect results in order
                    results = [f.result() for f in futures]
                    
                    # Write batch
                    for row, ip in zip(batch, results):
                        writer.writerow(row + [ip])
                    
                    total_processed += len(batch)
                    if total_processed % 5000 == 0:
                        elapsed = time.time() - start_time
                        rate = total_processed / elapsed
                        print(f"Processed {total_processed} rows... ({rate:.1f} rows/sec)", flush=True)

        elapsed = time.time() - start_time
        print(f"Done! Processed {total_processed} rows in {elapsed:.2f} seconds.")
        print(f"Output written to {output_file}")
        
    except Exception as e:
        print(f"Error processing file: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Resolve IP addresses from hosts in a CSV file.")
    parser.add_argument("input_file", help="Path to input CSV file")
    parser.add_argument("output_file", help="Path to output CSV file")
    parser.add_argument("--col", default="host", help="Name of the column containing hosts (default: 'host')")
    parser.add_argument("--workers", type=int, default=50, help="Number of threads (default: 50)")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.input_file):
        print(f"Error: Input file '{args.input_file}' does not exist.")
        sys.exit(1)
        
    process_csv(args.input_file, args.output_file, args.col, args.workers)
