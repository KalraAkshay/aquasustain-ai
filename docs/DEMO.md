# AquaSustain AI — three-minute demonstration

Target finished duration: 3:00. The supplied organizer screenshot says 3–4 minutes; the public themes page says 3 minutes. A three-minute cut is intended to satisfy both; check the signed-in portal for its exact limit.

Record the working deployed Cloud Run application. A Cloud Shell preview URL is not the submission prototype URL.

## Before recording

- Confirm the deployed ADK smoke test passes.
- Open the Cloud Run URL in an incognito browser and verify it needs no unexpected sign-in.
- Keep only the app and its official source tab visible. Hide terminals containing account details.
- Reset the example to 20 MW, 80% load, baseline WUE 1.2/reclaimed 0%, alternative WUE 0.6/reclaimed 50%.
- Select Ludhiana and Pune. Choose Full assessment + community action plan.
- Question: Explain the selected groundwater evidence and our alternative design. Propose three feasible water-stewardship actions with owners, prerequisites and KPIs.
- Feedback: Residents want confirmation that reclaimed-water supply will be reliable.
- Measure response time in a rehearsal. The workflow has a three-minute limit, so avoid spending the entire video waiting. Capture a real completed run and include a clearly labelled cut such as “Elapsed processing time shortened.” Never portray prerecorded output as a fresh live response.

## Timeline and spoken script

### 0:00–0:20 — Problem and purpose

Screen: AquaSustain opening screen and project title.

“Planning a data centre means planning for water. AquaSustain AI helps teams examine published groundwater evidence, estimate their design's freshwater demand, and prepare a practical water-stewardship proposal. Our focus is early planning in India.”

### 0:20–0:45 — Map and local evidence

Screen: click Punjab, choose Ludhiana, then use Compare both to add Pune.

“We start with a location. This map links to district entries in the official 2025 groundwater assessment. We can compare reported extraction pressure and open the source. These are regional records; they do not certify a specific site or guarantee available supply.”

### 0:45–1:10 — Transparent calculations

Screen: scenario inputs, freshwater results and water chart.

“For this example, we assume 20 megawatts of IT capacity at 80 percent average load. Changing the cooling-water intensity and assuming 50 percent reclaimed water reduces modelled freshwater demand from 168,192 to 42,048 cubic metres a year. The 75 percent reduction is a scenario result, not measured savings.”

### 1:10–1:45 — Agent delegation

Screen: full-assessment selector, question and feedback; submit; then show the completed real trace. Label any wait-time cut.

“The root coordinator delegates evidence analysis to one specialist and solution planning to another. The evidence specialist retrieves curated government records. The solutions specialist uses our deterministic calculator. The displayed trace records actual agent and tool execution, and the final response must pass structure and citation-reference checks.”

### 1:45–2:20 — Proposed actions and stakeholder feedback

Screen: action cards and feedback response from the actual run.

“The result goes beyond describing the concern. It proposes actions with suggested owners, prerequisites, timeframes and KPIs. Here we ask the system to address residents' concerns about reclaimed-water reliability. It treats that feedback as an unverified report and explains the checks needed before relying on the proposal.”

Adjust narration to the actual action cards; do not read an example as though it appeared in the run.

### 2:20–2:40 — Grounding and export

Screen: open one source citation and download the agent assessment.

“Each factual finding links back to allowed evidence or a calculation. Reviewers can inspect those sources and download the assessment, including the proposed actions and execution trace. We keep evidence gaps visible instead of generating unsupported pollution or ecological claims.”

### 2:40–3:00 — Google Cloud and close

Screen: deployed URL plus architecture slide or repository architecture section.

“AquaSustain uses Google ADK and Gemini within a FastAPI application on Cloud Run, with versioned evidence in Cloud Storage. The prototype supports a reviewable planning process. Our next step is validation with planners and richer local evidence, including verified supply and environmental measurements.”

## Publishing

Upload the real recording to a platform accepted by the submission portal. Make it accessible without requesting access. Verify playback in incognito, record the final duration and copy its direct URL into the submission checklist. Do not submit this script as the video.
