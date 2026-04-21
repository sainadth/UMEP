# Sidebar & Layer Controls Redesign — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split the sidebar into a blue-tinted "Model Inputs" section and a warm-tinted "Layers" section, and add a collapsible layer manager (visibility toggle + opacity slider per layer) to the top-right map legend.

**Architecture:** Pure frontend — three files only (`index.html`, `styles.css`, `app.js`). CSS defines two `panel-section` variants and layer card layout. HTML restructures the sidebar using those classes. JS adds a `setLayerState()` helper that keeps sidebar and legend controls in sync, then wires the new collapsible legend panel.

**Tech Stack:** HTML5, CSS3 (custom properties, `max-height` transition), Leaflet 1.9.4, vanilla JS (ES6)

---

## Files

| File | Change |
|---|---|
| `backend/app/static/styles.css` | Add section, card, and legend CSS classes; remove `.layer-control-row`, `.checkbox-row` |
| `backend/app/static/index.html` | Restructure sidebar into two `panel-section` divs; hide file inputs |
| `backend/app/static/app.js` | Add `setLayerState()`; remove duplicate opacity inputs; refactor event listeners; add legend layer panel |

---

## Task 1: CSS — Section and Layer Card Classes

**Files:**
- Modify: `backend/app/static/styles.css`

- [ ] **Step 1: Add new classes to end of styles.css**

Open `backend/app/static/styles.css` and append the following block at the end of the file:

```css
/* ── Panel sections ─────────────────────────────────────── */
.panel-section {
  padding: 14px 18px;
  border-bottom: 2px solid var(--border);
}

.panel-section--inputs {
  background: #f0f4ff;
  border-bottom-color: #c8d8f0;
}

.panel-section--layers {
  background: #fff8ee;
  border-bottom-color: #e8d8b0;
}

.section-header {
  font-size: 0.75rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  margin-bottom: 10px;
  margin-top: 0;
}

.section-header--inputs { color: #3060c0; }
.section-header--layers { color: #a05a00; }

/* ── Layer cards ────────────────────────────────────────── */
.layer-card {
  background: #fff;
  border: 1px solid #e8d8b0;
  border-radius: 8px;
  padding: 8px 10px;
  margin-bottom: 8px;
}

.layer-card-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.layer-card-row input[type="checkbox"] {
  width: auto;
  margin: 0;
  flex-shrink: 0;
  accent-color: var(--accent);
}

.layer-card-row .layer-name {
  flex: 1;
  font-weight: 600;
  font-size: 0.88rem;
}

.layer-card-row .opacity-label {
  font-size: 0.75rem;
  color: #888;
}

.layer-card-row input[type="range"] {
  width: 72px;
  padding: 0;
  accent-color: var(--accent);
}

.layer-card-controls {
  display: flex;
  gap: 6px;
  align-items: center;
  margin-top: 7px;
}

.layer-card-controls select {
  flex: 1;
  padding: 5px 6px;
  font-size: 0.8rem;
}

.layer-card-controls button {
  padding: 5px 8px;
  font-size: 0.78rem;
  border-radius: 6px;
  white-space: nowrap;
}

/* ── Info section ───────────────────────────────────────── */
.info-section {
  padding: 14px 18px;
}

.info-section h2 {
  margin-top: 10px;
  margin-bottom: 6px;
  font-size: 1rem;
}

/* ── Legend layer manager ───────────────────────────────── */
.tmrt-legend-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

.legend-toggle-btn {
  background: none;
  border: none;
  padding: 0 2px;
  font-size: 15px;
  color: #888;
  cursor: pointer;
  line-height: 1;
}

.legend-layers {
  overflow: hidden;
  max-height: 0;
  transition: max-height 0.25s ease;
}

.legend-layers.open {
  max-height: 140px;
}

.legend-layer-sep {
  border: none;
  border-top: 1px solid #e0d8cc;
  margin: 6px 0;
}

.legend-layer-row {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 4px;
}

.legend-layer-row input[type="checkbox"] {
  width: auto;
  margin: 0;
  accent-color: var(--accent);
}

.legend-layer-row span {
  flex: 1;
  font-size: 11px;
}

.legend-layer-row input[type="range"] {
  width: 64px;
  padding: 0;
  accent-color: var(--accent);
}
```

