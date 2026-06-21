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
from ._packers import free_pack, autofit_rows, position_name_packed, add_full_width_band

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
                "layout_mode": (["Template (fixed grid)",
                                 "Auto-fit rows (no crop)",
                                 "Free pack (no crop)"],
                                {"default": "Template (fixed grid)",
                                 "tooltip": "Template = exact grid, may crop/pad to fit panels. "
                                            "Auto-fit rows = images keep native shape, lined up by "
                                            "row, never cropped. Free pack = images flow left-to-right "
                                            "and wrap, never cropped. Use the no-crop modes when "
                                            "keeping the whole character matters more than sheet shape."}),
                "template": (TEMPLATE_NAMES + ["Custom"], {"default": TEMPLATE_NAMES[0],
                              "label": "[GRID] template",
                              "tooltip": "Used when layout_mode = Template (fixed grid)."}),
                "canvas_width": ("INT", {"default": 1920, "min": 64, "max": 8192, "step": 8,
                                         "label": "canvas_width  (GRID: exact / NO-CROP: max width)",
                                         "tooltip": "Template mode: exact canvas size (match output res). "
                                                    "No-crop modes: used as the max width before wrapping."}),
                "canvas_height": ("INT", {"default": 1080, "min": 64, "max": 8192, "step": 8,
                                          "label": "[GRID] canvas_height",
                                          "tooltip": "Template mode: exact canvas height. "
                                                     "No-crop modes: ignored (height grows to fit)."}),
                "row_target_height": ("INT", {"default": 560, "min": 64, "max": 4096, "step": 8,
                                              "label": "[NO-CROP] row_target_height",
                                              "tooltip": "No-crop modes only: height each image/row is "
                                                         "scaled to. Bigger = larger panels + taller sheet."}),
                "background_color": (["black", "white"], {"default": "black", "label": "background_color  (all modes)"}),
                "fit_mode": (["crop_fill", "fit_pad"], {"default": "crop_fill",
                              "label": "[GRID] fit_mode",
                              "tooltip": "Template mode only. crop_fill fills panels (may crop); "
                                         "fit_pad shows whole image with padding. No-crop modes "
                                         "ignore this (they never crop)."}),
                "panel_gap": ("INT", {"default": 0, "min": 0, "max": 128, "step": 1,
                                      "label": "panel_gap  (all modes)",
                                      "tooltip": "Gap between panels in pixels."}),
                "generated_video_action": ("STRING", {
                    "multiline": True,
                    "default": "the character walks forward through the scene, cinematic lighting",
                    "label": "generated_video_action  (all modes)",
                    "tooltip": "Action text for the '### Target Description' prompt part.",
                }),
                "preview_labels": ("BOOLEAN", {"default": False,
                                               "label": "preview_labels  (all modes)",
                                               "tooltip": "Draw panel numbers on a SEPARATE preview image. "
                                                          "Never baked into the sheet you feed the LoRA."}),
                "row_assignment": ("STRING", {
                    "default": "",
                    "label": "[AUTO-FIT ROWS] row_assignment (optional)",
                    "tooltip": "Auto-fit rows mode: OPTIONAL grouping of images into rows. "
                               "Commas group a row, '|' starts a new row, e.g. '1,2,3 | 4,5'. "
                               "Leave BLANK to put all wired images in one row. Any wired image "
                               "you don't list is added automatically — nothing is ever skipped. "
                               "Location spans full-width separately when location_full_width is on."}),
                "location_full_width": ("BOOLEAN", {"default": True,
                                "label": "[NO-CROP] location_full_width",
                                "tooltip": "No-crop modes: always span the background/location image "
                                           "across the full width of the sheet as its own band, no "
                                           "matter how many other images. Ignored in Template mode."}),
                "location_band_position": (["bottom", "top"], {"default": "bottom",
                                "label": "[NO-CROP] location_band_position",
                                "tooltip": "Where the full-width location band sits when "
                                           "location_full_width is on."}),
                "layout_json": ("STRING", {
                    "multiline": True,
                    "default": ('[\n'
                                '  {"slot": 0, "x": 0.0, "y": 0.55, "w": 1.0, "h": 0.45, "role": "location"},\n'
                                '  {"slot": 1, "x": 0.0, "y": 0.0, "w": 0.5, "h": 0.55, "role": "character"},\n'
                                '  {"slot": 2, "x": 0.5, "y": 0.0, "w": 0.5, "h": 0.55, "role": "character"}\n'
                                ']'),
                    "label": "[GRID: Custom] layout_json",
                    "tooltip": "Used only when template = Custom (Template mode). Normalized (0-1) rects.",
                }),
            },
            "optional": optional,
        }

    RETURN_TYPES = ("IMAGE", "STRING", "STRING", "STRING", "STRING", "IMAGE", "IMAGE")
    RETURN_NAMES = ("sheet_image", "full_prompt", "reference_sheet_prompt",
                    "generated_video_prompt", "negative_prompt", "labeled_preview", "layout_map")
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

    def build(self, layout_mode, template, canvas_width, canvas_height, row_target_height,
              background_color, fit_mode, panel_gap, generated_video_action, preview_labels,
              row_assignment="", location_full_width=True, location_band_position="bottom",
              layout_json="", **kwargs):

        bg_rgb = (0, 0, 0) if background_color == "black" else (255, 255, 255)

        def slot_image(sid):
            if sid == 0:
                return _tensor_to_pil(kwargs.get("background"))
            return _tensor_to_pil(kwargs.get(f"image_{sid}"))

        def slot_desc(sid):
            if sid == 0:
                return (kwargs.get("background_desc") or "").strip()
            return (kwargs.get(f"desc_{sid}") or "").strip()

        def slot_role(sid):
            if sid == 0:
                return "location"
            return "character"

        # ----------------------------------------------------------------- #
        # NO-CROP MODES (A free pack / B auto-fit rows)
        # ----------------------------------------------------------------- #
        if layout_mode in ("Auto-fit rows (no crop)", "Free pack (no crop)"):
            gap = max(panel_gap, 6)
            have_bg = slot_image(0) is not None
            span_location = bool(location_full_width) and have_bg

            if layout_mode == "Free pack (no crop)":
                # gather present images; skip bg here if it will be a full-width band
                items = []
                if have_bg and not span_location:
                    items.append((0, slot_role(0), slot_image(0)))
                for i in range(1, MAX_SLOTS + 1):
                    im = slot_image(i)
                    if im is not None:
                        items.append((i, slot_role(i), im))
                placed, cw, ch = free_pack(items, target_h=row_target_height,
                                           max_width=canvas_width, gap=gap)
            else:
                # Auto-fit rows: parse row_assignment like "1,2,3 | 4,5".
                # Track which slots got placed so we can auto-append any wired
                # image the user forgot to list (no image silently disappears).
                rows_items = []
                listed = set()
                spec = row_assignment.strip() or "1,2,3"
                for chunk in spec.split("|"):
                    row = []
                    for tok in chunk.split(","):
                        tok = tok.strip()
                        if not (tok.lstrip("-").isdigit()):
                            continue
                        sid = int(tok)
                        listed.add(sid)
                        if sid == 0 and span_location:
                            continue  # handled as full-width band below
                        im = slot_image(sid)
                        if im is not None:
                            row.append((sid, slot_role(sid), im))
                    if row:
                        rows_items.append(row)
                # auto-include any wired image NOT mentioned in row_assignment,
                # so nothing vanishes just because it wasn't listed.
                leftovers = []
                for i in range(1, MAX_SLOTS + 1):
                    if i in listed:
                        continue
                    im = slot_image(i)
                    if im is not None:
                        leftovers.append((i, slot_role(i), im))
                if leftovers:
                    rows_items.append(leftovers)
                # if nothing left (e.g. only bg), give a minimal width to anchor the band
                if rows_items:
                    placed, cw, ch = autofit_rows(rows_items, row_height=row_target_height,
                                                  max_width=max(canvas_width, 256), gap=gap)
                else:
                    placed, cw, ch = [], max(canvas_width, 256), 0

            # add the location as a full-width band spanning the whole sheet.
            # Ensure the sheet is a sensible width: at least the location's own
            # natural width at row height, and not absurdly narrow for few chars.
            if span_location:
                bg_img = slot_image(0)
                biw, bih = bg_img.size
                bg_aspect = biw / bih if bih else 1.0
                # candidate widths: current char-row width, location at row height,
                # and a floor so a single character doesn't make a tiny sheet.
                loc_natural_w = int(round(row_target_height * bg_aspect))
                target_w = max(cw, loc_natural_w, min(canvas_width, 1280))
                # re-center existing character rows to target_w
                if placed and target_w > cw:
                    # shift each rect so its row is centered in target_w
                    rows_by_y = {}
                    for p in placed:
                        rows_by_y.setdefault(p["y"], []).append(p)
                    recentered = []
                    for yk, row in rows_by_y.items():
                        row_sorted = sorted(row, key=lambda q: q["x"])
                        row_w = (row_sorted[-1]["x"] + row_sorted[-1]["w"]) - row_sorted[0]["x"]
                        offset = (target_w - row_w) // 2 - row_sorted[0]["x"]
                        for q in row_sorted:
                            nq = dict(q); nq["x"] = q["x"] + offset
                            recentered.append(nq)
                    placed = recentered
                cw = target_w
                placed, cw, ch = add_full_width_band(
                    placed, cw, bg_img, 0, slot_role(0),
                    at_bottom=(location_band_position == "bottom"), gap=gap)

            canvas = Image.new("RGB", (cw, ch), bg_rgb)
            preview = canvas.copy()
            pdraw = ImageDraw.Draw(preview)
            pfont = _font(max(16, row_target_height // 18))

            panel_lines = []
            # reading order: top-to-bottom, left-to-right
            for p in sorted(placed, key=lambda q: (q["y"], q["x"])):
                img = slot_image(p["slot"])
                if img is None:
                    continue
                resized = img.resize((max(1, p["w"]), max(1, p["h"])), Image.LANCZOS)
                canvas.paste(resized, (p["x"], p["y"]))
                preview.paste(resized, (p["x"], p["y"]))
                pos = position_name_packed(p, placed)
                if preview_labels:
                    pdraw.rectangle([p["x"], p["y"], p["x"]+p["w"]-1, p["y"]+p["h"]-1],
                                    outline=(255, 0, 0), width=3)
                    pdraw.text((p["x"]+6, p["y"]+6), f"{p['slot']}:{pos}", fill=(255, 0, 0), font=pfont)
                desc = slot_desc(p["slot"])
                if desc:
                    panel_lines.append(f"**{pos} ({role_label(p['role'])}):** {desc}")

            ref_block = ("### Reference Sheet Description\n" + "\n".join(panel_lines)
                         if panel_lines else "### Reference Sheet Description\n")
            gen_block = "### Target Description\n" + generated_video_action.strip()
            full_prompt = ref_block.rstrip() + "\n\n" + gen_block
            layout_map = self._render_layout_map_packed(placed, cw, ch)
            return (_pil_to_tensor(canvas), full_prompt, ref_block, gen_block, CARD_NEGATIVE,
                    _pil_to_tensor(preview), _pil_to_tensor(layout_map))

        # ----------------------------------------------------------------- #
        # TEMPLATE MODE (original fixed-rectangle behavior)
        # ----------------------------------------------------------------- #
        slots = self._resolve_layout(template, layout_json)

        canvas = Image.new("RGB", (canvas_width, canvas_height), bg_rgb)
        preview = canvas.copy()
        draw = ImageDraw.Draw(preview)
        font = _font(max(16, canvas_height // 40))

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
        full_prompt = reference_sheet_prompt.rstrip() + "\n\n" + generated_video_prompt

        layout_map = self._render_layout_map(slots, canvas_width, canvas_height)

        return (
            _pil_to_tensor(canvas),
            full_prompt,
            reference_sheet_prompt,
            generated_video_prompt,
            CARD_NEGATIVE,
            _pil_to_tensor(preview),
            _pil_to_tensor(layout_map),
        )

    def _render_layout_map_packed(self, placed, w, h):
        """Diagram for packed modes: colored rects at their packed positions."""
        img = Image.new("RGB", (max(1, w), max(1, h)), (24, 24, 28))
        draw = ImageDraw.Draw(img)
        f = _font(max(16, h // 30))
        for p in placed:
            col = _ROLE_COLORS.get(p.get("role", "element"), (110, 90, 130))
            draw.rectangle([p["x"]+4, p["y"]+4, p["x"]+p["w"]-4, p["y"]+p["h"]-4],
                           fill=col, outline=(230, 230, 230), width=2)
            pos = position_name_packed(p, placed)
            draw.multiline_text((p["x"]+12, p["y"]+12), f"#{p['slot']} {p.get('role','')}\n{pos}",
                                fill=(245, 245, 245), font=f, spacing=3)
        return img
