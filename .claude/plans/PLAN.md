# Plan: ACME Salary Management System

## Context
ACME's HR team manages salary data for 10,000 employees in several countries using spreadsheets. The assessment asks for an end-to-end web app that lets an HR Manager do two things: manage salary data, and answer questions about how the org pays people. Graders will look at:
- a one-page requirements doc
- clean architecture
- meaningful, fast, deterministic tests
- a seed script for 10k employees
- incremental commits
- artifacts showing how AI was used and the trade-offs made

The repo is already initialized and pushed to GitHub. It contains `.gitignore` and the requirements brief; there is no code yet.

**Decisions confirmed with the user**
- **Stack:** Python + FastAPI + SQLite on the backend, React (Vite + TypeScript + MUI) on the frontend.
- **Deployment:** local plus Docker (`docker-compose`) only, with no cloud deploy.
- **Currency:** salaries are stored in each country's local currency, and insights compare money only within a country. There is no FX conversion, and org-wide views show headcount only.
- **Auth:** full authentication with roles.
- **Project context:** all Claude context (plans, notes, prompts) lives in this project's `.claude/` folder and is committed with the repo.

## Approach overview
- The repo has two parts: `backend/` (FastAPI) and `frontend/` (Vite React), plus `docs/` for the artifacts.
- The backend has three layers:
  - routers (HTTP only)
  - services (business rules, RBAC-agnostic)
  - SQLAlchemy 2.0 models
- Pydantic v2 schemas sit at the boundary.
- Salary is stored as a **float** (annual, in local currency, e.g. `85000.50`). Pydantic validates it as positive and rounds it to 2 decimal places at the API boundary. Aggregates are rounded to 2 decimal places in responses, so float noise never shows up in the UI.
- Currency comes from the country through a config map, so it is never typed in freely.
- Every salary change writes an audit row. This gives the "how did pay change" story and replaces Excel's missing history.
- No national IDs or other sensitive identifiers are stored. Employee data is synthetic (Faker).

## Roles (RBAC)
| Role | Employees | Salaries | Insights | User mgmt |
|---|---|---|---|---|
| `admin` | CRUD | edit | view | CRUD users |
| `hr_manager` (primary persona) | CRUD | edit | view | – |
| `viewer` (e.g. finance/exec) | read | read | view | – |

Auth implementation:
- JWT bearer tokens (PyJWT) with expiry.
- Passwords hashed with `pwdlib[bcrypt]`.
- An OAuth2 password flow at `/api/auth/login`.
- A `require_roles(...)` FastAPI dependency.
- The seed script creates one user per role, with passwords taken from env and defaults documented.

## Data model (`backend/app/models/`)
- **`users`**: `id`, `email` (unique), `full_name`, `hashed_password`, `role` (enum), `is_active`, timestamps.
- **`employees`**: `id`, `employee_code` (unique, e.g. `ACME-00001`), `first_name`, `last_name`, `email` (unique), `job_title`, `department`, `country_code`, `currency` (derived), `salary` (float, annual), `employment_type` (full_time/part_time/contract), `hire_date`, `status` (active/terminated), timestamps.
  - Indexes on `country_code`, `department`, `job_title`, `status`, and `(country_code, job_title)`.
- **`salary_changes`**: `id`, `employee_id` FK, `old_salary` (float), `new_salary` (float), `effective_date`, `reason`, `changed_by_user_id` FK, `created_at`.
- **Reference data** lives in `app/core/reference.py`:
  - About 8 countries, each mapped to its currency (US/USD, GB/GBP, IN/INR, DE/EUR, CA/CAD, SG/SGD, AU/AUD, BR/BRL).
  - Departments, and job titles with per-country salary ranges used by the seed.
- Schema migrations use Alembic.

## API (`/api`, OpenAPI docs at `/docs`)
- **Auth:** `POST /auth/login`, `GET /auth/me`.
- **Users** (admin only): `GET/POST /users`, `PATCH /users/{id}` (role, active), `DELETE /users/{id}`.
- **Employees:**
  - `GET /employees`: server-side pagination (`page`, `page_size` ≤100), search `q` (name/email/code), filters (`country`, `department`, `job_title`, `status`, `employment_type`) and `sort`. Returns `{items, total, page, page_size}`.
  - `GET /employees/{id}`, `POST /employees`, `PATCH /employees/{id}` (write roles only).
  - Terminating an employee is a soft delete that sets `status=terminated`, so history is kept.
  - If a PATCH changes the salary, it must include `reason` and `effective_date`. The service writes a `salary_changes` row in the same transaction.
  - `GET /employees/{id}/salary-history`.
  - `GET /employees/export.csv` exports the filtered list as CSV. This is a direct bridge from Excel workflows.
