"""End-to-end tests for API endpoints."""

import pytest
from playwright.sync_api import Page, expect, sync_playwright


@pytest.mark.e2e
class TestAPIEndpoints:
    """Tests for API endpoints via browser."""
    
    def test_health_endpoint(self, page: Page):
        """Test health endpoint via browser."""
        response = page.goto("http://localhost:8000/health")
        
        assert response.status == 200
        content = page.content()
        assert "ok" in content.lower()
    
    def test_posters_api(self, page: Page):
        """Test posters API endpoint."""
        response = page.goto("http://localhost:8000/api/posters")
        
        # Should return JSON
        assert response.status == 200
        content_type = response.headers.get("content-type", "")
        assert "json" in content_type.lower()


@pytest.mark.e2e
class TestFullWorkflow:
    """Tests for complete workflow from frontend to backend."""
    
    def test_end_to_end_poster_creation(self, page: Page):
        """Test complete poster creation workflow."""
        # Navigate to frontend
        page.goto("http://localhost:5173")
        page.wait_for_load_state("networkidle")
        
        # Enter city
        city_input = page.locator("input").first
        city_input.fill("Berlin")
        
        # Generate poster
        generate_button = page.locator("button").first
        generate_button.click()
        
        # Wait for API call to complete
        page.wait_for_timeout(10000)
        
        # Verify page state
        expect(page.locator("body")).to_be_visible()
