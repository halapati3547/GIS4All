/* Site Scout front end: vanilla JS, Leaflet 1.9.4. */
const $ = (s) => document.querySelector(s);
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const SHORT = { SB9: "SB 9", SB684: "SB 684", AB2011: "AB 2011", SB4: "SB 4", SB79: "SB 79", HE: "HE" };
const MARK = { PASS: "✓", CLEAR: "✓", UNKNOWN: "?", FLAG: "!", FAIL: "✗" };
const COL = { hi: "#c2410c", mid: "#fb923c", low: "#ffffff", ex: "#9ca3af" };
const state = { meta: null, rows: [], sel: -1, markers: {}, limit: 10 };

const band = (r) => (r.hazard_excluded ? "ex" : r.score >= 70 ? "hi" : r.score >= 40 ? "mid" : "low");
const link = (url, text) => (url && /^https?:/.test(url) ? `<a href="${esc(url)}" target="_blank" rel="noopener">${esc(text)} ↗</a>` : esc(url || "—"));
const fmt = (n) => (n == null ? "?" : Number(n).toLocaleString());

const map = L.map("map").setView([33.745, -117.868], 13);
L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 19, attribution: "© OpenStreetMap contributors" }).addTo(map);
const legend = L.control({ position: "bottomleft" });
legend.onAdd = () => {
  const d = L.DomUtil.create("div");
  d.style.cssText = "background:#fff;padding:6px 8px;border-radius:4px;font-size:12px";
  d.innerHTML = `<span style="color:${COL.hi}">●</span> 70+ <span style="color:${COL.mid}">●</span> 40–69 <span style="color:${COL.hi}">○</span> &lt;40 <span style="color:${COL.ex}">✕</span> excluded`;
  return d;
};
legend.addTo(map);

async function api(path, opts) {
  const r = await fetch(path, opts);
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw Object.assign(new Error(body.detail || r.statusText), { status: r.status });
  return body;
}

async function loadMeta() {
  const m = (state.meta = await api("/api/meta"));
  $("#checked").textContent = `Data checked ${String(m.built_at || "").slice(0, 10) || "unknown"}`;
  $("#sample-banner").hidden = !m.using_sample;
}

function query() {
  const p = new URLSearchParams({ city: $("#city").value, limit: state.limit });
  if ($("#f-pathway").value) p.set("pathway", $("#f-pathway").value);
  if ($("#f-min").value) p.set("minSf", $("#f-min").value);
  if ($("#f-max").value) p.set("maxSf", $("#f-max").value);
  if ($("#f-he").checked) p.set("heOnly", "true");
  if ($("#f-haz").checked) p.set("excludeHazardUnknown", "true");
  return p;
}

async function loadSites() {
  let data;
  try { data = await api("/api/sites?" + query()); }
  catch (e) { $("#list").innerHTML = `<li class="empty">Could not load sites: ${esc(e.message)}</li>`; return; }
  state.rows = data.sites;
  state.sel = -1;
  $("#list-title").innerHTML = `${state.limit === 10 ? "Top 10 to call" : "Top " + state.limit} · ${data.total} candidates <button class="linkbtn" id="more">${state.limit === 10 ? "show 50" : "show top 10"}</button>`;
  $("#more").onclick = () => { state.limit = state.limit === 10 ? 50 : 10; loadSites(); };
  renderList();
  renderMarkers();
}

function badges(r) {
  const b = r.pathways.filter((p) => p.status !== "FAIL" && p.id !== "HE").map((p) => `${SHORT[p.id] || p.id} ${MARK[p.status] || ""}`);
  if (r.he_listed) b.push("HE ✓");
  if (r.owner_lead) b.push("SB 4 ★");
  return b.join(" · ");
}

function renderList() {
  const ol = $("#list");
  if (!state.rows.length) { ol.innerHTML = `<li class="empty">No sites match. Loosen the size band or pathway.</li>`; return; }
  ol.innerHTML = state.rows.map((r, i) => `
    <li data-i="${i}" class="${i === state.sel ? "sel" : ""} ${r.hazard_excluded ? "excluded" : ""}">
      <div class="chip ${band(r)}">${r.hazard_excluded ? "✕" : esc(r.score)}</div>
      <div><div>${esc(r.address || "APN " + r.apn_display)}</div>
      <div class="meta">${esc(badges(r)) || "no passing pathway"}</div>
      <div class="meta">${esc(r.why || "")}</div>
      <div class="meta">${["fire", "flood", "slope", "contamination"].map((k) => `${k} ${MARK[(r.hazards || {})[k]] || "?"}`).join(" · ")}</div>
      <div class="meta">${esc(r.acres)} ac · ${esc(r.land_use || "use unknown")}${r.hazard_excluded ? " · excluded by hazard" : ""}</div></div>
    </li>`).join("");
}

