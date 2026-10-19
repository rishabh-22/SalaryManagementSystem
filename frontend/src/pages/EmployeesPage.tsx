import { useMemo, useState } from 'react'
import { Link as RouterLink, useNavigate } from 'react-router-dom'
import { Alert, Box, Button, Link, Stack, Typography } from '@mui/material'
import {
  DataGrid,
  type GridColDef,
  type GridPaginationModel,
  type GridSortModel,
} from '@mui/x-data-grid'
import { downloadEmployeesCsv, useEmployees, useMeta } from '../api/hooks'
import { errorMessage } from '../api/client'
import type { Employee, EmployeeFilters } from '../api/types'
import { useAuth } from '../auth/AuthContext'
import { AddEmployeeDialog } from '../components/AddEmployeeDialog'
import { EmployeeFilterBar } from '../components/EmployeeFilterBar'
import { emptyFilters, type FilterState } from '../components/employeeFilters'
import { formatCurrency, label } from '../lib/format'
import { useDebounce } from '../lib/useDebounce'

const columns: GridColDef<Employee>[] = [
  { field: 'employee_code', headerName: 'Code', width: 120 },
  {
    field: 'first_name',
    headerName: 'First name',
    width: 140,
    renderCell: ({ row }) => (
      <Link component={RouterLink} to={`/employees/${row.id}`} aria-label={`View ${row.first_name} ${row.last_name}`}>
        {row.first_name}
      </Link>
    ),
  },
  { field: 'last_name', headerName: 'Last name', width: 140 },
  { field: 'email', headerName: 'Email', flex: 1, minWidth: 220, sortable: false },
  { field: 'job_title', headerName: 'Job title', width: 190 },
  { field: 'department', headerName: 'Department', width: 160 },
  { field: 'country_code', headerName: 'Country', width: 90 },
  {
    field: 'salary',
    headerName: 'Salary',
    width: 150,
    type: 'number',
    valueFormatter: (value: number, row: Employee) => formatCurrency(value, row.currency),
  },
  { field: 'hire_date', headerName: 'Hire date', width: 120 },
  {
    field: 'status',
    headerName: 'Status',
    width: 120,
    valueFormatter: (value: string) => label(value),
  },
]

export function EmployeesPage() {
  const navigate = useNavigate()
  const { canWrite } = useAuth()
  const metaQuery = useMeta()
  const [filters, setFilters] = useState<FilterState>(emptyFilters)
  const [paginationModel, setPaginationModel] = useState<GridPaginationModel>({ page: 0, pageSize: 25 })
  const [sortModel, setSortModel] = useState<GridSortModel>([])
  const [addOpen, setAddOpen] = useState(false)
  const [exportError, setExportError] = useState<string | null>(null)

  const debouncedQ = useDebounce(filters.q.trim(), 300)

  const activeFilters = useMemo<EmployeeFilters>(() => {
    const f: EmployeeFilters = {}
    if (debouncedQ) f.q = debouncedQ
    if (filters.country) f.country = filters.country
    if (filters.department) f.department = filters.department
    if (filters.job_title) f.job_title = filters.job_title
    if (filters.status) f.status = filters.status
    return f
  }, [debouncedQ, filters.country, filters.department, filters.job_title, filters.status])

  const sort = sortModel[0] ? `${sortModel[0].sort === 'desc' ? '-' : ''}${sortModel[0].field}` : undefined

  const { data, error, isFetching } = useEmployees({
    ...activeFilters,
    page: paginationModel.page + 1,
    page_size: paginationModel.pageSize,
    sort,
  })

  const changeFilters = (next: FilterState) => {
    setFilters(next)
    setPaginationModel((m) => ({ ...m, page: 0 }))
  }

  const handleExport = async () => {
    setExportError(null)
    try {
      await downloadEmployeesCsv(activeFilters, sort)
    } catch (err) {
      setExportError(errorMessage(err))
    }
  }

  return (
    <Stack spacing={2}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 1 }}>
        <Typography variant="h4" component="h1">
          Employees
        </Typography>
        <Stack direction="row" spacing={1}>
          <Button variant="outlined" onClick={handleExport}>
            Export CSV
          </Button>
          {canWrite && (
            <Button variant="contained" onClick={() => setAddOpen(true)}>
              Add employee
            </Button>
          )}
        </Stack>
      </Box>

      {metaQuery.data && <EmployeeFilterBar meta={metaQuery.data} value={filters} onChange={changeFilters} />}
      {metaQuery.error && <Alert severity="warning">Filters unavailable: {errorMessage(metaQuery.error)}</Alert>}
      {error && <Alert severity="error">{errorMessage(error)}</Alert>}
      {exportError && <Alert severity="error">{exportError}</Alert>}

      <Box sx={{ bgcolor: 'background.paper' }}>
        <DataGrid
          aria-label="Employees"
          columns={columns}
          rows={data?.items ?? []}
          rowCount={data?.total ?? 0}
          loading={isFetching}
          paginationMode="server"
          sortingMode="server"
          filterMode="server"
          paginationModel={paginationModel}
          onPaginationModelChange={setPaginationModel}
          sortModel={sortModel}
          onSortModelChange={(m) => {
            setSortModel(m)
            setPaginationModel((p) => ({ ...p, page: 0 }))
          }}
          pageSizeOptions={[10, 25, 50, 100]}
          disableRowSelectionOnClick
          disableColumnFilter
          disableColumnMenu
          autoHeight
          slotProps={{ loadingOverlay: { variant: 'linear-progress' } }}
          localeText={{ noRowsLabel: 'No employees match your filters' }}
        />
      </Box>

      {metaQuery.data && (
        <AddEmployeeDialog
          open={addOpen}
          meta={metaQuery.data}
          onClose={() => setAddOpen(false)}
          onCreated={(e) => {
            setAddOpen(false)
            navigate(`/employees/${e.id}`)
          }}
        />
      )}
    </Stack>
  )
}
