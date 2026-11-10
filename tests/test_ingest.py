"""Anonymized CR60 fixtures; never commit student PDFs or extracted personal headers."""
import io

import pytest
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject

from gradpath.contracts import GoalConstraints
from gradpath.ingest.cr60 import ReportError, earned, parse_pages, read_pdf
from gradpath.rules import standing
from gradpath.runtime.agent import Runtime
from gradpath.runtime.session import Store
from gradpath.snapshot import load
from gradpath.tools.planner import solve
from gradpath.tools.validator import validate

SNAP = load()


def report_pages():
    header = """CHULALONGKORN UNIVERSITY
PAGE {page} / 2
Student ID. 000 00000 00
Name Test Student
Birthdate Jan 01, 2000
Admission Jul 01, 2023
Field of Study Computer Engineering
COURSE NO ABBREVIATED NAME CREDIT GRADE
"""
    return [header.format(page=1) + """1ST SEMESTER 2023
2110101 COMP PROG 3.0 A
0299004 EXTERNAL COURSE 3.0 S
2110211 INTRO DATA STRUCT 3.0 W
CA CG GPA CAX CGX GPAX GPX
3.00 6.00 4.00 3.00 6.00 4.00 12.00
CA = CREDIT ATTEMPTED
Student Grade Report
As of 06 November 2026
""", header.format(page=2) + """2ND SEMESTER 2023
2110211 INTRO DATA STRUCT 3.0 A
3200106 ANOTHER EXTERNAL 3.0 U
CA CG GPA CAX CGX GPAX GPX
3.00 3.00 4.00 6.00 9.00 4.00 24.00
CA = CREDIT ATTEMPTED
Student Grade Report
As of 06 November 2026
"""]


def pdf_bytes(pages=None):
    """Generate an actual text PDF without a third-party fixture or renderer."""
    writer = PdfWriter()
    for text in pages or report_pages():
        page = writer.add_blank_page(width=612, height=792)
        font = DictionaryObject({NameObject('/Type'): NameObject('/Font'),
                                 NameObject('/Subtype'): NameObject('/Type1'),
                                 NameObject('/BaseFont'): NameObject('/Helvetica')})
        page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'): DictionaryObject({NameObject('/F1'): font})})
        content = ['BT /F1 10 Tf 40 750 Td 14 TL']
        for line in text.splitlines():
            escaped = line.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')
            content.append(f'({escaped}) Tj T*')
        content.append('ET')
        stream = DecodedStreamObject()
        stream.set_data('\n'.join(content).encode())
        page[NameObject('/Contents')] = writer._add_object(stream)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


@pytest.fixture
def rt(tmp_path, monkeypatch):
    monkeypatch.setattr('gradpath.runtime.agent._gpu', lambda: 'test')
    monkeypatch.setattr('gradpath.runtime.llm.model_info', lambda *a: {'model': 'scripted'})
    return Runtime(store=Store(tmp_path))


def profile(st):
    return {'entry_year': st.entry_year, 'next_term': st.next_term, 'confirmed': True}


def choices(st):
    return [{'record_index': u.record_index, 'field': u.field,
             'value': 'GE' if u.field == 'category' else u.candidates[0]} for u in st.unresolved]


def test_pdf_roundtrip_preserves_all_attempts_and_leading_zero():
    st = read_pdf(pdf_bytes(), SNAP)
    assert len(st.records) == 5
    assert st.records[1].course_id == '0299004'
    assert [(r.grade, r.term) for r in st.records if r.course_id == '2110211'] == [('W', '2566/1'), ('A', '2566/2')]
    assert st.entry_year == 2566 and st.next_term == '2567/1'
    assert st.report['reported_earned'] == earned(st.records, SNAP) == 9
    assert not st.report['reconciliation_errors']
    assert [(u.record_index, u.field) for u in st.unresolved] == [(1, 'category')]
    assert st.records[3].evidence.page == 2
    assert len(st.source_sha256) == 64
    serialized = st.model_dump_json()
    assert 'Test Student' not in serialized and 'Birthdate' not in serialized and '000 00000 00' not in serialized


