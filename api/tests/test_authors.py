from fastapi.testclient import TestClient


class TestAuthors:
    """Test authors-related functionality"""

    def test_get_articles_by_author(
        self, client: TestClient, clean_articles_index, sample_articles
    ):
        """Test getting articles by author"""
        # Create articles
        for article in sample_articles:
            client.post("/v1/articles/upsert", json=article)

        # Get articles by author
        response = client.get("/v1/authors/Test Author 1/articles")
        assert response.status_code == 200

        data = response.json()
        assert data["author"] == "Test Author 1"
        assert len(data["articles"]) == 2  # Two articles by Test Author 1

        # Verify all returned articles are by the correct author
        for article in data["articles"]:
            assert article["author"] == "Test Author 1"

    def test_get_articles_by_author_empty(
        self, client: TestClient, clean_articles_index
    ):
        """Test getting articles by author when no articles exist"""
        response = client.get("/v1/authors/NonexistentAuthor/articles")
        assert response.status_code == 200

        data = response.json()
        assert data["author"] == "NonexistentAuthor"
        assert len(data["articles"]) == 0
        assert data["total"] == 0

    def test_get_articles_by_author_with_pagination(
        self, client: TestClient, clean_articles_index, sample_articles
    ):
        """Test getting articles by author with pagination"""
        # Create articles
        for article in sample_articles:
            client.post("/v1/articles/upsert", json=article)

        # Test limit
        response = client.get("/v1/authors/Test Author 1/articles?limit=1")
        assert response.status_code == 200

        data = response.json()
        assert len(data["articles"]) == 1
        assert data["limit"] == 1

        # Test offset
        response = client.get("/v1/authors/Test Author 1/articles?limit=1&offset=1")
        assert response.status_code == 200

        data = response.json()
        assert len(data["articles"]) == 1
        assert data["offset"] == 1

    def test_get_articles_by_author_sorted_by_date(
        self, client: TestClient, clean_articles_index, sample_articles
    ):
        """Test that articles by author are sorted by publication date (descending)"""
        # Create articles
        for article in sample_articles:
            client.post("/v1/articles/upsert", json=article)

        response = client.get("/v1/authors/Test Author 1/articles")
        assert response.status_code == 200

        data = response.json()
        articles = data["articles"]

        # Verify articles are sorted by published date (descending)
        for i in range(len(articles) - 1):
            assert articles[i]["published"] >= articles[i + 1]["published"]
