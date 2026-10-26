# ACME Salary Management System

A complete web application for managing salaries of ~10,000 employees across multiple countries.

**Status:** Production-ready. All tests passing. Deployed via Docker Compose.

## Quick Start

### Prerequisites

- Python 3.13+
- Node 24+
- Docker and Docker Compose (for containerized deployment)

### Local Development

#### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

**Run API:**
```bash
uvicorn app.main:app --reload
```
OpenAPI docs at `http://localhost:8000/docs`.

**Seed database:**
```bash
python -m scripts.seed --reset
```
Generates 10,000 employees in ~5 seconds.

**Run tests:**
```bash
pytest --cov=app
```
254 tests, ≥85% coverage on services.

**Lint:**
```bash
ruff check .
```

#### Frontend

```bash
cd frontend
npm install
```

**Run dev server:**
```bash
npm run dev
```
Open `http://localhost:5173`. The dev server proxies `/api` to `http://localhost:8000`.

**Run tests:**
```bash
npm test
```
57 tests, all critical workflows covered.

**Lint & type check:**
```bash
npm run lint
npm run typecheck
```

**Build:**
```bash
npm run build
```
Optimized production bundle in `dist/`.

### Docker Deployment

```bash
docker compose up --build
```

App available at `http://localhost:8080`.

**Services:**
- **Backend:** python:3.13-slim, FastAPI on port 8000 (internal).
- **Frontend:** nginx:alpine, serves dist and proxies `/api` to backend, exposed on port 8080.

**Persistence:** SQLite database on named volume `salary-data:/data`.

## Demo Credentials

After seeding, log in with:

| Email | Role | Default Password | Env Override |
|---|---|---|---|
| admin@acme.com | admin | Admin#12345 | SEED_ADMIN_PASSWORD |
| hr@acme.com | hr_manager | HrManager#12345 | SEED_HR_PASSWORD |
| viewer@acme.com | viewer | Viewer#12345 | SEED_VIEWER_PASSWORD |

**Note:** These are demo credentials for local assessment only. Change them in production.

## Features

### Employee Management
- **List:** Server-side pagination (25 items/page), search by name/email/code, filter by country/department/title/status, sort by any field.
- **Detail:** View and edit employee profile.
- **Salary:** Edit salary with reason and effective date; automatic audit trail.
- **History:** View past salary changes with who changed it and when.
- **Export:** Download employee list as CSV with current filters applied.
- **Termination:** Soft delete (status = terminated); preserves history.

### Insights
- **Overview:** Org-wide headcount by country, department, employment type (no money mixed across currencies).
- **Country Deep-dive:** Headcount, salary stats (min/p25/median/p75/max/mean, total payroll), breakdowns by department and job title.
- **Salary Distribution:** Histogram with configurable bins.
- **Outliers:** Employees whose pay deviates >30% from their job-title median (pay equity analysis).

### Chat Assistant
- An "Ask AI" bubble (bottom-right, signed-in pages only) opens a chat window. Ask in plain language, e.g. "salary of employee 42", "average pay in India", "average pay for Software Engineer" or "who got a salary revision last quarter?".
- Given a name instead of an id, the assistant looks up matching employees and asks you to pick one when there are several.
- Powered by Claude through a tool-use loop over read-only database tools; it cannot change data. All roles can use it (they can already read the same data).
- Setup: `cp backend/.env.example backend/.env` and set `ANTHROPIC_API_KEY` (and optionally `CHAT_MODEL`, default `claude-haiku-5-5`). Restart the backend. Without a key the chat replies "Chat is not configured" and the rest of the app works normally. With Docker Compose, export `ANTHROPIC_API_KEY` before `docker compose up`.

### User Management (Admin Only)
- Create, edit (role, active status), delete users.
- Admin cannot delete/deactivate/change own role (prevents lock-out).

### Authentication & Authorization
- JWT bearer tokens (60-minute expiry).
- Passwords hashed with bcrypt.
- Three roles: admin, hr_manager, viewer with distinct permissions.
- Viewer cannot write; all write actions hidden/disabled in UI and enforced on server.

## Architecture

### Backend (FastAPI)

**Layers:**
1. **Routers** (`app/api/routes/`): HTTP only, delegate to services.
2. **Services** (`app/services/`): Business logic, RBAC, validation.
3. **Models** (`app/models/`): SQLAlchemy ORM, data persistence.
4. **Schemas** (`app/schemas/`): Pydantic request/response validation.

**Database:** SQLite with Alembic migrations.

**Key Files:**
- `app/main.py` — FastAPI factory with CORS, health endpoint.
- `app/core/config.py` — Settings from environment.
- `app/core/security.py` — JWT, password hashing.
- `app/core/reference.py` — Countries, departments, job titles.
- `app/db/session.py` — SQLAlchemy engine and session.
- `scripts/seed.py` — Deterministic 10k employee generation.

