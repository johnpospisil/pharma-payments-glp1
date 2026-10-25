// GLP-1 payments and prescribing explorer (P23, revised in P24). Static: reads data/meta.json and
// one brand file. Every value is a specialty x state x year aggregate; withheld cells arrive as
// negative codes (meta.codes) and are drawn as gaps, never as zeros.
"use strict";

const STATE_NAMES = {
  AL: "Alabama", AK: "Alaska", AZ: "Arizona", AR: "Arkansas", CA: "California", CO: "Colorado",
  CT: "Connecticut", DE: "Delaware", DC: "District of Columbia", FL: "Florida", GA: "Georgia",
  HI: "Hawaii", ID: "Idaho", IL: "Illinois", IN: "Indiana", IA: "Iowa", KS: "Kansas",
  KY: "Kentucky", LA: "Louisiana", ME: "Maine", MD: "Maryland", MA: "Massachusetts",
  MI: "Michigan", MN: "Minnesota", MS: "Mississippi", MO: "Missouri", MT: "Montana",
  NE: "Nebraska", NV: "Nevada", NH: "New Hampshire", NJ: "New Jersey", NM: "New Mexico",
  NY: "New York", NC: "North Carolina", ND: "North Dakota", OH: "Ohio", OK: "Oklahoma",
  OR: "Oregon", PA: "Pennsylvania", RI: "Rhode Island", SC: "South Carolina", SD: "South Dakota",
  TN: "Tennessee", TX: "Texas", UT: "Utah", VT: "Vermont", VA: "Virginia", WA: "Washington",
  WV: "West Virginia", WI: "Wisconsin", WY: "Wyoming", US: "United States",
  "Territories and other": "Territories and other",
};
const BRAND_VAR = {
  Ozempic: "--b-ozempic", Trulicity: "--b-trulicity", Mounjaro: "--b-mounjaro",
  Victoza: "--b-victoza", Rybelsus: "--b-rybelsus", Bydureon: "--b-bydureon",
  "Other GLP-1s": "--b-other",
};
const WITHHELD = -1;
const PAY_START_NONPHYS = 2021;

const pct = (v) => `${v.toFixed(v > 0 && v < 1 ? 2 : 1)}%`;
const usd = (v) => (v < 100 ? `$${v.toFixed(2)}` : `$${Math.round(v).toLocaleString("en-US")}`);
const num = (v) => Math.round(v).toLocaleString("en-US");
const dollars = (v) => `$${Math.round(v).toLocaleString("en-US")}`;
const per = (v) => v.toFixed(1);

function ratio(a, b, k = 1) {
  if (a < 0) return { code: a };
  if (b < 0) return { code: b };
  if (b === 0) return { code: "none" };
  return { v: (a / b) * k };
}
const METRICS = {
  pctPaid: { label: "% of prescribers paid", short: "% paid",
             axis: "Share of prescribers with a payment naming the brand that year",
             fmt: pct, calc: (g) => ratio(g("paid"), g("n"), 100), pay: true },
  usdPer: { label: "$ per prescriber", short: "$ per prescriber",
            axis: "Payments naming the brand, averaged over every prescriber in the group, paid or not",
            fmt: usd, calc: (g) => ratio(g("usd"), g("n")), pay: true },
  pctRegular: { label: "% with 11+ claims", short: "% with 11+ claims",
                axis: "Share of prescribers with 11 or more claims of the brand in the year",
                fmt: pct, calc: (g) => ratio(g("regular"), g("n"), 100) },
  per1000: { label: "Claims per 1,000", short: "claims per 1,000",
             axis: "Visible claims of the brand per 1,000 of the group's Part D claims (all drugs)",
             fmt: per, calc: (g) => ratio(g("claims"), g("tot"), 1000) },
};
const PAY = ["pctPaid", "usdPer"];
const RX = ["pctRegular", "per1000"];

const $ = (id) => document.getElementById(id);
const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);

let META, DATA = {}, S, TOTAL_SPEC;

function readHash() {
  const h = new URLSearchParams(location.hash.slice(1));
  const brands = META.brands.map((b) => b.key);
  const specs = META.specialties.map((s) => s.key);
  const yr = +h.get("year");
  return {
    brand: brands.includes(h.get("brand")) ? h.get("brand") : "Ozempic",
    spec: specs.includes(h.get("spec")) ? h.get("spec") : TOTAL_SPEC,
    state: META.states.includes(h.get("state")) ? h.get("state") : "US",
    year: META.years.includes(yr) ? yr : META.years.at(-1),
    pay: PAY.includes(h.get("pay")) ? h.get("pay") : "pctPaid",
    rx: RX.includes(h.get("rx")) ? h.get("rx") : "pctRegular",
    map: Object.keys(METRICS).includes(h.get("map")) ? h.get("map") : "pctPaid",
  };
}
function writeHash() {
  const h = new URLSearchParams({ brand: S.brand, spec: S.spec, state: S.state, year: S.year,
                                  pay: S.pay, rx: S.rx, map: S.map });
  history.replaceState(null, "", `#${h}`);
}

