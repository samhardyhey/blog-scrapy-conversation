#!/bin/bash

# Ingestion Wrapper Script
# Calls the Python ingestion script with proper parameters

set -e

# Default values
ELASTICSEARCH_HOST="elasticsearch"
ELASTICSEARCH_PORT="9200"
OUTPUT_DIR="/data"

echo "📥 Running ingestion..."

# Change to app directory
cd /app

# Run the Python ingestion script
python /app/scrapy/scripts/ingest.py \
    --host "$ELASTICSEARCH_HOST" \
    --port "$ELASTICSEARCH_PORT" \
    --output-dir "$OUTPUT_DIR"

echo "✅ Ingestion completed"