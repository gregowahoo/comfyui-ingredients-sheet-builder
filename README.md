# Ingredients Sheet Builder

**The missing prep step for the [LTX-2.3 IC-LoRA Ingredients](https://huggingface.co/Lightricks/LTX-2.3-22b-IC-LoRA-Ingredients) workflow.**

The Ingredients model conditions video generation on a *reference sheet* — a single
composite image with one clean panel per visual element (character turnarounds, a
face, props, and a location panel) on a black background with no text — **plus** a
two-part prompt that describes those panels in a specific trained format:

```
### Reference Sheet Description
**Top Row Left (Character):** <description>
**Full Width Bottom (Setting):** <description>

### Target Description
<the action you want>
```

Most people build that sheet with a flat text-to-image generator (e.g. Ideogram),
which is T2I-only, can't use your *existing* character images or generations, bakes
in text, and won't touch NSFW. **This node builds the sheet from your own images,
lays them out so nothing gets cropped, and emits the trained-format prompt** — the
part T2I sheet makers don't give you.

> Node category: **Ingredients/**

---

## What it does

- Composites a reference sheet from your images onto a **black, text-free canvas**.
- Three **layout modes**: a fixed-grid template system, plus two **no-crop** modes
  that keep every image's native shape so a full-body character is never truncated.
- The **location/background always spans the full width** of the sheet as its own
  band (optional, on by default) — even with just one other image.
- Assembles the prompt in the trained **positional format** (`**Top Row Left
  (Character):** ...`), computed from where each panel actually lands.
- Auto-captions are **external**: wire a `TextGenerate` (or any text source) per
  panel, or just type descriptions. Nothing is captioned inside this node, so it's
  small, debuggable, and NSFW-safe with a local captioner.
- Emits a single ready-to-use **`full_prompt`** (reference + target, correctly
  spaced) so you wire one output straight into the text encoder.

---

## Quick start

1. Wire your character images into `image_1`, `image_2`, ... and your location into
   `background`.
2. Caption each one (a `TextGenerate` per image into the matching `desc_*`), or just
   type a short description in each `desc_*` field.
3. Set `layout_mode` to **Auto-fit rows (no crop)** and leave `row_assignment`
   **blank** — every image you wired will show, nothing cropped, location spanning
   the full width.
4. Wire `sheet_image` → your reference path, `full_prompt` → positive text encode,
   `negative_prompt` → negative text encode. Run.

That's the whole loop. Everything below is detail and customization.

---

## Layout modes

Set `layout_mode`:

- **Template (fixed grid)** — pick one of 10 presets (or `Custom` JSON) of fixed
  rectangles. Images fit into panels via `crop_fill` (fills the panel, may crop) or
  `fit_pad` (whole image, padded). Exact and grid-like; can crop tall images.
- **Auto-fit rows (no crop)** — images keep native aspect and are laid out in rows.
  Just wire your images and they all appear; the sheet size adapts. **Nothing is
  ever cropped, and nothing is ever skipped** — any wired image shows up whether or
  not you mention it in `row_assignment`. Use `row_assignment` only if you *want* to
  control which images share a row (e.g. `1,2,3 | 4,5`); leave it blank for one row.
- **Free pack (no crop)** — images keep native aspect and flow left-to-right,
  wrapping to new rows automatically. **Nothing is ever cropped.**

Use the no-crop modes when keeping the *whole* character visible matters more than
the sheet being a tidy rectangle — the IC-LoRA model just needs to see each element
clearly. `row_target_height` controls how big the panels (and the sheet) are.

See `layout_templates_reference.png` for a visual map of the 10 fixed templates.
Wire the `layout_map` output to a Preview Image node to see any layout after a run.

---

## Inputs

**Required**

| Widget | Notes |
|---|---|
| `layout_mode` | `Template (fixed grid)` / `Auto-fit rows (no crop)` / `Free pack (no crop)` |
| `template` | One of 10 presets, or `Custom` (Template mode only) |
| `canvas_width` / `canvas_height` | Template mode: exact size (match output res). No-crop modes: `canvas_width` is the max width before wrapping; height grows to fit |
| `row_target_height` | No-crop modes: height each image/row is scaled to. Bigger = larger panels + taller sheet |
| `background_color` | `black` (IC-LoRA spec) or `white` |
| `fit_mode` | Template mode only. `crop_fill` (fills, may crop) or `fit_pad` (whole image, padded) |
| `panel_gap` | Pixels between panels |
| `generated_video_action` | The action text for the `### Target Description` |
| `preview_labels` | Draw panel numbers on a **separate** preview image only |
| `row_assignment` | Auto-fit rows mode: **optional** row grouping, e.g. `1,2,3 | 4,5`. Leave blank for one row. Any wired image not listed is added automatically — nothing is skipped |
| `location_full_width` | No-crop modes (default ON): location always spans the full sheet width as its own band |
| `location_band_position` | `bottom` or `top` for that band |
| `layout_json` | Used only when `template = Custom` |

**Optional (image + description per slot)**
- `background` (IMAGE) + `background_desc` (STRING) — the location panel (slot 0)
- `image_1`..`image_9` (IMAGE) + `desc_1`..`desc_9` (STRING) — element panels

Each `desc_*` field can be **typed directly**, or you can wire a text source into
it (right-click → Convert to input). Empty + no image = that panel is skipped.

## Outputs

| Output | Use |
|---|---|
| `sheet_image` (IMAGE) | The black, text-free composite — feed this to the IC-LoRA reference path |
| `full_prompt` (STRING) | **Reference + Target combined, correctly spaced — wire this one into your positive text encoder** |
| `reference_sheet_prompt` (STRING) | Just the `### Reference Sheet Description` block, if you want it separate |
| `generated_video_prompt` (STRING) | Just the `### Target Description` block |
| `negative_prompt` (STRING) | The card's recommended negative prompt |
| `labeled_preview` (IMAGE) | Same layout **with** panel numbers, for your eyes only — never feed this to the LoRA |
| `layout_map` (IMAGE) | A diagram of the chosen layout (numbered, colored panels) |

For most setups: wire **`full_prompt` → positive CLIP Text Encode**, and
**`negative_prompt` → negative CLIP Text Encode**. No concatenation needed.

---

## Captioning (external)

This node does **not** caption internally. You caption each panel **externally** and
the result flows into the `desc_*` inputs. This keeps the node small, makes each
caption visible/debuggable on its own, and lets you use any captioner.

Recommended: a **`TextGenerate`** node (from `comfyui-easy-use`) per panel, with a
`CLIPLoader` / text-encoder loader pointed at a vision-capable model (e.g. a Gemma
or Qwen-VL encoder). Feed each panel image into a TextGenerate, wire its text output
into the matching `desc_*` input. Connect the panel's image, or the model will
hallucinate a description.

> NSFW: because captioning is external and local, there's no cloud filter to refuse
> explicit panels — use a local vision-capable encoder.

## Custom layout JSON

When `template = Custom` (Template mode), `layout_json` is a list of slots.
Coordinates are fractions of the canvas (0–1), so layouts are resolution-independent.
`slot 0` is the background/location input.

```json
[
  {"slot": 0, "x": 0.0,  "y": 0.55, "w": 1.0,  "h": 0.45, "role": "location"},
  {"slot": 1, "x": 0.0,  "y": 0.0,  "w": 0.5,  "h": 0.55, "role": "character"},
  {"slot": 2, "x": 0.5,  "y": 0.0,  "w": 0.5,  "h": 0.55, "role": "character"}
]
```

`role` is one of `location` / `character` / `face` / `prop` / `element`, and feeds
the parenthetical in the prompt (`(Setting)` / `(Character)` / etc.). Bigger
rectangles reproduce more faithfully — give important elements more space.

---

## Wiring into the LTX IC-LoRA Ingredients workflow

1. Build your panels — load existing images (`LoadImage`) or pipe in fresh
   generations — into the slot inputs. Caption them (TextGenerate or typed).
2. `sheet_image` → the IC-LoRA **reference** input. The Ingredients workflow loops
   the still into a static video; it must match the output frame count (e.g. set
   `RepeatImageBatch` to your total frames, ≥ 121). The LTX repo's reference
   workflow wires this for you.
3. `full_prompt` → your positive text conditioning.
4. `negative_prompt` → the negative conditioning.
5. Recommended settings from the card: **LoRA strength 1.4, 30 steps, guidance
   4.0**, base **LTX-2.3-22B** + `ltx-2.3-22b-ic-lora-ingredients-0.9.safetensors`.

Tips from working with it:
- Open the action text with what's happening **from the first frame** (e.g.
  "From the first frame she is already mid-stride...") to avoid a hologram/garbled
  "settling" intro.
- For a single-character sheet, keep any other person off-frame in the action — the
  model can render a malformed second figure if you describe one that isn't in the
  sheet.
- Run sheet prep (captioning) and the heavy LTX render **separately** — both load
  large models; don't hold both at once on 16GB VRAM.

> The Ingredients model is gated on Hugging Face — log in and click **Agree and
> Access** to download the weights.

---

## Install

```
cd ComfyUI/custom_nodes
git clone https://github.com/gregowahoo/comfyui-ingredients-sheet-builder
pip install -r comfyui-ingredients-sheet-builder/requirements.txt
```
Restart ComfyUI. Find **Ingredients Sheet Builder** under the **Ingredients/**
category.

## License / credits

MIT (see LICENSE). Built to pair with Lightricks' LTX-2.3 IC-LoRA Ingredients. This
project includes no model weights; the LTX-2.3 model and its IC-LoRA are governed by
the LTX-2-community-license — obtain and use those separately under their own terms.
