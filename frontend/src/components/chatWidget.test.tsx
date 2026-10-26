import { beforeEach, describe, expect, it } from 'vitest'
import { http, HttpResponse } from 'msw'
import { Route, Routes } from 'react-router-dom'
import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ChatWidget } from './ChatWidget'
import { Layout } from './Layout'
import { RequireRole } from '../auth/RequireRole'
import { renderApp } from '../test/render'
import { server } from '../test/server'

beforeEach(() => localStorage.clear())

const openChat = async (user: ReturnType<typeof userEvent.setup>) =>
  user.click(await screen.findByRole('button', { name: 'Open chat assistant' }))

describe('ChatWidget', () => {
  it('shows a bubble that opens and closes the chat window', async () => {
    const user = userEvent.setup()
    renderApp(<ChatWidget />, { role: 'viewer' })

    expect(screen.queryByRole('dialog', { name: 'Chat assistant' })).not.toBeInTheDocument()
    await openChat(user)
    expect(screen.getByRole('dialog', { name: 'Chat assistant' })).toBeInTheDocument()
    expect(screen.getByText(/Ask me about salaries/)).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Close chat' }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Open chat assistant' })).toBeInTheDocument()
  })

  it('posts the question and shows the assistant reply', async () => {
    const user = userEvent.setup()
    renderApp(<ChatWidget />, { role: 'hr_manager' })
    await openChat(user)

    await user.type(screen.getByLabelText('Message'), 'Average pay in India?')
    await user.click(screen.getByRole('button', { name: 'Send' }))

    expect(await screen.findByText('You asked: Average pay in India?')).toBeInTheDocument()
    expect(screen.getByTestId('chat-user')).toHaveTextContent('Average pay in India?')
    expect(screen.getByLabelText('Message')).toHaveValue('')
  })

  it('sends the whole conversation with each request', async () => {
    const user = userEvent.setup()
    const bodies: { messages: { role: string; content: string }[] }[] = []
    server.use(
      http.post('/api/chat', async ({ request }) => {
        bodies.push((await request.json()) as (typeof bodies)[number])
        return HttpResponse.json({ reply: `answer ${bodies.length}`, tools_used: [] })
      }),
    )
    renderApp(<ChatWidget />, { role: 'viewer' })
    await openChat(user)

    await user.type(screen.getByLabelText('Message'), 'salary of Ana{Enter}')
    await screen.findByText('answer 1')
    await user.type(screen.getByLabelText('Message'), 'id 7{Enter}')
    await screen.findByText('answer 2')

    expect(bodies[1].messages).toEqual([
      { role: 'user', content: 'salary of Ana' },
      { role: 'assistant', content: 'answer 1' },
      { role: 'user', content: 'id 7' },
    ])
  })

  it('disables Send for blank input and does not submit on Shift+Enter', async () => {
    const user = userEvent.setup()
    renderApp(<ChatWidget />, { role: 'viewer' })
    await openChat(user)

    const send = screen.getByRole('button', { name: 'Send' })
    expect(send).toBeDisabled()
    await user.type(screen.getByLabelText('Message'), '   ')
    expect(send).toBeDisabled()

    await user.type(screen.getByLabelText('Message'), 'hello{Shift>}{Enter}{/Shift}there')
    expect(screen.queryByTestId('chat-user')).not.toBeInTheDocument()
    expect(send).toBeEnabled()
  })

  it('shows a thinking indicator while waiting for the reply', async () => {
    const user = userEvent.setup()
    let release: () => void = () => {}
    const gate = new Promise<void>((resolve) => (release = resolve))
    server.use(
      http.post('/api/chat', async () => {
        await gate
        return HttpResponse.json({ reply: 'done', tools_used: [] })
      }),
    )
    renderApp(<ChatWidget />, { role: 'viewer' })
    await openChat(user)
    await user.type(screen.getByLabelText('Message'), 'hi{Enter}')

    expect(await screen.findByRole('status')).toHaveTextContent('Thinking')
    expect(screen.getByRole('button', { name: 'Send' })).toBeDisabled()
    release()
    expect(await screen.findByText('done')).toBeInTheDocument()
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })

  it('shows the server error message when chat fails', async () => {
    const user = userEvent.setup()
    server.use(
      http.post('/api/chat', () => HttpResponse.json({ detail: 'Chat is not configured' }, { status: 503 })),
    )
    renderApp(<ChatWidget />, { role: 'viewer' })
    await openChat(user)
    await user.type(screen.getByLabelText('Message'), 'hi{Enter}')

    const alert = await screen.findByRole('alert')
    expect(within(alert).getByText('Chat is not configured')).toBeInTheDocument()
    expect(screen.getByTestId('chat-user')).toHaveTextContent('hi')
  })
})

describe('ChatWidget placement', () => {
  const app = (
    <Routes>
      <Route path="/login" element={<h1>Login page</h1>} />
      <Route element={<RequireRole />}>
        <Route element={<Layout />}>
          <Route path="/employees" element={<p>Employees content</p>} />
        </Route>
      </Route>
    </Routes>
  )

  it('is available on authenticated pages', async () => {
    renderApp(app, { route: '/employees', role: 'viewer' })
    expect(await screen.findByRole('button', { name: 'Open chat assistant' })).toBeInTheDocument()
  })

  it('is not shown on the login page', async () => {
    renderApp(app, { route: '/login' })
    expect(await screen.findByRole('heading', { name: 'Login page' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Open chat assistant' })).not.toBeInTheDocument()
  })
})
