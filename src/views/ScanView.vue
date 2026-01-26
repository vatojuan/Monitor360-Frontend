<script setup>
import { ref, onMounted, computed } from 'vue'
import api from '@/lib/api'

// --- ESTADO GLOBAL ---
const activeTab = ref('inbox')
const isLoading = ref(false)
const isScanning = ref(false)
const notification = ref({ show: false, message: '', type: 'success' })

// --- DATOS ---
const maestros = ref([])
const allDevicesList = ref([]) // Inventario completo para el buscador
const credentialProfiles = ref([])
const pendingDevices = ref([])
const scanProfiles = ref([])
const channels = ref([]) // Canales para alertas
const groups = ref([]) // Grupos del dashboard

// --- ESTADO INBOX ---
const selectedPending = ref([])
const adoptCredentialId = ref(null)

// --- ESTADO CONFIGURACIÓN (SCAN) ---
const scanConfig = ref({
  id: null, // ID para edición
  maestro_id: '',
  network_cidr: '192.168.88.0/24',
  interface: '',
  scan_ports: '8728, 80, 22', 
  scan_mode: 'manual', // 'manual', 'notify', 'auto'
  credential_profile_id: null,
  is_active: false,
  scan_interval_minutes: 60, 

  // Nuevos campos para Auto-Adoptar
  target_group: 'General',
  
  // NUEVO CAMPO: Solo Gestionados
  adopt_only_managed: false,

  // Banderas independientes para incluir sensores (UI Helper)
  include_ping_sensor: false,
  include_ethernet_sensor: false,
})

// --- COMPUTADA: Dispositivos Sugeridos (Contexto de Red del Maestro) ---
const suggestedTargetDevices = computed(() => {
  if (!scanConfig.value.maestro_id) return []

  // Buscamos el maestro seleccionado para ver su VPN
  const selectedMaestro = allDevicesList.value.find((d) => d.id === scanConfig.value.maestro_id)
  if (!selectedMaestro) return allDevicesList.value // Fallback

  const currentVpnId = selectedMaestro.vpn_profile_id

  // Filtramos dispositivos que estén en la misma VPN (o cuya VPN de su maestro sea la misma)
  return allDevicesList.value.filter((d) => {
    // Si no hay VPN configurada en el maestro, mostramos todos por seguridad/fallback
    if (!currentVpnId) return true

    if (d.is_maestro) {
      return d.vpn_profile_id === currentVpnId
    }
    if (d.maestro_id) {
      const dMaestro = allDevicesList.value.find((m) => m.id === d.maestro_id)
      return dMaestro && dMaestro.vpn_profile_id === currentVpnId
    }
    return d.vpn_profile_id === currentVpnId
  })
})

// --- ESTADO TEMPLATE SENSORES (COMPLETO) ---
const bulkPingConfig = ref({
  config: {
    interval_sec: 60,
    latency_threshold_ms: 150,
    display_mode: 'realtime',
    average_count: 5,
    ping_type: 'device_to_external',
    target_ip: '8.8.8.8',
  },
  ui_alert_timeout: {
    enabled: false,
    channel_id: null,
    cooldown_minutes: 5,
    tolerance_count: 1,
    notify_recovery: false,
  },
  ui_alert_latency: {
    enabled: false,
    threshold_ms: 200,
    channel_id: null,
    cooldown_minutes: 5,
    tolerance_count: 1,
    notify_recovery: false,
  },
  is_active: true,
  alerts_paused: false,
})

const bulkEthernetConfig = ref({
  config: {
    interface_name: 'ether1',
    interval_sec: 30,
  },
  ui_alert_speed_change: {
    enabled: false,
    channel_id: null,
    cooldown_minutes: 10,
    tolerance_count: 1,
    notify_recovery: false,
  },
  ui_alert_traffic: {
    enabled: false,
    threshold_mbps: 100,
    direction: 'any',
    channel_id: null,
    cooldown_minutes: 5,
    tolerance_count: 1,
    notify_recovery: false,
  },
  is_active: true,
  alerts_paused: false,
})

