import { Paper, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Typography } from '@mui/material'
import { useSalaryHistory } from '../api/hooks'
import { formatCurrency, formatPercent } from '../lib/format'
import { QueryState } from './QueryState'

export function SalaryHistoryTable({ employeeId, currency }: { employeeId: number; currency: string }) {
  const { data, isPending, error } = useSalaryHistory(employeeId)

  return (
    <Paper sx={{ p: 3 }}>
      <Typography variant="h6" component="h2" gutterBottom>
        Salary history
      </Typography>
      <QueryState isPending={isPending} error={error} isEmpty={data?.length === 0} emptyText="No salary changes recorded.">
        <TableContainer>
          <Table size="small" aria-label="Salary history">
            <TableHead>
              <TableRow>
                <TableCell>Effective date</TableCell>
                <TableCell align="right">Old salary</TableCell>
                <TableCell align="right">New salary</TableCell>
                <TableCell align="right">Change</TableCell>
                <TableCell>Reason</TableCell>
                <TableCell>Changed by</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {data?.map((c) => (
                <TableRow key={c.id}>
                  <TableCell>{c.effective_date}</TableCell>
                  <TableCell align="right">{formatCurrency(c.old_salary, currency)}</TableCell>
                  <TableCell align="right">{formatCurrency(c.new_salary, currency)}</TableCell>
                  <TableCell align="right">
                    {c.old_salary > 0 ? formatPercent((c.new_salary - c.old_salary) / c.old_salary) : '-'}
                  </TableCell>
                  <TableCell>{c.reason}</TableCell>
                  <TableCell>{c.changed_by?.full_name ?? '-'}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      </QueryState>
    </Paper>
  )
}
