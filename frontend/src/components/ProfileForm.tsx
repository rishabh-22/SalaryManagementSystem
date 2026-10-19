import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { Alert, Button, Paper, Stack, Typography } from '@mui/material'
import { useUpdateEmployee } from '../api/hooks'
import { errorMessage, fieldErrors, httpStatus } from '../api/client'
import type { Employee, EmployeeUpdate, Meta } from '../api/types'
import { EmployeeFields } from './employeeForm'
import { profileDefaults, profileSchema, type ProfileValues } from './employeeSchemas'

interface Props {
  employee: Employee
  meta: Meta
  readOnly: boolean
}

export function ProfileForm({ employee, meta, readOnly }: Props) {
  const update = useUpdateEmployee(employee.id)
  const [serverError, setServerError] = useState<string | null>(null)
  const [serverFields, setServerFields] = useState<Record<string, string>>({})
  const [saved, setSaved] = useState(false)
  const {
    control,
    register,
    handleSubmit,
    reset,
    formState: { errors, isDirty },
  } = useForm<ProfileValues>({ resolver: zodResolver(profileSchema), values: profileDefaults(employee) })

  const onSubmit = (values: ProfileValues) => {
    setServerError(null)
    setServerFields({})
    setSaved(false)
    update.mutate(values as EmployeeUpdate, {
      onSuccess: (updated) => {
        reset(profileDefaults(updated))
        setSaved(true)
      },
      onError: (err) => {
        setServerFields(httpStatus(err) === 409 ? { email: errorMessage(err) } : fieldErrors(err))
        setServerError(errorMessage(err))
      },
    })
  }

  return (
    <Paper component="form" onSubmit={handleSubmit(onSubmit)} noValidate sx={{ p: 3 }} aria-label="Employee profile">
      <Typography variant="h6" component="h2" gutterBottom>
        Profile
      </Typography>
      {serverError && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {serverError}
        </Alert>
      )}
      {saved && (
        <Alert severity="success" sx={{ mb: 2 }}>
          Profile saved.
        </Alert>
      )}
      <fieldset disabled={readOnly} style={{ border: 0, padding: 0, margin: 0 }}>
        <EmployeeFields control={control} register={register} errors={errors} meta={meta} serverErrors={serverFields} />
      </fieldset>
      {!readOnly && (
        <Stack direction="row" justifyContent="flex-end" sx={{ mt: 2 }}>
          <Button type="submit" variant="contained" disabled={!isDirty || update.isPending}>
            Save profile
          </Button>
        </Stack>
      )}
    </Paper>
  )
}
