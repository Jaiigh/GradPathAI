"""Read text-based Chulalongkorn CR60 grade reports, retaining course-row evidence.

Only academic rows and summary values leave this module. Identity headers, national IDs
and birth dates are neither persisted as extracted text nor passed to the model.
"""
from __future__ import annotations

import hashlib
import io
import re
import uuid
from decimal import Decimal

from pypdf import PdfReader

from .. import terms as T
from ..contracts import Evidence, Record, StudentState, UnresolvedField
from ..snapshot import Snapshot

MAX_BYTES = 10 * 1024 * 1024
MAX_PAGES = 20
TERM = re.compile(r"^(1ST|2ND|SUMMER)(?:\s+(?:SEMESTER|SESSION))?\s+(\d{4})$", re.I)
COURSE = re.compile(r"^(\d{7})\s+(.+?)\s+(\d+(?:\.\d+)?)\s*(\S+)?$")
SUMMARY = "CA CG GPA CAX CGX GPAX GPX"


class ReportError(ValueError):
    """A report cannot be imported reliably; the student should supply a complete PDF."""


def earned(records: list[Record], snap: Snapshot) -> int:
    return sum({r.course_id: r.credits or 0 for r in records if snap.earns_credit(r.grade)}.values())


def reconciliation(student: StudentState, snap: Snapshot) -> list[str]:
    """Recompute after corrections, before any confirmation can unlock planning."""
    if not student.report:
        return []
    errors = []
    for summary in student.report["terms"]:
        rs = [r for r in student.records if r.term == summary["term"]]
        granted = sum(r.credits or 0 for r in rs if snap.earns_credit(r.grade))
        if granted != summary["granted"]:
            errors.append(f"{summary['term']}: extracted earned credits {granted}, report CG {summary['granted']}")
        through = [r for r in student.records if T.key(r.term) <= T.key(summary["term"])]
        total = earned(through, snap)
        if total != summary["cumulative_granted"]:
            errors.append(f"{summary['term']}: extracted cumulative credits {total}, report CGX {summary['cumulative_granted']}")
    return errors


def read_pdf(data: bytes, snap: Snapshot) -> StudentState:
    if not data or len(data) > MAX_BYTES:
        raise ReportError("Upload a PDF smaller than 10 MB.")
    if not data.startswith(b"%PDF-"):
        raise ReportError("This file is not a PDF. Upload the original CR60 grade report.")
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise ReportError("Password-protected PDFs are not supported. Upload an unlocked copy.")
        if not 1 <= len(reader.pages) <= MAX_PAGES:
            raise ReportError("The report must contain between 1 and 20 pages.")
        pages = [p.extract_text(extraction_mode="layout") or "" for p in reader.pages]
    except ReportError:
        raise
    except Exception as e:
        raise ReportError("The PDF could not be read. Download a fresh CR60 PDF and try again.") from e
    return parse_pages(pages, snap, hashlib.sha256(data).hexdigest())


