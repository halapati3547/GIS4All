# Site Scout (GIS4All) — notes for Claude Code sessions

Read docs/BUILD-SPEC.md before changing anything. Short version:

- One real user: Habitat OC's acquisitions lead. Output: ranked Santa Ana parcels for 2–12 affordable ownership homes, with PASS / FAIL / UNKNOWN per legal test, a source URL and a checked date on every test.
- Rules live in pipeline/rules.py; weights in pipeline/score.py. Every threshold and weight is labelled ASSUMPTION until confirmed against the HCD fact sheet cited next to it. Never invent a statute number, fee or threshold. If no data layer covers a test, the answer is UNKNOWN with a reason.
- Claude (api/claude.py) only explains the site JSON it is given. It never produces a number or a legal conclusion. Default is MOCK_CLAUDE (offline template). The real call is a placeholder behind APP_ANTHROPIC_API_KEY.
- Data: public endpoints only (SCAG, OC GIS, Caltrans, data.ca.gov, IRS, Census). Cache under data/raw/. Never scrape city websites. No owner names, no personal information anywhere.
- Prototype only: draft call scripts, never send or file anything. "Not legal or financial advice" stays on every card.
- Folder ownership while building in parallel: pipeline/ + data/ (pipeline agent), api/ + web/ + data/sample/ (UI agent). Commits on main only, never force-push. Judges read main at 2:30 PM on 2026-11-07.

Run: `. .venv/bin/activate && python -m pipeline.build --city "Santa Ana"` then `MOCK_CLAUDE=1 uvicorn api.main:app --port 8000`.
