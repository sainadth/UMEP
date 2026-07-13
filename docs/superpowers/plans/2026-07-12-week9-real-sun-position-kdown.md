# Week 9 — Real Sun-Position-Driven Kdown Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Week 8 placeholder (`kdown_proxy` = linear rescale of an arbitrary input raster) with a real, sun-position-driven `Kdown = radG * SVF`, computed via UMEP's own `sun_position()` and gated by a real day/night branch, so plugin output actually changes with the chosen date/time instead of just mirroring whatever raster was selected.

**Architecture:** Split the new physics into a pure, QGIS-free module (`compute_week9.py`) that is fully unit-testable with pytest + numpy, and keep all Qt/QGIS-bound wiring (GUI controls, `Worker.run()`, sun-position import lookup) in `hello_plugin.py`, following the existing plugin's pattern where `read_raster_summary`/`rasters_match` are already free functions. The QGIS-bound pieces (new GUI controls, `locate_umep_sun_position()`, `Worker` wiring) are not unit-testable outside a running QGIS session — they get manual QGIS verification steps instead, consistent with how Weeks 6-8 were verified (no existing automated test suite in this project; this plan introduces the project's first one, scoped to what's actually testable headless).

**Tech Stack:** Python 3.13, numpy, pytest 9.0.2, PyQt (via `qgis.PyQt`), GDAL/OGR (`osgeo`), QGIS 4.0.3 runtime for manual verification. UMEP plugin (already installed at `C:\Users\spagadala1\AppData\Roaming\QGIS\QGIS4\profiles\default\python\plugins\UMEP`) supplies the real `sun_position()` at `Utilities/SEBESOLWEIGCommonFiles/sun_position.py`.

---

## File structure

- **Create:** `D:\San\GA_SUMMER_2026\hello_qgis_plugin\compute_week9.py` — pure functions: Kdown computation, tmrt_like formula, day/night flag, time/location dict builders, sun-altitude-from-zenith conversion, optional clear-sky radG estimate. No QGIS/PyQt/GDAL imports — numpy only.
- **Create:** `D:\San\GA_SUMMER_2026\hello_qgis_plugin\tests\test_compute_week9.py` — pytest unit tests for every function in `compute_week9.py`.
- **Create:** `D:\San\GA_SUMMER_2026\hello_qgis_plugin\tests\__init__.py` — empty, makes `tests` an importable package.
- **Modify:** `D:\San\GA_SUMMER_2026\hello_qgis_plugin\hello_plugin.py` — add `locate_umep_sun_position()`, new GUI controls in `HelloDialog.__init__`, rewrite the `Worker.run()` computation block to use `compute_week9`.
- **Modify:** `D:\San\GA_SUMMER_2026\hello_qgis_plugin\metadata.txt` — bump version to `0.5`, update `about` description.
- **Modify:** `D:\San\GA_SUMMER_2026\UMEP\SOLWEIG_Weekly_Updates.md` — add Week 9 section documenting what shipped, mirroring the Week 6/7/8 write-up style.

---

### Task 1: Test scaffolding

**Files:**
- Create: `D:\San\GA_SUMMER_2026\hello_qgis_plugin\tests\__init__.py`
- Create: `D:\San\GA_SUMMER_2026\hello_qgis_plugin\compute_week9.py`
- Test: `D:\San\GA_SUMMER_2026\hello_qgis_plugin\tests\test_compute_week9.py`

- [ ] **Step 1: Create empty tests package**

Create `D:\San\GA_SUMMER_2026\hello_qgis_plugin\tests\__init__.py` with empty content (0 bytes).

- [ ] **Step 2: Create empty compute module**

Create `D:\San\GA_SUMMER_2026\hello_qgis_plugin\compute_week9.py`:

```python
"""Pure computation functions for Week 9 (sun-position-driven Kdown).

No QGIS, PyQt, or GDAL imports here — this module must be importable
and testable with plain numpy, outside a running QGIS session.
"""

import numpy as np
```

- [ ] **Step 3: Write the failing test for `daynight_flag`**

Create `D:\San\GA_SUMMER_2026\hello_qgis_plugin\tests\test_compute_week9.py`:

```python
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from compute_week9 import daynight_flag


def test_daynight_flag_day():
    assert daynight_flag(45.0) == "D"


def test_daynight_flag_night():
    assert daynight_flag(-10.0) == "N"


def test_daynight_flag_zero_altitude_is_night():
    assert daynight_flag(0.0) == "N"
```

- [ ] **Step 4: Run test to verify it fails**

Run: `cd "D:\San\GA_SUMMER_2026\hello_qgis_plugin" && python -m pytest tests/test_compute_week9.py -v`
Expected: FAIL with `ImportError: cannot import name 'daynight_flag'`

