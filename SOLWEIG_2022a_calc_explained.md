# Solweig_2022a_calc — Deep Dive

**File:** `SOLWEIG/SOLWEIGpython/Solweig_2022a_calc.py`  
**Called by:** `solweigworker.py` → `Worker.run`, once per meteorological timestep.

---

## What it is

`Solweig_2022a_calc` is the **core per-timestep physics engine** of SOLWEIG. Every other module is either setup (loading data, parsing met files) or post-processing (writing rasters, computing PET/UTCI). This one function is where all the radiation math happens.

It takes ~80 parameters — the full spatial state of the scene plus one row of met data — and returns ~35 values: radiation flux grids, Tmrt, and diagnostic scalars.

---

## The two branches

The entire function forks on `altitude > 0`:

```
if altitude > 0:   ← DAYTIME  (sun above horizon)
else:              ← NIGHTTIME (sun below horizon)
```

Nighttime is trivial: all shortwave arrays are zeroed, `Lup` is a simple Stefan–Boltzmann blackbody at air temperature, and the function returns. Daytime is where everything interesting happens.

---

## Daytime sequence, step by step

### 1. Constants and sunrise time (lines 86–92)

```python
SBC = 5.67051e-8       # Stefan-Boltzmann constant
ea  = ...              # vapor pressure from Ta, RH
SNUP = daylen(jday, lat)[3]  # sunrise hour
```

`SNUP` is used later to anchor the surface temperature wave to the start of the day.

---

### 2. Vapor pressure and sky emissivity (lines 95–99)

```python
ea    = 6.107 * 10**((7.5*Ta)/(237.3+Ta)) * (RH/100.)   # hPa
msteg = 46.5 * (ea / (Ta + 273.15))
esky  = 1 - (1 + msteg)*exp(-sqrt(1.2 + 3.0*msteg)) + elvis
```

`esky` is the fraction of blackbody radiation emitted by the atmosphere — it controls how much longwave comes down from a clear sky (Prata 1996). The `elvis` term is a user-selectable correction flag (+1 if enabled).

---

### 3. Clearness index CI (lines 104–113)

```python
I0, CI, Kt, I0et, CIuncorr = clearnessindex_2013b(zen, jday, Ta, RH, radG, location, P)
```

`CI` (0–1) measures how cloudy it is relative to a clear-sky model. It is used in **four places** later:
- To correct diffuse sky radiation for clouds
- To correct surface temperature for cloud cover
- To blend isotropic longwave toward overcast blackbody
- To set nocturnal CI (the worker looks ahead to the first sunlit step)

If `onlyglobal == 1`, it also calls `diffusefraction()` here to split the measured global `radG` into `radD` (diffuse) + `radI` (direct beam normal).

---

### 4. Diffuse sky radiation field `dRad` (lines 118–134)

Two paths:

**Anisotropic (Perez model):**
```python
lv = Perez_v3(zenDeg, azimuth, radD, radI, jday, ...)  # relative luminance per sky patch
aniLum = sum over patches of: diffsh[:,:,idx] * lv[idx,2]
dRad = aniLum * radD
```

`diffsh` is a 3D array (`rows × cols × N_patches`) pre-computed by the SkyViewFactorCalculator — it tells each cell how much of each sky patch it can see. Multiplying by the Perez luminance and `radD` gives a spatially variable diffuse irradiance that depends on where the sun is.

**Isotropic fallback:**
```python
dRad = radD * svfbuveg
```

Flat fraction of diffuse sky visible, weighted by SVF accounting for vegetation.

---

### 5. Shadow raster (lines 137–144)

```python
if usevegdem:
    vegsh, sh, ... = shadowingfunction_wallheight_23(dsm, vegdem, vegdem2, azimuth, altitude, ...)
    shadow = sh - (1 - vegsh) * (1 - psi)   # vegetation partially transmits
else:
    sh, ... = shadowingfunction_wallheight_13(dsm, azimuth, altitude, ...)
    shadow = sh
```

`shadow` is a grid of 0 (shaded) to 1 (fully sunlit). The vegetation term reduces shadow where canopy is semi-transparent (`psi` is the transmissivity complement — `1 − transmissivity`).

---

### 6. Surface temperature (lines 148–177)

A **sinusoidal diurnal wave** parameterised by the land cover class:

```python
Tgamp = TgK * altmax + Tstart           # amplitude depends on max solar altitude today
Tg = Tgamp * sin( ((dectime_frac - SNUP/24) / (TmaxLST/24 - SNUP/24)) * pi/2 )
```

Then **cloud-corrected**:
```python
radG0 = radI0 * sin(altitude) + radD0   # clear-sky global
CI_TgG = (radG / radG0) + (1 - corr)   # how overcast vs. clear
Tg = Tg * CI_TgG                        # reduce Tg on cloudy days
```

`Tg` is a **temperature excess above `Ta`** (in °C), not an absolute temperature. It will be added to `Ta + 273.15` in the Stefan–Boltzmann formulas later.

---

### 7. Ground View Factors — `gvf_2018a` (lines 180–182)

```python
gvfLup, gvfalb, gvfalbnosh, [+ 12 directional variants] = gvf_2018a(wallsun, walls, buildings, ...)
```

This does an **18-direction radial scan** from each pixel. In each direction it casts a ray and accumulates: which surfaces are sunlit, what their albedo is, what longwave they emit. The return values are per-pixel weighted averages of those properties toward each cardinal hemisphere.

- `gvfLup` → used for `Lup` (upwelling longwave grid)
- `gvfalb` → used for `Kup` (reflected shortwave, shadow-weighted)
- `gvfalbnosh` → used for `Kup` (reflected shortwave, shadow-independent)

