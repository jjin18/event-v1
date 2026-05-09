# Eventful

Hackathon platform with contingent sponsor measurement. The product is the
operational and measurement layer underneath events: it designs the audience
for an event, runs a booth scanner against signed badge QR codes during the
event, executes contingent sponsor contracts post-event, generates a sponsor
packet, and tracks 30/60/90-day outcomes.

The full product spec lives in [`docs/FOUNDERS_PRD.md`](docs/FOUNDERS_PRD.md). This README is the operator's guide to what's actually wired in code.

## What ships today

**Audience design pipeline** (the room you want — same as before)
- `python -m packages.agents.run_intelligence` — objective → audience → sourcing → scoring → room balance, with optional preliminary sponsor matching when sponsors are configured.
- Outputs: `data/event_state.json`, `data/ranked_people.csv`, summaries under `docs/` and `logs/`.

**Sponsor measurement layer** (the contracts you sign on top of the room — PRD §5–§6)
- `POST /sponsors` — register a sponsor with structured ICP and contingent contract terms (base fee + per-match fee, capped).
- `GET  /sponsors/{id}/match-preview` — pre-event ranked attendees against the sponsor's ICP, with cited explanations.
- `POST /sponsors/{id}/staff/issue` — issue a signed booth-staff scanner-session URL.
- `GET  /scanner/{token}` — mobile-web booth scanner UI (server-rendered).
- `POST /scans` — log a booth scan; auto-computes ICP match against sponsor.icp and rolls into the live counter.
- `GET  /scans/by-sponsor/{id}` — real-time scan feed for the sponsor dashboard.
- `GET  /attendees/{id}/badge` — issue a signed badge token suitable for printing as a QR.
- `GET  /composition/{event_id}` — anonymized pre-event composition reveal (PRD §5.4); JSON variant at `/composition/{event_id}.json`.
- `POST /contracts/{id}/execute` — close out the contract: lock verified matches, compute capped invoice, stamp audit log.
- `POST /contracts/{id}/dispute` — flag a scan as confirmed/rejected during the dispute window.
- `GET  /packets/{id}` — post-event sponsor packet (HTML, browser-printable) with verified matches, memos, and a follow-up draft per match. JSON at `/packets/{id}.json`.
- `POST /outcomes/{id}/log` — capture sponsor outcome funnel (no_follow_up → contacted → interviewing → offered → hired/declined).
- `GET  /outcomes/{id}/export.csv` — outcomes CSV for sponsor finance reviews.

**Existing event surfaces** (unchanged)
- `POST /run` — runs the audience-design pipeline.
- `GET/POST/PATCH /attendees`, `GET /confirm/{token}`, `/event`, `/budget`, `/org/search`, `/messages/render`.

**Storage**
- File-based by default (`data/event_state.json`); optional Postgres when `DATABASE_URL` is set; Redis in compose for future jobs.

## Deferred from the PRD

These are explicit in `docs/FOUNDERS_PRD.md` but require external setup or significantly more scope, and are intentionally not wired in this revision:

- **LinkedIn / GitHub OAuth** for attendee identity verification (PRD §6.1) — needs registered apps and live secrets. Today the registration path is RSVP-link / manual; confidence-score machinery is scaffolded for OAuth to plug into.
- **Stripe payment execution** (PRD §6.5) — the contract route computes the final capped invoice and stamps the audit log; a payments worker should pick up rows where `payment_status == 'finalized'` and actually charge.
- **Voice memos** at booth scan (PRD §6.3) — the schema reserves `memo_audio_url`; the scanner UI captures text only.
- **Scheduled +14/+30/+60/+90 outcome emails** (PRD §6.7) — the endpoint logs the data; scheduling needs a Celery beat or external cron.
- **Native mobile app** — out of scope for v1; the scanner is mobile-web.
- **Self-serve sponsor / organizer onboarding** — every contract is hand-priced (PRD §3 "out of scope for v1").

## Quick HTTP example

```bash
PYTHONPATH=. uvicorn apps.api.main:app --reload --host 127.0.0.1 --port 8000

# 1. Run the audience-design pipeline
curl -s -X POST http://127.0.0.1:8000/run -H 'Content-Type: application/json' \
  -d '{"brief_text":"Event type: hackathon\nPeople we want: ML students\nGoal: hire engineers\n"}' | jq

# 2. Register a sponsor with contingent terms
curl -s -X POST http://127.0.0.1:8000/sponsors -H 'Content-Type: application/json' -d '{
  "company_name": "AI Taco",
  "icp": {"role_categories":["engineer"], "skill_signals":["pytorch"], "institution_signals":["MIT"]},
  "contract": {"base_fee": 5000, "per_match_fee": 1500, "cap": 20000}
}' | jq

# 3. Preview matches against ranked attendees
SID=$(curl -s http://127.0.0.1:8000/sponsors | jq -r '.sponsors[0].id')
curl -s http://127.0.0.1:8000/sponsors/$SID/match-preview | jq
```

Docker Compose mounts the repo at `/workspace` and sets `PYTHONPATH=/workspace` so `packages.*` imports resolve.

## Structure

```
event-v1/
├── apps/
│   └── api/              # FastAPI app + per-feature routers (sponsors, scans, contracts, packets, outcomes, ...)
├── packages/
│   ├── agents/           # Pipeline stages + run_intelligence
│   ├── enrichment/       # LLM audience designer + web-search curator
│   ├── scoring/          # attendee_fit (room ICP) + sponsor_match (per-sponsor ICP)
│   ├── report-gen/       # Reserved for future LLM reports
│   ├── integrations/     # Reserved for connectors
│   └── shared/           # event_state (incl. Sponsor/Scan/Contract/Outcome), tokens (HMAC badges + scanner sessions), db, io
├── data/                 # brief, seeds, outputs
├── docs/                 # FOUNDERS_PRD.md, architecture, summaries, structure_map
├── logs/
└── infra/                # Docker, init_db.sql, migrate_files_to_db.py
```

## Quickstart

```bash
pip install -r apps/api/requirements.txt

docker compose -f infra/docker/docker-compose.dev.yml up   # api + db + redis
```

## Eventful run

```bash
cp .env.example .env && export $(grep -v '^#' .env | xargs)

# optional schema
psql "$DATABASE_URL" -f infra/scripts/init_db.sql

python -m packages.agents.run_intelligence
# optional: python -m packages.agents.run_intelligence <brief_path> <seed_csv_path>

# Preview how agents interpret your brief — no prospect curation, no writes to ranked CSV / logs
python -m packages.agents.preview_intent data/event_brief.txt
python -m packages.agents.preview_intent data/event_brief.txt --audience   # adds LLM ICP design (+tokens)
python -m packages.agents.preview_intent data/event_brief.txt -i             # same + prompts each open question in terminal

python -m infra.scripts.migrate_files_to_db   # optional backfill into Postgres
```

**Inputs:** `data/event_brief.txt` (free prose works best with `ANTHROPIC_API_KEY`; offline-friendly labeled sections are in `data/event_brief.template.txt`). The pipeline extracts **event type**, **who you want in the room**, and **overall goal**, then builds ICPs and sourcing around them. Optional `data/people_seed.csv` skips LLM curation when present.

**Sourcing:** LLM + web search when `ANTHROPIC_API_KEY` is set and no seed CSV; CSV or offline otherwise (see pipeline stderr / summaries).

## Handoff / coordination

- **`packages/shared/event_state.py`** and **`visibility`** are the contract for other automation (e.g. ops branch).
- **`docs/structure_map.md`** describes how Agentic Ops can consume outputs (branch-specific).

## Docs

See `/docs` for architecture and data model.
