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

## Chat assistant
- `POST /api/chat` runs a Claude tool-use loop (`services/chat_agent.py`) over read-only tools (`services/chat_tools.py`). It never writes.
- Config lives in `backend/.env` (git-ignored; template in `backend/.env.example`): `ANTHROPIC_API_KEY`, `CHAT_MODEL`. Never commit the key.
- Tests fake the Anthropic client (`get_anthropic_client`); no test may call the real API.

## Git
- Branch `master`, remote `origin` (GitHub). Port 22 is blocked, so push with
  `GIT_SSH_COMMAND="ssh -o HostName=ssh.github.com -o Port=443" git push`.
- The global git identity in `~/.gitconfig` is the one to use. Never pass `-c user.name/-c user.email`
  and never change git config.
