import { useState } from 'react'
import { Link as RouterLink, NavLink, Outlet, useNavigate } from 'react-router-dom'
import {
  AppBar,
  Avatar,
  Box,
  Button,
  Chip,
  Container,
  IconButton,
  Menu,
  MenuItem,
  Toolbar,
  Typography,
} from '@mui/material'
import { useAuth } from '../auth/AuthContext'
import { label } from '../lib/format'

const navButtonSx = {
  color: 'inherit',
  '&.active': { backgroundColor: 'rgba(255,255,255,0.18)' },
}

export function Layout() {
  const { user, logout, hasRole } = useAuth()
  const navigate = useNavigate()
  const [anchor, setAnchor] = useState<HTMLElement | null>(null)

  const handleLogout = () => {
    setAnchor(null)
    logout()
    navigate('/login', { replace: true })
  }

  return (
    <Box sx={{ minHeight: '100vh', bgcolor: 'background.default' }}>
      <AppBar position="static">
        <Toolbar>
          <Typography variant="h6" component={RouterLink} to="/employees" sx={{ color: 'inherit', textDecoration: 'none', mr: 3 }}>
            ACME Salaries
          </Typography>
          <Box component="nav" aria-label="Main navigation" sx={{ display: 'flex', gap: 1, flexGrow: 1 }}>
            <Button component={NavLink} to="/employees" sx={navButtonSx}>
              Employees
            </Button>
            <Button component={NavLink} to="/insights" sx={navButtonSx}>
              Insights
            </Button>
            {hasRole('admin') && (
              <Button component={NavLink} to="/users" sx={navButtonSx}>
                Users
              </Button>
            )}
          </Box>
          {user && (
            <>
              <Chip
                label={label(user.role)}
                size="small"
                color="secondary"
                aria-label={`Role: ${label(user.role)}`}
                sx={{ mr: 1 }}
              />
              <IconButton color="inherit" aria-label="User menu" onClick={(e) => setAnchor(e.currentTarget)}>
                <Avatar sx={{ width: 32, height: 32 }}>{user.full_name.charAt(0).toUpperCase()}</Avatar>
              </IconButton>
              <Menu anchorEl={anchor} open={!!anchor} onClose={() => setAnchor(null)}>
                <MenuItem disabled>{user.full_name}</MenuItem>
                <MenuItem disabled>{user.email}</MenuItem>
                <MenuItem onClick={handleLogout}>Log out</MenuItem>
              </Menu>
            </>
          )}
        </Toolbar>
      </AppBar>
      <Container maxWidth="xl" sx={{ py: 3 }} component="main">
        <Outlet />
      </Container>
    </Box>
  )
}
