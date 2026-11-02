"""Build data/snapshots/cp2566-v0.json from rows extracted from the public 2566 curriculum page.

Usage (from the repository root):
    python scripts/build_snapshot_cp2566.py data/snapshots/sources/cp2566-page-rows.json data/snapshots/cp2566-v0.json

The rows file holds every "CODE ThaiName (EnglishName) credits(format)" line of source S1, captured on
2 Nov 2026 by converting the page HTML to text and matching that pattern. Curation rules (user policy,
2 Nov 2026): prefer the newest, 2566-specific source; record every conflict with its resolution; never
invent identity data (codes, credits).
"""
import json
import sys

rows = json.load(open(sys.argv[1], encoding="utf-8"))
out_path = sys.argv[2]

S1, S2, S3, S4, S5 = "S1", "S2", "S3", "S4", "S5"
sources = [
    {"id": S1, "title": "CP bachelor curriculum page, revised curriculum B.E. 2566 (Thai)", "type": "official_web",
     "url": "https://www.cp.eng.chula.ac.th/prospective/bachelor/", "accessed": "2026-11-02"},
    {"id": S2, "title": "Study-plan diagram: Bachelor of Engineering: Computer Engineering (2022) Final (138)", "type": "official_web",
     "url": "https://www.cp.eng.chula.ac.th/wp-content/uploads/2024/06/outline.png", "accessed": "2026-11-02"},
    {"id": S3, "title": "Chulalongkorn University regulation on higher-education study B.E. 2566 (Thai text, bilingual copy)",
     "type": "official_pdf",
     "url": "https://math.sc.chula.ac.th/wordpress/wp-content/uploads/2024/09/regulations_highereducationstudy_2023-CH.pdf",
     "accessed": "2026-11-02"},
    {"id": S4, "title": "Electrical Engineering B.Eng. curriculum B.E. 2566 (faculty-wide 2100xxx courses)", "type": "official_pdf",
     "url": "https://ee.eng.chula.ac.th/wp-content/uploads/2024/06/EEBEng2566.pdf", "accessed": "2026-11-02"},
    {"id": S5, "title": "CP bachelor curriculum page, B.E. 2561 (previous curriculum)", "type": "official_web",
     "url": "https://www.cp.eng.chula.ac.th/future/bachelor2018", "accessed": "2026-11-02"},
]

by_code = {}
for r in rows:
    code = r["code"]
    if code == "2110499" and r["name_en"] == "Senior Project in Engineering":
        continue  # duplicate listing; the later listing and S5 give 2100499 for this name (conflict C9)
    if "x" in code:
        continue  # placeholder codes are not course identities
    by_code.setdefault(code, r)

