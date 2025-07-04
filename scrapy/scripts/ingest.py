#!/usr/bin/env python3
"""
API Ingestion Script
Ingests articles from CSV files using the API
"""

import argparse
import hashlib
import os
import re
import sys
from datetime import datetime

import pandas as pd
import requests
from loguru import logger


def check_api_connection(api_url):
    """Check API connection."""
    try:
        response = requests.get(f"{api_url}/health")
        if response.status_code == 200:
            logger.info("Connected to API successfully")
            return True
        else:
            logger.error(f"API health check failed: {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"Failed to connect to API: {e}")
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


def generate_article_id(article_title):
    """Generate a hash-based ID from the article title."""
    return hashlib.md5(article_title.encode('utf-8')).hexdigest()


def check_existing_articles(api_url, article_titles):
    """Check which articles already exist in the index by title."""
    try:
        existing_titles = set()
        for title in article_titles:
            # Search for articles with this title
            response = requests.get(
                f"{api_url}/articles/search",
                params={"q": title, "limit": 1}
            )
            if response.status_code == 200:
                data = response.json()
                if data["articles"]:
                    # Check if any article has the exact same title
                    for article in data["articles"]:
                        if article.get("article_title") == title:
                            existing_titles.add(title)
                            break

        return existing_titles
    except Exception as e:
        logger.error(f"Error checking existing articles: {e}")
        return set()


def ingest_csv(api_url, csv_path, batch_size=100):
    """Ingest articles from CSV file using the API."""
    try:
        logger.info(f"Reading {csv_path}")
        df = pd.read_csv(csv_path)
        df["_source_file"] = os.path.basename(csv_path)

        logger.info(f"Found {len(df)} articles")

        # Check for existing articles to prevent duplicates
        titles = df["article_title"].dropna().tolist()
        existing_titles = check_existing_articles(api_url, titles)
        logger.info(f"Found {len(existing_titles)} existing articles, will skip duplicates")

        total_ingested = 0
        for i in range(0, len(df), batch_size):
            batch = df.iloc[i : i + batch_size]

            articles_to_ingest = []
            for _, row in batch.iterrows():
                article = clean_article(row)
                if article and article["article_title"] not in existing_titles:
                    articles_to_ingest.append(article)

            if articles_to_ingest:
                try:
                    # Use bulk API endpoint
                    response = requests.post(
                        f"{api_url}/articles/bulk",
                        json=articles_to_ingest
                    )

                    if response.status_code == 200:
                        result = response.json()
                        total_ingested += result.get("created", 0)
                        logger.info(
                            f"Batch {i//batch_size + 1}: {result.get('created', 0)} articles ingested"
                        )

                        if result.get("errors", 0) > 0:
                            logger.warning(
                                f"Batch {i//batch_size + 1}: {result.get('errors', 0)} failed"
                            )
                    else:
                        logger.error(f"Batch {i//batch_size + 1} failed: {response.status_code} - {response.text}")

                except Exception as e:
                    logger.error(f"Batch {i//batch_size + 1} error: {e}")
                    # Try individual indexing for debugging
                    for article in articles_to_ingest[:3]:  # Try first 3 articles individually
                        try:
                            response = requests.post(
                                f"{api_url}/articles",
                                json=article
                            )
                            if response.status_code == 200:
                                logger.info(f"Individual index success for: {article.get('article_title', 'NO_TITLE')}")
                            else:
                                logger.error(f"Individual index failed: {response.status_code} - {response.text}")
                        except Exception as individual_error:
                            logger.error(f"Individual index failed: {individual_error}")
                    continue

        logger.info(f"Ingested {total_ingested} articles from {csv_path}")
        return total_ingested

    except Exception as e:
        logger.error(f"Error ingesting {csv_path}: {e}")
        return 0


def has_date_in_filename(filename):
    """Check if filename contains a year-month-day datestamp."""
    # Pattern to match YYYY-MM-DD format in filename
    date_pattern = r'\d{4}-\d{2}-\d{2}'
    return bool(re.search(date_pattern, filename))


def main():
    parser = argparse.ArgumentParser(description="Ingest articles using the API")
    parser.add_argument("--api-url", default=os.getenv("API_URL", "http://localhost:8000"), help="API base URL")
    parser.add_argument("--output-dir", default="/data", help="Output directory")
    parser.add_argument("--batch-size", type=int, default=100, help="Batch size")

    args = parser.parse_args()

    # Check API connection
    if not check_api_connection(args.api_url):
        sys.exit(1)

    # Find CSV files with date in filename
    output_path = os.path.join(args.output_dir)
    if not os.path.exists(output_path):
        logger.error(f"Output directory does not exist: {output_path}")
        sys.exit(1)

    all_csv_files = [f for f in os.listdir(output_path) if f.endswith(".csv")]
    csv_files_with_date = [f for f in all_csv_files if has_date_in_filename(f)]

    logger.info(f"Found {len(all_csv_files)} total CSV files")
    logger.info(f"Found {len(csv_files_with_date)} CSV files with date in filename")

    if not csv_files_with_date:
        logger.warning(f"No CSV files with date found in {output_path}")
        return

    # Ingest CSV files with date in filename
    total_ingested = 0
    for csv_file in csv_files_with_date:
        csv_path = os.path.join(output_path, csv_file)
        logger.info(f"Processing file with date: {csv_file}")
        ingested = ingest_csv(args.api_url, csv_path, args.batch_size)
        total_ingested += ingested

    logger.info(f"Total articles ingested: {total_ingested}")


if __name__ == "__main__":
    main()
