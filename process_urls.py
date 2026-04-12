import csv
from urllib.parse import urlparse
import argparse
import sys
import os

def extract_host(url):
    try:
        url_str = str(url).strip()
        if not url_str:
            return ''
        
        # Add scheme if missing for proper parsing
        if not url_str.startswith(('http://', 'https://', '//', 'ftp://')):
             parsed = urlparse('http://' + url_str)
             return parsed.netloc
        
        parsed = urlparse(url_str)
        return parsed.netloc
    except Exception:
        return ''

def process_csv(input_file, output_file, url_col='url'):
    print(f"Reading from {input_file}...")
    try:
        with open(input_file, 'r', encoding='utf-8', newline='') as f_in:
            reader = csv.reader(f_in)
            
            header = None
            col_idx = -1
            
            for row in reader:
                if not row:
                    continue
                
                try:
                    col_idx = row.index(url_col)
                    header = row
                    break
                except ValueError:
                    lower_row = [str(r).lower().strip() for r in row]
                    if url_col.lower() in lower_row:
                        col_idx = lower_row.index(url_col.lower())
                        header = row
                        url_col = header[col_idx]
                        print(f"Warning: Exact column '{url_col}' not found. Using '{header[col_idx]}' instead.")
                        break
            
            if not header:
                print(f"Error: Could not find '{url_col}' column in the file.")
                sys.exit(1)
            
            new_header = header + ['host']
            
            with open(output_file, 'w', encoding='utf-8', newline='') as f_out:
                writer = csv.writer(f_out)
                writer.writerow(new_header)
                
                count = 0
                for row in reader:
                    # We might have empty rows in the data, just skip them or rewrite them?
                    # The original code did: `if not row: continue`
                    if not row:
                        continue
                    
                    if len(row) <= col_idx:
                        url_val = ''
                    else:
                        url_val = row[col_idx]
                    
                    host = extract_host(url_val)
                    writer.writerow(row + [host])
                    count += 1
                    
                    if count % 50000 == 0:
                        print(f"Processed {count} rows...", flush=True)

        print(f"Done! Processed {count} rows. Output written to {output_file}")
        
    except Exception as e:
        print(f"Error processing file: {e}")
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract host from URLs in a CSV file (Standard Library).")
    parser.add_argument("input_file", help="Path to input CSV file")
    parser.add_argument("output_file", help="Path to output CSV file")
    parser.add_argument("--col", default="URL", help="Name of the column containing URLs (default: 'URL')")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.input_file):
        print(f"Error: Input file '{args.input_file}' does not exist.")
        sys.exit(1)
        
    process_csv(args.input_file, args.output_file, args.col)
