<script setup>
import { ref, onMounted, watch } from 'vue'
import api from '@/lib/api'

// --- ESTADO GLOBAL ---
const maestros = ref([])
const credentialProfiles = ref([])
const notification = ref({ show: false, message: '', type: 'success' })
const isLoading = ref(false)
const isScanning = ref(false)

// --- ESTADO DE CONFIGURACIÓN ---
const selectedMaestroId = ref(null)
const scanConfig = ref({
  id: null,
  network_cidr: '192.168.88.0/24',
  interface: '', // Importante para v7
  scan_ports: '8728, 80',
  scan_mode: 'manual',
  credential_profile_id: null,
  target_group_name: '',
  is_active: false,
})

// --- ESTADO DE RESULTADOS ---
const discoveredDevices = ref([])
const selectedDevices = ref([])

// --- LIFECYCLE ---
onMounted(async () => {
  isLoading.value = true
  await Promise.all([fetchMaestros(), fetchCredentialProfiles()])
  isLoading.value = false
})

watch(selectedMaestroId, async (newId) => {
  if (newId) {
    await loadScanConfig(newId)
    discoveredDevices.value = []
    selectedDevices.value = []
  }
})

// --- API CALLS ---

async function fetchMaestros() {
  try {
    const { data } = await api.get('/devices?is_maestro=true')
    maestros.value = Array.isArray(data) ? data : []

    // Auto-seleccionar el primero
    if (maestros.value.length > 0 && !selectedMaestroId.value) {
      selectedMaestroId.value = maestros.value[0].id
    }
  } catch (e) {
    console.error('Error fetching maestros:', e)
    showNotification('Error cargando lista de maestros', 'error')
  }
}

async function fetchCredentialProfiles() {
  try {
    const { data } = await api.get('/credentials/profiles')
    credentialProfiles.value = data || []
  } catch (e) {
    console.error('Error fetching credentials:', e)
  }
}

async function loadScanConfig(maestroId) {
  try {
    const { data } = await api.get(`/discovery/config/${maestroId}`)
    if (data) {
      scanConfig.value = { ...data }
      // Asegurar que interface no sea null para el input
      if (!scanConfig.value.interface) scanConfig.value.interface = ''
    } else {
      // Defaults
      scanConfig.value = {
        id: null,
        network_cidr: '192.168.88.0/24',
        interface: '',
        scan_ports: '8728, 80',
        scan_mode: 'manual',
        credential_profile_id: null,
        target_group_name: '',
        is_active: false,
      }
    }
  } catch (e) {
    if (e.response?.status !== 404) {
      showNotification('Error cargando configuración', 'error')
    }
  }
}

async function saveConfig() {
  if (!selectedMaestroId.value) return
  try {
    // Convertir string vacío a null si es necesario, o enviarlo vacío
    const payload = {
      ...scanConfig.value,
      maestro_id: selectedMaestroId.value,
      interface: scanConfig.value.interface || null,
    }
    await api.post('/discovery/config', payload)
    showNotification('Configuración guardada', 'success')
  } catch (e) {
    console.error(e)
    showNotification('Error guardando configuración', 'error')
  }
}

async function runManualScan() {
  if (!selectedMaestroId.value) return

  isScanning.value = true
  discoveredDevices.value = [] // Limpiar tabla
  selectedDevices.value = [] // Limpiar selección

  try {
    // 1. Guardar configuración actual antes de escanear
    await saveConfig()

    // 2. Ejecutar Scan
    const { data } = await api.post(`/discovery/scan/${selectedMaestroId.value}`)
    discoveredDevices.value = data || []

    if (discoveredDevices.value.length === 0) {
      showNotification('Escaneo finalizado sin resultados.', 'info')
    } else {
      showNotification(`¡${discoveredDevices.value.length} dispositivos encontrados!`, 'success')
    }
  } catch (e) {
    console.error('Scan error:', e)
    // Mostrar el mensaje específico del backend (ej: Fallo Mikrotik...)
    const errorMsg = e.response?.data?.detail || 'Error desconocido durante el escaneo'
    showNotification(errorMsg, 'error')
  } finally {
    isScanning.value = false
  }
}

async function adoptSelected() {
  if (selectedDevices.value.length === 0) return

  try {
    const devicesToAdopt = discoveredDevices.value.filter((d) =>
      selectedDevices.value.includes(d.mac_address),
    )

    const payload = {
      maestro_id: selectedMaestroId.value,
      credential_profile_id: scanConfig.value.credential_profile_id,
      devices: devicesToAdopt,
    }

    const { data } = await api.post('/discovery/adopt', payload)

    showNotification(`Adoptados: ${data.adopted}`, 'success')

    // Quitar de la lista los adoptados
    discoveredDevices.value = discoveredDevices.value.filter(
      (d) => !selectedDevices.value.includes(d.mac_address),
    )
    selectedDevices.value = []
  } catch (e) {
    console.error(e)
    showNotification('Error durante la adopción', 'error')
  }
}

