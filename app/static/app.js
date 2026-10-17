'use strict';
const $ = id => document.getElementById(id);
const fmt = (n, digits=0) => new Intl.NumberFormat('en-IN',{maximumFractionDigits:digits,minimumFractionDigits:digits}).format(n);
const el = (tag, text, cls) => {const node=document.createElement(tag);if(text!==undefined)node.textContent=text;if(cls)node.className=cls;return node;};
let latestAgentAssessment=null;
let locations=[],states=[],selected=['punjab-ludhiana'],version=0,aiConfigured=false, visibleDistricts=8;
function alertMessage(text){$('alert').textContent=text;$('alert').hidden=!text;}
async function api(path,body){
 const response=await fetch(path,{signal:AbortSignal.timeout(195000),cache:'no-store',method:body?'POST':'GET',headers:body?{'Content-Type':'application/json'}:{},body:body?JSON.stringify(body):undefined});
 if(!response.ok){let msg=`Request failed (${response.status}).`;try{const e=await response.json();msg=typeof e.detail==='string'?e.detail:e.detail?.map(x=>`${x.loc.slice(1).join('.')}: ${x.msg}`).join(';')||msg;}catch{}throw Error(msg);}
 return response;
}
function option(value,label){const o=el('option',label);o.value=value;return o;}
function byId(id){return locations.find(l=>l.id===id);}
function displayName(c){return c.geography_level==='assessment_unit'?`${c.name} · ${c.district}, ${c.state||states.find(s=>s.id===c.state_id)?.name}`:`${c.name} · ${c.state||states.find(s=>s.id===c.state_id)?.name}`;}
function populateDistricts(preferred){
 const list=locations.filter(l=>l.state_id===$('state-select').value&&l.geography_level==='district').sort((a,b)=>a.name.localeCompare(b.name));
 $('district-select').replaceChildren(option('', 'State / UT overview'),...list.map(l=>option(l.id,l.name)));
 $('district-select').value=preferred||list[0]?.id||'';populateUnits(); renderDistrictBrowser(); highlightMap();
}
function populateUnits(){
 const district=byId($('district-select').value);
 const units=locations.filter(l=>l.state_id===$('state-select').value&&l.geography_level==='assessment_unit'&&l.district===district?.name);
 $('unit-select').replaceChildren(option('',district?'District context':'State / UT context'),...units.map(l=>option(l.id,l.name)));
 $('unit-select').disabled=!units.length;
 $('location-hint').textContent=units.length?`${units.length} category-only unit records are available for this district. Choose a unit only if it matches the location you want to assess.`:'Use the district or state assessment. Assessment-unit categories are not imported for this selection.';
}
function chips(){
 const host=$('selected-locations');host.replaceChildren();
 selected.forEach(id=>{const c=byId(id);const chip=el('span',undefined,'location-chip');chip.append(el('span',displayName(c)));const remove=el('button','×');remove.type='button';remove.setAttribute('aria-label',`Remove ${c.name}`);remove.addEventListener('click',()=>{selected=selected.filter(x=>x!==id);chips();invalidate();if(selected.length)calculate();else{$('candidate-cards').replaceChildren(el('p','Add a location to start the assessment.','empty-locations'));$('observations').replaceChildren();$('screening').textContent='No location selected.';}});chip.append(remove);host.append(chip);});
}
function request(ai=false){
 if(!$('scenario-form').reportValidity())throw Error('Check the scenario inputs.');
 if(!selected.length)throw Error('Add at least one location.');
 const common={it_capacity_mw:Number($('capacity').value),load_factor:Number($('load').value)/100};
 return {candidate_ids:[...selected],baseline:{...common,wue_l_per_kwh:Number($('base-wue').value),reclaimed_share:Number($('base-reclaimed').value)/100},alternative:{...common,wue_l_per_kwh:Number($('alt-wue').value),reclaimed_share:Number($('alt-reclaimed').value)/100},question:$('question').value,generate_ai:ai};
}
function sourceLink(evidence,text){const a=el('a',text,'source-link');a.href=evidence.source_url+(evidence.pdf_page?`#page=${evidence.pdf_page}`:'');a.target='_blank';a.rel='noopener noreferrer';return a;}
function renderCandidates(result){
 const host=$('candidate-cards');host.replaceChildren();
 result.candidates.forEach(c=>{
  const card=el('article',undefined,'candidate-card selected');card.append(el('h3',c.name),el('div',`${c.state.toUpperCase()} · ${c.geography_level.replace('_',' ').toUpperCase()}`,'state-label'));
  const e=c.resource_evidence,u=c.unit_evidence,stage=e.extraction_stage_percent;
  if(u){card.append(el('span',u.official_category,'coverage known-category'),el('p','Official assessment-unit category · 2025'),el('p',`District context: ${c.district}, ${fmt(stage,2)}% extraction stage. This percentage is not the unit’s percentage.`),sourceLink(u,'Open unit category source ↗'));}
  else{card.append(el('span',stage===null?'Insufficient usable data':`${e.assessment_year} · ${e.geography_level} evidence`,'coverage'+(stage>100?' concern':'')),el('div',stage===null?'Unavailable':`${fmt(stage,2)}%`,'evidence-value'),el('div',`${e.geography_level}-level groundwater extraction stage`,'evidence-label'));
   card.append(el('p',stage===null?e.quality_flags.join(' '):stage>100?'Reported extraction exceeds annual extractable groundwater resources.':'This aggregate does not establish available supply at a proposed site.'),sourceLink(e,'Open official table ↗'));
  }
  if(result.screening.status==='comparable'){const values=result.candidates.map(x=>x.resource_evidence.extraction_stage_percent);const rank=1+values.filter(v=>v<stage).length;card.append(el('div',`Regional extraction-stage order: ${rank} of ${values.length}`,'rank'));}
  const details=el('details');details.append(el('summary','Source and calculation basis'),el('p',c.description),el('p',e.source_locator));
  if(stage!==null)details.append(el('p',`Published annual extractable resources: ${fmt(e.annual_extractable_m3/1e6,2)} million m³. Published extraction for all uses: ${fmt(e.annual_extraction_m3/1e6,2)} million m³. Neither figure is a supply allocation for this project.`));
  details.append(el('p',e.verification));if(u)details.append(el('p',u.source_locator));card.append(details);host.append(card);
 });
 $('observations').replaceChildren(...result.observations.map(o=>{const n=el('div',undefined,'observation');n.append(el('p',o.text),el('small',o.basis));return n;}));
}
function svgNode(tag,attributes,text){const n=document.createElementNS('http://www.w3.org/2000/svg',tag);Object.entries(attributes).forEach(([k,v])=>n.setAttribute(k,String(v)));if(text!==undefined)n.textContent=text;return n;}
function chart(calc){
 const svg=$('water-chart');svg.replaceChildren();const max=Math.max(calc.baseline.onsite_water_m3,calc.alternative.onsite_water_m3,1);
 [['Baseline',calc.baseline],['Alternative',calc.alternative]].forEach(([label,c],i)=>{const y=22+i*64;svg.append(svgNode('text',{x:0,y:y+18},label));svg.append(svgNode('rect',{x:92,y,width:400,height:26,rx:4,fill:'#f0f4ed'}));const fresh=c.freshwater_m3/max*400,rec=c.reclaimed_water_m3/max*400;svg.append(svgNode('rect',{x:92,y,width:fresh,height:26,fill:'#0b7368'}),svgNode('rect',{x:92+fresh,y,width:rec,height:26,fill:'#b8d6ad'}),svgNode('text',{x:510,y:y+18},`${fmt(c.onsite_water_m3)} m³`));});
}
function render(result){
 $('result-state').textContent='MODELLED · NOT MEASURED';const c=result.calculations;$('reduction').textContent=fmt(Math.abs(c.reduction_m3));$('impact-title').textContent=c.reduction_m3>0?'A smaller freshwater footprint.':c.reduction_m3<0?'This design uses more freshwater.':'The freshwater demand is unchanged.';$('reduction-detail').textContent=c.reduction_percent===null?'The baseline is zero, so percentage reduction is not applicable.':`${fmt(Math.abs(c.reduction_percent),1)}% modelled freshwater ${c.reduction_m3>=0?'reduction':'increase'} with the alternative design.`;$('baseline-mld').textContent=fmt(c.baseline.freshwater_mld,4);$('alternative-mld').textContent=fmt(c.alternative.freshwater_mld,4);$('energy').textContent=fmt(c.baseline.it_energy_kwh/1e6,2);$('screening').textContent=result.screening.message;chart(c);renderCandidates(result);
}
function renderNarrative(result){
 const host=$('narrative');host.replaceChildren();
 if(!result.narrative){
 const messages={not_configured:'The AI service is not connected. Please contact the application administrator.',authentication_required:'The AI service needs administrator attention. Please try again later.',permission_denied:'The AI service is unavailable due to an access issue. Please contact the application administrator.',model_not_found:'The configured AI model is unavailable. Please contact the application administrator.',quota_exceeded:'The AI service is busy or has reached its usage limit. Please try again later.',timed_out:'Gemini did not answer in time. Retry this question.',invalid_response:'The answer failed structure or citation validation. It was not displayed. Retry the question.'};
 $('ai-status').textContent='Gemini needs attention';host.append(el('p',messages[result.ai_status]||'Gemini could not complete the request. Check the connection or retry.','ai-notice'),el('p','Your evidence and calculated results remain available.','muted'));return;
 }
 $('ai-status').textContent='Live Gemini response';host.append(el('p',result.narrative.summary));const list=el('ul');
 result.narrative.findings.forEach(f=>{const li=el('li',f.text);const seen=new Set();f.claim_keys.forEach(key=>{const claim=result.claims[key];if(claim?.source_id&&!seen.has(claim.source_id)){seen.add(claim.source_id);const link=sourceLink(claim.value,'[source]');link.className='citation';li.append(link);}else if(claim?.kind==='modelled'&&!seen.has('calculation')){seen.add('calculation');const a=el('a','[calculation]','citation');a.href='#impact-title';li.append(a);}});list.append(li);});host.append(list);
 for(const [title,items] of [['Trade-offs',result.narrative.tradeoffs],['Next checks',result.narrative.next_steps.map(k=>result.actions[k])],['Missing evidence',result.narrative.missing_evidence]]){if(!items.length)continue;host.append(el('h3',title));const ul=el('ul');items.forEach(t=>ul.append(el('li',t)));host.append(ul);}
 host.append(el('p','Generated by Gemini from this comparison. Verify interpretation against the linked source tables.','model-origin'));
}
function invalidate(){version++;latestAgentAssessment=null;$('download-agent-plan').hidden=true;$('agent-trace').replaceChildren();$('action-plan').replaceChildren();$('result-state').textContent='INPUTS CHANGED · RECALCULATE';$('ai-status').textContent=aiConfigured?'Gemini configured · new explanation needed':'Gemini connection required';$('narrative').replaceChildren(el('p','Generate a new explanation for the selected locations and assumptions.','muted'));}
async function calculate(ai=false){
 const button=ai?$('explain'):$('calculate');const old=button.textContent;let current;
 try{alertMessage('');const body=request(ai);current=++version;button.disabled=true;button.textContent=ai?'Generating explanation…':'Calculating…';const r=await(await api('/api/compare',body)).json();if(current!==version)return;render(r);if(ai)renderNarrative(r);}
 catch(e){alertMessage(e.message);}finally{button.disabled=false;button.textContent=old;}
}
$('state-select').addEventListener('change',()=>{$('location-search').value='';visibleDistricts=8;populateDistricts();});
$('district-select').addEventListener('change',()=>{populateUnits();renderDistrictBrowser();});
$('location-search').addEventListener('input',()=>{visibleDistricts=8;renderDistrictBrowser();});
$('add-location').addEventListener('click',()=>{const id=$('unit-select').value||$('district-select').value||'state-'+$('state-select').value;if(selected.includes(id)){alertMessage('This location is already selected.');return;}if(selected.length>=3){alertMessage('Remove one selected location before adding another; compare up to three at a time.');return;}selected.push(id);chips();invalidate();calculate();});
$('scenario-form').addEventListener('submit',e=>{e.preventDefault();calculate();});
$('scenario-form').addEventListener('input',()=>{$('base-share').textContent=$('base-reclaimed').value+'%';$('alt-share').textContent=$('alt-reclaimed').value+'%';invalidate();});
$('reset').addEventListener('click',()=>{$('scenario-form').reset();$('base-share').textContent='0%';$('alt-share').textContent='50%';invalidate();calculate();});
$('explain').addEventListener('click',assessAgents);$('question').addEventListener('input',invalidate);
 document.querySelectorAll('[data-question]').forEach(b=>b.addEventListener('click',()=>{$('question').value=b.dataset.question;invalidate();}));
