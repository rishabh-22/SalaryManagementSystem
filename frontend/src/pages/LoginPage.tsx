import { useState } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { Alert, Box, Button, Paper, TextField, Typography } from '@mui/material'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useAuth } from '../auth/AuthContext'
import { errorMessage, httpStatus } from '../api/client'

const schema = z.object({
  email: z.string().min(1, 'Email is required').email('Enter a valid email'),
  password: z.string().min(1, 'Password is required'),
})
type FormValues = z.infer<typeof schema>

export function LoginPage() {
  const { login, isAuthenticated } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [serverError, setServerError] = useState<string | null>(null)
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema) })

  const from = (location.state as { from?: string } | null)?.from ?? '/employees'
  if (isAuthenticated) return <Navigate to={from} replace />

  const onSubmit = async (values: FormValues) => {
    setServerError(null)
    try {
      await login(values.email, values.password)
      navigate(from, { replace: true })
    } catch (err) {
      setServerError(httpStatus(err) === 401 ? 'Invalid email or password.' : errorMessage(err))
    }
  }

  return (
    <Box sx={{ minHeight: '100vh', display: 'grid', placeItems: 'center', bgcolor: 'background.default', p: 2 }}>
      <Paper component="form" onSubmit={handleSubmit(onSubmit)} noValidate sx={{ p: 4, width: '100%', maxWidth: 400 }}>
        <Typography variant="h5" component="h1" gutterBottom>
          ACME Salary Management
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          Sign in to continue
        </Typography>
        {serverError && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {serverError}
          </Alert>
        )}
        <TextField
          label="Email"
          type="email"
          autoComplete="username"
          fullWidth
          margin="normal"
          error={!!errors.email}
          helperText={errors.email?.message}
          {...register('email')}
        />
        <TextField
          label="Password"
          type="password"
          autoComplete="current-password"
          fullWidth
          margin="normal"
          error={!!errors.password}
          helperText={errors.password?.message}
          {...register('password')}
        />
        <Button type="submit" variant="contained" fullWidth disabled={isSubmitting} sx={{ mt: 2 }}>
          Sign in
        </Button>
      </Paper>
    </Box>
  )
}