- **Meta:** `GET /meta` returns countries+currencies, departments and job titles for dropdowns.
- **Insights** (money is always scoped to one country):
  - `GET /insights/overview`: org-wide headcount by country, department and employment type, with no money mixed across currencies. Per-country headcount and median salary are shown in local currency.
  - `GET /insights/country/{code}`: KPI tiles (headcount, min/p25/median/p75/max/mean, total payroll), plus breakdowns by department and by job title (count, median, mean, min, max).
  - `GET /insights/country/{code}/distribution?bins=`: salary histogram.
  - `GET /insights/country/{code}/outliers?threshold=0.3`: employees whose pay is more than ±30% from their job-title median in that country. This is a pay-equity prompt for HR.
  - How it is computed:
    - Aggregates (count/min/max/avg/sum) run in SQL with `GROUP BY`.
    - Percentiles and medians are computed in Python with `statistics.quantiles`, because SQLite has no percentile function. At most about 10k ints per query, which is cheap. This is documented in PERFORMANCE.md.

## Backend layout
```
backend/
  pyproject.toml            # uv-managed; ruff, pytest config
  alembic/ ...
  app/
    main.py                 # app factory, CORS, routers, serves nothing else
    core/config.py          # pydantic-settings (DB URL, JWT secret, expiry)
    core/security.py        # hash/verify, create/decode JWT
    core/reference.py       # countries/currencies/departments/titles
    db/session.py           # engine, SessionLocal, get_db
    models/                 # user.py, employee.py, salary_change.py
    schemas/                # pydantic in/out models
    services/               # employee_service.py, insights_service.py, user_service.py
    api/deps.py             # get_current_user, require_roles
    api/routes/             # auth.py, users.py, employees.py, insights.py, meta.py
  scripts/seed.py           # deterministic (Faker seed=42, random.Random(42)), bulk insert 10k
  tests/
    conftest.py             # in-memory SQLite (StaticPool), TestClient, user/token fixtures, small factories
    unit/                   # services: salary change audit, stats/percentiles, outliers, salary rounding/validation, security
    api/                    # endpoints: auth, RBAC matrix (parametrized), pagination/filter/sort, validation errors
```
- **Seed:** generates 10k employees with realistic per-country, per-title salary ranges and a log-normal spread. It also adds a few historical salary changes for a subset, then inserts with `session.execute(insert(...), rows)` in batches. The target is under 5s. It is idempotent (`--reset` flag).
- **Tests:** they never use the seed's 10k rows. Small explicit fixtures keep them fast and deterministic, with a coverage target of ≥85% on services.

## Frontend layout (`frontend/`, Vite + React + TS)
- **Libraries:**
  - UI and charts: MUI, MUI X DataGrid (community, server-side mode), Recharts.
  - Data and routing: TanStack Query, React Router, axios.
  - Forms and validation: react-hook-form + zod.
- **Structure:** `src/api/` (typed client + hooks), `src/auth/` (AuthContext, token in memory + localStorage, `RequireRole` guard), `src/pages/`, `src/components/`.
- **Pages:**
  - **Login.**
  - **Employees:**
    - The DataGrid has a debounced search, filter bar (country/department/title/status) and server-side sort/pagination.
    - Salaries are formatted with `Intl.NumberFormat` in local currency.
    - There is a CSV export button and an "Add employee" dialog.
  - **Employee detail drawer/page:** profile edit form, a salary-change form (reason + effective date), and a salary history timeline/table.
  - **Insights:**
    - The overview shows headcount charts plus a per-country table.
    - Picking a country shows KPI tiles, a median-by-department bar chart, a salary histogram, a job-title table, and an outliers list linking to employees.
  - **Users** (admin only): list, create, change role, deactivate.
- Write actions are hidden or disabled for `viewer`. Their pages are still guarded on the server.
- **Tests:** Vitest + React Testing Library + MSW cover the login flow, role-based visibility, the employees table with mocked paginated data, salary form validation and currency formatting.

