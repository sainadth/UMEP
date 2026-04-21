const TAMUCC_LAT = 27.713651;
const TAMUCC_LON = -97.325456;

const streets = L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19,
  attribution: "&copy; OpenStreetMap contributors",
});

const satellite = L.tileLayer(
  "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
  {
    maxZoom: 19,
    attribution: "Tiles &copy; Esri",
  }
);

const map = L.map("map", {
  layers: [streets],
}).setView([TAMUCC_LAT, TAMUCC_LON], 14);

L.control.layers(
  {
    Streets: streets,
    Satellite: satellite,
  },
  {},
  { collapsed: false }
).addTo(map);

let heatLayer = null;
let demOverlay = null;
let dsmOverlay = null;
let timerId = null;
let tmrtOpacity = 0.6;
let demOpacity = 0.55;
let dsmOpacity = 0.55;
let tmrtVisible = true;
let demVisible = true;
let dsmVisible = true;

const runBtn = document.getElementById("runBtn");
const liveBtn = document.getElementById("liveBtn");
const statusBox = document.getElementById("statusBox");
const weatherBox = document.getElementById("weatherBox");
const selectedBox = document.getElementById("selectedBox");
const demInfoBox = document.getElementById("demInfoBox");
const dsmInfoBox = document.getElementById("dsmInfoBox");

const latInput = document.getElementById("latInput");
const lonInput = document.getElementById("lonInput");
const gridInput = document.getElementById("gridInput");
const spanInput = document.getElementById("spanInput");
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

let legendTmrtToggle = null;
let legendTmrtOpacity = null;
let legendDemToggle = null;
let legendDemOpacity = null;
let legendDsmToggle = null;
let legendDsmOpacity = null;

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

const legendMinEl = document.getElementById("legendMin");
const legendMaxEl = document.getElementById("legendMax");

latInput.value = TAMUCC_LAT;
lonInput.value = TAMUCC_LON;

function setStatus(msg) {
  statusBox.textContent = msg;
}

function updateLegend(min, max) {
  legendMinEl.textContent = Number.isFinite(min) ? `${min.toFixed(1)}` : "min";
  legendMaxEl.textContent = Number.isFinite(max) ? `${max.toFixed(1)}` : "max";
}

function applyLayerVisibility(layer, visible) {
  if (!layer) {
    return;
  }
  if (visible && !map.hasLayer(layer)) {
    layer.addTo(map);
  }
  if (!visible && map.hasLayer(layer)) {
    map.removeLayer(layer);
  }
}

function setLayerState(which, visible, opacity) {
  if (which === "tmrt") {
    tmrtVisible = visible;
    tmrtOpacity = opacity;
    tmrtLayerToggle.checked = visible;
    tmrtOpacityInput.value = String(opacity);
    applyLayerVisibility(heatLayer, visible);
    if (heatLayer && visible) heatLayer.setStyle({ fillOpacity: opacity });
    if (legendTmrtToggle) legendTmrtToggle.checked = visible;
    if (legendTmrtOpacity) legendTmrtOpacity.value = String(opacity);
  } else if (which === "dem") {
    demVisible = visible;
    demOpacity = opacity;
    demLayerToggle.checked = visible;
    demOpacityInput.value = String(opacity);
    applyLayerVisibility(demOverlay, visible);
    if (demOverlay && visible) demOverlay.setOpacity(opacity);
    if (legendDemToggle) legendDemToggle.checked = visible;
    if (legendDemOpacity) legendDemOpacity.value = String(opacity);
  } else if (which === "dsm") {
    dsmVisible = visible;
    dsmOpacity = opacity;
    dsmLayerToggle.checked = visible;
    dsmOpacityInput.value = String(opacity);
    applyLayerVisibility(dsmOverlay, visible);
    if (dsmOverlay && visible) dsmOverlay.setOpacity(opacity);
    if (legendDsmToggle) legendDsmToggle.checked = visible;
    if (legendDsmOpacity) legendDsmOpacity.value = String(opacity);
  }
}

