#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.schemas import Snapshot

path = Path(sys.argv[1]) if len(sys.argv)>1 else Path(__file__).resolve().parents[1]/'data/evidence_snapshot.json'
snapshot = Snapshot.model_validate_json(path.read_text())
print(f'{snapshot.version}: {len(snapshot.states)} states/UTs, {sum(c.geography_level == "district" for c in snapshot.candidates)} districts, {sum(c.unit_evidence is not None for c in snapshot.candidates)} unit records')
for candidate in snapshot.candidates:
    if candidate.geography_level == 'district' and candidate.resource_evidence.extraction_stage_percent is None:
        print(f'{candidate.name}: unusable source stage; excluded from ranking')
