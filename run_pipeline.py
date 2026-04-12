import argparse
import sys
import os

# Import the main functions from the three scripts
try:
    import process_urls
    import resolve_ips
    import tag_gcp_ips
except ImportError as e:
    print(f"Error importing required modules: {e}")
    print("Ensure process_urls.py, resolve_ips.py, and tag_gcp_ips.py are in the same directory.")
    sys.exit(1)

def run_pipeline(input_file, final_output_file, url_col='URL', workers=50, keep_temp=False):
    """ Orchestrates the pipeline """
    step1_output = final_output_file + ".step1.tmp.csv"
    step2_output = final_output_file + ".step2.tmp.csv"

    print("=" * 50)
    print(f"Starting Integrated URL Processing Pipeline")
    print(f"Input: {input_file}")
    print(f"Final Output: {final_output_file}")
    print("=" * 50)

    try:
        # Step 1: Extract Hosts
        print("\n--- STEP 1: Extracting Hosts ---")
        process_urls.process_csv(input_file, step1_output, url_col)

        # Step 2: Resolve IPs
        print("\n--- STEP 2: Resolving IPs ---")
        # process_urls adds 'host' column
        resolve_ips.process_csv(step1_output, step2_output, host_col='host', workers=workers)

        # Step 3: Tag GCP & Global IPs
        print("\n--- STEP 3: Tagging GCP & Global IPs ---")
        # resolve_ips adds 'ip' column
        tag_gcp_ips.process_csv(step2_output, final_output_file, ip_col='ip')

        print("\n" + "=" * 50)
        print("Pipeline Completed Successfully!")
        print(f"Final results are in: {final_output_file}")
        print("=" * 50)

    except Exception as e:
        print(f"\nPipeline failed during execution: {e}")
        print("Intermediate files have been preserved for debugging.")
        sys.exit(1)
        
    finally:
        # Cleanup
        if not keep_temp:
            print("\nCleaning up temporary files...")
            for tmp_file in [step1_output, step2_output]:
                if os.path.exists(tmp_file):
                    try:
                        os.remove(tmp_file)
                        print(f"  Removed {tmp_file}")
                    except OSError as e:
                        print(f"  Warning: Could not remove {tmp_file}: {e}")
        else:
            print("\nTemporary files preserved as requested:")
            print(f"  Step 1: {step1_output}")
            print(f"  Step 2: {step2_output}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Integrated pipeline for processing URLs, resolving IPs, and tagging GCP.")
    parser.add_argument("input_file", help="Path to the initial input CSV file containing URLs.")
    parser.add_argument("output_file", help="Path to the final output CSV file.")
    parser.add_argument("--col", default="URL", help="Name of the initial URL column (default: 'URL')")
    parser.add_argument("--workers", type=int, default=50, help="Number of threads for DNS resolution (default: 50)")
    parser.add_argument("--keep-temp", action="store_true", help="Keep intermediate temporary files (*.tmp.csv)")

    args = parser.parse_args()

    if not os.path.exists(args.input_file):
        print(f"Error: Input file '{args.input_file}' does not exist.")
        sys.exit(1)

    run_pipeline(args.input_file, args.output_file, args.col, args.workers, args.keep_temp)
