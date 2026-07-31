"""Integration tests for database operations."""

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from mapster.db import Base
from mapster.models import GenerationJob, MapCache, Poster


@pytest.mark.integration
class TestDatabaseOperations:
    """Tests for database operations."""
    
    def test_create_and_read_poster(self, db_session: Session, sample_poster_data):
        """Test creating and reading poster from database."""
        poster = Poster(
            city=sample_poster_data["city"],
            country=sample_poster_data["country"],
            theme=sample_poster_data["theme"],
            distance=sample_poster_data["distance"],
            format_name=sample_poster_data["format_name"],
            filename=f"{sample_poster_data['city'].lower()}-{sample_poster_data['theme']}.png",
        )
        
        db_session.add(poster)
        db_session.commit()
        
        # Read back
        retrieved = db_session.query(Poster).filter_by(id=poster.id).first()
        
        assert retrieved is not None
        assert retrieved.city == sample_poster_data["city"]
        assert retrieved.country == sample_poster_data["country"]
    
    def test_update_poster(self, db_session: Session):
        """Test updating poster in database."""
        poster = Poster(
            city="Berlin",
            country="Germany",
            theme="modern",
            distance=4000,
            format_name="12x18",
            filename="berlin-modern.png",
        )
        
        db_session.add(poster)
        db_session.commit()
        
        # Update
        poster.theme = "vintage"
        db_session.commit()
        
        # Verify update
        retrieved = db_session.query(Poster).filter_by(id=poster.id).first()
        assert retrieved.theme == "vintage"
    
    def test_delete_poster(self, db_session: Session):
        """Test soft deleting poster from database."""
        poster = Poster(
            city="Madrid",
            country="Spain",
            theme="colorful",
            distance=3500,
            format_name="18x24",
            filename="madrid-colorful.png",
        )
        
        db_session.add(poster)
        db_session.commit()
        
        # Soft delete
        poster.is_deleted = True
        db_session.commit()
        
        # Verify soft delete
        retrieved = db_session.query(Poster).filter_by(id=poster.id).first()
        assert retrieved.is_deleted is True
    
    def test_create_generation_job(self, db_session: Session):
        """Test creating generation job."""
        job = GenerationJob(
            status="pending",
            request_type="poster",
            request_data={"city": "Tokyo", "country": "Japan"},
        )
        
        db_session.add(job)
        db_session.commit()
        
        assert job.id is not None
        assert job.status == "pending"
    
    def test_update_job_status(self, db_session: Session):
        """Test updating generation job status."""
        job = GenerationJob(
            status="pending",
            request_type="poster",
            request_data={"city": "London", "country": "UK"},
        )
        
        db_session.add(job)
        db_session.commit()
        
        # Update status
        job.status = "processing"
        job.progress = 50
        db_session.commit()
        
        # Verify update
        retrieved = db_session.query(GenerationJob).filter_by(id=job.id).first()
        assert retrieved.status == "processing"
        assert retrieved.progress == 50
    
    def test_cache_operations(self, db_session: Session):
        """Test cache create, read, update operations."""
        cache = MapCache(
            cache_key="test-cache-key-123",
            data='{"streets": ["Main St", "Oak Ave"]}',
            city="Sydney",
            country="Australia",
            theme="coastal",
        )
        
        db_session.add(cache)
        db_session.commit()
        
        # Read
        retrieved = db_session.query(MapCache).filter_by(cache_key="test-cache-key-123").first()
        assert retrieved is not None
        assert retrieved.city == "Sydney"
        
        # Update access count
        retrieved.access_count += 1
        db_session.commit()
        
        # Verify
        updated = db_session.query(MapCache).filter_by(cache_key="test-cache-key-123").first()
        assert updated.access_count == 1
