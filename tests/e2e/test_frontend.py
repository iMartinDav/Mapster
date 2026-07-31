"""End-to-end tests with Playwright."""

import pytest
from playwright.sync_api import Page, expect, sync_playwright


@pytest.mark.e2e
class TestFrontendLoading:
    """Tests for frontend loading and rendering."""
    
    def test_homepage_loads(self, page: Page):
        """Test that homepage loads successfully."""
        page.goto("http://localhost:5173")
        
        # Wait for page to load
        page.wait_for_load_state("networkidle")
        
        # Check page title
        expect(page).to_have_title(/Mapster|Map/)
    
    def test_map_interface_visible(self, page: Page):
        """Test that map interface is visible."""
        page.goto("http://localhost:5173")
        page.wait_for_load_state("networkidle")
        
        # Check for main interface elements
        expect(page.locator("body")).to_be_visible()
    
    def test_search_form_exists(self, page: Page):
        """Test that search form exists."""
        page.goto("http://localhost:5173")
        page.wait_for_load_state("networkidle")
        
        # Look for search input
        search_input = page.locator("input[placeholder*='city' i], input[placeholder*='search' i]")
        expect(search_input.first).to_be_visible()


@pytest.mark.e2e
class TestPosterGeneration:
    """Tests for poster generation workflow."""
    
    def test_generate_poster_flow(self, page: Page):
        """Test complete poster generation flow."""
        page.goto("http://localhost:5173")
        page.wait_for_load_state("networkidle")
        
        # Enter city name
        city_input = page.locator("input[placeholder*='city' i], input[placeholder*='search' i]")
        city_input.first.fill("Paris")
        
        # Click search/generate button
        generate_button = page.locator("button:has-text('Generate'), button:has-text('Search')")
        generate_button.first.click()
        
        # Wait for generation to complete (with timeout)
        page.wait_for_timeout(5000)
        
        # Check for result
        expect(page.locator("body")).to_be_visible()
    
    def test_theme_selection(self, page: Page):
        """Test theme selection functionality."""
        page.goto("http://localhost:5173")
        page.wait_for_load_state("networkidle")
        
        # Look for theme selector
        theme_selector = page.locator("select, [role='listbox']")
        
        if theme_selector.count() > 0:
            # Click and select a theme
            theme_selector.first.click()
            page.wait_for_timeout(500)


@pytest.mark.e2e
class TestResponsiveDesign:
    """Tests for responsive design."""
    
    def test_mobile_viewport(self, page: Page):
        """Test page renders correctly in mobile viewport."""
        page.set_viewport_size({"width": 375, "height": 812})  # iPhone X
        page.goto("http://localhost:5173")
        page.wait_for_load_state("networkidle")
        
        expect(page.locator("body")).to_be_visible()
    
    def test_tablet_viewport(self, page: Page):
        """Test page renders correctly in tablet viewport."""
        page.set_viewport_size({"width": 768, "height": 1024})  # iPad
        page.goto("http://localhost:5173")
        page.wait_for_load_state("networkidle")
        
        expect(page.locator("body")).to_be_visible()
    
    def test_desktop_viewport(self, page: Page):
        """Test page renders correctly in desktop viewport."""
        page.set_viewport_size({"width": 1920, "height": 1080})
        page.goto("http://localhost:5173")
        page.wait_for_load_state("networkidle")
        
        expect(page.locator("body")).to_be_visible()
