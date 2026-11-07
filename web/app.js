/* Site Scout front end: vanilla JS, Leaflet 1.9.4. Extra styles live in app-extra.css (x- classes). */
const $ = (s) => document.querySelector(s);
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const SHORT = { SB9: "SB 9", SB684: "SB 684", AB2011: "AB 2011", SB4: "SB 4", SB79: "SB 79", HE: "HE", CH8: "Ch. 8" };
/* Plain-language names and one-line glossary for each pathway. */
const PLAIN = {
  SB9: "Lot split or duplex", SB684: "Small subdivision, up to 10 homes", AB2011: "Housing on a commercial site",
  SB4: "Church or college land", SB79: "Near transit", HE: "City housing-plan site",
  CH8: "County tax-default lead",
};
const GLOSS = {
  SB9: "SB 9: State law letting a single-family lot be split or hold two homes, approved without a hearing",
  SB684: "SB 684/1123: State law for up to 10 homes on a small lot, approved without a hearing",
  AB2011: "AB 2011: State law allowing affordable homes on commercial sites",
  SB4: "SB 4: State law letting churches and nonprofit colleges build affordable homes on their land",
  SB79: "SB 79: 2025 state law allowing more homes near major transit stops; the city's map is still draft",
  HE: "Housing element: the city's own list of sites it has planned for new homes",
  CH8: "Chapter 8: a nonprofit may buy a 5-year tax-defaulted parcel directly from the county (an acquisition lead, not a building pathway)",
};
const CH8_LAW = [["https://california.public.law/codes/ca_rev_and_tax_code_section_3791.4", "RTC 3791.4"],
  ["https://california.public.law/codes/ca_rev_and_tax_code_section_3695.5", "RTC 3695.5"],
  ["https://legiscan.com/CA/bill/AB418/2172", "AB 418"]];
const LAW = { SB9: "lot-split law", SB684: "small-subdivision law" };
const CHECK_PLAIN = {
  "Historic district": "Is it in a historic district? (check the city's list)",
  "No tenant occupancy in prior 3 years": "Has anyone rented it in the last 3 years?",
  "Wetland / farmland": "Is any of it wetland or farmland?",
  "No demolition of protected housing": "Would building here remove rent-controlled or affordable homes?",
  "Housing-element site": "Is it on the city's housing-plan site list?",
  "Very High fire hazard (LRA)": "Is it in a very-high fire zone? (the county fire map could not be checked)",
  "CAL FIRE 2025 fire-zone map (LRA)": "Check CAL FIRE's 2025 fire-zone map (the county layer is older)",
  "Slope": "Is the lot steep? (the regional slope field is empty)",
  "Contamination": "Any contamination record? (check EnviroStor and GeoTracker)",
  "Liquefaction zone": "Is it in a liquefaction zone? (a soils report, not an exclusion)",
  "Nonprofit objection filed before the auction notice is first published": "File the nonprofit objection with the county before the late-May auction notice",
  "Board of Supervisors hearing and price finding (AB 418, from 2026)": "County board hearing and price finding (AB 418): price at least auction value",
  "Still delinquent on the county tax map": "Is it still delinquent? (county tax map could not be checked)",
};
/* Short names for the data gaps that keep a pathway from being marked clear. */
const GAP_PLAIN = { fire: "fire map pending", flood: "flood map pending" };  // slope and contamination are unknown everywhere; they stay in the card checklist
const STATUTORY_IDS = ["SB9", "SB684", "AB2011", "SB4"];
const bestOpen = (pw) => (pw || []).find((p) => STATUTORY_IDS.includes(p.id) && p.status === "UNKNOWN");
const gapList = (hz) => Object.entries(hz || {}).filter(([k, v]) => k in GAP_PLAIN && (v && v.result ? v.result : v) === "UNKNOWN").map(([k]) => GAP_PLAIN[k]);
const ZONE_PLAIN = {
  R1: "zoned for single-family homes", R2: "zoned for apartments", R3: "zoned for apartments", R4: "zoned for apartments",
  C1: "zoned commercial", C2: "zoned commercial", C5: "zoned commercial", P: "zoned for parking or offices",
  M1: "zoned industrial", M2: "zoned industrial", O: "zoned open space or public", A1: "zoned open space or public",
};
const OK = ["PASS", "CLEAR"];
const DETAILS_KEY = "siteScout.details";
<<<<<<< HEAD
const COL = { hi: "#c2410c", mid: "#fb923c", low: "#ffffff", ex: "#9ca3af" };
const IRS_BMF = "https://www.irs.gov/charities-non-profits/exempt-organizations-business-master-file-extract-eo-bmf";
const state = { meta: null, rows: [], sel: -1, markers: {}, loadSeq: 0, cardSeq: 0, cardApn: null, limit: 10 };
=======
const COL = { hi: "#c2410c", mid: "#fb923c", low: "#94a3b8", ex: "#d1d5db" };
const IRS_BMF = "https://www.irs.gov/charities-non-profits/exempt-organizations-business-master-file-extract-eo-bmf";
const state = { meta: null, rows: [], sel: -1, markers: {}, loadSeq: 0, cardSeq: 0, cardApn: null };
>>>>>>> d49811d2d3484b1c620ef497009a990496c1e5f2

