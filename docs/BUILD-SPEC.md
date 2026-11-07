# Site Scout: build spec, PRD and design

**Project:** Site Scout — "Ten sites to call this month" for Habitat for Humanity of Orange County
**Repo:** https://github.com/halapati3547/GIS4All (public, default branch `main`; judges read `main` at 2:30 PM)
**Event:** Claude Impact Lab, UCI × SoCal Affordable Housing, November 7, 2026. Lane 1, Find it.
**Deadline:** code on `main` and video submitted by **2:30 PM**. Finalists demo live at 3:00 PM.
**This document is the brief for the building agent.** Read all of it before writing code, then follow the build order in section 10. Work autonomously. When something is ambiguous, pick the option that ships, write the choice in `docs/DECISIONS.md`, and keep going. Stop only when blocked on a secret.

---

## 1. PRD

### 1.1 Problem

Habitat OC must put 100 homes in its pipeline within three years, about five times its historic pace. Land is the largest line on every home's bill (about $360k of $535k in the organizers' worked example). Today Habitat finds sites by luck: a city calls about surplus land, or a congregation offers a parking lot. California has passed laws that open land by right (SB 9, SB 684/1123, AB 2011, SB 4, SB 79), and the parcel, zoning, hazard and land-use data are public. Nobody has joined the laws to the parcels for Orange County in a form a one-person acquisitions team can use.

### 1.2 The real user

