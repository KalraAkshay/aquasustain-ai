#!/usr/bin/env python3
"""Explicit live test; makes one chargeable model request, prints no credentials."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.schemas import CompareRequest
from app.main import run_comparison
scenario={'it_capacity_mw':20,'load_factor':.8,'wue_l_per_kwh':1.2,'reclaimed_share':0}
r=run_comparison(CompareRequest(candidate_ids=['punjab-ludhiana'],baseline=scenario,alternative={**scenario,'wue_l_per_kwh':.6,'reclaimed_share':.5},question='Explain the selected evidence and next checks.',generate_ai=True))
print('Gemini status:',r['ai_status'])
if r['ai_status']!='live':
 print('Verify the model ID/location, credentials, Vertex AI User access and quota. The app has not verified live AI.')
 sys.exit(1)
print('Live response received and claim references validated. Review factual wording in the application.')