const band = (r) => (r.hazard_excluded ? "ex" : r.score >= 70 ? "hi" : r.score >= 60 ? "mid" : "low");
const link = (url, text) => (url && /^https?:/.test(url) ? `<a href="${esc(url)}" target="_blank" rel="noopener">${esc(text)} ↗</a>` : esc(url || "—"));
const fmt = (n) => (n == null ? "?" : Number(n).toLocaleString());
const cardOpen = () => !$("#card").hidden;
const titleCase = (s) => String(s || "").toLowerCase().replace(/\b[a-z]/g, (c) => c.toUpperCase());
const CITY_NAMES = ["santa ana", "anaheim", "garden grove", "stanton"];
const cleanAddr = (a) => { let t = String(a || "").trim(); for (const c of CITY_NAMES) { const re = new RegExp("\\s+" + c + "$", "i"); t = t.replace(re, ""); } return titleCase(t); };
const siteTitle = (r) => (r.address ? cleanAddr(r.address) : `Parcel ${r.apn_display || r.apn} (no street address)`);
// Bands follow how the score is built: 55 = a state law clears on a lot of the right size; 60-69 adds vacant
// land, parking or other points; 70+ adds an owner lead (church) or a city housing-plan listing.
const plainLabel = (r) => (r.hazard_excluded || r.excluded_by_hazard ? "Hazard" : r.score >= 70 ? "Strong lead" : r.score >= 60 ? "Worth a call" : r.score >= 50 ? "Possible" : "Long shot");
const LABEL_HELP = {
  "Strong lead": "A state law clears on the data we have, and there is a church-owner or city housing-plan lead.",
  "Worth a call": "A state law clears, and the lot is vacant, parking or otherwise easier to build on.",
  "Possible": "A state law clears, but the lot is in use today and there is no owner lead yet.",
  "Long shot": "No state law fully clears yet; open details to see what is unknown.",
  "Hazard": "A mapped flood or fire hazard rules this site out.",
};
const info = (id) => (GLOSS[id] ? ` <span class="x-info" tabindex="0" role="img" title="${esc(GLOSS[id])}" aria-label="${esc(GLOSS[id])}">ⓘ</span>` : "");
const pathName = (id) => PLAIN[id] || SHORT[id] || id;
const zoneCode = (z) => String((z && typeof z === "object" ? z.city_code : z) || "").toUpperCase().split("-")[0];
// Prefer the pipeline's own category (works for every city); fall back to Santa Ana code letters.
const FAMILY_PLAIN = { "Single-family residential": "zoned for single-family homes", "Multifamily residential": "zoned for apartments",
  "Commercial / office": "zoned commercial or office", "Industrial": "zoned industrial", "Open space / public": "zoned open space or public" };
const zonePlain = (z) => {
  const fam = z && typeof z === "object" ? String(z.label || "").split(" (")[0] : "";
  if (fam === "Unmapped zone") return "";
  return FAMILY_PLAIN[fam] || ZONE_PLAIN[zoneCode(z)] || "";
};
function usePlain(label) {
  const l = String(label || "");
  if (/vacant/i.test(l)) return "Vacant lot";
  if (/parking facilit/i.test(l)) return "Parking lot";
  if (/religious/i.test(l)) return "Church or worship site";
  if (/^single family residential$/i.test(l)) return "Single-family home";
  return l || "Current use unknown";
}
const isVacantOrParking = (label) => /vacant|parking facilit/i.test(String(label || ""));
const bestOk = (pw) => (pw || []).find((p) => p.id !== "HE" && p.id !== "CH8" && OK.includes(p.status));
const leadLabel = (type) => (/relig|church|faith/i.test(String(type || "")) ? "May be church-owned (unconfirmed)" : "May be nonprofit-owned (unconfirmed)");
const lsGet = (k) => { try { return localStorage.getItem(k); } catch { return null; } };
const lsSet = (k, v) => { try { localStorage.setItem(k, v); } catch { /* storage blocked */ } };
const joinAnd = (a) => (a.length < 2 ? a.join("") : a.slice(0, -1).join(", ") + " and " + a[a.length - 1]);

/* ---------- map ---------- */
const map = L.map("map", { preferCanvas: true }).setView([33.745, -117.868], 13);
L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 19, attribution: "© OpenStreetMap contributors" }).addTo(map);
const legend = L.control({ position: "bottomleft" });
legend.onAdd = () => {
  const d = L.DomUtil.create("div", "x-legend");
  d.innerHTML = `<span style="color:${COL.hi}">●</span> Strong lead <span style="color:${COL.mid}">●</span> Worth a call <span style="color:#64748b">●</span> Possible <span style="color:${COL.ex}">●</span> Hazard`;
  return d;
};
legend.addTo(map);

function mkStyle(r, sel) {
  const b = band(r);
  return {
    radius: sel ? 11 : 6,
    color: sel ? "#111827" : b === "low" ? COL.hi : "#ffffff",
    weight: sel ? 3 : b === "low" ? 2 : 1.5,
    fillColor: COL[b],
    fillOpacity: b === "ex" ? 0.55 : 0.9,
  };
}

function renderMarkers(fit = true) {
  Object.values(state.markers).forEach((m) => m.remove());
  state.markers = {};
  const pts = [];
  state.rows.forEach((r, i) => {
    if (r.lat == null || r.lon == null) return;
    pts.push([r.lat, r.lon]);
    const tip = `${plainLabel(r)} · ${r.address ? titleCase(r.address) : "Parcel " + r.apn_display}`;
    state.markers[r.apn] = L.circleMarker([r.lat, r.lon], mkStyle(r, false))
      .bindTooltip(esc(tip), { direction: "top", offset: [0, -6] })
      .on("click", () => { if (!(state.sel === i && cardOpen())) select(i); })
      .addTo(map);
  });
  if (!fit) return;  // "Show more" keeps the current view
  if (pts.length === 1) map.setView(pts[0], 16);
  else if (pts.length) map.fitBounds(L.latLngBounds(pts), { padding: [30, 30], maxZoom: 16 });
}

function highlightMarker(prev, next) {
  const pr = state.rows[prev], nr = state.rows[next];
  if (pr && state.markers[pr.apn]) state.markers[pr.apn].setStyle(mkStyle(pr, false));
  if (nr && state.markers[nr.apn]) state.markers[nr.apn].setStyle(mkStyle(nr, true)).bringToFront();
}

/* ---------- data ---------- */
async function api(path, opts) {
  const r = await fetch(path, opts);
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw Object.assign(new Error(body.detail || r.statusText), { status: r.status });
  return body;
}

function gapNotice(meta) {
  const bad = (meta?.sources || []).filter((s) => ["empty", "failed"].includes(s.status));
  const el = $("#x-gaps");
  if (!el) return;
  if (!bad.length) { el.hidden = true; return; }
  const fire = bad.some((s) => /fire/i.test(s.name));
  el.hidden = false;
  el.innerHTML = `<b>Today's data gap:</b> ${esc(bad.map((s) => s.name).join(", "))} returned no data${fire ? ", so fire is \"unknown\" on every site and nothing can be marked fully clear yet" : ""}. Every other layer ran. <button class="linkbtn" type="button" onclick="openSources()">See sources</button>`;
}

