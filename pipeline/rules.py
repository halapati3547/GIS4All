"""Rule engine (BUILD-SPEC section 4). Pure functions over a parcel 'facts' dict built by build.py.

facts keys: apn, zone, acres, lu, flood, fire, liq, ind60, ind366, perim, near_stop, hqta, he
A value of None means the source layer failed / is missing -> the dependent test is UNKNOWN.
"""
from . import codes

CHECKED = "2026-11-07"
SQFT_PER_ACRE = 43560
HCD_SB9 = "https://www.hcd.ca.gov/sites/default/files/docs/planning-and-community/lot-splits-and-duplexes-sb-9.pdf"
HCD_FACTS = "https://www.hcd.ca.gov/sites/default/files/docs/planning-and-community/housing-law-fact-sheets.pdf"
HCD_SB4 = "https://www.hcd.ca.gov/sites/default/files/docs/planning-and-community/aff-hsg-faith-higher-ed-sb-4.pdf"
HCD_AB2011 = "https://www.hcd.ca.gov/sites/default/files/docs/planning-and-community/draft-ab-2011-guidelines.pdf"
SB79_MAP = "https://santa-ana.gov/documents/draft-sb-79-potential-eligibility-map-with-general-plan-land-uses"

SB9_MIN_SF = 2400
SB684_MF_MAX_AC = 5.0
SB684_SF_VACANT_MAX_AC = 1.5
AB2011_MAX_AC = 20.0
SB4_INDUSTRIAL_BUFFER_M = 366
AB2011_ADJ_M = 60
PERIM_RADIUS_M = 100
PERIM_SHARE = 0.75
TRANSIT_M = 805


# Tests a person must confirm by hand; no public data layer can answer them today.
CONFIRM = {"sb9.tenancy", "haz.historic", "haz.contamination", "haz.slope", "haz.wetland_farmland", "sb684.no_demo_protected"}
# sb4.owner_proxy stays a data test: without an owner lead SB 4 is UNKNOWN, never CLEAR.


def t(id_, label, result, reason, source):
    return {"id": id_, "label": label, "result": result, "reason": reason, "source": source, "checked": CHECKED,
            "kind": "confirm" if id_ in CONFIRM else "data"}


