"""
Packing layouts that NEVER truncate images (V2.1).

Both modes preserve each image's native aspect ratio. The reference sheet's
overall shape is allowed to be irregular; the priority is that LTX Ingredients
sees each character/element clearly and completely.

Mode A - free_pack:
    Images are scaled to a common target height and laid left-to-right, wrapping
    to a new row when the running width would exceed max_width. Rows can have
    different counts. Sheet width = max_width (or widest actual row); height grows
    to fit all rows. Simple, automatic.

Mode B - autofit_rows:
    Caller supplies row groupings (which images belong to which row). Within each
    row, all images are scaled to a SHARED row height (so they line up), keeping
    native aspect. Row width = sum of scaled widths. Sheet width = widest row;
    each row is centered. Tidy, sheet-like, predictable.

Both return a list of "placed" dicts:
    {slot, role, x, y, w, h}  (absolute pixels on the final canvas)
plus the final (canvas_w, canvas_h). The node then pastes each image at native
aspect into its placed rect (no crop, no letterbox needed because the rect IS the
image's aspect).
"""


def _aspect(img):
    w, h = img.size
    return w / h if h else 1.0


def free_pack(items, target_h=520, max_width=1920, gap=12, bg_first=False):
    """Mode A. items: list of (slot, role, pil_image) in desired order.
    Returns (placed, canvas_w, canvas_h)."""
    placed = []
    rows = []          # each row: list of [slot, role, img, w, h]
    cur, cur_w = [], 0
    for slot, role, img in items:
        a = _aspect(img)
        w = int(round(target_h * a))
        h = target_h
        if cur and cur_w + gap + w > max_width:
            rows.append((cur, cur_w))
            cur, cur_w = [], 0
        cur_w += (gap if cur else 0) + w
        cur.append([slot, role, img, w, h])
    if cur:
        rows.append((cur, cur_w))

    canvas_w = max((rw for _, rw in rows), default=1)
    canvas_w = min(max(canvas_w, 1), max_width) if rows else 1
    # final width is the widest row (so nothing is cut); not forced to max_width
    canvas_w = max((rw for _, rw in rows), default=1)

    y = gap
    for row, rw in rows:
        x = (canvas_w - rw) // 2 + 0  # center the row
        x = max(0, x)
        row_h = max(h for *_, h in row) if row else 0
        for slot, role, img, w, h in row:
            placed.append({"slot": slot, "role": role, "x": x, "y": y, "w": w, "h": h})
            x += w + gap
        y += row_h + gap
    canvas_h = y
    return placed, max(canvas_w + 0, 1), max(canvas_h, 1)


def autofit_rows(rows_items, row_height=560, max_width=2400, gap=12):
    """Mode B. rows_items: list of rows; each row is a list of (slot, role, pil_image).
    All images in a row share row_height; native aspect preserved.
    Returns (placed, canvas_w, canvas_h)."""
    placed = []
    laid = []   # (row_list_with_sizes, row_w)
    for row in rows_items:
        if not row:
            continue
        sized = []
        rw = 0
        for slot, role, img in row:
            a = _aspect(img)
            w = int(round(row_height * a))
            h = row_height
            rw += (gap if sized else 0) + w
            sized.append([slot, role, img, w, h])
        laid.append((sized, rw))

    canvas_w = max((rw for _, rw in laid), default=1)
    y = gap
    for sized, rw in laid:
        x = (canvas_w - rw) // 2
        x = max(0, x)
        for slot, role, img, w, h in sized:
            placed.append({"slot": slot, "role": role, "x": x, "y": y, "w": w, "h": h})
            x += w + gap
        y += row_height + gap
    canvas_h = y
    return placed, max(canvas_w + gap, 1), max(canvas_h, 1)


def position_name_packed(placed_rect, all_placed):
    """Position label for a packed rect, derived from its row + order within row.
    Mirrors templates.position_name semantics but works on absolute-pixel placed
    rects from the packers."""
    # group by row using y
    y = placed_rect["y"]
    row = sorted([p for p in all_placed if abs(p["y"] - y) < 4], key=lambda p: p["x"])
    n = len(row)
    try:
        rank = row.index(placed_rect)
    except ValueError:
        rank = sum(1 for p in row if p["x"] < placed_rect["x"])

    # vertical band by row index among distinct ys
    ys = sorted({p["y"] for p in all_placed})
    vidx = ys.index(y) if y in ys else 0
    nrows = len(ys)
    if nrows == 1:
        vband = "Top"
    elif vidx == 0:
        vband = "Top"
    elif vidx == nrows - 1:
        vband = "Bottom"
    else:
        vband = "Middle"

    # full-width row?
    canvas_w = max((p["x"] + p["w"]) for p in all_placed)
    if n == 1 and placed_rect["w"] >= 0.85 * canvas_w:
        return f"Full Width {vband}"

    if n <= 1:
        hband = ""
    elif n == 2:
        hband = ["Left", "Right"][min(rank, 1)]
    elif n == 3:
        hband = ["Left", "Center", "Right"][min(rank, 2)]
    elif n == 4:
        hband = ["Far Left", "Left", "Right", "Far Right"][min(rank, 3)]
    else:
        hband = f"#{rank + 1}"

    if not hband:
        return f"{vband} Row" if vband in ("Top", "Bottom") else vband
    if vband in ("Top", "Bottom"):
        return f"{vband} Row {hband}"
    return f"{vband} {hband}"


def add_full_width_band(placed, canvas_w, band_img, band_slot, band_role,
                        band_height=None, at_bottom=True, gap=12):
    """Lay a single image as a full-width band spanning canvas_w, added as its own
    row at the top or bottom of an existing 'placed' layout. The band keeps the
    sheet width; its height is chosen to fill the width at the image's native
    aspect (so it spans edge-to-edge). Returns (placed2, canvas_w, canvas_h).

    `placed` are the already-placed NON-band rects (characters etc.). This shifts
    them down if the band goes on top, and appends the band rect.
    """
    iw, ih = band_img.size
    a = iw / ih if ih else 1.0
    bh = band_height or int(round(canvas_w / a))  # height to span full width at native aspect
    bh = max(1, bh)

    existing_h = (max((p["y"] + p["h"]) for p in placed) if placed else 0)

    placed2 = []
    if at_bottom:
        # characters stay where they are; band sits below
        for p in placed:
            placed2.append(dict(p))
        band_y = existing_h + (gap if placed else 0)
    else:
        # band on top; push characters down by band height + gap
        shift = bh + gap
        for p in placed:
            q = dict(p); q["y"] = p["y"] + shift
            placed2.append(q)
        band_y = 0

    placed2.append({"slot": band_slot, "role": band_role,
                    "x": 0, "y": band_y, "w": canvas_w, "h": bh})
    canvas_h = max((p["y"] + p["h"]) for p in placed2)
    return placed2, canvas_w, canvas_h
