<script setup>
import { ref, onMounted, onUnmounted, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import api from '@/lib/api'
import { connectWebSocketWhenAuthenticated, getCurrentWebSocket } from '@/lib/ws'
import { waitForSession } from '@/lib/supabase'
import draggable from 'vuedraggable'

const router = useRouter()

// --- ESTADO PRINCIPAL ---
const allMonitors = ref([])
const groupedMonitors = ref({})
const activeGroup = ref(null)
const isSidebarCollapsed = ref(false)

// Estado de grupos sincronizado con DB
const dbGroups = ref([])

const liveSensorStatus = ref({})
const monitorToDelete = ref(null)
const collapsedCards = ref(new Set())

// --- Modales y Edición ---
const sensorDetailsToShow = ref(null)
const currentMonitorContext = ref(null)

const monitorToEdit = ref(null)
const editMonitorGroup = ref('')

const showGroupModal = ref(false)
const newGroupName = ref('')
const notification = ref({ show: false, message: '', type: 'success' })
const isRebooting = ref(false) // Estado de carga para el reboot

// --- COMPUTADOS ---
const hasParentMaestro = computed(() => !!currentMonitorContext.value?.maestro_id)
const channelsById = ref({})
const channelsList = computed(() => Object.values(channelsById.value))

// Ordenamos los grupos disponibles para los selectores
const availableGroups = computed(() => [...dbGroups.value].sort())

// --- FORMULARIOS ---
const createNewPingSensor = () => ({
  name: '',
  is_active: true,
  alerts_paused: false,
  config: {
    ping_type: 'device_to_external',
    target_ip: '',
    interval_sec: 60,
    latency_threshold_ms: 150,
    display_mode: 'realtime',
    average_count: 5,
  },
  ui_alert_timeout: { enabled: false, channel_id: null, cooldown_minutes: 5, tolerance_count: 1 },
  ui_alert_latency: {
    enabled: false,
    threshold_ms: 200,
    channel_id: null,
    cooldown_minutes: 5,
    tolerance_count: 1,
  },
})
const createNewEthernetSensor = () => ({
  name: '',
  is_active: true,
  alerts_paused: false,
  config: { interface_name: '', interval_sec: 30 },
  ui_alert_speed_change: {
    enabled: false,
    channel_id: null,
    cooldown_minutes: 10,
    tolerance_count: 1,
  },
  ui_alert_traffic: {
    enabled: false,
    threshold_mbps: 100,
    direction: 'any',
    channel_id: null,
    cooldown_minutes: 5,
    tolerance_count: 1,
  },
})
const newPingSensor = ref(createNewPingSensor())
const newEthernetSensor = ref(createNewEthernetSensor())

// --- API FETCHERS ---
async function fetchGroups() {
  try {
    const { data } = await api.get('/groups')
    dbGroups.value = data.map((g) => g.name)
  } catch (err) {
    console.error('Error fetching groups:', err)
  }
}

async function fetchAllMonitors() {
  try {
    const { data } = await api.get('/monitors')
    allMonitors.value = Array.isArray(data) ? data : []

    allMonitors.value.forEach((m) => {
      if (m.is_active === null || m.is_active === undefined) m.is_active = true
      if (m.alerts_paused === null || m.alerts_paused === undefined) m.alerts_paused = false
      ;(m.sensors || []).forEach((s) => {
        const sid = String(s.id)
        if (!liveSensorStatus.value[sid]) liveSensorStatus.value[sid] = { status: 'pending' }
      })
    })

    refreshGroupedMonitors()
    trySubscribeSensors()
  } catch (err) {
    console.error(err)
  }
}

// --- LOGICA DE GRUPOS ---
async function addNewGroup() {
  const name = newGroupName.value.trim()
  if (!name) return

  try {
    await api.post('/groups', { name: name })
    await fetchGroups()
    refreshGroupedMonitors()
    activeGroup.value = name
    showGroupModal.value = false
    newGroupName.value = ''
    showNotification('Grupo creado exitosamente.')
  } catch (err) {
    console.error(err)
    showNotification('Error al crear grupo.', 'error')
  }
}

function refreshGroupedMonitors() {
  const groups = {}
  dbGroups.value.forEach((gName) => {
    groups[gName] = []
  })
  if (!groups['General']) groups['General'] = []

  const sorted = [...allMonitors.value].sort((a, b) => (a.position || 0) - (b.position || 0))
  sorted.forEach((m) => {
    const gName = m.group_name || 'General'
    if (!groups[gName]) groups[gName] = []
    groups[gName].push(m)
  })

  groupedMonitors.value = groups

  const names = Object.keys(groups).sort()
  if (names.length > 0) {
    if (!activeGroup.value || !groups[activeGroup.value]) {
      activeGroup.value = names[0]
    }
  } else {
    activeGroup.value = null
  }
}

function getGroupStatusClass(groupName) {
  const monitors = groupedMonitors.value[groupName] || []
  let hasAlert = false
  for (const m of monitors) {
    if (!m.is_active) continue
    if (getOverallCardStatus(m)) {
      hasAlert = true
      break
    }
  }
  return hasAlert ? 'dot-red' : 'dot-green'
}

// --- D&D ---
async function onDragChange() {
  if (!activeGroup.value) return
  const monitorsInGroup = groupedMonitors.value[activeGroup.value]
  const payloadItems = []

  monitorsInGroup.forEach((m, index) => {
    m.position = index
    payloadItems.push({ monitor_id: m.monitor_id, group_name: activeGroup.value, position: index })
  })

  try {
    await api.post('/monitors/reorder', { items: payloadItems })
  } catch {
    /* ignore */
  }
}

// --- UTILIDADES ---
function formatBitrate(bits) {
  const n = Number(bits)
  if (!Number.isFinite(n) || n <= 0) return '0 Kbps'
  const kbps = n / 1000
  if (kbps < 1000) return `${kbps.toFixed(1)} Kbps`
  return `${(kbps / 1000).toFixed(1)} Mbps`
}
function formatLatency(ms) {
  if (ms == null || ms === '') return '—'
  const n = Number(ms)
  return Number.isFinite(n) ? Math.round(n) : ms
}
function getStatusClass(status) {
  if (['timeout', 'error', 'link_down'].includes(status)) return 'status-timeout'
  if (status === 'high_latency') return 'status-high-latency'
  if (['ok', 'link_up'].includes(status)) return 'status-ok'
  return 'status-pending'
}
function showNotification(m, t = 'success') {
  notification.value = { show: true, message: m, type: t }
  setTimeout(() => (notification.value.show = false), 4000)
}
function safeJsonParse(v, f = {}) {
  try {
    return JSON.parse(v)
  } catch {
    return f
  }
}
function toggleCardCollapse(mid) {
  collapsedCards.value.has(mid) ? collapsedCards.value.delete(mid) : collapsedCards.value.add(mid)
}

// --- WEBSOCKETS ---
function normalizeWsPayload(raw) {
  if (Array.isArray(raw)) return raw.flatMap(normalizeWsPayload)
  if (typeof raw === 'string') {
    try {
      return normalizeWsPayload(JSON.parse(raw))
    } catch {
      return []
    }
  }
  if (raw && typeof raw === 'object') {
    if (['sensor_update', 'sensor-status'].includes(raw.type)) {
      const i = raw.data || raw.payload
      if (i) return [i]
    }
    if (Object.prototype.hasOwnProperty.call(raw, 'sensor_id')) return [raw]
  }
  return []
}
function currentSensorIds() {
  return allMonitors.value.flatMap((m) =>
    m.is_active !== false
      ? (m.sensors || []).filter((s) => s.is_active !== false).map((s) => s.id)
      : [],
  )
}
function trySubscribeSensors() {
  const ws = getCurrentWebSocket()
  if (!ws || ws.readyState !== 1) return
  const ids = currentSensorIds()
  if (ids.length > 0) ws.send(JSON.stringify({ type: 'subscribe_sensors', sensor_ids: ids }))
}
watch(() => allMonitors.value, trySubscribeSensors, { deep: true })
async function ensureChannelsLoaded() {
  if (!Object.keys(channelsById.value).length) {
    try {
      const { data } = await api.get('/channels')
      data.forEach((c) => (channelsById.value[c.id] = c))
    } catch {
      /* ignore */
    }
  }
}

let wsOpenUnbind = null,
  directMsgUnbind = null
function handleRawMessage(evt) {
  try {
    const parsed = JSON.parse(evt.data)
    const updates = normalizeWsPayload(parsed)
    updates.forEach((u) => {
      if (u.sensor_id)
        liveSensorStatus.value[String(u.sensor_id)] = {
          ...liveSensorStatus.value[String(u.sensor_id)],
          ...u,
        }
    })
  } catch {
    /* ignore */
  }
}
function wireWsSyncAndSubs() {
  const ws = getCurrentWebSocket()
  if (!ws) {
    setTimeout(wireWsSyncAndSubs, 500)
    return
  }
  ws.removeEventListener('message', handleRawMessage)
  ws.addEventListener('message', handleRawMessage)
  if (ws.readyState === 1) trySubscribeSensors()
  const onOpen = () => trySubscribeSensors()
  ws.addEventListener('open', onOpen)
  wsOpenUnbind = () => {
    try {
      ws.removeEventListener('open', onOpen)
    } catch {
      /* ignore */
    }
  }
  directMsgUnbind = () => {
    try {
      ws.removeEventListener('message', handleRawMessage)
    } catch {
      /* ignore */
    }
  }
}

// --- LIFECYCLE ---
onMounted(async () => {
  try {
    await waitForSession({ requireAuth: true })
  } catch {
    return
  }
  await fetchGroups()
  await fetchAllMonitors()

  await connectWebSocketWhenAuthenticated()
  wireWsSyncAndSubs()
})
onUnmounted(() => {
  if (typeof wsOpenUnbind === 'function') wsOpenUnbind()
  if (typeof directMsgUnbind === 'function') directMsgUnbind()
})

// --- ACCIONES DE TARJETA ---
async function toggleMonitorActive(monitor) {
  const newVal = !monitor.is_active
  monitor.is_active = newVal
  try {
    await api.put(`/monitors/${monitor.monitor_id}`, { is_active: newVal })
    if (!newVal) trySubscribeSensors()
    showNotification(newVal ? 'Monitor encendido' : 'Monitor apagado')
  } catch {
    monitor.is_active = !newVal
    showNotification('Error', 'error')
  }
}
async function toggleMonitorPause(monitor) {
  const newVal = !monitor.alerts_paused
  monitor.alerts_paused = newVal
  try {
    await api.put(`/monitors/${monitor.monitor_id}`, { alerts_paused: newVal })
    showNotification(newVal ? 'Alertas pausadas' : 'Alertas activas')
  } catch {
    monitor.alerts_paused = !newVal
    showNotification('Error', 'error')
  }
}
function getOverallCardStatus(monitor) {
  if (monitor.is_active === false) return false
  if (!monitor.sensors || !monitor.sensors.length) return false
  return monitor.sensors.some((s) => {
    const st = liveSensorStatus.value[String(s.id)]?.status
    return ['timeout', 'error', 'high_latency', 'link_down'].includes(st)
  })
}
async function confirmDeleteMonitor() {
  if (!monitorToDelete.value) return
  try {
    await api.delete(`/monitors/${monitorToDelete.value.monitor_id}`)
    allMonitors.value = allMonitors.value.filter(
      (m) => m.monitor_id !== monitorToDelete.value.monitor_id,
    )
    refreshGroupedMonitors()
    monitorToDelete.value = null
  } catch {
    /* ignore */
  }
}
function requestDeleteMonitor(m, e) {
  e?.stopPropagation()
  monitorToDelete.value = m
}
function goToSensorDetail(id) {
  router.push(`/sensor/${id}`)
}

// --- GESTIÓN DE MONITOR (CAMBIO GRUPO + REBOOT) ---
function openMonitorSettings(monitor) {
  monitorToEdit.value = monitor
  editMonitorGroup.value = monitor.group_name || 'General'
}

async function saveMonitorSettings() {
  if (!monitorToEdit.value) return
  const newGroup = editMonitorGroup.value

  if (newGroup !== monitorToEdit.value.group_name) {
    try {
      await api.put(`/monitors/${monitorToEdit.value.monitor_id}`, { group_name: newGroup })
      if (!dbGroups.value.includes(newGroup)) {
        await fetchGroups()
      }
      const mLocal = allMonitors.value.find((m) => m.monitor_id === monitorToEdit.value.monitor_id)
      if (mLocal) mLocal.group_name = newGroup
      refreshGroupedMonitors()
      showNotification('Grupo actualizado')
    } catch (err) {
      console.error(err)
      showNotification('Error al actualizar grupo', 'error')
    }
  }
  monitorToEdit.value = null
}

async function requestReboot() {
  const m = monitorToEdit.value
  if (!m || !m.device_id) return

  if (
    !confirm(
      `¿Estás seguro de REINICIAR el dispositivo ${m.client_name}?\nSe perderá la conexión temporalmente.`,
    )
  ) {
    return
  }

  isRebooting.value = true
  try {
    await api.post(`/devices/${m.device_id}/reboot`)
    showNotification(`Reiniciando ${m.client_name}...`, 'success')
    monitorToEdit.value = null // Cerrar modal
  } catch (err) {
    console.error(err)
    showNotification(err.response?.data?.detail || 'Error al enviar comando de reinicio.', 'error')
  } finally {
    isRebooting.value = false
  }
}

// --- EDICION SENSOR (Lápiz) ---
async function showSensorDetails(s, m, e) {
  e?.stopPropagation()
  await ensureChannelsLoaded()
  sensorDetailsToShow.value = s
  currentMonitorContext.value = m
  const cfg = safeJsonParse(s.config)
  if (s.sensor_type === 'ping') {
    const d = createNewPingSensor()
    d.name = s.name
    d.is_active = s.is_active !== false
    d.alerts_paused = s.alerts_paused === true
    d.config = { ...d.config, ...cfg }
    if (!m.maestro_id) d.config.ping_type = 'device_to_external'
    ;(cfg.alerts || []).forEach((a) => {
      if (a.type === 'timeout') d.ui_alert_timeout = { enabled: true, ...a }
      if (a.type === 'high_latency') d.ui_alert_latency = { enabled: true, ...a }
    })
    newPingSensor.value = d
  } else {
    const d = createNewEthernetSensor()
    d.name = s.name
    d.is_active = s.is_active !== false
    d.alerts_paused = s.alerts_paused === true
    d.config = { interface_name: cfg.interface_name || '', interval_sec: cfg.interval_sec || 30 }
    ;(cfg.alerts || []).forEach((a) => {
      if (a.type === 'speed_change') d.ui_alert_speed_change = { enabled: true, ...a }
      if (a.type === 'traffic_threshold') d.ui_alert_traffic = { enabled: true, ...a }
    })
    newEthernetSensor.value = d
  }
}

async function handleUpdateSensor() {
  if (!sensorDetailsToShow.value) return

  const type = sensorDetailsToShow.value.sensor_type
  const uiData = type === 'ping' ? newPingSensor.value : newEthernetSensor.value
  const config = { ...uiData.config }
  config.alerts = []
  const num = (v, d) => (typeof v === 'number' && !isNaN(v) ? v : d)

  if (type === 'ping') {
    const t = uiData.ui_alert_timeout
    if (t.enabled && t.channel_id)
      config.alerts.push({
        type: 'timeout',
        channel_id: t.channel_id,
        cooldown_minutes: num(t.cooldown_minutes, 5),
        tolerance_count: num(t.tolerance_count, 1),
      })
    const l = uiData.ui_alert_latency
    if (l.enabled && l.channel_id)
      config.alerts.push({
        type: 'high_latency',
        threshold_ms: num(l.threshold_ms, 200),
        channel_id: l.channel_id,
        cooldown_minutes: num(l.cooldown_minutes, 5),
        tolerance_count: num(l.tolerance_count, 1),
      })
  } else {
    const s = uiData.ui_alert_speed_change
    if (s.enabled && s.channel_id)
      config.alerts.push({
        type: 'speed_change',
        channel_id: s.channel_id,
        cooldown_minutes: num(s.cooldown_minutes, 10),
        tolerance_count: num(s.tolerance_count, 1),
      })
    const tr = uiData.ui_alert_traffic
    if (tr.enabled && tr.channel_id)
      config.alerts.push({
        type: 'traffic_threshold',
        threshold_mbps: num(tr.threshold_mbps, 100),
        direction: tr.direction,
        channel_id: tr.channel_id,
        cooldown_minutes: num(tr.cooldown_minutes, 5),
        tolerance_count: num(tr.tolerance_count, 1),
      })
  }

  try {
    const payload = {
      name: uiData.name,
      config,
      is_active: uiData.is_active,
      alerts_paused: uiData.alerts_paused,
    }
    const { data } = await api.put(`/sensors/${sensorDetailsToShow.value.id}`, payload)

    const m = allMonitors.value.find((m) => m.monitor_id === currentMonitorContext.value.monitor_id)
    if (m) {
      const idx = m.sensors.findIndex((s) => s.id === sensorDetailsToShow.value.id)
      if (idx !== -1) m.sensors[idx] = { ...m.sensors[idx], ...data }
    }

    showNotification('Sensor guardado')
    if (payload.is_active !== sensorDetailsToShow.value.is_active) trySubscribeSensors()
    closeSensorDetails()
  } catch {
    showNotification('Error al guardar sensor', 'error')
  }
}
function closeSensorDetails() {
  sensorDetailsToShow.value = null
  currentMonitorContext.value = null
}
</script>

<template>
  <div class="layout-container">
    <aside class="sidebar" :class="{ 'sidebar-collapsed': isSidebarCollapsed }">
      <div class="sidebar-header">
        <h3 v-if="!isSidebarCollapsed">GRUPOS</h3>
        <button
          class="btn-toggle-sidebar"
          @click="isSidebarCollapsed = !isSidebarCollapsed"
          title="Alternar Barra"
        >
          {{ isSidebarCollapsed ? '☰' : '«' }}
        </button>
      </div>

      <div class="sidebar-actions" v-if="!isSidebarCollapsed">
        <button class="btn-add-group" @click="showGroupModal = true">+ Nuevo Grupo</button>
      </div>

      <ul class="group-list">
        <li
          v-for="gName in Object.keys(groupedMonitors).sort()"
          :key="gName"
          :class="{ active: activeGroup === gName }"
          @click="activeGroup = gName"
          :title="gName"
        >
          <span :class="['status-dot', getGroupStatusClass(gName)]"></span>
          <span v-if="!isSidebarCollapsed" class="group-name">{{ gName }}</span>
          <span v-if="!isSidebarCollapsed" class="badge">{{ groupedMonitors[gName].length }}</span>
        </li>
      </ul>
    </aside>

    <main class="main-content">
      <header class="content-header" v-if="activeGroup">
        <h2>{{ activeGroup }}</h2>
        <router-link to="/monitor-builder" class="btn-primary">Añadir Dispositivo</router-link>
      </header>
      <div v-else class="empty-selection">
        <p>Selecciona un grupo para ver sus monitores</p>
      </div>

      <div v-if="notification.show" :class="['notification', notification.type]">
        {{ notification.message }}
      </div>

      <div class="scroll-area" v-if="activeGroup && groupedMonitors[activeGroup]">
        <draggable
          :list="groupedMonitors[activeGroup]"
          group="monitors"
          item-key="monitor_id"
          class="dashboard-grid"
          @change="onDragChange"
          :animation="200"
          handle=".drag-handle"
        >
          <template #item="{ element: monitor }">
            <div
              :class="[
                'monitor-card',
                {
                  'status-alert': getOverallCardStatus(monitor),
                  'is-inactive': !monitor.is_active,
                  'is-collapsed': collapsedCards.has(monitor.monitor_id),
                },
              ]"
            >
              <div class="card-header" @dblclick="toggleCardCollapse(monitor.monitor_id)">
                <div class="header-left">
                  <span class="drag-handle">::</span>
                  <div class="title-container">
                    <h3>{{ monitor.client_name }}</h3>
                    <div class="badges-row">
                      <span v-if="!monitor.is_active" class="off-badge">OFF</span>
                      <span v-if="monitor.alerts_paused" class="pause-badge">⏸️</span>
                    </div>
                  </div>
                </div>

                <div class="card-actions-right">
                  <span class="device-ip" v-if="!collapsedCards.has(monitor.monitor_id)">
                    {{ monitor.ip_address }}
                  </span>
                  <span v-if="getOverallCardStatus(monitor)" class="alert-icon">⚠️</span>

                  <button
                    class="action-icon-btn"
                    @click="openMonitorSettings(monitor)"
                    title="Configuración de Monitor"
                  >
                    ⚙️
                  </button>

                  <button
                    class="action-icon-btn"
                    @click="toggleCardCollapse(monitor.monitor_id)"
                    :title="collapsedCards.has(monitor.monitor_id) ? 'Expandir' : 'Colapsar'"
                  >
                    {{ collapsedCards.has(monitor.monitor_id) ? '🔽' : '🔼' }}
                  </button>
                  <button
                    class="action-icon-btn"
                    :class="{ 'active-orange': monitor.alerts_paused }"
                    @click="toggleMonitorPause(monitor)"
                    title="Pausar Alertas"
                  >
                    {{ monitor.alerts_paused ? '🔕' : '🔔' }}
                  </button>
                  <button
                    class="action-icon-btn"
                    :class="{ 'active-red': !monitor.is_active }"
                    @click="toggleMonitorActive(monitor)"
                    title="Encender/Apagar"
                  >
                    {{ monitor.is_active ? '🔌' : '⚫' }}
                  </button>
                  <button class="remove-btn" @click="requestDeleteMonitor(monitor, $event)">
                    ×
                  </button>
                </div>
              </div>

              <div v-if="!collapsedCards.has(monitor.monitor_id)" class="card-body">
                <div class="sensors-container">
                  <div v-if="!monitor.sensors || monitor.sensors.length === 0" class="no-sensors">
                    Sin sensores.
                  </div>

                  <div
                    v-else
                    v-for="sensor in monitor.sensors"
                    :key="sensor.id"
                    class="sensor-row"
                    :class="{
                      'row-inactive': !sensor.is_active,
                      'row-paused': sensor.alerts_paused,
                    }"
                    @click="goToSensorDetail(sensor.id)"
                  >
                    <span class="sensor-name">
                      {{ sensor.name }}
                      <small v-if="sensor.alerts_paused">⏸️</small>
                    </span>

                    <div class="sensor-status-group">
                      <div
                        class="sensor-value"
                        :class="getStatusClass(liveSensorStatus[String(sensor.id)]?.status)"
                      >
                        <template v-if="!sensor.is_active">
                          <span class="text-off">OFF</span>
                        </template>

                        <template v-else-if="sensor.sensor_type === 'ping'">
                          <span v-if="liveSensorStatus[String(sensor.id)]?.status === 'timeout'"
                            >Timeout</span
                          >
                          <span v-else-if="liveSensorStatus[String(sensor.id)]?.status === 'error'"
                            >Error</span
                          >
                          <span
                            v-else-if="liveSensorStatus[String(sensor.id)]?.status === 'pending'"
                            >...</span
                          >
                          <span v-else
                            >{{
                              formatLatency(liveSensorStatus[String(sensor.id)]?.latency_ms)
                            }}
                            ms</span
                          >
                        </template>

                        <template v-else-if="sensor.sensor_type === 'ethernet'">
                          <div class="ethernet-data-flex">
                            <span class="ethernet-main-status">
                              {{
                                (liveSensorStatus[String(sensor.id)]?.status || 'pending').replace(
                                  '_',
                                  ' ',
                                )
                              }}
                              <span
                                class="ethernet-speed"
                                v-if="liveSensorStatus[String(sensor.id)]?.status === 'link_up'"
                              >
                                ({{ liveSensorStatus[String(sensor.id)]?.speed || '—' }})
                              </span>
                            </span>
                            <span
                              class="ethernet-traffic-row"
                              v-if="liveSensorStatus[String(sensor.id)]?.status !== 'pending'"
                            >
                              <span class="traf-item"
                                >↓
                                {{
                                  formatBitrate(liveSensorStatus[String(sensor.id)]?.rx_bitrate)
                                }}</span
                              >
                              <span class="traf-item"
                                >↑
                                {{
                                  formatBitrate(liveSensorStatus[String(sensor.id)]?.tx_bitrate)
                                }}</span
                              >
                            </span>
                          </div>
                        </template>

                        <template v-else>{{
                          liveSensorStatus[String(sensor.id)]?.status || 'pending'
                        }}</template>
                      </div>

                      <button
                        class="details-btn"
                        @click="showSensorDetails(sensor, monitor, $event)"
                      >
                        ✎
                      </button>
                    </div>
                  </div>
                </div>
              </div>

              <div
                v-else
                class="card-body collapsed-summary"
                :class="{ 'has-alert': getOverallCardStatus(monitor) }"
              >
                <span v-if="getOverallCardStatus(monitor)" class="summary-alert"
                  >⚠️ Atención Requerida</span
                >
                <span v-else class="summary-ok">✓ Sistema Operativo</span>
              </div>
            </div>
          </template>
        </draggable>
      </div>
    </main>

    <div v-if="showGroupModal" class="modal-overlay" @click.self="showGroupModal = false">
      <div class="modal-content small">
        <h3>Crear Nuevo Grupo</h3>
        <input v-model="newGroupName" placeholder="Nombre del Grupo" class="full-width-input" />
        <div class="modal-actions">
          <button class="btn-secondary" @click="showGroupModal = false">Cancelar</button>
          <button class="btn-primary" @click="addNewGroup">Crear</button>
        </div>
      </div>
    </div>

    <div v-if="monitorToEdit" class="modal-overlay" @click.self="monitorToEdit = null">
      <div class="modal-content small">
        <h3>Configurar Monitor</h3>
        <p class="modal-subtitle">
          {{ monitorToEdit.client_name }} ({{ monitorToEdit.ip_address }})
        </p>

        <div class="form-group" style="margin-top: 1.5rem">
          <label>Mover a Grupo:</label>
          <select v-model="editMonitorGroup" class="full-width-input">
            <option v-for="g in availableGroups" :key="g" :value="g">{{ g }}</option>
            <option value="Sin Grupo">Sin Grupo</option>
          </select>
        </div>

        <div
          class="danger-zone"
          style="margin-top: 2rem; border-top: 1px dashed #555; padding-top: 1rem"
        >
          <h4 style="color: #ff6b6b; margin-bottom: 0.5rem; font-size: 0.9rem">
            Acciones de Dispositivo
          </h4>
          <button class="btn-danger-outline" @click="requestReboot" :disabled="isRebooting">
            {{ isRebooting ? 'Reiniciando...' : '🔄 Reiniciar Dispositivo' }}
          </button>
        </div>

        <div class="modal-actions" style="margin-top: 2rem">
          <button class="btn-secondary" @click="monitorToEdit = null">Cerrar</button>
          <button class="btn-primary" @click="saveMonitorSettings">Guardar Cambios</button>
        </div>
      </div>
    </div>

    <div v-if="monitorToDelete" class="modal-overlay">
      <div class="modal-content small">
        <h3>Borrar Monitor</h3>
        <p>¿Seguro?</p>
        <div class="modal-actions">
          <button @click="monitorToDelete = null" class="btn-secondary">No</button>
          <button @click="confirmDeleteMonitor" class="btn-danger">Si</button>
        </div>
      </div>
    </div>

    <div v-if="sensorDetailsToShow" class="modal-overlay" @click.self="closeSensorDetails">
      <div class="modal-content">
        <h3>Editar: {{ sensorDetailsToShow.name }}</h3>

        <form @submit.prevent="handleUpdateSensor" class="config-form">
          <div class="sub-section span-3">
            <h4>Configuración General</h4>
            <div class="general-config-grid">
              <div class="form-group checkbox-group">
                <input
                  type="checkbox"
                  v-model="
                    (sensorDetailsToShow.sensor_type === 'ping' ? newPingSensor : newEthernetSensor)
                      .is_active
                  "
                  id="gAct"
                />
                <label for="gAct">Encendido</label>
              </div>
              <div class="form-group checkbox-group">
                <input
                  type="checkbox"
                  v-model="
                    (sensorDetailsToShow.sensor_type === 'ping' ? newPingSensor : newEthernetSensor)
                      .alerts_paused
                  "
                  id="gPau"
                />
                <label for="gPau">Pausar Alertas</label>
              </div>
            </div>
          </div>

          <template v-if="sensorDetailsToShow.sensor_type === 'ping'">
            <div class="form-group span-3">
              <label>Nombre</label><input type="text" v-model="newPingSensor.name" required />
            </div>

            <div class="form-group span-2">
              <label>Tipo</label>
              <select v-model="newPingSensor.config.ping_type" :disabled="!hasParentMaestro">
                <option value="device_to_external">Salida</option>
                <option value="maestro_to_device" v-if="hasParentMaestro">Entrada</option>
              </select>
            </div>

            <div class="form-group" v-if="newPingSensor.config.ping_type === 'device_to_external'">
              <label>IP Destino</label
              ><input type="text" v-model="newPingSensor.config.target_ip" />
            </div>
            <div class="form-group">
              <label>Intervalo</label
              ><input type="number" v-model.number="newPingSensor.config.interval_sec" />
            </div>
            <div class="form-group">
              <label>Umbral (ms)</label
              ><input type="number" v-model.number="newPingSensor.config.latency_threshold_ms" />
            </div>

            <div class="sub-section span-3">
              <h4>Alertas</h4>
              <div class="alert-config-item">
                <div class="form-group checkbox-group">
                  <input type="checkbox" v-model="newPingSensor.ui_alert_timeout.enabled" /><label
                    >Timeout</label
                  >
                </div>
                <div v-if="newPingSensor.ui_alert_timeout.enabled" class="form-group">
                  <label>Canal</label>
                  <select v-model="newPingSensor.ui_alert_timeout.channel_id">
                    <option v-for="c in channelsList" :key="c.id" :value="c.id">
                      {{ c.name }}
                    </option>
                  </select>
                </div>
              </div>
            </div>
          </template>

          <template v-if="sensorDetailsToShow.sensor_type === 'ethernet'">
            <div class="form-group span-2">
              <label>Nombre</label><input type="text" v-model="newEthernetSensor.name" required />
            </div>
            <div class="form-group">
              <label>Interfaz</label
              ><input type="text" v-model="newEthernetSensor.config.interface_name" />
            </div>

            <div class="sub-section span-3">
              <h4>Alertas</h4>
              <div class="alert-config-item">
                <div class="form-group checkbox-group">
                  <input
                    type="checkbox"
                    v-model="newEthernetSensor.ui_alert_speed_change.enabled"
                  /><label>Velocidad</label>
                </div>
                <div v-if="newEthernetSensor.ui_alert_speed_change.enabled" class="form-group">
                  <label>Canal</label>
                  <select v-model="newEthernetSensor.ui_alert_speed_change.channel_id">
                    <option v-for="c in channelsList" :key="c.id" :value="c.id">
                      {{ c.name }}
                    </option>
                  </select>
                </div>
              </div>
            </div>
          </template>

          <div class="modal-actions span-3">
            <button type="button" class="btn-secondary" @click="closeSensorDetails">Cancelar</button
            ><button type="submit" class="btn-primary">Guardar</button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* =========================================
   LAYOUT & SIDEBAR (USANDO VARIABLES DE TEMA)
   ========================================= */
