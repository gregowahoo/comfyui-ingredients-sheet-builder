# Changelog

All notable changes to this project are documented here.

## [3.0.0]

Complete rewrite. The node is now single-purpose: build an LTX-2.3 IC-LoRA
Ingredients reference sheet and output the panel descriptions as clean prose.

### Layout
- **One fixed layout, no modes.** Removed `layout_mode`, `template`, `layout_json`,
  `fit_mode`, and `row_assignment`. Character/prop panels go in a top row; the location
  is a full-width band (top or bottom).
- **Panels shown whole.** Each panel keeps its true aspect ratio - never cropped, never
  squished. With 4-5 panels the row scales to fill the width edge-to-edge.
- **Uniform black gutters** between panels, between the character row and location band,
  and around the whole sheet - matching Lightricks' example sheets and preventing hard
  seams from propagating into the rendered video. Controlled by `panel_gap` (default 12).
- **Default sheet size 1456x825**, matching the official example sheets. (The model card's
  768x448 is the output VIDEO size; the reference SHEET is larger and downscaled in the
  pipeline. Bigger sheets carry more detail and avoid banding.)
- **Drop a panel by muting its Load Image node** instead of managing a row-assignment string.

### Prompt
- **Clean prose output.** `reference_sheet_prompt` is now semicolon-joined prose with no
  `###` headers and no `**Position (Role):**` labels, matching the official sample format.
- **Per-panel IDs.** New `id_1`..`id_6` and `location_id` fields. Give the same name to every
  panel showing the same character so the prompt names one consistent identity instead of
  several separate-looking subjects.

### Inputs / Outputs
- Outputs: `sheet_image`, `reference_sheet_prompt`, `labeled_preview`.
- Removed outputs from earlier drafts: `full_prompt`, `generated_video_prompt`,
  `negative_prompt`, `target_header`, `llm_system_prompt`, `action_idea`.
- The captioning system prompt and the action idea now live in their own Text nodes in the
  workflow (kept out of the node so they can be edited freely). A starting system-prompt
  template is included as a reference comment at the top of `node.py`.

### Fixed
- The duplicate `layout_map` output that caused a `tuple index out of range` validation error
  has been removed.
- Black bars / screen-split lines no longer propagate into the video (whole panels on a black
  background at the correct sheet size, with gutters).

### Notes
- The old `_packers.py`, `templates.py`, and `layout_templates_reference.png` are no longer
  used and have been removed; the node is self-contained in `node.py`.

## [2.0.0]
- Externalized captioning; per-panel descriptions via `desc_*` inputs. Added layout modes,
  fit modes, and a full-width location band. (All superseded by the 3.0 rewrite.)

## [1.0.0]
- Initial release: composite reference-sheet builder with fixed-grid templates.