# Required courses: (category, plan year, plan semester) from the 2566 study plan (S1 table + S2 diagram).
required = {
    "2100111": ("GE_SPECIAL", 1, "1"), "2110221": ("GE_SPECIAL", 1, "2"),
    "5500111": ("LANG", 1, "1"), "5500112": ("LANG", 1, "2"), "5500208": ("LANG", 2, "2"), "5500308": ("LANG", 3, "2"),
    "2304103": ("MATH_SCI", 1, "1"), "2304183": ("MATH_SCI", 1, "1"), "2301107": ("MATH_SCI", 1, "1"),
    "2301108": ("MATH_SCI", 1, "2"), "2302127": ("MATH_SCI", 1, "2"), "2302163": ("MATH_SCI", 1, "2"),
    "2304104": ("MATH_SCI", 1, "2"), "2304184": ("MATH_SCI", 1, "2"), "2603284": ("MATH_SCI", 2, "1"),
    "2110101": ("ENG_BASIC", 1, "1"), "2110201": ("ENG_BASIC", 2, "2"), "2110203": ("ENG_BASIC", 3, "1"),
    "2100301": ("ENG_BASIC", 3, "S"),
    "2110215": ("CORE", 1, "2"), "2110200": ("CORE", 2, "1"), "2110211": ("CORE", 2, "1"), "2110251": ("CORE", 2, "1"),
    "2110263": ("CORE", 2, "1"), "2110313": ("CORE", 2, "2"), "2110322": ("CORE", 2, "2"), "2110327": ("CORE", 2, "2"),
    "2110352": ("CORE", 2, "2"), "2110363": ("CORE", 2, "2"), "2110426": ("CORE", 3, "1"), "2110318": ("CORE", 3, "1"),
    "2110366": ("CORE", 3, "1"), "2110423": ("CORE", 3, "1"), "2110471": ("CORE", 3, "1"), "2110488": ("CORE", 4, "1"),
    "2110489": ("CORE", 4, "2"),
}
core_electives = ["2110404", "2110521", "2110452", "2110531"]
multi_21c = {  # names on S1 carry placeholder codes; these codes come from the 2566 EE curriculum (S4)
    "2100223": ("Entrepreneurship and New Venture Creation", "ความเป็นผู้ประกอบการกับการสร้างธุรกิจใหม่"),
    "2100224": ("Technopreneurship", "ความเป็นผู้ประกอบการธุรกิจเทคโนโลยี"),
    "2100225": ("Design Thinking Principle", "หลักการคิดเชิงออกแบบ"),
    "2100226": ("Problem Solving Principle", "หลักการคิดแก้ไขปัญหา"),
}
# Prerequisites drawn as arrows on the study-plan diagram (S2); every other prerequisite is unknown.
prereqs = {
    "2110215": ["2110101"], "2110211": ["2110101"], "2110327": ["2110200", "2110211"], "2110313": ["2110211"],
    "2110366": ["2110263"], "5500112": ["5500111"], "5500208": ["5500112"], "5500308": ["5500208"],
}
dept_electives = [c for c in by_code if c not in required and c not in core_electives and c != "2110233"]
# Numbered sequences (part I before part II): an inference from course titles, not a published prerequisite.
sequences = {"2110477": ["2110476"], "2110496": ["2110495"], "2110498": ["2110497"], "2110489": ["2110488"]}


def course(code, name_th, name_en, credits, fmt, categories, kind, status="verified", srcs=(S1,), notes=()):
    plan = required.get(code)
    return {
        "name_th": name_th, "name_en": name_en, "credits": credits, "credit_format": fmt,
        "kind": kind, "categories": categories,
        "plan_term": {"year": plan[1], "semester": plan[2]} if plan else None,
        "offered": ({"semesters": [plan[2]], "status": "inferred", "basis": "study-plan semester (S1, S2)"} if plan
                    else {"semesters": None, "status": "unknown", "basis": "not published; varies by year"}),
        "prereqs": ({"all_of": prereqs[code], "status": "inferred", "basis": "study-plan diagram arrows (S2)"}
                    if code in prereqs else
                    {"all_of": sequences[code], "status": "inferred", "basis": "numbered course sequence (part I before part II)"}
                    if code in sequences else {"all_of": [], "status": "unknown", "basis": "not published"}),
        "status": status, "sources": list(srcs), "notes": list(notes),
    }


courses = {}
for code, (cat, _y, _s) in required.items():
    r = by_code[code]
    notes, status, credits, srcs = [], "verified", r["credits"], [S1, S2]
    if code == "2110318":
        credits, status = 1, "conflict"
        notes.append("C4: listed as 3(3-0-6); the study plan and the core total of 40 use 1 credit")
    if code == "2100111":
        status = "conflict"
        srcs.append(S4)
        notes.append("C5: the diagram shows code 2110111; the study-plan table shows 1 credit")
    courses[code] = course(code, r["name_th"], r["name_en"], credits, r["credit_format"], [cat], "required", status, srcs, notes)
for code in core_electives:
    r = by_code[code]
    courses[code] = course(code, r["name_th"], r["name_en"], r["credits"], r["credit_format"],
                           ["CORE_ELECTIVE", "DEPT_ELECTIVE", "FREE"], "core_elective")
for code in dept_electives:
    r = by_code[code]
    notes = ["C9: listed under 2110499 in the first listing"] if code == "2100499" else []
    courses[code] = course(code, r["name_th"], r["name_en"], r["credits"], r["credit_format"],
                           ["DEPT_ELECTIVE", "FREE"], "dept_elective", notes=notes)
