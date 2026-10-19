export type Role = 'admin' | 'hr_manager' | 'viewer'
export type EmploymentType = 'full_time' | 'part_time' | 'contract'
export type EmployeeStatus = 'active' | 'terminated'

export interface Country {
  code: string
  name: string
  currency: string
}

export interface Meta {
  countries: Country[]
  departments: string[]
  job_titles: string[]
  employment_types: EmploymentType[]
  statuses: EmployeeStatus[]
  roles: Role[]
}

export interface User {
  id: number
  email: string
  full_name: string
  role: Role
  is_active: boolean
  created_at: string
}

export interface TokenResponse {
  access_token: string
  token_type: string
}

export interface UserCreate {
  email: string
  full_name: string
  password: string
  role: Role
}

export interface UserUpdate {
  full_name?: string
  role?: Role
  is_active?: boolean
  password?: string
}

export interface Employee {
  id: number
  employee_code: string
  first_name: string
  last_name: string
  email: string
  job_title: string
  department: string
  country_code: string
  currency: string
  salary: number
  employment_type: EmploymentType
  hire_date: string
  status: EmployeeStatus
  created_at: string
  updated_at: string
}

export interface EmployeeCreate {
  first_name: string
  last_name: string
  email: string
  job_title: string
  department: string
  country_code: string
  employment_type: EmploymentType
  hire_date: string
  salary: number
}

export interface EmployeeUpdate extends Partial<EmployeeCreate> {
  status?: EmployeeStatus
  salary_change_reason?: string
  salary_effective_date?: string
}

export interface EmployeeFilters {
  q?: string
  country?: string
  department?: string
  job_title?: string
  status?: string
  employment_type?: string
}

export interface EmployeeListParams extends EmployeeFilters {
  page: number
  page_size: number
  sort?: string
}

export interface Page<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

export interface SalaryChange {
  id: number
  employee_id: number
  old_salary: number
  new_salary: number
  effective_date: string
  reason: string
  changed_by: { id: number; full_name: string } | null
  created_at: string
}

export interface Summary {
  headcount: number
  min: number | null
  p25: number | null
  median: number | null
  p75: number | null
  max: number | null
  mean: number | null
  total_payroll: number | null
}

export interface Overview {
  total_headcount: number
  by_country: {
    country_code: string
    currency: string
    headcount: number
    median_salary: number | null
    mean_salary: number | null
  }[]
  by_department: { department: string; headcount: number }[]
  by_employment_type: { employment_type: EmploymentType; headcount: number }[]
}

export interface CountryInsights {
  country_code: string
  currency: string
  summary: Summary
  by_department: { department: string; summary: Summary }[]
  by_job_title: { job_title: string; summary: Summary }[]
}

export interface Distribution {
  country_code: string
  currency: string
  bins: { lower: number; upper: number; count: number }[]
}

export interface OutlierItem {
  employee_id: number
  employee_code: string
  full_name: string
  job_title: string
  salary: number
  job_title_median: number
  deviation: number
}

export interface Outliers {
  country_code: string
  currency: string
  threshold: number
  items: OutlierItem[]
}
