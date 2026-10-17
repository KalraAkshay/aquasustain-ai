import json
import logging
import time
from collections import deque
from datetime import datetime, timezone
from threading import Lock
from uuid import uuid4
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from .schemas import CompareRequest, AgentRequest
from .calculator import compare_scenarios
from .evidence import ROOT, load_snapshot, select_candidates, screen, build_claims, catalogue, evidence_observations
from .gemini_client import ai_configured, generate

logging.basicConfig(level=logging.INFO)
log = logging.getLogger('aquasustain')
app = FastAPI(title='AquaSustain AI', version='0.4.0', docs_url=None, redoc_url=None)
app.mount('/static', StaticFiles(directory=ROOT/'app/static'), name='static')
calls, calls_lock = deque(), Lock()

ACTIONS = {
    'verify_unit':'Confirm the parcel and obtain its current official assessment-unit record.',
    'verify_supply':'Verify available supply, reclaimed-water quality and contractual volumes.',
    'validate_cooling':'Validate WUE, seasonal peaks and energy trade-offs with a cooling engineer.',
    'test_quality':'Obtain location-matched water-quality measurements for the intended use.',
    'community_review':'Review competing water uses and consult relevant local stakeholders.',
}


@app.middleware('http')
async def security_headers(request: Request, call_next):
    if request.method == 'POST':
        try:
            if int(request.headers.get('content-length', '0')) > 16384:
                return Response('Request too large', status_code=413)
        except ValueError:
            return Response('Invalid length', status_code=400)
        body = await request.body()
        if len(body) > 16384:
            return Response('Request too large', status_code=413)
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; base-uri 'none'; frame-ancestors 'self' https://console.cloud.google.com https://ssh.cloud.google.com https://*.cloudshell.googleusercontent.com"
    return response


@app.get('/')
def index():
    return FileResponse(ROOT/'app/static/index.html')


@app.get('/health')
def health():
    return {'status':'ok','version':'0.4.0','snapshot_version':load_snapshot().version,
            'ai_configured':ai_configured(),'ai_verified':False}


@app.get('/api/ai/status')
def ai_status():
    import os
    project = os.getenv('GOOGLE_CLOUD_PROJECT') or os.getenv('AQUA_PROJECT_ID')
    model = os.getenv('GEMINI_MODEL') or os.getenv('AQUA_MODEL_ID')
    credentials_found = False
    try:
        import google.auth
        google.auth.default(scopes=['https://www.googleapis.com/auth/cloud-platform'])
        credentials_found = True
    except Exception:
        pass
    return {'configured':ai_configured(), 'credentials_found':credentials_found,
            'model_configured':bool(model), 'project_configured':bool(project),
            'verified':False, 'message':'A successful question response is required to verify model access.'}


@app.get('/api/candidates')
def candidates():
    snap = load_snapshot()
    return {'snapshot_version':snap.version,'checked_at':snap.checked_at,
            'candidates':select_candidates([c.id for c in snap.candidates]),
            'ai_configured':ai_configured()}


@app.get('/api/locations')
def locations():
    return {**catalogue(), 'app_version':'0.4.0', 'ai_configured':ai_configured()}


def limit_model():
    with calls_lock:
        now = time.monotonic()
        while calls and now-calls[0] > 60:
            calls.popleft()
        if len(calls) >= 10:
            raise HTTPException(429, 'AI request limit reached. Wait a minute and retry.')
        calls.append(now)


def run_comparison(req: CompareRequest) -> dict:
    try:
        selected = select_candidates(req.candidate_ids)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    calc = compare_scenarios(req.baseline, req.alternative)
    screening = screen(selected)
    claims = build_claims(selected, calc)
    packet = {'question':req.question,'assumptions':{'baseline':req.baseline.model_dump(),'alternative':req.alternative.model_dump()},
              'candidates':selected,'calculations':calc,'screening':screening,'claims':claims}
    status, narrative = 'not_requested', None
    if req.generate_ai:
        limit_model()
        status, narrative = generate(packet)
    result = {'request_id':str(uuid4()),'created_at':datetime.now(timezone.utc).isoformat(),
              'snapshot_version':load_snapshot().version,'calculation_version':'normalized-year-v1',
              **packet, 'observations':evidence_observations(selected),
              'ai_status':status,'narrative':narrative,'actions':ACTIONS,
              'boundary':'Annual onsite consumption in litres per kWh of IT energy; normalized 365-day year. All design inputs are hypothetical. Reclaimed supply is not verified.'}
    log.info(json.dumps({'event':'comparison','request_id':result['request_id'],'ai_status':status,'candidate_count':len(selected)}))
    return result


