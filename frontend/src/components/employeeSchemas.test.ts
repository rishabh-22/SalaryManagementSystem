import { describe, expect, it } from 'vitest'
import { createSchema, emptyCreateValues, salaryChangeSchema, toCreatePayload } from './employeeSchemas'

const validChange = { salary: '120000', effective_date: '2026-04-01', reason: 'Annual review' }

describe('salaryChangeSchema', () => {
  it('accepts a complete change', () => {
    expect(salaryChangeSchema.safeParse(validChange).success).toBe(true)
  })

  it.each([
    ['reason', { reason: '' }, 'Reason is required'],
    ['reason (whitespace)', { reason: '   ' }, 'Reason is required'],
    ['effective date', { effective_date: '' }, 'Effective date is required'],
    ['salary (empty)', { salary: '' }, 'Salary is required'],
    ['salary (zero)', { salary: '0' }, 'Salary must be greater than 0'],
    ['salary (negative)', { salary: '-10' }, 'Salary must be greater than 0'],
    ['salary (not a number)', { salary: 'abc' }, 'Salary must be greater than 0'],
  ])('rejects invalid %s', (_name, override, message) => {
    const result = salaryChangeSchema.safeParse({ ...validChange, ...override })
    expect(result.success).toBe(false)
    if (!result.success) expect(result.error.issues.map((i) => i.message)).toContain(message)
  })
})

describe('createSchema / toCreatePayload', () => {
  const valid = {
    ...emptyCreateValues,
    first_name: 'Ana',
    last_name: 'Silva',
    email: 'ana@acme.com',
    job_title: 'Software Engineer',
    department: 'Engineering',
    country_code: 'BR',
    hire_date: '2021-03-15',
    salary: '185000.50',
  }

  it('accepts valid input and converts salary to a number', () => {
    expect(createSchema.safeParse(valid).success).toBe(true)
    expect(toCreatePayload(valid).salary).toBe(185000.5)
  })

  it('never sends currency (derived server-side)', () => {
    expect(Object.keys(toCreatePayload(valid))).not.toContain('currency')
  })

  it('rejects empty form and bad email', () => {
    expect(createSchema.safeParse(emptyCreateValues).success).toBe(false)
    expect(createSchema.safeParse({ ...valid, email: 'nope' }).success).toBe(false)
  })
})