function colorScale(value, min, max) {
  const x = Math.max(0, Math.min(1, (value - min) / Math.max(1e-6, max - min)));
  const r = Math.round(255 * Math.max(0, Math.min(1, 1.6 * x - 0.3)));
  const g = Math.round(255 * Math.max(0, Math.min(1, 1.2 - Math.abs(1.3 * x - 0.6))));
  const b = Math.round(255 * Math.max(0, Math.min(1, 1.2 - 1.6 * x)));
  return `rgb(${r},${g},${b})`;
}

function styleFeature(feature, min, max) {
  const tmrt = feature.properties.tmrt;
  return {
    fillColor: colorScale(tmrt, min, max),
    weight: 0,
    fillOpacity: tmrtOpacity,
    color: "transparent",
  };
}

function updateWeatherBox(meta) {
  weatherBox.textContent = JSON.stringify(
    {
      time: meta.time,
      timezone: meta.timezone,
      Ta_C: Number(meta.Ta).toFixed(2),
      RH_pct: Number(meta.RH).toFixed(1),
      Ws_mps: Number(meta.Ws).toFixed(2),
      radG_Wm2: Number(meta.radG).toFixed(1),
      radI_Wm2: Number(meta.radI).toFixed(1),
      radD_Wm2: Number(meta.radD).toFixed(1),
      pressure: Number(meta.P).toFixed(1),
      solar_altitude_deg: Number(meta.solar_altitude).toFixed(2),
      solar_azimuth_deg: Number(meta.solar_azimuth).toFixed(2),
    },
    null,
    2
  );
}

function updateSelectedBox(feature) {
  const p = feature.properties;
  const ring = feature.geometry.coordinates[0];
  const centerLon = (ring[0][0] + ring[2][0]) / 2;
  const centerLat = (ring[0][1] + ring[2][1]) / 2;

  selectedBox.textContent = JSON.stringify(
    {
      lat: Number(centerLat).toFixed(6),
      lon: Number(centerLon).toFixed(6),
      tmrt_C: Number(p.tmrt).toFixed(2),
      svf: Number(p.svf).toFixed(3),
      shade_fraction: Number(p.shade_fraction).toFixed(3),
      kdown_Wm2: Number(p.kdown).toFixed(2),
      kup_Wm2: Number(p.kup).toFixed(2),
      ldown_Wm2: Number(p.ldown).toFixed(2),
      lup_Wm2: Number(p.lup).toFixed(2),
      elev_m: p.elev_m !== undefined ? Number(p.elev_m).toFixed(2) : null,
      terrain_slope_norm:
        p.terrain_slope_norm !== undefined ? Number(p.terrain_slope_norm).toFixed(3) : null,
      terrain_roughness_norm:
        p.terrain_roughness_norm !== undefined ? Number(p.terrain_roughness_norm).toFixed(3) : null,
      grid_i: p.i,
      grid_j: p.j,
    },
    null,
    2
  );
}

async function fetchJson(url) {
  const res = await fetch(url);
  if (!res.ok) {
    const txt = await res.text();
    throw new Error(`Request failed: ${res.status} ${txt}`);
  }
  return res.json();
}

async function postDem(file) {
  const body = new FormData();
  body.append("file", file);

  const res = await fetch("/api/dem/upload", {
    method: "POST",
    body,
  });

  if (!res.ok) {
    const txt = await res.text();
    throw new Error(`DEM upload failed: ${res.status} ${txt}`);
  }

  return res.json();
}

async function postDsm(file) {
  const body = new FormData();
  body.append("file", file);

  const res = await fetch("/api/dsm/upload", {
    method: "POST",
    body,
  });

  if (!res.ok) {
    const txt = await res.text();
    throw new Error(`DSM upload failed: ${res.status} ${txt}`);
  }

  return res.json();
}

