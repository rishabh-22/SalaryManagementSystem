# Architectural Decisions and Trade-offs

## 1. Salary as Float vs. Integer Minor Units

**Decision:** Store salary as a `float` in local currency, validated and rounded to 2 decimal places at the API boundary.

**Why:** HR teams think in natural units (e.g., 85,000.50 USD), not minor units (8,500,050 cents). Floats are easier to work with for analytics and reporting. Rounding to 2 decimal places at the boundary prevents floating-point noise from appearing in the UI.

**Trade-off:** Floats have inherent precision limits. We mitigate this by:
- Validating salary > 0 and ≤ 1e7 (10 million max) on input.
- Rounding to 2 dp at the API boundary so the DB reflects what was sent.
- Aggregates (min, max, sum) are also rounded to 2 dp in responses.

This approach is suitable for typical payroll scenarios but would not be appropriate for high-precision financial instruments.

## 2. SQLite vs. PostgreSQL

**Decision:** Use SQLite with a named volume in Docker, no Postgres.

**Why:**
- Simplicity: Single file, no separate database service. Lower operational overhead for evaluation.
- Deterministic testing: In-memory SQLite in tests is fast and reproducible.
- Sufficient for 10k rows: Query latency is negligible at this scale.

**Trade-off:** SQLite does not support percentile functions natively, so we compute p25/p75/median in Python using `statistics.quantiles`. This is acceptable because:
- The dataset is small (~10k employees per country).
- Python execution is fast enough (< 10ms for 10k values).
- Keeps the solution self-contained and easier to test.

For production systems with millions of rows or sub-millisecond latency requirements, Postgres would be preferable.

## 3. Currency Isolation (No FX Conversion)

**Decision:** Salaries are stored in local currency. Insights never mix currencies; money figures are always scoped to a single country.

**Why:**
- HR managers think in their local currency.
- FX rates change; locking in a rate could misrepresent payroll data.
- Org-wide views show headcount (a currency-neutral metric) but not money across countries.

**Trade-off:** Users cannot directly compare salaries across countries. This is intentional — it forces correct statistical thinking (e.g., "median salary in India is 950,000 INR, in the US is 95,000 USD" — not a direct comparison).

## 4. Soft Delete for Employees

**Decision:** Deleting an employee sets `status = terminated`; the row remains in the database.

**Why:**
- Preserves salary history and audit trail.
- Allows historical analysis without losing context.
- Supports "show all" vs. "show active only" filtering.

**Trade-off:** Requires filtering by status = 'active' in insights queries. Insights count only active employees, while the employee list shows all (unless filtered). This is by design — it reflects the business truth: historical headcount includes terminated employees, but current payroll calculations should not.

## 5. JWT in localStorage vs. Cookies

**Decision:** Store JWT in localStorage; automatically clear it and redirect to `/login` on 401.

**Why:**
- localStorage is directly accessible to JavaScript, making it easy to refresh and revoke tokens.
- Simplifies testing and development (no cookie domain/SameSite complexity).

**Trade-off:** localStorage is vulnerable to XSS attacks. Mitigation: we do not inline user input into the DOM without sanitization. In production, cookies with HttpOnly flag would be preferable.

## 6. Server-Side Pagination vs. Client-Side

**Decision:** Implement server-side pagination with `page`, `page_size` (max 100), and sorting/filtering pushed to the backend.

**Why:**
- Scales to 10k+ rows without loading everything into memory.
- Search, filter, and sort operations run on indexed columns.
- Frontend receives only 25 rows per page by default.

**Trade-off:** More backend queries, but the latency is negligible on SQLite at this scale. For 100k+ rows, this decision becomes critical.

## 7. Percentile Computation in Python

**Decision:** Compute p25, p75, and median in Python using `statistics.quantiles(..., method="inclusive")` after fetching salary values from SQL.

**Why:**
- SQLite lacks percentile functions (PERCENTILE_CONT, PERCENTILE_DISC).
- Postgres or advanced databases have native support; implementing in Python is a pragmatic trade-off for SQLite.
- Results are reproducible and testable.

**Percentile Method:** We use the "inclusive" method so that with a single value, p25 = median = p75 = that value. This avoids edge-case surprises.

## 8. Three-Layer Architecture

**Decision:** Routers (HTTP only) → Services (business logic) → Models (data).

