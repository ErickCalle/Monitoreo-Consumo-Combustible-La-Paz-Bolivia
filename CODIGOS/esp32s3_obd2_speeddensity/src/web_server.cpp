// Local dashboard: WiFi SoftAP (+ optional STA), ESPAsyncWebServer with
// a WebSocket live feed and REST endpoints to browse/download/chart
// the CSV history stored on the microSD card.
//
// The dashboard HTML/CSS/JS below is 100% self-contained (no CDN
// scripts) on purpose: clients normally reach this device only through
// its own SoftAP, which has no internet access, so any externally
// hosted library (Chart.js, etc.) would simply fail to load. The line
// chart is a small hand-rolled canvas renderer instead.
#include <Arduino.h>
#include <WiFi.h>
#include <SD.h>
#include <ArduinoJson.h>
#include <ESPAsyncWebServer.h>
#include <esp_heap_caps.h>
#include <string.h>
#include "config.h"
#include "types.h"
#include "fuel_calc.h"
#include "sd_logger.h"
#include "web_server.h"

static AsyncWebServer server(WEB_SERVER_PORT);
static AsyncWebSocket ws("/ws");

// ------------------------------------------------------------------
static const char INDEX_HTML[] PROGMEM = R"HTMLDOC(
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ESP32 OBD2 - Consumo (Speed-Density)</title>
<style>
  /* Paleta validada (colorblind-safe, contraste verificado sobre superficie
     oscura) -- ver skill dataviz/references/palette.md. Todo el archivo
     referencia estos tokens en vez de hex sueltos, para que un cambio de
     marca futuro sea editar esta lista y nada mas. */
  :root {
    color-scheme: dark;
    --bg:        #0d0d0d;
    --surface:   #1a1a19;
    --surface-2: #141413;
    --ink:       #ffffff;
    --ink-2:     #c3c2b7;
    --muted:     #898781;
    --grid:      #2c2c2a;
    --axis:      #383835;
    --border:    rgba(255,255,255,.10);
    --accent:    #3987e5;
    --good:      #0ca30c;
    --critical:  #d03b3b;
    /* 8 colores categoricos, orden fijo -- nunca reasignar por filtro */
    --v1: #3987e5; --v2: #1f9e46; --v3: #d55181; --v4: #c98500;
    --v5: #199e70; --v6: #d95926; --v7: #9085e9; --v8: #e66767;
  }
  * { box-sizing:border-box; }
  body { margin:0; padding:0; background:var(--bg); color:var(--ink);
         font-family:-apple-system,Segoe UI,Roboto,sans-serif; }
  h1 { font-size:1.05rem; margin:0 0 14px; font-weight:600; }
  h2 { font-size:.78rem; text-transform:uppercase; letter-spacing:.06em; font-weight:600;
       color:var(--muted); margin:22px 0 10px; }
  .app { display:flex; min-height:100vh; }
  .sidebar { flex:0 0 150px; background:var(--surface-2); padding:16px 10px; display:flex;
             flex-direction:column; gap:4px; border-right:1px solid var(--border); }
  .tabBtn { background:none; border:none; color:var(--ink-2); text-align:left; padding:10px 12px;
            border-radius:8px; font-size:.9rem; cursor:pointer; transition:background .15s ease, color .15s ease; }
  .tabBtn:hover:not(.active) { background:rgba(255,255,255,.06); color:var(--ink); }
  .tabBtn.active { background:var(--accent); color:white; }
  .content { flex:1; min-width:0; padding:16px 20px; }
  .tabPane { display:none; }
  .tabPane.active { display:block; animation:fadeIn .18s ease; }
  @keyframes fadeIn { from{opacity:0; transform:translateY(3px);} to{opacity:1; transform:translateY(0);} }
  .pills { display:flex; gap:8px; margin-bottom:16px; flex-wrap:wrap; }
  .pill { padding:4px 10px 4px 8px; border-radius:999px; font-size:.8rem; background:rgba(255,255,255,.06);
          color:var(--ink-2); }
  .pill::before { content:''; display:inline-block; width:7px; height:7px; border-radius:50%;
                  margin-right:6px; background:var(--muted); vertical-align:middle; }
  .pill.ok { color:var(--ink); }
  .pill.ok::before { background:var(--good); }
  .pill.bad { color:var(--ink); }
  .pill.bad::before { background:var(--critical); }
  .heroRow { display:grid; grid-template-columns:repeat(auto-fit,minmax(170px,1fr)); gap:12px; margin-bottom:18px; }
  .heroCard { background:var(--surface); border:1px solid var(--border); border-left:3px solid var(--accent);
              border-radius:10px; padding:14px 16px; }
  .heroCard .l { font-size:.78rem; color:var(--muted); margin-bottom:6px; }
  .heroCard .v { font-size:1.9rem; font-weight:700; color:var(--ink); }
  .heroCard .u { font-size:.85rem; color:var(--muted); font-weight:400; }
  .grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(130px,1fr)); gap:10px; }
  .card { background:var(--surface); border:1px solid var(--border); border-radius:10px; padding:10px 12px; }
  .card .v { font-size:1.4rem; font-weight:600; color:var(--ink); }
  .card .l { font-size:.75rem; color:var(--muted); }
  .chartWrap { position:relative; }
  canvas { width:100%; height:220px; background:var(--surface); border:1px solid var(--border);
           border-radius:10px; touch-action:none; }
  .chartNote { font-size:.72rem; color:var(--muted); margin:6px 2px 0; display:none; }
  .chartNote.show { display:block; }
  .chartTip { position:absolute; pointer-events:none; background:#20201e; border:1px solid var(--border);
              border-radius:6px; padding:6px 9px; font-size:.75rem; display:none; z-index:5; white-space:nowrap; }
  .tipRow { display:flex; align-items:center; gap:6px; padding:1px 0; }
  .tipKey { width:10px; height:2px; border-radius:1px; display:inline-block; }
  .tipVal { font-weight:600; color:var(--ink); }
  .tipLab { color:var(--ink-2); }
  .file-row { display:flex; align-items:center; gap:10px; padding:8px 0; border-bottom:1px solid var(--border); flex-wrap:wrap; }
  .file-row span { flex:1; color:var(--ink-2); }
  button, a.btn { background:var(--accent); color:white; border:none; padding:6px 12px; border-radius:6px;
        cursor:pointer; text-decoration:none; font-size:.85rem; transition:filter .15s ease, transform .1s ease; }
  button:hover, a.btn:hover { filter:brightness(1.12); }
  button:active, a.btn:active { transform:translateY(1px); }
  button.danger { background:var(--critical); }
  #historyTitle { color:var(--muted); font-size:.85rem; }
  .varPicker { display:flex; flex-wrap:wrap; gap:6px 16px; margin:10px 0 6px; font-size:.82rem; }
  .varChk { display:flex; align-items:center; gap:5px; cursor:pointer; color:var(--ink-2); transition:color .15s ease; }
  .varChk:hover { color:var(--ink); }
  .varChk .dot { width:8px; height:8px; border-radius:50%; display:inline-block; }
  @media (max-width:640px) {
    .app { flex-direction:column; }
    .sidebar { flex-direction:row; border-right:none; border-bottom:1px solid var(--border); }
    .tabBtn { flex:1; text-align:center; }
  }