function renderMarkers() {
  Object.values(state.markers).forEach((m) => m.remove());
  state.markers = {};
  state.rows.forEach((r, i) => {
    if (r.lat == null || r.lon == null) return;
    const bnd = band(r);
    const icon = bnd === "ex"
      ? L.divIcon({ className: "mk-ex", html: "✕", iconSize: [16, 16] })
      : L.divIcon({ className: "", html: `<div class="mk" style="width:16px;height:16px;background:${COL[bnd]};${bnd === "low" ? `border-color:${COL.hi}` : ""}"></div>`, iconSize: [16, 16] });
    state.markers[r.apn] = L.marker([r.lat, r.lon], { icon, title: r.address || r.apn }).addTo(map).on("click", () => select(i));
  });
}

async function select(i) {
  if (i < 0 || i >= state.rows.length) return;
  state.sel = i;
  renderList();
  const r = state.rows[i];
  $(`#list li[data-i="${i}"]`)?.scrollIntoView({ block: "nearest" });
  if (r.lat != null) map.panTo([r.lat, r.lon]);
  try { renderCard(await api(`/api/sites/${encodeURIComponent(r.apn)}`)); }
  catch (e) { showCard(`<p class="empty">Could not load site: ${esc(e.message)}</p>`); }
}

function showCard(html) { const c = $("#card"); c.hidden = false; c.innerHTML = html; c.scrollTop = 0; setTimeout(() => map.invalidateSize(), 50); }

function testsTable(tests) {
  return `<table><tr><th>Test</th><th>Result</th><th>Reason</th><th>Source</th><th>Checked</th></tr>${tests.map((t) => `
    <tr><td>${esc(t.label || t.id)}</td><td class="t-${esc(t.result)}">${esc(t.result)}</td><td>${esc(t.reason)}</td>
    <td>${link(t.source, "source")}</td><td>${esc(t.checked)}</td></tr>`).join("")}</table>`;
}

function weightsTitle() {
  const w = (state.meta && state.meta.weights) || {};
  return Object.entries(w).filter(([k]) => k !== "label").map(([k, v]) => `${k}: ${v}`).join("\n") + `\n(${w.label || "ASSUMPTION"})`;
}

function renderCard(s) {
  const bd = s.score_breakdown || {};
  const hz = s.hazards || {};
  const he = s.housing_element || {};
  const sh = s.surplus_history;
  const ow = s.owner_lead;
  const excluded = s.excluded_by_hazard || ["flood", "fire"].some((k) => hz[k] && hz[k].result === "FAIL");
  showCard(`
    <header><h3>${esc(s.address || "")} · APN ${esc(s.apn_display || s.apn)}</h3><button class="linkbtn" id="close" aria-label="Close">✕</button></header>
    <div class="meta">${esc(s.acres)} ac (${fmt(s.sqft)} sf) · ${esc(s.zoning?.city_code)} ${esc(s.zoning?.label)} · ${esc(s.land_use?.label)} (SCAG LU24 ${esc(s.land_use?.code)}) · slope ${esc(s.slope ?? "?")}</div>
    <section><span class="score">SCORE ${esc(s.score)}</span> <span title="${esc(weightsTitle())}" class="linkbtn">ⓘ weights</span>
      ${excluded ? `<div class="t-FAIL">Excluded by hazard (still viewable)</div>` : ""}
      <div class="meta">size ${esc(bd.size_fit ?? 0)} · pathway ${esc(bd.best_pathway ?? 0)} · HE ${esc(bd.he_listed ?? 0)} · owner ${esc(bd.owner_lead ?? 0)} · use ${esc(bd.low_intensity ?? 0)} · transit ${esc(bd.transit ?? 0)} (ASSUMPTION)</div></section>
    <section><h2>Hazards</h2>${Object.entries(hz).map(([k, t]) => `<span title="${esc(t.reason)}">${esc(k)} <span class="t-${esc(t.result)}">${esc(t.result || "?")}</span></span>`).join(" · ") || "not run"}</section>
    <section><h2>Pathways</h2>${(s.pathways || []).map((p) => `
      <details><summary><span>${esc(p.name)}</span><span><span class="b ${esc(p.status)}">${esc(p.status)}</span>${p.status === "CLEAR" && p.to_confirm?.length ? ` <small>${p.to_confirm.length} to confirm</small>` : ""} ${esc(p.yield || "")}</span></summary>${testsTable(p.tests || [])}</details>`).join("") || `<p class="empty">No pathways evaluated.</p>`}</section>
    <section><h2>Housing element</h2>${he.listed ? `listed · ${esc(he.capacity_lower ?? 0)} lower-income, ${esc(he.capacity_moderate ?? 0)} moderate capacity · may be stale ${link(he.source, "source")}` : "not listed"}</section>
    <section><h2>Surplus history</h2>${sh ? `NOA ${esc(sh.date)} · ${esc(sh.status)} · ${esc(sh.existing_use || "")} · contact: ${esc(sh.contact || "—")} ${link(sh.source, "source")}` : "none found"}</section>
    <section><h2>Owner lead</h2>${ow ? `${esc(ow.org_name)} · ${esc(ow.type)} · ${esc(ow.source)} · <b>${esc(ow.note)}</b>` : "none found (proxy only)"}</section>
    <section><h2>Who to call</h2><ul>${(s.who_to_call || []).map((w) => `<li><b>${esc(w.who)}</b>: ${esc(w.why)} (${esc(w.contact)})</li>`).join("")}</ul></section>
    ${s.unknowns?.length ? `<section><h2>Unknowns</h2><ul>${s.unknowns.map((u) => `<li>${esc(u)}</li>`).join("")}</ul></section>` : ""}
    <div class="btns"><button class="btn" id="explain">✦ Explain with Claude</button>
      <a class="btn ghost" href="/api/sites/${encodeURIComponent(s.apn)}/export.json" download>Export JSON ⬇</a></div>
    <div id="explain-out"></div>
    <div class="footer">Not legal or financial advice. Prototype.</div>`);
  $("#close").onclick = () => { $("#card").hidden = true; setTimeout(() => map.invalidateSize(), 50); };
  $("#explain").onclick = () => explain(s.apn);
}

