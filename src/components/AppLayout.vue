<script setup>
import { ref, onMounted, onUnmounted, provide } from 'vue'
import TopbarPro from '@/components/TopbarPro.vue'

// Recibimos los datos desde App.vue para pasarlos al Topbar
const props = defineProps({
  realtime: { type: Boolean, default: false },
  uptime: { type: String, default: '00:00:00' },
  userEmail: { type: String, default: '' },
  userAvatar: { type: String, default: '' }
})

const emit = defineEmits(['logout'])

// Estado global del Layout
const isSidebarOpen = ref(false)
const isMobile = ref(false)

const toggleSidebar = () => {
  isSidebarOpen.value = !isSidebarOpen.value
}

const closeSidebar = () => {
  isSidebarOpen.value = false
}

// Detector de pantalla para Mobile-First
const checkScreen = () => {
  isMobile.value = window.innerWidth <= 820 // Coincide con el breakpoint de tu Topbar
  if (!isMobile.value) {
    isSidebarOpen.value = false // Auto-cierra el drawer si volvemos a PC
  }
}

onMounted(() => {
  checkScreen()
  window.addEventListener('resize', checkScreen, { passive: true })
})

onUnmounted(() => {
  window.removeEventListener('resize', checkScreen)
})

// Magia de Vue: Proveemos este estado a cualquier vista que viva dentro del RouterView
provide('appLayout', {
  isSidebarOpen,
  isMobile,
  closeSidebar
})
</script>

<template>
  <div class="app-layout" :class="{ 'is-mobile': isMobile }">
    <TopbarPro
      :realtime="realtime"
      :uptime="uptime"
      :userEmail="userEmail"
      :userAvatar="userAvatar"
      @logout="emit('logout')"
      @toggleSidebar="toggleSidebar"
    />

    <div class="layout-body">
      <transition name="fade">
        <div
          v-if="isMobile && isSidebarOpen"
          class="sidebar-overlay"
          @click="closeSidebar"
        ></div>
      </transition>

      <div class="main-router-container">
        <slot /> </div>
    </div>
  </div>
</template>

<style scoped>
/* Estructura base del Layout */
.app-layout {
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden; /* Evita scroll doble */
}

.layout-body {
  position: relative;
  display: flex;
  flex-grow: 1;
  overflow: hidden;
  height: calc(100vh - 44px); /* Descuenta la altura del TopbarPro */
}

.main-router-container {
  flex-grow: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  position: relative;
  width: 100%;
}

/* Fondo oscuro para celulares cuando el Drawer está abierto */
.sidebar-overlay {
  position: fixed;
  inset: 0;
  top: 44px; /* Empieza debajo del Topbar */
  background: rgba(0, 0, 0, 0.6);
  backdrop-filter: blur(4px);
  z-index: 90; /* Queda debajo del menú lateral pero encima del contenido */
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>

<style>
/* REGLAS CSS MÁGICAS GLOBALES 
   Al inyectar esto desde el Layout, reparamos automáticamente 
   el desorden visual de todas las vistas en celular sin tener que tocarlas una por una.
*/
@media (max-width: 820px) {
  /* Forzamos que las grillas de todas las páginas pasen a 1 sola columna */
  .dashboard-grid, 
  .general-config-grid, 
  .tools-grid {
    grid-template-columns: 1fr !important;
  }

  /* Reducimos los márgenes enormes en pantallas chicas */
  .scroll-area {
    padding: 1rem !important;
  }

  .content-header {
    padding: 0 1rem !important;
    height: auto !important;
    min-height: 60px;
    flex-direction: column;
    align-items: flex-start !important;
    justify-content: center;
    gap: 10px;
    padding-top: 10px !important;
    padding-bottom: 10px !important;
  }

  .header-actions {
    width: 100%;
    justify-content: space-between;
  }
}
</style>