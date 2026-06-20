"""
Ingredients Sheet Builder for ComfyUI
The prep step for the LTX-2.3 IC-LoRA Ingredients workflow.

Builds a reference sheet (black bg, one clean panel per element, no baked text)
from your own images or generation branches, with a modular vision backend for
auto-captioning, and emits the trained-format two-part prompt the Ingredients
model expects.
"""

from .node import IngredientsSheetBuilder

NODE_CLASS_MAPPINGS = {
    "IngredientsSheetBuilder": IngredientsSheetBuilder,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "IngredientsSheetBuilder": "Ingredients Sheet Builder",
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