def parse_pages(pages: list[str], snap: Snapshot, document_hash: str) -> StudentState:
    """Pure parser, also used with anonymized report fixtures in tests."""
    records, unresolved, summaries = [], [], []
    admissions, identities = set(), set()
    term = None
    term_closed = True
    seen_terms = set()
    seen_rows = set()
    report_date = None
    for page_no, raw in enumerate(pages, 1):
        if not raw.strip():
            raise ReportError(f"Page {page_no} has no readable text. Scanned PDFs need OCR, which is not supported yet.")
        flat = " ".join(raw.split())
        if "CHULALONGKORN" not in flat.upper() or "Student Grade Report" not in flat:
            raise ReportError("Upload a Chulalongkorn CR60 Student Grade Report in the supported English layout.")
        if "Field of Study Computer Engineering" not in flat:
            raise ReportError("Only Computer Engineering (CP 2566) is supported by this build.")
        label = re.search(r"PAGE\s+(\d+)\s*/\s*(\d+)", flat)
        if not label or (int(label[1]), int(label[2])) != (page_no, len(pages)):
            raise ReportError("The report has missing, repeated or reordered pages. Upload the complete PDF.")
        admission = re.search(r"Admission\s+[A-Za-z]+\s+\d{1,2},?\s+(\d{4})", flat)
        if not admission:
            raise ReportError("The admission year could not be read. Upload the original CR60 PDF.")
        admissions.add(int(admission[1]))
        # Used transiently to detect mixed-student pages; never returned or logged.
        identity = re.search(r"Student ID\.?\s*([\d ]{8,20})", raw)
        if identity:
            identities.add(re.sub(r"\s", "", identity[1]))
        date = re.search(r"As of\s+(\d{1,2}\s+[A-Za-z]+\s+\d{4})", flat)
        if date:
            report_date = date[1]
        lines = [" ".join(line.split()) for line in raw.splitlines()]
        in_table = False
        waiting_summary = False
        row_on_page = 0
        for line_no, line in enumerate(lines, 1):
            if not line:
                continue
            if line.startswith("COURSE NO"):
                in_table = True
                continue
            if line.startswith("CA ="):
                in_table = False
            if not in_table:
                continue
            match = TERM.fullmatch(line)
            if match:
                if term is not None and not term_closed:
                    raise ReportError(f"Missing credit summary for {term}.")
                year = int(match[2])
                year = year + 543 if year < 2400 else year
                sem = {"1ST": "1", "2ND": "2", "SUMMER": "S"}[match[1].upper()]
                term = T.label(year, sem)
                if term in seen_terms or (summaries and T.key(term) <= T.key(summaries[-1]["term"])):
                    raise ReportError("Semester sections are repeated or out of order.")
                seen_terms.add(term)
                term_closed = False
                continue
            if line == SUMMARY:
                waiting_summary = True
                continue
            if waiting_summary:
                nums = line.split()
                if len(nums) != 7 or any(not re.fullmatch(r"\d+(?:\.\d+)?", x) for x in nums) or not term:
                    raise ReportError(f"The credit summary on page {page_no} could not be read.")
                vals = list(map(Decimal, nums))
                summaries.append({"term": term, "attempted": float(vals[0]), "granted": float(vals[1]),
                                  "gpa": float(vals[2]), "cumulative_attempted": float(vals[3]),
                                  "cumulative_granted": float(vals[4]), "gpax": float(vals[5]),
                                  "grade_points": float(vals[6]), "page": page_no})
                waiting_summary, term_closed = False, True
                continue
            match = COURSE.fullmatch(line)
            if not match or not term or term_closed:
                raise ReportError(f"An unrecognized coursework row was found on page {page_no}, line {line_no}. Upload a clean CR60 PDF.")
            cid, title, credit_text, grade = match.groups()
            credits = Decimal(credit_text)
            if credits != int(credits) or not 0 <= credits <= 30:
                raise ReportError(f"Unsupported credit value for {cid} on page {page_no}; fractional credits need manual support.")
            if (term, cid) in seen_rows:
                raise ReportError(f"Course {cid} appears twice in {term}; review the original report.")
            seen_rows.add((term, cid))
            row_on_page += 1
            r = Record(course_id=cid, title=title, credits=int(credits), grade=grade, term=term,
                       evidence=Evidence(page=page_no, row=row_on_page, line=line_no, text=line))
            idx = len(records)
            if grade not in snap.data["grades"]:
                unresolved.append(UnresolvedField(record_index=idx, field="grade", reason="Grade is missing or not recognized; check the PDF.", candidates=list(snap.data["grades"])))
            if cid in snap.courses and r.credits != snap.courses[cid]["credits"]:
                unresolved.append(UnresolvedField(record_index=idx, field="credits", reason=f"Report: {r.credits} credits; curriculum: {snap.courses[cid]['credits']}. Confirm the report value.", candidates=[str(r.credits)]))
            records.append(r)
        if waiting_summary:
            raise ReportError(f"Missing credit summary on page {page_no}.")
    if len(admissions) != 1 or len(identities) > 1:
        raise ReportError("The pages appear to belong to different student reports.")
    if not records or not summaries or not term_closed:
        raise ReportError("No complete coursework table was found. Upload the original text-readable CR60 PDF.")
    entry_year = admissions.pop()
    entry_year = entry_year + 543 if entry_year < 2400 else entry_year
    if entry_year < 2566:
        raise ReportError("This admission year predates the supported CP 2566 curriculum.")
    last_term = records[-1].term
    following = T.following(last_term)
    if T.is_summer(following):
        following = T.following(following)
    student = StudentState(student_ref="pdf-" + uuid.uuid4().hex[:12], source_kind="pdf",
                           source_sha256=document_hash, snapshot_id=snap.snapshot_id,
                           entry_year=entry_year, next_term=following, records=records, unresolved=unresolved,
                           report={"format": "CR60", "pages": len(pages), "as_of": report_date,
                                   "last_term": last_term, "terms": summaries,
                                   "reported_earned": summaries[-1]["cumulative_granted"],
                                   "gpax": summaries[-1]["gpax"], "profile_confirmed": False})
    refresh_categories(student, snap)
    student.report["reconciliation_errors"] = reconciliation(student, snap)
    return student


def refresh_categories(student: StudentState, snap: Snapshot):
    """Require explicit placement for every earned course outside the curriculum catalog."""
    existing = {(u.record_index, u.field) for u in student.unresolved}
    for idx, r in enumerate(student.records):
        if ((snap.earns_credit(r.grade) or r.grade not in snap.data["grades"]) and r.course_id not in snap.courses and not r.category
                and (idx, "category") not in existing):
            student.unresolved.append(UnresolvedField(record_index=idx, field="category",
                reason="The report does not state the curriculum category. Confirm it from your course information; do not guess.",
                candidates=snap.slot_categories()))
