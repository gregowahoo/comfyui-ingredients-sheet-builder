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

Defaults follow the model card: the Ingredients model was trained at 768x448.
You can raise the resolution for more panel detail, but the sheet should match
your output video resolution (downscale factor 1).

Outputs:
  - sheet_image  : the composite sheet (wire to your loop-to-video / IC-LoRA ref)
  - full_prompt  : the assembled "Reference Sheet Description" + "Target Description"
  - reference_sheet_prompt : just the reference-sheet description part
  - generated_video_prompt : just the action/target part
  - negative_prompt : the suggested negative
  - labeled_preview : same sheet with panel numbers drawn on (for your eyes only;
                      never feed this to the model)

Wire a caption per panel into the desc_* inputs (type it, or wire a text node).
"""

import numpy as np
import torch
from PIL import Image, ImageDraw, ImageFont

MAX_PANELS = 6  # characters / props (slot 0 is the location, handled separately)
CARD_NEGATIVE = "worst quality, inconsistent motion, blurry, jittery, distorted"

# Model card spec (Lightricks LTX-2.3-22b-IC-LoRA-Ingredients): trained at 768x448.
SPEC_W, SPEC_H = 768, 448

# Default standing instructions for the captioning/LLM node that writes the
# Target Description. Editable on the node and exposed as an output socket.
DEFAULT_SYSTEM_PROMPT = (
    "You are writing ONLY the \"### Target Description\" section (the action/video prompt) "
    "for an LTX-2.3 IC-LoRA Ingredients video.\n\n"
    "You are looking at a REFERENCE SHEET image. It has two zones:\n"
    "1. CHARACTER PANELS - the individual figure shots (the top row). These show the MAIN "
    "CHARACTER. Take ALL of the character's appearance details (hair, skin, clothing/armor, "
    "distinguishing features) ONLY from these panels.\n"
    "2. LOCATION / SETTING panel - the wide environment shot (the full-width band). This is the "
    "BACKGROUND only. Use it for the setting and atmosphere. NEVER take the main character's "
    "appearance from it, and IGNORE any background people, crowds, or bystanders in it.\n\n"
    "Expand the ROUGH ACTION IDEA below into ONE polished, flowing cinematic action description, "
    "about 4-7 sentences, that:\n"
    "- Opens with \"From the first frame...\" with the character already in motion.\n"
    "- Features the EXACT main character from the character panels - restate their key appearance "
    "details so identity holds.\n"
    "- Sets the action in the SAME location shown in the setting panel.\n"
    "- Describes concrete physical motion with weight and direction.\n"
    "- Includes camera movement (tracking, push-in, arc, whip-pan) fitting the mood.\n"
    "- Ends with lighting/atmosphere matching the sheet.\n\n"
    "Output ONLY the action prose, beginning directly with \"From the first frame\". "
    "Do NOT write any header."
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


def _build_char_band(panel_imgs, W, band_h, gap):
    """Lay panels in one row, each shown WHOLE at its true aspect ratio (never
    cropped, never squished). Panels sit centered on a black background band of
    exactly W x band_h. Per the model card, a black background behind cleanly
    separated panels is the intended layout. If the row is wider than W, the
    whole row scales down uniformly to fit. Returns (PIL image, [(x, w)] rects)."""
    n = len(panel_imgs)
    if n == 0 or band_h <= 0:
        return Image.new("RGB", (W, max(1, band_h)), (0, 0, 0)), []

    # each panel to band_h tall at true aspect (whole panel, no crop)
    sized = []
    for im in panel_imgs:
        iw, ih = im.size
        w = max(1, int(round(iw * (band_h / ih)))) if ih else band_h
        sized.append(im.resize((w, band_h), Image.LANCZOS))

    gaps_total = gap * (n - 1)
    row_w = sum(s.size[0] for s in sized) + gaps_total

    # if the row is too wide for W, scale everything down uniformly so it fits
    panel_h = band_h
    if row_w > W:
        f = W / row_w
        panel_h = max(1, int(round(band_h * f)))
        sized = []
        for im in panel_imgs:
            iw, ih = im.size
            w = max(1, int(round(iw * (panel_h / ih)))) if ih else panel_h
            sized.append(im.resize((w, panel_h), Image.LANCZOS))
        gaps_total = gap * (n - 1)
        row_w = sum(s.size[0] for s in sized) + gaps_total

    # center the row horizontally and vertically on a black band
    band = Image.new("RGB", (W, band_h), (0, 0, 0))
    x = max(0, (W - row_w) // 2)
    y = max(0, (band_h - panel_h) // 2)
    rects = []
    for s in sized:
        band.paste(s, (x, y))
        rects.append((x, s.size[0]))
        x += s.size[0] + gap
    return band, rects


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
            "location_desc": ("STRING", {"multiline": True, "default": "",
                              "tooltip": "Description of the location panel."}),
        }
        for i in range(1, MAX_PANELS + 1):
            optional[f"image_{i}"] = ("IMAGE", {"tooltip": f"Character or prop {i}. "
                                     f"To leave it out, mute its Load Image node."})
            optional[f"desc_{i}"] = ("STRING", {"multiline": True, "default": "",
                                     "tooltip": f"Description of panel {i}."})
        return {
            "required": {
                "output_width": ("INT", {"default": SPEC_W, "min": 64, "max": 4096, "step": 8,
                                 "tooltip": "Sheet width. Match your OUTPUT VIDEO width. "
                                            "The model was trained at 768x448 — staying near "
                                            "that aspect ratio (~16:9) is safest. Larger = more "
                                            "panel detail but further from the trained size."}),
                "output_height": ("INT", {"default": SPEC_H, "min": 64, "max": 4096, "step": 8,
                                  "tooltip": "Sheet height. Match your OUTPUT VIDEO height. "
                                             "Trained value is 448."}),
                "location_position": (["bottom", "top"], {"default": "bottom",
                                      "tooltip": "Put the full-width location band at the "
                                                 "bottom or top of the sheet."}),
                "panel_gap": ("INT", {"default": 0, "min": 0, "max": 64, "step": 1,
                              "tooltip": "Pixels of gap between panels. 0 = edge-to-edge."}),
                "llm_system_prompt": ("STRING", {"multiline": True, "default": DEFAULT_SYSTEM_PROMPT,
                                      "tooltip": "Standing instructions for your captioning/LLM node "
                                                 "(how to write the Target Description). Editable here, "
                                                 "and also exposed as the 'llm_system_prompt' output so "
                                                 "you can wire it into your Generate Text node. Convert "
                                                 "to an input if you'd rather feed it from elsewhere."}),
                "action_idea": ("STRING", {"multiline": True,
                                "default": "the character walks forward through the scene, cinematic lighting",
                                "tooltip": "Your rough action idea. The LLM expands this into the polished "
                                           "Target Description. Exposed as the 'action_idea' output too."}),
                "show_panel_numbers": ("BOOLEAN", {"default": False,
                                       "tooltip": "Draw panel numbers on the labeled_preview output "
                                                  "(never on the real sheet)."}),
            },
            "optional": optional,
        }

    RETURN_TYPES = ("IMAGE", "STRING", "STRING", "STRING", "STRING", "IMAGE", "STRING", "STRING")
    RETURN_NAMES = ("sheet_image", "full_prompt", "reference_sheet_prompt",
                    "generated_video_prompt", "negative_prompt", "labeled_preview",
                    "llm_system_prompt", "action_idea")
    FUNCTION = "build"
    CATEGORY = "Ingredients"
    DESCRIPTION = ("Builds a single LTX-2.3 IC-LoRA Ingredients reference sheet: character/prop "
                   "panels in a top row at native shape (no crop, no black bars), plus a "
                   "full-width location band. Mute a Load Image node to drop that panel.")

    def build(self, output_width, output_height, location_position, panel_gap,
              llm_system_prompt, action_idea, show_panel_numbers, **kwargs):
        gap = max(0, int(panel_gap))
        W = max(64, int(output_width))
        H = max(64, int(output_height))

        # ---- gather whatever is actually wired in -------------------------- #
        panels = []  # (slot_index, pil_image, desc)
        for i in range(1, MAX_PANELS + 1):
            im = _tensor_to_pil(kwargs.get(f"image_{i}"))
            if im is not None:
                panels.append((i, im, (kwargs.get(f"desc_{i}") or "").strip()))
        loc_img = _tensor_to_pil(kwargs.get("location_image"))
        loc_desc = (kwargs.get("location_desc") or "").strip()

        # ---- lay out the sheet: character band + location band ------------- #
        # Each band fills the FULL WIDTH and an exact height; the two heights sum
        # to H, so the canvas is always completely filled (never any black gap).
        # Bands use cover-crop, so they never pad with black internally either.
        canvas = Image.new("RGB", (W, H), (0, 0, 0))
        char_rects = []   # (slot, x, y, w, h, desc) for labels/prompt
        char_y = 0
        loc_y = 0
        loc_h = 0

        if panels and loc_img is not None:
            char_h = int(round(H * 0.60))
            loc_h = H - char_h
        elif panels:
            char_h = H
            loc_h = 0
        else:
            char_h = 0
            loc_h = H

        # build the character band using the proven row builder
        char_band = None
        if panels and char_h > 0:
            panel_imgs = [im for _, im, _ in panels]
            char_band, rects = _build_char_band(panel_imgs, W, char_h, gap)
            for (slot, _, desc), (x, w) in zip(panels, rects):
                char_rects.append((slot, x, 0, w, char_h, desc))

        # build the location band, covering W x loc_h exactly
        loc_band = None
        if loc_img is not None and loc_h > 0:
            loc_band = _cover(loc_img, W, loc_h)

        # paste the bands; their heights sum to H so the canvas is fully covered
        if char_band is not None and loc_band is not None:
            if location_position == "top":
                canvas.paste(loc_band, (0, 0)); loc_y = 0
                canvas.paste(char_band, (0, loc_h)); char_y = loc_h
            else:
                canvas.paste(char_band, (0, 0)); char_y = 0
                canvas.paste(loc_band, (0, char_h)); loc_y = char_h
        elif char_band is not None:
            canvas.paste(char_band, (0, 0)); char_y = 0
        elif loc_band is not None:
            canvas.paste(loc_band, (0, 0)); loc_y = 0

        # ---- labeled preview ----------------------------------------------- #
        preview = canvas.copy()
        if show_panel_numbers:
            d = ImageDraw.Draw(preview)
            f = _font(max(16, char_h // 14) if char_h else 20)
            for idx, (slot, x, _y, w, h, _desc) in enumerate(char_rects):
                d.text((x + 6, char_y + 6), str(slot), fill=(255, 0, 0), font=f)
            if loc_band is not None:
                ly = 0 if location_position == "top" else (H - loc_h)
                d.text((6, ly + 6), "location", fill=(0, 180, 255), font=f)

        # ---- assemble the prompt ------------------------------------------- #
        lines = []
        n = len(char_rects)
        for idx, (slot, _x, _y, _w, _h, desc) in enumerate(char_rects):
            if desc:
                lines.append(f"**{_pos_label(idx, n)} (Character):** {desc}")
        if loc_img is not None and loc_desc:
            where = "Top" if location_position == "top" else "Bottom"
            lines.append(f"**Full-Width {where} (Location):** {loc_desc}")

        ref_block = "### Reference Sheet Description\n" + ("\n".join(lines) if lines else "")
        gen_block = "### Target Description\n" + action_idea.strip()
        full_prompt = ref_block.rstrip() + "\n\n" + gen_block

        return (
            _pil_to_tensor(canvas),
            full_prompt,
            ref_block,
            gen_block,
            CARD_NEGATIVE,
            _pil_to_tensor(preview),
            llm_system_prompt,
            action_idea,
        )


NODE_CLASS_MAPPINGS = {"IngredientsSheetBuilder": IngredientsSheetBuilder}
NODE_DISPLAY_NAME_MAPPINGS = {"IngredientsSheetBuilder": "Ingredients Sheet Builder"}
