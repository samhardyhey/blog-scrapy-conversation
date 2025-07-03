#!/bin/bash

# Scrapy Runner Script
# Runs the conversation spider

set -e

echo "🕷️  Running Scrapy spider..."

# Change to app directory
cd /app

# Run the spider
scrapy crawl conversation

echo "✅ Scrapy spider completed" 