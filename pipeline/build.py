"""Build data/candidates.json + data/meta.json.  Usage: python -m pipeline.build --city "Santa Ana" """
import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path

from . import codes, geo
from .fetch import query, bbox_params, digits, get_json
from .rules import evaluate, ch8_cleared, redemption_ratio, CHECKED, SQFT_PER_ACRE, AB2011_ADJ_M, SB4_INDUSTRIAL_BUFFER_M, PERIM_RADIUS_M, TRANSIT_M
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
    "D14": "https://www.octreasurer.gov/sites/ttc/files/2025-06/Impending%20Power%20to%20Sell%20-%20June%208.pdf",
    "D15": "https://www.ocgis.com/arcpub/rest/services/Treasurer_Tax_Collector/TTC_Final/MapServer/0/query",
}
NAMES = {"D1": "SCAG Zoning_poly_OR", "D2": "SCAG Existinglanduse_poly_OR", "D3": "SCAG HousingElementSite_poly_scag",
         "D4": "OC Floodplains", "D5": "OC Fire Hazard Severity Zones LRA", "D6": "OC Liquefaction",
         "D7": "Caltrans CA HQ Transit Areas", "D8": "SCAG Major Transit Stops 2022", "D9": "OC Parcels (address only)",
         "D14": "OC TTC Power-to-Sell list (PDF)", "D15": "OC TTC secured-tax map (Delinquent flag)"}
AFFECTS = {"D14": ["ch8.on_list"], "D15": ["ch8.current_status"]}
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


def load_owner_leads():
    """D10 proxy written by pipeline/proxies.py: {apn_digits: owner_lead}. Empty if the step was not run."""
    path = DATA / "owner_leads.json"
    if not path.exists():
        return {}
    leads = json.loads(path.read_text())
    print(f"    owner leads (D10 IRS proxy): {len(leads)} parcels")
    return leads


def load_tax_default_leads():
    """D14 (+ D15 status) written by pipeline/taxdefault.py: {apn_digits: lead}. Empty if the step was not run."""
    path = DATA / "tax_default_leads.json"
    if not path.exists():
        sources["D14"] = sources["D15"] = {"status": "not run", "rows": 0}
        return {}
    leads = json.loads(path.read_text())
    sources["D14"] = {"status": "ok", "rows": len(leads), "note": "annual snapshot, names discarded at parse"}
    st = [v["status"] for v in leads.values() if "status" in v]
    ok = sum(1 for x in st if x.get("queried"))
    sources["D15"] = {"status": "not run" if not st else "ok" if ok == len(st) else "partial" if ok else "failed",
                      "rows": ok, "queried": len(st), "note": f"{ok} of {len(st)} lead APNs answered; county data is not real-time"}
    print(f"    tax-default leads (D14 OC TTC): {len(leads)} APNs, D15 status for {ok}/{len(st)}")
    return leads


def lead_view(td):
    """Site-facing acquisition lead: the D14 row + D15 status + two ASSUMPTION signals."""
    s = td.get("status") or {}
    return dict(td, signals={"redemption_to_land_value": redemption_ratio(td), "assessed_land_value": s.get("assessed_land"),
                             "label": "ASSUMPTION: ratio = redemption / county assessed land value (low = owner has equity); "
                                      "assessed land value is a Prop 13 floor, not market"})


TTC_CALLS = [{"who": "OC Treasurer-Tax Collector, Tax-Defaulted Property / Tax Auction unit",
              "why": "parcel is on the county's Power-to-Sell list; ask about a Chapter 8 agreement sale and the Section 3695.5 objection deadline for the next auction",
              "contact": "(714) 834-3411, TaxAuction@octreasurer.gov (public contacts on the notice)"},
             {"who": "Habitat OC Land Bank Reserve (internal)",
              "why": "decide whether to file a nonprofit objection and application before the auction notice is published (late May)",
              "contact": "internal"}]


