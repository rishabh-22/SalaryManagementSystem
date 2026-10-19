import { Paper, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Typography } from '@mui/material'
import Grid from '@mui/material/Grid'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { useOverview } from '../../api/hooks'
import { formatCurrency, formatNumber, label } from '../../lib/format'
import { QueryState } from '../QueryState'
import { CHART_COLOR } from './chartTheme'

interface ChartCardProps {
  title: string
  data: { name: string; headcount: number }[]
  layout?: 'horizontal' | 'vertical'
}

function HeadcountChart({ title, data, layout = 'horizontal' }: ChartCardProps) {
  const vertical = layout === 'vertical'
  return (
    <Paper sx={{ p: 2, height: '100%' }}>
      <Typography variant="subtitle1" component="h3" gutterBottom>
        {title}
      </Typography>
      <div role="img" aria-label={`${title} bar chart`} style={{ width: '100%', height: vertical ? 340 : 260 }}>
        <ResponsiveContainer>
          <BarChart data={data} layout={vertical ? 'vertical' : 'horizontal'} margin={{ left: vertical ? 40 : 0 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={vertical} horizontal={!vertical} />
            {vertical ? (
              <>
                <XAxis type="number" />
                <YAxis type="category" dataKey="name" width={120} />
              </>
            ) : (
              <>
                <XAxis dataKey="name" />
                <YAxis />
              </>
            )}
            <Tooltip formatter={(v) => [formatNumber(Number(v)), 'Headcount']} />
            <Bar dataKey="headcount" fill={CHART_COLOR} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </Paper>
  )
}

export function OverviewSection() {
  const { data, isPending, error } = useOverview()

  return (
    <section aria-labelledby="overview-heading">
      <Typography variant="h5" component="h2" id="overview-heading" gutterBottom>
        Company overview
      </Typography>
      <QueryState isPending={isPending} error={error} isEmpty={data?.total_headcount === 0} emptyText="No active employees.">
        {data && (
          <Grid container spacing={2}>
            <Grid size={12}>
              <Typography variant="body1">
                Total active headcount: <strong>{formatNumber(data.total_headcount)}</strong>
              </Typography>
            </Grid>
            <Grid size={{ xs: 12, md: 8 }}>
              <HeadcountChart
                title="Headcount by department"
                layout="vertical"
                data={data.by_department.map((d) => ({ name: d.department, headcount: d.headcount }))}
              />
            </Grid>
            <Grid size={{ xs: 12, md: 4 }}>
              <HeadcountChart
                title="Headcount by employment type"
                data={data.by_employment_type.map((d) => ({ name: label(d.employment_type), headcount: d.headcount }))}
              />
            </Grid>
            <Grid size={12}>
              <Paper sx={{ p: 2 }}>
                <Typography variant="subtitle1" component="h3" gutterBottom>
                  By country (each in its local currency)
                </Typography>
                <TableContainer>
                  <Table size="small" aria-label="Headcount and salary by country">
                    <TableHead>
                      <TableRow>
                        <TableCell>Country</TableCell>
                        <TableCell>Currency</TableCell>
                        <TableCell align="right">Headcount</TableCell>
                        <TableCell align="right">Median salary</TableCell>
                        <TableCell align="right">Mean salary</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {data.by_country.map((c) => (
                        <TableRow key={c.country_code}>
                          <TableCell>{c.country_code}</TableCell>
                          <TableCell>{c.currency}</TableCell>
                          <TableCell align="right">{formatNumber(c.headcount)}</TableCell>
                          <TableCell align="right">{formatCurrency(c.median_salary, c.currency)}</TableCell>
                          <TableCell align="right">{formatCurrency(c.mean_salary, c.currency)}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              </Paper>
            </Grid>
          </Grid>
        )}
      </QueryState>
    </section>
  )
}