</style>
</head>
<body>
<div class="app">
  <nav class="sidebar">
    <h1>ESP32-S3 OBD2</h1>
    <button class="tabBtn active" data-tab="live">En vivo</button>
    <button class="tabBtn" data-tab="hist">Historial</button>
  </nav>
  <main class="content">

    <section id="tab-live" class="tabPane active">
      <div class="pills">
        <span id="pillCan" class="pill">CAN</span>
        <span id="pillSd" class="pill">SD</span>
        <span id="pillWs" class="pill">Enlace</span>
      </div>

      <div class="heroRow">
        <div class="heroCard">
          <div class="l">Consumo instantaneo</div>
          <div class="v"><span id="heroInstant">--</span><span class="u" id="heroInstantUnit"></span></div>
        </div>
        <div class="heroCard">
          <div class="l">Litros usados (viaje)</div>
          <div class="v"><span id="heroLiters">--</span><span class="u"> L</span></div>
        </div>
        <div class="heroCard">
          <div class="l">Costo (viaje)</div>
          <div class="v"><span id="heroCost">--</span><span class="u"> Bs</span></div>
        </div>
      </div>

      <div class="grid">
        <div class="card"><div class="v" id="rpm">--</div><div class="l">RPM</div></div>
        <div class="card"><div class="v" id="speed">--</div><div class="l">km/h</div></div>
        <div class="card"><div class="v" id="map">--</div><div class="l">MAP kPa</div></div>
        <div class="card"><div class="v" id="iat">--</div><div class="l">IAT &deg;C</div></div>
        <div class="card"><div class="v" id="coolant">--</div><div class="l">Refrig. &deg;C</div></div>
        <div class="card"><div class="v" id="baro">--</div><div class="l">Baro kPa<span id="baroEst"></span></div></div>
        <div class="card"><div class="v" id="ve">--</div><div class="l">VE %</div></div>
        <div class="card"><div class="v" id="l100">--</div><div class="l">L/100km inst.</div></div>
        <div class="card"><div class="v" id="lh">--</div><div class="l">L/h inst.</div></div>
        <div class="card"><div class="v" id="tripKm">--</div><div class="l">Viaje km</div></div>
        <div class="card"><div class="v" id="tripL">--</div><div class="l">Viaje L</div></div>
        <div class="card"><div class="v" id="tripAvg">--</div><div class="l">Prom. L/100km</div></div>
        <div class="card"><div class="v" id="tripTime">--</div><div class="l">Tiempo viaje</div></div>
      </div>

      <h2>En vivo (ultimos ~60s)</h2>
      <div class="varPicker" id="liveVarPicker"></div>
      <div class="chartWrap">
        <canvas id="liveChart" width="900" height="220"></canvas>
        <div class="chartTip" id="liveChartTip"></div>
      </div>
      <div class="chartNote" id="liveChartNote">Escala relativa: con 2+ variables cada linea se dibuja segun su propio rango (0-100%); el valor real de cada una queda en su etiqueta y en el tooltip.</div>
      <div style="margin-top:8px">
        <button class="danger" id="resetBtn">Reiniciar viaje</button>
      </div>
    </section>

    <section id="tab-hist" class="tabPane">
      <h2>Historial (microSD)</h2>
      <div id="fileList"></div>

      <div class="heroRow">
        <div class="heroCard">
          <div class="l">Distancia</div>
          <div class="v"><span id="histKm">--</span><span class="u"> km</span></div>
        </div>
        <div class="heroCard">
          <div class="l">Litros usados</div>
          <div class="v"><span id="histLiters">--</span><span class="u"> L</span></div>
        </div>
        <div class="heroCard">
          <div class="l">Tiempo de viaje</div>
          <div class="v"><span id="histTime">--:--:--</span></div>
        </div>
        <div class="heroCard">
          <div class="l">Costo</div>
          <div class="v"><span id="histCost">--</span><span class="u"> Bs</span></div>
        </div>
      </div>

      <div class="varPicker" id="histVarPicker"></div>
      <div id="historyTitle"></div>
      <div class="chartWrap">
        <canvas id="historyChart" width="900" height="220"></canvas>
        <div class="chartTip" id="historyChartTip"></div>
      </div>
      <div class="chartNote" id="historyChartNote">Escala relativa: con 2+ variables cada linea se dibuja segun su propio rango (0-100%); el valor real de cada una queda en su etiqueta y en el tooltip.</div>
    </section>

  </main>
</div>

