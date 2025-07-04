#!/usr/bin/env python3
"""
Elasticsearch Ingestion Script
Ingests articles from CSV files to Elasticsearch
"""

import argparse
import os
import sys
from datetime import datetime

import pandas as pd
from elasticsearch import Elasticsearch, helpers
from elasticsearch.exceptions import ConnectionError
from loguru import logger


def check_connection(es):
    """Check Elasticsearch connection."""
    try:
        info = es.info()
        logger.info(
            f"Connected to Elasticsearch {info.get('version', {}).get('number', 'unknown')}"
        )
        return True
    except ConnectionError as e:
        logger.error(f"Failed to connect to Elasticsearch: {e}")
        return False


def create_index(es, index_name="articles"):
    """Create articles index with mapping."""
    try:
        if es.indices.exists(index=index_name):
            logger.info(f"Index {index_name} already exists")
            return True

        mapping = {
            "mappings": {
                "properties": {
                    "author": {"type": "text"},
                    "article_title": {"type": "text"},
                    "article": {"type": "text"},
                    "published": {"type": "date"},
                    "url": {"type": "keyword"},
                    "topics": {"type": "text"},
                    "source_section": {"type": "keyword"},
                    "content_length": {"type": "integer"},
                    "word_count": {"type": "integer"},
                    "ingested_at": {"type": "date"},
                    "source_file": {"type": "keyword"},
                }
            },
            "settings": {"number_of_shards": 1, "number_of_replicas": 0},
        }

        es.indices.create(index=index_name, body=mapping)
        logger.info(f"Created index: {index_name}")
        return True

    except Exception as e:
        logger.error(f"Failed to create index: {e}")
        return False


def clean_article(row):
    """Clean article data."""
    try:
        article = {
            "author": str(row.get("author", "")).strip(),
            "article_title": str(row.get("article_title", "")).strip(),
            "article": str(row.get("article", "")).strip(),
            "url": str(row.get("url", "")).strip(),
            "topics": str(row.get("topics", "")).strip(),
            "source_section": str(row.get("source_section", "")).strip(),
            "ingested_at": datetime.now().isoformat(),
            "source_file": row.get("_source_file", "unknown"),
        }

        # Parse published date
        published = row.get("published")
        if pd.notna(published):
            try:
                if isinstance(published, str):
                    # Convert string date to ISO format
                    try:
                        # Try to parse the date string
                        if " " in published:
                            # Format like "2025-07-03 15:00:00"
                            dt = datetime.strptime(published, "%Y-%m-%d %H:%M:%S")
                        else:
                            # Format like "2025-07-03"
                            dt = datetime.strptime(published, "%Y-%m-%d")
                        article["published"] = dt.isoformat()
                    except ValueError:
                        # If parsing fails, try pandas to_datetime
                        dt = pd.to_datetime(published)
                        article["published"] = dt.isoformat()
                else:
                    # If it's already a datetime object
                    article["published"] = published.isoformat()
            except Exception as e:
                logger.warning(
                    f"Failed to parse date '{published}' for URL {article.get('url', 'NO_URL')}: {e}"
                )
                article["published"] = None
        else:
            article["published"] = None

        # Truncate very long articles to prevent indexing issues
        max_article_length = 10000  # Limit to 10k characters
        if len(article["article"]) > max_article_length:
            article["article"] = (
                article["article"][:max_article_length] + "... [truncated]"
            )
            logger.warning(f"Truncated article for URL: {article['url']}")

        # Calculate metrics
        article["content_length"] = len(article["article"])
        article["word_count"] = len(article["article"].split())

        # Clean topics
        if article["topics"]:
            topics = [
                topic.strip() for topic in article["topics"].split("|") if topic.strip()
            ]
            article["topics"] = "|".join(topics)

        # Validate required fields
        if not article["url"] or not article["article_title"]:
            logger.warning(
                f"Skipping article with missing URL or title: {article.get('url', 'NO_URL')}"
            )
            return None

        return article

    except Exception as e:
        logger.error(f"Error cleaning article: {e}")
        return None