function renderDemInfo(dem) {
  if (!dem) {
    demInfoBox.textContent = "No DEM selected.";
    return;
  }

  demInfoBox.textContent = JSON.stringify(
    {
      dem_id: dem.dem_id,
      name: dem.name,
      crs: dem.crs,
      width: dem.width,
      height: dem.height,
      min_elev_m: Number(dem.min_elev).toFixed(2),
      max_elev_m: Number(dem.max_elev).toFixed(2),
    },
    null,
    2
  );
}

function renderDsmInfo(dsm) {
  if (!dsm) {
    dsmInfoBox.textContent = "No DSM selected.";
    return;
  }

  dsmInfoBox.textContent = JSON.stringify(
    {
      dsm_id: dsm.dsm_id,
      name: dsm.name,
      crs: dsm.crs,
      width: dsm.width,
      height: dsm.height,
      min_val: Number(dsm.min_val).toFixed(2),
      max_val: Number(dsm.max_val).toFixed(2),
      bounds_latlon: dsm.bounds_latlon,
    },
    null,
    2
  );
}

async function refreshDemList() {
  const payload = await fetchJson("/api/dem/list");
  const dems = payload.dems || [];
  const current = demSelect.value;

  demSelect.innerHTML = "";
  const noneOpt = document.createElement("option");
  noneOpt.value = "";
  noneOpt.textContent = "None (procedural terrain)";
  demSelect.appendChild(noneOpt);

  for (const dem of dems) {
    const opt = document.createElement("option");
    opt.value = dem.dem_id;
    opt.textContent = `${dem.name} (${dem.width}x${dem.height})`;
    demSelect.appendChild(opt);
  }

  if (current && dems.some((d) => d.dem_id === current)) {
    demSelect.value = current;
  }

  const selected = dems.find((d) => d.dem_id === demSelect.value) || null;
  renderDemInfo(selected);
}

async function refreshDsmList() {
  const payload = await fetchJson("/api/dsm/list");
  const dsms = payload.dsms || [];
  const current = dsmSelect.value;

  dsmSelect.innerHTML = "";
  const noneOpt = document.createElement("option");
  noneOpt.value = "";
  noneOpt.textContent = "None";
  dsmSelect.appendChild(noneOpt);

  for (const dsm of dsms) {
    const opt = document.createElement("option");
    opt.value = dsm.dsm_id;
    opt.textContent = `${dsm.name} (${dsm.width}x${dsm.height})`;
    dsmSelect.appendChild(opt);
  }

  if (current && dsms.some((d) => d.dsm_id === current)) {
    dsmSelect.value = current;
  }

  const selected = dsms.find((d) => d.dsm_id === dsmSelect.value) || null;
  renderDsmInfo(selected);
}

async function loadDemOverlay(demId) {
  if (demOverlay) {
    map.removeLayer(demOverlay);
    demOverlay = null;
  }

  if (!demId) {
    return;
  }

  const overlay = await fetchJson(`/api/dem/${encodeURIComponent(demId)}/overlay`);
  demOverlay = L.imageOverlay(`${overlay.image_url}?t=${Date.now()}`, overlay.bounds, {
    opacity: demOpacity,
  });
  applyLayerVisibility(demOverlay, demVisible);
}

async function loadDsmOverlay(dsmId) {
  if (dsmOverlay) {
    map.removeLayer(dsmOverlay);
    dsmOverlay = null;
  }

  if (!dsmId) {
    return;
  }

  const overlay = await fetchJson(`/api/dsm/${encodeURIComponent(dsmId)}/overlay`);
  dsmOverlay = L.imageOverlay(`${overlay.image_url}?t=${Date.now()}`, overlay.bounds, {
    opacity: dsmOpacity,
  });
  applyLayerVisibility(dsmOverlay, dsmVisible);
}

