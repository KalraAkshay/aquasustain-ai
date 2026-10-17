# Upgrade to the agent workspace v0.4.0

Keep the working v3 directory. Upload the new ZIP to Cloud Shell home, stop the existing preview with Ctrl+C, and run:

```bash
unzip -o ~/AquaSustain_AI_Google_Cloud_MVP.zip -d ~/aquasustain-agents-v4
cd ~/aquasustain-agents-v4/aqua-sustain
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env.local
python scripts/check_agents.py
```

The example config contains your project `gcp-hackathon-in-2026`, previously successful model `gemini-3.5-flash`, global location and port 8081. Edit `.env.local` if needed. Do not copy credentials into this file. Existing ADC authentication is reused. Environment variables set earlier take precedence; ensure they match your intended configuration.

The live test may take up to three minutes and makes multiple billable Gemini requests. A successful result shows `ADK status: live` plus coordinator, specialist and tool execution events. If it fails, share the status/trace and error type (no tokens or credential files). The test validates structure and references, not factual meaning.

Start the preview:

```bash
bash scripts/start_local.sh
```

Open Web Preview → 8081 and refresh with Ctrl+Shift+R. Check footer `AGENT WORKSPACE · v0.4.0`. If 8081 is occupied, stop the previous server; alternatively run `PORT=8082 bash scripts/start_local.sh` and preview 8082.

After reopening Cloud Shell, only run:

```bash
cd ~/aquasustain-agents-v4/aqua-sustain
bash scripts/start_local.sh
```

## Demo

Select Ludhiana and Pune. Choose Full assessment + community action plan. Ask: “Explain the groundwater evidence and our alternative design. Propose a feasible water stewardship programme with owners, prerequisites and KPIs.” Add optional feedback: “Residents want evidence that reclaimed-water supply is reliable.” Click Assess with agent team.

Review the actual execution trace, sourced findings and proposed action cards. Then try evidence-only and design-only requests to demonstrate selective delegation. For a fisheries question, verify the agents disclose missing fish/water-quality evidence rather than inferring damage from groundwater data.

## What is not changed on your cloud account

This ZIP does not deploy or grant IAM access. Use the existing Cloud Run deployment script only after local agent validation. Its timeout is now 240 seconds and memory 1 GiB for the ADK dependency set.
