# Changelog

## [3.1.0] - 2026-06-25

### Added
- **`location_fit_bars`** (optional, default off): when on, the location image is
  shown whole (no crop) and the leftover space in the band is filled with black
  bars. Fixes wide location images (e.g. a beach) getting their top and bottom cut
  off. Off keeps the previous edge-to-edge crop behavior.
- **`location_height_percent`** (optional, default 40): restores the control that
  gives the location band a guaranteed share of the sheet height, so it can't be
  squeezed to a thin sliver. The character row fills the remainder.
- **Build stamp** at the top of `node.py` (`NODE_BUILD`), also printed to the
  ComfyUI startup console, so you can confirm which version is loaded.

### Changed
- The location height split now uses `location_height_percent` as a guaranteed
  share rather than a fixed 60/40 split. If filling width would make the character
  row exceed its allotment, panels are rebuilt whole and centered so the location
  keeps its share.
- Both new location fields are **optional** inputs, so existing saved workflows
  load without a "missing required input" error.

<!--
NOTE: Keep your existing changelog entries below this line. This file replaces
only the top of the changelog; paste your prior v3.0.0 and earlier entries
underneath if they were not preserved automatically.
-->