async function loadBrand(key) {
  if (!DATA[key]) {
    const file = META.brands.find((b) => b.key === key).file;
    const r = await fetch(`data/${file}`);
    if (!r.ok) throw new Error(`Could not load data/${file} (${r.status})`);
    DATA[key] = await r.json();
  }
  return DATA[key];
}

const brandMeta = () => META.brands.find((b) => b.key === S.brand);
const specIdx = (k) => META.specialties.findIndex((s) => s.key === k);
const stateIdx = (k) => META.states.indexOf(k);
const specMeta = (k) => META.specialties[specIdx(k)];
const specLabel = (k) => specMeta(k).label;
const placeLabel = (k) => STATE_NAMES[k] || k;
const isNonphys = (k) => !specMeta(k).physician;

function getter(d, yi, si, ti) {
  return (m) => d[m][yi][si][ti];
}
// the rest of the US: the national value minus the state's (both published: no new disclosure)
function restGetter(d, yi, si, ti) {
  const us = stateIdx("US");
  return (m) => {
    const a = d[m][yi][si][us], b = d[m][yi][si][ti];
    if (a < 0) return a;
    if (b < 0) return b;
    return a - b;
  };
}
function value(metric, g) {
  return METRICS[metric].calc(g);
}
function reason(code) {
  if (code === "none") return "no prescribers in this group";
  return META.codes[String(code)] || "withheld to protect privacy";
}
const isGap = (code) => code === WITHHELD;

// ------------------------------------------------------------------ series

function seriesFor(metric) {
  const d = DATA[S.brand];
  const si = specIdx(S.spec), ti = stateIdx(S.state);
  const color = css(BRAND_VAR[S.brand]);
  const mk = (gf, si2, ti2) => META.years.map((y, yi) => ({ year: y, yi, si: si2, ti: ti2,
                                                            ...value(metric, gf(d, yi, si2, ti2)) }));
  const out = [{ label: `${S.brand}, ${S.state === "US" ? specLabel(S.spec) : placeLabel(S.state)}`,
                 color, dash: false, pts: mk(getter, si, ti), main: true }];
  if (S.state !== "US") {
    out.push({ label: "Rest of the US, same group", color: css("--compare"), dash: true,
               pts: mk(restGetter, si, ti) });
  } else if (S.spec !== TOTAL_SPEC) {
    out.push({ label: "All physicians", color: css("--compare"), dash: true,
               pts: mk(getter, specIdx(TOTAL_SPEC), stateIdx("US")) });
  }
  return out;
}

function eventsFor() {
  return META.events.filter((e) => e.brand === S.brand || e.brand === "*");
}

// ------------------------------------------------------------------ line chart

function niceStep(v) {
  if (!(v > 0)) return 0.25;
  const p = 10 ** Math.floor(Math.log10(v));
  for (const m of [1, 2, 2.5, 5, 10]) if (m * p >= v) return m * p;
  return 10 * p;
}
function tickFmt(metric, t, ymax) {
  const d = ymax >= 10 ? 0 : ymax >= 1 ? 1 : 2;
  if (metric === "usdPer") return ymax >= 10 ? dollars(t) : `$${t.toFixed(2)}`;
  if (metric === "per1000") return t.toFixed(d);
  return `${t.toFixed(d)}%`;
}

