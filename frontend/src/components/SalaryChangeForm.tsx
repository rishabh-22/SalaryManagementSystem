import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { Alert, Button, Paper, Stack, TextField, Typography } from '@mui/material'
import { useUpdateEmployee } from '../api/hooks'
import { qk } from '../api/queryKeys'
import { errorMessage, fieldErrors } from '../api/client'
import { useQueryClient } from '@tanstack/react-query'
import type { Employee } from '../api/types'
import { formatCurrency } from '../lib/format'
import { salaryChangeSchema, type SalaryChangeValues } from './employeeSchemas'

const today = () => new Date().toISOString().slice(0, 10)

export function SalaryChangeForm({ employee }: { employee: Employee }) {
  const qc = useQueryClient()
  const update = useUpdateEmployee(employee.id)
  const [serverError, setServerError] = useState<string | null>(null)
  const [serverFields, setServerFields] = useState<Record<string, string>>({})
  const [saved, setSaved] = useState(false)
  const {
    register,
    handleSubmit,
    reset,
    setError,
    formState: { errors },
  } = useForm<SalaryChangeValues>({
    resolver: zodResolver(salaryChangeSchema),
    defaultValues: { salary: '', effective_date: today(), reason: '' },
  })

  const onSubmit = (values: SalaryChangeValues) => {
    setServerError(null)
    setServerFields({})
    setSaved(false)
    const salary = Number(values.salary)
    if (salary === employee.salary) {
      setError('salary', { message: 'New salary must differ from the current salary' })
      return
    }
    update.mutate(
      { salary, salary_effective_date: values.effective_date, salary_change_reason: values.reason.trim() },
      {
        onSuccess: () => {
          void qc.invalidateQueries({ queryKey: qk.salaryHistory(employee.id) })
          reset({ salary: '', effective_date: today(), reason: '' })
          setSaved(true)
        },
        onError: (err) => {
          setServerFields(fieldErrors(err))
          setServerError(errorMessage(err))
        },
      },
    )
  }

  const fieldProps = (name: keyof SalaryChangeValues, serverName: string) => {
    const message = errors[name]?.message ?? serverFields[serverName]
    return { error: !!message, helperText: message }
  }

  return (
    <Paper component="form" onSubmit={handleSubmit(onSubmit)} noValidate sx={{ p: 3 }} aria-label="Change salary">
      <Typography variant="h6" component="h2" gutterBottom>
        Change salary
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        Current salary: {formatCurrency(employee.salary, employee.currency)}
      </Typography>
      {serverError && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {serverError}
        </Alert>
      )}
      {saved && (
        <Alert severity="success" sx={{ mb: 2 }}>
          Salary updated.
        </Alert>
      )}
      <Stack spacing={2}>
        <TextField
          label={`New salary (${employee.currency})`}
          type="number"
          size="small"
          slotProps={{ htmlInput: { step: '0.01', min: 0 } }}
          {...fieldProps('salary', 'salary')}
          {...register('salary')}
        />
        <TextField
          label="Effective date"
          type="date"
          size="small"
          slotProps={{ inputLabel: { shrink: true } }}
          {...fieldProps('effective_date', 'salary_effective_date')}
          {...register('effective_date')}
        />
        <TextField
          label="Reason"
          size="small"
          multiline
          minRows={2}
          {...fieldProps('reason', 'salary_change_reason')}
          {...register('reason')}
        />
        <Button type="submit" variant="contained" disabled={update.isPending}>
          Apply salary change
        </Button>
      </Stack>
    </Paper>
  )
}
