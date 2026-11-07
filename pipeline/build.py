"""Build data/candidates.json + data/meta.json.  Usage: python -m pipeline.build --city "Santa Ana" """
import argparse
import json
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path

from . import codes, geo
from .fetch import query, bbox_params, digits
from .rules import evaluate, CHECKED, SQFT_PER_ACRE, AB2011_ADJ_M, SB4_INDUSTRIAL_BUFFER_M, PERIM_RADIUS_M, TRANSIT_M
from .score import score, excluded, WEIGHTS

DATA = Path(__file__).resolve().parent.parent / "data"
SCAG = "https://maps.scag.ca.gov/scaggis/rest/services"
OC = "https://www.ocgis.com/arcpub/rest/services/Map_Layers"
URLS = {
    "D1": SCAG + "/LDX/Zoning_poly_OR/MapServer/0/query",
    "D2": SCAG + "/LDX/Existinglanduse_poly_OR/MapServer/0/query",
    "D3": SCAG + "/LDX/HousingElementSite_poly_scag/MapServer/0/query",
    "D4": OC + "/Floodplains/MapServer/0/query",
    "D5": OC + "/Fire_Hazard_Severity_Zones_LRA/MapServer/0/query",
    "D6": OC + "/Liquefaction/MapServer/0/query",
    "D7": "https://caltrans-gis.dot.ca.gov/arcgis/rest/services/CHrailroad/CA_HQ_Transit_Areas/FeatureServer/0/query",
    "D8": SCAG + "/OpenData/Major_Transit_Stops_Plan_Year_2022/MapServer/0/query",
    "D9": OC + "/Parcels/FeatureServer/0/query",
}
NAMES = {"D1": "SCAG Zoning_poly_OR", "D2": "SCAG Existinglanduse_poly_OR", "D3": "SCAG HousingElementSite_poly_scag",
         "D4": "OC Floodplains", "D5": "OC Fire Hazard Severity Zones LRA", "D6": "OC Liquefaction",
         "D7": "Caltrans CA HQ Transit Areas", "D8": "SCAG Major Transit Stops 2022", "D9": "OC Parcels (address only)"}
sources = {}


def step(sid, fn):
    """Run one fetch; record status in sources; return features or None on failure."""
    try:
        feats = fn()
        sources[sid] = {"status": "ok", "rows": len(feats)}
        return feats
    except Exception as e:  # keep going; dependent tests become UNKNOWN
        print(f"  {sid} FAILED: {e}")
        sources[sid] = {"status": "failed", "rows": 0, "error": str(e)[:200]}
        return None


def skipped(sid):
    sources[sid] = {"status": "skipped", "rows": 0}
    return None


def apn_display(apn):
    return f"{apn[:3]}-{apn[3:6]}-{apn[6:]}" if len(apn) == 8 else apn


def load_parcels(city):
    sq = city.replace("'", "''")
    feats = step("D1", lambda: query("zoning", URLS["D1"], f"CITY='{sq}'", "APN24,CITY,ZN24_CITY,ZN24_SCAG,ACRES,SLOPE", 2000,
                                     {"returnGeometry": "true", "geometryPrecision": 5}))
    parcels = {}
    for f in feats or []:
        a, g = f["attributes"], f.get("geometry") or {}
        apn = digits(a["APN24"])
        if not apn or not g.get("rings"):
            continue
        lon, lat = geo.ring_centroid(g["rings"][0])
        prev = parcels.get(apn)
        if prev and prev["acres"] >= (a["ACRES"] or 0):
            continue  # stacked/duplicate APN: keep the largest polygon
        parcels[apn] = {"apn": apn, "zone": (a["ZN24_CITY"] or "").strip(), "scag_zone": a["ZN24_SCAG"],
                        "acres": a["ACRES"] or 0.0, "slope": a["SLOPE"], "lon": round(lon, 6), "lat": round(lat, 6),
                        "lu": None, "lu2": None}
    return parcels


