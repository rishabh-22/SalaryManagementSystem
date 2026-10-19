// Single-hue palette: every chart here encodes one measure, so colour carries no category meaning.
export const CHART_COLOR = '#1f6fb5'
export const CHART_COLOR_ACCENT = '#c2410c'

/** Compact axis tick, e.g. 95000 -> 95K. Currency is stated in the chart title, not repeated per tick. */
export const compactNumber = (n: number): string =>
  new Intl.NumberFormat('en-US', { notation: 'compact', maximumFractionDigits: 1 }).format(n)
