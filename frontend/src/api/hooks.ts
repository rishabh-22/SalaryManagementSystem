import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from './client'
import { qk } from './queryKeys'
import type {
  ChatMessage,
  ChatResponse,
  CountryInsights,
  Distribution,
  Employee,
  EmployeeCreate,
  EmployeeFilters,
  EmployeeListParams,
  EmployeeUpdate,
  Meta,
  Outliers,
  Overview,
  Page,
  SalaryChange,
  TokenResponse,
  User,
  UserCreate,
  UserUpdate,
} from './types'

export async function login(email: string, password: string): Promise<TokenResponse> {
  const body = new URLSearchParams({ username: email, password })
  const { data } = await api.post<TokenResponse>('/auth/login', body, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  })
  return data
}

export async function fetchMe(): Promise<User> {
  const { data } = await api.get<User>('/auth/me')
  return data
}

export const useMeta = () =>
  useQuery({
    queryKey: qk.meta,
    queryFn: async () => (await api.get<Meta>('/meta')).data,
    staleTime: Infinity,
  })

export const useChat = () =>
  useMutation({
    mutationFn: async (messages: ChatMessage[]) =>
      (await api.post<ChatResponse>('/chat', { messages })).data,
  })

// ---- employees
export const useEmployees = (params: EmployeeListParams) =>
  useQuery({
    queryKey: qk.employeeList(params),
    queryFn: async () => (await api.get<Page<Employee>>('/employees', { params })).data,
    placeholderData: keepPreviousData,
  })

export const useEmployee = (id: number) =>
  useQuery({
    queryKey: qk.employee(id),
    queryFn: async () => (await api.get<Employee>(`/employees/${id}`)).data,
    enabled: Number.isFinite(id),
    retry: false,
  })

export const useSalaryHistory = (id: number) =>
  useQuery({
    queryKey: qk.salaryHistory(id),
    queryFn: async () => (await api.get<SalaryChange[]>(`/employees/${id}/salary-history`)).data,
    enabled: Number.isFinite(id),
  })

export const useCreateEmployee = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body: EmployeeCreate) => (await api.post<Employee>('/employees', body)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.employees }),
  })
}

// Employee edits can change headcount/salary insights, so both caches are refreshed.
function useEmployeeMutation<TVars>(mutationFn: (vars: TVars) => Promise<Employee>) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn,
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: qk.employees })
      void qc.invalidateQueries({ queryKey: qk.insights })
    },
  })
}

export const useUpdateEmployee = (id: number) =>
  useEmployeeMutation(async (body: EmployeeUpdate) => (await api.patch<Employee>(`/employees/${id}`, body)).data)

export const useTerminateEmployee = (id: number) =>
  useEmployeeMutation<void>(async () => (await api.delete<Employee>(`/employees/${id}`)).data)

export async function downloadEmployeesCsv(filters: EmployeeFilters, sort?: string): Promise<void> {
  const { data } = await api.get<Blob>('/employees/export.csv', {
    params: { ...filters, sort },
    responseType: 'blob',
  })
  const url = URL.createObjectURL(data)
  const link = document.createElement('a')
  link.href = url
  link.download = 'employees.csv'
  link.click()
  URL.revokeObjectURL(url)
}

// ---- insights
export const useOverview = () =>
  useQuery({
    queryKey: qk.overview,
    queryFn: async () => (await api.get<Overview>('/insights/overview')).data,
  })

export const useCountryInsights = (code: string | null) =>
  useQuery({
    queryKey: qk.country(code ?? ''),
    queryFn: async () => (await api.get<CountryInsights>(`/insights/country/${code}`)).data,
    enabled: !!code,
  })

export const useDistribution = (code: string | null, bins = 10) =>
  useQuery({
    queryKey: qk.distribution(code ?? '', bins),
    queryFn: async () =>
      (await api.get<Distribution>(`/insights/country/${code}/distribution`, { params: { bins } })).data,
    enabled: !!code,
  })

export const useOutliers = (code: string | null, threshold = 0.3) =>
  useQuery({
    queryKey: qk.outliers(code ?? '', threshold),
    queryFn: async () =>
      (await api.get<Outliers>(`/insights/country/${code}/outliers`, { params: { threshold, limit: 50 } })).data,
    enabled: !!code,
  })

// ---- users
export const useUsers = () =>
  useQuery({
    queryKey: qk.users,
    queryFn: async () => (await api.get<User[]>('/users')).data,
  })

export const useCreateUser = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body: UserCreate) => (await api.post<User>('/users', body)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.users }),
  })
}

export const useUpdateUser = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, body }: { id: number; body: UserUpdate }) =>
      (await api.patch<User>(`/users/${id}`, body)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.users }),
  })
}

export const useDeleteUser = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id: number) => {
      await api.delete(`/users/${id}`)
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.users }),
  })
}
