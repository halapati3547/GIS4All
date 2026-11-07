"""Live address lookup: Census geocoder (D11) -> OC Parcels point query (D9) -> APN -> ranked site or live evaluation.

The per-parcel feature/site construction mirrors pipeline/build.py main() (it is inline there, so the minimal
logic is copied here); helpers (load_parcels, join_landuse, load_he, polys, URLS) are imported and read the
on-disk cache in data/raw/, so only the geocode, parcel and APN24 row queries hit the network.
"""
import hashlib
import json
import re
from datetime import datetime, timedelta, timezone

import requests

from . import build, codes, geo
from .fetch import RAW, _get, digits
from .rules import evaluate, SQFT_PER_ACRE, AB2011_ADJ_M, SB4_INDUSTRIAL_BUFFER_M, PERIM_RADIUS_M, TRANSIT_M
from .score import score

GEOCODER = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"
CITY = "Santa Ana"
_CTX = {}


def geocode(address):
    """(lon, lat, matched_address) or None. Cached at data/raw/geocode/<sha1>.json."""
    path = RAW / "geocode" / (hashlib.sha1(address.upper().encode()).hexdigest()[:16] + ".json")
    if path.exists():
        data = json.loads(path.read_text())
    else:
        r = requests.get(GEOCODER, params={"address": address, "benchmark": "Public_AR_Current", "format": "json"}, timeout=30)
        r.raise_for_status()
        data = r.json()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data))
    m = (data.get("result") or {}).get("addressMatches") or []
    if not m:
        return None
    c = m[0]["coordinates"]
    return c["x"], c["y"], m[0].get("matchedAddress")


def parcel_at(lon, lat, address=""):
    """OC Parcels attributes for a geocoded point, or None.

    The Census geocoder interpolates along the street centreline, so the point usually lands in the street.
    Query a ~70 m envelope and keep the parcel whose SITE_ADDRESS has the same house number and street word;
    fall back to a strict point-in-parcel hit.
    """
    def q(geom, gtype, rg="false"):
        return _get(build.URLS["D9"], {"geometry": geom, "geometryType": gtype, "inSR": 4326, "outSR": 4326,
                                       "spatialRel": "esriSpatialRelIntersects", "outFields": "*", "returnGeometry": rg,
                                       "f": "json"}).get("features") or []
    hit = q(f"{lon},{lat}", "esriGeometryPoint")
    m = re.match(r"\s*(\d+)\s+(.*)", address.split(",")[0])
    if m:
        num = m.group(1)
        words = [w for w in re.findall(r"[A-Z0-9]+", m.group(2).upper()) if w not in ("N", "S", "E", "W", "ST", "AVE", "AV", "BLVD", "DR", "RD", "WAY", "PL", "LN", "CT")]
        d = 0.0007
        for f in q(f"{lon - d},{lat - d},{lon + d},{lat + d}", "esriGeometryEnvelope"):
            sa = (f["attributes"].get("SITE_ADDRESS") or "").upper().split()
            if sa and sa[0] == num and all(w in sa for w in words[:1]):
                return f["attributes"]
    if hit:
        return hit[0]["attributes"]
    d = 0.0004  # last resort: nearest parcel centroid within ~45 m (labelled by the caller via SITE_ADDRESS)
    near = [f for f in q(f"{lon - d},{lat - d},{lon + d},{lat + d}", "esriGeometryEnvelope", "true") if (f.get("geometry") or {}).get("rings")]
    if not near:
        return None
    best = min(near, key=lambda f: geo.haversine_m(lon, lat, *geo.ring_centroid(f["geometry"]["rings"][0])))
    return best["attributes"]


