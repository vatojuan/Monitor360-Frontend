<script setup>
import { ref, onMounted } from 'vue'
import api from '@/lib/api'

// --- ESTADO GLOBAL ---
const activeTab = ref('inbox')
const isLoading = ref(false)
const isScanning = ref(false)
const notification = ref({ show: false, message: '', type: 'success' })

// --- DATOS ---
const maestros = ref([])
const credentialProfiles = ref([])
const pendingDevices = ref([])
const scanProfiles = ref([])

// --- ESTADO INBOX ---
const selectedPending = ref([])
const adoptCredentialId = ref(null)

// --- ESTADO CONFIGURACIÓN ---
const scanConfig = ref({
  maestro_id: '',
  network_cidr: '192.168.88.0/24',
  interface: '',
  scan_ports: '8728, 80',
  scan_mode: 'manual',
  credential_profile_id: null,
  is_active: false,
})

// --- LIFECYCLE ---
onMounted(async () => {
  await loadGlobalData()
})

async function loadGlobalData() {
  isLoading.value = true
  try {
    await Promise.all([
      fetchMaestros(),
      fetchCredentialProfiles(),
      fetchPendingDevices(),
      fetchScanProfiles(),
    ])
  } catch (e) {
    console.error(e)
    showNotification('Error cargando datos iniciales', 'error')
  } finally {
    isLoading.value = false
  }
}

// --- API CALLS ---
async function fetchMaestros() {
  const { data } = await api.get('/devices?is_maestro=true')
  maestros.value = data || []
}

async function fetchCredentialProfiles() {
  const { data } = await api.get('/credentials/profiles')
  credentialProfiles.value = data || []
}

async function fetchPendingDevices() {
  const { data } = await api.get('/discovery/pending')
  pendingDevices.value = data || []
}

async function fetchScanProfiles() {
  try {
    const { data } = await api.get('/discovery/profiles')
    scanProfiles.value = data || []
  } catch (e) {
    console.warn('No se pudieron cargar perfiles', e)
  }
}

// --- ACCIONES ---
async function runScan() {
  if (!scanConfig.value.maestro_id) return showNotification('Selecciona un Router Maestro', 'error')
  if (!scanConfig.value.interface || scanConfig.value.interface.trim() === '') {
    return showNotification('⚠️ La Interfaz es OBLIGATORIA (Ej: ether1, bridge)', 'error')
  }

  isScanning.value = true
  try {
    const payload = { ...scanConfig.value }
    await api.post('/discovery/config', payload)
    const { data } = await api.post(`/discovery/scan/${scanConfig.value.maestro_id}`)

    const count = data.length
    if (count > 0) {
      showNotification(`✅ Escaneo completado. ${count} nuevos en Bandeja.`, 'success')
      await fetchPendingDevices()
      activeTab.value = 'inbox'
    } else {
      showNotification('Escaneo completado. No se encontraron nuevos.', 'info')
    }
    await fetchScanProfiles()
  } catch (e) {
    console.error(e)
    showNotification(e.response?.data?.detail || 'Error durante el escaneo', 'error')
  } finally {
    isScanning.value = false
  }
}

async function adoptSelected() {
  if (selectedPending.value.length === 0) return
  try {
    const devicesToAdopt = pendingDevices.value.filter((d) =>
      selectedPending.value.includes(d.mac_address),
    )
    const payload = {
      maestro_id: devicesToAdopt[0].maestro_id,
      credential_profile_id: adoptCredentialId.value,
      devices: devicesToAdopt,
      naming_strategy: 'hostname',
    }
    const { data } = await api.post('/discovery/adopt', payload)
    if (data.adopted > 0) showNotification(`¡${data.adopted} dispositivos adoptados!`, 'success')
    selectedPending.value = []
    await fetchPendingDevices()
  } catch (e) {
    console.error(e)
    showNotification('Error al adoptar dispositivos', 'error')
  }
}

async function deletePending(mac) {
  if (!confirm('¿Descartar este dispositivo?')) return
  try {
    await api.delete(`/discovery/pending/${mac}`)
    await fetchPendingDevices()
    showNotification('Dispositivo descartado', 'success')
  } catch (e) {
    console.error(e)
    showNotification('Error al eliminar', 'error')
  }
}

