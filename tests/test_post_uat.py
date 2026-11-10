"""Post-UAT changes (9 Nov 2026): experiment arms A/B, NEED_INFO next steps (T11), retry after a stop (T09),
record-course questions (T05), course name/code mismatches, reply language and plan reasons. No Ollama needed."""
import json

import pytest

from gradpath.runtime.agent import Runtime
from gradpath.runtime.prompts import SYSTEM_B
from gradpath.runtime.session import Store

from test_runtime import AI, ScriptedLLM, last_obs, start, submit_plan, submit_plan_saying


@pytest.fixture
def make(tmp_path):
    def _make(steps, arm="C"):
        return Runtime(llm=ScriptedLLM(steps), store=Store(tmp_path), arm=arm)
    return _make


def tools_used(s):
    return [t for turn in s.turns for t in turn.tools]


# ---------------------------------------------------------------- arm A: fixed workflow
def test_arm_a_runs_the_fixed_order_and_the_llm_only_drafts_and_explains(make):
    rt = make([[("propose_goal", {"interests": ["AI"]})], "แผนนี้เน้นวิชา AI และจบตามกำหนด"], arm="A")
    s = start(rt)
    rt.message(s.session_id, "ช่วยวางแผนจนจบปี 4 อยากเน้น AI")
    assert s.outcome == "WAIT_USER" and s.pending("goal")
    rt.goal_decision(s.session_id, s.pending("goal").card_id, True)
    assert s.outcome == "DONE"
    assert tools_used(s) == ["propose_goal", "audit", "retrieve_courses", "solve_plan", "validate_plan", "submit_final"]
    assert s.items[-1].text == "แผนนี้เน้นวิชา AI และจบตามกำหนด"
    assert {"2110476", "2110477"} & set(s.plan_preferred[s.final_plan_id])


def test_arm_a_vague_workload_is_a_rule_question_without_a_model_call(make):
    rt = make([[("propose_goal", {"default_cap": 18})], "ok"], arm="A")
    s = start(rt)
    rt.message(s.session_id, "อยากได้แผนเรียนที่ไม่หนักเกินไป")
    assert s.outcome == "WAIT_USER" and s.asked[-1]["fields"] == ["caps"] and s.turns[-1].llm_calls == 0
    rt.message(s.session_id, "เทอมละไม่เกิน 18 หน่วยกิต")
    assert s.pending("goal").data["goal"]["default_cap"] == 18


def test_arm_a_infeasible_goal_ends_with_the_evidenced_blocker(make):
    rt = make([[("propose_goal", {"default_cap": 15})], "15 หน่วยกิตต่อเทอมไม่พอ"], arm="A")
    s = start(rt)
    rt.message(s.session_id, "ขอลงไม่เกินเทอมละ 15 หน่วยกิต")
    rt.goal_decision(s.session_id, s.pending("goal").card_id, True)
    assert s.outcome == "EVIDENCED_BLOCKER" and s.pending("blocker")


def test_arm_a_model_unavailable_stops(make):
    rt = make([], arm="A")
    s = rt.create_session("y3-base", fault="model_unavailable")
    rt.record(s.session_id, [], True)
    rt.message(s.session_id, "ช่วยวางแผนจนจบปี 4")
    assert s.outcome == "STOP_UNVERIFIED" and s.final_plan_id is None


# ---------------------------------------------------------------- arm B: no retrieval
def test_arm_b_has_no_retrieval_tool(make):
    rt = make([[("retrieve_courses", {"query": "AI"})], [("reply", {"kind": "info", "message": "ok"})]], arm="B")
    assert "retrieve_courses" not in [t["function"]["name"] for t in rt.tool_schemas]
    assert "retrieve_courses" not in SYSTEM_B and rt.system == SYSTEM_B
    s = start(rt)
    rt.message(s.session_id, "วิชา AI มีอะไรบ้าง")
    assert "unknown tool" in last_obs(s.llm_messages, "retrieve_courses")["error"] and not s.retrieved


# ---------------------------------------------------------------- UAT findings
def test_a_reply_of_digits_keeps_the_conversation_language(make):
    rt = make([[("ask_user", {"kind": "clarify", "fields": ["caps"], "question": "กี่หน่วยกิต"})],
               [("ask_user", {"kind": "clarify", "fields": ["caps"], "question": "ยืนยันไหม"})]])
    s = start(rt)
    rt.message(s.session_id, "อยากได้แผนที่ไม่หนัก")
    rt.message(s.session_id, "18")
    assert s.lang == "th" and "Thai" in s.llm_messages[-3]["content"]


