// src/lib/supabase.js
import { createClient } from '@supabase/supabase-js'
import api from './api' // 👈 importa tu cliente Axios

// ─────────────────────────────────────────────────────────────────────────────
// ENV de Vite (frontend)
// Asegurate de definir en .env (o .env.local):
//   VITE_SUPABASE_URL=https://<tu-ref>.supabase.co
//   VITE_SUPABASE_ANON_KEY=<tu anon key>
//   VITE_API_BASE_URL=http://127.0.0.1:8000/api   (en prod, tu dominio real)
// ─────────────────────────────────────────────────────────────────────────────
const SUPABASE_URL = (import.meta.env.VITE_SUPABASE_URL || '').trim()
const SUPABASE_ANON = (import.meta.env.VITE_SUPABASE_ANON_KEY || '').trim()

// URL base del backend; puede venir con o sin /api (lo normalizamos en api.js)
export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000').trim()

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

/**
 * Retorna { data, error } (compat con router.guard y demás)
 * data.session es null si no hay sesión
 */
export function getSession() {
  return supabase.auth.getSession()
}

/** Access token actual o null */
export async function getAccessToken() {
  const { data } = await supabase.auth.getSession()
  return data?.session?.access_token ?? null
}

/**
 * Espera a que exista sesión hasta timeoutMs.
 * - Si requireAuth=true y no aparece, lanza Error.
 * - Devuelve el access_token (string) o null si requireAuth=false.
 */
export async function waitForSession({ timeoutMs = 8000, requireAuth = false } = {}) {
  const start = Date.now()
  while (Date.now() - start < timeoutMs) {
    const { data } = await supabase.auth.getSession()
    const token = data?.session?.access_token
    if (token) return token
    // pequeño backoff para no saturar
    await new Promise((r) => setTimeout(r, 200))
  }
  if (requireAuth) throw new Error('No hay sesión de Supabase.')
  return null
}

/** Reexport simple por si querés suscribirte a cambios de auth desde otros módulos */
export function onAuthStateChange(cb) {
  return supabase.auth.onAuthStateChange(cb)
}

// 👇 NUEVO: mantener Axios sincronizado con Supabase
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
