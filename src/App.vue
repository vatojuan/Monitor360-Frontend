<!-- src/App.vue -->
<script setup>
import { ref, reactive, onMounted, onBeforeUnmount, computed } from 'vue'
import { RouterView, useRoute, useRouter } from 'vue-router'
import { supabase } from '@/lib/supabase'
import logo from '@/assets/logo.svg'

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

const liveTooltip = computed(() => {
  const parts = []
  parts.push(live.connected ? 'WS: conectado' : 'WS: reconectando')
  if (live.lastMsgIso) parts.push(`última: ${new Date(live.lastMsgIso).toLocaleString()}`)
  return parts.join(' · ')
})

// Permite pausar/reanudar el tiempo real desde la barra
const realtimeEnabled = ref(true)

let wsStateTimer = null
let offWsListener = null
let offAuthSub = null

async function getSession() {
  const { data } = await supabase.auth.getSession()
  session.value = data.session
  userEmail.value = data.session?.user?.email || ''
}

async function logout() {
  try {
    await supabase.auth.signOut()
  } catch (err) {
    if (import.meta?.env?.DEV) console.warn('[auth] signOut error:', err?.message || err)
  }
  session.value = null
  userEmail.value = ''
  router.push('/login')
}

// ===== Uptime para Topbar =====
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
  uptimeTimer = setInterval(() => (uptime.value = fmt(Date.now() - start)), 1000)
}
function stopUptime() {
  if (uptimeTimer) {
    clearInterval(uptimeTimer)
    uptimeTimer = null
  }
}

// ===== WS helpers =====
function startWsStatePolling() {
  stopWsStatePolling()
  wsStateTimer = setInterval(() => {
    try {
      const ws = getCurrentWebSocket()
      live.connected = ws?.readyState === WebSocket.OPEN
    } catch (err) {
      live.connected = false
      if (import.meta?.env?.DEV) {
        console.debug('[WS] state poll error:', err?.message || err)
      }
    }
  }, 1500)
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
    } catch (err) {
      if (import.meta?.env?.DEV) console.debug('[WS] offWsListener error:', err?.message || err)
    }
    offWsListener = null
  }
}

// Encendido de “Tiempo real”
async function startRealtime() {
  realtimeEnabled.value = true
  try {
    await connectWebSocketWhenAuthenticated()
  } catch (err) {
    if (import.meta?.env?.DEV) {
      console.warn('[WS] connectWhenAuthenticated falló (continuamos):', err?.message || err)
    }
  }
  attachWsListener()
  startWsStatePolling()
}

// Pausa de “Tiempo real”
function stopRealtime() {
  realtimeEnabled.value = false
  detachWsListener()
  stopWsStatePolling()
  try {
    const ws = getCurrentWebSocket()
    if (ws && ws.readyState === WebSocket.OPEN) ws.close(1000, 'paused-by-user')
  } catch (err) {
    if (import.meta?.env?.DEV) console.debug('[WS] close error:', err?.message || err)
  }
  live.connected = false
}

function onToggleRealtime() {
  if (realtimeEnabled.value) stopRealtime()
  else startRealtime()
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
    } catch (err) {
      if (import.meta?.env?.DEV) console.debug('[auth] unsubscribe error:', err?.message || err)
    }
  }

  // Arranque general
  startUptime()
  await startRealtime()
})

onBeforeUnmount(() => {
  try {
    if (typeof offAuthSub === 'function') offAuthSub()
  } catch (err) {
    if (import.meta?.env?.DEV) console.debug('[auth] offAuthSub error:', err?.message || err)
  }
  stopRealtime()
  stopUptime()
})
</script>

<template>
  <div id="app-layout">
    <!-- Topbar Pro (oculta en rutas con meta.hideChrome) -->
    <TopbarPro
      v-if="!hideChrome"
      :realtime="realtimeEnabled"
      :uptime="uptime"
      :userEmail="userEmail"
      :logoSrc="logo"
      @toggleRealtime="onToggleRealtime"
      @toggleSidebar="null /* integrar si habilitas sidebar */"
      @logout="logout"
    />

    <!-- Contenido -->
    <main class="main-content" :title="!hideChrome ? liveTooltip : null">
      <RouterView />
    </main>
  </div>
</template>

<style>
:root {
  /* Base para el efecto glass del Topbar */
  --m360-bg: #0b1220;

  /* Paleta existente */
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

/* Contenido; TopbarPro ya es sticky (44px). */
.main-content {
  width: 100%;
  padding: 16px;
  flex-grow: 1;
}

/* Responsivo mínimo para el contenido */
@media (max-width: 480px) {
  .main-content {
    padding: 12px;
  }
}
</style>
