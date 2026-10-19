import { beforeEach, describe, expect, it } from 'vitest'
import { Route, Routes } from 'react-router-dom'
import { screen } from '@testing-library/react'
import { EmployeeDetailPage } from './EmployeeDetailPage'
import { renderApp } from '../test/render'
import type { Role } from '../api/types'

beforeEach(() => localStorage.clear())

const ui = (
  <Routes>
    <Route path="/employees/:id" element={<EmployeeDetailPage />} />
  </Routes>
)

describe('EmployeeDetailPage role-based visibility', () => {
  it.each<Role>(['admin', 'hr_manager'])('%s sees the salary change form and history', async (role) => {
    renderApp(ui, { route: '/employees/1', role })
    expect(await screen.findByRole('form', { name: 'Change salary' })).toBeInTheDocument()
    expect(await screen.findByText('Annual review')).toBeInTheDocument()
    expect(screen.queryByText(/read-only access/i)).not.toBeInTheDocument()
  })

  it('viewer sees read-only notice, history, and no salary form', async () => {
    renderApp(ui, { route: '/employees/1', role: 'viewer' })
    expect(await screen.findByText(/read-only access/i)).toBeInTheDocument()
    expect(await screen.findByText('Annual review')).toBeInTheDocument()
    expect(screen.queryByRole('form', { name: 'Change salary' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /apply salary change/i })).not.toBeInTheDocument()
  })

  it('shows not-found feedback for an unknown employee', async () => {
    renderApp(ui, { route: '/employees/999', role: 'hr_manager' })
    expect(await screen.findByText(/not found/i)).toBeInTheDocument()
  })
})