$('download').addEventListener('click',async()=>{try{alertMessage('');const response=await api('/api/brief/download',request(false));const url=URL.createObjectURL(await response.blob());const a=el('a');a.href=url;a.download='AquaSustain_Decision_Brief.md';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}catch(e){alertMessage(e.message);}});

function renderDistrictBrowser(){
 const state=states.find(s=>s.id===$('state-select').value);$('browse-title').textContent=state?.name||'Choose a state';
 const query=$('location-search').value.trim().toLowerCase();
 const rows=locations.filter(l=>l.state_id===state?.id&&l.geography_level==='district'&&l.name.toLowerCase().includes(query)).sort((a,b)=>a.name.localeCompare(b.name));
 $('district-results').replaceChildren(...rows.slice(0,visibleDistricts).map(c=>{const b=el('button',c.name,'district-choice'+(c.id===$('district-select').value?' active':''));b.type='button';b.setAttribute('aria-pressed',String(c.id===$('district-select').value));b.addEventListener('click',()=>{$('district-select').value=c.id;populateUnits();renderDistrictBrowser();});return b;}));
 $('district-count').textContent=rows.length?`Showing ${Math.min(visibleDistricts,rows.length)} of ${rows.length} matching report districts`:'No matching district in this state. Try another spelling or state.';
 $('more-districts').hidden=rows.length<=visibleDistricts;
}
function highlightMap(){document.querySelectorAll('[data-state]').forEach(n=>{const active=n.dataset.state===$('state-select').value;n.classList.toggle('active',active);n.setAttribute('aria-pressed',String(active));});}
function chooseState(id){$('state-select').value=id;$('location-search').value='';visibleDistricts=8;populateDistricts();}
async function loadMap(){
 try{const response=await api('/static/india-map.svg?v=0.4.0');const doc=new DOMParser().parseFromString(await response.text(),'image/svg+xml');const svg=doc.documentElement;if(svg.nodeName!=='svg')throw Error('Map format error');$('india-map').replaceChildren(document.importNode(svg,true));document.querySelectorAll('[data-state]').forEach(n=>{n.addEventListener('click',()=>chooseState(n.dataset.state));n.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();chooseState(n.dataset.state);}});});highlightMap();}
 catch(e){$('india-map').replaceChildren(el('p','Map unavailable. Choose a state using the selector alongside it.','muted'));}
}
async function connectionCheck(){
 $('connection-detail').textContent='Checking AI availability…';
 try{const d=await(await api('/api/ai/status')).json();$('connection-detail').textContent=!d.project_configured?'The AI service has not been configured. Please contact the application administrator.':!d.model_configured?'The AI model has not been configured. Please contact the application administrator.':!d.credentials_found?'The AI service needs administrator attention.':'AI configuration is present. Run an assessment to confirm the service is working.';}
 catch(e){$('connection-detail').textContent=e.message;}
}
$('check-ai').addEventListener('click',connectionCheck);
$('more-districts').addEventListener('click',()=>{visibleDistricts+=8;renderDistrictBrowser();});
function demo(ids){selected=ids;const c=byId(ids[0]);chooseState(c.state_id);$('district-select').value=c.id;populateUnits();renderDistrictBrowser();chips();invalidate();calculate();}
document.querySelectorAll('[data-demo]').forEach(b=>b.addEventListener('click',()=>demo([b.dataset.demo])));
$('demo-compare').addEventListener('click',()=>demo(['punjab-ludhiana','maharashtra-pune']));
let loading=false;
async function start(){
 if(loading)return;loading=true;$('startup').hidden=false;$('retry-load').disabled=true;
 try{const data=await(await api('/api/locations')).json();if(data.app_version!=='0.4.0')throw Error('The server is running an older release. Stop it and start the v3 folder.');locations=data.locations;states=data.states;aiConfigured=data.ai_configured;
 $('snapshot').textContent=`2025 assessment · checked ${data.checked_at}`;$('coverage').textContent=`${data.coverage.states} states / UTs · ${data.coverage.districts} district entries`;$('coverage-note').textContent=data.coverage_note+` ${data.coverage.unavailable_district_stages} district extraction-stage values are unusable and excluded from ranking.`;
 $('ai-status').textContent=aiConfigured?'Gemini configured · awaiting first call':'Gemini connection required';$('state-select').replaceChildren(...states.map(s=>option(s.id,s.name)));$('state-select').value='punjab';populateDistricts('punjab-ludhiana');chips();await calculate();$('startup').hidden=true;loadMap();
 }catch(e){alertMessage('Workspace could not load. '+e.message);$('coverage').textContent='Connection needs attention';}finally{loading=false;$('retry-load').disabled=false;}
}
$('retry-load').addEventListener('click',start);start();

