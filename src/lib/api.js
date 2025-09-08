// src/lib/api.js
import axios from 'axios'
import { API_BASE_URL } from './supabase'

/**
 * Normaliza la base del backend:
 * - Acepta con o sin /api
 * - Evita dobles barras
 */
function ensureApiBase(url) {
  const u = (url || 'http://127.0.0.1:8000').trim().replace(/\/+$/, '')
  return /\/api$/i.test(u) ? u : `${u}/api`
}

const api = axios.create({
  baseURL: ensureApiBase(API_BASE_URL),
  timeout: 20000,
})

/**
 * REQUEST INTERCEPTOR
 * - Asegura que siempre haya Accept: application/json
 * - El header Authorization ya se setea en supabase.js con onAuthStateChange
 */
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

/**
 * RESPONSE INTERCEPTOR
 * - Si 401, simplemente rechaza (supabase.js actualizará el token automáticamente)
 */
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
