"""GET /api/lookup glue: map pipeline.lookup results to (status_code, payload)."""
from pipeline.lookup import lookup_address

NOT_PLACED = "Could not place that address. Try 'number street, city, CA'."
OUTSIDE = ("That address is not in a ranked list yet. Ranked lists cover the cities in the city menu; "
           "live checks of unranked addresses run in Santa Ana only today.")


def lookup(address, candidates=None):
    out = lookup_address(address, candidates)
    err = out.get("error")
    if not err:
        return 200, out
    if err == "outside":
        c = (out.get("city") or "").strip()
        msg = (f"This parcel is in {c}, but not in {c}'s ranked list of the top 1,000 sites. "
               "Live checks of unranked parcels run in Santa Ana only today.") if c else OUTSIDE
        return 422, {"detail": msg, "city": c}
    if err == "no SCAG zoning row for this APN":
        return 422, {"detail": "That parcel is not in the regional zoning data (often a condo unit, road or public parcel), "
                               "so Site Scout cannot screen it. Try the street address of the whole lot."}
    if err in ("geocode", "no parcel at that point"):
        return 404, {"detail": NOT_PLACED}
    return 502, {"detail": f"Live check failed: {err}"}
