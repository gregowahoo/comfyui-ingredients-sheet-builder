"""
Ingredients Sheet Builder (V3 - clean rewrite)
================================================

One job: take your reference images and build a single composite reference
sheet for the LTX-2.3 IC-LoRA Ingredients model.

How it lays out the sheet (no modes, no choices to get wrong):
  - Every CHARACTER/PROP image you wire in is placed in ONE row across the top,
    shown WHOLE at its true aspect ratio (never cropped, never squished).
  - Panels sit centered on a black background, which is the layout the model
    card specifies ("clean panels on a black background, no text").
  - The LOCATION image spans the full width as its own band, placed at the top
    or the bottom (your choice).
  - To leave an image OUT of the sheet, just disable/mute its Load Image node.
    Whatever is wired in, appears. Whatever isn't, doesn't.

Default sheet size is ~1456x825, matching Lightricks' own example sheets.
Bigger sheets give each panel more detail and downscale cleanly into the
pipeline; the output video itself is smaller (~768x448).

Outputs:
  - sheet_image  : the composite sheet (wire to your loop-to-video / IC-LoRA ref)
  - reference_sheet_prompt : the "### Reference Sheet Description" panel text
  - reference_sheet_prompt : the panel descriptions as clean semicolon prose
  - labeled_preview : same sheet with panel numbers drawn on (for your eyes only;
                      never feed this to the model)

Wire a caption per panel into the desc_* inputs (type it, or wire a text node).
"""

import numpy as np
import torch
from PIL import Image, ImageDraw, ImageFont

MAX_PANELS = 6  # characters / props (slot 0 is the location, handled separately)
CARD_NEGATIVE = "worst quality, inconsistent motion, blurry, jittery, distorted"  # reference only; not output


# Default sheet size. NOTE: the model's *output video* bucket is 768x448, but
# Lightricks' own example reference SHEETS are larger (~1456x825) — bigger sheets
# give each panel more detail and downscale cleanly into the pipeline, which
# avoids the faint seam/banding artifacts seen with cramped small sheets. So the
# sheet default is the larger size; it is downscaled to the output res downstream.
SPEC_W, SPEC_H = 1456, 825

# Default standing instructions for the captioning/LLM node that writes the
# Target Description. Editable on the node and exposed as an output socket.
# Reference system-prompt text for the captioning/LLM node that writes the action
# prose. This is NOT used by the node anymore — keep the system prompt in its own
# Text node in your workflow (so you can edit it freely over time) and wire it into
# your Generate Text node. Paste this as a starting point. Your action_idea text is
# appended after the "ACTION IDEA: " label at the end.
DEFAULT_SYSTEM_PROMPT = (
    "You are writing the action/video prompt (the motion description) "
    "for an LTX-2.3 IC-LoRA Ingredients video.\n\n"
    "You are looking at a REFERENCE SHEET image. It has two zones:\n"
    "1. CHARACTER PANELS - the individual figure shots (the top row). These show the MAIN "
    "CHARACTER. Take ALL of the character's appearance details (hair, skin, clothing/armor, "
    "distinguishing features) ONLY from these panels.\n"
    "2. LOCATION / SETTING panel - the wide environment shot (the full-width band). This is the "
    "BACKGROUND only. Use it for the setting and atmosphere. NEVER take the main character's "
    "appearance from it, and IGNORE any background people, crowds, or bystanders in it.\n\n"
    "Your task: take the ACTION IDEA given at the very end of this message and expand THAT "
    "specific action into ONE polished, flowing cinematic description of about 4-7 sentences. "
    "The action idea is the user's instruction for what happens in the video — you MUST follow "
    "it. Do NOT invent a different action; whatever the action idea says the character is doing "
    "(walking, singing, fighting, talking, etc.) is what your description must show.\n\n"
    "The description must:\n"
    "- Open with \"From the first frame...\" with the character already performing the action.\n"
    "- Feature the EXACT main character from the character panels - restate their key appearance "
    "details so identity holds.\n"
    "- Set the action in the SAME location shown in the setting panel.\n"
    "- Describe concrete physical motion with weight and direction.\n"
    "- Include camera movement (tracking, push-in, arc, whip-pan) fitting the mood.\n"
    "- End with lighting/atmosphere matching the sheet.\n\n"
    "Output ONLY the action prose, beginning directly with \"From the first frame\". "
    "Do NOT write any header.\n\n"
    "ACTION IDEA: "
)


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


