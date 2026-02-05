import argparse
import os.path

import matplotlib.pyplot as plt
import numpy as np

from tool_box.commute_heat_map.proj import Proj
from tool_box.commute_heat_map.google_maps import GoogleMaps


def get_args():
    parser = argparse.ArgumentParser(
        description="Compute the heat map of commute time in a given city from an origin position."
    )
    parser.add_argument(
        "origin",
        type=str,
        help="Origin address for the commute time calculation"
    )
    parser.add_argument(
        "city",
        type=str,
        help="City to build the heat map for"
    )
    parser.add_argument(
        "--radius",
        type=float,
        default=5000,
        help="Radius (in m) around the city center to consider for the heat map"
    )
    parser.add_argument(
        "--grid-size",
        type=float,
        default=500,
        help="Grid size (in m) for the heat map"
    )
    parser.add_argument(
        "--api-key-path",
        type=str,
        default=os.path.join(os.path.dirname(__file__), "api_key.txt"),
        help="Path to the API key file"
    )
    args = parser.parse_args()
    return args


def main():
    args = get_args()

    gmaps = GoogleMaps.login(args.api_key_path)

    origin_point = gmaps.get_point(args.origin)
    city_point = gmaps.get_point(args.city)

    proj = Proj(city_point)

    # Build a grid of points around the city center
    grid_x = np.arange(-args.radius, args.radius + args.grid_size, args.grid_size)
    grid_y = np.arange(-args.radius, args.radius + args.grid_size, args.grid_size)

    # Compute commute times for each point in the grid
    heat_map = np.full((len(grid_y), len(grid_x)), -1, dtype=int)
    for j, y in enumerate(grid_y):
        for i, x in enumerate(grid_x):
            grid_point = proj.to_latlon(x, y)
            travel_time = gmaps.get_commute_time(
                origin=origin_point,
                destination=grid_point,
            )
            heat_map[j, i] = travel_time

    # Plot the heat map
    print("Heat map of commute times (in seconds):")
    plt.imshow(heat_map, extent=(-args.radius, args.radius, -args.radius, args.radius), origin='lower', cmap='hot', interpolation='nearest')
    plt.colorbar(label='Commute Time (s)')
    plt.title(f'Commute Time Heat Map from {args.origin} in {args.city}')
    plt.xlabel('Distance East/West (m)')
    plt.ylabel('Distance North/South (m)')
    plt.savefig('commute_heat_map.png')


if __name__ == "__main__":
    main()
