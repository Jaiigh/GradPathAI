"""Build D19 on top of the preserved D18 snapshot."""
import json
from pathlib import Path

folder = Path(__file__).resolve().parent.parent / 'data' / 'snapshots'
data = json.loads((folder / 'cp2566-gened-v1.json').read_text())
data['snapshot_id'] = 'cp2566-internship-v2'
data['policy']['internship'] = {'course_id': '2100301', 'year': 3, 'semester': 'S', 'source': 'U2'}
data['sources'].append({'id': 'U2', 'type': 'project_decision', 'date': '2026-11-07',
                        'title': 'Owner instruction: Engineering Practice only in Year 3 summer; explicit supplemental completion confirmation'})
(folder / 'cp2566-internship-v2.json').write_text(json.dumps(data, ensure_ascii=False, indent=1))