**Role:** the acquisitions / real estate development lead at Habitat OC. One person, no GIS team. (A role, not a named person. Never put a real person's name in the repo.)

**Before:** waits for the phone to ring. Evaluates one offered site at a time, by hand, over weeks: pulls zoning from the city site, checks FEMA, calls planning to ask which law applies, and still does not know whether the owner would sell.

**After:** opens Site Scout, picks Santa Ana, and sees a ranked list of parcels where 2 to 12 affordable ownership homes could go by right. Each site shows which legal tests passed, failed or could not be checked, with the source and the date checked, who to call, and a plain-English brief. Pastes an address a congregation just emailed and gets the same card for that one parcel in ten seconds.

### 1.3 What it does (scope for today)

1. **Ranked list for one city (Santa Ana).** Parcels scored for a 2 to 12 home affordable ownership project, with the pathway that opens each one.
2. **Site card.** For any parcel: pathway tests as PASS / FAIL / UNKNOWN with source links and dates, hazard screen, current use, housing-element status, surplus-land history, owner-type lead (proxy, labelled), and who to call.
3. **Check one address.** Type an address, get the card. Serves the congregation scenario and the "real public case" judges ask for.
4. **Claude brief.** Claude explains the card in plain English, lists what a human must confirm, and drafts (never sends) a first call script. Claude never produces a number or a legal conclusion; the rule engine does.
5. **Export.** Each site exports as JSON with the fields a Lane 2 (time) or Lane 3 (money) tool would need. This answers the organizers' closing question about combining tools.

### 1.4 Out of scope today

Owner names. Any other city (the pipeline is parameterised by city; say "Anaheim is a parameter change" in the demo, do not build it). Slope analysis beyond the SCAG `SLOPE` field. Utility capacity. Contamination. Sending email or filing anything. Logins.

### 1.5 Success criteria (map to judging)

| Judge area | What must be true at 2:30 |
|---|---|
| Impact | The demo opens on the acquisitions lead's before/after and ends with "ten sites to call this month" on screen |
| Works | Every site on screen is a real Santa Ana APN from live public layers, with the source URL and "checked 2026-11-07" on the card. Every assumed weight or threshold is labelled ASSUMPTION |
| Scale | `python pipeline/build.py --city "Santa Ana"` is the whole pipeline; the README shows the one-line command for another city and says which layers cover all 34 OC cities |
| Innovation | Faith-land proxy (worship sites + IRS exempt orgs → parcels) and SB 79 transit flag, neither of which exists for OC |

### 1.6 Ground rules that apply (from the event)

- Public or provided data only. Cache every download once. Never scrape city websites (several return 403; the rule is stop). All sources here are county, SCAG, state or federal endpoints that allow it.
- No personal information. The OC parcel layer has no owner names; do not add any. The IRS file has an "in care of" person name column: drop it on load. Organisation names are fine.
- Prototype only. Draft the call script, never send it. Show "Not legal or financial advice" on every card.
- Never invent a statute number, threshold or fee. If a test has no data layer, the answer is UNKNOWN with a one-line reason.
- No API keys in the repo. `.env.example` only.

---

## 2. Architecture

```
                 ┌──────────────── pipeline/build.py (Python, run once, cached) ────────────────┐
                 │                                                                              │
  SCAG zoning ───┤  fetch → normalise APN → join layers → hazard PIP → proxies → rule engine   │
  SCAG land use ─┤  → score → data/candidates.json  +  data/raw/*.json (cache)                  │
  SCAG HE sites ─┤                                                                              │
  OC hazards ────┤                                                                              │
  HQTA / stops ──┤                                                                              │
  IRS BMF + OSM ─┤                                                                              │
  NOA CSV ───────┘                                                                              │
                                                     │
                                                     ▼
            ┌──────────────── api/ (FastAPI, uvicorn) ────────────────┐
            │ GET /api/sites?city&limit&pathway&minSf&maxSf&heOnly    │
            │ GET /api/sites/{apn}                                    │
            │ GET /api/lookup?address=…  (Census geocoder → OC parcel │
            │     point query → SCAG by APN → rule engine live)       │
            │ POST /api/explain {apn}  → Claude (cached per APN)      │
            │ GET /api/sites/{apn}/export.json                        │
            └─────────────────────────────────────────────────────────┘
                                                     │
                                                     ▼
            web/index.html + app.js + styles.css (vanilla JS, Leaflet via CDN, served by FastAPI static)
```

**Stack:** Python 3.11+, `requests`, `fastapi`, `uvicorn`, `anthropic`, `python-dotenv`. No geopandas, no shapely (install risk on a hall network). Point-in-polygon is a 20-line ray-cast in `pipeline/geo.py` with a bbox pre-check. Frontend is vanilla so there is no build step. Pin versions in `requirements.txt`.

**Claude model:** `claude-sonnet-5-5` for explanations (fast, cheap). Read the key from `APP_ANTHROPIC_API_KEY`. `MOCK_CLAUDE=1` returns templated text so the demo survives a dead network.

---

## 3. Data sources (all verified Nov 6 by organizers; endpoints re-tested Nov 7 10:20 AM)

| # | Layer | Endpoint | Fields used | Notes |
|---|---|---|---|---|
| D1 | SCAG Zoning by parcel | `https://maps.scag.ca.gov/scaggis/rest/services/LDX/Zoning_poly_OR/MapServer/0/query` | `APN24, CITY, ZN24_CITY, ZN24_SCAG, ACRES, SLOPE` + centroid | `where=CITY='Santa Ana'` → 42,896 rows. Max 2,000 per call: page with `resultOffset`. Use `returnGeometry=false&returnCentroid=true`; if centroid unsupported, `returnGeometry=true&geometryPrecision=5&outSR=4326` and compute centroid |
| D2 | SCAG Existing land use | `…/LDX/Existinglanduse_poly_OR/MapServer/0/query` | `APN24, LU24, LU24_2ND` | Same paging. **Read the layer's field domain / metadata for LU24 code meanings before using them; do not assume.** Expect families: 1xxx residential, 2xxx commercial/services, 3xxx industrial, 6xxx vacant, 8xxx open space. Find the codes for vacant, surface parking and religious facilities from the domain and record them in `pipeline/codes.py` with the URL you read |
| D3 | SCAG Housing Element sites | `…/LDX/HousingElementSite_poly_scag/MapServer/0/query` | `Assessor_Parcel_Number, Jurisdiction, lower/moderate/above capacity fields` | `where=COUNTY='Orange'` then filter Jurisdiction contains "Santa Ana" |
| D4 | OC Floodplains | `https://www.ocgis.com/arcpub/rest/services/Map_Layers/Floodplains/MapServer/0/query` | `FLD_ZONE` + polygons | County services return State Plane; pass `outSR=4326`. Pull polygons intersecting the Santa Ana bbox once, PIP locally. Max 1,000 per call |
| D5 | OC Fire Hazard Severity (LRA) | `…/Map_Layers/Fire_Hazard_Severity_Zones_LRA/MapServer/0/query` | hazard class + polygons | Same approach. Santa Ana may have none: that is a PASS with "no LRA zone intersects parcel", not UNKNOWN |
| D6 | OC Liquefaction | `…/Map_Layers/Liquefaction/MapServer/0/query` | polygons | Same |
| D7 | Caltrans HQ Transit Areas | `https://caltrans-gis.dot.ca.gov/arcgis/rest/services/CHrailroad/CA_HQ_Transit_Areas/FeatureServer/0/query` | `hqta_type, agency_primary` + polygons | bbox filter, PIP |
| D8 | SCAG Major Transit Stops 2022 | `https://maps.scag.ca.gov/scaggis/rest/services/OpenData/Major_Transit_Stops_Plan_Year_2022/MapServer/0/query` | points | Distance ≤ 0.5 mi (805 m) → SB 79 proxy flag |
| D9 | OC Parcels | `https://www.ocgis.com/arcpub/rest/services/Map_Layers/Parcels/FeatureServer/0/query` | `ASSESSMENT_NO`, site address, year built, bedrooms | Only for candidates and for address lookup (point query). Normalise APN to digits only on both sides before joining |
| D10 | IRS Exempt Orgs BMF, California | `https://www.irs.gov/pub/irs-soi/eo_ca.csv` | `NAME, STREET, CITY, ZIP, NTEE_CD, SUBSECTION, FOUNDATION` | Filter `CITY == 'SANTA ANA'` and (NTEE starts with `X` or FOUNDATION code for churches). **Drop the `ICO` column on load.** Geocode with Census batch geocoder (D11), then point-query D9 to get the APN |
| D11 | Census Geocoder | `https://geocoding.geo.census.gov/geocoder/locations/onelineaddress?address=…&benchmark=Public_AR_Current&format=json` | lat/lon | Also used by the address lookup feature |
| D12 | OSM places of worship | Overpass `[out:json];(nwr["amenity"="place_of_worship"](33.68,-117.97,33.79,-117.83););out center;` | name, religion, center | Returned 502 on Nov 6. One retry, then skip and say so in the UI |
| D13 | Surplus Land Act NOAs | `https://publish.data.ca.gov/dataset/0a52a6d9-4c1f-4905-8d25-6117c60c35c8/resource/bb81599a-e130-48aa-a6e3-bbcce9392d4f/download/noa_information.csv` | `APN, Address, City, Date Notice Issued, NOA Status, Parcel Size, Existing Use, contact` | 3,112 rows, 113 in OC, all `Archive`. Join on APN digits, fall back to address. Show as history, never as "available" |

Santa Ana bbox (WGS84): lon −117.97 to −117.83, lat 33.68 to 33.79. Cache every response under `data/raw/<layer>/<page>.json`. The pipeline must be re-runnable offline from cache.

---

## 4. Rule engine (`pipeline/rules.py`)

Every test returns `{"id", "label", "result": "PASS"|"FAIL"|"UNKNOWN", "reason", "source", "checked": "2026-11-07"}`. A pathway's status is FAIL if any test FAILs, PASS if all PASS, else UNKNOWN. Thresholds below come from HCD fact sheets as the organizers summarised them; **the agent must open each fact sheet URL, confirm the number, and cite the page in `source`. If it cannot confirm, the test is UNKNOWN, not a guess.**

Sources: HCD SB 9 sheet `https://www.hcd.ca.gov/sites/default/files/docs/planning-and-community/lot-splits-and-duplexes-sb-9.pdf`; HCD combined fact sheets (SB 684/1123, AB 2011) `https://www.hcd.ca.gov/sites/default/files/docs/planning-and-community/housing-law-fact-sheets.pdf`; HCD SB 4 sheet `https://www.hcd.ca.gov/sites/default/files/docs/planning-and-community/aff-hsg-faith-higher-ed-sb-4.pdf`; HCD AB 2011 draft guidelines `https://www.hcd.ca.gov/sites/default/files/docs/planning-and-community/draft-ab-2011-guidelines.pdf`.

### 4.1 Shared hazard tests (run once per parcel, reused by every pathway)

| id | PASS | FAIL | UNKNOWN |
|---|---|---|---|
| `haz.flood` | centroid outside any D4 polygon with `FLD_ZONE` starting `A` or `V` | inside one (label "Special Flood Hazard Area, mitigation required under some pathways") | D4 fetch failed |
| `haz.fire` | not in a Very High zone in D5 | in Very High | D5 failed |
| `haz.liquefaction` | outside D6 | inside D6 → **FLAG, not FAIL** (statutes do not exclude it; show as "investigation likely") | D6 failed |
| `haz.historic` | — | — | always UNKNOWN: "no verified historic-district layer for Santa Ana; check city list" |
| `haz.wetland_farmland` | — | — | always UNKNOWN today |

### 4.2 Pathways

**P1 SB 9, lot split and/or two units** (Gov Code 65852.21, 66411.7)
- `sb9.zone`: PASS if `ZN24_CITY` is a single-family zone. Santa Ana codes expected `R1`; confirm the city's zoning code list and record the mapping in `codes.py` as ASSUMPTION until confirmed.
- `sb9.urban`: PASS for all Santa Ana parcels (city is entirely within a Census urbanized area; cite Census UA).
- `sb9.size_split`: PASS if lot ≥ 2,400 sf (each resulting lot ≥ 1,200 sf per HCD sheet; confirm).
- `sb9.tenancy`: UNKNOWN always ("no data on tenant occupancy in prior 3 years").
- hazards: flood, fire, historic.
- Yield note shown on card: "up to 4 homes on the original lot".

**P2 SB 684 / SB 1123, small-lot subdivision up to 10 homes** (Gov Code 66499.41, 65913.4.5)
- `sb684.zone_size`: PASS if (multifamily zone and ≤ 5 acres) OR (single-family zone, vacant per D2, ≤ 1.5 acres). **Confirm both thresholds and the SB 1123 vacant-lot rule in the HCD sheet before coding; the organizers warn "lot-size limits differ by source".**
- `sb684.urban`: as above.
- `sb684.no_demo_protected`: UNKNOWN unless D2 says vacant (then PASS, "vacant per SCAG 2024 land use").
- hazards.
- Yield: "up to 10 homes".

**P3 AB 2011, housing on commercial sites, 100% affordable track** (Gov Code 65912.110 series)
- `ab2011.zone`: PASS if `ZN24_CITY` is a commercial/office zone where retail, office or parking is principally permitted (Santa Ana `C1, C2, C5, P` expected; confirm).
- `ab2011.size`: PASS if ≤ 20 acres.
- `ab2011.industrial_adjacency`: FAIL if any parcel with an industrial `LU24` (3xxx) shares a boundary; approximate with "any industrial-use parcel centroid within 60 m" and label the approximation. UNKNOWN if D2 missing.
- `ab2011.corridor`: not required for the 100% affordable track per HCD; show as "N/A for 100% affordable" with source.
- hazards.

**P4 SB 4, faith and nonprofit-college land** (Gov Code 65913.16, effective July 2, 2024)
- `sb4.owner_proxy`: PASS-as-LEAD if a D10 religious org address or a D12 worship site falls on the parcel (label "owner type is a PROXY from a public registry; confirm with the county assessor"). UNKNOWN otherwise. **Never FAIL this test; absence of a proxy is not evidence.**
- `sb4.perimeter_urban`: PASS if ≥ 75% of neighbouring parcel centroids within 100 m have an urban `LU24` (not vacant/agricultural). Label the approximation.
- `sb4.industrial_buffer`: FAIL if an industrial-use parcel centroid is within 1,200 ft (366 m) — confirm the distance and the use list in the sheet.
- hazards: flood FAIL, fire FAIL, plus `haz.wetland_farmland` UNKNOWN.

**P5 SB 79, transit-oriented upzoning** (effective July 1, 2026)
- `sb79.transit`: FLAG if within 0.5 mi of a D8 major transit stop. Show as "candidate: Santa Ana has published a draft SB 79 eligibility map; confirm applicability and tier there" with the city link `https://santa-ana.gov/documents/draft-sb-79-potential-eligibility-map-with-general-plan-land-uses`. This pathway never reaches PASS today.

**P6 Housing-element site** (not a statute: a city-identified site)
- `he.listed`: PASS if APN in D3, show the lower/moderate capacity the city assigned and "listed in adopted 6th-cycle housing element; may be stale".

**P7 Surplus land history**
- `sla.history`: INFO if APN or address in D13: date, status (Archive), existing use, and the agency contact field (that is a public agency contact, allowed).

### 4.3 Score (0–100, every weight is an ASSUMPTION and is shown in the UI)

```
size_fit        25  lot 2,400 sf – 1.0 ac → 25; 1–2 ac → 15; 1,200–2,400 sf → 10; else 0
best_pathway    25  any pathway PASS → 25; best is UNKNOWN with no FAIL → 12; all FAIL → 0
he_listed       15
owner_lead      15  SB 4 proxy present
low_intensity   10  LU24 is vacant or surface parking (codes from domain)
transit          5  inside HQTA or ≤ 0.5 mi of a major stop
hazard gate      —  haz.flood FAIL or haz.fire FAIL → score = 0 and "excluded by hazard" (still viewable)
```

Exclude from the ranked list: parcels < 1,200 sf, parcels > 5 acres, and parcels whose zoning is industrial, public facility or open space unless they are SB 4 leads or HE-listed. Keep them queryable by address.

---

## 5. Data model

`data/candidates.json`:

```json
{
  "city": "Santa Ana",
  "built_at": "2026-11-07T11:40:00-08:00",
  "sources": [{"id":"D1","name":"SCAG Zoning_poly_OR","url":"…","checked":"2026-11-07","status":"ok","rows":42896}],
  "weights": {"size_fit":25,"best_pathway":25,"he_listed":15,"owner_lead":15,"low_intensity":10,"transit":5,"label":"ASSUMPTION"},
  "sites": [
    {
      "apn": "00101105", "apn_display": "001-011-05",
      "address": "…", "lat": 33.74, "lon": -117.87,
      "acres": 0.34, "sqft": 14813, "slope": 0,
      "zoning": {"city_code":"R1","scag_code":"1100","label":"Single-family residential (ASSUMPTION: mapping to be confirmed)"},
      "land_use": {"code":"6100","label":"Vacant"},
      "year_built": null, "bedrooms": null,
      "hazards": {"flood":{"result":"PASS","reason":"…","source":"…","checked":"2026-11-07"}, "fire":{}, "liquefaction":{}, "historic":{}},
      "pathways": [
        {"id":"SB9","name":"SB 9 lot split / two units","status":"PASS","yield":"up to 4 homes",
         "tests":[{"id":"sb9.zone","label":"Single-family zone","result":"PASS","reason":"ZN24_CITY=R1","source":"https://…","checked":"2026-11-07"}]}
      ],
      "housing_element": {"listed": true, "capacity_lower": 8, "capacity_moderate": 0, "source":"…"},
      "surplus_history": null,
      "owner_lead": {"type":"religious_org_proxy","org_name":"…","source":"IRS EO BMF","note":"PROXY, confirm with assessor"},
      "transit": {"hqta": true, "major_stop_within_half_mile": true},
      "score": 78, "score_breakdown": {"size_fit":25,"best_pathway":25,"he_listed":15,"owner_lead":0,"low_intensity":10,"transit":3},
      "who_to_call": [{"who":"City of Santa Ana Planning Division (housing-element site)","why":"site is in the adopted inventory","contact":"public planning counter"}],
      "unknowns": ["Tenant occupancy in prior 3 years","Historic district status"]
    }
  ]
}
```

Export (`/api/sites/{apn}/export.json`) is the same object plus `"for_lane_2": {"pathway_is_ministerial": true, "clock_days": 60, "source": "…"}` and `"for_lane_3": {"land_line_hint": "ASSUMPTION: no price data; enter purchase price"}`.

---

## 6. API

| Method | Path | Behaviour |
|---|---|---|
| GET | `/api/sites` | Query: `city` (default Santa Ana), `limit` (default 50), `pathway` (SB9/SB684/AB2011/SB4/SB79/HE), `minSf`, `maxSf`, `heOnly`, `excludeHazardUnknown`. Returns ranked sites (score desc), trimmed to list fields |
| GET | `/api/sites/{apn}` | Full site object |
| GET | `/api/lookup?address=` | Geocode (D11) → OC parcel point query (D9) → APN → if in candidates return it; else fetch D1/D2 rows by APN, run hazards and rules live, return a site object with `"live": true` |
| POST | `/api/explain` | Body `{apn}`. Builds the prompt from the site object only (no outside facts), calls Claude, validates JSON `{brief, confirm_first[], call_script, caveats[]}`, caches to `data/explanations/{apn}.json`. `MOCK_CLAUDE=1` → templated text |
| GET | `/api/sites/{apn}/export.json` | Download |
| GET | `/api/meta` | `sources`, `weights`, `built_at`, counts, pipeline status per layer (ok / failed → which tests are UNKNOWN because of it) |

Claude prompt rules: system prompt says "You explain a parcel screening to a nonprofit acquisitions lead. Use only the JSON provided. Never state a number that is not in the JSON. Never say a project is approved or legal; say which tests passed and what must be confirmed. Output JSON with keys brief (≤120 words), confirm_first (3–5 items), call_script (≤100 words, draft, first person, for the city planner or organisation listed in who_to_call), caveats." 20 s timeout, one retry, fallback to template.

---

## 7. UI design

Single page, desktop first (judges demo on a laptop), works at 1280 px. Three columns: filters + ranked list (left, 360 px), map (centre, flexible), site card (right, 420 px, slides in). Top bar carries the city, the data-checked date, and the address box. Palette: neutral greys, one accent (deep orange `#c2410c`) for scores and PASS highlights; red `#b91c1c` for FAIL; amber `#b45309` for UNKNOWN; green `#15803d` for PASS. System font. No animation beyond the drawer slide.

### 7.1 Frame A: main screen

```
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│ ◧ Site Scout   City: [Santa Ana ▾]   Data checked 2026-11-07 ●   [ Check an address… 🔍 ] │
│                                     Not legal or financial advice · prototype · sources ⓘ │
├────────────────────┬───────────────────────────────────────────┬─────────────────────────┤
│ FILTERS            │                                           │                         │
│ Pathway [Any ▾]    │                                           │   (site card slides     │
│ Size  [2,400]–[1ac]│              LEAFLET MAP                  │    in here on click,    │
│ ☑ HE sites only    │     markers coloured by score band        │    see Frame B)         │
│ ☐ hide hazard unkn │     ● 70+  ● 40–69  ○ <40  ✕ excluded     │                         │
│ Weights ⓘ (ASSUMP) │                                           │                         │
├────────────────────┤                                           │                         │
│ TEN TO CALL · 312  │                                           │                         │
│ candidates         │                                           │                         │
│ ┌────────────────┐ │                                           │                         │
│ │ 78  917 N …    │ │                                           │                         │
│ │ SB 9 ✓ · HE ✓  │ │                                           │                         │
│ │ 0.34 ac · vacant│ │                                           │                         │
│ ├────────────────┤ │                                           │                         │
│ │ 74  1221 N …   │ │                                           │                         │
│ │ AB 2011 ? ·SB4 ★│ │                                           │                         │
│ │ 0.21 ac · parking│                                           │                         │
│ ├────────────────┤ │                                           │                         │
│ │ …              │ │                                           │                         │
│ └────────────────┘ │                                           │                         │
│ [Export top 10 ⬇]  │                                           │                         │
└────────────────────┴───────────────────────────────────────────┴─────────────────────────┘
```

List row: score chip, address (or APN if none), pathway badges (`✓` PASS, `?` UNKNOWN, `★` SB 4 lead), acres, current use. Click → marker focus + Frame B. Keyboard ↑↓ moves selection.

### 7.2 Frame B: site card (right drawer)

```
┌─────────────────────────────────────────────┐
│ 917 N Bristol St · APN 001-011-05      [✕]  │
│ 0.34 ac (14,813 sf) · R1 Single-family ·     │
│ Vacant (SCAG LU24 6100) · slope 0            │
│                                              │
│ SCORE 78 ───────────────────────── ⓘ weights │
│ size 25 · pathway 25 · HE 15 · owner 0 ·     │
│ use 10 · transit 3        (ASSUMPTION)       │
│                                              │
│ HAZARDS  flood PASS · fire PASS · liq FLAG · │
│          historic UNKNOWN                    │
│                                              │
│ PATHWAYS                                     │
│ ▸ SB 9 lot split / two units     PASS  4 homes│
│ ▾ SB 684/1123 small lot          UNKNOWN 10  │
│   ┌──────────────────────────────────────┐   │
│   │ test              result  source  ✓  │   │
│   │ zone + size       PASS    HCD ↗  11/7│   │
│   │ urban area        PASS    Census↗11/7│   │
│   │ no protected demo UNKNOWN —  "no data"│   │
│   │ flood             PASS    OC GIS↗11/7│   │
│   └──────────────────────────────────────┘   │
│ ▸ AB 2011 (100% affordable)      FAIL        │
│ ▸ SB 4 faith land                UNKNOWN     │
│ ▸ SB 79 transit                  FLAG        │
│                                              │
│ HOUSING ELEMENT  listed · 8 lower-income     │
│                  capacity · may be stale ↗   │
│ SURPLUS HISTORY  NOA 02-20-2026 · Archive ↗  │
│ OWNER LEAD       none found (proxy only)     │
│                                              │
│ WHO TO CALL                                  │
│ • Santa Ana Planning (HE site contact) ↗     │
│ • Santa Ana Real Property (NOA contact) ↗    │
│                                              │
│ [ ✦ Explain with Claude ]  [ Export JSON ⬇ ] │
│ ┌──────────────────────────────────────────┐ │
│ │ Brief: …                                 │ │
│ │ Confirm first: 1… 2… 3…                  │ │
│ │ Call script (draft, not sent): "Hi, …"   │ │
│ │ Caveats: …                               │ │
│ └──────────────────────────────────────────┘ │
│ Not legal or financial advice. Prototype.    │
└─────────────────────────────────────────────┘
```

### 7.3 Frame C: address lookup result

Same card, with a banner at the top: `Live check · fetched 11:52 AM · not in the ranked set` or `Ranked #14 of 312`. If geocoding fails: inline error "Could not place that address. Try 'number street, Santa Ana, CA'." If the parcel is outside Santa Ana: "Site Scout has layers for Santa Ana today. Other OC cities: run `build.py --city`."

### 7.4 Frame D: sources panel (click ⓘ in the top bar)

Table of every layer: name, URL, rows pulled, status (ok / failed), date checked, which tests go UNKNOWN when it fails. Plus the weights table with the ASSUMPTION label. This panel is what the judge sees when they ask "where does that come from".

### 7.5 Empty / failure states

- Pipeline layer failed → tests from that layer are UNKNOWN, the sources panel shows red, the list still renders.
- Claude unavailable → card shows the templated brief with a grey "offline template" tag.
- No candidates match filters → "No sites match. Loosen the size band or pathway."

---

## 8. Flows

### 8.1 Pipeline flow (`pipeline/build.py --city "Santa Ana"`)

```
1 fetch D1 zoning (paged) ──► parcels{apn: {...}}        cache data/raw/zoning/*.json
2 fetch D2 land use (paged) ──► join on apn
3 fetch D3 HE sites (OC) ──► join on apn
4 fetch D4,D5,D6 hazard polygons in bbox ──► PIP per parcel centroid
5 fetch D7 HQTA polygons, D8 stops ──► PIP + distance
6 load D10 IRS CSV → filter → geocode (D11, cache) → D9 point query → apn  ──► owner_lead
7 fetch D12 OSM (1 retry) ──► point → D9 → apn ──► owner_lead (merge)
8 load D13 NOA CSV → filter Santa Ana → join apn/address
9 rules.py per parcel → pathways, hazards, unknowns
10 score.py → score, breakdown; filter; sort
11 write data/candidates.json + data/meta.json; print summary (counts per pathway status)
```

Every step is a function with `--skip-<step>` and reads from cache when present. Steps 6 and 7 are the ones to cut if time runs out (owner_lead becomes "not run").

### 8.2 User flow (demo)

```
open app ──► Santa Ana list loads (≤1 s, local JSON)
   │
   ├─► click #1 ──► card: pathways, tests, sources ──► Explain with Claude ──► brief + call script
   │                                                   └─► Export JSON (show the lane_2 / lane_3 fields)
   │
   └─► paste a real listed address ──► live card ──► "this is the public case we tested against"
```

### 8.3 Claude flow

```
POST /api/explain {apn}
  ├─ cache hit → return
  ├─ build prompt: system rules + site JSON only
  ├─ anthropic.messages.create(model=claude-sonnet-5-5, max_tokens=700, timeout=20s)
  ├─ parse JSON, validate keys, strip any digits not present in the site JSON → if a number
  │  appears that is not in the input, replace with "[see card]" and add caveat "model text edited"
  └─ on error/timeout → template; tag "offline template"
```

---

## 9. Repo layout

```
GIS4All/
  README.md                 from templates/TEAM-README.md (event repo), filled in
  LICENSE                   MIT
  .env.example              APP_ANTHROPIC_API_KEY=  MOCK_CLAUDE=
  requirements.txt          pinned
  pipeline/
    build.py  fetch.py  geo.py  codes.py  rules.py  score.py  proxies.py
  api/
    main.py  claude.py  lookup.py
  web/
    index.html  app.js  styles.css
  data/
    candidates.json  meta.json  sample/candidates.sample.json (≤ 50 sites, committed)
    raw/   (gitignored)   explanations/ (gitignored)
  docs/
    DECISIONS.md  SOURCES.md  demo-script.md
  tests/
    test_rules.py  test_geo.py  (pytest, pure functions, no network)
```

Commit after every milestone directly on `main` (judges and the live demo read `main`; never force-push). `.gitignore` before the first commit. Tag the final commit `v0.1-hackathon`.

---

## 10. Build order with time boxes (now → 2:30 PM)

| By | Milestone | Done means |
|---|---|---|
| 11:10 | **M1 skeleton** | Repo, `.gitignore`, `requirements.txt`, `CLAUDE.md` (≤ 40 lines summarising sections 1.6, 4 and 6), `fetch.py` with paging + cache + `outSR=4326`, D1 pulled for Santa Ana and counted |
| 11:40 | **M2 joined parcels + hazards** | D2, D3, D4–D8 joined; `geo.py` PIP with tests; `candidates.json` exists with hazards filled |
| 12:10 | **M3 rules + score** | `rules.py` with every test in section 4, each citing a source URL; `score.py`; ranked list prints to console; `tests/test_rules.py` passes |
| 12:40 | **M4 API + list UI** | FastAPI serving `/api/sites`, `/api/meta`; Frame A renders with map markers and the ranked list from JSON |
| 1:10 | **M5 site card + Claude** | Frame B, `/api/explain` with cache and mock, Frame D sources panel, export |
| 1:35 | **M6 address lookup + proxies** | `/api/lookup`; IRS proxy (step 6) if M1–M5 are green, else mark "not run" |
| 1:50 | **M7 README + sample data** | README per template: user before/after, Try it, sources table, ASSUMPTION list, real vs mocked, where it is wrong. Commit `data/sample/candidates.sample.json`. `MOCK_CLAUDE=1 uvicorn api.main:app` works on a fresh clone |
| 2:15 | **M8 video** | 30-second recording per `docs/demo-script.md` (section 11). Upload on the hub |
| 2:30 | **Submit** | Form on the hub, repo URL (main page), video. Open the repo in a private window first |

**Cut list, in order:** OSM proxy (D12) → IRS proxy (D10) → SB 79 flag → map (ship the table) → Claude explain (ship template). Never cut: sources on the card, UNKNOWN reasons, ASSUMPTION labels, README Try-it, the video.

---

## 11. Demo script (30 seconds, one take)

1. (0–5 s) Title card: "Site Scout. For Habitat OC's acquisitions lead." Voice: "Habitat OC needs 100 homes in three years. Today they find land by luck."
2. (5–15 s) Frame A on screen. "Site Scout screens every parcel in Santa Ana against SB 9, SB 684, AB 2011 and SB 4, using public county, SCAG and state layers." Cursor on the sources badge.
3. (15–25 s) Click site #1. "Each site shows which legal tests pass, fail, or can't be checked, with the source and the date. Claude writes the brief and the first call." Scroll the tests table, show one UNKNOWN.
4. (25–30 s) "Ten sites to call this month. Next city is one command." Show the export button. End card: repo URL.

Live finals (3 minutes): same path, then paste the real listed address, then open the sources panel and say what is mocked and where it is wrong.

---

## 12. README checklist (from the event's submission rules)

- [ ] Follows `templates/TEAM-README.md` headings exactly.
- [ ] One real user, before and after, three sentences.
- [ ] "Try it": `git clone https://github.com/halapati3547/GIS4All.git && cd GIS4All && python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt && cp .env.example .env && MOCK_CLAUDE=1 uvicorn api.main:app --reload` then open `http://localhost:8000`. Runs on the committed sample without any key.
- [ ] Sources and assumptions table with a date-checked column; every weight and threshold marked ASSUMPTION.
- [ ] "What is real and what is mocked" table (layers ok / failed, proxies run or not, Claude live or template).
- [ ] "Where it gets things wrong": zoning-code mapping is unconfirmed, proxies are leads, adjacency is approximated by centroid distance, historic districts unknown.
- [ ] No keys, no personal information, repo public, everything on `main` by 2:30.