r = by_code["2110233"]
courses["2110233"] = course("2110233", r["name_th"], r["name_en"], r["credits"], r["credit_format"], ["FREE"], "other",
                            "conflict", notes=["C6: in the basic-engineering list but not in the study plan or the 11-credit total"])
for code, (en, th) in multi_21c.items():
    courses[code] = course(code, th, en, 3, "3(3-0-6)", ["MULTI_21C", "FREE"], "multi_21c", "inferred", (S1, S4),
                           ["code from the 2566 EE curriculum; the CP page shows a placeholder code"])

categories = [
    {"id": "GE_SOC", "name_th": "ศึกษาทั่วไป กลุ่มวิชาสังคมศาสตร์", "name_en": "General Education: Social Sciences",
     "min_credits": 3, "fill": "slot", "slot_credits": 3},
    {"id": "GE_HUM", "name_th": "ศึกษาทั่วไป กลุ่มวิชามนุษยศาสตร์", "name_en": "General Education: Humanities",
     "min_credits": 3, "fill": "slot", "slot_credits": 3},
    {"id": "GE_INTER", "name_th": "ศึกษาทั่วไป กลุ่มวิชาสหศาสตร์", "name_en": "General Education: Interdisciplinary",
     "min_credits": 3, "fill": "slot", "slot_credits": 3},
    {"id": "GE_SCI", "name_th": "ศึกษาทั่วไป กลุ่มวิชาวิทยาศาสตร์และคณิตศาสตร์", "name_en": "General Education: Science and Mathematics",
     "min_credits": 3, "fill": "slot", "slot_credits": 3},
    {"id": "GE_SPECIAL", "name_th": "ศึกษาทั่วไป กลุ่มพิเศษ", "name_en": "General Education: Special Group",
     "min_credits": 6, "fill": "listed"},
    {"id": "LANG", "name_th": "ศึกษาทั่วไป กลุ่มวิชาภาษาต่างประเทศ", "name_en": "General Education: Foreign Language",
     "min_credits": 12, "fill": "listed"},
    {"id": "MATH_SCI", "name_th": "หมวดวิชาพื้นฐานทางวิทยาศาสตร์และคณิตศาสตร์", "name_en": "Basic Science and Mathematics",
     "min_credits": 21, "fill": "listed"},
    {"id": "ENG_BASIC", "name_th": "หมวดวิชาพื้นฐานทางวิศวกรรม", "name_en": "Basic Engineering",
     "min_credits": 11, "fill": "listed", "status": "conflict", "note": "C2"},
    {"id": "CORE", "name_th": "หมวดวิชาแกนระดับสาขาวิชา", "name_en": "Core Courses",
     "min_credits": 40, "fill": "listed", "status": "conflict", "note": "C3"},
    {"id": "CORE_ELECTIVE", "name_th": "วิชาเลือกกลุ่มวิชาแกนระดับสาขาวิชา", "name_en": "Core-Level Electives",
     "min_credits": 6, "fill": "slot_or_listed", "slot_credits": 3,
     "unlisted_options": [{"code": None, "name_en": "Software-Defined Systems I", "name_th": "ระบบที่กำหนดโดยซอฟต์แวร์ 1",
                           "status": "unknown", "note": "C10: code not published (21105xx)"}]},
    {"id": "MULTI_21C", "name_th": "วิชาเลือกกลุ่มสหสาขาวิชาหรือทักษะสำหรับศตวรรษที่ 21",
     "name_en": "Multidisciplinary or 21st-Century Skills Electives", "min_credits": 6, "fill": "slot_or_listed", "slot_credits": 3,
     "unlisted_options": [{"code": None, "name_en": n, "status": "unknown", "note": "C11: code not published"} for n in
                          ("Project Management", "Marketing and Management in Engineering",
                           "Study Abroad for 21 Century Skill I", "Study Abroad for 21 Century Skill II")]},
    {"id": "DEPT_ELECTIVE", "name_th": "วิชาเลือกระดับสาขาวิชา", "name_en": "Department Electives",
     "min_credits": 18, "fill": "slot_or_listed", "slot_credits": 3},
    {"id": "FREE", "name_th": "หมวดวิชาเลือกเสรี", "name_en": "Free Electives", "min_credits": 6, "fill": "slot_or_any", "slot_credits": 3},
]