async function loadCities() {
  // Fill the city menu with every city that has a built dataset; keep ?city= or Santa Ana selected.
  let list = [];
  try { list = await api("/api/cities"); } catch { return; }
  const sel = $("#city");
  const want = new URLSearchParams(location.search).get("city") || sel.value || "Santa Ana";
  const names = list.map((c) => c.city).filter(Boolean).sort((a, b) => (a === "Santa Ana" ? -1 : b === "Santa Ana" ? 1 : a.localeCompare(b)));
  if (!names.length) return;
  sel.innerHTML = names.map((n) => `<option${n === want ? " selected" : ""}>${esc(n)}</option>`).join("");
}

function cityText() {
  const c = $("#city").value || "Santa Ana";
  const ex = document.querySelector(".x-explainer");
  if (ex) ex.textContent = `Where could Habitat build 2 to 12 affordable homes in ${c}? Pick a site on the left or type an address.`;
}

async function loadMeta() {
  const m = (state.meta = await api("/api/meta?city=" + encodeURIComponent($("#city").value || "Santa Ana")));
  gapNotice(state.meta);
  $("#checked").textContent = `Data checked ${String(m.built_at || "").slice(0, 10) || "unknown"}`;
  const sb = $("#sample-banner");
  if (sb) sb.hidden = !m.using_sample;
}

