# API Contract

Single source of truth shared by the backend, frontend and testing agents. If something here is wrong or missing, **do not improvise silently**: report it to the lead so the contract is updated for everyone.

## 1. Conventions
- Base path `/api`. JSON in/out unless noted. Interactive docs at `/docs`.
- Backend listens on `:8000`. Vite dev server on `:5173` proxies `/api` to `:8000`; CORS also allows `http://localhost:5173`. In Docker, nginx on `:8080` serves the frontend and proxies `/api` to `backend:8000`.
- Auth: `Authorization: Bearer <jwt>` on every endpoint except `POST /api/auth/login` and `GET /api/health`.
- Salary: float, annual, in the employee's **local currency**. Validated `> 0` and rounded to 2 dp on input; every money value in responses (including aggregates) is rounded to 2 dp.
- Dates: ISO `YYYY-MM-DD`. Timestamps: ISO 8601 UTC.
- Insights **never mix currencies**: money figures are always scoped to a single country.
- Insights count **active employees only**. The employee list shows all unless filtered by `status`.

### Errors
| Status | When | Body |
|---|---|---|
| 401 | missing/invalid/expired token, bad login, inactive user | `{"detail": "<message>"}` |
| 403 | role not allowed | `{"detail": "<message>"}` |
| 404 | unknown id / country code | `{"detail": "<message>"}` |
| 409 | duplicate email | `{"detail": "<message>"}` |
| 422 | validation failure | FastAPI default: `{"detail": [{"loc": [...], "msg": "...", "type": "..."}]}` |
| 400 | business rule (e.g. admin modifying own role) | `{"detail": "<message>"}` |

### Enums
- `role`: `admin` | `hr_manager` | `viewer`
- `employment_type`: `full_time` | `part_time` | `contract`
- `status`: `active` | `terminated`

### Permissions
| Endpoint group | admin | hr_manager | viewer |
|---|---|---|---|
| auth, meta, `GET` employees, salary history, insights | yes | yes | yes |
| `POST/PATCH/DELETE` employees | yes | yes | no (403) |
| `GET /employees/export.csv` | yes | yes | yes (read-only) |
| `/users*` | yes | no (403) | no (403) |

## 2. Endpoints

### Health and meta
- `GET /api/health` -> `{"status": "ok"}` (no auth)
- `GET /api/meta` ->
```json
{
  "countries": [{"code": "US", "name": "United States", "currency": "USD"}],
  "departments": ["Engineering", "..."],
  "job_titles": ["Software Engineer", "..."],
  "employment_types": ["full_time", "part_time", "contract"],
  "statuses": ["active", "terminated"],
  "roles": ["admin", "hr_manager", "viewer"]
}
```
Countries: US/USD, GB/GBP, IN/INR, DE/EUR, CA/CAD, SG/SGD, AU/AUD, BR/BRL.
Departments: Engineering, Product, Design, Sales, Marketing, Finance, HR, Operations, Customer Support, Legal.

### Auth
- `POST /api/auth/login` — **form-encoded** (`application/x-www-form-urlencoded`, OAuth2 password flow) with `username` (the email) and `password`.
  -> `200 {"access_token": "<jwt>", "token_type": "bearer"}`; bad credentials or inactive user -> 401.
  JWT claims: `sub` (user id as string), `role`, `exp`. Default expiry 60 min (`ACCESS_TOKEN_EXPIRE_MINUTES`).
- `GET /api/auth/me` -> `User`

`User`:
```json
{"id": 1, "email": "hr@acme.com", "full_name": "Hannah Reed", "role": "hr_manager", "is_active": true, "created_at": "2026-01-01T00:00:00Z"}
```

### Users (admin only)
- `GET /api/users` -> `User[]` (ordered by id)
- `POST /api/users` body `{email, full_name, password (min 8), role}` -> 201 `User`; duplicate email -> 409
- `PATCH /api/users/{id}` body any of `{full_name, role, is_active, password}` -> `User`
- `DELETE /api/users/{id}` -> 204
- An admin cannot delete, deactivate or change the role of **themselves** -> 400.