def _context():
    """Citywide layers from the build cache (loaded once per process)."""
    if not _CTX:
        parcels = build.load_parcels(CITY)
        lu_ok = build.join_landuse(parcels, CITY)
        plist = list(parcels.values())
        sf = build.query("transit_stops", build.URLS["D8"], "1=1", "OBJECTID,STATIONNAM", 1000, build.bbox_params())
        _CTX.update(
            parcels=parcels, lu_ok=lu_ok, he=build.load_he(CITY), owner_leads=build.load_owner_leads(),
            flood=build.polys("D4", "flood", "FLD_ZONE,SFHA_TF", 1000, False, True),
            fire=build.polys("D5", "fire_lra", "HAZ_CLASS,HAZ_CODE", 1000, False, True),
            liq=build.polys("D6", "liquefaction", "OBJECTID,QUAD_NAME", 1000, False),
            hqta=build.polys("D7", "hqta", "hqta_type,agency_primary", 2000, False),
            stops=geo.Grid([(f["geometry"]["x"], f["geometry"]["y"], None) for f in sf], 0.005),
            allg=geo.Grid([(p["lon"], p["lat"], p) for p in plist], 0.001),
            indg=geo.Grid([(p["lon"], p["lat"], p) for p in plist if codes.lu_family(p["lu"]) == "industrial"], 0.002))
    return _CTX


def _scag_row(url, apn, fields, geom):
    d = _get(url, {"where": f"APN24='{apn}'", "outFields": fields, "returnGeometry": "true" if geom else "false",
                   "outSR": 4326, "f": "json"})
    return d.get("features") or []


def live_site(apn, address):
    zf = _scag_row(build.URLS["D1"], apn, "APN24,CITY,ZN24_CITY,ZN24_SCAG,ACRES,SLOPE", True)
    zf = [f for f in zf if (f.get("geometry") or {}).get("rings")]
    if not zf:
        return {"error": "no SCAG zoning row for this APN"}
    f0 = max(zf, key=lambda f: f["attributes"]["ACRES"] or 0)  # stacked APN: keep the largest polygon, as build.py does
    a = f0["attributes"]
    if (a.get("CITY") or "").strip().lower() != CITY.lower():
        return {"error": "outside", "city": a.get("CITY")}
    lon, lat = geo.ring_centroid(f0["geometry"]["rings"][0])
    lf = _scag_row(build.URLS["D2"], apn, "APN24,LU24,LU24_2ND", False)
    la = lf[0]["attributes"] if lf else {}
    p = {"apn": apn, "zone": (a["ZN24_CITY"] or "").strip(), "scag_zone": a["ZN24_SCAG"], "acres": a["ACRES"] or 0.0,
         "slope": a["SLOPE"], "lon": round(lon, 6), "lat": round(lat, 6), "lu": la.get("LU24") or None, "lu2": la.get("LU24_2ND") or None}

    c = _context()
    x, y, f = p["lon"], p["lat"], dict(p)
    flood, fire, liq, hqta, stops = c["flood"], c["fire"], c["liq"], c["hqta"], c["stops"]
    if flood is None:
        f["flood"] = None
    else:
        hits = [q.attrs.get("FLD_ZONE") or "" for q in flood if q.contains(x, y)]
        f["flood"] = next((z for z in hits if z[:1] in "AV" and z), hits[0] if hits else "")
    hit = None if fire is None else geo.first_containing(fire, x, y)
    f["fire"] = None if fire is None else (hit.attrs.get("HAZ_CLASS") or "zone") if hit else ""
    f["liq"] = None if liq is None else geo.first_containing(liq, x, y) is not None
    f["hqta"] = None if hqta is None else geo.first_containing(hqta, x, y) is not None
    f["near_stop"] = bool(stops.near(x, y, TRANSIT_M))
    if c["lu_ok"] and lf:
        f["ind60"] = any(q[2]["apn"] != apn for q in c["indg"].near(x, y, AB2011_ADJ_M))
        f["ind366"] = any(q[2]["apn"] != apn for q in c["indg"].near(x, y, SB4_INDUSTRIAL_BUFFER_M))
        fams = [codes.lu_family(q[2]["lu"]) for q in c["allg"].near(x, y, PERIM_RADIUS_M) if q[2]["apn"] != apn]
        fams = [fm for fm in fams if fm != "unknown"]
        f["perim"] = (sum(fm not in ("vacant", "open_space", "agriculture") for fm in fams), len(fams))
    else:
        f["ind60"] = f["ind366"] = f["perim"] = None
    he = c["he"]
    f["he"] = None if he is None else he.get(apn, False)
    f["owner"] = c.get("owner_leads", {}).get(apn)

    hz, paths = evaluate(f)
    sc, br, gated = score(f, hz, paths, owner_lead=f["owner"])
    he_listed = bool(f["he"])
    fam = codes.zone_family(p["zone"])
    he_src = build.URLS["D3"].rsplit("/query", 1)[0]
    return {
        "apn": apn, "apn_display": build.apn_display(apn), "address": address,
        "lat": p["lat"], "lon": p["lon"], "acres": round(p["acres"], 4), "sqft": round(p["acres"] * SQFT_PER_ACRE),
        "slope": p["slope"],
        "zoning": {"city_code": p["zone"], "scag_code": p["scag_zone"],
                   "label": f"{codes.ZONE_FAMILY_LABEL.get(fam, 'Unmapped zone')} ({codes.ZONING_LABEL})"},
        "land_use": {"code": p["lu"], "label": codes.lu_label(p["lu"]), "secondary": p["lu2"], "source": codes.LU24_SOURCE},
        "year_built": None, "bedrooms": None,
        "hazards": {k: hz[k] for k in ("flood", "fire", "liquefaction", "slope", "contamination", "historic")},
        "pathways": paths,
        "housing_element": f["he"] if he_listed else {"listed": False if he is not None else None, "source": he_src},
        "surplus_history": None, "owner_lead": f["owner"],
        "transit": {"hqta": f["hqta"], "major_stop_within_half_mile": f["near_stop"]},
        "score": sc, "score_breakdown": br, "excluded_by_hazard": gated,
        "who_to_call": [{"who": "City of Santa Ana Planning Division", "why": "confirm zoning, pathway eligibility and hazards",
                         "contact": "public planning counter"}],
        "unknowns": sorted({tt["label"] for pw in paths for tt in pw["tests"] if tt["result"] == "UNKNOWN"}
                           | {h["label"] for h in hz.values() if h["result"] == "UNKNOWN"}),
        "live": True,
    }