<<<<<<< HEAD
function query() {
  const vac = $("#f-vacant")?.checked;
  // Land use is not an API filter, so for "vacant or parking" fetch the whole ranked set and filter here.
  const p = new URLSearchParams({ city: $("#city").value, limit: vac ? 1000 : state.limit });
=======
const PAGE = 50;
// Filter state. Defaults follow the UX review: start on land that is easiest to build on (houses off).
const FGROUPS = {
  use:   { multi: true,  def: ["vacant", "parking", "church", "commercial"],
           opts: [["vacant", "Vacant lot"], ["parking", "Parking"], ["church", "Church"], ["commercial", "Shop or office"], ["homes", "House"]] },
  lead:  { multi: true,  def: [],
           opts: [["church", "Church or nonprofit owner", "Unconfirmed: matched from the IRS nonprofit list"], ["tax", "County tax-sale lot", "On the county's list of tax-defaulted parcels"], ["plan", "City housing-plan site", "Listed in the city's housing element"]] },
  homes: { multi: false, def: "", opts: [["", "Any"], ["4", "4 or more"], ["10", "Up to 10"]] },
  size:  { multi: false, def: "", opts: [["", "Any"], ["s", "Under 7,500 sq ft"], ["m", "7,500–20,000"], ["l", "Over 20,000"]] },
};
const SIZES = { s: [null, 7499], m: [7500, 20000], l: [20001, null] };
const USE_SHORT = { vacant: "Vacant lot", parking: "Parking lot", church: "Church", commercial: "Shop or office", homes: "House" };
const freshFilters = () => ({ use: new Set(FGROUPS.use.def), lead: new Set(FGROUPS.lead.def), homes: FGROUPS.homes.def, size: FGROUPS.size.def });
state.f = freshFilters();
state.facets = {};

function query(offset = 0) {
  const p = new URLSearchParams({ city: $("#city").value, limit: PAGE, offset, sort: $("#f-sort").value });
  if (state.f.use.size && state.f.use.size < FGROUPS.use.opts.length) p.set("use", [...state.f.use].join(","));
  if (state.f.lead.size) p.set("lead", [...state.f.lead].join(","));
  if (state.f.homes) p.set("minHomes", state.f.homes);
  const sz = SIZES[state.f.size];
  if (sz && sz[0] != null) p.set("minSf", sz[0]);
  if (sz && sz[1] != null) p.set("maxSf", sz[1]);
>>>>>>> d49811d2d3484b1c620ef497009a990496c1e5f2
  if ($("#f-pathway").value) p.set("pathway", $("#f-pathway").value);
  if ($("#f-haz").checked) p.set("avoidHazards", "true");
  if ($("#f-addr").checked) p.set("hasAddress", "true");
  return p;
}

function facetCount(group, key) {
  const f = state.facets[group] || {};
  if (group === "homes") return key === "" ? null : (f["10"] || 0) + (key === "4" ? (f["4"] || 0) : 0);
  return f[key] || 0;
}

function renderChips() {
  for (const [g, def] of Object.entries(FGROUPS)) {
    const box = $("#g-" + g);
    if (!box) continue;
    box.innerHTML = def.opts.map(([k, text, help]) => {
      const on = def.multi ? state.f[g].has(k) : state.f[g] === k;
      const n = g === "size" ? null : facetCount(g, k);
      if (n === 0 && !on && k !== "") return "";
      return `<button type="button" class="x-chip${on ? " on" : ""}" data-g="${g}" data-k="${esc(k)}" aria-pressed="${on}"${help ? ` title="${esc(help)}"` : ""}>${esc(text)}${n != null ? ` <span class="x-cnt">${fmt(n)}</span>` : ""}</button>`;
    }).join("");
  }
  renderActive();
}

function renderActive() {
  const parts = [];
  const name = (g, k) => (FGROUPS[g].opts.find((o) => o[0] === k) || [k, k])[1];
  const useDefault = [...state.f.use].sort().join() === [...FGROUPS.use.def].sort().join();
  if (!useDefault) parts.push(["use", state.f.use.size ? [...state.f.use].map((k) => name("use", k)).join(" or ") : "No land types"]);
  if (state.f.lead.size) parts.push(["lead", [...state.f.lead].map((k) => name("lead", k)).join(" or ")]);
  if (state.f.homes) parts.push(["homes", name("homes", state.f.homes) + " homes"]);
  if (state.f.size) parts.push(["size", name("size", state.f.size)]);
  if ($("#f-pathway").value) parts.push(["pathway", $("#f-pathway").selectedOptions[0].textContent]);
  if ($("#f-haz").checked) parts.push(["haz", "Avoid hazard zones"]);
  if ($("#f-addr").checked) parts.push(["addr", "Has an address"]);
  const base = "";
  const hidden = parts.filter(([k]) => ["lead", "homes", "size", "pathway", "haz", "addr"].includes(k)).length;
  const mc = $("#more-count"); if (mc) mc.textContent = hidden ? `(${hidden} on)` : "";
  $("#x-active").innerHTML = base + parts.map(([k, t]) => `<button type="button" class="x-pill" data-clear="${k}" title="Remove this filter">${esc(t)} ✕</button>`).join("") +
    (parts.length || !useDefault ? ` <button type="button" class="linkbtn" data-clear="all">Reset filters</button>` : "");
}

function clearFilter(k) {
  if (k === "all") { state.f = freshFilters(); $("#f-pathway").value = ""; $("#f-haz").checked = false; $("#f-addr").checked = false; $("#f-sort").value = "score"; }
  else if (k === "use") state.f.use = new Set(FGROUPS.use.def);
  else if (k === "lead") state.f.lead = new Set();
  else if (k === "homes" || k === "size") state.f[k] = "";
  else if (k === "pathway") $("#f-pathway").value = "";
  else if (k === "haz") $("#f-haz").checked = false;
  else if (k === "addr") $("#f-addr").checked = false;
  renderChips(); loadSites();
}

async function loadSites(more = false) {
  const seq = ++state.loadSeq;
  const offset = more ? state.rows.length : 0;
  if (!more) $("#list").innerHTML = `<li class="x-loading" aria-busy="true">Loading…</li>` + `<li class="x-skel"></li>`.repeat(5);
  else moreBtn.textContent = "Loading…";
  exportBtn.disabled = true;
  let data;
  try { data = await api("/api/sites?" + query(offset)); }
  catch (e) {
    if (seq !== state.loadSeq) return;
    $("#list").innerHTML = `<li class="empty">Could not load sites: ${esc(e.message)}</li>`;
    return;
  }
  if (seq !== state.loadSeq) return; // a newer filter change won
<<<<<<< HEAD
  let rows = data.sites || [], total = data.total;
  if ($("#f-vacant")?.checked) { rows = rows.filter((r) => isVacantOrParking(r.land_use)); total = rows.length; rows = rows.slice(0, 50); }
  state.rows = rows;
  state.sel = -1;
  $("#list-title").innerHTML = `${state.limit === 10 ? "Top 10 sites to call first" : "Top " + state.limit + " sites"} · ${fmt(total)} found <button class="linkbtn" id="more">${state.limit === 10 ? "show 50" : "show top 10"}</button>`;
  $("#more").onclick = () => { state.limit = state.limit === 10 ? 50 : 10; loadSites(); };
=======
  state.rows = more ? state.rows.concat(data.sites || []) : (data.sites || []);
  if (!more) state.sel = -1;
  state.total = data.total;
  state.he_empty = state.f.lead.has("plan");
  state.facets = data.facets || {};
  renderChips();
<<<<<<< HEAD
  $("#list-title").innerHTML = `${fmt(data.total)} site${data.total === 1 ? "" : "s"} match` +
    `<small class="x-scope">from ${fmt(data.parcels)} parcels screened in ${esc($("#city").value)} · showing ${fmt(state.rows.length)}</small>`;
>>>>>>> d49811d2d3484b1c620ef497009a990496c1e5f2
=======
  $("#list-title").textContent = `${fmt(data.total)} site${data.total === 1 ? "" : "s"} in ${$("#city").value}`;
  $("#list-title").title = `From ${fmt(data.parcels)} parcels screened in ${$("#city").value}. Showing ${fmt(state.rows.length)}.`;
>>>>>>> 7ef598f33bc0b404df77cea4f29fc32b35d265f3
  renderList();
  renderMarkers(!more);
  const left = data.total - state.rows.length;
  moreBtn.hidden = left <= 0;
  moreBtn.textContent = `Show ${fmt(Math.min(PAGE, left))} more (${fmt(left)} left)`;
  exportBtn.disabled = !state.rows.length;
}

/* ---------- list ---------- */
function rowLine(r) {
  const parts = [esc(usePlain(r.land_use))];
  if (r.sqft != null) parts.push(`${fmt(r.sqft)} sq ft`);
  const best = bestOk(r.pathways);
  if (best) parts.push(`${esc(pathName(best.id))}${info(best.id)} looks clear`);
  else {
    const cand = bestOpen(r.pathways);
    const gaps = gapList(r.hazards);
    parts.push(cand ? `${esc(pathName(cand.id))}${info(cand.id)} fits so far${gaps.length ? ` <span class="x-gap">${esc(gaps.join(", "))}</span>` : ""}` : "Needs checking");
  }
  return parts.join(" · ");
}

function renderList() {
  const ol = $("#list");
  if (!state.rows.length) {
    const city = $("#city").value;
    ol.innerHTML = state.he_empty && city === "Santa Ana"
      ? `<li class="empty">Santa Ana's housing-plan sites are not in the regional data yet, so this filter finds none here. Try Anaheim, Garden Grove or Stanton.</li>`
      : `<li class="empty">No sites match these filters. <button type="button" class="linkbtn" data-clear="all">Reset filters</button> or turn on more land types, such as House.</li>`;
    return;
  }
  ol.innerHTML = state.rows.map((r, i) => `
    <li data-i="${i}" class="${i === state.sel ? "sel" : ""} ${r.hazard_excluded ? "excluded" : ""}">
      <div class="x-rowbody">
<<<<<<< HEAD
        <div class="x-rowtop"><span class="x-label x-${band(r)}" title="${esc(LABEL_HELP[plainLabel(r)] || "")}">${esc(plainLabel(r))}</span>${r.homes ? `<span class="x-homes">up to ${esc(r.homes)} homes</span>` : ""}</div>
        <div class="x-addr">${esc(siteTitle(r))}</div>
        <div class="x-line">${rowLine(r)}</div>
        <div class="x-line">${esc(r.why || "")}</div>
        <div class="x-line">${["fire", "flood", "slope", "contamination"].map((k) => `${k} ${({ PASS: "✓", UNKNOWN: "?", FLAG: "!", FAIL: "✗" })[(r.hazards || {})[k]] || "?"}`).join(" · ")}</div>
        ${r.owner_lead ? `<div class="x-leadtag">★ ${esc(leadLabel(r.owner_lead))}</div>` : ""}
        ${r.acquisition_lead ? `<div class="x-taxtag" title="On the county's Power-to-Sell list (LEAD, confirm status by APN)">◆ tax lead</div>` : ""}
=======
        <div class="x-rowtop"><span class="x-addr">${esc(siteTitle(r))}</span><span class="x-label x-${band(r)}" title="${esc(LABEL_HELP[plainLabel(r)] || "")}">${esc(plainLabel(r))}</span></div>
        <div class="x-line">${esc(USE_SHORT[r.use] || usePlain(r.land_use))}${r.sqft != null ? ` · ${fmt(r.sqft)} sq ft` : ""}${r.homes ? ` · <b class="x-homes">up to ${esc(r.homes)} homes</b>` : ""}${r.owner_lead ? ` · <span class="x-leadmark" title="${esc(leadLabel(r.owner_lead))}">★ church?</span>` : ""}${r.acquisition_lead ? ` · <span class="x-taxtag" title="On the county's tax-default list (confirm status by APN)">◆ tax lot</span>` : ""}</div>
>>>>>>> 7ef598f33bc0b404df77cea4f29fc32b35d265f3
      </div>
    </li>`).join("");
}

function setSel(i) {
  const prev = state.sel;
  state.sel = i;
  $("#list li.sel")?.classList.remove("sel");
  const li = $(`#list li[data-i="${i}"]`);
  if (li) { li.classList.add("sel"); li.scrollIntoView({ block: "nearest" }); }
  highlightMarker(prev, i);
}

/* export top 10 (quiet link injected under the list) */
const EXPORT_TEXT = "Download top 10 (JSON)";
const exportWrap = document.createElement("div");
exportWrap.className = "x-export";
exportWrap.innerHTML = `<button class="linkbtn x-quiet" id="export-top" type="button">${EXPORT_TEXT}</button><span class="meta" id="export-msg" aria-live="polite"></span>`;
$("#list").after(exportWrap);
const moreBtn = document.createElement("button");
moreBtn.type = "button"; moreBtn.className = "btn ghost x-showmore"; moreBtn.hidden = true;
$("#list").after(moreBtn);
moreBtn.onclick = () => loadSites(true);
const exportBtn = $("#export-top");
exportBtn.onclick = async () => {
  const top = state.rows.slice(0, 10);
  if (!top.length) return;
  const msg = $("#export-msg");
  exportBtn.disabled = true;
  exportBtn.textContent = "Preparing…";
  msg.textContent = "";
  try {
    const all = await Promise.all(top.map((r) => api(`/api/sites/${encodeURIComponent(r.apn)}/export.json`)));
    const url = URL.createObjectURL(new Blob([JSON.stringify(all, null, 2)], { type: "application/json" }));
    const a = Object.assign(document.createElement("a"), { href: url, download: `site-scout-top${all.length}.json` });
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 2000);
    msg.textContent = `Saved ${all.length} sites.`;
  } catch (e) { msg.textContent = `Export failed: ${e.message}`; }
  finally { exportBtn.disabled = false; exportBtn.textContent = EXPORT_TEXT; }
};

