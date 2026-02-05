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
    - Geocoding API: https://developers.google.com/maps/documentation/geocoding
    - Routes API: https://developers.google.com/maps/documentation/routes
    """

    GEOCODING_API_URL = "https://maps.googleapis.com/maps/api/geocode/json"

    ROUTES_API_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"
    DURATION_FIELD = "staticDuration"

    def __init__(self, api_key: str):
        self.api_key = api_key

    @classmethod
    def login(cls, api_key_path: str):
        with open(api_key_path, 'r') as f:
            api_key = f.read().strip()
        return cls(api_key)

    def get_point(self, address: str) -> Point:
        """Geocode an address into a geographical point.

        Args:
            address (str): The address to geocode.

        Returns:
            Point: The geographical point corresponding to the address.
        """
        params = {
            "address": address,
            "key": self.api_key,
        }
        response = requests.get(self.GEOCODING_API_URL, params=params)

        data = response.json()
        if data["status"] != "OK" or not data["results"]:
            raise RuntimeError(
                f"Error geocoding address '{address}', with status : {data['status']}")

        location = data["results"][0]["geometry"]["location"]
        point = Point(latitude=location["lat"], longitude=location["lng"])
        return point

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
