# Network Tools (DNS Lookup & URL Pipeline)

A modern, minimalist web application for DNS lookups with advanced CDN provider detection, and an asynchronous pipeline for bulk URL processing.

## Features

### 1. DNS Lookup Tool
- **Multi-Server Support**: Query using Default DNS, Google DNS, Cloudflare DNS, or Korean ISP DNS (KT, SKB, LGU+).
- **CDN Detection**: Automatically detects if resolved IP addresses belong to major CDN/Cloud providers:
  - **Google / Google Cloud**: Detects global vs regional IPs, including specific GCP regions.
  - **AWS**: Detects specific AWS regions.
  - **Cloudflare**
  - **Azure**
- **Smart Input**: Automatically extracts the domain name even if full URLs with protocols (`https://...`), paths, or port numbers are entered.
- **Minimalist UI**: A sleek, high-contrast, monochrome dark theme with sharp edges and a clean monospace font (`JetBrains Mono`).

### 2. URL Processing Pipeline
- Asynchronous processing of large CSV files containing URLs.
- Integration with Google Cloud Storage for input/output.
- Cloud event-driven execution.

## Project Structure

```text
├── main.py                 # Flask web server & API endpoints
├── cdn_detector.py         # CDN detection logic & IP range loader
├── requirements.txt        # Python dependencies
├── Dockerfile              # Container definition for Cloud Run
├── .dockerignore           # Files ignored in Docker build
├── .gitignore             # Files ignored in Git
├── static/
│   └── index.css          # Minimalist monochrome styling
└── templates/
    └── index.html         # Web UI template
```

## Local Development

### Prerequisites
- Python 3.11+
- Virtual environment (recommended)

### Setup
1. Clone the repository (or download the source).
2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Run the Flask server:
   ```bash
   python main.py
   ```
5. Open `http://localhost:8080` in your browser.

## Deployment to Google Cloud Run

### Prerequisites
- Google Cloud SDK installed and configured.
- A project with Cloud Build and Cloud Run APIs enabled.

### Steps
1. **Build and Push Image** using Cloud Build:
   ```bash
   gcloud builds submit --tag gcr.io/[PROJECT_ID]/network-tools --project [PROJECT_ID]
   ```
   *Replace `[PROJECT_ID]` with your actual Google Cloud project ID.*

2. **Deploy to Cloud Run**:
   ```bash
   gcloud run deploy network-tools \
     --image gcr.io/[PROJECT_ID]/network-tools \
     --region asia-northeast3 \
     --project [PROJECT_ID] \
     --platform managed \
     --no-allow-unauthenticated
   ```
   *Adjust flags as needed (e.g., `--allow-unauthenticated` if public access is desired).*

## License
MIT License
