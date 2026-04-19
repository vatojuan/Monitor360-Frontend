<template>
  <header :class="['m360-topbar', isHidden ? 'm360-topbar--hidden' : '']">
    <div class="m360-left">
      <button class="m360-iconbtn" @click="emit('toggleSidebar')" aria-label="Abrir menú">
        <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor">
          <path d="M3 6h18M3 12h18M3 18h18" />
        </svg>
      </button>

      <router-link to="/" class="m360-brand" aria-label="MonitorWISP">
        <template v-if="showImg">
          <img :src="currentLogo" alt="MonitorWISP" @error="handleImgError" />
        </template>
        <template v-else>
          <svg width="22" height="22" viewBox="0 0 24 24" aria-hidden="true">
            <defs>
              <linearGradient id="g" x1="0" x2="1" y1="0" y2="1">
                <stop offset="0" stop-color="#6AB4FF" />
                <stop offset="1" stop-color="#2B68FF" />
              </linearGradient>
            </defs>
            <rect x="2" y="2" width="20" height="20" rx="4" fill="url(#g)" />
            <path
              d="M7 12h10M9 9l3 6 3-6"
              stroke="#0b1220"
              stroke-width="1.8"
              stroke-linecap="round"
              stroke-linejoin="round"
            />
          </svg>
        </template>
        <span class="m360-brand-text">MonitorWISP</span>
      </router-link>

      <span class="m360-crumb" v-if="breadcrumb">{{ breadcrumb }}</span>
    </div>

    <div class="m360-center" />

    <div class="m360-right">
      <span class="m360-chip" :class="realtime ? 'is-on' : 'is-off'" aria-hidden="true">
        <span class="dot" />
        <span class="label">{{ realtime ? 'Tiempo real' : 'Reconectando…' }}</span>
      </span>

      <div class="m360-menu" ref="notifRef">
        <button class="m360-iconbtn" @click="toggleNotifications" aria-label="Notificaciones">
          <svg
            viewBox="0 0 24 24"
            width="20"
            height="20"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"></path>
            <path d="M13.73 21a2 2 0 0 1-3.46 0"></path>
          </svg>
          <span v-if="totalBadgeCount > 0" class="m360-badge">{{ totalBadgeCount }}</span>
        </button>

        <div v-if="showNotif" class="m360-pop notif-pop" role="menu">
          
          <div class="notif-tabs">
            <button 
              :class="['notif-tab', activeNotifTab === 'devices' ? 'active' : '']"
              @click="activeNotifTab = 'devices'"
            >
              Dispositivos ({{ notifications.length }})
            </button>
            <button 
              :class="['notif-tab', activeNotifTab === 'system' ? 'active' : '']"
              @click="activeNotifTab = 'system'"
            >
              Avisos ({{ sysNotifications.length }})
            </button>
          </div>

          <div v-if="activeNotifTab === 'devices'">
             <div v-if="notifications.length === 0" class="notif-empty">No hay dispositivos nuevos.</div>
             <div v-else class="notif-list">
                <div v-for="notif in notifications" :key="notif.mac_address" class="notif-item">
                  <div class="notif-info">
                    <div class="notif-top">
                      <span class="notif-vendor">{{ notif.vendor || 'Dispositivo' }}</span>
                      <span class="notif-ip">{{ notif.ip_address }}</span>
                    </div>
                    <span class="notif-mac">{{ notif.mac_address }}</span>
                  </div>
                  <div class="notif-actions">
                    <button @click="quickAdopt(notif)" class="btn-icon-action adopt" title="Adoptar">✔</button>
                    <button @click="quickDismiss(notif)" class="btn-icon-action dismiss" title="Ignorar">✕</button>
                  </div>
                </div>
             </div>
             <router-link to="/scan" class="notif-footer" @click="showNotif = false">
                Ir al Escáner Avanzado
             </router-link>
          </div>

          <div v-if="activeNotifTab === 'system'">
             <div class="notif-header-actions" v-if="sysNotifications.length > 0">
                <button @click="markAllRead" class="btn-text-small">Marcar todo leído</button>
             </div>
             <div v-if="sysNotifications.length === 0" class="notif-empty">Sin avisos recientes.</div>
             <div v-else class="notif-list">
                <div v-for="sys in sysNotifications" :key="sys.id" :class="['sys-item', sys.type]">
                   <div class="sys-content">
                      <span class="sys-title">{{ sys.title }}</span>
                      <span class="sys-msg">{{ sys.message }}</span>
                      
                      <button
                        v-if="getAdoptedDevices(sys).length > 0"
                        @click.stop="openDetails(getAdoptedDevices(sys), 'Dispositivos adoptados con éxito', 'success')"
                        class="btn-text-small view-details-btn success"
                      >
                        Ver adoptados ({{ getAdoptedDevices(sys).length }})
                      </button>

                      <button
                        v-if="getFailedDevices(sys).length > 0"
                        @click.stop="openDetails(getFailedDevices(sys), 'Detalles de fallo', 'error')"
                        class="btn-text-small view-details-btn"
                      >
                        Ver detalles de fallo ({{ getFailedDevices(sys).length }})
                      </button>

                      <span class="sys-time">{{ formatTime(sys.created_at) }}</span>
                   </div>
                   </div>
             </div>
          </div>

        </div>
      </div>

      <div class="m360-menu" ref="menuRef" @keydown.esc.prevent.stop="closeMenu">
        <button
          class="m360-iconbtn"
          @click="menu = !menu"
          aria-haspopup="menu"
          :aria-expanded="menu"
          aria-label="Abrir menú rápido"
        >
          <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor">
            <circle cx="5" cy="12" r="2" />
            <circle cx="12" cy="12" r="2" />
            <circle cx="19" cy="12" r="2" />
          </svg>
        </button>

        <div v-if="menu" class="m360-overlay" @click="closeMenu"></div>

        <div v-if="menu" class="m360-pop" role="menu">
          <router-link to="/" class="m360-item" role="menuitem" @click="closeMenu"
            >📊 Dashboard</router-link
          >
          <router-link to="/devices" class="m360-item" role="menuitem" @click="closeMenu"
            >⚙️ Gestionar dispositivos</router-link
          >
          <router-link to="/monitor-builder" class="m360-item" role="menuitem" @click="closeMenu"
            >➕ Añadir monitor</router-link
          >
          <router-link to="/scan" class="m360-item" role="menuitem" @click="closeMenu"
            >📡 Escáner de Red</router-link
          >
          <router-link to="/reports" class="m360-item" role="menuitem" @click="closeMenu"
            >🤖 Reportes IA</router-link
          >
          <router-link to="/credentials" class="m360-item" role="menuitem" @click="closeMenu"
            >🔐 Credenciales</router-link
          >
          <router-link to="/channels" class="m360-item" role="menuitem" @click="closeMenu"
            >📢 Canales</router-link
          >
          <router-link to="/vpns" class="m360-item" role="menuitem" @click="closeMenu"
            >🛡️ VPNs</router-link
          >
          
          <router-link to="/account" class="m360-item" role="menuitem" @click="closeMenu"
            >👤 Mi Cuenta</router-link
          >
          
          <router-link to="/billing" class="m360-item" role="menuitem" @click="closeMenu"
            >💳 Facturación y Límites</router-link
          >

          <button class="m360-item logout" type="button" role="menuitem" @click="onLogout">
            ⎋ Cerrar sesión
          </button>
        </div>
      </div>

      <router-link to="/account" class="m360-avatar" :title="userEmail || 'Mi Cuenta'" aria-label="Mi Cuenta">
        <img v-if="userAvatar" :src="userAvatar" alt="Avatar" class="avatar-img" />
        <span v-else>{{ (userEmail || 'U').slice(0, 1).toUpperCase() }}</span>
      </router-link>
    </div>
  </header>

  <transition name="fade">
    <div v-if="showDetailsModal" class="m360-modal-overlay" @click.self="showDetailsModal = false">
      <div class="m360-modal">
        <div class="m360-modal-header">
          <h3>{{ currentDetailsTitle }}</h3>
          <button class="m360-close-btn" @click="showDetailsModal = false">✕</button>
        </div>
        <div class="m360-modal-body">
          <ul class="details-list">
            <li v-for="(item, idx) in currentDetailsList" :key="idx" :class="currentDetailsType">{{ formatDeviceItem(item) }}</li>
          </ul>
        </div>
      </div>
    </div>
  </transition>


