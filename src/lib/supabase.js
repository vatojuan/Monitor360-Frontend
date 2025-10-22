// src/lib/supabase.js
import { createClient } from '@supabase/supabase-js'

const SUPABASE_URL = (import.meta.env.VITE_SUPABASE_URL || '').trim()
const SUPABASE_ANON = (import.meta.env.VITE_SUPABASE_ANON_KEY || '').trim()

/**
 * Resuelve la base del API:
 * - Si VITE_API_BASE_URL es absoluta (http/https), se usa tal cual.
 * - Si es relativa (ej. "/api"), se resuelve contra el origin actual.
 * - Si no existe, por defecto usa mismo origin + "/api" en navegador,
 *   o "http://127.0.0.1:8000" en contextos sin window (SSR/scripts).
 */
function resolveApiBase() {
  const raw = (import.meta.env.VITE_API_BASE_URL || '').trim()
  if (raw) {
    // Absoluta
    if (/^https?:\/\//i.test(raw)) {
      return raw.replace(/\/+$/, '')
    }
    // Relativa o ruta corta → resuelve contra el origin
    const origin =
      typeof window !== 'undefined' && window.location?.origin
        ? window.location.origin
        : 'http://127.0.0.1:5173'
    const url = new URL(raw.startsWith('/') ? raw : `/${raw}`, origin)
    return url.toString().replace(/\/+$/, '')
  }

  // Sin variable: usa mismo origin + /api si hay window
  if (typeof window !== 'undefined' && window.location?.origin) {
    return new URL('/api', window.location.origin).toString().replace(/\/+$/, '')
  }

  // Fallback para entornos sin window (scripts/SSR)
  return 'http://127.0.0.1:8000'
}

export const API_BASE_URL = resolveApiBase()

if (!SUPABASE_URL || !SUPABASE_ANON) {
  throw new Error('❌ Falta VITE_SUPABASE_URL o VITE_SUPABASE_ANON_KEY en el front.')
}

export const supabase = createClient(SUPABASE_URL, SUPABASE_ANON, {
  auth: {
    persistSession: true,
    autoRefreshToken: true,
    detectSessionInUrl: true,
  },
})

export function getSession() {
  return supabase.auth.getSession()
}

export async function getAccessToken() {
  const { data } = await supabase.auth.getSession()
  return data?.session?.access_token ?? null
}

/**
 * Espera hasta obtener un token de sesión (útil antes de abrir el WS).
 * @param {object} opts
 * @param {number} opts.timeoutMs Tiempo máx. en ms (default 8000)
 * @param {boolean} opts.requireAuth Si true, lanza error si no hay sesión
 * @returns {Promise<string|null>} access_token o null
 */
export async function waitForSession({ timeoutMs = 8000, requireAuth = false } = {}) {
  const start = Date.now()
  while (Date.now() - start < timeoutMs) {
    const { data } = await supabase.auth.getSession()
    const token = data?.session?.access_token
    if (token) return token
    await new Promise((r) => setTimeout(r, 200))
  }
  if (requireAuth) throw new Error('No hay sesión de Supabase.')
  return null
}

export function onAuthStateChange(cb) {
  return supabase.auth.onAuthStateChange(cb)
}