// --- UTILIDADES ---
function showNotification(msg, type) {
  notification.value = { show: true, message: msg, type }
  setTimeout(() => (notification.value.show = false), 5000) // 5 segundos para leer errores largos
}

function toggleSelection(mac) {
  if (selectedDevices.value.includes(mac)) {
    selectedDevices.value = selectedDevices.value.filter((m) => m !== mac)
  } else {
    selectedDevices.value.push(mac)
  }
}

function selectAll() {
  if (selectedDevices.value.length === discoveredDevices.value.length) {
    selectedDevices.value = []
  } else {
    selectedDevices.value = discoveredDevices.value.map((d) => d.mac_address)
  }
}
</script>

<template>
  <div class="discovery-layout fade-in">
    <transition name="slide-fade">
      <div v-if="notification.show" :class="['notification', notification.type]">
        {{ notification.message }}
      </div>
    </transition>

    <div class="header">
      <h1>📡 Descubrimiento de Red</h1>
      <div class="maestro-selector">
        <label>Router Maestro:</label>
        <select v-model="selectedMaestroId" class="maestro-select" :disabled="isScanning">
          <option :value="null" disabled>-- Selecciona --</option>
          <option v-for="m in maestros" :key="m.id" :value="m.id">
            {{ m.client_name || m.ip_address }} ({{ m.ip_address }})
          </option>
        </select>
      </div>
    </div>

    <div class="content-grid" v-if="selectedMaestroId">
      <aside class="config-panel">
        <div class="panel-section">
          <h3>🎯 Configuración de Escaneo</h3>

          <div class="form-group">
            <label>Red (CIDR)</label>
            <input
              type="text"
              v-model="scanConfig.network_cidr"
              placeholder="Ej: 192.168.88.0/24"
              :disabled="isScanning"
            />
          </div>

          <div class="form-group">
            <label>Interfaz (Opcional pero Recomendado)</label>
            <input
              type="text"
              v-model="scanConfig.interface"
              placeholder="Ej: bridge, ether1 (Vacío = auto)"
              :disabled="isScanning"
            />
            <small>Si falla, especifica la interfaz exacta.</small>
          </div>

          <div class="form-group">
            <label>Puertos (Filtro)</label>
            <input
              type="text"
              v-model="scanConfig.scan_ports"
              placeholder="Ej: 8728, 80"
              :disabled="isScanning"
            />
          </div>
        </div>

        <div class="panel-section">
          <h3>🔐 Adopción</h3>
          <div class="form-group">
            <label>Perfil de Credenciales</label>
            <select v-model="scanConfig.credential_profile_id" :disabled="isScanning">
              <option :value="null">-- Ninguno --</option>
              <option v-for="p in credentialProfiles" :key="p.id" :value="p.id">
                {{ p.name }}
              </option>
            </select>
          </div>
        </div>

        <div class="panel-actions">
          <button @click="runManualScan" class="btn-scan" :disabled="isScanning">
            <span v-if="isScanning" class="spinner-small"></span>
            {{ isScanning ? 'Escaneando...' : '🔍 Iniciar Escaneo' }}
          </button>
        </div>
      </aside>

      <main class="results-panel">
        <div class="results-header">
          <h3>Resultados ({{ discoveredDevices.length }})</h3>
          <button v-if="selectedDevices.length > 0" @click="adoptSelected" class="btn-adopt">
            Adoptar ({{ selectedDevices.length }})
          </button>
        </div>

        <div class="table-container">
          <table class="devices-table">
            <thead>
              <tr>
                <th width="40">
                  <input
                    type="checkbox"
                    @change="selectAll"
                    :checked="
                      discoveredDevices.length > 0 &&
                      selectedDevices.length === discoveredDevices.length
                    "
                    :disabled="discoveredDevices.length === 0"
                  />
                </th>
                <th>IP Address</th>
                <th>MAC Address</th>
                <th>Hostname / DNS</th>
                <th>Fabricante</th>
                <th>Estado</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="isScanning">
                <td colspan="6" class="state-row scanning">
                  <div class="spinner"></div>
                  <p>
                    Escaneando la red {{ scanConfig.network_cidr }} via
                    {{ scanConfig.interface || 'auto' }}...
                  </p>
                  <small>Esto puede tardar unos segundos.</small>
                </td>
              </tr>

              <tr v-else-if="discoveredDevices.length === 0">
                <td colspan="6" class="state-row empty">
                  No hay dispositivos pendientes. Configura los parámetros y pulsa "Iniciar
                  Escaneo".
                </td>
              </tr>

              <tr
                v-else
                v-for="dev in discoveredDevices"
                :key="dev.mac_address"
                :class="{ selected: selectedDevices.includes(dev.mac_address) }"
                @click="toggleSelection(dev.mac_address)"
              >
                <td>
                  <input
                    type="checkbox"
                    :checked="selectedDevices.includes(dev.mac_address)"
                    @click.stop="toggleSelection(dev.mac_address)"
                  />
                </td>
                <td class="font-mono text-highlight">{{ dev.ip_address }}</td>
                <td class="font-mono text-dim">{{ dev.mac_address }}</td>
                <td>{{ dev.hostname || dev.dns || '-' }}</td>
                <td>{{ dev.vendor || 'Desconocido' }}</td>
                <td><span class="status-badge pending">Pendiente</span></td>
              </tr>
            </tbody>
          </table>
        </div>
      </main>
    </div>

    <div v-else class="empty-state">
      <h2>⚠️ Selecciona un Maestro</h2>
      <p>Debes seleccionar un router con la sesión VPN activa para poder escanear su red local.</p>
    </div>
  </div>