</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import api from '@/lib/api' 
import logoSvgUrl from '@/assets/logo.svg?url'

const props = defineProps({
  realtime: { type: Boolean, default: true },
  userEmail: { type: String, default: '' },
  logoSrc: { type: String, default: '' },
  userAvatar: { type: String, default: '' }, 
})
const emit = defineEmits(['toggleSidebar', 'logout'])

/* Logo fallbacks */
const triedPublic = ref(false)
const showImg = ref(true)

const currentLogo = computed(() => {
  const viaProp = (props.logoSrc || '').trim()
  if (viaProp) return viaProp
  if (triedPublic.value) return '/icons/icon-192.png'
  return logoSvgUrl
})

const handleImgError = (e) => {
  if (!triedPublic.value) {
    triedPublic.value = true
    e.target.src = '/icons/icon-192.png'
  } else {
    showImg.value = false
  }
}

const route = useRoute()
const breadcrumb = computed(() => {
  const map = {
    '/': 'Dashboard',
    '/monitor-builder': 'Añadir monitor',
    '/scan': 'Descubrimiento',
    '/devices': 'Dispositivos',
    '/reports': 'Reportes IA',
    '/credentials': 'Credenciales',
    '/channels': 'Canales',
    '/vpns': 'VPNs',
    '/account': 'Mi Cuenta', 
    '/billing': 'Facturación y Límites', 
  }
  return map[route.path] ?? ''
})

