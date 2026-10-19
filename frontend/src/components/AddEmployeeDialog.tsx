import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { Alert, Button, Dialog, DialogActions, DialogContent, DialogTitle, TextField } from '@mui/material'
import Grid from '@mui/material/Grid'
import { useCreateEmployee } from '../api/hooks'
import { errorMessage, fieldErrors, httpStatus } from '../api/client'
import type { Employee, Meta } from '../api/types'
import { EmployeeFields } from './employeeForm'
import { createSchema, emptyCreateValues, toCreatePayload, type CreateValues } from './employeeSchemas'

interface Props {
  open: boolean
  meta: Meta
  onClose: () => void
  onCreated: (employee: Employee) => void
}

export function AddEmployeeDialog({ open, meta, onClose, onCreated }: Props) {
  const create = useCreateEmployee()
  const [serverError, setServerError] = useState<string | null>(null)
  const [serverFields, setServerFields] = useState<Record<string, string>>({})
  const {
    control,
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<CreateValues>({ resolver: zodResolver(createSchema), defaultValues: emptyCreateValues })

  const close = () => {
    reset(emptyCreateValues)
    setServerError(null)
    setServerFields({})
    onClose()
  }

  const onSubmit = (values: CreateValues) => {
    setServerError(null)
    setServerFields({})
    create.mutate(toCreatePayload(values), {
      onSuccess: (employee) => {
        reset(emptyCreateValues)
        onCreated(employee)
      },
      onError: (err) => {
        const fields = fieldErrors(err)
        setServerFields(fields)
        // 409 (duplicate email) is attached to the email field as well as the banner.
        if (httpStatus(err) === 409) setServerFields({ email: errorMessage(err) })
        setServerError(errorMessage(err))
      },
    })
  }

  return (
    <Dialog open={open} onClose={close} fullWidth maxWidth="sm" aria-labelledby="add-employee-title">
      <form onSubmit={handleSubmit(onSubmit)} noValidate>
        <DialogTitle id="add-employee-title">Add employee</DialogTitle>
        <DialogContent>
          {serverError && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {serverError}
            </Alert>
          )}
          <EmployeeFields control={control} register={register} errors={errors} meta={meta} serverErrors={serverFields}>
            <Grid size={{ xs: 12, sm: 6 }}>
              <TextField
                fullWidth
                size="small"
                label="Salary"
                type="number"
                slotProps={{ htmlInput: { step: '0.01', min: 0 } }}
                error={!!(errors.salary?.message ?? serverFields.salary)}
                helperText={errors.salary?.message ?? serverFields.salary ?? 'Annual, in the local currency'}
                {...register('salary')}
              />
            </Grid>
          </EmployeeFields>
        </DialogContent>
        <DialogActions>
          <Button onClick={close}>Cancel</Button>
          <Button type="submit" variant="contained" disabled={create.isPending}>
            Create employee
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  )
}