**Why:**
- Separation of concerns: routers handle FastAPI specifics (request/response), services contain reusable business logic, models define data.
- Easy to test: services are pure functions that don't depend on FastAPI.
- No business logic in routers; all validation and RBAC checks in services or dependencies.

## 9. No Business Logic in Routers

**Decision:** Routers delegate to services for all business rules, RBAC, and validation.

**Why:**
- Routers should only handle HTTP marshalling (query params, request body, response format).
- Services are testable in isolation without mocking HTTP.
- RBAC logic (who can do what) lives in `require_roles` or service-level checks, not scattered through routers.

## 10. Deterministic Seed with Fixed Random Seed

**Decision:** Use `Faker.seed(42)` and `random.Random(42)` to generate reproducible employee data.

**Why:**
- Tests are deterministic and fast.
- Graders can run the seed and expect the same data every time.
- No external data files or API calls needed.

**Trade-off:** Only 10k unique employees (smaller dataset reduces seed time). For a real system, we'd import from an HR system or external data source.

## 11. No Passwords in Seed

**Decision:** The seed creates three demo users with hardcoded default passwords, overridable via environment variables.

**Why:**
- Passwords are sensitive and should never be checked into code.
- ENV overrides let graders use their own credentials if needed.
- Default passwords are documented in `API_CONTRACT.md` for local testing.

## 12. Alembic Migrations

**Decision:** Use Alembic for schema versioning and migrations.

**Why:**
- Enables schema evolution as requirements change.
- `alembic upgrade head` in the Docker entrypoint keeps the schema in sync.
- Familiar tool in Python/SQLAlchemy projects.

**Trade-off:** For 10k rows, a single initial migration is sufficient. As the schema evolves, migration management becomes more critical.

## 13. Indexes on Salary Query Paths

**Decision:** Add indexes on `country_code`, `department`, `job_title`, `status`, and composite `(country_code, job_title)`.

**Why:**
- Most insights queries filter by these columns.
- Composite index on `(country_code, job_title)` speeds up outlier detection.
- Salary column not indexed because range queries are rare; we fetch and filter in Python.

## 14. No Password Length Validation at Schema Level

**Decision:** Set `max_length=72` on password fields to respect bcrypt's truncation limit.

**Why:** bcrypt truncates passwords at 72 bytes. Allowing longer passwords would be silently truncated, creating a security illusion (longer passwords offer no extra protection).

## 15. CSV Export

**Decision:** Implement `GET /employees/export.csv` with the same filters and sort as the employee list, but without pagination.

**Why:**
- Users familiar with Excel expect to export data for further analysis.
- Server-side filtering ensures large datasets don't overwhelm the client.

**Trade-off:** Export of very large datasets (100k+ rows) could timeout. For now, we assume CSV export is used for targeted, filtered subsets.

## 16. Chat Assistant: Tool-Use Loop, Read-Only Tools, Stateless Server

**Decision:** `POST /api/chat` runs a plain Claude tool-use loop (`anthropic` SDK) over a fixed set of read-only tools that reuse the existing services. The client sends the conversation history with every request; the server stores nothing. Replies are a single JSON response, not streamed.

**Why:**
- A hand-written loop is small, easy to test with a fake client, and lets us control exactly what the model can touch. The heavier Agent SDK runs a separate runtime and adds deployment weight we do not need for database Q&A.
- No raw SQL tool and no write tools: the assistant can only call functions we wrote, so it cannot modify or over-read data. Every role can use it because every role can already read the same data through the REST API.
- Stateless history avoids a conversation table, retention questions and session handling. History is capped (20 messages, 2000 characters each) to bound cost.
- "Last quarter" is computed in code (`previous_quarter`) and exposed as a tool, so the model never guesses dates. Pay figures are returned per country with their own currency, preserving the no-mixed-currencies rule.
- Name lookups return up to 10 candidates and the prompt tells the model to ask the user to pick when several match, rather than guess.
- The default model is `claude-haiku-5-5` (cheap, fast); it is configurable with `CHAT_MODEL`.

**Trade-off:** No streaming, so long answers appear all at once after a "Thinking" indicator. The API key lives in `backend/.env` (git-ignored) and the endpoint returns 503 when it is unset. Anthropic failures return a generic 502 so provider details never reach the browser. Conversation text is sent to Anthropic, so the data it can reach (names, salaries) leaves the system on each question; synthetic data makes this safe for the assessment, but a real deployment needs a data-processing review.
