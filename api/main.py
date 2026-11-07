"""Site Scout API: serves data/candidates.json (or the SAMPLE fallback) and the web/ UI."""
import collections
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


# ---------- plain-language facets used by the filter panel ----------
OK_STATUS = ("PASS", "CLEAR")


def label_of(site):
    """Same bands as the tool: 70+ strong, 60-69 worth a call, 50-59 possible, else long shot."""
    if hazard_excluded(site):
        return "hazard"
    sc = site.get("score") or 0
    return "strong" if sc >= 70 else "worth" if sc >= 60 else "possible" if sc >= 50 else "longshot"


def homes_of(site):
    """Most homes a cleared law allows on this lot: 10 under SB 684, 4 under SB 9, else None (not set by the law)."""
    ok = {p["id"] for p in site.get("pathways", []) if p["status"] in OK_STATUS}
    return 10 if "SB684" in ok else 4 if "SB9" in ok else None


def use_of(site):
    lu = str((site.get("land_use") or {}).get("label") or "").lower()
    if "vacant" in lu:
        return "vacant"
    if "parking" in lu:
        return "parking"
    if "religious" in lu:
        return "church"
    if "residential" in lu or "duplex" in lu or "apartment" in lu or "condominium" in lu:
        return "homes"
    if any(w in lu for w in ("commercial", "retail", "office", "hotel", "shopping")):
        return "commercial"
    return "other"


def leads_of(site):
    out = []
    if site.get("owner_lead"):
        out.append("church")
    if site.get("acquisition_lead"):
        out.append("tax")
    if (site.get("housing_element") or {}).get("listed"):
        out.append("plan")
    return out


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
        "label": label_of(site), "homes": homes_of(site), "use": use_of(site), "leads": leads_of(site),
    }


def has_pathway(site, pid):
    """A pathway filter keeps only sites where that law actually opens the site: PASS or CLEAR (every
    data-backed test passed). SB 79 is never cleared today, so it keeps FLAG (within reach of major transit).
    HE keeps sites listed in the city's housing element. UNKNOWN never counts as a match."""
    if pid == "HE":
        return bool((site.get("housing_element") or {}).get("listed"))
    if pid == "CH8":  # tax-default acquisition lead, if that layer is present
        return bool(site.get("acquisition_lead"))
    ok = ("PASS", "CLEAR", "FLAG") if pid == "SB79" else ("PASS", "CLEAR")
    return any(p["id"] == pid and p["status"] in ok for p in site.get("pathways", []))


def in_hazard_zone(site):
    """True when a mapped hazard touches the parcel: flood or fire FAIL, or a liquefaction FLAG."""
    hz = site.get("hazards") or {}
    return any((hz.get(k) or {}).get("result") in ("FAIL", "FLAG") for k in ("flood", "fire", "liquefaction"))


def get_site(apn):
    site = STATE["by_apn"].get(apn)
    if not site:
        raise HTTPException(404, f"no site with apn {apn}")
    return site


@app.get("/api/sites")
def sites(city: str = "Santa Ana", limit: int = 50, pathway: str | None = None,
          minSf: float | None = None, maxSf: float | None = None,
          heOnly: bool = False, excludeHazardUnknown: bool = False, avoidHazards: bool = False,
          vacantOnly: bool = False, offset: int = 0, label: str | None = None, lead: str | None = None,
          use: str | None = None, minHomes: int | None = None, hasAddress: bool = False, sort: str = "score"):
    """Filters combine with AND. label / lead / use take comma lists (any of). lead accepts church, tax, plan,
    any or none. sort: score (default), size_desc, size_asc, homes."""
    cd = city_data(city)
    if not cd:
        return {"city": city, "total": 0, "sites": []}
    cand = cd["candidates"]
    want_lead = set(lead.split(",")) if lead else None

    def lead_ok(x):
        have = set(leads_of(x))
        if "none" in want_lead:
            return not have
        if "any" in want_lead:
            return bool(have)
        return bool(want_lead & have)

    base = [  # filters that are not shown as chip groups
        lambda x: not pathway or has_pathway(x, pathway),
        lambda x: minSf is None or (x.get("sqft") or 0) >= minSf,
        lambda x: maxSf is None or (x.get("sqft") or 0) <= maxSf,
        lambda x: not heOnly or bool((x.get("housing_element") or {}).get("listed")),
        lambda x: not avoidHazards or not in_hazard_zone(x),
        lambda x: not vacantOnly or use_of(x) in ("vacant", "parking"),
        lambda x: not excludeHazardUnknown or not hazard_unknown(x),
        lambda x: not hasAddress or bool(x.get("address")),
    ]
    groups = {  # chip groups: each group's counts ignore that group's own selection
        "label": lambda x: not label or label_of(x) in label.split(","),
        "use": lambda x: not use or use_of(x) in use.split(","),
        "lead": lambda x: not want_lead or lead_ok(x),
        "homes": lambda x: not minHomes or (homes_of(x) or 0) >= minHomes,
    }
    pool = [x for x in cand.get("sites", []) if all(f(x) for f in base)]
    out = [x for x in pool if all(g(x) for g in groups.values())]
    keys = {"size_desc": lambda x: -(x.get("sqft") or 0), "size_asc": lambda x: x.get("sqft") or 0,
            "homes": lambda x: (-(homes_of(x) or 0), -(x.get("score") or 0))}
    out.sort(key=keys.get(sort, lambda x: -(x.get("score") or 0)))

    def facet(name, keyfn):
        others = [g for n, g in groups.items() if n != name]
        return collections.Counter(k for x in pool if all(g(x) for g in others) for k in keyfn(x))
    facets = {"label": facet("label", lambda x: [label_of(x)]), "use": facet("use", lambda x: [use_of(x)]),
              "lead": facet("lead", lambda x: leads_of(x) or ["none"]),
              "homes": facet("homes", lambda x: [str(homes_of(x) or 0)])}
    counts = cd["meta"].get("counts", {})
    return {"city": city, "total": len(out), "offset": offset, "shortlist": len(cand.get("sites", [])), "facets": facets,
            "eligible": counts.get("ranked"), "parcels": counts.get("parcels"),
            "sites": [list_row(s) for s in out[max(offset, 0):max(offset, 0) + max(limit, 0)]]}


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
