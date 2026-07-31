"""Integration tests for API endpoints."""

import pytest
import pytest_asyncio
from httpx import AsyncClient


@pytest.mark.integration
class TestHealthEndpoint:
    """Tests for health check endpoint."""
    
    @pytest_asyncio.async_test
    async def test_health_check(self, client: AsyncClient):
        """Test health check endpoint returns 200."""
        response = await client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "version" in data


@pytest.mark.integration
class TestPosterEndpoints:
    """Tests for poster API endpoints."""
    
    @pytest_asyncio.async_test
    async def test_create_poster(self, client: AsyncClient, sample_poster_data):
        """Test poster creation endpoint."""
        response = await client.post("/api/posters", json=sample_poster_data)
        
        # Should return 202 Accepted for async job
        assert response.status_code == 202
        data = response.json()
        assert "job_id" in data
        assert data["status"] == "pending"
    
    @pytest_asyncio.async_test
    async def test_get_posters_list(self, client: AsyncClient):
        """Test getting list of posters."""
        response = await client.get("/api/posters")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
    
    @pytest_asyncio.async_test
    async def test_get_poster_by_id(self, client: AsyncClient, sample_poster_data):
        """Test getting poster by ID."""
        # First create a poster
        create_response = await client.post("/api/posters", json=sample_poster_data)
        assert create_response.status_code == 202
        job_id = create_response.json()["job_id"]
        
        # Get poster
        response = await client.get(f"/api/posters/{job_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert "id" in data


@pytest.mark.integration
class TestGeographicEndpoints:
    """Tests for geographic API endpoints."""
    
    @pytest_asyncio.async_test
    async def test_validate_geographic_request(self, client: AsyncClient):
        """Test geographic request validation."""
        response = await client.post("/api/validate", json={
            "city": "Paris",
            "country": "France",
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert "center_lat" in data
        assert "center_lon" in data
    
    @pytest_asyncio.async_test
    async def test_validate_invalid_geographic_request(self, client: AsyncClient):
        """Test validation with invalid geographic request."""
        response = await client.post("/api/validate", json={
            "city": "NonExistentCity123",
            "country": "NonExistentCountry",
        })
        
        # Should return error for invalid location
        assert response.status_code in [400, 404, 422]
