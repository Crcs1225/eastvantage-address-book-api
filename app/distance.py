"""Great-circle distance on a sphere using the IUGG mean Earth radius."""

from math import asin, cos, radians, sin, sqrt

EARTH_RADIUS_KM = 6371.0088


def haversine_km(latitude: float, longitude: float,
                 other_latitude: float, other_longitude: float) -> float:
    lat1, lat2 = radians(latitude), radians(other_latitude)
    delta_lat = lat2 - lat1
    delta_lon = radians(other_longitude - longitude)
    haversine = sin(delta_lat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(delta_lon / 2) ** 2
    # Round-off near antipodal points can otherwise put sqrt outside its domain.
    return 2 * EARTH_RADIUS_KM * asin(sqrt(min(1.0, max(0.0, haversine))))
