import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { Alert, Box, CircularProgress } from '@mui/material'
import { useAuth } from './AuthContext'
import type { Role } from '../api/types'

interface Props {
  /** Omit to require only authentication. */
  roles?: Role[]
}

export function RequireRole({ roles }: Props) {
  const { user, isLoading, isAuthenticated } = useAuth()
  const location = useLocation()

  if (isLoading) {
    return (
      <Box sx={{ display: 'grid', placeItems: 'center', minHeight: '50vh' }}>
        <CircularProgress aria-label="Loading session" />
      </Box>
    )
  }
  if (!isAuthenticated) return <Navigate to="/login" replace state={{ from: location.pathname }} />
  if (roles && user && !roles.includes(user.role)) {
    return (
      <Alert severity="error" sx={{ m: 3 }}>
        You do not have permission to view this page.
      </Alert>
    )
  }
  return <Outlet />
}
