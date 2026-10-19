import { beforeEach, describe, expect, it } from 'vitest'
import { http, HttpResponse } from 'msw'
import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { InsightsPage } from './InsightsPage'
import { server } from '../test/server'
import { renderApp } from '../test/render'

beforeEach(() => localStorage.clear())

async function pickCountry(name: RegExp) {
  const user = userEvent.setup()
  await user.click(await screen.findByRole('combobox', { name: 'Country' }))
  await user.click(await screen.findByRole('option', { name }))
}

describe('InsightsPage', () => {
  it('renders the org overview and states that currencies are never combined', async () => {
    renderApp(<InsightsPage />, { role: 'viewer' })
    expect(await screen.findByRole('heading', { name: 'Insights' })).toBeInTheDocument()
    expect(screen.getByText(/never converted or combined/i)).toBeInTheDocument()
    expect(await screen.findByText(/select a country/i)).toBeInTheDocument()
    // overview table shows each country's median in its own currency
    expect(await screen.findByText('$100,000.00')).toBeInTheDocument()
    expect(screen.getByText(/R\$\s?180,000\.00/)).toBeInTheDocument()
  })

  it('shows KPI tiles in the selected country currency', async () => {
    renderApp(<InsightsPage />, { role: 'viewer' })
    await pickCountry(/United States/)
    const region = await screen.findByRole('region', { name: 'Insights for US' })
    expect(within(within(region).getByRole('group', { name: 'Headcount' })).getByText('6')).toBeInTheDocument()
    expect(within(within(region).getByRole('group', { name: 'Median salary' })).getByText('$100,000.00')).toBeInTheDocument()
    expect(within(within(region).getByRole('group', { name: 'Total payroll' })).getByText('$600,000.00')).toBeInTheDocument()
  })

  it('renders the job-title table and the outliers list with signed deviation', async () => {
    renderApp(<InsightsPage />, { role: 'viewer' })
    await pickCountry(/United States/)
    const titles = await screen.findByRole('table', { name: 'Salary by job title' })
    expect(within(titles).getByText('Software Engineer')).toBeInTheDocument()
    expect(within(titles).getByText('Account Executive')).toBeInTheDocument()
    const outliers = await screen.findByRole('table', { name: 'Salary outliers' })
    expect(within(outliers).getByRole('link', { name: 'Zoe Outlier' })).toHaveAttribute('href', '/employees/5')
    expect(within(outliers).getByText('+60%')).toBeInTheDocument()
    expect(within(outliers).getByText('$160,000.00')).toBeInTheDocument()
  })

  it('formats a different country in its own currency', async () => {
    renderApp(<InsightsPage />, { role: 'viewer' })
    await pickCountry(/India/)
    const region = await screen.findByRole('region', { name: 'Insights for IN' })
    expect(within(within(region).getByRole('group', { name: 'Median salary' })).getByText(/₹\s?100,000\.00/)).toBeInTheDocument()
  })

  it('shows an empty state for a country with no active employees', async () => {
    server.use(
      http.get('/api/insights/country/:code', () =>
        HttpResponse.json({
          country_code: 'DE',
          currency: 'EUR',
          summary: { headcount: 0, min: null, p25: null, median: null, p75: null, max: null, mean: null, total_payroll: null },
          by_department: [],
          by_job_title: [],
        }),
      ),
    )
    renderApp(<InsightsPage />, { role: 'viewer' })
    await pickCountry(/Germany/)
    expect(await screen.findByText(/no active employees in this country/i)).toBeInTheDocument()
  })

  it('shows an error when the country request fails', async () => {
    server.use(http.get('/api/insights/country/:code', () => HttpResponse.json({ detail: 'Unknown country code' }, { status: 404 })))
    renderApp(<InsightsPage />, { role: 'viewer' })
    await pickCountry(/United States/)
    expect(await screen.findByText(/unknown country code/i)).toBeInTheDocument()
  })
})