- [ ] **Step 2: Remove obsolete classes from styles.css**

Delete the following two rule blocks from `styles.css` (they will no longer be used):

```css
.layer-control-row {
  margin-top: 8px;
  display: grid;
  gap: 6px;
}

.checkbox-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 0;
  margin-bottom: 0;
}
```

Also update `.tmrt-legend-title` — remove its `margin-bottom` (that spacing now lives in `.tmrt-legend-header`):

Find:
```css
.tmrt-legend-title {
  margin-bottom: 6px;
  font-size: 12px;
  font-weight: 700;
  color: #2f2a20;
}
```

Replace with:
```css
.tmrt-legend-title {
  font-size: 12px;
  font-weight: 700;
  color: #2f2a20;
}
```

- [ ] **Step 3: Verify CSS file is valid**

Open the file in a text editor or run:
```bash
# on any system with node
node -e "require('fs').readFileSync('backend/app/static/styles.css','utf8'); console.log('OK')"
```
Expected: `OK` (no parse error thrown).

- [ ] **Step 4: Commit**

```bash
git add backend/app/static/styles.css
git commit -m "style: add panel-section, layer-card, and legend-layers CSS classes"
```

---

## Task 2: HTML — Restructure Sidebar

**Files:**
- Modify: `backend/app/static/index.html`

- [ ] **Step 1: Replace the entire `<aside class="panel">` block**

In `backend/app/static/index.html`, replace everything between (and including) `<aside class="panel">` and its closing `</aside>` with:

```html
      <aside class="panel">
        <div style="padding: 14px 18px 10px;">
          <h1>Live TMRT 2D</h1>
          <p class="subtitle">SOLWEIG-inspired operational predictor</p>
        </div>

        <!-- ── Model Inputs ──────────────────────────── -->
        <div class="panel-section panel-section--inputs">
          <p class="section-header section-header--inputs">⚙ Model Inputs</p>

          <label>Latitude</label>
          <input id="latInput" type="number" step="0.0001" value="27.713651" />

          <label>Longitude</label>
          <input id="lonInput" type="number" step="0.0001" value="-97.325456" />

          <label>Grid Size</label>
          <input id="gridInput" type="number" min="10" max="100" value="40" />

          <label>Map Span (m)</label>
          <input id="spanInput" type="number" min="200" max="5000" value="1200" />

          <div class="button-row">
            <button id="runBtn">Run Prediction</button>
            <button id="liveBtn" class="secondary">Start Live</button>
          </div>

          <div class="status" id="statusBox">Idle</div>
        </div>

        <!-- ── Layers ────────────────────────────────── -->
        <div class="panel-section panel-section--layers">
          <p class="section-header section-header--layers">🗂 Layers</p>

          <!-- TMRT -->
          <div class="layer-card">
            <div class="layer-card-row">
              <input id="tmrtLayerToggle" type="checkbox" checked />
              <span class="layer-name">TMRT</span>
              <span class="opacity-label">opacity</span>
              <input id="tmrtOpacityInput" type="range" min="0" max="1" step="0.05" value="0.6" />
            </div>
          </div>

          <!-- DEM -->
          <div class="layer-card">
            <div class="layer-card-row">
              <input id="demLayerToggle" type="checkbox" checked />
              <span class="layer-name">DEM</span>
              <span class="opacity-label">opacity</span>
              <input id="demOpacityInput" type="range" min="0" max="1" step="0.05" value="0.55" />
            </div>
            <div class="layer-card-controls">
              <select id="demSelect">
                <option value="">None (procedural terrain)</option>
              </select>
              <button id="uploadDemBtn" class="secondary">Upload</button>
              <button id="refreshDemBtn" class="secondary">↺</button>
            </div>
            <input id="demFileInput" type="file" accept=".tif,.tiff" style="display:none" />
          </div>

          <!-- DSM -->
          <div class="layer-card">
            <div class="layer-card-row">
              <input id="dsmLayerToggle" type="checkbox" checked />
              <span class="layer-name">DSM</span>
              <span class="opacity-label">opacity</span>
              <input id="dsmOpacityInput" type="range" min="0" max="1" step="0.05" value="0.55" />
            </div>
            <div class="layer-card-controls">
              <select id="dsmSelect">
                <option value="">None</option>
              </select>
              <button id="uploadDsmBtn" class="secondary">Upload</button>
              <button id="refreshDsmBtn" class="secondary">↺</button>
            </div>
            <input id="dsmFileInput" type="file" accept=".tif,.tiff" style="display:none" />
          </div>
        </div>

        <!-- ── Info ──────────────────────────────────── -->
        <div class="info-section">
          <h2>Live Weather</h2>
          <pre id="weatherBox" class="mono"></pre>

          <h2>DEM Info</h2>
          <pre id="demInfoBox" class="mono">No DEM selected.</pre>

          <h2>DSM Info</h2>
          <pre id="dsmInfoBox" class="mono">No DSM selected.</pre>

          <h2>Selected Cell</h2>
          <pre id="selectedBox" class="mono">Click a TMRT cell on the map to inspect detailed values.</pre>

          <p class="small-note">
            Note: fast approximation for web operations; not full SOLWEIG radiative transfer.
          </p>
        </div>
      </aside>
```

