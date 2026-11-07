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
        return 422, {"detail": OUTSIDE, "city": out.get("city")}
    if err in ("geocode", "no parcel at that point"):
        return 404, {"detail": NOT_PLACED}
    return 502, {"detail": f"Live check failed: {err}"}
