import argparse
from collections import Counter
import os.path

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFont
from scipy.cluster.vq import kmeans2
from scipy.ndimage import (label, find_objects, gaussian_filter, center_of_mass,
                           distance_transform_edt)
from skimage.color import rgb2lab, lab2rgb


def get_args(args=None):
    parser = argparse.ArgumentParser(
        description="Convert a color image into a paint-by-numbers template.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "input_image",
        type=str,
        help="Path to the input color image"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output path (default: paint_by_numbers.png next to script)"
    )
    parser.add_argument(
        "--n-colors",
        type=int,
        default=20,
        help="Number of colors to quantize to"
    )
    parser.add_argument(
        "--max-size",
        type=int,
        default=1024,
        help="Maximum dimension (width or height) of the working image"
    )
    parser.add_argument(
        "--min-region-size",
        type=float,
        default=0.0001,
        help="Minimum region size as a fraction of image area"
    )
    parser.add_argument(
        "--smooth",
        type=float,
        default=2.0,
        help="Gaussian sigma for smoothing region boundaries"
    )
    parser.add_argument(
        "--contrast",
        type=float,
        default=1.0,
        help="Contrast enhancement factor (1.0 = no change)"
    )
    parser.add_argument(
        "--saturation",
        type=float,
        default=1.5,
        help="Color saturation enhancement factor (1.0 = no change)"
    )
    parser.add_argument(
        "--font-size",
        type=float,
        default=0.01,
        help="Font size as a fraction of the output height"
    )
    parser.add_argument(
        "--scale",
        type=int,
        default=2,
        help="Integer upscale factor applied before rendering labels"
    )
    parser.add_argument(
        "--legend",
        type=str,
        default=None,
        help="Output path for the color legend image (default: legend.png next to script)"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Save intermediate images (quantized, edges)"
    )
    return parser.parse_args(args)


def quantize_colors(image, n_colors):
    """Quantize image colors using k-means clustering in CIELAB space.

    Clustering in LAB produces perceptually balanced palette entries.
    Centroids are converted back to uint8 RGB for the returned palette.

    Returns:
        labels: (H, W) int array mapping each pixel to a color index
        palette: (n_colors, 3) uint8 array of cluster center colors
    """
    H, W = image.shape[:2]
    pixels = image.reshape(-1, 3)

    # Clamp n_colors to the number of unique colors in the image
    unique_colors = len(np.unique(pixels, axis=0))
    n_colors = min(n_colors, unique_colors)

    pixels_lab = rgb2lab(pixels.reshape(1, -1, 3)).reshape(-1, 3)
    centroids_lab, labels = kmeans2(pixels_lab, n_colors, minit="++", iter=20, rng=42)

    palette = (lab2rgb(centroids_lab.reshape(1, -1, 3)).reshape(-1, 3) * 255).round().astype(np.uint8)
    return labels.reshape(H, W), palette


