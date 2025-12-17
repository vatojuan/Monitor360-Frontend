<script setup>
import { ref, onMounted, onUnmounted, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import api from '@/lib/api'
import { connectWebSocketWhenAuthenticated, getCurrentWebSocket } from '@/lib/ws'
import { waitForSession } from '@/lib/supabase'

const router = useRouter()

const monitors = ref([])
const liveSensorStatus = ref({})
const monitorToDelete = ref(null)

// --- Estado para el Modal de Edición ---
const sensorDetailsToShow = ref(null) // El sensor original siendo editado
const currentMonitorContext = ref(null) // El monitor padre (para contexto de IP/Maestro)
const notification = ref({ show: false, message: '', type: 'success' })

// --- COMPUTADO: Lógica de negocio para Ping ---
const hasParentMaestro = computed(() => {
  // Verificamos si el monitor (dispositivo) tiene un maestro_id asignado.
  return !!currentMonitorContext.value?.maestro_id
})

// Formularios Reactivos (mismo esquema que MonitorBuilder)
const createNewPingSensor = () => ({
  name: '',
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
  config: {
    interface_name: '',
    interval_sec: 30,
  },
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

// --- Canales ---
const channelsById = ref({})
const channelsList = computed(() => Object.values(channelsById.value)) // Para los select

async function ensureChannelsLoaded() {
  if (Object.keys(channelsById.value).length) return
  try {
    const { data } = await api.get('/channels')
    const map = {}
    ;(Array.isArray(data) ? data : []).forEach((c) => {
      map[c.id] = c
    })
    channelsById.value = map
  } catch (e) {
    if (import.meta?.env?.DEV) console.error(e)
  }
}

// --- Helpers Formato ---
function formatBitrate(bits) {
  const n = Number(bits)
  if (!Number.isFinite(n) || n <= 0) return '0 Kbps'
  const kbps = n / 1000
  if (kbps < 1000) return `${kbps.toFixed(1)} Kbps`
  const mbps = kbps / 1000
  return `${mbps.toFixed(1)} Mbps`
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

function showNotification(message, type = 'success') {
  notification.value = { show: true, message, type }
  setTimeout(() => {
    notification.value.show = false
  }, 4000)
}

function safeJsonParse(v, fallback = {}) {
  if (typeof v === 'object' && v !== null) return v
  try {
    return JSON.parse(v)
  } catch {
    return fallback
  }
}

/**
 * Normaliza payload WS
 */
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
    if (raw.type === 'sensor_batch' && Array.isArray(raw.items)) return raw.items
    if (['sensor_update', 'sensor-status'].includes(raw.type) || raw.event === 'sensor_update') {
      const inner = raw.data || raw.payload || raw.sensor || raw.body || null
      if (inner && typeof inner === 'object') return [inner]
    }
    if (['welcome', 'ready', 'pong', 'hello'].includes(raw.type)) return []
    if (Object.prototype.hasOwnProperty.call(raw, 'sensor_id')) return [raw]
  }
  return []
}

/* ================= SUBSCRIPCIÓN ================ */
const lastSubscribedIds = ref([])

function currentSensorIds() {
  const ids = []
  for (const m of monitors.value) {
    for (const s of m.sensors || []) ids.push(s.id)
  }
  return ids
}

function trySubscribeSensors() {
  const ws = getCurrentWebSocket()
  if (!ws || ws.readyState !== WebSocket.OPEN) return
  const ids = currentSensorIds()
  if (!ids.length) return

  const same =
    ids.length === lastSubscribedIds.value.length &&
    ids.every((v, i) => v === lastSubscribedIds.value[i])
  if (same) return

  try {
    ws.send(JSON.stringify({ type: 'subscribe_sensors', sensor_ids: ids }))
    lastSubscribedIds.value = ids.slice()
  } catch {
    /* ignore */
  }
}

watch(
  () => monitors.value.map((m) => (m.sensors || []).map((s) => s.id)).flat(),
  () => trySubscribeSensors(),
)

// =========================================================
// GESTIÓN DE WEBSOCKET
// =========================================================
let wsOpenUnbind = null
let directMsgUnbind = null

function handleRawMessage(event) {
  try {
    const txt = event.data
    if (txt.includes('pong')) return
    const parsed = JSON.parse(txt)
    const updates = normalizeWsPayload(parsed)
    if (updates.length > 0) {
      for (const u of updates) {
        if (u && u.sensor_id != null) {
          const sid = String(u.sensor_id)
          const currentData = liveSensorStatus.value[sid] || {}
          liveSensorStatus.value[sid] = { ...currentData, ...u }
        }
      }
    }
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

  directMsgUnbind = () => {
    try {
      ws.removeEventListener('message', handleRawMessage)
    } catch {
      /* ignore */
    }
  }

  const sendSyncAndSubs = () => {
    try {
      ws.send(JSON.stringify({ type: 'sync_request', resource: 'sensors_latest' }))
    } catch {
      /* ignore */
    }
    trySubscribeSensors()
  }

  if (ws.readyState === WebSocket.OPEN) sendSyncAndSubs()

  const onOpen = () => sendSyncAndSubs()
  ws.addEventListener('open', onOpen)

  wsOpenUnbind = () => {
    try {
      ws.removeEventListener('open', onOpen)
    } catch {
      /* ignore */
    }
  }
}

/* ====================== Lifecycle ========================= */
onMounted(async () => {
  try {
    await waitForSession({ requireAuth: true, timeoutMs: 8000 })
  } catch {
    try {
      router.push({ name: 'login' })
    } catch {
      /* ignore */
    }
    return
  }

  await fetchAllMonitors()
  try {
    await connectWebSocketWhenAuthenticated()
  } catch {
    /* ignore */
  }
  wireWsSyncAndSubs()
})

onUnmounted(() => {
  if (typeof wsOpenUnbind === 'function') wsOpenUnbind()
  if (typeof directMsgUnbind === 'function') directMsgUnbind()
})

/* ====================== API ========================= */
async function fetchAllMonitors() {
  try {
    const { data } = await api.get('/monitors')
    monitors.value = Array.isArray(data) ? data : []
    monitors.value.forEach((m) => {
      ;(m.sensors || []).forEach((s) => {
        const sid = String(s.id)
        if (!liveSensorStatus.value[sid]) liveSensorStatus.value[sid] = { status: 'pending' }
      })
    })
    trySubscribeSensors()
  } catch (err) {
    if (import.meta?.env?.DEV) console.error(err)
    monitors.value = []
  }
}

/* ====================== UI Actions ========================= */
function requestDeleteMonitor(monitor, event) {
  if (event?.stopPropagation) event.stopPropagation()
  monitorToDelete.value = monitor
}

async function confirmDeleteMonitor() {
  if (!monitorToDelete.value) return
  try {
    await api.delete(`/monitors/${monitorToDelete.value.monitor_id}`)
    monitors.value = monitors.value.filter((m) => m.monitor_id !== monitorToDelete.value.monitor_id)
  } catch {
    /* ignore */
  } finally {
    monitorToDelete.value = null
  }
}

function getOverallCardStatus(monitor) {
  if (!monitor.sensors || monitor.sensors.length === 0) return false
  return monitor.sensors.some((sensor) => {
    const sid = String(sensor.id)
    const status = liveSensorStatus.value[sid]?.status
    return ['timeout', 'error', 'high_latency', 'link_down'].includes(status)
  })
}

function goToSensorDetail(sensorId) {
  router.push(`/sensor/${sensorId}`)
}

/* ====================== EDICIÓN DE SENSOR (MODAL) ========================= */

// Abre el modal y rellena el formulario correspondiente
async function showSensorDetails(sensor, monitor, event) {
  if (event?.stopPropagation) event.stopPropagation()
  await ensureChannelsLoaded()

  sensorDetailsToShow.value = sensor
  currentMonitorContext.value = monitor

  const cfg = safeJsonParse(sensor.config, {})

  if (sensor.sensor_type === 'ping') {
    const uiData = createNewPingSensor()
    uiData.name = sensor.name
    uiData.config = { ...uiData.config, ...cfg }

    // CORRECCIÓN LÓGICA:
    // Si abrimos un sensor 'maestro_to_device' pero el monitor NO tiene padre (maestro_id es null),
    // forzamos visualmente a 'device_to_external' para evitar guardar configuraciones rotas.
    if (!monitor.maestro_id) {
      uiData.config.ping_type = 'device_to_external'
    }

    ;(cfg.alerts || []).forEach((a) => {
      if (a.type === 'timeout') uiData.ui_alert_timeout = { enabled: true, ...a }
      if (a.type === 'high_latency') uiData.ui_alert_latency = { enabled: true, ...a }
    })
    newPingSensor.value = uiData
  } else if (sensor.sensor_type === 'ethernet') {
    const uiData = createNewEthernetSensor()
    uiData.name = sensor.name
    uiData.config = {
      interface_name: cfg.interface_name || '',
      interval_sec: cfg.interval_sec || 30,
    }
    ;(cfg.alerts || []).forEach((a) => {
      if (a.type === 'speed_change') uiData.ui_alert_speed_change = { enabled: true, ...a }
      if (a.type === 'traffic_threshold') uiData.ui_alert_traffic = { enabled: true, ...a }
    })
    newEthernetSensor.value = uiData
  }
}

function closeSensorDetails() {
  sensorDetailsToShow.value = null
  currentMonitorContext.value = null
}

// Construye el payload
function buildPayload(type, data) {
  const config = { ...data.config }

  // SEGURIDAD: Validación final antes de enviar
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
  return { name: data.name, config }
}

async function handleUpdateSensor() {
  if (!sensorDetailsToShow.value) return
  const type = sensorDetailsToShow.value.sensor_type
  const uiData = type === 'ping' ? newPingSensor.value : newEthernetSensor.value

  try {
    const payload = buildPayload(type, uiData)
    const { data } = await api.put(`/sensors/${sensorDetailsToShow.value.id}`, payload)

    // Actualizar lista localmente
    const mIdx = monitors.value.findIndex(
      (m) => m.monitor_id === currentMonitorContext.value.monitor_id,
    )
    if (mIdx !== -1) {
      const sIdx = monitors.value[mIdx].sensors.findIndex(
        (s) => s.id === sensorDetailsToShow.value.id,
      )
      if (sIdx !== -1) {
        monitors.value[mIdx].sensors[sIdx] = { ...monitors.value[mIdx].sensors[sIdx], ...data }
      }
    }

    showNotification('Sensor actualizado correctamente')
    closeSensorDetails()
  } catch (err) {
    showNotification(err?.response?.data?.detail || 'Error al actualizar', 'error')
  }
}
</script>

<template>
  <div>
    <div v-if="notification.show" :class="['notification', notification.type]">
      {{ notification.message }}
    </div>

    <div v-if="monitorToDelete" class="modal-overlay" @click.self="monitorToDelete = null">
      <div class="modal-content small">
        <h3>Confirmar Eliminación</h3>
        <p>
          ¿Seguro que quieres eliminar el monitor para
          <strong>{{ monitorToDelete.client_name }}</strong
          >?
        </p>
        <div class="modal-actions">
          <button class="btn-secondary" @click="monitorToDelete = null">Cancelar</button>
          <button class="btn-danger" @click="confirmDeleteMonitor">Eliminar</button>
        </div>
      </div>
    </div>

    <div v-if="sensorDetailsToShow" class="modal-overlay" @click.self="closeSensorDetails">
      <div class="modal-content">
        <h3>Editar Sensor: {{ sensorDetailsToShow.sensor_type }}</h3>

        <form
          v-if="sensorDetailsToShow.sensor_type === 'ping'"
          @submit.prevent="handleUpdateSensor"
          class="config-form"
        >
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
            <h4>Alertas</h4>
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
            <h4>Alertas</h4>
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

    <main class="dashboard-grid">
      <div v-if="monitors.length === 0" class="empty-state">
        <h3>No hay monitores activos</h3>
        <p>Ve a <router-link to="/monitor-builder" class="link">Añadir Monitor</router-link>.</p>
      </div>

      <div
        v-for="monitor in monitors"
        :key="monitor.monitor_id"
        :class="['monitor-card', { 'status-alert': getOverallCardStatus(monitor) }]"
      >
        <div class="card-header">
          <h3>{{ monitor.client_name }}</h3>
          <span class="device-info-header">{{ monitor.ip_address }}</span>
          <span v-if="getOverallCardStatus(monitor)" class="alert-icon">⚠️</span>
          <button class="remove-btn" @click="requestDeleteMonitor(monitor, $event)">×</button>
        </div>

        <div class="card-body">
          <div class="sensors-container">
            <div v-if="!monitor.sensors || monitor.sensors.length === 0" class="no-sensors">
              Sin sensores.
            </div>
            <div
              v-else
              v-for="sensor in monitor.sensors"
              :key="sensor.id"
              class="sensor-row"
              @click="goToSensorDetail(sensor.id)"
            >
              <span class="sensor-name">{{ sensor.name }}</span>
              <div class="sensor-status-group">
                <div
                  class="sensor-value"
                  :class="getStatusClass(liveSensorStatus[String(sensor.id)]?.status)"
                >
                  <template v-if="sensor.sensor_type === 'ping'">
                    <span v-if="liveSensorStatus[String(sensor.id)]?.status === 'timeout'"
                      >Timeout</span
                    >
                    <span v-else-if="liveSensorStatus[String(sensor.id)]?.status === 'error'"
                      >Error</span
                    >
                    <span v-else-if="liveSensorStatus[String(sensor.id)]?.status === 'pending'"
                      >...</span
                    >
                    <span v-else
                      >{{ formatLatency(liveSensorStatus[String(sensor.id)]?.latency_ms) }} ms</span
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
                        ↓ {{ formatBitrate(liveSensorStatus[String(sensor.id)]?.rx_bitrate) }} / ↑
                        {{ formatBitrate(liveSensorStatus[String(sensor.id)]?.tx_bitrate) }}
                      </span>
                    </div>
                  </template>

                  <template v-else>{{
                    liveSensorStatus[String(sensor.id)]?.status || 'pending'
                  }}</template>
                </div>
                <button class="details-btn" @click="showSensorDetails(sensor, monitor, $event)">
                  ✎
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>

<style scoped>
.dashboard-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  gap: 1.5rem;
}
.monitor-card {
  background-color: var(--surface-color);
  border-radius: 12px;
  border: 1px solid var(--primary-color);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.monitor-card.status-alert {
  border-color: var(--secondary-color);
  box-shadow: 0 0 8px var(--secondary-color);
}
.card-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.75rem 1rem;
  background-color: var(--primary-color);
}
.card-header h3 {
  flex-grow: 1;
  margin: 0;
  font-size: 1.1rem;
  color: white;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.device-info-header {
  font-size: 0.85rem;
  color: var(--gray);
  flex-shrink: 0;
}
.alert-icon {
  font-size: 1.25rem;
}
.remove-btn {
  background: none;
  border: none;
  color: var(--gray);
  font-size: 1.5rem;
  cursor: pointer;
}
.card-body {
  padding: 1rem;
  flex-grow: 1;
}
.sensors-container {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
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
}
.sensor-row:hover {
  background-color: var(--primary-color);
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
.empty-state {
  grid-column: 1 / -1;
  text-align: center;
  background-color: var(--surface-color);
  padding: 4rem;
  border-radius: 12px;
}
.empty-state .link {
  color: var(--blue);
  text-decoration: underline;
  cursor: pointer;
}
.no-sensors {
  color: var(--gray);
  font-style: italic;
  text-align: center;
  padding: 1rem;
}

/* MODALS */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background-color: rgba(0, 0, 0, 0.7);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 2000;
}
.modal-content {
  background-color: var(--surface-color);
  padding: 2rem;
  border-radius: 12px;
  max-width: 800px;
  width: 92%;
  text-align: left;
  max-height: 90vh;
  overflow-y: auto;
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
.modal-actions button {
  padding: 0.6rem 1.2rem;
  border: none;
  border-radius: 6px;
  font-weight: bold;
  cursor: pointer;
}
.btn-secondary {
  background-color: var(--primary-color);
  color: white;
}
.btn-danger {
  background-color: var(--secondary-color);
  color: white;
}
.btn-primary {
  background-color: var(--blue);
  color: white;
}

/* ESTILOS DE FORMULARIO (Igual que Builder) */
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
