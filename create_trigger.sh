PROJECT_ID="[YOUR_GCP_PROJECT]"
PROJECT_NUMBER=$(gcloud projects describe ${PROJECT_ID} --format="value(projectNumber)")
gcloud eventarc triggers create gcs-to-url-backend \
    --location=asia-northeast3 \
    --destination-run-service=url-backend \
    --destination-run-region=asia-northeast3 \
    --event-filters="type=google.cloud.storage.object.v1.finalized" \
    --event-filters="bucket=cdn-url-input-bucket" \
    --service-account="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
