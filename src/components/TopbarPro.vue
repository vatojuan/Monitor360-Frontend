<template>
  <header :class="['m360-topbar', isHidden ? 'm360-topbar--hidden' : '']">
    <!-- Lado izquierdo: logo + breadcrumb corto -->
    <div class="m360-left">
      <button class="m360-iconbtn" @click="$emit('toggleSidebar')" aria-label="Abrir menú">
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
      <!-- Indicador tiempo real (solo display, no botón) -->
      <span
        class="m360-chip"
        :class="realtime ? 'is-on' : 'is-off'"
        aria-label="Estado tiempo real"
      >
        <span class="dot" />
        <span class="label">{{ realtime ? 'Tiempo real' : 'Reconectando…' }}</span>
      </span>

      <!-- Menú rápido -->
      <div class="m360-menu" @keydown.esc="menu = false">
        <button
          class="m360-iconbtn"
          @click="menu = !menu"
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
          <router-link to="/monitor-builder" class="m360-item" role="menuitem">
            Añadir monitor
          </router-link>
          <router-link to="/devices" class="m360-item" role="menuitem">
            Gestionar dispositivos
          </router-link>
          <router-link to="/credentials" class="m360-item" role="menuitem">
            Credenciales
          </router-link>
          <router-link to="/channels" class="m360-item" role="menuitem">Canales</router-link>
          <router-link to="/vpns" class="m360-item" role="menuitem">VPNs</router-link>

          <!-- Logout consistente con paleta -->
          <button class="m360-item logout" role="menuitem" @click="$emit('logout')">
            Cerrar sesión
          </button>
        </div>
      </div>

      <!-- Avatar mínimo -->
      <div class="m360-avatar" :title="userEmail || 'Cuenta'" aria-label="Cuenta">
        <span>{{ (userEmail || 'U').slice(0, 1).toUpperCase() }}</span>
      </div>
    </div>
  </header>

  <!-- FAB móvil (opcional) -->
  <router-link to="/monitor-builder" class="m360-fab" aria-label="Añadir monitor">
    <svg viewBox="0 0 24 24" width="22" height="22" fill="currentColor">
      <path d="M11 11V5h2v6h6v2h-6v6h-2v-6H5v-2z" />
    </svg>
  </router-link>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, computed } from 'vue'
import { useRoute } from 'vue-router'

defineProps({
  realtime: { type: Boolean, default: true }, // solo display
  userEmail: { type: String, default: '' },
  logoSrc: { type: String, default: '/favicon-32x32.png' },
})

defineEmits(['toggleSidebar', 'logout'])

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

/* Chip realtime (solo display) */
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

/* Logout consistente (sin fondo blanco) */
.m360-item.logout {
  color: #ff9a9a;
  border-top: 1px solid rgba(255, 154, 154, 0.2);
  margin-top: 6px;
}
.m360-item.logout:hover {
  background: rgba(233, 69, 96, 0.15);
  color: #ffc7c7;
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
  .m360-fab {
    display: grid;
  }
}
</style>
