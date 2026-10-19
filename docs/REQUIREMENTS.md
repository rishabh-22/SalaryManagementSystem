# Requirements: ACME Salary Management

## Goal
Replace the HR team's Excel files with a web app where the HR Manager can maintain salary data for ~10,000 employees in several countries and answer "how do we pay people?" in seconds.

## Persona
**HR Manager**, who owns salary data and answers questions from leadership and finance. Two secondary roles: *Admin* (also manages users) and *Viewer* (read-only, e.g. finance).

## In scope
1. **Employee records**: create, view, edit, and terminate (soft delete) employees with country, department, job title, employment type, hire date and annual salary in local currency.
2. **Fast browsing**: server-side search, filters (country, department, title, status), sorting and pagination that stay quick at 10k rows.
3. **Salary changes with history**: every change needs an effective date and a reason, and is kept as an audit trail with who made it.
4. **Pay insights**: per country, the headcount, min/median/mean/percentiles/max and payroll, with breakdowns by department and job title, a salary distribution, and outliers more than 30% from their job-title median.
5. **CSV export** of the filtered employee list, as a bridge from the Excel workflow.
6. **Authentication and roles**: JWT login, with admin, hr_manager and viewer permissions enforced on the server.
7. **Seed script** that generates 10,000 synthetic employees, and a Docker setup to run everything locally.

## Deliberately out of scope (and why)
| Left out | Reason |
|---|---|
| Currency conversion / org-wide payroll totals | FX rates change and need a source of truth; mixing currencies silently gives wrong answers. Insights compare money within one country only. |
| Bulk Excel import | Data is seeded; a robust importer needs mapping and error-handling UX that would crowd out core value. |
| Payroll, tax, benefits, bonuses, equity | Different problem (compensation processing); base salary answers the stated questions. |
| Approval workflows | Single HR persona; adds process complexity without changing the core data model. |
| SSO / password reset / MFA | Basic JWT auth covers the access-control need; identity integration is deployment-specific. |
| Cloud deployment | Delivered as a local Docker setup; hosting choice is an operations decision. |
| National IDs or other sensitive identifiers | Not needed for salary analysis and a liability to store. |

## Success criteria
- Employee list responds quickly with 10k rows (server-side pagination and indexes).
- Insights numbers are correct and tested, including edge cases (empty groups, single employee).
- Every salary change is traceable, and viewers cannot modify anything.