def site_unknowns(paths, hz=None):
    """UNKNOWN test labels (pathway tests plus hazard screens); a CH8 block without a lead is not a gap in the
    site's data, so it is left out."""
    labels = {tt["label"] for pw in paths if not (pw["id"] == "CH8" and pw["status"] == "UNKNOWN")
              for tt in pw["tests"] if tt["result"] == "UNKNOWN"}
    labels |= {h["label"] for h in (hz or {}).values() if h["result"] == "UNKNOWN"}
    return sorted(labels)


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


def polys(sid, name, fields, page, skip, empty_unknown=False):
    """empty_unknown: a hazard layer that returns 0 features for the city cannot by itself tell 'no hazard' from a
    bad query. So ask the same layer for its countywide count: if it has features elsewhere, the empty city result is
    real (return [], tests PASS); if the count fails or is 0, return None (tests UNKNOWN) and record status 'empty'."""
    if skip:
        return skipped(sid)
    feats = step(sid, lambda: query(name, URLS[sid], "1=1", fields, page, bbox_params()))
    if feats is not None and empty_unknown and not feats:
        try:
            n = int(get_json(f"{name}_count", URLS[sid], {"where": "1=1", "returnCountOnly": "true"}).get("count") or 0)
        except Exception as e:  # count check failed: stay UNKNOWN
            print(f"  {sid} countywide count failed: {e}")
            n = 0
        if n > 0:
            sources[sid] = {"status": "ok", "rows": 0, "countywide_rows": n,
                            "note": f"0 zones in the Santa Ana bbox; the layer returned {n} zones countywide, so the empty result is real"}
            return []
        sources[sid] = {"status": "empty", "rows": 0, "error": "layer returned 0 features for the Santa Ana bbox and no countywide count"}
        return None
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
        # batch caches are keyed by position, so a re-ranked list can miss APNs: fetch only those, keyed by content
        miss = [s for s in sites if s["apn"] not in found]
        for i in range(0, len(miss), 50):
            chunk = miss[i:i + 50]
            key = hashlib.sha1(",".join(s["apn"] for s in chunk).encode()).hexdigest()[:12]
            ins = ",".join(f"'{s['apn_display']}'" for s in chunk)
            feats = query(f"oc_parcels/m{key}", URLS["D9"], f"ASSESSMENT_NO IN ({ins})",
                          "ASSESSMENT_NO,SITE_ADDRESS,YEAR_BUILT,NBR_BEDROOMS", 1000, {"returnGeometry": "false"})
            for f in feats:
                found[digits(f["attributes"]["ASSESSMENT_NO"])] = f["attributes"]
        sources["D9"] = {"status": "ok", "rows": sum(s["apn"] in found for s in sites)}
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
    owner_leads = load_owner_leads()
    tax_leads = load_tax_default_leads()
    print("4/6 hazards ...")
    flood = polys("D4", "flood", "FLD_ZONE,SFHA_TF", 1000, args.skip_hazards, True)
    fire = polys("D5", "fire_lra", "HAZ_CLASS,HAZ_CODE", 1000, args.skip_hazards, True)
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
    sites, status_counts, excl, lead_seen = [], Counter(), Counter(), []
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
        f["owner"] = owner_leads.get(p["apn"])
        f["tax_default"] = tax_leads.get(p["apn"])
        f["tax_status"] = (f["tax_default"] or {}).get("status")

        hz, paths = evaluate(f)
        acq = lead_view(f["tax_default"]) if f["tax_default"] and not ch8_cleared(paths) else None
        if f["tax_default"]:
            lead_seen.append((p["apn"], acq is not None))
        for pw in paths:
            status_counts[f"{pw['id']}:{pw['status']}"] += 1
        he_listed = bool(f["he"])
        why = excluded(f, he_listed=he_listed, owner_lead=bool(f["owner"]), acquisition_lead=bool(acq))
        if why:
            excl[why] += 1
            continue
        sc, br, gated = score(f, hz, paths, owner_lead=f["owner"], acquisition_lead=acq)
        fam = codes.zone_family(p["zone"])
        unknowns = site_unknowns(paths, hz)
        sites.append({
            "apn": p["apn"], "apn_display": apn_display(p["apn"]), "address": None,
            "lat": p["lat"], "lon": p["lon"], "acres": round(p["acres"], 4),
            "sqft": round(p["acres"] * SQFT_PER_ACRE), "slope": p["slope"],
            "zoning": {"city_code": p["zone"], "scag_code": p["scag_zone"],
                       "label": f"{codes.ZONE_FAMILY_LABEL.get(fam, 'Unmapped zone')} ({codes.ZONING_LABEL})"},
            "land_use": {"code": p["lu"], "label": codes.lu_label(p["lu"]), "secondary": p["lu2"], "source": codes.LU24_SOURCE},
            "year_built": None, "bedrooms": None,
            "hazards": {k: hz[k] for k in ("flood", "fire", "fire_2025", "liquefaction", "slope", "contamination", "historic")},
            "pathways": paths,
            "housing_element": f["he"] if he_listed else {"listed": False if he is not None else None, "source": URLS["D3"].rsplit("/query", 1)[0]},
            "surplus_history": None, "owner_lead": f["owner"], "acquisition_lead": acq,
            "transit": {"hqta": f["hqta"], "major_stop_within_half_mile": f["near_stop"]},
            "score": sc, "score_breakdown": br, "excluded_by_hazard": gated,
            "who_to_call": (TTC_CALLS if acq else []) + ([{"who": f["owner"]["org_name"], "why": "religious-organisation lead on this parcel (PROXY); ask whether they would consider housing on the site",
                              "contact": "organisation's public contact; address from the IRS exempt-organisations file"}] if f["owner"] else []) +
                           [{"who": "City of Santa Ana Planning Division (housing-element site)" if he_listed
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
    src = [{"id": k, "name": NAMES[k], "url": URLS[k].rsplit("/query", 1)[0], "checked": CHECKED,
            **({"affects": AFFECTS[k]} if k in AFFECTS else {}), **sources.get(k, {"status": "not run", "rows": 0})}
           for k in URLS]
    written = {s["apn"] for s in sites}
    live = [a for a, ok in lead_seen if ok]
    in_top = [a for a in live if a in written]
    out = {"city": args.city, "built_at": built, "sources": src, "weights": WEIGHTS, "sites": sites}
    meta = {"city": args.city, "built_at": built, "sources": src, "weights": WEIGHTS,
            "counts": {"parcels": len(parcels), "evaluated": len(plist), "ranked": ranked, "written": len(sites),
                       "excluded": dict(excl), "excluded_by_hazard": sum(s["excluded_by_hazard"] for s in sites),
                       "pathway_status": dict(sorted(status_counts.items()))},
            "notes": [f"owner_lead (SB 4 proxy, D10 IRS BMF + Census geocoder + OC Parcels): {len(owner_leads)} parcels with a lead; OSM (D12) not run",
                      f"acquisition_lead (D14 OC TTC Power-to-Sell 2024+2025): {len(lead_seen)} Santa Ana parcels on the list, "
                      f"{len(lead_seen) - len(live)} cleared on the county tax map (D15) and dropped, {len(live)} carry the lead, "
                      f"{len(in_top)} in the ranked output (top {args.top}): {', '.join(apn_display(a) for a in sorted(in_top))}",
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
    for pid in ("SB9", "SB684", "AB2011", "SB4", "SB79", "HE", "CH8"):
        print(f"{pid:<8} " + "  ".join(f"{status_counts.get(f'{pid}:{st}', 0):>5}" for st in ("PASS", "CLEAR", "UNKNOWN", "FAIL", "FLAG")))
    print(f"\nranked {ranked}, wrote {len(sites)}; excluded {dict(excl)}")
    for s in sites[:5]:
        print(f"  {s['score']:>3}  {s['apn_display']}  {s['zoning']['city_code']:<6} {s['sqft']:>7} sf  {s['land_use']['label']}  {s['address']}")


if __name__ == "__main__":
    main()
