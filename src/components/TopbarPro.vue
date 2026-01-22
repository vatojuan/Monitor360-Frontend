<template>
  <header :class="['m360-topbar', isHidden ? 'm360-topbar--hidden' : '']">
    <div class="m360-left">
      <button class="m360-iconbtn" @click="emit('toggleSidebar')" aria-label="Abrir menú">
        <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor">
          <path d="M3 6h18M3 12h18M3 18h18" />
        </svg>
      </button>

      <router-link to="/" class="m360-brand" aria-label="Monitor360">
        <template v-if="showImg">
          <img :src="currentLogo" alt="Monitor360" @error="handleImgError" />
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
        <span class="m360-brand-text">Monitor360</span>
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
          <span v-if="notifications.length > 0" class="m360-badge">{{ notifications.length }}</span>
        </button>

        <div v-if="showNotif" class="m360-pop notif-pop" role="menu">
          <div class="notif-header">
            <span>Dispositivos Nuevos</span>
            <button @click="fetchNotifications" class="refresh-btn" title="Actualizar">↻</button>
          </div>

          <div v-if="notifications.length === 0" class="notif-empty">Sin novedades.</div>

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
                <button @click="quickAdopt(notif)" class="btn-icon-action adopt" title="Adoptar">
                  ✔
                </button>
                <button
                  @click="quickDismiss(notif)"
                  class="btn-icon-action dismiss"
                  title="Ignorar"
                >
                  ✕
                </button>
              </div>
            </div>
          </div>

          <router-link to="/scan" class="notif-footer" @click="showNotif = false">
            Ir al Escáner Avanzado
          </router-link>
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
          <router-link to="/monitor-builder" class="m360-item" role="menuitem" @click="closeMenu"
            >➕ Añadir monitor</router-link
          >
          <router-link to="/scan" class="m360-item" role="menuitem" @click="closeMenu"
            >📡 Escáner de Red</router-link
          >
          <router-link to="/devices" class="m360-item" role="menuitem" @click="closeMenu"
            >⚙️ Gestionar dispositivos</router-link
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

          <button class="m360-item logout" type="button" role="menuitem" @click="onLogout">
            ⎋ Cerrar sesión
          </button>
        </div>
      </div>

      <div class="m360-avatar" :title="userEmail || 'Cuenta'" aria-label="Cuenta">
        <span>{{ (userEmail || 'U').slice(0, 1).toUpperCase() }}</span>
      </div>
    </div>
  </header>

  <div v-if="fabOpen" class="m360-overlay" @click="fabOpen = false"></div>

  <div class="m360-fab-wrapper">
    <div class="m360-fab-main" @click.stop="fabOpen = !fabOpen" aria-label="Acciones rápidas">
      <svg
        viewBox="0 0 24 24"
        width="22"
        height="22"
        fill="currentColor"
        :class="{ open: fabOpen }"
      >
        <path d="M11 11V5h2v6h6v2h-6v6h-2v-6H5v-2z" />
      </svg>
    </div>

    <transition name="fade">
      <div v-if="fabOpen" class="m360-fab-menu" @click.stop>
        <router-link to="/monitor-builder" class="m360-fab-item" @click="closeFab"
          >➕ Añadir</router-link
        >
        <router-link to="/scan" class="m360-fab-item" @click="closeFab">📡 Escáner</router-link>
        <router-link to="/devices" class="m360-fab-item" @click="closeFab"
          >⚙️ Dispositivos</router-link
        >
        <button class="m360-fab-item danger-solid" type="button" @click="onFabLogout">
          ⎋ Cerrar sesión
        </button>
      </div>
    </transition>
  </div>
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
    '/credentials': 'Credenciales',
    '/channels': 'Canales',
    '/vpns': 'VPNs',
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

/* Notificaciones (Nuevo) */
const showNotif = ref(false)
const notifRef = ref(null)
const notifications = ref([])
let notifInterval = null

const toggleNotifications = () => {
  showNotif.value = !showNotif.value
}

const fetchNotifications = async () => {
  try {
    const { data } = await api.get('/discovery/pending')
    notifications.value = Array.isArray(data) ? data : []
  } catch (e) {
    console.debug('Error fetching notifications:', e)
  }
}