/* Ocultar topbar al scrollear */
const isHidden = ref(false)
let lastY = 0
const onScroll = () => {
  const y = window.scrollY || 0
  isHidden.value = y > 24 && y > lastY
  lastY = y
}
onMounted(() => window.addEventListener('scroll', onScroll, { passive: true }))
onBeforeUnmount(() => window.removeEventListener('scroll', onScroll))

/* Menú Principal */
const menu = ref(false)
const menuRef = ref(null)
const closeMenu = () => {
  menu.value = false
}

/* Notificaciones (Nuevo Sistema Dual) */
const showNotif = ref(false)
const notifRef = ref(null)
const activeNotifTab = ref('devices') // 'devices' | 'system'

const notifications = ref([]) // Dispositivos pendientes (Mode 1)
const sysNotifications = ref([]) // Avisos de sistema (Mode 2 y 3)
let notifInterval = null

// Badge total
const totalBadgeCount = computed(() => notifications.value.length + sysNotifications.value.length)

// --- Lógica del Modal de Detalles ---
const showDetailsModal = ref(false)
const currentDetailsList = ref([])
const currentDetailsTitle = ref('Detalles')
const currentDetailsType = ref('error') // 'success' | 'error'

const formatDeviceItem = (item) => {
  if (typeof item === 'string') return item
  const name = item.name || item.hostname || item.host || item.device_name || ''
  const ip = item.ip_address || item.ip || ''
  if (name && ip) return `${name} — ${ip}`
  if (ip) return ip
  if (name) return name
  return JSON.stringify(item)
}

const parseMeta = (sys) => {
  if (!sys.meta_data) return {}
  if (typeof sys.meta_data === 'string') {
    try { return JSON.parse(sys.meta_data) } catch { return {} }
  }
  return sys.meta_data
}

const getFailedDevices = (sys) => {
  const m = parseMeta(sys)
  let devices = m.failed_devices || m.failed || m.errors || m.failed_items || m.error_details || []

  if (Array.isArray(devices) && devices.length > 0 && typeof devices[0] === 'object' && devices[0]?.status) {
    devices = devices.filter(d => d.status === 'failed' || d.status === 'error')
  }

  // Fallback: si solo tenemos un conteo, crear placeholder legible
  if ((!devices || devices.length === 0) && Number(m.failed_count) > 0) {
    return [`${m.failed_count} dispositivo(s) con error de adopción`]
  }

  return devices || []
}

const getAdoptedDevices = (sys) => {
  const m = parseMeta(sys)
  let devices = m.adopted_devices || m.adopted || m.results || m.successful || m.successful_devices || m.success_items || m.devices || []

  if (Array.isArray(devices) && devices.length > 0 && typeof devices[0] === 'object' && devices[0]?.status) {
    devices = devices.filter(d => d.status === 'adopted' || d.status === 'success')
  }

  // Fallback: si el backend solo envía el conteo (successful_count), generar placeholder
  if ((!devices || devices.length === 0) && Number(m.successful_count) > 0) {
    return [`${m.successful_count} dispositivo(s) adoptado(s) con éxito`]
  }

  return devices || []
}

