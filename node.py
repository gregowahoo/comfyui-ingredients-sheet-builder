"""
Ingredients Sheet Builder (V2) - the prep step for the LTX-2.3 IC-LoRA
Ingredients workflow.

V2 changes vs V1:
  - Internal vision/Ollama captioning REMOVED. Captioning is now external:
    wire a TextGenerate (or any STRING-producing) node per panel into the
    desc_* inputs. Type them manually, or leave empty to skip a panel.
  - Prompt assembled in the trained positional format:
        **Top Row Left (Character):** <caption>
    computed from each panel's layout position + role.
  - Default canvas 1920x1080 (set to match your output video resolution;
    reference downscale factor is 1).
  - New presets where the location spans a full row (top or bottom).
  - layout_preview output: a numbered diagram of the chosen template so you can
    see the layout without click-selecting (visualization aid).

Node category: Ingredients/
"""

import json
import numpy as np
import torch
from PIL import Image, ImageDraw, ImageFont

from .templates import (
    TEMPLATES, TEMPLATE_NAMES, get_template, max_slot_in_templates,
    position_name, role_label,
)

MAX_SLOTS = max(9, max_slot_in_templates())
CARD_NEGATIVE = "worst quality, inconsistent motion, blurry, jittery, distorted"

_ROLE_COLORS = {
    "location": (60, 90, 140),
    "character": (150, 70, 70),
    "face": (150, 110, 60),
    "prop": (70, 130, 90),
    "element": (110, 90, 130),
}


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
    return torch.from_numpy(arr)[None, ...]


def _fit_into(cell_w, cell_h, img, mode):
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


def _font(size):
    try:
        return ImageFont.truetype("arial.ttf", size)
    except Exception:
        try:
            return ImageFont.truetype("DejaVuSans.ttf", size)
        except Exception:
            return ImageFont.load_default()


