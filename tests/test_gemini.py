import json
from types import SimpleNamespace
from app.gemini_client import generate


def test_sdk_configuration():
    from google.genai import types
    from app.schemas import Narrative
    options=types.HttpOptions(timeout=20000,retry_options=types.HttpRetryOptions(attempts=1))
    config=types.GenerateContentConfig(response_mime_type='application/json',response_schema=Narrative)
    assert options.timeout==20000
    assert config.response_schema is Narrative


def test_integration_contract(monkeypatch):
    from google import genai
    monkeypatch.setenv('GOOGLE_CLOUD_PROJECT','test-project')
    monkeypatch.setenv('GEMINI_MODEL','test-model')
    reply={'summary':'Assumed demand is lower.','findings':[{'text':'Review the scenario.','claim_keys':['baseline.freshwater_m3']}],'tradeoffs':['Supply requires verification.'],'next_steps':['verify_supply'],'missing_evidence':['Supply contract']}
    class FakeClient:
        def __init__(self,**kwargs):
            assert kwargs['vertexai'] is True
            self.models=self
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def generate_content(self,**kwargs):
            assert kwargs['model']=='test-model'
            return SimpleNamespace(text=json.dumps(reply))
    monkeypatch.setattr(genai,'Client',FakeClient)
    status,narrative=generate({'claims':{'baseline.freshwater_m3':{'value':168192}}})
    assert status=='live'
    assert narrative['next_steps']==['verify_supply']


def test_model_failure_keeps_fallback(monkeypatch):
    from google import genai
    monkeypatch.setenv('GOOGLE_CLOUD_PROJECT','test-project')
    monkeypatch.setenv('GEMINI_MODEL','test-model')
    def fail(**kwargs):raise RuntimeError('test error')
    monkeypatch.setattr(genai,'Client',fail)
    assert generate({'claims':{}})==('unavailable',None)


def test_permission_error_is_actionable(monkeypatch):
    from google import genai
    monkeypatch.setenv('GOOGLE_CLOUD_PROJECT','test-project')
    monkeypatch.setenv('GEMINI_MODEL','test-model')
    class Denied(Exception):
        code=403
    def fail(**kwargs):raise Denied('private details must not escape')
    monkeypatch.setattr(genai,'Client',fail)
    assert generate({'claims':{}})==('permission_denied',None)
