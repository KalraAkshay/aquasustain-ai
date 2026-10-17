#!/usr/bin/env python3
"""Check the submitted service URL; --agents makes a billable multi-agent request."""
import argparse
import sys
import httpx


def verify(url, agents=False):
    with httpx.Client(base_url=url.rstrip('/'),timeout=210,follow_redirects=False) as client:
        page=client.get('/');page.raise_for_status()
        if 'AGENT WORKSPACE' not in page.text:
            raise ValueError('URL does not serve the expected agent workspace.')
        health=client.get('/health');health.raise_for_status()
        if health.json().get('version')!='0.4.0':
            raise ValueError('Unexpected application version.')
        body={'candidate_ids':['punjab-ludhiana','maharashtra-pune'],'generate_ai':False}
        response=client.post('/api/compare',json=body);response.raise_for_status()
        data=response.json()
        if data['calculations']['baseline']['freshwater_m3']!=168192 or data['calculations']['alternative']['freshwater_m3']!=42048:
            raise ValueError('Reference scenario failed.')
        print('PASS: unauthenticated application page, release and reference calculation.')
        if agents:
            response=client.post('/api/agents/assess',json={**body,'task':'full','question':'Explain the selected evidence and propose feasible water-stewardship actions.'})
            response.raise_for_status();data=response.json()
            if data.get('ai_status')!='live' or not data.get('plan'):
                raise ValueError('ADK did not return a validated live plan: '+data.get('ai_status','missing'))
            used={e['actor'] for e in data['trace'] if e['event']=='tool_completed'}
            if used!={'retrieve_environmental_evidence','compare_water_scenarios'}:
                raise ValueError('Required business tool execution missing.')
            print('PASS: live ADK full assessment and both business tools. Review factual meaning separately.')


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('url');parser.add_argument('--agents',action='store_true')
    args=parser.parse_args()
    try:verify(args.url,args.agents)
    except Exception as exc:
        print('FAILED:',str(exc),file=sys.stderr);sys.exit(1)
