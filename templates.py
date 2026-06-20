"""
Layout templates for the Ingredients Sheet Builder (V2).

Each slot: {slot, x, y, w, h, role} with x/y/w/h normalized 0..1.
slot 0 = background/location input. role in:
location|character|face|prop|element.

Model-card principle: bigger panels carry over better, so location and primary
character panels get the most space.

V2 adds position_name() so the node can label panels in the trained format:
    **Top Row Left (Character):** <caption>
plus presets where the location spans a full row.
"""


def position_name(slot):
    """Human label for a slot derived from its rect: 'Top Row Left',
    'Bottom Row Right', 'Middle Center', 'Full Width Top', 'Full Frame', etc."""
    x, y, w, h = slot["x"], slot["y"], slot["w"], slot["h"]
    cx = x + w / 2.0
    cy = y + h / 2.0
    full_w = w >= 0.85
    full_h = h >= 0.85
    if full_w and full_h:
        return "Full Frame"
    if cy < 0.34:
        vband = "Top"
    elif cy < 0.67:
        vband = "Middle"
    else:
        vband = "Bottom"
    if full_w:
        return f"Full Width {vband}"
    if cx < 0.34:
        hband = "Left"
    elif cx < 0.67:
        hband = "Center"
    else:
        hband = "Right"
    if vband in ("Top", "Bottom"):
        return f"{vband} Row {hband}"
    return f"{vband} {hband}"


def role_label(role):
    return {
        "location": "Setting",
        "character": "Character",
        "face": "Character - Face",
        "prop": "Prop",
        "element": "Element",
    }.get(role, "Element")


TEMPLATES = {
    "1 char + location": [
        {"slot": 0, "x": 0.50, "y": 0.00, "w": 0.50, "h": 1.00, "role": "location"},
        {"slot": 1, "x": 0.00, "y": 0.00, "w": 0.50, "h": 1.00, "role": "character"},
    ],
    "char + face + location": [
        {"slot": 0, "x": 0.62, "y": 0.00, "w": 0.38, "h": 1.00, "role": "location"},
        {"slot": 1, "x": 0.00, "y": 0.00, "w": 0.38, "h": 1.00, "role": "character"},
        {"slot": 2, "x": 0.38, "y": 0.00, "w": 0.24, "h": 1.00, "role": "face"},
    ],
    "1x3 row": [
        {"slot": 1, "x": 0.0000, "y": 0.00, "w": 0.3333, "h": 1.00, "role": "character"},
        {"slot": 2, "x": 0.3333, "y": 0.00, "w": 0.3333, "h": 1.00, "role": "character"},
        {"slot": 3, "x": 0.6666, "y": 0.00, "w": 0.3334, "h": 1.00, "role": "character"},
    ],
    "1x5 row": [
        {"slot": 1, "x": 0.00, "y": 0.00, "w": 0.20, "h": 1.00, "role": "character"},
        {"slot": 2, "x": 0.20, "y": 0.00, "w": 0.20, "h": 1.00, "role": "character"},
        {"slot": 3, "x": 0.40, "y": 0.00, "w": 0.20, "h": 1.00, "role": "character"},
        {"slot": 4, "x": 0.60, "y": 0.00, "w": 0.20, "h": 1.00, "role": "character"},
        {"slot": 5, "x": 0.80, "y": 0.00, "w": 0.20, "h": 1.00, "role": "character"},
    ],
    "2x2 grid": [
        {"slot": 1, "x": 0.00, "y": 0.00, "w": 0.50, "h": 0.50, "role": "element"},
        {"slot": 2, "x": 0.50, "y": 0.00, "w": 0.50, "h": 0.50, "role": "element"},
        {"slot": 3, "x": 0.00, "y": 0.50, "w": 0.50, "h": 0.50, "role": "element"},
        {"slot": 4, "x": 0.50, "y": 0.50, "w": 0.50, "h": 0.50, "role": "element"},
    ],
    "2x3 grid": [
        {"slot": 1, "x": 0.0000, "y": 0.00, "w": 0.3333, "h": 0.50, "role": "element"},
        {"slot": 2, "x": 0.3333, "y": 0.00, "w": 0.3333, "h": 0.50, "role": "element"},
        {"slot": 3, "x": 0.6666, "y": 0.00, "w": 0.3334, "h": 0.50, "role": "element"},
        {"slot": 4, "x": 0.0000, "y": 0.50, "w": 0.3333, "h": 0.50, "role": "element"},
        {"slot": 5, "x": 0.3333, "y": 0.50, "w": 0.3333, "h": 0.50, "role": "element"},
        {"slot": 6, "x": 0.6666, "y": 0.50, "w": 0.3334, "h": 0.50, "role": "element"},
    ],
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
    "chars + location bottom row": [
        {"slot": 1, "x": 0.0000, "y": 0.00, "w": 0.3333, "h": 0.55, "role": "character"},
        {"slot": 2, "x": 0.3333, "y": 0.00, "w": 0.3333, "h": 0.55, "role": "character"},
        {"slot": 3, "x": 0.6666, "y": 0.00, "w": 0.3334, "h": 0.55, "role": "character"},
        {"slot": 0, "x": 0.0000, "y": 0.55, "w": 1.00, "h": 0.45, "role": "location"},
    ],
    "chars + location top row": [
        {"slot": 0, "x": 0.00, "y": 0.00, "w": 1.00, "h": 0.45, "role": "location"},
        {"slot": 1, "x": 0.00, "y": 0.45, "w": 0.25, "h": 0.55, "role": "character"},
        {"slot": 2, "x": 0.25, "y": 0.45, "w": 0.25, "h": 0.55, "role": "character"},
        {"slot": 3, "x": 0.50, "y": 0.45, "w": 0.25, "h": 0.55, "role": "character"},
        {"slot": 4, "x": 0.75, "y": 0.45, "w": 0.25, "h": 0.55, "role": "character"},
    ],
    "full kit + location bottom": [
        {"slot": 1, "x": 0.00, "y": 0.00, "w": 0.34, "h": 0.55, "role": "character"},
        {"slot": 2, "x": 0.34, "y": 0.00, "w": 0.22, "h": 0.55, "role": "face"},
        {"slot": 3, "x": 0.56, "y": 0.00, "w": 0.22, "h": 0.55, "role": "prop"},
        {"slot": 4, "x": 0.78, "y": 0.00, "w": 0.22, "h": 0.55, "role": "prop"},
        {"slot": 0, "x": 0.00, "y": 0.55, "w": 1.00, "h": 0.45, "role": "location"},
    ],
}

TEMPLATE_NAMES = list(TEMPLATES.keys())


def get_template(name):
    return TEMPLATES.get(name)


def max_slot_in_templates():
    hi = 0
    for slots in TEMPLATES.values():
        for s in slots:
            hi = max(hi, s["slot"])
    return hi
