import io
import math
import os.path
import requests

from PIL import Image

from tool_box.commute_heat_map.proj import Point

class GoogleMaps(object):
    """Wrapper around the GoogleMap APIs.

    References:
    - Geocoding API: https://developers.google.com/maps/documentation/geocoding
    - Routes API: https://developers.google.com/maps/documentation/routes
    - Static Maps API: https://developers.google.com/maps/documentation/maps-static
    """

    GEOCODING_API_URL = "https://maps.googleapis.com/maps/api/geocode/json"

    ROUTES_API_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"
    DURATION_FIELD = "staticDuration"

    MAPS_STATIC_API_URL = "https://maps.googleapis.com/maps/api/staticmap"
    STATIC_MAP_PIXEL_SIZE = 640  # Max size for free tier is 640x640

    def __init__(self, api_key: str):
        self.api_key = api_key

    @classmethod
    def login(cls, api_key_path: str):
        with open(api_key_path, 'r') as f:
            api_key = f.read().strip()
        return cls(api_key)

    def _geocode(self, address: str) -> dict:
        params = {
            "address": address,
            "key": self.api_key,
        }
        response = requests.get(self.GEOCODING_API_URL, params=params)

        data = response.json()
        if data["status"] != "OK" or not data["results"]:
            raise RuntimeError(
                f"Error geocoding address '{address}', with status : {data['status']}")

        return data["results"][0]

    def get_city_name(self, address: str) -> str:
        """Infer the city name from an address using the geocoding API.

        Args:
            address (str): The address to infer the city name from.

        Returns:
            str: The inferred city name.
        """
        result = self._geocode(address)

        for component in result["address_components"]:
            if "locality" in component["types"]:
                return component["long_name"]

        raise RuntimeError(f"Could not infer city name from address '{address}'")

    def get_point(self, address: str) -> Point:
        """Geocode an address into a geographical point.

        Args:
            address (str): The address to geocode.

        Returns:
            Point: The geographical point corresponding to the address.
        """
        result = self._geocode(address)
        location = result["geometry"]["location"]
        point = Point(latitude=location["lat"], longitude=location["lng"])
        return point

    def get_bounds(self, address: str) -> tuple[Point, Point]:
        """Get the bounding box of an address.

        Args:
            address (str): The address to geocode.

        Returns:
            tuple(Point, Point): The southwest and northeast corners of the bounding box.
        """
        result = self._geocode(address)
        bounds = result["geometry"]["bounds"]
        southwest = bounds["southwest"]
        northeast = bounds["northeast"]
        sw_point = Point(latitude=southwest["lat"], longitude=southwest["lng"])
        ne_point = Point(latitude=northeast["lat"], longitude=northeast["lng"])
        return sw_point, ne_point

    def get_travel_time(self, origin: Point | str, destination: Point | str, travel_mode: str) -> int:
        """Compute travel time between two locations using the specified travel mode.

        Args:
            origin: The starting location.
            destination: The destination location.

        Returns:
            int: Commute time (in s)
        """
        if isinstance(origin, str):
            origin = self.get_point(origin)
        if isinstance(destination, str):
            destination = self.get_point(destination)

        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": f"routes.{self.DURATION_FIELD}",
        }
        body = {
            "origin": {"location": {"latLng": vars(origin)}},
            "destination": {"location": {"latLng": vars(destination)}},
            "travelMode": travel_mode,
        }
        response = requests.post(self.ROUTES_API_URL, headers=headers, json=body)

        data = response.json()
        if "routes" not in data or not data["routes"]:
            raise RuntimeError(
                f"Error computing {travel_mode} route between {origin} and {destination}: \n"
                f"{data.get('error', 'UNKNOWN ERROR')}")

        route = data["routes"][0]
        duration_value = route[self.DURATION_FIELD]
        if not duration_value.endswith("s"):
            raise RuntimeError(f"Unexpected duration format: {duration_value}")

        duration = int(duration_value[:-1])
        return duration

    def get_commute_time(self, origin: Point | str, destination: Point | str) -> int:
        return self.get_travel_time(origin, destination, travel_mode="TRANSIT")

    def render_static_map(self, center: Point | str, dx: int, dy: int)-> Image.Image:
        """Build a static map centered on the specified location and covering the specified radius.

        Args:
            center: The center of the map (address or "lat,lng").
            dx: The width of the area to cover (in meters).
            dy: The height of the area to cover (in meters).

        Returns:
            Image.Image: The cropped static map image covering the specified area.

        Documentation:
        - Styles: https://developers.google.com/maps/documentation/maps-static/styling
        """
        if isinstance(center, str):
            center = self.get_point(center)

        def meters_per_pixel(zoom: int) -> float:
            return 156543.03392 * math.cos(center.latitude * math.pi / 180) / (2 ** zoom)

        # Find the zoom level that covers slightly more than the area of interest
        image_length = max(dx, dy) + 1 # m
        zoom = 0
        while image_length > max(dx, dy):
            zoom += 1
            image_length = meters_per_pixel(zoom) * self.STATIC_MAP_PIXEL_SIZE
        # Decrease the zoom to ensure we cover the whole area of interest
        zoom -= 1

        # Query the static map API
        params = [
            ("key", self.api_key),
            ("format", "png"),
            ("center", f"{center.latitude},{center.longitude}"),
            ("zoom", zoom),
            ("size", f"{self.STATIC_MAP_PIXEL_SIZE}x{self.STATIC_MAP_PIXEL_SIZE}"),
            ("maptype", "roadmap"),
            # - Hide all labels
            ("style", "feature:all|element:labels|visibility:off"),
            # - Hide administrative boundaries (e.g. city borders)
            ("style", "feature:administrative|visibility:off"),
        ]
        response = requests.get(self.MAPS_STATIC_API_URL, params=params)
        if response.status_code != 200:
            raise RuntimeError(f"Error querying static map API: {response.text}")

        static_map = Image.open(io.BytesIO(response.content))

        # Crop it to the desired area
        crop_pixel_size_x = int(dx / meters_per_pixel(zoom))
        crop_pixel_size_y = int(dy / meters_per_pixel(zoom))
        left = (static_map.width - crop_pixel_size_x) // 2
        upper = (static_map.height - crop_pixel_size_y) // 2
        right = left + crop_pixel_size_x
        lower = upper + crop_pixel_size_y
        cropped_map = static_map.crop((left, upper, right, lower))

        return cropped_map


if __name__ == "__main__":
    maps = GoogleMaps.login(os.path.join(os.path.dirname(__file__), "api_key.txt"))

    origin = Point(48.8443, 2.3744)  # Gare de Lyon
    destination = Point(48.8418, 2.3213)  # Gare Montparnasse
    commute_time_gps = maps.get_commute_time(origin, destination)
    print(f"Commute time from {origin} to {destination} is {commute_time_gps} seconds.")

    origin = "Gare de Lyon, Paris, France"
    destination = "Gare Montparnasse, Paris, France"
    commute_time_address = maps.get_commute_time(origin, destination)
    print(f"Commute time from '{origin}' to '{destination}' is {commute_time_address} seconds.")

    city = maps.get_city_name(origin)
    print(f"The city name inferred from '{origin}' is '{city}'.")
