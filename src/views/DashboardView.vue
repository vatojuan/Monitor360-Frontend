<script setup>
import { ref, onMounted, onUnmounted, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import api from '@/lib/api'
import { connectWebSocketWhenAuthenticated, getCurrentWebSocket } from '@/lib/ws'
import { waitForSession } from '@/lib/supabase'
import draggable from 'vuedraggable'

const router = useRouter()

// --- ESTADO ---
const allMonitors = ref([])
const groupedMonitors = ref({})
const activeGroup = ref(null)

const liveSensorStatus = ref({})
const monitorToDelete = ref(null)
const collapsedCards = ref(new Set())

// --- Modales y UI ---
const sensorDetailsToShow = ref(null)
const currentMonitorContext = ref(null)
const editMonitorGroup = ref('')
const showGroupModal = ref(false)
const newGroupName = ref('')
const notification = ref({ show: false, message: '', type: 'success' })

// --- COMPUTADOS ---
const hasParentMaestro = computed(() => !!currentMonitorContext.value?.maestro_id)
const channelsById = ref({})
const channelsList = computed(() => Object.values(channelsById.value))
const availableGroups = computed(() => Object.keys(groupedMonitors.value).sort())

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

// --- LÓGICA DE GRUPOS ---

function refreshGroupedMonitors() {
  const groups = {}
  // Ordenar por posición
  const sorted = [...allMonitors.value].sort((a, b) => (a.position || 0) - (b.position || 0))

  sorted.forEach((m) => {
    const gName = m.group_name || 'General'
    if (!groups[gName]) groups[gName] = []
    groups[gName].push(m)
  })
  groupedMonitors.value = groups

  // Seleccionar grupo por defecto si no hay uno activo
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

function addNewGroup() {
  if (!newGroupName.value) return
  if (!groupedMonitors.value[newGroupName.value]) {
    groupedMonitors.value[newGroupName.value] = []
  }
  activeGroup.value = newGroupName.value
  showGroupModal.value = false
  newGroupName.value = ''
}

async function onDragChange() {
  if (!activeGroup.value) return

  const monitorsInGroup = groupedMonitors.value[activeGroup.value]
  const payloadItems = []

  monitorsInGroup.forEach((m, index) => {
    m.position = index
    payloadItems.push({
      monitor_id: m.monitor_id,
      group_name: activeGroup.value,
      position: index,
    })
  })

  try {
    await api.post('/monitors/reorder', { items: payloadItems })
  } catch {
    showNotification('Error guardando orden', 'error')
  }
}

// --- API & LIFECYCLE ---
async function fetchAllMonitors() {
  try {
    const { data } = await api.get('/monitors')
    allMonitors.value = Array.isArray(data) ? data : []
    allMonitors.value.forEach((m) => {
      if (m.is_active === undefined || m.is_active === null) m.is_active = true
      if (m.alerts_paused === undefined || m.alerts_paused === null) m.alerts_paused = false
      ;(m.sensors || []).forEach((s) => {
        const sid = String(s.id)
        if (!liveSensorStatus.value[sid]) liveSensorStatus.value[sid] = { status: 'pending' }
      })
    })
    refreshGroupedMonitors()
    trySubscribeSensors()
  } catch (err) {
    if (import.meta.env.DEV) console.error(err)
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

onMounted(async () => {
  try {
    await waitForSession({ requireAuth: true })
  } catch {
    return
  }
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

// --- MODAL EDICION + CAMBIO DE GRUPO ---
async function showSensorDetails(s, m, e) {
  e?.stopPropagation()
  await ensureChannelsLoaded()
  sensorDetailsToShow.value = s
  currentMonitorContext.value = m
  editMonitorGroup.value = m.group_name || 'Sin Grupo'

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

  // 1. Cambio de Grupo
  const newGroup = editMonitorGroup.value
  if (newGroup !== currentMonitorContext.value.group_name) {
    try {
      await api.put(`/monitors/${currentMonitorContext.value.monitor_id}`, { group_name: newGroup })
      const mLocal = allMonitors.value.find(
        (m) => m.monitor_id === currentMonitorContext.value.monitor_id,
      )
      if (mLocal) mLocal.group_name = newGroup
      refreshGroupedMonitors()
      // Saltamos al grupo nuevo para que el usuario vea su cambio
      activeGroup.value = newGroup
    } catch (e) {
      if (import.meta.env.DEV) console.error(e)
    }
  }

  // 2. Actualizar Sensor
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

    showNotification('Guardado correctamente')
    if (payload.is_active !== sensorDetailsToShow.value.is_active) trySubscribeSensors()
    closeSensorDetails()
  } catch {
    showNotification('Error al guardar', 'error')
  }
}
function closeSensorDetails() {
  sensorDetailsToShow.value = null
  currentMonitorContext.value = null
}
</script>

<template>
  <div class="layout-container">
    <aside class="sidebar">
      <div class="sidebar-header">
        <h3>GRUPOS</h3>
        <button class="btn-add-group" @click="showGroupModal = true" title="Crear Grupo">+</button>
      </div>
      <ul class="group-list">
        <li
          v-for="gName in Object.keys(groupedMonitors).sort()"
          :key="gName"
          :class="{ active: activeGroup === gName }"
          @click="activeGroup = gName"
        >
          <span :class="['status-dot', getGroupStatusClass(gName)]"></span>
          <span class="group-name">{{ gName }}</span>
          <span class="badge">{{ groupedMonitors[gName].length }}</span>
        </li>
      </ul>
    </aside>

    <main class="main-content">
      <header class="content-header" v-if="activeGroup">
        <h2>{{ activeGroup }}</h2>
        <div class="header-actions">
          <router-link to="/monitor-builder" class="btn-primary">Añadir Dispositivo</router-link>
        </div>
      </header>
      <div v-else class="empty-selection">
        <p>Selecciona o crea un grupo para comenzar</p>
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
                  <div class="title-wrapper">
                    <h3>
                      {{ monitor.client_name }}
                      <span v-if="!monitor.is_active" class="off-badge">OFF</span>
                      <span v-if="monitor.alerts_paused" class="pause-badge">⏸️</span>
                    </h3>
                  </div>
                </div>

                <div class="card-actions-right">
                  <span class="device-ip" v-if="!collapsedCards.has(monitor.monitor_id)">{{
                    monitor.ip_address
                  }}</span>

                  <span v-if="getOverallCardStatus(monitor)" class="alert-icon">⚠️</span>

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
                          <span class="val-off">OFF</span>
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
                          <div class="ethernet-data">
                            <span class="ethernet-status">
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
                              class="ethernet-traffic"
                              v-if="liveSensorStatus[String(sensor.id)]?.status !== 'pending'"
                            >
                              ↓
                              {{ formatBitrate(liveSensorStatus[String(sensor.id)]?.rx_bitrate) }} /
                              ↑ {{ formatBitrate(liveSensorStatus[String(sensor.id)]?.tx_bitrate) }}
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

              <div v-else class="card-body collapsed-summary">
                <span v-if="getOverallCardStatus(monitor)" class="summary-alert"
                  >⚠️ Problemas detectados</span
                >
                <span v-else class="summary-ok"
                  >Todo Operativo ({{ monitor.sensors.length }} sensores)</span
                >
              </div>
            </div>
          </template>
        </draggable>
      </div>
    </main>

    <div v-if="showGroupModal" class="modal-overlay" @click.self="showGroupModal = false">
      <div class="modal-content small">
        <h3>Crear Nuevo Grupo</h3>
        <input
          v-model="newGroupName"
          placeholder="Nombre (Ej: Clientes VIP)"
          class="full-width-input"
        />
        <div class="modal-actions">
          <button class="btn-secondary" @click="showGroupModal = false">Cancelar</button>
          <button class="btn-primary" @click="addNewGroup">Crear</button>
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

        <form
          v-if="sensorDetailsToShow.sensor_type === 'ping'"
          @submit.prevent="handleUpdateSensor"
          class="config-form"
        >
          <div class="sub-section span-3">
            <h4>Configuración General</h4>
            <div class="general-config-grid">
              <div class="form-group checkbox-group">
                <input type="checkbox" v-model="newPingSensor.is_active" id="pActive" />
                <label for="pActive" :class="newPingSensor.is_active ? 'text-green' : 'text-gray'">
                  {{ newPingSensor.is_active ? '🟢 ENCENDIDO' : '⚫ APAGADO' }}
                </label>
              </div>
              <div class="form-group checkbox-group">
                <input type="checkbox" v-model="newPingSensor.alerts_paused" id="pPause" />
                <label for="pPause" :class="newPingSensor.alerts_paused ? 'text-orange' : ''">
                  {{ newPingSensor.alerts_paused ? '⏸️ ALERTAS PAUSADAS' : '🔔 ALERTAS ACTIVAS' }}
                </label>
              </div>
              <div class="form-group" style="grid-column: span 2">
                <label>Mover a Grupo</label>
                <select v-model="editMonitorGroup">
                  <option v-for="g in availableGroups" :key="g" :value="g">{{ g }}</option>
                  <option value="Sin Grupo">Sin Grupo</option>
                </select>
              </div>
            </div>
          </div>

          <div class="form-group span-3">
            <label>Nombre</label><input type="text" v-model="newPingSensor.name" required />
          </div>
          <div class="form-group span-2">
            <label>Tipo</label>
            <select v-model="newPingSensor.config.ping_type" :disabled="!hasParentMaestro">
              <option value="device_to_external">Salida (Desde Disp.)</option>
              <option value="maestro_to_device" v-if="hasParentMaestro">
                Entrada (Desde Maestro)
              </option>
            </select>
          </div>
          <div class="form-group" v-if="newPingSensor.config.ping_type === 'device_to_external'">
            <label>IP Destino</label><input type="text" v-model="newPingSensor.config.target_ip" />
          </div>
          <div class="form-group">
            <label>Intervalo (s)</label
            ><input type="number" v-model.number="newPingSensor.config.interval_sec" />
          </div>
          <div class="form-group">
            <label>Umbral (ms)</label
            ><input type="number" v-model.number="newPingSensor.config.latency_threshold_ms" />
          </div>
          <div class="form-group">
            <label>Modo</label
            ><select v-model="newPingSensor.config.display_mode">
              <option value="realtime">Tiempo Real</option>
              <option value="average">Promedio</option>
            </select>
          </div>
          <div class="form-group" v-if="newPingSensor.config.display_mode === 'average'">
            <label>Muestras</label
            ><input type="number" v-model.number="newPingSensor.config.average_count" />
          </div>

          <div class="sub-section span-3">
            <h4>Alertas</h4>
            <div class="alert-config-item">
              <div class="form-group checkbox-group span-3">
                <input
                  type="checkbox"
                  v-model="newPingSensor.ui_alert_timeout.enabled"
                  id="eTo"
                /><label for="eTo">Timeout</label>
              </div>
              <template v-if="newPingSensor.ui_alert_timeout.enabled">
                <div class="form-group">
                  <label>Canal</label
                  ><select v-model="newPingSensor.ui_alert_timeout.channel_id">
                    <option v-for="c in channelsList" :key="c.id" :value="c.id">
                      {{ c.name }}
                    </option>
                  </select>
                </div>
                <div class="form-group">
                  <label>CD (min)</label
                  ><input
                    type="number"
                    v-model.number="newPingSensor.ui_alert_timeout.cooldown_minutes"
                  />
                </div>
                <div class="form-group">
                  <label>Tol</label
                  ><input
                    type="number"
                    v-model.number="newPingSensor.ui_alert_timeout.tolerance_count"
                  />
                </div>
              </template>
            </div>
            <div class="alert-config-item mt-1">
              <div class="form-group checkbox-group span-3">
                <input
                  type="checkbox"
                  v-model="newPingSensor.ui_alert_latency.enabled"
                  id="eLat"
                /><label for="eLat">Latencia Alta</label>
              </div>
              <template v-if="newPingSensor.ui_alert_latency.enabled">
                <div class="form-group">
                  <label>Umbral</label
                  ><input
                    type="number"
                    v-model.number="newPingSensor.ui_alert_latency.threshold_ms"
                  />
                </div>
                <div class="form-group">
                  <label>Canal</label
                  ><select v-model="newPingSensor.ui_alert_latency.channel_id">
                    <option v-for="c in channelsList" :key="c.id" :value="c.id">
                      {{ c.name }}
                    </option>
                  </select>
                </div>
                <div class="form-group">
                  <label>CD (min)</label
                  ><input
                    type="number"
                    v-model.number="newPingSensor.ui_alert_latency.cooldown_minutes"
                  />
                </div>
              </template>
            </div>
          </div>
          <div class="modal-actions span-3">
            <button type="button" class="btn-secondary" @click="closeSensorDetails">Cancelar</button
            ><button type="submit" class="btn-primary">Guardar</button>
          </div>
        </form>

        <form
          v-if="sensorDetailsToShow.sensor_type === 'ethernet'"
          @submit.prevent="handleUpdateSensor"
          class="config-form"
        >
          <div class="sub-section span-3">
            <h4>Configuración General</h4>
            <div class="general-config-grid">
              <div class="form-group checkbox-group">
                <input type="checkbox" v-model="newEthernetSensor.is_active" id="eActive" />
                <label
                  for="eActive"
                  :class="newEthernetSensor.is_active ? 'text-green' : 'text-gray'"
                  >{{ newEthernetSensor.is_active ? '🟢 ENCENDIDO' : '⚫ APAGADO' }}</label
                >
              </div>
              <div class="form-group checkbox-group">
                <input type="checkbox" v-model="newEthernetSensor.alerts_paused" id="ePause" />
                <label for="ePause" :class="newEthernetSensor.alerts_paused ? 'text-orange' : ''">{{
                  newEthernetSensor.alerts_paused ? '⏸️ ALERTAS PAUSADAS' : '🔔 ALERTAS ACTIVAS'
                }}</label>
              </div>
              <div class="form-group" style="grid-column: span 2">
                <label>Mover a Grupo</label>
                <select v-model="editMonitorGroup">
                  <option v-for="g in availableGroups" :key="g" :value="g">{{ g }}</option>
                  <option value="Sin Grupo">Sin Grupo</option>
                </select>
              </div>
            </div>
          </div>

          <div class="form-group span-2">
            <label>Nombre</label><input type="text" v-model="newEthernetSensor.name" required />
          </div>
          <div class="form-group">
            <label>Interfaz</label
            ><input type="text" v-model="newEthernetSensor.config.interface_name" required />
          </div>
          <div class="form-group span-3">
            <label>Intervalo (s)</label
            ><input type="number" v-model.number="newEthernetSensor.config.interval_sec" required />
          </div>

          <div class="sub-section span-3">
            <h4>Alertas</h4>
            <div class="alert-config-item">
              <div class="form-group checkbox-group span-3">
                <input
                  type="checkbox"
                  v-model="newEthernetSensor.ui_alert_speed_change.enabled"
                  id="eSp"
                /><label for="eSp">Cambio de Velocidad</label>
              </div>
              <template v-if="newEthernetSensor.ui_alert_speed_change.enabled">
                <div class="form-group">
                  <label>Canal</label
                  ><select v-model="newEthernetSensor.ui_alert_speed_change.channel_id">
                    <option v-for="c in channelsList" :key="c.id" :value="c.id">
                      {{ c.name }}
                    </option>
                  </select>
                </div>
                <div class="form-group">
                  <label>CD (min)</label
                  ><input
                    type="number"
                    v-model.number="newEthernetSensor.ui_alert_speed_change.cooldown_minutes"
                  />
                </div>
              </template>
            </div>
            <div class="alert-config-item mt-1">
              <div class="form-group checkbox-group span-3">
                <input
                  type="checkbox"
                  v-model="newEthernetSensor.ui_alert_traffic.enabled"
                  id="eTr"
                /><label for="eTr">Umbral Tráfico</label>
              </div>
              <template v-if="newEthernetSensor.ui_alert_traffic.enabled">
                <div class="form-group">
                  <label>Mbps</label
                  ><input
                    type="number"
                    v-model.number="newEthernetSensor.ui_alert_traffic.threshold_mbps"
                  />
                </div>
                <div class="form-group">
                  <label>Canal</label
                  ><select v-model="newEthernetSensor.ui_alert_traffic.channel_id">
                    <option v-for="c in channelsList" :key="c.id" :value="c.id">
                      {{ c.name }}
                    </option>
                  </select>
                </div>
              </template>
            </div>
          </div>
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
/* LAYOUT GLOBAL (MASTER-DETAIL) */
.layout-container {
  display: flex;
  height: 100vh;
  overflow: hidden;
  background: #121212;
  color: #eee;
}

/* SIDEBAR IZQUIERDO */
.sidebar {
  width: 250px;
  background: #1a1a1a;
  border-right: 1px solid #333;
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
}
.sidebar-header {
  padding: 1.5rem 1rem;
  border-bottom: 1px solid #333;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.sidebar-header h3 {
  margin: 0;
  font-size: 1rem;
  color: #fff;
  letter-spacing: 1px;
  font-weight: bold;
}
.btn-add-group {
  background: var(--blue);
  border: none;
  color: white;
  width: 24px;
  height: 24px;
  border-radius: 4px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.2rem;
}

.group-list {
  list-style: none;
  padding: 0;
  margin: 0;
  overflow-y: auto;
  flex-grow: 1;
}
.group-list li {
  padding: 1rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 0.8rem;
  transition: background 0.2s;
  border-left: 3px solid transparent;
}
.group-list li:hover {
  background: #252525;
}
.group-list li.active {
  background: #2a2a2a;
  border-left-color: var(--blue);
}
.group-name {
  flex-grow: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  font-size: 0.95rem;
}
.badge {
  background: #333;
  font-size: 0.75rem;
  padding: 2px 6px;
  border-radius: 10px;
  color: #aaa;
}
.status-dot {
  width: 8px;
  height: 8px;
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

/* MAIN CONTENT (DERECHA) */
.main-content {
  flex-grow: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  position: relative;
}
.content-header {
  padding: 1rem 2rem;
  background: #1a1a1a;
  border-bottom: 1px solid #333;
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-shrink: 0;
}
.content-header h2 {
  margin: 0;
  font-size: 1.5rem;
  color: white;
}
.btn-primary {
  background: var(--blue);
  color: white;
  border: none;
  padding: 0.6rem 1.2rem;
  border-radius: 6px;
  font-weight: bold;
  cursor: pointer;
  text-decoration: none;
  display: inline-block;
}
.empty-selection {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100%;
  color: #666;
  font-size: 1.2rem;
}

/* AREA SCROLLABLE Y GRID */
.scroll-area {
  flex-grow: 1;
  overflow-y: auto;
  padding: 2rem;
}
.dashboard-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  gap: 1.5rem;
}

/* TARJETAS (Estilos Originales Restaurados) */
.monitor-card {
  background-color: var(--surface-color);
  border-radius: 12px;
  border: 1px solid var(--primary-color);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  transition: opacity 0.3s;
}
.monitor-card.status-alert {
  border-color: var(--secondary-color);
  box-shadow: 0 0 8px var(--secondary-color);
}
.monitor-card.is-inactive {
  opacity: 0.6;
  border-style: dashed;
  border-color: #444;
}
.monitor-card.is-collapsed {
  height: auto;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  padding: 0.5rem 1rem;
  background-color: var(--primary-color);
  cursor: grab;
}
.card-header:active {
  cursor: grabbing;
}
.header-left {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  overflow: hidden;
}
.drag-handle {
  color: rgba(255, 255, 255, 0.6);
  font-size: 1.2rem;
  cursor: grab;
  margin-right: 0.3rem;
}
.title-wrapper h3 {
  margin: 0;
  font-size: 1.1rem;
  color: white;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
.off-badge {
  background: #444;
  font-size: 0.7rem;
  padding: 2px 5px;
  border-radius: 4px;
}
.pause-badge {
  font-size: 0.9rem;
}

.card-actions-right {
  display: flex;
  align-items: center;
  gap: 0.25rem;
}
.device-ip {
  font-size: 0.85rem;
  color: #ccc;
  margin-right: 0.5rem;
}
.alert-icon {
  font-size: 1.25rem;
}
.action-icon-btn {
  background: none;
  border: none;
  font-size: 1.2rem;
  color: rgba(255, 255, 255, 0.8);
  cursor: pointer;
  padding: 0 3px;
  transition: opacity 0.2s;
}
.action-icon-btn:hover {
  opacity: 1;
  color: white;
}
.active-orange {
  color: #fbbf24;
  text-shadow: 0 0 5px orange;
  opacity: 1;
}
.active-red {
  color: #ff6b6b;
  text-shadow: 0 0 5px red;
  opacity: 1;
}
.remove-btn {
  background: none;
  border: none;
  color: #ccc;
  font-size: 1.5rem;
  cursor: pointer;
  margin-left: 0.5rem;
}
.remove-btn:hover {
  color: #d9534f;
}

.card-body {
  padding: 1rem;
  flex-grow: 1;
}
.collapsed-summary {
  padding: 0.5rem 1rem;
  background-color: #222;
  font-size: 0.85rem;
  text-align: center;
  font-style: italic;
  color: #aaa;
  border-top: 1px solid #333;
}
.summary-alert {
  color: var(--secondary-color);
  font-weight: bold;
}
.summary-ok {
  color: var(--green);
}

/* SENSORES (Estilos Originales Restaurados) */
.sensors-container {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}
.no-sensors {
  font-style: italic;
  color: var(--gray);
  text-align: center;
  padding: 1rem;
}
.sensor-row {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 1rem;
  align-items: center;
  background-color: var(--bg-color);
  padding: 0.6rem 0.8rem;
  border-radius: 6px;
  cursor: pointer;
  transition: background-color 0.2s;
  border-left: 3px solid transparent;
}
.sensor-row:hover {
  background-color: var(--primary-color);
}
.sensor-row.row-paused {
  border-left-color: orange;
}
.sensor-row.row-inactive {
  opacity: 0.5;
}

.sensor-name {
  font-size: 0.9rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.sensor-value {
  text-align: right;
}
.val-off {
  color: #666;
  font-weight: bold;
  font-size: 0.8rem;
  letter-spacing: 1px;
}

/* ETHERNET DATA ORIGINAL */
.ethernet-data {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
}
.ethernet-status {
  font-weight: bold;
  font-size: 0.95rem;
  text-transform: capitalize;
}
.ethernet-speed {
  font-weight: normal;
  color: var(--gray);
  font-size: 0.85rem;
  margin-left: 0.25rem;
}
.ethernet-traffic {
  font-size: 0.8rem;
  color: var(--gray);
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
  color: var(--gray);
  font-size: 1.2rem;
  cursor: pointer;
  width: 30px;
  height: 30px;
  line-height: 30px;
  text-align: center;
  border-radius: 50%;
}
.details-btn:hover {
  background-color: rgba(255, 255, 255, 0.1);
  color: var(--blue);
}

/* MODALS Y FORMULARIOS */
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
  border-radius: 12px;
  width: 92%;
  max-width: 800px;
  max-height: 90vh;
  overflow-y: auto;
  text-align: left;
}
.modal-content.small {
  max-width: 400px;
}
.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 1rem;
  margin-top: 1.5rem;
}

.config-form {
  padding: 1rem;
  background-color: var(--bg-color);
  border-radius: 8px;
  border: 1px solid var(--primary-color);
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
  color: var(--gray);
  font-size: 0.85rem;
}
.form-group input,
.form-group select {
  padding: 0.6rem;
  background-color: var(--surface-color);
  border: 1px solid var(--primary-color);
  border-radius: 6px;
  color: white;
  width: 100%;
}
.general-config-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 1rem;
  align-items: end;
}
.sub-section {
  grid-column: span 3;
  background: var(--surface-color);
  padding: 1rem;
  border-radius: 8px;
  margin-top: 0.5rem;
  border: 1px solid var(--primary-color);
}
.sub-section h4 {
  margin: 0 0 0.5rem 0;
  border-bottom: 1px solid #444;
  padding-bottom: 0.5rem;
}
.alert-config-item {
  display: contents;
}
.alert-config-item > .form-group {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0.5rem;
  grid-column: span 3;
  align-items: center;
  margin-bottom: 0.5rem;
}
.checkbox-group {
  flex-direction: row;
  align-items: center;
  gap: 0.5rem;
}
.c-green {
  color: var(--green);
  font-weight: bold;
}
.c-gray {
  color: #666;
  font-weight: bold;
}
.c-orange {
  color: #fbbf24;
  font-weight: bold;
}
.mt-1 {
  margin-top: 1rem;
}

/* UTILS */
.btn-secondary {
  background: var(--primary-color);
  color: white;
  border: none;
  padding: 0.6rem 1.2rem;
  border-radius: 6px;
  font-weight: bold;
  cursor: pointer;
}
.btn-danger {
  background: var(--secondary-color);
  color: white;
  border: none;
  padding: 0.6rem 1.2rem;
  border-radius: 6px;
  font-weight: bold;
  cursor: pointer;
}
.notification {
  position: fixed;
  top: 90px;
  right: 20px;
  padding: 1rem 1.5rem;
  border-radius: 8px;
  color: white;
  font-weight: bold;
  z-index: 3000;
}
.notification.success {
  background: var(--green);
}
.notification.error {
  background: var(--secondary-color);
}
</style>
