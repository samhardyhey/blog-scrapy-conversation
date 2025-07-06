from fastapi.testclient import TestClient


class TestStats:
    """Test statistics functionality"""

    def test_get_stats_empty(self, client: TestClient, clean_articles_index):
        """Test getting stats when no articles exist"""
        response = client.get("/v1/stats")
        assert response.status_code == 200

        data = response.json()
        assert data["total_articles"] == 0
        assert data["average_content_length"] is None
        assert data["author_stats"]["total_authors"] == 0
        assert data["department_stats"]["total_departments"] == 0
        assert data["topic_stats"]["total_topics"] == 0

    def test_get_stats_with_data(
        self, client: TestClient, clean_articles_index, sample_articles
    ):
        """Test getting stats when articles exist"""
        # Create articles
        for article in sample_articles:
            client.post("/v1/articles/upsert", json=article)

        response = client.get("/v1/stats")
        assert response.status_code == 200

        data = response.json()
        assert data["total_articles"] == 3
        assert data["average_content_length"] is not None
        assert data["author_stats"]["total_authors"] == 2  # Two unique authors
        assert data["department_stats"]["total_departments"] == 2  # Two departments
        assert data["topic_stats"]["total_topics"] > 0

    def test_author_stats(
        self, client: TestClient, clean_articles_index, sample_articles
    ):
        """Test author statistics"""
        # Create articles
        for article in sample_articles:
            client.post("/v1/articles/upsert", json=article)

        response = client.get("/v1/stats")
        assert response.status_code == 200

        data = response.json()
        author_stats = data["author_stats"]

        assert author_stats["total_authors"] == 2
        assert len(author_stats["top_authors"]) == 2

        # Verify top authors are sorted by article count (descending)
        top_authors = author_stats["top_authors"]
        for i in range(len(top_authors) - 1):
            assert (
                top_authors[i]["article_count"] >= top_authors[i + 1]["article_count"]
            )

        # Verify specific authors
        author_names = [author["author"] for author in top_authors]
        assert "Test Author 1" in author_names
        assert "Test Author 2" in author_names

    def test_department_stats(
        self, client: TestClient, clean_articles_index, sample_articles
    ):
        """Test department statistics"""
        # Create articles
        for article in sample_articles:
            client.post("/v1/articles/upsert", json=article)

        response = client.get("/v1/stats")
        assert response.status_code == 200

        data = response.json()
        dept_stats = data["department_stats"]

        assert dept_stats["total_departments"] == 2
        assert len(dept_stats["top_departments"]) == 2

        # Verify departments are sorted by article count (descending)
        top_depts = dept_stats["top_departments"]
        for i in range(len(top_depts) - 1):
            assert top_depts[i]["article_count"] >= top_depts[i + 1]["article_count"]

        # Verify specific departments
        dept_names = [dept["department"] for dept in top_depts]
        assert "technology" in dept_names
        assert "science" in dept_names

    def test_topic_stats(
        self, client: TestClient, clean_articles_index, sample_articles
    ):
        """Test topic statistics"""
        # Create articles
        for article in sample_articles:
            client.post("/v1/articles/upsert", json=article)

        response = client.get("/v1/stats")
        assert response.status_code == 200

        data = response.json()
        topic_stats = data["topic_stats"]

        assert topic_stats["total_topics"] > 0
        assert len(topic_stats["top_topics"]) > 0

        # Verify top topics are sorted by article count (descending)
        top_topics = topic_stats["top_topics"]
        for i in range(len(top_topics) - 1):
            assert top_topics[i]["article_count"] >= top_topics[i + 1]["article_count"]

    def test_publication_timeline_stats(
        self, client: TestClient, clean_articles_index, sample_articles
    ):
        """Test publication timeline statistics"""
        # Create articles
        for article in sample_articles:
            client.post("/v1/articles/upsert", json=article)

        response = client.get("/v1/stats")
        assert response.status_code == 200

        data = response.json()
        pub_stats = data["publication_stats"]

        assert "timeline" in pub_stats
        assert len(pub_stats["timeline"]) > 0

        # Verify timeline entries have required fields
        for entry in pub_stats["timeline"]:
            assert "month" in entry
            assert "count" in entry
            assert isinstance(entry["count"], int)

    def test_ingestion_timeline_stats(
        self, client: TestClient, clean_articles_index, sample_articles
    ):
        """Test ingestion timeline statistics"""
        # Create articles
        for article in sample_articles:
            client.post("/v1/articles/upsert", json=article)

        response = client.get("/v1/stats")
        assert response.status_code == 200

        data = response.json()
        ingestion_stats = data["ingestion_stats"]

        assert "timeline" in ingestion_stats
        # Note: ingestion timeline might be empty if _timestamp field is not available
        # This is expected behavior
