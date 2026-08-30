# Sales Signal Intelligence Platform

A full-stack tool that pulls deals from HubSpot, tracks how they actually
move through the pipeline over time, and uses Claude to flag which ones need
attention - **At Risk**, **Stalling**, or **On Track** - with a one-line
reason for each.

## How it works

1. **Sync** pulls every deal from HubSpot's CRM API (name, stage, amount,
   activity) and saves it to Postgres.
2. Every sync also writes a **snapshot** of each deal's state. Over time,
   this snapshot history is what lets the platform calculate real velocity:
   how many days deals *actually* spend in each stage, on average.
3. For every deal, Claude is given its own numbers - days in its current
   stage, days since last contact, and the real historical average for that
   stage - and returns a signal plus a one-sentence, numbers-grounded reason.
4. The dashboard shows a Kanban-style pipeline board, one column per stage,
   with a summary bar of totals up top and a manual Sync button.

## Stack

| Layer | Technology |
|---|---|
| Backend | Python, FastAPI |
| Database | PostgreSQL (Neon) |
| Frontend | React, TypeScript, Vite, Tailwind CSS |
| AI | Groq API (`groq` SDK, GPT-OSS-120B, free tier) |
| CRM | HubSpot CRM API (v3/v4) |

## Project structure

```
sales-signal-platform/
├── backend/
│   ├── main.py            FastAPI app: /sync, /deals, /summary, /stages
│   ├── hubspot_client.py  HubSpot API wrapper (deals, notes, associations)
│   ├── database.py        SQLAlchemy models + velocity calculation
│   ├── ai_engine.py       Groq prompt + classification + fallback
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── components/
│   │   │   ├── PipelineBoard.tsx
│   │   │   ├── DealCard.tsx
│   │   │   └── SummaryBar.tsx
│   │   ├── lib/api.ts
│   │   └── types/deal.ts
│   └── package.json
├── seed.py                 Creates 50 realistic fake HubSpot deals + history
├── .env.example
└── README.md
```

## Setup

### 1. Neon PostgreSQL

