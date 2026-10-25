// GLP-1 payments and prescribing explorer (P23). Static: reads data/meta.json and one brand file.
// Every value is a specialty x state x year aggregate; withheld cells arrive as negative codes
// (see meta.codes) and are drawn as gaps, never as zeros.
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
};
const BRAND_VAR = {
  Ozempic: "--b-ozempic", Trulicity: "--b-trulicity", Mounjaro: "--b-mounjaro",
  Victoza: "--b-victoza", Rybelsus: "--b-rybelsus", Bydureon: "--b-bydureon",
  "Other GLP-1s": "--b-other", "All GLP-1s": "--b-all",
};
const SHORT = { "-1": "fewer than 11", "-2": "one prescriber > 50% of $", "-3": "withheld (subtraction)",
                "-4": "not reported", "-5": "not on market", none: "no prescribers" };
const DISCLOSURE = new Set([-1, -2, -3]);

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
  pctPaid: { label: "% of prescribers paid", axis: "Share of prescribers with a payment naming the brand",
             fmt: pct, calc: (g) => ratio(g("paid"), g("n"), 100) },
  usdPer: { label: "$ per prescriber", axis: "Promotional dollars naming the brand, per prescriber",
            fmt: usd, calc: (g) => ratio(g("usd"), g("n")) },
  pctRegular: { label: "% prescribing it regularly", axis: "Share of prescribers with 11 or more claims of the brand",
                fmt: pct, calc: (g) => ratio(g("regular"), g("n"), 100) },
  per1000: { label: "Claims per 1,000", axis: "Brand claims per 1,000 of their other diabetes claims",
             fmt: per, calc: (g) => ratio(g("claims"), g("dm"), 1000) },
};
const PAY = ["pctPaid", "usdPer"];
const RX = ["pctRegular", "per1000"];

const $ = (id) => document.getElementById(id);
const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);

let META, DATA = {}, S;

