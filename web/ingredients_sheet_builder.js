/**
 * Ingredients Sheet Builder — dynamic panel sockets + upstream muting
 *
 * Keeps all MAX_PANELS image_N sockets always present so connections survive
 * panel-count changes. When num_panels changes:
 *   - Mutes (mode=4) the upstream chain for slots above the active count
 *   - Unmutes (mode=0) the upstream chain for slots at or below it
 *   - Hides id_N / desc_N widgets for inactive slots
 * Only IMAGE-type inputs are followed during traversal so shared model nodes
 * (CLIP, VAE, etc.) are never touched.
 */

import { app } from "../../scripts/app.js";

const NODE_NAME  = "IngredientsSheetBuilder";
const MAX_PANELS = 8;

console.log("[IngredientsSheetBuilder] JS extension loaded");

/**
 * Walk upstream from node's input at inputIdx, setting mode on every found
 * node. Follows IMAGE and STRING inputs; skips MODEL/CLIP/VAE/LATENT to
 * avoid touching shared model nodes.
 */
const SKIP_TYPES = new Set(["MODEL","CLIP","VAE","LATENT","CONDITIONING","CONTROL_NET"]);

function setUpstreamChain(graph, node, inputIdx, mode, depth) {
    if (depth <= 0 || !graph) return;
    const inp = node.inputs?.[inputIdx];
    if (!inp?.link) return;
    // links may be a plain object or a Map depending on ComfyUI version
    const link = graph.links?.get
        ? graph.links.get(inp.link)
        : graph.links?.[inp.link];
    if (!link) return;
    const src = graph.getNodeById?.(link.origin_id);
    if (!src) return;
    if (src.mode === mode) return; // already correct, skip subtree
    src.mode = mode;
    for (let i = 0; i < (src.inputs?.length ?? 0); i++) {
        const t = src.inputs[i].type;
        if (!SKIP_TYPES.has(t)) {
            setUpstreamChain(graph, src, i, mode, depth - 1);
        }
    }
}

app.registerExtension({
    name: "IngredientsSheetBuilder.DynamicPanels",

    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== NODE_NAME) return;
        console.log("[IngredientsSheetBuilder] Hooking node type");

        // ── sync function ────────────────────────────────────────────────────
        nodeType.prototype._syncPanels = function (active) {
            active = Math.max(1, Math.min(MAX_PANELS, parseInt(active) || 1));
            console.log(`[IngredientsSheetBuilder] _syncPanels → ${active}`);

            // Ensure all MAX_PANELS image_N sockets exist so connections survive
            const existing = new Set((this.inputs ?? []).map(i => i.name));
            for (let i = 1; i <= MAX_PANELS; i++) {
                if (!existing.has(`image_${i}`)) {
                    this.addInput(`image_${i}`, "IMAGE");
                }
            }

            // Mute/unmute upstream chains for each slot.
            // Check image_N, desc_N, and id_N inputs — Get_Image Desc nodes
            // connect via desc_N so we must traverse those too.
            const graph = this.graph ?? app.graph;
            if (graph) {
                for (let i = 1; i <= MAX_PANELS; i++) {
                    const mode = i <= active ? 0 : 4; // 0=active, 4=muted
                    for (const name of [`image_${i}`, `desc_${i}`, `id_${i}`]) {
                        const idx = (this.inputs ?? []).findIndex(inp => inp.name === name);
                        if (idx >= 0) setUpstreamChain(graph, this, idx, mode, 6);
                    }
                }
            }

            // Keep all widgets visible so connections to muted nodes remain
            // drawn — user can see exactly what slot each Get_Image belongs to.

            // Never shrink the node; only grow to enforce the minimum.
            const w0 = Math.max(this.size[0], 500);
            const w1 = Math.max(this.size[1], 600);
            if (w0 !== this.size[0] || w1 !== this.size[1]) this.setSize([w0, w1]);
            this.setDirtyCanvas(true, true);
        };

        // ── enforce minimum size on every resize drag ────────────────────────
        const origResize = nodeType.prototype.onResize;
        nodeType.prototype.onResize = function (size) {
            if (size[0] < 500) { size[0] = 500; this.size[0] = 500; }
            if (size[1] < 600) { size[1] = 600; this.size[1] = 600; }
            origResize?.apply(this, arguments);
        };

        // ── on node created ──────────────────────────────────────────────────
        const origCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            origCreated?.apply(this, arguments);
            const self = this;

            // Belt-and-suspenders: set min_size AND hook onResize
            this.min_size = [500, 600];

            // Wait one frame for ComfyUI to finish building the node
            requestAnimationFrame(() => {
                const numW = self.widgets?.find(w => w.name === "num_panels");
                if (!numW) {
                    console.warn("[IngredientsSheetBuilder] num_panels widget not found");
                    return;
                }

                // Initial sync: remove slots above num_panels (Python starts with 8)
                self._syncPanels(numW.value);

                // Intercept future value changes
                const origCb = numW.callback;
                numW.callback = function (value, ...rest) {
                    origCb?.call(this, value, ...rest);
                    self._syncPanels(value);
                };
            });
        };

        // ── on workflow load (restore saved state) ───────────────────────────
        const origConfigure = nodeType.prototype.onConfigure;
        nodeType.prototype.onConfigure = function (data) {
            origConfigure?.apply(this, arguments);
            this.min_size = [500, 600];
            const self = this;
            requestAnimationFrame(() => {
                const numW = self.widgets?.find(w => w.name === "num_panels");
                if (numW) self._syncPanels(numW.value);
            });
        };
    },
});
