from fastapi.testclient import TestClient


class TestTopics:
    """Test topics-related functionality"""

    def test_get_articles_by_topic(
        self, client: TestClient, clean_articles_index, sample_articles
    ):
        """Test getting articles by topic"""
        # Create articles
        for article in sample_articles:
            client.post("/v1/articles/upsert", json=article)

        # Get articles by topic
        response = client.get("/v1/topics/API/articles")
        assert response.status_code == 200

        data = response.json()
        assert data["topic"] == "API"
        assert len(data["articles"]) > 0

        # Verify all returned articles contain the topic
        for article in data["articles"]:
            assert "API" in article["topics"]

    def test_get_articles_by_topic_empty(
        self, client: TestClient, clean_articles_index
    ):
        """Test getting articles by topic when no articles exist"""
        response = client.get("/v1/topics/NonexistentTopic/articles")
        assert response.status_code == 200

        data = response.json()
        assert data["topic"] == "NonexistentTopic"
        assert len(data["articles"]) == 0
        assert data["total"] == 0

    def test_get_articles_by_topic_with_pagination(
        self, client: TestClient, clean_articles_index, sample_articles
    ):
        """Test getting articles by topic with pagination"""
        # Create articles
        for article in sample_articles:
            client.post("/v1/articles/upsert", json=article)

        # Test limit
        response = client.get("/v1/topics/Testing/articles?limit=1")
        assert response.status_code == 200

        data = response.json()
        assert len(data["articles"]) == 1
        assert data["limit"] == 1

        # Test offset
        response = client.get("/v1/topics/Testing/articles?limit=1&offset=1")
        assert response.status_code == 200

        data = response.json()
        assert len(data["articles"]) == 1
        assert data["offset"] == 1

    def test_get_popular_topics(
        self, client: TestClient, clean_articles_index, sample_articles
    ):
        """Test getting popular topics"""
        # Create articles
        for article in sample_articles:
            client.post("/v1/articles/upsert", json=article)

        response = client.get("/v1/topics/popular")
        assert response.status_code == 200

        data = response.json()
        assert "popular_topics" in data
        assert len(data["popular_topics"]) > 0

        # Verify topics are sorted by count (descending)
        topics = data["popular_topics"]
        for i in range(len(topics) - 1):
            assert topics[i]["count"] >= topics[i + 1]["count"]

    def test_get_popular_topics_with_limit(
        self, client: TestClient, clean_articles_index, sample_articles
    ):
        """Test getting popular topics with limit"""
        # Create articles
        for article in sample_articles:
            client.post("/v1/articles/upsert", json=article)

        response = client.get("/v1/topics/popular?limit=2")
        assert response.status_code == 200

        data = response.json()
        assert len(data["popular_topics"]) == 2

    def test_get_popular_topics_empty(self, client: TestClient, clean_articles_index):
        """Test getting popular topics when no articles exist"""
        response = client.get("/v1/topics/popular")
        assert response.status_code == 200

        data = response.json()
        assert "popular_topics" in data
        assert len(data["popular_topics"]) == 0