- [ ] **Step 2: Verify all element IDs still exist**

All of these IDs must be present in the new HTML (grep to confirm):

```bash
grep -E 'id="(latInput|lonInput|gridInput|spanInput|runBtn|liveBtn|statusBox|tmrtLayerToggle|tmrtOpacityInput|demLayerToggle|demOpacityInput|demSelect|uploadDemBtn|refreshDemBtn|demFileInput|dsmLayerToggle|dsmOpacityInput|dsmSelect|uploadDsmBtn|refreshDsmBtn|dsmFileInput|weatherBox|demInfoBox|dsmInfoBox|selectedBox)"' backend/app/static/index.html | wc -l
```

Expected: `24` (one match per ID).

- [ ] **Step 3: Commit**

```bash
git add backend/app/static/index.html
git commit -m "feat: restructure sidebar into inputs and layers sections"
```

---

## Task 3: JS — setLayerState Helper + Refactored Event Listeners

**Files:**
- Modify: `backend/app/static/app.js`

- [ ] **Step 1: Remove stale variable declarations**

At the top of `app.js`, find and remove these two lines (they reference inputs that no longer exist in the HTML):

```js
const tmrtLayerOpacityInput = document.getElementById("tmrtLayerOpacityInput");
```
```js
const dsmLayerOpacityInput = document.getElementById("dsmLayerOpacityInput");
```

Also remove:
```js
const dsmOpacityInput = document.getElementById("dsmOpacityInput");
```
…and re-add it in the correct position (it now exists in HTML; it was previously a duplicate). Verify `dsmOpacityInput` appears exactly once in the `const` declarations block.

The full updated `const` block for layer-related inputs should read:

```js
const tmrtLayerToggle = document.getElementById("tmrtLayerToggle");
const tmrtOpacityInput = document.getElementById("tmrtOpacityInput");
const demLayerToggle = document.getElementById("demLayerToggle");
const demOpacityInput = document.getElementById("demOpacityInput");
const dsmLayerToggle = document.getElementById("dsmLayerToggle");
const dsmOpacityInput = document.getElementById("dsmOpacityInput");
const demFileInput = document.getElementById("demFileInput");
const uploadDemBtn = document.getElementById("uploadDemBtn");
const refreshDemBtn = document.getElementById("refreshDemBtn");
const demSelect = document.getElementById("demSelect");
const dsmFileInput = document.getElementById("dsmFileInput");
const uploadDsmBtn = document.getElementById("uploadDsmBtn");
const refreshDsmBtn = document.getElementById("refreshDsmBtn");
const dsmSelect = document.getElementById("dsmSelect");
```

- [ ] **Step 2: Add legend element variables (placeholder values — wired in Task 4)**

After the block above, add:

```js
let legendTmrtToggle = null;
let legendTmrtOpacity = null;
let legendDemToggle = null;
let legendDemOpacity = null;
let legendDsmToggle = null;
let legendDsmOpacity = null;
```

- [ ] **Step 3: Add setLayerState() helper**

Add this function immediately after the `applyLayerVisibility()` function (around line 107 in the original file):

