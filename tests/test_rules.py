from pipeline import rules, score, codes


def facts(**kw):
    f = {"apn": "00000001", "zone": "R1", "acres": 0.15, "lu": "1110", "flood": "X", "fire": "", "liq": False,
         "ind60": False, "ind366": False, "perim": (10, 10), "near_stop": False, "hqta": False, "he": None}
    f.update(kw)
    return f


def path(paths, pid):
    return next(p for p in paths if p["id"] == pid)


def test_test_shape():
    hz, paths = rules.evaluate(facts())
    for p in paths:
        for t in p["tests"]:
            assert set(t) == {"id", "label", "result", "reason", "source", "checked", "kind"}
            assert t["checked"] == "2026-11-07"
            assert t["source"].startswith("https://")


def test_pathway_status():
    mk = lambda r, kind="data": {"result": r, "kind": kind}
    assert rules.pathway_status([mk("PASS"), mk("FLAG"), mk("N/A")]) == "PASS"
    assert rules.pathway_status([mk("PASS"), mk("UNKNOWN")]) == "UNKNOWN"
    assert rules.pathway_status([mk("UNKNOWN"), mk("FAIL")]) == "FAIL"
    # only human-confirm items left -> CLEAR
    assert rules.pathway_status([mk("PASS"), mk("UNKNOWN", "confirm")]) == "CLEAR"
    assert rules.to_confirm([{"result": "UNKNOWN", "kind": "confirm", "label": "x"}]) == ["x"]


def test_sb9_size_and_zone():
    _, paths = rules.evaluate(facts(acres=2000 / 43560))
    sz = next(t for t in path(paths, "SB9")["tests"] if t["id"] == "sb9.size_split")
    assert sz["result"] == "FAIL"
    _, paths = rules.evaluate(facts(zone="C1"))
    z = next(t for t in path(paths, "SB9")["tests"] if t["id"] == "sb9.zone")
    assert z["result"] == "FAIL"
    _, paths = rules.evaluate(facts(zone="SD84"))
    assert next(t for t in path(paths, "SB9")["tests"] if t["id"] == "sb9.zone")["result"] == "UNKNOWN"
    # tenancy and historic are always UNKNOWN, so SB 9 cannot PASS today
    assert path(paths, "SB9")["status"] in ("UNKNOWN", "FAIL")


def test_sb684_vacant_single_family():
    _, paths = rules.evaluate(facts(lu="3100", acres=1.0))
    zs = next(t for t in path(paths, "SB684")["tests"] if t["id"] == "sb684.zone_size")
    assert zs["result"] == "PASS"
    _, paths = rules.evaluate(facts(lu="3100", acres=2.0))
    assert path(paths, "SB684")["status"] == "FAIL"
    _, paths = rules.evaluate(facts(zone="R3", acres=4.9))
    assert next(t for t in path(paths, "SB684")["tests"] if t["id"] == "sb684.zone_size")["result"] == "PASS"


def test_sb4_owner_proxy_never_fails():
    _, paths = rules.evaluate(facts(ind366=True))
    sb4 = path(paths, "SB4")
    assert next(t for t in sb4["tests"] if t["id"] == "sb4.owner_proxy")["result"] == "UNKNOWN"
    assert sb4["status"] == "FAIL"  # because of the industrial buffer, not the proxy


def test_hazards():
    hz, _ = rules.evaluate(facts(flood="AE", liq=True))
    assert hz["flood"]["result"] == "FAIL"
    assert hz["liquefaction"]["result"] == "FLAG"
    hz, _ = rules.evaluate(facts(flood=None, fire=None))
    assert hz["flood"]["result"] == "UNKNOWN" and hz["fire"]["result"] == "UNKNOWN"


def test_slope_and_contamination():
    hz, _ = rules.evaluate(facts(slope=0))
    assert hz["slope"]["result"] == "UNKNOWN"  # 0 may be unpopulated
    hz, _ = rules.evaluate(facts(slope=None))
    assert hz["slope"]["result"] == "UNKNOWN"
    hz, _ = rules.evaluate(facts(slope=12))
    assert hz["slope"]["result"] == "FLAG" and hz["slope"]["source"].startswith("https://")
    assert hz["contamination"]["result"] == "UNKNOWN" and hz["contamination"]["checked"] == "2026-11-07"


def test_no_open_pathway_is_capped():
    f = facts(zone="M1", lu="3100", acres=0.2, ind366=True, owner={"org_name": "X", "source": "s"}, near_stop=True)
    hz, paths = rules.evaluate(f)
    assert all(p["status"] == "FAIL" for p in paths if p["id"] in score.STATUTORY)
    s, b, _ = score.score(f, hz, paths, owner_lead=f["owner"])
    assert b["best_pathway"] == 0 and sum(b.values()) > score.WEIGHTS["no_open_pathway_cap"]
    assert s == score.WEIGHTS["no_open_pathway_cap"]


def test_score_and_gate():
    f = facts(lu="3100", near_stop=True)
    hz, paths = rules.evaluate(f)
    s, b, gated = score.score(f, hz, paths)
    # R1 vacant lot: SB 9 is CLEAR (only tenancy/historic left to confirm) -> best_pathway 25
    assert b == {"size_fit": 25, "best_pathway": 25, "he_listed": 0, "owner_lead": 0, "low_intensity": 10, "transit": 5}
    assert s == 65 and not gated
    assert any(p["id"] == "SB9" and p["status"] == "CLEAR" for p in paths)
    assert all(p["status"] != "CLEAR" for p in paths if p["id"] == "SB4")
    f = facts(flood="A")
    hz, paths = rules.evaluate(f)
    s, _, gated = score.score(f, hz, paths)
    assert s == 0 and gated


def test_size_fit_and_exclusions():
    assert score.size_fit(1000) == 0 and score.size_fit(1500) == 10
    assert score.size_fit(5000) == 15 and score.size_fit(8000) == 25 and score.size_fit(60000) == 15
    assert score.excluded(facts(acres=0.01)) == "lot under 1,200 sf"
    assert score.excluded(facts(acres=6)) == "lot over 5 acres"
    assert score.excluded(facts(zone="M1")) is not None
    assert score.excluded(facts(zone="M1"), he_listed=True) is None


def test_codes():
    assert codes.zone_family("C1-MD") == "commercial"
    assert codes.zone_family("OZ1") is None
    assert codes.lu_family("1900") == "vacant" and codes.lu_family("1311") == "industrial"
