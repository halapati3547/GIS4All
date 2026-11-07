/* Site Scout front end: vanilla JS, Leaflet 1.9.4. Extra styles live in app-extra.css (x- classes). */
const $ = (s) => document.querySelector(s);
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const SHORT = { SB9: "SB 9", SB684: "SB 684", AB2011: "AB 2011", SB4: "SB 4", SB79: "SB 79", HE: "HE" };
const STRIP = ["SB9", "SB684", "AB2011", "SB4", "SB79"];
const MARK = { PASS: "✓", CLEAR: "✓", UNKNOWN: "?", FLAG: "!", FAIL: "✗", "N/A": "–" };
const COL = { hi: "#c2410c", mid: "#fb923c", low: "#ffffff", ex: "#9ca3af" };
const IRS_BMF = "https://www.irs.gov/charities-non-profits/exempt-organizations-business-master-file-extract-eo-bmf";
const state = { meta: null, rows: [], sel: -1, markers: {}, loadSeq: 0, cardSeq: 0, cardApn: null };

const band = (r) => (r.hazard_excluded ? "ex" : r.score >= 70 ? "hi" : r.score >= 40 ? "mid" : "low");
const link = (url, text) => (url && /^https?:/.test(url) ? `<a href="${esc(url)}" target="_blank" rel="noopener">${esc(text)} ↗</a>` : esc(url || "—"));
const fmt = (n) => (n == null ? "?" : Number(n).toLocaleString());
const cardOpen = () => !$("#card").hidden;
const joinAnd = (a) => (a.length < 2 ? a.join("") : a.slice(0, -1).join(", ") + " and " + a[a.length - 1]);