async function runPrediction() {
  const lat = Number(latInput.value);
  const lon = Number(lonInput.value);
  const grid = Number(gridInput.value);
  const span = Number(spanInput.value);
  const demId = demSelect.value;

  if (!Number.isFinite(lat) || !Number.isFinite(lon)) {
    setStatus("Invalid coordinates");
    return;
  }

  setStatus("Fetching live weather + TMRT grid...");

  try {
    const weather = await fetchJson(`/api/weather/live?lat=${lat}&lon=${lon}`);
    updateWeatherBox(weather);

    const demQuery = demId ? `&dem_id=${encodeURIComponent(demId)}` : "";
    const tmrt = await fetchJson(
      `/api/tmrt/grid?lat=${lat}&lon=${lon}&grid_size=${grid}&span_m=${span}${demQuery}`
    );

    const min = tmrt.metadata.tmrt_min;
    const max = tmrt.metadata.tmrt_max;
    updateLegend(min, max);

    if (heatLayer) {
      map.removeLayer(heatLayer);
    }

    heatLayer = L.geoJSON(tmrt, {
      style: (f) => styleFeature(f, min, max),
      onEachFeature: (feature, layer) => {
        layer.bindTooltip(
          `Tmrt: ${feature.properties.tmrt.toFixed(1)} C<br>` +
            `SVF: ${feature.properties.svf.toFixed(2)}<br>` +
            `Shade: ${(feature.properties.shade_fraction * 100).toFixed(0)}%`
        );

        layer.on("click", () => {
          updateSelectedBox(feature);
        });
      },
    });
    applyLayerVisibility(heatLayer, tmrtVisible);

    // Preselect first cell after each run so data panel is always populated.
    if (tmrt.features && tmrt.features.length > 0) {
      updateSelectedBox(tmrt.features[0]);
    }

    map.setView([lat, lon], map.getZoom());
    setStatus(
      `Updated at ${weather.time}. Tmrt range ${min.toFixed(1)} to ${max.toFixed(1)} C${
        demId ? " (DEM enabled)" : ""
      }`
    );
  } catch (err) {
    setStatus(`Error: ${err.message}`);
  }
}

runBtn.addEventListener("click", runPrediction);

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
  } finally {
    demFileInput.value = "";
  }
});

refreshDemBtn.addEventListener("click", async () => {
  try {
    await refreshDemList();
    setStatus("DEM list refreshed");
  } catch (err) {
    setStatus(`Error: ${err.message}`);
  }
});

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
  } finally {
    dsmFileInput.value = "";
  }
});

refreshDsmBtn.addEventListener("click", async () => {
  try {
    await refreshDsmList();
    setStatus("DSM list refreshed");
  } catch (err) {
    setStatus(`Error: ${err.message}`);
  }
});

demSelect.addEventListener("change", async () => {
  try {
    const payload = await fetchJson("/api/dem/list");
    const dem = (payload.dems || []).find((d) => d.dem_id === demSelect.value) || null;
    renderDemInfo(dem);
    await loadDemOverlay(demSelect.value);
  } catch (_err) {
    renderDemInfo(null);
  }
});

dsmSelect.addEventListener("change", async () => {
  try {
    const payload = await fetchJson("/api/dsm/list");
    const dsm = (payload.dsms || []).find((d) => d.dsm_id === dsmSelect.value) || null;
    renderDsmInfo(dsm);
    await loadDsmOverlay(dsmSelect.value);
  } catch (_err) {
    renderDsmInfo(null);
  }
});

liveBtn.addEventListener("click", () => {
  if (timerId) {
    clearInterval(timerId);
    timerId = null;
    liveBtn.textContent = "Start Live";
    setStatus("Live mode stopped");
    return;
  }

  runPrediction();
  timerId = setInterval(runPrediction, 5 * 60 * 1000);
  liveBtn.textContent = "Stop Live";
  setStatus("Live mode running (5 min refresh)");
});

map.on("click", (evt) => {
  latInput.value = evt.latlng.lat.toFixed(6);
  lonInput.value = evt.latlng.lng.toFixed(6);
});

Promise.all([refreshDemList(), refreshDsmList()])
  .then(async () => {
    if (demSelect.value) {
      await loadDemOverlay(demSelect.value);
    }
    if (dsmSelect.value) {
      await loadDsmOverlay(dsmSelect.value);
    }
    await runPrediction();
  })
  .catch(() => runPrediction());
