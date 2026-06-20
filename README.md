# Ingredients Sheet Builder

**The missing prep step for the [LTX-2.3 IC-LoRA Ingredients](https://huggingface.co/Lightricks/LTX-2.3-22b-IC-LoRA-Ingredients) workflow.**

The Ingredients model conditions video generation on a *reference sheet* — a single
composite image with one clean panel per visual element (each character as a
face + turnaround, each prop, and one location panel) on a black background with
no text — **plus** a two-part prompt that describes those panels:

```
Reference sheet: <descriptions of the panels>
Generated video: <the action you want>
```

Most people build that sheet with a flat text-to-image generator (e.g. Ideogram),
which is T2I-only, can't use your *existing* character images or generations,
bakes in text, and won't touch NSFW. **This node builds the sheet from your own
images or generation branches, lays them out per the model's guidance, and emits
the trained-format prompt strings** — the part T2I sheet makers don't give you.

> Node category: **Ingredients/** — the first of a planned mini-suite.

---

## What it does

- Composites a reference sheet onto a **black 768×448 canvas** (the trained bucket), **no baked text**.
- 10 **role-aware layout templates** — location and primary-character panels get the
  most space, because the model card says *"bigger panels carry over better."*
- A **Custom** template that reads a normalized-rect layout JSON, so you can size
  every panel by importance yourself.
- A dedicated **background/location** input (slot 0) for the environment panel.
- A **modular vision backend** to auto-caption each panel (or type descriptions yourself).
- Outputs both prompt parts ready to wire into the LTX text encoder, plus the
  card's recommended **negative prompt**.

---

## Inputs

**Required**
| Widget | Notes |
|---|---|
| `template` | One of 10 presets, or `Custom` |
| `canvas_width` / `canvas_height` | Default 768×448 (trained bucket) |
| `background_color` | `black` (IC-LoRA spec) or `white` |
| `fit_mode` | `crop_fill` (uniform, crops overflow) or `fit_pad` (whole image, bars) |
| `panel_gap` | Pixels between panels — **keep 0 for IC-LoRA** |
| `vision_backend` | `none` / `ollama` / `openai_compatible` / `gemini` / `anthropic` |
| `vision_model` | e.g. `llava`, `qwen2-vl`, `gpt-4o-mini`, `gemini-2.0-flash` |
| `vision_base_url` | Ollama root, or an OpenAI-compatible `/v1` root |
| `vision_api_key` | Blank for local Ollama |
| `caption_prompt` | Instruction sent to the vision model per panel |
| `generated_video_action` | The action text for `Generated video:` |
| `preview_labels` | Draw panel numbers on a **separate** preview image only |
| `layout_json` | Used only when `template = Custom` |

**Optional (image + description per slot)**
- `background` (IMAGE) + `background_desc` (STRING) — the location panel (slot 0)
- `image_1`..`image_9` (IMAGE) + `desc_1`..`desc_9` (STRING) — element panels

For each panel the description is taken from the manual `desc_*` field if you
filled it; otherwise the chosen vision backend captions the image. With
`vision_backend = none`, only your manual descriptions are used.

## Outputs

| Output | Use |
|---|---|
| `sheet_image` (IMAGE) | The black, text-free composite — feed this to the IC-LoRA reference path |
| `reference_sheet_prompt` (STRING) | `Reference sheet: ...` — wire into your positive text |
| `generated_video_prompt` (STRING) | `Generated video: ...` |
| `negative_prompt` (STRING) | The card's recommended negative |
| `labeled_preview` (IMAGE) | Same layout **with** panel numbers, for your eyes only — never feed this to the LoRA |

---

## Vision backends (modular, swappable)

Pick how you caption panels. All behind one dropdown:

- **`none`** — no model; uses your typed `desc_*` fields.
- **`ollama`** — local Ollama server. NSFW-safe, no key. **Recommended for character work.**
  Requires Ollama running with a vision model pulled: `ollama pull llava` (or a qwen2-vl gguf).
  Set `vision_base_url` to `http://localhost:11434`.
- **`openai_compatible`** — any OpenAI-style `/v1/chat/completions` vision endpoint:
  Grok/xAI (`https://api.x.ai/v1`), LM Studio (`http://localhost:1234/v1`), OpenRouter, etc.
- **`gemini`** — Google Gemini API.
- **`anthropic`** — Anthropic API.

> **NSFW caveat:** cloud vision APIs (gemini, anthropic, most hosted
> openai_compatible providers) will refuse explicit imagery. For NSFW panels use
> **`ollama`** locally. The cloud backends are fine for SFW props/locations.

Adding a backend later is one function in `vision_backends.py` — they all share
one interface and return a caption string.

---

## Custom layout JSON

When `template = Custom`, `layout_json` is a list of slots. Coordinates are
fractions of the canvas (0–1), so layouts are resolution-independent. `slot 0` is
the background/location input.

```json
[
  {"slot": 0, "x": 0.0,  "y": 0.0,  "w": 1.0,  "h": 1.0,  "role": "location"},
  {"slot": 1, "x": 0.02, "y": 0.30, "w": 0.30, "h": 0.68, "role": "character"},
  {"slot": 2, "x": 0.34, "y": 0.55, "w": 0.20, "h": 0.43, "role": "face"}
]
```

`role` is informational (`location` / `character` / `face` / `prop` / `element`).
Tip: give important elements the biggest rectangles — the model reproduces large
panels more faithfully.

---

## Wiring into the LTX IC-LoRA Ingredients workflow

1. Build your panels — load existing images (`LoadImage`) or pipe in fresh
   generations — into the slot inputs.
2. `sheet_image` → the IC-LoRA **reference / control** input. The Ingredients
   workflow loops the still into a static video; it must be **≥ 121 frames** at
   the output resolution (768×448, 24 fps). Use the LTX repo's reference workflow
   which already wires this.
3. `reference_sheet_prompt` + `generated_video_prompt` → your text conditioning,
   concatenated (or kept separate while you test).
4. `negative_prompt` → the negative conditioning.
5. Recommended model settings from the card: **LoRA strength 1.4, 30 steps,
   guidance 4.0**, base model **LTX-2.3-22B** + `ltx-2.3-22b-ic-lora-ingredients-0.9.safetensors`
   in `models/loras`.

> The Ingredients model is gated on Hugging Face — log in and click **Agree and
> Access** to download the weights.

---

## Install

```
cd ComfyUI/custom_nodes
git clone <your-repo-url> comfyui-ingredients-sheet-builder
# or copy this folder in
pip install -r comfyui-ingredients-sheet-builder/requirements.txt
```
Restart ComfyUI. Find **Ingredients Sheet Builder** under the **Ingredients/**
category.

## License / credits

Built to pair with Lightricks' LTX-2.3 IC-LoRA Ingredients. Respect the
LTX-2-community-license for the model weights.
