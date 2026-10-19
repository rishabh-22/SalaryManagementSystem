import { Controller, type Control, type FieldErrors, type FieldPath, type UseFormRegister } from 'react-hook-form'
import { MenuItem, TextField } from '@mui/material'
import Grid from '@mui/material/Grid'
import type { Meta } from '../api/types'
import type { ProfileValues } from './employeeSchemas'
import { label } from '../lib/format'

interface FieldsProps<T extends ProfileValues> {
  control: Control<T>
  register: UseFormRegister<T>
  errors: FieldErrors<T>
  meta: Meta
  /** Server-side 422 messages by field, shown when no client error exists. */
  serverErrors?: Record<string, string>
  children?: React.ReactNode
}

/** Shared profile inputs used by the create dialog and the edit form. */
export function EmployeeFields<T extends ProfileValues>({
  control,
  register,
  errors,
  meta,
  serverErrors = {},
  children,
}: FieldsProps<T>) {
  const err = (name: keyof ProfileValues) => {
    const message = (errors as FieldErrors<ProfileValues>)[name]?.message ?? serverErrors[name]
    return { error: !!message, helperText: message }
  }
  const select = (name: keyof ProfileValues, text: string, options: { value: string; text: string }[]) => (
    <Controller
      control={control}
      name={name as FieldPath<T>}
      render={({ field }) => (
        <TextField select fullWidth size="small" label={text} {...err(name)} {...field}>
          {options.map((o) => (
            <MenuItem key={o.value} value={o.value}>
              {o.text}
            </MenuItem>
          ))}
        </TextField>
      )}
    />
  )
  const plain = (name: keyof ProfileValues, text: string, type = 'text') => (
    <TextField
      fullWidth
      size="small"
      label={text}
      type={type}
      slotProps={type === 'date' ? { inputLabel: { shrink: true } } : undefined}
      {...err(name)}
      {...register(name as FieldPath<T>)}
    />
  )

  return (
    <Grid container spacing={2}>
      <Grid size={{ xs: 12, sm: 6 }}>{plain('first_name', 'First name')}</Grid>
      <Grid size={{ xs: 12, sm: 6 }}>{plain('last_name', 'Last name')}</Grid>
      <Grid size={12}>{plain('email', 'Email', 'email')}</Grid>
      <Grid size={{ xs: 12, sm: 6 }}>
        {select('job_title', 'Job title', meta.job_titles.map((t) => ({ value: t, text: t })))}
      </Grid>
      <Grid size={{ xs: 12, sm: 6 }}>
        {select('department', 'Department', meta.departments.map((d) => ({ value: d, text: d })))}
      </Grid>
      <Grid size={{ xs: 12, sm: 6 }}>
        {select(
          'country_code',
          'Country',
          meta.countries.map((c) => ({ value: c.code, text: `${c.name} (${c.currency})` })),
        )}
      </Grid>
      <Grid size={{ xs: 12, sm: 6 }}>
        {select(
          'employment_type',
          'Employment type',
          meta.employment_types.map((t) => ({ value: t, text: label(t) })),
        )}
      </Grid>
      <Grid size={{ xs: 12, sm: 6 }}>{plain('hire_date', 'Hire date', 'date')}</Grid>
      {children}
    </Grid>
  )
}
