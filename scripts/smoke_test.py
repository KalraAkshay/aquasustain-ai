#!/usr/bin/env python3
"""Check a running local or Cloud Run service, optionally including a paid live AI call."""
import argparse
import httpx

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('url')
    parser.add_argument('--ai',action='store_true')
    args=parser.parse_args()
    with httpx.Client(base_url=args.url.rstrip('/'),timeout=45) as client:
        health=client.get('/health');health.raise_for_status()
        result=client.post('/api/compare',json={'candidate_ids':['punjab-ludhiana','maharashtra-pune'],'generate_ai':args.ai})
        result.raise_for_status();data=result.json()
        assert data['calculations']['baseline']['freshwater_m3']==168192
        assert data['calculations']['alternative']['freshwater_m3']==42048
        if args.ai:
            assert data['ai_status']=='live', f"Live Gemini verification failed: {data['ai_status']}"
        print({'health':'ok','calculation':'passed','ai_status':data['ai_status']})


if __name__ == "__main__":
    main()
