import axios, { AxiosError } from 'axios'

const TOKEN_KEY = 'acme_token'

export const tokenStore = {
  get: (): string | null => localStorage.getItem(TOKEN_KEY),
  set: (token: string) => localStorage.setItem(TOKEN_KEY, token),
  clear: () => localStorage.removeItem(TOKEN_KEY),
}

export const api = axios.create({ baseURL: '/api' })

api.interceptors.request.use((config) => {
  const token = tokenStore.get()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    // A 401 from the login call itself just means bad credentials.
    const isLoginCall = error.config?.url?.includes('/auth/login')
    if (error.response?.status === 401 && !isLoginCall) {
      tokenStore.clear()
      if (window.location.pathname !== '/login') window.location.assign('/login')
    }
    return Promise.reject(error)
  },
)

interface ValidationItem {
  loc: (string | number)[]
  msg: string
}

type ErrorBody = { detail?: string | ValidationItem[] } | undefined

/** Turns any API failure into one human-readable message. */
export function errorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    if (!error.response) return 'Cannot reach the server. Please try again.'
    const detail = (error.response.data as ErrorBody)?.detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) {
      return detail.map((d) => `${d.loc.filter((p) => p !== 'body').join('.')}: ${d.msg}`).join('; ')
    }
    return `Request failed (${error.response.status})`
  }
  return error instanceof Error ? error.message : 'Unexpected error'
}

/** Field-level messages for a 422, keyed by the last loc segment. */
export function fieldErrors(error: unknown): Record<string, string> {
  const out: Record<string, string> = {}
  if (axios.isAxiosError(error) && error.response?.status === 422) {
    const detail = (error.response.data as ErrorBody)?.detail
    if (Array.isArray(detail)) {
      for (const d of detail) out[String(d.loc[d.loc.length - 1])] = d.msg
    }
  }
  return out
}

export function httpStatus(error: unknown): number | undefined {
  return axios.isAxiosError(error) ? error.response?.status : undefined
}