.layout-container {
  display: flex;
  height: 100vh;
  background: var(--bg-color);
  color: #eee;
  overflow: hidden;
}

/* Sidebar */
.sidebar {
  width: 250px;
  background: var(--surface-color);
  border-right: 1px solid var(--primary-color);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  transition: width 0.3s ease;
}
.sidebar.sidebar-collapsed {
  width: 60px;
}

.sidebar-header {
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 1rem;
  border-bottom: 1px solid var(--primary-color);
}
.sidebar-header h3 {
  margin: 0;
  font-size: 1rem;
  color: #fff;
  white-space: nowrap;
  overflow: hidden;
}
.btn-toggle-sidebar {
  background: none;
  border: 1px solid var(--primary-color);
  color: #aaa;
  cursor: pointer;
  padding: 2px 6px;
  border-radius: 4px;
}

.sidebar-actions {
  padding: 1rem;
  border-bottom: 1px solid var(--primary-color);
}
.btn-add-group {
  width: 100%;
  background: var(--blue);
  color: white;
  border: none;
  padding: 0.5rem;
  border-radius: 4px;
  cursor: pointer;
  font-weight: bold;
}

.group-list {
  list-style: none;
  padding: 0;
  margin: 0;
  overflow-y: auto;
  flex-grow: 1;
}
.group-list li {
  padding: 0.8rem 1rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 10px;
  border-left: 3px solid transparent;
  transition: background 0.2s;
  height: 50px;
}
.group-list li:hover {
  background: rgba(255, 255, 255, 0.05);
}
.group-list li.active {
  background: rgba(255, 255, 255, 0.1);
  border-left-color: var(--blue);
}

