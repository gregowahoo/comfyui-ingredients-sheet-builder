"""
Layout templates for the Ingredients Sheet Builder.

Each template is a list of "slots". A slot is a dict:
    {
        "slot": <int>,            # which image input fills it (1..N); 0 = background/location
        "x": <float 0..1>,        # left edge as fraction of canvas width
        "y": <float 0..1>,        # top edge as fraction of canvas height
        "w": <float 0..1>,        # width as fraction of canvas width
        "h": <float 0..1>,        # height as fraction of canvas height
        "role": <str>,            # informational: "location" | "character" | "face" | "prop" | "element"
    }

Design principle from the LTX-2.3 IC-LoRA Ingredients model card:
    "Bigger panels carry over better. The more space an element takes up in the
     reference image, the more faithfully it carries over into the generated video."
So in every template the LOCATION panel and the PRIMARY CHARACTER panel get the
most real estate; secondary elements (faces, props) get smaller panels.

Coordinates are normalized (0..1) so templates are resolution-independent.
The "Custom" template is handled separately by reading the layout_json widget.
"""

# Slot 0 is conventionally the background/location panel.
# Every other slot is a numbered element image input.

TEMPLATES = {
    # ------------------------------------------------------------------ #
    # 1. Single character turnaround + location
    "1 char + location": [
        {"slot": 0, "x": 0.50, "y": 0.00, "w": 0.50, "h": 1.00, "role": "location"},
        {"slot": 1, "x": 0.00, "y": 0.00, "w": 0.50, "h": 1.00, "role": "character"},
    ],

    # 2. Character turnaround + face close-up + location
    "char + face + location": [
        {"slot": 0, "x": 0.62, "y": 0.00, "w": 0.38, "h": 1.00, "role": "location"},
        {"slot": 1, "x": 0.00, "y": 0.00, "w": 0.38, "h": 1.00, "role": "character"},
        {"slot": 2, "x": 0.38, "y": 0.00, "w": 0.24, "h": 1.00, "role": "face"},
    ],

    # 3. Classic 1x3 row (e.g. left / front / right) - equal panels
    "1x3 row": [
        {"slot": 1, "x": 0.00, "y": 0.00, "w": 0.3333, "h": 1.00, "role": "character"},
        {"slot": 2, "x": 0.3333, "y": 0.00, "w": 0.3333, "h": 1.00, "role": "character"},
        {"slot": 3, "x": 0.6666, "y": 0.00, "w": 0.3334, "h": 1.00, "role": "character"},
    ],

    # 4. 1x5 row (full 5-angle turnaround)
    "1x5 row": [
        {"slot": 1, "x": 0.00, "y": 0.00, "w": 0.20, "h": 1.00, "role": "character"},
        {"slot": 2, "x": 0.20, "y": 0.00, "w": 0.20, "h": 1.00, "role": "character"},
        {"slot": 3, "x": 0.40, "y": 0.00, "w": 0.20, "h": 1.00, "role": "character"},
        {"slot": 4, "x": 0.60, "y": 0.00, "w": 0.20, "h": 1.00, "role": "character"},
        {"slot": 5, "x": 0.80, "y": 0.00, "w": 0.20, "h": 1.00, "role": "character"},
    ],

    # 5. 2x2 grid
    "2x2 grid": [
        {"slot": 1, "x": 0.00, "y": 0.00, "w": 0.50, "h": 0.50, "role": "element"},
        {"slot": 2, "x": 0.50, "y": 0.00, "w": 0.50, "h": 0.50, "role": "element"},
        {"slot": 3, "x": 0.00, "y": 0.50, "w": 0.50, "h": 0.50, "role": "element"},
        {"slot": 4, "x": 0.50, "y": 0.50, "w": 0.50, "h": 0.50, "role": "element"},
    ],

    # 6. 2x3 grid (6 elements)
    "2x3 grid": [
        {"slot": 1, "x": 0.0000, "y": 0.00, "w": 0.3333, "h": 0.50, "role": "element"},
        {"slot": 2, "x": 0.3333, "y": 0.00, "w": 0.3333, "h": 0.50, "role": "element"},
        {"slot": 3, "x": 0.6666, "y": 0.00, "w": 0.3334, "h": 0.50, "role": "element"},
        {"slot": 4, "x": 0.0000, "y": 0.50, "w": 0.3333, "h": 0.50, "role": "element"},
        {"slot": 5, "x": 0.3333, "y": 0.50, "w": 0.3333, "h": 0.50, "role": "element"},
        {"slot": 6, "x": 0.6666, "y": 0.50, "w": 0.3334, "h": 0.50, "role": "element"},
    ],

    # 7. 2x4 grid (8-angle full turnaround)
    "2x4 grid (8 angles)": [
        {"slot": 1, "x": 0.00, "y": 0.00, "w": 0.25, "h": 0.50, "role": "character"},
        {"slot": 2, "x": 0.25, "y": 0.00, "w": 0.25, "h": 0.50, "role": "character"},
        {"slot": 3, "x": 0.50, "y": 0.00, "w": 0.25, "h": 0.50, "role": "character"},
        {"slot": 4, "x": 0.75, "y": 0.00, "w": 0.25, "h": 0.50, "role": "character"},
        {"slot": 5, "x": 0.00, "y": 0.50, "w": 0.25, "h": 0.50, "role": "character"},
        {"slot": 6, "x": 0.25, "y": 0.50, "w": 0.25, "h": 0.50, "role": "character"},
        {"slot": 7, "x": 0.50, "y": 0.50, "w": 0.25, "h": 0.50, "role": "character"},
        {"slot": 8, "x": 0.75, "y": 0.50, "w": 0.25, "h": 0.50, "role": "character"},
    ],

    # 8. Hero character + location + supporting strip
    #    Big character left, big location top-right, 3 small supporting bottom-right.
    "hero + location + strip": [
        {"slot": 1, "x": 0.00, "y": 0.00, "w": 0.45, "h": 1.00, "role": "character"},
        {"slot": 0, "x": 0.45, "y": 0.00, "w": 0.55, "h": 0.60, "role": "location"},
        {"slot": 2, "x": 0.45, "y": 0.60, "w": 0.1833, "h": 0.40, "role": "element"},
        {"slot": 3, "x": 0.6333, "y": 0.60, "w": 0.1833, "h": 0.40, "role": "element"},
        {"slot": 4, "x": 0.8166, "y": 0.60, "w": 0.1834, "h": 0.40, "role": "element"},
    ],

    # 9. Two characters + prop + location (multi-character scene)
    #    Two character panels left, big location right, prop inset bottom.
    "2 chars + prop + location": [
        {"slot": 1, "x": 0.00, "y": 0.00, "w": 0.30, "h": 0.65, "role": "character"},
        {"slot": 2, "x": 0.30, "y": 0.00, "w": 0.30, "h": 0.65, "role": "character"},
        {"slot": 0, "x": 0.60, "y": 0.00, "w": 0.40, "h": 1.00, "role": "location"},
        {"slot": 3, "x": 0.00, "y": 0.65, "w": 0.60, "h": 0.35, "role": "prop"},
    ],

    # 10. Cinematic: huge location backdrop with character + face insets on top
    #     (location is the dominant panel; good for environment-heavy scenes)
    "location hero + insets": [
        {"slot": 0, "x": 0.00, "y": 0.00, "w": 1.00, "h": 1.00, "role": "location"},
        {"slot": 1, "x": 0.02, "y": 0.30, "w": 0.30, "h": 0.68, "role": "character"},
        {"slot": 2, "x": 0.34, "y": 0.55, "w": 0.20, "h": 0.43, "role": "face"},
        {"slot": 3, "x": 0.78, "y": 0.55, "w": 0.20, "h": 0.43, "role": "prop"},
    ],
}

# Display order for the dropdown (presets first, Custom appended by the node).
TEMPLATE_NAMES = list(TEMPLATES.keys())


def get_template(name):
    """Return the slot list for a named preset, or None if not found."""
    return TEMPLATES.get(name)


def max_slot_in_templates():
    """Highest numbered element slot across all presets (for declaring inputs)."""
    hi = 0
    for slots in TEMPLATES.values():
        for s in slots:
            hi = max(hi, s["slot"])
    return hi
