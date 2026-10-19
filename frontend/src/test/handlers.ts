import { http, HttpResponse, type RequestHandler } from 'msw'
import type {
  CountryInsights,
  Distribution,
  Employee,
  Meta,
  Outliers,
  Overview,
  Role,
  SalaryChange,
  User,
} from '../api/types'

// ---- synthetic fixtures shaped exactly like docs/API_CONTRACT.md ----

export const meta: Meta = {
  countries: [
    { code: 'US', name: 'United States', currency: 'USD' },
    { code: 'BR', name: 'Brazil', currency: 'BRL' },
    { code: 'IN', name: 'India', currency: 'INR' },
    { code: 'DE', name: 'Germany', currency: 'EUR' },
  ],
  departments: ['Engineering', 'Sales', 'HR'],
  job_titles: ['Software Engineer', 'Account Executive'],
  employment_types: ['full_time', 'part_time', 'contract'],
  statuses: ['active', 'terminated'],
  roles: ['admin', 'hr_manager', 'viewer'],
}

export const makeUser = (role: Role, overrides: Partial<User> = {}): User => ({
  id: 1,
  email: `${role}@acme.com`,
  full_name: role === 'admin' ? 'Alex Admin' : role === 'hr_manager' ? 'Hannah Reed' : 'Vic Viewer',
  role,
  is_active: true,
  created_at: '2026-01-01T00:00:00Z',
  ...overrides,
})

export const employees: Employee[] = [
  {
    id: 1, employee_code: 'ACME-00001', first_name: 'Ana', last_name: 'Silva', email: 'ana.silva@acme.com',
    job_title: 'Software Engineer', department: 'Engineering', country_code: 'BR', currency: 'BRL',
    salary: 185000.5, employment_type: 'full_time', hire_date: '2021-03-15', status: 'active',
    created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z',
  },
  {
    id: 2, employee_code: 'ACME-00002', first_name: 'John', last_name: 'Miller', email: 'john.miller@acme.com',
    job_title: 'Account Executive', department: 'Sales', country_code: 'US', currency: 'USD',
    salary: 95000, employment_type: 'part_time', hire_date: '2020-07-01', status: 'active',
    created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z',
  },
  {
    id: 3, employee_code: 'ACME-00003', first_name: 'Priya', last_name: 'Nair', email: 'priya.nair@acme.com',
    job_title: 'Software Engineer', department: 'Engineering', country_code: 'IN', currency: 'INR',
    salary: 2500000, employment_type: 'contract', hire_date: '2019-11-20', status: 'terminated',
    created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z',
  },
]

export const salaryHistory: SalaryChange[] = [
  {
    id: 2, employee_id: 1, old_salary: 170000, new_salary: 185000.5, effective_date: '2026-04-01',
    reason: 'Annual review', changed_by: { id: 2, full_name: 'Hannah Reed' }, created_at: '2026-04-01T00:00:00Z',
  },
]

const summary = (headcount: number, base: number) => ({
  headcount, min: base * 0.5, p25: base * 0.75, median: base, p75: base * 1.25, max: base * 1.5,
  mean: base, total_payroll: base * headcount,
})

export const overview: Overview = {
  total_headcount: 9,
  by_country: [
    { country_code: 'US', currency: 'USD', headcount: 6, median_salary: 100000, mean_salary: 95000 },
    { country_code: 'BR', currency: 'BRL', headcount: 3, median_salary: 180000, mean_salary: 181000 },
  ],
  by_department: [
    { department: 'Engineering', headcount: 6 },
    { department: 'Sales', headcount: 3 },
  ],
  by_employment_type: [
    { employment_type: 'full_time', headcount: 8 },
    { employment_type: 'part_time', headcount: 1 },
  ],
}

export const countryInsights = (code: string): CountryInsights => ({
  country_code: code,
  currency: meta.countries.find((c) => c.code === code)?.currency ?? 'USD',
  summary: summary(6, 100000),
  by_department: [
    { department: 'Engineering', summary: summary(4, 110000) },
    { department: 'Sales', summary: summary(2, 55000) },
  ],
  by_job_title: [
    { job_title: 'Software Engineer', summary: summary(4, 110000) },
    { job_title: 'Account Executive', summary: summary(2, 55000) },
  ],
})

export const distribution = (code: string): Distribution => ({
  country_code: code,
  currency: meta.countries.find((c) => c.code === code)?.currency ?? 'USD',
  bins: [
    { lower: 50000, upper: 100000, count: 3 },
    { lower: 100000, upper: 160000, count: 3 },
  ],
})

