#!/usr/bin/env python3
"""Real ADK assessment; may make multiple billable model calls."""
import asyncio
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.schemas import AgentRequest
from app.main import assess
r=asyncio.run(assess(AgentRequest(candidate_ids=['punjab-ludhiana'],task='full',question='Explain the evidence and propose a feasible water and community action plan.')))
print('ADK status:',r['ai_status'])
for e in r['trace']:print(e['actor'],e['event'])
if r['ai_status']!='live':
 print('See trace and server failure category. No validated agent plan is available.')
 sys.exit(1)
print('Root, required tool execution and final claim references validated. Review interpretation and proposed actions in the UI.')
