import os
from functools import lru_cache
from pathlib import Path
from .schemas import Snapshot

ROOT = Path(__file__).resolve().parents[1]


@lru_cache(maxsize=1)
def load_snapshot() -> Snapshot:
    uri = os.getenv('EVIDENCE_GCS_URI', '')
    if uri:
        if not uri.startswith('gs://') or '/' not in uri[5:]:
            raise RuntimeError('EVIDENCE_GCS_URI must identify a gs://bucket/object snapshot.')
        from google.cloud import storage
        bucket, name = uri[5:].split('/', 1)
        raw = storage.Client().bucket(bucket).blob(name).download_as_bytes(timeout=20)
    else:
        raw = (ROOT / 'data/evidence_snapshot.json').read_bytes()
    return Snapshot.model_validate_json(raw)


@lru_cache(maxsize=1)
def candidate_index():
    return {c.id:c for c in load_snapshot().candidates}


def select_candidates(ids: list[str]) -> list[dict]:
    by_id=candidate_index()
    unknown=set(ids)-by_id.keys()
    if unknown:
        raise ValueError('Unknown candidate: '+', '.join(sorted(unknown)))
    return [by_id[i].model_dump() for i in ids]


def catalogue():
    snap=load_snapshot()
    return {'snapshot_version':snap.version,'checked_at':snap.checked_at,
        'coverage':{'states':len(snap.states),'districts':sum(s.district_count for s in snap.states),
                    'assessment_units':sum(c.geography_level=='assessment_unit' for c in snap.candidates),
                    'unavailable_district_stages':sum(c.geography_level=='district' and c.resource_evidence.extraction_stage_percent is None for c in snap.candidates)},
        'coverage_note':snap.source_manifest['coverage_note'],
        'states':[{'id':s.id,'name':s.name,'district_count':s.district_count} for s in sorted(snap.states,key=lambda s:s.name)],
        'locations':[{'id':c.id,'name':c.name,'state_id':c.state_id,'district':c.district,'geography_level':c.geography_level} for c in snap.candidates]}


def screen(candidates: list[dict]) -> dict:
    scopes={c['geography_level'] for c in candidates}
    if len(scopes)!=1:
        return {'status':'mixed_geography','ranking':[], 'message':'Selected records use different geographic levels. Review them separately; no automatic ranking is provided.'}
    level=candidates[0]['geography_level']
    if level=='assessment_unit':
        units=[c['unit_evidence'] for c in candidates]
        if not all(units):
            return {'status':'insufficient_evidence','ranking':[], 'message':'Assessment-unit evidence is missing.'}
        return {'status':'category_only','ranking':[], 'message':'Published assessment-unit categories are available. No unit-specific extraction percentages were imported. The district percentage is not a percentage for these units.'}
    evidence=[c['resource_evidence'] for c in candidates]
    if len({e['assessment_year'] for e in evidence})!=1:
        return {'status':'mixed_years','ranking':[], 'message':'Assessment years differ; no automatic ranking is provided.'}
    if any(e['extraction_stage_percent'] is None or e['quality_flags'] for e in evidence):
        return {'status':'insufficient_evidence','ranking':[], 'message':'At least one selected record has missing or unusable data. No automatic ranking is provided; a printed zero is not treated as low risk.'}
    if len(candidates)<2:
        return {'status':'single_candidate','ranking':[], 'message':f'Review the published {level}-level extraction stage below. Add another {level} to compare regional extraction pressure.'}
    ordered=sorted(candidates,key=lambda c:c['resource_evidence']['extraction_stage_percent'])
    return {'status':'comparable','ranking':[c['id'] for c in ordered],
        'message':f'Ordered by reported {level}-level extraction stage for the same assessment year. Ties have no preference. This is regional screening, not a site approval or an allocation of water.'}


def build_claims(candidates: list[dict], calculations: dict) -> dict:
    claims={}
    for name in ['baseline','alternative']:
        for key,value in calculations[name].items():
            claims[f'{name}.{key}']={'value':value,'kind':'modelled','source_id':None}
    for key in ['reduction_m3','reduction_percent']:
        claims[f'delta.{key}']={'value':calculations[key],'kind':'modelled','source_id':None}
    for c in candidates:
        r=c['resource_evidence']
        claims[f"{c['id']}.{r['geography_level']}_context"]={'value':r,'kind':r['geography_level']+'_aggregate','source_id':r['evidence_id']}
        if c['unit_evidence']:
            u=c['unit_evidence']
            claims[f"{c['id']}.unit_category"]={'value':u,'kind':'assessment_unit_category','source_id':u['evidence_id']}
    return claims


def evidence_observations(candidates: list[dict]) -> list[dict]:
    observations=[]
    for c in candidates:
        e=c['resource_evidence'];stage=e['extraction_stage_percent'];level=e['geography_level']
        if c['unit_evidence']:
            text=f"{c['name']} has the published 2025 assessment-unit category {c['unit_evidence']['official_category']}. Obtain site-specific supply evidence before planning groundwater reliance."
        elif stage is None:
            text=f"{c['name']}: usable extraction-stage evidence is missing. Obtain a current local assessment."
        elif stage>100:
            text=f"{c['name']}: published {level}-level extraction is {stage:.2f}% of annual extractable groundwater resources. Total extraction exceeds that resource estimate; investigate supply options and local competing uses."
        else:
            text=f"{c['name']}: published {level}-level extraction is {stage:.2f}% of annual extractable groundwater resources. This aggregate does not establish spare supply at a proposed site."
        observations.append({'candidate_id':c['id'],'text':text,'basis':'Rule-based reading of published evidence; not generated by AI.'})
    return observations