Create a project at [neon.tech](https://neon.tech), then copy the
connection string from **Connect** on your project dashboard. It looks like:

```
postgresql://user:password@ep-xxxx.us-east-2.aws.neon.tech/sales_signal?sslmode=require
```

No manual schema setup needed - the backend creates all three tables
(`deals`, `deal_snapshots`, `deal_signals`) automatically on startup.

### 2. HubSpot Private App

1. In your HubSpot account: **Settings -> Integrations -> Private Apps ->
   Create a private app**.
2. Under **Scopes**, enable:
   - `crm.objects.deals.read`
   - `crm.objects.deals.write`
   - `crm.objects.notes.read`
   - `crm.objects.notes.write`
3. Copy the generated access token (starts with `pat-`).

Stage IDs are portal-specific - HubSpot assigns numeric internal IDs per
account rather than reusing the same string across every portal. This repo
is wired to the stage IDs for the account it was built against (fetched via
`GET /crm/v3/pipelines/deals`: Visitor Engaged, Lead Captured, Lead
Nurtured, Demo Delivered, In Negotiation, Deal Won, Deal Lost). If you're
pointing this at a different HubSpot portal, fetch that same endpoint for
your account and update `STAGE_LABELS` in `backend/main.py` and
`STAGE_SEQUENCE` in `seed.py` to match.

### 3. Groq API key (free)

Grab a key from [console.groq.com](https://console.groq.com) -> API Keys.
No billing required for the free tier.

### 4. Environment variables

```bash
cp .env.example .env
```

Fill in `DATABASE_URL`, `HUBSPOT_API_KEY`, and `GROQ_API_KEY`. Leave
`GROQ_MODEL` and `CORS_ORIGINS` as-is unless you need to change them.

```bash
cp frontend/.env.example frontend/.env
```

### 5. Backend

Uses Python 3.11 (the `X | None` type hints throughout the backend require
3.10+; if you only have an older `python3` on your PATH, install 3.11 via
`brew install python@3.11` first).

```bash
cd backend
/opt/homebrew/bin/python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Run the API:

```bash
uvicorn main:app --reload --port 8010
```

Port 8010 (not the more obvious 8000) is deliberate - 8000 is a common default that
collides with other local services (Docker containers, other projects' dev
servers). If 8010 is also taken on your machine, pick another port and
update it in both `.env` (`CORS_ORIGINS`) and `frontend/.env`
(`VITE_API_URL`).

### 6. Seed data (optional, but recommended for a first run)

From the project root, with the backend venv still active:

```bash
pip install -r backend/requirements.txt   # if not already installed in this shell
python seed.py
```

This creates 50 realistic deals directly in your HubSpot account (varied
stages, deal sizes, and contact activity - some deals recently touched, some
stale, some with no logged activity at all) and seeds matching historical
snapshots in Postgres so velocity math has real numbers immediately instead
of waiting on real sync history to build up.

### 7. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open the URL Vite prints (default `http://localhost:5173`).

### 8. Run a sync

Click **Sync from HubSpot** in the dashboard header (or `curl -X POST
http://127.0.0.1:8010/sync`). This pulls every deal, records a snapshot, and
runs Groq classification on each one - the pipeline board populates right
after.

## Deployment

Backend on Render, frontend on Vercel.

**Backend (Render):**
1. New -> Blueprint, point it at this repo. `render.yaml` at the project
   root configures the service automatically (Python 3.11.9, build/start
   commands, health check).
2. Fill in the env vars Render prompts for (`DATABASE_URL`,
   `HUBSPOT_API_KEY`, `GROQ_API_KEY`, `GROQ_MODEL`, `CORS_ORIGINS`) - same
   values as your local `.env`, except `CORS_ORIGINS` should be your
   eventual Vercel URL instead of `localhost:5173` (you can update this
   after the frontend is deployed and get its real URL).
3. Deploy. Note the resulting `https://<name>.onrender.com` URL.

**Frontend (Vercel):**
1. New Project, import this repo, set **Root Directory** to `frontend`
   (framework preset Vite should be auto-detected).
2. Add env var `VITE_API_URL` = your Render backend URL from above.
3. Deploy.
4. Go back to Render and update `CORS_ORIGINS` to the real Vercel URL, then
   redeploy the backend so it accepts requests from the deployed frontend.

Render's free tier spins down after ~15 minutes of inactivity - the first
request after a period of idleness can take 30-60s to wake back up.

## Notes on the AI signal

Groq (GPT-OSS-120B) is given, per deal: its name, current stage, days in
that stage, days since last contact, the deal amount, and - critically - the
**real average days other deals have spent in that same stage**, computed
from `deal_snapshots` history (`get_avg_days_in_stage` in
`backend/database.py`). That comparison against actual pipeline history is
what keeps the signal grounded rather than a generic guess. Early on, before
much snapshot history exists, this average falls back to a flat default (5
days) - `seed.py` sidesteps that by seeding realistic historical snapshots
directly, so even a first run has real averages to compare against.

If the Groq API call fails for a given deal (rate limit, bad key, transient
outage), a simple rule-based fallback still classifies it so one failed call
doesn't stop the whole sync - the reason text will say so explicitly when
that happens.

## Troubleshooting

- **Reason text says "rule-based fallback - Groq call failed"** -
  `gpt-oss-120b` is a reasoning model: without `reasoning_effort="low"` (set
  in `ai_engine.py`), it burns most of its token budget on hidden reasoning
  before ever emitting the JSON answer, truncating the response mid-object.
  If you swap to a different Groq model and see this again, either drop
  `reasoning_effort` (non-reasoning models don't use it) or raise
  `max_tokens`.
- **"model decommissioned" from Groq** - the model ID in `.env`
  (`GROQ_MODEL`) may have been retired. Check
  console.groq.com/docs/models for the current model ID and update the env
  var.
- **HubSpot 403s** - double check your Service Key / Private App has all
  four scopes listed above enabled.
- **Deals not appearing after seeding** - `seed.py` only writes to HubSpot +
  Postgres; it doesn't generate signals. Run a sync (step 8) afterward.
