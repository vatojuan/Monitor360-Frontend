<script setup>
import { ref, onMounted, onUnmounted, computed, watch, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import api from '@/lib/api'
import { connectWebSocketWhenAuthenticated, getCurrentWebSocket } from '@/lib/ws'
import { waitForSession } from '@/lib/supabase'
import draggable from 'vuedraggable'

const router = useRouter()

// --- ESTADO PRINCIPAL ---
const allMonitors = ref([])
const groupedMonitors = ref({}) // Estructura: { "Grupo A": [monitor1, monitor2], ... }
const groupOrder = ref([])

const liveSensorStatus = ref({})
const monitorToDelete = ref(null)
const collapsedCards = ref(new Set())

// --- Estado Modal Edición Sensor ---
const sensorDetailsToShow = ref(null)
const currentMonitorContext = ref(null)
const notification = ref({ show: false, message: '', type: 'success' })

// --- Estado Gestión de Grupos ---
const showGroupModal = ref(false)
const newGroupName = ref('')

// --- COMPUTADOS ---
const hasParentMaestro = computed(() => !!currentMonitorContext.value?.maestro_id)
const channelsById = ref({})
const channelsList = computed(() => Object.values(channelsById.value))

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

// --- LOGICA DE GRUPOS Y ORDENAMIENTO ---

function refreshGroupedMonitors() {
  const groups = {}
  const sorted = [...allMonitors.value].sort((a, b) => (a.position || 0) - (b.position || 0))

  sorted.forEach((m) => {
    const gName = m.group_name || 'Sin Grupo'
    if (!groups[gName]) groups[gName] = []
    groups[gName].push(m)
  })
  groupedMonitors.value = groups
}

async function onDragChange(evt, groupName) {
  const payloadItems = []

  for (const [gName, monitors] of Object.entries(groupedMonitors.value)) {
    monitors.forEach((m, index) => {
      m.group_name = gName
      m.position = index
      payloadItems.push({
        monitor_id: m.monitor_id,
        group_name: gName,
        position: index,
      })
    })
  }

  try {
    await api.post('/monitors/reorder', { items: payloadItems })
  } catch (e) {
    showNotification('Error guardando el nuevo orden', 'error')
  }
}

function addNewGroup() {
  if (!newGroupName.value) return
  if (!groupedMonitors.value[newGroupName.value]) {
    groupedMonitors.value[newGroupName.value] = []
  }
  showGroupModal.value = false
  newGroupName.value = ''
}

// --- LOGICA COLAPSO ---
function toggleCardCollapse(monitorId) {
  if (collapsedCards.value.has(monitorId)) {
    collapsedCards.value.delete(monitorId)
  } else {
    collapsedCards.value.add(monitorId)
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
    console.error(err)
  }
}

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
function safeJsonParse(v, f = {}) {
  try {
    return JSON.parse(v)
  } catch {
    return f
  }
}
function showNotification(m, t = 'success') {
  notification.value = { show: true, message: m, type: t }
  setTimeout(() => (notification.value.show = false), 4000)
}

async function ensureChannelsLoaded() {
  if (Object.keys(channelsById.value).length) return
  try {
    const { data } = await api.get('/channels')
    data.forEach((c) => (channelsById.value[c.id] = c))
  } catch {
    /* ignore */
  }
}

// WS Logic
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
    m.is_active ? (m.sensors || []).filter((s) => s.is_active).map((s) => s.id) : [],
  )
}

function trySubscribeSensors() {
  const ws = getCurrentWebSocket()
  if (!ws || ws.readyState !== 1) return
  const ids = currentSensorIds()
  ws.send(JSON.stringify({ type: 'subscribe_sensors', sensor_ids: ids }))
}

watch(() => allMonitors.value, trySubscribeSensors, { deep: true })

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

