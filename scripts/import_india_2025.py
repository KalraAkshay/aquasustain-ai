#!/usr/bin/env python3
"""Reproduce the national snapshot from the official 2025 CGWB PDF.
Usage: python scripts/import_india_2025.py /path/to/report.pdf
Requires requirements-data.txt; not used by the serving application.
"""
import hashlib
import json
import re
import sys
from pathlib import Path
import fitz

ROOT = Path(__file__).resolve().parents[1]
SOURCE = 'https://www.jalshakti-dowr.gov.in/static/uploads/2025/11/711d8d476bbf498cd90f8038e7371227.pdf'
TITLE = 'CGWB National Compilation on Dynamic Ground Water Resources of India 2025'


def slug(s):
    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')


def clean(s):
    return ' '.join((s or '').split())


def number(s):
    return None if clean(s) in {'','-','NA'} else float(clean(s).replace(',',''))


def resource(row, page, level, evidence_id):
    multiplier = 1_000_000_000 if level == 'state' else 10_000
    extractable, extraction, stage = number(row[8]), number(row[12]), number(row[15])
    flags = []
    if not extractable or number(row[6]) is None:
        stage = None
        flags.append('The source has missing recharge or zero extractable resources. Its printed zero extraction stage is not usable for screening.')
    if level == 'district' and stage is not None:
        assert abs(extraction/extractable*100-stage)<.12, (row[1], stage)
    return {
        'evidence_id':evidence_id,'assessment_year':2025,'geography_level':level,
        'extraction_stage_percent':stage,
        'annual_extractable_m3':None if extractable is None else round(extractable*multiplier,2),
        'annual_extraction_m3':None if extraction is None else round(extraction*multiplier,2),
        'source_url':SOURCE,'source_title':TITLE,
        'source_locator':f'Annexure {"I" if level=="state" else "II"}; PDF page {page}; printed page {page-26}; row {clean(row[1])}',
        'pdf_page':page,'quality_flags':flags,
        'verification':'Extracted from official table; schema and ratio checks passed. Sample pages visually checked; no blanket human review claim.'
    }


def main():
    source=Path(sys.argv[1]);doc=fitz.open(source)
    assert len(doc)==482, 'Unexpected report revision; review page references.'
    state_table=doc[168].find_tables().tables[0].extract()
    states=[]
    names={}
    for row in state_table:
        if (row[0] or '').isdigit() and row[1]!='2':
            name=clean(row[1])
            name={'Andaman And Nicobar':'Andaman and Nicobar Islands','Jammu And Kashmir':'Jammu and Kashmir'}.get(name,name)
            state={'id':slug(name),'name':name,'evidence':resource(row,169,'state',f'cgwb25-state-{slug(name)}')}
            states.append(state);names[name.upper()]=state
    aliases={'CHHATISGARH':'CHHATTISGARH','ANDAMAN & NICOBAR ISLANDS':'ANDAMAN AND NICOBAR ISLANDS','JAMMU & KASHMIR':'JAMMU AND KASHMIR'}
    candidates=[];raw=[]
    for page in range(173,211):
        table=doc[page-1].find_tables().tables[0].extract()
        title=clean(table[1][0]);state=names[aliases.get(title,title)]
        for row in table:
            if (row[0] or '').isdigit() and row[1]!='2':
                district=clean(row[1]);candidate_id=f"{state['id']}-{slug(district)}"
                evidence=resource(row,page,'district',f'cgwb25-{candidate_id}')
                candidates.append({'id':candidate_id,'name':district,'state':state['name'],'state_id':state['id'],'district':district,
                    'geography_level':'district','description':'District-level assessment from the 2025 report. This is regional context, not a parcel or supply allocation.',
                    'resource_evidence':evidence,'unit_evidence':None})
                raw.append({'candidate_id':candidate_id,'pdf_page':page,'source_row':row})
    # Targeted category-only records read and visually verified on printed page 357.
    ludhiana=next(c for c in candidates if c['id']=='punjab-ludhiana')
    unit_names=['Raikot','Pakhowal','Dehlon','Samrala','Machhiwara','Ludhiana-2','Jagraon','Sudhar','Ludhiana-1','Sidhwan Bet','Maloud','Khanna','Ludhiana City','Doraha']
    unit_table=doc[382].find_tables().tables[0].extract()
    for name in unit_names:
        assert any(clean(row[-1])==name for row in unit_table), name
        candidates.append({'id':'punjab-ludhiana-unit-'+slug(name),'name':name,'state':'Punjab','state_id':'punjab','district':'Ludhiana',
            'geography_level':'assessment_unit','description':'Published assessment-unit category. No unit-specific numeric extraction stage imported; district statistics remain separate.',
            'resource_evidence':ludhiana['resource_evidence'],
            'unit_evidence':{'evidence_id':'cgwb25-ludhiana-unit-'+slug(name),'assessment_year':2025,'unit_name':name,
                'extraction_stage_percent':None,'official_category':'Over-exploited','source_url':SOURCE,'source_title':TITLE,
                'source_locator':f'Annexure IV(A); PDF page 383; printed page 357; Ludhiana row, {name}',
                'pdf_page':383,'reviewed_by':'AI-assisted visual transcription','reviewed_at':'2026-10-11'}})
    for state in states:
        state['district_count']=sum(c['geography_level']=='district' and c['state_id']==state['id'] for c in candidates)
        candidates.append({'id':'state-'+state['id'],'name':state['name']+' overview','state':state['name'],'state_id':state['id'],'district':None,
            'geography_level':'state','description':'State or union territory aggregate. Does not classify a district or site.',
            'resource_evidence':state['evidence'],'unit_evidence':None})
    assert len(states)==36
    assert sum(c['geography_level']=='district' for c in candidates)==709
    assert len({c['id'] for c in candidates})==len(candidates)
    snapshot={'schema_version':2,'version':'india-2025-national-v2','checked_at':'2026-10-11','states':states,'candidates':candidates,
        'source_manifest':{'source_url':SOURCE,'title':TITLE,'sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
            'retrieved_at':'2026-10-11','source_pdf_pages':482,
            'coverage_note':'36 states/UTs; 709 district entries as named in the 2025 report; 14 category-only assessment-unit entries in Ludhiana. This is not a current administrative directory or full block-level coverage.'}}
    (ROOT/'data/evidence_snapshot.json').write_text(json.dumps(snapshot,ensure_ascii=False,indent=2)+'\n')
    (ROOT/'data/extraction_audit.json').write_text(json.dumps(raw,ensure_ascii=False,indent=2)+'\n')
    print('Imported',len(states),'states/UTs, 709 district entries, 14 Ludhiana units')
    print('Unavailable district stages:',[(c['name'],c['state']) for c in candidates if c['geography_level']=='district' and c['resource_evidence']['extraction_stage_percent'] is None])


if __name__=='__main__':main()