</template>

<style scoped>
/* Variables locales para facilitar cambios */
:root {
  --primary: #3b82f6;
  --bg-panel: #1e1e1e;
  --border: #333;
}

.discovery-layout {
  padding: 1.5rem;
  max-width: 1600px;
  margin: 0 auto;
  color: #e5e5e5;
}

/* Header */
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 2rem;
  padding-bottom: 1rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}
.header h1 {
  margin: 0;
  color: var(--primary);
}

.maestro-select {
  padding: 0.6rem 1rem;
  background: #2d2d2d;
  border: 1px solid #444;
  color: white;
  border-radius: 6px;
  min-width: 300px;
}

/* Grid */
.content-grid {
  display: grid;
  grid-template-columns: 320px 1fr;
  gap: 1.5rem;
  align-items: start;
}

/* Paneles */
.config-panel,
.results-panel {
  background: #1a1a1a;
  border: 1px solid #333;
  border-radius: 8px;
  padding: 1.5rem;
}

.panel-section {
  margin-bottom: 2rem;
}
.panel-section h3 {
  margin-top: 0;
  font-size: 1rem;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: #888;
  border-bottom: 1px solid #333;
  padding-bottom: 0.5rem;
  margin-bottom: 1rem;
}

/* Formularios */
.form-group {
  margin-bottom: 1rem;
}
.form-group label {
  display: block;
  font-size: 0.85rem;
  margin-bottom: 0.4rem;
  color: #ccc;
}
.form-group input,
.form-group select {
  width: 100%;
  padding: 0.6rem;
  background: #252525;
  border: 1px solid #444;
  color: white;
  border-radius: 4px;
}
.form-group input:focus {
  border-color: var(--primary);
  outline: none;
}
.form-group small {
  display: block;
  margin-top: 4px;
  font-size: 0.75rem;
  color: #666;
}

/* Botones */
.btn-scan {
  width: 100%;
  padding: 0.8rem;
  background: var(--primary);
  color: white;
  border: none;
  border-radius: 6px;
  font-weight: bold;
  cursor: pointer;
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 0.5rem;
}
.btn-scan:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.btn-adopt {
  background: #10b981;
  color: white;
  border: none;
  padding: 0.5rem 1rem;
  border-radius: 4px;
  cursor: pointer;
  font-weight: bold;
}

/* Tabla */
.table-container {
  overflow-x: auto;
}
.devices-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.9rem;
}
.devices-table th {
  text-align: left;
  padding: 0.8rem;
  border-bottom: 2px solid #444;
  color: #aaa;
}
.devices-table td {
  padding: 0.8rem;
  border-bottom: 1px solid #333;
}
.devices-table tr:hover {
  background: #252525;
  cursor: pointer;
}
.devices-table tr.selected {
  background: rgba(59, 130, 246, 0.15);
}

/* Estados de Tabla */
.state-row {
  text-align: center;
  padding: 4rem !important;
  color: #777;
}
.state-row.scanning {
  color: var(--primary);
}

/* Tipografía */
.font-mono {
  font-family: 'Consolas', monospace;
}
.text-highlight {
  color: #fff;
  font-weight: 500;
}
.text-dim {
  color: #777;
}
.status-badge {
  background: #f59e0b;
  color: #000;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 0.7rem;
  font-weight: bold;
  text-transform: uppercase;
}

/* Spinner */
.spinner {
  width: 24px;
  height: 24px;
  border: 3px solid rgba(59, 130, 246, 0.3);
  border-radius: 50%;
  border-top-color: var(--primary);
  animation: spin 1s linear infinite;
  margin: 0 auto 1rem;
}
.spinner-small {
  width: 16px;
  height: 16px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

/* Notificaciones */
.notification {
  position: fixed;
  top: 80px;
  right: 20px;
  padding: 1rem 1.5rem;
  border-radius: 6px;
  color: white;
  font-weight: 600;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
  z-index: 9999;
}
.notification.success {
  background: #10b981;
}
.notification.error {
  background: #ef4444;
}
.notification.info {
  background: #3b82f6;
}

/* Transiciones */
.slide-fade-enter-active,
.slide-fade-leave-active {
  transition: all 0.3s ease;
}
.slide-fade-enter-from,
.slide-fade-leave-to {
  transform: translateX(20px);
  opacity: 0;
}
</style>
