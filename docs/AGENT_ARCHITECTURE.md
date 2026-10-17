# AquaSustain ADK architecture — v0.4.0

## Implemented components

- Root `aquasustain_coordinator`: Gemini-backed ADK LlmAgent. Calls specialists through AgentTool and synthesizes validated JSON.
- Child `environmental_evidence_agent`: has one business tool, `retrieve_environmental_evidence`. Retrieves the current request's official groundwater records and claim ledger from the curated snapshot. It does not browse live government websites.
- Child `water_solutions_agent`: has one business tool, `compare_water_scenarios`. Returns the exact server-validated deterministic scenario calculations and assumptions, which the model cannot replace through tool arguments. Proposes actions with owners, timelines, prerequisites and KPIs.

There are two business tools and two AgentTool wrappers. Wrappers are ADK's delegation mechanism, not additional environmental tools. Both business functions bind to a validated, request-scoped packet; no arbitrary URLs or model-chosen location IDs are accepted.

## Request lifecycle

POST `/api/agents/assess` accepts existing scenario fields plus `task` (full/evidence/design) and optional `feedback`.

1. FastAPI validates locations, input bounds, task and feedback length.
2. Existing server code retrieves the selected snapshot records and computes the authoritative scenarios.
3. A fresh ADK coordinator/specialist graph and in-memory session are created.
4. Evidence-only calls the evidence child. Design-only calls the solutions child. Full calls evidence first, then solutions, then synthesizes.
5. Actual agent callbacks and business tool executions append a request-local trace. It is returned at completion, not streamed, and contains no hidden reasoning or raw model responses.
6. Final JSON is validated against `AgentPlan`: narrative findings, allowed citation keys, proposed actions, feedback response. The executed tool route must match the selected task. Calculation claims require the calculator; official claims require evidence retrieval. An invalid plan is withheld.
7. Session data is deleted after completion. No persistent conversational memory or stored feedback is implied.

The tools do not predict pollution, biodiversity loss, fish mortality, soil erosion, air impacts or legal eligibility for CSR. The solutions agent identifies evidence gaps and suggests reviewable investigations. Stakeholder feedback is unverified user input and can influence a new proposed plan, not the official evidence.

## Configuration and deployment

`app/__init__.py` loads `.env.local` with python-dotenv; existing process environment variables take precedence. Cloud Run uses service environment variables and a runtime service account. `.env.local` is excluded from Git and is not copied into the Docker image.

Gemini is explicitly configured for Vertex AI using the known project/model/location. Legacy single-call generation uses 60-second timeout and 8192 output tokens. Each ADK Gemini request also uses a 60-second timeout, 8192 output tokens and no SDK retries. The workflow wall-clock limit is 180 seconds, browser limit 195 seconds, Cloud Run request limit 240 seconds. No automatic retry loop is added. A specialist can be invoked at most once per request. ADK's max_llm_calls=12 bounds each runner invocation; nested agent runners may each make multiple calls. This is not a global spending cap. Existing ten-assessment-per-minute per-process limit remains.

ADK 1.10.0, Google Gen AI 2.29.0 and the dependency set in requirements.txt were installed and verified together. This is a tested pinned set, not a claim to use the latest ADK. Newer ADK pins tried during integration conflicted with the app's FastAPI/SDK constraints. Do not independently upgrade one dependency without re-running the delegation tests.

## Files

- `app/agents/workflow.py`: construction, tool wrappers, runner, trace, validation, timeout.
- `prompts/agent_common.txt`: shared factual and action boundaries.
- `prompts/coordinator.txt`, `evidence_agent.txt`, `solutions_agent.txt`: role instructions and routing.
- `app/schemas.py`: request, action and final-plan contracts.
- `scripts/check_agents.py`: live full-workflow smoke test (multiple billable calls).
- `tests/test_agents.py`: real ADK orchestration with a scripted model plus rejection/isolation tests.

## Verification limits

The scripted-model test exercises actual ADK agent delegation, tool invocation, callbacks and return synthesis. It does not establish live Gemini function-call reliability or factual accuracy. The user verified the prior single-agent Gemini path on October 13; the ADK path must be verified separately. Agent prose and proposed programme feasibility require human review even when all reference keys validate.

The existing factual brief download still exports deterministic evidence and scenarios; generated community plans are available separately through Download agent assessment (JSON), including the returned source ledger and trace. Changing inputs clears that export until a new valid plan is generated.
