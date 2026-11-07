# Market research: Claude Impact Lab, UCI × SoCal Affordable Housing (Nov 7, 2026)

Written 10:30 AM on hackathon day. Build window ends **2:30 PM**. Everything below is scoped to about 3.5 hours of building.

## 1. What the event actually is (not what the title says)

- **The partner is Habitat for Humanity of Orange County (Habitat OC)**, with the UCI Merage Center for Real Estate (Ed Coulson, Hilda Villadelgado). Lunch sponsor is EyeOn Automations (Kelly Stephens, 14 years at PulteGroup). Anthropic's Keith Mancuso ran the workshop.
- **Habitat OC's goal: 100 homes in its pipeline in 3 years.** They built 239 homes in 35 years (~7 a year). 100 in 3 years is ~33 a year, about **5x their historic pace**. That is the "Scale" story every judge will recognize.
- **What Habitat OC builds:** small infill ownership. 12 duplexes in Fullerton, 6 duplexes in Stanton, condos in Rancho Santa Margarita, single-family in Santa Ana and Costa Mesa, a semi-detached in Irvine. Low- and moderate-income deed restrictions. So "a site" for them means 1 to 12 homes, not a 100-unit tower.
- **Their stated bottleneck (from the brief):** they find land by luck. "A city calls about surplus land, or a church offers its parking lot."
- **The organizing frame:** family price + subsidies + fundraising − cost to create = $0. In the worked example, **land is $360k of a $535k home**. Land is the biggest line.
- **The closing question judges will ask the room:** if we combined the best Find + Clear + Fund tools, could one OC home hit $0? Tools that export clean, sourced numbers are "combinable" and will be remembered.

## 2. How to get into the top 10

The path to a prize has two gates, and they are judged differently.

**Gate 1, shortlist (2:30 PM):** judges watch **every video** and vote. 10 finalists. Nobody sees your repo or app before the video. So the 30-second video is the single highest-leverage artifact of the day. Structure: one named user → their problem in one sentence → the tool running on a real OC address → the result with sources visible → one honest "unknown".

**Gate 2, finals (3:00 PM):** live demo, scored 1–5 on four equal areas. Ties go to Impact.

| Area | What the docs literally say | What it means for you |
|---|---|---|
| Impact | "A nonprofit or city would use it next month to help get homes built" | Build for a Habitat OC staff role by name (acquisitions lead, project manager, finance lead) |
| Works | "Live demo on real data, sources shown. Rough and working beats polished" | Real APNs, real statutes, dates checked, ASSUMPTION labels on screen |
| Scale | "A believable path to the next 100 projects. A believable path beats a big claim" | Show the same pipeline runs on all 34 OC cities or all of California |
| Innovation | "A new way to see or solve the problem. New thinking, not just new tech" | Not a chatbot over PDFs. Connect two public datasets nobody has connected |

What explicitly **does not place**: slides without a demo, made-up numbers presented as facts, anything with real personal information. The prior Impact Lab (Oct 17, Illumination Health + Home) weighted the nonprofit partner's "day-one" view most heavily. Expect Habitat OC staff on the panel to have the same pull.

**Competition read:** 160 seats, 486 registered, 63% build regularly, so expect 30–40 teams. One team (Keystone, github.com/krishcal9-bit/homestretch) already has a polished live Next.js app bending the brief toward homeowner payment shock and mortgage readiness. Expect clustering: Lane 3 gap calculators (the synthetic deal makes it the easy on-ramp) and Lane 2 "ask the ADU rules" chatbots. Lane 1 is the hardest technically, so fewer working demos will exist there, and a working one stands out.

## 3. The opportunities the organizers themselves flagged as open

These come from the DATA-SOURCES files. Each is a gap the organizers verified on Nov 6 and nobody has filled.

