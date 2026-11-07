# D14: tax-default acquisition lead (Chapter 8) — build guide for the pipeline agent

Read `CLAUDE.md` and `docs/BUILD-SPEC.md` first. This document adds two data layers (D14 the county's annual Power-to-Sell list, D15 the county tax map's live delinquency flag) and one lead type. It does not add a legal pathway and it changes no existing test. Budget: 60–90 minutes. Folder ownership stands: pipeline agent edits `pipeline/`, `data/`, `tests/`; UI agent edits `api/`, `web/`. The UI section at the end is for the UI agent.

## 1. What this is, in one paragraph

Every June the Orange County Treasurer-Tax Collector publishes the "Notice of Power and Intent to Sell Tax-Defaulted Property": every parcel that has been tax-defaulted for five or more years and so becomes subject to the county's power to sell on July 1. California lets a nonprofit buy such a parcel directly from the county (Revenue and Taxation Code 3791.4, a "Chapter 8 agreement sale") and lets it block the public auction by filing an objection before the auction notice is published (RTC 3695.5). Habitat is the textbook buyer: for vacant land the statute requires the nonprofit to build housing for low-income households or dedicate it to public use. Nobody in OC is using this for housing. We join that list to our Santa Ana parcels and surface each hit as an **acquisition lead** next to the SB 4 owner lead. The county already prints Habitat's call list once a year; Site Scout picks it up.

## 2. Source (D14)

