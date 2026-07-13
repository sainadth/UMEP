# Week 9 — Real Sun-Position-Driven Kdown

**Status:** Approved
**Project:** GA Summer 2026 — UMEP / SOLWEIG plugin build-out
**Plugin:** `hello_qgis_plugin` (source: `D:\San\GA_SUMMER_2026\hello_qgis_plugin\`)
**Predecessor:** Week 8 baseline (`tmrt_like = Ta + alpha*(Kdown_proxy/100) - beta*Wind`, where `Kdown_proxy` was a linear rescale of whatever raster was chosen as "primary raster" — see Week 8 finding below)

## 1. Problem statement

The Week 8 baseline computation is a pure affine (linear, monotonic) transform of its input raster: `kdown_proxy = rescale(input, 0, 1000)`, then `tmrt_like = Ta + alpha*(kdown_proxy/100) - beta*Wind`. Because both steps are order-preserving, the output always visually mirrors the input's spatial pattern exactly, regardless of what raster is chosen (buildings mask → output looks like a building stencil; DSM → output looks exactly like the DSM). It has no dependency on sun position, time of day, or radiation geometry — a run at noon and a run at midnight produce identical output. This was expected and intentional for Week 8 (the goal was proving the Worker/QThread/GeoTIFF pipeline, not physical correctness), but it means the output has zero physical meaning and cannot be used for any thermal comparison.

Week 9 replaces the arbitrary `kdown_proxy` with a real, sun-position-driven `Kdown` so that the plugin's output actually responds to when and where the run happens — the first step toward SOLWEIG parity.

## 2. Scope

**In scope:**
- Real solar geometry (zenith/azimuth → sun altitude) via UMEP's own `sun_position.py`
- Isotropic-sky `Kdown = radG * SVF` (single global radiation value, no direct/diffuse split, no anisotropic Perez patches)
- Day/night branching: `Kdown = 0` at night, matching SOLWEIG's own day/night split
- Single-timestep manual GUI inputs (date, time, UTC offset, radG) — no met-file parsing
- Output filename D/N suffix convention matching real SOLWEIG

**Out of scope (deferred to Week 10+):**
- Shadow casting (buildings/vegetation blocking direct sun)
- Direct/diffuse radiation split, clearness index
- Anisotropic (Perez) sky model
- Longwave (L) fluxes — `absL`/`ewall` params stay unused for now
- Multi-timestep met-file loop

## 3. Architecture

Extends the existing `Worker(QObject)` / `HelloDialog` structure in `hello_plugin.py` — no new files, no new classes. Same threading pattern (QThread + progress/error/finished signals) as Week 7/8.

### 3.1 New GUI inputs (`HelloDialog.__init__`)

| Control | Type | Default | Notes |
|---|---|---|---|
| SVF raster | `QgsMapLayerComboBox` (RasterLayer filter) | none | **New required picker.** Must grid-match the primary (DSM) raster via existing `rasters_match()`. |
| Date | 3× `QSpinBox` (year/month/day) or `QDateEdit` | today's date | Feeds `sun_position()` time dict |
| Time | `QTimeEdit` or 2× `QSpinBox` (hour/min) | 12:00 | Feeds `sun_position()` time dict |
| UTC offset | `QDoubleSpinBox` | 1.0 | SOLWEIG GUI default |
| Global radiation `radG` | `QDoubleSpinBox`, range 1–1300 | 895 | SOLWEIG's manual single-timestep default |

Existing controls (Ta, Wind, alpha, beta, output folder, run prefix, timestamp) are unchanged. Lat/lon/altitude continue to come from the primary raster's corner (Week 6 `_corner_lat_lon` / `read_raster_summary`, reused as-is).

### 3.2 Sun position

Import `sun_position` from UMEP's installed copy: `Utilities/SEBESOLWEIGCommonFiles/sun_position.py`, located relative to the UMEP plugin install directory (sibling of this plugin under QGIS's `python/plugins/`). Rationale: this is the same validated NREL-SPA-derived algorithm real SOLWEIG uses (atmospheric refraction, topocentric correction, etc.) — reimplementing it from scratch would be significant, error-prone extra work for no benefit, and the project's own stated pattern is "reuse SOLWEIG technique."

- **Import path resolution:** locate the UMEP plugin directory via QGIS's plugin registry (`qgis.utils.plugins` / `QgsApplication.qgisSettingsDirPath()` plugin path) and add its path to `sys.path` if not already importable.
- **Failure mode:** if the import fails (UMEP not installed in this QGIS profile), raise a clear `ImportError`-derived message surfaced through the existing `Worker.error` signal / `QMessageBox` — no silent fallback to a fabricated sun position. This keeps failures loud, consistent with the rest of the plugin's validation style (raster mismatch, unwritable folder, etc.).

Call shape:
```python
time_dict = {"year": ..., "month": ..., "day": ..., "hour": ..., "min": ..., "sec": 0, "UTC": utc_offset}
location_dict = {"latitude": lat, "longitude": lon, "altitude": dsm_altitude}
sun = sun_position(time_dict, location_dict)   # -> {"zenith":..., "azimuth":...}
sun_altitude = 90 - sun["zenith"]
```

### 3.3 Worker.run() — updated computation

Replaces the current `kdown_proxy` block (`hello_plugin.py:195-211`):

1. Read DSM (existing: lat/lon/altitude via `read_raster_summary`-equivalent logic already in the worker)
2. Read SVF array; validate grid match against DSM (reuse `rasters_match()`)
3. Build `time_dict` / `location_dict` from new GUI fields; call `sun_position()`
4. Branch on `sun_altitude`:
   - `<= 0` (night): `Kdown = np.zeros_like(svf_array)`; `daynight_flag = "N"`
   - `> 0` (day): `Kdown = radG * svf_array`; clip to `[0, radG]`; `daynight_flag = "D"`
5. `tmrt_like = Ta + alpha*(Kdown/100) - beta*Wind`, clipped to `[-30, 80]` (unchanged from Week 8)
6. NoData mask: union of DSM NoData and SVF NoData; preserved in output as `-9999` (unchanged pattern from Week 8)
7. Output filename: `tmrt_like_{daynight_flag}.tif` inside the existing run-folder/timestamp scheme
8. `run_info_week9.txt` (new key set, same write pattern as Week 8's `run_info_week8.txt`): input DSM/SVF paths, date/time, UTC offset, lat/lon, computed sun altitude/azimuth, radG, day/night flag, Ta/Wind/alpha/beta, output stats (min/max/mean)

### 3.4 Validation additions

- SVF raster required before run (same pattern as existing DSM-required check)
- SVF/DSM grid match required (block run on mismatch, same as current secondary-raster check)
- Sun-position import failure surfaces as a run error, not a crash

## 4. Data flow

```
DSM (primary raster) ──► lat/lon/altitude (corner reprojection, existing Week 6 code)
SVF raster ──► grid-matched against DSM ──► svf_array
GUI (date/time/UTC/radG) ──► time_dict/location_dict ──► sun_position() ──► sun_altitude, sun_azimuth
                                                              │
                                              day/night branch (sun_altitude > 0 ?)
                                                              │
                                          Kdown = radG * svf_array   OR   Kdown = 0
                                                              │
                                    tmrt_like = Ta + alpha*(Kdown/100) - beta*Wind
                                                              │
                                          clip[-30,80] + NoData mask ──► GeoTIFF (D/N suffix)
                                                              │
                                                    run_info_week9.txt
```

## 5. Testing (Week 9 acceptance)

| Test | Method | Pass condition |
|---|---|---|
| Day/night differ | Run same inputs at noon vs. midnight | Noon output shows SVF-weighted gradient; midnight output is flat (all `Ta - beta*Wind`), filename suffix D vs N |
| Time sensitivity | Run at 08:00 vs 14:00 (if sun altitude differs enough to matter — note: with no direct/diffuse split, `radG` is manual and constant, so the ONLY thing that changes between two daytime runs is the D/N flag and sun altitude/azimuth logged in run_info; `Kdown` magnitude itself does not vary with time within "day" since `radG` is a manual constant, not derived from sun angle) | Documented explicitly as a known Week 9 limitation, not a bug — see §6 |
| radG sensitivity | Increase `radG` | Daytime output mean increases proportionally |
| SVF gradient | Visual check | Output shows continuous gradient following `svf` raster, not a binary stencil |
| Missing SVF | Run without selecting SVF raster | Validation error, run blocked |
| SVF/DSM mismatch | Mismatched grids | Validation error, run blocked |
| sun_position import failure (manual test, optional) | Simulate missing UMEP path | Clear error surfaced, no crash |

## 6. Known limitation carried forward

Because `radG` is a manually-entered constant (not derived from sun angle, clearness index, or time), two daytime runs at different times of day with the same `radG` will produce numerically identical `Kdown` — only the day/night boundary itself is time-sensitive in Week 9. This is an accurate reflection of SOLWEIG's own "single-timestep manual mode" (§2.5.1 of the weekly doc), which also takes `radG` as a direct manual input rather than deriving it. Full time-of-day sensitivity within daytime requires either a met file (multi-timestep, Week 11+) or clearness-index/direct-diffuse modeling (Week 10+ physics), not scoped here.

## 6.1 Optional stretch goal (non-blocking)

If time permits after the core Week 9 scope (§2) is done and tested, add a simple clear-sky estimate so `radG` varies with sun angle instead of staying a flat manual constant:

```
radG ≈ I0 * sin(sun_altitude) * transmissivity
```

where `I0` is extraterrestrial radiation (already a documented SOLWEIG POI output column, §2.4.2) and `transmissivity` is a fixed placeholder constant (e.g. 0.75) — not a real clearness-index model. This is explicitly a stretch goal, not a requirement: it must not block or delay the core deliverables in §7, and if dropped, Week 9 ships with manual `radG` as originally scoped. Full clearness-index/direct-diffuse modeling remains Week 10+ work.

## 7. Deliverables

- Updated `hello_plugin.py` (v0.5) with SVF input, sun-position Kdown, day/night branching
- `run_info_week9.txt` per run
- Screenshots: dialog with new date/time/radG/SVF controls; noon run output; midnight (flat) run output; run_info contents
- Test log against §5 matrix
