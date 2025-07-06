import pytest
from fastapi.testclient import TestClient
from elasticsearch import Elasticsearch
import os
import time

from main import app


@pytest.fixture(scope="session")
def es_client():
    """Elasticsearch client fixture"""
    es_host = os.getenv("ELASTICSEARCH_HOST", "elasticsearch")
    es_port = os.getenv("ELASTICSEARCH_PORT", "9200")
    client = Elasticsearch([f"http://{es_host}:{es_port}"])

    # Wait for Elasticsearch to be ready
    max_retries = 30
    for i in range(max_retries):
        try:
            client.info()
            break
        except Exception:
            if i == max_retries - 1:
                raise Exception("Elasticsearch not ready after 30 retries")
            time.sleep(1)

    return client


@pytest.fixture(scope="session")
def client():
    """FastAPI test client"""
    return TestClient(app)


@pytest.fixture(scope="function")
def clean_articles_index(es_client):
    """Clean articles index before each test"""
    # Delete index if it exists
    try:
        es_client.indices.delete(index="articles")
    except:
        pass

    # Create fresh index
    es_client.indices.create(
        index="articles",
        body={
            "mappings": {
                "properties": {
                    "article_title": {"type": "text"},
                    "article": {"type": "text"},
                    "author": {
                        "type": "text",
                        "fields": {"keyword": {"type": "keyword"}}
                    },
                    "published": {"type": "date"},
                    "url": {"type": "keyword"},
                    "topics": {
                        "type": "text",
                        "fields": {"keyword": {"type": "keyword"}}
                    },
                    "source_section": {"type": "keyword"},
                    "content_length": {"type": "long"}
                }
            }
        }
    )

    # Wait for index to be ready
    es_client.indices.refresh(index="articles")

    yield

    # Clean up after test
    try:
        es_client.indices.delete(index="articles")
    except:
        pass


@pytest.fixture
def sample_article():
    """Sample article data for testing"""
    return {
        "article_title": "Test Article Title",
        "article": "This is a test article content for testing purposes.",
        "author": "Test Author",
        "published": "2025-01-15T10:00:00Z",
        "url": "https://example.com/test-article",
        "topics": "Testing|API|Development",
        "source_section": "technology",
        "content_length": 50
    }


@pytest.fixture
def sample_articles():
    """Multiple sample articles for testing"""
    return [
        {
            "article_title": "First Test Article",
            "article": "This is the first test article content.",
            "author": "Test Author 1",
            "published": "2025-01-15T10:00:00Z",
            "url": "https://example.com/first-article",
            "topics": "Testing|API",
            "source_section": "technology",
            "content_length": 40
        },
        {
            "article_title": "Second Test Article",
            "article": "This is the second test article content.",
            "author": "Test Author 2",
            "published": "2025-01-16T11:00:00Z",
            "url": "https://example.com/second-article",
            "topics": "Development|Testing",
            "source_section": "science",
            "content_length": 45
        },
        {
            "article_title": "Third Test Article",
            "article": "This is the third test article content.",
            "author": "Test Author 1",
            "published": "2025-01-17T12:00:00Z",
            "url": "https://example.com/third-article",
            "topics": "API|Development",
            "source_section": "technology",
            "content_length": 42
        }
    ]