function lineChart(el, metric, kind) {
  const series = seriesFor(metric);
  const M = METRICS[metric];
  const W = Math.max(280, el.clientWidth);
  const H = Math.round(Math.min(300, Math.max(210, W * 0.38)));
  const narrow = W < 480;
  const m = { l: narrow ? 44 : 56, r: narrow ? 46 : 64, t: 14, b: 30 };
  const years = META.years;
  const x = (y) => m.l + ((y - years[0]) / (years.at(-1) - years[0])) * (W - m.l - m.r);
  const all = series.flatMap((s) => s.pts.filter((p) => p.v !== undefined).map((p) => p.v));
  const top = Math.max(...all, 0) * 1.05;
  const stepY = niceStep(top / 4);
  const ymax = stepY * Math.max(1, Math.ceil(top / stepY));
  const y = (v) => H - m.b - (v / ymax) * (H - m.t - m.b);
  const ticks = Array.from({ length: Math.round(ymax / stepY) + 1 }, (_, i) => i * stepY);
  const step = x(years[1]) - x(years[0]);
  const pid = `hatch-${kind}`;
  let g = `<defs><pattern id="${pid}" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
      <rect width="6" height="6" style="fill:var(--masked)"/><rect width="2" height="6" style="fill:var(--hatch)"/></pattern></defs>`;
  // context bands: not yet in Part D; NP/PA payments not reported
  const b = brandMeta();
  const bands = [];
  if (b.first_partd && b.first_partd > years[0]) bands.push([years[0], b.first_partd - 1, "Not yet in Part D"]);
  if (kind === "pay" && isNonphys(S.spec)) bands.push([years[0], PAY_START_NONPHYS - 1, "Payments not reported before 2021"]);
  const band = bands.sort((p, q) => q[1] - p[1])[0];
  if (band) {
    const x0 = Math.max(m.l - step / 2, x(band[0]) - step / 2), x1 = x(band[1]) + step / 2;
    g += `<rect x="${x0}" y="${m.t}" width="${x1 - x0}" height="${H - m.t - m.b}" style="fill:var(--raised)"/>`;
    if (x1 - x0 > 90) g += `<text x="${(x0 + x1) / 2}" y="${m.t + (H - m.t - m.b) / 2}" text-anchor="middle" class="anno">${esc(band[2])}</text>`;
  }
  const main = series[0];
  for (const p of main.pts) {
    if (isGap(p.code) && !(band && p.year <= band[1])) {
      g += `<rect x="${x(p.year) - step / 2 + 1}" y="${m.t}" width="${step - 2}" height="${H - m.t - m.b}" fill="url(#${pid})" rx="2"/>`;
    }
  }
  for (const t of ticks) {
    g += `<line x1="${m.l}" x2="${W - m.r}" y1="${y(t)}" y2="${y(t)}" style="stroke:var(--grid)" stroke-width="1"/>`;
    g += `<text x="${m.l - 8}" y="${y(t) + 4}" text-anchor="end" class="tick">${esc(tickFmt(metric, t, ymax))}</text>`;
  }
  g += `<line x1="${m.l}" x2="${W - m.r}" y1="${y(0)}" y2="${y(0)}" style="stroke:var(--axis)" stroke-width="1"/>`;
  for (const yr of years) {
    if (narrow && (years.at(-1) - yr) % 3 !== 0) continue;
    g += `<text x="${x(yr)}" y="${H - 8}" text-anchor="middle" class="tick">${yr}</text>`;
  }
  g += `<line x1="${x(S.year)}" x2="${x(S.year)}" y1="${m.t}" y2="${H - m.b}" style="stroke:var(--axis)" stroke-dasharray="2 3"/>`;
  for (const s of [...series].reverse()) {
    let d = "", dPartial = "", pen = false;
    for (const p of s.pts) {
      if (p.v === undefined) { pen = false; continue; }
      const pt = `${x(p.year).toFixed(1)},${y(p.v).toFixed(1)}`;
      // 2013 payments cover August–December only: draw the 2013–2014 step dashed
      if (kind === "pay" && p.year === 2014 && pen) {
        dPartial = `M${x(2013).toFixed(1)},${y(s.pts[0].v).toFixed(1)}L${pt}`;
        d += `M${pt}`;
      } else {
        d += `${pen ? "L" : "M"}${pt}`;
      }
      pen = true;
    }
    g += `<path d="${d}" fill="none" style="stroke:${s.color}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round" ${s.dash ? 'stroke-dasharray="5 4"' : ""}/>`;
    if (dPartial) g += `<path d="${dPartial}" fill="none" style="stroke:${s.color}" stroke-width="2" stroke-dasharray="2 3" opacity="0.8"/>`;
    for (const p of s.pts) {
      if (p.v === undefined) continue;
      const hollow = kind === "pay" && p.year === 2013;
      const r = s.main ? 4 : 3;
      g += `<circle cx="${x(p.year)}" cy="${y(p.v)}" r="${r}" style="fill:${hollow ? "var(--surface)" : s.color};stroke:${hollow ? s.color : "var(--surface)"}" stroke-width="${hollow ? 1.5 : 2}"/>`;
    }
  }
  // market events: numbered markers on the axis, listed under the charts
  const evs = eventsFor();
  evs.forEach((e, i) => {
    const same = evs.filter((o) => o.year === e.year);
    const cx = x(e.year) + (same.indexOf(e) - (same.length - 1) / 2) * 15;  // spread same-year markers
    g += `<g class="event"><circle cx="${cx}" cy="${H - m.b}" r="7" style="fill:var(--surface);stroke:var(--ink2)" stroke-width="1"/>
      <text x="${cx}" y="${H - m.b + 3.5}" text-anchor="middle" class="evnum">${i + 1}</text></g>`;
  });
  // end labels, nudged apart when the lines finish close together
  const ends = series.map((s) => ({ s, p: [...s.pts].reverse().find((p) => p.v !== undefined) }))
    .filter((e) => e.p).map((e) => ({ ...e, ly: y(e.p.v) + 4 }));
  if (ends.length === 2 && ends[0].p.year === ends[1].p.year && Math.abs(ends[0].ly - ends[1].ly) < 14) {
    const [hi, lo] = ends[0].ly <= ends[1].ly ? [ends[0], ends[1]] : [ends[1], ends[0]];
    const mid = (hi.ly + lo.ly) / 2;
    hi.ly = mid - 7; lo.ly = mid + 7;
  }
  for (const e of ends) {
    g += `<text x="${x(e.p.year) + 8}" y="${e.ly}" class="${e.s.main ? "endlabel" : "endlabel sub"}">${esc(M.fmt(e.p.v))}</text>`;
  }
  g += `<line class="cross" x1="0" x2="0" y1="${m.t}" y2="${H - m.b}" style="stroke:var(--ink2)" stroke-width="1" visibility="hidden"/>`;
  g += `<rect class="hit" x="${m.l - step / 2}" y="0" width="${W - m.l - m.r + step}" height="${H - m.b + 8}" fill="transparent"/>`;
  el.innerHTML = `<svg viewBox="0 0 ${W} ${H}" aria-hidden="true">${g}</svg>`;
  el.tabIndex = 0;
  el.setAttribute("role", "group");
  el.setAttribute("aria-roledescription", "chart");
  el.setAttribute("aria-label", `${M.axis}: ${series[0].label}, ${years[0]} to ${years.at(-1)}. Left and right arrow keys read each year; every value is also in the table of numbers.`);

  const svg = el.querySelector("svg"), cross = svg.querySelector(".cross");
  const show = (yi, cx, cy) => {
    const yr = years[yi];
    cross.setAttribute("x1", x(yr)); cross.setAttribute("x2", x(yr)); cross.setAttribute("visibility", "visible");
    let h = `<div class="t">${yr}${kind === "pay" && yr === 2013 ? " (payments August–December only)" : ""}</div>`;
    for (const s of series) {
      const p = s.pts[yi];
      const v = p.v !== undefined ? M.fmt(p.v) : esc(reason(p.code));
      h += `<div class="row"><span class="sw" style="--c:${s.color}"></span><span>${esc(s.label)}: <strong>${v}</strong></span></div>`;
    }
    const p = main.pts[yi], gt = getter(DATA[S.brand], yi, p.si, p.ti);
    const n = gt("n"), cnt = kind === "pay" ? gt("paid") : gt("regular");
    if (n > 0) {
      h += `<div class="sub">${num(n)} prescribers in this group</div>`;
      if (cnt >= 0) h += `<div class="sub">${num(cnt)} ${kind === "pay" ? "paid for the brand" : "with 11+ claims"}</div>`;
    }
    for (const e of eventsFor().filter((e) => e.year === yr)) h += `<div class="sub">${esc(e.label)}</div>`;
    tip(h, cx, cy);
  };
  const hide = () => { cross.setAttribute("visibility", "hidden"); untip(); };
  const pick = (ev) => {
    const r = svg.getBoundingClientRect();
    const px = ((ev.clientX - r.left) / r.width) * W;
    const yi = Math.max(0, Math.min(years.length - 1, Math.round((px - m.l) / step)));
    show(yi, ev.clientX, ev.clientY);
  };
  svg.querySelector(".hit").addEventListener("pointermove", pick);
  svg.querySelector(".hit").addEventListener("pointerdown", pick);
  svg.addEventListener("pointerleave", hide);
  let ki = years.indexOf(S.year);
  el.onkeydown = (e) => {
    if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
    e.preventDefault();
    ki = Math.max(0, Math.min(years.length - 1, ki + (e.key === "ArrowRight" ? 1 : -1)));
    const r = svg.getBoundingClientRect();
    show(ki, r.left + (x(years[ki]) / W) * r.width, r.top + r.height * 0.3);
  };
  el.onblur = hide;
  return series;
}

