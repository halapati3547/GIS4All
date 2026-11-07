"""D14 parse + D15 status + CH8 rule. Fixture rows are synthetic: made-up APNs and names only."""
import json
from pathlib import Path

from pipeline import rules, score, taxdefault as td
from tests.test_rules import facts, path

# Synthetic pdftotext -layout output: two table columns side by side plus notice text, as on the county PDF.
FIXTURE_2025 = """\
           NOTICE OF POWER AND INTENT TO SELL TAX-DEFAULTED PROPERTY                         NO.1 000-000-01   DOE, JANE TR        100 MAIN ST SANTA ANA             $1,234.56
The parcels listed herein will become subject to the Tax Collector's power to sell on        NO.2 000-000-02   ROE, RICHARD        ADDRESS NOT AVAILABLE             $99.00
July 1, 2099, at 12:01 a.m. The amounts necessary to redeem are set forth opposite           NO. 3 898-000-03  TIMESHARE, OWNER    ADDRESS NOT AVAILABLE             $10.00
the parcel numbers as of June 30, 2099. These amounts include penalties and costs.           NO.4 000-000-04   SMITH, JOHN         200 ELM ST SANTA ANA              $20,000.00   NO.5 000-000-05   EXAMPLE TRUST   300 OAK AV SANTA ANA   $5.00   more notice text
"""
FIXTURE_2024 = """\
The parcels listed herein will become subject to the Tax Collector's power to sell on        NO.1 000-000-01   DOE, JANE TR        100 MAIN ST SANTA ANA             $1,100.00
July 2, 2098, at 12:01 a.m. set forth opposite the parcel numbers as of July 1, 2098.         NO.2 000-000-09   NOBODY, NOT REAL    9 PINE ST SANTA ANA
"""
NAMES = ("DOE", "JANE", "ROE", "RICHARD", "SMITH", "JOHN", "TIMESHARE, OWNER", "EXAMPLE TRUST", "NOBODY")


def leads():
    return td.build_leads({2025: FIXTURE_2025, 2024: FIXTURE_2024})


def test_parse_rows_and_dates():
    rows = td.parse_rows(FIXTURE_2025)
    assert [r["apn"] for r in rows] == ["000-000-01", "000-000-02", "898-000-03", "000-000-04", "000-000-05"]
    assert rows[0]["amount"] == 1234.56 and rows[3]["amount"] == 20000.0 and rows[4]["amount"] == 5.0
    assert rows[1]["situs"] is False and rows[0]["situs"] is True
    assert td.notice_dates(FIXTURE_2025) == ("2099-07-01", "2099-06-30")
    assert td.notice_dates(FIXTURE_2024) == ("2098-07-02", "2098-07-01")


def test_build_leads_merge_and_timeshare():
    out, counts = leads()
    assert counts[2025] == {"rows": 5, "timeshare_dropped": 1, "kept": 4}
    assert "89800003" not in out and len(out) == 5
    a = out["00000001"]
    assert a["years_on_list"] == [2024, 2025]  # on both lists
    assert a["power_to_sell_since"] == "2098-07-02"  # earliest list wins
    assert a["redemption_amount"] == 1234.56 and a["redemption_as_of"] == "2099-06-30"  # newest list wins
    assert out["00000002"]["situs_address_on_notice"] is False
    assert out["00000009"]["redemption_amount"] is None  # amount not printed -> None, not 0


def test_no_names_key_set():
    out, _ = leads()
    out["00000001"]["status"] = td.status_from_rows([{"AssessmentNo": "000-000-01", "Delinquent": 1, "alv": 1000.0}])
    for v in out.values():
        assert set(v) <= td.LEAD_KEYS and set(v) >= td.LEAD_KEYS - {"status"}
        if "status" in v:
            assert set(v["status"]) == td.STATUS_KEYS
    blob = json.dumps(out).upper()
    assert not any(n in blob for n in NAMES)
    assert "Name" not in td.TTC_FIELDS.split(",")


