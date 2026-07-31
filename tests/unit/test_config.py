"""Unit tests for application configuration."""

import pytest
from mapster.config import Settings, get_settings


class TestSettings:
    """Tests for application settings."""
    
    def test_settings_defaults(self):
        """Test default settings values."""
        settings = Settings()
        
        assert settings.APP_NAME == "Mapster"
        assert settings.HOST == "0.0.0.0"
        assert settings.PORT == 8000
        assert settings.DEBUG is False
    
    def test_settings_database_url(self):
        """Test database URL configuration."""
        settings = Settings()
        
        assert "postgresql" in settings.DATABASE_URL
        assert "asyncpg" in settings.DATABASE_URL_ASYNC
    
    def test_get_settings_caching(self):
        """Test settings caching."""
        settings1 = get_settings()
        settings2 = get_settings()
        
        assert settings1 is settings2
    
    def test_settings_model_config(self):
        """Test settings model configuration."""
        settings = Settings()
        
        assert settings.Config.env_file == ".env"
        assert settings.Config.case_sensitive is True
