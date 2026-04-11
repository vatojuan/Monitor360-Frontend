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
  overflow-y: auto;
  overflow-x: hidden;
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
/* ============================================================
   REGLAS GLOBALES DE RESPONSIVIDAD MÓVIL
   Se inyectan desde AppLayout y aplican a TODAS las vistas.
   Breakpoint principal: 820px
   ============================================================ */
@media (max-width: 820px) {

  /* --- GRIDS: todos colapsan a 1 columna --- */
  .dashboard-grid,
  .general-config-grid,
  .tools-grid,
  .credentials-layout,
  .profiles-grid,
  .content-grid,
  .create-form-grid,
  .grid-2,
  .config-grid,
  .account-grid {
    grid-template-columns: 1fr !important;
  }

  /* Los ítems del grid no desbordan su celda */
  .monitor-card-wrapper,
  .monitor-card {
    min-width: 0;
    max-width: 100%;
    box-sizing: border-box;
  }

  /* --- SCROLL AREAS: sin desborde horizontal --- */
  .scroll-area {
    padding: 1rem !important;
    overflow-x: hidden !important;
  }

  /* --- CONTENEDORES DE PÁGINA sin ancho fijo --- */
  .page-wrap,
  .detail-view,
  .account-container {
    padding: 0.75rem !important;
    box-sizing: border-box;
  }

  /* --- HEADERS DE SECCIÓN: apilados en columna --- */
  .content-header {
    padding: 0.75rem 1rem !important;
    height: auto !important;
    min-height: 50px;
    flex-direction: column;
    align-items: flex-start !important;
    gap: 8px;
  }

  /* --- BOTONES: envuelven si no caben en una fila --- */
  .header-actions {
    width: 100%;
    flex-wrap: wrap !important;
    gap: 0.4rem !important;
  }

  /* --- TABS: envuelven si no caben --- */
  .tabs {
    flex-wrap: wrap !important;
    gap: 0.4rem !important;
  }

  /* --- FILTROS Y ACCIONES EN FILA: envuelven --- */
  .filter-bar {
    flex-direction: column !important;
    align-items: stretch !important;
    gap: 0.5rem !important;
  }

  .filter-controls,
  .toggle-group,
  .bulk-actions,
  .bulk-actions-bar,
  .manage-header {
    flex-wrap: wrap !important;
    gap: 0.4rem !important;
  }

  /* Los botones dentro de grupos tienen tamaño mínimo usable */
  .toggle-group button,
  .bulk-actions button,
  .header-actions button,
  .header-actions a {
    white-space: nowrap;
    font-size: 0.82rem;
    padding: 0.4rem 0.7rem !important;
  }

  /* --- TABLAS: scroll horizontal --- */
  .table-responsive,
  .history-table-wrap {
    overflow-x: auto !important;
    -webkit-overflow-scrolling: touch;
  }

  /* --- MODALES: ancho completo --- */
  .modal-content,
  .modal-content.large-modal,
  .large-modal {
    width: 95vw !important;
    max-width: 95vw !important;
    padding: 1rem !important;
    margin: 0 auto;
    box-sizing: border-box;
  }

  /* --- FORMULARIOS: sin ancho fijo --- */
  .form-layout {
    max-width: 100% !important;
  }

  /* Inputs y selects no desbordan */
  input, select, textarea {
    max-width: 100%;
    box-sizing: border-box;
  }
}
</style>