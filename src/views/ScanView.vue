<script setup>
import { ref, onMounted, computed } from 'vue'
import api from '@/lib/api'

// --- ESTADO GLOBAL ---
const activeTab = ref('inbox')
const isLoading = ref(false)
const isScanning = ref(false)
const isAdopting = ref(false) // [NUEVO] Estado de carga para la adopción asíncrona
const notification = ref({ show: false, message: '', type: 'success' })

// --- DATOS ---
const maestros = ref([])
const allDevicesList = ref([]) // Inventario completo
const credentialProfiles = ref([])
const pendingDevices = ref([])
const ignoredDevices = ref([]) // Lista Negra
const scanProfiles = ref([])
const channels = ref([]) 
const groups = ref([])

// --- ESTADO FILTROS INBOX ---
const inboxFilter = ref({
  search: '',
  type: 'all', // all, infra, generic
  vendor: ''
})

// --- ESTADO FILTROS IGNORADOS ---
const ignoredFilter = ref({
  search: '',
  type: 'all',
  vendor: ''
})

// --- ESTADO SELECCIÓN ---
const selectedPending = ref([])
const selectedIgnored = ref([])
const adoptCredentialId = ref(null)

// --- ESTADO CONFIGURACIÓN (SCAN) ---
const scanConfig = ref({
  id: null,
  maestro_id: '',
  network_cidr: '192.168.88.0/24',
  interface: '',
  scan_ports: '8728, 80, 22', 
  scan_mode: 'manual', 
  credential_profile_id: null,
  is_active: false,
  scan_interval_minutes: 60, 
  target_group: 'General',
  adopt_only_managed: false,
  include_ping_sensor: false,
  include_ethernet_sensor: false,
})

// --- ESTADO TEMPLATE SENSORES ---
const bulkPingConfig = ref({
  config: { interval_sec: 60, latency_threshold_ms: 150, display_mode: 'realtime', average_count: 5, ping_type: 'device_to_external', target_ip: '8.8.8.8' },
  ui_alert_timeout: { enabled: false, channel_id: null, cooldown_minutes: 5, tolerance_count: 1, notify_recovery: false },
  ui_alert_latency: { enabled: false, threshold_ms: 200, channel_id: null, cooldown_minutes: 5, tolerance_count: 1, notify_recovery: false },
  is_active: true, alerts_paused: false
})

const bulkEthernetConfig = ref({
  config: { interface_name: 'ether1', interval_sec: 30 },
  ui_alert_speed_change: { enabled: false, channel_id: null, cooldown_minutes: 10, tolerance_count: 1, notify_recovery: false },
  ui_alert_traffic: { enabled: false, threshold_mbps: 100, direction: 'any', channel_id: null, cooldown_minutes: 5, tolerance_count: 1, notify_recovery: false },
  is_active: true, alerts_paused: false
})

// --- COMPUTADA: Dispositivos Sugeridos ---
const suggestedTargetDevices = computed(() => {
  if (!scanConfig.value.maestro_id) return []
  const selectedMaestro = allDevicesList.value.find((d) => d.id === scanConfig.value.maestro_id)
  if (!selectedMaestro) return allDevicesList.value 
  const currentVpnId = selectedMaestro.vpn_profile_id
  return allDevicesList.value.filter((d) => {
    if (!currentVpnId) return true
    if (d.is_maestro) return d.vpn_profile_id === currentVpnId
    if (d.maestro_id) {
      const dMaestro = allDevicesList.value.find((m) => m.id === d.maestro_id)
      return dMaestro && dMaestro.vpn_profile_id === currentVpnId
    }
    return d.vpn_profile_id === currentVpnId
  })
})

// =============================================================================
// LÓGICA DE FILTRADO
// =============================================================================

// Helper para detectar si es infraestructura (Gestionable)
function isInfra(dev) {
    const v = (dev.vendor || '').toLowerCase();
    const p = (dev.platform || '').toLowerCase();
    const managedVendors = ['mikrotik', 'ubiquiti', 'ubnt', 'mimosa', 'cambium', 'cisco', 'juniper'];
    return managedVendors.some(mv => v.includes(mv)) || p.length > 0 || !!dev.identity;
}

// Filtro Genérico Reutilizable
function filterDevicesList(list, filters) {
    return list.filter(d => {
        // 1. Search Text
        if (filters.search) {
            const q = filters.search.toLowerCase();
            const textMatch = (
                (d.ip_address || '').includes(q) ||
                (d.mac_address || '').toLowerCase().includes(q) ||
                (d.identity || '').toLowerCase().includes(q) ||
                (d.hostname || '').toLowerCase().includes(q) ||
                (d.vendor || '').toLowerCase().includes(q)
            );
            if (!textMatch) return false;
        }
        // 2. Vendor Dropdown
        if (filters.vendor && filters.vendor !== '') {
            if ((d.vendor || 'Desconocido') !== filters.vendor) return false;
        }
        // 3. Type Toggle
        if (filters.type === 'infra') {
            if (!isInfra(d)) return false;
        } else if (filters.type === 'generic') {
            if (isInfra(d)) return false;
        }
        return true;
    });
}

// Computed: Listas Filtradas
const filteredPendingDevices = computed(() => filterDevicesList(pendingDevices.value, inboxFilter.value));
const filteredIgnoredDevices = computed(() => filterDevicesList(ignoredDevices.value, ignoredFilter.value));

// Computed: Listas de Vendors Únicos (para los selects)
const pendingVendors = computed(() => [...new Set(pendingDevices.value.map(d => d.vendor || 'Desconocido'))].sort());
const ignoredVendors = computed(() => [...new Set(ignoredDevices.value.map(d => d.vendor || 'Desconocido'))].sort());


// =============================================================================
// LIFECYCLE & API
// =============================================================================
onMounted(async () => { await loadGlobalData() })

async function loadGlobalData() {
  isLoading.value = true
  try {
    await Promise.all([
      fetchMaestrosAndDevices(), fetchCredentialProfiles(), fetchPendingDevices(),
      fetchIgnoredDevices(), fetchScanProfiles(), fetchChannels(), fetchGroups(),
    ])
  } catch (e) { showNotification('Error cargando datos', 'error') } 
  finally { isLoading.value = false }
}