| | |
|---|---|
| Publisher | Orange County Treasurer-Tax Collector (TTC) |
| Document | Notice of Power and Intent to Sell Tax-Defaulted Property, RTC 3361–3362, published on or before June 8 |
| 2025 list (current) | `https://www.octreasurer.gov/sites/ttc/files/2025-06/Impending%20Power%20to%20Sell%20-%20June%208.pdf` (the filename says "Impending" but the body is the Power and Intent to Sell list; the sibling file `Notice%20of%20Impending%20Power%20to%20Sell%20-%20June%208.pdf` is the legal notice with **no parcels**, do not use it) |
| 2024 list | `https://www.octreasurer.gov/sites/ttc/files/2024-09/Notice%20of%20Power%20and%20Intent%20to%20Sell%20Tax-Defaulted%20Property%20June%202024.pdf` |
| Index page | `https://octreasurer.gov/taxdefaultedproperty` (returns 403 to scripts; open in a browser to find next year's file) |
| Format | One-page PDF, multi-column table: `NO.### APN  ASSESSEE NAME  PROPERTY LOCATION  $REDEMPTION` |
| Rows 2025 | 234 total, 92 San Clemente timeshare intervals (APN books 898, 899, 916), 142 others, 15 with a Santa Ana situs, 12 non-timeshare rows with `ADDRESS NOT AVAILABLE` |
| Rows 2024 | 151 total, 77 timeshares, 49 standard parcels, 5 Santa Ana |
| Also useful | Auction notice (late May, `.../2025-06/Notice%20of%20Public%20Auction%20Final%20-%20June%2025.pdf`): same columns plus minimum bid. A parcel on it has **left** the Chapter 8 window for that year. Three-year list (September 8, `Property%20Tax%20Delinquency%203%20years%20-%202025.pdf`): parcels where the county's mail came back undeliverable; mostly timeshares; optional second signal |

Parsing: `pdftotext -layout` works (poppler is on the dev Mac; `brew install poppler`). If you add a Python dependency instead, use `pypdf` and pin it in `requirements.txt`. The regex below parsed all 234 rows of the 2025 file and all 133 readable rows of the 2024 file:

```python
ROW = re.compile(r'(\d{3}-\d{3}-\d{2})\s+(.*?)\s{2,}(\S.*?)\s{2,}(\$[\d,]+\.\d{2})')
# groups: apn_display, assessee (DISCARD), property_location, redemption_amount
```

## 3. Privacy rule (non-negotiable)

`CLAUDE.md`: no owner names, no personal information anywhere. The assessee column is a person's name in most rows. **Discard group 2 at parse time and never write it to disk, logs or JSON**, exactly as `pipeline/proxies.py` drops the IRS `ICO` column. Keep: APN, whether a situs address exists, the redemption amount, the list year. Cache the PDF under `data/raw/ttc/` (gitignored). Add a test that asserts no key or value in `data/tax_default_leads.json` contains a comma-separated surname pattern or the string "TR" followed by a name; simplest is to assert the allowed key set exactly.

## 4. Pipeline changes

### 4a. New module `pipeline/taxdefault.py`

Mirror `pipeline/proxies.py`. Standalone: `python -m pipeline.taxdefault` writes `data/tax_default_leads.json`. Not wired into `build.py`'s network path; `build.py` only loads the JSON if present (same pattern as `load_owner_leads`).

```python
"""D14 tax-default acquisition lead: OC TTC Power-to-Sell list -> APN -> Chapter 8 eligibility.
Assessee names are discarded while parsing each row and never stored."""
LISTS = {  # year the parcel became subject to the power to sell -> PDF
    2025: "https://www.octreasurer.gov/sites/ttc/files/2025-06/Impending%20Power%20to%20Sell%20-%20June%208.pdf",
    2024: "https://www.octreasurer.gov/sites/ttc/files/2024-09/Notice%20of%20Power%20and%20Intent%20to%20Sell%20Tax-Defaulted%20Property%20June%202024.pdf",
}
TIMESHARE_BOOKS = {"898", "899", "916"}
SOURCE = "OC Treasurer-Tax Collector, Notice of Power and Intent to Sell Tax-Defaulted Property (RTC 3361-3362)"
```

Output shape, keyed by APN digits (use `fetch.digits`):

```json
{
  "40024225": {
    "type": "tax_default_chapter8",
    "power_to_sell_since": "2024-07-02",
    "years_on_list": [2024, 2025],
    "redemption_amount": 20043.40,
    "redemption_as_of": "2025-07-01",
    "situs_address_on_notice": true,
    "timeshare": false,
    "source": "OC Treasurer-Tax Collector, Notice of Power and Intent to Sell Tax-Defaulted Property (RTC 3361-3362)",
    "source_url": "https://www.octreasurer.gov/sites/ttc/files/2025-06/Impending%20Power%20to%20Sell%20-%20June%208.pdf",
    "checked": "2026-11-07",
    "note": "LEAD from a public county notice; redemption may have occurred since publication. Confirm current status at TaxBill.octreasurer.gov by APN."
  }
}
```

Rules while building it:
- Parse every list in `LISTS`, newest first. A parcel on both keeps the earliest `power_to_sell_since` and lists both years. Date = July 1 of the list year for 2025, July 2 for 2024 (both dates are in the notice text; read it from the PDF rather than hard-coding if you have time).
- Drop timeshare books entirely. Keep condo and mobile-home books (93x); they will be excluded by zoning or size downstream and are honest data.
- Do not filter by the city text in the location column. The join to D1 parcels is what restricts to Santa Ana; the county's location field spells cities inconsistently.
- `redemption_amount` is a float, parsed from the `$` column. Store `redemption_as_of` from the notice ("as of July 1, 2025").

### 4b. `pipeline/build.py`

- Add `D14` to `URLS`/`NAMES` as a non-ArcGIS source: name `"OC TTC Power-to-Sell list (PDF)"`, url the 2025 PDF. `step()` is ArcGIS-shaped, so record it the way `load_owner_leads` does: status `ok` with row count when the JSON exists, `not run` otherwise.
- `load_tax_default_leads()` next to `load_owner_leads()`; `f["tax_default"] = tax_leads.get(p["apn"])` in the parcel loop, **before** `excluded()` and `score()`. The join must happen in the full 42k-parcel loop, not after the top-1000 cut. None of the 2024 Santa Ana APNs are in today's `candidates.json`; that is the point.
- Site object: add `"acquisition_lead": f["tax_default"]` beside `"owner_lead"`. Keep `owner_lead` unchanged so the UI does not break before the UI agent lands.
- `who_to_call`: when `f["tax_default"]`, prepend  
  `{"who": "OC Treasurer-Tax Collector, Tax-Defaulted Property / Tax Auction unit", "why": "parcel is on the county's Power-to-Sell list; ask about a Chapter 8 agreement sale and the Section 3695.5 objection deadline for the next auction", "contact": "(714) 834-3411, TaxAuction@octreasurer.gov (public contacts on the notice)"}`  
  and `{"who": "Habitat OC Land Bank Reserve (internal)", "why": "decide whether to file a nonprofit objection and application before the auction notice is published (late May)", "contact": "internal"}`.
- `meta.notes`: add `f"acquisition_lead (D14 OC TTC Power-to-Sell 2024+2025): {n} Santa Ana parcels on the list, {m} in the ranked output"`.
- Rebuild runs offline from `data/raw/`; the only new network call is the PDF download inside `taxdefault.py`.

### 4c. `pipeline/rules.py`

Do **not** add a statutory pathway. Chapter 8 is an acquisition route, not a zoning entitlement, and `best_pathway` must stay about SB 9 / SB 684 / AB 2011 / SB 4. Add one informational block the card can render, built the same way as `sb79()`:

```python
CH8_RTC_3791_4 = "https://california.public.law/codes/ca_rev_and_tax_code_section_3791.4"
CH8_RTC_3695_5 = "https://california.public.law/codes/ca_rev_and_tax_code_section_3695.5"
AB418 = "https://legiscan.com/CA/bill/AB418/2172"

def chapter8(f):
    """Acquisition lead, not a pathway. Never FAIL on absence: no lead -> UNKNOWN."""
    td = f.get("tax_default")
    if not td:
        return {"id": "CH8", "name": "Chapter 8 tax-default acquisition (lead)", "status": "UNKNOWN", "yield": None,
                "tests": [t("ch8.on_list", "On the county Power-to-Sell list (5+ years tax-defaulted)", "UNKNOWN",
                            "APN not on the 2024 or 2025 OC TTC notice; absence is not evidence", CH8_RTC_3791_4)]}
    tests = [
        t("ch8.on_list", "On the county Power-to-Sell list (5+ years tax-defaulted)", "PASS",
          f"subject to the Tax Collector's power to sell since {td['power_to_sell_since']}; redemption ${td['redemption_amount']:,.0f} as of {td['redemption_as_of']}", td["source_url"]),
        t("ch8.vacant_or_substandard", "Vacant land (nonprofit must build low-income housing) or substandard residence (must rehabilitate)",
          "PASS" if codes.lu_family(f["lu"]) == "vacant" else "FLAG",
          "vacant per SCAG 2024 land use" if codes.lu_family(f["lu"]) == "vacant" else f"existing use {codes.lu_label(f['lu'])}: residential property qualifies only if substandard; confirm", CH8_RTC_3791_4),
        t("ch8.objection_window", "Nonprofit objection filed before the auction notice is first published", "UNKNOWN",
          "OC publishes the auction notice in late May for a June sale; file the RTC 3695.5 objection and purchase application before then. Not on the June 2025 auction list.", CH8_RTC_3695_5),
        t("ch8.board_hearing", "Board of Supervisors hearing and price finding (AB 418, from 2026)", "UNKNOWN",
          "price must be at least the parcel's tax-sale value, or tax-sale value below the redemption amount; hearing costs paid by the nonprofit", AB418),
        _ch8_status(f),  # D15 live check, see 4h
    ]
    return {"id": "CH8", "name": "Chapter 8 tax-default acquisition (lead)", "status": "FLAG", "yield": None, "tests": tests}
```

```python
TTC_MAP = "https://www.ocgis.com/arcpub/rest/services/Treasurer_Tax_Collector/TTC_Final/MapServer/0"

def _ch8_status(f):
    """D15: county tax-map Delinquent flag. Data test: None -> UNKNOWN, 1 -> PASS (still delinquent), else FAIL (cleared)."""
    s = f.get("tax_status")
    if s is None or s.get("delinquent") is None and not s.get("queried"):
        return t("ch8.current_status", "Still delinquent on the county tax map", "UNKNOWN",
                 "OC Treasurer tax-map layer not queried or unavailable; check TaxBill.octreasurer.gov by APN", TTC_MAP)
    if s["delinquent"] == 1:
        return t("ch8.current_status", "Still delinquent on the county tax map", "PASS",
                 f"Delinquent=1 on the county's secured-tax map layer (checked {s['checked']}; county says data is not real-time). "
                 "Bankruptcy stay and payment-plan status still unknown", TTC_MAP)
    return t("ch8.current_status", "Still delinquent on the county tax map", "FAIL",
             f"no delinquency flag on the county's secured-tax map layer (checked {s['checked']}): likely redeemed or sold since the notice", TTC_MAP)
```

A `FAIL` here should drop the lead from scoring (`acquisition_lead` becomes `None` in `build.py` but the CH8 block still renders so the user sees why). Add `"ch8.objection_window", "ch8.board_hearing"` to `CONFIRM` so they count as human-confirm items; `ch8.current_status` stays a data test. Append `chapter8(f)` to `paths` in `evaluate()` **after** the `sb79(f), he(f)` line, so `STATUTORY` and `best_pathway` are untouched. Statutes: do not paraphrase thresholds you have not read. The three URLs above were read on 2026-11-07; the five-year rule, the three-year rule with a nuisance-abatement lien, and the AB 418 hearing requirement are in those texts.

### 4d. `pipeline/score.py`

Keep the weights summing to 100. Make the existing 15-point `owner_lead` bucket mean "any acquisition lead": awarded when either the SB 4 proxy or the tax-default lead is present. Rename nothing in the JSON (`score_breakdown.owner_lead` stays, the UI reads it). Change the signature to `score(f, hz, paths, owner_lead=None, acquisition_lead=None)` and `excluded(f, he_listed=False, owner_lead=False, acquisition_lead=False)`; a tax-default lead, like an owner lead, keeps an industrial/open-space-zoned parcel in the ranked list. Add a comment: `# ASSUMPTION: a county-listed tax-defaulted parcel is as strong a lead as a faith-owner proxy`. Update `WEIGHTS` label text if you surface it.

### 4e. `pipeline/lookup.py`

Mirror `build.py`: load `tax_default_leads.json` into the lookup context, set `f["tax_default"]`, pass it to `score`, include `acquisition_lead` in the returned site. The live path is how the demo pastes a real listed address.

### 4f. Tests (`tests/test_taxdefault.py`, `tests/test_rules.py`)

- Parse a **synthetic** fixture string (made-up APNs like `000-000-01`, made-up names like `DOE, JANE TR`, `ADDRESS NOT AVAILABLE`, `$1,234.56`) and assert: row count, timeshare book dropped, `situs_address_on_notice` false for `ADDRESS NOT AVAILABLE`, amount parsed, and **the set of keys of every lead equals the documented key set** (this is the no-names test).
- `chapter8(facts())` with no lead -> status `UNKNOWN`, one test, never `FAIL`.
- `chapter8(facts(tax_default=..., lu="1900"))` -> status `FLAG`, `ch8.vacant_or_substandard` PASS.
- `score(... acquisition_lead=lead)` awards 15 under `owner_lead` and total still ≤ 100; `excluded()` keeps an `M1` parcel with a lead.
- Existing `test_sb4_owner_proxy_never_fails` and breakdown test must still pass unchanged.

### 4g. Smoke check after `python -m pipeline.build --city "Santa Ana"`

Santa Ana APNs on the 2024 notice (digits): `39627104 40024225 40510504 41106333 50224108`. On the 2025 notice the Santa Ana-situs rows include `40025103 40531251 40809416 40024225 41106333 01015106`. Two APNs appear on both years (`40024225`, `41106333`), which is itself a signal: subject to sale since July 2024 and still not auctioned in June 2025. Checked against the cached D1 layer on 2026-11-07: 8 of those 9 APNs are Santa Ana parcels (`50224108` is unincorporated North Tustin with a Santa Ana mailing city, so the join correctly drops it). Among the 8: `41106333` is zoned M1 (0.39 ac), which is why `excluded()` must let a lead keep an industrial-zoned parcel; `40025103` is C5 (0.49 ac), an AB 2011 candidate; the rest are R1 lots of 0.14–0.18 ac. Expect roughly 10–15 Santa Ana parcels to carry the lead; several will be improved single-family lots that FLAG on `ch8.vacant_or_substandard`. At least a few should now enter the top 1,000. Print how many did in `meta.notes`. If zero join, check `digits()` normalisation on both sides before anything else.

### 4h. D15: live status check against the county tax map (removes the manual step)

The county's own tax map (`ocgov.com/octaxmap`) is an ArcGIS web map backed by a public OC GIS service. It is the same host family as D4–D6 and D9, so it is inside the "public endpoints only" rule.

| | |
|---|---|
| Service | `https://www.ocgis.com/arcpub/rest/services/Treasurer_Tax_Collector/TTC_Final/MapServer` |
| Layer 0 | `Landbase.GIS.Secured_Property_Tax_Information`, titled "2026-2027 Secured Property Tax Information" in the web map (`arcgis.com` item `765630ac3daf403c867461d5e904f907`) |
| Query | `.../MapServer/0/query?where=AssessmentNo='400-242-25'&outFields=AssessmentNo,Delinquent,ta,alv,aiv,tav,UseDqLanduse,ViewPayBill&returnGeometry=false&f=json` |
| Fields to use | `Delinquent` (Integer: `1` or null), `ta` (current-year tax), `alv` / `aiv` / `tav` (assessed land / improvement / total value), `UseDqLanduse` (county use code, 4 chars), `ViewPayBill` (deep link to the bill) |
| Fields to **never request** | `Name` (assessee), `situs` is fine but redundant with D9 |
| Behaviour | Slow and flaky: a single-APN query returns in 1–20 s, `IN (...)` lists and `returnDistinctValues` / countywide counts time out with HTTP 503 "Wait timeout". Query **one APN at a time, only for parcels that carry a D14 lead** (about 15), with `--retry`-style backoff (4 tries, 4 s apart). Cache under `data/raw/ttc_status/<apn>.json` like every other layer. Never run it over the 42k parcels |
| Disclaimer | County: data "is not real-time", "as is", confirm with the County office before business decisions. The ocgov.com use policy marks site content public domain and forbids only activity that degrades the portal. Fifteen single-row queries is fine; a bulk pull is not |
| Semantics (ASSUMPTION) | `Delinquent=1` means the parcel carries delinquent secured taxes on the roll the map was built from. It does **not** by itself mean "subject to power to sell"; a parcel on a five-year payment plan can still show 1, and a parcel redeemed after the map's build date may still show 1. Label it exactly that way |

Validation run on 2026-11-07 against the D14 Santa Ana APNs (names not requested):

| APN | On notice | `Delinquent` | Read |
|---|---|---|---|
| 400-242-25 | 2024 and 2025 | 1 | still delinquent, lead stands |
| 411-063-33 | 2024 and 2025 | 1 | still delinquent, lead stands |
| 405-105-04 | 2024 | 1 | still delinquent |
| 396-271-04 | 2024 only | 1 | delinquent but off the 2025 list: likely on a payment plan |
| 405-312-51, 408-094-16 | 2025 | 1 | still delinquent |
| 400-251-03 | 2025 | null | cleared since June: drop |
| 010-151-06 | 2025 | null | cleared since June: drop |
| 002-162-29, 008-091-03 | June 2025 auction list | 1 | still flagged after the auction: either unsold or the map predates the sale. This is why the flag is an ASSUMPTION |
| 007-203-24 (control, church lot) | none | null, all tax fields null | exempt parcel, behaves as expected |

Implementation:
- `pipeline/taxdefault.py` gets a second entry point `status(apns) -> {apn: {"delinquent": 1|None, "tax_current_year": ta, "assessed_land": alv, "assessed_improvement": aiv, "assessed_total": tav, "county_use_code": UseDqLanduse, "bill_url": ViewPayBill, "queried": True, "checked": CHECKED, "source": TTC_MAP}}`. Run it after the D14 parse for the APNs that joined to a D1 parcel. Write the result into the same `tax_default_leads.json` under a `status` key so `build.py` needs no second file. A query that fails after retries writes `{"queried": False}` so the rule reports UNKNOWN, never a silent pass.
- `build.py`: `f["tax_status"] = (f["tax_default"] or {}).get("status")`. If `ch8.current_status` is FAIL, set `acquisition_lead = None` for scoring but keep the CH8 block.
- Two extra signals come free with the row and belong on the card and in the export, both labelled ASSUMPTION:
  - **Donation-likelihood ratio** = redemption amount ÷ assessed land value. 400-242-25: $20,043 ÷ $222,997 ≈ 9%. 411-063-33: $59,075 ÷ $1,078,893 ≈ 5%. A low ratio means the owner has equity and is disengaged rather than cash-trapped, which is the bargain-sale donation profile from the research note. Show the ratio, not a verdict.
  - **Lane 3 land hint** = assessed land value `alv`. Prop 13 keeps it below market, so it is a floor. Replace the current `"ASSUMPTION: no price data"` export hint with `"ASSUMPTION: county assessed land value $X (Prop 13 floor, not market); redemption $Y as of DATE"` whenever `alv` is present. This is the first real number Lane 3 gets from Lane 1.
- Add `D15` to the sources list with status `ok` / `partial` (n of m APNs answered) / `failed`, `affects: ["ch8.current_status"]`.
- Test: a fake `status()` response with `delinquent=1`, `None` after a query, and `queried=False` must map to PASS, FAIL, UNKNOWN respectively.
- Optional, if time remains: query D15 for the `--address-top` parcels too. `alv` for the top 300 gives every exported site a land-value floor, and any unexpected `Delinquent=1` among them is a lead the notice has not reached yet (fewer than five years). Keep it to the top 300 and respect the one-at-a-time rule.

## 5. API and UI (UI agent)

- `api/main.py` `list_row`: add `acquisition_lead: bool`. `/api/sites?pathway=CH8` should match sites whose `acquisition_lead` is non-null (same way `pathway=HE` matches `housing_element.listed`).
- Export `for_lane_3`: when a lead exists, `"land_line_hint": "ASSUMPTION: AB 418 requires price >= tax-sale value; county redemption amount $X (as of DATE) is the floor, not the price"`. Keep the existing hint otherwise.
- `web/app.js`: list chip `tax lead ◆` (new class, distinct from `owner lead ★`); `whyLine` adds "county tax-default lead"; card gets a section **Acquisition lead** above Owner lead:  
  "On the county Power-to-Sell list since 2024-07-02 · redemption $20,043 as of 2025-07-01 · Chapter 8 eligible for a nonprofit · objection due before the late-May auction notice · AB 418 board hearing required · **LEAD, confirm current status by APN**" with the notice link and the two statute links. Render the CH8 block in the pathways list in grey as informational (status FLAG), not as a chip in the SB strip.
- Sources panel: D14 row, `affects: ["ch8.on_list"]`, note "annual snapshot, names discarded at parse".
- Never show a name. The JSON carries none; do not add one from any other source.

## 6. Demo and docs

- `docs/demo-script.md`, 3-minute finals, insert after step 3: "Filter to tax leads. These parcels have been tax-defaulted five years; state law lets Habitat stop the auction and buy direct. The county prints this list every June. Nobody has picked it up." (15 s)
- `docs/DECISIONS.md`, Pipeline section: record the two PDF URLs, row counts, the timeshare-book filter, the names-discarded rule, the decision to share the 15-point lead bucket, and that CH8 is informational not statutory.
- README "what is real / what is mocked": D14 real, parsed from the county PDF; status at call time not verified.

## 7. Cut list, in order

If time runs short: (1) skip the 2024 list, parse 2025 only; (2) skip the optional top-300 D15 pass; (3) skip `lookup.py`; (4) skip the CH8 block and keep only the lead + D15 status + score + card section; (5) skip the UI filter. Never cut: names discarded at parse, the D15 status check for leads (it is the difference between a list and a call list), source URL and checked date on the lead, the "county data is not real-time" note.

## 8. Legal references read on 2026-11-07

- RTC 3791.4 (nonprofit purchase, 5 years or 3 years with nuisance-abatement lien, use obligations): `https://california.public.law/codes/ca_rev_and_tax_code_section_3791.4`
- RTC 3695.5 (nonprofit objection before first publication of the auction notice stops the sale): `https://california.public.law/codes/ca_rev_and_tax_code_section_3695.5`
- AB 418, Chapter 149 Statutes of 2025 (board hearing, price at least tax-sale value, costs to purchaser): `https://legiscan.com/CA/bill/AB418/2172`
- LA County's Chapter 8 program as the operating model (portal shares parcel lists with registered nonprofits): `https://ttc.lacounty.gov/chapter-8-agreement-sale/`
- OC TTC auction page (three "Sale by Agreement" results, 2016–2017, none to a nonprofit): `https://octreasurer.gov/taxauction`

Not legal advice. Every statement on the card about Chapter 8 must carry one of these URLs.