<script>
// Colores en orden fijo (nunca reasignar por filtro) tomados de la paleta
// categorica validada del skill dataviz -- 8 tonos con separacion CVD >=8
// entre adyacentes, ya verificados contra la superficie oscura (#1a1a19).
const VARS = [
  {id:'l100',    label:'L/100km',      color:'#3987e5', liveKey:'instant_L100km', histKey:'l100',    decimals:1},
  {id:'speed',   label:'Velocidad',    color:'#1f9e46', liveKey:'speed_kmh',      histKey:'speed',   decimals:0},
  {id:'rpm',     label:'RPM',          color:'#d55181', liveKey:'rpm',            histKey:'rpm',     decimals:0},
  {id:'map',     label:'MAP',          color:'#c98500', liveKey:'map_kpa',        histKey:'map',     decimals:0},
  {id:'iat',     label:'IAT',          color:'#199e70', liveKey:'iat_c',          histKey:'iat',     decimals:0},
  {id:'coolant', label:'Refrigerante', color:'#d95926', liveKey:'coolant_c',      histKey:'coolant', decimals:0},
  {id:'ve',      label:'VE %',         color:'#9085e9', liveKey:'ve_pct',         histKey:'ve',      decimals:0},
  {id:'lh',      label:'L/h',          color:'#e66767', liveKey:'instant_Lh',     histKey:'lh',      decimals:2},
];
const DEFAULT_VARS = ['l100', 'speed'];
const THEME = {grid:'#2c2c2a', muted:'#898781', crosshair:'#54534f', surface:'#1a1a19', ink:'#ffffff'};

function buildVarPicker(containerId, onChange) {
  const el = document.getElementById(containerId);
  VARS.forEach(v => {
    const label = document.createElement('label');
    label.className = 'varChk';
    const cb = document.createElement('input');
    cb.type = 'checkbox';
    cb.dataset.var = v.id;
    cb.checked = DEFAULT_VARS.includes(v.id);
    cb.onchange = onChange;
    const dot = document.createElement('span');
    dot.className = 'dot';
    dot.style.background = v.color;
    label.appendChild(cb);
    label.appendChild(dot);
    label.appendChild(document.createTextNode(v.label));
    el.appendChild(label);
  });
}
function checkedVars(containerId) {
  return Array.from(document.querySelectorAll('#' + containerId + ' input:checked')).map(cb => cb.dataset.var);
}

// Chart geometry/base render are split from drawChart() so the hover
// handler can redraw just the base + a crosshair/dot overlay on every
// pointermove without recomputing scales, and so it has a fixed frame
// (canvas._chartState) to hit-test against instead of re-deriving it.
//
// With 2+ series of unrelated units (RPM 0-7000 vs L/100km 0-20) a single
// shared y-scale mangles the smaller one flat against the baseline -- a
// dual/mixed-scale chart. Instead: 1 series keeps a real, labeled axis
// (baseline at 0, like before); 2+ series each get their own min-max
// normalized to 0-100% of their own range ("indexed to a common base"),
// so shapes/trends compare fairly. The underlying data point values stay
// in real units always -- only the plotted Y position is normalized -- so
// the tooltip and the end-of-line label still show the true number.
function computeChartGeom(canvas, seriesList) {
  const w = canvas.width, h = canvas.height;
  const pad = {l:46, r:14, t:14, b:36};
  let allX = [];
  seriesList.forEach(s => s.data.forEach(p => allX.push(p.x)));
  const xmin = Math.min.apply(null, allX), xmax = Math.max.apply(null, allX);
  const xScale = x => pad.l + (x-xmin)/((xmax-xmin)||1)*(w-pad.l-pad.r);

  const multi = seriesList.length > 1;
  const domains = {};
  seriesList.forEach(s => {
    const ys = s.data.map(p => p.y);
    let ymin = multi ? Math.min.apply(null, ys) : 0;
    let ymax = Math.max(multi ? ymin+1 : 1, Math.max.apply(null, ys)) * (multi ? 1 : 1.1);
    if (ymin === ymax) { ymin -= 1; ymax += 1; }
    domains[s.id] = {ymin, ymax};
  });
  function yScale(series, value) {
    const {ymin, ymax} = domains[series.id];
    return h - pad.b - (value-ymin)/((ymax-ymin)||1)*(h-pad.t-pad.b);
  }
  return {w, h, pad, xmin, xmax, xScale, yScale, domains, multi};
}

// Live chart spans ~60s -> "-Ns" ticks read naturally; history can span many
// minutes -> mm:ss reads better there. Both are relative to the plotted
// window, not wall-clock time (the firmware only ever sends uptime_ms).
function formatTimeTick(xVal, xmax, spanSeconds) {
  if (spanSeconds <= 180) {
    const rel = Math.round(xVal - xmax);
    return rel === 0 ? '0s' : rel + 's';
  }
  const total = Math.round(xVal);
  return Math.floor(total/60) + ':' + String(total%60).padStart(2,'0');
}

function renderChartBase(ctx, geom, seriesList) {
  const {w, h, pad} = geom;
  ctx.clearRect(0,0,w,h);
  ctx.font = '10px -apple-system,Segoe UI,sans-serif';
  ctx.textAlign = 'left';

  ctx.strokeStyle = THEME.grid; ctx.lineWidth = 1;
  for (let i=0;i<=4;i++){
    const gy = pad.t + i*(h-pad.t-pad.b)/4;
    ctx.beginPath(); ctx.moveTo(pad.l,gy); ctx.lineTo(w-pad.r,gy); ctx.stroke();
  }
  ctx.fillStyle = THEME.muted;
  if (!geom.multi) {
    const {ymin, ymax} = geom.domains[seriesList[0].id];
    for (let i=0;i<=4;i++){
      const gy = pad.t + i*(h-pad.t-pad.b)/4;
      ctx.fillText((ymax - i*(ymax-ymin)/4).toFixed(1), 3, gy+3);
    }
  } else {
    ['100%','75%','50%','25%','0%'].forEach((lab,i)=>{
      ctx.fillText(lab, 3, pad.t + i*(h-pad.t-pad.b)/4 + 3);
    });
  }

  const span = geom.xmax - geom.xmin;
  ctx.fillStyle = THEME.muted;
  [0, 0.5, 1].forEach((frac,i)=>{
    const xVal = geom.xmin + frac*span;
    ctx.textAlign = i===0 ? 'left' : (i===1 ? 'center' : 'right');
    ctx.fillText(formatTimeTick(xVal, geom.xmax, span), geom.xScale(xVal), h - pad.b + 14);
  });
  ctx.textAlign = 'left';

  const endLabelYs = [];
  seriesList.forEach(s=>{
    ctx.strokeStyle = s.color; ctx.lineWidth = 2; ctx.lineJoin = 'round'; ctx.lineCap = 'round';
    ctx.beginPath();
    s.data.forEach((p,i)=>{
      const X = geom.xScale(p.x), Y = geom.yScale(s, p.y);
      if (i===0) ctx.moveTo(X,Y); else ctx.lineTo(X,Y);
    });
    ctx.stroke();

    // Direct label at the line's end (real value, never the normalized
    // position) -- skipped when it would collide with one already placed,
    // per "don't stack converging end-labels" (falls back to legend+tooltip).
    const last = s.data[s.data.length-1];
    if (last) {
      const X = geom.xScale(last.x), Y = geom.yScale(s, last.y);
      ctx.beginPath(); ctx.arc(X,Y,3,0,Math.PI*2); ctx.fillStyle = s.color; ctx.fill();
      const collides = endLabelYs.some(y => Math.abs(y-Y) < 10);
      if (!collides) {
        endLabelYs.push(Y);
        ctx.fillStyle = THEME.ink;
        ctx.textAlign = 'right';
        ctx.fillText(last.y.toFixed(s.decimals != null ? s.decimals : 1), X-7, Y-6);
        ctx.textAlign = 'left';
      }
    }
  });

  // Legend: a line-key (not a filled box) beside the label, per the marks spec.
  let lx = pad.l;
  seriesList.forEach(s=>{
    ctx.strokeStyle = s.color; ctx.lineWidth = 2;
    ctx.beginPath(); ctx.moveTo(lx, h-7); ctx.lineTo(lx+14, h-7); ctx.stroke();
    ctx.fillStyle = THEME.ink;
    ctx.fillText(s.label, lx+18, h-4);
    lx += 18 + s.label.length*6 + 16;
  });
}