## Docker
- **Backend:** `backend/Dockerfile` (python-slim, uv). The entrypoint runs `alembic upgrade head` and then seeds the DB if it is empty.
- **Frontend:** `frontend/Dockerfile` is a multi-stage build: Node build, then nginx serving `dist` and proxying `/api` to the backend.
- **Compose:** `docker-compose.yml` wires the two services together and puts the SQLite file on a named volume. `docker compose up` gives a working app at `http://localhost:8080`.

## Artifacts
- **`.claude/`** (committed): this plan at `.claude/plans/PLAN.md`, a project `CLAUDE.md` with conventions and commands, and the key prompts used.
- **`docs/REQUIREMENTS.md`:** one page covering the goal, persona, in-scope features, and what is deliberately out of scope, with reasons. Out of scope:
  - FX conversion
  - bulk Excel import
  - payroll/tax processing
  - approvals workflow
  - SSO
  - multi-tenancy
  - cloud deploy
- **`docs/ARCHITECTURE.md`:** Mermaid diagrams (components, ER diagram, request flow).
- **`docs/DECISIONS.md`:** trade-offs, such as:
  - SQLite vs Postgres
  - salary as a float (rounded to 2 decimal places at the boundary) instead of integer minor units
  - local-currency-only insights
  - soft delete
  - Python percentiles
  - JWT in localStorage vs cookies
- **`docs/PERFORMANCE.md`:** indexes, pagination, query timings on 10k rows, and seed timing.
- **`docs/AI_USAGE.md`:** the prompts and instructions used, where AI output was corrected, and how correctness was verified.
- **`README.md`:** quick start (local dev and Docker), default credentials, and how to run tests.

## Repository
- **Remote:** `origin` = `git@github.com:rishabh-22/SalaryManagementSystem.git`. The user already initialized the repo; the branch is `master`.
- **Push access:** verified on 2026-10-19. `.gitignore` and the requirements doc are already on `origin/master`.
- **Pushing:**
  - Port 22 is blocked on this network, so push over port 443 with `GIT_SSH_COMMAND="ssh -o HostName=ssh.github.com -o Port=443" git push`. This override isn't needed if the user adds a `~/.ssh/config` entry.
  - Push after each milestone commit, so the history on GitHub shows how the solution evolved.
- **Git identity:** none is configured, so commit with `git -c user.name="Rishabh Bhardwaj" -c user.email="rishabh.bhardwaj@ust.com"`.
- **Commit messages:** concise, conventional-style (`feat(api): ...`, `test: ...`, `docs: ...`), with the Co-Authored-By trailer.

## Commit sequence (incremental, each pushed to origin/master)
1. Fill in `.gitignore` (Python, Node, SQLite, env), then add `.claude/plans/PLAN.md`, a project `CLAUDE.md` and `docs/REQUIREMENTS.md`.
2. Backend scaffold: config, DB session, health endpoint, pytest setup.
3. Models + Alembic migration + reference data.
4. Auth: security utils, login/me, `require_roles`, plus tests.
5. Employees CRUD + pagination/filter/sort, plus tests.
6. Salary changes + history + audit, plus tests.
7. Insights service + endpoints, plus unit tests for the statistics.
8. Users admin endpoints + RBAC matrix tests.
9. Seed script (10k), with timing noted.
10. Frontend scaffold, auth flow and layout.
11. Employees grid + detail/edit/salary forms.
12. Insights dashboard.
13. Users admin page + role-based UI.
14. Frontend tests.
15. CSV export.
16. Dockerfiles + compose.
17. Docs: architecture, decisions, performance, AI usage, README.

## Verification
- `cd backend && uv run pytest --cov=app` should pass with coverage reported. `uv run ruff check .` should be clean.
- `uv run python -m scripts.seed --reset` should insert 10,000 employees, with the time it takes logged.
- `uv run uvicorn app.main:app --reload`, then manual checks in `/docs`:
  - log in as each role
  - confirm a viewer gets 403 on writes
  - change a salary and confirm the history row appears
  - check the insights numbers for one country against a direct SQL query
- `cd frontend && npm test && npm run build` should pass. With `npm run dev`, click through:
  - login
  - search/filter/sort the grid across 10k rows
  - edit an employee
  - make a salary change
  - the insights per country
  - the users page as admin, and confirm it is hidden as viewer
- `docker compose up --build` should serve the app at localhost:8080 with seeded data, and the full flow should work there.
- `git log --oneline` should show the incremental history, and `git status` should be clean and in sync with `origin/master` on GitHub.