// --- LIFECYCLE ---
onMounted(async () => {
  await loadGlobalData()
})

async function loadGlobalData() {
  isLoading.value = true
  try {
    await Promise.all([
      fetchMaestrosAndDevices(),
      fetchCredentialProfiles(),
      fetchPendingDevices(),
      fetchScanProfiles(),
      fetchChannels(),
      fetchGroups(),
    ])
  } catch (e) {
    console.error(e)
    showNotification('Error cargando datos iniciales', 'error')
  } finally {
    isLoading.value = false
  }
}

// --- API CALLS ---
async function fetchMaestrosAndDevices() {
  try {
    const { data } = await api.get('/devices')
    // Guardamos todos para el buscador de IP
    allDevicesList.value = data || []
    // Filtramos solo los maestros para el select de "Router Maestro"
    maestros.value = (data || []).filter((d) => d.is_maestro === true)
  } catch (e) {
    console.error('Error fetching devices', e)
    maestros.value = []
    allDevicesList.value = []
  }
}

async function fetchCredentialProfiles() {
  const { data } = await api.get('/credentials/profiles')
  credentialProfiles.value = data || []
}

async function fetchPendingDevices() {
  // Pide explícitamente incluir los manuales en la bandeja de entrada
  const { data } = await api.get('/discovery/pending', { params: { include_manual: true } })
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

async function fetchChannels() {
  try {
    const { data } = await api.get('/channels')
    channels.value = data || []
  } catch (e) {
    console.error(e)
  }
}

async function fetchGroups() {
  try {
    const { data } = await api.get('/groups')
    groups.value = (data || []).map((g) => g.name)
  } catch (e) {
    console.error(e)
  }
}

// --- HELPER: CONSTRUIR CONFIGURACIÓN DE SENSOR (Igual que Bulk) ---
function buildSensorConfigPayload(type, data) {
  const finalConfig = { ...data.config }
  const alerts = []
  const onlyNums = (v, f) => (typeof v === 'number' && !isNaN(v) ? v : f)

  if (type === 'ping') {
    if (data.ui_alert_timeout.enabled && data.ui_alert_timeout.channel_id) {
      const a = data.ui_alert_timeout
      alerts.push({
        type: 'timeout',
        channel_id: a.channel_id,
        cooldown_minutes: onlyNums(a.cooldown_minutes, 5),
        tolerance_count: Math.max(1, onlyNums(a.tolerance_count, 1)),
        notify_recovery: !!a.notify_recovery,
      })
    }
    if (data.ui_alert_latency.enabled && data.ui_alert_latency.channel_id) {
      const a = data.ui_alert_latency
      alerts.push({
        type: 'high_latency',
        threshold_ms: onlyNums(a.threshold_ms, 200),
        channel_id: a.channel_id,
        cooldown_minutes: onlyNums(a.cooldown_minutes, 5),
        tolerance_count: Math.max(1, onlyNums(a.tolerance_count, 1)),
        notify_recovery: !!a.notify_recovery,
      })
    }
  } else if (type === 'ethernet') {
    if (data.ui_alert_speed_change.enabled && data.ui_alert_speed_change.channel_id) {
      const a = data.ui_alert_speed_change
      alerts.push({
        type: 'speed_change',
        channel_id: a.channel_id,
        cooldown_minutes: onlyNums(a.cooldown_minutes, 10),
        tolerance_count: Math.max(1, onlyNums(a.tolerance_count, 1)),
        notify_recovery: !!a.notify_recovery,
      })
    }
    if (data.ui_alert_traffic.enabled && data.ui_alert_traffic.channel_id) {
      const a = data.ui_alert_traffic
      alerts.push({
        type: 'traffic_threshold',
        threshold_mbps: onlyNums(a.threshold_mbps, 100),
        direction: a.direction || 'any',
        channel_id: a.channel_id,
        cooldown_minutes: onlyNums(a.cooldown_minutes, 5),
        tolerance_count: Math.max(1, onlyNums(a.tolerance_count, 1)),
        notify_recovery: !!a.notify_recovery,
      })
    }
  }

  finalConfig.alerts = alerts
  return {
    sensor_type: type,
    name_template: '{{hostname}} - Sensor', // Fijo para auto-adoptar
    config: finalConfig,
    is_active: data.is_active,
    alerts_paused: data.alerts_paused,
  }
}

// --- HELPER: RESTAURAR CONFIGURACIÓN DE SENSOR (Para Editar) ---
function restoreSensorConfig(sensors) {
  if (!sensors || !Array.isArray(sensors)) {
    scanConfig.value.include_ping_sensor = false
    scanConfig.value.include_ethernet_sensor = false
    return
  }

  const pingSensor = sensors.find(s => s.sensor_type === 'ping')
  if (pingSensor) {
    scanConfig.value.include_ping_sensor = true
    bulkPingConfig.value.config = { ...pingSensor.config }
    if (pingSensor.config.alerts) {
      pingSensor.config.alerts.forEach(a => {
        if (a.type === 'timeout') bulkPingConfig.value.ui_alert_timeout = { ...bulkPingConfig.value.ui_alert_timeout, ...a, enabled: true }
        if (a.type === 'high_latency') bulkPingConfig.value.ui_alert_latency = { ...bulkPingConfig.value.ui_alert_latency, ...a, enabled: true }
      })
    }
  }

  const ethSensor = sensors.find(s => s.sensor_type === 'ethernet')
  if (ethSensor) {
    scanConfig.value.include_ethernet_sensor = true
    bulkEthernetConfig.value.config = { ...ethSensor.config }
    if (ethSensor.config.alerts) {
      ethSensor.config.alerts.forEach(a => {
        if (a.type === 'speed_change') bulkEthernetConfig.value.ui_alert_speed_change = { ...bulkEthernetConfig.value.ui_alert_speed_change, ...a, enabled: true }
        if (a.type === 'traffic_threshold') bulkEthernetConfig.value.ui_alert_traffic = { ...bulkEthernetConfig.value.ui_alert_traffic, ...a, enabled: true }
      })
    }
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

    // Si es Auto-Adoptar y está activo, preparamos la lista de sensores a crear
    if (scanConfig.value.is_active && scanConfig.value.scan_mode === 'auto') {
      const sensorsToCreate = []

      if (scanConfig.value.include_ping_sensor) {
        sensorsToCreate.push(buildSensorConfigPayload('ping', bulkPingConfig.value))
      }

      if (scanConfig.value.include_ethernet_sensor) {
        sensorsToCreate.push(buildSensorConfigPayload('ethernet', bulkEthernetConfig.value))
      }

      payload.sensors_config = sensorsToCreate
    }

    // --- GUARDAR CONFIGURACIÓN ---
    if (scanConfig.value.is_active) {
       await api.post('/discovery/config', payload)
       showNotification('✅ Tarea guardada correctamente', 'success')
    } 

    // Ejecutar escaneo inmediato
    const { data } = await api.post(`/discovery/scan/${scanConfig.value.maestro_id}`, payload)

    // CORRECCIÓN CLAVE: Ahora manejamos el status 'started' para tareas en background
    if (data.status === 'started') {
        showNotification('✅ Escaneo iniciado en segundo plano. Los resultados aparecerán en breve.', 'info')
        // No cambiamos de pestaña inmediatamente para que el usuario vea que inició
        // Opcional: activeTab.value = 'inbox' 
    } else {
        // Fallback para respuesta síncrona antigua (si existiera)
        const count = data.length
        if (count > 0) {
            showNotification(`✅ Escaneo completado. ${count} nuevos en Bandeja.`, 'success')
            activeTab.value = 'inbox'
        } else {
            showNotification('Escaneo completado. No se encontraron nuevos.', 'info')
        }
    }
    
    // Solo refrescamos la lista de perfiles si realmente guardamos uno
    if (scanConfig.value.is_active) {
        await fetchScanProfiles()
    }
    
    // Refrescamos la bandeja por si acaso (aunque los resultados tardarán en llegar)
    fetchPendingDevices() // Sin await para no bloquear
    
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

// --- FUNCIÓN EDITAR ---
async function editScanProfile(profile) {
    try {
        const { data } = await api.get(`/discovery/config/${profile.maestro_id}`)
        if (data) {
            scanConfig.value = {
                ...scanConfig.value, 
                ...data, 
                id: profile.id, 
                is_active: true
            }
            
            if (data.sensors_config) {
                restoreSensorConfig(data.sensors_config)
            } else {
                // Reset sensores si no tiene
                scanConfig.value.include_ping_sensor = false
                scanConfig.value.include_ethernet_sensor = false
            }
            
            window.scrollTo({ top: 0, behavior: 'smooth' })
            showNotification('✏️ Editando tarea...', 'info')
        }
    } catch (e) {
        console.error(e)
        showNotification('Error cargando perfil para editar', 'error')
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

function getCredentialName(id) {
  if (!id) return 'Sin Credenciales (Ping)';
  const c = credentialProfiles.value.find(p => p.id === id);
  return c ? c.name : 'ID Desconocido';
}

async function toggleProfileStatus(profile) {
  const newState = !profile.is_active;
  try {
    profile.is_active = newState; 
    await api.patch(`/discovery/profiles/${profile.id}/toggle`, {
      active: newState
    });
    showNotification(newState ? 'Tarea reanudada' : 'Tarea pausada', 'info');
  } catch (e) {
    profile.is_active = !newState;
    console.error(e);
    showNotification('Error actualizando estado', 'error');
  }
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
              <th>Identity</th>
              <th>Fabricante</th>
              <th>Plataforma</th>
              <th>Hostname</th>
              <th>Origen</th>
              <th>Acciones</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="pendingDevices.length === 0">
              <td colspan="9" class="empty-row">
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

              <td class="text-highlight font-weight-bold">{{ dev.identity || '-' }}</td>
              <td>{{ dev.vendor || 'Desconocido' }}</td>
              <td>{{ dev.platform || '-' }}</td>

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
          <h3>{{ scanConfig.id ? '✏️ Editando Tarea' : '🚀 Nuevo Escaneo' }}</h3>
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
            <label>Puertos a Escanear <span class="required">*</span></label>
            <input type="text" v-model="scanConfig.scan_ports" placeholder="8728, 80, 22" />
            <small>Separados por comas. (Ej: 22 para SSH, 8728 para API)</small>
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

            <template v-if="scanConfig.is_active">
              <div class="form-group interval-group">
                <label>Intervalo de Escaneo (Minutos)</label>
                <div class="input-hint-row">
                  <input 
                    type="number" 
                    v-model.number="scanConfig.scan_interval_minutes" 
                    min="5" 
                    placeholder="60"
                  />
                  <span class="hint">⚠️ Mínimo recomendado: 15 min para evitar CPU alto.</span>
                </div>
              </div>

              <div class="radio-group">
                <label
                  ><input type="radio" v-model="scanConfig.scan_mode" value="notify" /> Solo Notificar</label
                >
                <label
                  ><input type="radio" v-model="scanConfig.scan_mode" value="auto" /> Auto-Adoptar</label
                >
              </div>

              <div v-if="scanConfig.scan_mode === 'notify' || (scanConfig.scan_mode === 'auto' && !scanConfig.include_ping_sensor && !scanConfig.include_ethernet_sensor)" 
                   class="checkbox-row" style="margin-top:10px; margin-bottom:15px; margin-left:5px;">
                   <input type="checkbox" id="chkManaged" v-model="scanConfig.adopt_only_managed" />
                   <label for="chkManaged" style="font-size:0.9rem; color:#ccc;">
                     Solo dispositivos gestionados (Con Credenciales)
                   </label>
                   <small style="display:block; width:100%; margin-left: 26px; color:#777;">
                     Ignorar dispositivos sin credenciales (impresoras, móviles).
                   </small>
              </div>

              <div v-if="scanConfig.scan_mode === 'auto'" class="auto-adopt-panel fade-in">
                <hr class="separator" />
                <h4 class="mini-title">🏗️ Receta de Adopción</h4>

                <div class="form-group">
                  <label>Grupo de Destino</label>
                  <select v-model="scanConfig.target_group">
                    <option value="General">General</option>
                    <option v-for="g in groups" :key="g" :value="g">{{ g }}</option>
                  </select>
                </div>

                <div class="sensor-selection-group">
                  <div class="checkbox-row">
                    <input type="checkbox" id="chkPing" v-model="scanConfig.include_ping_sensor" />
                    <label for="chkPing"><strong>Incluir Sensor PING</strong></label>
                  </div>

                  <div v-if="scanConfig.include_ping_sensor" class="mini-config fade-in">
                    <div class="form-group">
                      <label>Destino (IP)</label>
                      <div style="position: relative">
                        <input
                          list="scan-target-list"
                          type="text"
                          v-model="bulkPingConfig.config.target_ip"
                          placeholder="Ej: 8.8.8.8 o selecciona..."
                          class="search-input"
                        />
                        <datalist id="scan-target-list">
                          <option
                            v-for="d in suggestedTargetDevices"
                            :key="d.id"
                            :value="d.ip_address"
                          >
                            {{ d.client_name }}
                          </option>
                        </datalist>
                      </div>
                    </div>

                    <div class="config-grid">
                      <div class="form-group">
                        <label>Intervalo (s)</label>
                        <input
                          type="number"
                          v-model.number="bulkPingConfig.config.interval_sec"
                          class="tiny-input-full"
                        />
                      </div>
                      <div class="form-group">
                        <label>Visualización</label>
                        <select
                          v-model="bulkPingConfig.config.display_mode"
                          class="tiny-input-full"
                        >
                          <option value="realtime">Tiempo Real</option>
                          <option value="average">Promedio</option>
                        </select>
                      </div>
                      <div
                        class="form-group"
                        v-if="bulkPingConfig.config.display_mode === 'average'"
                      >
                        <label>Muestras</label>
                        <input
                          type="number"
                          v-model.number="bulkPingConfig.config.average_count"
                          class="tiny-input-full"
                        />
                      </div>
                    </div>

                    <hr class="separator-light" />

                    <div class="chk-label">
                      <input type="checkbox" v-model="bulkPingConfig.ui_alert_timeout.enabled" />
                      Timeout
                    </div>
                    <div v-if="bulkPingConfig.ui_alert_timeout.enabled" class="alert-details">
                      <select
                        v-model="bulkPingConfig.ui_alert_timeout.channel_id"
                        class="mini-select"
                      >
                        <option :value="null">-- Canal --</option>
                        <option v-for="c in channels" :key="c.id" :value="c.id">
                          {{ c.name }}
                        </option>
                      </select>
                      <input
                        type="number"
                        v-model.number="bulkPingConfig.ui_alert_timeout.cooldown_minutes"
                        placeholder="Cool(m)"
                        class="tiny-input"
                        title="Enfriamiento"
                      />
                      <input
                        type="number"
                        v-model.number="bulkPingConfig.ui_alert_timeout.tolerance_count"
                        placeholder="Tol."
                        class="tiny-input"
                        title="Tolerancia"
                      />
                      <label class="tiny-chk"
                        ><input
                          type="checkbox"
                          v-model="bulkPingConfig.ui_alert_timeout.notify_recovery"
                        />
                        Recup.</label
                      >
                    </div>

                    <div class="chk-label">
                      <input type="checkbox" v-model="bulkPingConfig.ui_alert_latency.enabled" />
                      Latencia
                    </div>
                    <div v-if="bulkPingConfig.ui_alert_latency.enabled" class="alert-details">
                      <input
                        type="number"
                        v-model.number="bulkPingConfig.ui_alert_latency.threshold_ms"
                        placeholder="ms"
                        class="tiny-input"
                        title="Umbral ms"
                      />
                      <select
                        v-model="bulkPingConfig.ui_alert_latency.channel_id"
                        class="mini-select"
                      >
                        <option :value="null">-- Canal --</option>
                        <option v-for="c in channels" :key="c.id" :value="c.id">
                          {{ c.name }}
                        </option>
                      </select>
                      <input
                        type="number"
                        v-model.number="bulkPingConfig.ui_alert_latency.cooldown_minutes"
                        placeholder="Cool(m)"
                        class="tiny-input"
                        title="Enfriamiento"
                      />
                      <input
                        type="number"
                        v-model.number="bulkPingConfig.ui_alert_latency.tolerance_count"
                        placeholder="Tol."
                        class="tiny-input"
                        title="Tolerancia"
                      />
                      <label class="tiny-chk"
                        ><input
                          type="checkbox"
                          v-model="bulkPingConfig.ui_alert_latency.notify_recovery"
                        />
                        Recup.</label
                      >
                    </div>
                  </div>

                  <hr class="separator" />

                  <div class="checkbox-row">
                    <input
                      type="checkbox"
                      id="chkEther"
                      v-model="scanConfig.include_ethernet_sensor"
                    />
                    <label for="chkEther"><strong>Incluir Sensor ETHERNET</strong></label>
                  </div>

                  <div v-if="scanConfig.include_ethernet_sensor" class="mini-config fade-in">
                    <div class="config-grid">
                      <div class="form-group">
                        <label>Interfaz</label>
                        <input
                          v-model="bulkEthernetConfig.config.interface_name"
                          placeholder="ether1"
                          class="tiny-input-full"
                        />
                      </div>
                      <div class="form-group">
                        <label>Intervalo (s)</label>
                        <input
                          type="number"
                          v-model.number="bulkEthernetConfig.config.interval_sec"
                          class="tiny-input-full"
                        />
                      </div>
                    </div>

                    <hr class="separator-light" />

                    <div class="chk-label">
                      <input
                        type="checkbox"
                        v-model="bulkEthernetConfig.ui_alert_speed_change.enabled"
                      />
                      Cambio Vel.
                    </div>
                    <div
                      v-if="bulkEthernetConfig.ui_alert_speed_change.enabled"
                      class="alert-details"
                    >
                      <select
                        v-model="bulkEthernetConfig.ui_alert_speed_change.channel_id"
                        class="mini-select"
                      >
                        <option :value="null">-- Canal --</option>
                        <option v-for="c in channels" :key="c.id" :value="c.id">
                          {{ c.name }}
                        </option>
                      </select>
                      <input
                        type="number"
                        v-model.number="bulkEthernetConfig.ui_alert_speed_change.cooldown_minutes"
                        placeholder="Cool(m)"
                        class="tiny-input"
                        title="Enfriamiento"
                      />
                      <input
                        type="number"
                        v-model.number="bulkEthernetConfig.ui_alert_speed_change.tolerance_count"
                        placeholder="Tol."
                        class="tiny-input"
                        title="Tolerancia"
                      />
                      <label class="tiny-chk"
                        ><input
                          type="checkbox"
                          v-model="bulkEthernetConfig.ui_alert_speed_change.notify_recovery"
                        />
                        Recup.</label
                      >
                    </div>

                    <div class="chk-label">
                      <input
                        type="checkbox"
                        v-model="bulkEthernetConfig.ui_alert_traffic.enabled"
                      />
                      Tráfico
                    </div>
                    <div v-if="bulkEthernetConfig.ui_alert_traffic.enabled" class="alert-details">
                      <input
                        type="number"
                        v-model.number="bulkEthernetConfig.ui_alert_traffic.threshold_mbps"
                        placeholder="Mbps"
                        class="tiny-input"
                        title="Umbral Mbps"
                      />
                      <select
                        v-model="bulkEthernetConfig.ui_alert_traffic.channel_id"
                        class="mini-select"
                      >
                        <option :value="null">-- Canal --</option>
                        <option v-for="c in channels" :key="c.id" :value="c.id">
                          {{ c.name }}
                        </option>
                      </select>
                      <input
                        type="number"
                        v-model.number="bulkEthernetConfig.ui_alert_traffic.cooldown_minutes"
                        placeholder="Cool(m)"
                        class="tiny-input"
                        title="Enfriamiento"
                      />
                      <input
                        type="number"
                        v-model.number="bulkEthernetConfig.ui_alert_traffic.tolerance_count"
                        placeholder="Tol."
                        class="tiny-input"
                        title="Tolerancia"
                      />
                      <label class="tiny-chk"
                        ><input
                          type="checkbox"
                          v-model="bulkEthernetConfig.ui_alert_traffic.notify_recovery"
                        />
                        Recup.</label
                      >
                    </div>
                  </div>
                </div>
              </div>
            </template>
          </div>

          <div class="form-actions">
            <button @click="runScan" class="btn-scan" :disabled="isScanning">
              {{ isScanning ? '⏳ Escaneando...' : (scanConfig.id ? '💾 Guardar Cambios' : '🔍 Ejecutar / Guardar') }}
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
                <span title="Red Objetivo">🌐 {{ prof.network_cidr }}</span>
                <span title="Interfaz">🔌 {{ prof.interface }}</span>
                <span title="Frecuencia">⏱️ Cada {{ prof.scan_interval_minutes || 60 }} min</span>
              </div>
              <div class="profile-sub-details">
                 <span class="cred-badge">
                   🔐 {{ getCredentialName(prof.credential_profile_id) }}
                 </span>
                 <span v-if="prof.scan_mode === 'auto'" class="auto-tag">
                   🤖 Auto-Adoptar: {{ prof.target_group }}
                 </span>
                 <span v-else class="notify-tag">
                   🔔 Solo Notificar
                 </span>
                 <span v-if="prof.sensors_template && prof.sensors_template.length > 0" class="sensors-badge">
                   📡 {{ prof.sensors_template.length }} Sensores
                 </span>
                 <span v-if="prof.adopt_only_managed && (!prof.sensors_template || prof.sensors_template.length === 0)" class="managed-badge">
                   🛡️ Solo Gestionados
                 </span>
              </div>
            </div>

            <div class="profile-actions">
              <button 
                @click="editScanProfile(prof)" 
                class="btn-icon-action btn-edit"
                title="Editar Tarea"
              >
                ✏️
              </button>

              <button 
                @click="toggleProfileStatus(prof)" 
                class="btn-icon-action"
                :title="prof.is_active ? 'Pausar Tarea' : 'Reanudar Tarea'"
              >
                {{ prof.is_active ? '⏸️' : '▶️' }}
              </button>

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
.font-weight-bold {
  font-weight: bold;
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
  align-self: start;
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

/* CLASE SEARCH INPUT AÑADIDA PARA EL BUSCADOR DE IP */
.search-input {
  width: 100%;
  padding: 10px;
  background-color: var(--bg-color);
  border: 1px solid var(--primary-color);
  color: white;
  border-radius: 6px;
  font-size: 0.9rem;
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
  padding: 15px;
  border-radius: 6px;
  margin-bottom: 20px;
  border: 1px dashed var(--primary-color);
}
.automation-box h4 {
  margin: 0 0 10px 0;
  font-size: 0.95rem;
  color: var(--gray);
  border-bottom: 1px solid #333;
  padding-bottom: 5px;
}
.checkbox-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
  color: white;
}
.radio-group {
  display: flex;
  gap: 15px;
  margin-bottom: 10px;
  font-size: 0.9rem;
  color: #ccc;
}
/* AUTO ADOPT PANEL STYLES */
.auto-adopt-panel {
  margin-top: 15px;
  padding-top: 10px;
}
.separator {
  border: 0;
  border-top: 1px solid var(--primary-color);
  margin: 10px 0;
  opacity: 0.5;
}
.separator-light {
  border: 0;
  border-top: 1px dashed #555;
  margin: 8px 0;
}
.mini-title {
  color: var(--blue);
  font-size: 0.9rem;
  margin-bottom: 10px;
}
.sensor-selection-group {
  margin-top: 10px;
}
.mini-config {
  background: rgba(0, 0, 0, 0.2);
  padding: 10px;
  border-radius: 4px;
  margin-top: 5px;
  margin-bottom: 15px;
}
.config-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}
.chk-label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.85rem;
  color: #ccc;
  margin-top: 8px;
}
.alert-details {
  display: flex;
  gap: 5px;
  margin-top: 5px;
  margin-left: 10px;
  flex-wrap: wrap; /* Para que bajen si no caben */
  align-items: center;
}
.mini-select {
  padding: 4px;
  font-size: 0.8rem;
  background: var(--bg-color);
  border: 1px solid #555;
  color: white;
  border-radius: 4px;
  width: 90px;
}
.tiny-input {
  width: 50px !important;
  padding: 4px !important;
  font-size: 0.8rem;
  height: 28px;
  background-color: var(--bg-color);
  border: 1px solid #555;
  color: white;
  border-radius: 4px;
}
.tiny-input-full {
  width: 100% !important;
  padding: 6px !important;
  font-size: 0.85rem;
}
.tiny-chk {
  font-size: 0.75rem;
  display: flex;
  align-items: center;
  gap: 3px;
  color: #aaa;
}
.auto-tag {
  font-size: 0.75rem;
  color: var(--green);
  margin-top: 4px;
  font-weight: bold;
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

/* --- ESTILOS NUEVOS PARA MEJORAS UI --- */
.interval-group input {
  width: 100px;
}
.input-hint-row {
  display: flex;
  align-items: center;
  gap: 10px;
}
.hint {
  font-size: 0.8rem;
  color: #ffcc00; /* Amarillo advertencia */
}
.profile-sub-details {
  margin-top: 5px;
  font-size: 0.8rem;
  display: flex;
  gap: 10px;
  align-items: center;
}
.cred-badge {
  background: rgba(255,255,255,0.1);
  padding: 2px 6px;
  border-radius: 4px;
  color: #ddd;
}
.notify-tag {
  color: var(--blue);
  font-weight: bold;
}
.sensors-badge {
  background: rgba(100, 200, 255, 0.1);
  padding: 2px 6px;
  border-radius: 4px;
  color: #89cff0;
  border: 1px solid rgba(137, 207, 240, 0.3);
}
.managed-badge {
  background: rgba(255, 165, 0, 0.1);
  padding: 2px 6px;
  border-radius: 4px;
  color: #ffa500;
  border: 1px solid rgba(255, 165, 0, 0.3);
}
.btn-icon-action {
  background: none;
  border: 1px solid var(--primary-color);
  border-radius: 50%;
  width: 32px;
  height: 32px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1rem;
  color: white;
  transition: all 0.2s;
  margin-right: 5px;
}
.btn-icon-action:hover {
  background: rgba(255,255,255,0.1);
}
.btn-edit:hover {
  border-color: var(--blue);
  color: var(--blue);
}
</style>