/* ---------- card ---------- */
async function select(i) {
  if (i < 0 || i >= state.rows.length) return;
  setSel(i);
  const r = state.rows[i];
  if (r.lat != null) map.panTo([r.lat, r.lon]);
  const seq = ++state.cardSeq;
  try {
    const s = await api(`/api/sites/${encodeURIComponent(r.apn)}`);
    if (seq === state.cardSeq) renderCard(s);
  } catch (e) { if (seq === state.cardSeq) showCard(`<p class="empty">Could not load site: ${esc(e.message)}</p>`); }
}

function showCard(html) { const c = $("#card"); c.hidden = false; c.innerHTML = html; c.scrollTop = 0; setTimeout(() => map.invalidateSize(), 50); }
function closeCard() { if (!cardOpen()) return; $("#card").hidden = true; state.cardApn = null; setTimeout(() => map.invalidateSize(), 50); }

function testsTable(tests) {
  return `<table><tr><th>Test</th><th>Result</th><th>Reason</th><th>Source</th><th>Checked</th></tr>${tests.map((t) => `
    <tr><td>${esc(t.label || t.id)}</td><td class="t-${esc(t.result)}">${esc(t.result)}</td><td>${esc(t.reason)}</td>
    <td>${link(t.source, "source")}</td><td>${esc(t.checked)}</td></tr>`).join("")}</table>`;
}

function weightsTitle() {
  const w = (state.meta && state.meta.weights) || {};
  return Object.entries(w).filter(([k]) => k !== "label").map(([k, v]) => `${k}: ${v}`).join("\n") + `\n(${w.label || "ASSUMPTION"})`;
}

/* One plain sentence, built only from fields on the site object (no codes). */
function whyLine(s) {
  const use = usePlain(s.land_use?.label);
  const zone = zonePlain(s.zoning);
  let out = zone ? `${use}, ${zone}` : use;
  if (s.sqft != null) out += `, about ${fmt(s.sqft)} sq ft`;
  const clear = (s.pathways || []).filter((p) => p.id !== "HE" && OK.includes(p.status)).map((p) => pathName(p.id).toLowerCase());
  if (clear.length) out += `. ${joinAnd(clear).replace(/^./, (c) => c.toUpperCase())} ${clear.length > 1 ? "look" : "looks"} clear on the data we have`;
  else {
    const cand = bestOpen(s.pathways);
    const gaps = gapList(s.hazards);
    out += cand ? `. ${pathName(cand.id)} fits on zoning and size${gaps.length ? `; ${joinAnd(gaps)}, so it can't be marked clear yet` : "; a few checks remain"}`
                : ". No state-law pathway is clear yet; it needs checking";
  }
  if (s.transit?.hqta || s.transit?.major_stop_within_half_mile) out += ", near major transit";
  if (s.acquisition_lead) out += ", county tax-default lead";
  return out + ".";
}

