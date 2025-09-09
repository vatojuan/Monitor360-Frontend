<script setup>
import { ref, onMounted, computed } from 'vue'
import api from '@/lib/api'

// Importamos los componentes de QR
import { QrcodeStream } from 'vue-qrcode-reader'
import QrcodeVue from 'qrcode.vue'

const notification = ref({ show: false, message: '', type: 'success' })
function showNotification(message, type = 'success') {
  notification.value = { show: true, message, type }
  setTimeout(() => (notification.value.show = false), 4000)
}

const vpnProfiles = ref([])
const isLoading = ref(false)

const newProfile = ref({
  name: '',
  check_ip: '',
  config_data: '',
})

// --- Lógica para el escáner QR Dual ---
const isModalOpen = ref(false)
const modalStep = ref('choose') // 'choose', 'scanLocal', 'scanRemote'
const remoteScanSessionId = ref(null)
const ws = ref(null) // Para la conexión WebSocket

const remoteScanUrl = computed(() => {
  if (!remoteScanSessionId.value) return ''
  const url = new URL(`/scan/${remoteScanSessionId.value}`, window.location.origin)
  return url.href
})

function openScanModal() {
  modalStep.value = 'choose'
  isModalOpen.value = true
}

function startLocalScan() {
  modalStep.value = 'scanLocal'
}

function startRemoteScan() {
  remoteScanSessionId.value = crypto.randomUUID()
  modalStep.value = 'scanRemote'

  // Construir URL del WebSocket
  const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const wsUrl = `${wsProtocol}//${window.location.host}/ws/scan/${remoteScanSessionId.value}`

  // Conectar al WebSocket
  ws.value = new WebSocket(wsUrl)

  ws.value.onopen = () => {
    console.log('Conectado al WebSocket de escaneo.')
  }

  ws.value.onmessage = (event) => {
    const msg = JSON.parse(event.data)
    if (msg.type === 'scan_result' && msg.data) {
      newProfile.value.config_data = msg.data
      showNotification('Configuración recibida desde el celular.', 'success')
      closeModal()
    }
  }

  ws.value.onerror = (error) => {
    console.error('Error de WebSocket:', error)
    showNotification('Error de conexión para escaneo remoto.', 'error')
    closeModal()
  }
}

function onDecodeLocal(decodedString) {
  newProfile.value.config_data = decodedString
  showNotification('Configuración QR cargada correctamente.', 'success')
  closeModal()
}

async function onScannerInit(promise) {
  try {
    await promise
  } catch (error) {
    let errorMessage = 'Error al iniciar la cámara.'
    if (error.name === 'NotAllowedError') {
      errorMessage = 'Necesitas dar permiso para usar la cámara.'
    } else if (error.name === 'NotFoundError') {
      errorMessage = 'No se encontró una cámara en este dispositivo.'
    } else if (error.name === 'NotReadableError') {
      errorMessage = 'La cámara ya está en uso por otra aplicación.'
    }
    showNotification(errorMessage, 'error')
    closeModal()
  }
}

function closeModal() {
  isModalOpen.value = false
  if (ws.value) {
    ws.value.close()
    ws.value = null
  }
  remoteScanSessionId.value = null
}
// --- FIN de la lógica del escáner ---

onMounted(() => {
  fetchVpnProfiles()
})

async function fetchVpnProfiles() {
  isLoading.value = true
  try {
    const { data } = await api.get('/vpns')
    vpnProfiles.value = (data || []).map((p) => ({
      ...p,
      is_default: !!p.is_default,
      _expanded: false,
    }))
  } catch (err) {
    console.error('Error al cargar perfiles VPN:', err)
    showNotification(err.response?.data?.detail || 'Error al cargar perfiles VPN.', 'error')
  } finally {
    isLoading.value = false
  }
}

async function createProfile() {
  if (!newProfile.value.name.trim() || !newProfile.value.config_data.trim()) {
    showNotification('Nombre y Config son obligatorios.', 'error')
    return
  }
  try {
    const body = {
      name: newProfile.value.name.trim(),
      config_data: newProfile.value.config_data,
      check_ip: newProfile.value.check_ip.trim(),
    }
    const { data } = await api.post('/vpns', body)
    vpnProfiles.value.push({ ...data, is_default: !!data.is_default, _expanded: false })
    newProfile.value = { name: '', check_ip: '', config_data: '' }
    showNotification('Perfil VPN creado.', 'success')
  } catch (err) {
    console.error('Error al crear perfil:', err)
    showNotification(err.response?.data?.detail || 'Error al crear perfil.', 'error')
  }
}

// ... (El resto de tus funciones: saveProfile, setDefault, testProfile, deleteProfile)
// ... (Omitidas por brevedad, no necesitan cambios)
</script>