async function fetchMaestrosAndDevices() {
  try {
    const { data } = await api.get('/devices')
    allDevicesList.value = data || []
    maestros.value = (data || []).filter((d) => d.is_maestro === true)
  } catch (e) { maestros.value = []; allDevicesList.value = [] }
}
async function fetchCredentialProfiles() { const { data } = await api.get('/credentials/profiles'); credentialProfiles.value = data || [] }
async function fetchPendingDevices() { const { data } = await api.get('/discovery/pending', { params: { include_manual: true } }); pendingDevices.value = data || [] }
async function fetchIgnoredDevices() { try { const { data } = await api.get('/discovery/ignored'); ignoredDevices.value = data || [] } catch (e) {} }
async function fetchScanProfiles() { try { const { data } = await api.get('/discovery/profiles'); scanProfiles.value = data || [] } catch (e) {} }
async function fetchChannels() { try { const { data } = await api.get('/channels'); channels.value = data || [] } catch (e) {} }
async function fetchGroups() { try { const { data } = await api.get('/groups'); groups.value = (data || []).map((g) => g.name) } catch (e) {} }

// --- ACTIONS CONFIG ---
function buildSensorConfigPayload(type, data) { 
  const finalConfig = { ...data.config }
  const alerts = []
  const onlyNums = (v, f) => (typeof v === 'number' && !isNaN(v) ? v : f)
  if (type === 'ping') {
    if (data.ui_alert_timeout.enabled && data.ui_alert_timeout.channel_id) alerts.push({ type: 'timeout', channel_id: data.ui_alert_timeout.channel_id, cooldown_minutes: onlyNums(data.ui_alert_timeout.cooldown_minutes, 5), tolerance_count: Math.max(1, onlyNums(data.ui_alert_timeout.tolerance_count, 1)), notify_recovery: !!data.ui_alert_timeout.notify_recovery })
    if (data.ui_alert_latency.enabled && data.ui_alert_latency.channel_id) alerts.push({ type: 'high_latency', threshold_ms: onlyNums(data.ui_alert_latency.threshold_ms, 200), channel_id: data.ui_alert_latency.channel_id, cooldown_minutes: onlyNums(data.ui_alert_latency.cooldown_minutes, 5), tolerance_count: Math.max(1, onlyNums(data.ui_alert_latency.tolerance_count, 1)), notify_recovery: !!data.ui_alert_latency.notify_recovery })
  } else if (type === 'ethernet') {
    if (data.ui_alert_speed_change.enabled && data.ui_alert_speed_change.channel_id) alerts.push({ type: 'speed_change', channel_id: data.ui_alert_speed_change.channel_id, cooldown_minutes: onlyNums(data.ui_alert_speed_change.cooldown_minutes, 10), tolerance_count: Math.max(1, onlyNums(data.ui_alert_speed_change.tolerance_count, 1)), notify_recovery: !!data.ui_alert_speed_change.notify_recovery })
    if (data.ui_alert_traffic.enabled && data.ui_alert_traffic.channel_id) alerts.push({ type: 'traffic_threshold', threshold_mbps: onlyNums(data.ui_alert_traffic.threshold_mbps, 100), direction: data.ui_alert_traffic.direction || 'any', channel_id: data.ui_alert_traffic.channel_id, cooldown_minutes: onlyNums(data.ui_alert_traffic.cooldown_minutes, 5), tolerance_count: Math.max(1, onlyNums(data.ui_alert_traffic.tolerance_count, 1)), notify_recovery: !!data.ui_alert_traffic.notify_recovery })
  }
  return { sensor_type: type, name_template: '{{hostname}} - Sensor', config: finalConfig, is_active: data.is_active, alerts_paused: data.alerts_paused }
}

function restoreSensorConfig(sensors) { 
  if (!sensors || !Array.isArray(sensors)) { scanConfig.value.include_ping_sensor = false; scanConfig.value.include_ethernet_sensor = false; return }
  const pingSensor = sensors.find(s => s.sensor_type === 'ping')
  if (pingSensor) {
    scanConfig.value.include_ping_sensor = true; bulkPingConfig.value.config = { ...pingSensor.config }
    if (pingSensor.config.alerts) pingSensor.config.alerts.forEach(a => { if (a.type === 'timeout') bulkPingConfig.value.ui_alert_timeout = { ...bulkPingConfig.value.ui_alert_timeout, ...a, enabled: true }; if (a.type === 'high_latency') bulkPingConfig.value.ui_alert_latency = { ...bulkPingConfig.value.ui_alert_latency, ...a, enabled: true } })
  }
  const ethSensor = sensors.find(s => s.sensor_type === 'ethernet')
  if (ethSensor) {
    scanConfig.value.include_ethernet_sensor = true; bulkEthernetConfig.value.config = { ...ethSensor.config }
    if (ethSensor.config.alerts) ethSensor.config.alerts.forEach(a => { if (a.type === 'speed_change') bulkEthernetConfig.value.ui_alert_speed_change = { ...bulkEthernetConfig.value.ui_alert_speed_change, ...a, enabled: true }; if (a.type === 'traffic_threshold') bulkEthernetConfig.value.ui_alert_traffic = { ...bulkEthernetConfig.value.ui_alert_traffic, ...a, enabled: true } })
  }
}