def plan_items(*items):
    return [{"course": i} if i[0].isdigit() else {"slot": i} for i in items]


study_plan = [
    {"year": 1, "semester": "1", "credits": 16, "items": plan_items("2304103", "2304183", "2301107", "2110101", "2100111", "5500111")},
    {"year": 1, "semester": "2", "credits": 20,
     "items": plan_items("2110215", "2110221", "2301108", "2302127", "2302163", "2304104", "2304184", "5500112")},
    {"year": 2, "semester": "1", "credits": 16, "items": plan_items("2110200", "2110211", "2110251", "2110263", "2603284", "GE")},
    {"year": 2, "semester": "2", "credits": 19,
     "items": plan_items("2110201", "2110313", "2110322", "2110327", "2110352", "2110363", "5500208")},
    {"year": 3, "semester": "1", "credits": 18,
     "items": plan_items("2110203", "2110426", "2110318", "2110366", "2110423", "2110471", "DEPT_ELECTIVE", "GE")},
    {"year": 3, "semester": "2", "credits": 15, "items": plan_items("MULTI_21C", "CORE_ELECTIVE", "DEPT_ELECTIVE", "FREE", "5500308")},
    {"year": 3, "semester": "S", "credits": 2, "items": plan_items("2100301")},
    {"year": 4, "semester": "1", "credits": 17,
     "items": plan_items("2110488", "CORE_ELECTIVE", "DEPT_ELECTIVE", "DEPT_ELECTIVE", "GE", "GE")},
    {"year": 4, "semester": "2", "credits": 15, "items": plan_items("2110489", "MULTI_21C", "DEPT_ELECTIVE", "DEPT_ELECTIVE", "FREE")},
]


def v(value, status, src, loc, note=None):
    return {"value": value, "status": status, "source": src, "location": loc, **({"note": note} if note else {})}