### Employees
`Employee`:
```json
{
  "id": 1, "employee_code": "ACME-00001",
  "first_name": "Ana", "last_name": "Silva", "email": "ana.silva@acme.com",
  "job_title": "Software Engineer", "department": "Engineering",
  "country_code": "BR", "currency": "BRL",
  "salary": 185000.5,
  "employment_type": "full_time", "hire_date": "2021-03-15", "status": "active",
  "created_at": "...", "updated_at": "..."
}
```
`currency` is derived from `country_code`; clients never send it. `employee_code` is server-generated as `ACME-` + id zero-padded to 5 digits.

- `GET /api/employees` — query params:
  | param | notes |
  |---|---|
  | `page` | default 1, >= 1 |
  | `page_size` | default 25, 1–100 |
  | `q` | case-insensitive substring over first name, last name, email, employee code |
  | `country`, `department`, `job_title`, `status`, `employment_type` | exact match |
  | `sort` | field name, prefix `-` for descending. Allowed: `id`, `employee_code`, `first_name`, `last_name`, `job_title`, `department`, `country_code`, `salary`, `hire_date`, `status`. Default `id`. Unknown field -> 422. Ties broken by `id`. |

  -> `{"items": Employee[], "total": 10000, "page": 1, "page_size": 25}`
- `GET /api/employees/export.csv` — same filters and `sort` as the list, no pagination. `text/csv`, header `Content-Disposition: attachment; filename="employees.csv"`. Columns: `employee_code,first_name,last_name,email,job_title,department,country_code,currency,salary,employment_type,hire_date,status`. Route must be declared **before** `/{id}`.
- `GET /api/employees/{id}` -> `Employee`
- `POST /api/employees` (admin, hr_manager) body: `first_name, last_name, email, job_title, department, country_code, employment_type, hire_date, salary` -> 201 `Employee` (status `active`). Duplicate email -> 409; unknown country/department/job title -> 422. Creating does **not** write a salary-history row.
- `PATCH /api/employees/{id}` (admin, hr_manager) body: any of `first_name, last_name, email, job_title, department, country_code, employment_type, hire_date, status, salary, salary_change_reason, salary_effective_date`.
  - If `salary` is present **and differs** from the current salary, both `salary_change_reason` (non-empty) and `salary_effective_date` are required, else 422. The employee update and the `salary_changes` row are written in **one transaction**.
  - If `salary` is present but equal to the current salary, no history row is written.
  - If `country_code` changes, `currency` follows automatically.
- `DELETE /api/employees/{id}` (admin, hr_manager) -> soft delete: sets `status = terminated`, returns 200 `Employee`. Idempotent.
- `GET /api/employees/{id}/salary-history` -> `SalaryChange[]` newest first (by `effective_date` desc, then `id` desc)

`SalaryChange`:
```json
{"id": 1, "employee_id": 1, "old_salary": 100000.0, "new_salary": 110000.0, "effective_date": "2026-04-01", "reason": "Annual review", "changed_by": {"id": 2, "full_name": "Hannah Reed"}, "created_at": "..."}
```

### Insights
All require auth (any role). Unknown country code -> 404. Money is in the country's local currency.

`Summary` (a country, department or job-title group; all money rounded to 2 dp; for an empty group `headcount` is 0 and every other number is `null`):
`{"headcount", "min", "p25", "median", "p75", "max", "mean", "total_payroll"}`

Percentile method (so numbers are reproducible): `statistics.quantiles(values, n=4, method="inclusive")` for p25/p75; `statistics.median` for the median. With a single value, p25 = median = p75 = that value.