async function explain(apn) {
  const out = $("#explain-out");
  out.innerHTML = `<p class="meta">Asking Claude…</p>`;
  try {
    const e = await api("/api/explain", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ apn }) });
    const offline = /template/i.test(e.source || "");
    out.innerHTML = `<div class="explain">${offline ? `<span class="tag">offline template</span>` : `<span class="tag">${esc(e.source)}</span>`}
      <p><b>Brief:</b> ${esc(e.brief)}</p>
      <p><b>Confirm first:</b></p><ol>${(e.confirm_first || []).map((c) => `<li>${esc(c)}</li>`).join("")}</ol>
      <p><b>Call script (draft, not sent):</b> “${esc(e.call_script)}”</p>
      <p><b>Caveats:</b></p><ul>${(e.caveats || []).map((c) => `<li>${esc(c)}</li>`).join("")}</ul></div>`;
  } catch (err) { out.innerHTML = `<p class="t-FAIL">Explain failed: ${esc(err.message)}</p>`; }
}

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

$("#sources-btn").onclick = openSources;
$("#weights-btn").onclick = openSources;
["#f-pathway", "#f-min", "#f-max", "#f-he", "#f-haz", "#city"].forEach((s) => $(s).addEventListener("change", loadSites));
$("#list").addEventListener("click", (e) => { const li = e.target.closest("li[data-i]"); if (li) select(+li.dataset.i); });
document.addEventListener("keydown", (e) => {
  if (["INPUT", "SELECT", "TEXTAREA"].includes(document.activeElement.tagName) || $("#sources").open) return;
  if (e.key === "ArrowDown") { e.preventDefault(); select(Math.min(state.sel + 1, state.rows.length - 1)); }
  if (e.key === "ArrowUp") { e.preventDefault(); select(Math.max(state.sel - 1, 0)); }
});
$("#lookup").addEventListener("submit", async (e) => {
  e.preventDefault();
  const msg = $("#lookup-msg");
  const a = $("#address").value.trim();
  if (!a) { msg.textContent = "Type an address first."; return; }
  msg.textContent = "Checking…";
  try {
    const s = await api("/api/lookup?address=" + encodeURIComponent(a));
    msg.textContent = "";
    renderCard(s);
    const t = new Date(s.fetched_at || Date.now()).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
    const b = document.createElement("div");
    b.className = "lookup-banner";
    b.style.cssText = "background:#fff7ed;border:1px solid #fb923c;border-radius:4px;padding:4px 8px;margin-bottom:6px;font-size:13px";
    b.textContent = s.rank ? `Ranked #${s.rank} of ${s.total}` : `Live check · fetched ${t} · not in the ranked set`;
    $("#card").prepend(b);
    if (s.lat && s.lon) map.setView([s.lat, s.lon], 17);
  } catch (err) {
    msg.textContent = [404, 422].includes(err.status) ? err.message : "Could not place that address. Try 'number street, Santa Ana, CA'.";
  }
});

loadMeta().catch(() => { $("#checked").textContent = "Data checked: meta unavailable"; });
loadSites();