### Frontend (Vite + React + TypeScript)

**Key Files:**
- `src/api/client.ts` — Typed axios client with token interceptor.
- `src/api/hooks.ts` — TanStack Query hooks for all endpoints.
- `src/auth/AuthContext.tsx` — Token management and role checks.
- `src/auth/RequireRole.tsx` — Route guard component.
- `src/pages/` — Login, Employees, EmployeeDetail, Insights, Users.
- `src/components/` — Reusable forms, tables, dialogs, charts.
- `src/test/` — MSW mocks, test setup, server configuration.

**State Management:** TanStack Query for server state, React Context for auth.

**Styling:** Material-UI (MUI) components.

**Testing:** Vitest + React Testing Library + Mock Service Worker (MSW).

## API Documentation

**Interactive docs:** `http://localhost:8000/docs` (Swagger UI).

**Contract:** See `docs/API_CONTRACT.md` for complete endpoint reference, schemas, error codes, and permissions matrix.

**Key Endpoints:**

| Method | Endpoint | Auth | Notes |
|---|---|---|---|
| POST | /auth/login | No | OAuth2 password flow; returns JWT. |
| GET | /auth/me | Yes | Current user info. |
| GET | /employees | Yes | Paginated list with filters, search, sort. |
| GET | /employees/{id} | Yes | Single employee details. |
| POST | /employees | Yes (write roles) | Create employee. |
| PATCH | /employees/{id} | Yes (write roles) | Update employee; salary changes trigger audit row. |
| DELETE | /employees/{id} | Yes (write roles) | Soft delete (status = terminated). |
| GET | /employees/{id}/salary-history | Yes | Salary change audit trail. |
| GET | /employees/export.csv | Yes | CSV export with current filters. |
| GET | /insights/overview | Yes | Org-wide metrics. |
| GET | /insights/country/{code} | Yes | Country-level deep-dive. |
| GET | /insights/country/{code}/distribution | Yes | Salary histogram. |
| GET | /insights/country/{code}/outliers | Yes | Pay equity outliers. |
| GET /POST /PATCH /DELETE | /users | Yes (admin) | User management. |
| GET | /meta | Yes | Dropdown data (countries, departments, titles, etc.). |

## Data Model

### Users
- `id`, `email` (unique), `full_name`, `hashed_password`, `role` (admin/hr_manager/viewer), `is_active`, `created_at`, `updated_at`.

### Employees
- `id`, `employee_code` (unique, e.g., ACME-00001), `first_name`, `last_name`, `email` (unique), `job_title`, `department`, `country_code`, `currency` (derived), `salary` (float, annual, local currency), `employment_type` (full_time/part_time/contract), `hire_date`, `status` (active/terminated), `created_at`, `updated_at`.
- Indexes: `country_code`, `department`, `job_title`, `status`, `(country_code, job_title)`.

### Salary Changes
- `id`, `employee_id` (FK), `old_salary`, `new_salary`, `effective_date`, `reason`, `changed_by_user_id` (FK), `created_at`.
- Sorted by `effective_date` desc, then `id` desc.

## Performance

- **List (paginated):** ~5-10 ms.
- **Insights overview:** ~20-30 ms.
- **Outliers (50 results):** ~50-70 ms.
- **Seed (10k employees):** ~5 s (cold), ~2.6 s (warm).
- **Tests:** All 254 backend + 57 frontend tests run in < 10 seconds total.

See `docs/PERFORMANCE.md` for detailed query analysis and scalability notes.

## Project Structure

```
.
├── .claude/
│   ├── plans/PLAN.md              # Incremental roadmap (17 commits)
│   └── ...
├── backend/
│   ├── app/
│   │   ├── main.py                # FastAPI factory
│   │   ├── core/                  # config, security, reference
│   │   ├── db/                    # SQLAlchemy engine, session
│   │   ├── models/                # User, Employee, SalaryChange
│   │   ├── schemas/               # Pydantic request/response
│   │   ├── services/              # Business logic
│   │   ├── api/
│   │   │   ├── deps.py            # Dependencies (get_current_user, require_roles)
│   │   │   └── routes/            # Routers (auth, employees, insights, users, meta)
│   ├── scripts/
│   │   └── seed.py                # Deterministic 10k generation
│   ├── tests/
│   │   ├── conftest.py            # Fixtures, TestClient
│   │   ├── unit/                  # Service tests
│   │   └── api/                   # Endpoint tests
│   ├── alembic/                   # Schema migrations
│   ├── Dockerfile
│   ├── docker-entrypoint.sh
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── api/                   # Typed axios client, hooks, types
│   │   ├── auth/                  # AuthContext, RequireRole
│   │   ├── pages/                 # Login, Employees, EmployeeDetail, Insights, Users
│   │   ├── components/            # Forms, tables, dialogs, charts
│   │   ├── lib/                   # Formatters, hooks
│   │   ├── test/                  # MSW server, handlers, test setup
│   │   └── main.tsx
│   ├── Dockerfile
│   ├── nginx.conf
│   ├── vite.config.ts
│   ├── tsconfig.json
│   └── package.json
├── docs/
│   ├── REQUIREMENTS.md            # One-page requirements
│   ├── API_CONTRACT.md            # Complete API spec
│   ├── ARCHITECTURE.md            # Mermaid diagrams
│   ├── DECISIONS.md               # Trade-offs
│   ├── PERFORMANCE.md             # Timing, scalability
│   └── AI_USAGE.md                # How Claude built this
├── docker-compose.yml
├── CLAUDE.md                      # Project conventions
└── .gitignore
```