def test_unpublished_course_need_info_lists_what_is_missing_and_can_plan_the_rest(make):
    rt = make([
        [("retrieve_courses", {"query": "Software-Defined Systems I"})],
        [("ask_user", {"kind": "need_info", "fields": ["must_take"], "question": "ยังไม่มีรหัสวิชานี้"})],
        [("propose_goal", {})],
    ])
    s = start(rt)
    rt.message(s.session_id, "ต้องลงวิชา Software-Defined Systems I ด้วย ช่วยวางแผนจนจบให้หน่อย")
    assert s.outcome == "NEED_INFO"
    steps = s.items[-1]
    assert steps.kind == "next_steps" and steps.data["missing"] == ["Software-Defined Systems I"]
    assert "21105xx" not in steps.text and "ยังไม่ประกาศ" in steps.text and "วางแผนส่วนที่เหลือไปก่อน" in steps.text
    rt.defer_missing(s.session_id)
    assert s.outcome == "WAIT_USER" and s.pending("goal") and "plan the rest now" in s.llm_messages[-1]["content"]
    assert s.pending("goal").data["goal"]["must_take"] == []


def test_defer_falls_back_to_the_default_goal_when_the_draft_is_rejected(make):
    rt = make([
        [("ask_user", {"kind": "need_info", "fields": ["must_take"], "question": "รหัสวิชาคืออะไร"})],
        [("propose_goal", {"interests": ["Software-Defined Systems I"]})],
    ])
    s = start(rt)
    rt.message(s.session_id, "ต้องลงวิชา Software-Defined Systems I")
    assert s.items[-1].data["missing"] == ["Software-Defined Systems I"]        # named, not retrieved
    rt.defer_missing(s.session_id)
    g = s.pending("goal").data["goal"]
    assert g["interests"] == [] and g["must_take"] == [] and s.turns[-1].tools == ["propose_goal"]


def test_defer_needs_a_need_info_outcome(make):
    rt = make([])
    s = start(rt)
    with pytest.raises(ValueError):
        rt.defer_missing(s.session_id)


def test_course_name_next_to_another_courses_code_is_rejected(make):
    rt = make([
        [("propose_goal", {"must_take": ["2110413"]})],
        [("solve_plan", {"preferred_course_ids": []})],
        submit_plan_saying("This plan includes Software-Defined Systems I (2110413)."),
        submit_plan_saying("This plan includes Computer Security (2110413)."),
    ])
    s = start(rt)
    rt.message(s.session_id, "ต้องลง 2110413")
    rt.goal_decision(s.session_id, s.pending("goal").card_id, True)
    assert s.outcome == "DONE" and s.turns[-1].revisions == 1
    assert "2110413 is Computer Security" in json.dumps(last_obs(s.llm_messages[:-2], "submit_final"))


def test_question_about_a_course_already_in_the_record_is_refused(make):
    rt = make([
        [("ask_user", {"kind": "clarify", "fields": ["must_take"], "question": "ต้องการเรียน 2110327 ซ้ำใช่ไหม"})],
        [("propose_goal", {"interests": ["AI"]})],
    ])
    s = start(rt, persona="y3-retake-open")
    rt.message(s.session_id, "จัดแผนสาย AI จนจบปี 4")
    assert "confirmed record" in last_obs(s.llm_messages, "ask_user")["error"]
    assert not s.asked and s.pending("goal")


def test_retry_after_a_planner_timeout_keeps_record_and_goal(make):
    rt = make([
        [("propose_goal", {"interests": ["AI"]})],
        [("solve_plan", {"preferred_course_ids": AI})],
        [("solve_plan", {"preferred_course_ids": AI})],
        submit_plan,
    ])
    s = rt.create_session("y3-base", fault="planner_timeout")
    rt.record(s.session_id, [], True)
    rt.message(s.session_id, "อยากเน้น AI")
    rt.goal_decision(s.session_id, s.pending("goal").card_id, True)
    assert s.outcome == "STOP_UNVERIFIED" and s.items[-1].data["retry"]
    rt.retry(s.session_id, clear_fault=True)
    assert s.outcome == "DONE" and s.goal.goal_version == 1 and s.student.record_version == 1
    with pytest.raises(ValueError):
        rt.retry(s.session_id)


