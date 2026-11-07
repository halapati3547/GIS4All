# Site Scout

> For Habitat for Humanity of Orange County's acquisitions lead: a ranked list of Santa Ana parcels where 2 to 12 affordable ownership homes could go by right, with every legal test shown as PASS, FAIL or UNKNOWN, its source and the date checked.

**Team:** GIS4All
**Members:** [names]
**Lane:** 1 Find it
**Built at:** Claude Impact Lab: UCI × SoCal Affordable Housing, November 7, 2026

## The real user

The acquisitions lead at Habitat OC. One person, no GIS team, and a goal of 100 homes in the pipeline within three years, about five times the historic pace. Land is the largest line on every home's bill.

**Before:** waits for a city or a congregation to call about a site, then spends weeks checking zoning, hazards and which state law might apply, one parcel at a time.
**After:** opens Site Scout, sees ten Santa Ana sites to call this month, each with the law that opens it, the tests that passed or could not be checked, and who to call. Pastes an address a congregation emailed and gets the same card in seconds.

## What we built

- A pipeline that joins SCAG parcel zoning and land use, the adopted housing-element site inventory, county flood, fire and liquefaction layers, and transit areas for every parcel in Santa Ana, then runs each parcel through SB 9, SB 684/1123, AB 2011, SB 4 and SB 79 tests and scores it for a 2 to 12 home project.
- A web app: ranked list, map, and a site card with the test table, sources, who to call, a Claude-written brief and draft call script, and a JSON export a Lane 2 or Lane 3 tool could consume.

**Demo video:** uploaded on the hub
**Live demo:** run locally, see Try it

## How Claude is used

- We built it with Claude Code from a written spec (`docs/BUILD-SPEC.md`), one agent on the pipeline and one on the UI, with a lead session integrating.
- Inside the tool, Claude explains a site card in plain English, lists what a person must confirm first, and drafts (never sends) a first call. It only sees the site's JSON and never produces a number or a legal conclusion. The rule engine does that. Today the Claude call runs in offline template mode by default; the live call is behind `APP_ANTHROPIC_API_KEY`.

## Try it

```bash
git clone https://github.com/halapati3547/GIS4All.git && cd GIS4All
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
MOCK_CLAUDE=1 uvicorn api.main:app --port 8000
```

Open http://localhost:8000. It runs on the committed data without any key. To rebuild the data from the live public endpoints (about 10 minutes, cached under `data/raw/`):

```bash
python -m pipeline.build --city "Santa Ana"
```

Needs Python 3.11 or newer. No API key is required; set `APP_ANTHROPIC_API_KEY` in `.env` and unset `MOCK_CLAUDE` to use Claude live.

## Sources and assumptions

| Item | Source or assumption | Date checked |
|---|---|---|
| Parcel zoning, acres, slope (all 34 OC cities) | SCAG Zoning_poly_OR, https://maps.scag.ca.gov/scaggis/rest/services/LDX/Zoning_poly_OR/MapServer | 2026-11-07 |
| Existing land use | SCAG Existinglanduse_poly_OR (same server) | 2026-11-07 |
| Housing-element sites | SCAG HousingElementSite_poly_scag (same server) | 2026-11-07 |
| Flood, fire (LRA), liquefaction | OC Public Works Map_Layers, https://www.ocgis.com/arcpub/rest/services | 2026-11-07 |
| High-quality transit areas | Caltrans CA_HQ_Transit_Areas | 2026-11-07 |
| Major transit stops | SCAG Major_Transit_Stops_Plan_Year_2022 | 2026-11-07 |
| SB 9 tests | HCD fact sheet, https://www.hcd.ca.gov/sites/default/files/docs/planning-and-community/lot-splits-and-duplexes-sb-9.pdf | 2026-11-07 |
| SB 684/1123, AB 2011 tests | HCD combined fact sheets, https://www.hcd.ca.gov/sites/default/files/docs/planning-and-community/housing-law-fact-sheets.pdf | 2026-11-07 |
| SB 4 tests | HCD fact sheet, https://www.hcd.ca.gov/sites/default/files/docs/planning-and-community/aff-hsg-faith-higher-ed-sb-4.pdf | 2026-11-07 |
| SB 79 applicability in Santa Ana | City draft eligibility map, https://santa-ana.gov/documents/draft-sb-79-potential-eligibility-map-with-general-plan-land-uses (flag only, never PASS) | 2026-11-07 |
| Santa Ana zoning-code → category mapping (R1, R2–R4, C1/C2/C5/P, M1/M2) | ASSUMPTION, to confirm against the Santa Ana municipal code | 2026-11-07 |
| Score weights (25/25/15/15/10/5) and size bands | ASSUMPTION, shown in the app | 2026-11-07 |
| Adjacency and perimeter tests approximated by centroid distance (60 m, 100 m, 366 m) | ASSUMPTION | 2026-11-07 |

Every number we made up is labelled ASSUMPTION here and in the tool.

## What is real and what is mocked

| Part | Status |
|---|---|
| Parcel, zoning, land use, housing-element joins | working (live public data, cached) |
| Flood, fire, liquefaction, transit screens | working where the layer loaded; the Sources panel shows any layer that failed and which tests went UNKNOWN |
| Rule engine and score | working; thresholds cite HCD fact sheets, mapping and weights are ASSUMPTION |
| Owner-type proxy for SB 4 (IRS exempt orgs, worship sites) | [to fill: run / not run] |
| Address lookup | [to fill] |
| Claude brief and call script | placeholder: offline template by default; live call wired but not used in the demo |
| Sending anything to a city or owner | not built, by design |

## Where it gets things wrong

- Zoning-code categories are a mapping we assumed; a Santa Ana overlay or specific-plan zone can change the answer.
- Historic-district status, tenant occupancy, wetlands, farmland and contamination are UNKNOWN for every parcel; we have no verified layer.
- Owner type is a proxy from a public registry when present, and absent otherwise. Absence is not evidence.
- Industrial adjacency and the SB 4 perimeter test are approximated from neighbouring parcel centroids, not shared boundaries.
- A PASS means the written tests we could check passed. It is not an approval and not legal advice.

## Next steps

Run the same pipeline for the other 33 OC cities (one command each; the SCAG layers already cover them). Confirm the zoning mapping with each city's code. Add the county assessor roll for owner type. Join the HCD annual-progress-report permit dates so each site also shows how long this city really takes (Lane 2), and feed the export into a gap calculator (Lane 3).

## Data and privacy

This project uses only public or provided data. It contains no personal information about real tenants, buyers or residents. It does not file applications or contact any city or person.

## License

MIT, see the LICENSE file in this repo.
