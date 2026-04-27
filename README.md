# Multi-Modal Nutrition AI Agent (Django)

A small Django app that extends the previous AI Chef project: **text + image** in, **structured nutrition estimates** out, with **LangChain tool calling** (mock search + CSV log) and **session memory** (last 5 messages + a short rolling summary).

**Safety:** the app and API always return:

> This is not medical or dietary advice. Consult a qualified professional.

## What it does

- **Analyze meals** (describe food or upload a kitchen photo) — JSON with meal name, estimated calories, protein/carbs/fats, ingredients, summary, and recommendations.
- **Search-style questions** (e.g. “healthy food near me”) — the agent can call a **mock** `search_nutrition_places` tool and you’ll see **sample** restaurant/store listings plus notes.
- **Logging** — when appropriate, the agent calls `save_nutrition_to_csv` to append a row to `data/nutrition_log.csv` (no user database; CSV is gitignored by default).
- **Memory** — the last few turns are kept in the Django **session**; older turns are folded into a short text summary for context.

## Setup

1. Python 3.10+ recommended.
2. Create a virtualenv and install dependencies:

   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. Copy or create `.env` in the project root and set at least:

   ```env
   OPENAI_API_KEY=sk-...
   ```

4. Run migrations (Django’s built-in tables only) and the dev server:

   ```bash
   python manage.py migrate
   python manage.py runserver
   ```

5. Open `http://127.0.0.1:8000/` in your browser.

## Project layout (high level)

- `config/` — Django project settings and URL routing.
- `kitchen/views.py` — one view, agent loop, session memory, JSON response.
- `kitchen/nutrition_tools.py` — search + CSV tools for LangChain `bind_tools`.
- `kitchen/templates/kitchen/index.html` — form, cards (macros, recommendations), search block, disclaimer.
- `data/` — folder for the CSV log (the CSV file is ignored; `data/.gitkeep` is tracked).

## API shape (JSON POST response)

- `meals` — list of objects with: `meal`, `calories`, `protein`, `carbs`, `fats`, `ingredients`, `summary`, `recommendations`.
- `search_results` — object from the search tool, or `null` if the tool was not used.
- `assistant_message` — used when the model’s reply is not a JSON array (e.g. short follow-up text).
- `disclaimer` — same medical disclaimer string as in the page footer.
- `error` — `null` on success, or an error string.

## Git workflow (suggested for teams)

The repository can follow a **main**-first workflow and short-lived **feature** branches, for example:

| Branch (example) | What it might contain |
|------------------|------------------------|
| `main` | Stable, shippable code |
| `feature/nutrition-analysis` | System prompt, JSON contract, response normalization |
| `feature/tools` | `nutrition_tools.py`, agent loop, CSV path in settings |
| `feature/ui-update` | Template: macros, search section, disclaimer |
| `feature/memory` | Session history and summarization in `views.py` |

**Workflow:** open a branch from `main`, make small **logical commits** with messages such as `feat: …` or `ui: …`, open a PR, then merge to `main` so `main` always stays runnable. You can align one PR with each row above, or land several as separate commits in a single integrated branch, depending on team preference.

## License / lab use

Suitable for coursework or demos. Replace the mock search tool with a real map or vendor API if you go beyond a prototype.
