#!/bin/bash

# Ingestion Wrapper Script
# Calls the Python ingestion script with proper parameters

set -e

# Use environment variables with defaults
API_URL="${API_URL:-http://localhost:8000}"
OUTPUT_DIR="/data"

echo "📥 Running ingestion..."

# Change to app directory
cd /app

# Run the Python ingestion script
python /app/scripts/ingest.py \
    --api-url "$API_URL" \
    --output-dir "$OUTPUT_DIR"

echo "✅ Ingestion completed"