function promising(s) {
  const pw = s.pathways || [];
  const out = [];
  if (s.sqft != null) {
    const y = pw.find((p) => OK.includes(p.status) && /\d/.test(p.yield || "") && LAW[p.id]);
    const n = y && (y.yield.match(/up to \d+ homes?/i) || [])[0];
    out.push(`${fmt(s.sqft)} sq ft lot${n ? `: ${esc(n)} under the ${LAW[y.id]}${info(y.id)}` : ""}.`);
  }
  if (s.land_use?.label) out.push(`Today it is: ${esc(usePlain(s.land_use.label).toLowerCase())}${/vacant|parking/i.test(s.land_use.label) ? ", so nobody would be displaced" : ""}.`);
  const clear = pw.filter((p) => p.id !== "HE" && OK.includes(p.status));
  if (clear.length) out.push(`${clear.map((p) => `${esc(pathName(p.id))}${info(p.id)}`).join(", ")}: every data check passed.`);
  else {
    const cand = bestOpen(pw);
    if (cand) {
      const passed = (cand.tests || []).filter((t) => t.result === "PASS").length;
      const waiting = (cand.tests || []).filter((t) => t.result === "UNKNOWN" && t.kind === "data").map((t) => t.label);
      out.push(`${esc(pathName(cand.id))}${info(cand.id)}: ${passed} data check${passed === 1 ? "" : "s"} passed${waiting.length ? `; waiting on ${esc(waiting.map((w) => w.replace(/ \(LRA\)/, "").toLowerCase()).join(", "))}` : ""}.`);
    }
  }
  if (s.acquisition_lead) out.push(`On the county's tax-default sale list since ${esc(s.acquisition_lead.power_to_sell_since)}: a nonprofit can ask to buy it directly${info("CH8")} (lead, needs confirming).`);
  if (s.owner_lead) out.push(`Possible owner: ${esc(s.owner_lead.org_name || "a nonprofit")} (from a public registry, needs confirming).`);
  if (s.housing_element?.listed) out.push("The city already lists it as a housing-plan site.");
  if (s.transit?.hqta || s.transit?.major_stop_within_half_mile) out.push("Within half a mile of a major transit stop.");
  return out.slice(0, 4);
}

function checklist(s) {
  const pw = s.pathways || [];
  const best = bestOk(pw) || pw.find((p) => !["HE", "CH8"].includes(p.id) && p.status === "UNKNOWN");
  const seen = new Set();
  return [...((best && best.to_confirm) || []), ...(s.unknowns || [])]
    .filter((t) => t && !seen.has(t) && seen.add(t)).slice(0, 5).map((t) => CHECK_PLAIN[t] || t);
}

function plainWho(w) {
  const why = String(w.why || "");
  if (/religious|lead on this parcel/i.test(why)) return "May own or use this land (from a public registry, needs confirming). Ask if they would consider housing here.";
  if (/planning/i.test(w.who || "")) return "Confirm the zoning, which state laws apply, and any hazards.";
  const t = why.replace(/\s*\(PROXY\)/gi, "").trim();
  return t ? t[0].toUpperCase() + t.slice(1).replace(/\.?$/, ".") : "";
}

function bestPathwayIndex(pw) {
  let i = pw.findIndex((p) => p.id !== "CH8" && ["CLEAR", "PASS"].includes(p.status));
  if (i < 0) i = pw.findIndex((p) => p.id !== "CH8" && p.status === "UNKNOWN");
  return i;
}

function pathwaysHtml(pw) {
  if (!pw.length) return `<p class="empty">No pathways evaluated.</p>`;
  const best = bestPathwayIndex(pw);
  return pw.map((p, i) => {
    const tc = p.status !== "FAIL" && p.to_confirm?.length ? p.to_confirm : [];
    const cls = p.id === "CH8" ? "INFO" : p.status;  // CH8 is informational: grey, never a pathway colour
    return `<details${i === best ? " open" : ""}><summary><span>${esc(p.name)}${info(p.id)}</span><span><span class="b ${esc(cls)}">${esc(p.status)}</span>${
      tc.length ? ` <small>${tc.length} to confirm</small>` : ""} ${esc(p.yield || "")}</span></summary>${
      tc.length ? `<ul class="x-confirm">${tc.map((t) => `<li>${esc(t)}</li>`).join("")}</ul>` : ""}${testsTable(p.tests || [])}</details>`;
  }).join("");
}

function ownerHtml(ow) {
  if (!ow) return "none found (proxy only)";
  // Organisation name only; the data carries no person names and none are added.
  return `<div class="x-lead-block"><div class="x-lead-org">★ ${esc(ow.org_name || "Organisation lead")}</div>
    <div class="meta">${esc(ow.type)} · ${esc(ow.source)}</div>
    <div><b>${esc(ow.note || "PROXY, confirm with the county assessor")}</b></div>
    <div class="meta">${link(IRS_BMF, "IRS EO Business Master File")}</div></div>`;
}

function acquisitionHtml(a) {
  if (!a) return "";
  // County notice fields only; the data carries no assessee names and none are added.
  const amt = a.redemption_amount == null ? "redemption amount not on the notice" : `redemption $${fmt(Math.round(a.redemption_amount))} as of ${esc(a.redemption_as_of)}`;
  const st = a.status || {};
  const flag = !st.queried ? "county tax map not checked" : st.delinquent === 1 ? `still delinquent on the county tax map (checked ${esc(st.checked)}, not real-time)` : "status unknown on the county tax map";
  const sig = a.signals || {};
  const extra = [sig.assessed_land_value ? `assessed land value $${fmt(Math.round(sig.assessed_land_value))}` : "",
    sig.redemption_to_land_value != null ? `redemption is ${Math.round(sig.redemption_to_land_value * 100)}% of land value` : ""].filter(Boolean).join(" · ");
  return `<section><h2>Acquisition lead</h2><div class="x-lead-block"><div class="x-lead-org">◆ County Power-to-Sell list (${esc((a.years_on_list || []).join(", "))})</div>
    <div>On the county Power-to-Sell list since ${esc(a.power_to_sell_since)} · ${amt} · Chapter 8 eligible for a nonprofit · objection due before the late-May auction notice · AB 418 board hearing required · <b>LEAD, county status below</b></div>
    <div class="meta">${flag}${extra ? ` · ${extra} (ASSUMPTION signals: Prop 13 floor, not market; ratio is not a verdict)` : ""}</div>
    <div class="meta">${link(a.source_url, "county notice")} · ${CH8_LAW.map(([u, t]) => link(u, t)).join(" · ")}${st.bill_url ? ` · ${link(st.bill_url, "tax bill")}` : ""}</div></div></section>`;
}