.group-name {
  flex-grow: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  font-size: 0.9rem;
}
.badge {
  background: var(--bg-color);
  padding: 2px 6px;
  border-radius: 10px;
  font-size: 0.75rem;
  color: #aaa;
  border: 1px solid var(--primary-color);
}
.status-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  display: block;
  flex-shrink: 0;
}
.dot-green {
  background-color: var(--green);
  box-shadow: 0 0 5px var(--green);
}
.dot-red {
  background-color: var(--secondary-color);
  box-shadow: 0 0 5px var(--secondary-color);
}

/* MAIN CONTENT */
.main-content {
  flex-grow: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  position: relative;
}
.content-header {
  height: 60px;
  padding: 0 2rem;
  border-bottom: 1px solid var(--primary-color);
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-shrink: 0;
  background: var(--surface-color);
}
.content-header h2 {
  margin: 0;
  font-size: 1.4rem;
  color: white;
}
.btn-primary {
  background: var(--blue);
  color: white;
  border: none;
  padding: 0.5rem 1rem;
  border-radius: 4px;
  text-decoration: none;
  font-weight: bold;
}
.empty-selection {
  flex-grow: 1;
  display: flex;
  justify-content: center;
  align-items: center;
  color: #666;
  font-size: 1.2rem;
}

/* =========================================
   GRID & TARJETAS
   ========================================= */
