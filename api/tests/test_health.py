import pytest
from fastapi.testclient import TestClient


class TestHealthChecks:
    """Test health check endpoints"""

    def test_health_check(self, client: TestClient):
        """Test basic health check"""
        response = client.get("/v1/misc/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "blog-scraper-api"
        assert data["version"] == "1.0.0"
        assert "timestamp" in data

    def test_liveness_check(self, client: TestClient):
        """Test liveness check"""
        response = client.get("/v1/misc/health/live")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "alive"
        assert data["service"] == "blog-scraper-api"
        assert "timestamp" in data

    def test_readiness_check_success(self, client: TestClient, clean_articles_index):
        """Test readiness check when Elasticsearch is available"""
        response = client.get("/v1/misc/health/ready")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "ready"
        assert data["service"] == "blog-scraper-api"
        assert data["version"] == "1.0.0"
        assert "timestamp" in data
        
        # Check Elasticsearch dependency info
        dependencies = data["dependencies"]
        assert "elasticsearch" in dependencies
        es_info = dependencies["elasticsearch"]
        assert es_info["status"] == "connected"
        assert "version" in es_info
        assert "cluster_name" in es_info

    def test_readiness_check_elasticsearch_info(self, client: TestClient, clean_articles_index):
        """Test that readiness check includes Elasticsearch version and cluster info"""
        response = client.get("/v1/misc/health/ready")
        assert response.status_code == 200
        
        data = response.json()
        es_info = data["dependencies"]["elasticsearch"]
        
        # Verify Elasticsearch info is present
        assert es_info["version"] != "unknown"
        assert es_info["cluster_name"] != "unknown" 