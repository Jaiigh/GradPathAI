import pytest

from gradpath.contracts import GoalConstraints, Record
from gradpath.fixtures import load_persona
from gradpath.rules import standing, internship_info
from gradpath.runtime.agent import Runtime
from gradpath.runtime.session import Store
from gradpath.snapshot import load
from gradpath.tools.planner import solve, diagnose
from gradpath.tools.validator import validate


def student(next_term='2569/1'):
    st = load_persona('y4-final')
    st.snapshot_id = load().snapshot_id
    st.entry_year, st.next_term = 2566, next_term
    st.records = [r for r in st.records if r.course_id != '2100301']
    return st


def test_missing_after_fixed_summer_requires_info_not_extension():
    st = student()
    snap = load()
    for end in ['2569/2', '2570/2', '2572/2']:
        goal = GoalConstraints(horizon_end=end, allow_summer=True)
        assert solve(snap, st, goal)['status'] == 'NEED_INFO'
        assert not diagnose(snap, st, goal).get('alternatives')
    st.internship_completed = True
    plan = solve(snap, st, GoalConstraints(horizon_end='2569/2'))['candidate']
    assert not any(i.course_id == '2100301' for t in plan.terms for i in t.items)
    assert validate(snap, st, GoalConstraints(horizon_end='2569/2'), plan).valid


@pytest.mark.parametrize('next_term', ['2568/1', '2568/S'])
def test_mandatory_summer_is_fixed_even_without_optional_summer_consent(next_term):
    st, snap = student(next_term), load()
    goal = GoalConstraints(horizon_end='2570/2', allow_summer=False)
    plan = solve(snap, st, goal)['candidate']
    items = [(t, i) for t in plan.terms for i in t.items if i.course_id == '2100301']
    assert len(items) == 1
    term, item = items[0]
    assert term.term == '2568/S' and 'fixed_year3_summer' in item.flags
    assert validate(snap, st, goal, plan).valid
    term.items.remove(item)
    next(t for t in plan.terms if t.term == '2569/S').items.append(item)
    plan.plan_hash = plan.compute_hash()
    assert any('cannot move term' in e for e in validate(snap, st, goal, plan).errors)


def test_attestation_separate_from_report_and_no_double_count():
    st, snap = student(), load()
    st.report = {'reported_earned': 113, 'gpax': 3.53}
    original = st.model_dump()
    st.internship_completed = True
    assert standing(snap, st).completed['2100301'] == 2
    assert st.records == student().records and st.report == original['report']
    assert internship_info(snap, st)['supplemental_credits'] == 2
    st.records.append(Record(course_id='2100301', credits=2, grade='S', term='2568/S'))
    assert internship_info(snap, st)['supplemental_credits'] == 0
    assert standing(snap, st).completed['2100301'] == 2
    assert '2100301' not in standing(load('cp2566-v0'), student()).completed


def test_confirmation_persists_can_revoke_and_invalidates_plan(tmp_path, monkeypatch):
    monkeypatch.setattr('gradpath.runtime.agent._gpu', lambda: 'test')
    monkeypatch.setattr('gradpath.runtime.llm.model_info', lambda *a: {'model': 'scripted'})
    rt = Runtime(store=Store(tmp_path))
    s = rt.create_session(student=student())
    s.add('agent', 'plan', plan={'plan_id': 'old'})
    s.final_plan_id = 'old'
    rt.internship_decision(s.session_id, True)
    assert s.items[0].data['stale'] and s.final_plan_id is None
    rt.sessions.clear()
    s = rt.get(s.session_id)
    assert s.student.internship_completed
    rt.internship_decision(s.session_id, False)
    s.student.confirmed = True
    rt.message(s.session_id, 'วางแผนให้หน่อย')
    assert s.outcome == 'NEED_INFO'
    s.student.next_term = '2568/2'
    with pytest.raises(ValueError):
        rt.internship_decision(s.session_id, True)


def test_existing_gened_upload_migrates_without_assuming_completion(tmp_path, monkeypatch):
    monkeypatch.setattr('gradpath.runtime.agent._gpu', lambda: 'test')
    monkeypatch.setattr('gradpath.runtime.llm.model_info', lambda *a: {'model': 'scripted'})
    rt = Runtime(store=Store(tmp_path))
    st = student()
    st.source_kind, st.snapshot_id = 'pdf', 'cp2566-gened-v1'
    s = rt.create_session(student=st)
    version = s.student.record_version
    rt.sessions.clear()
    restored = rt.get(s.session_id)
    assert restored.snapshot_id == load().snapshot_id
    assert restored.student.record_version == version + 1
    assert not restored.student.internship_completed
    assert rt.view(restored)['internship']['needs_review']
    rt.sessions.clear()
    assert rt.get(s.session_id).student.record_version == version + 1
