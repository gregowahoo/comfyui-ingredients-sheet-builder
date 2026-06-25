# ComfyUI Ingredients Sheet Builder

A single-purpose ComfyUI custom node that builds a **reference sheet** for the
**LTX-2.3 IC-LoRA Ingredients** model. It arranges your character/prop images in
a top row and your location image as a full-width band, on a clean black
background with uniform gutters — matching the spec Lightricks uses for their own
example sheets (1456×825).

Build: see the `NODE_BUILD` line at the top of `node.py`. It also prints to the
ComfyUI startup console so you can confirm which version is loaded.

## What it does

- Lays out up to 6 character/prop panels in a top row, each shown **whole** at its
  true aspect ratio (no squish, no crop).
- Adds the location/environment image as a **full-width band** at the bottom (or
  top), which gets a guaranteed share of the sheet height.
- Outputs the finished sheet, a ready-to-use prompt, and a labeled preview for
  checking your layout.

## Inputs

### Required

| Input | Default | What it does |
|-------|---------|--------------|
| `output_width` | 1456 | Sheet width. 1456 matches Lightricks' example sheets. Keep the ~16:9 ratio. |
| `output_height` | 825 | Sheet height. |
| `location_position` | bottom | Put the full-width location band at the bottom or top. |
| `panel_gap` | 12 | Black gap (px) between panels and between the character row and location band. 0 = edge-to-edge (not recommended). |
| `show_panel_numbers` | false | Draw panel numbers on the labeled preview only (never on the real sheet). |

### Optional

| Input | Default | What it does |
|-------|---------|--------------|
| `location_image` | — | The location/environment/set. Spans the full width as its own band. |
| `location_height_percent` | 40 | How much of the sheet height the location band gets (the character row fills the rest). Higher = more location shown, less squish/crop. |
| `location_fit_bars` | false | OFF: location fills the band edge-to-edge, cropping top/bottom if needed. ON: shows the whole location undistorted and fills leftover space with black bars. Turn ON if a wide location (e.g. a beach) is getting cut off. |
| `location_id` | — | Optional name/ID for the location, threaded through the description. |
| `location_desc` | — | Description of the location panel. |
| `image_1`–`image_6` | — | Character or prop panels. Mute a Load Image node to drop that panel. |
| `id_1`–`id_6` | — | Optional name/ID per panel, so one character is referred to consistently across panels. |
| `desc_1`–`desc_6` | — | Description per panel. |

## Outputs

| Output | Type | What it is |
|--------|------|------------|
| `sheet_image` | IMAGE | The finished reference sheet to feed the Ingredients model. |
| `reference_sheet_prompt` | STRING | A clean prose prompt describing the sheet contents. |
| `labeled_preview` | IMAGE | The same sheet with panel labels/numbers for your own checking. |

## The two location controls (most common adjustment)

If your location image looks wrong in the band, these two work together:

- **`location_height_percent`** — gives the band more or less room. Bump it up
  (e.g. 50) if the location is being squeezed too thin.
- **`location_fit_bars`** — turn ON to keep the whole location image visible
  (with black bars) instead of cropping its top and bottom to fill the band.

For a wide beach that was getting its top and bottom cut off: set
`location_height_percent` around 50 and turn `location_fit_bars` ON.

## Notes

- Panels are never cropped or squished; each is shown at its native aspect on the
  black background, per the model card.
- A clear `panel_gap` keeps the model from blending panels or carrying a seam line
  into the generated video.
- The sheet (1456×825) is intentionally larger than the output video (~768×448);
  the pipeline downscales it, and the larger sheet carries more identity detail.

## License

Personal project. Use at your own discretion.