const openDetails = (list, title = 'Detalles de Auditoría', type = 'error') => {
  if (list.length > 0) {
    currentDetailsList.value = list
    currentDetailsTitle.value = title
    currentDetailsType.value = type
    showDetailsModal.value = true
    showNotif.value = false
  }
}
// ------------------------------------

const toggleNotifications = async () => {
  showNotif.value = !showNotif.value
  if (showNotif.value) {
      await fetchAllNotifications()
      // Si hay avisos de sistema y no dispositivos, cambiamos a tab sistema
      if (notifications.value.length === 0 && sysNotifications.value.length > 0) {
          activeNotifTab.value = 'system'
      }
  }
}

const fetchAllNotifications = async () => {
  await Promise.all([fetchPendingDevices(), fetchSystemNotifications()])
}

// 1. Fetch Dispositivos Pendientes
const fetchPendingDevices = async () => {
  try {
    const { data } = await api.get('/discovery/pending')
    notifications.value = Array.isArray(data) ? data : []
  } catch (e) {
    console.debug('Error fetching pending devices:', e)
  }
}

// 2. Fetch Avisos de Sistema (Nuevo)
const fetchSystemNotifications = async () => {
  try {
    const { data } = await api.get('/notifications', { params: { unread_only: true } })
    sysNotifications.value = Array.isArray(data) ? data : []
  } catch (e) {
    console.debug('Error fetching system notifs:', e)
  }
}

// Marcar Avisos como Leídos
const markAllRead = async () => {
    try {
        await api.post('/notifications/read', { ids: [] }) // Empty list = All
        sysNotifications.value = []
        // Opcional: mostrar notificación toast "Limpiado"
    } catch (e) {
        console.error(e)
    }
}

const quickAdopt = async (notif) => {
  try {
    const payload = {
      maestro_id: notif.maestro_id,
      credential_profile_id: null, // Auto-resolve
      devices: [notif],
    }
    await api.post('/discovery/adopt', payload)
    
    // Remover localmente y refrescar para ver si generó aviso de sistema
    notifications.value = notifications.value.filter((n) => n.mac_address !== notif.mac_address)
    setTimeout(fetchSystemNotifications, 1000) // Dar tiempo al backend
  } catch (e) {
    console.error(e) 
    alert('Error al adoptar. Intenta desde el Escáner.')
  }
}

const quickDismiss = async (notif) => {
  try {
    await api.delete(`/discovery/pending/${notif.mac_address}`)
    notifications.value = notifications.value.filter((n) => n.mac_address !== notif.mac_address)
  } catch (e) {
    console.error(e)
  }
}

