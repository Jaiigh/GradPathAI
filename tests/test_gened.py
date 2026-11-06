"""Pooled GenEd rules, legacy credits and session migration (D18)."""
import pytest

from gradpath.contracts import GoalConstraints, Record, StudentState
from gradpath.fixtures import load_persona
from gradpath.runtime.agent import Runtime
from gradpath.runtime.session import Card, Store
from gradpath.snapshot import DEFAULT_SNAPSHOT, LEGACY_GENED, load
from gradpath.tools.audit import audit
from gradpath.tools.planner import solve
from gradpath.tools.validator import validate


def test_pooled_gened_and_frozen_snapshot_are_distinct():
    current, original = load(), load('cp2566-v0')
    assert current.snapshot_id == DEFAULT_SNAPSHOT
    assert current.categories['GE']['min_credits'] == 12
    assert not LEGACY_GENED.intersection(current.categories)
    assert LEGACY_GENED <= original.categories.keys() and 'GE' not in original.categories
    assert current.content_hash != original.content_hash
    assert sum(c['min_credits'] for c in current.categories.values()) == 138
    assert current.categories['GE_SPECIAL']['min_credits'] == 6
    assert current.categories['LANG']['min_credits'] == 12


@pytest.mark.parametrize('category', sorted(LEGACY_GENED) + ['GE'])
def test_twelve_credits_in_one_group_satisfy_gened(category):
    snap, st = load(), load_persona('y4-final')
    for r in st.records:
        if r.category in LEGACY_GENED:
            r.category = category
    assert 'GE' not in audit(snap, st)['category_deficits']
    goal = GoalConstraints(horizon_end='2569/2')
    result = solve(snap, st, goal)
    assert result['status'] == 'PLAN'
    plan = result['candidate']
    assert not any(i.slot == 'GE' for t in plan.terms for i in t.items)
    check = validate(snap, st, goal, plan)
    assert check.valid, check.errors
    assert check.category_totals['GE'] == 12


def test_missing_gened_is_planned_and_validator_rejects_shortfall():
    snap, st = load(), load_persona('y4-final')
    st.records.remove(next(r for r in st.records if r.category in LEGACY_GENED))
    st.records.append(Record(course_id='EXTRA-FREE', credits=3, category='FREE', grade='S', term='2569/1'))
    assert audit(snap, st)['category_deficits']['GE'] == 3
    goal = GoalConstraints(horizon_end='2569/2')
    plan = solve(snap, st, goal)['candidate']
    assert sum(i.credits for t in plan.terms for i in t.items if i.slot == 'GE') == 3
    assert validate(snap, st, goal, plan).valid
    for t in plan.terms:
        t.items = [i for i in t.items if i.slot != 'GE']
    plan.plan_hash = plan.compute_hash()
    result = validate(snap, st, goal, plan)
    assert not result.valid and any('category GE:' in e for e in result.errors)


def test_uploaded_session_migrates_once_and_invalidates_old_plan(tmp_path, monkeypatch):
    monkeypatch.setattr('gradpath.runtime.agent._gpu', lambda: 'test')
    monkeypatch.setattr('gradpath.runtime.llm.model_info', lambda *a: {'model': 'scripted'})
    rt = Runtime(store=Store(tmp_path))
    st = load_persona('y4-final')
    st.source_kind, st.confirmed = 'pdf', True
    s = rt.create_session(student=st)
    old_version = s.student.record_version
    s.goal = GoalConstraints(horizon_end='2569/2', confirmed=True)
    s.add('agent', 'plan', plan={'plan_id': 'old'})
    s.final_plan_id = 'old'
    s.cards.append(Card(card_id='X-old', kind='blocker', data={}))
    s.llm_messages.append({'role': 'assistant', 'content': 'Old category requirements'})
    rt.store.save(s)
    rt.sessions.clear()
    migrated = rt.get(s.session_id)
    assert migrated.snapshot_id == migrated.student.snapshot_id == DEFAULT_SNAPSHOT
    assert migrated.student.record_version == old_version + 1
    assert migrated.student.confirmed and migrated.goal.confirmed
    assert not any(r.category in LEGACY_GENED for r in migrated.student.records)
    assert migrated.final_plan_id is None and migrated.items[0].data['stale']
    assert migrated.cards[0].status == 'superseded' and not migrated.llm_messages
    rt.sessions.clear()
    assert rt.get(s.session_id).student.record_version == old_version + 1
    assert rt.create_session(task_id='T01').snapshot_id == 'cp2566-v0'


def test_new_import_picker_exposes_one_gened_option():
    from gradpath.ingest.cr60 import refresh_categories
    snap = load()
    st = StudentState(student_ref='test', snapshot_id=snap.snapshot_id, entry_year=2566, next_term='2569/1',
                      records=[Record(course_id='0299004', credits=3, grade='S', term='2567/1')])
    refresh_categories(st, snap)
    options = st.unresolved[0].candidates
    assert 'GE' in options and not LEGACY_GENED.intersection(options)
