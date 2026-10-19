import { Link as RouterLink } from 'react-router-dom'
import {
  Link,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material'
import Grid from '@mui/material/Grid'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { useCountryInsights, useDistribution, useOutliers } from '../../api/hooks'
import type { Summary } from '../../api/types'
import { formatCurrency, formatNumber, formatPercent } from '../../lib/format'
import { QueryState } from '../QueryState'
import { CHART_COLOR, compactNumber } from './chartTheme'

function Kpi({ name, value }: { name: string; value: string }) {
  return (
    <Paper sx={{ p: 2 }} role="group" aria-label={name}>
      <Typography variant="caption" color="text.secondary">
        {name}
      </Typography>
      <Typography variant="h6" component="p">
        {value}
      </Typography>
    </Paper>
  )
}

function KpiTiles({ summary, currency }: { summary: Summary; currency: string }) {
  const money = (v: number | null) => formatCurrency(v, currency)
  const tiles: [string, string][] = [
    ['Headcount', formatNumber(summary.headcount)],
    ['Median salary', money(summary.median)],
    ['Mean salary', money(summary.mean)],
    ['25th percentile', money(summary.p25)],
    ['75th percentile', money(summary.p75)],
    ['Minimum', money(summary.min)],
    ['Maximum', money(summary.max)],
    ['Total payroll', money(summary.total_payroll)],
  ]
  return (
    <Grid container spacing={2}>
      {tiles.map(([name, value]) => (
        <Grid key={name} size={{ xs: 6, md: 3 }}>
          <Kpi name={name} value={value} />
        </Grid>
      ))}
    </Grid>
  )
}

function ChartFrame({ title, description, children }: { title: string; description: string; children: React.ReactNode }) {
  return (
    <Paper sx={{ p: 2, height: '100%' }}>
      <Typography variant="subtitle1" component="h3">
        {title}
      </Typography>
      <Typography variant="caption" color="text.secondary" component="p" gutterBottom>
        {description}
      </Typography>
      <div role="img" aria-label={title} style={{ width: '100%', height: 300 }}>
        <ResponsiveContainer>{children as React.ReactElement}</ResponsiveContainer>
      </div>
    </Paper>
  )
}

function DistributionChart({ code }: { code: string }) {
  const { data, isPending, error } = useDistribution(code)
  return (
    <QueryState isPending={isPending} error={error} isEmpty={data?.bins.length === 0} emptyText="No salary data.">
      {data && (
        <ChartFrame
          title={`Salary distribution (${data.currency})`}
          description="Number of active employees per salary band"
        >
          <BarChart
            data={data.bins.map((b) => ({
              range: b.lower === b.upper ? compactNumber(b.lower) : `${compactNumber(b.lower)}-${compactNumber(b.upper)}`,
              count: b.count,
            }))}
          >
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="range" interval="preserveStartEnd" />
            <YAxis allowDecimals={false} />
            <Tooltip formatter={(v) => [formatNumber(Number(v)), 'Employees']} />
            <Bar dataKey="count" fill={CHART_COLOR} />
          </BarChart>
        </ChartFrame>
      )}
    </QueryState>
  )
}

function OutliersList({ code }: { code: string }) {
  const { data, isPending, error } = useOutliers(code)
  return (
    <Paper sx={{ p: 2 }}>
      <Typography variant="subtitle1" component="h3" gutterBottom>
        Salary outliers
      </Typography>
      <Typography variant="caption" color="text.secondary" component="p" gutterBottom>
        More than {data ? formatPercent(data.threshold).replace('+', '') : '30%'} away from their job title median
      </Typography>
      <QueryState isPending={isPending} error={error} isEmpty={data?.items.length === 0} emptyText="No outliers found.">
        {data && (
          <TableContainer sx={{ maxHeight: 400 }}>
            <Table size="small" stickyHeader aria-label="Salary outliers">
              <TableHead>
                <TableRow>
                  <TableCell>Employee</TableCell>
                  <TableCell>Job title</TableCell>
                  <TableCell align="right">Salary</TableCell>
                  <TableCell align="right">Title median</TableCell>
                  <TableCell align="right">Deviation</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {data.items.map((o) => (
                  <TableRow key={o.employee_id}>
                    <TableCell>
                      <Link component={RouterLink} to={`/employees/${o.employee_id}`}>
                        {o.full_name}
                      </Link>{' '}
                      <Typography variant="caption" color="text.secondary">
                        {o.employee_code}
                      </Typography>
                    </TableCell>
                    <TableCell>{o.job_title}</TableCell>
                    <TableCell align="right">{formatCurrency(o.salary, data.currency)}</TableCell>
                    <TableCell align="right">{formatCurrency(o.job_title_median, data.currency)}</TableCell>
                    <TableCell align="right">{formatPercent(o.deviation)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </QueryState>
    </Paper>
  )
}

export function CountrySection({ code }: { code: string }) {
  const { data, isPending, error } = useCountryInsights(code)

  return (
    <QueryState isPending={isPending} error={error} isEmpty={data?.summary.headcount === 0} emptyText="No active employees in this country.">
      {data && (
        <Grid container spacing={2} aria-label={`Insights for ${data.country_code}`} role="region">
          <Grid size={12}>
            <KpiTiles summary={data.summary} currency={data.currency} />
          </Grid>
          <Grid size={{ xs: 12, lg: 6 }}>
            <ChartFrame
              title={`Median salary by department (${data.currency})`}
              description="Active employees only"
            >
              <BarChart
                layout="vertical"
                margin={{ left: 40 }}
                data={data.by_department.map((d) => ({ name: d.department, median: d.summary.median ?? 0 }))}
              >
                <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                <XAxis type="number" tickFormatter={compactNumber} />
                <YAxis type="category" dataKey="name" width={120} />
                <Tooltip formatter={(v) => [formatCurrency(Number(v), data.currency), 'Median']} />
                <Bar dataKey="median" fill={CHART_COLOR} />
              </BarChart>
            </ChartFrame>
          </Grid>
          <Grid size={{ xs: 12, lg: 6 }}>
            <DistributionChart code={code} />
          </Grid>
          <Grid size={12}>
            <Paper sx={{ p: 2 }}>
              <Typography variant="subtitle1" component="h3" gutterBottom>
                By job title ({data.currency})
              </Typography>
              <TableContainer sx={{ maxHeight: 440 }}>
                <Table size="small" stickyHeader aria-label="Salary by job title">
                  <TableHead>
                    <TableRow>
                      <TableCell>Job title</TableCell>
                      <TableCell align="right">Headcount</TableCell>
                      <TableCell align="right">Min</TableCell>
                      <TableCell align="right">Median</TableCell>
                      <TableCell align="right">Mean</TableCell>
                      <TableCell align="right">Max</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {data.by_job_title.map((j) => (
                      <TableRow key={j.job_title}>
                        <TableCell>{j.job_title}</TableCell>
                        <TableCell align="right">{formatNumber(j.summary.headcount)}</TableCell>
                        <TableCell align="right">{formatCurrency(j.summary.min, data.currency)}</TableCell>
                        <TableCell align="right">{formatCurrency(j.summary.median, data.currency)}</TableCell>
                        <TableCell align="right">{formatCurrency(j.summary.mean, data.currency)}</TableCell>
                        <TableCell align="right">{formatCurrency(j.summary.max, data.currency)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </Paper>
          </Grid>
          <Grid size={12}>
            <OutliersList code={code} />
          </Grid>
        </Grid>
      )}
    </QueryState>
  )
}
