import { beforeEach, describe, expect, it } from 'vitest'
import { Route, Routes } from 'react-router-dom'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Layout } from './Layout'
import { RequireRole } from '../auth/RequireRole'
import { renderApp } from '../test/render'
import { tokenStore } from '../api/client'
import type { Role } from '../api/types'

const ui = (
  <Routes>
    <Route path="/login" element={<h1>Login page</h1>} />
    <Route element={<RequireRole />}>
      <Route element={<Layout />}>
        <Route path="/employees" element={<p>Employees content</p>} />
        <Route element={<RequireRole roles={['admin']} />}>
          <Route path="/users" element={<p>Users content</p>} />
        </Route>
      </Route>
    </Route>
  </Routes>
)

beforeEach(() => localStorage.clear())

describe('role-based navigation', () => {
  it.each<[Role, boolean]>([
    ['admin', true],
    ['hr_manager', false],
    ['viewer', false],
  ])('%s sees Users nav: %s', async (role, visible) => {
    renderApp(ui, { route: '/employees', role })
    expect(await screen.findByText('Employees content')).toBeInTheDocument()
    const link = screen.queryByRole('link', { name: 'Users' })
    if (visible) expect(link).toBeInTheDocument()
    else expect(link).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Insights' })).toBeInTheDocument()
  })

  it('shows the signed-in role', async () => {
    renderApp(ui, { route: '/employees', role: 'viewer' })
    expect(await screen.findByLabelText('Role: Viewer')).toBeInTheDocument()
  })

  it('blocks a viewer who navigates directly to /users', async () => {
    renderApp(ui, { route: '/users', role: 'viewer' })
    expect(await screen.findByText(/do not have permission/i)).toBeInTheDocument()
    expect(screen.queryByText('Users content')).not.toBeInTheDocument()
  })

  it('lets an admin open /users', async () => {
    renderApp(ui, { route: '/users', role: 'admin' })
    expect(await screen.findByText('Users content')).toBeInTheDocument()
  })

  it('redirects anonymous visitors to /login', async () => {
    renderApp(ui, { route: '/employees' })
    expect(await screen.findByRole('heading', { name: 'Login page' })).toBeInTheDocument()
  })

  it('logs out: clears token and returns to login', async () => {
    const user = userEvent.setup()
    renderApp(ui, { route: '/employees', role: 'hr_manager' })
    await user.click(await screen.findByRole('button', { name: 'User menu' }))
    await user.click(await screen.findByRole('menuitem', { name: 'Log out' }))
    expect(await screen.findByRole('heading', { name: 'Login page' })).toBeInTheDocument()
    expect(tokenStore.get()).toBeNull()
  })
})