function legend(el, series, withHidden) {
  el.innerHTML = series.map((s) =>
    `<span class="key"><span class="swatch${s.dash ? " dash" : ""}" style="--c:${s.color}"></span>${esc(s.label)}</span>`).join("")
    + (withHidden ? `<span class="key"><span class="swatch hidden-key"></span>Withheld to protect privacy</span>` : "");
}

// ------------------------------------------------------------------ tooltip

function tip(html, cx, cy) {
  const t = $("tooltip");
  t.innerHTML = html; t.hidden = false;
  const r = t.getBoundingClientRect();
  let left = cx + 14, top = cy + 14;
  if (left + r.width > innerWidth - 8) left = cx - r.width - 14;
  if (top + r.height > innerHeight - 8) top = cy - r.height - 14;
  t.style.left = `${Math.max(8, left)}px`; t.style.top = `${Math.max(8, top)}px`;
}
function untip() { $("tooltip").hidden = true; }

// ------------------------------------------------------------------ state tiles

// fixed breaks for a brand x group x measure, pooled over every year, so shades compare across years
function breaks(metric) {
  const d = DATA[S.brand], si = specIdx(S.spec);
  const vals = [];
  META.years.forEach((_, yi) => {
    for (const st of Object.keys(META.tiles)) {
      const r = value(metric, getter(d, yi, si, stateIdx(st)));
      if (r.v !== undefined) vals.push(r.v);
    }
  });
  vals.sort((a, b) => a - b);
  if (vals.length < 10) return [];
  return [...new Set([0.2, 0.4, 0.6, 0.8].map((f) => vals[Math.floor(f * (vals.length - 1))]))]
    .filter((c) => c > vals[0] && c < vals.at(-1));
}

