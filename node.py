"""
Ingredients Sheet Builder - the prep step for the LTX-2.3 IC-LoRA Ingredients
workflow. Composes a reference sheet (one clean panel per visual element, black
background, no baked text) AND emits the trained-format two-part prompt the
Ingredients model expects:

    Reference sheet: <panel descriptions>
    Generated video: <action>

Replaces flat T2I sheet generators (e.g. Ideogram) because it builds the sheet
from YOUR images or generation branches, supports NSFW (local captioning), and
produces the prompt text the model was trained on - not just a picture.

Node category: Ingredients/
"""

import json
import numpy as np
import torch
from PIL import Image, ImageDraw, ImageFont

from .templates import TEMPLATES, TEMPLATE_NAMES, get_template, max_slot_in_templates
from .vision_backends import caption_image, BACKENDS, DEFAULT_CAPTION_PROMPT

MAX_SLOTS = max(9, max_slot_in_templates())  # always expose enough element inputs

# Recommended negative prompt straight from the IC-LoRA model card.
CARD_NEGATIVE = "worst quality, inconsistent motion, blurry, jittery, distorted"


# ---- tensor <-> PIL helpers (ComfyUI IMAGE = float tensor [B,H,W,C] 0..1) --- #
def _tensor_to_pil(img_tensor):
    if img_tensor is None:
        return None
    arr = img_tensor
    if arr.dim() == 4:
        arr = arr[0]
    arr = (arr.clamp(0, 1).cpu().numpy() * 255).astype(np.uint8)
    return Image.fromarray(arr, "RGB")


def _pil_to_tensor(pil_image):
    arr = np.asarray(pil_image.convert("RGB")).astype(np.float32) / 255.0
    return torch.from_numpy(arr)[None, ...]  # [1,H,W,C]


