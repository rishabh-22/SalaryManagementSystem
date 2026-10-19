import { beforeEach, describe, expect, it } from 'vitest'
import { http, HttpResponse } from 'msw'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { EmployeesPage } from './EmployeesPage'
import { server } from '../test/server'
import { renderApp } from '../test/render'
import { employees } from '../test/handlers'
import type { Role } from '../api/types'

beforeEach(() => localStorage.clear())

describe('EmployeesPage', () => {
  it('renders rows from the paginated API with per-row currency formatting', async () => {
    renderApp(<EmployeesPage />, { role: 'hr_manager' })
    expect(await screen.findByText('ACME-00001')).toBeInTheDocument()
    expect(screen.getByText('ACME-00002')).toBeInTheDocument()
    expect(screen.getByText('Silva')).toBeInTheDocument()
    // BRL, USD and INR in the same grid, each in its own currency
    expect(screen.getByText(/R\$\s?185,000\.50/)).toBeInTheDocument()
    expect(screen.getByText('$95,000.00')).toBeInTheDocument()
    expect(screen.getByText(/₹\s?2,500,000\.00/)).toBeInTheDocument()
  })

  it('shows a friendly status label and links to the detail page', async () => {
    renderApp(<EmployeesPage />, { role: 'hr_manager' })
    await screen.findByText('ACME-00001')
    expect(screen.getByText('Terminated')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'View Ana Silva' })).toHaveAttribute('href', '/employees/1')
  })

  it('requests server-side pagination with page and page_size', async () => {
    let seen: URLSearchParams | undefined
    server.use(
      http.get('/api/employees', ({ request }) => {
        seen = new URL(request.url).searchParams
        return HttpResponse.json({ items: [], total: 0, page: 1, page_size: 25 })
      }),
    )
    renderApp(<EmployeesPage />, { role: 'viewer' })
    expect(await screen.findByText('No employees match your filters')).toBeInTheDocument()
    expect(seen?.get('page')).toBe('1')
    expect(seen?.get('page_size')).toBe('25')
  })

  it('sends the search term to the API after typing', async () => {
    const queries: (string | null)[] = []
    server.use(
      http.get('/api/employees', ({ request }) => {
        queries.push(new URL(request.url).searchParams.get('q'))
        return HttpResponse.json({ items: [employees[0]], total: 1, page: 1, page_size: 25 })
      }),
    )
    const user = userEvent.setup()
    renderApp(<EmployeesPage />, { role: 'hr_manager' })
    await screen.findByText('ACME-00001')
    const search = screen.getByRole('searchbox', { name: /search employees/i })
    await user.type(search, 'ana')
    await waitFor(() => expect(queries).toContain('ana'), { timeout: 2000 }) // debounced 300ms
    expect(queries.filter((q) => q === 'a' || q === 'an')).toEqual([]) // no request per keystroke
  })

  it('shows an error alert when the API fails', async () => {
    server.use(http.get('/api/employees', () => HttpResponse.json({ detail: 'Boom' }, { status: 500 })))
    renderApp(<EmployeesPage />, { role: 'hr_manager' })
    expect(await screen.findByText(/request failed \(500\)|boom/i)).toBeInTheDocument()
  })

  it.each<[Role, boolean]>([
    ['admin', true],
    ['hr_manager', true],
    ['viewer', false],
  ])('%s sees Add employee: %s', async (role, visible) => {
    renderApp(<EmployeesPage />, { role })
    await screen.findByText('ACME-00001')
    const button = screen.queryByRole('button', { name: 'Add employee' })
    if (visible) expect(button).toBeInTheDocument()
    else expect(button).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Export CSV' })).toBeInTheDocument() // read-only export for all
  })

  it('validates the Add employee dialog before submitting', async () => {
    let posted = false
    server.use(
      http.post('/api/employees', () => {
        posted = true
        return HttpResponse.json({}, { status: 201 })
      }),
    )
    const user = userEvent.setup()
    renderApp(<EmployeesPage />, { role: 'hr_manager' })
    await user.click(await screen.findByRole('button', { name: 'Add employee' }))
    const dialog = await screen.findByRole('dialog', { name: 'Add employee' })
    await user.click(within(dialog).getByRole('button', { name: 'Create employee' }))
    expect(await within(dialog).findByText('First name is required')).toBeInTheDocument()
    expect(within(dialog).getByText('Last name is required')).toBeInTheDocument()
    expect(within(dialog).getByText('Email is required')).toBeInTheDocument()
    expect(within(dialog).getByText('Salary is required')).toBeInTheDocument()
    expect(posted).toBe(false)
  })
})