def check_existing_urls(es, index_name, urls):
    """Check which URLs already exist in the index."""
    try:
        # Create a query to check for existing URLs
        query = {"query": {"terms": {"url": urls}}, "_source": ["url"]}

        response = es.search(index=index_name, body=query, size=10000)
        existing_urls = {hit["_source"]["url"] for hit in response["hits"]["hits"]}
        return existing_urls
    except Exception as e:
        logger.error(f"Error checking existing URLs: {e}")
        return set()


def ingest_csv(es, csv_path, index_name="articles", batch_size=100):
    """Ingest articles from CSV file."""
    try:
        logger.info(f"Reading {csv_path}")
        df = pd.read_csv(csv_path)
        df["_source_file"] = os.path.basename(csv_path)

        logger.info(f"Found {len(df)} articles")

        # Check for existing URLs to prevent duplicates
        urls = df["url"].dropna().tolist()
        existing_urls = check_existing_urls(es, index_name, urls)
        logger.info(f"Found {len(existing_urls)} existing URLs, will skip duplicates")

        total_ingested = 0
        for i in range(0, len(df), batch_size):
            batch = df.iloc[i : i + batch_size]

            actions = []
            for _, row in batch.iterrows():
                article = clean_article(row)
                if article and article["url"] not in existing_urls:
                    # Use URL as document ID to prevent duplicates
                    actions.append(
                        {
                            "_index": index_name,
                            "_id": article["url"],  # Use URL as document ID
                            "_source": article,
                        }
                    )

            if actions:
                try:
                    # Use bulk with detailed error reporting
                    success, errors = helpers.bulk(
                        es, actions, stats_only=False, raise_on_error=False
                    )
                    total_ingested += success
                    logger.info(
                        f"Batch {i//batch_size + 1}: {success} articles ingested"
                    )

                    if errors:
                        logger.warning(
                            f"Batch {i//batch_size + 1}: {len(errors)} failed"
                        )
                        for error in errors[:5]:  # Log first 5 errors
                            logger.error(f"Bulk error: {error}")

                except Exception as e:
                    logger.error(f"Batch {i//batch_size + 1} error: {e}")
                    # Try individual indexing for debugging
                    for action in actions[:3]:  # Try first 3 actions individually
                        try:
                            es.index(
                                index=action["_index"],
                                id=action["_id"],
                                body=action["_source"],
                            )
                            logger.info(
                                f"Individual index success for: {action['_id']}"
                            )
                        except Exception as individual_error:
                            logger.error(
                                f"Individual index failed for {action['_id']}: {individual_error}"
                            )
                    continue

        logger.info(f"Ingested {total_ingested} articles from {csv_path}")
        return total_ingested

    except Exception as e:
        logger.error(f"Error ingesting {csv_path}: {e}")
        return 0


def main():
    parser = argparse.ArgumentParser(description="Ingest articles to Elasticsearch")
    parser.add_argument("--host", default="localhost", help="Elasticsearch host")
    parser.add_argument("--port", type=int, default=9200, help="Elasticsearch port")
    parser.add_argument("--index", default="articles", help="Index name")
    parser.add_argument("--output-dir", default="/data", help="Output directory")
    parser.add_argument("--batch-size", type=int, default=100, help="Batch size")

    args = parser.parse_args()

    # Connect to Elasticsearch
    es = Elasticsearch([f"http://{args.host}:{args.port}"])

    if not check_connection(es):
        sys.exit(1)

    # Create index
    if not create_index(es, args.index):
        sys.exit(1)

    # Find CSV files
    output_path = os.path.join(args.output_dir)
    if not os.path.exists(output_path):
        logger.error(f"Output directory does not exist: {output_path}")
        sys.exit(1)

    csv_files = [f for f in os.listdir(output_path) if f.endswith(".csv")]
    if not csv_files:
        logger.warning(f"No CSV files found in {output_path}")
        return

    # Ingest all CSV files
    total_ingested = 0
    for csv_file in csv_files:
        csv_path = os.path.join(output_path, csv_file)
        ingested = ingest_csv(es, csv_path, args.index, args.batch_size)
        total_ingested += ingested

    logger.info(f"Total articles ingested: {total_ingested}")


if __name__ == "__main__":
    main()