def join_landuse(parcels, city):
    sq = city.replace("'", "''")
    feats = step("D2", lambda: query("landuse", URLS["D2"], f"CITY='{sq}'", "APN24,LU24,LU24_2ND", 2000,
                                     {"returnGeometry": "false"}))
    if feats is None:
        return False
    for f in feats:
        p = parcels.get(digits(f["attributes"]["APN24"]))
        if p:
            p["lu"], p["lu2"] = f["attributes"]["LU24"] or None, f["attributes"]["LU24_2ND"] or None
    return True


def load_he(city):
    feats = step("D3", lambda: query("housing_element", URLS["D3"], "COUNTY='Orange'", "*", 2000, {"returnGeometry": "false"}))
    if feats is None:
        return None
    out = {}
    for f in feats:
        a = f["attributes"]
        if city.upper() in (a.get("Jurisdiction") or "").upper():
            out[digits(a.get("Assessor_Parcel_Number") or a.get("APN24"))] = {
                "listed": True, "capacity_lower": a.get("Low_Income_HE_Capacity"),
                "capacity_moderate": a.get("Moderate_Income_HE_Capacity"),
                "capacity_above_moderate": a.get("Above_Moderate_Income_HE_Capacity"),
                "capacity_total": a.get("Total_HE_Capacity"), "source": URLS["D3"].rsplit("/query", 1)[0]}
    sources["D3"]["city_rows"] = len(out)
    return out or None  # no rows for this city -> UNKNOWN, not "not listed"


def polys(sid, name, fields, page, skip):
    if skip:
        return skipped(sid)
    feats = step(sid, lambda: query(name, URLS[sid], "1=1", fields, page, bbox_params()))
    return None if feats is None else geo.polygons_from_features(feats)