async function assessAgents(){
 const button=$('explain');const label=button.textContent;let current;
 try{alertMessage('');const body={...request(false),task:$('agent-task').value,feedback:$('stakeholder-feedback').value};current=++version;button.disabled=true;button.textContent='Specialists are working…';latestAgentAssessment=null;$('download-agent-plan').hidden=true;$('agent-trace').replaceChildren(el('li','Assessment running. Execution events will appear on completion.'));$('action-plan').replaceChildren();$('narrative').replaceChildren();
 const r=await(await api('/api/agents/assess',body)).json();if(current!==version)return;render(r);
 $('agent-trace').replaceChildren(...r.trace.map(t=>el('li',`${t.actor.replaceAll('_',' ')} · ${t.event.replaceAll('_',' ')}${t.elapsed_seconds===null?'':` · ${t.elapsed_seconds}s`}`)));
 renderNarrative({...r,narrative:r.plan});
 if(r.plan){latestAgentAssessment=r;$('download-agent-plan').hidden=false;$('ai-status').textContent='Live ADK agent assessment';const host=$('action-plan');host.append(el('h3','Proposed community & water action plan'),el('p','Draft for review. Actions have not been approved or executed.','muted'));
 r.plan.action_plan.forEach(a=>{const card=el('article',undefined,'action-card');card.append(el('h4',a.action));for(const [label,key] of [['Proposed owner','owner'],['Timeframe','timeframe'],['Prerequisite','prerequisite'],['Measure','kpi']])card.append(el('p',`${label}: ${a[key]}`));host.append(card);});host.append(el('p',r.plan.feedback_response,'feedback-response'));}
 }catch(e){alertMessage(e.message);$('agent-trace').replaceChildren(el('li','Request failed or timed out; no completed plan is available.'));}finally{button.disabled=false;button.textContent=label;}
}
$('agent-task').addEventListener('change',invalidate);$('stakeholder-feedback').addEventListener('input',invalidate);

$('download-agent-plan').addEventListener('click',()=>{
 if(!latestAgentAssessment)return;
 const blob=new Blob([JSON.stringify(latestAgentAssessment,null,2)],{type:'application/json'});
 const url=URL.createObjectURL(blob);const a=el('a');a.href=url;a.download='AquaSustain_Agent_Assessment.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
});