const quickAdopt = async (notif) => {
  try {
    // --- CORRECCIÓN CRÍTICA ---
    // NO debemos enviar notif.profile_id como credential_profile_id.
    // notif.profile_id es el perfil de ESCANEO.
    // Enviamos null para que el Backend resuelva automáticamente las credenciales
    // asociadas a ese perfil de escaneo.
    
    const payload = {
      maestro_id: notif.maestro_id,
      credential_profile_id: null, // <--- CAMBIO AQUÍ: Null para activar auto-resolución en backend
      devices: [notif],
    }
    await api.post('/discovery/adopt', payload)
    
    // Remover de la lista localmente para feedback inmediato
    notifications.value = notifications.value.filter((n) => n.mac_address !== notif.mac_address)
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

/* Cerrar al cambiar de ruta */
const fabOpen = ref(false)
watch(
  () => route.fullPath,
  () => {
    menu.value = false
    showNotif.value = false
    fabOpen.value = false
  },
)

/* Esc global */
const onKeydown = (e) => {
  if (e.key === 'Escape') {
    if (menu.value) menu.value = false
    if (showNotif.value) showNotif.value = false
    if (fabOpen.value) fabOpen.value = false
  }
}

/* Click outside (Menú y Notificaciones) */
const onDocPointerDown = (e) => {
  if (menu.value && menuRef.value && !menuRef.value.contains(e.target)) {
    menu.value = false
  }
  if (showNotif.value && notifRef.value && !notifRef.value.contains(e.target)) {
    showNotif.value = false
  }
}

onMounted(() => {
  window.addEventListener('keydown', onKeydown)
  document.addEventListener('pointerdown', onDocPointerDown, true)

  fetchNotifications()
  notifInterval = setInterval(fetchNotifications, 30000)
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKeydown)
  document.removeEventListener('pointerdown', onDocPointerDown, true)
  if (notifInterval) clearInterval(notifInterval)
})

/* Logout handlers */
const onLogout = () => {
  menu.value = false
  emit('logout')
}
const onFabLogout = () => {
  fabOpen.value = false
  emit('logout')
}
const closeFab = () => {
  fabOpen.value = false
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

/* Estilos específicos de Notificaciones */
.notif-pop {
  width: 300px;
  padding: 0;
  overflow: hidden;
}
.notif-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px;
  background: rgba(0, 0, 0, 0.2);
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  font-size: 13px;
  font-weight: bold;
  color: #b9cdfa;
}
.refresh-btn {
  background: none;
  border: none;
  color: #93a4c7;
  cursor: pointer;
  font-size: 14px;
}
.refresh-btn:hover {
  color: white;
}

.notif-list {
  max-height: 300px;
  overflow-y: auto;
}
.notif-empty {
  padding: 20px;
  text-align: center;
  color: #93a4c7;
  font-size: 13px;
  font-style: italic;
}

.notif-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}
.notif-item:last-child {
  border-bottom: none;
}
.notif-item:hover {
  background: rgba(255, 255, 255, 0.03);
}

.notif-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.notif-top {
  display: flex;
  gap: 6px;
  align-items: center;
}
.notif-vendor {
  font-size: 13px;
  font-weight: bold;
  color: #e0e0e0;
}
.notif-ip {
  font-size: 11px;
  color: #3ddc84;
  background: rgba(61, 220, 132, 0.1);
  padding: 1px 4px;
  border-radius: 4px;
}
.notif-mac {
  font-size: 11px;
  color: #93a4c7;
  font-family: monospace;
}

.notif-actions {
  display: flex;
  gap: 4px;
}
.btn-icon-action {
  width: 24px;
  height: 24px;
  border-radius: 4px;
  border: none;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.2s;
}
.btn-icon-action.adopt {
  background: rgba(61, 220, 132, 0.2);
  color: #3ddc84;
}
.btn-icon-action.adopt:hover {
  background: #3ddc84;
  color: black;
}
.btn-icon-action.dismiss {
  background: rgba(233, 69, 96, 0.2);
  color: #e94560;
}
.btn-icon-action.dismiss:hover {
  background: #e94560;
  color: white;
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
.notif-footer:hover {
  background: rgba(83, 114, 240, 0.1);
}

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
}

/* SPEED DIAL */
.m360-fab-wrapper {
  position: fixed;
  right: 14px;
  bottom: 14px;
  z-index: 45;
  display: none;
}
.m360-fab-main {
  width: 48px;
  height: 48px;
  border-radius: 14px;
  background: #2b68ff;
  color: white;
  display: grid;
  place-items: center;
  box-shadow: 0 10px 28px rgba(0, 0, 0, 0.35);
  cursor: pointer;
  user-select: none;
  transition: transform 0.15s ease;
}
.m360-fab-main:hover {
  transform: translateY(-1px);
}
.m360-fab-main svg.open {
  transform: rotate(45deg);
  transition: transform 0.15s ease;
}

.m360-fab-menu {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 8px;
  margin-bottom: 10px;
}
.m360-fab-item {
  background: #1a2236;
  color: #cfe0ff;
  padding: 6px 10px;
  border-radius: 8px;
  font-size: 13px;
  text-decoration: none;
  box-shadow: 0 3px 10px rgba(0, 0, 0, 0.3);
}
.m360-fab-item:hover {
  background: #2b68ff;
  color: white;
}
.m360-fab-item.danger-solid {
  background: #e94560;
  color: #fff;
  border: none;
}
.m360-fab-item.danger-solid:hover {
  filter: brightness(1.05);
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
  .m360-fab-wrapper {
    display: block;
  }
}
</style>