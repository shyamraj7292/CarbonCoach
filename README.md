# CarbonCoach 🌱

An AI agent that helps people **understand, track, and reduce** their personal
carbon footprint — through natural conversation, photo logging, and a live
dashboard.

> "Drove 15km to work and had a beef burger for lunch" → CarbonCoach calculates
> the CO2e, logs it, and tells you the single biggest swap you could make.

## How it works

```
Frontend (vanilla JS + Chart.js)
   │  chat · dashboard · photo upload
   ▼
FastAPI backend  (/api/chat, /api/dashboard, /api/onboard, /api/insights, /api/photo)
   │
   ▼
Agent service — Gemini reason-act-observe loop
   ├─ calculate_emissions(category, activity, quantity)
   ├─ log_activity(category, activity, quantity, note)
   ├─ get_history(period)
   ├─ compare_to_average(country)
   └─ suggest_swaps(top_n)
   │
   ▼
emission_factors.json (~60 factors: transport, food, energy, shopping, waste)
   + local JSON store (users, activities) — or Firestore if configured
```

Gemini's role is to **map natural language to tool calls** — every CO2e number
comes from `emissions_engine.py`, a deterministic calculator over curated
emission factors (DEFRA/BEIS, EPA, Poore & Nemecek 2018). The agent never
invents a number.

## Setup

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
# edit .env and set GEMINI_API_KEY (https://aistudio.google.com/apikey)
```

Without `GEMINI_API_KEY`, the agent runs in a basic keyword-fallback mode
(recognizes patterns like "drove 10km" or "had a beef burger") — useful for
testing the rest of the stack without an API key.

## Run

```bash
cd backend
python main.py
```

Open http://localhost:8080

The activity store (`backend/data/store.json`) starts empty. Every number the
dashboard and agent show comes from activities you actually log through the
chat or photo upload — there is no seeded or simulated data anywhere in the
app.

## Run tests

```bash
cd backend
python -m pytest -v
```

## API

| Endpoint | Method | Description |
|---|---|---|
| `/api/chat` | POST | `{ "message": "..." }` → agent reply + logged actions |
| `/api/photo` | POST | multipart image (+ optional `message`) → Gemini vision logs the activity |
| `/api/dashboard/summary` | GET | today/week/month totals, category breakdown, benchmark comparison |
| `/api/dashboard/history?days=14` | GET | daily CO2e time series |
| `/api/insights` | GET | weekly summary, top category, quantified swap suggestion, goal progress |
| `/api/onboard` | GET/POST | get/set country + annual goal |

## Project structure

```
backend/
  main.py                  FastAPI app
  data/emission_factors.json   curated emission factors + benchmarks
  data/store.json           local JSON store (users + activities)
  services/
    emissions_engine.py    deterministic CO2e calculator
    tools.py                agent tool implementations
    agent_service.py        Gemini reason-act-observe loop + photo logging
    storage_service.py      local JSON storage (Firestore-ready)
  routes/                   chat, dashboard, onboard, insights, photo
  tests/                    pytest unit tests
frontend/
  index.html / css / js     chat UI + dashboard (Chart.js)
```

## Notes

- Single user (`default_user`) — no auth/multi-user support yet by design.
- Emission factors are representative national/global averages used for
  estimation, not audit-grade measurements. Sources listed in
  `emission_factors.json`.
- No seeded, mocked, or simulated data anywhere — `backend/data/store.json`
  is the only persistence layer and is populated solely by real logged
  activity.
