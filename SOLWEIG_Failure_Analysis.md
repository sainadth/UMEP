# SOLWEIG Failure Analysis

Audit of the UMEP SOLWEIG plugin (`SOLWEIG/solweig.py`, `SOLWEIG/solweigworker.py`,
`SOLWEIG/SOLWEIGpython/*.py`) to identify where the model and its QGIS wrapper can
fail or silently produce wrong results, ranked by how likely each is to hit a
typical UMEP user (urban climate researchers running SOLWEIG on city-scale rasters).

## 1. Input validation gaps (high likelihood)

- `solweig.py:302-313` — meteorological file parsing wrapped in a bare `except:`
  that swallows all errors (encoding issues, wrong delimiter, partial rows) into
  one generic "check format" dialog — no line number or column diagnostics.
- `solweig.py:315-330` — only checks `metdata.shape[1] == 24`; never validates
  column ranges (RH 0-100, non-negative radiation, hour 0-23). A shifted-column
  met file passes silently and produces physically wrong Tmrt.
- `solweig.py:388-389` — DSM NoData is blindly zeroed
  (`self.dsm[self.dsm == nd] = 0.0`) rather than masked/flagged. NoData borders
  mid-raster (common with clipped tiles) create fake ground-level pits that skew
  shadow/SVF calculations with no warning.
- `solweig.py:701-709` — bare `except:` around SVF zip-file loading gives only a
  generic "corrupt zipfile" message, masking the real cause (mismatched grid
  count, missing patch-option variant).
- Extent/resolution checks (`solweig.py:465-468, 513-516, 553-556, 613-618,
  714-720, 745-751, 770-776`) compare only array shape, never CRS or
  geotransform/origin. Two rasters with identical dimensions but offset origin,
  or different pixel size that happens to yield the same shape, silently
  misalign — producing spatially wrong results with no error.
- POI coordinates (`solweig.py:1014-1023`) convert to row/col via
  `np.round((x-minx)*scale)` with **no bounds check**. A POI outside the DSM
  extent (or on the edge) produces an out-of-range index that throws an
  unhandled `IndexError` deep in `solweigworker.py:570-627`, often after a long
  run.

## 2. Numerical stability issues (high likelihood, silent)

- `SOLWEIGpython/cylindric_wedge.py:18-20` — divides by
  `tan(alfa)*tan(beta)`, where `alfa` (svfalfa) is exactly 0 in fully open areas
  and `beta` (zenith) approaches 90° at sunrise/sunset. Both produce `inf`/`nan`;
  only `F_sh`'s NaNs get patched downstream (`Solweig_2022a_calc.py:383`), but
  the intermediate `inf` propagates through `ukil`/`Ssurf` unhandled.
- `SOLWEIGpython/gvf_2018a.py:52` — `wallsun / walls * buildings` divides by
  `walls`, which is 0 for all non-wall pixels, generating `0/0 = nan` across
  most of the grid every timestep (masked downstream by `== 1`, but spams
  invalid-value warnings and wastes cycles).
- `Solweig_2022a_calc.py:293-300` — `np.log(90 - zen_deg)` and
  `radG/radI0` divisions have no zero/negative guards; near-polar latitudes or
  zenith ≈ 90° degenerate these terms.

## 3. Physics/model limitations (moderate, by design, under-documented)

- Static vegetation transmissivity `psi`, driven by hardcoded day-of-year
  thresholds `leafon1=97, leafoff1=300`
  (`Utilities/SEBESOLWEIGCommonFiles/Solweig_v2015_metdata_noload.py:35-36`,
  flagged `# TODO this should change`) — wrong for non-temperate/Southern
  Hemisphere sites.
- Isotropic-sky branch (`Solweig_2022a_calc.py:544-569`) is a coarse
  Jonsson et al. (2006) approximation; the more accurate anisotropic
  Perez-based path only runs if `anisotropic_sky==1`, and most users leave the
  default.
- SVF/shadow matrices are precomputed once and reused across the whole run —
  no check that `amaxvalue` (max height range) covers very tall/thin building
  geometries, which can silently truncate shadows.

## 4. Performance/scalability

- `solweigworker.py:366-791` — an unvectorized per-timestep Python loop calling
  the full physics engine every step, on a single `QThread`
  (`solweig.py:1670-1685`) — no multi-core use, full 2D array reallocation each
  iteration. City-scale, sub-hourly, full-year runs are CPU/memory-heavy.
- Size warnings only at `sizex*sizey > 250000/1000000`
  (`solweig.py:778-788`) are informational — no actual safeguard against memory
  exhaustion on very large DSMs.

## 5. Error handling gaps

- `solweigworker.py:800-815` — top-level `except Exception` reports a raw
  traceback string via `print_exception()`/`linecache` — opaque to non-developer
  users.
- No cancellation check inside the per-timestep loop beyond `self.killed` at the
  very end (`solweigworker.py:797`) — "kill" doesn't abort mid-run promptly.

## 6. Known TODOs in-source

- `solweig.py:115` — deferred UI feature.
- `Lside_veg_v2015a.py:66` / `Lside_veg_v2022a.py:67` — commented-out beta-sun
  correction, flagged as an unimplemented improvement for shaded-wall longwave.

## Highest-impact failure modes for real users

1. Bare-except met-file/SVF loading → opaque failures with no actionable
   diagnostics.
2. Unbounded POI indexing → late crash, often after a long run.
3. `cylindric_wedge` / `gvf_2018a` division-by-zero patterns → silent NaN/Inf
   propagation that degrades Tmrt accuracy with no warning surfaced in the UI.
4. Shape-only raster matching (no CRS/origin check) → silently misaligned
   inputs producing spatially wrong results.

## Implications for a rebuilt plugin

The companion project (`hello_qgis_plugin`, weekly build-up toward a smaller
SOLWEIG-style tool) is a natural place to apply fixes for the above, since it
already re-implements SOLWEIG's raster I/O and validation path from scratch.
Week 10 of that project ("Robustness Hardening") directly targets failure
modes 1 and 4 above: strict raster matching (shape + pixel size + CRS +
origin), explicit NoData-fraction warnings instead of silent zero-fill, POI
bounds validation before any indexing, and NaN/Inf sanitization on the output
raster before it's written to disk. See that repo's `week10-robustness` branch
and its `WEEK10_NOTES.md` for what was implemented and tested.
