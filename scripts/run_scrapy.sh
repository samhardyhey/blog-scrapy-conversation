#!/bin/bash

# Script to run Scrapy spider inside Docker container

echo "Running Scrapy spider in Docker container..."

# Run the spider
docker-compose exec scrapy scrapy crawl conversation

echo "Spider execution completed!" 