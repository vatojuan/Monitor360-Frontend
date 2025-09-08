import { createClient } from '@supabase/supabase-js'

const SUPABASE_URL = (import.meta.env.VITE_SUPABASE_URL || '').trim()
const SUPABASE_ANON = (import.meta.env.VITE_SUPABASE_ANON_KEY || '').trim()

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