async function runScan() {
  if (!scanConfig.value.maestro_id) return showNotification('Selecciona un Router Maestro', 'error')
  
  isScanning.value = true
  try {
    const payload = { ...scanConfig.value }
    if (scanConfig.value.is_active && scanConfig.value.scan_mode === 'auto') {
      const sensorsToCreate = []
      if (scanConfig.value.include_ping_sensor) sensorsToCreate.push(buildSensorConfigPayload('ping', bulkPingConfig.value))
      if (scanConfig.value.include_ethernet_sensor) sensorsToCreate.push(buildSensorConfigPayload('ethernet', bulkEthernetConfig.value))
      payload.sensors_config = sensorsToCreate
    }
    if (scanConfig.value.is_active) {
       await api.post('/discovery/config', payload); showNotification(scanConfig.value.id ? '✅ Tarea actualizada' : '✅ Nueva tarea creada', 'success'); resetConfigForm()
    } else {
        const { data } = await api.post(`/discovery/scan/${scanConfig.value.maestro_id}`, payload); if (data.status === 'started') showNotification('✅ Escaneo iniciado.', 'info')
    }
    await fetchScanProfiles()
  } catch (e) { showNotification(e.response?.data?.detail || 'Error', 'error') } finally { isScanning.value = false }
}

function resetConfigForm() {
    scanConfig.value = { id: null, maestro_id: '', network_cidr: '192.168.88.0/24', interface: '', scan_ports: '8728, 80, 22', scan_mode: 'manual', credential_profile_id: null, is_active: false, scan_interval_minutes: 60, target_group: 'General', adopt_only_managed: false, include_ping_sensor: false, include_ethernet_sensor: false }
}

// --- ACTIONS INBOX ---
function toggleSelection(mac) { selectedPending.value.includes(mac) ? selectedPending.value = selectedPending.value.filter(m => m !== mac) : selectedPending.value.push(mac) }

function selectAll() {
  const visibleMacs = filteredPendingDevices.value.map(d => d.mac_address);
  const allVisibleSelected = visibleMacs.every(mac => selectedPending.value.includes(mac));
  
  if (allVisibleSelected) {
      selectedPending.value = [];
  } else {
      selectedPending.value = [...visibleMacs];
  }
}

// [MODIFICADO] Lógica de adopción para arquitectura asíncrona (Opción B)
async function adoptSelected() {
  if (selectedPending.value.length === 0) return
  isAdopting.value = true // Activa estado de carga

  try {
    const devicesToAdopt = pendingDevices.value.filter((d) => selectedPending.value.includes(d.mac_address))
    const payload = { maestro_id: devicesToAdopt[0].maestro_id, credential_profile_id: adoptCredentialId.value, devices: devicesToAdopt, naming_strategy: 'hostname' }
    
    const { data } = await api.post('/discovery/adopt', payload); 
    
    // 1. Manejo del estado "processing" del Worker
    if (data.status === 'processing') {
      showNotification('⏳ ' + data.message, 'info');
      
      // 2. ACTUALIZACIÓN OPTIMISTA: 
      // Los ocultamos de la UI inmediatamente para que el usuario sienta respuesta instantánea.
      pendingDevices.value = pendingDevices.value.filter(d => !selectedPending.value.includes(d.mac_address));
      selectedPending.value = [];

      // 3. POLLING SECUENCIAL
      // Verificamos la base de datos a los 4 y 10 segundos para consolidar 
      // la eliminación real y refrescar la campanita de notificaciones.
      [4000, 10000].forEach(delay => {
        setTimeout(async () => {
          await fetchPendingDevices();
          // Disparamos un evento global que el Layout/Campanita puede escuchar 
          // para actualizar su contador de notificaciones no leídas
          window.dispatchEvent(new Event('refresh-notifications'));
        }, delay);
      });

    } else if (data.adopted !== undefined) {
      // (Fallback) Si por alguna razón el endpoint responde de forma síncrona
      if (data.adopted > 0) showNotification(`¡${data.adopted} adoptados!`, 'success');
      selectedPending.value = [];
      await fetchPendingDevices();
    }

  } catch (e) { 
    showNotification('Error al enviar orden de adopción', 'error') 
  } finally {
    isAdopting.value = false
  }
}

async function ignoreSelected() {
    if (selectedPending.value.length === 0) return;
    if (!confirm(`¿Ignorar ${selectedPending.value.length} dispositivos?`)) return;
    isLoading.value = true;
    try {
        await Promise.all(selectedPending.value.map(mac => api.delete(`/discovery/pending/${mac}`)));
        showNotification('Ignorados correctamente', 'success'); selectedPending.value = []; await fetchPendingDevices(); await fetchIgnoredDevices();
    } catch (e) { showNotification('Error', 'error') } finally { isLoading.value = false; }
}

async function deletePending(mac) {
  if (!confirm('¿Ignorar este dispositivo?')) return
  try { await api.delete(`/discovery/pending/${mac}`); await fetchPendingDevices(); await fetchIgnoredDevices(); showNotification('Movido a Ignorados', 'success') } catch (e) { showNotification('Error', 'error') }
}

// --- ACTIONS IGNORED ---
function toggleIgnoredSelection(mac) { selectedIgnored.value.includes(mac) ? selectedIgnored.value = selectedIgnored.value.filter(m => m !== mac) : selectedIgnored.value.push(mac) }

function selectAllIgnored() {
    const visibleMacs = filteredIgnoredDevices.value.map(d => d.mac_address);
    const allVisibleSelected = visibleMacs.every(mac => selectedIgnored.value.includes(mac));
    if (allVisibleSelected) { selectedIgnored.value = [] } else { selectedIgnored.value = [...visibleMacs] }
}

async function restoreSelected() {
    if (selectedIgnored.value.length === 0) return;
    if (!confirm(`¿Restaurar ${selectedIgnored.value.length} dispositivos?`)) return;
    isLoading.value = true;
    try { await Promise.all(selectedIgnored.value.map(mac => api.post(`/discovery/restore/${mac}`))); showNotification('Restaurados', 'success'); selectedIgnored.value = []; await fetchIgnoredDevices(); await fetchPendingDevices(); } catch (e) { showNotification('Error', 'error') } finally { isLoading.value = false; }
}

async function hardDeleteSelected() {
    if (selectedIgnored.value.length === 0) return;
    if (!confirm(`⚠️ ¿Eliminar DEFINITIVAMENTE ${selectedIgnored.value.length} dispositivos?`)) return;
    isLoading.value = true;
    try { await Promise.all(selectedIgnored.value.map(mac => api.delete(`/discovery/ignored/${mac}`))); showNotification('Eliminados', 'info'); selectedIgnored.value = []; await fetchIgnoredDevices(); } catch (e) { showNotification('Error', 'error') } finally { isLoading.value = false; }
}

