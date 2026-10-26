import { useEffect, useRef, useState } from 'react'
import type { KeyboardEvent } from 'react'
import { Alert, Box, Button, Fab, IconButton, Paper, TextField, Typography } from '@mui/material'
import { errorMessage } from '../api/client'
import { useChat } from '../api/hooks'
import type { ChatMessage } from '../api/types'

const MAX_HISTORY = 20
const MAX_LENGTH = 2000

const GREETING =
  'Hi! Ask me about salaries, for example: "What is the salary of employee 42?", ' +
  '"Average pay in India?" or "Who got a salary revision last quarter?"'

/** The API requires the history to start with a user message and stay within its size cap. */
function historyForRequest(messages: ChatMessage[]): ChatMessage[] {
  const recent = messages.slice(-MAX_HISTORY)
  const firstUser = recent.findIndex((m) => m.role === 'user')
  return firstUser === -1 ? [] : recent.slice(firstUser)
}

export function ChatWidget() {
  const [open, setOpen] = useState(false)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [draft, setDraft] = useState('')
  const [error, setError] = useState<string | null>(null)
  const chat = useChat()
  const logRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const el = logRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [messages, chat.isPending, open])

  const send = () => {
    const content = draft.trim()
    if (!content || chat.isPending) return
    const next: ChatMessage[] = [...messages, { role: 'user', content }]
    setMessages(next)
    setDraft('')
    setError(null)
    chat.mutate(historyForRequest(next), {
      onSuccess: (data) => setMessages((prev) => [...prev, { role: 'assistant', content: data.reply }]),
      onError: (e) => setError(errorMessage(e)),
    })
  }

  const onKeyDown = (e: KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      send()
    }
  }

  if (!open) {
    return (
      <Fab
        color="primary"
        variant="extended"
        aria-label="Open chat assistant"
        onClick={() => setOpen(true)}
        sx={{ position: 'fixed', bottom: 24, right: 24, zIndex: 1300 }}
      >
        Ask AI
      </Fab>
    )
  }

  return (
    <Paper
      role="dialog"
      aria-label="Chat assistant"
      elevation={8}
      sx={{
        position: 'fixed',
        bottom: 24,
        right: 24,
        zIndex: 1300,
        width: 380,
        maxWidth: 'calc(100vw - 32px)',
        height: 520,
        maxHeight: 'calc(100vh - 48px)',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
      }}
    >
      <Box sx={{ bgcolor: 'primary.main', color: 'primary.contrastText', px: 2, py: 1, display: 'flex', alignItems: 'center' }}>
        <Typography variant="subtitle1" sx={{ flexGrow: 1 }}>
          Salary assistant
        </Typography>
        <IconButton size="small" color="inherit" aria-label="Close chat" onClick={() => setOpen(false)}>
          <span aria-hidden="true">&times;</span>
        </IconButton>
      </Box>

      <Box
        ref={logRef}
        role="log"
        aria-live="polite"
        aria-label="Conversation"
        sx={{ flexGrow: 1, overflowY: 'auto', p: 2, display: 'flex', flexDirection: 'column', gap: 1 }}
      >
        <Bubble role="assistant" content={GREETING} />
        {messages.map((m, i) => (
          <Bubble key={i} role={m.role} content={m.content} />
        ))}
        {chat.isPending && (
          <Typography role="status" variant="body2" color="text.secondary">
            Thinking…
          </Typography>
        )}
        {error && (
          <Alert severity="error" onClose={() => setError(null)}>
            {error}
          </Alert>
        )}
      </Box>

      <Box sx={{ p: 1.5, display: 'flex', gap: 1, borderTop: 1, borderColor: 'divider' }}>
        <TextField
          label="Message"
          size="small"
          fullWidth
          multiline
          maxRows={4}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={onKeyDown}
          slotProps={{ htmlInput: { maxLength: MAX_LENGTH } }}
        />
        <Button variant="contained" onClick={send} disabled={!draft.trim() || chat.isPending}>
          Send
        </Button>
      </Box>
    </Paper>
  )
}

function Bubble({ role, content }: ChatMessage) {
  const mine = role === 'user'
  return (
    <Box
      data-testid={`chat-${role}`}
      sx={{
        alignSelf: mine ? 'flex-end' : 'flex-start',
        maxWidth: '85%',
        px: 1.5,
        py: 1,
        borderRadius: 2,
        bgcolor: mine ? 'primary.main' : 'grey.200',
        color: mine ? 'primary.contrastText' : 'text.primary',
        whiteSpace: 'pre-wrap',
        overflowWrap: 'anywhere',
      }}
    >
      <Typography variant="body2">{content}</Typography>
    </Box>
  )
}