- [ ] **Step 5: Implement `daynight_flag`**

Add to `compute_week9.py`:

```python
def daynight_flag(sun_altitude_deg):
    """Return 'D' for daytime (sun above horizon), 'N' otherwise.

    Matches SOLWEIG's own day/night convention: altitude <= 0 is night.
    """
    return "N" if sun_altitude_deg <= 0 else "D"
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd "D:\San\GA_SUMMER_2026\hello_qgis_plugin" && python -m pytest tests/test_compute_week9.py -v`
Expected: PASS (3 tests)

- [ ] **Step 7: Commit**

```bash
cd "D:\San\GA_SUMMER_2026"
git init 2>/dev/null; git add hello_qgis_plugin/compute_week9.py hello_qgis_plugin/tests/
git commit -m "test: add daynight_flag with passing tests (Week 9)"
```

(If `hello_qgis_plugin` is not its own git repo and instead tracked inside a parent repo, adjust the `git add` paths accordingly — check `git status` first to confirm which repo root is in effect before committing.)

---

### Task 2: `compute_kdown`

**Files:**
- Modify: `D:\San\GA_SUMMER_2026\hello_qgis_plugin\compute_week9.py`
- Test: `D:\San\GA_SUMMER_2026\hello_qgis_plugin\tests\test_compute_week9.py`

- [ ] **Step 1: Write the failing tests**

Append to `test_compute_week9.py`:

```python
import numpy as np
from compute_week9 import compute_kdown


def test_compute_kdown_night_is_zero():
    svf = np.array([[0.2, 0.8], [1.0, 0.0]])
    result = compute_kdown(svf, sun_altitude_deg=-5.0, radG=895.0)
    np.testing.assert_array_equal(result, np.zeros_like(svf))


def test_compute_kdown_day_scales_by_svf():
    svf = np.array([0.0, 0.5, 1.0])
    result = compute_kdown(svf, sun_altitude_deg=45.0, radG=800.0)
    np.testing.assert_allclose(result, [0.0, 400.0, 800.0])


def test_compute_kdown_clips_to_radG():
    svf = np.array([1.5])  # out-of-range input should still clip output
    result = compute_kdown(svf, sun_altitude_deg=45.0, radG=800.0)
    np.testing.assert_allclose(result, [800.0])


def test_compute_kdown_returns_float_array():
    svf = np.array([[1, 0], [0, 1]], dtype=int)
    result = compute_kdown(svf, sun_altitude_deg=45.0, radG=100.0)
    assert result.dtype == np.float64
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "D:\San\GA_SUMMER_2026\hello_qgis_plugin" && python -m pytest tests/test_compute_week9.py -v`
Expected: FAIL with `ImportError: cannot import name 'compute_kdown'`

- [ ] **Step 3: Implement `compute_kdown`**

Add to `compute_week9.py`:

```python
def compute_kdown(svf_array, sun_altitude_deg, radG):
    """Isotropic-sky incoming shortwave: radG * SVF during day, zero at night.

    svf_array: numpy array, sky view factor, nominally 0..1 per pixel.
    sun_altitude_deg: sun altitude in degrees (90 - zenith).
    radG: manual global radiation constant, W/m^2.
    """
    svf_array = np.asarray(svf_array, dtype=float)
    if sun_altitude_deg <= 0:
        return np.zeros_like(svf_array, dtype=float)
    kdown = radG * svf_array
    return np.clip(kdown, 0.0, radG)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "D:\San\GA_SUMMER_2026\hello_qgis_plugin" && python -m pytest tests/test_compute_week9.py -v`
Expected: PASS (7 tests total)

- [ ] **Step 5: Commit**

```bash
git add hello_qgis_plugin/compute_week9.py hello_qgis_plugin/tests/test_compute_week9.py
git commit -m "feat: add compute_kdown isotropic Kdown (Week 9)"
```

---

### Task 3: `compute_tmrt_like`

**Files:**
- Modify: `D:\San\GA_SUMMER_2026\hello_qgis_plugin\compute_week9.py`
- Test: `D:\San\GA_SUMMER_2026\hello_qgis_plugin\tests\test_compute_week9.py`

- [ ] **Step 1: Write the failing tests**

Append to `test_compute_week9.py`:

```python
from compute_week9 import compute_tmrt_like


def test_compute_tmrt_like_matches_week8_formula():
    kdown = np.array([0.0, 1000.0])
    result = compute_tmrt_like(kdown, ta=32.0, wind=2.0, alpha=0.7, beta=0.25)
    # Ta + alpha*(kdown/100) - beta*wind
    # kdown=0:    32 + 0    - 0.5 = 31.5
    # kdown=1000: 32 + 7.0  - 0.5 = 38.5
    np.testing.assert_allclose(result, [31.5, 38.5])


def test_compute_tmrt_like_clips_to_range():
    kdown = np.array([1e6, -1e6])
    result = compute_tmrt_like(kdown, ta=32.0, wind=0.0, alpha=1.0, beta=1.0)
    assert result[0] == 80.0
    assert result[1] == -30.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "D:\San\GA_SUMMER_2026\hello_qgis_plugin" && python -m pytest tests/test_compute_week9.py -v`
