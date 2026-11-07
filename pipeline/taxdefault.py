"""D14 tax-default acquisition lead: OC TTC Power-to-Sell list -> APN -> Chapter 8 eligibility.
D15 status: the county tax map's Delinquent flag, one APN per query, only for leads that join to a D1 parcel.

Usage: python -m pipeline.taxdefault   (writes data/tax_default_leads.json; build.py only reads it)
Assessee names are discarded while parsing each row and never stored: a row is reduced to APN, whether the
notice prints a situs address, and the redemption amount before anything else touches it. The D15 query never
requests the layer's Name field.
"""
import json
import re
import subprocess
import time
from datetime import datetime
from pathlib import Path

import requests

from .fetch import RAW, digits
from .rules import CHECKED

LISTS = {  # year the parcel became subject to the power to sell -> PDF
    2025: "https://www.octreasurer.gov/sites/ttc/files/2025-06/Impending%20Power%20to%20Sell%20-%20June%208.pdf",
    2024: "https://www.octreasurer.gov/sites/ttc/files/2024-09/Notice%20of%20Power%20and%20Intent%20to%20Sell%20Tax-Defaulted%20Property%20June%202024.pdf",
}
TIMESHARE_BOOKS = {"898", "899", "916"}
SOURCE = "OC Treasurer-Tax Collector, Notice of Power and Intent to Sell Tax-Defaulted Property (RTC 3361-3362)"
NOTE = ("LEAD from a public county notice; redemption may have occurred since publication. "
        "Confirm current status at TaxBill.octreasurer.gov by APN.")
TTC_MAP = "https://www.ocgis.com/arcpub/rest/services/Treasurer_Tax_Collector/TTC_Final/MapServer/0"
TTC_FIELDS = "AssessmentNo,Delinquent,ta,alv,aiv,tav,UseDqLanduse,ViewPayBill"  # never add Name
TTC_NOTE = "county says the tax-map data is not real-time; confirm with the Treasurer-Tax Collector"
PDFTOTEXT = "/opt/homebrew/bin/pdftotext"
PDF_DIR = RAW / "ttc"
STATUS_DIR = RAW / "ttc_status"
OUT = RAW.parent / "tax_default_leads.json"
LEAD_KEYS = {"type", "power_to_sell_since", "years_on_list", "redemption_amount", "redemption_as_of",
             "situs_address_on_notice", "timeshare", "source", "source_url", "checked", "note", "status"}
STATUS_KEYS = {"delinquent", "tax_current_year", "assessed_land", "assessed_improvement", "assessed_total",
               "county_use_code", "bill_url", "queried", "found", "checked", "source", "note"}

ROW_START = re.compile(r"NO\.\s*\d+")
APN = re.compile(r"\s*(\d{3}-\d{3}-\d{2})\b")
AMOUNT = re.compile(r"\$([\d,]+\.\d{2})")
DATE = r"([A-Z][a-z]+\s+\d{1,2},\s*\d{4})"


def _iso(s):
    return datetime.strptime(" ".join(s.replace(",", ", ").split()), "%B %d, %Y").date().isoformat()


def pdf_text(year):
    """Cached PDF -> pdftotext -layout text (text kept in memory only)."""
    path = PDF_DIR / f"list_{year}.pdf"
    if not path.exists():
        PDF_DIR.mkdir(parents=True, exist_ok=True)
        r = requests.get(LISTS[year], headers={"User-Agent": "Mozilla/5.0"}, timeout=60)
        r.raise_for_status()
        path.write_bytes(r.content)
    return subprocess.run([PDFTOTEXT, "-layout", str(path), "-"], capture_output=True, text=True, check=True).stdout


def notice_dates(text):
    """(power_to_sell_since, redemption_as_of) read from the notice body (the left column, before any NO. row)."""
    body = " ".join(ROW_START.split(line)[0] for line in text.splitlines())
    body = " ".join(body.split())
    since = re.search(r"power to sell on " + DATE, body)
    as_of = re.search(r"parcel numbers as of " + DATE, body)
    return (_iso(since.group(1)) if since else None), (_iso(as_of.group(1)) if as_of else None)


def parse_rows(text):
    """Every 'NO.### APN ...' segment -> {apn, situs, amount}. The assessee name is never extracted.

    pdftotext lays several table columns side by side, so a line holds up to three rows; each row runs from its
    NO.### marker to the next one. The amount is the first $ figure in the segment; anything after it is notice
    text from the neighbouring column and is dropped unread.
    """
    rows = []
    for line in text.splitlines():
        starts = list(ROW_START.finditer(line))
        for i, m in enumerate(starts):
            seg = line[m.end(): starts[i + 1].start() if i + 1 < len(starts) else len(line)]
            a = APN.match(seg)
            if not a:
                continue
            amt = AMOUNT.search(seg)
            head = seg[: amt.start()] if amt else seg  # name + location; inspected for one phrase only
            rows.append({"apn": a.group(1),
                         "situs": "ADDRESS NOT AVAILABLE" not in head.upper(),
                         "amount": float(amt.group(1).replace(",", "")) if amt else None})
            del head, seg
    return rows


