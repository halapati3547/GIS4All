"""Explain a site with Claude. Default path is the offline template (MOCK_CLAUDE=1 or no key)."""
import json
import os
import re

MODEL = "claude-sonnet-5-5"
SYSTEM = (
    "You explain a parcel screening to a nonprofit acquisitions lead. Use only the JSON provided. "
    "Never state a number that is not in the JSON. Never say a project is approved or legal; say which "
    "tests passed and what must be confirmed. Output JSON with keys brief (<=120 words), confirm_first "
    "(3-5 items), call_script (<=100 words, draft, first person, for the city planner or organisation "
    "listed in who_to_call), caveats. Output only the JSON object."
)
KEYS = ("brief", "confirm_first", "call_script", "caveats")


def template(site):
    paths = site.get("pathways", [])
    passed = [p["name"] for p in paths if p["status"] == "PASS"]
    flagged = [p["name"] for p in paths if p["status"] in ("UNKNOWN", "FLAG")]
    failed = [p["name"] for p in paths if p["status"] == "FAIL"]
    where = site.get("address") or f"APN {site.get('apn_display', site['apn'])}"
    use = (site.get("land_use") or {}).get("label", "unknown use")
    zone = (site.get("zoning") or {}).get("city_code", "unknown zone")
    brief = f"{where} is {site.get('acres')} acres, zoned {zone}, currently {use}. "
    brief += f"Screening tests passed for: {', '.join(passed)}. " if passed else "No pathway passed every test. "
    if flagged:
        brief += f"Still open (unknown or flagged): {', '.join(flagged)}. "
    if failed:
        brief += f"Failed: {', '.join(failed)}. "
    if site.get("excluded_by_hazard") or any((site.get("hazards", {}).get(k) or {}).get("result") == "FAIL" for k in ("flood", "fire")):
        brief += "A hazard test failed, so the site is excluded from ranking. "
    brief += "This is a screen, not an approval."
    unknown_tests = [t["label"] for p in paths for t in p.get("tests", []) if t["result"] == "UNKNOWN"]
    confirm = list(dict.fromkeys(site.get("unknowns", []) + unknown_tests))[:5]
    while len(confirm) < 3:
        confirm.append(["Current owner with the county assessor", "Zoning code with the planning division", "Any recorded easements"][len(confirm)])
    who = (site.get("who_to_call") or [{"who": "the City of Santa Ana Planning Division"}])[0]
    script = (f"Hi, I work with a nonprofit housing developer and I am looking at {where}. "
              f"Our screen suggests it may fit {passed[0] if passed else 'a state housing pathway'}, "
              f"but several items still need confirming, starting with: {confirm[0]}. Who is the right person to talk to? Thank you.")
    caveats = ["Owner type and zoning mappings are proxies or assumptions until confirmed.",
               "Not legal or financial advice. Prototype screening only."]
    return {"brief": brief, "confirm_first": confirm, "call_script": f"(Draft for {who['who']}) {script}",
            "caveats": caveats, "source": "offline template"}


def _numbers_guard(out, site_json):
    """Replace any number in model text that is not in the input JSON."""
    allowed = set(re.findall(r"\d+(?:\.\d+)?", site_json))
    edited = False

    def fix(text):
        nonlocal edited
        def sub(m):
            nonlocal edited
            if m.group(0) in allowed:
                return m.group(0)
            edited = True
            return "[see card]"
        return re.sub(r"\d+(?:\.\d+)?", sub, text)

    out["brief"] = fix(out["brief"])
    out["call_script"] = fix(out["call_script"])
    out["confirm_first"] = [fix(x) for x in out["confirm_first"]]
    if edited:
        out["caveats"].append("model text edited")
    return out


def call_claude(site):
    import anthropic
    site_json = json.dumps(site)
    client = anthropic.Anthropic(api_key=os.environ["APP_ANTHROPIC_API_KEY"], timeout=20.0, max_retries=1)
    msg = client.messages.create(model=MODEL, max_tokens=700, system=SYSTEM,
                                 messages=[{"role": "user", "content": site_json}])
    text = "".join(b.text for b in msg.content if b.type == "text")
    out = json.loads(text[text.find("{"): text.rfind("}") + 1])
    if not all(k in out for k in KEYS):
        raise ValueError("missing keys")
    out["confirm_first"] = [str(x) for x in out["confirm_first"]][:5]
    out["caveats"] = [str(x) for x in (out["caveats"] if isinstance(out["caveats"], list) else [out["caveats"]])]
    out = _numbers_guard(out, site_json)
    out["source"] = MODEL
    return out


def explain(site, cache_dir):
    cache = cache_dir / f"{site['apn']}.json"
    if cache.exists():
        return json.loads(cache.read_text())
    if os.environ.get("MOCK_CLAUDE") or not os.environ.get("APP_ANTHROPIC_API_KEY"):
        return template(site)  # placeholder path: not cached so a real run can replace it later
    try:
        out = call_claude(site)
    except Exception:
        return template(site)
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(out, indent=1))
    return out