# ---------- shared hazards (4.1) ----------
def hazards(f, source=HCD_FACTS):
    out = {}
    if f["flood"] is None:
        out["flood"] = t("haz.flood", "Flood hazard", "UNKNOWN", "OC Floodplains layer failed to load or returned no features", source)
    elif f["flood"][:1] in ("A", "V"):
        out["flood"] = t("haz.flood", "Special Flood Hazard Area, mitigation required under some pathways", "FAIL",
                         f"centroid inside OC Floodplains FLD_ZONE={f['flood']}", source)
    else:
        z = f" (FLD_ZONE={f['flood']})" if f["flood"] else ""
        out["flood"] = t("haz.flood", "Flood hazard", "PASS", f"centroid outside any A/V flood zone{z}", source)
    if f["fire"] is None:
        out["fire"] = t("haz.fire", "Very High fire hazard (LRA)", "UNKNOWN", "OC Fire LRA layer failed to load or returned no features", source)
    elif "VERY HIGH" in f["fire"].upper():
        out["fire"] = t("haz.fire", "Very High fire hazard (LRA)", "FAIL", f"centroid inside LRA zone {f['fire']}", source)
    else:
        why = f"LRA zone {f['fire']} (not Very High)" if f["fire"] else "no LRA fire zone intersects parcel (layer verified countywide)"
        out["fire"] = t("haz.fire", "Very High fire hazard (LRA)", "PASS", why, source)
    if f["liq"] is None:
        out["liquefaction"] = t("haz.liquefaction", "Liquefaction zone", "UNKNOWN", "OC Liquefaction layer failed to load", source)
    elif f["liq"]:
        out["liquefaction"] = t("haz.liquefaction", "Liquefaction zone", "FLAG",
                                "inside mapped liquefaction zone: investigation likely (not an exclusion)", source)
    else:
        out["liquefaction"] = t("haz.liquefaction", "Liquefaction zone", "PASS", "outside mapped liquefaction zones", source)
    sl = f.get("slope")
    sl_src = "https://maps.scag.ca.gov/scaggis/rest/services/LDX/Zoning_poly_OR/MapServer/0"
    if sl is None:
        out["slope"] = t("haz.slope", "Slope", "UNKNOWN", "SCAG SLOPE field is empty for this parcel", sl_src)
    elif sl == 0:
        # SCAG reports 0 for every Santa Ana parcel we built; that looks unpopulated rather than flat.
        out["slope"] = t("haz.slope", "Slope", "UNKNOWN",
                         "SCAG SLOPE = 0, which may mean unpopulated rather than flat; check a topographic map", sl_src)
    else:
        out["slope"] = t("haz.slope", "Slope", "FLAG",
                         f"SCAG SLOPE = {sl}; no cited steepness threshold, review (ASSUMPTION: not an exclusion)", sl_src)
    out["contamination"] = t("haz.contamination", "Contamination", "UNKNOWN",
                             "no contamination layer loaded; check DTSC EnviroStor and SWRCB GeoTracker for this APN",
                             "https://www.envirostor.dtsc.ca.gov/public/")
    out["historic"] = t("haz.historic", "Historic district", "UNKNOWN",
                        "no verified historic-district layer for this city; check city list", source)
    out["wetland_farmland"] = t("haz.wetland_farmland", "Wetland / farmland", "UNKNOWN",
                                "no wetland or farmland layer checked today", source)
    return out


def pathway_status(tests):
    """FAIL: a test failed. UNKNOWN: a data-backed test could not be run. CLEAR: every data-backed test
    passed and only human-confirm items remain. PASS: everything passed (rare today)."""
    if any(x["result"] == "FAIL" for x in tests):
        return "FAIL"
    if any(x["result"] == "UNKNOWN" and x.get("kind") == "data" for x in tests):
        return "UNKNOWN"
    if any(x["result"] == "UNKNOWN" for x in tests):
        return "CLEAR"
    return "PASS"


def to_confirm(tests):
    return [x["label"] for x in tests if x["result"] == "UNKNOWN" and x.get("kind") == "confirm"]


def _zone_test(id_, label, f, wanted, source):
    fam = codes.zone_family(f["zone"])
    if fam is None:
        return t(id_, label, "UNKNOWN", f"ZN24_CITY={f['zone']!r} is not in the ASSUMPTION zoning mapping", source)
    ok = fam in wanted
    return t(id_, label, "PASS" if ok else "FAIL",
             f"ZN24_CITY={f['zone']} ({codes.ZONE_FAMILY_LABEL[fam]}, ASSUMPTION mapping)", source)


def _urban(id_, source):
    return t(id_, "Urbanized area", "PASS",
             "the city lies within the Census Los Angeles–Long Beach–Anaheim urbanized area (Census Urban Areas)", source)


def _haz(hz, keys, fail_overrides=()):
    return [hz[k] for k in keys]


def sb9(f, hz):
    s = HCD_SB9
    sqft = f["acres"] * SQFT_PER_ACRE
    tests = [
        _zone_test("sb9.zone", "Single-family zone", f, {"single_family"}, s),
        _urban("sb9.urban", s),
        t("sb9.size_split", "Lot large enough to split (>= 2,400 sf)", "PASS" if sqft >= SB9_MIN_SF else "FAIL",
          f"lot ~{sqft:,.0f} sf (SCAG ACRES={f['acres']:.3f})", s),
        t("sb9.tenancy", "No tenant occupancy in prior 3 years", "UNKNOWN", "no data on tenant occupancy in prior 3 years", s),
    ] + [dict(x, source=s) for x in _haz(hz, ("flood", "fire", "historic"))]
    return {"id": "SB9", "name": "SB 9 lot split / two units", "yield": "up to 4 homes on the original lot", "tests": tests}