/* ---------- map ---------- */
const map = L.map("map", { preferCanvas: true }).setView([33.745, -117.868], 13);
L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 19, attribution: "© OpenStreetMap contributors" }).addTo(map);
const legend = L.control({ position: "bottomleft" });
legend.onAdd = () => {
  const d = L.DomUtil.create("div", "x-legend");
  d.innerHTML = `<span style="color:${COL.hi}">●</span> 70+ <span style="color:${COL.mid}">●</span> 40–69 <span style="color:${COL.hi}">○</span> &lt;40 <span style="color:${COL.ex}">●</span> excluded`;
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

function renderMarkers() {
  Object.values(state.markers).forEach((m) => m.remove());
  state.markers = {};
  const pts = [];
  state.rows.forEach((r, i) => {
    if (r.lat == null || r.lon == null) return;
    pts.push([r.lat, r.lon]);
    const tip = `${r.address || "APN " + r.apn_display} · ${r.hazard_excluded ? "excluded" : "score " + r.score}`;
    state.markers[r.apn] = L.circleMarker([r.lat, r.lon], mkStyle(r, false))
      .bindTooltip(esc(tip), { direction: "top", offset: [0, -6] })
      .on("click", () => { if (!(state.sel === i && cardOpen())) select(i); })
      .addTo(map);
  });
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

async function loadMeta() {
  const m = (state.meta = await api("/api/meta"));
  $("#checked").textContent = `Data checked ${String(m.built_at || "").slice(0, 10) || "unknown"}`;
  const sb = $("#sample-banner");
  if (sb) sb.hidden = !m.using_sample;
}

function query() {
  const p = new URLSearchParams({ city: $("#city").value, limit: 50 });
  if ($("#f-pathway").value) p.set("pathway", $("#f-pathway").value);
  if ($("#f-min").value) p.set("minSf", $("#f-min").value);
  if ($("#f-max").value) p.set("maxSf", $("#f-max").value);
  if ($("#f-he").checked) p.set("heOnly", "true");
  if ($("#f-haz").checked) p.set("excludeHazardUnknown", "true");
  return p;
}

async function loadSites() {
  const seq = ++state.loadSeq;
  $("#list").innerHTML = `<li class="x-loading" aria-busy="true">Loading…</li>` + `<li class="x-skel"></li>`.repeat(5);
  exportBtn.disabled = true;
  let data;
  try { data = await api("/api/sites?" + query()); }
  catch (e) {
    if (seq !== state.loadSeq) return;
    $("#list").innerHTML = `<li class="empty">Could not load sites: ${esc(e.message)}</li>`;
    return;
  }
  if (seq !== state.loadSeq) return; // a newer filter change won
  state.rows = data.sites || [];
  state.sel = -1;
  $("#list-title").textContent = `Ten to call · ${fmt(data.total)} candidates`;
  renderList();
  renderMarkers();
  exportBtn.disabled = !state.rows.length;
}

/* ---------- list ---------- */
function chipStrip(r) {
  const by = Object.fromEntries((r.pathways || []).map((p) => [p.id, p.status]));
  const chips = STRIP.map((id) => {
    const st = by[id] || "N/A";
    const muted = st === "FAIL" || st === "N/A";
    return `<span class="b ${esc(st)}${muted ? " x-muted" : ""}" title="${esc(SHORT[id])}: ${esc(st)}">${esc(SHORT[id])} ${MARK[st] || ""}</span>`;
  });
  if (r.he_listed) chips.push(`<span class="b PASS" title="Housing-element site">HE ✓</span>`);
  if (r.owner_lead) chips.push(`<span class="b x-lead" title="Owner lead (PROXY)">owner lead ★</span>`);
  return `<div class="x-strip">${chips.join("")}</div>`;
}

function renderList() {
  const ol = $("#list");
  if (!state.rows.length) { ol.innerHTML = `<li class="empty">No sites match. Loosen the size band or pathway.</li>`; return; }
  ol.innerHTML = state.rows.map((r, i) => `
    <li data-i="${i}" class="${i === state.sel ? "sel" : ""} ${r.hazard_excluded ? "excluded" : ""}">
      <div class="chip ${band(r)}">${r.hazard_excluded ? "✕" : esc(r.score)}</div>
      <div class="x-rowbody"><div class="x-addr">${esc(r.address || "APN " + r.apn_display)}</div>
      ${chipStrip(r)}
      <div class="meta">${esc(r.acres)} ac · ${esc(r.land_use || "use unknown")}${r.hazard_excluded ? " · excluded by hazard" : ""}</div></div>
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

/* export top 10 (button injected under the list) */
const exportWrap = document.createElement("div");
exportWrap.className = "x-export";
exportWrap.innerHTML = `<button class="btn ghost" id="export-top" type="button">Export top 10 ⬇</button><span class="meta" id="export-msg"></span>`;
$("#list").after(exportWrap);
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
  finally { exportBtn.disabled = false; exportBtn.textContent = "Export top 10 ⬇"; }
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

/* One line, built only from fields on the site object. */
function whyLine(s) {
  const bd = s.score_breakdown || {};
  const parts = [];
  const use = s.land_use?.label, zone = s.zoning?.city_code;
  const lot = [use, zone].filter(Boolean).join(" ");
  if (lot || s.sqft != null) parts.push(`${lot ? lot + " lot" : "Lot"}${s.sqft != null ? `, ${fmt(s.sqft)} sf` : ""}`);
  const clear = (s.pathways || []).filter((p) => p.id !== "HE" && ["PASS", "CLEAR"].includes(p.status)).map((p) => SHORT[p.id] || p.id);
  if (clear.length) parts.push(`${joinAnd(clear)} clear`);
  else if ((s.pathways || []).some((p) => p.id !== "HE" && p.status === "UNKNOWN")) parts.push("pathways still unknown");
  if (s.housing_element?.listed) parts.push("housing-element site");
  if (s.owner_lead && bd.owner_lead) parts.push("owner lead (proxy)");
  if (s.transit?.hqta || s.transit?.major_stop_within_half_mile || bd.transit) parts.push("near transit");
  return parts.join(" · ");
}

function bestPathwayIndex(pw) {
  let i = pw.findIndex((p) => ["CLEAR", "PASS"].includes(p.status));
  if (i < 0) i = pw.findIndex((p) => p.status === "UNKNOWN");
  return i;
}

function pathwaysHtml(pw) {
  if (!pw.length) return `<p class="empty">No pathways evaluated.</p>`;
  const best = bestPathwayIndex(pw);
  return pw.map((p, i) => {
    const tc = p.status !== "FAIL" && p.to_confirm?.length ? p.to_confirm : [];
    return `<details${i === best ? " open" : ""}><summary><span>${esc(p.name)}</span><span><span class="b ${esc(p.status)}">${esc(p.status)}</span>${
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

function renderCard(s) {
  const bd = s.score_breakdown || {};
  const hz = s.hazards || {};
  const he = s.housing_element || {};
  const sh = s.surplus_history;
  const excluded = s.excluded_by_hazard || ["flood", "fire"].some((k) => hz[k] && hz[k].result === "FAIL");
  state.cardApn = s.apn;
  showCard(`
    <header><h3>${s.address ? esc(s.address) + " · " : ""}APN ${esc(s.apn_display || s.apn)}</h3><button class="linkbtn" id="close" aria-label="Close">✕</button></header>
    <div class="x-why">${esc(whyLine(s))}</div>
    <div class="meta">${esc(s.acres)} ac (${fmt(s.sqft)} sf) · ${esc(s.zoning?.city_code)} ${esc(s.zoning?.label)} · ${esc(s.land_use?.label)} (SCAG LU24 ${esc(s.land_use?.code)}) · slope ${esc(s.slope ?? "?")}</div>
    <section><span class="score">SCORE ${esc(s.score)}</span> <span title="${esc(weightsTitle())}" class="linkbtn">ⓘ weights</span>
      ${excluded ? `<div class="t-FAIL">Excluded by hazard (still viewable)</div>` : ""}
      <div class="meta">size ${esc(bd.size_fit ?? 0)} · pathway ${esc(bd.best_pathway ?? 0)} · HE ${esc(bd.he_listed ?? 0)} · owner ${esc(bd.owner_lead ?? 0)} · use ${esc(bd.low_intensity ?? 0)} · transit ${esc(bd.transit ?? 0)} (ASSUMPTION)</div></section>
    <section><h2>Hazards</h2>${Object.entries(hz).map(([k, t]) => `<span title="${esc(t.reason)}">${esc(k)} <span class="t-${esc(t.result)}">${esc(t.result || "?")}</span></span>`).join(" · ") || "not run"}</section>
    <section><h2>Pathways</h2>${pathwaysHtml(s.pathways || [])}</section>
    <section><h2>Housing element</h2>${he.listed ? `listed · ${esc(he.capacity_lower ?? 0)} lower-income, ${esc(he.capacity_moderate ?? 0)} moderate capacity · may be stale ${link(he.source, "source")}` : he.listed === false ? "not listed" : "unknown"}</section>
    <section><h2>Surplus history</h2>${sh ? `NOA ${esc(sh.date)} · ${esc(sh.status)} · ${esc(sh.existing_use || "")} · contact: ${esc(sh.contact || "—")} ${link(sh.source, "source")}` : "none found"}</section>
    <section><h2>Owner lead</h2>${ownerHtml(s.owner_lead)}</section>
    <section><h2>Who to call</h2><ul>${(s.who_to_call || []).map((w) => `<li><b>${esc(w.who)}</b>: ${esc(w.why)} (${esc(w.contact)})</li>`).join("")}</ul></section>
    ${s.unknowns?.length ? `<section><h2>Unknowns</h2><ul>${s.unknowns.map((u) => `<li>${esc(u)}</li>`).join("")}</ul></section>` : ""}
    <div class="btns"><button class="btn" id="explain">✦ Explain with Claude</button>
      <a class="btn ghost" href="/api/sites/${encodeURIComponent(s.apn)}/export.json" download>Export JSON ⬇</a></div>
    <div id="explain-out"></div>
    <div class="footer">Not legal or financial advice. Prototype.</div>`);
  $("#close").onclick = closeCard;
  $("#explain").onclick = () => explain(s.apn);
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
  out.innerHTML = `<p class="meta">Asking Claude…</p>`;
  if (btn) btn.disabled = true;
  try {
    const e = await api("/api/explain", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ apn }) });
    if (state.cardApn !== apn) return;
    const offline = /template/i.test(e.source || "");
    out.innerHTML = `<div class="explain">
      <p>${esc(e.brief)}</p>
      <h2>Confirm first</h2><ol>${(e.confirm_first || []).map((c) => `<li>${esc(c)}</li>`).join("")}</ol>
      <h2>Call script <span class="tag">Draft, not sent</span></h2>
      <blockquote class="x-script" id="call-script">${esc(e.call_script)}</blockquote>
      <div class="x-copyrow"><button class="btn ghost" id="copy-script" type="button">Copy call script</button><span class="meta" id="copy-msg"></span></div>
      ${e.caveats?.length ? `<h2>Caveats</h2><ul class="x-caveats">${e.caveats.map((c) => `<li>${esc(c)}</li>`).join("")}</ul>` : ""}
      <div class="meta">Source: <span class="tag">${esc(offline ? "offline template" : e.source || "Claude")}</span></div></div>`;
    $("#copy-script").onclick = async () => {
      const ok = await copyText(e.call_script || "");
      $("#copy-msg").textContent = ok ? "Copied." : "Copy not available here; select the text above and copy it manually.";
    };
  } catch (err) { if (state.cardApn === apn) out.innerHTML = `<p class="t-FAIL">Explain failed: ${esc(err.message)}</p>`; }
  finally { const b = $("#explain"); if (b) b.disabled = false; }
}

/* ---------- sources panel ---------- */
function openSources() {
  const m = state.meta || {};
  const w = m.weights || {};
  $("#sources").innerHTML = `
    <h3>Sources ${m.using_sample ? `<span class="tag">SAMPLE</span>` : ""}</h3>
    <table><tr><th>Layer</th><th>URL</th><th>Rows</th><th>Status</th><th>Checked</th><th>Goes UNKNOWN if failed</th></tr>
    ${(m.sources || []).map((s) => `<tr><td>${esc(s.id)} ${esc(s.name)}</td><td>${link(s.url, s.url)}</td><td>${fmt(s.rows)}</td>
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
  msg.textContent = "Checking…";
  msg.classList.add("x-busy");
  input.disabled = true;
  try {
    const s = await api("/api/lookup?address=" + encodeURIComponent(a));
    msg.textContent = "";
    state.cardSeq++;
    renderCard(s);
    const t = new Date(s.fetched_at || Date.now()).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
    const b = document.createElement("div");
    b.className = "banner lookup-banner x-banner";
    b.textContent = s.rank ? `Ranked #${s.rank} of ${s.total}` : `Live check · fetched ${t} · not in the ranked set`;
    $("#card").prepend(b);
    const i = state.rows.findIndex((r) => r.apn === s.apn);
    if (i >= 0) setSel(i);
    if (s.lat && s.lon) map.setView([s.lat, s.lon], 17);
  } catch (err) {
    msg.textContent = [404, 422].includes(err.status) ? err.message : "Could not place that address. Try 'number street, Santa Ana, CA'.";
  } finally {
    msg.classList.remove("x-busy");
    input.disabled = false;
    input.focus();
  }
}

/* ---------- wiring ---------- */
$("#sources-btn").onclick = openSources;
$("#weights-btn").onclick = openSources;
["#f-pathway", "#f-min", "#f-max", "#f-he", "#f-haz", "#city"].forEach((s) => $(s).addEventListener("change", loadSites));
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

loadMeta().catch(() => { $("#checked").textContent = "Data checked: meta unavailable"; });
loadSites();
