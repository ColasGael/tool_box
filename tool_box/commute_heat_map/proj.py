import pyproj


class Point(object):
    """A geographical point."""

    def __init__(self, latitude: float, longitude: float):
        self.latitude = latitude
        self.longitude = longitude

    def __repr__(self):
        return f"Point(latitude={self.latitude}, longitude={self.longitude})"


class Proj(object):
    """Local Equidistant Conic (EQDC) projection centered on a given reference point.
    """

    def __init__(self, origin: Point):
        """Build a local EQDC projection centered on the reference point
        """
        self.proj_eqdc = pyproj.Proj(
            proj='eqdc',
            lat_0=origin.latitude,
            lon_0=origin.longitude,
            lat_1=origin.latitude - 2,
            lat_2=origin.latitude + 2,
            x_0=0,
            y_0=0,
            ellps='WGS84',
            units='m'
        )

    def to_xy(self, point: Point) -> tuple[float, float]:
        """Convert a geographical point to local EQDC coordinates (x, y)."""
        x, y = self.proj_eqdc(point.longitude, point.latitude)
        return x, y

    def to_latlon(self, x: float, y: float) -> Point:
        """Convert local EQDC coordinates (x, y) to a geographical point."""
        lon, lat = self.proj_eqdc(x, y, inverse=True)
        return Point(latitude=lat, longitude=lon)


if __name__ == "__main__":
    origin = Point(latitude=37.7749, longitude=-122.4194)  # San Francisco, CA
    proj = Proj(origin)
    assert proj.to_xy(origin) == (0.0, 0.0)

    point = Point(latitude=34.0522, longitude=-118.2437)  # Los Angeles, CA
    x, y = proj.to_xy(point)
    recovered_point = proj.to_latlon(x, y)
    assert abs(recovered_point.latitude - point.latitude) < 1e-6
    assert abs(recovered_point.longitude - point.longitude) < 1e-6