// --- UTILIDADES ---
function showNotification(msg, type) {
  notification.value = { show: true, message: msg, type }
  setTimeout(() => (notification.value.show = false), 5000)
}

function toggleSelection(mac) {
  if (selectedPending.value.includes(mac)) {
    selectedPending.value = selectedPending.value.filter((m) => m !== mac)
  } else {
    selectedPending.value.push(mac)
  }
}

function selectAll() {
  if (selectedPending.value.length === pendingDevices.value.length) {
    selectedPending.value = []
  } else {
    selectedPending.value = pendingDevices.value.map((d) => d.mac_address)
  }
}

function getMaestroName(id) {
  const m = maestros.value.find((x) => x.id === id)
  return m ? m.name || m.client_name || m.ip_address : 'Desconocido'
}
</script>

<template>
  <div class="discovery-layout fade-in">
    <div v-if="notification.show" :class="['notification', notification.type]">
      {{ notification.message }}
    </div>

    <div class="header">
      <div class="title-block">
        <h1>📡 Centro de Descubrimiento</h1>
        <p class="subtitle">Escanea, clasifica y adopta dispositivos en tu red.</p>
      </div>
      <div class="tabs">
        <button :class="{ active: activeTab === 'inbox' }" @click="activeTab = 'inbox'">
          📨 Bandeja de Entrada
          <span v-if="pendingDevices.length">({{ pendingDevices.length }})</span>
        </button>
        <button :class="{ active: activeTab === 'scanners' }" @click="activeTab = 'scanners'">
          ⚙️ Motores de Escaneo
        </button>
      </div>
    </div>

    <div v-if="activeTab === 'inbox'" class="content-panel fade-in">
      <div class="toolbar">
        <div class="toolbar-left">
          <span class="selection-count" v-if="selectedPending.length > 0">
            {{ selectedPending.length }} seleccionados
          </span>
          <span class="selection-count" v-else>Selecciona para adoptar</span>
        </div>
        <div class="toolbar-right">
          <div class="adopt-control">
            <select v-model="adoptCredentialId" :disabled="selectedPending.length === 0">
              <option :value="null">Sin Credenciales (Solo Ping)</option>
              <option v-for="p in credentialProfiles" :key="p.id" :value="p.id">
                🔐 {{ p.name }}
              </option>
            </select>
            <button
              @click="adoptSelected"
              class="btn-primary"
              :disabled="selectedPending.length === 0"
            >
              ✅ Adoptar
            </button>
          </div>
          <button @click="loadGlobalData" class="btn-secondary btn-icon" title="Recargar">
            🔄
          </button>
        </div>
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
                    selectedPending.length > 0 && selectedPending.length === pendingDevices.length
                  "
                />
              </th>
              <th>IP Address</th>
              <th>MAC Address</th>
              <th>Fabricante</th>
              <th>Hostname</th>
              <th>Origen</th>
              <th>Acciones</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="pendingDevices.length === 0">
              <td colspan="7" class="empty-row">📭 La bandeja está vacía.</td>
            </tr>
            <tr
              v-for="dev in pendingDevices"
              :key="dev.mac_address"
              :class="{ selected: selectedPending.includes(dev.mac_address) }"
            >
              <td>
                <input
                  type="checkbox"
                  :checked="selectedPending.includes(dev.mac_address)"
                  @click="toggleSelection(dev.mac_address)"
                />
              </td>
              <td class="font-mono">{{ dev.ip_address }}</td>
              <td class="font-mono text-dim">{{ dev.mac_address }}</td>
              <td>{{ dev.vendor || 'Desconocido' }}</td>
              <td>{{ dev.hostname || '-' }}</td>
              <td>{{ getMaestroName(dev.maestro_id) }}</td>
              <td>
                <button @click="deletePending(dev.mac_address)" class="btn-danger btn-sm">
                  🗑️
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div v-if="activeTab === 'scanners'" class="content-grid fade-in">
      <div class="config-panel">
        <h3>🚀 Nuevo Escaneo</h3>
        <div class="form-layout">
          <div class="form-group">
            <label>Router Maestro</label>
            <select v-model="scanConfig.maestro_id">
              <option value="" disabled>-- Selecciona Router --</option>
              <option v-for="m in maestros" :key="m.id" :value="m.id">
                {{ m.name || m.client_name }} ({{ m.ip_address }})
              </option>
            </select>
          </div>

          <div class="form-group">
            <label>Red Objetivo (CIDR)</label>
            <input
              type="text"
              v-model="scanConfig.network_cidr"
              placeholder="Ej: 192.168.88.0/24"
            />
          </div>

          <div class="form-group">
            <label>Interfaz <span style="color: var(--error-red)">*</span></label>
            <input
              type="text"
              v-model="scanConfig.interface"
              placeholder="Ej: ether1, bridge-lan"
            />
          </div>

          <div class="form-group">
            <label>Perfil Credenciales (Default)</label>
            <select v-model="scanConfig.credential_profile_id">
              <option :value="null">-- Ninguno (Solo Ping) --</option>
              <option v-for="p in credentialProfiles" :key="p.id" :value="p.id">
                {{ p.name }}
              </option>
            </select>
          </div>

          <div class="automation-box">
            <h4>🤖 Automatización</h4>
            <div class="checkbox-row">
              <input type="checkbox" id="activeTask" v-model="scanConfig.is_active" />
              <label for="activeTask">Guardar como Tarea</label>
            </div>
            <div class="radio-group" v-if="scanConfig.is_active">
              <label
                ><input type="radio" v-model="scanConfig.scan_mode" value="notify" /> Solo
                Notificar</label
              >
              <label
                ><input type="radio" v-model="scanConfig.scan_mode" value="auto" />
                Auto-Adoptar</label
              >
            </div>
          </div>

          <div class="form-actions">
            <button @click="runScan" class="btn-primary full-width" :disabled="isScanning">
              {{ isScanning ? '⏳ Escaneando...' : '🔍 Ejecutar Ahora' }}
            </button>
          </div>
        </div>
      </div>

      <div class="profiles-panel">
        <h3>⚙️ Automatizaciones Activas</h3>
        <div v-if="scanProfiles.length === 0" class="empty-list">No hay tareas configuradas.</div>
        <ul class="profiles-list">
          <li v-for="prof in scanProfiles" :key="prof.id" class="profile-card">
            <div class="profile-info">
              <strong>{{ getMaestroName(prof.maestro_id) }}</strong>
              <small>{{ prof.network_cidr }} ({{ prof.interface }})</small>
            </div>
            <span v-if="prof.is_active" class="badge-success">ACTIVO</span>
            <span v-else class="badge-inactive">PAUSADO</span>
          </li>
        </ul>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* VARIABLES (Copiadas de ManageDeviceView) */
