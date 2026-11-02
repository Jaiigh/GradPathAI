"""Generate synthetic UAT personas (StudentState JSON) that follow the cp2566-v0 study plan.

Usage (from the repository root): python scripts/make_personas.py .
Writes data/fixtures/personas/*.json; the output is deterministic.
"""
import json
import sys
from pathlib import Path

repo = Path(sys.argv[1])
snap = json.loads((repo / "data/snapshots/cp2566-v0.json").read_text(encoding="utf-8"))
out = repo / "data/fixtures/personas"
out.mkdir(parents=True, exist_ok=True)
GRADES = ["A", "B+", "B", "A", "C+", "B", "B+", "A", "C", "B"]


def records_for(entry_year, last_year_sem, fills, overrides=None, extra=()):
    """Records for every study-plan item up to (year, sem) inclusive. fills maps slot occurrence -> (code, category)."""
    overrides = overrides or {}
    recs, slot_seen, i = [], {}, 0
    order = {"1": 0, "2": 1, "S": 2}
    for term in snap["study_plan"]:
        if (term["year"], order[term["semester"]]) > (last_year_sem[0], order[last_year_sem[1]]):
            break
        label = f"{entry_year + term['year'] - 1}/{term['semester']}"
        for item in term["items"]:
            if "course" in item:
                cid = item["course"]
                grade = "S" if cid == "2100301" else GRADES[i % len(GRADES)]
                i += 1
                recs.append({"course_id": cid, "term": label, "grade": overrides.get(cid, grade)})
            else:
                n = slot_seen.get(item["slot"], 0)
                slot_seen[item["slot"]] = n + 1
                code, cat = fills[(item["slot"], n)]
                rec = {"course_id": code, "term": label, "grade": GRADES[i % len(GRADES)]}
                i += 1
                if code not in snap["courses"]:
                    rec.update({"title": f"Synthetic {cat} course", "credits": 3, "category": cat})
                recs.append(rec)
    recs.extend(extra)
    return recs


def persona(ref, entry_year, records, unresolved=(), note=""):
    return {"student_ref": ref, "record_version": 1, "source_kind": "persona", "source_sha256": None,
            "snapshot_id": "cp2566-v0", "entry_year": entry_year, "next_term": "2569/2",
            "records": records, "unresolved": list(unresolved), "confirmed": False, "_note": note}


y3_fills = {("GE", 0): ("GEN-SOC-01", "GE_SOC"), ("GE", 1): ("GEN-HUM-01", "GE_HUM"), ("DEPT_ELECTIVE", 0): ("2110443", None)}
people = {
    "y1-start": persona("P-Y1", 2569, records_for(2569, (1, "1"), {}),
                        note="Year 1 after semester 1/2569; plans 2569/2 to 2572/2"),
    "y2-mid": persona("P-Y2", 2568, records_for(2568, (2, "1"), {("GE", 0): ("GEN-SCI-01", "GE_SCI")}),
                      note="Year 2 after semester 2569/1; plans 2569/2 to 2571/2"),
    "y3-base": persona("P-Y3", 2567, records_for(2567, (3, "1"), y3_fills),
                       note="Year 3 after semester 2569/1; plans 2569/2 to 2570/2 (summer 2569/S for 2100301)"),
    "y3-retake-open": persona("P-Y3-F", 2567, records_for(2567, (3, "1"), y3_fills, {"2110327": "F"}),
                              note="2110327 Algorithm Design graded F in 2568/2 and not yet retaken"),
    "y3-retake-passed": persona("P-Y3-FB", 2567, records_for(2567, (3, "1"), y3_fills, {"2603284": "F"},
                                                         extra=[{"course_id": "2603284", "term": "2569/1", "grade": "B"}]),
                                note="2603284 Statistics: F in 2568/1, B on retake in 2569/1"),
    "y4-final": persona("P-Y4", 2566, records_for(2566, (4, "1"), {
        ("GE", 0): ("GEN-SOC-02", "GE_SOC"), ("GE", 1): ("GEN-HUM-02", "GE_HUM"), ("GE", 2): ("GEN-INT-02", "GE_INTER"),
        ("GE", 3): ("GEN-SCI-02", "GE_SCI"), ("DEPT_ELECTIVE", 0): ("2110476", None), ("DEPT_ELECTIVE", 1): ("2110571", None),
        ("DEPT_ELECTIVE", 2): ("2110572", None), ("DEPT_ELECTIVE", 3): ("2110573", None), ("MULTI_21C", 0): ("2100225", None),
        ("CORE_ELECTIVE", 0): ("2110531", None), ("CORE_ELECTIVE", 1): ("2110404", None), ("FREE", 0): ("FREE-OTH-01", "FREE")}),
        note="Year 4 after semester 2569/1; only 2569/2 remains"),
}
base = people["y3-base"]["records"]
idx_211 = next(i for i, r in enumerate(base) if r["course_id"] == "2110211")
unres_grade = [dict(r) for r in base]
unres_grade[idx_211]["grade"] = None
unres_grade[idx_211]["evidence"] = {"page": 1, "row": 14, "text": "2110211 INTRO DATA STRUCT 3 ?"}
people["y3-unclear-grade"] = persona("P-Y3-G", 2567, unres_grade,
                                     [{"record_index": idx_211, "field": "grade", "reason": "grade unreadable in source", "candidates": ["B", "B+"]}],
                                     "grade of 2110211 unreadable; tester confirms B")
unres_id = [dict(r) for r in base]
unres_id[idx_211]["course_id"] = "21102?1"
unres_id[idx_211]["title"] = "INTRO DATA STRUCT"
unres_id[idx_211]["evidence"] = {"page": 1, "row": 14, "text": "21102?1 INTRO DATA STRUCT 3 B"}
people["y3-unclear-id"] = persona("P-Y3-ID", 2567, unres_id,
                                  [{"record_index": idx_211, "field": "course_id", "reason": "one digit unreadable", "candidates": ["2110211"]}],
                                  "course id of a Data Structures record unreadable; tester confirms 2110211")
for name, p in people.items():
    (out / f"{name}.json").write_text(json.dumps(p, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{name:18} entry {p['entry_year']}  records {len(p['records']):3}  unresolved {len(p['unresolved'])}")
