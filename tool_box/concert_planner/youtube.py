import json
import os.path
from typing import Optional

from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials

import googleapiclient.discovery
import googleapiclient.errors


class Youtube(object):
    """Wrapper around the YouTube Data API.

    Reference: https://developers.google.com/youtube/v3
    """

    YOUTUBE_API_SERVICE_NAME = "youtube"
    YOUTUBE_API_VERSION = "v3"
    YOUTUBE_API_SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]

    TOKEN_FILE = os.path.join(os.path.dirname(__file__), "youtube_token.json")

    def __init__(self, client):
        self.client = client

    @classmethod
    def login(cls, client_secrets_file: str):
        """Authenticate and return a YouTube API client.

        Args:
            client_secrets_file (str): Path to the client secrets JSON file.

        Returns:
            googleapiclient.discovery.Resource: Authenticated YouTube API client.
        """
        def create_new_credentials():
            flow = InstalledAppFlow.from_client_secrets_file(client_secrets_file, cls.YOUTUBE_API_SCOPES)
            credentials = flow.run_local_server(port=0, open_browser=False)
            # Save the credentials for the next run
            with open(cls.TOKEN_FILE, 'w') as token_file:
                token_file.write(credentials.to_json())
            return credentials

        credentials = None
        if os.path.exists(cls.TOKEN_FILE):
            # Load the cached credentials
            with open(cls.TOKEN_FILE, 'r') as token_file:
                token = json.load(token_file)
                credentials = Credentials.from_authorized_user_info(token, cls.YOUTUBE_API_SCOPES)

        if not credentials or not credentials.valid:
            credentials = create_new_credentials()
        elif not credentials.valid:
            if credentials.expired and credentials.refresh_token:
                # Refresh the credentials if they are expired
                credentials.refresh(Request())
            else:
                # Credentials cannot be refreshed, create new ones
                credentials = create_new_credentials()
        youtube = googleapiclient.discovery.build(
            cls.YOUTUBE_API_SERVICE_NAME, cls.YOUTUBE_API_VERSION, credentials=credentials)
        return cls(youtube)

    def get_video_infos(self, video_id: str, info_names: dict) -> dict:
        """Get specific information about a YouTube video.

        Args:
            video_id (str): ID of the YouTube video.
            info_names (dict): Dictionary mapping part names to lists of info names to retrieve.

        Returns:
            dict: The requested information about the video.
        """
        video_request = self.client.videos().list(
            id=video_id,
            part=",".join(info_names.keys()),
        )
        video_response = video_request.execute()
        items = video_response.get("items", [])
        if not items:
            raise ValueError(f"Video with ID {video_id} not found.")
        video = items[0]
        infos = {}
        for part_name, info_names in info_names.items():
            if part_name not in video:
                raise ValueError(f"Part '{part_name}' not found in video data: {video}")
            part_info = video[part_name]
            for info_name in info_names:
                if info_name not in part_info:
                    raise ValueError(f"Info '{info_name}' not found in part '{part_name}': {part_info}")
                info = part_info[info_name]
                if info_name == "duration":
                    info = self._parse_video_duration(info)
                infos[info_name] = info
        return infos

    def _parse_video_duration(self, duration: str) -> int:
        """Get the duration of a YouTube video in seconds.

        Args:
            video_id (str): ID of the YouTube video.

        Returns:
            int: Duration of the video in seconds.
        """
        duration = duration.replace('PT', '')
        hours = minutes = seconds = 0
        if 'H' in duration:
            hours = int(duration.split('H')[0])
            duration = duration.split('H')[1]
        if 'M' in duration:
            minutes = int(duration.split('M')[0])
            duration = duration.split('M')[1]
        if 'S' in duration:
            seconds = int(duration.split('S')[0])
        total_seconds = hours * 3600 + minutes * 60 + seconds
        return total_seconds

    def search(self, **kwargs) -> Optional[str]:
        """Search YouTube for a given query.

        Args:
            **kwargs: Search parameters.

        Default search parameters:
            type (str, default: "video"): Type of resource to search for.
            maxResults (int, default: 1): Maximum number of results to return.

        Returns:
            str: The ID of the found resource, or None if not found.
        """
        resource_type = kwargs.pop("type", "video")
        request = self.client.search().list(
            part="snippet",
            type=resource_type,
            maxResults=kwargs.pop("maxResults", 1),
            **kwargs
        )
        response = request.execute()
        items = response.get("items", [])
        if items:
            return items[0]["id"][f"{resource_type}Id"]
        else:
            print(f"No resource found for query: {kwargs}")
            return None

    def find_artist_channel(self, artist_name: str) -> Optional[str]:
        """Find a YouTube channel for a given artist.

        Args:
            artist_name (str): Name of the artist.

        Returns:
            str: The ID of the artist's channel, or None if not found.
        """
        return self.search(type="channel", q=artist_name)

    def find_channel_most_popular_video(self, channel_id: str) -> Optional[str]:
        """Find the most popular video from a given channel.

        Args:
            channel_id (str): ID of the YouTube channel.

        Returns:
            str: The ID of the most popular video found, or None if not found.
        """
        return self.search(channelId=channel_id, order="viewCount")

    def find_playlist_by_title(self, title: str) -> Optional[str]:
        """Find a playlist by its title.

        Args:
            title (str): Title of the playlist to find.

        Returns:
            str: The ID of the found playlist, or None if not found.
        """
        request = self.client.playlists().list(
            part="snippet",
            mine=True,
            maxResults=50
        )
        response = request.execute()
        items = response.get("items", [])
        for item in items:
            if item["snippet"]["title"] == title:
                return item["id"]
        print(f"No playlist found with title: {title}")
        return None

    def delete_playlist(self, playlist_id: str) -> dict:
        """Delete a YouTube playlist by its ID.

        Args:
            playlist_id (str): ID of the playlist to delete.

        Returns:
            dict: The API response for the playlist deletion.
        """

        request = self.client.playlists().delete(
            id=playlist_id
        )
        response = request.execute()
        print(f"Deleted playlist {playlist_id}")
        return response

    def create_playlist(self, title: str, description: str, private: bool = True) -> str:
        """Create a YouTube playlist and return its ID.

        Args:
            title (str): Title of the playlist.
            description (str): Description of the playlist.
            private (bool): Whether the playlist is private. Defaults to True.

        Returns:
            str: The ID of the created playlist.
        """
        if private:
            privacy_status = "private"
        else:
            privacy_status = "public"
        request = self.client.playlists().insert(
            part="snippet,status",
            body={
                "snippet": {
                    "title": title,
                    "description": description
                },
                "status": {
                    "privacyStatus": privacy_status
                }
            }
        )
        response = request.execute()
        return response["id"]

    def add_video_to_playlist(self, video_id: str, playlist_id: str) -> dict:
        """Add a video to a YouTube playlist.

        Args:
            video_id (str): ID of the video to add.
            playlist_id (str): ID of the playlist to add the video to.

        Returns:
            dict: The API response for the playlist item insertion.
        """
        request = self.client.playlistItems().insert(
            part="snippet",
            body={
                "snippet": {
                    "playlistId": playlist_id,
                    "resourceId": {
                        "kind": "youtube#video",
                        "videoId": video_id
                    }
                }
            }
        )
        response = request.execute()
        return response
