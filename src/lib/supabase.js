// src/lib/supabase.js
import { createClient } from '@supabase/supabase-js'

const SUPABASE_URL = (import.meta.env.VITE_SUPABASE_URL || '').trim()
const SUPABASE_ANON = (import.meta.env.VITE_SUPABASE_ANON_KEY || '').trim()

// Resuelve un API_BASE_URL SIEMPRE absoluto (sin slash final).
// - Si VITE_API_BASE_URL es absoluto → lo normaliza.
// - Si es relativo (p.ej. "/api") o vacío → usa window.location.origin + "/api".
// - En SSR o sin window → fallback local http://127.0.0.1:8000/api
function resolveApiBase() {
  const env = (import.meta.env.VITE_API_BASE_URL || '').trim()

  // Intentar con el env tal cual (acepta absoluto o relativo respecto al origin del browser)
  if (env) {
    try {
      const base =
        typeof window !== 'undefined' ? new URL(env, window.location.origin) : new URL(env) // si es absoluto, también funciona en SSR
      base.pathname = base.pathname.replace(/\/+$/, '') // sin slash final
      return base.toString()
    } catch {
      // sigue a fallback
    }
  }

  // Fallback: mismo host del front + "/api"
  if (typeof window !== 'undefined') {
    const fallback = new URL('/api', window.location.origin)
    fallback.pathname = fallback.pathname.replace(/\/+$/, '')
    return fallback.toString()
  }

  // Último recurso en SSR
  return 'http://127.0.0.1:8000/api'
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
