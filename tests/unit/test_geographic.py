"""Unit tests for geospatial utilities."""

import pytest
import numpy as np
from shapely.geometry import Point, Polygon


class TestGeographicCalculations:
    """Tests for geographic calculations."""
    
    def test_point_creation(self):
        """Test creating geographic points."""
        point = Point(2.3522, 48.8566)  # Paris coordinates
        
        assert point.x == 2.3522
        assert point.y == 48.8566
        assert point.is_valid
    
    def test_distance_calculation(self):
        """Test distance calculation between points."""
        paris = Point(2.3522, 48.8566)
        london = Point(-0.1276, 51.5074)
        
        # Calculate distance in degrees (approximate)
        distance_degrees = paris.distance(london)
        
        # London should be roughly 3-4 degrees away from Paris
        assert 3 < distance_degrees < 5
    
    def test_polygon_creation(self):
        """Test creating geographic polygons."""
        # Simple square polygon
        coords = [
            (0, 0),
            (1, 0),
            (1, 1),
            (0, 1),
            (0, 0),
        ]
        polygon = Polygon(coords)
        
        assert polygon.is_valid
        assert polygon.area == 1.0
    
    def test_point_in_polygon(self):
        """Test point-in-polygon check."""
        polygon = Polygon([
            (0, 0),
            (10, 0),
            (10, 10),
            (0, 10),
            (0, 0),
        ])
        
        inside_point = Point(5, 5)
        outside_point = Point(15, 5)
        
        assert polygon.contains(inside_point)
        assert not polygon.contains(outside_point)


class TestCoordinateConversions:
    """Tests for coordinate system conversions."""
    
    def test_degrees_to_radians(self):
        """Test degree to radian conversion."""
        degrees = 180
        radians = np.radians(degrees)
        
        assert abs(radians - np.pi) < 1e-10
    
    def test_haversine_distance(self):
        """Test haversine distance calculation."""
        from math import radians, sin, cos, sqrt, asin
        
        def haversine(lat1, lon1, lat2, lon2):
            """Calculate haversine distance in km."""
            lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
            dlat = lat2 - lat1
            dlon = lon2 - lon1
            a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
            c = 2 * asin(sqrt(a))
            r = 6371  # Radius of earth in km
            return c * r
        
        # Paris to London (~344 km)
        distance = haversine(48.8566, 2.3522, 51.5074, -0.1276)
        
        assert 340 < distance < 350