def test_real_output_key_set_if_built():
    p = Path(td.OUT)
    if not p.exists():
        return
    for v in json.loads(p.read_text()).values():
        assert set(v) <= td.LEAD_KEYS
        assert set(v.get("status", {})) <= td.STATUS_KEYS | {"queried", "checked", "source"}


def lead(**status):
    out, _ = leads()
    x = out["00000001"]
    if status:
        x["status"] = status
    return x


def ch8(**kw):
    _, paths = rules.evaluate(facts(**kw))
    return path(paths, "CH8")


def test_ch8_no_lead_is_unknown_never_fail():
    p = rules.chapter8(facts())
    assert p["status"] == "UNKNOWN" and len(p["tests"]) == 1 and p["tests"][0]["result"] == "UNKNOWN"
    _, paths = rules.evaluate(facts())
    assert path(paths, "CH8")["status"] == "UNKNOWN"


def test_ch8_lead_vacant_flag():
    x = lead()
    p = ch8(tax_default=x, tax_status=None, lu="1900")
    assert p["status"] == "FLAG"
    res = {t["id"]: t for t in p["tests"]}
    assert res["ch8.on_list"]["result"] == "PASS" and res["ch8.vacant_or_substandard"]["result"] == "PASS"
    assert res["ch8.objection_window"]["kind"] == "confirm" and res["ch8.board_hearing"]["kind"] == "confirm"
    assert res["ch8.current_status"]["kind"] == "data" and res["ch8.current_status"]["result"] == "UNKNOWN"
    for t in p["tests"]:
        assert t["checked"] == rules.CHECKED and t["source"].startswith("https://")
    assert res["ch8.on_list"]["source"] == td.LISTS[2025]
    assert ch8(tax_default=x, lu="1110")["tests"][1]["result"] == "FLAG"


def test_ch8_status_mapping():
    ok = td.status_from_rows([{"AssessmentNo": "000-000-01", "Delinquent": 1, "alv": 10000.0}])
    cleared = td.status_from_rows([{"AssessmentNo": "000-000-01", "Delinquent": None, "alv": 10000.0}])
    missing = td.status_from_rows([])
    failed = {"queried": False, "checked": rules.CHECKED, "source": td.TTC_MAP}
    get = lambda s: next(t for t in ch8(tax_default=lead(**s), tax_status=s)["tests"] if t["id"] == "ch8.current_status")
    assert get(ok)["result"] == "PASS" and "ASSUMPTION" in get(ok)["reason"]
    assert get(cleared)["result"] == "FAIL"
    assert get(failed)["result"] == "UNKNOWN"
    assert get(missing)["result"] == "UNKNOWN"
    assert ch8(tax_default=lead(**cleared), tax_status=cleared)["status"] == "FAIL"
    assert rules.redemption_ratio(lead(**ok)) == round(1234.56 / 10000.0, 3)


def test_ch8_not_statutory():
    _, paths = rules.evaluate(facts(tax_default=lead(), lu="1900"))
    assert "CH8" not in rules.STATUTORY
    assert score.best_pathway(paths) == score.best_pathway([p for p in paths if p["id"] != "CH8"])


def test_score_and_exclusion_with_acquisition_lead():
    x = lead()
    f = facts(tax_default=x)
    hz, paths = rules.evaluate(f)
    s0, b0, _ = score.score(f, hz, paths)
    s, b, _ = score.score(f, hz, paths, acquisition_lead=x)
    assert b["owner_lead"] == 15 and b0["owner_lead"] == 0 and s == s0 + 15 and s <= 100
    _, b2, _ = score.score(f, hz, paths, owner_lead={"org_name": "x"}, acquisition_lead=x)
    assert b2["owner_lead"] == 15  # one shared bucket, not 30
    # the six weights sum to 95 today (25+25+15+15+10+5); the lead shares a bucket, so the total is unchanged.
    # no_open_pathway_cap is a cap, not a weight.
    assert sum(v for k, v in score.WEIGHTS.items() if k not in ("label", "no_open_pathway_cap")) == 95
    assert score.excluded(facts(zone="M1")) is not None
    assert score.excluded(facts(zone="M1"), acquisition_lead=True) is None