function renderCard(s) {
  const bd = s.score_breakdown || {};
  const hz = s.hazards || {};
  const he = s.housing_element || {};
  const sh = s.surplus_history;
  const excluded = s.excluded_by_hazard || ["flood", "fire"].some((k) => hz[k] && hz[k].result === "FAIL");
  const label = excluded ? "Hazard" : plainLabel(s);
  const bullets = promising(s);
  const checks = checklist(s);
  const who = s.who_to_call || [];
  const showDetails = lsGet(DETAILS_KEY) === "1";
  state.cardApn = s.apn;
  showCard(`
    <header><h3>${esc(siteTitle(s))}</h3><button class="linkbtn" id="close" aria-label="Close site card">✕</button></header>
    <div class="x-cardlabel"><span class="x-label x-${excluded ? "ex" : band(s)}">${esc(label)}</span> </div>
    <div class="x-why">${esc(whyLine(s))}</div>
    ${excluded ? `<p class="t-FAIL">Inside a mapped flood or fire hazard zone, so it is ranked last. Still viewable.</p>` : ""}
    ${bullets.length ? `<section><h2>Why it's promising</h2><ul class="x-bullets">${bullets.map((b) => `<li>${b}</li>`).join("")}</ul></section>` : ""}
    ${checks.length ? `<section><h2>Check before you call</h2><ul class="x-checks">${checks.map((c) => `<li><span class="x-box" aria-hidden="true"></span>${esc(c)}</li>`).join("")}</ul></section>` : ""}
    ${who.length ? `<section><h2>Who to call</h2><ul class="x-who">${who.map((w) => `<li><b>${esc(w.who)}</b><br><span>${esc(plainWho(w))}</span></li>`).join("")}</ul></section>` : ""}
    <div class="btns"><button class="btn" id="explain" type="button">✦ Write my call script</button>
      <button class="btn ghost" id="details-btn" type="button" aria-expanded="${showDetails}" aria-controls="details">${showDetails ? "Hide details" : "Show details"}</button></div>
    <div id="explain-out" aria-live="polite"></div>
    <div id="details" class="x-details"${showDetails ? "" : " hidden"}>
      <p class="x-legendline">CLEAR = every data test passed, only human checks remain · UNKNOWN = a data test could not run · FAIL = does not fit · FLAG = note</p>
      <div class="meta">APN ${esc(s.apn_display || s.apn)} · ${esc(s.acres)} ac (${fmt(s.sqft)} sf) · zoning ${esc(s.zoning?.city_code)} ${esc(s.zoning?.label)} · ${esc(s.land_use?.label)} (SCAG LU24 ${esc(s.land_use?.code)}) · slope ${esc(s.slope ?? "?")}</div>
      <section><span class="score">SCORE ${esc(s.score)}</span> <span title="${esc(weightsTitle())}" class="linkbtn">ⓘ weights</span>
        ${excluded ? `<div class="t-FAIL">Excluded by hazard (still viewable)</div>` : ""}
        <div class="meta">size ${esc(bd.size_fit ?? 0)} · pathway ${esc(bd.best_pathway ?? 0)} · HE ${esc(bd.he_listed ?? 0)} · owner ${esc(bd.owner_lead ?? 0)} · use ${esc(bd.low_intensity ?? 0)} · transit ${esc(bd.transit ?? 0)} (ASSUMPTION)</div></section>
      <section><h2>Hazards</h2>${Object.entries(hz).map(([k, t]) => `<span title="${esc(t.reason)}">${esc(k)} <span class="t-${esc(t.result)}">${esc(t.result || "?")}</span></span>`).join(" · ") || "not run"}</section>
      <section><h2>Pathways</h2>${pathwaysHtml(s.pathways || [])}</section>
      <section><h2>Housing element</h2>${he.listed ? `listed · ${esc(he.capacity_lower ?? 0)} lower-income, ${esc(he.capacity_moderate ?? 0)} moderate capacity · may be stale ${link(he.source, "source")}` : he.listed === false ? "not listed" : `unknown ${link(he.source, "source")}`}</section>
      <section><h2>Surplus history</h2>${sh ? `NOA ${esc(sh.date)} · ${esc(sh.status)} · ${esc(sh.existing_use || "")} · contact: ${esc(sh.contact || "—")} ${link(sh.source, "source")}` : "none found"}</section>
      ${acquisitionHtml(s.acquisition_lead)}
      <section><h2>Owner lead</h2>${ownerHtml(s.owner_lead)}</section>
      <section><h2>Who to call (full)</h2><ul>${who.map((w) => `<li><b>${esc(w.who)}</b>: ${esc(w.why)} (${esc(w.contact)})</li>`).join("")}</ul></section>
      ${s.unknowns?.length ? `<section><h2>Unknowns</h2><ul>${s.unknowns.map((u) => `<li>${esc(u)}</li>`).join("")}</ul></section>` : ""}
      <div class="btns"><a class="btn ghost" href="/api/sites/${encodeURIComponent(s.apn)}/export.json" download>Export JSON ⬇</a></div>
    </div>
    <div class="footer">Not legal or financial advice. Prototype.</div>`);
  $("#close").onclick = closeCard;
  $("#explain").onclick = () => explain(s.apn);
  $("#details-btn").onclick = () => {
    const d = $("#details");
    const open = d.hidden;
    d.hidden = !open;
    $("#details-btn").textContent = open ? "Hide details" : "Show details";
    $("#details-btn").setAttribute("aria-expanded", String(open));
    lsSet(DETAILS_KEY, open ? "1" : "0");
  };
}

/* ---------- explain ---------- */
async function copyText(text) {
  try { await navigator.clipboard.writeText(text); return true; }
  catch {
    const ta = Object.assign(document.createElement("textarea"), { value: text });
    ta.style.cssText = "position:fixed;opacity:0";
    document.body.appendChild(ta); ta.select();
    let ok = false;
    try { ok = document.execCommand("copy"); } catch { ok = false; }
    ta.remove();
    return ok;
  }
}

async function explain(apn) {
  const out = $("#explain-out");
  const btn = $("#explain");
  out.innerHTML = `<p class="meta">Writing your call script…</p>`;
  if (btn) btn.disabled = true;
  try {
    const e = await api("/api/explain", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ apn }) });
    if (state.cardApn !== apn) return;
    const offline = /template/i.test(e.source || "");
    out.innerHTML = `<div class="explain">
      <h2>In short</h2><p>${esc(e.brief)}</p>
      <h2>Check first</h2><ol>${(e.confirm_first || []).map((c) => `<li>${esc(CHECK_PLAIN[c] || c)}</li>`).join("")}</ol>
      <h2>Call script <span class="tag">Draft, not sent</span></h2>
      <blockquote class="x-script" id="call-script">${esc(e.call_script)}</blockquote>
      <div class="x-copyrow"><button class="btn ghost" id="copy-script" type="button">Copy call script</button><span class="meta" id="copy-msg" aria-live="polite"></span></div>
      ${e.caveats?.length ? `<ul class="x-caveats">${e.caveats.map((c) => `<li>${esc(c)}</li>`).join("")}</ul>` : ""}
      <div class="meta">Source: <span class="tag">${esc(offline ? "offline template" : e.source || "Claude")}</span></div></div>`;
    $("#copy-script").onclick = async () => {
      const ok = await copyText(e.call_script || "");
      $("#copy-msg").textContent = ok ? "Copied." : "Copy not available here; select the text above and copy it manually.";
    };
  } catch (err) { if (state.cardApn === apn) out.innerHTML = `<p class="t-FAIL">Could not write the call script: ${esc(err.message)}</p>`; }
  finally { const b = $("#explain"); if (b) b.disabled = false; }
}

/* ---------- sources panel ---------- */
function openSources() {
  const m = state.meta || {};
  const w = m.weights || {};
  $("#sources").innerHTML = `
    <h3>Sources ${m.using_sample ? `<span class="tag">SAMPLE</span>` : ""}</h3>
    <table><tr><th>Layer</th><th>URL</th><th>Rows</th><th>Status</th><th>Checked</th><th>Goes UNKNOWN if failed</th></tr>
    ${(m.sources || []).map((s) => `<tr><td>${esc(s.id)} ${esc(s.name)}${s.note ? `<div class="meta">${esc(s.note)}</div>` : ""}</td><td>${link(s.url, s.url)}</td><td>${fmt(s.rows)}</td>
      <td class="st-${esc(s.status)}">${esc(s.status)}</td><td>${esc(s.checked)}</td><td>${esc((s.affects || []).join(", ") || "—")}</td></tr>`).join("")}</table>
    <h3>Score weights <span class="tag">${esc(w.label || "ASSUMPTION")}</span></h3>
    <table>${Object.entries(w).filter(([k]) => k !== "label").map(([k, v]) => `<tr><td>${esc(k)}</td><td>${esc(v)}</td></tr>`).join("")}</table>
    <p class="meta">Every weight is an ASSUMPTION. Flood or fire FAIL sets the score to 0 (excluded by hazard).</p>
    <form method="dialog"><button class="btn">Close</button></form>`;
  $("#sources").showModal();
}

/* ---------- address lookup ---------- */
async function lookup(e) {
  e.preventDefault();
  const msg = $("#lookup-msg");
  const input = $("#address");
  const a = input.value.trim();
  if (!a) { msg.textContent = "Type an address first."; return; }
  msg.textContent = "Checking… (public servers, up to 20 seconds)";
  msg.classList.add("x-busy");
  input.disabled = true;
  const slow = setTimeout(() => { msg.textContent = "Still checking… the county and Census servers are slow right now."; }, 8000);
  try {
    const s = await api("/api/lookup?address=" + encodeURIComponent(a));
    msg.textContent = "";
    // The address may be in another built city: switch the menu and list to it first.
    const sel = $("#city");
    if (s.city && s.city !== sel.value && [...sel.options].some((o) => o.value === s.city)) {
      sel.value = s.city; cityText(); loadMeta().catch(() => {}); await loadSites();
      try { const u = new URL(location.href); u.searchParams.set("city", s.city); history.replaceState(null, "", u); } catch {}
    }
    state.cardSeq++;
    renderCard(s);
    const b = document.createElement("div");
    b.className = "banner lookup-banner x-banner";
    b.textContent = s.rank ? `In the ${s.city || ""} list, ranked #${s.rank} of ${fmt(s.total)}` : "Checked live just now (not in the ranked list)";
    $("#card").prepend(b);
    const i = state.rows.findIndex((r) => r.apn === s.apn);
    if (i >= 0) setSel(i);
    if (s.lat && s.lon) map.setView([s.lat, s.lon], 17);
  } catch (err) {
    msg.textContent = [404, 422].includes(err.status) ? err.message : "Could not place that address. Try 'number street, city, CA'.";
  } finally {
    clearTimeout(slow);
    msg.classList.remove("x-busy");
    input.disabled = false;
    input.focus();
  }
}

