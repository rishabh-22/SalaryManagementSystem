import { useState } from 'react'
import { Controller, useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Alert, Button, Dialog, DialogActions, DialogContent, DialogTitle, MenuItem, Stack, TextField } from '@mui/material'
import { useCreateUser } from '../api/hooks'
import { errorMessage } from '../api/client'
import type { Meta, UserCreate } from '../api/types'
import { label } from '../lib/format'

const schema = z.object({
  full_name: z.string().trim().min(1, 'Full name is required'),
  email: z.string().trim().min(1, 'Email is required').email('Enter a valid email'),
  password: z.string().min(8, 'Password must be at least 8 characters'),
  role: z.enum(['admin', 'hr_manager', 'viewer']),
})
type Values = z.infer<typeof schema>

const defaults: Values = { full_name: '', email: '', password: '', role: 'viewer' }

interface Props {
  open: boolean
  roles: Meta['roles']
  onClose: () => void
}

export function CreateUserDialog({ open, roles, onClose }: Props) {
  const create = useCreateUser()
  const [serverError, setServerError] = useState<string | null>(null)
  const {
    control,
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<Values>({ resolver: zodResolver(schema), defaultValues: defaults })

  const close = () => {
    reset(defaults)
    setServerError(null)
    onClose()
  }

  const onSubmit = (values: Values) => {
    setServerError(null)
    create.mutate(values as UserCreate, {
      onSuccess: close,
      onError: (err) => setServerError(errorMessage(err)),
    })
  }

  return (
    <Dialog open={open} onClose={close} fullWidth maxWidth="xs" aria-labelledby="create-user-title">
      <form onSubmit={handleSubmit(onSubmit)} noValidate>
        <DialogTitle id="create-user-title">Create user</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            {serverError && <Alert severity="error">{serverError}</Alert>}
            <TextField
              label="Full name"
              size="small"
              error={!!errors.full_name}
              helperText={errors.full_name?.message}
              {...register('full_name')}
            />
            <TextField
              label="Email"
              type="email"
              size="small"
              error={!!errors.email}
              helperText={errors.email?.message}
              {...register('email')}
            />
            <TextField
              label="Password"
              type="password"
              size="small"
              autoComplete="new-password"
              error={!!errors.password}
              helperText={errors.password?.message ?? 'At least 8 characters'}
              {...register('password')}
            />
            <Controller
              control={control}
              name="role"
              render={({ field }) => (
                <TextField select size="small" label="Role" {...field}>
                  {roles.map((r) => (
                    <MenuItem key={r} value={r}>
                      {label(r)}
                    </MenuItem>
                  ))}
                </TextField>
              )}
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={close}>Cancel</Button>
          <Button type="submit" variant="contained" disabled={create.isPending}>
            Create user
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  )
}