- `GET /api/insights/overview` ->
```json
{
  "total_headcount": 9500,
  "by_country": [{"country_code": "US", "currency": "USD", "headcount": 2000, "median_salary": 95000.0, "mean_salary": 98000.12}],
  "by_department": [{"department": "Engineering", "headcount": 1500}],
  "by_employment_type": [{"employment_type": "full_time", "headcount": 8000}]
}
```
`by_*` lists are sorted by `headcount` descending, ties by name/code ascending.
- `GET /api/insights/country/{code}` ->
```json
{
  "country_code": "US", "currency": "USD",
  "summary": {"headcount": 2000, "min": 0, "p25": 0, "median": 0, "p75": 0, "max": 0, "mean": 0, "total_payroll": 0},
  "by_department": [{"department": "Engineering", "summary": {"...Summary": ""}}],
  "by_job_title": [{"job_title": "Software Engineer", "summary": {"...Summary": ""}}]
}
```
Groups sorted by `headcount` descending, ties by name ascending. Groups with no active employees are omitted.
- `GET /api/insights/country/{code}/distribution?bins=10` (`bins` 1–50, default 10) ->
`{"country_code", "currency", "bins": [{"lower": 50000.0, "upper": 60000.0, "count": 12}]}`.
Equal-width bins between min and max; each bin is `[lower, upper)` except the last, which includes `upper`. If every salary is equal, return a single bin with `lower == upper`. No employees -> `"bins": []`.
- `GET /api/insights/country/{code}/outliers?threshold=0.3&limit=50` (`threshold` > 0, default 0.3; `limit` 1–200) ->
```json
{"country_code": "US", "currency": "USD", "threshold": 0.3,
 "items": [{"employee_id": 5, "employee_code": "ACME-00005", "full_name": "A B", "job_title": "Software Engineer", "salary": 150000.0, "job_title_median": 100000.0, "deviation": 0.5}]}
```
`deviation = (salary - job_title_median) / job_title_median` (signed, rounded to 4 dp). An employee is an outlier when `abs(deviation) > threshold`. Only job titles with **at least 3 active employees** in that country are evaluated (avoids noise). Sorted by `abs(deviation)` descending, then `employee_id`.

### Chat
- `POST /api/chat` (any authenticated role). Stateless: the client sends the conversation so far.
  Body: `{"messages": [{"role": "user" | "assistant", "content": "..."}]}` — 1–20 messages, each 1–2000 non-blank characters, and the last one must be from `user` (else 422).
  -> `200 {"reply": "...", "tools_used": ["search_employees", "get_employee_salary"]}`
  - `503 {"detail": "Chat is not configured"}` when the selected provider's API key is empty (`OPENAI_API_KEY`, or `ANTHROPIC_API_KEY` when `USE_ANTHROPIC_KEY=true`); `502 {"detail": "The assistant is unavailable right now"}` when the provider call fails.
- The reply comes from an LLM tool-use loop, at most `CHAT_MAX_TOOL_ITERATIONS` model calls. The provider is chosen by `USE_ANTHROPIC_KEY`: `true` = Anthropic (`ANTHROPIC_MODEL`), otherwise OpenAI (`OPENAI_MODEL`, default `gpt-4o`). The request and response shapes are identical for both. Tools are read-only: `search_employees`, `get_employee_salary`, `get_salary_history`, `get_average_pay` (by country and/or job title, per country in local currency), `list_salary_revisions` (by `effective_date` range), `get_current_date` (today and the previous calendar quarter). Tool failures are returned to the model as error results, not as HTTP errors.

## 3. Seed script
`python -m scripts.seed [--reset] [--count 10000]`, run from `backend/`.
- Deterministic (`random.Random(42)`, `Faker.seed(42)`); 10,000 employees by default, spread across all 8 countries; ~95% active.
- Realistic per-country, per-job-title salary ranges with a log-normal spread; some historical `salary_changes` rows for a subset.
- Bulk inserts in batches; target well under 10 s.
- Without `--reset` it is a no-op if employees already exist (idempotent). `--reset` drops and recreates data.
- Always ensures three demo users exist (passwords overridable via env):
  | email | role | default password | env override |
  |---|---|---|---|
  | `admin@acme.com` | admin | `Admin#12345` | `SEED_ADMIN_PASSWORD` |
  | `hr@acme.com` | hr_manager | `HrManager#12345` | `SEED_HR_PASSWORD` |
  | `viewer@acme.com` | viewer | `Viewer#12345` | `SEED_VIEWER_PASSWORD` |
  These are demo credentials for a local assessment build only.

