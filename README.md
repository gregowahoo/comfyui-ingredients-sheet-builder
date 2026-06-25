# ComfyUI Ingredients Sheet Builder

A focused ComfyUI custom node that builds a clean **reference sheet** for the
[LTX-2.3 IC-LoRA Ingredients](https://huggingface.co/Lightricks/LTX-2.3-22b-IC-LoRA-Ingredients)
model, and assembles the panel descriptions into the clean prose format that model expects.

Wire in your character/prop images and a location image, give each panel a name and a
description, and the node composes them into one composite sheet — character panels in a
top row, the location as a full-width band, with uniform black gutters like Lightricks'
own example sheets. It also outputs the reference-sheet prompt as clean semicolon prose.

---

## What it does

The Ingredients model conditions video generation on a **reference sheet** — a single
composite image inventorying the characters, props, and location of a scene — so generated
videos keep those elements visually consistent. This node produces exactly that, with no
layout modes or templates to configure.

- **Character / prop panels** go in one row across the top, each shown **whole** at its true
  aspect ratio — never cropped (no cut-off heads/feet) and never squished. The row scales to
  fill the width when it can, so with 4-5 panels you get an edge-to-edge layout.
- **The location image** spans the full width as its own band, at the top or bottom.
- **Uniform black gutters** separate every panel, separate the character row from the location
  band, and frame the whole sheet - matching the official example sheets and preventing hard
  seams from carrying into the rendered video.
- **Per-panel names (IDs)** thread one consistent identity through the prompt: give every panel
  that shows the same character the same name, and the description names that character on each
  panel instead of describing five separate-looking people.
- **To leave an image off the sheet**, mute its `Load Image` node (Ctrl-M). Whatever is wired in
  appears; whatever isn't doesn't.

### Sheet size vs. video size

The default sheet size is **1456x825**, matching Lightricks' own example sheets - *not* the
768x448 figure from the model card. That 768x448 is the **output video** size; the **reference
sheet** is larger and gets downscaled in the pipeline. Bigger sheets give each panel more detail
and downscale cleanly, which avoids faint seam/banding artifacts seen with cramped small sheets.

---

## Inputs

| Input | Type | Notes |
|------|------|-------|
| `output_width` / `output_height` | INT | Sheet size. Default **1456x825** (matches the example sheets; keep ~16:9). |
| `location_position` | choice | `bottom` or `top` - where the full-width location band sits. |
| `panel_gap` | INT | Black gutter (px) between panels, between the rows, and around the whole sheet. Default **12**. |
| `show_panel_numbers` | BOOLEAN | Draws panel numbers on `labeled_preview` only - never on the real sheet. |
| `location_image` | IMAGE (optional) | The location / environment / set panel. |
| `location_id` | STRING (optional) | Name for the location (e.g. "the Aeterna atrium"). |
| `location_desc` | STRING (optional) | Description of the location panel. |
| `image_1` ... `image_6` | IMAGE (optional) | Character / prop panels. Mute a Load Image node to drop one. |
| `id_1` ... `id_6` | STRING (optional) | Name for each panel. Give the **same name** to every panel showing the same character. |
| `desc_1` ... `desc_6` | STRING (optional) | Description of each panel. |

## Outputs

| Output | Type | Notes |
|------|------|-------|
| `sheet_image` | IMAGE | The composite reference sheet. Wire to the reference / `LoadImage` input of the LTX Ingredients workflow. |
| `reference_sheet_prompt` | STRING | The panel descriptions as clean semicolon-joined prose (no headers, no labels). |
| `labeled_preview` | IMAGE | The sheet with panel numbers drawn on. For your eyes only - never feed it to the model. |

The action/video prompt and the captioning system prompt are **not** part of this node - keep
those in their own Text nodes in your workflow so you can edit them freely (see below).

---

## Install

```
cd ComfyUI/custom_nodes
git clone https://github.com/gregowahoo/comfyui-ingredients-sheet-builder.git
```

Restart ComfyUI. The node appears under the **Ingredients** category as
**Ingredients Sheet Builder**. Only Pillow and NumPy are required, both of which ship with ComfyUI.

---

## Using it with the LTX Ingredients workflow

Start from Lightricks' official example workflow:

[`LTX-2.3_ICLoRA_Ingredients_Single_Stage_Distilled.json`](https://github.com/Lightricks/ComfyUI-LTXVideo/blob/master/example_workflows/2.3/LTX-2.3_ICLoRA_Ingredients_Single_Stage_Distilled.json)

Replace the `LoadImage` node that supplies the reference sheet with this node's `sheet_image`
output. The downstream wiring (`LTXAddVideoICLoRAGuide`, `LTXVImgToVideoConditionOnly` with
`bypass_i2v` = True, the IC-LoRA loader) stays as the example provides it. `bypass_i2v = True`
is correct for Ingredients - the sheet is conditioning, not a first frame.

### Building the full prompt

The reference description and the action prose are joined downstream:

```
[reference_sheet_prompt]  [your action prose]
```

Keep the **action idea** and the **captioning system prompt** each in their own Text node, wire
them into your captioning/Generate Text node, and concatenate that node's output with
`reference_sheet_prompt`. A starting system-prompt template (with an `ACTION IDEA:` label at the
end) is included as a reference comment at the top of `node.py`.

### Tips from the model card

- **Bigger panels carry over better** - the more sheet area an element occupies, the more
  faithfully it appears. Give your main character the most space; use 4-5 panels for an
  edge-to-edge row.
- **Keep the location panel free of prominent people** - background figures can bleed into the
  character. Use IDs to keep one named character consistent across panels.
- **Ingredients runs on the distilled checkpoint.**

---

## License

See [LICENSE](LICENSE). The LTX-2.3 model and its IC-LoRAs are covered by the
[LTX-2 Community License](https://huggingface.co/Lightricks/LTX-2.3-22b-IC-LoRA-Ingredients).
