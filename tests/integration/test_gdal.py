"""Integration tests for GDAL processor."""

import numpy as np
import pytest
from pathlib import Path
import tempfile

from mapster.gdal_processor import GDALGeospatialProcessor


@pytest.fixture
def gdal_processor():
    """Create GDAL processor for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        processor = GDALGeospatialProcessor(cache_dir=tmpdir)
        yield processor


class TestGDALGeospatialProcessor:
    """Tests for GDAL geospatial processor."""
    
    def test_create_vector_from_points(self, gdal_processor):
        """Test creating vector file from points."""
        points = [
            {"lon": 2.3522, "lat": 48.8566, "name": "Paris"},
            {"lon": -0.1276, "lat": 51.5074, "name": "London"},
            {"lon": 13.4050, "lat": 52.5200, "name": "Berlin"},
        ]
        
        output_path = str(gdal_processor.cache_dir / "test_points.geojson")
        result = gdal_processor.create_vector_from_points(points, output_path)
        
        assert result == output_path
        assert Path(output_path).exists()
    
    def test_get_raster_statistics(self, gdal_processor):
        """Test getting raster statistics."""
        # Create a simple test raster
        data = np.random.rand(100, 100).astype(np.float32)
        input_path = str(gdal_processor.cache_dir / "test_raster.tif")
        
        from osgeo import gdal
        
        driver = gdal.GetDriverByName("GTiff")
        dataset = driver.Create(input_path, 100, 100, 1, gdal.GDT_Float32)
        dataset.SetGeoTransform((0, 1, 0, 0, 0, -1))
        
        band = dataset.GetRasterBand(1)
        band.WriteArray(data)
        band.FlushCache()
        
        dataset = None
        
        # Get statistics
        stats = gdal_processor.get_raster_statistics(input_path)
        
        assert "min" in stats
        assert "max" in stats
        assert "mean" in stats
        assert "std_dev" in stats
        assert stats["width"] == 100
        assert stats["height"] == 100
