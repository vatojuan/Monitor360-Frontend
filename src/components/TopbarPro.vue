<template>
  <header :class="['m360-topbar', isHidden ? 'm360-topbar--hidden' : '']">
    <!-- Lado izquierdo: logo + breadcrumb corto -->
    <div class="m360-left">
      <button
        class="m360-iconbtn"
        @click="$emit('toggleSidebar')"
        title="Menú"
        aria-label="Abrir menú"
      >
        <!-- hamburguesa -->
        <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor">
          <path d="M3 6h18M3 12h18M3 18h18" />
        </svg>
      </button>

      <router-link to="/" class="m360-brand" aria-label="Monitor360">
        <img :src="logoSrc" alt="" />
        <span class="m360-brand-text">Monitor360</span>
      </router-link>

      <span class="m360-crumb" v-if="breadcrumb">{{ breadcrumb }}</span>
    </div>

    <!-- Centro: espacio libre (deja ver monitores) -->
    <div class="m360-center" />

    <!-- Lado derecho: acciones compactas -->
    <div class="m360-right">
      <!-- Toggle tiempo real -->
      <button
        class="m360-chip"
        :class="realtime ? 'is-on' : 'is-off'"
        @click="$emit('toggleRealtime')"
        aria-pressed="realtime"
      >
        <span class="dot" />
        <span class="label">{{ realtime ? 'Tiempo real' : 'Pausado' }}</span>
      </button>

      <!-- Reloj/uptime (opcional) -->
      <span class="m360-time" v-if="uptime">{{ uptime }}</span>

      <!-- Command Palette -->
      <button
        class="m360-iconbtn"
        @click="openCmd = true"
        title="Comandos (Ctrl/⌘+K)"
        aria-label="Abrir comandos"
      >
        <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor">
          <path d="M10 4h4v2h-4zM4 10h2v4H4zm14 0h2v4h-2zM10 18h4v2h-4zM7 7h10v10H7z" />
        </svg>
      </button>

      <!-- Menú rápido -->
      <div class="m360-menu" @keydown.esc="menu = false">
        <button
          class="m360-iconbtn"
          @click="menu = !menu"
          title="Más"
          aria-haspopup="menu"
          :aria-expanded="menu"
        >
          <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor">
            <circle cx="5" cy="12" r="2" />
            <circle cx="12" cy="12" r="2" />
            <circle cx="19" cy="12" r="2" />
          </svg>
        </button>
        <div v-if="menu" class="m360-pop" role="menu">
          <router-link to="/" class="m360-item" role="menuitem">Dashboard</router-link>
          <router-link to="/monitor-builder" class="m360-item" role="menuitem"
            >Añadir monitor</router-link
          >
          <router-link to="/devices" class="m360-item" role="menuitem"
            >Gestionar dispositivos</router-link
          >
          <router-link to="/credentials" class="m360-item" role="menuitem"
            >Credenciales</router-link
          >
          <router-link to="/channels" class="m360-item" role="menuitem">Canales</router-link>
          <router-link to="/vpns" class="m360-item" role="menuitem">VPNs</router-link>
          <button class="m360-item danger" role="menuitem" @click="$emit('logout')">
            Cerrar sesión
          </button>
        </div>
      </div>

      <!-- Avatar mínimo -->
      <div class="m360-avatar" :title="userEmail || 'Cuenta'" aria-label="Cuenta">
        <span>{{ (userEmail || 'U').slice(0, 1).toUpperCase() }}</span>
      </div>
    </div>

    <!-- Command Palette (muy simple) -->
    <div v-if="openCmd" class="m360-cmd" @click.self="openCmd = false">
      <div class="m360-cmd-box">
        <input
          v-model="query"
          type="search"
          placeholder="Escribe un comando o busca (ej: añadir monitor)…"
          @keydown.esc="openCmd = false"
          @keydown.enter="runFirst"
          aria-label="Buscar comando"
        />
        <div class="m360-cmd-list">
          <router-link
            v-for="(opt, i) in filtered"
            :key="opt.to + String(i)"
            :to="opt.to"
            class="m360-cmd-item"
            @click="openCmd = false"
          >
            {{ opt.label }}
          </router-link>
        </div>
      </div>
    </div>
  </header>

  <!-- FAB móvil (opcional) -->
  <router-link
    to="/monitor-builder"
    class="m360-fab"
    title="Añadir monitor"
    aria-label="Añadir monitor"
  >
    <svg viewBox="0 0 24 24" width="22" height="22" fill="currentColor">
      <path d="M11 11V5h2v6h6v2h-6v6h-2v-6H5v-2z" />
    </svg>
  </router-link>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, computed } from 'vue'
