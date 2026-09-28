# FitFlow

[![CI](https://github.com/OfriKeidar/FitFlow/actions/workflows/ci.yml/badge.svg)](https://github.com/OfriKeidar/FitFlow/actions/workflows/ci.yml)

### 🔗 [Live demo: fitflow-rgtr.onrender.com](https://fitflow-rgtr.onrender.com)
Log in with **`demo@fitflow.app`** / **`demo1234`** (a shared account with 5 weeks of data), or create your own.
*Free hosting: the first visit after a quiet period can take up to a minute while the server wakes up.*

**An adaptive nutrition & training coach.** Tell it what you ate in plain language, and it tracks
calories and macros, **learns your real metabolism from your own data**, and suggests meals from what
you have at home using an optimization algorithm.

A Hebrew, mobile-first web app. The design principle behind it: **deterministic algorithms at the core, AI at the edges.**
The LLM turns free text into calls to tested code. It never makes up a number.

<p align="center">
  <img src="docs/screenshots/today.png" width="200" alt="Daily dashboard">
  <img src="docs/screenshots/meal.png" width="200" alt="Meal suggestion from the pantry">
  <img src="docs/screenshots/progress.png" width="200" alt="Progress and target">
  <img src="docs/screenshots/workouts.png" width="200" alt="Workout stats">
</p>
<p align="center">
  <img src="docs/screenshots/onboarding.png" width="200" alt="Onboarding with target date">
  <img src="docs/screenshots/chat.png" width="200" alt="AI coach chat">
  <img src="docs/screenshots/profile.png" width="200" alt="Editable profile and goal">
  <img src="docs/screenshots/today-dark.png" width="200" alt="Dark mode">
</p>

## Highlights

| | What | How |
|---|---|---|
| 🧠 | **Adaptive TDEE**: learns how many calories *you* actually burn | Energy balance + least-squares slope of the weight trend, damped and capped; works with daily, weekly or monthly weigh-ins |
| 🍽️ | **"What should I eat?"** from what's at home, plus **"fit my meal"** amounts | **Integer Linear Programming** (PuLP/CBC): pantry limits, sensible-meal constraints, weighted macro deviation; **no-good cuts** for alternative suggestions |
| 💬 | **AI coach**: "I ate 2 eggs and ran for 30 minutes" | Tool-use agent with a hand-written loop; **proposes** entries, and the user **confirms** before anything is saved |
| 🔌 | **Any LLM**: Gemini (free), Claude, or any OpenAI-style API | Provider adapters; model fallback and a circuit breaker for free-tier quotas and overloads |
| 📈 | **Weight trend** without the daily water noise | Time-aware EWMA (alpha depends on the gap between weigh-ins) |
| 🎯 | **Target date**: "you'll reach 70 kg around Nov 26" | Pace as a % of body weight (safe for every body size); switches to maintenance at the target |
| 🥗 | **4,500+ Israeli foods** with household units ("1 cup", "1 slice") | The Ministry of Health's national nutrition database, imported by a script; relevance-ranked search so "egg" finds a fresh egg, not egg powder |
| 🔍 | **Insights** like "you eat 544 kcal more on weekends" | Statistics with minimum-data and minimum-effect thresholds, so it doesn't report noise |
| 🔐 | **Auth** | scrypt password hashing, stateless JWT, same error for unknown email and wrong password |

## Architecture

```mermaid
flowchart LR
    UI["React + TypeScript<br/>(mobile-first, RTL)"] -->|"/api (JWT)"| API["FastAPI<br/>validation · auth"]
    API --> SVC["services/<br/>use-cases · food search"]
    API --> AI["ai/<br/>agent + tools<br/>(Gemini / Claude)"]
    AI -->|"tool calls"| SVC
    SVC --> DOM["domain/<br/>pure algorithms<br/>(no DB, no network)"]
    SVC --> DB[("PostgreSQL / SQLite<br/>SQLAlchemy")]
    MOH["Ministry of Health<br/>food CSVs"] -.->|"scripts/import_tzameret.py<br/>(once, offline)"| DB
```

- **`domain/`** holds the algorithms as pure functions: energy targets, adaptive TDEE, the ILP optimizer, insights. Most of the tests live here.
- **`services/`** loads data, runs the domain logic and saves the results. `mappers.py` keeps SQLAlchemy out of the domain.
- **`ai/`** is the agent loop, the tool definitions and the prompt. Write tools only create *pending actions*.
- **`api/`** holds the FastAPI routes and Pydantic schemas. **`web.py`** serves the API and the built frontend from one origin.
- **`data/`** ships the food databases as JSON; `db/seed.py` loads them on first start and `db/migrate.py` upgrades existing databases in place.

Design decisions, trade-offs and the bugs found along the way are in **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)**.

## Algorithms

The core logic is built on classic algorithms from CS courses:

| Algorithm | Where | The problem it solves in the app |
|---|---|---|
| **Knapsack** (bounded, multi-dimensional) | `domain/optimizer.py` | "What should I eat from what's at home?" Foods are the items, servings are copies (bounded by the pantry), and the 4 macros are 4 "weight" dimensions. The goal is to land closest to the meal's target, not to maximize value |
| **Integer Linear Programming**, solved by **branch and bound** (CBC) | `domain/optimizer.py` | How the knapsack above is actually solved, with extra rules: at most 4 foods, at most 2 per category |
| **LP modeling techniques**: absolute value with deviation variables, **Big-M** linking | `domain/optimizer.py` | `|total - target|` becomes `under - over` variables, so being short on protein can cost more than being over. Big-M links "how many servings" (integer) to "is it on the plate" (binary) |
| **No-good cuts** (enumerating distinct solutions) | `domain/optimizer.py` | "Another suggestion": a constraint that forbids exactly the previous combination, then solve again |
| **Dynamic programming, 1-D** (the Kadane pattern) | `domain/workout_stats.py` | Longest workout streak in days and in weeks: `run[i] = run[i-1] + 1` if day *i* follows day *i-1*, else `1`; the answer is `max(run)`. O(n) time, O(1) memory |
| **Recurrence / exponential smoothing** (a low-pass filter) | `domain/trend.py` | The weight trend: `trend[i] = trend[i-1] + α·(weight[i] - trend[i-1])`, with α depending on the days between weigh-ins. Filters daily water noise in one pass |
| **Least-squares linear regression** | `domain/trend.py` | The rate of weight change (kg/day), in closed form, O(n) |
| **Online learning update** with step clipping | `domain/trend.py` | Adaptive TDEE: each week, a step towards what the data shows (learning rate 0.5, capped at 150 kcal), like one gradient-descent step with gradient clipping |
| **Sorting by a lexicographic key** + top-k | `services/food_search.py` | Ranking 4,500 foods: (curated first, match quality, processed last, name length). O(C log C) over at most 300 candidates |
| **Hash maps / sets** | `workout_stats.py`, `db/seed.py` | Counting the most frequent activity, and O(1) duplicate checks when loading the food database |

**Why ILP and not the knapsack DP?** The textbook DP runs in O(n·W), pseudo-polynomial in a *single*
capacity W. Here there are 4 dimensions (calories, protein, carbs, fat), so the DP table would be
n × K × P × C × F states, plus the "at most 4 foods / 2 per category" rules as extra dimensions. The
problem is NP-hard in general, but with ~10-20 pantry foods, branch and bound solves it in milliseconds,
and new rules are just new constraints.

## Stack
**Backend:** Python 3.11, FastAPI, SQLAlchemy 2, PuLP, Gemini (OpenAI-compatible API) / Anthropic SDK, PyJWT, pytest (126 tests)
**Frontend:** React 19, TypeScript, Vite, Recharts, a PWA manifest, dark mode
**Ops:** Docker (multi-stage, non-root), docker-compose with PostgreSQL, GitHub Actions (tests on SQLite *and* PostgreSQL, lint, build, Docker smoke test), Render blueprint

## Run it

```bash
# Backend
python -m venv .venv
.venv/Scripts/pip install -e ".[dev]"
.venv/Scripts/python -m pytest                     # 126 tests
.venv/Scripts/python -m scripts.seed_demo           # optional: demo account with 5 weeks of data
.venv/Scripts/uvicorn fitflow.api.main:app          # API + interactive docs at http://localhost:8000/docs

# Frontend (second terminal)
cd frontend && npm install && npm run dev           # http://localhost:5173
```

The demo account is `demo@fitflow.app` / `demo1234`.

Or run the whole stack, including PostgreSQL, the way it runs in production:
```bash
docker compose up --build                           # http://localhost:8000
```

The AI coach needs a key in `.env` (copy `.env.example`). A **free Gemini key** from
[Google AI Studio](https://aistudio.google.com) is enough, and `ANTHROPIC_API_KEY` works too. Everything else works
without one, including all the tests (the agent is tested against scripted fake clients).

## Data
Food nutrition values: the Israeli national nutrition database (Tzameret), Israel Ministry of Health, via [data.gov.il](https://data.gov.il).