| Gap (their words) | Lane | Why it matters |
|---|---|---|
| "Owner and tax-exempt status per parcel (needed for SB 4) is not in any free verified layer. Only proxies: worship sites and the IRS exempt-organizations file" | 1 | SB 4 by-right housing on faith land is the single biggest new land supply, and nobody can see it for OC |
| "Nobody has audited any OC city against AB 2234. That is an open task a team could do" | 2 | State law requires online checklists and sample applications; a 34-city audit is new |
| "No OC open permit dataset. Use APR Table A and A2 for benchmark timelines" | 2 | APR A2 has entitlement, permit and CO dates per project for every city; nobody has turned it into "how long does it really take here" |
| "No free affordable-ownership pro forma template has been confirmed" | 3 | A pro forma built from HSC 50052.5 plus a live Freddie Mac rate "would be useful on its own" |
| Surplus-land notices: "many rows are Archive, parcel size is text like 9,005 SF" | 1 | I pulled the CSV: 3,112 rows statewide, 113 in OC, and **all 113 are Archive**. So this is a history of what cities disposed, not a live pipeline. Useful as a layer, weak as a headline |
| "Housing-element site lists can go stale" | 1 | 2,126 adopted OC sites in the SCAG layer; compare with building footprints and APR permits to find which are still real |

Also missing from the brief entirely: **SB 79** (transit-oriented upzoning, signed Oct 2025, in force July 1, 2026). SCAG publishes a TOD map and Santa Ana published a draft SB 79 eligibility map. The brief says "the best teams find sources nobody else used." This is one.

## 4. Ranked options

### Option A (recommended): "Ten sites to call this month" — a site scout for Habitat OC's acquisitions lead (Lane 1)

**One line:** For one OC city, rank parcels where a 2–12 home affordable ownership project could go by right, show which legal test each site passes, fails or can't be checked, and who to call.

**The real user:** Habitat OC's acquisitions / real estate development lead (a role, not a named person). Before: waits for a church or a city to call. After: opens a ranked list of sites in Santa Ana with the law that opens each one, the hazards already screened, and the owner-type lead to confirm.

**Why it wins on the rubric**
- Impact: lands on the largest line of the bill ($360k land) and on Habitat's stated bottleneck (finding land by luck). Habitat OC already builds in Santa Ana, Fullerton, Stanton and Anaheim.
- Works: every input is a verified free endpoint (tested this morning: SCAG zoning has 42,896 Santa Ana parcel rows; OC parcels layer has 703,000 polygons).
- Scale: the SCAG layers cover all 34 OC cities with the same fields, so "next city" is a parameter change. Same approach works statewide.
- Innovation: the SB 4 faith-land proxy (worship sites + IRS exempt-org file joined to parcels) is the exact missing field the organizers called out. Adding SB 79 transit zones is a source nobody in the brief listed.

**Scope that fits 3.5 hours**
1. Pick **Santa Ana** (verified city parcel API, verified zoning API, a published draft SB 79 map, and Habitat already builds there). Anaheim is the fallback.
2. Python script pulls, once, and caches JSON: SCAG `Zoning_poly_OR` (APN, zoning, acres, slope), SCAG `Existinglanduse_poly_OR` (LU24: find parking, vacant, low-intensity), SCAG `HousingElementSite_poly_scag` filtered `COUNTY='Orange'`, OC Floodplains, OC Fire Hazard LRA, OC Liquefaction, Caltrans HQTA transit areas, OSM `amenity=place_of_worship` (use an extract or retry Overpass) and the IRS BMF filtered to religious orgs in Santa Ana ZIPs.
3. Rule engine: per parcel, per pathway (SB 9, SB 684/1123 small-lot, SB 4 proxy, AB 2011 corridor, SB 79 transit, housing-element site, surplus-land history) → PASS / FAIL / UNKNOWN per test, each with the source URL and the date checked. Never guess a test you have no layer for; print UNKNOWN.
4. Score and rank: acres fit for 2–12 homes, no fire/flood/liquefaction hit, near transit, in a housing-element inventory, worship-owner proxy. Output top 10.
5. UI: Leaflet map + ranked list + a site card. Claude's job at runtime: explain the card in plain English, draft (not send) the call script to the owner or city, and summarize the statute test list from the HCD fact sheet. Claude never produces a number.
6. Export each site as JSON with the pathway and cost-relevant fields, so a Lane 2 or Lane 3 team could consume it. Say this out loud in the demo: it answers the closing question.