def merge_small_regions(labels, min_region_size):
    """Reassign connected components smaller than min_region_size to their most-contacted neighbor.

    Processes components from smallest to largest so merges cascade correctly.
    """
    labels = labels.copy()
    n_colors = int(labels.max()) + 1
    H, W = labels.shape

    # Build global component map (1-indexed; 0 = unused placeholder)
    comp_map = np.zeros((H, W), dtype=np.int32)
    comp_color = [0]  # comp_color[comp_id] = color_idx
    next_id = 1
    for color_idx in range(n_colors):
        lbl, num = label(labels == color_idx)
        for i in range(1, num + 1):
            comp_map[lbl == i] = next_id
            comp_color.append(color_idx)
            next_id += 1

    comp_color = np.array(comp_color, dtype=np.int32)
    sizes = np.bincount(comp_map.ravel(), minlength=next_id).astype(np.int64)
    sizes[0] = min_region_size  # prevent the placeholder from being processed

    # Bounding boxes for each component (find_objects result[i] = bbox of label i+1)
    bboxes = find_objects(comp_map)

    for sc in np.argsort(sizes):
        if sizes[sc] == 0 or sizes[sc] >= min_region_size:
            continue
        bbox = bboxes[sc - 1]
        if bbox is None:
            continue  # already merged away

        # Expand bbox by 1 to include immediate neighbors
        r0 = max(0, bbox[0].start - 1)
        r1 = min(H, bbox[0].stop + 1)
        c0 = max(0, bbox[1].start - 1)
        c1 = min(W, bbox[1].stop + 1)
        patch = comp_map[r0:r1, c0:c1]
        sc_mask = (patch == sc)

        # Adjacent pixels outside the component
        neighbor_mask = np.zeros_like(sc_mask)
        neighbor_mask[:-1, :] |= sc_mask[1:, :]
        neighbor_mask[1:, :] |= sc_mask[:-1, :]
        neighbor_mask[:, :-1] |= sc_mask[:, 1:]
        neighbor_mask[:, 1:] |= sc_mask[:, :-1]
        neighbor_mask &= ~sc_mask

        neighbor_ids = patch[neighbor_mask]
        neighbor_ids = neighbor_ids[neighbor_ids != sc]
        if len(neighbor_ids) == 0:
            continue

        best = int(np.argmax(np.bincount(neighbor_ids, minlength=next_id)))
        comp_map[r0:r1, c0:c1][sc_mask] = best
        labels[r0:r1, c0:c1][sc_mask] = comp_color[best]
        sizes[best] += sizes[sc]
        sizes[sc] = 0

    return labels


def smooth_labels(labels, sigma):
    """Smooth region boundaries by blurring per-color probability maps and taking argmax."""
    n_colors = int(labels.max()) + 1
    # Build one float map per color, blur each, then pick the dominant color per pixel
    maps = np.stack(
        [gaussian_filter((labels == i).astype(np.float32), sigma=sigma) for i in range(n_colors)],
        axis=0,
    )
    return np.argmax(maps, axis=0).astype(labels.dtype)


def detect_edges(labels):
    """Detect boundaries between differently-labeled regions.

    Returns:
        edge_mask: (H, W) bool array, True where a region boundary exists
    """
    edge_mask = np.zeros(labels.shape, dtype=bool)
    edge_mask[:-1, :] |= (labels[:-1, :] != labels[1:, :])   # top pixel of each horizontal boundary
    edge_mask[:, :-1] |= (labels[:, :-1] != labels[:, 1:])   # left pixel of each vertical boundary
    return edge_mask


def find_region_centroids(labels, n_colors, min_region_size):
    """Find the centroid of each connected region above the size threshold.

    Returns:
        regions: list of dicts {"color_idx", "comp_id", "centroid", "size"}
        comp_map: (H, W) int array mapping each pixel to its unique component ID (0 = none)
    """
    regions = []
    comp_map = np.zeros(labels.shape, dtype=np.int32)
    next_comp_id = 1

    for color_idx in range(n_colors):
        mask = (labels == color_idx)
        labeled_array, num_features = label(mask)
        if num_features == 0:
            continue

        bboxes = find_objects(labeled_array)
        for comp_idx, bbox in enumerate(bboxes, start=1):
            if bbox is None:
                continue
            patch = labeled_array[bbox] == comp_idx
            size = int(patch.sum())
            if size < min_region_size:
                continue

            # Register this component in the global map
            comp_id = next_comp_id
            next_comp_id += 1
            comp_map[bbox][patch] = comp_id

            cy, cx = center_of_mass(patch)
            row = int(round(cy)) + bbox[0].start
            col = int(round(cx)) + bbox[1].start
            # Snap to nearest component pixel if center of mass falls outside the region
            if not patch[row - bbox[0].start, col - bbox[1].start]:
                patch_rows, patch_cols = np.where(patch)
                dists = np.hypot(patch_rows - (row - bbox[0].start),
                                 patch_cols - (col - bbox[1].start))
                nearest = np.argmin(dists)
                row = int(patch_rows[nearest]) + bbox[0].start
                col = int(patch_cols[nearest]) + bbox[1].start
            regions.append({"color_idx": color_idx, "comp_id": comp_id,
                            "centroid": (row, col), "size": size})

    return regions, comp_map


