# Conversation Scraper 📚

Academic article scraper and search API for The Conversation. Collects articles, indexes them in Elasticsearch, and provides a searchable API interface.

## Features
- 🕷️ Scrapy-based article collection
- 📑 Elasticsearch indexing
- 🔍 Search API endpoints
- 🚀 Deployment tooling

## Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Configure Elasticsearch
# (Add configuration steps here)
```

## Usage
```bash
# Run scraper
scrapy crawl conversation -O output/expanded_articles.csv

# Index articles
python index_articles.py

# Start API server
python api/main.py
```

## Structure
- 🕷️ `conversation/` # Scrapy project
  - `spiders/` # Article scrapers
  - `items.py` # Data models
- 📓 `notebooks/` # Development notebooks
- 📤 `output/` # Scraped data
- 🔧 `api/` # Search API
- 📝 `requirements.txt` # Dependencies

## TODO
- integration tests/basic functionality
- unit tests/test suite
- CI/CD
- terraform/aws K8s