async function restoreDevice(mac) { if(!confirm('¿Restaurar?')) return; try { await api.post(`/discovery/restore/${mac}`); await fetchIgnoredDevices(); await fetchPendingDevices(); showNotification('Restaurado', 'success') } catch(e) {} }
async function hardDeleteDevice(mac) { if(!confirm('¿Eliminar DEFINITIVAMENTE?')) return; try { await api.delete(`/discovery/ignored/${mac}`); await fetchIgnoredDevices(); showNotification('Eliminado', 'info') } catch(e) {} }

// --- UTIL ---
async function deleteScanProfile(id) { if (!confirm('¿Eliminar tarea?')) return; try { await api.delete(`/discovery/profiles/${id}`); await fetchScanProfiles(); showNotification('Eliminada', 'success') } catch (e) {} }
function editScanProfile(profile) { 
    scanConfig.value = { ...scanConfig.value, id: profile.id, maestro_id: profile.maestro_id, network_cidr: profile.network_cidr, interface: profile.interface, scan_ports: profile.scan_ports, scan_mode: profile.scan_mode, credential_profile_id: profile.credential_profile_id, is_active: profile.is_active, scan_interval_minutes: profile.scan_interval_minutes, target_group: profile.target_group || 'General', adopt_only_managed: profile.adopt_only_managed || false }
    if (profile.sensors_template) restoreSensorConfig(profile.sensors_template); else { scanConfig.value.include_ping_sensor = false; scanConfig.value.include_ethernet_sensor = false }
    window.scrollTo({ top: 0, behavior: 'smooth' }); showNotification(`✏️ Editando: ${profile.network_cidr}`, 'info') 
}
function showNotification(msg, type) { notification.value = { show: true, message: msg, type }; setTimeout(() => (notification.value.show = false), 5000) }
function getMaestroName(id) { const m = maestros.value.find((x) => x.id === id); return m ? m.name || m.client_name || m.ip_address : 'Desconocido' }
function getCredentialName(id) { if (!id) return 'Sin Credenciales'; const c = credentialProfiles.value.find(p => p.id === id); return c ? c.name : 'ID Desconocido' }
async function toggleProfileStatus(profile) { const newState = !profile.is_active; try { profile.is_active = newState; await api.patch(`/discovery/profiles/${profile.id}/toggle`, { active: newState }); showNotification(newState ? 'Reanudada' : 'Pausada', 'info'); } catch (e) { profile.is_active = !newState; } }
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
        <button :class="['tab-btn', { active: activeTab === 'inbox' }]" @click="activeTab = 'inbox'">
          📨 Bandeja de Entrada
          <span class="badge" v-if="pendingDevices.length">{{ pendingDevices.length }}</span>
        </button>
        <button :class="['tab-btn', { active: activeTab === 'ignored' }]" @click="activeTab = 'ignored'">
          🚫 Ignorados
          <span class="badge badge-gray" v-if="ignoredDevices.length">{{ ignoredDevices.length }}</span>
        </button>
        <button :class="['tab-btn', { active: activeTab === 'scanners' }]" @click="activeTab = 'scanners'">
          ⚙️ Motores de Escaneo
        </button>
      </div>
    </div>

    <div v-if="activeTab === 'inbox'" class="content-panel fade-in">
      
      <div class="filter-bar">
          <div class="search-group">
              <span class="icon">🔍</span>
              <input type="text" v-model="inboxFilter.search" placeholder="Buscar IP, MAC, Nombre..." class="filter-input" />
          </div>
          
          <div class="filter-controls">
              <select v-model="inboxFilter.vendor" class="filter-select">
                  <option value="">Todo Fabricante</option>
                  <option v-for="v in pendingVendors" :key="v" :value="v">{{ v }}</option>
              </select>

              <div class="toggle-group">
                  <button :class="{ active: inboxFilter.type === 'all' }" @click="inboxFilter.type = 'all'">Todos</button>
                  <button :class="{ active: inboxFilter.type === 'infra' }" @click="inboxFilter.type = 'infra'" title="Mikrotik, Ubiquiti, Cisco...">Infra</button>
                  <button :class="{ active: inboxFilter.type === 'generic' }" @click="inboxFilter.type = 'generic'">Genéricos</button>
              </div>
          </div>
      </div>

      <div class="toolbar">
        <div class="toolbar-left">
          <span class="selection-count" v-if="selectedPending.length > 0">
            {{ selectedPending.length }} seleccionados
          </span>
          <span class="selection-count" v-else> 
             Mostrando {{ filteredPendingDevices.length }} de {{ pendingDevices.length }}
          </span>
        </div>
        <div class="toolbar-right">
            <button v-if="selectedPending.length > 0" @click="ignoreSelected" class="btn-action-del" style="margin-right: 15px;">
                🚫 Ignorar ({{ selectedPending.length }})
            </button>

            <div class="adopt-control">
                <select v-model="adoptCredentialId" class="credential-select" :disabled="selectedPending.length === 0 || isAdopting">
                <option :value="null">Sin Credenciales</option>
                <option v-for="p in credentialProfiles" :key="p.id" :value="p.id">🔐 {{ p.name }}</option>
                </select>
                <button @click="adoptSelected" class="btn-adopt" :disabled="selectedPending.length === 0 || isAdopting">
                {{ isAdopting ? '⏳ Adoptando...' : '✅ Adoptar' }}
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
                <input type="checkbox" @change="selectAll" 
                       :checked="selectedPending.length > 0 && filteredPendingDevices.length > 0 && filteredPendingDevices.every(d => selectedPending.includes(d.mac_address))" />
              </th>
              <th>IP Address</th>
              <th>MAC Address</th>
              <th>Identity</th>
              <th>Fabricante</th>
              <th>Plataforma</th>
              <th>Hostname</th>
              <th>Origen</th>
              <th>Acciones</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="filteredPendingDevices.length === 0">
              <td colspan="9" class="empty-row">
                  {{ pendingDevices.length === 0 ? '📭 Bandeja vacía.' : '🔍 No hay coincidencias con los filtros.' }}
              </td>
            </tr>
            <tr v-for="dev in filteredPendingDevices" :key="dev.mac_address" :class="{ selected: selectedPending.includes(dev.mac_address) }">
              <td>
                <input type="checkbox" :checked="selectedPending.includes(dev.mac_address)" @click="toggleSelection(dev.mac_address)" />
              </td>
              <td class="font-mono text-highlight">{{ dev.ip_address }}</td>
              <td class="font-mono text-dim">{{ dev.mac_address }}</td>
              <td class="text-highlight font-weight-bold">{{ dev.identity || '-' }}</td>
              <td>{{ dev.vendor || 'Desconocido' }}</td>
              <td>{{ dev.platform || '-' }}</td>
              <td>{{ dev.hostname || '-' }}</td>
              <td>{{ getMaestroName(dev.maestro_id) }}</td>
              <td>
                <button @click="deletePending(dev.mac_address)" class="btn-sm btn-del" title="Ignorar (Mover a Blacklist)">🚫</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div v-if="activeTab === 'ignored'" class="content-panel fade-in">
        
        <div class="filter-bar filter-bar-ignored">
            <div class="search-group">
                <span class="icon">🔍</span>
                <input type="text" v-model="ignoredFilter.search" placeholder="Buscar en Ignorados..." class="filter-input" />
            </div>
            
            <div class="filter-controls">
                <select v-model="ignoredFilter.vendor" class="filter-select">
                    <option value="">Todo Fabricante</option>
                    <option v-for="v in ignoredVendors" :key="v" :value="v">{{ v }}</option>
                </select>

                <div class="toggle-group">
                    <button :class="{ active: ignoredFilter.type === 'all' }" @click="ignoredFilter.type = 'all'">Todos</button>
                    <button :class="{ active: ignoredFilter.type === 'infra' }" @click="ignoredFilter.type = 'infra'">Infra</button>
                    <button :class="{ active: ignoredFilter.type === 'generic' }" @click="ignoredFilter.type = 'generic'">Genéricos</button>
                </div>
            </div>
        </div>

        <div class="toolbar" style="background: rgba(255,50,50,0.1); border-color: var(--error-red);">
            <div class="toolbar-left">
                <span class="selection-count" style="color: white; font-weight: bold;" v-if="selectedIgnored.length > 0">
                    {{ selectedIgnored.length }} seleccionados
                </span>
                <span class="selection-count" style="color: #ffaaaa;" v-else>
                    🚫 Mostrando {{ filteredIgnoredDevices.length }} ignorados
                </span>
            </div>
            <div class="toolbar-right">
                <div v-if="selectedIgnored.length > 0" style="display: flex; gap: 10px; margin-right: 15px;">
                    <button @click="restoreSelected" class="btn-action-restore">♻️ Restaurar ({{ selectedIgnored.length }})</button>
                    <button @click="hardDeleteSelected" class="btn-action-del">💀 Olvidar ({{ selectedIgnored.length }})</button>
                </div>
                <button @click="fetchIgnoredDevices" class="btn-icon" title="Recargar Lista">🔄</button>
            </div>
        </div>

        <div class="table-container">
            <table class="devices-table">
                <thead>
                    <tr>
                        <th width="40">
                            <input type="checkbox" @change="selectAllIgnored" 
                                   :checked="selectedIgnored.length > 0 && filteredIgnoredDevices.length > 0 && filteredIgnoredDevices.every(d => selectedIgnored.includes(d.mac_address))" />
                        </th>
                        <th>IP Address</th>
                        <th>MAC Address</th>
                        <th>Identity</th>
                        <th>Fabricante</th>
                        <th>Plataforma</th>
                        <th>Hostname</th>
                        <th style="text-align: right;">Acciones</th>
                    </tr>
                </thead>
                <tbody>
                    <tr v-if="filteredIgnoredDevices.length === 0">
                        <td colspan="8" class="empty-row">
                            {{ ignoredDevices.length === 0 ? '✅ No hay dispositivos ignorados.' : '🔍 No hay coincidencias.' }}
                        </td>
                    </tr>
                    <tr v-for="dev in filteredIgnoredDevices" :key="dev.mac_address" class="ignored-row" :class="{ selected: selectedIgnored.includes(dev.mac_address) }">
                        <td>
                            <input type="checkbox" :checked="selectedIgnored.includes(dev.mac_address)" @click="toggleIgnoredSelection(dev.mac_address)" />
                        </td>
                        <td class="font-mono text-dim">{{ dev.ip_address }}</td>
                        <td class="font-mono text-dim">{{ dev.mac_address }}</td>
                        <td class="text-dim">{{ dev.identity || '-' }}</td>
                        <td class="text-dim">{{ dev.vendor || 'Desconocido' }}</td>
                        <td class="text-dim">{{ dev.platform || '-' }}</td>
                        <td class="text-dim">{{ dev.hostname || '-' }}</td>
                        <td style="text-align: right;">
                            <button @click="restoreDevice(dev.mac_address)" class="btn-sm btn-restore" title="Restaurar" style="margin-right: 10px;">♻️</button>
                            <button @click="hardDeleteDevice(dev.mac_address)" class="btn-sm btn-del" title="Olvidar Definitivamente">💀</button>
                        </td>
                    </tr>
                </tbody>
            </table>
        </div>
    </div>

    <div v-if="activeTab === 'scanners'" class="content-grid fade-in">
      <aside class="config-panel">
        <div class="panel-header">
          <h3>{{ scanConfig.id ? '✏️ Editando Tarea' : '🚀 Nuevo Escaneo' }}</h3>
        </div>
        <div class="form-body">
          <div class="form-group">
            <label>Router Maestro</label>
            <select v-model="scanConfig.maestro_id">
              <option value="" disabled>-- Selecciona Router --</option>
              <option v-for="m in maestros" :key="m.id" :value="m.id">{{ m.name || m.client_name }} ({{ m.ip_address }})</option>
            </select>
          </div>
          <div class="form-group">
            <label>Red Objetivo (CIDR)</label>
            <input type="text" v-model="scanConfig.network_cidr" placeholder="Ej: 192.168.88.0/24" />
          </div>
          <div class="form-group">
            <label>Interfaz</label>
            <input type="text" v-model="scanConfig.interface" placeholder="Auto-detectar (Recomendado)" />
          </div>
          <div class="form-group">
            <label>Puertos</label>
            <input type="text" v-model="scanConfig.scan_ports" placeholder="8728, 80, 22" />
          </div>
          <div class="form-group">
            <label>Credenciales Default</label>
            <select v-model="scanConfig.credential_profile_id">
              <option :value="null">-- Ninguno --</option>
              <option v-for="p in credentialProfiles" :key="p.id" :value="p.id">{{ p.name }}</option>
            </select>
          </div>

          <div class="automation-box">
            <h4>🤖 Automatización</h4>
            <div class="checkbox-row">
              <input type="checkbox" id="activeTask" v-model="scanConfig.is_active" />
              <label for="activeTask">Tarea Recurrente</label>
            </div>
            <template v-if="scanConfig.is_active">
              <div class="form-group interval-group">
                <label>Intervalo (min)</label>
                <div class="input-hint-row">
                  <input type="number" v-model.number="scanConfig.scan_interval_minutes" min="5" placeholder="60" />
                  <span class="hint">Recomendado: >15 min</span>
                </div>
              </div>
              <div class="radio-group">
                <label><input type="radio" v-model="scanConfig.scan_mode" value="notify" /> Notificar</label>
                <label><input type="radio" v-model="scanConfig.scan_mode" value="auto" /> Auto-Adoptar</label>
              </div>
               <div v-if="scanConfig.scan_mode === 'notify' || (scanConfig.scan_mode === 'auto' && !scanConfig.include_ping_sensor && !scanConfig.include_ethernet_sensor)" 
                    class="checkbox-row" style="margin-top:10px; margin-bottom:15px; margin-left:5px;">
                   <input type="checkbox" id="chkManaged" v-model="scanConfig.adopt_only_managed" />
                   <label for="chkManaged" style="font-size:0.9rem; color:#ccc;">Solo Gestionados (Credenciales)</label>
              </div>
              <div v-if="scanConfig.scan_mode === 'auto'" class="auto-adopt-panel fade-in">
                <hr class="separator" />
                <h4 class="mini-title">🏗️ Receta</h4>
                <div class="form-group">
                  <label>Grupo</label>
                  <select v-model="scanConfig.target_group">
                    <option value="General">General</option>
                    <option v-for="g in groups" :key="g" :value="g">{{ g }}</option>
                  </select>
                </div>
                <div class="sensor-selection-group">
                  <div class="checkbox-row">
                    <input type="checkbox" id="chkPing" v-model="scanConfig.include_ping_sensor" />
                    <label for="chkPing">Incluir PING</label>
                  </div>
                  <div v-if="scanConfig.include_ping_sensor" class="mini-config fade-in">
                     <div class="form-group">
                        <input list="scan-target-list" type="text" v-model="bulkPingConfig.config.target_ip" placeholder="Target IP" class="search-input" />
                        <datalist id="scan-target-list"><option v-for="d in suggestedTargetDevices" :key="d.id" :value="d.ip_address">{{ d.client_name }}</option></datalist>
                     </div>
                     <div class="chk-label"><input type="checkbox" v-model="bulkPingConfig.ui_alert_timeout.enabled" /> Timeout Alert</div>
                  </div>
                  <div class="checkbox-row">
                    <input type="checkbox" id="chkEther" v-model="scanConfig.include_ethernet_sensor" />
                    <label for="chkEther">Incluir ETHERNET</label>
                  </div>
                  <div v-if="scanConfig.include_ethernet_sensor" class="mini-config fade-in">
                      <input v-model="bulkEthernetConfig.config.interface_name" placeholder="Interface Name" class="tiny-input-full" />
                  </div>
                </div>
              </div>
            </template>
          </div>
          <div class="form-actions">
            <button v-if="scanConfig.id" @click="resetConfigForm" class="btn-cancel" :disabled="isScanning">❌ Cancelar</button>
            <button @click="runScan" class="btn-scan" :disabled="isScanning">
               {{ isScanning ? '⏳...' : (scanConfig.id ? '💾 Guardar Cambios' : (scanConfig.is_active ? '💾 Guardar Tarea' : '🚀 Escanear Ahora')) }}
            </button>
          </div>
        </div>
      </aside>

      <section class="profiles-panel">
        <div class="panel-header"><h3>⚙️ Tareas Activas</h3></div>
        <div class="profiles-list">
          <div v-if="scanProfiles.length === 0" class="empty-list">Sin tareas.</div>
          <div v-for="prof in scanProfiles" :key="prof.id" class="profile-card">
            <div class="profile-info">
              <strong>{{ getMaestroName(prof.maestro_id) }}</strong>
              <div class="profile-details"><span>🌐 {{ prof.network_cidr }}</span><span>🔌 {{ prof.interface || 'Auto-detectada' }}</span></div>
              <div class="profile-sub-details">
                 <span class="cred-badge">🔐 {{ getCredentialName(prof.credential_profile_id) }}</span>
                 <span v-if="prof.scan_mode === 'auto'" class="auto-tag">🤖 Auto</span>
                 <span v-else class="notify-tag">🔔 Notify</span>
              </div>
            </div>
            <div class="profile-actions">
              <button @click="editScanProfile(prof)" class="btn-icon-action btn-edit" title="Editar">✏️</button>
              <button @click="toggleProfileStatus(prof)" class="btn-icon-action">{{ prof.is_active ? '⏸️' : '▶️' }}</button>
              <button @click="deleteScanProfile(prof.id)" class="btn-sm btn-del" title="Eliminar">🗑️</button>
            </div>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
