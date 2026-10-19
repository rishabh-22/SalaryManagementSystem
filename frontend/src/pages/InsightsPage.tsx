import { useState } from 'react'
import { Alert, MenuItem, Stack, TextField, Typography } from '@mui/material'
import { useMeta } from '../api/hooks'
import { errorMessage } from '../api/client'
import { CountrySection } from '../components/insights/CountrySection'
import { OverviewSection } from '../components/insights/OverviewSection'

export function InsightsPage() {
  const { data: meta, error } = useMeta()
  const [country, setCountry] = useState('')

  return (
    <Stack spacing={3}>
      <Typography variant="h4" component="h1">
        Insights
      </Typography>
      <Alert severity="info">
        Salaries are shown in each country&apos;s local currency and are never converted or combined across countries.
        Figures cover active employees only.
      </Alert>
      <OverviewSection />
      <section aria-labelledby="country-heading">
        <Stack spacing={2}>
          <Typography variant="h5" component="h2" id="country-heading">
            Country insights
          </Typography>
          {error && <Alert severity="error">{errorMessage(error)}</Alert>}
          <TextField
            select
            size="small"
            label="Country"
            value={country}
            onChange={(e) => setCountry(e.target.value)}
            sx={{ maxWidth: 320 }}
            disabled={!meta}
          >
            {meta?.countries.map((c) => (
              <MenuItem key={c.code} value={c.code}>
                {c.name} ({c.currency})
              </MenuItem>
            ))}
          </TextField>
          {country ? (
            <CountrySection code={country} />
          ) : (
            <Alert severity="info">Select a country to see salary statistics.</Alert>
          )}
        </Stack>
      </section>
    </Stack>
  )
}
