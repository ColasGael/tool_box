import os.path
import requests


class Point(object):
    """A geographical point."""

    def __init__(self, latitude: float, longitude: float):
        self.latitude = latitude
        self.longitude = longitude

    def __repr__(self):
        return f"Point(latitude={self.latitude}, longitude={self.longitude})"


class GoogleMaps(object):
    """Wrapper around the GoogleMap APIs.

    References:
    - Routes API: https://developers.google.com/maps/documentation/routes
    """

    ROUTES_API_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"
    DURATION_FIELD = "staticDuration"

    def __init__(self, api_key: str):
        self.api_key = api_key

    @classmethod
    def login(cls, api_key_path: str):
        with open(api_key_path, 'r') as f:
            api_key = f.read().strip()
        return cls(api_key)

    def get_travel_time(self, origin: Point, destination: Point, travel_mode: str) -> int:
        """Compute travel time between two locations using the specified travel mode.

        Args:
            origin (str): The starting location.
            destination (str): The destination location.

        Returns:
            int: Commute time (in s)
        """
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

    def get_commute_time(self, origin: Point, destination: Point) -> int:
        return self.get_travel_time(origin, destination, travel_mode="TRANSIT")


if __name__ == "__main__":
    # origin = "Gare de Lyon, Paris, France"
    origin = Point(48.844294, 2.373084)  # Gare de Lyon
    # destination = "Gare Montparnasse, Paris, France"
    destination = Point(48.840047, 2.320873)  # Gare Montparnasse

    maps = GoogleMaps.login(os.path.join(os.path.dirname(__file__), "api_key.txt"))
    commute_time = maps.get_commute_time(origin, destination)
    print(f"Commute time from {origin} to {destination} is {commute_time} seconds.")