def _font(size):
    for name in ("arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _scale_to_height(img, h):
    """Resize an image to a target height, keeping aspect (never crops)."""
    w0, h0 = img.size
    if h0 <= 0:
        return img
    w = max(1, int(round(w0 * (h / h0))))
    return img.resize((w, max(1, h)), Image.LANCZOS)


def _scale_to_width(img, w):
    w0, h0 = img.size
    if w0 <= 0:
        return img
    h = max(1, int(round(h0 * (w / w0))))
    return img.resize((max(1, w), h), Image.LANCZOS)


def _build_char_band(panel_imgs, W, band_h, gap, fill_width=False):
    """Lay panels in one row, each WHOLE at true aspect (no crop, no squish),
    centered on a black band of width W. If fill_width is True, the row is scaled
    UP so its total width spans W (panels get proportionally taller — still whole,
    still undistorted); the band's height grows to match and is returned so the
    caller can lay out the rest. If the row is wider than W it always scales down
    to fit. Returns (PIL image, [(x, w)] rects, actual_band_height)."""
    n = len(panel_imgs)
    if n == 0 or band_h <= 0:
        return Image.new("RGB", (W, max(1, band_h)), (0, 0, 0)), [], max(1, band_h)

    # each panel to band_h tall at true aspect (whole panel, no crop)
    sized = []
    for im in panel_imgs:
        iw, ih = im.size
        w = max(1, int(round(iw * (band_h / ih)))) if ih else band_h
        sized.append(im.resize((w, band_h), Image.LANCZOS))

    gaps_total = gap * (n - 1)
    row_w = sum(s.size[0] for s in sized) + gaps_total
    panel_h = band_h

    avail = max(1, W - gaps_total)
    content_w = sum(s.size[0] for s in sized)
    # scale factor to make the row span the full width (up if fill_width, and
    # always down if it's too wide)
    if content_w > 0:
        f = avail / content_w
        if (fill_width and f > 1.0) or f < 1.0:
            panel_h = max(1, int(round(band_h * f)))
            sized = []
            for im in panel_imgs:
                iw, ih = im.size
                w = max(1, int(round(iw * (panel_h / ih)))) if ih else panel_h
                sized.append(im.resize((w, panel_h), Image.LANCZOS))
            gaps_total = gap * (n - 1)
            row_w = sum(s.size[0] for s in sized) + gaps_total

    out_h = panel_h  # band is exactly as tall as the (possibly rescaled) panels
    band = Image.new("RGB", (W, out_h), (0, 0, 0))
    x = max(0, (W - row_w) // 2)
    rects = []
    for s in sized:
        band.paste(s, (x, 0))
        rects.append((x, s.size[0]))
        x += s.size[0] + gap
    return band, rects, out_h


def _cover(img, w, h):
    """Scale img to COVER an exact w x h rect, center-cropping overflow.
    Never leaves black padding."""
    w = max(1, int(w)); h = max(1, int(h))
    iw, ih = img.size
    if iw <= 0 or ih <= 0:
        return Image.new("RGB", (w, h), (0, 0, 0))
    scale = max(w / iw, h / ih)
    nw, nh = max(1, int(round(iw * scale))), max(1, int(round(ih * scale)))
    r = img.resize((nw, nh), Image.LANCZOS)
    left = max(0, (nw - w) // 2)
    top = max(0, (nh - h) // 2)
    return r.crop((left, top, left + w, top + h))


def _fit_bars(img, w, h):
    """Scale img to FIT INSIDE an exact w x h rect, keeping the whole image (no
    crop). Leftover space is filled with black bars. Use this instead of _cover
    when the whole location must stay visible (e.g. a wide beach that _cover
    would crop top and bottom off of)."""
    w = max(1, int(w)); h = max(1, int(h))
    iw, ih = img.size
    if iw <= 0 or ih <= 0:
        return Image.new("RGB", (w, h), (0, 0, 0))
    scale = min(w / iw, h / ih)
    nw, nh = max(1, int(round(iw * scale))), max(1, int(round(ih * scale)))
    r = img.resize((nw, nh), Image.LANCZOS)
    out = Image.new("RGB", (w, h), (0, 0, 0))
    out.paste(r, ((w - nw) // 2, (h - nh) // 2))
    return out


def _pos_label(i, n):
    """Human-readable position name for the prompt, e.g. 'Top Row Left'."""
    if n == 1:
        return "Top Row Center"
    if i == 0:
        return "Top Row Far Left"
    if i == n - 1:
        return "Top Row Far Right"
    if n == 2:
        return "Top Row Left" if i == 0 else "Top Row Right"
    if i == 1:
        return "Top Row Left"
    if i == n - 2:
        return "Top Row Right"
    return f"Top Row Middle {i}"


class IngredientsSheetBuilder:
    @classmethod
    def INPUT_TYPES(cls):
        optional = {
            "location_image": ("IMAGE", {"tooltip": "The location / environment / set. "
                                         "Spans the full width as its own band."}),
            "location_height_percent": ("INT", {"default": 40, "min": 10, "max": 80, "step": 5,
                                        "tooltip": "How much of the sheet height the location band "
                                                   "gets (the character row fills the rest). Higher = "
                                                   "more of the location shown, less squish/crop. "
                                                   "Default 40."}),
            "location_fit_bars": ("BOOLEAN", {"default": False,
                                  "tooltip": "OFF (default): the location image fills the band "
                                             "edge-to-edge, cropping its top/bottom if needed. "
                                             "ON: show the WHOLE location image undistorted and "
                                             "fill the leftover space with black bars. Turn ON "
                                             "if your location (e.g. a wide beach) is getting "
                                             "its top and bottom cut off."}),
            "location_id": ("STRING", {"default": "",
                            "tooltip": "Optional name/ID for the location (e.g. 'the Aeterna atrium'). "
                                       "Threaded through the description so it's referred to consistently."}),
            "location_desc": ("STRING", {"multiline": True, "default": "",
                              "tooltip": "Description of the location panel."}),
        }
        for i in range(1, MAX_PANELS + 1):
            optional[f"image_{i}"] = ("IMAGE", {"tooltip": f"Character or prop {i}. "
                                     f"To leave it out, mute its Load Image node."})
            optional[f"id_{i}"] = ("STRING", {"default": "",
                                   "tooltip": f"Name/ID for panel {i} (e.g. 'Lily'). Give the SAME "
                                              f"name to every panel that shows the same character, so "
                                              f"all panels describe ONE consistent identity instead of "
                                              f"separate people. Used to tag the description and to tell "
                                              f"the captioner who this is."})
            optional[f"desc_{i}"] = ("STRING", {"multiline": True, "default": "",
                                     "tooltip": f"Description of panel {i}. If an ID is set, the "
                                                f"description is threaded with that name."})
        return {
            "required": {
                "output_width": ("INT", {"default": SPEC_W, "min": 64, "max": 4096, "step": 8,
                                 "tooltip": "Sheet width. Default 1456 matches Lightricks' own "
                                            "example sheets. Bigger sheets give each panel more "
                                            "detail and downscale cleanly (the output VIDEO is "
                                            "smaller, ~768x448). Keep the ~16:9 ratio."}),
                "output_height": ("INT", {"default": SPEC_H, "min": 64, "max": 4096, "step": 8,
                                  "tooltip": "Sheet height. Default 825 (matches the example "
                                             "sheets, ~16:9 with the width)."}),
                "location_position": (["bottom", "top"], {"default": "bottom",
                                      "tooltip": "Put the full-width location band at the "
                                                 "bottom or top of the sheet."}),
                "panel_gap": ("INT", {"default": 12, "min": 0, "max": 128, "step": 1,
                              "tooltip": "Black gap (px) between panels AND between the character "
                                         "row and the location band. A clear gap keeps the model "
                                         "from blending elements or carrying a seam into the video. "
                                         "0 = edge-to-edge (not recommended)."}),
                "show_panel_numbers": ("BOOLEAN", {"default": False,
                                       "tooltip": "Draw panel numbers on the labeled_preview output "
                                                  "(never on the real sheet)."}),
            },
            "optional": optional,
        }

    RETURN_TYPES = ("IMAGE", "STRING", "IMAGE")
    RETURN_NAMES = ("sheet_image", "reference_sheet_prompt", "labeled_preview")
    FUNCTION = "build"
    CATEGORY = "Ingredients"
    DESCRIPTION = ("Builds a single LTX-2.3 IC-LoRA Ingredients reference sheet: character/prop "
                   "panels in a top row at native shape (no crop, no black bars), plus a "
                   "full-width location band. Mute a Load Image node to drop that panel.")

    def build(self, output_width, output_height, location_position, panel_gap,
              show_panel_numbers, location_height_percent=40,
              location_fit_bars=False, **kwargs):
        gap = max(0, int(panel_gap))
        W = max(64, int(output_width))
        H = max(64, int(output_height))

        # ---- gather whatever is actually wired in -------------------------- #
        panels = []  # (slot_index, pil_image, desc, pid)
        for i in range(1, MAX_PANELS + 1):
            im = _tensor_to_pil(kwargs.get(f"image_{i}"))
            if im is not None:
                desc = (kwargs.get(f"desc_{i}") or "").strip()
                pid = (kwargs.get(f"id_{i}") or "").strip()
                panels.append((i, im, desc, pid))
        loc_img = _tensor_to_pil(kwargs.get("location_image"))
        loc_desc = (kwargs.get("location_desc") or "").strip()
        loc_id = (kwargs.get("location_id") or "").strip()

        # ---- lay out the sheet: character band + location band ------------- #
        # Build everything inside an INNER area inset by `gap` on all four sides,
        # then the outer black border equals the panel gaps and the band gap — a
        # uniform black gutter everywhere, matching Lightricks' example sheets.
        canvas = Image.new("RGB", (W, H), (0, 0, 0))
        char_rects = []   # (slot, x, y, w, h, desc) for labels/prompt
        char_y = 0
        loc_y = 0
        loc_h = 0

        inner_x = gap
        inner_y = gap
        inner_w = max(2, W - 2 * gap)   # width available inside the outer margin
        inner_h = max(2, H - 2 * gap)   # height available inside the outer margin

        if panels and loc_img is not None:
            band_gap = gap
            avail = max(2, inner_h - band_gap)
            # The location gets a GUARANTEED share of the height (the user's
            # percent). The character row fills the rest. This keeps the location
            # image from being squished/cropped down to a thin sliver when the
            # character panels happen to be tall.
            loc_pct = max(10, min(80, int(location_height_percent))) / 100.0
            loc_h = int(round(avail * loc_pct))
            char_h = avail - loc_h
        elif panels:
            band_gap = 0
            char_h = inner_h
            loc_h = 0
        else:
            band_gap = 0
            char_h = 0
            loc_h = inner_h

        # build the character band (fill the inner width so the row reaches the
        # same edges as the location band -> uniform border all around)
        char_band = None
        if panels and char_h > 0:
            panel_imgs = [im for _, im, _, _ in panels]
            char_band, rects, actual_char_h = _build_char_band(
                panel_imgs, inner_w, char_h, gap, fill_width=True)
            # the character row must not exceed its allotted height, so the
            # location keeps its guaranteed share. If filling width made the row
            # taller than its slot, rebuild without fill (panels stay whole, just
            # smaller and centered) and pin char_h to its allotment.
            if loc_img is not None:
                if actual_char_h > char_h:
                    char_band, rects, actual_char_h = _build_char_band(
                        panel_imgs, inner_w, char_h, gap, fill_width=False)
                # keep the location's guaranteed share fixed
                loc_h = inner_h - char_h - band_gap
            else:
                char_h = actual_char_h
            for (slot, _, desc, pid), (x, w) in zip(panels, rects):
                char_rects.append((slot, inner_x + x, 0, w, char_h, desc, pid))

        # build the location band, covering inner_w x loc_h exactly
        loc_band = None
        if loc_img is not None and loc_h > 0:
            loc_band = _fit_bars(loc_img, inner_w, loc_h) if location_fit_bars \
                else _cover(loc_img, inner_w, loc_h)

        # paste the bands inside the inner area, with the band gap between them.
        if char_band is not None and loc_band is not None:
            if location_position == "top":
                canvas.paste(loc_band, (inner_x, inner_y)); loc_y = inner_y
                canvas.paste(char_band, (inner_x, inner_y + loc_h + band_gap))
                char_y = inner_y + loc_h + band_gap
            else:
                canvas.paste(char_band, (inner_x, inner_y)); char_y = inner_y
                canvas.paste(loc_band, (inner_x, inner_y + char_h + band_gap))
                loc_y = inner_y + char_h + band_gap
        elif char_band is not None:
            canvas.paste(char_band, (inner_x, inner_y)); char_y = inner_y
        elif loc_band is not None:
            canvas.paste(loc_band, (inner_x, inner_y)); loc_y = inner_y

        # ---- labeled preview ----------------------------------------------- #
        preview = canvas.copy()
        if show_panel_numbers:
            d = ImageDraw.Draw(preview)
            f = _font(max(16, char_h // 14) if char_h else 20)
            for idx, (slot, x, _y, w, h, _desc, _pid) in enumerate(char_rects):
                d.text((x + 6, char_y + 6), str(slot), fill=(255, 0, 0), font=f)
            if loc_band is not None:
                ly = 0 if location_position == "top" else (H - loc_h)
                d.text((6, ly + 6), "location", fill=(0, 180, 255), font=f)

        # ---- assemble the prompt ------------------------------------------- #
        # Clean prose like the official LTX samples: descriptions joined by
        # semicolons, no headers, no position/role labels. If a panel has an ID
        # (name), thread it in so the same character is named consistently.
        def _tag(desc, pid):
            desc = desc.strip()
            if not pid:
                return desc
            if not desc:
                return pid
            # if the description doesn't already start with the name, prefix it
            if desc.lower().startswith(pid.lower()):
                return desc
            return f"{pid}: {desc}"

        parts = []
        for idx, (slot, _x, _y, _w, _h, desc, pid) in enumerate(char_rects):
            tagged = _tag(desc, pid)
            if tagged:
                parts.append(tagged)
        if loc_img is not None and (loc_desc or loc_id):
            parts.append(_tag(loc_desc, loc_id))

        ref_block = "; ".join(p for p in parts if p)

        return (
            _pil_to_tensor(canvas),
            ref_block,
            _pil_to_tensor(preview),
        )


NODE_CLASS_MAPPINGS = {"IngredientsSheetBuilder": IngredientsSheetBuilder}
NODE_DISPLAY_NAME_MAPPINGS = {"IngredientsSheetBuilder": "Ingredients Sheet Builder"}