function drawChart(canvas, seriesList) {
  const ctx = canvas.getContext('2d');
  const totalPoints = seriesList.reduce((n,s) => n + s.data.length, 0);
  if (totalPoints < 2) {
    ctx.clearRect(0,0,canvas.width,canvas.height);
    ctx.fillStyle = THEME.muted;
    ctx.font = '11px -apple-system,Segoe UI,sans-serif';
    ctx.fillText('sin datos suficientes', 46, canvas.height/2);
    canvas._chartState = null;
    return;
  }
  const geom = computeChartGeom(canvas, seriesList);
  canvas._chartState = {seriesList, geom};
  renderChartBase(ctx, geom, seriesList);
}

// Finds, per series, the data point nearest snappedX (linear scan -- series
// are at most a few hundred points, plenty fast for a pointermove handler).
function nearestPoints(seriesList, snappedX) {
  return seriesList.map(s => {
    let best = null, bestDist = Infinity;
    s.data.forEach(p => {
      const d = Math.abs(p.x - snappedX);
      if (d < bestDist) { bestDist = d; best = p; }
    });
    return {series: s, point: best};
  }).filter(r => r.point);
}

function drawHoverOverlay(canvas, snappedX) {
  const state = canvas._chartState;
  if (!state) return;
  const ctx = canvas.getContext('2d');
  renderChartBase(ctx, state.geom, state.seriesList);
  const px = state.geom.xScale(snappedX);
  ctx.strokeStyle = THEME.crosshair; ctx.lineWidth = 1;
  ctx.beginPath(); ctx.moveTo(px, state.geom.pad.t); ctx.lineTo(px, state.geom.h - state.geom.pad.b); ctx.stroke();

  nearestPoints(state.seriesList, snappedX).forEach(({series, point}) => {
    const x = state.geom.xScale(point.x), y = state.geom.yScale(series, point.y);
    ctx.beginPath(); ctx.arc(x, y, 5, 0, Math.PI*2); ctx.fillStyle = THEME.surface; ctx.fill(); // surface ring
    ctx.beginPath(); ctx.arc(x, y, 4, 0, Math.PI*2); ctx.fillStyle = series.color; ctx.fill(); // 8px marker
  });
}

function updateTooltip(tipEl, canvas, snappedX) {
  const state = canvas._chartState;
  if (!state) return;
  tipEl.innerHTML = '';
  nearestPoints(state.seriesList, snappedX).forEach(({series, point}) => {
    const row = document.createElement('div');
    row.className = 'tipRow';
    const key = document.createElement('span');
    key.className = 'tipKey';
    key.style.background = series.color;
    const val = document.createElement('span');
    val.className = 'tipVal';
    val.textContent = point.y.toFixed(series.decimals != null ? series.decimals : 2);
    const lab = document.createElement('span');
    lab.className = 'tipLab';
    lab.textContent = series.label;
    row.appendChild(key); row.appendChild(val); row.appendChild(lab);
    tipEl.appendChild(row);
  });
}

// Wires one canvas + its tooltip div to a shared hover/touch handler: finds
// the pointer's X in chart-data space, snaps to it (readers aim at a
// position, not a 2px line), and redraws the crosshair/dots + tooltip.
function attachHover(canvasId, tipId) {
  const canvas = document.getElementById(canvasId);
  const tip = document.getElementById(tipId);

  function handleMove(clientX, clientY) {
    const state = canvas._chartState;
    if (!state) return;
    const rect = canvas.getBoundingClientRect();
    const cx = (clientX - rect.left) * (canvas.width / rect.width);
    const {xmin, xmax, w, pad} = state.geom;
    const t = (cx - pad.l) / (w - pad.l - pad.r);
    const snappedX = Math.max(xmin, Math.min(xmax, xmin + t * (xmax - xmin)));

    drawHoverOverlay(canvas, snappedX);
    updateTooltip(tip, canvas, snappedX);
    tip.style.display = 'block';
    const left = Math.min(clientX - rect.left + 12, rect.width - tip.offsetWidth - 8);
    tip.style.left = Math.max(left, 4) + 'px';
    tip.style.top = Math.max(clientY - rect.top - tip.offsetHeight - 10, 4) + 'px';
  }

  canvas.addEventListener('pointermove', e => handleMove(e.clientX, e.clientY));
  canvas.addEventListener('pointerleave', () => {
    tip.style.display = 'none';
    const state = canvas._chartState;
    if (state) renderChartBase(canvas.getContext('2d'), state.geom, state.seriesList);
  });
}

