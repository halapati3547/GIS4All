
## API and UI

- **Data loading.** `api/main.py` loads `data/candidates.json` + `data/meta.json` at startup. If `candidates.json` is missing it falls back to `data/sample/*.sample.json` (made-up sites, top-level `"SAMPLE"` key) and sets `meta.using_sample=true`; the UI then shows a yellow "Showing SAMPLE data" banner. Restart the server after the pipeline writes new data.
- **meta.json shape (assumed).** `{city, built_at, sources:[{id,name,url,checked,status:"ok"|"failed",rows,affects:[test ids]}], weights:{...,label:"ASSUMPTION"}, counts:{...}}`. Any missing key is filled from `candidates.json`. `affects` drives the "goes UNKNOWN if failed" column.
- **Hazard exclusion.** A site counts as excluded if `excluded_by_hazard` is true or `hazards.flood/fire.result == "FAIL"`. `excludeHazardUnknown` drops sites whose flood or fire result is UNKNOWN.
- **Pathway filter.** `pathway=X` keeps sites with a pathway of that id whose status is not FAIL. `pathway=HE` also matches `housing_element.listed`.
- **Pathway ids** expected: `SB9, SB684, AB2011, SB4, SB79, HE`. Statuses: `PASS, FAIL, UNKNOWN, FLAG` (INFO renders grey).
- **Export.** `for_lane_2.pathway_is_ministerial` is true when SB9/SB684/AB2011/SB4 is PASS; `clock_days: 60` is labelled ASSUMPTION.
- **Claude.** Placeholder by default: with `MOCK_CLAUDE` set or no `APP_ANTHROPIC_API_KEY`, `/api/explain` returns a template built from pathway statuses and unknowns, tagged `source:"offline template"`. Templates are not cached so a later real call can replace them; real responses are cached to `data/explanations/{apn}.json`. Real path: `claude-sonnet-5-5`, max_tokens 700, 20 s timeout, 1 retry, numbers not in the input replaced with "[see card]".
- **Address lookup** returns 501 `{"detail":"address lookup lands in M6"}`; the UI shows it inline.
- **Front end.** Vanilla JS, Leaflet 1.9.4 from cdnjs, OSM tiles; no build step. Stacks below 1000 px.