Expected: FAIL with `ImportError: cannot import name 'compute_tmrt_like'`

- [ ] **Step 3: Implement `compute_tmrt_like`**

Add to `compute_week9.py`:

```python
def compute_tmrt_like(kdown, ta, wind, alpha, beta):
    """Week 8/9 baseline formula: Ta + alpha*(Kdown/100) - beta*Wind, clipped to [-30, 80]."""
    kdown = np.asarray(kdown, dtype=float)
    tmrt = ta + alpha * (kdown / 100.0) - beta * wind
    return np.clip(tmrt, -30.0, 80.0)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "D:\San\GA_SUMMER_2026\hello_qgis_plugin" && python -m pytest tests/test_compute_week9.py -v`
Expected: PASS (9 tests total)

- [ ] **Step 5: Commit**

```bash
git add hello_qgis_plugin/compute_week9.py hello_qgis_plugin/tests/test_compute_week9.py
git commit -m "feat: add compute_tmrt_like formula (Week 9)"
```

---

### Task 4: time/location dict builders and sun-altitude conversion

**Files:**
- Modify: `D:\San\GA_SUMMER_2026\hello_qgis_plugin\compute_week9.py`
- Test: `D:\San\GA_SUMMER_2026\hello_qgis_plugin\tests\test_compute_week9.py`

- [ ] **Step 1: Write the failing tests**

Append to `test_compute_week9.py`:

```python
from compute_week9 import (
    build_time_dict,
    build_location_dict,
    sun_altitude_from_zenith,
    resolve_sun_altitude,
)


def test_build_time_dict():
    result = build_time_dict(year=2026, month=7, day=12, hour=14, minute=30, utc_offset=1.0)
    assert result == {
        "year": 2026, "month": 7, "day": 12,
        "hour": 14, "min": 30, "sec": 0, "UTC": 1.0,
    }


def test_build_location_dict():
    result = build_location_dict(lat=27.70661, lon=-97.33157, altitude=3.0)
    assert result == {"latitude": 27.70661, "longitude": -97.33157, "altitude": 3.0}


def test_sun_altitude_from_zenith():
    assert sun_altitude_from_zenith(60.0) == 30.0
    assert sun_altitude_from_zenith(95.0) == -5.0


def test_resolve_sun_altitude_calls_injected_sun_position_func():
    time_dict = build_time_dict(2026, 7, 12, 12, 0, 1.0)
    location_dict = build_location_dict(27.7, -97.3, 3.0)

    def fake_sun_position(time, location):
        assert time == time_dict
        assert location == location_dict
        return {"zenith": 50.0, "azimuth": 180.0}

    altitude, azimuth = resolve_sun_altitude(time_dict, location_dict, fake_sun_position)
    assert altitude == 40.0
    assert azimuth == 180.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "D:\San\GA_SUMMER_2026\hello_qgis_plugin" && python -m pytest tests/test_compute_week9.py -v`
Expected: FAIL with `ImportError: cannot import name 'build_time_dict'`

- [ ] **Step 3: Implement the four functions**

Add to `compute_week9.py`:

```python
def build_time_dict(year, month, day, hour, minute, utc_offset):
    """Build the time dict shape UMEP's sun_position() expects."""
    return {
        "year": year, "month": month, "day": day,
        "hour": hour, "min": minute, "sec": 0, "UTC": utc_offset,
    }


def build_location_dict(lat, lon, altitude):
    """Build the location dict shape UMEP's sun_position() expects."""
    return {"latitude": lat, "longitude": lon, "altitude": altitude}


def sun_altitude_from_zenith(zenith_deg):
    """Sun altitude (degrees above horizon) from zenith angle (degrees from vertical)."""
    return 90.0 - zenith_deg


def resolve_sun_altitude(time_dict, location_dict, sun_position_func):
    """Call sun_position_func(time_dict, location_dict) and return (altitude, azimuth).

    sun_position_func is dependency-injected so this stays testable without
    importing UMEP's real sun_position (which requires a running QGIS session
    to locate). In production, hello_plugin.py passes the real function via
    locate_umep_sun_position().
    """
    sun = sun_position_func(time_dict, location_dict)
    return sun_altitude_from_zenith(sun["zenith"]), sun["azimuth"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "D:\San\GA_SUMMER_2026\hello_qgis_plugin" && python -m pytest tests/test_compute_week9.py -v`
