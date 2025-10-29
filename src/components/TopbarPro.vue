<template>
  <header :class="['m360-topbar', isHidden ? 'm360-topbar--hidden' : '']">
    <!-- Izquierda -->
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
          <!-- Fallback SVG inline -->
          <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true">
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

    <!-- Derecha -->
    <div class="m360-right">
      <span class="m360-chip" :class="realtime ? 'is-on' : 'is-off'" aria-hidden="true">
        <span class="dot" />
        <span class="label">{{ realtime ? 'Tiempo real' : 'Reconectando…' }}</span>
      </span>

      <!-- Menú -->
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

        <!-- Overlay auxiliar -->
        <div v-if="menu" class="m360-overlay" @click="closeMenu"></div>

        <div v-if="menu" class="m360-pop" role="menu">
          <router-link to="/" class="m360-item" role="menuitem" @click="closeMenu"
            >Dashboard</router-link
          >
          <router-link to="/monitor-builder" class="m360-item" role="menuitem" @click="closeMenu"
            >Añadir monitor</router-link
          >
          <router-link to="/devices" class="m360-item" role="menuitem" @click="closeMenu"
            >Gestionar dispositivos</router-link
          >
          <router-link to="/credentials" class="m360-item" role="menuitem" @click="closeMenu"
            >Credenciales</router-link
          >
          <router-link to="/channels" class="m360-item" role="menuitem" @click="closeMenu"
            >Canales</router-link
          >
          <router-link to="/vpns" class="m360-item" role="menuitem" @click="closeMenu"
            >VPNs</router-link
          >

          <button class="m360-item logout" type="button" role="menuitem" @click="onLogout">
            Cerrar sesión
          </button>
        </div>
      </div>

      <!-- Avatar -->
      <div class="m360-avatar" :title="userEmail || 'Cuenta'" aria-label="Cuenta">
        <span>{{ (userEmail || 'U').slice(0, 1).toUpperCase() }}</span>
      </div>
    </div>
  </header>

  <!-- SPEED DIAL (móvil) -->
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
import logoSvgUrl from '@/assets/logo.svg?url' // ✅ tu logo real

const props = defineProps({
  realtime: { type: Boolean, default: true },
  userEmail: { type: String, default: '' },
  logoSrc: { type: String, default: '' }, // permite override si querés
})
const emit = defineEmits(['toggleSidebar', 'logout'])

/* Logo fallbacks: prop → logo.svg (src/assets) → /icons/icon-192.png (public) → SVG inline */
const triedPublic = ref(false)
const showImg = ref(true)

const currentLogo = computed(() => {
  const viaProp = (props.logoSrc || '').trim()
  if (viaProp) return viaProp // 1) Prop
  if (triedPublic.value) return '/icons/icon-192.png' // 3) Public
  return logoSvgUrl // 2) Asset Vite (svg)
})

const handleImgError = (e) => {
  if (!triedPublic.value) {
    triedPublic.value = true
    e.target.src = '/icons/icon-192.png'
  } else {
    showImg.value = false // 4) SVG inline
  }
}

const route = useRoute()
const breadcrumb = computed(() => {
  const map = {
    '/': 'Dashboard',
    '/monitor-builder': 'Añadir monitor',
    '/devices': 'Dispositivos',
    '/credentials': 'Credenciales',
    '/channels': 'Canales',
    '/vpns': 'VPNs',
  }
  return map[route.path] ?? ''
})

/* Ocultar topbar al scrollear hacia abajo */
const isHidden = ref(false)
let lastY = 0
const onScroll = () => {
  const y = window.scrollY || 0
  isHidden.value = y > 24 && y > lastY
  lastY = y
}
onMounted(() => window.addEventListener('scroll', onScroll, { passive: true }))
onBeforeUnmount(() => window.removeEventListener('scroll', onScroll))

/* Menú */
const menu = ref(false)
const menuRef = ref(null)
const closeMenu = () => {
  menu.value = false
}

/* Cerrar al cambiar de ruta */
const fabOpen = ref(false)
watch(
  () => route.fullPath,
  () => {
    menu.value = false
    fabOpen.value = false
  },
)

/* Esc global para cerrar menú y fab */
const onKeydown = (e) => {
  if (e.key === 'Escape') {
    if (menu.value) menu.value = false
    if (fabOpen.value) fabOpen.value = false
  }
}

/* Click/tap fuera en TODA la página (fase captura, compatible móvil) */
const onDocPointerDown = (e) => {
  if (!menu.value) return
  const root = menuRef.value
  if (root && !root.contains(e.target)) {
    menu.value = false
  }
}
onMounted(() => {
  window.addEventListener('keydown', onKeydown)
  document.addEventListener('pointerdown', onDocPointerDown, true)
})
onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKeydown)
  document.removeEventListener('pointerdown', onDocPointerDown, true)
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

/* Speed Dial */
const closeFab = () => {
  fabOpen.value = false
}
</script>

<style scoped>
/* Overlay global para click-outside (menú & speed dial) */
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
  gap: 8px;
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
  gap: 8px;
  text-decoration: none;
}
.m360-brand img {
  width: 18px;
  height: 18px;
  border-radius: 4px;
}
.m360-brand-text {
  font-size: 13px;
  font-weight: 700;
  color: #b9cdfa;
  letter-spacing: 0.2px;
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
}
.m360-iconbtn:hover {
  background: rgba(255, 255, 255, 0.06);
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

/* Menú */
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
.m360-item:focus-visible {
  outline: 2px solid rgba(130, 180, 255, 0.35);
  outline-offset: 2px;
  background: rgba(255, 255, 255, 0.04);
}

/* Logout consistente */
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

/* Logout del Speed Dial: sólido */
.m360-fab-item.danger-solid {
  background: #e94560;
  color: #fff;
  border: none;
}
.m360-fab-item.danger-solid:hover {
  filter: brightness(1.05);
}

/* Transición */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.18s;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* Responsive */
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
