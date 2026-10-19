export function formatCurrency(amount: number | null | undefined, currency: string): string {
  if (amount === null || amount === undefined) return '-'
  return new Intl.NumberFormat('en-US', { style: 'currency', currency, maximumFractionDigits: 2 }).format(amount)
}

export function formatNumber(value: number): string {
  return new Intl.NumberFormat('en-US').format(value)
}

export function formatPercent(fraction: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'percent',
    maximumFractionDigits: 1,
    signDisplay: 'exceptZero',
  }).format(fraction)
}

const LABELS: Record<string, string> = {
  full_time: 'Full time',
  part_time: 'Part time',
  contract: 'Contract',
  active: 'Active',
  terminated: 'Terminated',
  admin: 'Admin',
  hr_manager: 'HR manager',
  viewer: 'Viewer',
}

export const label = (value: string): string => LABELS[value] ?? value
