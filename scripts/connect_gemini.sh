#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
command -v gcloud >/dev/null || { echo 'Run this script in Google Cloud Shell.'; exit 1; }
AQUA_SETUP_PROJECT="${GOOGLE_CLOUD_PROJECT:-${AQUA_PROJECT_ID:-$(gcloud config get-value project 2>/dev/null)}}"
read -r -p "Google Cloud project [$AQUA_SETUP_PROJECT]: " AQUA_SETUP_INPUT
AQUA_SETUP_PROJECT="${AQUA_SETUP_INPUT:-$AQUA_SETUP_PROJECT}"
[[ -n "$AQUA_SETUP_PROJECT" && "$AQUA_SETUP_PROJECT" != '(unset)' ]] || { echo 'A project ID is required.'; exit 1; }
AQUA_SETUP_MODEL="${GEMINI_MODEL:-${AQUA_MODEL_ID:-}}"
echo 'Use an exact Gemini model ID available in your project’s Vertex AI Model Garden.'
read -r -p "Gemini model ID [$AQUA_SETUP_MODEL]: " AQUA_SETUP_INPUT
AQUA_SETUP_MODEL="${AQUA_SETUP_INPUT:-$AQUA_SETUP_MODEL}"
[[ -n "$AQUA_SETUP_MODEL" ]] || { echo 'A supported model ID is required; no model was guessed.'; exit 1; }
export GOOGLE_CLOUD_PROJECT="$AQUA_SETUP_PROJECT"
export GEMINI_MODEL="$AQUA_SETUP_MODEL"
export GEMINI_LOCATION="${GEMINI_LOCATION:-${AQUA_MODEL_LOCATION:-global}}"
echo 'Enabling the Vertex AI API for the selected project. Model requests may incur charges.'
gcloud services enable aiplatform.googleapis.com --project="$GOOGLE_CLOUD_PROJECT"
if [[ ! -x .venv/bin/python ]]; then python3 -m venv .venv; fi
.venv/bin/python -m pip -q install -r requirements.txt
if ! .venv/bin/python -c 'import google.auth; from google.auth.transport.requests import Request; c,_=google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"]); c.refresh(Request())' 2>/dev/null; then
  gcloud auth application-default login
fi
echo 'Checking credentials and a live grounded Gemini response…'
.venv/bin/python scripts/check_gemini.py
echo 'Starting v0.4.0. Open Web Preview on port 8081.'
unset EVIDENCE_GCS_URI
exec .venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8081}"
