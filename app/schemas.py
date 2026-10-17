from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)


class Scenario(StrictModel):
    it_capacity_mw: float = Field(default=20, gt=0, le=1000)
    load_factor: float = Field(default=.8, gt=0, le=1)
    wue_l_per_kwh: float = Field(default=1.2, ge=0, le=10)
    reclaimed_share: float = Field(default=0, ge=0, le=1)


class CompareRequest(StrictModel):
    candidate_ids: list[str] = Field(min_length=1, max_length=3)
    baseline: Scenario = Field(default_factory=Scenario)
    alternative: Scenario = Field(default_factory=lambda: Scenario(wue_l_per_kwh=.6, reclaimed_share=.5))
    question: str = Field(default='Explain the water demand trade-offs and the evidence still needed before choosing a site.', max_length=1000)
    generate_ai: bool = False

    @model_validator(mode='after')
    def unique_candidates(self):
        if len(set(self.candidate_ids)) != len(self.candidate_ids):
            raise ValueError('Choose distinct candidates.')
        return self


class Finding(StrictModel):
    text: str = Field(max_length=600)
    claim_keys: list[str] = Field(min_length=1, max_length=8)


class Narrative(StrictModel):
    summary: str = Field(max_length=1000)
    findings: list[Finding] = Field(max_length=4)
    tradeoffs: list[str] = Field(max_length=4)
    next_steps: list[Literal['verify_unit', 'verify_supply', 'validate_cooling', 'test_quality', 'community_review']] = Field(max_length=5)
    missing_evidence: list[str] = Field(max_length=5)


class UnitEvidence(StrictModel):
    evidence_id: str = Field(pattern=r'^[a-zA-Z0-9_-]{1,80}$')
    assessment_year: int = Field(ge=2000, le=2100)
    unit_name: str = Field(min_length=1, max_length=120)
    extraction_stage_percent: float | None = Field(default=None, ge=0, le=1000)
    official_category: Literal['Safe', 'Semi-critical', 'Critical', 'Over-exploited', 'Saline']
    source_url: str = Field(pattern=r'^https://')
    source_title: str = Field(min_length=1, max_length=250)
    source_locator: str = Field(min_length=1, max_length=200)
    pdf_page: int | None = Field(default=None, ge=1)
    reviewed_by: str = Field(min_length=2, max_length=100)
    reviewed_at: str = Field(min_length=10, max_length=40)


class ResourceEvidence(StrictModel):
    evidence_id: str
    assessment_year: int
    geography_level: Literal['state', 'district']
    extraction_stage_percent: float | None = Field(ge=0, le=1000)
    annual_extractable_m3: float | None = Field(ge=0)
    annual_extraction_m3: float | None = Field(ge=0)
    source_url: str = Field(pattern=r'^https://')
    source_title: str
    source_locator: str
    pdf_page: int = Field(ge=1)
    quality_flags: list[str]
    verification: str


class Candidate(StrictModel):
    id: str = Field(pattern=r'^[a-z0-9-]{1,140}$')
    name: str
    state: str
    state_id: str
    district: str | None
    geography_level: Literal['state', 'district', 'assessment_unit']
    description: str
    resource_evidence: ResourceEvidence
    unit_evidence: UnitEvidence | None = None


class StateRecord(StrictModel):
    id: str
    name: str
    district_count: int = Field(ge=0)
    evidence: ResourceEvidence


class Snapshot(StrictModel):
    schema_version: Literal[2]
    version: str
    checked_at: str
    candidates: list[Candidate] = Field(min_length=1, max_length=2000)
    states: list[StateRecord]
    source_manifest: dict

    @model_validator(mode='after')
    def unique_ids(self):
        if len({c.id for c in self.candidates}) != len(self.candidates):
            raise ValueError('Duplicate candidate ID')
        states = {s.id:s for s in self.states}
        if len(states) != len(self.states):
            raise ValueError('Duplicate state ID')
        for candidate in self.candidates:
            if candidate.state_id not in states or states[candidate.state_id].name != candidate.state:
                raise ValueError('Candidate state mismatch')
        for state in self.states:
            if sum(c.geography_level=='district' and c.state_id==state.id for c in self.candidates)!=state.district_count:
                raise ValueError('District count mismatch')
        return self


class AgentRequest(CompareRequest):
    task: Literal['full', 'evidence', 'design'] = 'full'
    feedback: str = Field(default='', max_length=1500)


class ProposedAction(StrictModel):
    action: str = Field(min_length=1, max_length=500)
    owner: str = Field(min_length=1, max_length=150)
    timeframe: str = Field(min_length=1, max_length=100)
    prerequisite: str = Field(min_length=1, max_length=500)
    kpi: str = Field(min_length=1, max_length=300)


class AgentPlan(Narrative):
    action_plan: list[ProposedAction] = Field(max_length=5)
    feedback_response: str = Field(max_length=1000)
