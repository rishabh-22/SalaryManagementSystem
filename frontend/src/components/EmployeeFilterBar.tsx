import { Box, Button, MenuItem, TextField } from '@mui/material'
import type { Meta } from '../api/types'
import { label } from '../lib/format'
import { emptyFilters, type FilterState } from './employeeFilters'

interface Props {
  meta: Meta
  value: FilterState
  onChange: (next: FilterState) => void
}

const ALL = ''

export function EmployeeFilterBar({ meta, value, onChange }: Props) {
  const set = (patch: Partial<FilterState>) => onChange({ ...value, ...patch })

  const select = (key: Exclude<keyof FilterState, 'q'>, text: string, options: { value: string; text: string }[]) => (
    <TextField
      select
      size="small"
      label={text}
      value={value[key]}
      onChange={(e) => set({ [key]: e.target.value })}
      sx={{ minWidth: 160 }}
    >
      <MenuItem value={ALL}>All</MenuItem>
      {options.map((o) => (
        <MenuItem key={o.value} value={o.value}>
          {o.text}
        </MenuItem>
      ))}
    </TextField>
  )

  const isFiltered = Object.values(value).some(Boolean)

  return (
    <Box role="search" aria-label="Employee filters" sx={{ display: 'flex', flexWrap: 'wrap', gap: 2, alignItems: 'center' }}>
      <TextField
        size="small"
        type="search"
        label="Search employees"
        placeholder="Name, email or code"
        value={value.q}
        onChange={(e) => set({ q: e.target.value })}
        sx={{ minWidth: 240 }}
      />
      {select('country', 'Country', meta.countries.map((c) => ({ value: c.code, text: c.name })))}
      {select('department', 'Department', meta.departments.map((d) => ({ value: d, text: d })))}
      {select('job_title', 'Job title', meta.job_titles.map((t) => ({ value: t, text: t })))}
      {select('status', 'Status', meta.statuses.map((s) => ({ value: s, text: label(s) })))}
      {isFiltered && <Button onClick={() => onChange(emptyFilters)}>Clear filters</Button>}
    </Box>
  )
}
