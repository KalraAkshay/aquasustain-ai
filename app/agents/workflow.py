import asyncio
import json
import logging
import os
import time
from uuid import uuid4
from functools import cached_property
from google import genai
from google.adk.agents import LlmAgent
from google.adk.models.google_llm import Gemini
from google.adk.runners import Runner
from google.adk.agents.run_config import RunConfig
from google.adk.sessions import InMemorySessionService
from google.adk.tools.agent_tool import AgentTool
from google.genai import types
from ..evidence import ROOT
from ..gemini_client import ai_configured, validate_narrative
from ..schemas import AgentPlan

log = logging.getLogger('aquasustain')


class VertexGemini(Gemini):
    @cached_property
    def api_client(self):
        return genai.Client(vertexai=True,
            project=os.getenv('GOOGLE_CLOUD_PROJECT') or os.getenv('AQUA_PROJECT_ID'),
            location=os.getenv('GEMINI_LOCATION') or os.getenv('AQUA_MODEL_LOCATION','global'),
            http_options=types.HttpOptions(timeout=60000,retry_options=types.HttpRetryOptions(attempts=1)))


def build_agents(packet, trace, model=None):
    """Fresh instances and immutable request-scoped data; no cross-user state."""
    started = time.monotonic()
    counts = {}
    def record(actor, event):
        trace.append({'actor':actor,'event':event,'elapsed_seconds':round(time.monotonic()-started,2)})

    def retrieve_environmental_evidence() -> dict:
        """Retrieve official groundwater snapshot records for the user's selected locations. No live web browsing."""
        record('retrieve_environmental_evidence','tool_completed')
        return {'candidates':packet['candidates'],'screening':packet['screening'],
                'claims':{k:v for k,v in packet['claims'].items() if v.get('kind')!='modelled'},
                'coverage':'Published groundwater snapshot only. No fish mortality, marine, soil, air or water-quality observations supplied.'}

    def compare_water_scenarios() -> dict:
        """Return server-computed water scenarios for the exact user inputs. Values cannot be changed by the model."""
        if packet['task']=='full' and not any(t['actor']=='retrieve_environmental_evidence' for t in trace):
            raise ValueError('Evidence must be retrieved before planning a full assessment.')
        record('compare_water_scenarios','tool_completed')
        return {'assumptions':packet['assumptions'],'calculations':packet['calculations'],
                'claims':{k:v for k,v in packet['claims'].items() if v.get('kind')=='modelled'},
                'boundary':'Hypothetical onsite consumption. No verified reclaimed supply or achieved savings.'}

    def before(callback_context):
        name=callback_context.agent_name
        counts[name]=counts.get(name,0)+1
        if counts[name]>1:
            raise ValueError('Repeated specialist invocation blocked; start a new assessment instead.')
        record(name,'agent_started')
    def after(callback_context):
        record(callback_context.agent_name,'agent_completed')

    if model is None:
        model=VertexGemini(model=os.getenv('GEMINI_MODEL') or os.getenv('AQUA_MODEL_ID'),
            retry_options=types.HttpRetryOptions(attempts=1))
    config=types.GenerateContentConfig(temperature=.1,max_output_tokens=8192)
    common=(ROOT/'prompts/agent_common.txt').read_text()
    evidence=LlmAgent(name='environmental_evidence_agent',model=model,
        description='Official groundwater evidence, provenance, community-impact evidence gaps.',
        instruction=common+'\n'+(ROOT/'prompts/evidence_agent.txt').read_text(),
        tools=[retrieve_environmental_evidence],generate_content_config=config,
        before_agent_callback=before,after_agent_callback=after)
    solutions=LlmAgent(name='water_solutions_agent',model=model,
        description='Calculated design comparison and proposed community water stewardship actions.',
        instruction=common+'\n'+(ROOT/'prompts/solutions_agent.txt').read_text(),
        tools=[compare_water_scenarios],generate_content_config=config,
        before_agent_callback=before,after_agent_callback=after)
    root=LlmAgent(name='aquasustain_coordinator',model=model,
        instruction=common+'\n'+(ROOT/'prompts/coordinator.txt').read_text()+'\nFINAL JSON SCHEMA:\n'+json.dumps(AgentPlan.model_json_schema()),
        tools=[AgentTool(agent=evidence),AgentTool(agent=solutions)],generate_content_config=config,
        before_agent_callback=before,after_agent_callback=after)
    return root


def validate_plan(raw, packet, trace):
    # Accept a single JSON fence, but never repair truncated JSON or invent fields.
    text=raw.strip()
    if text.startswith('```json') and text.endswith('```'):
        text=text[7:-3].strip()
    plan=AgentPlan.model_validate_json(text)
    base=plan.model_dump(exclude={'action_plan','feedback_response'})
    validate_narrative(json.dumps(base),packet)
    completed={t['actor'] for t in trace if t['event']=='tool_completed'}
    required={'evidence':{'retrieve_environmental_evidence'},'design':{'compare_water_scenarios'},
              'full':{'retrieve_environmental_evidence','compare_water_scenarios'}}[packet['task']]
    if required!=completed:
        raise ValueError('Required specialist tool route was not followed.')
    for finding in plan.findings:
        for key in finding.claim_keys:
            if packet['claims'][key].get('kind')=='modelled' and 'compare_water_scenarios' not in completed:
                raise ValueError('Calculation claim without calculator execution.')
            if packet['claims'][key].get('kind')!='modelled' and 'retrieve_environmental_evidence' not in completed:
                raise ValueError('Official claim without evidence retrieval.')
    if packet['task']!='evidence' and not plan.action_plan:
        raise ValueError('An action plan is required for design/full requests.')
    return plan.model_dump()


async def execute(packet, trace, model=None):
    root=build_agents(packet,trace,model)
    service=InMemorySessionService()
    session=await service.create_session(app_name='aquasustain',user_id='request',session_id=str(uuid4()))
    runner=Runner(agent=root,app_name='aquasustain',session_service=service)
    final=''
    try:
        async for event in runner.run_async(user_id='request',session_id=session.id,
            new_message=types.Content(role='user',parts=[types.Part(text=json.dumps({
                'question':packet['question'],'task':packet['task'],'feedback':packet['feedback'],
                'selected_locations':[c['name'] for c in packet['candidates']]}))]),
            run_config=RunConfig(max_llm_calls=12)):
            if event.author=='aquasustain_coordinator' and event.is_final_response() and event.content:
                final=''.join(p.text or '' for p in event.content.parts or [] if not p.thought)
        return validate_plan(final,packet,trace)
    finally:
        await service.delete_session(app_name='aquasustain',user_id='request',session_id=session.id)
        await runner.close()


async def generate_plan(packet):
    trace=[]
    if not ai_configured():
        return {'ai_status':'not_configured','plan':None,'trace':trace}
    try:
        plan=await asyncio.wait_for(execute(packet,trace),timeout=180)
        return {'ai_status':'live','plan':plan,'trace':trace}
    except Exception as exc:
        code=getattr(exc,'code',None)
        status='timed_out' if isinstance(exc,TimeoutError) else 'invalid_response' if isinstance(exc,ValueError) else 'permission_denied' if code==403 else 'quota_exceeded' if code==429 else 'unavailable'
        log.warning(json.dumps({'event':'adk_failure','error_type':type(exc).__name__,'status':status}))
        trace.append({'actor':'workflow','event':status,'elapsed_seconds':None})
        return {'ai_status':status,'plan':None,'trace':trace}
