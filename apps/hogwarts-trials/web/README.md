# Hogwarts Trials Web

A playable public practice-quiz frontend using Next.js 16.3.3, React 19 and strict TypeScript. Original CSS ornamentation, system fonts, midnight blue, parchment and gold create a responsive study-room experience without external assets.

## Screens and behavior

- `/`: introduction and API-driven discovery, with title, description and question count.
- `/quizzes/[quizId]`: single-choice and multiple-choice player, question navigation, answered progress, clear/skip actions and explicit unanswered submission notice.
- The same player displays server totals, per-question outcomes and submitted selections after grading. Replay clears the run; discovery is always reachable.

Native radios/checkboxes, fieldsets, focus indicators, keyboard controls, live status messages and reduced-motion styles support accessibility. Loading, empty catalog, missing configuration, unavailable service, malformed responses and retry states are included. Grading errors preserve selections; concurrent final submissions are blocked. Answers remain in component memory only; navigating away or refreshing clears them.

## Run locally

Use the repository-pinned Node 24.20.0 and pnpm 11.21.0. From the repository root:

```powershell
pnpm install --frozen-lockfile
uv sync --frozen --all-packages --group dev
uv run --package hogwarts-trials-api uvicorn hogwarts_trials_api.main:app --reload --host 127.0.0.1 --port 8000
```

In a second PowerShell terminal:

```powershell
$env:HOGWARTS_TRIALS_API_URL = 'http://127.0.0.1:8000'
pnpm --filter hogwarts-trials-web run dev
```

Open http://localhost:3000. Keep configuration in the process environment; the repository validator rejects local environment files even when Git ignores them. Restart Next.js after changing configuration. The backend defaults to its synthetic in-memory catalog; no database or credentials are needed. See the [API README](../api/README.md) for backend configuration.

## Integration boundary

The backend URL is server-only configuration, an HTTP(S) origin with no credentials, path, query or fragment. It is never a `NEXT_PUBLIC` variable. Browser requests use these fixed same-origin Next.js handlers:

| Next.js route | FastAPI operation |
| --- | --- |
| `GET /api/quizzes` | `GET /api/v1/quizzes` |
| `GET /api/quizzes/[quizId]` | `GET /api/v1/quizzes/{quiz_id}` |
| `POST /api/quizzes/[quizId]/grade` | `POST /api/v1/quizzes/{quiz_id}/grade` |

Handlers validate UUIDs, project only public DTO fields, disable caching and redirects, and enforce an eight-second upstream timeout (including response decoding). Invalid requests return 400; upstream 404/422 map to controlled messages, malformed success responses to 502, unavailable service/configuration to 503, and timeout to 504. Raw errors, unexpected fields and answer keys are never forwarded. No cookies, authorization headers or arbitrary browser-supplied URLs are forwarded. Production builds require neither backend configuration nor a running API.

Grading sends `{ submissions: [{ question_id, selected_choice_ids }] }`, omitting unanswered questions entirely. The backend alone grades; the client checks result shape, totals consistency, quiz/question IDs and echoed selections. It never infers correct answers or supplies explanations. Grading is stateless, not saved account progression. Current questions are synthetic demonstration material, not curated Harry Potter canon. Authentication, saved runs/history, sorting, house points and leaderboards remain deferred; protected attempt endpoints are unused.

## Validation

```powershell
pnpm --filter hogwarts-trials-web run lint
pnpm --filter hogwarts-trials-web run typecheck
pnpm --filter hogwarts-trials-web run test
pnpm --filter hogwarts-trials-web run build
pnpm --filter hogwarts-trials-web run start
python scripts/validate_repository.py
python scripts/validate_toolchain.py
python scripts/validate_contract_schemas.py
python -m unittest discover -s scripts/tests
```

Tests use the native Node runner and synthetic fixtures with injected fetch functions. They require no live API, secrets or network and run in the web validation workflow.

## Troubleshooting

- **Not configured:** set the server environment variable above and restart Next.js. The application can still build and render without it.
- **Unavailable/timeout:** check that FastAPI is running and reachable from the Next.js server; then use the on-page retry action. No catalog is fabricated.
- **Not found:** return to discovery; the quiz may no longer be available.
- **Submission rejected:** review selections and retry. Answers remain in memory.
- **Unexpected response:** confirm frontend/backend contract compatibility. Private upstream details are intentionally hidden.

This is an unofficial fan project, not affiliated with or endorsed by franchise owners.