**Risks and how to cut**
- GIS joins are the time sink. Use ArcGIS REST server-side spatial queries (`geometry` + `spatialRel=esriSpatialRelIntersects`, `outSR=4326`) instead of local geoprocessing. County services return at most 1,000 rows and SCAG 2,000 per call; page with `resultOffset`.
- If Overpass is down (it returned 502 on Nov 6), use the IRS BMF alone and label the proxy as a lead.
- If the map is late, ship the ranked table and site cards first. A table with sources beats a map without them.
- Do not use owner names. Parcel data is public; owner names tied to people are personal information under the ground rules. Owner *type* via a nonprofit registry is fine, labelled as a proxy.

### Option B (strong fallback, lowest technical risk): "Which city gets me to keys faster?" (Lane 2)

**One line:** Turn HCD's Annual Progress Report tables into real entitlement → permit → certificate-of-occupancy timelines for every OC city by project type, and audit each city's posted checklist against state law.

- Data: APR Table A2 (927,006 rows statewide, fields `ENT_APPROVE_DT1`, `BP_ISSUE_DT1`, `CO_ISSUE_DT1`, `UNIT_CAT`), free CKAN API, no key, verified. Table A has application submit dates and SB 35 flags.
- Output: a 34-city league table of median days per phase for ADU, 2–4 unit and 5+ unit projects, with sample sizes and "what the data cannot show" (plan-check rounds, utility sign-offs) stated plainly.
- Claude's job: read one city's ADU checklist PDF (Anaheim's Nov 2025 checklist still cites repealed Gov Code 65852.2) and flag stale statute numbers against the SB 477 renumbering (now 66310–66342) and AB 2234 requirements. That is the "nobody has audited any OC city" task.
- Rubric: Works is near-certain, Scale is statewide by construction, Impact is real for a Habitat project manager choosing between two cities (scenario C02) and for a city permit tech. Innovation is moderate: new way to see, built from a dataset most teams will skip.
- Pick this if nobody on the team is comfortable with geospatial data.

### Option C (crowded, pick only with a twist): the honest $0 pro forma (Lane 3)

- Affordable price from Health and Safety Code 50052.5, the HCD 2026 income limits (June 23, 2026 revision, show the date), the Freddie Mac PMMS CSV for the live rate, and a stackable program list (CalHome, CalHFA MyHome, FHLB WISH, Santa Ana My First Home, Garden Grove) with confirmed / unconfirmed flags.
- The organizers say no free template exists, so it has standalone value. But it is the natural on-ramp for every team that opens `synthetic-example-deal.json`, so expect several. Keystone is already adjacent and polished.
- Only choose this if you have a Habitat finance or lending angle the others will not, for example a donor view ("your $25,000 pays for these lines of this home") tied to a real listed OC property with ASSUMPTION labels.

## 5. Decision rule

- Someone on the team can pull GeoJSON and do a spatial query in Python today → **Option A**.
- Team is strongest at data wrangling and writing, not maps → **Option B**.
- Team has a finance or lending person and a donor story → Option C with the twist, otherwise avoid it.

## 6. Timeline for the rest of today

| Time | Do |
|---|---|
| 10:30–10:50 | Choose option, register team on the hub, assign: data, UI, README/sources, video |
| 10:50–12:00 | Data pull and cache. Rule engine with PASS/FAIL/UNKNOWN and sources. Pick one real public OC case |
| 12:00–1:15 | UI: ranked list, site card, map if time. Wire Claude for explanation and call-script drafting |
| 1:15–1:45 | README from `templates/TEAM-README.md`: user before/after, Try it commands, what is real vs mocked, ASSUMPTION table. `.env.example`, no keys |
| 1:45–2:15 | Record the 30-second video. Person → problem → real address → result with sources → one honest unknown |
| 2:15–2:30 | Submit on the hub. Check the repo in a private window. Keep the app running for the live demo |

## 7. Things that quietly cost points

- Scraping city websites. Several return 403 and the rules say stop. Use SCAG, OC GIS, data.ca.gov and HCD PDFs; all verified.
- Hard-coding a statute number without the date you checked. ADU law was renumbered; old numbers in your tool look careless to a legal judge (ambassador Michael Brown is a lawyer).
- A number with no label. "ASSUMPTION" on screen is rewarded; a confident made-up number disqualifies.
- Building a form that files or emails anything. Draft only.
- A demo that needs the hall Wi-Fi to fetch live. Cache everything to JSON and ship a sample.

## 8. Key sources

Hackathon
- Hub: https://claudesocal.com/uci-impact-lab
- Starter repo (brief, lanes, data lists, README template): https://github.com/travcjohnson/claude-impact-lab-uci
- Luma page naming Habitat OC: https://luma.com/uci-impact-lab
- Prior Impact Lab judging doc (partner view weighted most): https://github.com/travcjohnson/claude-impact-lab-oc
- Competitor already live: https://github.com/krishcal9-bit/homestretch

Habitat OC
- Our Homes (project types, cities, 100-home pipeline goal): https://habitatoc.org/our-homes/
- Keys to 100 campaign: https://habitatoc.org/keys-to-100-raises-330000-for-affordable-homeownership-in-orange-county/

Data endpoints tested this morning
- SCAG zoning by parcel, all 34 OC cities: https://maps.scag.ca.gov/scaggis/rest/services/LDX/Zoning_poly_OR/MapServer
- SCAG existing land use (LU24): https://maps.scag.ca.gov/scaggis/rest/services/LDX/Existinglanduse_poly_OR/MapServer
- SCAG housing-element sites: https://maps.scag.ca.gov/scaggis/rest/services/LDX/HousingElementSite_poly_scag/MapServer
- OC parcels (703,000): https://www.ocgis.com/arcpub/rest/services/Map_Layers/Parcels/FeatureServer/0
- Surplus Land Act notices CSV (3,112 rows, 113 OC, all Archive): https://publish.data.ca.gov/dataset/0a52a6d9-4c1f-4905-8d25-6117c60c35c8/resource/bb81599a-e130-48aa-a6e3-bbcce9392d4f/download/noa_information.csv
- APR Table A2 (entitlement, permit, CO dates): https://data.ca.gov/api/3/action/datastore_search?resource_id=fe505d9b-8c36-42ba-ba30-08bc4f34e022&limit=5
- Santa Ana draft SB 79 eligibility map: https://santa-ana.gov/documents/draft-sb-79-potential-eligibility-map-with-general-plan-land-uses
- SCAG SB 79 TOD map: https://rdp.scag.ca.gov/portal/apps/experiencebuilder/experience/?id=6a2891fa768646f8a410b1e7d249d8e2

Law
- HCD SB 4 fact sheet: https://www.hcd.ca.gov/sites/default/files/docs/planning-and-community/aff-hsg-faith-higher-ed-sb-4.pdf
- HCD SB 9 fact sheet: https://www.hcd.ca.gov/sites/default/files/docs/planning-and-community/lot-splits-and-duplexes-sb-9.pdf
- HCD combined housing law fact sheets (AB 2011, SB 684/1123, SB 6): https://www.hcd.ca.gov/sites/default/files/docs/planning-and-community/housing-law-fact-sheets.pdf
- SB 79 summary: https://sd11.senate.ca.gov/news/governor-newsom-signs-senator-wieners-landmark-law-build-more-homes-near-public-transit
- AB 130 CEQA infill exemption (2025): https://www.hklaw.com/en/insights/publications/2025/07/california-legislature-enacts-major-ceqa-reforms-for-housing-rich
- HCD ADU Handbook, March 2026 (new section numbers): https://www.hcd.ca.gov/sites/default/files/docs/policy-and-research/adu-handbook-update.pdf
