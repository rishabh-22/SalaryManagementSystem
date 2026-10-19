import type { ReactElement } from 'react'
import { render } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AuthProvider } from '../auth/AuthContext'
import { tokenStore } from '../api/client'
import { tokenFor } from './handlers'
import type { Role } from '../api/types'

/** Renders with router, react-query and auth providers. Pass `role` to start signed in. */
export function renderApp(ui: ReactElement, opts: { route?: string; role?: Role } = {}) {
  if (opts.role) tokenStore.set(tokenFor(opts.role))
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[opts.route ?? '/']}>
        <AuthProvider>{ui}</AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}
