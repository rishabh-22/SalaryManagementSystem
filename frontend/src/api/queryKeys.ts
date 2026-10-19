import type { EmployeeListParams } from './types'

export const qk = {
  me: ['me'] as const,
  meta: ['meta'] as const,
  users: ['users'] as const,
  employees: ['employees'] as const,
  employeeList: (params: EmployeeListParams) => ['employees', 'list', params] as const,
  employee: (id: number) => ['employees', 'detail', id] as const,
  salaryHistory: (id: number) => ['employees', 'history', id] as const,
  insights: ['insights'] as const,
  overview: ['insights', 'overview'] as const,
  country: (code: string) => ['insights', 'country', code] as const,
  distribution: (code: string, bins: number) => ['insights', 'distribution', code, bins] as const,
  outliers: (code: string, threshold: number) => ['insights', 'outliers', code, threshold] as const,
}
