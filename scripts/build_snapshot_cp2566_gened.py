"""Build the pooled GenEd revision without changing the frozen UAT snapshot.

Run from the repository root: python scripts/build_snapshot_cp2566_gened.py
The rule change comes from the project owner's instruction on 7 Nov 2026 (D18).
"""
import json
from pathlib import Path

root = Path(__file__).resolve().parent.parent
folder = root / "data" / "snapshots"
data = json.loads((folder / "cp2566-v0.json").read_text(encoding="utf-8"))
legacy = {"GE_SOC", "GE_HUM", "GE_INTER", "GE_SCI"}
data.update(snapshot_id="cp2566-gened-v1", built_on="2026-11-07")
data["categories"] = [{
    "id": "GE", "name_th": "กลุ่มวิชาศึกษาทั่วไป GenEd", "name_en": "General Education (GenEd)",
    "min_credits": 12, "fill": "slot", "slot_credits": 3,
    "sources": ["U1"], "note": "Pooled requirement; no minimum for individual subject groups (D18).",
}] + [c for c in data["categories"] if c["id"] not in legacy]
data["policy"]["gened"] = {"category": "GE", "min_credits": 12,
                           "legacy_categories": sorted(legacy), "source": "U1"}
data["sources"].append({"id": "U1", "type": "project_decision", "date": "2026-11-07",
                        "title": "Project owner instruction: combine the four GenEd groups into 12 credits",
                        "reference": "docs/decisions.md#d18-pooled-general-education-credits"})
for conflict in data["conflicts"]:
    if conflict["id"] == "C13":
        conflict.update(status="resolved", resolution="Use a pooled 12-credit GenEd requirement per U1 / D18.")
target = folder / f"{data['snapshot_id']}.json"
target.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"Built {target.name}: GenEd 12 credits; total {sum(c['min_credits'] for c in data['categories'])} credits")
