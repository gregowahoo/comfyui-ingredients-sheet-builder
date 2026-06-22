# Changelog

All notable changes to this project are documented here.

## [3.0.0]

Complete rewrite. The node is now single-purpose: build an LTX-2.3 IC-LoRA
Ingredients reference sheet, nothing else.

### Changed
- **Stripped to one layout.** Removed `layout_mode`, `template`, `layout_json`,
  `fit_mode`, and `row_assignment`. There are no modes to pick wrong now — the node
  always lays character/prop panels in a top row with the location as a full-width band.
- **Panels are shown whole, on a black background.** Each panel keeps its true aspect
  ratio — never cropped (no cut-off heads/feet) and never squished. Remaining space is
  black background, which is the layout the model card specifies.
- **Renamed `background` → `location_image`** to match the model card's terminology.
- **Resolution defaults to 768×448** (the model's trained size) instead of 1920×1080.
- **Drop a panel by muting its Load Image node**, instead of managing a row-assignment
  string. Whatever is wired in appears; whatever isn't doesn't.

### Added
- `llm_system_prompt` and `action_idea` as editable fields **and** output sockets, so the
  captioning instructions and the rough action idea can be wired into a Generate Text node
  (or fed in from elsewhere via Convert to input).
- `labeled_preview` output (panel numbers drawn on a copy, never on the real sheet).

### Fixed
- The duplicate `layout_map` output that caused a `tuple index out of range` validation
  error has been removed; the output list is now clean and consistent.
- Black bars can no longer bleed into the rendered video, because panels are shown whole
  on a black background rather than padded with black framing inside a panel.

### Notes
- The old `_packers.py` and `templates.py` are no longer used; the node is self-contained
  in `node.py`. They can be left in place (harmless) or removed.

## [2.0.0]
- Externalized captioning (removed internal Ollama/vision dependency); per-panel
  descriptions wired in via `desc_*` inputs.
- Added layout modes (Template, Auto-fit rows, Free pack), `fit_clamp` fit mode, and
  full-width location band. (All superseded by the 3.0 rewrite.)

## [1.0.0]
- Initial release: composite reference-sheet builder with fixed-grid templates.