def build_leads(texts):
    """texts: {year: pdftotext output}. Newest list wins for amount/as-of/source; earliest date wins for since."""
    leads, counts = {}, {}
    for year in sorted(texts, reverse=True):
        since, as_of = notice_dates(texts[year])
        rows = parse_rows(texts[year])
        kept = [r for r in rows if r["apn"][:3] not in TIMESHARE_BOOKS]
        counts[year] = {"rows": len(rows), "timeshare_dropped": len(rows) - len(kept), "kept": len(kept)}
        for r in kept:
            k = digits(r["apn"])
            cur = leads.get(k)
            if cur is None:
                leads[k] = {"type": "tax_default_chapter8", "power_to_sell_since": since, "years_on_list": [year],
                            "redemption_amount": r["amount"], "redemption_as_of": as_of,
                            "situs_address_on_notice": r["situs"], "timeshare": False, "source": SOURCE,
                            "source_url": LISTS[year], "checked": CHECKED, "note": NOTE}
            else:
                if year not in cur["years_on_list"]:
                    cur["years_on_list"].append(year)
                if since and (cur["power_to_sell_since"] is None or since < cur["power_to_sell_since"]):
                    cur["power_to_sell_since"] = since
                if cur["redemption_amount"] is None and r["amount"] is not None:
                    cur["redemption_amount"], cur["redemption_as_of"] = r["amount"], as_of
                cur["situs_address_on_notice"] = cur["situs_address_on_notice"] or r["situs"]
    for v in leads.values():
        v["years_on_list"].sort()
    return leads, counts


def d1_apns():
    """APN digits of the cached D1 (SCAG zoning) parcels, i.e. the city the build was run for."""
    out = set()
    for p in (RAW / "zoning").glob("*.json"):
        for f in json.loads(p.read_text()).get("features", []):
            out.add(digits(f["attributes"].get("APN24")))
    out.discard("")
    return out


def _query_one(apn_disp, tries=4, wait=4.0):
    last = None
    for i in range(tries):
        try:
            r = requests.get(TTC_MAP + "/query", params={"where": f"AssessmentNo='{apn_disp}'", "outFields": TTC_FIELDS,
                                                       "returnGeometry": "false", "f": "json"}, timeout=40)
            r.raise_for_status()
            d = r.json()
            if "error" in d:
                raise RuntimeError(str(d["error"])[:120])
            return [{k: f["attributes"].get(k) for k in TTC_FIELDS.split(",")} for f in d.get("features", [])]
        except (requests.RequestException, ValueError, RuntimeError) as e:
            last = e
            if i < tries - 1:
                time.sleep(wait)
    raise RuntimeError(f"D15 {apn_disp} failed after {tries} tries: {str(last)[:120]}")


def status_from_rows(rows):
    """D15 rows (requested fields only) -> status object. No row -> found False (UNKNOWN downstream)."""
    base = {"queried": True, "checked": CHECKED, "source": TTC_MAP, "note": TTC_NOTE}
    if not rows:
        return dict(base, found=False, delinquent=None, tax_current_year=None, assessed_land=None,
                    assessed_improvement=None, assessed_total=None, county_use_code=None, bill_url=None)
    a = rows[0]
    return dict(base, found=True, delinquent=1 if a.get("Delinquent") == 1 else None, tax_current_year=a.get("ta"),
                assessed_land=a.get("alv"), assessed_improvement=a.get("aiv"), assessed_total=a.get("tav"),
                county_use_code=(a.get("UseDqLanduse") or "").strip() or None, bill_url=a.get("ViewPayBill"))


def status(apns, sleep=0.5):
    """{apn_digits: status}. One APN per request, cached at data/raw/ttc_status/<apn>.json (only the requested
    fields). A query that fails after retries returns {"queried": False}; it is not cached so a re-run retries."""
    STATUS_DIR.mkdir(parents=True, exist_ok=True)
    out = {}
    for apn in apns:
        path = STATUS_DIR / f"{apn}.json"
        if path.exists():
            rows = json.loads(path.read_text())["rows"]
        else:
            disp = f"{apn[:3]}-{apn[3:6]}-{apn[6:]}"
            try:
                rows = _query_one(disp)
            except RuntimeError as e:
                print(f"  {e}")
                out[apn] = {"queried": False, "checked": CHECKED, "source": TTC_MAP}
                continue
            path.write_text(json.dumps({"apn": disp, "fetched": datetime.now().isoformat(timespec="seconds"), "rows": rows}))
            time.sleep(sleep)
        out[apn] = status_from_rows(rows)
    return out


def main():
    texts = {y: pdf_text(y) for y in LISTS}
    leads, counts = build_leads(texts)
    for y, c in counts.items():
        print(f"D14 {y}: {c['rows']} rows, {c['timeshare_dropped']} timeshare dropped, {c['kept']} kept")
    city = d1_apns()
    joined = sorted(k for k in leads if k in city)
    print(f"D14 {len(leads)} distinct non-timeshare APNs, {len(joined)} join to a cached D1 parcel")
    st = status(joined)
    for k in joined:
        leads[k]["status"] = st[k]
    ok = sum(1 for s in st.values() if s.get("queried"))
    print(f"D15 answered {ok}/{len(joined)}")
    print("APN          years       Delinq  land_value  redemption")
    for k in joined:
        s, l = leads[k]["status"], leads[k]
        print(f"{k[:3]}-{k[3:6]}-{k[6:]}  {','.join(map(str, l['years_on_list'])):<10}  {str(s.get('delinquent')):<6}  "
              f"{s.get('assessed_land')!s:<10}  {l['redemption_amount']}")
    OUT.write_text(json.dumps(leads, indent=1))
    print(f"-> {OUT}")
    return leads


if __name__ == "__main__":
    main()
