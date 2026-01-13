import argparse
import datetime
import heapq
import os.path
import requests
from typing import Optional

from tool_box.concert_planner.ticketmaster import TicketMaster
from tool_box.concert_planner.youtube import Youtube


def get_city() -> Optional[str]:
    try:
        response = requests.get("https://ipinfo.io/json")
        data = response.json()
        city = data.get("city", None)
        return city
    except Exception as e:
        print(f"Error determining city: {e}")
        return None


def get_args():
    parser = argparse.ArgumentParser(description="Build a YouTube playlist of upcoming concerts in your city.")
    parser.add_argument(
        "--city",
        type=str,
        help="City to search for upcoming concerts (default: where this script is run from)"
    )
    parser.add_argument(
        "--months-ahead",
        type=int,
        default=3,
        help="Number of months ahead to look for concerts"
    )
    parser.add_argument(
        "--client-secrets",
        type=str,
        default=os.path.join(os.path.dirname(__file__), "client_secret.json"),
        help="Path to client secrets JSON file"
    )
    parser.add_argument(
        "--playlist-title",
        type=str,
        default="Upcoming Concerts",
        help="Title of the YouTube playlist to create"
    )
    parser.add_argument(
        "--max-videos",
        type=int,
        default=50,
        help="Maximum number of videos to add to the playlist"
    )
    args = parser.parse_args()

    # Infer the city
    if not args.city:
        args.city = get_city()
        if not args.city:
            raise ValueError("City could not be determined. Please provide a city using the --city argument.")

    return args


def find_concerts_ticketmaster(city, months_ahead):
    ticketmaster = TicketMaster.login()
    # Cover the entire month, months_ahead months from now
    this_month = datetime.datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    start_date = this_month.replace(month=this_month.month + months_ahead)
    end_date = this_month.replace(month=this_month.month + months_ahead + 1)
    return ticketmaster.find_upcoming_artists(city, start_date, end_date)


def build_playlist(client_secrets, playlist_title, city, months_ahead, artists, max_videos):
    """Create a YouTube playlist of the most popular songs from upcoming concerts in a given city.

    Args:
        client_secrets (str): Path to the YouTube client secrets JSON file.
        playlist_title (str): Title of the YouTube playlist to create.
        city (str): City to search for upcoming concerts.
        months_ahead (int): Number of months ahead to look for concerts.
        artists (list of str): List of artist names with upcoming concerts.
        max_videos (int): Maximum number of videos to add to the playlist. If -1, add all found videos.

    Notes:
        - The playlist will contain the most popular song from each artist, sorted by view count.
        - Videos longer than 15 minutes are skipped.
    """

    youtube = Youtube.login(client_secrets)
    # Songs sorted by view count
    songs = []
    for artist in artists:
        # Find the artist most popular song
        artist_id = youtube.find_artist_channel(artist)
        if not artist_id:
            continue
        video_id = youtube.find_channel_most_popular_video(artist_id)
        if not video_id:
            continue
        # Get metrics about the video
        info_names = {
            "contentDetails": ["duration"],
            "statistics": ["viewCount"],
        }
        video_infos = youtube.get_video_infos(video_id, info_names)
        # Filter out long videos (>15 minutes)
        video_duration = video_infos["duration"]
        if video_duration > 15 * 60:
            print(f"Skipping {artist} video {video_id} due to long duration ({video_duration} seconds).")
            continue
        # Sort by view count
        view_count = int(video_infos["viewCount"])
        heapq.heappush(songs, (-view_count, video_id))
    # Delete the previous month's playlist
    existing_playlist_id = youtube.find_playlist_by_title(playlist_title)
    if existing_playlist_id:
        youtube.delete_playlist(existing_playlist_id)
    # Create a new playlist
    playlist_id = youtube.create_playlist(
        title=playlist_title,
        description=f"Upcoming concerts in {city} for the next {months_ahead} months.",
    )
    # Add the top max_videos songs to the playlist
    # NOTE: the playlist will be sorted by decreasing number of views
    playlist_idx = 0
    while songs and (max_videos == -1 or playlist_idx < max_videos):
        _, video_id = heapq.heappop(songs)
        print(f"Adding video {video_id} to playlist ({playlist_idx}/{max_videos}).")
        youtube.add_video_to_playlist(video_id, playlist_id)
        playlist_idx += 1


def main():
    args = get_args()
    artists = find_concerts_ticketmaster(args.city, args.months_ahead)
    print(f"Found {len(artists)} upcoming artists in {args.city}: {artists}")
    build_playlist(
        args.client_secrets, args.playlist_title, args.city, args.months_ahead, artists, args.max_videos)


if __name__ == "__main__":
    main()
