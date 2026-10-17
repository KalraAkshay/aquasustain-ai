import copy
import json
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from app.main import app, calls
from app.schemas import Scenario, Snapshot
from app.calculator import calculate, compare_scenarios
from app.evidence import ROOT, screen, load_snapshot, select_candidates, catalogue
from app.gemini_client import validate_narrative

client=TestClient(app)


def test_golden_case():
    r=compare_scenarios(Scenario(),Scenario(wue_l_per_kwh=.6,reclaimed_share=.5))
    assert r['baseline']['freshwater_m3']==168192
    assert r['alternative']['freshwater_m3']==42048
    assert r['baseline']['freshwater_mld']==.4608
    assert r['reduction_m3']==126144
    assert r['reduction_percent']==75


@pytest.mark.parametrize('kwargs',[{'load_factor':0},{'load_factor':1.1},{'reclaimed_share':1.1},{'wue_l_per_kwh':-1},{'it_capacity_mw':0},{'wue_l_per_kwh':float('nan')},{'it_capacity_mw':float('inf')}])
def test_reject_invalid(kwargs):
    with pytest.raises(ValidationError): Scenario(**kwargs)


def test_zero_and_worse_alternative():
    r=compare_scenarios(Scenario(wue_l_per_kwh=0),Scenario())
    assert r['reduction_percent'] is None
    assert r['reduction_m3']<0
    assert calculate(Scenario(reclaimed_share=1))['freshwater_m3']==0


def test_mass_balance():
    for share in [0,.1,.33,.5,1]:
        r=calculate(Scenario(reclaimed_share=share))
        assert r['freshwater_m3']+r['reclaimed_water_m3']==pytest.approx(r['onsite_water_m3'])


def test_national_coverage():
    r=client.get('/api/locations').json()
    assert r['coverage']=={'states':36,'districts':709,'assessment_units':14,'unavailable_district_stages':3}
    assert len(r['locations'])==759
    assert {s['id'] for s in r['states']}=={c['state_id'] for c in r['locations']}


@pytest.mark.parametrize('state',[s.id for s in load_snapshot().states])
def test_every_state_comparison_api(state):
    r=client.post('/api/compare',json={'candidate_ids':['state-'+state]})
    assert r.status_code==200
    assert r.json()['candidates'][0]['geography_level']=='state'
    assert r.json()['calculations']['baseline']['freshwater_m3']==168192


def test_ludhiana_district_value_and_provenance():
    r=client.post('/api/compare',json={'candidate_ids':['punjab-ludhiana']}).json()
    e=r['candidates'][0]['resource_evidence']
    assert e['extraction_stage_percent']==194.65
    assert e['annual_extractable_m3']==1233654000
    assert e['pdf_page']==193
    assert 'district' in r['observations'][0]['text']
    assert 'official_category' not in e


def test_district_comparison_does_not_change_design_water():
    r=client.post('/api/compare',json={'candidate_ids':['punjab-ludhiana','maharashtra-pune']}).json()
    assert r['screening']['ranking']==['maharashtra-pune','punjab-ludhiana']
    assert r['calculations']['baseline']['freshwater_m3']==168192
    assert r['candidates'][1]['resource_evidence']['extraction_stage_percent']==63.23


def test_missing_evidence_cannot_rank():
    r=client.post('/api/compare',json={'candidate_ids':['tamil-nadu-nagapattinam','punjab-ludhiana']}).json()
    assert r['screening']['ranking']==[]
    assert r['screening']['status']=='insufficient_evidence'
    assert r['candidates'][0]['resource_evidence']['extraction_stage_percent'] is None


def test_mixed_years_and_mixed_geography():
    items=select_candidates(['punjab-ludhiana','maharashtra-pune'])
    items[0]['resource_evidence']['assessment_year']=2024
    assert screen(items)['status']=='mixed_years'
    assert screen(select_candidates(['punjab-ludhiana','state-punjab']))['status']=='mixed_geography'


def test_unit_category_never_inherits_district_percentage():
    r=client.post('/api/compare',json={'candidate_ids':['punjab-ludhiana-unit-ludhiana-city']}).json()
    c=r['candidates'][0]
    assert c['unit_evidence']['official_category']=='Over-exploited'
    assert c['unit_evidence']['extraction_stage_percent'] is None
    assert c['resource_evidence']['geography_level']=='district'
    assert r['screening']['status']=='category_only'
    assert 'punjab-ludhiana-unit-ludhiana-city.district_context' in r['claims']
    assert 'punjab-ludhiana-unit-ludhiana-city.unit_category' in r['claims']


@pytest.mark.parametrize('body',[{'candidate_ids':['unknown']},{'candidate_ids':[]},{'candidate_ids':['punjab-ludhiana','punjab-ludhiana']},{'candidate_ids':['punjab-ludhiana'],'question':'x'*1001},{'candidate_ids':['state-punjab','state-goa','state-delhi','state-bihar']}])
def test_invalid_requests(body):
    assert client.post('/api/compare',json=body).status_code==422


