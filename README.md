# FitFlow

Adaptive nutrition & training coach. Log meals and workouts in plain language; FitFlow tracks
calories and macros, learns your real metabolism from your weight trend, and suggests meals
from what you have at home.

**Deterministic algorithms at the core, AI at the edges.**

| Component | Technique |
|---|---|
| Initial targets | Mifflin-St Jeor BMR, energy-balance deficit, safety caps |
| Weight trend | Time-aware EWMA (works with daily / weekly / monthly weigh-ins) |
| Adaptive TDEE | Energy-balance inversion with damping and data-sufficiency checks |
| Meal suggestions | Integer Linear Programming (PuLP / CBC) over the user's pantry |
| Workout burn | Net MET calculation |
| Chat logging | LLM tool-use agent *(in progress)* |

## Run tests
```bash
python -m venv .venv
.venv/Scripts/pip install -e ".[dev]"
.venv/Scripts/python -m pytest
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for design notes.
