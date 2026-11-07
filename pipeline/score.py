"""Score (BUILD-SPEC 4.3). Every weight is an ASSUMPTION and is shown in the UI."""
from . import codes
from .rules import STATUTORY, SQFT_PER_ACRE

WEIGHTS = {"size_fit": 25, "best_pathway": 25, "he_listed": 15, "owner_lead": 15,
           "low_intensity": 10, "transit": 5, "no_open_pathway_cap": 30, "label": "ASSUMPTION"}


def size_fit(sqft):
    if 6000 <= sqft <= SQFT_PER_ACRE:
        return 25
    if 2400 <= sqft < 6000:
        return 15  # ASSUMPTION: under ~6,000 sf it is hard to fit 2+ homes
    if SQFT_PER_ACRE < sqft <= 2 * SQFT_PER_ACRE:
        return 15
    if 1200 <= sqft < 2400:
        return 10
    return 0


def best_pathway(paths):
    st = [p["status"] for p in paths if p["id"] in STATUTORY]
    if "PASS" in st or "CLEAR" in st:
        return 25
    if "UNKNOWN" in st:
        return 12
    return 0


def score(f, hz, paths, owner_lead=None):
    """Return (score, breakdown, excluded_by_hazard)."""
    he_pass = any(p["id"] == "HE" and p["status"] == "PASS" for p in paths)
    b = {
        "size_fit": size_fit(f["acres"] * SQFT_PER_ACRE),
        "best_pathway": best_pathway(paths),
        "he_listed": WEIGHTS["he_listed"] if he_pass else 0,
        "owner_lead": WEIGHTS["owner_lead"] if owner_lead else 0,
        "low_intensity": WEIGHTS["low_intensity"] if (f["lu"] in codes.LU_VACANT or f["lu"] in codes.LU_SURFACE_PARKING) else 0,
        "transit": WEIGHTS["transit"] if (f["hqta"] or f["near_stop"]) else 0,
    }
    gated = hz["flood"]["result"] == "FAIL" or hz["fire"]["result"] == "FAIL"
    total = sum(b.values())
    # ASSUMPTION: a site where every statutory pathway FAILs (and it is not a housing-element site) cannot
    # rank among the sites to call, however well it scores on size, owner lead and land use.
    if b["best_pathway"] == 0 and not he_pass:
        total = min(total, WEIGHTS["no_open_pathway_cap"])
    return (0 if gated else total), b, gated


def excluded(f, he_listed=False, owner_lead=False):
    """Reason string if the parcel is dropped from the ranked list, else None."""
    sqft = f["acres"] * SQFT_PER_ACRE
    if sqft < 1200:
        return "lot under 1,200 sf"
    if f["acres"] > 5:
        return "lot over 5 acres"
    if codes.zone_family(f["zone"]) in ("industrial", "open_space") and not (he_listed or owner_lead):
        return "industrial / public / open-space zoning"
    return None
