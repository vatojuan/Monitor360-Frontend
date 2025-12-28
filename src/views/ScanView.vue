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
  id: null, // ID del perfil de escaneo en DB
  network_cidr: '192.168.1.0/24',
  interface: '',
  scan_ports: '8728, 80',
  scan_mode: 'manual', // manual, notify, auto
  credential_profile_id: null,
  target_group_name: '',
  is_active: false,
})

// --- ESTADO DE RESULTADOS ---
const discoveredDevices = ref([])
const selectedDevices = ref([]) // Set de MACs seleccionadas

// --- LIFECYCLE ---
onMounted(async () => {
  isLoading.value = true
  await Promise.all([fetchMaestros(), fetchCredentialProfiles()])
  isLoading.value = false
})

// Cargar configuración cuando cambia el maestro seleccionado
watch(selectedMaestroId, async (newId) => {
  if (newId) {
    await loadScanConfig(newId)
    discoveredDevices.value = [] // Limpiar resultados anteriores
    selectedDevices.value = []
  }
})

// --- API CALLS ---

async function fetchMaestros() {
  try {
    // Necesitamos un endpoint que devuelva solo dispositivos que sean maestros (o todos y filtramos)
    const { data } = await api.get('/devices?is_maestro=true')
    // Si la API de devices no filtra, filtramos aquí:
    maestros.value = Array.isArray(data)
      ? data.filter((d) => d.is_maestro || d.maestro_id === null)
      : [] // Ajustar según tu lógica de qué es un maestro

    // Auto-seleccionar el primero si hay
    if (maestros.value.length > 0 && !selectedMaestroId.value) {
      selectedMaestroId.value = maestros.value[0].id
    }
  } catch (e) {
    console.error('Error fetching maestros:', e) // Corregido: Usamos 'e'
    showNotification('Error cargando maestros', 'error')
  }
}

async function fetchCredentialProfiles() {
  try {
    const { data } = await api.get('/credentials/profiles')
    credentialProfiles.value = data || []
  } catch (e) {
    console.error(e)
  }
}

async function loadScanConfig(maestroId) {
  try {
    // Endpoint hipotético para obtener config por maestro
    // Si no existe, usamos valores default
    const { data } = await api.get(`/discovery/config/${maestroId}`)
    if (data) {
      scanConfig.value = { ...data }
    } else {
      // Reset a defaults si no hay config guardada
      scanConfig.value = {
        id: null,
        network_cidr: '192.168.1.0/24',
        interface: '',
        scan_ports: '8728, 80',
        scan_mode: 'manual',
        credential_profile_id: null,
        target_group_name: '',
        is_active: false,
      }
    }
  } catch (e) {
    // Si da 404 es que no hay config, no es error crítico
    if (e.response && e.response.status !== 404) {
      showNotification('Error cargando configuración', 'error')
    }
  }
}

async function saveConfig() {
  if (!selectedMaestroId.value) return
  try {
    const payload = { ...scanConfig.value, maestro_id: selectedMaestroId.value }
    await api.post('/discovery/config', payload)
    showNotification('Configuración guardada', 'success')
  } catch (e) {
    console.error('Error saving config:', e) // Corregido: Usamos 'e'
    showNotification('Error al guardar configuración', 'error')
  }
}

async function runManualScan() {
  if (!selectedMaestroId.value) return
  isScanning.value = true
  discoveredDevices.value = []
  try {
    // Guardamos primero por si cambió algo
    await saveConfig()

    // Disparar escaneo
    const { data } = await api.post(`/discovery/scan/${selectedMaestroId.value}`)
    discoveredDevices.value = data || []

    if (discoveredDevices.value.length === 0) {
      showNotification('Escaneo finalizado. No se encontraron nuevos dispositivos.', 'info')
    } else {
      showNotification(`Se encontraron ${discoveredDevices.value.length} dispositivos.`, 'success')
    }
  } catch (e) {
    console.error('Error scanning:', e) // Corregido: Usamos 'e' para loguear
    showNotification(e.response?.data?.detail || 'Error durante el escaneo', 'error')
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

    await api.post('/discovery/adopt', payload)
    showNotification(`¡${devicesToAdopt.length} dispositivos adoptados correctamente!`, 'success')

    // Limpiar lista
    discoveredDevices.value = discoveredDevices.value.filter(
      (d) => !selectedDevices.value.includes(d.mac_address),
    )
    selectedDevices.value = []
  } catch (e) {
    console.error('Error adopting:', e) // Corregido: Usamos 'e'
    showNotification('Error al adoptar dispositivos', 'error')
  }
}