const liveSeries = {};
VARS.forEach(v => liveSeries[v.id] = []);
const MAX_LIVE_POINTS = 120;

function setPill(id, ok, textOk, textBad){
  const el = document.getElementById(id);
  el.textContent = ok ? textOk : textBad;
  el.className = 'pill ' + (ok ? 'ok' : 'bad');
}

function onLiveData(d){
  document.getElementById('rpm').textContent = d.rpm;
  document.getElementById('speed').textContent = d.speed_kmh.toFixed(0);
  document.getElementById('map').textContent = d.map_kpa.toFixed(0);
  document.getElementById('iat').textContent = d.iat_c.toFixed(0);
  document.getElementById('coolant').textContent = d.coolant_c.toFixed(0);
  document.getElementById('baro').textContent = d.baro_kpa.toFixed(0);
  document.getElementById('baroEst').textContent = d.baro_is_estimated ? ' (ISA)' : '';
  document.getElementById('ve').textContent = d.ve_pct.toFixed(0);
  document.getElementById('l100').textContent = d.instant_L100km.toFixed(1);
  document.getElementById('lh').textContent = d.instant_Lh.toFixed(2);
  document.getElementById('tripKm').textContent = d.trip_km.toFixed(2);
  document.getElementById('tripL').textContent = d.trip_fuel_L.toFixed(3);
  document.getElementById('tripAvg').textContent = d.trip_avg_L100km.toFixed(1);
  const s = d.trip_time_s|0;
  document.getElementById('tripTime').textContent =
      String((s/3600|0)).padStart(2,'0')+':'+String((s/60%60|0)).padStart(2,'0')+':'+String(s%60).padStart(2,'0');

  setPill('pillCan', d.can_ok, 'CAN: OK', 'CAN: sin datos');
  setPill('pillSd', d.sd_ok, 'SD: OK', 'SD: --');

  const moving = d.speed_kmh > 2.0;
  document.getElementById('heroInstant').textContent = (moving ? d.instant_L100km : d.instant_Lh).toFixed(1);
  document.getElementById('heroInstantUnit').textContent = moving ? ' L/100km' : ' L/h';
  document.getElementById('heroLiters').textContent = d.trip_fuel_L.toFixed(2);
  document.getElementById('heroCost').textContent = d.trip_cost_bs.toFixed(1);

  const t = d.uptime_ms/1000;
  VARS.forEach(v => {
    const buf = liveSeries[v.id];
    buf.push({x:t, y:d[v.liveKey]});
    if (buf.length > MAX_LIVE_POINTS) buf.shift();
  });
  renderLiveChart();
}

function renderLiveChart(){
  const chosen = checkedVars('liveVarPicker');
  const seriesList = VARS.filter(v => chosen.includes(v.id))
      .map(v => ({id:v.id, label:v.label, color:v.color, decimals:v.decimals, data:liveSeries[v.id]}));
  drawChart(document.getElementById('liveChart'), seriesList);
  document.getElementById('liveChartNote').classList.toggle('show', seriesList.length > 1);
}

// Instrumentacion para la prueba de latencia/estabilidad del panel web
// (Seccion 4.3.7 del Capitulo 4). No afecta el funcionamiento normal del
// panel, solo registra en el propio navegador: usar wsStatsReport() en la
// consola del navegador para ver un resumen, o wsStatsDownload() para
// bajar un CSV con todos los intervalos y analizarlo con
// CODIGOS/ws_latency_report.py.
const wsStats = { intervals: [], reconnects: 0, lastMsgTime: null, startTime: performance.now() };
function wsStatsReport(){
  const iv = wsStats.intervals;
  if (!iv.length) { console.log('wsStats: sin muestras todavia.'); return; }
  const mean = iv.reduce((a,b)=>a+b,0) / iv.length;
  const std = Math.sqrt(iv.reduce((a,b)=>a+(b-mean)**2,0) / iv.length);
  const sessionMin = (performance.now() - wsStats.startTime) / 60000;
  console.log(`wsStats: n=${iv.length} intervalos | media=${mean.toFixed(1)}ms | desv=${std.toFixed(1)}ms | `
    + `min=${Math.min(...iv).toFixed(1)}ms | max=${Math.max(...iv).toFixed(1)}ms | `
    + `reconexiones=${wsStats.reconnects} | sesion=${sessionMin.toFixed(1)}min`);
}
function wsStatsDownload(){
  const csv = 'intervalo_ms\n' + wsStats.intervals.map(x => x.toFixed(1)).join('\n');
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([csv], {type: 'text/csv'}));
  a.download = 'ws_intervals.csv';
  a.click();
}

let ws;
function connectWs(){
  ws = new WebSocket('ws://' + location.host + '/ws');
  ws.onopen = () => setPill('pillWs', true, 'Enlace: WS', 'Enlace: --');
  ws.onmessage = (ev) => {
    const now = performance.now();
    if (wsStats.lastMsgTime !== null) wsStats.intervals.push(now - wsStats.lastMsgTime);
    wsStats.lastMsgTime = now;
    try { onLiveData(JSON.parse(ev.data)); } catch(e){}
  };
  ws.onclose = () => { wsStats.reconnects++; setPill('pillWs', false, 'Enlace: WS', 'Enlace: polling'); setTimeout(connectWs, 2000); };
  ws.onerror = () => ws.close();
}
connectWs();
setInterval(()=>{
  if (!ws || ws.readyState !== 1) {
    fetch('/api/live').then(r=>r.json()).then(onLiveData).catch(()=>{});
  }
}, 1500);

document.getElementById('resetBtn').onclick = () => {
  if (confirm('Reiniciar el contador de viaje?')) {
    fetch('/api/reset', {method:'POST'});
  }
};

