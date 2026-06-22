# ComfyUI Ingredients Sheet Builder

A single-purpose ComfyUI custom node that builds a clean **reference sheet** for the
[LTX-2.3 IC-LoRA Ingredients](https://huggingface.co/Lightricks/LTX-2.3-22b-IC-LoRA-Ingredients)
model — and assembles the matching prompt in the exact format that model expects.

Wire in your character/prop images and a location image, and the node composes them
into one composite sheet with character panels in a top row and the location as a
full-width band. It also outputs a ready-to-use prompt and an editable system prompt
for your captioning/LLM node.

---

## What it does

The Ingredients model conditions video generation on a **reference sheet** — a single
composite image inventorying the characters, props, and location of a scene — so that
generated videos keep those elements visually consistent. The model card specifies the
sheet should be *clean panels on a black background, no text.* This node produces exactly
that, and nothing else: no layout modes, no template picker, no settings to get wrong.

- **Character / prop panels** are placed in one row across the top, each shown **whole**
  at its true aspect ratio — never cropped (no cut-off heads/feet) and never squished.
  Panels sit centered on a black background, which is the model card's intended layout.
- **The location image** spans the full width as its own band, at the top or bottom.
- **To leave an image off the sheet**, just mute its `Load Image` node (Ctrl-M). Whatever
  is wired in appears; whatever isn't doesn't.
- **Black bars never bleed into your video.** Because each panel is shown whole on a black
  background (rather than a panel padded with black bars), there is no flat black framing
  baked into a panel for the model to carry across every frame.

### Why "whole panels on black"?

For tall character portraits, you cannot simultaneously (a) fill the full width, (b) keep
true proportions, and (c) show the whole character — when the panels don't naturally tile
to the sheet width, one of those must give. This node keeps proportions and the whole
character, and lets the remaining space be black background — which is what the model was
trained on. If you want panels to fill more of the width, use fewer panels per row.

---

## Inputs

| Input | Type | Notes |
|------|------|-------|
| `output_width` / `output_height` | INT | Sheet size. Defaults to **768×448** (the model's trained size). Match your output video resolution (downscale factor 1). Larger = more panel detail but further from the trained bucket. |
| `location_position` | choice | `bottom` or `top` — where the full-width location band sits. |
| `panel_gap` | INT | Pixels of black gap between panels (0 = panels touch). A small gap can help the model keep elements separate. |
| `llm_system_prompt` | STRING | Standing instructions for your captioning/LLM node. Editable here, also exposed as an output socket; convert to an input to feed it from elsewhere. |
| `action_idea` | STRING | Your rough action idea; the LLM expands it into the Target Description. Also an output. |
| `show_panel_numbers` | BOOLEAN | Draws panel numbers on `labeled_preview` only — never on the real sheet. |
| `location_image` | IMAGE (optional) | The location / environment / set panel. |
| `location_desc` | STRING (optional) | Description of the location panel. |
| `image_1` … `image_6` | IMAGE (optional) | Character / prop panels. Mute a Load Image node to drop that panel. |
| `desc_1` … `desc_6` | STRING (optional) | Per-panel descriptions. |

## Outputs

| Output | Type | Notes |
|------|------|-------|
| `sheet_image` | IMAGE | The composite reference sheet. Wire this to the reference/`LoadImage` input of the LTX Ingredients workflow. |
| `full_prompt` | STRING | `### Reference Sheet Description` + `### Target Description`, combined. |
| `reference_sheet_prompt` | STRING | Just the reference-sheet description part. |
| `generated_video_prompt` | STRING | Just the action/target part. |
| `negative_prompt` | STRING | Suggested negative (`worst quality, inconsistent motion, blurry, jittery, distorted`). |
| `labeled_preview` | IMAGE | The sheet with panel numbers drawn on. For your eyes only — do **not** feed it to the model. |
| `llm_system_prompt` | STRING | Pass-through of the system prompt field, to wire into your Generate Text node. |
| `action_idea` | STRING | Pass-through of the action idea field. |

---

## Install

```
cd ComfyUI/custom_nodes
git clone https://github.com/gregowahoo/comfyui-ingredients-sheet-builder.git
```

Restart ComfyUI. The node appears under the **Ingredients** category as
**Ingredients Sheet Builder**.

Only [Pillow](https://pypi.org/project/Pillow/) and NumPy are required, both of which
ship with ComfyUI.

---

## Using it with the LTX Ingredients workflow

Start from Lightricks' official example workflow:

[`LTX-2.3_ICLoRA_Ingredients_Single_Stage_Distilled.json`](https://github.com/Lightricks/ComfyUI-LTXVideo/blob/master/example_workflows/2.3/LTX-2.3_ICLoRA_Ingredients_Single_Stage_Distilled.json)

Then replace the `LoadImage` node that supplies the reference sheet with this node's
`sheet_image` output. The downstream wiring (`LTXAddVideoICLoRAGuide`,
`LTXVImgToVideoConditionOnly`, the IC-LoRA loader, looping the still into a static video)
stays as the example provides it.

The prompt format this node emits matches the official example exactly, e.g.:

```
### Reference Sheet Description
**Top Row Left (Character):** <your description>
**Full-Width Bottom (Location):** <your description>

### Target Description
<your action prose>
```

### Tips from the model card

- **Bigger panels carry over better** — the more sheet area an element occupies, the more
  faithfully it appears in the video. Give your main character the most space.
- **One composite sheet, at output resolution, looped into a static video** is the expected
  input. This node makes the sheet; the looping happens downstream in the LTX workflow.
- **Ingredients runs on the distilled checkpoint** via the `ICLoraPipeline`.

---

## License

See [LICENSE](LICENSE). The LTX-2.3 model and its IC-LoRAs are covered by the
[LTX-2 Community License](https://huggingface.co/Lightricks/LTX-2.3-22b-IC-LoRA-Ingredients).
