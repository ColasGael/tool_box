import datetime
import os.path
import requests


class TicketMaster(object):
    """Wrapper around the TicketMaster API.

    Reference: https://developer.ticketmaster.com/products-and-docs/apis/discovery-api/v2/
    """

    BASE_URL = "https://app.ticketmaster.com/discovery/v2/"

    TOKEN_FILE = os.path.join(os.path.dirname(__file__), "ticketmaster_token.txt")


    def __init__(self, api_key):
        self.api_key = api_key

    @classmethod
    def login(cls):
        """Authenticate and return a TicketMaster API client.

        Returns:
            TicketMaster: Authenticated TicketMaster API client.
        """
        api_key = None
        if os.path.exists(cls.TOKEN_FILE):
            with open(cls.TOKEN_FILE, 'r') as token_file:
                api_key = token_file.read().strip()
        if not api_key:
            raise ValueError(f"TicketMaster API key not found. Please save it to {cls.TOKEN_FILE}")
        return cls(api_key)

    def build_url(self, endpoint: str, params: dict) -> str:
        """Build the full URL for a TicketMaster API request.

        Args:
            endpoint (str): API endpoint.
            params (dict): Query parameters.

        Returns:
            str: Full URL for the API request.
        """
        params["apikey"] = self.api_key
        query_string = "&".join([f"{key}={value}" for key, value in params.items()])
        return f"{self.BASE_URL}{endpoint}?{query_string}"

    def find_upcoming_artists(
            self, city: str, start_date: datetime.datetime, end_date: datetime.datetime,
            radius: int = 10, size: int = 200) -> list:
        """Find upcoming artists in a given city within a date range.

        Args:
            city (str): City to search for concerts.
            start_date (datetime.datetime): Start date for the search.
            end_date (datetime.datetime): End date for the search.
            radius (int, default: 10): Search radius in km.
            size (int, default: 200): Maximum number of results to return.

        Returns:
            list: List of upcoming concerts.
        """
        endpoint = "events.json"
        params = {
            "classificationName": "music",
            "city": city,
            "radius": radius,
            "unit": "km",
            "startDateTime": start_date.isoformat(timespec='seconds') + "Z",
            "endDateTime": end_date.isoformat(timespec='seconds') + "Z",
            "sort": "date,asc",
            "size": size,
        }
        url = self.build_url(endpoint, params)
        response = requests.get(url)
        if response.status_code != 200:
            raise RuntimeError(f"Error {response.status_code} fetching events from {url}:\n{response.text}")

        data = response.json()
        events = data.get("_embedded", {}).get("events", [])

        # Extract unique artists and their first concert date
        concerts = dict()
        for event in events:
            artists = event.get("_embedded", {}).get("attractions", [])
            if not artists:
                continue
            artist_name = artists[0]["name"]
            if artist_name in concerts:
                continue
            concert_date = event.get("dates", {}).get("start", {}).get("localDate")
            if not concert_date:
                continue
            concerts[artist_name] = concert_date

        # Sort the artists by concert date
        artists = sorted(concerts.keys(), key=lambda name: concerts[name])
        return artists
