# FitFlow - Architecture and Design Notes

These notes explain what each part of the system does and **why** it was built that way.
They double as interview preparation: each "Why" is an answer to a likely question.

## Core principle: deterministic core, AI at the edges

The LLM **never computes a number**. It translates free text ("I ate 2 eggs and ran for
half an hour") into calls to our own functions. Every calculation is a plain Python function
with unit tests, so the system is reliable, testable, and cheap to run.

## Layers

```
api/       HTTP (FastAPI): validation, auth, JSON in/out
ai/        The coach agent: LLM + tools
services/  Use-cases: load from the DB, run domain logic, save results
db/        SQLAlchemy models (SQLite in development, PostgreSQL in production)
domain/    The algorithms. No database, no network, no AI.
```

Each layer only depends on the layers below it. `services/mappers.py` converts database rows
into domain objects, so the domain layer never imports SQLAlchemy.

**Why:** the valuable logic (algorithms) is isolated and trivially testable. You could replace
the database or the LLM provider without touching a single algorithm.

## Domain modules

### `energy.py` - initial targets
- **BMR** with the Mifflin-St Jeor formula, multiplied by an activity factor = **TDEE**
  (total daily energy expenditure).
- Calorie target = TDEE +/- (weekly rate x 7700 / 7). Losing 0.5 kg/week = a 550 kcal daily deficit.
- Macros: protein by body weight, fat as 25% of calories, carbs fill the rest.
- Goals: cut, maintain, bulk, and recomp (a 5% deficit with high protein).
- **Safety limits:** at most 1% of body weight lost per week, and a minimum calorie floor.

### `activity.py` - workout calories
`(MET - 1) x weight_kg x hours`, and every activity belongs to a category (strength / cardio / other).
**Why subtract 1 MET?** Resting energy is already counted in the BMR. Without the subtraction,
the hour of resting burn during a workout would be counted twice.

### `trend.py` - learning the user's real metabolism
1. **Weight smoothing (EWMA).** Scale weight jumps +/-1 kg a day from water and salt. An
   exponential moving average filters that noise for the progress chart. Alpha depends on the
   gap between weigh-ins (`1 - 0.9^days`), so it works for daily, weekly or monthly weigh-ins.
2. **Adaptive TDEE (energy balance).**
   `expenditure = average intake - (weight slope in kg/day x 7700) - average workout calories`.
   The slope comes from a **least-squares linear regression**, not from the EWMA.
   **Interview story:** the first version used the EWMA trend. An API integration test exposed
   that EWMA *lags behind* steady weight loss: with 4 weekly weigh-ins it underestimated TDEE
   by ~150 kcal. Regression has no lag on a steady trend and still averages out noise, so it
   now drives the math and EWMA is only used for the chart.
3. **Safeguards:** at least 14 days of data, food logged on at least 70% of those days, move
   only halfway towards the new estimate, and never more than 150 kcal per update.

> Future upgrade to discuss: a Kalman filter, which estimates weight and TDEE together and
> tracks how confident it is in each.

### `optimizer.py` - "what should I eat from what I have at home?"
**Integer Linear Programming** with PuLP and the CBC solver:
- **Variables:** how many servings of each food (integer), and whether each food is used (binary).
- **Constraints:** only foods at home and in the available amounts, suitable for the time of day,
  not disliked, at most 4 foods and at most 2 from the same category, so the meal makes sense.
- **Objective:** minimize the distance from the remaining macros. Missing protein and going
  over calories are penalized the most.
- **The |x| trick:** each deviation is split into two non-negative variables (`under` and `over`),
  which keeps an absolute value linear.

**Why not a greedy algorithm?** Greedy picks "the most protein first" and misses good
combinations. ILP finds the best combination under all constraints at once. The problem is
knapsack-like (NP-hard in general), but with 20-50 foods CBC solves it in milliseconds.

### `insights.py` - pattern detection
Simple statistics: weekend vs weekday eating, hitting the protein target on training days vs
rest days, and weekly workout streaks. An insight is reported only when there is **enough
data** and the **effect is large enough**. Otherwise it's just noise.
The week follows the Israeli calendar (Sunday to Saturday, with Friday and Saturday as the weekend).

## The AI layer (`ai/`)

### How a chat turn works
```
user message
    -> send conversation + tool definitions to Claude  <------------+
    -> Claude answers. Does it want tools? (stop_reason == tool_use) |
         yes: run each tool with OUR code, send results back -------+
         no:  final reply -> save the whole turn, return it
```
The loop is written by hand in `agent.py` (not the SDK's tool runner) so every step is visible
and under our control.

### Design decisions
- **Human in the loop.** There is no tool that writes to the log. `propose_*` tools create a
  `PendingAction` with a preview, and only the user's Confirm click writes data. The model
  cannot bypass this, even if it misunderstands or is manipulated by a prompt.
- **Numbers come from tools.** Nutrition comes from the food database, workout calories from our
  MET formula, and remaining targets from `daily_status`. The one exception is foods missing from the
  database: the model estimates them, and the proposal is labelled as an estimate for the user to confirm.
- **Model output is untrusted input.** Tool arguments are validated with Pydantic. Invalid
  arguments go back to the model as an `is_error` tool result, so it can correct itself.
- **Atomic turns.** Chat messages and pending actions from one turn are committed together. On a
  refusal, an API error, or too many tool rounds, the whole turn is rolled back.
- **Safety limits.** A cap of 8 tool rounds per turn stops an endless loop.
- **Conversation storage.** Messages are stored verbatim (all content blocks). The API requires
  earlier blocks to be replayed unchanged. There is one conversation per day, which keeps the
  context small.
- **Model settings.** `claude-opus-5` with `effort: medium` (chat doesn't need deep reasoning),
  adaptive thinking, prompt caching of the conversation prefix, and server-side refusal fallbacks.
- **Testability.** The Anthropic client is injected, so tests use a scripted fake. The tests cover
  our loop, gate, persistence and error handling, with no API key and no cost.

## Database design decisions
- **Nutrition snapshots.** A log entry copies the food's values at logging time. Fixing a food in
  the database later doesn't silently rewrite the user's history.
- **One weigh-in per day** (unique constraint). Logging again replaces the earlier value.
- **"No entries" does not mean "ate nothing".** Unlogged days are excluded from calculations.
- **Accessing another user's entry returns 404, not 403**, so we don't leak that it exists.
- **Confirming an action twice returns 404**, so a double click never logs twice.

## API
`POST /users` · `GET/PATCH /me` · `GET /foods?q=` · `GET/PUT/DELETE /pantry/{id}` · `/disliked/{id}`
`POST /log/food` · `/log/custom-food` · `/log/workout` · `/log/weight` · `DELETE /log/...`
`GET /today` (dashboard, plus the weekly target update) · `/coach/meal-suggestion?hour=` · `/coach/insights`
`GET /workouts/week` · `/progress`
`POST /chat` · `GET /chat/history` · `POST /chat/actions/{id}/confirm` · `/reject`

Authentication currently uses an `X-User-Id` header. It must be replaced with JWT before deployment.

## Tests
`pytest` runs 65 tests. They include a simulated user with a known TDEE and noisy weigh-ins,
checking that the algorithm recovers the TDEE for daily, weekly and monthly weigh-ins, plus
end-to-end API tests and agent tests with a fake LLM.
