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
| Chat logging | LLM tool-use agent *(in progress)* |

## Run
```bash
python -m venv .venv
.venv/Scripts/pip install -e ".[dev]"
.venv/Scripts/python -m pytest                          # tests
.venv/Scripts/uvicorn fitflow.api.main:app --reload     # API docs at http://localhost:8000/docs
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for design notes.