// --- HELPERS ---
function showNotification(msg, type) {
  notification.value = { show: true, message: msg, type }
  setTimeout(() => (notification.value.show = false), 4000)
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
    <div v-if="notification.show" :class="['notification', notification.type]">
      {{ notification.message }}
    </div>

    <div class="header">
      <h1>📡 Descubrimiento de Red</h1>
      <div class="maestro-selector">
        <label>Escaneando desde:</label>
        <select v-model="selectedMaestroId" class="maestro-select">
          <option :value="null" disabled>-- Selecciona un Maestro --</option>
          <option v-for="m in maestros" :key="m.id" :value="m.id">
            {{ m.name || m.client_name }} ({{ m.ip_address }})
          </option>
        </select>
      </div>
    </div>

    <div class="content-grid" v-if="selectedMaestroId">
      <aside class="config-panel">
        <div class="panel-section">
          <h3>🎯 Objetivo</h3>
          <div class="form-group">
            <label>Red a Escanear (CIDR)</label>
            <input
              type="text"
              v-model="scanConfig.network_cidr"
              placeholder="Ej: 192.168.88.0/24"
            />
          </div>
          <div class="form-group">
            <label>Puertos (Filtro)</label>
            <input type="text" v-model="scanConfig.scan_ports" placeholder="Ej: 8728, 80" />
            <small>Solo mostrará equipos con estos puertos abiertos.</small>
          </div>
          <div class="form-group">
            <label>Interfaz (Opcional)</label>
            <input type="text" v-model="scanConfig.interface" placeholder="Ej: ether2" />
          </div>
        </div>

        <div class="panel-section">
          <h3>🔐 Acceso</h3>
          <div class="form-group">
            <label>Perfil de Credenciales</label>
            <select v-model="scanConfig.credential_profile_id">
              <option :value="null">-- Sin credenciales (Solo Ping) --</option>
              <option v-for="p in credentialProfiles" :key="p.id" :value="p.id">
                {{ p.name }}
              </option>
            </select>
            <small>Se usarán para intentar la adopción.</small>
          </div>
        </div>

        <div class="panel-section automation-section">
          <h3>🤖 Automatización</h3>
          <div class="radio-group">
            <label class="radio-label">
              <input type="radio" v-model="scanConfig.scan_mode" value="manual" />
              <span class="radio-custom"></span>
              Manual (Off)
            </label>
            <label class="radio-label">
              <input type="radio" v-model="scanConfig.scan_mode" value="notify" />
              <span class="radio-custom"></span>
              Solo Notificar
            </label>
            <label class="radio-label">
              <input type="radio" v-model="scanConfig.scan_mode" value="auto" />
              <span class="radio-custom"></span>
              Auto-Adoptar
            </label>
          </div>
          <div class="switch-group">
            <label>Tarea Activa</label>
            <input type="checkbox" v-model="scanConfig.is_active" />
          </div>
        </div>

        <div class="panel-actions">
          <button @click="saveConfig" class="btn-save">Guardar Config</button>
          <button @click="runManualScan" class="btn-scan" :disabled="isScanning">
            {{ isScanning ? 'Escaneando...' : '🔍 Escanear Ahora' }}
          </button>
        </div>
      </aside>

      <main class="results-panel">
        <div class="results-header">
          <h3>Dispositivos Encontrados ({{ discoveredDevices.length }})</h3>
          <button v-if="selectedDevices.length > 0" @click="adoptSelected" class="btn-adopt">
            Adoptar Seleccionados ({{ selectedDevices.length }})
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
                      selectedDevices.length > 0 &&
                      selectedDevices.length === discoveredDevices.length
                    "
                  />
                </th>
                <th>IP Address</th>
                <th>MAC Address</th>
                <th>Fabricante</th>
                <th>Hostname</th>
                <th>Estado</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="discoveredDevices.length === 0 && !isScanning">
                <td colspan="6" class="empty-row">
                  {{
                    isScanning ? '...' : 'Haz clic en "Escanear Ahora" para buscar dispositivos.'
                  }}
                </td>
              </tr>
              <tr v-if="isScanning">
                <td colspan="6" class="empty-row scanning-row">
                  <span class="spinner">🌀</span> Escaneando la red {{ scanConfig.network_cidr }}...
                </td>
              </tr>
              <tr
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
                <td class="font-mono">{{ dev.ip_address }}</td>
                <td class="font-mono text-dim">{{ dev.mac_address }}</td>
                <td>{{ dev.vendor || 'Desconocido' }}</td>
                <td>{{ dev.hostname || '-' }}</td>
                <td><span class="status-badge pending">Pendiente</span></td>
              </tr>
            </tbody>
          </table>
        </div>
      </main>
    </div>

    <div v-else class="empty-state">
      <p>⚠️ No se encontraron dispositivos "Maestros" configurados.</p>
      <p>
        Debes configurar un dispositivo como Maestro (con VPN activa) para poder escanear redes
        remotas.
      </p>
    </div>
  </div>
</template>

<style scoped>
/* Layout Base */
.discovery-layout {
  padding: 1rem;
  max-width: 1600px;
  margin: 0 auto;
}
.fade-in {
  animation: fadeIn 0.4s ease-out;
}
@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: 0;
  }
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
  font-size: 1.8rem;
  color: var(--blue);
}
.maestro-selector {
  display: flex;
  align-items: center;
  gap: 1rem;
}
.maestro-select {
  padding: 0.6rem;
  border-radius: 6px;
  background-color: var(--surface-color);
  color: white;
  border: 1px solid var(--primary-color);
  min-width: 250px;
}

