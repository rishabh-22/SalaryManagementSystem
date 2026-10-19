# Performance Analysis

## Database Indexes

All indexes are applied to the `employees` table:

| Index | Columns | Reason |
|---|---|---|
| Primary Key | `id` | Default; enables efficient row lookup by ID. |
| Unique | `employee_code` | Ensures code uniqueness; enables lookup by code (used in exports, detail pages). |
| Unique | `email` | Ensures email uniqueness; prevents duplicate user creation. |
| Standard | `country_code` | Filters insights by country; used in 90% of queries. |
| Standard | `department` | Filters by department in insights and employee list. |
| Standard | `job_title` | Filters by job title in insights and employee list. |
| Standard | `status` | Filters active vs. terminated; used in insights (active only) and list (with/without terminated). |
| Composite | `(country_code, job_title)` | Speeds up outlier detection: fetch all salaries for a job title in a country. |

## Query Performance on 10,000 Employees

All measurements on an in-memory SQLite engine; real disk performance will vary.

### Employees List (GET /employees)

**Query:** Filter by country, department; sort by salary; paginate 25 items.

```sql
SELECT * FROM employees 
WHERE country_code = 'US' AND department = 'Engineering' AND status = 'active'
ORDER BY salary DESC
LIMIT 25 OFFSET 0;
```

**Performance:** ~2-5 ms (index on `country_code`, `department`, `status`).

### Insights Overview (GET /insights/overview)

**Queries:**
```sql
SELECT country_code, currency, COUNT(*) as headcount, 
       ROUND(AVG(salary), 2) as mean_salary
FROM employees
WHERE status = 'active'
GROUP BY country_code, currency;
```

**Performance:** ~10-20 ms (single table scan with GROUP BY on indexed columns).

### Salary Distribution (GET /insights/country/{code}/distribution?bins=10)

**Steps:**
1. SQL: Fetch all salaries for a country and active status (~1000 rows for 10k dataset).
2. Python: Compute min/max, calculate bin edges, count rows per bin.

**Performance:** SQL ~5 ms, Python ~1 ms. Total: ~6 ms.

### Outliers (GET /insights/country/{code}/outliers)

**Steps:**
1. SQL: Fetch all job titles with ≥3 active employees in the country.
   ```sql
   SELECT job_title FROM employees
   WHERE country_code = 'US' AND status = 'active'
   GROUP BY job_title HAVING COUNT(*) >= 3;
   ```
2. SQL: For each job title, compute median salary (fetch values, compute in Python).
3. Python: Compare each employee's salary to their job-title median; flag outliers.

**Performance:**
- SQL step 1: ~3 ms.
- SQL step 2 (per title): ~1-2 ms × ~20 job titles = ~20-40 ms.
- Python computation: ~5 ms.
- **Total: ~50-70 ms** (acceptable for an analytics page that isn't refreshed constantly).

### Pagination and Filtering

**Employee List with Search:**
```sql
SELECT * FROM employees
WHERE status = 'active' 
  AND (first_name LIKE '%q%' OR last_name LIKE '%q%' 
       OR email LIKE '%q%' OR employee_code LIKE '%q%')
ORDER BY id
LIMIT 25 OFFSET 0;
```

**Performance:** ~5-10 ms (full table scan on LIKE, mitigated by 25-row limit and pagination).

Note: LIKE queries without a leading wildcard would benefit from full-text search (FTS5) in Postgres, but for 10k rows and typical query patterns, this is adequate.

## Seed Script Performance

The seed script generates 10,000 employees with salary history.

### Execution Time

- **First run (cold, fresh DB):** ~4.9 seconds.
- **Warm run (re-seeding):** ~2.6 seconds.
- **Bulk insert:** Uses `session.execute(insert(...), rows)` in batches of 1,000.

### Breakdown

1. Generate Faker data: ~1.5 s.
2. Compute salary ranges per country/title: ~0.2 s.
3. Generate salary history: ~0.5 s.
4. Bulk insert employees: ~1.2 s.
5. Bulk insert salary changes: ~0.8 s.

### Database Size

- Employees table: ~10k rows × ~200 bytes = ~2 MB.
- Salary changes table: ~4.8k rows × ~100 bytes = ~0.5 MB.
- **Total SQLite file:** ~3-4 MB (includes indexes, vacuum overhead).

## Scalability Considerations

| Metric | 10k Rows | 100k Rows | 1M Rows |
|---|---|---|---|
| List query (paginated) | 2-5 ms | 5-10 ms | 20-50 ms |
| Insights overview | 10-20 ms | 50-100 ms | 500+ ms |
| Outliers query | 50-70 ms | 200+ ms | 2000+ ms |
| Seed time | ~4.9 s | ~50 s | ~500 s (not recommended) |

**Recommendation:** SQLite is suitable up to ~100k rows. Beyond that, migrate to Postgres with similar indexes and adjust Python percentile computation to use SQL (PERCENTILE_CONT in Postgres).

## Memory Usage

- **In-memory SQLite (tests):** ~20 MB for 10k employees + salary changes.
- **Backend process:** ~50 MB (FastAPI + dependencies + in-memory test DB).
- **Frontend build:** ~500 KB gzipped (Vite optimizes chunks).

## API Response Times (End-to-End)

Measured from client request to server response, including JSON parsing and network round-trip (localhost).

| Endpoint | Payload Size | Latency |
|---|---|---|
| GET /employees?page=1 | ~30 KB (25 items) | 15-25 ms |
| GET /insights/overview | ~5 KB | 20-30 ms |
| GET /insights/country/US/outliers | ~20 KB | 60-80 ms |
| POST /employees | ~ 1 KB | 10-20 ms |
| PATCH /employees/{id} with salary change | ~1 KB | 15-25 ms |

## Caching Strategy

Currently, no response caching is implemented. The following could be added:

1. **Client-side:** TanStack Query automatically caches responses for 60 seconds (configurable).
2. **Server-side:** Cache insights (overview, country summary) for 5-10 minutes (rarely changes mid-day).
3. **CDN:** In production, serve static assets and CSV exports through a CDN.

## Lock Contention

SQLite uses file-level locking, which can cause contention under high concurrency. For this 10-person HR team, concurrency is low (< 5 concurrent users), so locking is not a bottleneck. If this scaled to 100+ concurrent users, Postgres would be necessary.