Expected: PASS (13 tests total)

- [ ] **Step 5: Commit**

```bash
git add hello_qgis_plugin/compute_week9.py hello_qgis_plugin/tests/test_compute_week9.py
git commit -m "feat: add time/location dict builders and sun altitude resolver (Week 9)"
```

---

### Task 5 (optional stretch goal): `clear_sky_radG`

Per spec §6.1, this is non-blocking — implement only if Tasks 1-4 and the integration tasks (6-9) are done with time remaining. If skipped, skip this task entirely and proceed to Task 6; do not leave a partial/broken version in `compute_week9.py`.

**Files:**
- Modify: `D:\San\GA_SUMMER_2026\hello_qgis_plugin\compute_week9.py`
- Test: `D:\San\GA_SUMMER_2026\hello_qgis_plugin\tests\test_compute_week9.py`

- [ ] **Step 1: Write the failing tests**

Append to `test_compute_week9.py`:

```python
from compute_week9 import clear_sky_radG


def test_clear_sky_radG_zero_at_night():
    assert clear_sky_radG(sun_altitude_deg=-10.0, i0=1361.0) == 0.0


def test_clear_sky_radG_scales_with_altitude():
    low = clear_sky_radG(sun_altitude_deg=10.0, i0=1361.0, transmissivity=0.75)
    high = clear_sky_radG(sun_altitude_deg=80.0, i0=1361.0, transmissivity=0.75)
    assert 0.0 < low < high

def test_clear_sky_radG_default_transmissivity():
    result = clear_sky_radG(sun_altitude_deg=90.0, i0=1000.0)
    # sin(90deg) == 1.0, default transmissivity 0.75
    np.testing.assert_allclose(result, 750.0, atol=1e-6)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "D:\San\GA_SUMMER_2026\hello_qgis_plugin" && python -m pytest tests/test_compute_week9.py -v`
Expected: FAIL with `ImportError: cannot import name 'clear_sky_radG'`

- [ ] **Step 3: Implement `clear_sky_radG`**

Add to `compute_week9.py`:

```python
def clear_sky_radG(sun_altitude_deg, i0, transmissivity=0.75):
    """Optional stretch-goal clear-sky radG estimate (spec sec 6.1).

    Not a real clearness-index model -- a fixed-transmissivity placeholder
    so radG varies with sun angle instead of staying a flat manual constant.
    """
    if sun_altitude_deg <= 0:
        return 0.0
    return float(i0 * np.sin(np.radians(sun_altitude_deg)) * transmissivity)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "D:\San\GA_SUMMER_2026\hello_qgis_plugin" && python -m pytest tests/test_compute_week9.py -v`
Expected: PASS (16 tests total)

- [ ] **Step 5: Commit**

```bash
git add hello_qgis_plugin/compute_week9.py hello_qgis_plugin/tests/test_compute_week9.py
git commit -m "feat: add optional clear_sky_radG stretch-goal estimate (Week 9)"
```

---

### Task 6: `locate_umep_sun_position()` in `hello_plugin.py`

This function is QGIS-bound (needs `qgis.core.QgsApplication`) and cannot be unit tested outside a running QGIS session. No test step here — verified manually in Task 9's QGIS test matrix.

**Files:**
- Modify: `D:\San\GA_SUMMER_2026\hello_qgis_plugin\hello_plugin.py`

- [ ] **Step 1: Add the import locator function**

Add near the top of `hello_plugin.py`, after the existing imports (after line 32, before `WGS84_WKT`):

```python
def locate_umep_sun_position():
    """Find and import UMEP's real sun_position() from the installed UMEP plugin.

    Raises ImportError with a clear, actionable message if UMEP is not
    installed in this QGIS profile -- no silent fallback to a fabricated
    sun position (spec sec 3.2).
    """
    from qgis.core import QgsApplication

    profile_path = QgsApplication.qgisSettingsDirPath()
    sun_pos_dir = os.path.join(
        profile_path, "python", "plugins", "UMEP",
        "Utilities", "SEBESOLWEIGCommonFiles",
    )
    if not os.path.isdir(sun_pos_dir):
        raise ImportError(
            "UMEP plugin not found at {}. Install and enable the UMEP "
            "plugin (Plugins -> Manage and Install Plugins -> UMEP) "
            "before running the Week 9 computation.".format(sun_pos_dir)
        )
    if sun_pos_dir not in sys.path:
        sys.path.insert(0, sun_pos_dir)
    from sun_position import sun_position  # noqa: E402

    return sun_position
```

- [ ] **Step 2: Add the `sys` import**

Check the top of `hello_plugin.py` (currently `import os` and `from datetime import datetime` at lines 8-9). Add `import sys` alongside them:

```python
import os
import sys
from datetime import datetime
```

- [ ] **Step 3: Manual verification (no automated test possible)**

Manual check in QGIS Python console (Plugins -> Python Console), with the `hello_qgis_plugin` installed:

```python
from hello_qgis_plugin.hello_plugin import locate_umep_sun_position
sun_position = locate_umep_sun_position()
print(sun_position({"year": 2026, "month": 7, "day": 12, "hour": 12, "min": 0, "sec": 0, "UTC": 1.0},
                    {"latitude": 27.7, "longitude": -97.3, "altitude": 3.0}))
```

Expected: prints a dict with `zenith` and `azimuth` keys, no exception.

- [ ] **Step 4: Commit**

```bash
git add hello_qgis_plugin/hello_plugin.py
git commit -m "feat: add locate_umep_sun_position import locator (Week 9)"
```

---

### Task 7: New GUI controls in `HelloDialog`

**Files:**
- Modify: `D:\San\GA_SUMMER_2026\hello_qgis_plugin\hello_plugin.py`

- [ ] **Step 1: Add the SVF raster combo**

In `hello_plugin.py`, inside `HelloDialog.__init__`, immediately after the existing `self.combo_poi` block (after the line `layers_form.addRow("Point layer (optional):", self.combo_poi)`, before `layers_box.setLayout(layers_form)`), add:

```python
        self.combo_svf = QgsMapLayerComboBox()
        self.combo_svf.setFilters(QgsMapLayerProxyModel.Filter.RasterLayer)
        layers_form.addRow("SVF raster (required, Week 9):", self.combo_svf)
```

- [ ] **Step 2: Add date/time/UTC/radG controls**

In `hello_plugin.py`, add these imports to the `qgis.PyQt.QtWidgets` import block (alongside `QDoubleSpinBox`):

```python
    QSpinBox,
```

Then, inside `HelloDialog.__init__`, after the existing `params_box.setLayout(params_form)` / `root.addWidget(params_box)` lines (after the Week 7/8 Parameters group, before the Output group), add a new group:

```python
        sun_box = QGroupBox("Sun position (Week 9)")
        sun_form = QFormLayout()

        self.spin_year = QSpinBox()
        self.spin_year.setRange(1900, 2100)
        self.spin_year.setValue(datetime.now().year)
        sun_form.addRow("Year:", self.spin_year)

        self.spin_month = QSpinBox()
        self.spin_month.setRange(1, 12)
        self.spin_month.setValue(datetime.now().month)
        sun_form.addRow("Month:", self.spin_month)

        self.spin_day = QSpinBox()
        self.spin_day.setRange(1, 31)
        self.spin_day.setValue(datetime.now().day)
        sun_form.addRow("Day:", self.spin_day)

        self.spin_hour = QSpinBox()
        self.spin_hour.setRange(0, 23)
        self.spin_hour.setValue(12)
        sun_form.addRow("Hour (local):", self.spin_hour)

        self.spin_minute = QSpinBox()
        self.spin_minute.setRange(0, 59)
        self.spin_minute.setValue(0)
        sun_form.addRow("Minute:", self.spin_minute)

        self.spin_utc_offset = QDoubleSpinBox()
        self.spin_utc_offset.setRange(-12.0, 12.0)
        self.spin_utc_offset.setSingleStep(0.5)
        self.spin_utc_offset.setValue(1.0)
        sun_form.addRow("UTC offset:", self.spin_utc_offset)

        self.spin_radG = QDoubleSpinBox()
        self.spin_radG.setRange(1.0, 1300.0)
        self.spin_radG.setSingleStep(5.0)
        self.spin_radG.setValue(895.0)
        sun_form.addRow("Global radiation radG (W/m2):", self.spin_radG)

        sun_box.setLayout(sun_form)
        root.addWidget(sun_box)
```

- [ ] **Step 3: Manual verification (no automated test possible for Qt widgets)**

Reinstall the plugin (copy `hello_qgis_plugin/` to the QGIS profile plugins dir, same as prior weeks), reload it in QGIS, open the dialog. Confirm: "SVF raster" picker appears under Layers; "Sun position (Week 9)" group appears with Year/Month/Day/Hour/Minute/UTC offset/radG fields, defaulting to today's date, 12:00, UTC 1.0, radG 895.

- [ ] **Step 4: Commit**

```bash
git add hello_qgis_plugin/hello_plugin.py
git commit -m "feat: add SVF picker and sun-position GUI controls (Week 9)"
```

---

### Task 8: Rewrite `Worker` to use `compute_week9`

**Files:**
- Modify: `D:\San\GA_SUMMER_2026\hello_qgis_plugin\hello_plugin.py`

- [ ] **Step 1: Add the compute_week9 import**