/* ESTILOS GLOBALES */
.discovery-layout { max-width: 1400px; margin: 0 auto; padding: 20px; }
.header { display: flex; justify-content: space-between; align-items: flex-end; margin-bottom: 20px; border-bottom: 1px solid var(--primary-color); padding-bottom: 10px; }
.title-block h1 { margin: 0; color: var(--blue); font-size: 1.8rem; }
.title-block .subtitle { margin: 5px 0 0; color: var(--gray); font-size: 0.9rem; }
.tabs { display: flex; gap: 10px; }
.tab-btn { background: none; border: none; padding: 10px 20px; color: var(--gray); font-size: 1rem; cursor: pointer; border-radius: 8px 8px 0 0; transition: all 0.2s; position: relative; }
.tab-btn:hover { color: #ccc; }
.tab-btn.active { background-color: var(--primary-color); color: white; font-weight: bold; }
.badge { background: var(--error-red); color: white; font-size: 0.7rem; padding: 2px 6px; border-radius: 10px; position: absolute; top: 5px; right: 5px; }
.badge-gray { background: #555; color: #ccc; font-size: 0.7rem; padding: 2px 6px; border-radius: 10px; position: absolute; top: 5px; right: 5px; }

/* NUEVOS ESTILOS PARA LA BARRA DE FILTROS */
.filter-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: rgba(255, 255, 255, 0.03);
    padding: 12px 15px;
    border-radius: 8px 8px 0 0;
    margin-bottom: 2px;
    flex-wrap: wrap;
    gap: 15px;
}
.filter-bar-ignored {
    background: rgba(255, 50, 50, 0.05); /* Tinte rojo sutil para ignorados */
}
.search-group {
    display: flex;
    align-items: center;
    background: var(--bg-color);
    padding: 0 10px;
    border-radius: 6px;
    border: 1px solid #444;
    flex: 1;
    min-width: 200px;
    max-width: 400px;
}
.search-group .icon { color: #777; margin-right: 5px; }
.filter-input {
    background: transparent;
    border: none;
    color: white;
    padding: 8px 0;
    width: 100%;
    outline: none;
}
.filter-controls {
    display: flex;
    align-items: center;
    gap: 15px;
    flex-wrap: wrap;
}
.filter-select {
    background: var(--bg-color);
    color: white;
    border: 1px solid #444;
    padding: 6px 10px;
    border-radius: 6px;
    outline: none;
    font-size: 0.9rem;
    min-width: 150px;
}
.toggle-group {
    display: flex;
    background: var(--bg-color);
    border-radius: 6px;
    border: 1px solid #444;
    overflow: hidden;
}
.toggle-group button {
    background: transparent;
    border: none;
    color: #aaa;
    padding: 6px 12px;
    cursor: pointer;
    font-size: 0.85rem;
    transition: all 0.2s;
    border-right: 1px solid #444;
}
.toggle-group button:last-child { border-right: none; }
.toggle-group button:hover { color: white; background: rgba(255,255,255,0.05); }
.toggle-group button.active {
    background: var(--primary-color);
    color: white;
    font-weight: bold;
}

/* TOOLBAR & ACTIONS */
.toolbar { background: var(--surface-color); padding: 15px; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid rgba(255,255,255,0.05); }
.selection-count { color: #aaa; font-weight: 500; }
.toolbar-right { display: flex; gap: 15px; align-items: center; }
.adopt-control { display: flex; gap: 10px; background: var(--bg-color); padding: 5px; border-radius: 6px; border: 1px solid var(--primary-color); }
.credential-select { background: transparent; border: none; color: white; padding: 5px; outline: none; }
.credential-select option { background-color: var(--bg-color); color: white; }

.btn-adopt { background: var(--green); color: white; border: none; padding: 5px 15px; border-radius: 4px; cursor: pointer; font-weight: bold; }
.btn-adopt:disabled { background: var(--bg-color); color: var(--gray); cursor: not-allowed; opacity: 0.5; }
.btn-icon { background: none; border: none; font-size: 1.2rem; cursor: pointer; color: var(--gray); }

/* BOTONES MASIVOS NUEVOS */
.btn-action-restore { background: transparent; border: 1px solid var(--green); color: var(--green); padding: 6px 12px; border-radius: 6px; cursor: pointer; font-weight: bold; transition: all 0.2s; }
.btn-action-restore:hover { background: var(--green); color: white; }
.btn-action-del { background: transparent; border: 1px solid var(--error-red); color: var(--error-red); padding: 6px 12px; border-radius: 6px; cursor: pointer; font-weight: bold; transition: all 0.2s; }
.btn-action-del:hover { background: var(--error-red); color: white; }

/* TABLES */
.table-container { background: var(--surface-color); border-radius: 0 0 8px 8px; overflow: hidden; }
.devices-table { width: 100%; border-collapse: collapse; }
.devices-table th { background: rgba(255, 255, 255, 0.05); color: var(--gray); text-align: left; padding: 12px; font-size: 0.9rem; }
.devices-table td { padding: 12px; border-bottom: 1px solid var(--primary-color); color: white; }
.devices-table tr:hover { background: rgba(255, 255, 255, 0.03); }
.devices-table tr.selected { background: rgba(106, 180, 255, 0.1); }
.ignored-row td { color: #888; }
.font-mono { font-family: monospace; }
.text-highlight { color: var(--blue); }
.text-dim { color: #777; }
.font-weight-bold { font-weight: bold; }
.empty-row { text-align: center; padding: 40px; color: var(--gray); font-style: italic; border: 2px dashed var(--primary-color); margin: 20px; }

/* MINI BUTTONS */
.btn-sm { padding: 4px 8px; border: none; border-radius: 4px; cursor: pointer; }
.btn-del { background: transparent; border: 1px solid var(--error-red); color: var(--error-red); }
.btn-del:hover { background-color: var(--error-red); color: white; }
.btn-restore { background: transparent; border: 1px solid var(--green); color: var(--green); }
.btn-restore:hover { background-color: var(--green); color: white; }

/* LAYOUT SCANNERS */
.content-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(350px, 1fr)); gap: 20px; }
.config-panel { background: var(--surface-color); border-radius: 12px; overflow: hidden; align-self: start; }
.panel-header { background: rgba(255, 255, 255, 0.05); padding: 15px; border-bottom: 1px solid var(--primary-color); }
.panel-header h3 { margin: 0; color: var(--blue); font-size: 1.1rem; }
.form-body { padding: 20px; }
.form-group { margin-bottom: 15px; }
.form-group label { display: block; margin-bottom: 5px; font-weight: 500; font-size: 0.9rem; color: var(--gray); }
.form-group input, .form-group select { width: 100%; padding: 10px; background-color: var(--bg-color); border: 1px solid var(--primary-color); color: white; border-radius: 6px; }
.form-group select option { background-color: var(--bg-color); color: white; }
.search-input { width: 100%; padding: 10px; background-color: var(--bg-color); border: 1px solid var(--primary-color); color: white; border-radius: 6px; font-size: 0.9rem; }
.form-group small { display: block; margin-top: 4px; color: #777; font-size: 0.8rem; }
.required { color: var(--error-red); font-size: 0.8rem; }
.automation-box { background: var(--bg-color); padding: 15px; border-radius: 6px; margin-bottom: 20px; border: 1px dashed var(--primary-color); }
.automation-box h4 { margin: 0 0 10px 0; font-size: 0.95rem; color: var(--gray); border-bottom: 1px solid #333; padding-bottom: 5px; }
.checkbox-row { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; color: white; }
.radio-group { display: flex; gap: 15px; margin-bottom: 10px; font-size: 0.9rem; color: #ccc; }
.auto-adopt-panel { margin-top: 15px; padding-top: 10px; }
.separator { border: 0; border-top: 1px solid var(--primary-color); margin: 10px 0; opacity: 0.5; }
.separator-light { border: 0; border-top: 1px dashed #555; margin: 8px 0; }
.mini-title { color: var(--blue); font-size: 0.9rem; margin-bottom: 10px; }
.sensor-selection-group { margin-top: 10px; }
.mini-config { background: rgba(0, 0, 0, 0.2); padding: 10px; border-radius: 4px; margin-top: 5px; margin-bottom: 15px; }
.config-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.chk-label { display: flex; align-items: center; gap: 8px; font-size: 0.85rem; color: #ccc; margin-top: 8px; }
.alert-details { display: flex; gap: 5px; margin-top: 5px; margin-left: 10px; flex-wrap: wrap; align-items: center; }
.mini-select { padding: 4px; font-size: 0.8rem; background: var(--bg-color); border: 1px solid #555; color: white; border-radius: 4px; width: 90px; }
.tiny-input { width: 50px !important; padding: 4px !important; font-size: 0.8rem; height: 28px; background-color: var(--bg-color); border: 1px solid #555; color: white; border-radius: 4px; }
.tiny-input-full { width: 100% !important; padding: 6px !important; font-size: 0.85rem; }
.tiny-chk { font-size: 0.75rem; display: flex; align-items: center; gap: 3px; color: #aaa; }
.auto-tag { font-size: 0.75rem; color: var(--green); margin-top: 4px; font-weight: bold; }
.btn-scan { flex: 1; padding: 12px; background: var(--blue); color: white; border: none; border-radius: 6px; font-weight: bold; cursor: pointer; font-size: 1rem; }
.btn-scan:disabled { opacity: 0.7; cursor: not-allowed; }
.btn-cancel { padding: 12px 15px; background: transparent; border: 1px solid var(--gray); color: var(--gray); border-radius: 6px; font-weight: bold; cursor: pointer; margin-right: 10px; transition: all 0.2s; }
.btn-cancel:hover { border-color: white; color: white; }
.form-actions { display: flex; justify-content: space-between; }
.profiles-panel { background: var(--surface-color); border-radius: 12px; }
.profiles-list { padding: 20px; }
.empty-list { color: var(--gray); text-align: center; padding: 20px; border: 2px dashed var(--primary-color); border-radius: 8px; }
.profile-card { display: flex; justify-content: space-between; align-items: center; padding: 15px; background: var(--bg-color); border-radius: 8px; margin-bottom: 10px; }
.profile-info strong { display: block; margin-bottom: 5px; color: white; }
.profile-details { font-size: 0.85rem; color: #aaa; display: flex; gap: 15px; }
.profile-actions { display: flex; align-items: center; gap: 10px; }
.notification { position: fixed; top: 90px; right: 20px; padding: 1rem 1.5rem; border-radius: 8px; color: white; font-weight: bold; z-index: 1000; }
.notification.success { background: var(--green); }
.notification.error { background: var(--error-red); }
.notification.info { background: var(--blue); }
.fade-in { animation: fadeIn 0.3s ease; }
@keyframes fadeIn { from { opacity: 0; transform: translateY(5px); } to { opacity: 1; transform: 0; } }
.interval-group input { width: 100px; }
.input-hint-row { display: flex; align-items: center; gap: 10px; }
.hint { font-size: 0.8rem; color: #ffcc00; }
.profile-sub-details { margin-top: 5px; font-size: 0.8rem; display: flex; gap: 10px; align-items: center; }
.cred-badge { background: rgba(255,255,255,0.1); padding: 2px 6px; border-radius: 4px; color: #ddd; }
.notify-tag { color: var(--blue); font-weight: bold; }
.sensors-badge { background: rgba(100, 200, 255, 0.1); padding: 2px 6px; border-radius: 4px; color: #89cff0; border: 1px solid rgba(137, 207, 240, 0.3); }
.managed-badge { background: rgba(255, 165, 0, 0.1); padding: 2px 6px; border-radius: 4px; color: #ffa500; border: 1px solid rgba(255, 165, 0, 0.3); }
.btn-icon-action { background: none; border: 1px solid var(--primary-color); border-radius: 50%; width: 32px; height: 32px; cursor: pointer; display: flex; align-items: center; justify-content: center; font-size: 1rem; color: white; transition: all 0.2s; margin-right: 5px; }
.btn-icon-action:hover { background: rgba(255,255,255,0.1); }
.btn-edit:hover { border-color: var(--blue); color: var(--blue); }
</style>