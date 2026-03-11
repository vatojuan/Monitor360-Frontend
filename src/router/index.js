// src/router/index.js
import { createRouter, createWebHistory } from 'vue-router'
import DashboardView from '../views/DashboardView.vue'
import MonitorBuilderView from '../views/MonitorBuilderView.vue'
import ManageDeviceView from '../views/ManageDeviceView.vue'
import CredentialsView from '../views/CredentialsView.vue'
import MonitorDetailView from '../views/MonitorDetailView.vue'
import ChannelsView from '../views/ChannelsView.vue'
import VpnsView from '../views/VpnsView.vue'
import ScanView from '../views/ScanView.vue'
import LoginView from '../views/LoginView.vue'
import ReportsView from '../views/ReportsView.vue'
import BillingView from '../views/BillingView.vue'
// ✅ IMPORTACIONES PARA LEGALES
import TermsView from '../views/TermsView.vue'
import PrivacyView from '../views/PrivacyView.vue'

// ✅ IMPORTANTE: Agregamos "supabase" a la importación para poder consultar la base de datos
import { getSession, supabase } from '@/lib/supabase'

const routes = [
  // Login oculta el chrome
  { path: '/login', name: 'login', component: LoginView, meta: { hideChrome: true } },

  // RUTAS PÚBLICAS
  { 
    path: '/terms', 
    name: 'terms', 
    component: TermsView, 
    meta: { hideChrome: true } 
  },
  { 
    path: '/privacy', 
    name: 'privacy', 
    component: PrivacyView, 
    meta: { hideChrome: true } 
  },

  { path: '/', name: 'dashboard', component: DashboardView, meta: { requiresAuth: true } },
  {
    path: '/monitor-builder',
    name: 'monitor-builder',
    component: MonitorBuilderView,
    meta: { requiresAuth: true },
  },
  {
    path: '/devices',
    name: 'manage-devices',
    component: ManageDeviceView,
    meta: { requiresAuth: true },
  },
  {
    path: '/credentials',
    name: 'credentials',
    component: CredentialsView,
    meta: { requiresAuth: true },
  },
  {
    path: '/sensor/:id',
    name: 'sensor-detail',
    component: MonitorDetailView,
    meta: { requiresAuth: true },
  },
  { path: '/channels', name: 'channels', component: ChannelsView, meta: { requiresAuth: true } },
  { path: '/vpns', name: 'vpns', component: VpnsView, meta: { requiresAuth: true } },
  
  // Ruta de Reportes IA
  { 
    path: '/reports', 
    name: 'reports', 
    component: ReportsView, 
    meta: { requiresAuth: true } 
  },

  // Ruta de escáner interna
  {
    path: '/scan',
    name: 'scan',
    component: ScanView,
    meta: { requiresAuth: true },
  },

  // Ruta del panel de suscripciones/pagos
  {
    path: '/billing',
    name: 'billing',
    component: BillingView,
    meta: { requiresAuth: true },
  },

  // Fallback
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
  scrollBehavior() {
    return { top: 0 }
  },
})

async function waitSupabaseWarmup(ms = 0) {
  if (ms > 0) await new Promise((r) => setTimeout(r, ms))
}

router.beforeEach(async (to) => {
  await waitSupabaseWarmup(0)

  const { data: sessionData } = await getSession()
  const hasSession = !!sessionData?.session

  // 1. Si ya estoy logueado e intento ir a /login → redirigir a destino (o /)
  if (to.name === 'login' && hasSession) {
    const dest =
      typeof to.query.redirect === 'string' && to.query.redirect ? to.query.redirect : '/'
    if (to.fullPath === dest) return true
    return { path: dest }
  }

  // 2. Si la ruta requiere auth y no hay sesión → mandar a login
  if (to.meta?.requiresAuth && !hasSession) {
    if (to.name === 'login') return true
    return { name: 'login', query: { redirect: to.fullPath } }
  }

  // 3. 🔒 EL PAYWALL TOTAL 🔒
  // Si tiene sesión, va a una ruta protegida y NO es la página de billing...
  if (to.meta?.requiresAuth && hasSession && to.name !== 'billing') {
    try {
      // Buscamos su suscripción actual en la base de datos
      const { data: sub, error } = await supabase
        .from('subscriptions')
        .select('plan_id, status')
        .eq('owner_id', sessionData.session.user.id)
        .single()

      if (error && error.code !== 'PGRST116') {
        console.error('[Router] Error validando plan:', error)
      }

      // Definimos si tiene acceso total (Es PRO y está Activo)
      const isPro = sub && sub.plan_id !== 'free' && sub.status === 'active'

      // Si no es PRO, lo pateamos a la pantalla de pago
      if (!isPro) {
        return { name: 'billing' }
      }
    } catch (err) {
      console.error('[Paywall] Falla en la validación:', err)
      // Por seguridad extrema ante un error, redirigimos a pagar
      return { name: 'billing' }
    }
  }

  return true
})

export default router