/* Grid Layout */
.content-grid {
  display: grid;
  grid-template-columns: 350px 1fr;
  gap: 2rem;
  align-items: start;
}

/* Config Panel */
.config-panel {
  background-color: var(--surface-color);
  border-radius: 12px;
  padding: 1.5rem;
  border: 1px solid var(--primary-color);
}
.panel-section {
  margin-bottom: 2rem;
}
.panel-section h3 {
  margin-top: 0;
  font-size: 1.1rem;
  color: var(--blue);
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  padding-bottom: 0.5rem;
  margin-bottom: 1rem;
}

.form-group {
  margin-bottom: 1rem;
}
.form-group label {
  display: block;
  margin-bottom: 0.4rem;
  font-weight: 500;
  font-size: 0.9rem;
}
.form-group input,
.form-group select {
  width: 100%;
  padding: 0.6rem;
  border-radius: 6px;
  background-color: var(--bg-color);
  border: 1px solid var(--primary-color);
  color: white;
}
.form-group small {
  color: var(--gray);
  font-size: 0.8rem;
  display: block;
  margin-top: 0.3rem;
}

.automation-section {
  background-color: rgba(0, 0, 0, 0.2);
  padding: 1rem;
  border-radius: 8px;
}
.radio-group {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  margin-bottom: 1rem;
}
.radio-label {
  display: flex;
  align-items: center;
  cursor: pointer;
  font-size: 0.9rem;
}
.radio-label input {
  margin-right: 0.5rem;
}

.panel-actions {
  display: flex;
  flex-direction: column;
  gap: 0.8rem;
}
.btn-save {
  padding: 0.8rem;
  background-color: var(--primary-color);
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-weight: bold;
}
.btn-scan {
  padding: 0.8rem;
  background-color: var(--blue);
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-weight: bold;
  font-size: 1.05rem;
  transition: background 0.2s;
}
.btn-scan:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}
.btn-scan:hover:not(:disabled) {
  background-color: #2563eb;
}

/* Results Panel */
.results-panel {
  background-color: var(--surface-color);
  border-radius: 12px;
  padding: 1.5rem;
  min-height: 500px;
  border: 1px solid var(--primary-color);
  display: flex;
  flex-direction: column;
}
.results-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}
.btn-adopt {
  background-color: var(--green);
  color: white;
  border: none;
  padding: 0.6rem 1.2rem;
  border-radius: 6px;
  cursor: pointer;
  font-weight: bold;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
}

.table-container {
  overflow-x: auto;
  flex-grow: 1;
}
.devices-table {
  width: 100%;
  border-collapse: collapse;
}
.devices-table th {
  text-align: left;
  padding: 1rem;
  border-bottom: 2px solid var(--primary-color);
  color: var(--gray);
  font-size: 0.9rem;
}
.devices-table td {
  padding: 1rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}
.devices-table tr:hover {
  background-color: rgba(255, 255, 255, 0.02);
}
.devices-table tr.selected {
  background-color: rgba(58, 130, 246, 0.1);
}

.empty-row {
  text-align: center;
  padding: 4rem !important;
  color: var(--gray);
  font-style: italic;
}
.scanning-row {
  color: var(--blue);
  font-weight: bold;
}
.spinner {
  display: inline-block;
  animation: spin 1s linear infinite;
  margin-right: 0.5rem;
}
@keyframes spin {
  100% {
    transform: rotate(360deg);
  }
}

.font-mono {
  font-family: monospace;
}
.text-dim {
  color: var(--gray);
}
.status-badge {
  padding: 0.2rem 0.6rem;
  border-radius: 4px;
  font-size: 0.75rem;
  font-weight: bold;
  text-transform: uppercase;
}
.status-badge.pending {
  background-color: #f59e0b;
  color: black;
}

/* Utils */
.notification {
  position: fixed;
  top: 90px;
  right: 20px;
  padding: 1rem 1.5rem;
  border-radius: 8px;
  color: white;
  font-weight: bold;
  z-index: 1000;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
}
.notification.success {
  background-color: var(--green);
}
.notification.error {
  background-color: var(--error-red);
}
.notification.info {
  background-color: var(--blue);
}

.empty-state {
  text-align: center;
  padding: 4rem;
  color: var(--gray);
  font-size: 1.1rem;
}
</style>