function loadFiles(){
  fetch('/api/files').then(r=>r.json()).then(list=>{
    const el = document.getElementById('fileList');
    el.innerHTML = '';
    if (!list.length) { el.textContent = 'Sin archivos en la SD todavia.'; return; }
    list.forEach(f=>{
      const row = document.createElement('div');
      row.className = 'file-row';
      const nameSpan = document.createElement('span');
      nameSpan.textContent = f.name + ' (' + (f.size/1024).toFixed(1) + ' KB)';
      const viewBtn = document.createElement('button');
      viewBtn.textContent = 'Ver grafica';
      viewBtn.onclick = () => viewChart(f.name);
      const dlLink = document.createElement('a');
      dlLink.className = 'btn';
      dlLink.href = '/api/download?file=' + encodeURIComponent(f.name);
      dlLink.textContent = 'Descargar CSV';
      row.appendChild(nameSpan); row.appendChild(viewBtn); row.appendChild(dlLink);
      el.appendChild(row);
    });
  });
}

let lastHistPoints = [];

function viewChart(name){
  document.getElementById('historyTitle').textContent = 'Cargando ' + name + '...';
  fetch('/api/chartdata?file=' + encodeURIComponent(name) + '&maxpoints=300')
    .then(r=>r.json())
    .then(data=>{
      lastHistPoints = data.points;
      renderHistChart();
      document.getElementById('historyTitle').textContent =
          'Historial: ' + name + ' (' + data.points.length + ' puntos)';

      const s = data.summary;
      document.getElementById('histKm').textContent = s.km.toFixed(2);
      document.getElementById('histLiters').textContent = s.liters.toFixed(2);
      document.getElementById('histCost').textContent = s.cost_bs.toFixed(1);
      const t = s.time_s|0;
      document.getElementById('histTime').textContent =
          String((t/3600|0)).padStart(2,'0')+':'+String((t/60%60|0)).padStart(2,'0')+':'+String(t%60).padStart(2,'0');
    });
}

function renderHistChart(){
  const chosen = checkedVars('histVarPicker');
  const seriesList = VARS.filter(v => chosen.includes(v.id)).map(v => ({
    id: v.id, label: v.label, color: v.color, decimals: v.decimals,
    data: lastHistPoints.map(p => ({x:p.t/1000, y:p[v.histKey]})),
  }));
  drawChart(document.getElementById('historyChart'), seriesList);
  document.getElementById('historyChartNote').classList.toggle('show', seriesList.length > 1);
}

document.querySelectorAll('.tabBtn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tabBtn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tabPane').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById('tab-' + btn.dataset.tab).classList.add('active');
  });
});

buildVarPicker('liveVarPicker', renderLiveChart);
buildVarPicker('histVarPicker', renderHistChart);
attachHover('liveChart', 'liveChartTip');
attachHover('historyChart', 'historyChartTip');
loadFiles();
</script>
</body>
</html>
)HTMLDOC";

// ------------------------------------------------------------------
static void buildLiveJson(String &out) {
  VehicleData vd;
  if (xSemaphoreTake(g_dataMutex, pdMS_TO_TICKS(50)) == pdTRUE) {
    vd = g_vehicleData;
    xSemaphoreGive(g_dataMutex);
  }
  JsonDocument doc;
  doc["rpm"] = vd.rpm;
  doc["speed_kmh"] = vd.speed_kmh;
  doc["map_kpa"] = vd.map_kpa;
  doc["iat_c"] = vd.iat_c;
  doc["coolant_c"] = vd.coolant_c;
  // Logged/displayed for sensor validation only (compare vs. MAP with the
  // engine off and contact on, or vs. the ISA estimate) -- never fed back
  // into the speed-density calculation, which already self-corrects for
  // altitude via the live MAP reading (see the note in config.h).
  doc["baro_kpa"] = vd.baro_kpa;
  doc["baro_is_estimated"] = vd.baro_is_estimated;
  doc["ve_pct"] = vd.ve_pct;
  doc["maf_gs"] = vd.maf_calc_gs;
  doc["fuel_gs"] = vd.fuel_gs;
  doc["instant_Lh"] = vd.instant_Lh;
  doc["instant_L100km"] = vd.instant_L100km;
  doc["trip_km"] = vd.trip_distance_km;
  doc["trip_fuel_L"] = vd.trip_fuel_L;
  doc["trip_cost_bs"] = vd.trip_fuel_L * FUEL_PRICE_BS_PER_L;
  doc["trip_avg_L100km"] = vd.trip_avg_L100km;
  doc["trip_time_s"] = vd.trip_time_s;
  doc["can_ok"] = g_systemStatus.can_ok;
  doc["sd_ok"] = g_systemStatus.sd_ok;
  doc["uptime_ms"] = millis();
  serializeJson(doc, out);
}

// Only "trip_###.csv" (prefix/ext from config.h, digits in between) is
// ever allowed through to the SD card -- blocks path traversal / access
// to arbitrary files via the ?file= query params.
static bool isValidLogFilename(const String &name) {
  size_t prefixLen = strlen(SD_LOG_FILE_PREFIX);
  size_t extLen = strlen(SD_LOG_FILE_EXT);
  if (name.length() <= prefixLen + extLen) return false;
  if (name.length() >= SD_LOG_MAX_FILENAME_LEN) return false; // matches sd_logger.cpp's on-disk name cap
  if (!name.startsWith(SD_LOG_FILE_PREFIX)) return false;
  if (!name.endsWith(SD_LOG_FILE_EXT)) return false;
  if (name.indexOf('/') >= 0 || name.indexOf('\\') >= 0) return false;
  for (size_t i = prefixLen; i < name.length() - extLen; i++) {
    if (!isDigit(name[i])) return false;
  }
  return true;
}

static bool csvField(const String &line, int fieldIdx, String &out) {
  int start = 0, idx = 0;
  while (idx < fieldIdx) {
    int comma = line.indexOf(',', start);
    if (comma < 0) return false;
    start = comma + 1;
    idx++;
  }
  int comma = line.indexOf(',', start);
  out = (comma < 0) ? line.substring(start) : line.substring(start, comma);
  out.trim();
  return out.length() > 0;
}

// Reads an entire SD file into a heap buffer (PSRAM preferred) under
// g_sdMutex, held only for this one fast SD-speed read -- NOT for
// whatever the caller does with the bytes afterwards (a slow WiFi
// transfer, CSV parsing, ...). This is what keeps handleDownload() and
// handleChartData() from starving sdLoggerTask's once-a-second writes.
// Returns nullptr (and leaves outSize at 0) on any failure, including
// "file bigger than MAX_SD_READ_BYTES" -- rejected rather than risking
// an allocation failure. Caller must free() the returned buffer.
// The buffer is always NUL-terminated at buf[outSize] so it can also be
// treated as a C string, e.g. for a String(const char*) copy.
#define MAX_SD_READ_BYTES (4 * 1024 * 1024)