def _fit_into(cell_w, cell_h, img, mode):
    """Return img resized to fill (crop) or fit (pad) a cell of cell_w x cell_h."""
    if cell_w <= 0 or cell_h <= 0:
        return Image.new("RGB", (max(1, cell_w), max(1, cell_h)), (0, 0, 0))
    iw, ih = img.size
    target = cell_w / cell_h
    src = iw / ih
    if mode == "fit_pad":
        scale = min(cell_w / iw, cell_h / ih)
        nw, nh = max(1, int(iw * scale)), max(1, int(ih * scale))
        resized = img.resize((nw, nh), Image.LANCZOS)
        canvas = Image.new("RGB", (cell_w, cell_h), (0, 0, 0))
        canvas.paste(resized, ((cell_w - nw) // 2, (cell_h - nh) // 2))
        return canvas
    # crop_fill (default)
    if src > target:
        nh = cell_h
        nw = max(1, int(src * nh))
    else:
        nw = cell_w
        nh = max(1, int(nw / src))
    resized = img.resize((nw, nh), Image.LANCZOS)
    left = (nw - cell_w) // 2
    top = (nh - cell_h) // 2
    return resized.crop((left, top, left + cell_w, top + cell_h))


class IngredientsSheetBuilder:
    """
    Builds the IC-LoRA reference sheet image + the trained-format prompt strings.
    """

    @classmethod
    def INPUT_TYPES(cls):
        optional = {
            "background": ("IMAGE", {"tooltip": "Location/environment panel (slot 0)."}),
        }
        # numbered element image inputs + a per-slot description override
        for i in range(1, MAX_SLOTS + 1):
            optional[f"image_{i}"] = ("IMAGE",)
            optional[f"desc_{i}"] = ("STRING", {
                "multiline": True, "default": "",
                "tooltip": f"Manual description for panel {i}. "
                           f"Used as-is when vision_backend=none, or as a fallback/override.",
            })
        optional["background_desc"] = ("STRING", {
            "multiline": True, "default": "",
            "tooltip": "Manual description for the location/background panel (slot 0).",
        })

        return {
            "required": {
                "template": (TEMPLATE_NAMES + ["Custom"], {"default": TEMPLATE_NAMES[0]}),
                "canvas_width": ("INT", {"default": 768, "min": 64, "max": 4096, "step": 8}),
                "canvas_height": ("INT", {"default": 448, "min": 64, "max": 4096, "step": 8}),
                "background_color": (["black", "white"], {"default": "black"}),
                "fit_mode": (["crop_fill", "fit_pad"], {"default": "crop_fill"}),
                "panel_gap": ("INT", {"default": 0, "min": 0, "max": 128, "step": 1,
                                      "tooltip": "Gap between panels in pixels. Keep 0 for IC-LoRA."}),
                "vision_backend": (BACKENDS, {"default": "none"}),
                "vision_model": ("STRING", {"default": "llava",
                                            "tooltip": "e.g. llava / qwen2-vl (ollama), gpt-4o-mini, gemini-2.0-flash"}),
                "vision_base_url": ("STRING", {"default": "http://localhost:11434",
                                               "tooltip": "Ollama root, or OpenAI-compatible /v1 root, etc."}),
                "vision_api_key": ("STRING", {"default": "", "tooltip": "Leave blank for local Ollama."}),
                "caption_prompt": ("STRING", {"multiline": True, "default": DEFAULT_CAPTION_PROMPT}),
                "generated_video_action": ("STRING", {
                    "multiline": True,
                    "default": "the character walks forward through the scene, cinematic lighting",
                    "tooltip": "The action/shot for the 'Generated video:' prompt part.",
                }),
                "preview_labels": ("BOOLEAN", {"default": False,
                                               "tooltip": "Draw panel numbers on a SEPARATE preview image. "
                                                          "Never baked into the IMAGE you feed the LoRA."}),
                "layout_json": ("STRING", {
                    "multiline": True,
                    "default": ('[\n'
                                '  {"slot": 0, "x": 0.0, "y": 0.0, "w": 1.0, "h": 1.0, "role": "location"},\n'
                                '  {"slot": 1, "x": 0.02, "y": 0.30, "w": 0.30, "h": 0.68, "role": "character"},\n'
                                '  {"slot": 2, "x": 0.34, "y": 0.55, "w": 0.20, "h": 0.43, "role": "face"}\n'
                                ']'),
                    "tooltip": "Only used when template = Custom. Normalized (0-1) rects. "
                               "slot 0 = background/location input.",
                }),
            },
            "optional": optional,
        }

    RETURN_TYPES = ("IMAGE", "STRING", "STRING", "STRING", "IMAGE")
    RETURN_NAMES = ("sheet_image", "reference_sheet_prompt", "generated_video_prompt",
                    "negative_prompt", "labeled_preview")
    FUNCTION = "build"
    CATEGORY = "Ingredients"
    DESCRIPTION = ("Prep step for the LTX-2.3 IC-LoRA Ingredients workflow: compose a "
                   "reference sheet from your images/generations and emit the trained-format "
                   "'Reference sheet:' / 'Generated video:' prompt strings.")

    # ---------------------------------------------------------------- #
    def _resolve_layout(self, template, layout_json):
        if template == "Custom":
            try:
                slots = json.loads(layout_json) if layout_json.strip() else []
            except json.JSONDecodeError as e:
                raise ValueError(f"Custom layout_json is not valid JSON: {e}")
            return slots
        return get_template(template) or []

    def build(self, template, canvas_width, canvas_height, background_color, fit_mode,
              panel_gap, vision_backend, vision_model, vision_base_url, vision_api_key,
              caption_prompt, generated_video_action, preview_labels, layout_json="",
              **kwargs):

        slots = self._resolve_layout(template, layout_json)

        bg_rgb = (0, 0, 0) if background_color == "black" else (255, 255, 255)
        canvas = Image.new("RGB", (canvas_width, canvas_height), bg_rgb)
        preview = canvas.copy()
        draw = ImageDraw.Draw(preview)
        try:
            font = ImageFont.truetype("arial.ttf", max(16, canvas_height // 28))
        except Exception:
            font = ImageFont.load_default()

        # gather the images per slot id
        def slot_image(sid):
            if sid == 0:
                return _tensor_to_pil(kwargs.get("background"))
            return _tensor_to_pil(kwargs.get(f"image_{sid}"))

        def slot_manual_desc(sid):
            if sid == 0:
                return (kwargs.get("background_desc") or "").strip()
            return (kwargs.get(f"desc_{sid}") or "").strip()

        # composite + collect descriptions in slot order
        panel_descs = []  # list of (role, text)
        # sort slots by reading order (top-to-bottom, left-to-right) for the prompt
        ordered = sorted(slots, key=lambda s: (round(s["y"], 3), round(s["x"], 3)))

        for s in ordered:
            sid = s["slot"]
            role = s.get("role", "element")
            x = int(s["x"] * canvas_width)
            y = int(s["y"] * canvas_height)
            w = int(s["w"] * canvas_width)
            h = int(s["h"] * canvas_height)
            if panel_gap > 0:
                x += panel_gap // 2
                y += panel_gap // 2
                w = max(1, w - panel_gap)
                h = max(1, h - panel_gap)

            img = slot_image(sid)
            if img is not None:
                fitted = _fit_into(w, h, img, fit_mode)
                canvas.paste(fitted, (x, y))
                preview.paste(fitted, (x, y))

            # label on preview only
            if preview_labels:
                tag = f"{sid}:{role}" if sid != 0 else "0:location"
                draw.rectangle([x, y, x + w - 1, y + h - 1], outline=(255, 0, 0), width=2)
                draw.text((x + 6, y + 6), tag, fill=(255, 0, 0), font=font)

            # description: manual first, else auto-caption
            manual = slot_manual_desc(sid)
            if manual:
                text = manual
            elif img is not None:
                cap, err = caption_image(
                    img, vision_backend, vision_model, caption_prompt,
                    vision_api_key, vision_base_url,
                )
                text = cap if cap else (f"[{role}]" if not err else f"[caption failed: {err}]")
            else:
                text = ""  # empty slot, skip in prompt

            if text:
                panel_descs.append((role, text))

        # assemble the trained-format prompt parts
        if panel_descs:
            joined = "; ".join(t for _, t in panel_descs)
            reference_sheet_prompt = f"Reference sheet: {joined}"
        else:
            reference_sheet_prompt = "Reference sheet: "

        generated_video_prompt = f"Generated video: {generated_video_action.strip()}"

        return (
            _pil_to_tensor(canvas),
            reference_sheet_prompt,
            generated_video_prompt,
            CARD_NEGATIVE,
            _pil_to_tensor(preview),
        )