:root {
  --bg-color: #121212;
  --panel: #1b1b1b;
  --font-color: #eaeaea;
  --gray: #9aa0a6;
  --primary-color: #6ab4ff;
  --secondary-color: #ff6b6b;
  --green: #2ea043;
  --error-red: #d9534f;
  --border: #333;
}

.discovery-layout {
  padding: 1rem;
  max-width: 1400px;
  margin: 0 auto;
  color: var(--font-color);
}

/* Header & Tabs */
.header {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  margin-bottom: 1rem;
  border-bottom: 1px solid var(--border);
  padding-bottom: 10px;
}
.title-block h1 {
  margin: 0;
  color: var(--primary-color);
  font-size: 1.8rem;
}
.title-block .subtitle {
  margin: 5px 0 0;
  color: var(--gray);
  font-size: 0.9rem;
}

.tabs {
  display: flex;
  gap: 0.5rem;
}
.tabs > button {
  background: transparent;
  color: var(--font-color);
  border: 1px solid var(--primary-color);
  border-radius: 8px;
  padding: 0.5rem 1rem;
  cursor: pointer;
  transition: 0.2s;
}
.tabs > button.active {
  background: var(--primary-color);
  color: #0b1220;
  font-weight: bold;
}

/* Panels */
.content-panel,
.config-panel,
.profiles-panel {
  background: #252525;
  border-radius: 10px;
  padding: 1.5rem;
  border: 1px solid var(--border);
}
.content-grid {
  display: grid;
  grid-template-columns: 350px 1fr;
  gap: 20px;
  align-items: start;
}

