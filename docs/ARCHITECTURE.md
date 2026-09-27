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
- Goals: cut, maintain or bulk, with a **target weight** and a pace (relaxed / recommended / fast).
- **The pace is a share of body weight** (cut: 0.5-1% per week, bulk: 0.15-0.4%), not a fixed number
  of kg, so it's safe for every body size. The app shows the estimated date the target is reached.
- **Reaching the target switches the targets to maintenance** automatically.
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

**"Give me a different suggestion" uses no-good cuts.** Each earlier suggestion used a set of foods S.
The constraint `sum(used[f] for f in S) <= |S| - 1` forbids exactly that combination, so the solver
returns the next-best one. It's the standard way to enumerate alternative ILP solutions. When nothing is
left, the problem becomes infeasible and the app says "no more different combinations".

**"Fit my meal" (`fit_meal`) reuses the same model.** The user picks the foods and the solver picks only the
amounts. Every chosen food must be used, there are no pantry or meal-structure limits, and the amounts go in
**half servings**: integer variables count units of 0.5, which is more precise and still an ILP.

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

### Provider-agnostic (`providers.py`)
The loop talks to a small `LLMProvider` interface (`complete()` and `tool_results()`), with one adapter per API.
This is the Adapter / Strategy pattern:
- **`AnthropicProvider`** is Claude via the Anthropic SDK.
- **`OpenAICompatibleProvider`** covers any OpenAI-style API. The default is **Google Gemini's free tier**, and the
  same adapter works for Groq, OpenRouter or a local Ollama: only the URL and the model name change.
- The provider is chosen by configuration (`GEMINI_API_KEY` / `ANTHROPIC_API_KEY` / `LLM_PROVIDER` in `.env`).
  No code changes.
- Messages are stored in each provider's own format, tagged with the provider, because tool calls look
  different in each API.

### Running on a free tier: lessons from the live API
- **Model fallback.** Free models are often "503 overloaded", and the quota is **per model** (for example,
  5 requests per minute). So the adapter tries a list of models in order, and only reports "busy" if all of them fail.
- **Circuit breaker.** A model that hit its quota is skipped for 60 seconds, and an overloaded one for 20.
  Without this, every request first wasted seconds on the same failing model.
- **Fewer round trips.** `search_foods` takes all the foods of a message in one call, so one message
  is about 3 requests instead of 5 or 6. That's faster, and it uses less quota.
- **Replay the model's messages unchanged, including fields you don't know.** Gemini rejected the 2nd request
  with "missing thought_signature". The adapter had rebuilt each tool call from the fields it knew and dropped
  `extra_content.google.thought_signature`. Now tool calls are stored exactly as received. This is the same rule as
  Claude's thinking blocks, and it's covered by a regression test.
- **Observability.** At first the chat returned 503 with nothing in the server log, so it couldn't be debugged.
  Now every model call logs its model and duration, fallbacks are warnings, and LLM failures log a full traceback.
- **A daily limit per user** (`CHAT_DAILY_LIMIT`, 30 by default). The free quota is shared by everyone, so one
  user can't use it up. Only messages the user typed count, not tool rounds, and a blocked message never reaches the model.
- **Hebrew grammatical gender.** Gemini guessed the user's gender from the name ("דנה" -> feminine verbs),
  but the profile said male. The per-user context now says explicitly which forms to use.

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
- **Model settings.** Claude: `claude-opus-5` with `effort: medium`, prompt caching and server-side refusal fallbacks.
  Gemini: `reasoning_effort: low`, since chat and simple tool calls don't need deep thinking, and it's faster and cheaper on quota.
- **Testability.** The provider's client is injected, so tests use scripted fakes for both APIs, built from
  the SDKs' real response types. They cover the loop, the gate, persistence, fallback, the circuit breaker
  and error handling, with no API key and no cost.

## Frontend (`frontend/`)
React and TypeScript with Vite. A mobile-first, right-to-left (Hebrew) layout with dark mode, installable as a PWA.

```
src/api/        types.ts mirrors the backend schemas; client.ts has one function per endpoint
src/hooks/      useApi: load data on mount, with loading, error and reload
src/components/ Logo (animated loader), ActionCard (the confirm/reject gate), MacroBar, BottomNav
src/pages/      Onboarding, Today, Chat, Meal, Workouts, Progress
```
- **One place for API calls.** Components never build URLs or headers. They call `api.today()` and so on.
- **Colors are CSS variables**, redefined for dark mode. Components never hardcode colors.
- **User-facing errors are Hebrew**, mapped from HTTP status codes in `errorMessage()`. The server's
  technical message is kept on the error object for debugging.
- **Code splitting.** The progress page, together with the charting library (~370 KB), loads only when
  it is opened, which roughly halves the initial bundle.
- **Dev proxy.** Vite forwards `/api/*` to FastAPI, so there's a single origin and no CORS setup.

## Bugs found by using the real UI (good interview stories)
1. **A GET request with a side effect.** `GET /today` lazily runs the weekly TDEE update. React
   StrictMode calls effects twice in development: the first request performed the update, and the second
   reported "no update", so the banner never showed. The fix makes the *response* idempotent: the server
   stores the previous TDEE, so every request that day returns the same result.