regulations = {
    "max_credits_regular": v(22, "verified", S3, "clause 59(2)(a)"),
    "max_credits_summer": v(9, "verified", S3, "clause 59(2)(a)"),
    "overload": v("more than the limits only with a reason and the dean's approval", "verified", S3, "clause 59, last paragraph"),
    "min_credits_regular": v(None, "unknown", S3, "clause 59", "no minimum is stated for bachelor's students"),
    "graduation_min_gpax": v(2.0, "verified", S3, "graduation requirements for bachelor's degrees"),
    "earned_credit_grades": v(["A", "B+", "B", "C+", "C", "D+", "D", "S"], "verified", S3, "definitions"),
    "gpa_grades": v(["A", "B+", "B", "C+", "C", "D+", "D", "F"], "verified", S3, "definitions"),
    "required_course_retake_grades": v(["F", "U", "W"], "verified", S3, "clause 67(1)"),
    "elective_retake_rule": v("F, U or W in an elective: retake it or take another course instead", "verified", S3, "clause 67(2)"),
    "prereq_satisfied_by": v(["A", "B+", "B", "C+", "C", "D+", "D", "S"], "inferred", S3, "definitions",
                             "assumed: a prerequisite is satisfied by a course with earned credit"),
}
conflicts = [
    {"id": "C1", "topic": "total credits", "values": {"S1 structure table": 141, "S1 stated total and study plan": 138},
     "resolution": 138, "reason": "the structure table repeats the 2561 values (S5); 2566-specific lists and the plan give 138",
     "status": "resolved"},
    {"id": "C2", "topic": "basic engineering credits", "values": {"S1 structure table": 15, "S1 heading": 11, "S1 list incl. 2110233": 12},
     "resolution": 11, "reason": "the 2566 heading and the study plan exclude 2110233", "status": "resolved"},
    {"id": "C3", "topic": "core credits",
     "values": {"S1 structure table": 45, "S1 heading": 40, "S1 list with 2110318 at 3": 42, "S2 legend": 39},
     "resolution": 40, "reason": "heading 40 matches the list with 2110318 at 1 credit, as in the study plan", "status": "resolved"},
    {"id": "C4", "topic": "2110318 credits", "values": {"S1 course list": 3, "S1 study plan": 1, "S2 diagram": 1},
     "resolution": 1, "status": "open"},
    {"id": "C5", "topic": "Exploring Engineering World",
     "values": {"S2 code": "2110111", "S1/S4 code": "2100111", "S1 plan table credits": 1, "S1 GE list, S2, S4 credits": 3},
     "resolution": {"code": "2100111", "credits": 3}, "reason": "semester 1/1 totals 16 only with 3 credits", "status": "resolved"},
    {"id": "C6", "topic": "2110233 Computer Engineering Mathematics Laboratory",
     "values": {"S1 basic-engineering list": "listed", "S1 study plan": "absent"},
     "resolution": "not required; may count as a free elective", "status": "open"},
    {"id": "C7", "topic": "semester 4/1 credits", "values": {"S2 header": 16, "S1 table and S2 items": 17}, "resolution": 17,
     "status": "resolved"},
    {"id": "C8", "topic": "S2 approved-elective code in 4/1", "values": {"S2": "2110101"},
     "resolution": "core-level elective slot (2110101 is Computer Programming)", "status": "resolved"},
    {"id": "C9", "topic": "Senior Project in Engineering code", "values": {"S1 first listing": "2110499", "S1 second listing, S5": "2100499"},
     "resolution": "2100499", "status": "resolved"},
    {"id": "C10", "topic": "Software-Defined Systems I code", "values": {"S1": "21105xx"},
     "resolution": "unknown; NEED_INFO if requested", "status": "open"},
    {"id": "C11", "topic": "21st-century skills course codes", "values": {"S1": "placeholders", "S4": "2100223-2100226 for four of eight"},
     "resolution": "four codes inferred from S4; four unknown", "status": "open"},
    {"id": "C12", "topic": "2100301 credit counting", "values": {"S1 footnote": "S/U, not counted", "S1 plan total": "2 credits included in 138"},
     "resolution": "counted as in the plan total", "status": "open"},
    {"id": "C13", "topic": "Gen-Ed rule for students entering in 2566",
     "values": {"S1": "3 credits per group", "Gen-Ed centre material (unverified)": "12 credits from any group"},
     "resolution": "per-group minimums from S1", "status": "open"},
]
grades = {g: {"earns_credit": g in regulations["earned_credit_grades"]["value"], "in_gpa": g in regulations["gpa_grades"]["value"]}
          for g in ["A", "B+", "B", "C+", "C", "D+", "D", "F", "S", "U", "W"]}
snapshot = {
    "snapshot_id": "cp2566-v0", "schema_version": 1, "built_on": "2026-11-02",
    "program": {"name_th": "หลักสูตรวิศวกรรมศาสตรบัณฑิต สาขาวิชาวิศวกรรมคอมพิวเตอร์ (หลักสูตรปรับปรุง พ.ศ. 2566)",
                "name_en": "Bachelor of Engineering Program in Computer Engineering (revised B.E. 2566)",
                "university": "Chulalongkorn University", "curriculum_year": 2566, "total_credits": 138,
                "regular_terms": 8, "status": "verified", "sources": [S1, S2]},
    "policy": {"identity_data_missing": "NEED_INFO",
               "supplementary_data_missing": "plan, and label the item as unverified (prerequisites, offerings)"},
    "regulations": regulations, "grades": grades, "categories": categories, "courses": dict(sorted(courses.items())),
    "study_plan": study_plan, "conflicts": conflicts, "sources": sources,
}
json.dump(snapshot, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
req = sum(c["credits"] for c in courses.values() if c["kind"] == "required")
print("courses:", len(courses), "| required credits:", req, "| dept electives:", len(dept_electives),
      "| plan total:", sum(t["credits"] for t in study_plan),
      "| category minimums:", sum(c["min_credits"] for c in categories))