```js
function setLayerState(which, visible, opacity) {
  if (which === "tmrt") {
    tmrtVisible = visible;
    tmrtOpacity = opacity;
    tmrtLayerToggle.checked = visible;
    tmrtOpacityInput.value = String(opacity);
    applyLayerVisibility(heatLayer, visible);
    if (heatLayer) heatLayer.setStyle({ fillOpacity: opacity });
    if (legendTmrtToggle) legendTmrtToggle.checked = visible;
    if (legendTmrtOpacity) legendTmrtOpacity.value = String(opacity);
  } else if (which === "dem") {
    demVisible = visible;
    demOpacity = opacity;
    demLayerToggle.checked = visible;
    demOpacityInput.value = String(opacity);
    applyLayerVisibility(demOverlay, visible);
    if (demOverlay) demOverlay.setOpacity(opacity);
    if (legendDemToggle) legendDemToggle.checked = visible;
    if (legendDemOpacity) legendDemOpacity.value = String(opacity);
  } else if (which === "dsm") {
    dsmVisible = visible;
    dsmOpacity = opacity;
    dsmLayerToggle.checked = visible;
    dsmOpacityInput.value = String(opacity);
    applyLayerVisibility(dsmOverlay, visible);
    if (dsmOverlay) dsmOverlay.setOpacity(opacity);
    if (legendDsmToggle) legendDsmToggle.checked = visible;
    if (legendDsmOpacity) legendDsmOpacity.value = String(opacity);
  }
}
```

- [ ] **Step 4: Replace all layer event listeners**

Find and delete the following event listener blocks (all of them — they will be replaced):

```js
tmrtOpacityInput.addEventListener("input", ...
tmrtLayerOpacityInput.addEventListener("input", ...
tmrtLayerToggle.addEventListener("change", ...
demLayerToggle.addEventListener("change", ...
demOpacityInput.addEventListener("input", ...
dsmOpacityInput.addEventListener("input", ...
dsmLayerOpacityInput.addEventListener("input", ...
dsmLayerToggle.addEventListener("change", ...
```

Replace them all with:

```js
tmrtLayerToggle.addEventListener("change", () =>
  setLayerState("tmrt", tmrtLayerToggle.checked, tmrtOpacity)
);
tmrtOpacityInput.addEventListener("input", () =>
  setLayerState("tmrt", tmrtVisible, Number(tmrtOpacityInput.value))
);

demLayerToggle.addEventListener("change", () =>
  setLayerState("dem", demLayerToggle.checked, demOpacity)
);
demOpacityInput.addEventListener("input", () =>
  setLayerState("dem", demVisible, Number(demOpacityInput.value))
);

dsmLayerToggle.addEventListener("change", () =>
  setLayerState("dsm", dsmLayerToggle.checked, dsmOpacity)
);
dsmOpacityInput.addEventListener("input", () =>
  setLayerState("dsm", dsmVisible, Number(dsmOpacityInput.value))
);
```

- [ ] **Step 5: Fix upload buttons to trigger hidden file inputs**

The file inputs are now hidden (`display:none`). Update the upload button listeners so they open the file picker, and move upload logic to the `change` event.

Find and replace the `uploadDemBtn` listener:

```js
// OLD — delete this entire block:
uploadDemBtn.addEventListener("click", async () => {
  const file = demFileInput.files && demFileInput.files[0];
  if (!file) {
    setStatus("Choose a DEM .tif file first");
    return;
  }
  setStatus(`Uploading DEM: ${file.name} ...`);
  try {
    const uploaded = await postDem(file);
    await refreshDemList();
    demSelect.value = uploaded.dem_id;
    renderDemInfo(uploaded);
    await loadDemOverlay(uploaded.dem_id);
    setStatus(`DEM uploaded: ${uploaded.name}`);
  } catch (err) {
    setStatus(`Error: ${err.message}`);
  }
});
```

Replace with:

```js
uploadDemBtn.addEventListener("click", () => demFileInput.click());

demFileInput.addEventListener("change", async () => {
  const file = demFileInput.files && demFileInput.files[0];
  if (!file) return;
  setStatus(`Uploading DEM: ${file.name} ...`);
  try {
    const uploaded = await postDem(file);
    await refreshDemList();
    demSelect.value = uploaded.dem_id;
    renderDemInfo(uploaded);
    await loadDemOverlay(uploaded.dem_id);
    setStatus(`DEM uploaded: ${uploaded.name}`);
  } catch (err) {
    setStatus(`Error: ${err.message}`);
  }
});
```

Find and replace the `uploadDsmBtn` listener:

```js
// OLD — delete this entire block:
uploadDsmBtn.addEventListener("click", async () => {
  const file = dsmFileInput.files && dsmFileInput.files[0];
  if (!file) {
    setStatus("Choose a DSM .tif file first");
    return;
  }
  setStatus(`Uploading DSM: ${file.name} ...`);
  try {
    const uploaded = await postDsm(file);
    await refreshDsmList();
    dsmSelect.value = uploaded.dsm_id;
    renderDsmInfo(uploaded);
    await loadDsmOverlay(uploaded.dsm_id);
    setStatus(`DSM uploaded and overlaid: ${uploaded.name}`);
  } catch (err) {
    setStatus(`Error: ${err.message}`);
  }
});
```

Replace with:

```js
uploadDsmBtn.addEventListener("click", () => dsmFileInput.click());

dsmFileInput.addEventListener("change", async () => {
  const file = dsmFileInput.files && dsmFileInput.files[0];
  if (!file) return;
  setStatus(`Uploading DSM: ${file.name} ...`);
  try {
    const uploaded = await postDsm(file);
    await refreshDsmList();
    dsmSelect.value = uploaded.dsm_id;
    renderDsmInfo(uploaded);
    await loadDsmOverlay(uploaded.dsm_id);
    setStatus(`DSM uploaded and overlaid: ${uploaded.name}`);
  } catch (err) {
    setStatus(`Error: ${err.message}`);
  }
});
```

- [ ] **Step 6: Manual smoke test**

Start the backend server and open `http://localhost:8000` (or whatever port is configured):

```bash
cd backend && uvicorn app.main:app --reload
```

Verify:
1. Sidebar shows blue "Model Inputs" section at top.
2. Sidebar shows warm "Layers" section with TMRT, DEM, DSM cards.
3. Checking/unchecking TMRT toggle hides/shows the heat layer.
4. Moving DEM opacity slider updates the DEM overlay opacity live.
5. Clicking "Upload" on DEM card opens the file picker.
6. Clicking "↺" on DEM card refreshes the DEM list.

- [ ] **Step 7: Commit**

```bash
git add backend/app/static/app.js
git commit -m "feat: add setLayerState helper and refactor layer event listeners"
```

---

## Task 4: JS — Collapsible Legend Layer Manager

**Files:**
- Modify: `backend/app/static/app.js`

- [ ] **Step 1: Replace legendControl.onAdd**

Find the existing `legendControl.onAdd` block:

```js
const legendControl = L.control({ position: "topright" });
legendControl.onAdd = () => {
  const div = L.DomUtil.create("div", "tmrt-legend leaflet-bar");
  div.innerHTML =
    '<div class="tmrt-legend-title">TMRT (deg C)</div>' +
    '<div class="tmrt-legend-gradient"></div>' +
    '<div class="tmrt-legend-scale"><span id="legendMin">min</span><span id="legendMax">max</span></div>';
  L.DomEvent.disableClickPropagation(div);
  return div;
};
legendControl.addTo(map);
```

Replace it with:

```js
const legendControl = L.control({ position: "topright" });
legendControl.onAdd = () => {
  const div = L.DomUtil.create("div", "tmrt-legend leaflet-bar");
  div.innerHTML =
    '<div class="tmrt-legend-header">' +
      '<span class="tmrt-legend-title">TMRT (deg C)</span>' +
      '<button class="legend-toggle-btn" id="legendToggleBtn" title="Toggle layers">⊞</button>' +
    '</div>' +
    '<div class="tmrt-legend-gradient"></div>' +
    '<div class="tmrt-legend-scale"><span id="legendMin">min</span><span id="legendMax">max</span></div>' +
    '<div class="legend-layers" id="legendLayers">' +
      '<hr class="legend-layer-sep" />' +
      '<div class="legend-layer-row">' +
        '<input type="checkbox" id="legendTmrtToggle" checked />' +
        '<span>TMRT</span>' +
        '<input type="range" id="legendTmrtOpacity" min="0" max="1" step="0.05" value="0.6" />' +
      '</div>' +
      '<div class="legend-layer-row">' +
        '<input type="checkbox" id="legendDemToggle" checked />' +
        '<span>DEM</span>' +
        '<input type="range" id="legendDemOpacity" min="0" max="1" step="0.05" value="0.55" />' +
      '</div>' +
      '<div class="legend-layer-row">' +
        '<input type="checkbox" id="legendDsmToggle" checked />' +
        '<span>DSM</span>' +
        '<input type="range" id="legendDsmOpacity" min="0" max="1" step="0.05" value="0.55" />' +
      '</div>' +
    '</div>';
  L.DomEvent.disableClickPropagation(div);
  return div;
};
legendControl.addTo(map);
```