// --- UI ACTIONS ---
async function toggleMonitorActive(monitor) {
  const newVal = !monitor.is_active
  monitor.is_active = newVal
  try {
    await api.put(`/monitors/${monitor.monitor_id}`, { is_active: newVal })
    if (!newVal) trySubscribeSensors()
    showNotification(newVal ? 'Monitor ON' : 'Monitor OFF')
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
    showNotification(newVal ? 'Alertas Pausadas' : 'Alertas Activas')
  } catch {
    monitor.alerts_paused = !newVal
    showNotification('Error', 'error')
  }
}
function getOverallCardStatus(monitor) {
  if (!monitor.is_active) return false
  if (!monitor.sensors?.length) return false
  return monitor.sensors.some((s) => {
    const st = liveSensorStatus.value[String(s.id)]?.status
    return ['timeout', 'error', 'high_latency', 'link_down'].includes(st)
  })
}
async function confirmDeleteMonitor() {
  if (!monitorToDelete.value) return
  try {
    await api.delete(`/monitors/${monitorToDelete.value.monitor_id}`)
    await fetchAllMonitors()
    monitorToDelete.value = null
  } catch {
    /* ignore */
  }
}
function requestDeleteMonitor(m, e) {
  e?.stopPropagation()
  monitorToDelete.value = m
}

// --- EDICION SENSOR ---
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

function buildPayload(type, data) {
  const config = { ...data.config }

  if (type === 'ping' && !currentMonitorContext.value?.maestro_id) {
    config.ping_type = 'device_to_external'
  }

  config.alerts = []
  const num = (v, d) => (typeof v === 'number' && !isNaN(v) ? v : d)

  if (type === 'ping') {
    const t = data.ui_alert_timeout
    if (t.enabled && t.channel_id) {
      config.alerts.push({
        type: 'timeout',
        channel_id: t.channel_id,
        cooldown_minutes: num(t.cooldown_minutes, 5),
        tolerance_count: num(t.tolerance_count, 1),
      })
    }
    const l = data.ui_alert_latency
    if (l.enabled && l.channel_id) {
      config.alerts.push({
        type: 'high_latency',
        threshold_ms: num(l.threshold_ms, 200),
        channel_id: l.channel_id,
        cooldown_minutes: num(l.cooldown_minutes, 5),
        tolerance_count: num(l.tolerance_count, 1),
      })
    }
  } else if (type === 'ethernet') {
    const s = data.ui_alert_speed_change
    if (s.enabled && s.channel_id) {
      config.alerts.push({
        type: 'speed_change',
        channel_id: s.channel_id,
        cooldown_minutes: num(s.cooldown_minutes, 10),
        tolerance_count: num(s.tolerance_count, 1),
      })
    }
    const tr = data.ui_alert_traffic
    if (tr.enabled && tr.channel_id) {
      config.alerts.push({
        type: 'traffic_threshold',
        threshold_mbps: num(tr.threshold_mbps, 100),
        direction: tr.direction,
        channel_id: tr.channel_id,
        cooldown_minutes: num(tr.cooldown_minutes, 5),
        tolerance_count: num(tr.tolerance_count, 1),
      })
    }
  }

  return {
    name: data.name,
    config,
    is_active: data.is_active,
    alerts_paused: data.alerts_paused,
  }
}

async function handleUpdateSensor() {
  if (!sensorDetailsToShow.value) return
  const type = sensorDetailsToShow.value.sensor_type
  const uiData = type === 'ping' ? newPingSensor.value : newEthernetSensor.value

  try {
    const payload = buildPayload(type, uiData)
    const { data } = await api.put(`/sensors/${sensorDetailsToShow.value.id}`, payload)

    const m = allMonitors.value.find((m) => m.monitor_id === currentMonitorContext.value.monitor_id)
    if (m) {
      const idx = m.sensors.findIndex((s) => s.id === sensorDetailsToShow.value.id)
      if (idx !== -1) m.sensors[idx] = { ...m.sensors[idx], ...data }
    }

    showNotification('Sensor actualizado correctamente')
    if (payload.is_active !== sensorDetailsToShow.value.is_active) trySubscribeSensors()
    sensorDetailsToShow.value = null
  } catch (e) {
    showNotification(e.message || 'Error', 'error')
  }
}

function closeSensorDetails() {
  sensorDetailsToShow.value = null
  currentMonitorContext.value = null
}
</script>