def test_ai_not_configured(monkeypatch):
    for name in ['GOOGLE_CLOUD_PROJECT','GEMINI_MODEL','AQUA_PROJECT_ID','AQUA_MODEL_ID']:monkeypatch.delenv(name,raising=False)
    calls.clear()
    r=client.post('/api/compare',json={'candidate_ids':['punjab-ludhiana'],'generate_ai':True}).json()
    assert r['ai_status']=='not_configured'
    assert r['narrative'] is None
    assert r['calculations']['baseline']['freshwater_m3']==168192


def test_reject_fabricated_reference():
    payload={'summary':'Example','findings':[{'text':'Example','claim_keys':['invented']}],'tradeoffs':[],'next_steps':[],'missing_evidence':[]}
    with pytest.raises(ValueError): validate_narrative(json.dumps(payload),{'claims':{}})


def test_export_recomputes_and_has_national_evidence():
    r=client.post('/api/brief/download',json={'candidate_ids':['punjab-ludhiana'],'generate_ai':True})
    assert r.status_code==200
    assert '168,192.0000' in r.text
    assert '194.65%' in r.text
    assert '#page=193' in r.text
    assert 'District context' in r.text
    assert 'attachment' in r.headers['content-disposition']


def test_unit_export_labels_missing_percentage():
    r=client.post('/api/brief/download',json={'candidate_ids':['punjab-ludhiana-unit-doraha']})
    assert 'Unit extraction percentage not imported' in r.text
    assert 'None%' not in r.text


def test_ui_and_health():
    assert client.get('/').status_code==200
    assert 'state-select' in client.get('/').text
    assert client.get('/static/app.js').status_code==200
    assert client.get('/health').json()['version']=='0.4.0'
    assert 'frame-ancestors' in client.get('/').headers['content-security-policy']


def test_model_rate_limit(monkeypatch):
    calls.clear()
    monkeypatch.setattr('app.main.generate',lambda packet:('not_configured',None))
    for _ in range(10):
        assert client.post('/api/compare',json={'candidate_ids':['punjab-ludhiana'],'generate_ai':True}).status_code==200
    assert client.post('/api/compare',json={'candidate_ids':['punjab-ludhiana'],'generate_ai':True}).status_code==429
    calls.clear()


def test_snapshot_integrity():
    s=load_snapshot().model_dump();s['states'][0]['district_count']=999
    with pytest.raises(ValidationError):Snapshot.model_validate(s)


def test_body_limit():
    assert client.post('/api/compare',content='x'*17000,headers={'Content-Type':'application/json'}).status_code==413


def test_all_district_extraction_ratios_and_state_totals():
    snapshot=load_snapshot()
    for state in snapshot.states:
        districts=[c for c in snapshot.candidates if c.state_id==state.id and c.geography_level=='district']
        for metric in ['annual_extractable_m3','annual_extraction_m3']:
            total=sum(getattr(c.resource_evidence,metric) or 0 for c in districts)
            # State table is rounded to 0.01 bcm, equivalent to 10 million m3.
            assert abs(total-getattr(state.evidence,metric))<=5_100_000
        for c in districts:
            e=c.resource_evidence
            if e.extraction_stage_percent is not None:
                assert abs(e.annual_extraction_m3/e.annual_extractable_m3*100-e.extraction_stage_percent)<.12


def test_html_js_ids_match():
    import re
    from pathlib import Path
    root=Path(__file__).resolve().parents[1]/'app/static'
    html=(root/'index.html').read_text();js=(root/'app.js').read_text()
    ids=re.findall(r'id="([^"]+)"',html)
    assert len(ids)==len(set(ids))
    assert set(re.findall(r"\$\('([^']+)'\)",js))<=set(ids)


def test_map_matches_all_states():
    import xml.etree.ElementTree as ET
    tree=ET.parse(ROOT/'app/static/india-map.svg')
    ids={n.attrib['data-state'] for n in tree.iter() if 'data-state' in n.attrib}
    assert ids=={s.id for s in load_snapshot().states}
    assert len(ids)==36


def test_release_assets_and_cloud_shell_embedding():
    r=client.get('/')
    assert '/static/app.js?v=0.4.0' in r.text
    assert '/static/styles.css?v=0.4.0' in r.text
    assert client.get('/api/locations').json()['app_version']=='0.4.0'
    assert 'https://console.cloud.google.com' in r.headers['content-security-policy']
    assert client.get('/static/india-map.svg').status_code==200


def test_ai_status_does_not_expose_credentials(monkeypatch):
    import google.auth
    monkeypatch.setenv('GOOGLE_CLOUD_PROJECT','private-project')
    monkeypatch.setenv('GEMINI_MODEL','private-model')
    monkeypatch.setattr(google.auth,'default',lambda **kw:(object(),'private-project'))
    r=client.get('/api/ai/status').json()
    assert r['configured'] and r['credentials_found'] and r['verified'] is False
    assert 'private-project' not in str(r) and 'private-model' not in str(r)
