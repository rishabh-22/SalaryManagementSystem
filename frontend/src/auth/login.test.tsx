import { beforeEach, describe, expect, it } from 'vitest'
import { Route, Routes } from 'react-router-dom'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { LoginPage } from '../pages/LoginPage'
import { tokenStore } from '../api/client'
import { DEMO_PASSWORD, tokenFor } from '../test/handlers'
import { renderApp } from '../test/render'

const ui = (
  <Routes>
    <Route path="/login" element={<LoginPage />} />
    <Route path="/employees" element={<h1>Employees landing</h1>} />
  </Routes>
)

beforeEach(() => localStorage.clear())

describe('login flow', () => {
  it('signs in, stores the token and navigates to employees', async () => {
    const user = userEvent.setup()
    renderApp(ui, { route: '/login' })
    await user.type(screen.getByLabelText(/email/i), 'hr@acme.com')
    await user.type(screen.getByLabelText(/password/i), DEMO_PASSWORD)
    await user.click(screen.getByRole('button', { name: /sign in/i }))
    expect(await screen.findByRole('heading', { name: 'Employees landing' })).toBeInTheDocument()
    expect(tokenStore.get()).toBe(tokenFor('hr_manager'))
  })

  it('shows an error and stores no token on bad credentials', async () => {
    const user = userEvent.setup()
    renderApp(ui, { route: '/login' })
    await user.type(screen.getByLabelText(/email/i), 'hr@acme.com')
    await user.type(screen.getByLabelText(/password/i), 'wrong')
    await user.click(screen.getByRole('button', { name: /sign in/i }))
    expect(await screen.findByText(/invalid email or password/i)).toBeInTheDocument()
    expect(tokenStore.get()).toBeNull()
  })

  it('validates required fields before calling the API', async () => {
    const user = userEvent.setup()
    renderApp(ui, { route: '/login' })
    await user.click(screen.getByRole('button', { name: /sign in/i }))
    expect(await screen.findByText(/email is required/i)).toBeInTheDocument()
    expect(screen.getByText(/password is required/i)).toBeInTheDocument()
  })

  it('rejects a malformed email', async () => {
    const user = userEvent.setup()
    renderApp(ui, { route: '/login' })
    await user.type(screen.getByLabelText(/email/i), 'not-an-email')
    await user.type(screen.getByLabelText(/password/i), 'x')
    await user.click(screen.getByRole('button', { name: /sign in/i }))
    expect(await screen.findByText(/valid email/i)).toBeInTheDocument()
  })

  it('redirects an already signed-in user away from /login', async () => {
    renderApp(ui, { route: '/login', role: 'viewer' })
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Employees landing' })).toBeInTheDocument())
  })
})