---

### 8. Surface temperature wave-delay — `TsWaveDelay_2015a` (lines 187–195)

The raw `gvfLup` is smoothed with an exponential filter:
```python
weight = exp(-33.27 * timeadd)
Lup = gvfLup*(1 - weight) + Lup_previous * weight
```

This simulates thermal inertia — surfaces don't respond instantly to solar forcing. The state arrays `Tgmap1`, `Tgmap1E/S/W/N` persist **across timesteps** (they are passed in and returned, updated each call).

---

### 9. Cylindric wedge factor `F_sh` (line 198)

```python
F_sh = cylindric_wedge(zen, svfalfa, rows, cols)
```

`F_sh` is the fraction of the cylindrical model's side surface that is **shaded by surrounding buildings**, based on the sun's zenith angle and the SVF-derived effective building-height angle. It is used in:
- `Kdown` (wall reflection term)
- `Kup` (ground reflection term)
- `Lside` (wall longwave — distinguishes sunlit vs. shaded wall fractions)

---

### 10. Shortwave fluxes (lines 202–217)

```python
# Kdown — downward on horizontal
Kdown = radI*shadow*sin(alt) + dRad + albedo_b*(1-svfbuveg)*(radG*(1-F_sh) + radD*F_sh)

# Kup — upward from ground
Kup, KupE, KupS, KupW, KupN = Kup_veg_2015a(radI, radD, radG, ...)

# Keast/Ksouth/Kwest/Knorth, KsideI, KsideD, Kside
Keast, Ksouth, Kwest, Knorth, KsideI, KsideD, Kside = Kside_veg_v2022a(radI, radD, ...)
```

`Kdown` has three components:
1. **Direct beam** hitting sunlit pixels: `radI × shadow × sin(α)`
2. **Diffuse sky** reaching each cell: `dRad`
3. **Reflected from walls**: `albedo_b × (1−svfbuveg) × ...`

`Kup` follows the same structure but uses GVF-weighted albedo maps to account for what the upward-looking hemisphere sees.

`Kside` for a **cylinder** uses `cos(α)` (perpendicular projection) rather than `sin(α)` — a cylinder integrates azimuthal incident radiation differently from a flat horizontal surface.

---

### 11. Longwave fluxes (lines 264–310)

**Ldown (downward):**
- Anisotropic: `Lcyl_v2022a` — patches with Martin & Berdahl emissivity, weighted by shadow matrices
- Isotropic: Jonsson et al. 2006 four-term SVF-weighted formula combining sky, shaded walls, sunlit walls, reflected sky

**Lside (cardinal walls):**
- `Lside_veg_v2022a` — for each of East/South/West/North: sum of sky, sunlit wall, shaded wall, vegetation, ground, and reflected contributions

When anisotropic is on and the box model is used, both the `Lcyl_v2022a` directional terms **and** the `Lside_veg_v2022a` ground terms are summed (lines 314–317).

---

### 12. Tmrt assembly (lines 321–334)

```python
# Standing cylinder, isotropic sky:
Sstr = absK*(KsideI*Fcyl + (Kdown+Kup)*Fup + (Keast+Ksouth+Kwest+Knorth)*Fside) \
     + absL*((Ldown+Lup)*Fup + (Lnorth+Least+Lsouth+Lwest)*Fside)

Tmrt = sqrt(sqrt(Sstr / (absL * SBC))) - 273.2
```

`Sstr` is the total **absorbed radiant flux density** on the human body model. The factors `Fside`, `Fup`, `Fcyl` are the angular (view) factors between the body and surrounding surfaces — they encode the body geometry (cylinder vs. box, standing vs. seated). `absK` and `absL` are human absorption coefficients for shortwave and longwave.

The final formula is the inverse Stefan–Boltzmann: find the temperature of a hypothetical uniform enclosure that would produce the same `Sstr`.

---

## Return values

The function returns ~35 values. Most are grids (same shape as the DSM):

| Return | Type | Meaning |
|---|---|---|
| `Tmrt` | grid | **Primary output** — Mean Radiant Temperature (°C) |
| `Kdown`, `Kup` | grid | Shortwave down/up on horizontal |
| `Keast`…`Knorth` | grid | Shortwave on cardinal faces |
| `Ldown`, `Lup` | grid | Longwave down/up |
| `Least`…`Lnorth` | grid | Longwave on cardinal faces |
| `shadow` | grid | Shadow fraction (0–1) |
| `Tg` | grid | Surface temperature excess (°C above Ta) |
| `esky` | scalar | Sky emissivity for this timestep |
| `CI` | scalar | Clearness index (passed through/updated) |
| `Tgmap1`…`Tgmap1N` | grid | Updated wave-delay state (persists to next call) |
| `firstdaytime` | scalar | Reset to 1 on nighttime — tells next daytime to reinit wave delay |
| `timeadd` | scalar | Accumulated wave-delay timer (persists to next call) |
| `Lside`, `L_patches` | grid/array | Anisotropic cylinder LW side; patch luminance data |

---

## Key design patterns

- **Stateful across calls** — `Tgmap1*`, `firstdaytime`, `timeadd` are returned and fed back in the next iteration. The function itself is pure; the worker manages state.
- **Two sky models coexist** — `anisotropic_sky` flag selects between Perez patches (expensive, accurate) and isotropic SVF (fast, approximate) for both shortwave and longwave.
- **Two body models** — `cyl=1` uses a cylinder (realistic for standing person); `cyl=0` uses a box (simpler, less physical).
- **Grid + scalar mixed** — Most physical fields are full numpy arrays (one value per pixel). Solar geometry, met data, and CI are scalars for the timestep.