class IngredientsSheetBuilder:

    @classmethod
    def INPUT_TYPES(cls):
        optional = {
            "background": ("IMAGE", {"tooltip": "Location/environment panel (slot 0)."}),
            "background_desc": ("STRING", {
                "multiline": True, "default": "",
                "tooltip": "Description for the location panel. Type it, OR wire a "
                           "TextGenerate output in (right-click > Convert to input).",
            }),
        }
        for i in range(1, MAX_SLOTS + 1):
            optional[f"image_{i}"] = ("IMAGE",)
            optional[f"desc_{i}"] = ("STRING", {
                "multiline": True, "default": "",
                "tooltip": f"Description for panel {i}. Type it, OR wire a TextGenerate "
                           f"output in (right-click > Convert to input). Empty + no image "
                           f"= panel skipped.",
            })

        return {
            "required": {
                "template": (TEMPLATE_NAMES + ["Custom"], {"default": TEMPLATE_NAMES[0]}),
                "canvas_width": ("INT", {"default": 1920, "min": 64, "max": 8192, "step": 8,
                                         "tooltip": "Set to match your OUTPUT video resolution "
                                                    "(reference downscale factor = 1)."}),
                "canvas_height": ("INT", {"default": 1080, "min": 64, "max": 8192, "step": 8}),
                "background_color": (["black", "white"], {"default": "black"}),
                "fit_mode": (["crop_fill", "fit_pad"], {"default": "crop_fill"}),
                "panel_gap": ("INT", {"default": 0, "min": 0, "max": 128, "step": 1,
                                      "tooltip": "Gap between panels in pixels. Keep 0 for IC-LoRA."}),
                "generated_video_action": ("STRING", {
                    "multiline": True,
                    "default": "the character walks forward through the scene, cinematic lighting",
                    "tooltip": "Action text for the 'Generated video:' prompt part.",
                }),
                "preview_labels": ("BOOLEAN", {"default": False,
                                               "tooltip": "Draw panel numbers on a SEPARATE preview image. "
                                                          "Never baked into the sheet you feed the LoRA."}),
                "layout_json": ("STRING", {
                    "multiline": True,
                    "default": ('[\n'
                                '  {"slot": 0, "x": 0.0, "y": 0.55, "w": 1.0, "h": 0.45, "role": "location"},\n'
                                '  {"slot": 1, "x": 0.0, "y": 0.0, "w": 0.5, "h": 0.55, "role": "character"},\n'
                                '  {"slot": 2, "x": 0.5, "y": 0.0, "w": 0.5, "h": 0.55, "role": "character"}\n'
                                ']'),
                    "tooltip": "Used only when template = Custom. Normalized (0-1) rects. "
                               "slot 0 = background/location input.",
                }),
            },
            "optional": optional,
        }

    RETURN_TYPES = ("IMAGE", "STRING", "STRING", "STRING", "IMAGE", "IMAGE")
    RETURN_NAMES = ("sheet_image", "reference_sheet_prompt", "generated_video_prompt",
                    "negative_prompt", "labeled_preview", "layout_map")
    FUNCTION = "build"
    CATEGORY = "Ingredients"
    DESCRIPTION = ("Prep step for the LTX-2.3 IC-LoRA Ingredients workflow. Composes a "
                   "reference sheet from your images and assembles the trained-format "
                   "'Reference sheet:' / 'Generated video:' prompt. Caption each panel "
                   "externally (e.g. a TextGenerate per panel) into the desc_* inputs.")

    # ------------------------------------------------------------------ #
    def _resolve_layout(self, template, layout_json):
        if template == "Custom":
            try:
                slots = json.loads(layout_json) if layout_json.strip() else []
            except json.JSONDecodeError as e:
                raise ValueError(f"Custom layout_json is not valid JSON: {e}")
            return slots
        return get_template(template) or []

    def _render_layout_map(self, slots, w, h):
        """A standalone diagram of the layout: colored numbered rects on dark."""
        img = Image.new("RGB", (w, h), (24, 24, 28))
        draw = ImageDraw.Draw(img)
        f = _font(max(18, h // 30))
        for s in slots:
            sid = s["slot"]
            role = s.get("role", "element")
            x = int(s["x"] * w); y = int(s["y"] * h)
            cw = int(s["w"] * w); ch = int(s["h"] * h)
            col = _ROLE_COLORS.get(role, (110, 90, 130))
            draw.rectangle([x + 4, y + 4, x + cw - 4, y + ch - 4], fill=col, outline=(230, 230, 230), width=2)
            pos = position_name(s, slots)
            tag = f"#{sid}  {role}\n{pos}"
            draw.multiline_text((x + 14, y + 14), tag, fill=(245, 245, 245), font=f, spacing=4)
        return img

    def build(self, template, canvas_width, canvas_height, background_color, fit_mode,
              panel_gap, generated_video_action, preview_labels, layout_json="",
              **kwargs):

        slots = self._resolve_layout(template, layout_json)

        bg_rgb = (0, 0, 0) if background_color == "black" else (255, 255, 255)
        canvas = Image.new("RGB", (canvas_width, canvas_height), bg_rgb)
        preview = canvas.copy()
        draw = ImageDraw.Draw(preview)
        font = _font(max(16, canvas_height // 40))

        def slot_image(sid):
            if sid == 0:
                return _tensor_to_pil(kwargs.get("background"))
            return _tensor_to_pil(kwargs.get(f"image_{sid}"))

        def slot_desc(sid):
            if sid == 0:
                return (kwargs.get("background_desc") or "").strip()
            return (kwargs.get(f"desc_{sid}") or "").strip()

        # order slots in reading order for the prompt
        ordered = sorted(slots, key=lambda s: (round(s["y"], 3), round(s["x"], 3)))

        panel_lines = []
        for s in ordered:
            sid = s["slot"]
            role = s.get("role", "element")
            x = int(s["x"] * canvas_width)
            y = int(s["y"] * canvas_height)
            w = int(s["w"] * canvas_width)
            h = int(s["h"] * canvas_height)
            if panel_gap > 0:
                x += panel_gap // 2; y += panel_gap // 2
                w = max(1, w - panel_gap); h = max(1, h - panel_gap)

            img = slot_image(sid)
            if img is not None:
                fitted = _fit_into(w, h, img, fit_mode)
                canvas.paste(fitted, (x, y))
                preview.paste(fitted, (x, y))

            if preview_labels:
                pos = position_name(s, slots)
                tag = f"{sid}:{pos}"
                draw.rectangle([x, y, x + w - 1, y + h - 1], outline=(255, 0, 0), width=2)
                draw.text((x + 6, y + 6), tag, fill=(255, 0, 0), font=font)

            desc = slot_desc(sid)
            if desc:
                pos = position_name(s, slots)
                rl = role_label(role)
                panel_lines.append(f"**{pos} ({rl}):** {desc}")

        if panel_lines:
            ref_block = "### Reference Sheet Description\n" + "\n".join(panel_lines)
        else:
            ref_block = "### Reference Sheet Description\n"

        reference_sheet_prompt = ref_block
        generated_video_prompt = "### Target Description\n" + generated_video_action.strip()

        layout_map = self._render_layout_map(slots, canvas_width, canvas_height)

        return (
            _pil_to_tensor(canvas),
            reference_sheet_prompt,
            generated_video_prompt,
            CARD_NEGATIVE,
            _pil_to_tensor(preview),
            _pil_to_tensor(layout_map),
        )