def lookup_address(address: str, candidates=None) -> dict:
    """Return a site dict (with rank/total if ranked, else live=True) or {"error": ...}."""
    try:
        address = (address or "").strip()
        if not address:
            return {"error": "geocode"}
        if "," not in address:  # no city given
            address += ", Santa Ana, CA"
        g = geocode(address)
        if not g:
            return {"error": "geocode"}
        lon, lat, matched = g
        pa = parcel_at(lon, lat, matched or address)
        if not pa:
            return {"error": "no parcel at that point"}
        apn = digits(pa.get("ASSESSMENT_NO"))
        site_addr = (pa.get("SITE_ADDRESS") or "").strip()
        site_addr = matched if not site_addr or "NOT AVAILABLE" in site_addr.upper() else site_addr
        if candidates is None:
            candidates = json.loads((build.DATA / "candidates.json").read_text())
        sites = sorted(candidates.get("sites", []), key=lambda s: -s.get("score", 0))
        for i, s in enumerate(sites):
            if s["apn"] == apn:
                return dict(s, rank=i + 1, total=len(sites))
        out = live_site(apn, site_addr)
        if "error" not in out:
            out["fetched_at"] = datetime.now(timezone(timedelta(hours=-8))).isoformat(timespec="seconds")
        return out
    except Exception as e:
        return {"error": str(e)[:160]}


if __name__ == "__main__":
    import sys
    print(json.dumps(lookup_address(" ".join(sys.argv[1:])), indent=1)[:3000])
