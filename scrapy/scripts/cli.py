#!/usr/bin/env python3
"""
Blog Scraper CLI
A Typer CLI application for managing articles
"""

import os
import re
from datetime import datetime

import pandas as pd
import requests
import typer
from loguru import logger

app = typer.Typer(help="Blog Scraper CLI for managing articles")


def check_api_connection(api_url: str) -> bool:
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


def has_date_in_filename(filename: str) -> bool:
    """Check if filename contains a year-month-day datestamp."""
    # Pattern to match YYYY-MM-DD format in filename
    date_pattern = r"\d{4}-\d{2}-\d{2}"
    return bool(re.search(date_pattern, filename))


def ingest_csv(api_url: str, csv_path: str, batch_size: int = 100) -> int:
    """Ingest articles from CSV file using the API."""
    try:
        logger.info(f"Reading {csv_path}")
        df = pd.read_csv(csv_path)
        df["_source_file"] = os.path.basename(csv_path)
        logger.info(f"Found {len(df)} articles")

        # drop duplicates
        df = df.drop_duplicates(subset=["article_title"])
        logger.info(f"Dropped duplicates, now {len(df)} articles")

        total_processed = 0
        total_created = 0
        total_updated = 0

        for i in range(0, len(df), batch_size):
            batch = df.iloc[i : i + batch_size]

            articles_to_process = []
            for _, row in batch.iterrows():
                article = clean_article(row)
                if article:
                    articles_to_process.append(article)

            if articles_to_process:
                try:
                    # Use bulk-upsert API endpoint
                    response = requests.post(
                        f"{api_url}/articles/bulk-upsert", json=articles_to_process
                    )

                    if response.status_code == 200:
                        result = response.json()
                        total_created += result.get("created", 0)
                        total_updated += result.get("updated", 0)
                        total_processed += len(articles_to_process)

                        logger.info(
                            f"Batch {i//batch_size + 1}: {result.get('created', 0)} created, {result.get('updated', 0)} updated"
                        )

                        if result.get("errors", 0) > 0:
                            logger.warning(
                                f"Batch {i//batch_size + 1}: {result.get('errors', 0)} failed"
                            )
                    else:
                        logger.error(
                            f"Batch {i//batch_size + 1} failed: {response.status_code} - {response.text}"
                        )

                except Exception as e:
                    logger.error(f"Batch {i//batch_size + 1} error: {e}")
                    # Try individual upsert for debugging
                    for article in articles_to_process[
                        :3
                    ]:  # Try first 3 articles individually
                        try:
                            response = requests.post(
                                f"{api_url}/articles/upsert", json=article
                            )
                            if response.status_code == 200:
                                result = response.json()
                                logger.info(
                                    f"Individual upsert success for: {article.get('article_title', 'NO_TITLE')} - {result.get('action')}"
                                )
                            else:
                                logger.error(
                                    f"Individual upsert failed: {response.status_code} - {response.text}"
                                )
                        except Exception as individual_error:
                            logger.error(
                                f"Individual upsert failed: {individual_error}"
                            )
                    continue

        logger.info(
            f"Processed {total_processed} articles from {csv_path} ({total_created} created, {total_updated} updated)"
        )
        return total_processed

    except Exception as e:
        logger.error(f"Error ingesting {csv_path}: {e}")
        return 0


@app.command()
def ingest(
    api_url: str = typer.Option(
        default=os.getenv("API_URL"), help="API base URL"
    ),
    output_dir: str = typer.Option(
        default="/data", help="Output directory containing CSV files"
    ),
    batch_size: int = typer.Option(default=100, help="Batch size for processing"),
):
    """Ingest articles from CSV files with date in filename."""
    # Check API connection
    if not check_api_connection(api_url):
        raise typer.Exit(1)

    # Find CSV files with date in filename
    output_path = os.path.join(output_dir)
    if not os.path.exists(output_path):
        logger.error(f"Output directory does not exist: {output_path}")
        raise typer.Exit(1)

    all_csv_files = [f for f in os.listdir(output_path) if f.endswith(".csv")]
    csv_files_with_date = [f for f in all_csv_files if has_date_in_filename(f)]

    logger.info(f"Found {len(all_csv_files)} total CSV files")
    logger.info(f"Found {len(csv_files_with_date)} CSV files with date in filename")

    if not csv_files_with_date:
        logger.warning(f"No CSV files with date found in {output_path}")
        return

    # Process CSV files with date in filename
    total_processed = 0
    for csv_file in csv_files_with_date:
        csv_path = os.path.join(output_path, csv_file)
        logger.info(f"Processing file with date: {csv_file}")
        processed = ingest_csv(api_url, csv_path, batch_size)
        total_processed += processed

    logger.info(f"Total articles processed: {total_processed}")


@app.command()
def delete_all(
    api_url: str = typer.Option(
        default=os.getenv("API_URL"), help="API base URL"
    ),
    confirm: bool = typer.Option(
        default=False, help="Confirm deletion without prompting"
    ),
):
    """Delete all articles from the index."""
    # Check API connection
    if not check_api_connection(api_url):
        raise typer.Exit(1)

    # Get all articles to delete
    try:
        logger.info("Fetching all articles...")
        response = requests.get(f"{api_url}/articles", params={"limit": 10000})
        if response.status_code != 200:
            logger.error(f"Failed to fetch articles: {response.status_code}")
            raise typer.Exit(1)

        data = response.json()
        articles = data.get("articles", [])
        total_articles = data.get("total", 0)

        if total_articles == 0:
            logger.info("No articles found to delete")
            return

        logger.info(f"Found {total_articles} articles to delete")

        # Confirm deletion
        if not confirm:
            if not typer.confirm(
                f"Are you sure you want to delete all {total_articles} articles?"
            ):
                logger.info("Deletion cancelled")
                return

        # Delete articles in batches
        deleted_count = 0
        batch_size = 100

        for i in range(0, len(articles), batch_size):
            batch = articles[i : i + batch_size]

            for article in batch:
                try:
                    article_id = article.get("id")
                    if article_id:
                        delete_response = requests.delete(
                            f"{api_url}/articles/{article_id}"
                        )
                        if delete_response.status_code == 200:
                            deleted_count += 1
                            if (
                                deleted_count % 10 == 0
                            ):  # Log progress every 10 deletions
                                logger.info(f"Deleted {deleted_count} articles...")
                        else:
                            logger.warning(
                                f"Failed to delete article {article_id}: {delete_response.status_code}"
                            )
                except Exception as e:
                    logger.error(f"Error deleting article: {e}")

            # If we have more articles to fetch, get the next batch
            if i + batch_size >= len(articles) and deleted_count < total_articles:
                response = requests.get(
                    f"{api_url}/articles",
                    params={"limit": 10000, "offset": len(articles)},
                )
                if response.status_code == 200:
                    data = response.json()
                    articles.extend(data.get("articles", []))

        logger.info(f"Successfully deleted {deleted_count} articles")

    except Exception as e:
        logger.error(f"Error during deletion: {e}")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