function emptyMapText() {
  const b = brandMeta();
  if (b.first_partd && S.year < b.first_partd && !METRICS[S.map].pay) return `${S.brand} was not yet in Part D in ${S.year}.`;
  if (METRICS[S.map].pay && isNonphys(S.spec) && S.year < PAY_START_NONPHYS)
    return `Payments to ${specLabel(S.spec).toLowerCase()}s were not reported before 2021.`;
  return "Every state is withheld or empty for this selection.";
}

function drawMap() {
  const d = DATA[S.brand], yi = META.years.indexOf(S.year), si = specIdx(S.spec);
  const M = METRICS[S.map];
  const states = Object.keys(META.tiles);
  const vals = states.map((st) => ({ st, ...value(S.map, getter(d, yi, si, stateIdx(st))) }));
  const q = breaks(S.map);
  const nb = q.length + 1;
  const ramp = (k) => (nb === 1 ? 2 : Math.round((k * 4) / (nb - 1)));
  const bin = (v) => ramp(q.filter((c) => v >= c).length);
  const el = $("tiles");
  el.innerHTML = "";
  const focusSt = META.tiles[S.state] ? S.state : states[0];
  for (const v of vals) {
    const [c, r] = META.tiles[v.st];
    const b = document.createElement("button");
    b.type = "button";
    b.className = "tile";
    b.dataset.st = v.st;
    b.style.gridColumn = c + 1; b.style.gridRow = r + 1;
    b.tabIndex = v.st === focusSt ? 0 : -1;
    b.setAttribute("aria-pressed", String(S.state === v.st));
    const name = STATE_NAMES[v.st];
    if (v.v !== undefined) {
      const k = bin(v.v);
      b.style.setProperty("--fill", `var(--seq-${k})`);
      b.style.setProperty("--tink", `var(--seq-t${k})`);
      b.setAttribute("aria-label", `${name}: ${M.fmt(v.v)}`);
      b.innerHTML = `<span class="ab">${v.st}</span><span class="val">${esc(M.fmt(v.v))}</span>`;
    } else {
      b.classList.add(isGap(v.code) ? "masked" : "empty");
      b.setAttribute("aria-label", `${name}: ${reason(v.code)}`);
      b.innerHTML = `<span class="ab">${v.st}</span>`;
    }
    b.addEventListener("click", () => { S.state = S.state === v.st ? "US" : v.st; render(v.st); });
    b.addEventListener("pointerenter", (e) => {
      const g = getter(d, yi, si, stateIdx(v.st)), n = g("n");
      tip(`<div class="t">${esc(name)}, ${S.year}</div><div>${esc(M.label)}: <strong>${v.v !== undefined ? esc(M.fmt(v.v)) : esc(reason(v.code))}</strong></div>`
        + (n > 0 ? `<div class="sub">${num(n)} prescribers</div>` : ""), e.clientX, e.clientY);
    });
    b.addEventListener("pointermove", (e) => { if (!$("tooltip").hidden) tip($("tooltip").innerHTML, e.clientX, e.clientY); });
    b.addEventListener("pointerleave", untip);
    el.appendChild(b);
  }
  const shown = vals.filter((v) => v.v !== undefined);
  const edges = q.map((c) => M.fmt(c));
  let lg = "";
  if (!shown.length) {
    lg = `<span class="k">${esc(emptyMapText())}</span>`;
  } else if (nb === 1) {
    lg = `<span class="k"><span class="sw" style="--fill:var(--seq-2)"></span>Shown</span>`;
  } else {
    for (let k = 0; k < nb; k++) {
      const txt = k === 0 ? `under ${edges[0]}` : k === nb - 1 ? `${edges[k - 1]} and above` : `${edges[k - 1]} to under ${edges[k]}`;
      lg += `<span class="k"><span class="sw" style="--fill:var(--seq-${ramp(k)})"></span>${esc(txt)}</span>`;
    }
  }
  lg += `<span class="k"><span class="sw" style="--fill:var(--hatchfill)"></span>Withheld</span>`;
  if (vals.some((v) => !isGap(v.code) && v.v === undefined)) lg += `<span class="k"><span class="sw flat"></span>No data</span>`;
  $("map-legend").innerHTML = lg;
  $("year-out").textContent = S.year === 2013 && M.pay ? "2013 (payments Aug–Dec)" : S.year;
  // the selected state's value, for phones (no hover) and screen readers
  const sel = META.tiles[S.state] ? vals.find((v) => v.st === S.state) : null;
  $("readout").textContent = sel
    ? `${STATE_NAMES[sel.st]}, ${S.year}: ${sel.v !== undefined ? `${M.fmt(sel.v)} (${M.short})` : reason(sel.code)}.`
    : "Select a state to filter the charts. Select it again to return to the United States.";
}

