import hashlib

from fastapi.testclient import TestClient


class TestArticleLifecycle:
    """Test the complete article lifecycle: Create, Read, Update, Delete"""

    def test_create_article(
        self, client: TestClient, clean_articles_index, sample_article
    ):
        """Test creating a new article"""
        response = client.post("/v1/articles/upsert", json=sample_article)

        assert response.status_code == 200
        data = response.json()
        assert data["action"] == "created"
        assert data["message"] == "Article created successfully"

        # Verify the article was actually created
        article_id = data["id"]
        get_response = client.get(f"/v1/articles/{article_id}")
        assert get_response.status_code == 200

        article_data = get_response.json()
        assert article_data["article_title"] == sample_article["article_title"]
        assert article_data["author"] == sample_article["author"]

    def test_update_article(
        self, client: TestClient, clean_articles_index, sample_article
    ):
        """Test updating an existing article"""
        # First create the article
        create_response = client.post("/v1/articles/upsert", json=sample_article)
        assert create_response.status_code == 200

        # Update the article
        updated_article = sample_article.copy()
        updated_article["article"] = "This is the updated article content."
        updated_article["content_length"] = 60

        update_response = client.post("/v1/articles/upsert", json=updated_article)
        assert update_response.status_code == 200

        data = update_response.json()
        assert data["action"] == "updated"
        assert data["message"] == "Article updated successfully"

        # Verify the article was actually updated
        article_id = data["id"]
        get_response = client.get(f"/v1/articles/{article_id}")
        assert get_response.status_code == 200

        article_data = get_response.json()
        assert article_data["article"] == updated_article["article"]
        assert article_data["content_length"] == updated_article["content_length"]

    def test_get_article(
        self, client: TestClient, clean_articles_index, sample_article
    ):
        """Test retrieving a specific article"""
        # Create the article first
        create_response = client.post("/v1/articles/upsert", json=sample_article)
        article_id = create_response.json()["id"]

        # Get the article
        response = client.get(f"/v1/articles/{article_id}")
        assert response.status_code == 200

        data = response.json()
        assert data["id"] == article_id
        assert data["article_title"] == sample_article["article_title"]
        assert data["author"] == sample_article["author"]
        assert data["article"] == sample_article["article"]

    def test_get_article_not_found(self, client: TestClient, clean_articles_index):
        """Test getting a non-existent article"""
        fake_id = "nonexistent123"
        response = client.get(f"/v1/articles/{fake_id}")
        assert response.status_code == 404

    def test_delete_article(
        self, client: TestClient, clean_articles_index, sample_article
    ):
        """Test deleting an article"""
        # Create the article first
        create_response = client.post("/v1/articles/upsert", json=sample_article)
        article_id = create_response.json()["id"]

        # Delete the article
        response = client.delete(f"/v1/articles/{article_id}")
        assert response.status_code == 200

        data = response.json()
        assert data["id"] == article_id
        assert data["message"] == "Article deleted successfully"

        # Verify the article was actually deleted
        get_response = client.get(f"/v1/articles/{article_id}")
        assert get_response.status_code == 404

    def test_delete_article_not_found(self, client: TestClient, clean_articles_index):
        """Test deleting a non-existent article"""
        fake_id = "nonexistent123"
        response = client.delete(f"/v1/articles/{fake_id}")
        assert response.status_code == 404

    def test_article_id_consistency(
        self, client: TestClient, clean_articles_index, sample_article
    ):
        """Test that article IDs are consistent based on title hash"""
        # Create article twice with same title
        response1 = client.post("/v1/articles/upsert", json=sample_article)
        response2 = client.post("/v1/articles/upsert", json=sample_article)

        assert response1.status_code == 200
        assert response2.status_code == 200

        # Both should have the same ID
        id1 = response1.json()["id"]
        id2 = response2.json()["id"]
        assert id1 == id2

        # Verify it's the expected hash
        expected_id = hashlib.md5(
            sample_article["article_title"].encode("utf-8")
        ).hexdigest()
        assert id1 == expected_id