// Helpers de formato
const formatTime = (ts) => {
    if (!ts) return ''
    const d = new Date(ts)
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

/* Cerrar al cambiar de ruta */
watch(
  () => route.fullPath,
  () => {
    menu.value = false
    showNotif.value = false
  },
)

/* Esc global */
const onKeydown = (e) => {
  if (e.key === 'Escape') {
    if (menu.value) menu.value = false
    if (showNotif.value) showNotif.value = false
    if (showDetailsModal.value) showDetailsModal.value = false
  }
}

/* Click outside */
const onDocPointerDown = (e) => {
  if (menu.value && menuRef.value && !menuRef.value.contains(e.target)) {
    menu.value = false
  }
  if (showNotif.value && notifRef.value && !notifRef.value.contains(e.target)) {
    showNotif.value = false
  }
}

// --- EVENTOS GLOBALES DE WEBSOCKET Y POLLING ---
const handleGlobalNotificationEvent = () => {
  fetchAllNotifications()
  // Reintentos escalonados para cubrir latencia de BD
  setTimeout(fetchAllNotifications, 3000)
  setTimeout(fetchAllNotifications, 8000)
  setTimeout(fetchAllNotifications, 15000)
}

// Recibe el payload completo del WS vía CustomEvent.detail (system_notification)
const handleSystemNotificationWS = async (event) => {
  const msg = event?.detail
  if (msg?.title || msg?.message) {
    // Inyectar notificación inmediata sin esperar el fetch REST
    const synthetic = {
      id: `ws-${Date.now()}`,
      title: msg.title || 'Aviso del sistema',
      message: msg.message || '',
      type: msg.level || 'info',
      meta_data: msg.meta_data ?? null,
      created_at: new Date().toISOString(),
      _synthetic: true,
    }
    sysNotifications.value = [synthetic, ...sysNotifications.value.filter(n => !n._synthetic)]
    if (showNotif.value) activeNotifTab.value = 'system'
  }
  // Sincronizar con REST tras breve delay (reemplaza la entrada sintética con la real de BD)
  setTimeout(fetchSystemNotifications, 1500)
}

const handleDiscoveryDeviceDismissed = (event) => {
  const mac = event?.detail?.mac
  if (!mac) return
  notifications.value = notifications.value.filter(n => n.mac_address !== mac)
}

// Cuando termina un scan, el worker de adopción puede tardar hasta ~60s en completar.
// Hacemos polling cada 8s durante 60s para no depender del WS (que puede perderse en reconexiones).
let _scanPollingInterval = null
const handleDiscoveryScanFinished = () => {
  if (_scanPollingInterval) clearInterval(_scanPollingInterval)
  let elapsed = 0
  _scanPollingInterval = setInterval(() => {
    fetchAllNotifications()
    elapsed += 8000
    if (elapsed >= 60000) {
      clearInterval(_scanPollingInterval)
      _scanPollingInterval = null
    }
  }, 8000)
}

onMounted(() => {
  window.addEventListener('keydown', onKeydown)
  document.addEventListener('pointerdown', onDocPointerDown, true)

  window.addEventListener('refresh-notifications', handleGlobalNotificationEvent)
  window.addEventListener('new_notification', handleGlobalNotificationEvent)
  window.addEventListener('system_notification', handleSystemNotificationWS)
  window.addEventListener('discovery_device_dismissed', handleDiscoveryDeviceDismissed)
  window.addEventListener('discovery_scan_finished', handleDiscoveryScanFinished)
  window.addEventListener('adoption_complete', handleGlobalNotificationEvent)

  fetchAllNotifications()
  notifInterval = setInterval(fetchAllNotifications, 30000)
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKeydown)
  document.removeEventListener('pointerdown', onDocPointerDown, true)

  window.removeEventListener('refresh-notifications', handleGlobalNotificationEvent)
  window.removeEventListener('new_notification', handleGlobalNotificationEvent)
  window.removeEventListener('system_notification', handleSystemNotificationWS)
  window.removeEventListener('discovery_device_dismissed', handleDiscoveryDeviceDismissed)
  window.removeEventListener('discovery_scan_finished', handleDiscoveryScanFinished)
  window.removeEventListener('adoption_complete', handleGlobalNotificationEvent)

  if (notifInterval) clearInterval(notifInterval)
  if (_scanPollingInterval) clearInterval(_scanPollingInterval)
})

/* Logout handlers */
const onLogout = () => {
  menu.value = false
  emit('logout')
}

</script>

<style scoped>
/* Overlay global */
.m360-overlay {
  position: fixed;
  inset: 0;
  z-index: 40;
  background: transparent;
}

