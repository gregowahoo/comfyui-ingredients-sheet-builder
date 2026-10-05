# Changelog

All notable changes to this project are documented here.

## [5.0.0] - 2026-07-30

**Decoupled.** This node builds the reference sheet and the panel descriptions —
and nothing else. Turning the sheet into a finished action prompt is now entirely
a downstream job (the separate **Action Prompt Writer** package, your own LLM node,
or pasting a prompt by hand). This keeps the builder simple and lets the consumer
choose how the action is written.

### Removed (breaking)
- **`system_prompt` input** and the bundled `DEFAULT_SYSTEM_PROMPT` — action-writer
  scaffolding that didn't belong here.
- **`llm_prompt` output** (was `system_prompt + action_idea`). The 4th output is
  gone; the node now returns 3.
- **Bundled `IngredientsActionWriter` and `IngredientsActionIdea` nodes** — removed
  from this package. Use `comfyui-action-prompt-writer` instead.
- **`anthropic` dependency** — no longer needed here.

### Changed
- **Output renamed `video_prompt_template` → `prompt`** (same slot, slot 2). It's the
  two-part `Reference sheet: … / Generated video: <your simple action>` text, with
  your raw `action_idea` passed straight through (never LLM-revised).
- `action_idea` is now a plain simple-action field (blank default, updated tooltip):
  one line describing what happens, handed downstream as-is.

### Migration
Saved workflows: the builder loses its `llm_prompt` output and `system_prompt`
widget. Re-point anything that consumed `llm_prompt`, and if the old `system_prompt`
text shows up in the `action_idea` box, clear it. (The `DB_BAB_…LTX_Video_Generator`
workflow was migrated automatically.)

## [4.4.0] - 2026-07-29

### Changed
- **`video_prompt_template` now carries your RAW typed action** after
  `Generated video:` (whatever you put in `action_idea`, verbatim, not LLM-revised).
  This makes the builder output a complete-but-rough prompt that the new
  **Action Prompt Writer** node can read and rewrite. The placeholder default is
  treated as empty.

### Removed
- **`lora_keywords` field** (added briefly in 4.3.0) — moved to the new Action
  Prompt Writer node, which is where the action is actually assembled. Keeping it
  here would double-apply the trigger words.

## [4.3.0] - 2026-07-29

### Added
- **`lora_keywords` field** (optional, on the Sheet Builder). Type your LoRA
  trigger/activation words (e.g. `LTXNUDES, Breast Massage`) and they are merged to
  the **start** of the "Generated video:" prompt, before the generated action prose
  — so the final prompt reads `Generated video: LTXNUDES, Breast Massage, <action>`.
  Commas/spacing/newlines are normalized; leave blank to omit. Existing workflows
  load unchanged (it's an optional input).

## [4.2.3] - 2026-07-29

### Changed
- **Blank line between panels in the reference block.** Each `Name:` description is
  now separated by a blank line (paragraph per panel) for easier reading in the
  Show Text preview.

## [4.2.2] - 2026-07-29

### Changed
- **One panel per line in the reference block.** `video_prompt_template` now puts
  each `Name:` description on its own line (still `;`-separated per the LTX
  Ingredients format) under a `Reference sheet:` header, so the panels are easy to
  read at a glance instead of running together on one line.

## [4.2.1] - 2026-07-29

### Fixed
- **Clean line spacing in the reference block.** Panel captions coming from
  multiline fields / caption LLMs sometimes carried stray newlines and double
  spaces, which survived the `; ` join and put blank lines *between* panel
  descriptions in `video_prompt_template`. Each caption is now whitespace-collapsed
  to a single line before joining, so the "Reference sheet:" block is one clean
  line and the only break is the intended blank line before "Generated video:".
  (Same `_clean_desc` helper that strips the "Here's a description of…:" preamble.)

## [4.2.0] - 2026-07-27

### Added
- **`IngredientsActionIdea` node ("Ingredients Action Idea").** Upstream companion:
  type a short seed, Claude drafts a concrete action idea (the "what happens",
  not the cinematic prose) to feed the builder's `action_idea`. Replaces the old
  Text-node → text-LLM → ShowText chain with one node. Inputs: `instruction`,
  `model`, `max_tokens`, `seed`, optional `context` / `system_prompt` / `api_key`.
  Output: `action_idea`.

Clean 3-node flow: **Action Idea → Sheet Builder → Action Writer**.

## [4.1.0] - 2026-07-27

### Added
- **`IngredientsActionWriter` node ("Ingredients Action Writer").** Generates the
  "Generated video" action prose with **Claude vision** — it actually looks at the
  reference sheet image, so character/setting details are accurate. No external
  LLM node to wire up.
  - Inputs: `sheet_image` + `llm_prompt` (both from the builder), `model`
    (default `claude-opus-4-8`), `max_tokens`, `seed` (bump to re-roll), and
    optional `video_prompt_template` (from the builder) + `api_key` (blank = use
    `ANTHROPIC_API_KEY`).
  - Outputs: `action_prose` and `final_prompt` (= the builder's reference block +
    the generated action, ready for the LTX text encoder).
- **`anthropic`** added to dependencies (install into ComfyUI's Python:
  `C:\Comfy\python_embeded\python.exe -m pip install anthropic`).

### Wiring
Builder `sheet_image` → Action Writer `sheet_image`; builder `llm_prompt` →
Action Writer `llm_prompt`; builder `video_prompt_template` → Action Writer
`video_prompt_template`. Action Writer `final_prompt` → your LTX text encoder.

## [4.0.0] - 2026-06-27

The V4 rewrite. Adds a two-part LLM prompt workflow, per-slot panel controls,
and a small web UI. **Breaking:** the node's outputs changed, so saved workflows
will need to be rewired.

### Added
- **`num_panels`** (required, default 4): how many character/prop slots are active
  (1-8). Slots above this are ignored even if wired.
- **`enable_location`** (optional, default on): drop the location band and let the
  character row fill the whole sheet, without unplugging the location image.
- **`system_prompt`** (required, default template): the captioning/LLM system prompt,
  now on the node and exposed as an output so it wires straight into a Generate Text node.
- **`action_idea`** (required): what you want to happen in the video; appended after
  `ACTION IDEA:` in the system prompt and surfaced as the `llm_prompt` output.
- **Web UI** (`web/ingredients_sheet_builder.js`, registered via `WEB_DIRECTORY`).

### Changed
- **Outputs restructured (4, was 3):** `sheet_image`, `labeled_preview`,
  `video_prompt_template`, `llm_prompt`. `video_prompt_template` is the semicolon-prose
  reference block wrapped as `Reference sheet: {…}\n\nGenerated video: `, ready to
  concatenate LLM output; `llm_prompt` is `system_prompt + action_idea`.
- **Max panels 6 -> 8.**
- **Default sheet size 1456x825 -> 1536x896**, matching the official Lightricks
  `compose_sheet` canvas.
- A panel is included only if its image socket is connected; empty slots are skipped
  and the row reflows automatically.
- Improved tooltips throughout; added a tip that the official Ingredients LoRA runs
  best at strength 1.4.

### Removed
- The standalone `reference_sheet_prompt` output (its prose now lives inside
  `video_prompt_template`).
- The internal `_pos_label` position-naming helper.

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
