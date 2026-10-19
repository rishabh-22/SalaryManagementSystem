# ACME Salary Management System

HR-manager web app for managing salaries of ~10,000 employees across countries.
Plan: `.claude/plans/PLAN.md`. Requirements: `docs/REQUIREMENTS.md`.

## Stack
- Backend: Python 3.13, FastAPI, SQLAlchemy 2.0, SQLite, Alembic, pytest (`backend/`)
- Frontend: React + TypeScript + Vite + MUI (`frontend/`)

## Conventions
- Layers: routers (HTTP only) -> services (business rules) -> models. No business logic in routers.
- Salary is a float in local currency, rounded to 2 dp at the API boundary. Insights never mix currencies.
- Tests use small explicit fixtures and in-memory SQLite, never the 10k seed. They must be fast and deterministic.
- No real PII: all employee data is synthetic (Faker, fixed seed).
- Small, incremental commits with conventional prefixes (`feat:`, `test:`, `docs:`, `chore:`).

## Commands
- Backend setup: `python -m venv backend/.venv`, activate, `pip install -e "backend[dev]"`
- Backend tests: `cd backend && pytest --cov=app`
- Run API: `cd backend && uvicorn app.main:app --reload`
- Seed: `cd backend && python -m scripts.seed --reset`

## Git
- Branch `master`, remote `origin` (GitHub). Port 22 is blocked, so push with
  `GIT_SSH_COMMAND="ssh -o HostName=ssh.github.com -o Port=443" git push`.
- No global git identity is set; commit with
  `git -c user.name="Rishabh Bhardwaj" -c user.email="rishabh.bhardwaj@ust.com" commit ...`.
