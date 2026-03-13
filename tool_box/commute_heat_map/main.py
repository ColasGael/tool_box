import argparse
import io
import os.path

import matplotlib.pyplot as plt
import numpy as np
from PIL import Image
from scipy.interpolate import griddata

from tool_box.commute_heat_map.proj import Proj
from tool_box.commute_heat_map.google_maps import GoogleMaps


def get_args(args=None):
    parser = argparse.ArgumentParser(
        description="Compute the heat map of commute time in a given city from an origin position."
    )
    parser.add_argument(
        "origin",
        type=str,
        help="Origin address for the commute time calculation"
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
        default=100,
        help="Grid size (in m) for the heat map"
    )
    parser.add_argument(
        "--api-key-path",
        type=str,
        default=os.path.join(os.path.dirname(__file__), "api_key.txt"),
        help="Path to the API key file"
    )
    parser.add_argument(
        "--heat-map-array-path",
        type=str,
        default=os.path.join(os.path.dirname(__file__), "commute_heat_map.npy"),
        help="Path to save the heat map array (in .npy format)"
    )
    args = parser.parse_args(args)
    return args


def render_heat_map(heat_map: np.ndarray, args, debug=False) -> Image.Image:
    # Interpolate NaN values
    x = np.arange(heat_map.shape[1])
    y = np.arange(heat_map.shape[0])
    xx, yy = np.meshgrid(x, y)
    valid_mask = ~np.isnan(heat_map)
    heat_map = griddata(
        (xx[valid_mask], yy[valid_mask]),
        heat_map[valid_mask],
        (xx, yy),
        method='cubic',
    )
    # Convert to minutes
    heat_map = heat_map // 60

    # Visualize the heat map
    plt.imshow(
        heat_map,
        extent=(-args.radius, args.radius, -args.radius, args.radius),
        origin='lower',
        cmap='jet_r',  # gradient from red (short commute) to blue (long commute)
        interpolation='bicubic',  # smooth
    )

    # Adjust rendering
    save_kwargs = {}
    if debug:
        plt.colorbar(label='Commute Time (min)')
        plt.title(f'Commute Time Heat Map from {args.origin} in {args.city}')
        plt.xlabel('Distance East/West (m)')
        plt.ylabel('Distance North/South (m)')
    else:
        # Remove axes
        plt.axis('off')
        save_kwargs = {
            # Remove any whitespace padding around the image
            "bbox_inches": 'tight',
            "pad_inches": 0,
            # Save at a high resolution
            "dpi": 600,
        }

    buffer = io.BytesIO()
    plt.savefig(buffer, **save_kwargs)
    plt.clf()

    return Image.open(buffer)


def build_heat_map(gmaps, args) -> np.ndarray:
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
            try:
                travel_time = gmaps.get_commute_time(
                    origin=origin_point,
                    destination=grid_point,
                )
            except RuntimeError:
                travel_time = np.nan
            heat_map[j, i] = travel_time

    return heat_map


def main():
    args = get_args()
    gmaps = GoogleMaps.login(args.api_key_path)

    # Infer the city name from the origin address
    args.city = gmaps.get_city_name(args.origin)

    # Get the heat map
    if os.path.exists(args.heat_map_array_path):
        print(f"Loading pre-computed heat map from {args.heat_map_array_path}...")
        heat_map = np.load(args.heat_map_array_path)
    else:
        print(f"Building heat map for {args.city} from {args.origin}...")
        heat_map = build_heat_map(gmaps, args)
        np.save(args.heat_map_array_path, heat_map)
    heat_map_image = render_heat_map(heat_map, args)

    # Get the static map
    static_map = gmaps.render_static_map(args.city, args.radius)
    static_map = static_map.resize(heat_map_image.size)

    # Overlay the heat map on the static map
    final_image = Image.blend(
        static_map.convert("RGBA"),
        heat_map_image.convert("RGBA"),
        alpha=0.65
    )
    final_image.save(os.path.join(os.path.dirname(__file__), 'commute_heat_map_final.png'))


if __name__ == "__main__":
    # Test the heat map visualization
    args = get_args([
        "Gare de Lyon, Paris, France",
    ])
    args.city = "Paris"

    # Build a synthetic heat map
    n_points = args.radius * 2 // args.grid_size + 1
    # - radiating from an off-center point
    heat_map = np.zeros((n_points, n_points))
    center_x, center_y = 20, 20
    for j in range(n_points):
        for i in range(n_points):
            distance = np.sqrt((i - center_x) ** 2 + (j - center_y) ** 2)
            heat_map[j, i] = distance * 10  # Commute time increases with distance
    # - with some noise
    heat_map += np.random.rand(n_points, n_points) * 500
    # - add some random NaN values to simulate unreachable areas
    for _ in range(100):
        i = np.random.randint(0, n_points)
        j = np.random.randint(0, n_points)
        heat_map[j, i] = np.nan

    heat_map_image = render_heat_map(heat_map, args, debug=True)
    heat_map_image.show()