@app.post('/api/compare')
def compare(req: CompareRequest):
    return run_comparison(req)


@app.post('/api/brief/download')
def download(req: CompareRequest):
    # Recompute authoritative results. Export never incurs another model request.
    result = run_comparison(req.model_copy(update={'generate_ai':False}))
    c = result['calculations']
    lines = ['# AquaSustain AI water planning brief','',f"Created: {result['created_at']}",f"Evidence snapshot: {result['snapshot_version']}",'',
             '## Scenario assumptions','',result['boundary'],'',
             '| Parameter | Baseline | Alternative |','|---|---:|---:|']
    for key in req.baseline.model_dump():
        lines.append(f'| {key} | {getattr(req.baseline,key)} | {getattr(req.alternative,key)} |')
    lines += ['', '## Modelled results','', '| Measure | Baseline | Alternative |','|---|---:|---:|']
    for key in c['baseline']:
        lines.append(f"| {key} | {c['baseline'][key]:,.4f} | {c['alternative'][key]:,.4f} |")
    percent = 'Not applicable (zero baseline)' if c['reduction_percent'] is None else f"{c['reduction_percent']:.2f}%"
    lines += ['',f"Freshwater reduction: {c['reduction_m3']:,.2f} m³/year ({percent}). Negative reduction means increased demand.",'','## Location evidence','',result['screening']['message']]
    for candidate in result['candidates']:
        lines += ['',f"### {candidate['name']}",candidate['description']]
        context = candidate['resource_evidence']
        stage = context['extraction_stage_percent']
        stage_text = f'{stage:.2f}%' if stage is not None else 'Unavailable or unusable; no risk inference'
        lines += [f"Geography: {candidate['geography_level']}; {candidate['state']}; district {candidate['district'] or 'not applicable'}.",
                  f"{context['geography_level'].title()} context ({context['assessment_year']}): groundwater extraction stage {stage_text}.",
                  'Denominator: annual extractable groundwater resources. This is not site-level water availability.',
                  f"Source: {context['source_url']}#page={context['pdf_page']}",context['source_locator']]
        lines += context['quality_flags']
        unit = candidate['unit_evidence']
        if unit:
            lines += [f"Assessment unit: {unit['unit_name']} ({unit['assessment_year']}); official category {unit['official_category']}. Unit extraction percentage not imported.",f"Source: {unit['source_url']}#page={unit['pdf_page']}",unit['source_locator']]
        else:
            lines += ['Assessment-unit evidence: not imported for this selection. No site risk category assigned.']
    lines += ['', '## Evidence observations', '']+[o['text'] for o in result['observations']]
    lines += ['', '## AI contribution', '', 'Gemini can explain selected evidence, answer questions and identify next investigations. All numbers above were calculated or retrieved by code. Location changes do not automatically change the WUE assumption.']
    lines += ['','## Next checks',''] + [f'- {v}' for v in ACTIONS.values()]
    lines += ['','This export contains reproducible facts and calculations. The interactive Gemini narrative is not included.']
    return Response('\n'.join(lines), media_type='text/markdown', headers={'Content-Disposition':'attachment; filename="AquaSustain_Decision_Brief.md"'})


@app.post('/api/agents/assess')
async def assess(req: AgentRequest):
    from .agents.workflow import generate_plan
    # Reuse validated server arithmetic and curated evidence, with no legacy model call.
    base=run_comparison(CompareRequest.model_validate(req.model_dump(exclude={'task','feedback'})).model_copy(update={'generate_ai':False}))
    limit_model()
    packet={**base,'task':req.task,'feedback':req.feedback}
    workflow=await generate_plan(packet)
    return {**base,**workflow,'task':req.task,'architecture':'adk-coordinator-two-specialists-v1'}
