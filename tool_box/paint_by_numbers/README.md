# paint_by_numbers

Converts a color image into a paint-by-numbers template: flat color regions with black outlines and numbered labels.

## Usage

```bash
paint-by-numbers <input_image> [options]
```

### Arguments

| Argument | Default | Description |
|---|---|---|
| `input_image` | - | Path to the input color image (JPEG, PNG, HEIC, ...) |
| `--output` | `paint_by_numbers.png` next to script | Output path for the paint-by-numbers image |
| `--legend` | `legend.png` next to script | Output path for the color legend image |
| `--max-size` | 1024 | Maximum dimension (px) before processing; preserves aspect ratio |
| `--n-colors` | 20 | Number of colors to quantize to |
| `--min-region-size` | 0.0001 | Minimum region size as a fraction of image area -- smaller regions are merged into neighbors |
| `--smooth` | 2.0 | Gaussian sigma for smoothing region boundaries |
| `--contrast` | 1.0 | Contrast enhancement factor (1.0 = no change) |
| `--saturation` | 1.5 | Color saturation enhancement factor (1.0 = no change) |
| `--scale` | 2 | Integer upscale factor applied to the working image before rendering |
| `--font-size` | 0.01 | Font size for region labels as a fraction of the output height |
| `--debug` | off | Save intermediate images (`debug_quantized.png`, `debug_edges.png`) |

## Install

```bash
pip install -e ".[paint-by-numbers]"
```

## Pipeline

1. **Load & resize** -- image is downscaled so its longest side <= `--max-size`
2. **Enhance** -- contrast and saturation adjusted via `PIL.ImageEnhance`
3. **Quantize** -- k-means++ (`scipy.cluster.vq.kmeans2`) reduces to `--n-colors` flat colors
4. **Merge small regions** -- connected components below `--min-region-size` x image area are absorbed by their most-contacted neighbor
5. **Smooth boundaries** -- per-color probability maps are Gaussian-blurred; argmax gives smooth region edges
6. **Merge small regions** (second pass) -- cleans up tiny regions reintroduced by smoothing
7. **Find centroids** -- `scipy.ndimage.center_of_mass` per connected component; unique component IDs tracked in a global map
8. **Upscale** -- labels and component map are upscaled `--scale`x with nearest-neighbor (no blurring of region shapes)
9. **Re-smooth & detect edges** -- a second smooth pass at output resolution anti-aliases the upscaled staircase; 1px edges detected via neighbour comparison
10. **Render paint-by-numbers** -- white canvas, black 1px edges, each number placed at the nearest valid position to the centroid where the full text fits (via `distance_transform_edt`)
11. **Render legend** -- color swatches with region numbers, per-color region count, and total region count

## Note

The tool does better on images that are already "simplified".

That's why it is sometimes worth pre-processing the input image through an AI Image model, with a prompt like:

> Simplify this image:
> - smaller palette of colors ~15
> - more uniform color regions