// roving focus: the tile grid is one tab stop; arrow keys move between tiles
function tileKeys(e) {
  const keys = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] };
  if (!keys[e.key] || !e.target.dataset.st) return;
  e.preventDefault();
  const [dc, dr] = keys[e.key];
  const [c0, r0] = META.tiles[e.target.dataset.st];
  let best = null, bd = Infinity;
  for (const [st, [c, r]] of Object.entries(META.tiles)) {
    const along = dc ? (c - c0) * dc : (r - r0) * dr;
    if (along <= 0) continue;
    const across = dc ? Math.abs(r - r0) : Math.abs(c - c0);
    const dist = along + across * 3;
    if (dist < bd) { bd = dist; best = st; }
  }
  if (!best) return;
  const next = $("tiles").querySelector(`[data-st="${best}"]`);
  for (const t of $("tiles").children) t.tabIndex = -1;
  next.tabIndex = 0; next.focus();
}

// ------------------------------------------------------------------ table, text

function cell(v, fmt) {
  if (v < 0) return `<td class="hid">${esc(v === WITHHELD ? "withheld" : reason(v))}</td>`;
  return `<td>${fmt(v)}</td>`;
}
function cellR(r, fmt) {
  if (r.v === undefined) return `<td class="hid">${esc(r.code === WITHHELD ? "withheld" : reason(r.code))}</td>`;
  return `<td>${fmt(r.v)}</td>`;
}
function drawTable() {
  const d = DATA[S.brand], si = specIdx(S.spec), ti = stateIdx(S.state);
  let h = `<caption class="sr">${esc(S.brand)}, ${esc(specLabel(S.spec))}, ${esc(placeLabel(S.state))}</caption>
    <thead><tr><th>Year</th><th>Prescribers</th><th>Paid</th><th>% paid</th><th>Payments naming the brand</th><th>$ per prescriber</th>
    <th>With 11+ claims</th><th>% with 11+ claims</th><th>Claims (visible rows)</th><th>Per 1,000 Part D claims</th></tr></thead><tbody>`;
  META.years.forEach((y, yi) => {
    const g = getter(d, yi, si, ti);
    h += `<tr><td>${y === 2013 ? "2013 (payments Aug–Dec)" : y}</td>${cell(g("n"), num)}${cell(g("paid"), num)}${cellR(value("pctPaid", g), pct)}
      ${cell(g("usd"), dollars)}${cellR(value("usdPer", g), usd)}${cell(g("regular"), num)}
      ${cellR(value("pctRegular", g), pct)}${cell(g("claims"), num)}${cellR(value("per1000", g), per)}</tr>`;
  });
  $("table").innerHTML = h + "</tbody>";
}

function drawEvents() {
  const ev = eventsFor();
  $("events").innerHTML = ev.length
    ? `<h3>What else happened</h3><ol>${ev.map((e) => `<li><strong>${e.year}</strong> ${esc(e.label)}</li>`).join("")}</ol>
       <p>Labels, launches, shortages and generics move these lines whether or not anyone was paid. Drug makers also
       promote a brand most at launch and wind promotion down once a successor arrives, so payments and prescribing
       rise and fall together over a brand's life.</p>`
    : "";
}