def _find_label_position(comp_map, comp_id, centroid_row, centroid_col, tw, th):
    """Find the valid anchor position closest to the centroid where the text box fits.

    Uses the distance transform: a pixel is a valid center if its distance to the nearest
    non-region pixel is >= the half-diagonal of the text box.
    Falls back to the deepest interior point for regions too thin to fit the text.
    """
    region_mask = (comp_map == comp_id)
    edt = distance_transform_edt(region_mask)
    threshold = np.hypot(th / 2, tw / 2)
    valid = np.argwhere(edt >= threshold)
    if len(valid) > 0:
        dists = np.hypot(valid[:, 0] - centroid_row, valid[:, 1] - centroid_col)
        best = valid[np.argmin(dists)]
        return int(best[0]), int(best[1])
    # Region too thin to fit the text box: place at the deepest interior point
    best = np.unravel_index(np.argmax(edt), edt.shape)
    return int(best[0]), int(best[1])


def render_legend(palette, labels, regions, font_size):
    """Render a color legend mapping region numbers to their palette colors.

    Only includes colors that are actually present in the final label map.
    Uses a 2-column layout when there are more than 10 colors.
    """
    region_counts = Counter(r["color_idx"] for r in regions)

    used_colors = sorted(set(labels.ravel().tolist()))
    n = len(used_colors)

    swatch_w, swatch_h = 40, 20
    padding = 8
    text_gap = 6

    def label_text(color_idx):
        return f"{color_idx + 1} ({region_counts[color_idx]})"

    font = ImageFont.load_default(size=font_size)
    widest = max((label_text(c) for c in used_colors), key=len)
    tb = font.getbbox(widest)
    text_w = tb[2] - tb[0]
    text_h = tb[3] - tb[1]

    row_h = max(swatch_h, text_h) + padding
    col_w = padding + swatch_w + text_gap + text_w + padding

    total_text = f"Total: {len(regions)} regions"
    total_tb = font.getbbox(total_text)
    total_h = total_tb[3] - total_tb[1]

    n_cols = 2 if n > 10 else 1
    n_rows = (n + n_cols - 1) // n_cols

    W = max(col_w * n_cols + padding, total_tb[2] - total_tb[0] + 2 * padding)
    H = padding + n_rows * row_h + padding + total_h + padding

    img = Image.new("RGB", (W, H), (255, 255, 255))
    draw = ImageDraw.Draw(img)

    for i, color_idx in enumerate(used_colors):
        col = i // n_rows
        row = i % n_rows
        x = padding + col * col_w
        y = padding + row * row_h

        color = tuple(int(c) for c in palette[color_idx])
        draw.rectangle([x, y, x + swatch_w - 1, y + swatch_h - 1], fill=color, outline=(0, 0, 0))
        draw.text(
            (x + swatch_w + text_gap, y + swatch_h // 2),
            label_text(color_idx),
            fill=(0, 0, 0),
            font=font,
            anchor="lm",
        )

    total_y = padding + n_rows * row_h + padding
    draw.line([(padding, total_y - padding // 2), (W - padding, total_y - padding // 2)], fill=(200, 200, 200))
    draw.text((padding, total_y), total_text, fill=(0, 0, 0), font=font, anchor="la")

    return img


def render_paint_by_number(image_shape, edge_mask, regions, comp_map, font_size):
    """Render a white canvas with black region outlines and numbered labels.

    Returns:
        PIL Image (RGB)
    """
    H, W = image_shape[:2]
    canvas_arr = np.full((H, W, 3), 255, dtype=np.uint8)
    canvas_arr[edge_mask] = [180, 180, 180]
    canvas = Image.fromarray(canvas_arr)
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default(size=font_size)

    # Draw labels largest-region-first so small regions aren't hidden
    for region in sorted(regions, key=lambda r: r["size"], reverse=True):
        centroid_row, centroid_col = region["centroid"]
        text = str(region["color_idx"] + 1)  # 1-indexed
        tb = font.getbbox(text)
        tw, th = tb[2] - tb[0], tb[3] - tb[1]
        row, col = _find_label_position(
            comp_map, region["comp_id"], centroid_row, centroid_col, tw, th
        )
        draw.text((col, row), text, fill=(80, 80, 80), font=font, anchor="mm")

    return canvas


def render_quantized(labels, palette):
    """Render the flat-color quantized image (for debug)."""
    return Image.fromarray(palette[labels].astype(np.uint8))


def main():
    args = get_args()

    output_dir = os.path.dirname(__file__)
    if args.output is None:
        args.output = os.path.join(output_dir, "paint_by_numbers.png")
    if args.legend is None:
        args.legend = os.path.join(output_dir, "legend.png")

    print(f"Loading image from {args.input_image}...")
    pil_image = Image.open(args.input_image).convert("RGB")
    W, H = pil_image.size
    if max(W, H) > args.max_size:
        scale = args.max_size / max(W, H)
        pil_image = pil_image.resize((int(W * scale), int(H * scale)), Image.LANCZOS)
        print(f"Resized to {pil_image.size[0]}x{pil_image.size[1]}")

    print("Enhancing contrast and saturation...")
    pil_image = ImageEnhance.Contrast(pil_image).enhance(args.contrast)
    pil_image = ImageEnhance.Color(pil_image).enhance(args.saturation)
    image = np.array(pil_image)

    print(f"Quantizing to {args.n_colors} colors...")
    labels, palette = quantize_colors(image, args.n_colors)

    H_img, W_img = image.shape[:2]
    min_region_px = max(1, int(args.min_region_size * H_img * W_img))
    print(f"Min region size: {min_region_px}px ({args.min_region_size*100:.2f}% of {W_img}x{H_img})")

    print("Merging small regions...")
    labels = merge_small_regions(labels, min_region_px)

    print("Smoothing region boundaries...")
    labels = smooth_labels(labels, args.smooth)

    print("Merging small regions (post-smooth)...")
    labels = merge_small_regions(labels, min_region_px)

    used_colors = set(labels.ravel().tolist())
    unused_colors = set(range(len(palette))) - used_colors
    if unused_colors:
        print(f"Dropped {len(unused_colors)} unused color(s): {sorted(c + 1 for c in unused_colors)}")
    print(f"Final colors used: {len(used_colors)}")

    if args.debug:
        debug_path = os.path.join(output_dir, "debug_quantized.png")
        quantized_img = render_quantized(labels, palette)
        quantized_img.save(debug_path)
        print(f"Saved quantized image to {debug_path}")
        quantized_img.show()

    print("Finding region centroids...")
    regions, comp_map = find_region_centroids(labels, labels.max() + 1, min_region_px)
    print(f"Found {len(regions)} regions above {min_region_px} pixels")

    if args.scale > 1:
        s = args.scale
        print(f"Upscaling {s}x before rendering...")
        labels = np.kron(labels, np.ones((s, s), dtype=labels.dtype))
        comp_map = np.kron(comp_map, np.ones((s, s), dtype=np.int32))
        regions = [
            {**r, "centroid": (r["centroid"][0] * s, r["centroid"][1] * s)}
            for r in regions
        ]
        render_shape = (image.shape[0] * s, image.shape[1] * s)
    else:
        render_shape = image.shape

    # Re-smooth at output resolution to anti-alias the upscaled staircase edges
    labels = smooth_labels(labels, sigma=1.0)

    print("Detecting region edges...")
    edge_mask = detect_edges(labels)

    if args.debug:
        debug_path = os.path.join(output_dir, "debug_edges.png")
        Image.fromarray((edge_mask * 255).astype(np.uint8), mode="L").save(debug_path)
        print(f"Saved edge mask to {debug_path}")

    font_size_px = max(8, int(args.font_size * render_shape[0]))
    print(f"Font size: {font_size_px}px ({args.font_size*100:.1f}% of {render_shape[0]}px height)")

    print("Rendering color legend...")
    legend = render_legend(palette, labels, regions, font_size_px)
    legend.save(args.legend)
    print(f"Saved color legend to {args.legend}")

    print("Rendering paint-by-numbers image...")
    result = render_paint_by_number(render_shape, edge_mask, regions, comp_map, font_size_px)
    result.save(args.output)
    print(f"Saved paint-by-numbers image to {args.output}")


if __name__ == "__main__":
    main()