## 4. Backend module interface (so tests can be written in parallel)
- `app.main`: `create_app() -> FastAPI` and module-level `app`. Routers mounted under `/api`.
- `app.db.base.Base` (SQLAlchemy `DeclarativeBase`); `app.models` imports all models (`User`, `Employee`, `SalaryChange`) so `Base.metadata.create_all` works.
- `app.db.session`: `get_db()` FastAPI dependency yielding a `Session`; tests override it with an in-memory SQLite engine (`StaticPool`, `check_same_thread=False`).
- `app.core.config.settings` (pydantic-settings): `DATABASE_URL` (default `sqlite:///./salary.db`), `JWT_SECRET`, `JWT_ALGORITHM` (HS256), `ACCESS_TOKEN_EXPIRE_MINUTES` (60), `CORS_ORIGINS`.
- `app.core.security`: `hash_password(plain) -> str`, `verify_password(plain, hashed) -> bool`, `create_access_token(subject: str, role: str, expires_delta: timedelta | None = None) -> str`, `decode_access_token(token) -> dict` (raises on invalid or expired).
- `app.core.reference`: `COUNTRIES` (code -> name/currency), `DEPARTMENTS`, `JOB_TITLES`.
- `app.services.stats` (pure functions, no DB): `summarize(values: list[float]) -> dict` returning exactly the `Summary` keys (`headcount`, `min`, `p25`, `median`, `p75`, `max`, `mean`, `total_payroll`; empty input -> headcount 0, rest `None`); `histogram(values: list[float], bins: int) -> list[dict]` with `lower/upper/count`; `deviation(salary: float, median: float) -> float`.
- Model columns as in `.claude/plans/PLAN.md` (data model section): `User(email, full_name, hashed_password, role, is_active)`, `Employee(employee_code, first_name, last_name, email, job_title, department, country_code, currency, salary, employment_type, hire_date, status)`, `SalaryChange(employee_id, old_salary, new_salary, effective_date, reason, changed_by_user_id)`.

## 5. Frontend expectations
- Vite + React + TypeScript (strict), Node 24 (`.nvmrc` + `engines`). MUI, MUI X DataGrid community (server-side mode), Recharts, TanStack Query, React Router, axios, react-hook-form + zod. Tests: Vitest + React Testing Library + MSW.
- All HTTP goes through one typed axios client in `src/api/`; a 401 clears the token and routes to `/login`.
- Routes: `/login`, `/employees`, `/employees/:id`, `/insights`, `/users` (admin only). Unknown route -> not-found page. Guard routes by role with a `RequireRole` component; also hide actions the role cannot perform.
- Format salary with `Intl.NumberFormat` using the employee's `currency`.
- Components needing stable test hooks use accessible roles/labels (e.g. labelled form fields, `role="button"` names). Add `data-testid` only where no accessible query exists.

## 6. Docker (to be written, **not run here**, tested later on another machine)
- `backend/Dockerfile`: `python:3.13-slim`, installs the package, runs `backend/docker-entrypoint.sh` (`alembic upgrade head`, then seed only if the employees table is empty, then `uvicorn app.main:app --host 0.0.0.0 --port 8000`). Env: `DATABASE_URL=sqlite:////data/salary.db`, `JWT_SECRET` (required in compose), `CORS_ORIGINS`.
- `frontend/Dockerfile`: multi-stage — `node:24-alpine` builds, `nginx:alpine` serves `dist`. `frontend/nginx.conf`: SPA fallback to `index.html`, proxy `/api/` to `http://backend:8000`.
- `docker-compose.yml` (repo root, written by the **backend** agent): services `backend` (volume `salary-data:/data`, healthcheck on `/api/health`) and `frontend` (`8080:80`, `depends_on` backend healthy). Add `.dockerignore` files in `backend/` and `frontend/`.
- Both agents state in their final report that Docker files are **untested**.