def sb684(f, hz):
    s = HCD_FACTS
    fam, ac, vacant = codes.zone_family(f["zone"]), f["acres"], codes.lu_family(f["lu"]) == "vacant"
    if fam is None:
        zs = t("sb684.zone_size", "Multifamily <= 5 ac, or vacant single-family <= 1.5 ac", "UNKNOWN",
               f"ZN24_CITY={f['zone']!r} not in ASSUMPTION zoning mapping", s)
    elif fam == "multifamily":
        zs = t("sb684.zone_size", "Multifamily <= 5 ac, or vacant single-family <= 1.5 ac",
               "PASS" if ac <= SB684_MF_MAX_AC else "FAIL", f"multifamily zone {f['zone']}, {ac:.2f} ac", s)
    elif fam == "single_family":
        ok = vacant and ac <= SB684_SF_VACANT_MAX_AC
        zs = t("sb684.zone_size", "Multifamily <= 5 ac, or vacant single-family <= 1.5 ac", "PASS" if ok else "FAIL",
               f"single-family zone {f['zone']}, {ac:.2f} ac, {'vacant' if vacant else 'not vacant'} per SCAG 2024 land use", s)
    else:
        zs = t("sb684.zone_size", "Multifamily <= 5 ac, or vacant single-family <= 1.5 ac", "FAIL",
               f"zone {f['zone']} is {codes.ZONE_FAMILY_LABEL[fam]} (ASSUMPTION mapping)", s)
    nd = (t("sb684.no_demo_protected", "No demolition of protected housing", "PASS", "vacant per SCAG 2024 land use", s)
          if vacant else t("sb684.no_demo_protected", "No demolition of protected housing", "UNKNOWN",
                           f"existing use {codes.lu_label(f['lu'])}; protected-unit status unknown", s))
    tests = [zs, _urban("sb684.urban", s), nd] + [dict(x, source=s) for x in _haz(hz, ("flood", "fire", "historic"))]
    return {"id": "SB684", "name": "SB 684 / SB 1123 small-lot subdivision", "yield": "up to 10 homes", "tests": tests}


def ab2011(f, hz):
    s = HCD_AB2011
    tests = [
        _zone_test("ab2011.zone", "Commercial / office / parking zone", f, {"commercial"}, s),
        t("ab2011.size", "Site <= 20 acres", "PASS" if f["acres"] <= AB2011_MAX_AC else "FAIL", f"{f['acres']:.2f} ac", s),
    ]
    if f["ind60"] is None:
        tests.append(t("ab2011.industrial_adjacency", "Not adjoining an industrial use", "UNKNOWN", "SCAG land use missing", s))
    else:
        tests.append(t("ab2011.industrial_adjacency", "Not adjoining an industrial use", "FAIL" if f["ind60"] else "PASS",
                       ("an" if f["ind60"] else "no") + f" industrial-use parcel centroid within {AB2011_ADJ_M} m "
                       "(APPROXIMATION of 'shares a boundary')", s))
    tests.append(t("ab2011.corridor", "Commercial corridor frontage", "N/A",
                   "N/A for 100% affordable track per HCD", s))
    tests += [dict(x, source=s) for x in _haz(hz, ("flood", "fire", "historic"))]
    return {"id": "AB2011", "name": "AB 2011 housing on commercial sites (100% affordable)", "yield": None, "tests": tests}


