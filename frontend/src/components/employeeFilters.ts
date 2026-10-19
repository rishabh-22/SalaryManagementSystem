export interface FilterState {
  q: string
  country: string
  department: string
  job_title: string
  status: string
}

export const emptyFilters: FilterState = { q: '', country: '', department: '', job_title: '', status: '' }
