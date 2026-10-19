import { describe, expect, it } from 'vitest'
import { formatCurrency, formatNumber, formatPercent, label } from './format'

describe('formatCurrency', () => {
  it('formats using the employee currency, not a global one', () => {
    expect(formatCurrency(95000, 'USD')).toBe('$95,000.00')
    expect(formatCurrency(185000.5, 'BRL')).toContain('185,000.50')
    expect(formatCurrency(185000.5, 'BRL')).toContain('R$')
    expect(formatCurrency(80000, 'EUR')).toContain('€')
    expect(formatCurrency(80000, 'GBP')).toContain('£')
  })

  it('never renders different currencies identically', () => {
    expect(formatCurrency(1000, 'USD')).not.toBe(formatCurrency(1000, 'INR'))
  })

  it('shows a dash for missing values', () => {
    expect(formatCurrency(null, 'USD')).toBe('-')
    expect(formatCurrency(undefined, 'USD')).toBe('-')
  })

  it('keeps zero and rounds to two decimals', () => {
    expect(formatCurrency(0, 'USD')).toBe('$0.00')
    expect(formatCurrency(1234.567, 'USD')).toBe('$1,234.57')
  })
})

describe('other formatters', () => {
  it('groups thousands', () => expect(formatNumber(10000)).toBe('10,000'))
  it('formats signed percentages', () => {
    expect(formatPercent(0.6)).toBe('+60%')
    expect(formatPercent(-0.5)).toBe('-50%')
    expect(formatPercent(0)).toBe('0%')
  })
  it('humanises enum values and passes unknown ones through', () => {
    expect(label('full_time')).toBe('Full time')
    expect(label('hr_manager')).toBe('HR manager')
    expect(label('mystery')).toBe('mystery')
  })
})