At the top of `hello_plugin.py`, after the existing `from osgeo import gdal, osr` line, add:

```python
from .compute_week9 import (
    compute_kdown,
    compute_tmrt_like,
    daynight_flag,
    build_time_dict,
    build_location_dict,
    resolve_sun_altitude,
)
```

- [ ] **Step 2: Extend `Worker.__init__` to accept the new parameters**

Replace the `Worker.__init__` signature and body (currently `hello_plugin.py:148-167`) with:

```python
    def __init__(
        self,
        primary_uri,
        svf_uri,
        output_dir,
        run_prefix,
        use_timestamp,
        ta,
        wind,
        alpha,
        beta,
        year,
        month,
        day,
        hour,
        minute,
        utc_offset,
        radG,
    ):
        super().__init__()
        self.primary_uri = primary_uri
        self.svf_uri = svf_uri
        self.output_dir = output_dir
        self.run_prefix = run_prefix.strip() or "run"
        self.use_timestamp = use_timestamp
        self.ta = float(ta)
        self.wind = float(wind)
        self.alpha = float(alpha)
        self.beta = float(beta)
        self.year = int(year)
        self.month = int(month)
        self.day = int(day)
        self.hour = int(hour)
        self.minute = int(minute)
        self.utc_offset = float(utc_offset)
        self.radG = float(radG)
        self._cancel_requested = False
```

- [ ] **Step 3: Replace the computation block in `Worker.run()`**

Replace the body of `Worker.run()` from the `self.progress.emit(5, ...)` line through the `tmrt_like = ...` / `tmrt_like = np.clip(...)` lines (currently `hello_plugin.py:177-211`) with:

```python
    def run(self):
        try:
            self.progress.emit(5, "Opening primary raster (for lat/lon/altitude)...")
            ds = gdal.Open(self.primary_uri)
            if ds is None:
                raise ValueError("Could not open primary raster in worker.")

            self._check_cancel()
            primary_arr = ds.ReadAsArray().astype(float)
            if primary_arr.ndim > 2:
                primary_arr = primary_arr[0]

            self.progress.emit(15, "Opening SVF raster...")
            svf_ds = gdal.Open(self.svf_uri)
            if svf_ds is None:
                raise ValueError("Could not open SVF raster in worker.")
            svf_arr = svf_ds.ReadAsArray().astype(float)
            if svf_arr.ndim > 2:
                svf_arr = svf_arr[0]
            svf_band = svf_ds.GetRasterBand(1)
            svf_nodata = svf_band.GetNoDataValue()

            band = ds.GetRasterBand(1)
            nodata_in = band.GetNoDataValue()

            mask = np.zeros(primary_arr.shape, dtype=bool)
            if nodata_in is not None:
                mask = mask | (primary_arr == nodata_in)
            if svf_nodata is not None:
                mask = mask | (svf_arr == svf_nodata)

            self.progress.emit(30, "Computing sun position...")
            self._check_cancel()

            altitude = float(np.median(primary_arr[~mask])) if mask.any() else float(np.median(primary_arr))
            if altitude <= 0:
                altitude = 3.0

            geotransform = ds.GetGeoTransform()
            width = ds.RasterXSize
            height = ds.RasterYSize
            minx = geotransform[0]
            miny = geotransform[3] + width * geotransform[4] + height * geotransform[5]
            old_cs = osr.SpatialReference()
            old_cs.ImportFromWkt(ds.GetProjection())
            new_cs = osr.SpatialReference()
            new_cs.ImportFromWkt(WGS84_WKT)
            transform = osr.CoordinateTransformation(old_cs, new_cs)
            lonlat = transform.TransformPoint(minx, miny)
            gdalver = float(gdal.__version__[0])
            if gdalver >= 3.0:
                lat, lon = lonlat[1], lonlat[0]
            else:
                lat, lon = lonlat[0], lonlat[1]

            time_dict = build_time_dict(
                self.year, self.month, self.day, self.hour, self.minute, self.utc_offset
            )
            location_dict = build_location_dict(lat, lon, altitude)
            sun_position_func = locate_umep_sun_position()
            sun_altitude, sun_azimuth = resolve_sun_altitude(
                time_dict, location_dict, sun_position_func
            )

            self.progress.emit(50, "Computing Kdown and Tmrt-like raster...")
            self._check_cancel()

            kdown = compute_kdown(svf_arr, sun_altitude, self.radG)
            tmrt_like = compute_tmrt_like(kdown, self.ta, self.wind, self.alpha, self.beta)

            nodata_out = -9999.0
            if mask.any():
                tmrt_like[mask] = nodata_out

            flag = daynight_flag(sun_altitude)
```

- [ ] **Step 4: Update the output-writing block to use the new filename and run_info**