import { useRoute } from 'vue-router'

defineProps({
  realtime: { type: Boolean, default: true },
  uptime: { type: String, default: '' },
  userEmail: { type: String, default: '' },
  logoSrc: { type: String, default: '/favicon-32x32.png' },
})

defineEmits(['toggleRealtime', 'toggleSidebar', 'logout'])

const route = useRoute()
const breadcrumb = computed(() => {
  // título corto a la derecha del logo
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

const isHidden = ref(false)
let lastY = 0
const onScroll = () => {
  const y = window.scrollY || 0
  isHidden.value = y > 24 && y > lastY // oculta si vas bajando
  lastY = y
}
onMounted(() => window.addEventListener('scroll', onScroll, { passive: true }))
onBeforeUnmount(() => window.removeEventListener('scroll', onScroll))

// menú
const menu = ref(false)
const closeOnRoute = () => (menu.value = false)
onMounted(() => window.addEventListener('hashchange', closeOnRoute))
onBeforeUnmount(() => window.removeEventListener('hashchange', closeOnRoute))

// command palette
const openCmd = ref(false)
const query = ref('')
const options = [
  { label: 'Dashboard', to: '/' },
  { label: 'Añadir monitor', to: '/monitor-builder' },
  { label: 'Gestionar dispositivos', to: '/devices' },
  { label: 'Credenciales', to: '/credentials' },
  { label: 'Canales', to: '/channels' },
  { label: 'VPNs', to: '/vpns' },
]
const filtered = computed(() =>
  options.filter((o) => o.label.toLowerCase().includes(query.value.toLowerCase().trim())),
)
const runFirst = () => {
  const f = filtered.value[0]
  if (f) {
    openCmd.value = false
    // navegación se resuelve por <router-link>
  }
}
// atajo Ctrl/⌘+K
const onKey = (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
    e.preventDefault()
    openCmd.value = !openCmd.value
    query.value = ''
  }
}
onMounted(() => window.addEventListener('keydown', onKey))
onBeforeUnmount(() => window.removeEventListener('keydown', onKey))
</script>

<style scoped>
/* Layout base */
.m360-topbar {
  position: sticky;
  top: 0;
  z-index: 50;
  height: 44px;
  display: grid;
  grid-template-columns: 1fr auto 1fr;
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

.m360-left,
.m360-right {
  display: flex;
  align-items: center;
  gap: 8px;
}
.m360-center {
  pointer-events: none;
} /* no poner nada en el centro */

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
  opacity: 0.7;
}

/* Hora / uptime */
.m360-time {
  font-size: 12px;
  color: #9fb2dd;
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
  background: #0f1626;
  border: 1px solid rgba(130, 180, 255, 0.22);
  border-radius: 12px;
  padding: 6px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.35);
}
.m360-item {
  display: block;
  padding: 8px 10px;
  border-radius: 8px;
  font-size: 13px;
  color: #ccdaff;
  text-decoration: none;
}
.m360-item:hover {
  background: rgba(255, 255, 255, 0.06);
}
.m360-item.danger {
  color: #ffb4b4;
}

/* Avatar simple */
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

/* Command Palette */
.m360-cmd {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  display: grid;
  place-items: start center;
  padding-top: 10vh;
  z-index: 70;
}
.m360-cmd-box {
  width: min(720px, calc(100vw - 24px));
  background: #0e1525;
  border: 1px solid rgba(130, 180, 255, 0.22);
  border-radius: 14px;
  overflow: hidden;
}
.m360-cmd-box input {
  width: 100%;
  height: 44px;
  background: #0b1220;
  border: 0;
  color: #dfe8ff;
  padding: 0 12px;
  font-size: 14px;
  outline: none;
  border-bottom: 1px solid rgba(130, 180, 255, 0.15);
}
.m360-cmd-list {
  max-height: 50vh;
  overflow: auto;
}
.m360-cmd-item {
  display: block;
  padding: 10px 12px;
  color: #cfe0ff;
  text-decoration: none;
  font-size: 14px;
}
.m360-cmd-item:hover {
  background: rgba(255, 255, 255, 0.06);
}

/* FAB móvil */
.m360-fab {
  position: fixed;
  right: 14px;
  bottom: 14px;
  width: 48px;
  height: 48px;
  border-radius: 14px;
  background: #2b68ff;
  color: white;
  display: none;
  place-items: center;
  box-shadow: 0 10px 28px rgba(0, 0, 0, 0.35);
  z-index: 45;
}

/* Responsivo */
@media (max-width: 820px) {
  .m360-crumb,
  .m360-time,
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
  .m360-chip .label {
    display: none;
  }
  .m360-fab {
    display: grid;
  }
}
</style>