/* Forms & Inputs (Igual que ManageDeviceView) */
.form-layout {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}
.form-group label {
  display: block;
  margin-bottom: 0.4rem;
  font-weight: 500;
  font-size: 0.9rem;
}

input,
select {
  width: 100%;
  background: #1a1a1a;
  color: var(--font-color);
  border: 1px solid #333;
  border-radius: 8px;
  padding: 0.6rem 0.7rem;
}

/* Fix específico para opciones en select */
select option {
  background-color: #1a1a1a;
  color: var(--font-color);
}

.automation-box {
  background: #1a1a1a;
  padding: 1rem;
  border-radius: 8px;
  border: 1px dashed #444;
}
.checkbox-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
}
.checkbox-row input {
  width: auto;
}
.radio-group {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
.radio-group input {
  margin-right: 0.5rem;
}

/* Buttons */
.btn-primary {
  background: var(--green);
  color: white;
  border: none;
  padding: 0.6rem 1.2rem;
  border-radius: 8px;
  font-weight: bold;
  cursor: pointer;
}
.btn-primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.btn-secondary {
  background: transparent;
  border: 1px solid var(--primary-color);
  color: var(--font-color);
  border-radius: 8px;
  padding: 0.6rem;
  cursor: pointer;
}
.btn-danger {
  background: var(--error-red);
  color: white;
  border: none;
  padding: 0.4rem 0.8rem;
  border-radius: 6px;
  cursor: pointer;
}
.btn-icon {
  font-size: 1.2rem;
  padding: 0.4rem 0.8rem;
}
.full-width {
  width: 100%;
  margin-top: 10px;
}

/* Toolbar & Table */
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
  padding-bottom: 1rem;
  border-bottom: 1px solid #333;
}
.adopt-control {
  display: flex;
  gap: 0.5rem;
}
.table-container {
  overflow-x: auto;
}
.devices-table {
  width: 100%;
  border-collapse: collapse;
}
.devices-table th {
  text-align: left;
  padding: 1rem;
  color: var(--gray);
  border-bottom: 1px solid #333;
}
.devices-table td {
  padding: 1rem;
  border-bottom: 1px solid #333;
  color: #ddd;
}
.devices-table tr:hover {
  background: rgba(255, 255, 255, 0.02);
}
.devices-table tr.selected {
  background: rgba(106, 180, 255, 0.1);
}

.font-mono {
  font-family: monospace;
}
.text-dim {
  color: var(--gray);
}
.empty-row {
  text-align: center;
  padding: 3rem;
  color: var(--gray);
  font-style: italic;
}

/* Profiles List */
.profiles-list {
  list-style: none;
  padding: 0;
  margin: 0;
}
.profile-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem;
  background: #1a1a1a;
  border-radius: 8px;
  margin-bottom: 0.5rem;
  border: 1px solid #333;
}
.profile-info {
  display: flex;
  flex-direction: column;
}
.badge-success {
  color: var(--green);
  font-weight: bold;
  font-size: 0.8rem;
  border: 1px solid var(--green);
  padding: 2px 6px;
  border-radius: 4px;
}
.badge-inactive {
  color: var(--gray);
  font-weight: bold;
  font-size: 0.8rem;
  border: 1px solid var(--gray);
  padding: 2px 6px;
  border-radius: 4px;
}

/* Notification */
.notification {
  position: fixed;
  bottom: 20px;
  right: 20px;
  padding: 1rem 1.5rem;
  border-radius: 8px;
  color: white;
  font-weight: bold;
  z-index: 2000;
}
.notification.success {
  background: var(--green);
}
.notification.error {
  background: var(--error-red);
}
.notification.info {
  background: var(--primary-color);
}

.fade-in {
  animation: fadeIn 0.3s ease;
}
@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(5px);
  }
  to {
    opacity: 1;
    transform: 0;
  }
}
</style>