def test_plan_view_gives_a_reason_per_course_and_category_totals(make):
    rt = make([
        [("propose_goal", {"interests": ["AI"]})],
        [("retrieve_courses", {"query": "AI"})],
        [("solve_plan", {"preferred_course_ids": AI})],
        submit_plan,
    ])
    s = start(rt, persona="y3-retake-open")
    rt.message(s.session_id, "อยากเน้น AI")
    rt.goal_decision(s.session_id, s.pending("goal").card_id, True)
    plan = s.items[-1].data["plan"]
    items = {i["course_id"]: i for t in plan["terms"] for i in t["items"] if i.get("course_id")}
    assert "retake" in items["2110327"]["reasons"]
    assert any("interest" in i["reasons"] for i in items.values())
    core = next(c for c in plan["categories"] if c["id"] == "CORE")
    assert core["after"] >= core["min"] > core["before"]


def test_course_title_without_a_code_is_not_an_interest(make):
    rt = make([
        [("propose_goal", {"interests": ["Software-Defined Systems I"]})],
        [("propose_goal", {"interests": ["AI"]})],
    ])
    s = start(rt)
    rt.message(s.session_id, "ต้องการลงวิชา Software-Defined Systems I ให้ได้ อยากเน้น AI ด้วย")
    assert "not a study topic" in json.dumps(last_obs(s.llm_messages[:-2], "propose_goal"))
    assert s.pending("goal").data["goal"]["interests"] == ["AI"]


def test_next_steps_name_a_typed_code_that_is_not_in_the_snapshot(make):
    rt = make([[("ask_user", {"kind": "need_info", "fields": ["must_take"], "question": "รหัสวิชาคืออะไร"})]])
    s = start(rt)
    rt.message(s.session_id, "2110415")
    assert "2110415" in s.items[-1].text and s.items[-1].kind == "next_steps"


def test_a_retake_in_must_take_is_not_a_goal_change(make):
    rt = make([[("propose_goal", {"must_take": ["2110327"], "interests": ["AI"]})]])
    s = start(rt, persona="y3-retake-open")
    rt.message(s.session_id, "ช่วยดูว่าวิชา 2110327 ที่ได้ F ถูกนำกลับมาวางแผนไหม ขอแผนสาย AI")
    assert s.pending("goal").data["goal"]["must_take"] == []
    assert "always planned" in last_obs(s.llm_messages, "propose_goal")["note"]


def test_an_answer_that_double_counts_a_course_is_rejected(make):
    wrong = "วิชา 2110521 นับเป็นวิชาเลือกระดับแกน (CORE_ELECTIVE) และวิชาเลือกของภาค (DEPT_ELECTIVE) ได้ในเวลาเดียวกัน"
    right = "วิชา 2110521 นับได้เพียงหมวดเดียวในแผน: CORE_ELECTIVE หรือ DEPT_ELECTIVE อย่างใดอย่างหนึ่ง"
    rt = make([[("retrieve_courses", {"query": "2110521"})],
               [("reply", {"kind": "info", "message": wrong})],
               [("reply", {"kind": "info", "message": right})]])
    s = start(rt)
    rt.message(s.session_id, "วิชา 2110521 นับเป็นทั้งวิชาเลือกระดับแกนและวิชาเลือกของภาคพร้อมกันได้ไหม")
    assert "one-category rule" in last_obs(s.llm_messages[:-2], "reply")["error"]
    assert s.items[-1].text == right


def test_a_retake_taken_from_the_state_block_is_dropped_before_grounding(make):
    rt = make([[("propose_goal", {"must_take": ["2110327"], "interests": ["AI"]})]])
    s = start(rt, persona="y3-retake-open")
    rt.message(s.session_id, "จากประวัติที่มี ช่วยจัดแผนสาย AI จนจบปี 4 ให้หน่อย")     # the code is never typed
    assert s.pending("goal").data["goal"]["must_take"] == [] and s.turns[-1].tools == ["propose_goal"]


def test_an_interest_the_student_never_stated_is_dropped(make):
    rt = make([[("propose_goal", {"interests": ["AI"]})]])
    s = start(rt)
    rt.message(s.session_id, "ช่วยวางแผนให้หน่อย")
    assert s.pending("goal").data["goal"]["interests"] == []
    assert "did not state" in last_obs(s.llm_messages, "propose_goal")["note"]


@pytest.mark.parametrize("said,topic", [("ชอบปัญญาประดิษฐ์", "AI"), ("อยากไปสาย system ครับ", "systems"),
                                        ("สนใจ machine learning", "AI"), ("I like AI", "AI")])
def test_an_interest_in_the_students_words_is_kept(make, said, topic):
    rt = make([[("propose_goal", {"interests": [topic]})]])
    s = start(rt)
    rt.message(s.session_id, said)
    assert s.pending("goal").data["goal"]["interests"] == [topic]
