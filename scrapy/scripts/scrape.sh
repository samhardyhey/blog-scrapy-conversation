#!/bin/bash

# Scrapy Runner Script
# Runs the conversation spider

set -e

echo "🕷️  Running Scrapy spider..."

# Change to app directory
cd /app

# Generate timestamp for output file (YYYY-MM-DD format)
TIMESTAMP=$(date +"%Y-%m-%d")

echo "📅 Using timestamp: $TIMESTAMP"

# Run the spider
scrapy crawl conversation

echo "✅ Scrapy spider completed"
echo "📁 Output saved to: /data/conversation_articles_${TIMESTAMP}.csv" 