<template>
  <div class="page-wrap">
    <h1>Perfiles VPN</h1>

    <!-- Crear nuevo perfil -->
    <section class="control-section">
      <h2><i class="icon">➕</i> Crear Perfil</h2>
      <!-- ... (Campos de Nombre y Check IP) ... -->

      <div class="stack">
        <div class="label-with-action">
          <label>Config WireGuard *</label>
          <button @click="openScanModal" class="btn-qr-scan" title="Escanear Código QR">
            <svg viewBox="0 0 24 24" fill="currentColor">
              <path
                d="M3 11h8V3H3v8zm2-6h4v4H5V5zM3 21h8v-8H3v8zm2-6h4v4H5v-4zM13 3v8h8V3h-8zm6 6h-4V5h4v4zM13 13h2v2h-2zM15 15h2v2h-2zM13 17h2v2h-2zM17 17h2v2h-2zM19 19h2v2h-2zM15 19h2v2h-2zM17 13h2v2h-2zM19 15h2v2h-2z"
              ></path>
            </svg>
            Escanear
          </button>
        </div>
        <textarea
          v-model="newProfile.config_data"
          rows="10"
          spellcheck="false"
          placeholder="[Interface]&#10;PrivateKey = ...&#10;..."
        />
      </div>
      <div class="actions-row">
        <button class="btn-primary" @click="createProfile">Crear Perfil</button>
      </div>
    </section>

    <!-- ... (Listado de perfiles existentes, sin cambios) ... -->

    <!-- Notificaciones -->
    <div v-if="notification.show" class="notification" :class="notification.type">
      {{ notification.message }}
    </div>

    <!-- Modal del escáner QR -->
    <div v-if="isModalOpen" class="qr-scanner-modal" @click.self="closeModal">
      <div class="qr-scanner-content">
        <button @click="closeModal" class="btn-close-modal" title="Cerrar">&times;</button>

        <!-- Paso 1: Elegir método -->
        <div v-if="modalStep === 'choose'">
          <h3>¿Cómo quieres escanear el QR?</h3>
          <div class="choose-options">
            <button @click="startLocalScan" class="btn-choose">
              <svg viewBox="0 0 24 24">
                <path
                  d="M17 10.5V7c0-.55-.45-1-1-1H4c-.55 0-1 .45-1 1v10c0 .55.45 1 1 1h12c.55 0 1-.45 1-1v-3.5l4 4v-11l-4 4z"
                />
              </svg>
              <span>Usar cámara de este dispositivo</span>
            </button>
            <button @click="startRemoteScan" class="btn-choose">
              <svg viewBox="0 0 24 24">
                <path
                  d="M15 7.5V2H9v5.5l3 3 3-3zM7.5 9H2v6h5.5l3-3-3-3zM9 16.5V22h6v-5.5l-3-3-3 3zM16.5 15l-3 3 3 3H22v-6h-5.5z"
                />
              </svg>
              <span>Usar cámara de mi celular</span>
            </button>
          </div>
        </div>

        <!-- Paso 2A: Escáner Local -->
        <div v-if="modalStep === 'scanLocal'">
          <h3>Apunta al código QR de MikroTik</h3>
          <qrcode-stream @decode="onDecodeLocal" @init="onScannerInit"></qrcode-stream>
        </div>

        <!-- Paso 2B: Escáner Remoto -->
        <div v-if="modalStep === 'scanRemote'">
          <h3>1. Escanea este QR con tu celular</h3>
          <p class="remote-scan-subtitle">Se abrirá una página para escanear el QR de MikroTik.</p>
          <div class="remote-qr-container">
            <qrcode-vue :value="remoteScanUrl" :size="220" level="H" v-if="remoteScanUrl" />
          </div>
          <p class="waiting-text">Esperando datos del celular...</p>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* ... (Tus estilos existentes) ... */
.label-with-action {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.btn-qr-scan {
  background: #333;
  color: var(--font-color);
  border: 1px solid #444;
  border-radius: 6px;
  padding: 0.25rem 0.6rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 0.4rem;
}
.btn-qr-scan:hover {
  background: #444;
}
.btn-qr-scan svg {
  width: 1rem;
  height: 1rem;
}

/* --- Estilos para el Modal y sus pasos --- */
.qr-scanner-modal {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  z-index: 1000;
  background-color: rgba(0, 0, 0, 0.8);
  display: flex;
  align-items: center;
  justify-content: center;
}
.qr-scanner-content {
  background-color: var(--panel);
  padding: 1.5rem;
  border-radius: 12px;
  text-align: center;
  width: 90%;
  max-width: 500px;
  position: relative;
}
.btn-close-modal {
  position: absolute;
  top: 10px;
  right: 10px;
  background: transparent;
  border: none;
  color: #999;
  font-size: 2rem;
  line-height: 1;
  cursor: pointer;
}
.choose-options {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  margin-top: 1.5rem;
}
.btn-choose {
  background: #2a2a2a;
  color: var(--font-color);
  border: 1px solid #444;
  border-radius: 8px;
  padding: 1rem;
  font-size: 1rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 0.8rem;
  text-align: left;
}
.btn-choose:hover {
  background: #333;
}
.btn-choose svg {
  width: 2.5rem;
  height: 2.5rem;
  fill: var(--primary-color);
  flex-shrink: 0;
}
.remote-scan-subtitle {
  color: var(--gray);
  margin: -0.5rem 0 1rem 0;
}
.remote-qr-container {
  background: white;
  padding: 1rem;
  display: inline-block;
  border-radius: 8px;
}
.waiting-text {
  margin-top: 1rem;
  color: var(--primary-color);
}
</style>