.scroll-area {
  flex-grow: 1;
  overflow-y: auto;
  padding: 2rem;
}
.dashboard-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
  gap: 1.5rem;
}

.monitor-card {
  background-color: var(--surface-color);
  border: 1px solid var(--primary-color);
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  transition: all 0.2s;
}
.monitor-card.status-alert {
  border-color: var(--secondary-color);
  box-shadow: 0 0 8px rgba(255, 100, 100, 0.2);
}
.monitor-card.is-inactive {
  opacity: 0.7;
  border-style: dashed;
}

.card-header {
  background: var(--primary-color);
  padding: 0.6rem 1rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
  cursor: grab;
}
.header-left {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  overflow: hidden;
}
.drag-handle {
  color: rgba(255, 255, 255, 0.5);
  cursor: grab;
  font-size: 1.2rem;
  margin-right: 5px;
}
.title-container h3 {
  margin: 0;
  font-size: 1rem;
  color: #fff;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  display: flex;
  align-items: center;
}
.off-badge {
  background: #444;
  font-size: 0.7rem;
  padding: 1px 4px;
  border-radius: 3px;
  margin-left: 5px;
}
.pause-badge {
  font-size: 0.9rem;
  margin-left: 5px;
}

.card-actions-right {
  display: flex;
  align-items: center;
  gap: 4px;
}
.device-ip {
  font-size: 0.8rem;
  color: #ccc;
  margin-right: 8px;
}
.action-icon-btn {
  background: none;
  border: none;
  font-size: 1.1rem;
  color: #ccc;
  cursor: pointer;
  padding: 2px;
}
.action-icon-btn:hover {
  color: #fff;
}
.active-orange {
  color: #fbbf24;
  opacity: 1;
}
.active-red {
  color: #ff6b6b;
  opacity: 1;
}
.remove-btn {
  color: #ccc;
  font-size: 1.4rem;
  background: none;
  border: none;
  cursor: pointer;
  margin-left: 5px;
}