2. **A whole day on one plate.** With nothing logged yet, the meal optimizer tried to fit the entire day's
   remaining calories into a single meal (3 servings of everything). Now each meal gets an even share
   of what's left, based on the meals remaining at that hour, capped at 40% of the daily target.
3. **A shared object holding per-user data.** When adding the user's name to the AI prompt, it was
   first stored on the shared `CoachAgent` (`self.user_name`). Two users chatting at the same moment
   could then have seen each other's name. Now it's passed as an argument, and a comment explains why.
4. **Inputs smaller than 16px.** iPhones zoom the whole page when such an input gets focus, which is
   annoying on the login screen. All inputs are now 16px.
5. **Missing API key crashed with a 500.** The SDK raises a `TypeError` when no credentials are
   configured. Now the dependency checks credentials first and returns a clear 503.

## Authentication (`services/auth.py`)
- **Passwords** are stored as a salted **scrypt** hash, never in plain text. scrypt is deliberately slow
  and memory-hungry, so guessing passwords from a leaked database is expensive. A random salt per user
  means equal passwords get different hashes. The check uses `hmac.compare_digest`, which takes the
  same time wherever the difference is, so nothing leaks through response times.
- **Login returns a JWT** signed with HS256. It contains the user id and an expiry (7 days). The server
  keeps no sessions: it only checks the signature with a secret from the `JWT_SECRET` environment variable.
- **Every protected endpoint** depends on `get_current_user`. Without a valid token the result is 401,
  and the handler never runs.
- **One error for "unknown email" and "wrong password"**, so attackers can't find out which emails are registered.
- **Frontend:** the token lives in localStorage and every request sends `Authorization: Bearer ...`.
  A 401 clears it and returns to the login screen. Trade-off: localStorage is readable by any script
  on the page (XSS). An httpOnly cookie is safer, but it needs CSRF protection.
- **Not done yet (good to mention):** rate limiting on login, email verification, password reset,
  and refresh tokens.

## Deployment and CI
- **One container** (`Dockerfile`, multi-stage): Node builds the frontend, and the final image contains only
  Python and the built files. `fitflow/web.py` serves the API under `/api` and the React app at `/`,
  from a single origin, so there's no CORS configuration.
- **Single-page-app fallback:** unknown paths return `index.html`, so refreshing the browser on `/chat`
  loads the app instead of a 404.
- **PostgreSQL in production** (`DATABASE_URL`), SQLite locally. `postgres://` URLs from hosting platforms
  are normalized for SQLAlchemy.
- **Secrets only in environment variables:** `JWT_SECRET`, `ANTHROPIC_API_KEY`. None are in git.
- **The container doesn't run as root**, and `/api/health` answers the platform's health checks.
- **CI (GitHub Actions)** runs on every push: the Python tests on SQLite **and on PostgreSQL**, frontend lint
  and build (including the type check), and a Docker build followed by a smoke test that starts the
  container and checks the API and the app respond.
- **Packaging bugs found while building this:** `pip install -e .` failed (setuptools doesn't allow
  several top-level folders in a flat layout), and the food database lived outside the package, so an
  installed app couldn't find it. Both are fixed in `pyproject.toml`.

## Editing and corrections
- **Editing a logged food:** a new amount scales the stored values (2 eggs to 3 eggs is x1.5). Values the user
  types, for example from a package label, override that. Editing a workout recomputes its calories with the
  same MET formula used for logging.
- **Fixing the profile:** a corrected weight replaces the **sign-up** weigh-in if it's still the only one
  (a typo like 87 instead of 78), and is otherwise logged as today's weight. Until the TDEE has been learned from
  data, a corrected sex, age, height, activity level or weight also recomputes the formula TDEE.

## Database design decisions
- **Nutrition snapshots.** A log entry copies the food's values at logging time. Fixing a food in
  the database later doesn't silently rewrite the user's history.
- **One weigh-in per day** (unique constraint). Logging again replaces the earlier value.
- **"No entries" does not mean "ate nothing".** Unlogged days are excluded from calculations.
- **Accessing another user's entry returns 404, not 403**, so we don't leak that it exists.
- **Confirming an action twice returns 404**, so a double click never logs twice.

## API
`POST /auth/register` · `POST /auth/login` · `GET/PATCH /me` · `GET /plan-preview` · `GET /foods?q=` · `GET/PUT/DELETE /pantry/{id}` · `/disliked/{id}`
`POST /log/food` · `/log/custom-food` · `/log/workout` · `/log/weight` · `DELETE /log/...`
`GET /today` (dashboard, plus the weekly target update) · `/coach/meal-suggestion?hour=` · `/coach/insights`
`GET /workouts/week` · `/workouts/stats` · `/progress`
`POST /chat` · `GET /chat/history` · `GET /chat/actions` · `POST /chat/actions/{id}/confirm` · `/reject`

## Tests
`pytest` runs 118 tests. They include a simulated user with a known TDEE and noisy weigh-ins,
checking that the algorithm recovers the TDEE for daily, weekly and monthly weigh-ins, plus
end-to-end API tests and agent tests with a fake LLM.