/* Layout base */
.m360-topbar {
  position: sticky;
  top: 0;
  z-index: 50;
  height: 44px;
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  gap: 8px;
  padding: 0 10px;
  backdrop-filter: saturate(1.2) blur(8px);
  background: color-mix(in srgb, var(--m360-bg, #0b1220) 70%, transparent);
  border-bottom: 1px solid color-mix(in srgb, #7aa0ff 12%, transparent);
  transition: transform 0.2s ease;
}
.m360-topbar--hidden {
  transform: translateY(-100%);
}

.m360-left {
  justify-self: start;
  display: flex;
  align-items: center;
  gap: 10px;
}
.m360-center {
  pointer-events: none;
}
.m360-right {
  justify-self: end;
  display: flex;
  align-items: center;
  gap: 8px;
}

/* Marca */
.m360-brand {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  text-decoration: none;
}
.m360-brand img {
  width: 22px;
  height: 22px;
  border-radius: 5px;
}
.m360-brand-text {
  font-size: 15px;
  font-weight: 800;
  color: #b9cdfa;
  letter-spacing: 0.2px;
  line-height: 1;
  -webkit-font-smoothing: antialiased;
}
.m360-crumb {
  font-size: 12px;
  color: #93a4c7;
  opacity: 0.9;
}

/* Botones */
.m360-iconbtn {
  width: 28px;
  height: 28px;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: #cfe0ff;
  display: grid;
  place-items: center;
  position: relative;
}
.m360-iconbtn:hover {
  background: rgba(255, 255, 255, 0.06);
}

/* Badge de Notificaciones */
.m360-badge {
  position: absolute;
  top: -2px;
  right: -2px;
  background: #e94560;
  color: white;
  font-size: 9px;
  font-weight: bold;
  height: 14px;
  min-width: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 10px;
  border: 1px solid #0b1220;
}

/* Chip realtime */
.m360-chip {
  height: 24px;
  border-radius: 999px;
  border: 1px solid rgba(130, 180, 255, 0.25);
  background: rgba(130, 180, 255, 0.08);
  padding: 0 8px;
  display: inline-flex;
  gap: 6px;
  align-items: center;
  font-size: 12px;
  color: #cfe0ff;
  user-select: none;
  cursor: default;
  pointer-events: none;
}
.m360-chip .dot {
  width: 6px;
  height: 6px;
  border-radius: 999px;
  background: #9aa9c8;
}
.m360-chip.is-on .dot {
  background: #37e39f;
  box-shadow: 0 0 0 3px rgba(55, 227, 159, 0.18);
}
.m360-chip.is-off {
  opacity: 0.8;
}

/* Menú & Popups */
.m360-menu {
  position: relative;
}
.m360-pop {
  position: absolute;
  right: 0;
  top: 36px;
  min-width: 200px;
  z-index: 45;
  background: #0f1626;
  border: 1px solid rgba(130, 180, 255, 0.22);
  border-radius: 12px;
  padding: 6px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.35);
}

/* --- ESTILOS NOTIFICACIONES MEJORADOS --- */
.notif-pop {
  width: 320px;
  padding: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

/* Tabs Header */
.notif-tabs {
  display: flex;
  background: rgba(0,0,0,0.3);
  border-bottom: 1px solid rgba(255,255,255,0.1);
}
.notif-tab {
  flex: 1;
  background: none;
  border: none;
  padding: 10px;
  color: #8899b0;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  border-bottom: 2px solid transparent;
  transition: all 0.2s;
}
.notif-tab:hover {
  color: #ccd6f6;
  background: rgba(255,255,255,0.05);
}
.notif-tab.active {
  color: #64ffda;
  border-bottom-color: #64ffda;
  background: rgba(100, 255, 218, 0.05);
}

.notif-header-actions {
    padding: 8px;
    text-align: right;
    border-bottom: 1px solid rgba(255,255,255,0.05);
}
.btn-text-small {
    background: none;
    border: none;
    color: #64ffda;
    font-size: 11px;
    cursor: pointer;
    text-decoration: underline;
}

.notif-list {
  max-height: 300px;
  overflow-y: auto;
}
.notif-empty {
  padding: 30px;
  text-align: center;
  color: #93a4c7;
  font-size: 13px;
  font-style: italic;
}

/* Items Pendientes */
.notif-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}
.notif-item:hover { background: rgba(255, 255, 255, 0.03); }

.notif-info { display: flex; flex-direction: column; gap: 2px; }
.notif-top { display: flex; gap: 6px; align-items: center; }
.notif-vendor { font-size: 13px; font-weight: bold; color: #e0e0e0; }
.notif-ip {
  font-size: 11px;
  color: #3ddc84;
  background: rgba(61, 220, 132, 0.1);
  padding: 1px 4px;
  border-radius: 4px;
}
.notif-mac { font-size: 11px; color: #93a4c7; font-family: monospace; }

.notif-actions { display: flex; gap: 4px; }
.btn-icon-action {
  width: 24px;
  height: 24px;
  border-radius: 4px;
  border: none;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}
.btn-icon-action.adopt { background: rgba(61, 220, 132, 0.2); color: #3ddc84; }
.btn-icon-action.dismiss { background: rgba(233, 69, 96, 0.2); color: #e94560; }

/* Items Sistema (Avisos) */
.sys-item {
    padding: 12px;
    border-bottom: 1px solid rgba(255,255,255,0.05);
    border-left: 3px solid transparent;
}
.sys-item.success { border-left-color: #3ddc84; }
.sys-item.error { border-left-color: #e94560; }
.sys-item.info { border-left-color: #64ffda; }

.sys-content {
    display: flex;
    flex-direction: column;
    gap: 4px;
}
.sys-title {
    font-size: 13px;
    font-weight: bold;
    color: #fff;
}
.sys-msg {
    font-size: 12px;
    color: #aab6d3;
    line-height: 1.3;
}
.sys-time {
    font-size: 10px;
    color: #5f7096;
    align-self: flex-end;
}

.view-details-btn {
  margin-top: 4px;
  align-self: flex-start;
  padding: 4px 8px;
  background: rgba(100, 255, 218, 0.1);
  border-radius: 4px;
  color: #64ffda;
  text-decoration: none;
  transition: background 0.2s;
}
.view-details-btn:hover {
  background: rgba(100, 255, 218, 0.2);
}

.notif-footer {
  display: block;
  text-align: center;
  padding: 10px;
  background: rgba(0, 0, 0, 0.2);
  border-top: 1px solid rgba(255, 255, 255, 0.05);
  color: #5372f0;
  font-size: 12px;
  font-weight: bold;
  text-decoration: none;
}
.notif-footer:hover { background: rgba(83, 114, 240, 0.1); }

/* Items menú normal */
.m360-item {
  display: block;
  width: 100%;
  text-align: left;
  padding: 8px 10px;
  border-radius: 8px;
  font-size: 13px;
  color: #ccdaff;
  text-decoration: none;
  background: transparent;
  border: 0;
  outline: 0;
}
.m360-item:hover {
  background: rgba(255, 255, 255, 0.06);
}
.m360-item.logout {
  color: #ff9a9a;
  border-top: 1px solid rgba(255, 154, 154, 0.2);
  margin-top: 6px;
}
.m360-item.logout:hover {
  background: rgba(233, 69, 96, 0.15);
  color: #ffc7c7;
}

/* Avatar */
.m360-avatar {
  width: 26px;
  height: 26px;
  border-radius: 999px;
  background: #1a2236;
  border: 1px solid rgba(130, 180, 255, 0.25);
  color: #cfe0ff;
  display: grid;
  place-items: center;
  font-size: 12px;
  font-weight: 700;
  overflow: hidden;
  cursor: pointer;
  text-decoration: none;
  transition: border-color 0.2s, box-shadow 0.2s;
}
.m360-avatar:hover {
  border-color: rgba(130, 180, 255, 0.7);
  box-shadow: 0 0 0 2px rgba(130, 180, 255, 0.2);
}
.avatar-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

/* --- ESTILOS DEL MODAL DE DETALLES --- */
.m360-modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  backdrop-filter: blur(4px);
  z-index: 9999;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}
.m360-modal {
  background: #0f1626;
  border: 1px solid rgba(130, 180, 255, 0.22);
  border-radius: 12px;
  width: 100%;
  max-width: 600px;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.5);
}
.m360-modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}
.m360-modal-header h3 {
  margin: 0;
  color: #fff;
  font-size: 16px;
}
.m360-close-btn {
  background: transparent;
  border: none;
  color: #93a4c7;
  font-size: 18px;
  cursor: pointer;
}
.m360-close-btn:hover {
  color: #ff9a9a;
}
.m360-modal-body {
  padding: 20px;
  overflow-y: auto;
}
.details-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.details-list li {
  background: rgba(255, 255, 255, 0.03);
  padding: 12px;
  border-radius: 6px;
  font-size: 13px;
  font-family: monospace;
  word-break: break-all;
}
.details-list li.error {
  color: #ff9a9a;
  border-left: 3px solid #e94560;
}
.details-list li.success {
  color: #3ddc84;
  border-left: 3px solid #3ddc84;
}

/* Transitions */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.18s;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

@media (max-width: 820px) {
  .m360-crumb,
  .m360-brand-text {
    display: none;
  }
  .m360-topbar {
    height: 42px;
    padding: 0 8px;
  }
  .m360-iconbtn {
    width: 26px;
    height: 26px;
  }
  .m360-modal {
    max-width: 95vw;
  }
}

@media (max-width: 400px) {
  .notif-pop {
    width: calc(100vw - 2rem);
    max-width: 340px;
  }
}
</style>