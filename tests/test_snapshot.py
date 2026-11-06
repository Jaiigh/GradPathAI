from gradpath import snapshot, terms as T

SNAP = snapshot.load()
STATUSES = {"verified", "inferred", "unknown", "conflict"}


def test_totals_agree():
    plan_total = sum(t["credits"] for t in SNAP.data["study_plan"])
    category_total = sum(c["min_credits"] for c in SNAP.data["categories"])
    assert plan_total == category_total == SNAP.total_credits == 138
    assert sum(SNAP.courses[c]["credits"] for c in SNAP.required_courses()) == 90


def test_study_plan_terms_sum_to_their_stated_credits():
    for t in SNAP.data["study_plan"]:
        credits = sum(SNAP.courses[i["course"]]["credits"] if "course" in i else SNAP.categories[
            i["slot"]]["slot_credits"] for i in t["items"])
        assert credits == t["credits"], (t["year"], t["semester"])


def test_every_required_course_is_in_the_plan_once():
    planned = [i["course"] for t in SNAP.data["study_plan"] for i in t["items"] if "course" in i]
    assert sorted(planned) == sorted(SNAP.required_courses())


def test_statuses_and_references_are_well_formed():
    for cid, c in SNAP.courses.items():
        assert len(cid) == 7 and cid.isdigit(), cid
        assert c["status"] in STATUSES
        assert c["offered"]["status"] in STATUSES and c["prereqs"]["status"] in STATUSES
        for p in c["prereqs"]["all_of"]:
            assert p in SNAP.courses, (cid, p)
        for k in c["categories"]:
            assert k in SNAP.categories, (cid, k)
    assert {x["status"] for x in SNAP.data["conflicts"]} <= {"resolved", "open"}
    assert all(r["status"] in STATUSES for r in SNAP.data["regulations"].values())


def test_regulation_limits():
    assert SNAP.regulation("max_credits_regular") == 22
    assert SNAP.regulation("max_credits_summer") == 9


def test_terms():
    assert T.span("2569/2", "2570/2") == ["2569/2", "2569/S", "2570/1", "2570/2"]
    assert T.following("2569/S") == "2570/1"
    assert T.end_of_year4(2567) == "2570/2"
    assert T.study_year("2570/1", 2567) == 4