def fetch_addresses(sites):
    """Batch OC Parcels lookups for the given sites; APNs normalised to digits on both sides."""
    found = {}
    try:
        for i in range(0, len(sites), 50):
            chunk = sites[i:i + 50]
            ins = ",".join(f"'{s['apn_display']}'" for s in chunk)
            feats = query(f"oc_parcels/b{i // 50}", URLS["D9"], f"ASSESSMENT_NO IN ({ins})",
                          "ASSESSMENT_NO,SITE_ADDRESS,YEAR_BUILT,NBR_BEDROOMS", 1000, {"returnGeometry": "false"})
            for f in feats:
                found[digits(f["attributes"]["ASSESSMENT_NO"])] = f["attributes"]
        sources["D9"] = {"status": "ok", "rows": len(found)}
    except Exception as e:
        print(f"  D9 FAILED: {e}")
        sources["D9"] = {"status": "failed", "rows": len(found), "error": str(e)[:200]}
    for s in sites:
        a = found.get(s["apn"])
        if a:
            addr = (a.get("SITE_ADDRESS") or "").strip()
            s["address"] = None if not addr or "NOT AVAILABLE" in addr.upper() else addr
            yb = (a.get("YEAR_BUILT") or "").strip()
            s["year_built"] = int(yb) if yb.isdigit() and int(yb) > 0 else None
            s["bedrooms"] = a.get("NBR_BEDROOMS") or None


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--city", default="Santa Ana")
    ap.add_argument("--skip-hazards", action="store_true")
    ap.add_argument("--skip-transit", action="store_true")
    ap.add_argument("--skip-address", action="store_true")
    ap.add_argument("--limit", type=int, default=0, help="only evaluate the first N parcels (dev)")
    ap.add_argument("--top", type=int, default=1000, help="number of ranked sites written to candidates.json")
    ap.add_argument("--address-top", type=int, default=300)
    args = ap.parse_args(argv)

    print("1/6 zoning ..."); parcels = load_parcels(args.city)
    print(f"    {len(parcels)} parcels")
    print("2/6 land use ..."); lu_ok = join_landuse(parcels, args.city)
    print("3/6 housing element ..."); he = load_he(args.city)
    print("4/6 hazards ...")
    flood = polys("D4", "flood", "FLD_ZONE,SFHA_TF", 1000, args.skip_hazards)
    fire = polys("D5", "fire_lra", "HAZ_CLASS,HAZ_CODE", 1000, args.skip_hazards)
    liq = polys("D6", "liquefaction", "OBJECTID,QUAD_NAME", 1000, args.skip_hazards)
    print("5/6 transit ...")
    hqta = polys("D7", "hqta", "hqta_type,agency_primary", 2000, args.skip_transit)
    stops = None
    if args.skip_transit:
        skipped("D8")
    else:
        sf = step("D8", lambda: query("transit_stops", URLS["D8"], "1=1", "OBJECTID,STATIONNAM", 1000, bbox_params()))
        stops = None if sf is None else geo.Grid([(f["geometry"]["x"], f["geometry"]["y"], None) for f in sf], 0.005)

    plist = list(parcels.values())
    allg = geo.Grid([(p["lon"], p["lat"], p) for p in plist], 0.001)
    indg = geo.Grid([(p["lon"], p["lat"], p) for p in plist if codes.lu_family(p["lu"]) == "industrial"], 0.002)
    if args.limit:
        plist = plist[:args.limit]

    print(f"6/6 rules + score on {len(plist)} parcels ...")
    sites, status_counts, excl = [], Counter(), Counter()
    for p in plist:
        x, y = p["lon"], p["lat"]
        f = dict(p)
        if flood is None:
            f["flood"] = None
        else:
            hits = [q.attrs.get("FLD_ZONE") or "" for q in flood if q.contains(x, y)]
            f["flood"] = next((z for z in hits if z[:1] in "AV" and z), hits[0] if hits else "")
        hit = None if fire is None else geo.first_containing(fire, x, y)
        f["fire"] = None if fire is None else (hit.attrs.get("HAZ_CLASS") or "zone") if hit else ""
        f["liq"] = None if liq is None else geo.first_containing(liq, x, y) is not None
        f["hqta"] = None if hqta is None else geo.first_containing(hqta, x, y) is not None
        f["near_stop"] = None if stops is None else bool(stops.near(x, y, TRANSIT_M))
        if lu_ok:
            f["ind60"] = any(q[2] is not p for q in indg.near(x, y, AB2011_ADJ_M))
            f["ind366"] = any(q[2] is not p for q in indg.near(x, y, SB4_INDUSTRIAL_BUFFER_M))
            nb = [q[2] for q in allg.near(x, y, PERIM_RADIUS_M) if q[2] is not p]
            fams = [codes.lu_family(n["lu"]) for n in nb]
            fams = [fm for fm in fams if fm != "unknown"]
            f["perim"] = (sum(fm not in ("vacant", "open_space", "agriculture") for fm in fams), len(fams))
        else:
            f["ind60"] = f["ind366"] = f["perim"] = None
        f["he"] = None if he is None else he.get(p["apn"], False)

        hz, paths = evaluate(f)
        for pw in paths:
            status_counts[f"{pw['id']}:{pw['status']}"] += 1
        he_listed = bool(f["he"])
        why = excluded(f, he_listed=he_listed, owner_lead=False)
        if why:
            excl[why] += 1
            continue
        sc, br, gated = score(f, hz, paths, owner_lead=None)
        fam = codes.zone_family(p["zone"])
        unknowns = sorted({tt["label"] for pw in paths for tt in pw["tests"] if tt["result"] == "UNKNOWN"})
        sites.append({
            "apn": p["apn"], "apn_display": apn_display(p["apn"]), "address": None,
            "lat": p["lat"], "lon": p["lon"], "acres": round(p["acres"], 4),
            "sqft": round(p["acres"] * SQFT_PER_ACRE), "slope": p["slope"],
            "zoning": {"city_code": p["zone"], "scag_code": p["scag_zone"],
                       "label": f"{codes.ZONE_FAMILY_LABEL.get(fam, 'Unmapped zone')} ({codes.ZONING_LABEL})"},
            "land_use": {"code": p["lu"], "label": codes.lu_label(p["lu"]), "secondary": p["lu2"], "source": codes.LU24_SOURCE},
            "year_built": None, "bedrooms": None,
            "hazards": {k: hz[k] for k in ("flood", "fire", "liquefaction", "historic")},
            "pathways": paths,
            "housing_element": f["he"] if he_listed else {"listed": False if he is not None else None, "source": URLS["D3"].rsplit("/query", 1)[0]},
            "surplus_history": None, "owner_lead": None,
            "transit": {"hqta": f["hqta"], "major_stop_within_half_mile": f["near_stop"]},
            "score": sc, "score_breakdown": br, "excluded_by_hazard": gated,
            "who_to_call": [{"who": "City of Santa Ana Planning Division (housing-element site)" if he_listed
                             else "City of Santa Ana Planning Division",
                             "why": "site is in the adopted inventory" if he_listed else "confirm zoning, pathway eligibility and hazards",
                             "contact": "public planning counter"}],
            "unknowns": unknowns,
        })

    sites.sort(key=lambda s: (-s["score"], -s["score_breakdown"]["size_fit"], s["apn"]))
    ranked = len(sites)
    sites = sites[:args.top]
    if not args.skip_address:
        print(f"    addresses for top {min(args.address_top, len(sites))} ...")
        fetch_addresses(sites[:args.address_top])
    else:
        skipped("D9")

    tz = timezone(timedelta(hours=-8))
    built = datetime.now(tz).isoformat(timespec="seconds")
    src = [{"id": k, "name": NAMES[k], "url": URLS[k].rsplit("/query", 1)[0], "checked": CHECKED, **sources.get(k, {"status": "not run", "rows": 0})}
           for k in URLS]
    out = {"city": args.city, "built_at": built, "sources": src, "weights": WEIGHTS, "sites": sites}
    meta = {"city": args.city, "built_at": built, "sources": src, "weights": WEIGHTS,
            "counts": {"parcels": len(parcels), "evaluated": len(plist), "ranked": ranked, "written": len(sites),
                       "excluded": dict(excl), "excluded_by_hazard": sum(s["excluded_by_hazard"] for s in sites),
                       "pathway_status": dict(sorted(status_counts.items()))},
            "notes": ["owner_lead (SB 4 proxy, D10/D12) not run: sb4.owner_proxy is UNKNOWN for every parcel",
                      "surplus_history (D13) not run",
                      "LU24 labels from SCAG layer metadata; zoning mapping is ASSUMPTION"]}
    if args.limit:
        meta["notes"].append(f"dev run: --limit {args.limit}")
    (DATA / "candidates.json").write_text(json.dumps(out, separators=(",", ":")))
    (DATA / "meta.json").write_text(json.dumps(meta, indent=2))

    print("\nLayer  status    rows")
    for s in src:
        print(f"{s['id']:<6} {s['status']:<9} {s['rows']}")
    print("\nPathway  PASS  CLEAR  UNKNOWN  FAIL  FLAG")
    for pid in ("SB9", "SB684", "AB2011", "SB4", "SB79", "HE"):
        print(f"{pid:<8} " + "  ".join(f"{status_counts.get(f'{pid}:{st}', 0):>5}" for st in ("PASS", "CLEAR", "UNKNOWN", "FAIL", "FLAG")))
    print(f"\nranked {ranked}, wrote {len(sites)}; excluded {dict(excl)}")
    for s in sites[:5]:
        print(f"  {s['score']:>3}  {s['apn_display']}  {s['zoning']['city_code']:<6} {s['sqft']:>7} sf  {s['land_use']['label']}  {s['address']}")


if __name__ == "__main__":
    main()
