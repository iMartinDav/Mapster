"""Integration tests for database cache."""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from mapster.cache import DatabaseCache


@pytest.mark.integration
class TestDatabaseCache:
    """Tests for PostgreSQL database cache."""
    
    @pytest_asyncio.async_test
    async def test_set_and_get(self, async_db: AsyncSession):
        """Test setting and getting cache values."""
        cache = DatabaseCache(async_db)
        
        # Set value
        test_data = {"streets": ["Main St", "Oak Ave"], "buildings": []}
        success = await cache.set(
            cache_key="test-key-123",
            data=test_data,
            city="Paris",
            country="France",
            theme="minimalist",
        )
        assert success is True
        
        # Get value
        retrieved = await cache.get("test-key-123")
        assert retrieved is not None
        assert retrieved["streets"] == ["Main St", "Oak Ave"]
    
    @pytest_asyncio.async_test
    async def test_get_nonexistent(self, async_db: AsyncSession):
        """Test getting nonexistent cache key."""
        cache = DatabaseCache(async_db)
        
        retrieved = await cache.get("nonexistent-key")
        assert retrieved is None
    
    @pytest_asyncio.async_test
    async def test_delete(self, async_db: AsyncSession):
        """Test deleting cache entry."""
        cache = DatabaseCache(async_db)
        
        # Set value
        await cache.set(
            cache_key="delete-me",
            data={"test": "data"},
            city="Berlin",
            country="Germany",
            theme="dark",
        )
        
        # Delete
        success = await cache.delete("delete-me")
        assert success is True
        
        # Verify deleted
        retrieved = await cache.get("delete-me")
        assert retrieved is None
    
    @pytest_asyncio.async_test
    async def test_access_count(self, async_db: AsyncSession):
        """Test access count increment."""
        cache = DatabaseCache(async_db)
        
        # Set value
        await cache.set(
            cache_key="access-test",
            data={"counter": 0},
            city="London",
            country="UK",
            theme="vintage",
        )
        
        # Access multiple times
        for _ in range(5):
            await cache.get("access-test")
        
        # Check stats
        stats = await cache.get_stats()
        assert stats["total_accesses"] >= 5
    
    @pytest_asyncio.async_test
    async def test_invalidate_city(self, async_db: AsyncSession):
        """Test invalidating cache for a city."""
        cache = DatabaseCache(async_db)
        
        # Set multiple entries for same city
        for i in range(3):
            await cache.set(
                cache_key=f"paris-{i}",
                data={"index": i},
                city="Paris",
                country="France",
                theme="minimalist",
            )
        
        # Invalidate all Paris entries
        invalidated = await cache.invalidate_city("Paris", "France")
        assert invalidated == 3
        
        # Verify all deleted
        for i in range(3):
            retrieved = await cache.get(f"paris-{i}")
            assert retrieved is None
    
    @pytest_asyncio.async_test
    async def test_get_stats(self, async_db: AsyncSession):
        """Test cache statistics."""
        cache = DatabaseCache(async_db)
        
        # Add some entries
        for i in range(5):
            await cache.set(
                cache_key=f"stat-test-{i}",
                data={"index": i},
                city=f"City{i}",
                country="Country",
                theme="test",
            )
        
        stats = await cache.get_stats()
        
        assert "total_entries" in stats
        assert "total_accesses" in stats
        assert stats["total_entries"] == 5