function readHash() {
  const h = new URLSearchParams(location.hash.slice(1));
  const brands = META.brands.map((b) => b.key);
  const specs = META.specialties.map((s) => s.key);
  const yr = +h.get("year");
  return {
    brand: brands.includes(h.get("brand")) ? h.get("brand") : "Ozempic",
    spec: specs.includes(h.get("spec")) ? h.get("spec") : "all",
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

const specIdx = (k) => META.specialties.findIndex((s) => s.key === k);
const stateIdx = (k) => META.states.indexOf(k);
const specLabel = (k) => META.specialties[specIdx(k)].label;
const placeLabel = (k) => STATE_NAMES[k] || k;

function getter(d, yi, si, ti) {
  return (m) => d[m][yi][si][ti];
}
function value(metric, d, yi, si, ti) {
  return METRICS[metric].calc(getter(d, yi, si, ti));
}
function reason(code) {
  if (code === "none") return "no prescribers in this group";
  return META.codes[String(code)] || "withheld";
}

// ------------------------------------------------------------------ series

function seriesFor(metric) {
  const d = DATA[S.brand];
  const si = specIdx(S.spec), ti = stateIdx(S.state);
  const color = css(BRAND_VAR[S.brand]);
  const mk = (si, ti) => META.years.map((y, yi) => ({ year: y, ...value(metric, d, yi, si, ti), yi, si, ti }));
  const out = [{ label: `${S.brand}, ${S.state === "US" ? specLabel(S.spec).toLowerCase() : placeLabel(S.state)}`,
                 color, dash: false, pts: mk(si, ti), main: true }];
  if (S.state !== "US") {
    out.push({ label: `United States, same specialty`, color: css("--compare"), dash: true,
               pts: mk(si, stateIdx("US")) });
  } else if (S.spec !== "all") {
    out.push({ label: "All specialties", color: css("--compare"), dash: true,
               pts: mk(specIdx("all"), stateIdx("US")) });
  }
  out[0].label = S.state === "US" ? `${S.brand}, ${specLabel(S.spec)}` : `${S.brand}, ${placeLabel(S.state)}`;
  return out;
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
  const m = { l: narrow ? 44 : 56, r: narrow ? 46 : 64, t: 12, b: 28 };
  const years = META.years;
  const x = (y) => m.l + ((y - years[0]) / (years.at(-1) - years[0])) * (W - m.l - m.r);
  const all = series.flatMap((s) => s.pts.filter((p) => p.v !== undefined).map((p) => p.v));
  const top = Math.max(...all, 0) * 1.05;
  const stepY = niceStep(top / 4);
  const ymax = stepY * Math.max(1, Math.ceil(top / stepY));
  const y = (v) => H - m.b - (v / ymax) * (H - m.t - m.b);
  const ticks = Array.from({ length: Math.round(ymax / stepY) + 1 }, (_, i) => i * stepY);
  const step = (x(years[1]) - x(years[0]));
  const pid = `hatch-${kind}`;
  let g = `<defs><pattern id="${pid}" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
      <rect width="6" height="6" style="fill:var(--masked)"/><rect width="2" height="6" style="fill:var(--hatch)"/></pattern></defs>`;
  // withheld years of the selected series
  const main = series[0];
  for (const p of main.pts) {
    if (DISCLOSURE.has(p.code)) {
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
  // selected year (from the map slider)
  g += `<line x1="${x(S.year)}" x2="${x(S.year)}" y1="${m.t}" y2="${H - m.b}" style="stroke:var(--axis)" stroke-dasharray="2 3"/>`;
  // NPs and PAs enter Open Payments in 2021
  if (kind === "pay" && S.spec === "all") {
    const xa = x(META.op_nonphysician_from) - step / 2;
    g += `<line x1="${xa}" x2="${xa}" y1="${m.t}" y2="${H - m.b}" style="stroke:var(--muted)" stroke-dasharray="4 3"/>`;
    g += `<text x="${xa - 5}" y="${m.t + 12}" text-anchor="end" class="anno">NPs, PAs reported from 2021</text>`;
  }
  for (const s of [...series].reverse()) {
    let d = "", pen = false;
    for (const p of s.pts) {
      if (p.v === undefined) { pen = false; continue; }
      d += `${pen ? "L" : "M"}${x(p.year).toFixed(1)},${y(p.v).toFixed(1)}`;
      pen = true;
    }
    g += `<path d="${d}" fill="none" style="stroke:${s.color}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round" ${s.dash ? 'stroke-dasharray="5 4"' : ""}/>`;
    for (const p of s.pts) {
      if (p.v === undefined) continue;
      const hollow = kind === "pay" && p.year === 2013;
      const r = s.main ? 4 : 3;
      g += `<circle cx="${x(p.year)}" cy="${y(p.v)}" r="${r}" style="fill:${hollow ? "var(--surface)" : s.color};stroke:${hollow ? s.color : "var(--surface)"}" stroke-width="${hollow ? 1.5 : 2}"/>`;
    }
  }
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
  g += `<rect class="hit" x="${m.l - step / 2}" y="0" width="${W - m.l - m.r + step}" height="${H}" fill="transparent"/>`;
  el.innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(M.axis)}, ${esc(series[0].label)}, ${years[0]}–${years.at(-1)}. The table below has every value.">${g}</svg>`;
  el.tabIndex = 0;
  el.setAttribute("aria-label", `${M.axis}. Use the left and right arrow keys to read each year.`);

  const svg = el.querySelector("svg"), cross = svg.querySelector(".cross");
  const show = (yi, cx, cy) => {
    const yr = years[yi];
    cross.setAttribute("x1", x(yr)); cross.setAttribute("x2", x(yr)); cross.setAttribute("visibility", "visible");
    let h = `<div class="t">${yr}${kind === "pay" && yr === 2013 ? " (August–December only)" : ""}</div>`;
    for (const s of series) {
      const p = s.pts[yi];
      const v = p.v !== undefined ? M.fmt(p.v) : `hidden: ${esc(reason(p.code))}`;
      h += `<div class="row"><span class="sw" style="--c:${s.color}"></span><span>${esc(s.label)}: <strong>${v}</strong></span></div>`;
    }
    const p = main.pts[yi], gt = getter(DATA[S.brand], yi, p.si, p.ti);
    const n = gt("n"), cnt = kind === "pay" ? gt("paid") : gt("regular");
    if (n > 0) {
      h += `<div class="sub">${num(n)} prescribers in this group</div>`;
      if (cnt >= 0) h += `<div class="sub">${num(cnt)} ${kind === "pay" ? "paid for the brand" : "with 11+ claims"}</div>`;
    }
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

function drawMap() {
  const d = DATA[S.brand], yi = META.years.indexOf(S.year), si = specIdx(S.spec);
  const M = METRICS[S.map];
  const states = Object.keys(META.tiles);
  const vals = states.map((st) => ({ st, ...value(S.map, d, yi, si, stateIdx(st)) }));
  const shown = vals.filter((v) => v.v !== undefined).map((v) => v.v).sort((a, b) => a - b);
  // quintile breaks, merged where states share a value (then fewer, wider steps of the ramp)
  const q = shown.length >= 5
    ? [...new Set([0.2, 0.4, 0.6, 0.8].map((f) => shown[Math.floor(f * (shown.length - 1))]))].filter((c) => c < shown.at(-1))
    : [];
  const nb = q.length + 1;
  const ramp = (k) => (nb === 1 ? 2 : Math.round((k * 4) / (nb - 1)));
  const bin = (v) => ramp(q.filter((c) => v > c).length);
  const darkText = 3; // the two darkest-contrast bins take the opposite ink
  const el = $("tiles");
  el.innerHTML = "";
  for (const v of vals) {
    const [c, r] = META.tiles[v.st];
    const b = document.createElement("button");
    b.type = "button";
    b.className = "tile";
    b.style.gridColumn = c + 1; b.style.gridRow = r + 1;
    b.setAttribute("aria-pressed", String(S.state === v.st));
    const name = STATE_NAMES[v.st];
    let label;
    if (v.v !== undefined) {
      const k = bin(v.v);
      b.style.setProperty("--fill", `var(--seq-${k})`);
      b.style.setProperty("--tink", k >= darkText ? "var(--seq-ink-dark)" : "var(--seq-ink-light)");
      label = `${name}: ${M.fmt(v.v)}`;
      b.innerHTML = `<span class="ab">${v.st}</span><span class="val">${esc(M.fmt(v.v))}</span>`;
    } else {
      b.classList.add(DISCLOSURE.has(v.code) ? "masked" : "empty");
      label = `${name}: hidden, ${reason(v.code)}`;
      b.innerHTML = `<span class="ab">${v.st}</span>`;
    }
    b.setAttribute("aria-label", label);
    b.addEventListener("click", () => { S.state = S.state === v.st ? "US" : v.st; render(); });
    b.addEventListener("pointerenter", (e) => {
      const g = getter(d, yi, si, stateIdx(v.st)), n = g("n");
      tip(`<div class="t">${esc(name)}, ${S.year}</div><div>${esc(M.label)}: <strong>${v.v !== undefined ? esc(M.fmt(v.v)) : "hidden"}</strong></div>`
        + (v.v === undefined ? `<div class="sub">${esc(reason(v.code))}</div>` : "")
        + (n > 0 ? `<div class="sub">${num(n)} prescribers</div>` : ""), e.clientX, e.clientY);
    });
    b.addEventListener("pointermove", (e) => { if (!$("tooltip").hidden) tip($("tooltip").innerHTML, e.clientX, e.clientY); });
    b.addEventListener("pointerleave", untip);
    el.appendChild(b);
  }
  const edges = [shown[0], ...q, shown.at(-1)];
  $("map-legend").innerHTML = (shown.length
    ? Array.from({ length: nb }, (_, k) => `<span class="k"><span class="sw" style="--fill:var(--seq-${ramp(k)})"></span>${esc(M.fmt(edges[k]))}${nb > 1 ? `–${esc(M.fmt(edges[k + 1]))}` : ""}</span>`).join("")
    : `<span class="k">No state can be shown for this selection.</span>`)
    + `<span class="k"><span class="sw" style="--fill:var(--hatchfill)"></span>Withheld</span>`;
}

// ------------------------------------------------------------------ table, text

function cell(v, fmt) {
  if (v < 0) return `<td class="hid" title="${esc(reason(v))}">${esc(SHORT[String(v)] || "hidden")}</td>`;
  return `<td>${fmt(v)}</td>`;
}
function cellR(r, fmt) {
  if (r.v === undefined) return `<td class="hid" title="${esc(reason(r.code))}">${esc(SHORT[String(r.code)] || "hidden")}</td>`;
  return `<td>${fmt(r.v)}</td>`;
}
function drawTable() {
  const d = DATA[S.brand], si = specIdx(S.spec), ti = stateIdx(S.state);
  let h = `<caption class="sr">${esc(S.brand)}, ${esc(specLabel(S.spec))}, ${esc(placeLabel(S.state))}</caption>
    <thead><tr><th>Year</th><th>Prescribers</th><th>Paid</th><th>% paid</th><th>Promotional $</th><th>$ per prescriber</th>
    <th>11+ claims</th><th>% regular</th><th>Claims (11+ rows)</th><th>Per 1,000</th></tr></thead><tbody>`;
  META.years.forEach((y, yi) => {
    const g = getter(d, yi, si, ti);
    h += `<tr><td>${y}</td>${cell(g("n"), num)}${cell(g("paid"), num)}${cellR(value("pctPaid", d, yi, si, ti), pct)}
      ${cell(g("usd"), dollars)}${cellR(value("usdPer", d, yi, si, ti), usd)}${cell(g("regular"), num)}
      ${cellR(value("pctRegular", d, yi, si, ti), pct)}${cell(g("claims"), num)}${cellR(value("per1000", d, yi, si, ti), per)}</tr>`;
  });
  $("table").innerHTML = h + "</tbody>";
}

function drawText() {
  const c = META.caveat;
  $("caveat").innerHTML = `
    <p><strong>Lines that rise together do not show that payments changed prescribing.</strong>
    Drug makers tend to reach prescribers whose practices are already growing. In the article's event study,
    paid physicians became more likely to prescribe the paid brand regularly (${c.att_trulicity} / ${c.att_victoza} / ${c.att_ozempic}
    percentage points for Trulicity, Victoza and Ozempic), but their statin prescribing, which no GLP-1 payment should affect,
    rose too (${c.statin_trulicity} / ${c.statin_victoza} / ${c.statin_ozempic}). Much of that contrast is targeting, not influence.</p>
    <p>The clearer sign of a brand-specific shift is the paid brand's share of a doctor's GLP-1 prescribing
    (${c.share_trulicity} / ${c.share_ozempic} / ${c.share_mounjaro} points for Trulicity, Ozempic and Mounjaro), which needs the
    prescriber-level comparison in the article and cannot be read from these totals.</p>
    <p>Differences between states and specialties also reflect who practises there, insurer formularies and the mix of patients.
    None of this says anything about any individual prescriber, or about whether any prescription was appropriate.</p>`;
  const other = META.other_brands.join(", ");
  $("notes").innerHTML = `
    <ul>
    <li><strong>Who is counted.</strong> Medicare Part D prescribers who treat diabetes regularly (the article's analysis panel),
      placed each year in the state and specialty of their Part D record. Part D excludes weight-loss-only prescribing, so this is diabetes use.</li>
    <li><strong>Payments.</strong> Promotional payments in CMS Open Payments that name the brand: meals, speaker and consulting fees, travel,
      education, gifts. Research grants, royalties and acquisitions are excluded. A payment naming several drugs is split equally between them.
      Program year 2013 covers August–December only (hollow points). Payments to nurse practitioners, physician assistants and other
      non-physicians were not reported before 2021, so those years are blank for them and the all-specialty line counts physicians' payments only.</li>
    <li><strong>Prescribing.</strong> Medicare hides any prescriber-drug row with fewer than 11 claims. "Prescribing regularly" means 11 or more
      claims in the year, which is always observed. Claims count only those visible rows, so claims per 1,000 is a lower bound.</li>
    <li><strong>Brands.</strong> "Other GLP-1s" is ${esc(other)}. "All GLP-1s" is every diabetes GLP-1 brand; Wegovy and Zepbound are left out.</li>
    <li><strong>Privacy.</strong> No individual prescriber is named, mapped or ranked. A cell is withheld when it describes 1 to 10 prescribers,
      a state's dollars are withheld when one prescriber received more than half of them, and further cells are withheld where a hidden value
      could otherwise be worked out by subtracting the shown ones from a total.</li>
    <li><strong>Data.</strong> <a href="data/meta.json">meta.json</a> and one file per brand in <a href="data/">app/data</a>
      (layout: metric, year, specialty, state; negative numbers are withheld cells, explained in meta.json). Built by
      <code>python -m ppg.app.build</code> from CMS Open Payments and Medicare Part D Prescribers, 2013–2024.
      Code: <a href="https://github.com/johnpospisil/pharma-payments-glp1">github.com/johnpospisil/pharma-payments-glp1</a>.</li>
    </ul>`;
}

function captions() {
  const b = META.brands.find((x) => x.key === S.brand);
  const launch = b.launch && b.launch > META.years[0] ? ` ${S.brand} reached Part D in ${b.launch}.` : "";
  const nonphys = !META.specialties[specIdx(S.spec)].physician && S.spec !== "all"
    ? " Payments to this group were not reported before 2021." : "";
  $("pay-note").textContent = `${METRICS[S.pay].axis}.${nonphys}${launch}`;
  $("rx-note").textContent = `${METRICS[S.rx].axis}.${S.rx === "per1000" ? " Counts only rows with 11 or more claims." : ""}${launch}`;
}

function selectionLine() {
  const d = DATA[S.brand], yi = META.years.indexOf(S.year);
  const n = d.n[yi][specIdx(S.spec)][stateIdx(S.state)];
  const who = S.spec === "all" ? "all specialties" : specLabel(S.spec).toLowerCase();
  const count = n > 0 ? `${num(n)} prescribers in ${S.year}.` : n === 0 ? `No prescribers in ${S.year}.` : `Prescriber count withheld for ${S.year}.`;
  $("selection").innerHTML = `<strong>${esc(S.brand)}</strong>, ${esc(who)}, ${esc(placeLabel(S.state))}. ${count}`;
}

// ------------------------------------------------------------------ controls

function controls() {
  $("brands").innerHTML = META.brands.map((b) =>
    `<button type="button" class="brand" data-k="${esc(b.key)}" style="--c:var(${BRAND_VAR[b.key]})"><span class="dot"></span>${esc(b.key)}</button>`).join("");
  $("brands").addEventListener("click", (e) => {
    const k = e.target.closest(".brand")?.dataset.k;
    if (k) { S.brand = k; render(); }
  });
  $("spec").innerHTML = [META.specialties.at(-1), ...META.specialties.slice(0, -1)]
    .map((s) => `<option value="${s.key}">${esc(s.label)}</option>`).join("");
  $("spec").addEventListener("change", (e) => { S.spec = e.target.value; render(); });
  const st = META.states;
  $("state").innerHTML = [`<option value="US">United States</option>`,
    ...st.filter((s) => s !== "US").map((s) => `<option value="${esc(s)}">${esc(STATE_NAMES[s] || s)}</option>`)].join("");
  $("state").addEventListener("change", (e) => { S.state = e.target.value; render(); });
  const tog = (id, keys, field) => {
    $(id).innerHTML = keys.map((k) => `<button type="button" data-k="${k}">${esc(METRICS[k].label)}</button>`).join("");
    $(id).addEventListener("click", (e) => { const k = e.target.closest("button")?.dataset.k; if (k) { S[field] = k; render(); } });
  };
  tog("pay-metric", PAY, "pay");
  tog("rx-metric", RX, "rx");
  $("map-metric").innerHTML = Object.entries(METRICS).map(([k, m]) => `<option value="${k}">${esc(m.label)}</option>`).join("");
  $("map-metric").addEventListener("change", (e) => { S.map = e.target.value; render(); });
  const yr = $("year");
  yr.min = META.years[0]; yr.max = META.years.at(-1);
  yr.addEventListener("input", (e) => { S.year = +e.target.value; render(); });
}

function syncControls() {
  for (const b of document.querySelectorAll(".brand")) b.setAttribute("aria-pressed", String(b.dataset.k === S.brand));
  $("spec").value = S.spec; $("state").value = S.state; $("map-metric").value = S.map;
  $("year").value = S.year; $("year-out").textContent = S.year;
  for (const [id, f] of [["pay-metric", "pay"], ["rx-metric", "rx"]])
    for (const b of $(id).querySelectorAll("button")) b.setAttribute("aria-pressed", String(b.dataset.k === S[f]));
}

async function render() {
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
  legend($("pay-legend"), ps, ps[0].pts.some((p) => DISCLOSURE.has(p.code)));
  const rs = lineChart($("rx-chart"), S.rx, "rx");
  legend($("rx-legend"), rs, rs[0].pts.some((p) => DISCLOSURE.has(p.code)));
  captions();
  drawMap();
  drawTable();
  writeHash();
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
  S = readHash();
  controls();
  drawText();
  await render();
  let w = innerWidth;
  addEventListener("resize", () => { if (innerWidth !== w) { w = innerWidth; render(); } });
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", render);
}
init();