Replace the block starting at `self.progress.emit(60, "Preparing output folder...")` through the `meta = {...}` dict and `run_info` write (currently `hello_plugin.py:217-266`) with:

```python
            self.progress.emit(60, "Preparing output folder...")
            self._check_cancel()

            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            run_name = self.run_prefix
            if self.use_timestamp:
                run_name = "{}_{}".format(run_name, stamp)
            run_dir = os.path.join(self.output_dir, run_name)
            os.makedirs(run_dir, exist_ok=True)

            out_path = os.path.join(run_dir, "tmrt_like_{}.tif".format(flag))
            drv = gdal.GetDriverByName("GTiff")
            out_ds = drv.Create(
                out_path,
                ds.RasterXSize,
                ds.RasterYSize,
                1,
                gdal.GDT_Float32,
            )
            if out_ds is None:
                raise RuntimeError("Failed to create output GeoTIFF.")

            self.progress.emit(80, "Writing output GeoTIFF...")
            self._check_cancel()

            out_ds.SetGeoTransform(ds.GetGeoTransform())
            out_ds.SetProjection(ds.GetProjection())
            out_band = out_ds.GetRasterBand(1)
            out_band.SetNoDataValue(nodata_out)
            out_band.WriteArray(tmrt_like.astype(np.float32))
            out_band.FlushCache()
            out_ds.FlushCache()

            valid_out = tmrt_like[tmrt_like != nodata_out]
            meta = {
                "ta": self.ta,
                "wind": self.wind,
                "alpha": self.alpha,
                "beta": self.beta,
                "radG": self.radG,
                "utc_offset": self.utc_offset,
                "date": "{:04d}-{:02d}-{:02d} {:02d}:{:02d}".format(
                    self.year, self.month, self.day, self.hour, self.minute
                ),
                "lat": lat,
                "lon": lon,
                "sun_altitude": sun_altitude,
                "sun_azimuth": sun_azimuth,
                "daynight_flag": flag,
                "input_uri": self.primary_uri,
                "svf_uri": self.svf_uri,
                "output_path": out_path,
                "min": float(np.min(valid_out)) if valid_out.size else nodata_out,
                "max": float(np.max(valid_out)) if valid_out.size else nodata_out,
                "mean": float(np.mean(valid_out)) if valid_out.size else nodata_out,
            }

            run_info = os.path.join(run_dir, "run_info_week9.txt")
            with open(run_info, "w", encoding="utf-8") as fh:
                fh.write("SOLWEIG Builder sun-position computation (Week 9)\n")
                for key in (
                    "input_uri", "svf_uri", "output_path", "date", "utc_offset",
                    "lat", "lon", "sun_altitude", "sun_azimuth", "daynight_flag",
                    "radG", "ta", "wind", "alpha", "beta", "min", "max", "mean",
                ):
                    fh.write("{}: {}\n".format(key, meta[key]))

            self.progress.emit(100, "Finished.")
            self.finished.emit(out_path, meta)
        except Exception as exc:
            self.error.emit(str(exc))
```

- [ ] **Step 5: Update `start_run()` to validate the SVF raster and pass the new Worker args**

In `HelloDialog.start_run()` (currently `hello_plugin.py:515-570`), after the existing primary-raster-required check (`if primary is None: ...`), add an SVF-required check:

```python
        svf_layer = self.combo_svf.currentLayer()
        if svf_layer is None:
            QMessageBox.critical(self, "Error", "No SVF raster selected (required for Week 9).")
            return
```

Then replace the `self.worker = Worker(...)` construction with:

```python
        svf_uri = _layer_uri(svf_layer)
        self.thread = QThread()
        self.worker = Worker(
            primary_uri=uri,
            svf_uri=svf_uri,
            output_dir=output_dir,
            run_prefix=self.edit_run_prefix.text(),
            use_timestamp=self.chk_timestamp.isChecked(),
            ta=self.spin_ta.value(),
            wind=self.spin_wind.value(),
            alpha=self.spin_alpha.value(),
            beta=self.spin_beta.value(),
            year=self.spin_year.value(),
            month=self.spin_month.value(),
            day=self.spin_day.value(),
            hour=self.spin_hour.value(),
            minute=self.spin_minute.value(),
            utc_offset=self.spin_utc_offset.value(),
            radG=self.spin_radG.value(),
        )
```

- [ ] **Step 6: Update `on_worker_finished` summary text to show sun info**

In `on_worker_finished` (currently `hello_plugin.py:581-603`), after the existing `self.summary.append("Finished: {}"...)` line, add:

```python
        self.summary.append(
            "Sun: altitude={:.2f} deg, azimuth={:.2f} deg, flag={}".format(
                meta["sun_altitude"], meta["sun_azimuth"], meta["daynight_flag"]
            )
        )
```