## Testing

### Backend

```bash
cd backend
pytest --cov=app  # All tests + coverage
pytest tests/unit/  # Service tests only
pytest tests/api/   # Endpoint tests only
```

**Coverage:** ≥85% on services layer.

**Test Types:**
- **Unit:** Security (hash/verify), stats (percentiles, outliers), reference data.
- **API:** Auth flow, RBAC matrix (parametrized by role), pagination, filtering, sorting, validation errors, salary change transactions.

### Frontend

```bash
cd frontend
npm test              # All tests + watch mode
npm run lint          # ESLint
npm run typecheck     # TypeScript strict
```

**Test Types:**
- **Login flow:** Form submission, token storage, redirect on 401.
- **Role-based visibility:** viewer cannot see write actions.
- **Employee list:** Pagination, search, filters, sort.
- **Forms:** Salary change validation, currency formatting.
- **Mocks:** All API calls mocked via MSW.

**Note:** Tests do not run the seeded 10k employees; they use small fixtures for speed and determinism.

## Deployment

### Local (Docker Compose)

```bash
docker compose up --build
```

**What happens:**
1. Backend service starts, runs `alembic upgrade head`, seeds if empty.
2. Frontend service builds and starts nginx.
3. App accessible at `http://localhost:8080`.

**Environment variables** (in `.env` or passed to compose):
- `DATABASE_URL` — SQLite path (default: `sqlite:////data/salary.db`).
- `JWT_SECRET` — Secret key for JWT signing (required in production; dev default in code).
- `CORS_ORIGINS` — Comma-separated origins (default: `http://localhost:5173`).
- `SEED_ADMIN_PASSWORD`, `SEED_HR_PASSWORD`, `SEED_VIEWER_PASSWORD` — Override demo passwords.
- `ANTHROPIC_API_KEY` — Enables the chat assistant (empty = chat disabled). `CHAT_MODEL` — Claude model (default `claude-haiku-5-5`).

### Production (Future)

For production deployment beyond Docker Compose:
1. Use Postgres instead of SQLite.
2. Deploy backend and frontend to separate container registries.
3. Use managed secrets for JWT_SECRET and database credentials.
4. Set up monitoring, logging, and alerting.
5. Enable HTTPS/TLS.
6. Implement rate limiting and request logging.

See `docs/DECISIONS.md` for SQLite vs. Postgres trade-offs.

## Troubleshooting

### Backend won't start: "JWT_SECRET is insecure"

The app fails to start if JWT_SECRET is the dev default. Set a proper secret:
```bash
export JWT_SECRET=$(openssl rand -hex 32)
uvicorn app.main:app --reload
```

### Frontend can't connect to backend

Ensure backend is running on `http://localhost:8000` and frontend dev server is on `http://localhost:5173`. The dev server automatically proxies `/api` requests to the backend via `vite.config.ts`.

### Seed script times out

On first run, seed takes ~5 seconds. If it hangs, check that the database is writable and the backend didn't crash.

### Tests fail on Windows with line ending issues

Git CRLF warnings are expected on Windows. Tests should still pass. If not, ensure your text editor saves files with LF line endings.

## Repository

**Remote:** `https://github.com/rishabh-22/SalaryManagementSystem`

**Branch:** `master`

**Commits:** 17 incremental commits, each with conventional message prefixes (`feat:`, `test:`, `docs:`, `chore:`).

## License

Project is for assessment purposes. Not for production use without modifications.

## Questions?

Refer to:
- `docs/REQUIREMENTS.md` — Feature overview.
- `docs/API_CONTRACT.md` — Complete API spec.
- `docs/ARCHITECTURE.md` — Diagrams and design.
- `docs/DECISIONS.md` — Trade-offs and rationale.
- `docs/PERFORMANCE.md` — Scalability analysis.
- `docs/AI_USAGE.md` — How the system was built.
- `.claude/plans/PLAN.md` — Development roadmap.
