import { beforeEach, describe, expect, it } from 'vitest'
import { http, HttpResponse } from 'msw'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { SalaryChangeForm } from './SalaryChangeForm'
import { server } from '../test/server'
import { renderApp } from '../test/render'
import { employees } from '../test/handlers'

const ana = employees[0] // BRL 185000.50

beforeEach(() => localStorage.clear())

function capturePatch() {
  const bodies: Record<string, unknown>[] = []
  server.use(
    http.patch('/api/employees/:id', async ({ request }) => {
      const body = (await request.json()) as Record<string, unknown>
      bodies.push(body)
      return HttpResponse.json({ ...ana, ...body })
    }),
  )
  return bodies
}

describe('SalaryChangeForm', () => {
  it('shows the current salary in the employee currency and labels the field with it', () => {
    renderApp(<SalaryChangeForm employee={ana} />, { role: 'hr_manager' })
    expect(screen.getByText(/R\$\s?185,000\.50/)).toBeInTheDocument()
    expect(screen.getByLabelText('New salary (BRL)')).toBeInTheDocument()
    expect(screen.getByLabelText('Reason')).toBeInTheDocument()
    expect(screen.getByLabelText('Effective date')).toBeInTheDocument()
  })

  it('requires salary and reason and does not call the API', async () => {
    const bodies = capturePatch()
    const user = userEvent.setup()
    renderApp(<SalaryChangeForm employee={ana} />, { role: 'hr_manager' })
    await user.click(screen.getByRole('button', { name: 'Apply salary change' }))
    expect(await screen.findByText('Salary is required')).toBeInTheDocument()
    expect(screen.getByText('Reason is required')).toBeInTheDocument()
    expect(bodies).toHaveLength(0)
  })

  it('rejects a whitespace-only reason', async () => {
    const bodies = capturePatch()
    const user = userEvent.setup()
    renderApp(<SalaryChangeForm employee={ana} />, { role: 'hr_manager' })
    await user.type(screen.getByLabelText('New salary (BRL)'), '200000')
    await user.type(screen.getByLabelText('Reason'), '   ')
    await user.click(screen.getByRole('button', { name: 'Apply salary change' }))
    expect(await screen.findByText('Reason is required')).toBeInTheDocument()
    expect(bodies).toHaveLength(0)
  })

  it('rejects zero and negative salaries', async () => {
    const user = userEvent.setup()
    renderApp(<SalaryChangeForm employee={ana} />, { role: 'hr_manager' })
    await user.type(screen.getByLabelText('New salary (BRL)'), '-5')
    await user.type(screen.getByLabelText('Reason'), 'Typo')
    await user.click(screen.getByRole('button', { name: 'Apply salary change' }))
    expect(await screen.findByText('Salary must be greater than 0')).toBeInTheDocument()
  })

  it('rejects an unchanged salary client-side', async () => {
    const bodies = capturePatch()
    const user = userEvent.setup()
    renderApp(<SalaryChangeForm employee={ana} />, { role: 'hr_manager' })
    await user.type(screen.getByLabelText('New salary (BRL)'), '185000.5')
    await user.type(screen.getByLabelText('Reason'), 'No-op')
    await user.click(screen.getByRole('button', { name: 'Apply salary change' }))
    expect(await screen.findByText(/must differ from the current salary/i)).toBeInTheDocument()
    expect(bodies).toHaveLength(0)
  })

  it('submits salary, reason and effective date with the contract field names', async () => {
    const bodies = capturePatch()
    const user = userEvent.setup()
    renderApp(<SalaryChangeForm employee={ana} />, { role: 'hr_manager' })
    await user.type(screen.getByLabelText('New salary (BRL)'), '200000')
    await user.clear(screen.getByLabelText('Effective date'))
    await user.type(screen.getByLabelText('Effective date'), '2026-04-01')
    await user.type(screen.getByLabelText('Reason'), ' Annual review ')
    await user.click(screen.getByRole('button', { name: 'Apply salary change' }))
    expect(await screen.findByText('Salary updated.')).toBeInTheDocument()
    expect(bodies).toEqual([
      { salary: 200000, salary_effective_date: '2026-04-01', salary_change_reason: 'Annual review' },
    ])
  })

  it('surfaces a server-side 422 on the relevant field', async () => {
    server.use(
      http.patch('/api/employees/:id', () =>
        HttpResponse.json(
          { detail: [{ loc: ['body'], msg: 'salary_change_reason is required', type: 'value_error' }] },
          { status: 422 },
        ),
      ),
    )
    const user = userEvent.setup()
    renderApp(<SalaryChangeForm employee={ana} />, { role: 'hr_manager' })
    await user.type(screen.getByLabelText('New salary (BRL)'), '200000')
    await user.type(screen.getByLabelText('Reason'), 'x')
    await user.click(screen.getByRole('button', { name: 'Apply salary change' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(/salary_change_reason is required/)
  })
})
