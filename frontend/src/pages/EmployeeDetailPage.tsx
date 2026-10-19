import { useState } from 'react'
import { Link as RouterLink, useParams } from 'react-router-dom'
import { Alert, Box, Button, Chip, Stack, Typography } from '@mui/material'
import Grid from '@mui/material/Grid'
import { useEmployee, useMeta, useTerminateEmployee } from '../api/hooks'
import { errorMessage, httpStatus } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { ConfirmDialog } from '../components/ConfirmDialog'
import { ProfileForm } from '../components/ProfileForm'
import { QueryState } from '../components/QueryState'
import { SalaryChangeForm } from '../components/SalaryChangeForm'
import { SalaryHistoryTable } from '../components/SalaryHistoryTable'
import { formatCurrency, label } from '../lib/format'

export function EmployeeDetailPage() {
  const id = Number(useParams().id)
  const { canWrite } = useAuth()
  const employeeQuery = useEmployee(id)
  const metaQuery = useMeta()
  const terminate = useTerminateEmployee(id)
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)

  const employee = employeeQuery.data
  const notFound = httpStatus(employeeQuery.error) === 404 || !Number.isFinite(id)

  const handleTerminate = () => {
    setActionError(null)
    terminate.mutate(undefined, {
      onSuccess: () => setConfirmOpen(false),
      onError: (err) => {
        setConfirmOpen(false)
        setActionError(errorMessage(err))
      },
    })
  }

  return (
    <Stack spacing={2}>
      <Box>
        <Button component={RouterLink} to="/employees" size="small">
          Back to employees
        </Button>
      </Box>
      {notFound ? (
        <Alert severity="error">Employee not found.</Alert>
      ) : (
        <QueryState isPending={employeeQuery.isPending || metaQuery.isPending} error={employeeQuery.error ?? metaQuery.error}>
          {employee && metaQuery.data && (
            <>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, flexWrap: 'wrap' }}>
                <Typography variant="h4" component="h1">
                  {employee.first_name} {employee.last_name}
                </Typography>
                <Chip label={employee.employee_code} variant="outlined" />
                <Chip
                  label={label(employee.status)}
                  color={employee.status === 'active' ? 'success' : 'default'}
                  aria-label={`Status: ${label(employee.status)}`}
                />
                <Typography variant="h6" component="p" color="text.secondary" sx={{ flexGrow: 1 }}>
                  {formatCurrency(employee.salary, employee.currency)} / year
                </Typography>
                {canWrite && employee.status === 'active' && (
                  <Button color="error" variant="outlined" onClick={() => setConfirmOpen(true)}>
                    Terminate employee
                  </Button>
                )}
              </Box>
              {actionError && <Alert severity="error">{actionError}</Alert>}
              {!canWrite && <Alert severity="info">You have read-only access.</Alert>}
              <Grid container spacing={2}>
                <Grid size={{ xs: 12, md: 7 }}>
                  <ProfileForm employee={employee} meta={metaQuery.data} readOnly={!canWrite} />
                </Grid>
                {canWrite && (
                  <Grid size={{ xs: 12, md: 5 }}>
                    <SalaryChangeForm employee={employee} />
                  </Grid>
                )}
                <Grid size={12}>
                  <SalaryHistoryTable employeeId={employee.id} currency={employee.currency} />
                </Grid>
              </Grid>
              <ConfirmDialog
                open={confirmOpen}
                title="Terminate employee?"
                message={`${employee.first_name} ${employee.last_name} will be marked as terminated and excluded from insights. Their record and salary history are kept.`}
                confirmLabel="Confirm termination"
                busy={terminate.isPending}
                onConfirm={handleTerminate}
                onCancel={() => setConfirmOpen(false)}
              />
            </>
          )}
        </QueryState>
      )}
    </Stack>
  )
}
