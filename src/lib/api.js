import axios from 'axios'
import { API_BASE_URL, supabase } from './supabase'

function ensureApiBase(url) {
  const u = (url || 'http://127.0.0.1:8000').trim().replace(/\/+$/, '')
  return /\/api$/i.test(u) ? u : `${u}/api`
}

const api = axios.create({
  baseURL: ensureApiBase(API_BASE_URL),
  timeout: 20000,
})

// 👇 sincronizar token aquí
supabase.auth.onAuthStateChange((_event, session) => {
  if (session?.access_token) {
    api.defaults.headers.common['Authorization'] = `Bearer ${session.access_token}`
    if (import.meta.env.DEV) {
      console.debug('[supabase] Refrescado access_token')
    }
  } else {
    delete api.defaults.headers.common['Authorization']
  }
})

api.interceptors.request.use(
  async (config) => {
    config.headers = config.headers || {}
    if (!config.headers.Accept) {
      config.headers.Accept = 'application/json'
    }
    return config
  },
  (error) => Promise.reject(error),
)

api.interceptors.response.use(
  (res) => res,
  async (error) => {
    const { response } = error || {}
    if (response?.status === 401 && import.meta.env.DEV) {
      console.debug('[api] 401 Unauthorized - probablemente token expirado')
    }
    return Promise.reject(error)
  },
)

export default api
