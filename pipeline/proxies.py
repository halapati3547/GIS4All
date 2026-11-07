"""SB 4 owner-type PROXY (D10): IRS Exempt Orgs BMF -> Census geocoder (D11) -> OC Parcels (D9) -> APN.

Usage: python -m pipeline.proxies   (writes data/owner_leads.json; not wired into build.py)
The ICO column (a person's name) is skipped while parsing each row and never stored.
"""
import csv
import json
import time

import requests

from .fetch import RAW, digits
from .lookup import geocode, parcel_at

IRS_URL = "https://www.irs.gov/pub/irs-soi/eo_ca.csv"
CSV = RAW / "irs" / "eo_ca.csv"
OUT = RAW.parent / "owner_leads.json"
SOURCE = "IRS Exempt Organizations BMF (eo_ca.csv), Census geocoder, OC Parcels"
CAP = 250


def download():
    if CSV.exists():
        return
    CSV.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(IRS_URL, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(CSV.with_suffix(".part"), "wb") as fh:
            for chunk in r.iter_content(1 << 20):
                fh.write(chunk)
    CSV.with_suffix(".part").rename(CSV)


def orgs(city):
    """Religious orgs (NTEE X* or FOUNDATION 10 = church) in the city, deduped by street."""
    out, seen = [], set()
    with open(CSV, newline="", encoding="latin-1") as fh:
        rd = csv.reader(fh)
        head = next(rd)
        keep = [i for i, h in enumerate(head) if h != "ICO"]  # drop ICO before building any row
        names = [head[i] for i in keep]
        for raw in rd:
            row = dict(zip(names, (raw[i] if i < len(raw) else "" for i in keep)))
            if row["CITY"].strip().upper() != city.upper():
                continue
            if not (row["NTEE_CD"].startswith("X") or row["FOUNDATION"].strip() == "10"):
                continue
            st = " ".join(row["STREET"].upper().split())
            if st and st not in seen:
                seen.add(st)
                out.append({"name": row["NAME"].strip(), "street": st, "zip": row["ZIP"][:5]})
    return out


def local_matcher(city):
    """Match a point to a parcel using the cached SCAG zoning polygons for the city (no county server call).
    Strict containment first; Census points sit on the street centreline, so fall back to the nearest
    parcel centroid within 45 m."""
    from . import geo
    folder = RAW / "cities" / city.lower().replace(" ", "-") / "zoning"
    if city == "Santa Ana":
        folder = RAW / "zoning"
    polys = []
    for f in sorted(folder.glob("*.json")):
        polys += geo.polygons_from_features(json.loads(f.read_text()).get("features", []))
    cents = [(geo.ring_centroid(pg.rings[0]), pg) for pg in polys]

    def match(lon, lat):
        hit = geo.first_containing(polys, lon, lat)
        if hit:
            return digits(hit.attrs.get("APN24"))
        best, bd = None, 45.0
        for (cx, cy), pg in cents:
            if abs(cx - lon) > 0.0006 or abs(cy - lat) > 0.0006:
                continue
            d = geo.haversine_m(lon, lat, cx, cy)
            if d < bd:
                best, bd = pg, d
        return digits(best.attrs.get("APN24")) if best else None
    return match, len(polys)


def owner_leads(city="Santa Ana", cap=CAP, local=False):
    download()
    found = orgs(city)
    cache_dir = RAW / "geocode"
    leads, geocoded = {}, 0
    match = None
    if local:
        match, n = local_matcher(city)
        print(f"[{city}] local parcel matching against {n} cached SCAG parcel polygons")
    for o in found[:cap]:
        addr = f"{o['street']}, {city}, CA {o['zip']}"
        before = len(list(cache_dir.glob("*.json"))) if cache_dir.exists() else 0
        try:
            g = geocode(addr)
            if len(list(cache_dir.glob("*.json"))) > before:
                time.sleep(0.2)
            if not g:
                continue
            geocoded += 1
            apn = match(g[0], g[1]) if match else digits((parcel_at(g[0], g[1], g[2] or addr) or {}).get("ASSESSMENT_NO"))
        except Exception as e:
            print(f"  skip {o['street']}: {str(e)[:80]}")
            continue
        if apn and apn not in leads:
            leads[apn] = {"type": "religious_org_proxy", "org_name": o["name"], "source": SOURCE,
                          "note": "PROXY from a public registry; confirm with the county assessor"}
    out = OUT if city == "Santa Ana" else RAW.parent / "cities" / city.lower().replace(" ", "-") / "owner_leads.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(leads, indent=1))
    print(f"[{city}] orgs {len(found)} (capped at {cap}), geocoded {geocoded}, matched a parcel {len(leads)} -> {out}")
    return leads


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--city", default="Santa Ana")
    ap.add_argument("--cap", type=int, default=CAP)
    ap.add_argument("--local", action="store_true", help="match to cached SCAG parcel polygons instead of the OC Parcels server")
    a = ap.parse_args()
    owner_leads(a.city, a.cap, a.local)