export const outliers = (code: string): Outliers => ({
  country_code: code,
  currency: meta.countries.find((c) => c.code === code)?.currency ?? 'USD',
  threshold: 0.3,
  items: [
    {
      employee_id: 5, employee_code: 'ACME-00005', full_name: 'Zoe Outlier', job_title: 'Software Engineer',
      salary: 160000, job_title_median: 100000, deviation: 0.6,
    },
  ],
})

/** Token strings encode the role so the /auth/me handler can answer per role. */
export const tokenFor = (role: Role) => `test-token-${role}`
const roleFromAuth = (header: string | null): Role | null => {
  const m = /^Bearer test-token-(admin|hr_manager|viewer)$/.exec(header ?? '')
  return m ? (m[1] as Role) : null
}

export const DEMO_PASSWORD = 'Passw0rd!123'
const demoEmails: Record<string, Role> = {
  'admin@acme.com': 'admin',
  'hr@acme.com': 'hr_manager',
  'viewer@acme.com': 'viewer',
}

const unauthorized = () => HttpResponse.json({ detail: 'Could not validate credentials' }, { status: 401 })

export const handlers: RequestHandler[] = [
  http.get('/api/health', () => HttpResponse.json({ status: 'ok' })),

  http.post('/api/auth/login', async ({ request }) => {
    const form = new URLSearchParams(await request.text())
    const role = demoEmails[form.get('username') ?? '']
    if (!role || form.get('password') !== DEMO_PASSWORD) {
      return HttpResponse.json({ detail: 'Incorrect email or password' }, { status: 401 })
    }
    return HttpResponse.json({ access_token: tokenFor(role), token_type: 'bearer' })
  }),

  http.get('/api/auth/me', ({ request }) => {
    const role = roleFromAuth(request.headers.get('Authorization'))
    return role ? HttpResponse.json(makeUser(role)) : unauthorized()
  }),

  http.get('/api/meta', () => HttpResponse.json(meta)),

  http.get('/api/employees', ({ request }) => {
    const url = new URL(request.url)
    const page = Number(url.searchParams.get('page') ?? 1)
    const pageSize = Number(url.searchParams.get('page_size') ?? 25)
    const q = (url.searchParams.get('q') ?? '').toLowerCase()
    let items = employees
    if (q) items = items.filter((e) => `${e.first_name} ${e.last_name} ${e.email} ${e.employee_code}`.toLowerCase().includes(q))
    const country = url.searchParams.get('country')
    if (country) items = items.filter((e) => e.country_code === country)
    return HttpResponse.json({
      items: items.slice((page - 1) * pageSize, page * pageSize),
      total: items.length,
      page,
      page_size: pageSize,
    })
  }),

  http.get('/api/employees/:id', ({ params }) => {
    const emp = employees.find((e) => e.id === Number(params.id))
    return emp ? HttpResponse.json(emp) : HttpResponse.json({ detail: 'Employee not found' }, { status: 404 })
  }),

  http.get('/api/employees/:id/salary-history', ({ params }) =>
    HttpResponse.json(salaryHistory.filter((h) => h.employee_id === Number(params.id))),
  ),

  http.patch('/api/employees/:id', async ({ params, request }) => {
    const emp = employees.find((e) => e.id === Number(params.id))
    if (!emp) return HttpResponse.json({ detail: 'Employee not found' }, { status: 404 })
    const body = (await request.json()) as Record<string, unknown>
    return HttpResponse.json({ ...emp, ...body })
  }),

  http.post('/api/employees', async ({ request }) => {
    const body = (await request.json()) as Record<string, unknown>
    return HttpResponse.json({ ...employees[0], ...body, id: 99, employee_code: 'ACME-00099' }, { status: 201 })
  }),

  http.get('/api/insights/overview', () => HttpResponse.json(overview)),
  http.get('/api/insights/country/:code', ({ params }) => HttpResponse.json(countryInsights(String(params.code)))),
  http.get('/api/insights/country/:code/distribution', ({ params }) =>
    HttpResponse.json(distribution(String(params.code))),
  ),
  http.get('/api/insights/country/:code/outliers', ({ params }) => HttpResponse.json(outliers(String(params.code)))),

  http.get('/api/users', () => HttpResponse.json([makeUser('admin'), makeUser('hr_manager', { id: 2 }), makeUser('viewer', { id: 3 })])),
]
