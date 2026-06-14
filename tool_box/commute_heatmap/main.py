import argparse
import io
import os.path

import matplotlib.pyplot as plt
import numpy as np
from PIL import Image
from scipy.interpolate import griddata

from tool_box.commute_heatmap.proj import Proj
from tool_box.commute_heatmap.google_maps import GoogleMaps


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
        "--heatmap-array-path",
        type=str,
        default=os.path.join(os.path.dirname(__file__), "commute_heatmap.npy"),
        help="Path to save the heat map array (in .npy format)"
    )
    parser.add_argument(
        "--debug",
        action='store_true',
        help="Whether to show and save the intermediate images"
    )
    args = parser.parse_args(args)
    return args


def render_heatmap(heatmap: np.ndarray, args, debug=False) -> Image.Image:
    # Interpolate NaN values
    x = np.arange(heatmap.shape[1])
    y = np.arange(heatmap.shape[0])
    xx, yy = np.meshgrid(x, y)
    valid_mask = ~np.isnan(heatmap)
    heatmap = griddata(
        (xx[valid_mask], yy[valid_mask]),
        heatmap[valid_mask],
        (xx, yy),
        method='cubic',
    )
    # Convert to minutes
    heatmap = heatmap // 60

    # Visualize the heat map
    plt.imshow(
        heatmap,
        origin='lower',
        extent=(args.sw_point_x, args.ne_point_x, args.sw_point_y, args.ne_point_y),
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


def build_heatmap(gmaps, proj, args) -> np.ndarray:
    origin_point = gmaps.get_point(args.origin)

    # Build a grid of points covering the city bounds
    grid_x = np.arange(args.sw_point_x, args.ne_point_x + args.grid_size, args.grid_size)
    grid_y = np.arange(args.sw_point_y, args.ne_point_y + args.grid_size, args.grid_size)

    # Compute commute times for each point in the grid
    heatmap = np.full((len(grid_y), len(grid_x)), -1, dtype=float)
    for j, y in enumerate(grid_y):
        for i, x in enumerate(grid_x):
            grid_point = proj.to_latlon(x, y)
            try:
                travel_time = gmaps.get_commute_time(
                    origin=origin_point,
                    destination=grid_point,
                )
            except Exception as e:
                travel_time = np.nan
                print(f"WARNING: Could not compute commute time from {origin_point} to {grid_point}, due to: {e}")
            heatmap[j, i] = travel_time

    return heatmap


def main():
    args = get_args()
    gmaps = GoogleMaps.login(args.api_key_path)

    # Infer the city name from the origin address
    args.city = gmaps.get_city_name(args.origin)

    # Initialize the projection centered on the city
    city_point = gmaps.get_point(args.city)
    proj = Proj(city_point)

    # Get the city bounds to determine the area to cover with the heat map
    sw_point, ne_point = gmaps.get_bounds(args.city)
    args.sw_point_x, args.sw_point_y = proj.to_xy(sw_point)
    args.ne_point_x, args.ne_point_y = proj.to_xy(ne_point)

    # Get the heat map
    if os.path.exists(args.heatmap_array_path):
        print(f"Loading pre-computed heat map from {args.heatmap_array_path}...")
        heatmap = np.load(args.heatmap_array_path)
    else:
        print(f"Building heat map for {args.city} from {args.origin}...")
        heatmap = build_heatmap(gmaps, proj, args)
        np.save(args.heatmap_array_path, heatmap)
    heatmap_image = render_heatmap(heatmap, args, debug=args.debug)

    if args.debug:
        heatmap_image.save(os.path.join(os.path.dirname(__file__), 'commute_heatmap_debug.png'))
        heatmap_image.show()

    # Convert the city bounds to a center point and an area size (dx, dy)
    center_point = (sw_point + ne_point) / 2
    dx = args.ne_point_x - args.sw_point_x
    dy = args.ne_point_y - args.sw_point_y

    # Get the static map
    static_map = gmaps.render_static_map(center_point, dx, dy)

    if args.debug:
        static_map.save(os.path.join(os.path.dirname(__file__), 'static_map_debug.png'))
        static_map.show()

    static_map = static_map.resize(heatmap_image.size)

    # Overlay the heat map on the static map
    if not args.debug:
        final_image = Image.blend(
            static_map.convert("RGBA"),
            heatmap_image.convert("RGBA"),
            alpha=0.65
        )
        final_image.save(os.path.join(os.path.dirname(__file__), 'commute_heatmap_final.png'))


if __name__ == "__main__":
    # Test the heat map visualization
    args = get_args([
        "Gare de Lyon, Paris, France",
    ])
    args.city = "Paris"
    args.sw_point_x, args.sw_point_y = 0, 0
    args.ne_point_x, args.ne_point_y = 10000, 10000

    # Build a synthetic heat map
    heatmap = np.zeros((
        args.ne_point_y // args.grid_size + 1,
        args.ne_point_x // args.grid_size + 1
    ))
    # - radiating from an off-center point
    center_x, center_y = 20, 20
    for j in range(heatmap.shape[0]):
        for i in range(heatmap.shape[1]):
            distance = np.sqrt((i - center_x) ** 2 + (j - center_y) ** 2)
            heatmap[j, i] = distance * 10  # Commute time increases with distance
    # - with some noise
    heatmap += np.random.rand(*heatmap.shape) * 500
    # - add some random NaN values to simulate unreachable areas
    for _ in range(100):
        i = np.random.randint(0, heatmap.shape[1])
        j = np.random.randint(0, heatmap.shape[0])
        heatmap[j, i] = np.nan

    heatmap_image = render_heatmap(heatmap, args, debug=True)
    heatmap_image.show()