function drawText() {
  const c = META.caveat;
  $("caveat").innerHTML = `
    <p><strong>Lines that rise or fall together do not show that payments changed prescribing.</strong>
    Drug makers promote a brand most at launch and stop once a successor arrives (Victoza's payments ended as Novo Nordisk
    moved to Ozempic), and they tend to reach prescribers whose practices are already growing. In the article's event study,
    paid physicians became more likely to have 11 or more claims of the paid brand (${c.att_trulicity} / ${c.att_victoza} /
    ${c.att_ozempic} percentage points for Trulicity, Victoza and Ozempic), but their statin prescribing, which no GLP-1
    payment should affect, rose too (${c.statin_trulicity} / ${c.statin_victoza} / ${c.statin_ozempic} percentage points).
    That pattern is consistent with companies reaching practices that were already growing.</p>
    <p>A brand-specific shift needs the prescriber-level comparison in the article and cannot be read from these totals.
    States and groups also differ in formularies, patients and practice size: a state with more payments and more
    prescribing does not show that its paid prescribers prescribe more. Nothing here says anything about any
    individual prescriber, or about whether any prescription was appropriate.</p>`;
  const other = META.other_brands.join(", ");
  const files = META.brands.map((b) => `<a href="data/${b.file}">${esc(b.file)}</a>`).join(", ");
  $("notes").innerHTML = `
    <ul>
    <li><strong>Who is counted.</strong> Medicare Part D prescribers who treat diabetes regularly (the article's analysis panel),
      placed each year in the state and group of their Part D record, so the population changes from year to year as prescribers
      enter, leave or move. "Other physician" is mostly emergency medicine, hospital medicine, paediatrics and surgery.
      Nurse practitioners and physician assistants are shown on their own, not inside "All physicians".
      "Territories and other" pools Puerto Rico, Guam, the Virgin Islands, military and unknown addresses.</li>
    <li><strong>Payments.</strong> Promotional payments in CMS Open Payments that name the brand: meals, speaker and consulting fees,
      travel, education, gifts. Research grants, royalties and acquisitions are excluded. A payment naming several drugs is split
      equally between them. "$ per prescriber" averages over every prescriber in the group, paid or not, so a few speakers' fees can
      dominate it. Program year 2013 covers August–December only (hollow points, dotted step). Payments to nurse practitioners and
      physician assistants were not reported before 2021. Ozempic shows payments in 2017, before its first year in Part D.</li>
    <li><strong>Prescribing.</strong> A claim is a pharmacy fill attributed to the prescriber, not a patient or a new prescription:
      11 claims a year can be one patient refilling monthly or a few on 90-day supplies. Medicare hides any prescriber-drug row with
      fewer than 11 claims, so "% with 11+ claims" is always observed but rises with practice size, and "claims per 1,000" counts
      visible rows only. The hidden share changes by brand and year: shrinking brands lose most rows, so their visible decline is
      steeper than real use.</li>
    <li><strong>Which measures count what.</strong> "% paid" and "% with 11+ claims" count each prescriber once. "$ per prescriber" and
      "claims per 1,000" add up dollars and claims, so high-volume prescribers weigh more.</li>
    <li><strong>Brands.</strong> "Other GLP-1s" is ${esc(other)}, mostly the insulin combinations Soliqua and Xultophy.
      ${esc(META.excluded_brands.join(", "))} are left out: Part D cannot cover weight-loss-only prescriptions, and Wegovy's
      cardiovascular coverage began only in March 2024. Plans did not always verify a diabetes diagnosis, so a small part of
      Ozempic and Mounjaro use may be for weight.</li>
    <li><strong>Privacy.</strong> No individual prescriber is named, mapped or ranked. A cell is withheld when it describes 1 to 10
      prescribers, when one prescriber received more than half of a state's (or a small national group's) dollars, when everyone in a
      group of fewer than 20 shares the attribute, and wherever a hidden value could otherwise be worked out from the published
      totals. Every withheld cell looks the same, whatever the reason. Withheld states are not random: they include the smallest
      and most concentrated.</li>
    <li><strong>Data.</strong> <a href="data/meta.json">meta.json</a> and one file per brand: ${files}
      (layout: metric, year, group, state; negative numbers are withheld or structural cells, explained in meta.json). Built by
      <code>python -m ppg.app.build</code> from CMS Open Payments and Medicare Part D Prescribers, 2013–2024.
      Code: <a href="https://github.com/johnpospisil/pharma-payments-glp1">github.com/johnpospisil/pharma-payments-glp1</a>.</li>
    </ul>`;
}

function captions() {
  const b = brandMeta();
  const launch = b.first_partd && b.first_partd > META.years[0]
    ? ` ${S.brand} ${b.approved ? `was approved in ${b.approved} and ` : ""}first appears in Part D data in ${b.first_partd}.` : "";
  const nonphys = isNonphys(S.spec) ? " Payments to this group were not reported before 2021." : "";
  $("pay-note").textContent = `${METRICS[S.pay].axis}.${nonphys}${launch}`;
  const yi = META.years.indexOf(S.year);
  const vis = b.visible_pct ? b.visible_pct[yi] : null;
  const visTxt = S.rx === "per1000" && vis != null
    ? ` In ${S.year} the visible rows hold about ${vis}% of ${S.brand}'s Medicare Part D claims.` : "";
  $("rx-note").textContent = `${METRICS[S.rx].axis}.${visTxt}${launch}`;
}