def sb4(f, hz):
    s = HCD_SB4
    ow = f.get("owner")
    if ow:
        tests = [t("sb4.owner_proxy", "Owned by a religious institution or nonprofit college (PROXY)", "PASS",
                   f"LEAD: {ow.get('org_name')} at this parcel per {ow.get('source')}. PROXY, confirm with the county assessor", s)]
    else:
        tests = [t("sb4.owner_proxy", "Owned by a religious institution or nonprofit college (PROXY)", "UNKNOWN",
                   "no religious-org or college lead found for this parcel; absence of a proxy is not evidence", s)]
    if f["perim"] is None:
        tests.append(t("sb4.perimeter_urban", "Perimeter >= 75% urban uses", "UNKNOWN", "no neighbouring land-use data", s))
    else:
        urb, tot = f["perim"]
        share = urb / tot if tot else 0
        tests.append(t("sb4.perimeter_urban", "Perimeter >= 75% urban uses",
                       "UNKNOWN" if tot == 0 else ("PASS" if share >= PERIM_SHARE else "FAIL"),
                       f"{urb}/{tot} neighbouring parcel centroids within {PERIM_RADIUS_M} m have urban land use "
                       f"(APPROXIMATION of perimeter test)" if tot else "no neighbouring parcels found within 100 m", s))
    if f["ind366"] is None:
        tests.append(t("sb4.industrial_buffer", "No industrial use within 1,200 ft", "UNKNOWN", "SCAG land use missing", s))
    else:
        tests.append(t("sb4.industrial_buffer", "No industrial use within 1,200 ft", "FAIL" if f["ind366"] else "PASS",
                       ("an" if f["ind366"] else "no") + f" industrial-use parcel centroid within {SB4_INDUSTRIAL_BUFFER_M} m", s))
    tests += [dict(x, source=s) for x in _haz(hz, ("flood", "fire", "wetland_farmland"))]
    return {"id": "SB4", "name": "SB 4 faith / nonprofit-college land", "yield": None, "tests": tests}


def sb79(f):
    s = SB79_MAP
    if f["near_stop"] is None:
        x = t("sb79.transit", "Within 0.5 mi of a major transit stop", "UNKNOWN", "SCAG transit stops layer failed", s)
        st = "UNKNOWN"
    elif f["near_stop"]:
        x = t("sb79.transit", "Within 0.5 mi of a major transit stop", "FLAG",
              "candidate: confirm applicability and tier on the city's SB 79 eligibility map (Santa Ana's is a published draft)", s)
        st = "FLAG"
    else:
        x = t("sb79.transit", "Within 0.5 mi of a major transit stop", "FAIL", "no SCAG 2022 major transit stop within 805 m", s)
        st = "FAIL"
    return {"id": "SB79", "name": "SB 79 transit-oriented upzoning", "status": st, "yield": None, "tests": [x]}


def he(f):
    s = "https://maps.scag.ca.gov/scaggis/rest/services/LDX/HousingElementSite_poly_scag/MapServer/0"
    h = f["he"]
    if h is None:
        x, st = t("he.listed", "Housing-element site", "UNKNOWN",
                  "SCAG housing-element layer has no records for this city or failed to load; check the city's adopted inventory", s), "UNKNOWN"
    elif h is False:
        x, st = t("he.listed", "Housing-element site", "FAIL", "APN not in SCAG housing-element site layer", s), "FAIL"
    else:
        x, st = t("he.listed", "Housing-element site", "PASS",
                  f"listed in adopted 6th-cycle housing element (lower {h['capacity_lower']}, moderate {h['capacity_moderate']}); may be stale", s), "PASS"
    return {"id": "HE", "name": "Housing-element site", "status": st, "yield": None, "tests": [x]}


STATUTORY = ("SB9", "SB684", "AB2011", "SB4")


def evaluate(f):
    """Return (hazards, pathways) for one parcel."""
    hz = hazards(f)
    paths = [sb9(f, hz), sb684(f, hz), ab2011(f, hz), sb4(f, hz)]
    for p in paths:
        p["status"] = pathway_status(p["tests"])
        p["to_confirm"] = to_confirm(p["tests"])
    paths += [sb79(f), he(f)]
    return hz, paths
