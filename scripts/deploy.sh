#!/usr/bin/env bash
set -euo pipefail
# Run in Google Cloud Shell from the project root. No credentials belong in this file.
: "${AQUA_PROJECT_ID:?Set AQUA_PROJECT_ID to your billing-enabled Google Cloud project ID}"
: "${AQUA_MODEL_ID:?Set AQUA_MODEL_ID to a Gemini model available to your project}"
AQUA_REGION="${AQUA_REGION:-asia-south1}"
AQUA_MODEL_LOCATION="${AQUA_MODEL_LOCATION:-global}"
AQUA_BUCKET="${AQUA_PROJECT_ID}-aquasustain-evidence"
AQUA_RUNTIME_SA="aqua-runtime@${AQUA_PROJECT_ID}.iam.gserviceaccount.com"
AQUA_BUILD_SA="aqua-build@${AQUA_PROJECT_ID}.iam.gserviceaccount.com"
AQUA_TAG="$(date -u +%Y%m%d%H%M%S)"
AQUA_IMAGE="${AQUA_REGION}-docker.pkg.dev/${AQUA_PROJECT_ID}/aquasustain/app:${AQUA_TAG}"
command -v gcloud >/dev/null || { echo 'Run this script in Google Cloud Shell.'; exit 1; }
test -f Dockerfile || { echo 'Run from the aqua-sustain directory.'; exit 1; }
gcloud config set project "$AQUA_PROJECT_ID"
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com aiplatform.googleapis.com storage.googleapis.com iam.googleapis.com logging.googleapis.com
gcloud iam service-accounts describe "$AQUA_RUNTIME_SA" >/dev/null 2>&1 || gcloud iam service-accounts create aqua-runtime --display-name='AquaSustain runtime'
gcloud iam service-accounts describe "$AQUA_BUILD_SA" >/dev/null 2>&1 || gcloud iam service-accounts create aqua-build --display-name='AquaSustain container builder'
gcloud projects add-iam-policy-binding "$AQUA_PROJECT_ID" --member="serviceAccount:$AQUA_RUNTIME_SA" --role=roles/aiplatform.user --condition=None >/dev/null
gcloud projects add-iam-policy-binding "$AQUA_PROJECT_ID" --member="serviceAccount:$AQUA_BUILD_SA" --role=roles/logging.logWriter --condition=None >/dev/null
gcloud artifacts repositories describe aquasustain --location="$AQUA_REGION" >/dev/null 2>&1 || gcloud artifacts repositories create aquasustain --repository-format=docker --location="$AQUA_REGION"
gcloud artifacts repositories add-iam-policy-binding aquasustain --location="$AQUA_REGION" --member="serviceAccount:$AQUA_BUILD_SA" --role=roles/artifactregistry.writer >/dev/null
gcloud storage buckets describe "gs://$AQUA_BUCKET" >/dev/null 2>&1 || gcloud storage buckets create "gs://$AQUA_BUCKET" --location="$AQUA_REGION" --uniform-bucket-level-access
gcloud storage buckets add-iam-policy-binding "gs://$AQUA_BUCKET" --member="serviceAccount:$AQUA_RUNTIME_SA" --role=roles/storage.objectViewer >/dev/null
gcloud storage buckets add-iam-policy-binding "gs://$AQUA_BUCKET" --member="serviceAccount:$AQUA_BUILD_SA" --role=roles/storage.objectViewer >/dev/null
# Every release gets an immutable snapshot path, so rollback restores the same evidence.
gcloud storage cp data/evidence_snapshot.json "gs://$AQUA_BUCKET/snapshots/$AQUA_TAG.json"
gcloud builds submit . --config=cloudbuild.yaml --substitutions="_IMAGE=$AQUA_IMAGE" --service-account="projects/$AQUA_PROJECT_ID/serviceAccounts/$AQUA_BUILD_SA" --gcs-source-staging-dir="gs://$AQUA_BUCKET/build-source"
gcloud run deploy aqua-sustain --image="$AQUA_IMAGE" --region="$AQUA_REGION" \
  --service-account="$AQUA_RUNTIME_SA" --allow-unauthenticated \
  --min-instances=0 --max-instances=2 --memory=1Gi --cpu=1 --concurrency=8 --timeout=240 \
  --set-env-vars="GOOGLE_CLOUD_PROJECT=$AQUA_PROJECT_ID,GEMINI_MODEL=$AQUA_MODEL_ID,GEMINI_LOCATION=$AQUA_MODEL_LOCATION,EVIDENCE_GCS_URI=gs://$AQUA_BUCKET/snapshots/$AQUA_TAG.json"
gcloud run services describe aqua-sustain --region="$AQUA_REGION" --format='value(status.url)'
