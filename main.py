import os
import json
import uuid
from flask import Flask, request, render_template, jsonify, send_file, after_this_request
from google.cloud import storage
import dns.resolver
import cdn_detector

# Import our pipeline scripts
import run_pipeline

app = Flask(__name__)

# Required environment variable: GCS_OUTPUT_BUCKET
OUTPUT_BUCKET_NAME = os.environ.get('GCS_OUTPUT_BUCKET')


def cleanup_temp_files(*paths):
    for path in paths:
        if os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass

def resolve_dns(domain, server_ip=None):
    results = {
        'A': [],
        'AAAA': [],
        'CNAME': [],
        'TXT': []
    }
    
    resolver = dns.resolver.Resolver()
    if server_ip:
        resolver.nameservers = [server_ip]
        
    try:
        answers = resolver.resolve(domain, 'A')
        for r in answers:
            ip = str(r)
            provider, detail = cdn_detector.detect_provider(ip)
            results['A'].append({'ip': ip, 'provider': provider, 'detail': detail})
    except Exception:
        pass
        
    try:
        answers = resolver.resolve(domain, 'AAAA')
        for r in answers:
            ip = str(r)
            provider, detail = cdn_detector.detect_provider(ip)
            results['AAAA'].append({'ip': ip, 'provider': provider, 'detail': detail})
    except Exception:
        pass
        
    try:
        answers = resolver.resolve(domain, 'CNAME')
        results['CNAME'] = [str(r) for r in answers]
    except Exception:
        pass
        
    try:
        answers = resolver.resolve(domain, 'TXT')
        results['TXT'] = [str(r) for r in answers]
    except Exception:
        pass
        
    return results

def process_file(bucket_name, file_name):
    """Downloads, processes, and uploads the file."""
    if not OUTPUT_BUCKET_NAME:
        print("Error: GCS_OUTPUT_BUCKET is not set.")
        return False
        
    storage_client = storage.Client()
    
    # Setup local temp paths
    job_id = str(uuid.uuid4())[:8]
    # Cloud Run provides an in-memory /tmp file system
    local_input = f"/tmp/input_{job_id}.csv"
    local_output = f"/tmp/output_{job_id}.csv"
    
    try:
        # 1. Download from Input Bucket
        print(f"Downloading gs://{bucket_name}/{file_name} to {local_input}")
        input_bucket = storage_client.bucket(bucket_name)
        input_blob = input_bucket.blob(file_name)
        input_blob.download_to_filename(local_input)
        
        # 2. Run Pipeline Scripts
        print(f"Running pipeline on {local_input}")
        # Default workers 50, you can increase if needed via ENV var
        workers = int(os.environ.get('DNS_WORKERS', 50))
        
        # Call the orchestrator function
        # Note: Depending on file size, this might take minutes. Cloud Run timeout should be increased.
        run_pipeline.run_pipeline(local_input, local_output, url_col='URL', workers=workers, keep_temp=False)
        
        # 3. Upload to Output Bucket
        output_blob_name = f"processed_{file_name}"
        print(f"Uploading results to gs://{OUTPUT_BUCKET_NAME}/{output_blob_name}")
        output_bucket = storage_client.bucket(OUTPUT_BUCKET_NAME)
        output_blob = output_bucket.blob(output_blob_name)
        output_blob.upload_from_filename(local_output)
        
        print(f"Successfully processed {file_name}")
        return True
        
    except Exception as e:
        print(f"Error processing {file_name}: {e}")
        return False
        
    finally:
        # 4. Clean up /tmp to avoid memory leaks
        # Cloud Run /tmp is RAM, so cleaning up is CRITICAL
        cleanup_temp_files(local_input, local_output)

@app.route('/', methods=['GET', 'POST'])
def root():
    if request.method == 'POST':
        """Receives CloudEvent or plain Pub/Sub push"""
        data = request.get_json(silent=True)
        if not data:
            return ("Bad Request: No JSON body", 400)
            
        bucket_name = None
        file_name = None
        
        if request.headers.get('ce-type') == 'google.cloud.storage.object.v1.finalized':
             bucket_name = data.get('bucket')
             file_name = data.get('name')
             
        elif 'bucket' in data and 'name' in data:
             bucket_name = data['bucket']
             file_name = data['name']
             
        if not bucket_name or not file_name:
             print(f"Could not extract bucket/name from event: {data}")
             return ("OK (Ignored)", 200)
             
        print(f"Received event for gs://{bucket_name}/{file_name}")
        if not process_file(bucket_name, file_name):
            return ("Processing failed", 500)

        return ("OK", 200)
    else:
        return render_template('index.html')

@app.route('/api/dns', methods=['GET'])
def dns_lookup():
    domain = request.args.get('domain')
    server = request.args.get('server')
    if not domain:
        return jsonify({'error': 'Domain is required'}), 400
        
    server_map = {
        'google': '8.8.8.8',
        'cloudflare': '1.1.1.1',
        'kt': '168.126.63.1',
        'skb': '219.250.36.130',
        'lgu': '164.124.101.2'
    }
    
    server_ip = server_map.get(server) if server else None
    
    results = resolve_dns(domain, server_ip)
    return jsonify(results)

@app.route('/api/process', methods=['POST'])
def process_uploaded_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    url_col = request.form.get('url_col', 'URL')
    
    if file and file.filename.endswith('.csv'):
        job_id = str(uuid.uuid4())[:8]
        local_input = f"/tmp/upload_{job_id}.csv"
        local_output = f"/tmp/processed_{job_id}.csv"
        
        try:
            file.save(local_input)
            
            # Run pipeline
            workers = int(os.environ.get('DNS_WORKERS', 50))
            run_pipeline.run_pipeline(local_input, local_output, url_col=url_col, workers=workers, keep_temp=False)

            @after_this_request
            def remove_temp_files(response):
                cleanup_temp_files(local_input, local_output)
                return response

            return send_file(local_output, as_attachment=True, download_name='processed_urls.csv')
            
        except Exception as e:
            cleanup_temp_files(local_input, local_output)
            return jsonify({'error': str(e)}), 500
    else:
        return jsonify({'error': 'Invalid file type, only CSV allowed'}), 400

@app.route('/health')
def health_check():
    return "OK", 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