.card-body {
  padding: 0.8rem;
  flex-grow: 1;
}

/* SENSORES: FLEXBOX PARA ALINEACION */
.sensors-container {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
.sensor-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: var(--bg-color);
  padding: 0.5rem 0.8rem;
  border-radius: 4px;
  border-left: 3px solid transparent;
  cursor: pointer;
  transition: background 0.2s;
}
.sensor-row:hover {
  background: var(--primary-color);
}
.sensor-row.row-paused {
  border-left-color: #fbbf24;
}
.sensor-row.row-inactive {
  opacity: 0.5;
}

.sensor-name {
  font-size: 0.9rem;
  color: #ddd;
  font-weight: 500;
}

/* CONTENEDOR DERECHO DEL SENSOR: DATOS + LAPIZ */
.sensor-status-group {
  display: flex;
  align-items: center;
  gap: 12px;
  text-align: right;
}
.sensor-value {
  font-size: 0.9rem;
  font-family: monospace;
  color: #fff;
}
.text-off {
  color: #666;
  font-weight: bold;
  font-size: 0.8rem;
}

/* ETHERNET DATA RESTAURADO */
.ethernet-data-flex {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  line-height: 1.2;
}
.ethernet-main-status {
  font-weight: bold;
  text-transform: capitalize;
  font-size: 0.85rem;
}
.ethernet-traffic-row {
  font-size: 0.75rem;
  color: #aaa;
  display: flex;
  gap: 8px;
}
.traf-item {
  white-space: nowrap;
}

