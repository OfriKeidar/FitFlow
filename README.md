# FitFlow

Adaptive nutrition & training coach. Log meals and workouts in plain language; FitFlow tracks
calories and macros, learns your real metabolism from your weight trend, and suggests meals
from what you have at home.

**Deterministic algorithms at the core, AI at the edges.**

| Component | Technique |
|---|---|
| Initial targets | Mifflin-St Jeor BMR, energy-balance deficit, safety caps |
| Weight trend | Time-aware EWMA (works with daily / weekly / monthly weigh-ins) |
| Adaptive TDEE | Energy balance + least-squares weight slope, damped, with data-sufficiency checks |
| Meal suggestions | Integer Linear Programming (PuLP / CBC) over the user's pantry |
| Workout burn | Net MET calculation, strength / cardio / other |
| Insights | Weekend vs weekday intake, protein on training days, workout streaks |
| Auth | scrypt password hashing, JWT bearer tokens |
| Chat coach | Claude tool-use agent; proposes entries, the user confirms before anything is saved |

## Stack
Python, FastAPI, SQLAlchemy, PuLP, the Anthropic SDK, and pytest for the backend. React, TypeScript, Vite and
Recharts for the frontend: a mobile-first, right-to-left Hebrew web app with dark mode, installable as a PWA.

## Run
```bash
# Backend
python -m venv .venv
.venv/Scripts/pip install -e ".[dev]"
.venv/Scripts/python -m pytest                     # 89 tests
.venv/Scripts/uvicorn fitflow.api.main:app         # API + docs at http://localhost:8000/docs

# Frontend (in a second terminal)
cd frontend
npm install
npm run dev                                         # http://localhost:5173
```

Optional demo data (5 weeks of history, so charts and insights have something to show).
It creates the account `demo@fitflow.app` with password `demo1234`:
```bash
.venv/Scripts/python -m scripts.seed_demo
```

Or run the full stack (app and PostgreSQL) the way it runs in production:
```bash
docker compose up --build                           # http://localhost:8000
```

The AI coach needs an Anthropic API key in the `ANTHROPIC_API_KEY` environment variable.
Everything else, including all tests, runs without it.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for design notes.