<template>
  <div class="dashboard-container">
    <div class="dashboard-toolbar">
      <h2>Panel de Control</h2>
      <button class="btn-primary" @click="showGroupModal = true">+ Nuevo Grupo</button>
    </div>

    <div v-if="notification.show" :class="['notification', notification.type]">
      {{ notification.message }}
    </div>

    <div v-if="showGroupModal" class="modal-overlay" @click.self="showGroupModal = false">
      <div class="modal-content small">
        <h3>Crear Nuevo Grupo</h3>
        <input
          v-model="newGroupName"
          placeholder="Nombre del grupo (Ej: Clientes VIP)"
          class="full-width-input"
        />
        <div class="modal-actions">
          <button class="btn-secondary" @click="showGroupModal = false">Cancelar</button>
          <button class="btn-primary" @click="addNewGroup">Crear</button>
        </div>
      </div>
    </div>

    <div class="board-layout">
      <div
        v-if="allMonitors.length === 0 && Object.keys(groupedMonitors).length === 0"
        class="empty-state"
      >
        <h3>No hay monitores activos</h3>
        <p>Ve a <router-link to="/monitor-builder" class="link">Añadir Monitor</router-link>.</p>
      </div>

      <div v-for="(monitors, groupName) in groupedMonitors" :key="groupName" class="swimlane">
        <div class="swimlane-header">
          <h3>
            {{ groupName }} <span class="count-badge">{{ monitors.length }}</span>
          </h3>
        </div>

        <draggable
          :list="monitors"
          group="monitors"
          item-key="monitor_id"
          class="swimlane-content"
          @change="(evt) => onDragChange(evt, groupName)"
          :animation="200"
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
                  <h3>
                    {{ monitor.client_name }}
                    <span v-if="!monitor.is_active" class="off-badge">OFF</span>
                    <span v-if="monitor.alerts_paused" class="pause-badge">⏸️</span>
                  </h3>
                </div>

                <div class="card-actions">
                  <button
                    class="icon-btn"
                    @click="toggleCardCollapse(monitor.monitor_id)"
                    title="Colapsar/Expandir"
                  >
                    {{ collapsedCards.has(monitor.monitor_id) ? '🔽' : '🔼' }}
                  </button>
                  <button
                    class="icon-btn"
                    :class="{ 'active-orange': monitor.alerts_paused }"
                    @click="toggleMonitorPause(monitor)"
                  >
                    {{ monitor.alerts_paused ? '🔕' : '🔔' }}
                  </button>
                  <button
                    class="icon-btn"
                    :class="{ 'active-red': !monitor.is_active }"
                    @click="toggleMonitorActive(monitor)"
                  >
                    {{ monitor.is_active ? '🔌' : '⚫' }}
                  </button>
                  <button class="remove-btn" @click="requestDeleteMonitor(monitor, $event)">
                    ×
                  </button>
                </div>
              </div>

              <div v-if="!collapsedCards.has(monitor.monitor_id)" class="card-body">
                <div class="device-meta">IP: {{ monitor.ip_address }}</div>
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
                      <small v-if="sensor.alerts_paused" class="pause-icon">⏸️</small>
                    </span>

                    <div class="sensor-status-group">
                      <div
                        class="sensor-value"
                        :class="getStatusClass(liveSensorStatus[String(sensor.id)]?.status)"
                      >
                        <template v-if="!sensor.is_active"
                          ><span class="val-off">OFF</span></template
                        >
                        <template v-else-if="sensor.sensor_type === 'ping'">
                          {{
                            liveSensorStatus[String(sensor.id)]?.status === 'ok'
                              ? formatLatency(liveSensorStatus[String(sensor.id)]?.latency_ms) +
                                ' ms'
                              : liveSensorStatus[String(sensor.id)]?.status || '...'
                          }}
                        </template>
                        <template v-else-if="sensor.sensor_type === 'ethernet'">
                          <div class="eth-mini">
                            <span>{{
                              (liveSensorStatus[String(sensor.id)]?.status || '').replace(
                                'link_',
                                '',
                              )
                            }}</span>
                            <small v-if="liveSensorStatus[String(sensor.id)]?.rx_bitrate">
                              ↓{{ formatBitrate(liveSensorStatus[String(sensor.id)]?.rx_bitrate) }}
                            </small>
                          </div>
                        </template>
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
              <div v-else class="card-collapsed-summary">
                <span v-if="getOverallCardStatus(monitor)" class="summary-alert"
                  >⚠️ Problemas detectados</span
                >
                <span v-else class="summary-ok"
                  >Todo OK ({{ monitor.sensors.length }} sensores)</span
                >
              </div>
            </div>
          </template>
        </draggable>
      </div>
    </div>

    <div v-if="sensorDetailsToShow" class="modal-overlay" @click.self="closeSensorDetails">
      <div class="modal-content">
        <h3>Editar Sensor: {{ sensorDetailsToShow.name }}</h3>

        <form
          v-if="sensorDetailsToShow.sensor_type === 'ping'"
          @submit.prevent="handleUpdateSensor"
          class="config-form"
        >
          <div class="sub-section span-3">
            <h4>Estado del Sensor</h4>
            <div class="alert-config-item">
              <div class="form-group checkbox-group">
                <input type="checkbox" v-model="newPingSensor.is_active" id="pActive" />
                <label for="pActive" :class="newPingSensor.is_active ? 'c-green' : 'c-gray'">
                  {{ newPingSensor.is_active ? '🟢 ENCENDIDO' : '⚫ APAGADO' }}
                </label>
              </div>
              <div class="form-group checkbox-group">
                <input type="checkbox" v-model="newPingSensor.alerts_paused" id="pPause" />
                <label for="pPause" :class="newPingSensor.alerts_paused ? 'c-orange' : ''">
                  {{ newPingSensor.alerts_paused ? '⏸️ ALERTAS PAUSADAS' : '🔔 ALERTAS ACTIVAS' }}
                </label>
              </div>
            </div>
          </div>

          <div class="form-group span-3">
            <label>Nombre</label>
            <input type="text" v-model="newPingSensor.name" required />
          </div>

          <div class="form-group span-2">
            <label>Tipo de Ping</label>
            <select v-model="newPingSensor.config.ping_type" :disabled="!hasParentMaestro">
              <option value="device_to_external">Desde Dispositivo (Salida)</option>
              <option value="maestro_to_device" v-if="hasParentMaestro">
                Al Dispositivo (Entrada)
              </option>
            </select>
            <p v-if="!hasParentMaestro" class="form-hint warning-text">
              ⚠️ Este dispositivo no tiene Maestro asignado. Solo puede hacer ping externo.
            </p>
          </div>

          <div class="form-group" v-if="newPingSensor.config.ping_type === 'device_to_external'">
            <label>IP Destino</label>
            <input type="text" v-model="newPingSensor.config.target_ip" placeholder="8.8.8.8" />
          </div>
          <div class="form-group">
            <label>Intervalo (seg)</label>
            <input type="number" v-model.number="newPingSensor.config.interval_sec" required />
          </div>
          <div class="form-group">
            <label>Umbral Latencia (ms)</label>
            <input type="number" v-model.number="newPingSensor.config.latency_threshold_ms" />
          </div>
          <div class="form-group">
            <label>Modo</label>
            <select v-model="newPingSensor.config.display_mode">
              <option value="realtime">Tiempo Real</option>
              <option value="average">Promedio</option>
            </select>
          </div>
          <div class="form-group" v-if="newPingSensor.config.display_mode === 'average'">
            <label>Muestras para Promedio</label>
            <input type="number" v-model.number="newPingSensor.config.average_count" />
          </div>

          <div class="sub-section span-3">
            <h4>Configuración de Alertas</h4>
            <div class="alert-config-item">
              <div class="form-group checkbox-group span-3">
                <input type="checkbox" v-model="newPingSensor.ui_alert_timeout.enabled" id="eTo" />
                <label for="eTo">Timeout</label>
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
                  <label>Enfriamiento (min)</label
                  ><input
                    type="number"
                    v-model.number="newPingSensor.ui_alert_timeout.cooldown_minutes"
                  />
                </div>
                <div class="form-group">
                  <label>Tolerancia (fallos)</label
                  ><input
                    type="number"
                    v-model.number="newPingSensor.ui_alert_timeout.tolerance_count"
                  />
                </div>
              </template>
            </div>
            <div class="alert-config-item mt-1">
              <div class="form-group checkbox-group span-3">
                <input type="checkbox" v-model="newPingSensor.ui_alert_latency.enabled" id="eLat" />
                <label for="eLat">Latencia Alta</label>
              </div>
              <template v-if="newPingSensor.ui_alert_latency.enabled">
                <div class="form-group">
                  <label>Umbral (ms)</label
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
                  <label>Enfriamiento (min)</label
                  ><input
                    type="number"
                    v-model.number="newPingSensor.ui_alert_latency.cooldown_minutes"
                  />
                </div>
              </template>
            </div>
          </div>

          <div class="modal-actions span-3">
            <button type="button" class="btn-secondary" @click="closeSensorDetails">
              Cancelar
            </button>
            <button type="submit" class="btn-primary">Guardar Cambios</button>
          </div>
        </form>

        <form
          v-if="sensorDetailsToShow.sensor_type === 'ethernet'"
          @submit.prevent="handleUpdateSensor"
          class="config-form"
        >
          <div class="sub-section span-3">
            <h4>Estado del Sensor</h4>
            <div class="alert-config-item">
              <div class="form-group checkbox-group">
                <input type="checkbox" v-model="newEthernetSensor.is_active" id="eActive" />
                <label for="eActive" :class="newEthernetSensor.is_active ? 'c-green' : 'c-gray'">
                  {{ newEthernetSensor.is_active ? '🟢 ENCENDIDO' : '⚫ APAGADO' }}
                </label>
              </div>
              <div class="form-group checkbox-group">
                <input type="checkbox" v-model="newEthernetSensor.alerts_paused" id="ePause" />
                <label for="ePause" :class="newEthernetSensor.alerts_paused ? 'c-orange' : ''">
                  {{
                    newEthernetSensor.alerts_paused ? '⏸️ ALERTAS PAUSADAS' : '🔔 ALERTAS ACTIVAS'
                  }}
                </label>
              </div>
            </div>
          </div>

          <div class="form-group span-2">
            <label>Nombre</label>
            <input type="text" v-model="newEthernetSensor.name" required />
          </div>
          <div class="form-group">
            <label>Interfaz</label>
            <input type="text" v-model="newEthernetSensor.config.interface_name" required />
          </div>
          <div class="form-group span-3">
            <label>Intervalo (seg)</label>
            <input type="number" v-model.number="newEthernetSensor.config.interval_sec" required />
          </div>

          <div class="sub-section span-3">
            <h4>Configuración de Alertas</h4>
            <div class="alert-config-item">
              <div class="form-group checkbox-group span-3">
                <input
                  type="checkbox"
                  v-model="newEthernetSensor.ui_alert_speed_change.enabled"
                  id="eSp"
                />
                <label for="eSp">Cambio de Velocidad</label>
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
                  <label>Enfriamiento (min)</label
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
                />
                <label for="eTr">Umbral Tráfico</label>
              </div>
              <template v-if="newEthernetSensor.ui_alert_traffic.enabled">
                <div class="form-group">
                  <label>Umbral (Mbps)</label
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
            <button type="button" class="btn-secondary" @click="closeSensorDetails">
              Cancelar
            </button>
            <button type="submit" class="btn-primary">Guardar Cambios</button>
          </div>
        </form>
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
  </div>