class TestArticleListAndSearch:
    """Test article listing and search functionality"""

    def test_get_articles_empty(self, client: TestClient, clean_articles_index):
        """Test getting articles when index is empty"""
        response = client.get("/v1/articles")
        assert response.status_code == 200

        data = response.json()
        assert data["articles"] == []
        assert data["total"] == 0

    def test_get_articles_with_data(
        self, client: TestClient, clean_articles_index, sample_articles
    ):
        """Test getting articles when data exists"""
        # Create multiple articles
        for article in sample_articles:
            client.post("/v1/articles/upsert", json=article)

        response = client.get("/v1/articles")
        assert response.status_code == 200

        data = response.json()
        assert len(data["articles"]) == 3
        assert data["total"] == 3

    def test_get_articles_with_pagination(
        self, client: TestClient, clean_articles_index, sample_articles
    ):
        """Test article pagination"""
        # Create multiple articles
        for article in sample_articles:
            client.post("/v1/articles/upsert", json=article)

        # Test limit
        response = client.get("/v1/articles?limit=2")
        assert response.status_code == 200

        data = response.json()
        assert len(data["articles"]) == 2
        assert data["limit"] == 2

        # Test offset
        response = client.get("/v1/articles?limit=1&offset=1")
        assert response.status_code == 200

        data = response.json()
        assert len(data["articles"]) == 1
        assert data["offset"] == 1

    def test_search_articles(
        self, client: TestClient, clean_articles_index, sample_articles
    ):
        """Test article search functionality"""
        # Create articles
        for article in sample_articles:
            client.post("/v1/articles/upsert", json=article)

        # Search by query
        response = client.get("/v1/articles/search?q=Test")
        assert response.status_code == 200

        data = response.json()
        assert len(data["articles"]) > 0

        # Search by author
        response = client.get("/v1/articles/search?author=Test Author 1")
        assert response.status_code == 200

        data = response.json()
        assert len(data["articles"]) == 2  # Two articles by Test Author 1

        # Search by topics
        response = client.get("/v1/articles/search?topics=API")
        assert response.status_code == 200

        data = response.json()
        assert len(data["articles"]) > 0

    def test_search_articles_with_date_range(
        self, client: TestClient, clean_articles_index, sample_articles
    ):
        """Test article search with date filtering"""
        # Create articles
        for article in sample_articles:
            client.post("/v1/articles/upsert", json=article)

        # Search with date range
        response = client.get(
            "/v1/articles/search?date_from=2025-01-15&date_to=2025-01-16"
        )
        assert response.status_code == 200

        data = response.json()
        assert len(data["articles"]) == 2  # Two articles in date range


class TestBulkOperations:
    """Test bulk article operations"""

    def test_bulk_upsert_articles(
        self, client: TestClient, clean_articles_index, sample_articles
    ):
        """Test bulk upserting multiple articles"""
        response = client.post("/v1/articles/bulk-upsert", json=sample_articles)
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "success"
        assert data["created"] == 3
        assert data["updated"] == 0

        # Verify articles were created
        get_response = client.get("/v1/articles")
        assert get_response.status_code == 200
        assert len(get_response.json()["articles"]) == 3

    def test_bulk_upsert_empty_list(self, client: TestClient, clean_articles_index):
        """Test bulk upsert with empty list"""
        response = client.post("/v1/articles/bulk-upsert", json=[])
        assert response.status_code == 400

        data = response.json()
        assert "No articles provided" in data["detail"]

    def test_bulk_upsert_mixed_operations(
        self, client: TestClient, clean_articles_index, sample_articles
    ):
        """Test bulk upsert with some new and some existing articles"""
        # Create first article
        client.post("/v1/articles/upsert", json=sample_articles[0])

        # Bulk upsert all articles (first should update, others should create)
        response = client.post("/v1/articles/bulk-upsert", json=sample_articles)
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "success"
        assert data["created"] == 2
        assert data["updated"] == 1


class TestRelatedArticles:
    """Test related articles functionality"""

    def test_get_related_articles(
        self, client: TestClient, clean_articles_index, sample_articles
    ):
        """Test finding related articles"""
        # Create articles
        for article in sample_articles:
            client.post("/v1/articles/upsert", json=article)

        # Get the first article's ID
        articles_response = client.get("/v1/articles")
        first_article_id = articles_response.json()["articles"][0]["id"]

        # Get related articles
        response = client.get(f"/v1/articles/{first_article_id}/related")
        assert response.status_code == 200

        data = response.json()
        assert data["article_id"] == first_article_id
        assert len(data["related_articles"]) > 0

    def test_get_related_articles_not_found(
        self, client: TestClient, clean_articles_index
    ):
        """Test getting related articles for non-existent article"""
        fake_id = "nonexistent123"
        response = client.get(f"/v1/articles/{fake_id}/related")
        assert response.status_code == 404


class TestArticleTimeline:
    """Test article timeline functionality"""

    def test_get_publication_timeline(
        self, client: TestClient, clean_articles_index, sample_articles
    ):
        """Test getting publication timeline"""
        # Create articles
        for article in sample_articles:
            client.post("/v1/articles/upsert", json=article)

        response = client.get("/v1/articles/timeline")
        assert response.status_code == 200

        data = response.json()
        assert "timeline" in data
        assert len(data["timeline"]) > 0

    def test_get_publication_timeline_with_filter(
        self, client: TestClient, clean_articles_index, sample_articles
    ):
        """Test getting publication timeline with source section filter"""
        # Create articles
        for article in sample_articles:
            client.post("/v1/articles/upsert", json=article)

        response = client.get("/v1/articles/timeline?source_section=technology")
        assert response.status_code == 200

        data = response.json()
        assert "timeline" in data
        assert data["source_section"] == "technology"