- [ ] **Step 2: Wire legend controls after addTo(map)**

Immediately after `legendControl.addTo(map);`, add:

```js
const legendToggleBtn = document.getElementById("legendToggleBtn");
const legendLayersDiv = document.getElementById("legendLayers");
legendTmrtToggle = document.getElementById("legendTmrtToggle");
legendTmrtOpacity = document.getElementById("legendTmrtOpacity");
legendDemToggle = document.getElementById("legendDemToggle");
legendDemOpacity = document.getElementById("legendDemOpacity");
legendDsmToggle = document.getElementById("legendDsmToggle");
legendDsmOpacity = document.getElementById("legendDsmOpacity");

legendToggleBtn.addEventListener("click", () => {
  const open = legendLayersDiv.classList.toggle("open");
  legendToggleBtn.textContent = open ? "⊟" : "⊞";
});

legendTmrtToggle.addEventListener("change", () =>
  setLayerState("tmrt", legendTmrtToggle.checked, tmrtOpacity)
);
legendTmrtOpacity.addEventListener("input", () =>
  setLayerState("tmrt", tmrtVisible, Number(legendTmrtOpacity.value))
);

legendDemToggle.addEventListener("change", () =>
  setLayerState("dem", legendDemToggle.checked, demOpacity)
);
legendDemOpacity.addEventListener("input", () =>
  setLayerState("dem", demVisible, Number(legendDemOpacity.value))
);

legendDsmToggle.addEventListener("change", () =>
  setLayerState("dsm", legendDsmToggle.checked, dsmOpacity)
);
legendDsmOpacity.addEventListener("input", () =>
  setLayerState("dsm", dsmVisible, Number(legendDsmOpacity.value))
);
```

Note: `legendTmrtToggle` etc. are assigned here (not declared with `let`) — they were declared as `let` variables earlier in Task 3 Step 2.

- [ ] **Step 3: Manual smoke test**

With the server still running (`uvicorn app.main:app --reload`), reload `http://localhost:8000` and verify:

1. Legend shows "TMRT (deg C)" title with a `⊞` button to the right.
2. Clicking `⊞` expands the legend to show TMRT / DEM / DSM rows with checkboxes and sliders, button becomes `⊟`.
3. Clicking `⊟` collapses the rows with a smooth animation.
4. Unchecking TMRT in the legend hides the heat layer; sidebar TMRT checkbox also becomes unchecked.
5. Moving DEM opacity slider in the legend updates the overlay; sidebar DEM slider moves to match.
6. Sidebar controls sync back to legend: move sidebar DSM opacity slider → legend DSM slider moves too.

- [ ] **Step 4: Commit**

```bash
git add backend/app/static/app.js
git commit -m "feat: add collapsible legend layer manager with visibility and opacity controls"
```

---

## Self-Review

**Spec coverage:**

| Spec requirement | Task |
|---|---|
| Sidebar split: blue Inputs section | Task 2 |
| Sidebar split: warm Layers section | Task 2 |
| TMRT card: toggle + opacity | Task 2, Task 3 |
| DEM card: toggle + opacity + select + upload + refresh | Task 2, Task 3 |
| DSM card: toggle + opacity + select + upload + refresh | Task 2, Task 3 |
| Info boxes retained | Task 2 |
| Legend always shows gradient + scale | Task 4 |
| Legend ⊞/⊟ toggle button | Task 4 |
| Legend layer rows collapse/expand | Task 4 (CSS `max-height` transition in Task 1) |
| Sidebar and legend controls synced | Task 3 (`setLayerState`) |
| Duplicate opacity inputs removed | Task 3 |
| Upload buttons trigger hidden file input | Task 3 |

All spec requirements covered. No TBDs. Method names consistent across tasks (`setLayerState`, `legendTmrtToggle`, `legendDemOpacity`, etc.). File paths exact.