.status-ok {
  color: var(--green);
}
.status-high-latency {
  color: #facc15;
}
.status-timeout {
  color: var(--secondary-color);
}
.status-pending {
  color: var(--gray);
}

.details-btn {
  background: none;
  border: none;
  color: #666;
  font-size: 1.1rem;
  cursor: pointer;
  padding: 2px;
}
.details-btn:hover {
  color: var(--blue);
}

.collapsed-summary {
  padding: 0.5rem 1rem;
  background: var(--bg-color);
  font-size: 0.85rem;
  text-align: center;
  color: #888;
}
.collapsed-summary.has-alert {
  background: rgba(255, 107, 107, 0.1);
  color: var(--secondary-color);
  font-weight: bold;
}
.summary-ok {
  color: var(--green);
}
.summary-alert {
  color: var(--secondary-color);
}

/* MODALES */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0, 0, 0, 0.7);
  z-index: 2000;
  display: flex;
  justify-content: center;
  align-items: center;
}
.modal-content {
  background: var(--surface-color);
  padding: 2rem;
  border-radius: 8px;
  width: 90%;
  max-width: 650px;
}
.modal-content.small {
  max-width: 400px;
}
.modal-subtitle {
  color: #aaa;
  font-size: 0.9rem;
  margin-top: -0.5rem;
  margin-bottom: 1.5rem;
}
.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 1rem;
  margin-top: 1.5rem;
}
.config-form {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1rem;
}
.form-group {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}
.form-group.span-2 {
  grid-column: span 2;
}
.form-group.span-3 {
  grid-column: span 3;
}
.form-group label {
  font-weight: bold;
  color: #888;
  font-size: 0.8rem;
}
.form-group input,
.form-group select {
  padding: 0.6rem;
  background: var(--bg-color);
  border: 1px solid var(--primary-color);
  border-radius: 4px;
  color: white;
  width: 100%;
}
.full-width-input {
  width: 100%;
  padding: 0.8rem;
  background: var(--bg-color);
  border: 1px solid var(--primary-color);
  border-radius: 4px;
  color: white;
}
.general-config-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
  align-items: end;
}
.sub-section {
  grid-column: span 3;
  background: var(--bg-color);
  padding: 1rem;
  border-radius: 6px;
  border: 1px solid var(--primary-color);
  margin-top: 0.5rem;
}
.sub-section h4 {
  margin: 0 0 0.8rem 0;
  border-bottom: 1px solid var(--primary-color);
  padding-bottom: 0.5rem;
  color: #ccc;
}
.alert-config-item {
  display: contents;
}
.checkbox-group {
  flex-direction: row;
  align-items: center;
  gap: 0.5rem;
}
.text-green {
  color: var(--green);
  font-weight: bold;
}
.text-gray {
  color: #666;
  font-weight: bold;
}
.text-orange {
  color: #fbbf24;
  font-weight: bold;
}
.btn-secondary {
  background: var(--primary-color);
  color: white;
  border: none;
  padding: 0.6rem 1.2rem;
  border-radius: 6px;
  cursor: pointer;
}
.btn-danger {
  background: var(--secondary-color);
  color: white;
  border: none;
  padding: 0.6rem 1.2rem;
  border-radius: 6px;
  cursor: pointer;
}
.btn-danger-outline {
  width: 100%;
  background: transparent;
  color: #ff6b6b;
  border: 1px solid #ff6b6b;
  padding: 0.8rem;
  border-radius: 6px;
  cursor: pointer;
  font-weight: bold;
  transition: all 0.2s;
}
.btn-danger-outline:hover:not(:disabled) {
  background: #ff6b6b;
  color: white;
}
.btn-danger-outline:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.notification {
  position: fixed;
  top: 20px;
  right: 20px;
  padding: 1rem 1.5rem;
  border-radius: 4px;
  z-index: 3000;
  color: white;
  font-weight: bold;
}
.notification.success {
  background: var(--green);
}
.notification.error {
  background: var(--secondary-color);
}
</style>
