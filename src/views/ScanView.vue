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

// --- NUEVA FUNCIÓN: ELIMINAR PERFIL DE ESCANEO ---
async function deleteScanProfile(id) {
  if (!confirm('¿Eliminar esta automatización de escaneo?')) return
  try {
    await api.delete(`/discovery/profiles/${id}`)
    await fetchScanProfiles()
    showNotification('Automatización eliminada', 'success')
  } catch (e) {
    console.error(e)
    showNotification('Error al eliminar automatización', 'error')
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
        <button
          :class="['tab-btn', { active: activeTab === 'inbox' }]"
          @click="activeTab = 'inbox'"
        >
          📨 Bandeja de Entrada
          <span class="badge" v-if="pendingDevices.length">{{ pendingDevices.length }}</span>
        </button>
        <button
          :class="['tab-btn', { active: activeTab === 'scanners' }]"
          @click="activeTab = 'scanners'"
        >
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
          <span class="selection-count" v-else> Selecciona dispositivos para adoptar </span>
        </div>
        <div class="toolbar-right">
          <div class="adopt-control">
            <select
              v-model="adoptCredentialId"
              class="credential-select"
              :disabled="selectedPending.length === 0"
            >
              <option :value="null">Sin Credenciales (Solo Ping)</option>
              <option v-for="p in credentialProfiles" :key="p.id" :value="p.id">
                🔐 {{ p.name }}
              </option>
            </select>
            <button
              @click="adoptSelected"
              class="btn-adopt"
              :disabled="selectedPending.length === 0"
            >
              ✅ Adoptar
            </button>
          </div>
          <button @click="loadGlobalData" class="btn-icon" title="Recargar Lista">🔄</button>
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
              <td colspan="7" class="empty-row">
                📭 La bandeja está vacía. Ve a "Motores de Escaneo" para buscar.
              </td>
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
              <td class="font-mono text-highlight">{{ dev.ip_address }}</td>
              <td class="font-mono text-dim">{{ dev.mac_address }}</td>
              <td>{{ dev.vendor || 'Desconocido' }}</td>
              <td>{{ dev.hostname || '-' }}</td>
              <td>{{ getMaestroName(dev.maestro_id) }}</td>
              <td>
                <button
                  @click="deletePending(dev.mac_address)"
                  class="btn-sm btn-del"
                  title="Descartar"
                >
                  🗑️
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div v-if="activeTab === 'scanners'" class="content-grid fade-in">
      <aside class="config-panel">
        <div class="panel-header">
          <h3>🚀 Nuevo Escaneo</h3>
        </div>
        <div class="form-body">
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
            <label>Interfaz <span class="required">*</span></label>
            <input
              type="text"
              v-model="scanConfig.interface"
              placeholder="Ej: ether1, bridge-lan"
            />
            <small>Nombre exacto de la interfaz en el Mikrotik.</small>
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
              <label for="activeTask">Guardar como Tarea Recurrente</label>
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
            <button @click="runScan" class="btn-scan" :disabled="isScanning">
              {{ isScanning ? '⏳ Escaneando...' : '🔍 Ejecutar Ahora' }}
            </button>
          </div>
        </div>
      </aside>

      <section class="profiles-panel">
        <div class="panel-header">
          <h3>⚙️ Automatizaciones Activas</h3>
        </div>
        <div class="profiles-list">
          <div v-if="scanProfiles.length === 0" class="empty-list">No hay tareas configuradas.</div>
          <div v-for="prof in scanProfiles" :key="prof.id" class="profile-card">
            <div class="profile-info">
              <strong>{{ getMaestroName(prof.maestro_id) }}</strong>
              <div class="profile-details">
                <span>🌐 {{ prof.network_cidr }}</span>
                <span>🔌 {{ prof.interface }}</span>
              </div>
            </div>
            <div class="profile-actions">
              <div class="profile-status">
                <span v-if="prof.is_active" class="badge-success">ACTIVO</span>
                <span v-else class="badge-inactive">PAUSADO</span>
              </div>
              <button
                @click="deleteScanProfile(prof.id)"
                class="btn-sm btn-del"
                title="Eliminar Automatización"
              >
                🗑️
              </button>
            </div>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
/* ESTILOS BASADOS EN TU TEMA GLOBAL */
.discovery-layout {
  max-width: 1400px;
  margin: 0 auto;
  padding: 20px;
}

/* Header */
.header {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  margin-bottom: 20px;
  border-bottom: 1px solid var(--primary-color);
  padding-bottom: 10px;
}
.title-block h1 {
  margin: 0;
  color: var(--blue);
  font-size: 1.8rem;
}
.title-block .subtitle {
  margin: 5px 0 0;
  color: var(--gray);
  font-size: 0.9rem;
}

/* Tabs */
.tabs {
  display: flex;
  gap: 10px;
}
.tab-btn {
  background: none;
  border: none;
  padding: 10px 20px;
  color: var(--gray);
  font-size: 1rem;
  cursor: pointer;
  border-radius: 8px 8px 0 0;
  transition: all 0.2s;
  position: relative;
}
.tab-btn:hover {
  color: #ccc;
}
.tab-btn.active {
  background-color: var(--primary-color);
  color: white;
  font-weight: bold;
}
.badge {
  background: var(--error-red);
  color: white;
  font-size: 0.7rem;
  padding: 2px 6px;
  border-radius: 10px;
  position: absolute;
  top: 5px;
  right: 5px;
}

/* Inbox Toolbar */
.toolbar {
  background: var(--surface-color);
  padding: 15px;
  border-radius: 8px 8px 0 0;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.selection-count {
  color: #aaa;
  font-weight: 500;
}
.toolbar-right {
  display: flex;
  gap: 15px;
  align-items: center;
}

.adopt-control {
  display: flex;
  gap: 10px;
  background: var(--bg-color);
  padding: 5px;
  border-radius: 6px;
  border: 1px solid var(--primary-color);
}
.credential-select {
  background: transparent;
  border: none;
  color: white;
  padding: 5px;
  outline: none;
}
.credential-select option {
  background-color: var(--bg-color);
  color: white;
}

.btn-adopt {
  background: var(--green);
  color: white;
  border: none;
  padding: 5px 15px;
  border-radius: 4px;
  cursor: pointer;
  font-weight: bold;
}
.btn-adopt:disabled {
  background: var(--bg-color);
  color: var(--gray);
  cursor: not-allowed;
  opacity: 0.5;
}
.btn-icon {
  background: none;
  border: none;
  font-size: 1.2rem;
  cursor: pointer;
  color: var(--gray);
}

/* Tables */
.table-container {
  background: var(--surface-color);
  border-radius: 0 0 8px 8px;
  overflow: hidden;
}
.devices-table {
  width: 100%;
  border-collapse: collapse;
}
.devices-table th {
  background: rgba(255, 255, 255, 0.05);
  color: var(--gray);
  text-align: left;
  padding: 12px;
  font-size: 0.9rem;
}
.devices-table td {
  padding: 12px;
  border-bottom: 1px solid var(--primary-color);
  color: white;
}
.devices-table tr:hover {
  background: rgba(255, 255, 255, 0.03);
}
.devices-table tr.selected {
  background: rgba(106, 180, 255, 0.1);
}

.font-mono {
  font-family: monospace;
}
.text-highlight {
  color: var(--blue);
}
.text-dim {
  color: #777;
}
.empty-row {
  text-align: center;
  padding: 40px;
  color: var(--gray);
  font-style: italic;
  border: 2px dashed var(--primary-color);
  margin: 20px;
}

.btn-sm {
  padding: 4px 8px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}
/* Estilo del botón borrar corregido: outline rojo profesional */
.btn-del {
  background: transparent;
  border: 1px solid var(--error-red);
  color: var(--error-red);
}
.btn-del:hover {
  background-color: var(--error-red);
  color: white;
}

/* Scanners Grid */
.content-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
  gap: 20px;
}

/* Config Panel */
.config-panel {
  background: var(--surface-color);
  border-radius: 12px;
  overflow: hidden;
}
.panel-header {
  background: rgba(255, 255, 255, 0.05);
  padding: 15px;
  border-bottom: 1px solid var(--primary-color);
}
.panel-header h3 {
  margin: 0;
  color: var(--blue);
  font-size: 1.1rem;
}
.form-body {
  padding: 20px;
}

.form-group {
  margin-bottom: 15px;
}
.form-group label {
  display: block;
  margin-bottom: 5px;
  font-weight: 500;
  font-size: 0.9rem;
  color: var(--gray);
}
.form-group input,
.form-group select {
  width: 100%;
  padding: 10px;
  background-color: var(--bg-color);
  border: 1px solid var(--primary-color);
  color: white;
  border-radius: 6px;
}
.form-group select option {
  background-color: var(--bg-color);
  color: white;
}

.form-group small {
  display: block;
  margin-top: 4px;
  color: #777;
  font-size: 0.8rem;
}
.required {
  color: var(--error-red);
  font-size: 0.8rem;
}

.automation-box {
  background: var(--bg-color);
  padding: 10px;
  border-radius: 6px;
  margin-bottom: 20px;
  border: 1px dashed var(--primary-color);
}
.automation-box h4 {
  margin: 0 0 10px 0;
  font-size: 0.9rem;
  color: var(--gray);
}
.checkbox-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 5px;
  color: white;
}
.radio-group {
  display: flex;
  gap: 15px;
  margin-top: 5px;
  font-size: 0.9rem;
  color: #ccc;
}

.btn-scan {
  width: 100%;
  padding: 12px;
  background: var(--blue);
  color: white;
  border: none;
  border-radius: 6px;
  font-weight: bold;
  cursor: pointer;
  font-size: 1rem;
}
.btn-scan:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

/* Profiles List */
.profiles-panel {
  background: var(--surface-color);
  border-radius: 12px;
}
.profiles-list {
  padding: 20px;
}
.empty-list {
  color: var(--gray);
  text-align: center;
  padding: 20px;
  border: 2px dashed var(--primary-color);
  border-radius: 8px;
}

.profile-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 15px;
  background: var(--bg-color);
  border-radius: 8px;
  margin-bottom: 10px;
}
.profile-info strong {
  display: block;
  margin-bottom: 5px;
  color: white;
}
.profile-details {
  font-size: 0.85rem;
  color: #aaa;
  display: flex;
  gap: 15px;
}
.profile-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}
.badge-success {
  background: var(--green);
  padding: 3px 8px;
  border-radius: 12px;
  font-size: 0.7rem;
  color: white;
}
.badge-inactive {
  background: var(--gray);
  padding: 3px 8px;
  border-radius: 12px;
  font-size: 0.7rem;
  color: white;
}

/* Notification */
.notification {
  position: fixed;
  top: 90px;
  right: 20px;
  padding: 1rem 1.5rem;
  border-radius: 8px;
  color: white;
  font-weight: bold;
  z-index: 1000;
}
.notification.success {
  background: var(--green);
}
.notification.error {
  background: var(--error-red);
}
.notification.info {
  background: var(--blue);
}

/* Animations */
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
