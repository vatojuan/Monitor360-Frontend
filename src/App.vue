<!-- src/App.vue -->
<script setup>
import { ref, reactive, onMounted, onBeforeUnmount, computed } from 'vue'
import { RouterView, useRoute, useRouter } from 'vue-router'
import { supabase } from '@/lib/supabase'
import TopbarPro from '@/components/TopbarPro.vue'
import { connectWebSocketWhenAuthenticated, addWsListener, getCurrentWebSocket } from '@/lib/ws'

const route = useRoute()
const router = useRouter()

// ===== Auth/session =====
const session = ref(null)
const userEmail = ref('')

// Ocultar chrome en rutas que lo pidan
const hideChrome = computed(() => route.meta?.hideChrome === true)

// ===== Estado de tiempo real / WS =====
const live = reactive({
  connected: false,
  lastMsgIso: null,
})

// Uptime (para TopbarPro)
const uptime = ref('00:00:00')
let uptimeTimer = null
const fmt = (ms) => {
  const s = Math.floor(ms / 1000)
  const hh = String(Math.floor(s / 3600)).padStart(2, '0')
  const mm = String(Math.floor((s % 3600) / 60)).padStart(2, '0')
  const ss = String(s % 60).padStart(2, '0')
  return `${hh}:${mm}:${ss}`
}
function startUptime() {
  const start = Date.now()
  stopUptime()
  uptimeTimer = setInterval(() => {
    uptime.value = fmt(Date.now() - start)
  }, 1000)
}
function stopUptime() {
  if (uptimeTimer) {
    clearInterval(uptimeTimer)
    uptimeTimer = null
  }
}

// ===== WS helpers =====
let wsStateTimer = null
let offWsListener = null
let offAuthSub = null

async function getSession() {
  const { data } = await supabase.auth.getSession()
  session.value = data.session
  userEmail.value = data.session?.user?.email || ''
}

async function onLogout() {
  try {
    await supabase.auth.signOut()
  } catch (e) {
    if (import.meta?.env?.DEV) console.warn('[auth] signOut error:', e?.message || e)
  }
  session.value = null
  userEmail.value = ''
  router.push('/login')
}

function startWsStatePolling() {
  stopWsStatePolling()
  wsStateTimer = setInterval(() => {
    try {
      const ws = getCurrentWebSocket()
      live.connected = ws?.readyState === WebSocket.OPEN
    } catch (e) {
      if (import.meta?.env?.DEV) console.debug('[WS] state poll error:', e?.message || e)
      live.connected = false
    }
  }, 1200)
}
function stopWsStatePolling() {
  if (wsStateTimer) {
    clearInterval(wsStateTimer)
    wsStateTimer = null
  }
}

function attachWsListener() {
  detachWsListener()
  offWsListener = addWsListener((msg) => {
    if (!msg || typeof msg !== 'object') return
    const ts = (typeof msg.timestamp === 'string' && msg.timestamp) || new Date().toISOString()
    live.lastMsgIso = ts
  })
}
function detachWsListener() {
  if (typeof offWsListener === 'function') {
    try {
      offWsListener()
    } catch (e) {
      if (import.meta?.env?.DEV) console.debug('[WS] offWsListener error:', e?.message || e)
    }
    offWsListener = null
  }
}

async function ensureRealtime() {
  try {
    await connectWebSocketWhenAuthenticated()
  } catch (e) {
    if (import.meta?.env?.DEV) {
      console.warn('[WS] connectWhenAuthenticated falló (continuamos):', e?.message || e)
    }
  }
  attachWsListener()
  startWsStatePolling()
}

onMounted(async () => {
  await getSession()

  // Suscripción a cambios de sesión
  const { data: sub } = supabase.auth.onAuthStateChange(async (_event, s) => {
    session.value = s
    userEmail.value = s?.user?.email || ''
  })
  offAuthSub = () => {
    try {
      sub?.subscription?.unsubscribe()
    } catch (e) {
      if (import.meta?.env?.DEV) console.debug('[auth] unsubscribe error:', e?.message || e)
    }
  }

  startUptime()
  await ensureRealtime()
})

onBeforeUnmount(() => {
  try {
    if (typeof offAuthSub === 'function') offAuthSub()
  } catch (e) {
    if (import.meta?.env?.DEV) console.debug('[auth] offAuthSub error:', e?.message || e)
  }
  detachWsListener()
  stopWsStatePolling()
  try {
    const ws = getCurrentWebSocket()
    if (ws && ws.readyState === WebSocket.OPEN) ws.close(1000, 'app-unmount')
  } catch (e) {
    if (import.meta?.env?.DEV) console.debug('[WS] close error:', e?.message || e)
  }
  stopUptime()
})
</script>

<template>
  <div id="app-layout">
    <!-- Topbar Pro (oculta en páginas con meta.hideChrome) -->
    <TopbarPro
      v-if="!hideChrome"
      :realtime="live.connected"
      :uptime="uptime"
      :userEmail="userEmail"
      @logout="onLogout"
    />

    <!-- Contenido -->
    <main class="main-content">
      <RouterView />
    </main>
  </div>
</template>

<style>
:root {
  --m360-bg: #0b1220; /* base del efecto glass del Topbar */
  --bg-color: #1a1a2e;
  --surface-color: #16213e;
  --primary-color: #0f3460;
  --secondary-color: #e94560;
  --font-color: #e0e0e0;
  --green: #3ddc84;
  --gray: #8d8d8d;
  --blue: #5372f0;
  --error-red: #f87171;
}

*,
*::before,
*::after {
  box-sizing: border-box;
}

html,
body,
#app {
  height: 100%;
}

body {
  margin: 0;
  background-color: var(--bg-color);
  color: var(--font-color);
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

#app-layout {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
}

/* TopbarPro es sticky; padding sobrio en contenido */
.main-content {
  width: 100%;
  padding: 16px;
  flex-grow: 1;
}

@media (max-width: 480px) {
  .main-content {
    padding: 12px;
  }
}
</style>
