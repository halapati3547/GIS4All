"""Site Scout API: serves data/candidates.json (or the SAMPLE fallback) and the web/ UI."""
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from api import claude

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
load_dotenv(ROOT / ".env")

app = FastAPI(title="Site Scout")
STATE = {"candidates": {"sites": []}, "meta": {}, "by_apn": {}, "cities": {}}  # cities: {name_lower: {candidates, meta}}


def _read(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_data():
    real = DATA / "candidates.json"
    using_sample = not real.exists()
    cand = _read(real if not using_sample else DATA / "sample" / "candidates.sample.json")
    meta_path = DATA / ("sample/meta.sample.json" if using_sample else "meta.json")
    meta = _read(meta_path) if meta_path.exists() else {}
    # Fill anything meta lacks from the candidates file.
    for key in ("city", "built_at", "sources", "weights"):
        meta.setdefault(key, cand.get(key))
    meta["using_sample"] = using_sample
    meta.setdefault("counts", {})
    meta["counts"].setdefault("candidates", len(cand.get("sites", [])))
    cities = {(cand.get("city") or "Santa Ana").lower(): {"candidates": cand, "meta": meta}}
    # Other OC cities built with `python -m pipeline.build --city "<City>"` live in data/cities/<slug>/.
    if not using_sample:
        for cpath in sorted((DATA / "cities").glob("*/candidates.json")):
            c = _read(cpath)
            mp = cpath.parent / "meta.json"
            m = _read(mp) if mp.exists() else {}
            for key in ("city", "built_at", "sources", "weights"):
                m.setdefault(key, c.get(key))
            m["using_sample"] = False
            m.setdefault("counts", {})
            m["counts"].setdefault("candidates", len(c.get("sites", [])))
            cities[(c.get("city") or cpath.parent.name).lower()] = {"candidates": c, "meta": m}
    by_apn = {}
    for city_name, cd in cities.items():
        for site in cd["candidates"].get("sites", []):
            site.setdefault("city", cd["candidates"].get("city"))
            by_apn[site["apn"]] = site
    STATE.update(candidates=cand, meta=meta, by_apn=by_apn, cities=cities)


def city_data(city):
    return STATE["cities"].get((city or "Santa Ana").lower())


@app.on_event("startup")
def _startup():
    load_data()


def hazard_excluded(site):
    if site.get("excluded_by_hazard"):
        return True
    hz = site.get("hazards") or {}
    return any((hz.get(k) or {}).get("result") == "FAIL" for k in ("flood", "fire"))


def hazard_unknown(site):
    hz = site.get("hazards") or {}
    return any((hz.get(k) or {}).get("result") == "UNKNOWN" for k in ("flood", "fire"))


def why(site):
    """One line for the list: the open pathways, or why there is none. Built only from fields already in the JSON."""
    paths = [p for p in site.get("pathways", []) if p["id"] in ("SB9", "SB684", "AB2011", "SB4") and p["status"] != "FAIL"]
    names = {"SB9": "SB 9", "SB684": "SB 684/1123", "AB2011": "AB 2011", "SB4": "SB 4"}
    opens = ", ".join(f"{names[p['id']]} ({p['status'].lower()})" for p in paths) or "no statutory pathway open"
    unk = [k for k, v in (site.get("hazards") or {}).items() if k in ("flood", "fire", "slope", "contamination") and v.get("result") == "UNKNOWN"]
    return opens + (f"; hazards unchecked: {', '.join(unk)}" if unk else "")


def list_row(site):
    owner = site.get("owner_lead") or {}
    return {
        "why": why(site),
        "hazards": {k: (v or {}).get("result") for k, v in (site.get("hazards") or {}).items()},
        "apn": site["apn"], "apn_display": site.get("apn_display", site["apn"]),
        "address": site.get("address"), "lat": site.get("lat"), "lon": site.get("lon"),
        "acres": site.get("acres"), "sqft": site.get("sqft"), "score": site.get("score", 0),
        "land_use": (site.get("land_use") or {}).get("label"),
        "zoning": (site.get("zoning") or {}).get("city_code"),
        "pathways": [{"id": p["id"], "status": p["status"]} for p in site.get("pathways", [])],
        "he_listed": bool((site.get("housing_element") or {}).get("listed")),
        "owner_lead": owner.get("type"),
        "acquisition_lead": bool(site.get("acquisition_lead")),
        "hazard_excluded": hazard_excluded(site),
    }


def has_pathway(site, pid):
    if pid == "HE" and (site.get("housing_element") or {}).get("listed"):
        return True
    if pid == "CH8":  # tax-default acquisition lead (informational, not a pathway): match the live lead only
        return bool(site.get("acquisition_lead"))
    return any(p["id"] == pid and p["status"] != "FAIL" for p in site.get("pathways", []))


def get_site(apn):
    site = STATE["by_apn"].get(apn)
    if not site:
        raise HTTPException(404, f"no site with apn {apn}")
    return site


@app.get("/api/sites")
def sites(city: str = "Santa Ana", limit: int = 50, pathway: str | None = None,
          minSf: float | None = None, maxSf: float | None = None,
          heOnly: bool = False, excludeHazardUnknown: bool = False):
    cd = city_data(city)
    if not cd:
        return {"city": city, "total": 0, "sites": []}
    cand = cd["candidates"]
    out = []
    for s in cand.get("sites", []):
        sf = s.get("sqft") or 0
        if pathway and not has_pathway(s, pathway):
            continue
        if minSf is not None and sf < minSf:
            continue
        if maxSf is not None and sf > maxSf:
            continue
        if heOnly and not (s.get("housing_element") or {}).get("listed"):
            continue
        if excludeHazardUnknown and hazard_unknown(s):
            continue
        out.append(s)
    out.sort(key=lambda s: s.get("score", 0), reverse=True)
    return {"city": city, "total": len(out), "sites": [list_row(s) for s in out[:max(limit, 0)]]}


def lane3_hint(lead):
    """Land-price hint for Lane 3. Only county numbers from the lead; never a price."""
    if not lead:
        return "ASSUMPTION: no price data; enter purchase price"
    amt, as_of = lead.get("redemption_amount"), lead.get("redemption_as_of")
    red = f"redemption ${amt:,.0f} as of {as_of}" if amt is not None else "redemption amount not on the notice"
    alv = (lead.get("status") or {}).get("assessed_land")
    land = f"county assessed land value ${alv:,.0f} (Prop 13 floor, not market); " if alv else ""
    return (f"ASSUMPTION: {land}{red}. AB 418 requires price >= tax-sale value; the redemption amount is the floor, "
            "not the price (https://legiscan.com/CA/bill/AB418/2172)")


@app.get("/api/sites/{apn}/export.json")
def export(apn: str):
    site = dict(get_site(apn))
    ministerial = [p for p in site.get("pathways", []) if p["id"] in ("SB9", "SB684", "AB2011", "SB4") and p["status"] == "PASS"]
    site["for_lane_2"] = {
        "pathway_is_ministerial": bool(ministerial),
        "pathways": [p["id"] for p in ministerial],
        "clock_days": 60 if ministerial else None,
        "source": "ASSUMPTION: 60-day ministerial review clock; confirm per statute and HCD fact sheets "
                  "https://www.hcd.ca.gov/sites/default/files/docs/planning-and-community/housing-law-fact-sheets.pdf",
    }
    site["for_lane_3"] = {"land_line_hint": lane3_hint(site.get("acquisition_lead"))}
    return JSONResponse(site, headers={"Content-Disposition": f'attachment; filename="{apn}.json"'})


@app.get("/api/sites/{apn}")
def site_detail(apn: str):
    return get_site(apn)


@app.get("/api/meta")
def meta(city: str = "Santa Ana"):
    cd = city_data(city) or {"meta": STATE["meta"]}
    return {**cd["meta"], "cities": [v["candidates"].get("city") for v in STATE["cities"].values()]}


@app.get("/api/cities")
def cities():
    """Every city with a built dataset, with headline counts for the landing page and the city switcher."""
    out = []
    for v in STATE["cities"].values():
        c, m = v["candidates"], v["meta"]
        sites_ = c.get("sites", [])
        counts = m.get("counts", {})
        out.append({"city": c.get("city"), "built_at": c.get("built_at"),
                    "parcels": counts.get("parcels"), "ranked": counts.get("ranked"), "written": len(sites_),
                    "strong_leads": sum(1 for s in sites_ if (s.get("score") or 0) >= 70),
                    "owner_leads": sum(1 for s in sites_ if s.get("owner_lead")),
                    "he_listed": sum(1 for s in sites_ if (s.get("housing_element") or {}).get("listed"))})
    return out


@app.get("/api/lookup")
def lookup(address: str = ""):
    from api.lookup import lookup as do_lookup
    allc = {"sites": [s for v in STATE["cities"].values() for s in v["candidates"].get("sites", [])]}
    code, payload = do_lookup(address, allc)
    if code == 200 and payload.get("apn") and payload["apn"] not in STATE["by_apn"]:
        STATE["by_apn"][payload["apn"]] = payload  # live site: make explain/export work for it
    return JSONResponse(payload, status_code=code)


class ExplainBody(BaseModel):
    apn: str


@app.post("/api/explain")
def explain(body: ExplainBody):
    return claude.explain(get_site(body.apn), DATA / "explanations")


app.mount("/", StaticFiles(directory=ROOT / "web", html=True), name="web")