/* ---------- wiring ---------- */
$("#sources-btn").onclick = openSources;
$("#weights-btn").onclick = openSources;
["#f-pathway", "#f-haz", "#f-addr", "#f-sort"].forEach((sel) => $(sel).addEventListener("change", () => { renderActive(); loadSites(); }));
document.querySelector(".filters").addEventListener("click", (e) => {
  const b = e.target.closest(".x-chip");
  if (!b) return;
  const g = b.dataset.g, k = b.dataset.k, def = FGROUPS[g];
  if (def.multi) { state.f[g].has(k) ? state.f[g].delete(k) : state.f[g].add(k); }
  else state.f[g] = state.f[g] === k ? "" : k;
  renderChips(); loadSites();
});
$("#x-active").addEventListener("click", (e) => { const b = e.target.closest("[data-clear]"); if (b) clearFilter(b.dataset.clear); });
$("#list").addEventListener("click", (e) => { const b = e.target.closest("[data-clear]"); if (b) { e.stopPropagation(); clearFilter(b.dataset.clear); } });
renderChips();
$("#list").addEventListener("click", (e) => { const li = e.target.closest("li[data-i]"); if (li) select(+li.dataset.i); });
$("#lookup").addEventListener("submit", lookup);
$("#address").addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); $("#lookup").requestSubmit(); } });
document.addEventListener("keydown", (e) => {
  if ($("#sources").open) return;
  if (e.key === "Escape") { closeCard(); return; }
  if (["INPUT", "SELECT", "TEXTAREA"].includes(document.activeElement.tagName)) return;
  if (!state.rows.length) return;
  if (e.key === "ArrowDown") { e.preventDefault(); select(Math.min(state.sel + 1, state.rows.length - 1)); }
  if (e.key === "ArrowUp") { e.preventDefault(); select(Math.max(state.sel - 1, 0)); }
});

loadCities().finally(() => {
  cityText();
  loadMeta().catch(() => { $("#checked").textContent = "Data checked: meta unavailable"; });
  loadSites();
});