- [ ] **Step 7: Manual verification in QGIS (no automated test possible for Worker/Qt code)**

Reinstall the plugin, open QGIS with `Solweig_latest` project. Run twice:
1. Primary raster = `DSM_TAMUCC`, SVF raster = `svf`, date/time = today, 12:00 noon, radG = 895. Expect: output filename ends `_D.tif`, visible gradient following `svf`, `run_info_week9.txt` shows `daynight_flag: D` and a real `sun_altitude` > 0.
2. Same inputs but hour = 0 (midnight). Expect: output filename ends `_N.tif`, entire raster is flat `Ta - beta*Wind` (31.5 with defaults), `run_info_week9.txt` shows `daynight_flag: N` and `sun_altitude` <= 0.

Confirm both runs auto-load into QGIS and both `run_info_week9.txt` files contain plausible (non-crashing) `sun_altitude`/`sun_azimuth` values.

- [ ] **Step 8: Commit**

```bash
git add hello_qgis_plugin/hello_plugin.py
git commit -m "feat: wire Worker to real sun-position Kdown computation (Week 9)"
```

---

### Task 9: Version bump and weekly doc update

**Files:**
- Modify: `D:\San\GA_SUMMER_2026\hello_qgis_plugin\metadata.txt`
- Modify: `D:\San\GA_SUMMER_2026\UMEP\SOLWEIG_Weekly_Updates.md`

- [ ] **Step 1: Bump plugin version**

In `metadata.txt`, change:

```
version=0.4
```

to:

```
version=0.5
```

And change the `about=` line to:

```
about=Week 9: Replaces the Week 8 placeholder with real sun-position-driven Kdown (UMEP sun_position + SVF, isotropic sky, day/night branch). Output now genuinely responds to date/time instead of mirroring the input raster. Includes Week 6-8 input handling, threading, and GeoTIFF output.
```

- [ ] **Step 2: Run the full test suite one more time**

Run: `cd "D:\San\GA_SUMMER_2026\hello_qgis_plugin" && python -m pytest tests/ -v`
Expected: PASS (13 or 16 tests, depending on whether Task 5's stretch goal was completed)

- [ ] **Step 3: Add a Week 9 section to the weekly doc**

In `SOLWEIG_Weekly_Updates.md`, after the end of the "Week 8" section (after line 1056, before the "## Cumulative status (Weeks 1-8)" heading), insert a new section documenting: what was built (real sun-position Kdown, SVF requirement, day/night branch), the Week 8 finding that motivated it (affine-transform limitation — output always mirrored input regardless of physics), the test matrix results from Task 8 Step 7, and screenshots once captured. Follow the existing Week 6/7/8 section structure (Goals / Tasks completed / Code added / Hands-on test / Screenshots & deliverables / What we learned / Next week).

Update the "## Cumulative status" heading to "Weeks 1-9" and update the roadmap table's Week 9 status if one exists.

- [ ] **Step 4: Commit**

```bash
git add hello_qgis_plugin/metadata.txt SOLWEIG_Weekly_Updates.md
git commit -m "docs: bump plugin to v0.5, document Week 9 (real sun-position Kdown)"
```

---

## Plan self-review notes

- **Spec coverage:** §2 in-scope items (sun_position import, isotropic Kdown, day/night branch, manual GUI inputs, D/N filename suffix) are covered by Tasks 6-8. §3.1 GUI table covered by Task 7. §3.2 sun-position import covered by Task 6. §3.3 Worker steps 1-8 covered by Task 8 Steps 1-6. §3.4 validation covered by Task 8 Step 5. §5 test matrix covered by Task 8 Step 7 (day/night and SVF-gradient rows; radG-sensitivity and missing-SVF/mismatch rows are exercised the same way as their Week 8 equivalents and are not re-detailed step-by-step here to avoid repetition — same manual pattern, different inputs). §6.1 stretch goal covered by Task 5, explicitly optional. §7 deliverables covered by Task 9.
- **Known gap acknowledged, not silently dropped:** shadow casting and multi-timestep met-file loops are explicitly out of scope per spec §2 and not present in any task — correct, they're Week 10+.
- **Type/signature consistency check:** `compute_kdown(svf_array, sun_altitude_deg, radG)`, `compute_tmrt_like(kdown, ta, wind, alpha, beta)`, `daynight_flag(sun_altitude_deg)`, `build_time_dict(year, month, day, hour, minute, utc_offset)`, `build_location_dict(lat, lon, altitude)`, `resolve_sun_altitude(time_dict, location_dict, sun_position_func)` — used with these exact names/argument orders consistently across Tasks 2-4 (tests) and Task 8 (integration). `locate_umep_sun_position()` takes no args, matches Task 6 and Task 8 Step 3 usage.