static uint8_t *readFileToBuffer(const String &path, size_t &outSize) {
  outSize = 0;
  if (xSemaphoreTake(g_sdMutex, pdMS_TO_TICKS(1000)) != pdTRUE) return nullptr;

  uint8_t *buf = nullptr;
  File f = SD.open(path, FILE_READ);
  if (f) {
    size_t sz = f.size();
    if (sz > 0 && sz <= MAX_SD_READ_BYTES) {
      buf = (uint8_t *)heap_caps_malloc(sz + 1, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
      if (!buf) buf = (uint8_t *)malloc(sz + 1); // PSRAM alloc failed -> try internal heap
      if (buf) {
        size_t readBytes = f.read(buf, sz);
        if (readBytes == sz) {
          buf[sz] = '\0';
          outSize = sz;
        } else {
          free(buf);
          buf = nullptr;
        }
      }
    }
    f.close();
    g_systemStatus.sd_activity_until_ms = millis() + 200;
  }
  xSemaphoreGive(g_sdMutex);
  return buf;
}

// ------------------------------------------------------------------
static void handleLive(AsyncWebServerRequest *request) {
  String out;
  buildLiveJson(out);
  request->send(200, "application/json", out);
}

static void handleFiles(AsyncWebServerRequest *request) {
  JsonDocument doc;
  JsonArray arr = doc.to<JsonArray>();

  if (xSemaphoreTake(g_sdMutex, pdMS_TO_TICKS(1000)) == pdTRUE) {
    File dir = SD.open(SD_LOG_DIR);
    if (dir && dir.isDirectory()) {
      File f = dir.openNextFile();
      while (f) {
        if (!f.isDirectory()) {
          String name = f.name();
          int slash = name.lastIndexOf('/');
          if (slash >= 0) name = name.substring(slash + 1);
          JsonObject o = arr.add<JsonObject>();
          o["name"] = name;
          o["size"] = f.size();
        }
        f.close();
        f = dir.openNextFile();
      }
    }
    if (dir) dir.close();
    g_systemStatus.sd_activity_until_ms = millis() + 120;
    xSemaphoreGive(g_sdMutex);
  }

  String out;
  serializeJson(doc, out);
  request->send(200, "application/json", out);
}

// Struct shared between the response fill callback and the onDisconnect
// safety net below, so the buffer is freed exactly once no matter which
// of the two actually finishes last.
struct DownloadBuf {
  uint8_t *buf;
  size_t size;
  bool freed;
};

// Reads the whole file into RAM up front (via readFileToBuffer, which
// only holds g_sdMutex for that fast read) and serves it from memory,
// so g_sdMutex is fully released before the -- potentially multi-second,
// client-throughput-bound -- network transfer even starts. onDisconnect
// is registered as a safety net: if the client aborts mid-download,
// ESPAsyncWebServer's fill callback is never called again to reach its
// normal free() path, so without this the buffer would leak.
static void handleDownload(AsyncWebServerRequest *request) {
  if (!request->hasParam("file")) {
    request->send(400, "text/plain", "falta el parametro file");
    return;
  }
  String fname = request->getParam("file")->value();
  if (!isValidLogFilename(fname)) {
    request->send(400, "text/plain", "nombre de archivo invalido");
    return;
  }
  String path = String(SD_LOG_DIR) + "/" + fname;

  size_t size = 0;
  uint8_t *buf = readFileToBuffer(path, size);
  if (!buf) {
    request->send(404, "text/plain", "archivo no encontrado, vacio o demasiado grande");
    return;
  }

  DownloadBuf *ctx = new DownloadBuf{buf, size, false};
  auto freeOnce = [ctx]() {
    if (!ctx->freed) {
      ctx->freed = true;
      free(ctx->buf);
    }
  };

  request->onDisconnect([ctx, freeOnce]() {
    freeOnce();
    delete ctx;
  });

  AsyncWebServerResponse *response = request->beginResponse(
      "text/csv", ctx->size,
      [ctx, freeOnce](uint8_t *dest, size_t maxLen, size_t index) -> size_t {
        size_t remaining = ctx->size - index;
        size_t n = (remaining < maxLen) ? remaining : maxLen;
        memcpy(dest, ctx->buf + index, n);
        if (index + n >= ctx->size) freeOnce(); // last chunk read -> release the buffer now
        return n;
      });
  response->addHeader("Content-Disposition", "attachment; filename=" + fname);
  request->send(response);
}

// Parses the CSV on-device and returns a decimated JSON point list so
// the browser never has to download/parse a raw multi-thousand-row
// file just to draw a chart. The file is pulled into RAM once via
// readFileToBuffer (g_sdMutex held only for that read); both the
// line-count pass and the point-extraction pass then run against the
// in-memory copy with no SD/mutex involvement, so charting a large log
// can no longer starve sdLoggerTask's writes the way two full on-card
// passes under the lock used to.
static void handleChartData(AsyncWebServerRequest *request) {
  if (!request->hasParam("file")) {
    request->send(400, "text/plain", "falta el parametro file");
    return;
  }
  String fname = request->getParam("file")->value();
  if (!isValidLogFilename(fname)) {
    request->send(400, "text/plain", "nombre de archivo invalido");
    return;
  }
  int maxPoints = 200;
  if (request->hasParam("maxpoints")) {
    maxPoints = request->getParam("maxpoints")->value().toInt();
  }
  maxPoints = constrain(maxPoints, 10, 2000);

  String path = String(SD_LOG_DIR) + "/" + fname;
  size_t size = 0;
  uint8_t *buf = readFileToBuffer(path, size);

  JsonDocument doc;
  JsonArray arr = doc["points"].to<JsonArray>();
  JsonObject summary = doc["summary"].to<JsonObject>();
  summary["km"] = 0.0;
  summary["liters"] = 0.0;
  summary["cost_bs"] = 0.0;
  summary["time_s"] = 0;

  if (buf) {
    String content((const char *)buf); // buf is NUL-terminated by readFileToBuffer
    free(buf);

    int bodyStart = content.indexOf('\n');
    bodyStart = (bodyStart < 0) ? content.length() : bodyStart + 1;

    size_t totalLines = 0;
    for (int i = bodyStart; i < (int)content.length(); i++) {
      if (content[i] == '\n') totalLines++;
    }
    size_t stride = (totalLines > (size_t)maxPoints) ? (totalLines / (size_t)maxPoints) : 1;

    // Trip totals (km/liters/cost) are cumulative columns -- the summary
    // is just whatever the last valid row says, no need to re-derive it.
    // Trip duration isn't logged directly, so it's approximated from the
    // first and last uptime_ms seen (logging only starts after the first
    // good CAN cycle, so this tracks the actual driving window closely).
    long firstUptimeMs = -1, lastUptimeMs = 0;
    bool haveSummaryRow = false;

    size_t lineNo = 0;
    int start = bodyStart;
    while (start < (int)content.length()) {
      int nl = content.indexOf('\n', start);
      String line = (nl < 0) ? content.substring(start) : content.substring(start, nl);
      if (line.length() > 0) {
        // columns: uptime_ms,rpm,speed_kmh,map_kpa,iat_c,coolant_c,ve_pct,
        //          maf_gs,fuel_gs,instant_Lh,instant_L100km,trip_km,
        //          trip_fuel_L,trip_avg_L100km,can_status,trip_cost_bs
        String sT, sKm, sFuelL, sCostBs;
        if (csvField(line, 0, sT) && csvField(line, 11, sKm) &&
            csvField(line, 12, sFuelL) && csvField(line, 15, sCostBs)) {
          long t = sT.toInt();
          if (firstUptimeMs < 0) firstUptimeMs = t;
          lastUptimeMs = t;
          summary["km"] = sKm.toFloat();
          summary["liters"] = sFuelL.toFloat();
          summary["cost_bs"] = sCostBs.toFloat();
          haveSummaryRow = true;
        }

        if ((lineNo % stride) == 0) {
          String sRpm, sSpeed, sMap, sIat, sCoolant, sVe, sLh, sL100;
          if (csvField(line, 1, sRpm) && csvField(line, 2, sSpeed) &&
              csvField(line, 3, sMap) && csvField(line, 4, sIat) && csvField(line, 5, sCoolant) &&
              csvField(line, 6, sVe) && csvField(line, 9, sLh) && csvField(line, 10, sL100)) {
            JsonObject o = arr.add<JsonObject>();
            o["t"] = sT.toInt();
            o["rpm"] = sRpm.toInt();
            o["speed"] = sSpeed.toFloat();
            o["map"] = sMap.toFloat();
            o["iat"] = sIat.toFloat();
            o["coolant"] = sCoolant.toFloat();
            o["ve"] = sVe.toFloat();
            o["lh"] = sLh.toFloat();
            o["l100"] = sL100.toFloat();
          }
        }
      }
      lineNo++;
      start = (nl < 0) ? (int)content.length() : nl + 1;
    }

    if (haveSummaryRow) {
      summary["time_s"] = (lastUptimeMs - firstUptimeMs) / 1000;
    }
  }

  String out;
  serializeJson(doc, out);
  request->send(200, "application/json", out);
}

static void handleReset(AsyncWebServerRequest *request) {
  if (xSemaphoreTake(g_dataMutex, pdMS_TO_TICKS(200)) == pdTRUE) {
    fuelCalcResetTrip(g_vehicleData);
    xSemaphoreGive(g_dataMutex);
  }
  request->send(200, "application/json", "{\"ok\":true}");
}

static void onWsEvent(AsyncWebSocket * /*server*/, AsyncWebSocketClient *client, AwsEventType type,
                       void * /*arg*/, uint8_t * /*data*/, size_t /*len*/) {
  if (type == WS_EVT_CONNECT) {
    String json;
    buildLiveJson(json);
    client->text(json);
  }
}

static void webSocketPushTask(void *pvParameters) {
  (void)pvParameters;
  for (;;) {
    if (ws.count() > 0) {
      String json;
      buildLiveJson(json);
      ws.textAll(json);
    }
    ws.cleanupClients();
    vTaskDelay(pdMS_TO_TICKS(WS_PUSH_PERIOD_MS));
  }
}

// ------------------------------------------------------------------
void webServerInit() {
  WiFi.mode(WIFI_AP_STA);
  bool apOk = WiFi.softAP(WIFI_AP_SSID, WIFI_AP_PASS);

  if (strlen(WIFI_STA_SSID) > 0) {
    WiFi.begin(WIFI_STA_SSID, WIFI_STA_PASS);
    uint32_t start = millis();
    while (WiFi.status() != WL_CONNECTED && (millis() - start) < WIFI_STA_CONNECT_TIMEOUT_MS) {
      vTaskDelay(pdMS_TO_TICKS(200));
    }
    if (WiFi.status() == WL_CONNECTED) {
      configTime(0, 0, "pool.ntp.org", "time.nist.gov"); // best-effort; only useful if STA has internet
    }
  }

  if (!apOk) {
    systemReportError(ErrorCode::WIFI_FAIL);
  }

  ws.onEvent(onWsEvent);
  server.addHandler(&ws);

  server.on("/", HTTP_GET, [](AsyncWebServerRequest *request) {
    request->send(200, "text/html", INDEX_HTML);
  });
  server.on("/api/live", HTTP_GET, handleLive);
  server.on("/api/files", HTTP_GET, handleFiles);
  server.on("/api/download", HTTP_GET, handleDownload);
  server.on("/api/chartdata", HTTP_GET, handleChartData);
  server.on("/api/reset", HTTP_POST, handleReset);
  server.onNotFound([](AsyncWebServerRequest *request) {
    request->send(404, "text/plain", "not found");
  });

  server.begin();
  g_systemStatus.server_active = apOk;

  xTaskCreatePinnedToCore(webSocketPushTask, "wsPush", STACK_WEBSOCK_TASK, nullptr,
                           PRIO_WEBSOCK_TASK, nullptr, CORE_WEBSOCK_TASK);
}