function selectionLine() {
  const d = DATA[S.brand], yi = META.years.indexOf(S.year);
  const n = d.n[yi][specIdx(S.spec)][stateIdx(S.state)];
  const who = specLabel(S.spec).toLowerCase();
  const count = n > 0 ? `${num(n)} prescribers in ${S.year}.` : n === 0 ? `No prescribers in ${S.year}.` : `Prescriber count withheld for ${S.year}.`;
  $("selection").innerHTML = `<strong>${esc(S.brand)}</strong>, ${esc(who)}, ${esc(placeLabel(S.state))}. ${count}`;
}

// ------------------------------------------------------------------ controls

function radioGroup(el, items, field, labelOf) {
  el.setAttribute("role", "radiogroup");
  el.innerHTML = items.map((k) => `<button type="button" role="radio" data-k="${esc(k)}">${labelOf(k)}</button>`).join("");
  el.addEventListener("click", (e) => {
    const k = e.target.closest("button")?.dataset.k;
    if (k) { S[field] = k; render(); }
  });
  el.addEventListener("keydown", (e) => {
    if (!["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(e.key)) return;
    e.preventDefault();
    const i = items.indexOf(S[field]);
    const j = (i + (e.key === "ArrowRight" || e.key === "ArrowDown" ? 1 : -1) + items.length) % items.length;
    S[field] = items[j];
    render().then(() => el.querySelector(`[data-k="${CSS.escape(items[j])}"]`)?.focus());
  });
}

function controls() {
  const brands = META.brands.map((b) => b.key);
  radioGroup($("brands"), brands, "brand",
    (k) => `<span class="dot" style="--c:var(${BRAND_VAR[k]})"></span>${esc(k)}`);
  for (const b of $("brands").children) b.classList.add("brand");
  const order = [META.specialties.find((s) => s.key === TOTAL_SPEC),
                 ...META.specialties.filter((s) => s.key !== TOTAL_SPEC)];
  $("spec").innerHTML = order.map((s) => `<option value="${s.key}">${esc(s.label)}</option>`).join("");
  $("spec").addEventListener("change", (e) => { S.spec = e.target.value; render(); });
  $("state").innerHTML = [`<option value="US">United States</option>`,
    ...META.states.filter((s) => s !== "US").map((s) => `<option value="${esc(s)}">${esc(STATE_NAMES[s] || s)}</option>`)].join("");
  $("state").addEventListener("change", (e) => { S.state = e.target.value; render(); });
  radioGroup($("pay-metric"), PAY, "pay", (k) => esc(METRICS[k].label));
  radioGroup($("rx-metric"), RX, "rx", (k) => esc(METRICS[k].label));
  $("map-metric").innerHTML = Object.entries(METRICS).map(([k, m]) => `<option value="${k}">${esc(m.label)}</option>`).join("");
  $("map-metric").addEventListener("change", (e) => { S.map = e.target.value; render(); });
  const yr = $("year");
  yr.min = META.years[0]; yr.max = META.years.at(-1);
  yr.addEventListener("input", (e) => { S.year = +e.target.value; render(); });
  $("tiles").addEventListener("keydown", tileKeys);
}

function syncControls() {
  for (const [id, f] of [["brands", "brand"], ["pay-metric", "pay"], ["rx-metric", "rx"]])
    for (const b of $(id).querySelectorAll("button")) {
      const on = b.dataset.k === S[f];
      b.setAttribute("aria-checked", String(on));
      b.tabIndex = on ? 0 : -1;
    }
  $("spec").value = S.spec; $("state").value = S.state; $("map-metric").value = S.map;
  $("year").value = S.year;
}

async function render(focusTile) {
  try {
    await loadBrand(S.brand);
  } catch (err) {
    $("selection").textContent = `${err.message}. Reload the page to try again.`;
    return;
  }
  untip();
  syncControls();
  selectionLine();
  const ps = lineChart($("pay-chart"), S.pay, "pay");
  legend($("pay-legend"), ps, ps[0].pts.some((p) => isGap(p.code)));
  const rs = lineChart($("rx-chart"), S.rx, "rx");
  legend($("rx-legend"), rs, rs[0].pts.some((p) => isGap(p.code)));
  captions();
  drawEvents();
  drawMap();
  drawTable();
  writeHash();
  if (focusTile) $("tiles").querySelector(`[data-st="${focusTile}"]`)?.focus();
}

async function init() {
  try {
    const r = await fetch("data/meta.json");
    if (!r.ok) throw new Error(`Could not load data/meta.json (${r.status})`);
    META = await r.json();
  } catch (err) {
    $("selection").textContent = `${err.message}. The explorer has to be opened from a web server, not as a local file.`;
    return;
  }
  TOTAL_SPEC = META.specialties.at(-1).key;
  S = readHash();
  controls();
  drawText();
  await render();
  let w = innerWidth;
  addEventListener("resize", () => { if (innerWidth !== w) { w = innerWidth; render(); } });
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => render());
}
init();
