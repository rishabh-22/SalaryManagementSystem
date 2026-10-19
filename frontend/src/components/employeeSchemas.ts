import { z } from 'zod'
import type { Employee, EmployeeCreate } from '../api/types'

/** Form state is all strings; numbers are parsed on submit via toCreatePayload. */
export const salaryField = z
  .string()
  .trim()
  .min(1, 'Salary is required')
  .refine((v) => Number.isFinite(Number(v)) && Number(v) > 0, 'Salary must be greater than 0')

export const profileSchema = z.object({
  first_name: z.string().trim().min(1, 'First name is required'),
  last_name: z.string().trim().min(1, 'Last name is required'),
  email: z.string().trim().min(1, 'Email is required').email('Enter a valid email'),
  job_title: z.string().min(1, 'Job title is required'),
  department: z.string().min(1, 'Department is required'),
  country_code: z.string().min(1, 'Country is required'),
  employment_type: z.string().min(1, 'Employment type is required'),
  hire_date: z.string().min(1, 'Hire date is required'),
})
export type ProfileValues = z.infer<typeof profileSchema>

export const createSchema = profileSchema.extend({ salary: salaryField })
export type CreateValues = z.infer<typeof createSchema>

export const emptyCreateValues: CreateValues = {
  first_name: '',
  last_name: '',
  email: '',
  job_title: '',
  department: '',
  country_code: '',
  employment_type: 'full_time',
  hire_date: '',
  salary: '',
}

export function profileDefaults(e: Employee): ProfileValues {
  return {
    first_name: e.first_name,
    last_name: e.last_name,
    email: e.email,
    job_title: e.job_title,
    department: e.department,
    country_code: e.country_code,
    employment_type: e.employment_type,
    hire_date: e.hire_date,
  }
}

export function toCreatePayload(v: CreateValues): EmployeeCreate {
  return {
    ...v,
    employment_type: v.employment_type as EmployeeCreate['employment_type'],
    salary: Number(v.salary),
  }
}

export const salaryChangeSchema = z.object({
  salary: salaryField,
  effective_date: z.string().min(1, 'Effective date is required'),
  reason: z.string().trim().min(1, 'Reason is required'),
})
export type SalaryChangeValues = z.infer<typeof salaryChangeSchema>
