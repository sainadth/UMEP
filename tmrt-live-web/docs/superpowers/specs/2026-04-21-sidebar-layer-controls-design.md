# Sidebar & Layer Controls Redesign

**Date:** 2026-04-21  
**Status:** Approved  
**Scope:** `backend/app/static/index.html`, `styles.css`, `app.js`

---

## Goal

Improve the sidebar UX by visually separating model input fields from layer controls (QGIS-style), and add a collapsible layer manager to the top-right legend so users can toggle layer visibility and opacity directly on the map.

---

## Sidebar Structure

The sidebar splits into two visually distinct sections separated by background color and a section header label.

### Section 1 — Model Inputs (blue tint)

Background: `#f0f4ff`, border-bottom: `#c8d8f0`  
Header label: `⚙ Model Inputs` (uppercase, `#3060c0`)

Contains:
- Latitude input
- Longitude input
- Grid Size input
- Map Span (m) input
- Run Prediction + Start Live buttons
- Status box

### Section 2 — Layers (warm tint)

Background: `#fff8ee`, border-bottom: `#e8d8b0`  
Header label: `🗂 Layers` (uppercase, `#a05a00`)

Contains one card per layer. Each card has:
- Visibility checkbox (left)
- Layer name (center)
- Opacity label + range slider (right)

**TMRT card** — checkbox + opacity slider only (no file controls; TMRT is computed).

**DEM card** — checkbox + opacity slider, plus:
- Active DEM `<select>` dropdown
- Upload button (triggers hidden file input)
- Refresh button

**DSM card** — checkbox + opacity slider, plus:
- Active DSM `<select>` dropdown
- Upload button (triggers hidden file input)
- Refresh button

### Info section (below Layers)

Retained as-is but styled consistently:
- Live Weather
- DEM Info
- DSM Info
- Selected Cell

---

## Legend Layer Manager (top-right on map)

The existing `L.control` legend gains a collapsible layer section below the gradient bar.

### Always visible
- Title: `TMRT (deg C)`
- Color gradient bar
- Min / max scale labels
- Toggle button (`⊞` expand / `⊟` collapse)

### Collapsible section (default: collapsed)
Three rows — one per layer — each with:
- Visibility checkbox
- Layer name
- Opacity range slider

Collapse/expand is a smooth CSS `max-height` transition (e.g. 0 → 120px).

---

## State Sync

Sidebar and legend controls share the same JS state variables (`tmrtOpacity`, `demOpacity`, `dsmOpacity`, `tmrtVisible`, `demVisible`, `dsmVisible`). A single `setLayerState(layer, visible, opacity)` helper updates both the map layer and both UI controls in one call, preventing drift.

The current redundant pair (`tmrtOpacityInput` + `tmrtLayerOpacityInput`) is removed. One slider per layer in the sidebar; the legend slider is the second control, both wired to the same handler.

---

## CSS Changes

| New class | Purpose |
|---|---|
| `.panel-section` | Shared padding/border-bottom wrapper |
| `.panel-section--inputs` | Blue tint background |
| `.panel-section--layers` | Warm tint background |
| `.section-header` | Uppercase label + icon row |
| `.layer-card` | White card with border-radius inside Layers section |
| `.layer-card-row` | Flex row: checkbox + name + opacity slider |
| `.layer-card-controls` | Sub-row for select + upload + refresh buttons |
| `.legend-layers` | Collapsible div inside legend control |
| `.legend-toggle-btn` | ⊞/⊟ button top-right of legend |

---

## Files Changed

| File | Changes |
|---|---|
| `index.html` | Restructure sidebar into two `panel-section` divs; update legend HTML in `app.js` |
| `styles.css` | Add new classes above; remove obsolete `layer-control-row`, `checkbox-row` |
| `app.js` | Add `setLayerState()` helper; wire legend collapse toggle; remove duplicate opacity input sync code |

---

## Out of Scope

- Drag-and-drop layer reordering
- Layer z-index control
- Additional layer types beyond TMRT, DEM, DSM
