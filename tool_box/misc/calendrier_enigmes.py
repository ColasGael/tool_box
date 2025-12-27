from argparse import ArgumentParser
import itertools
import os
import requests
from requests.auth import HTTPBasicAuth
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
import string

from pprint import pprint
import tqdm

BASE_URL = "https://www.tresoraparis.fr"

COOKIES = {
    "connexion-utap": "OFdPSiUyRjglMkJLZUQ5JTJCbU1vNUZmMHFDZyUzRCUzRDplcWJtc0gxNEF3N2s4VmdRTDJ3ZmRnJTNEJTNE",
}


def get_hint(hint, day, year=2024):
    # Specify the username and password
    username = 'gael.colas@free.fr'
    password = 'JUEU41GH'

    session = requests.Session()

    # Send a GET request with Basic Authentication
    response = session.get(f"{BASE_URL}/login", auth=HTTPBasicAuth(username, password))
    pprint(response)

    payload = {"aventCode": f"avent{year}", "dayNumber": day, "hintNumber": hint}
    response = session.post(f"{BASE_URL}/api/online/avent/hint", data=payload)

    return response


def download_image(url: str, outdir: str) -> None:
    image_name = os.path.basename(url)

    # Expand the user directory
    outpath = os.path.expanduser(os.path.join(outdir, image_name))

    # Create a session
    session = requests.Session()

    # Define a retry strategy
    retry_strategy = Retry(
        total=3,  # Total number of retries
        status_forcelist=[429, 500, 502, 503, 504],  # Retry on these status codes
        method_whitelist=["HEAD", "GET", "OPTIONS"],  # Retry for these HTTP methods
        backoff_factor=1  # Wait time between retries
    )

    # Mount the retry strategy to the session
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    # Send a GET request to the URL
    response = session.get(url)

    # Check if the request was successful
    if response.status_code == 200:
        # Open the local file in binary write mode
        with open(outpath, 'wb') as file:
            # Write the content of the response to the file
            file.write(response.content)
        # print(f"Image successfully downloaded: {outpath}")
        return True
    else:
        # print(f"Failed to download image {image_name}. Status code: {response.status_code}")
        return False


def find_image(day: int, outdir: str) -> str:
    base_url = "https://s3.eu-west-3.amazonaws.com/tresoraparis1/app/games-online/avent2024/enigmas"

    # Iterate over all possible 6-letter combinations
    for suffix in tqdm.tqdm(itertools.product(string.ascii_uppercase, repeat=6)):
        image_name = f"{day}-1-{suffix}.png"
        url = f"{base_url}/{image_name}"
        if download_image(url, outdir):
            return image_name

    raise ValueError("Image not found")


def get_args():
    parser = ArgumentParser(description="Attempt to hack the advent calendar")
    parser.add_argument("hint", type=int)
    parser.add_argument("day", type=int)
    parser.add_argument("--year", type=int, default=2024)
    parser.add_argument('--outdir', type=str, default="~/Downloads/", help='Directory to save the image')
    return parser.parse_args()


def main():
    args = get_args()
    hint = get_hint(args.hint, args.day, args.year)
    pprint(hint)
    # image_name = find_image(args.day, args.outdir)
    # print(f"Found image for day {args.day}: {image_name}")


if __name__ == "__main__":
    main()