</template>

<style scoped>
.dashboard-container {
  padding: 1rem;
  color: #eee;
}
.dashboard-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 2rem;
}
.btn-primary {
  background: var(--blue);
  color: white;
  border: none;
  padding: 0.6rem 1.2rem;
  border-radius: 6px;
  cursor: pointer;
}
.full-width-input {
  width: 100%;
  padding: 0.8rem;
  background: #222;
  border: 1px solid #444;
  color: white;
  border-radius: 6px;
  margin-bottom: 1rem;
}

/* SWIMLANES */
.swimlane {
  margin-bottom: 2rem;
}
.swimlane-header {
  border-bottom: 1px solid #444;
  margin-bottom: 1rem;
  padding-bottom: 0.5rem;
  display: flex;
  align-items: center;
}
.swimlane-header h3 {
  margin: 0;
  color: #aaa;
  font-size: 1rem;
  text-transform: uppercase;
  letter-spacing: 1px;
}
.count-badge {
  background: #333;
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 0.8rem;
  margin-left: 0.5rem;
}

.swimlane-content {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
  gap: 1.5rem;
  min-height: 100px; /* Zona de drop visible */
  background: rgba(255, 255, 255, 0.02);
  padding: 1rem;
  border-radius: 8px;
  border: 1px dashed #333;
}