@pytest.mark.parametrize('fault', ['missing_page', 'reordered', 'mixed_student', 'unreadable_row', 'fractional', 'scan'])
def test_incomplete_or_unsupported_reports_fail_closed(fault):
    pages = report_pages()
    if fault == 'missing_page': pages = pages[:1]
    if fault == 'reordered': pages.reverse()
    if fault == 'mixed_student': pages[1] = pages[1].replace('000 00000 00', '000 00000 01')
    if fault == 'unreadable_row': pages[0] = pages[0].replace('2110101', '2110?01')
    if fault == 'fractional': pages[0] = pages[0].replace('COMP PROG 3.0', 'COMP PROG 2.5')
    if fault == 'scan': pages[0] = ''
    with pytest.raises(ReportError):
        parse_pages(pages, SNAP, 'test')


def test_non_pdf_and_oversized_uploads():
    with pytest.raises(ReportError): read_pdf(b'not a pdf', SNAP)
    with pytest.raises(ReportError): read_pdf(b'%PDF-' + b'x' * (10 * 1024 * 1024), SNAP)


def test_categories_and_profile_must_be_confirmed_atomically(rt):
    s = rt.create_session(student=read_pdf(pdf_bytes(), SNAP))
    before = s.student.model_dump()
    with pytest.raises(ValueError): rt.record(s.session_id, [], True)
    with pytest.raises(ValueError): rt.record(s.session_id, [], True, profile(s.student))
    assert s.student.model_dump() == before
    rt.record(s.session_id, choices(s.student), True, profile(s.student))
    assert s.student.confirmed and s.student.record_version == 2
    assert standing(SNAP, s.student).completed['2110211'] == 3
    assert rt.view(s)['audit']['earned_credits'] == 9
    goal = GoalConstraints(horizon_end='2569/2')
    result = solve(SNAP, s.student, goal)
    assert result['status'] == 'PLAN'
    assert validate(SNAP, s.student, goal, result['candidate']).valid


def test_mismatched_totals_cannot_be_confirmed(rt):
    pages = report_pages()
    pages[1] = pages[1].replace('6.00 9.00', '6.00 12.00')
    s = rt.create_session(student=parse_pages(pages, SNAP, 'test'))
    assert s.student.report['reconciliation_errors']
    with pytest.raises(ValueError, match='credit mismatches'):
        rt.record(s.session_id, choices(s.student), True, profile(s.student))
    assert not s.student.confirmed


def test_missing_grade_can_be_corrected_and_reconciled(rt):
    pages = report_pages()
    pages[0] = pages[0].replace('EXTERNAL COURSE 3.0 S', 'EXTERNAL COURSE 3.0 ?')
    s = rt.create_session(student=parse_pages(pages, SNAP, 'test'))
    changes = choices(s.student)
    for c in changes:
        if c['field'] == 'grade': c['value'] = 'S'
    rt.record(s.session_id, changes, True, profile(s.student))
    assert s.student.confirmed and not s.student.report['reconciliation_errors']


def test_report_credits_not_silently_overwritten_by_snapshot(rt):
    pages = report_pages()
    pages[0] = pages[0].replace('COMP PROG 3.0', 'COMP PROG 4.0').replace('3.00 6.00 4.00 3.00 6.00', '4.00 7.00 4.00 4.00 7.00')
    pages[1] = pages[1].replace('6.00 9.00', '7.00 10.00')
    s = rt.create_session(student=parse_pages(pages, SNAP, 'test'))
    assert any(u.field == 'credits' for u in s.student.unresolved)
    rt.record(s.session_id, choices(s.student), True, profile(s.student))
    assert standing(SNAP, s.student).completed['2110101'] == 4
    assert rt.view(s)['records'][0]['credits'] == 4


def test_replacement_invalidates_old_plans_goals_and_pending_cards(rt):
    from gradpath.runtime.session import Card
    s = rt.create_session(student=read_pdf(pdf_bytes(), SNAP))
    rt.record(s.session_id, choices(s.student), True, profile(s.student))
    s.goal = GoalConstraints(horizon_end='2569/2', confirmed=True)
    s.final_plan_id = 'old'
    s.add('agent', 'plan', plan={'plan_id': 'old'})
    s.cards.append(Card(card_id='G-old', kind='goal', data={}))
    s.llm_messages.append({'role': 'user', 'content': 'old context'})
    old_version = s.student.record_version
    rt.replace_report(s.session_id, read_pdf(pdf_bytes(), SNAP))
    assert s.student.record_version == old_version + 1 and not s.student.confirmed
    assert s.goal is None and s.final_plan_id is None and not s.llm_messages
    assert next(i for i in s.items if i.kind == 'plan').data['stale'] and s.cards[0].status == 'superseded'
    assert rt.store.load(s.session_id).student.source_kind == 'pdf'


