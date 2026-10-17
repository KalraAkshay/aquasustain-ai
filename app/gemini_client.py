import json
import logging
import os
from .evidence import ROOT
from .schemas import Narrative

log = logging.getLogger('aquasustain')


def ai_configured() -> bool:
    return bool((os.getenv('GOOGLE_CLOUD_PROJECT') or os.getenv('AQUA_PROJECT_ID')) and (os.getenv('GEMINI_MODEL') or os.getenv('AQUA_MODEL_ID')))


def validate_narrative(raw: str, packet: dict) -> dict:
    result = Narrative.model_validate_json(raw)
    for finding in result.findings:
        if any(key not in packet['claims'] for key in finding.claim_keys):
            raise ValueError('Model returned an unknown claim key.')
    return result.model_dump()


def generate(packet: dict) -> tuple[str, dict | None]:
    if not ai_configured():
        return 'not_configured', None
    try:
        from google import genai
        from google.genai import types
        with genai.Client(
            vertexai=True,
            project=os.getenv('GOOGLE_CLOUD_PROJECT') or os.getenv('AQUA_PROJECT_ID'),
            location=os.getenv('GEMINI_LOCATION') or os.getenv('AQUA_MODEL_LOCATION', 'global'),
            http_options=types.HttpOptions(timeout=60000, retry_options=types.HttpRetryOptions(attempts=1)),
        ) as client:
            response = client.models.generate_content(
                model=os.getenv('GEMINI_MODEL') or os.getenv('AQUA_MODEL_ID'),
                contents=json.dumps(packet),
                config=types.GenerateContentConfig(
                    system_instruction=(ROOT/'prompts/compare.txt').read_text(),
                    temperature=0.1,
                    max_output_tokens=8192,
                    response_mime_type='application/json',
                    response_schema=Narrative,
                ),
            )
        return 'live', validate_narrative(response.text or '', packet)
    except Exception as exc:
        # Never log credentials, raw prompts or model response bodies.
        log.warning(json.dumps({'event':'model_failure','error_type':type(exc).__name__}))
        code = getattr(exc, 'code', None) or getattr(exc, 'status_code', None)
        kind = type(exc).__name__
        if kind == 'DefaultCredentialsError' or code == 401:
            return 'authentication_required', None
        if code == 403:
            return 'permission_denied', None
        if code == 404:
            return 'model_not_found', None
        if code == 429:
            return 'quota_exceeded', None
        if 'Timeout' in kind:
            return 'timed_out', None
        if kind in {'ValidationError', 'ValueError'}:
            return 'invalid_response', None
        return 'unavailable', None
