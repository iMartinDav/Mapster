"""Unit tests for database models."""

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from mapster.db import Base
from mapster.models import GenerationJob, MapCache, Poster


@pytest.fixture
def db_session():
    """Create a test database session."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    
    with Session(engine) as session:
        yield session
    
    Base.metadata.drop_all(engine)


class TestPosterModel:
    """Tests for Poster model."""
    
    def test_create_poster(self, db_session: Session):
        """Test creating a new poster."""
        poster = Poster(
            city="Paris",
            country="France",
            theme="minimalist",
            distance=5000,
            format_name="12x18",
            filename="paris-minimalist.png",
            content_type="image/png",
        )
        
        db_session.add(poster)
        db_session.commit()
        
        assert poster.id is not None
        assert poster.city == "Paris"
        assert poster.country == "France"
        assert poster.created_at is not None
    
    def test_poster_to_dict(self, db_session: Session):
        """Test poster to_dict method."""
        poster = Poster(
            city="Tokyo",
            country="Japan",
            theme="dark",
            distance=3000,
            format_name="24x36",
            filename="tokyo-dark.png",
            content_type="image/png",
        )
        
        db_session.add(poster)
        db_session.commit()
        
        poster_dict = poster.to_dict()
        
        assert poster_dict["city"] == "Tokyo"
        assert poster_dict["country"] == "Japan"
        assert poster_dict["theme"] == "dark"
        assert "image_url" in poster_dict
        assert "thumbnail_url" in poster_dict
    
    def test_poster_repr(self, db_session: Session):
        """Test poster string representation."""
        poster = Poster(
            city="London",
            country="UK",
            theme="vintage",
            distance=4000,
            format_name="18x24",
            filename="london-vintage.png",
            content_type="image/png",
        )
        
        db_session.add(poster)
        db_session.commit()
        
        repr_str = repr(poster)
        assert "London" in repr_str
        assert "UK" in repr_str
        assert "vintage" in repr_str


class TestMapCacheModel:
    """Tests for MapCache model."""
    
    def test_create_cache_entry(self, db_session: Session):
        """Test creating a cache entry."""
        cache = MapCache(
            cache_key="abc123def456",
            data='{"streets": [], "buildings": []}',
            city="Berlin",
            country="Germany",
            theme="modern",
        )
        
        db_session.add(cache)
        db_session.commit()
        
        assert cache.id is not None
        assert cache.cache_key == "abc123def456"
        assert cache.access_count == 0
    
    def test_cache_repr(self, db_session: Session):
        """Test cache string representation."""
        cache = MapCache(
            cache_key="xyz789",
            data='{"streets": []}',
            city="Madrid",
            country="Spain",
            theme="colorful",
        )
        
        db_session.add(cache)
        db_session.commit()
        
        repr_str = repr(cache)
        assert "Madrid" in repr_str
        assert "Spain" in repr_str
        assert "xyz789" in repr_str


class TestGenerationJobModel:
    """Tests for GenerationJob model."""
    
    def test_create_job(self, db_session: Session):
        """Test creating a generation job."""
        job = GenerationJob(
            status="pending",
            request_type="poster",
            request_data={"city": "Rome", "country": "Italy"},
        )
        
        db_session.add(job)
        db_session.commit()
        
        assert job.id is not None
        assert job.status == "pending"
        assert job.progress == 0
    
    def test_job_to_dict(self, db_session: Session):
        """Test job to_dict method."""
        job = GenerationJob(
            status="completed",
            request_type="poster",
            request_data={"city": "Barcelona", "country": "Spain"},
            result={"filename": "barcelona.png"},
        )
        
        db_session.add(job)
        db_session.commit()
        
        job_dict = job.to_dict()
        
        assert job_dict["status"] == "completed"
        assert job_dict["result"]["filename"] == "barcelona.png"
        assert "created_at" in job_dict
    
    def test_job_repr(self, db_session: Session):
        """Test job string representation."""
        job = GenerationJob(
            status="processing",
            request_type="poster",
            request_data={"city": "Amsterdam", "country": "Netherlands"},
        )
        
        db_session.add(job)
        db_session.commit()
        
        repr_str = repr(job)
        assert "processing" in repr_str