def test_upload_api_stores_pdf_and_rejects_bad_inputs(rt, monkeypatch):
    from fastapi.testclient import TestClient
    from gradpath.api import app as module
    monkeypatch.setattr(module, 'runtime', rt)
    client = TestClient(module.app)
    data = pdf_bytes()
    response = client.post('/api/uploads', files={'file': ('report.pdf', data, 'application/pdf')})
    assert response.status_code == 200, response.text
    view = response.json()
    sid = view['session_id']
    assert view['student']['source_kind'] == 'pdf' and len(view['records']) == 5
    assert 'operator' not in view
    assert client.get(f'/api/sessions/{sid}/report').content == data
    assert client.post('/api/uploads', files={'file': ('bad.pdf', b'bad')}).status_code == 422
    assert client.get('/api/sessions/missing/report').status_code == 404
    lock = rt.lock(sid)
    lock.acquire()
    try:
        assert client.post(f'/api/sessions/{sid}/report', files={'file': ('new.pdf', data)}).status_code == 409
    finally:
        lock.release()
    updated = client.post(f'/api/sessions/{sid}/report', files={'file': ('new.pdf', data)}).json()
    assert updated['student']['record_version'] == 2


def test_interrupted_session_can_be_resumed_after_restart(rt):
    s = rt.create_session(student=read_pdf(pdf_bytes(), SNAP))
    s.busy = True
    rt.store.save(s)
    rt.sessions.clear()
    restored = rt.get(s.session_id)
    assert not restored.busy and restored.outcome == 'STOP_UNVERIFIED'
    assert not rt.store.load(s.session_id).busy


def summer_pages(summer_rows, closing="", trailing=False):
    """One-page report with an S/U-only summer session that CR60 prints without a CA/CG row."""
    head = """CHULALONGKORN UNIVERSITY
PAGE 1 / 1
Student ID. 000 00000 00
Admission Jul 01, 2023
Field of Study Computer Engineering
COURSE NO ABBREVIATED NAME CREDIT GRADE
1ST SEMESTER 2023
2110101 COMP PROG 3.0 A
CA CG GPA CAX CGX GPAX GPX
3.00 3.00 4.00 3.00 3.00 4.00 12.00
SUMMER SESSION 2023
""" + summer_rows + closing
    if not trailing:
        head += """1ST SEMESTER 2024
2110215 PROG METH I 3.0 B
CA CG GPA CAX CGX GPAX GPX
3.00 3.00 3.00 6.00 12.00 3.50 21.00
"""
    return [head + """CA = CREDIT ATTEMPTED
Student Grade Report
As of 06 November 2026
"""]


SU_SUMMER = "3200106 FUND ORAL BIO HLTH 3.0 S\n3700110 GOOD HEALTH 3.0 S\n"


def test_summer_of_s_grades_without_a_summary_row_is_read_and_reconciled():
    st = parse_pages(summer_pages(SU_SUMMER), SNAP, "hash")
    assert st.report["terms_without_summary"] == ["2566/S"]
    assert [r.term for r in st.records].count("2566/S") == 2
    assert st.report["reconciliation_errors"] == []          # the 2567/1 CGX (12) includes the summer S credits
    assert st.report["reported_earned"] == 12


def test_a_trailing_s_only_summer_adds_its_credits_to_the_reported_total():
    st = parse_pages(summer_pages(SU_SUMMER, trailing=True), SNAP, "hash")
    assert st.report["last_term"] == "2566/S" and st.report["reported_earned"] == 3 + 6
    assert st.next_term == "2567/1"


def test_a_letter_graded_term_without_its_summary_is_still_rejected():
    with pytest.raises(ReportError, match="Missing credit summary for 2566/S"):
        parse_pages(summer_pages("2110200 DISCRETE STRUC 3.0 B\n"), SNAP, "hash")
