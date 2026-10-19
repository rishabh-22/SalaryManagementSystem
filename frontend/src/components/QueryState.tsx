import type { ReactNode } from 'react'
import { Alert, Box, CircularProgress } from '@mui/material'
import { errorMessage } from '../api/client'

interface Props {
  isPending: boolean
  error: unknown
  isEmpty?: boolean
  emptyText?: string
  children: ReactNode
}

/** Shared loading / error / empty rendering for query-backed sections. */
export function QueryState({ isPending, error, isEmpty, emptyText = 'No data to show.', children }: Props) {
  if (isPending) {
    return (
      <Box sx={{ display: 'grid', placeItems: 'center', py: 4 }}>
        <CircularProgress aria-label="Loading" />
      </Box>
    )
  }
  if (error) return <Alert severity="error">{errorMessage(error)}</Alert>
  if (isEmpty) return <Alert severity="info">{emptyText}</Alert>
  return <>{children}</>
}
