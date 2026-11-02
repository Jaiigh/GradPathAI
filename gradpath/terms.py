"""Term labels: Buddhist-era academic year and semester, e.g. "2569/1", "2569/2", summer "2569/S".

The summer session of academic year Y follows Y/2 and precedes (Y+1)/1.
"""
from __future__ import annotations

import re

SEMESTERS = ("1", "2", "S")
_LABEL = re.compile(r"^(\d{4})/([12S])$")


def parse(label: str) -> tuple[int, str]:
    m = _LABEL.match(label.strip())
    if not m:
        raise ValueError(f"bad term label {label!r}; expected e.g. 2569/1, 2569/2 or 2569/S")
    return int(m.group(1)), m.group(2)


def key(label: str) -> tuple[int, int]:
    year, sem = parse(label)
    return year, SEMESTERS.index(sem)


def label(year: int, sem: str) -> str:
    return f"{year}/{sem}"


def following(term: str) -> str:
    year, sem = parse(term)
    return label(year, "2") if sem == "1" else label(year, "S") if sem == "2" else label(year + 1, "1")


def span(first: str, last: str) -> list[str]:
    """All terms from first to last inclusive, summers included."""
    if key(first) > key(last):
        return []
    out, t = [first], first
    while t != last:
        t = following(t)
        out.append(t)
    return out


def study_year(term: str, entry_year: int) -> int:
    return parse(term)[0] - entry_year + 1


def end_of_year4(entry_year: int) -> str:
    return label(entry_year + 3, "2")


def semester(term: str) -> str:
    return parse(term)[1]


def is_summer(term: str) -> bool:
    return semester(term) == "S"