/* CARDS */
.monitor-card {
  background: var(--surface-color);
  border: 1px solid var(--primary-color);
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  transition: all 0.2s;
}
.monitor-card.is-inactive {
  opacity: 0.6;
  border-style: dashed;
}
.monitor-card.status-alert {
  border-color: var(--secondary-color);
  box-shadow: 0 0 10px rgba(255, 0, 0, 0.2);
}
.monitor-card.is-collapsed {
  height: auto;
}

.card-header {
  background: #2a2a2a;
  padding: 0.6rem 1rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
  cursor: grab; /* Para drag */
}
.card-header:active {
  cursor: grabbing;
}
.header-left {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
.drag-handle {
  color: #666;
  font-size: 1.2rem;
  cursor: grab;
  margin-right: 0.5rem;
}
.card-header h3 {
  margin: 0;
  font-size: 1rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.card-actions {
  display: flex;
  gap: 0.3rem;
}
.icon-btn {
  background: none;
  border: none;
  font-size: 1.1rem;
  cursor: pointer;
  opacity: 0.6;
  transition: opacity 0.2s;
}
.icon-btn:hover {
  opacity: 1;
}
.active-orange {
  opacity: 1;
  text-shadow: 0 0 5px orange;
}
.active-red {
  opacity: 1;
  text-shadow: 0 0 5px red;
}

.card-body {
  padding: 1rem;
}
.device-meta {
  font-size: 0.8rem;
  color: #888;
  margin-bottom: 0.8rem;
}
.card-collapsed-summary {
  padding: 0.5rem 1rem;
  font-size: 0.85rem;
  background: #222;
}
.summary-alert {
  color: var(--secondary-color);
  font-weight: bold;
}
.summary-ok {
  color: var(--green);
}

.sensor-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.5rem;
  background: #222;
  margin-bottom: 0.5rem;
  border-radius: 4px;
  border-left: 3px solid transparent;
  cursor: pointer;
}
.sensor-row:hover {
  background: #333;
}
.sensor-row.row-paused {
  border-left-color: orange;
}
.sensor-row.row-inactive {
  opacity: 0.5;
}

.eth-mini {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  font-size: 0.8rem;
  line-height: 1.1;
}
.val-off {
  font-weight: bold;
  color: #555;
}

/* Utilidades */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0, 0, 0, 0.8);
  z-index: 999;
  display: flex;
  justify-content: center;
  align-items: center;
}
.modal-content {
  background: #1e1e1e;
  padding: 2rem;
  border-radius: 8px;
  width: 90%;
  max-width: 600px;
}
.modal-content.small {
  max-width: 400px;
}
.btn-secondary {
  background: #444;
  color: white;
  border: none;
  padding: 0.5rem 1rem;
  border-radius: 4px;
  cursor: pointer;
}
.btn-danger {
  background: #d9534f;
  color: white;
  border: none;
  padding: 0.5rem 1rem;
  border-radius: 4px;
  cursor: pointer;
}
.btn-primary {
  background: var(--blue);
  color: white;
  border: none;
  padding: 0.6rem 1.2rem;
  border-radius: 6px;
  cursor: pointer;
}

/* ESTILOS DE FORMULARIO */
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
.form-group select:disabled {
  opacity: 0.7;
  cursor: not-allowed;
  background-color: #2a2a2a;
}
.warning-text {
  color: #fbbf24;
  font-size: 0.8rem;
  margin-top: 0.25rem;
}

.sub-section {
  grid-column: span 3;
  background-color: var(--surface-color);
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
.mt-1 {
  margin-top: 1rem;
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

.sensor-status-group {
  display: flex;
  align-items: center;
  gap: 0.5rem;
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
  background-color: var(--green);
}
.notification.error {
  background-color: var(--secondary-color);
}
</style>
