import asyncio
import json
import pytest
from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_response import LlmResponse
from google.genai import types
from app.agents.workflow import execute, validate_plan, generate_plan, build_agents
from app.main import run_comparison
from app.schemas import CompareRequest


def packet(task='full'):
    return {**run_comparison(CompareRequest(candidate_ids=['punjab-ludhiana'])), 'task':task,'feedback':''}


def plan():
    return {'summary':'Review the proposed design and local evidence.',
      'findings':[{'text':'The baseline is a modelled scenario.','claim_keys':['baseline.freshwater_m3']}],
      'tradeoffs':['Reclaimed supply needs verification.'],'next_steps':['verify_supply'],
      'missing_evidence':['Verified supply contract'],
      'action_plan':[{'action':'Verify reclaimed-water supply','owner':'Facility planner','timeframe':'Before design approval','prerequisite':'Supplier consultation','kpi':'Verified contractual volume'}],
      'feedback_response':'No stakeholder feedback was provided.'}


class ScriptedModel(BaseLlm):
    model: str='scripted-test-model'
    task: str='full'
    async def generate_content_async(self,llm_request,stream=False):
        names=set(llm_request.tools_dict)
        responses={p.function_response.name for c in llm_request.contents for p in c.parts or [] if p.function_response}
        if 'environmental_evidence_agent' in names:
            route={'full':['environmental_evidence_agent','water_solutions_agent'],'evidence':['environmental_evidence_agent'],'design':['water_solutions_agent']}[self.task]
            name=next((n for n in route if n not in responses),None)
            args={'request':'Assess the selected evidence and draft actions.'}
            value=plan()
            if self.task=='evidence':
                value['action_plan']=[]
                value['findings']=[{'text':'Review district evidence.','claim_keys':['punjab-ludhiana.district_context']}]
            answer=json.dumps(value)
        else:
            name=next(iter(names)) if not names & responses else None
            args={}
            answer='Tool results reviewed; retain supplied claim keys and evidence limitations.'
        part=types.Part(function_call=types.FunctionCall(name=name,args=args)) if name else types.Part(text=answer)
        yield LlmResponse(content=types.Content(role='model',parts=[part]))


def test_real_adk_runner_delegates_and_executes_both_tools():
    trace=[]
    r=asyncio.run(execute(packet(),trace,ScriptedModel()))
    assert r['action_plan'][0]['owner']=='Facility planner'
    calls=[t['actor'] for t in trace if t['event']=='tool_completed']
    assert calls==['retrieve_environmental_evidence','compare_water_scenarios']
    agents=[t['actor'] for t in trace if t['event']=='agent_started']
    assert agents==['aquasustain_coordinator','environmental_evidence_agent','water_solutions_agent']


def test_plan_without_required_execution_rejected():
    with pytest.raises(ValueError,match='Required specialist'):
        validate_plan(json.dumps(plan()),packet(),[])


def test_forged_citation_rejected():
    p=plan();p['findings'][0]['claim_keys']=['invented.claim']
    with pytest.raises(ValueError,match='unknown claim'):
        validate_plan(json.dumps(p),packet(),[])


def test_unconfigured_workflow_has_no_fake_execution(monkeypatch):
    for k in ['GOOGLE_CLOUD_PROJECT','GEMINI_MODEL','AQUA_PROJECT_ID','AQUA_MODEL_ID']:monkeypatch.delenv(k,raising=False)
    r=asyncio.run(generate_plan(packet()))
    assert r=={'ai_status':'not_configured','plan':None,'trace':[]}


def test_each_request_has_separate_agent_instances():
    a=build_agents(packet(),[],ScriptedModel());b=build_agents(packet(),[],ScriptedModel())
    assert a is not b and a.tools[0].agent is not b.tools[0].agent


@pytest.mark.parametrize('task,tool',[('evidence','retrieve_environmental_evidence'),('design','compare_water_scenarios')])
def test_selective_delegation(task,tool):
    trace=[]
    asyncio.run(execute(packet(task),trace,ScriptedModel(task=task)))
    assert [t['actor'] for t in trace if t['event']=='tool_completed']==[tool]
