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
const sensorDetailsToShow = ref(null)

// --- Canales ---
const channelsById = ref({})

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
  return Number.isFinite(n) ? n.toFixed(1) : ms
}

// --- Helpers Visualización ---
function toDisplay(v) {
  try {
    if (v == null) return '—'
    if (typeof v === 'object') return JSON.stringify(v, null, 2)
    return String(v)
  } catch {
    return String(v)
  }
}
function isMultilineValue(v) {
  if (v == null) return false
  if (typeof v === 'object') return true
  const s = String(v).trim()
  return s.includes('\n') || s.length > 80 || s.startsWith('{') || s.startsWith('[')
}

function alertTypeLabel(t) {
  switch (t) {
    case 'timeout':
      return 'Timeout'
    case 'high_latency':
      return 'Latencia alta'
    case 'speed_change':
      return 'Cambio de velocidad'
    case 'traffic_threshold':
      return 'Umbral de tráfico'
    default:
      return t || '—'
  }
}

/**
 * Normaliza payload
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
// GESTIÓN DE WEBSOCKET (Nativo + Sync)
// =========================================================
let wsOpenUnbind = null
let directMsgUnbind = null

// Función para procesar mensajes directamente (Bypass de @/lib/ws)
function handleRawMessage(event) {
  try {
    const txt = event.data
    // Ignorar pongs para rendimiento
    if (txt.includes('pong')) return

    const parsed = JSON.parse(txt)
    const updates = normalizeWsPayload(parsed)

    if (updates.length > 0) {
      for (const u of updates) {
        if (u && u.sensor_id != null) {
          const sid = String(u.sensor_id)
          const currentData = liveSensorStatus.value[sid] || {}
          // Reactividad directa
          liveSensorStatus.value[sid] = { ...currentData, ...u }
        }
      }
    }
  } catch {
    // Ignorar errores de parseo
  }
}

function wireWsSyncAndSubs() {
  const ws = getCurrentWebSocket()
  // Si no hay WS, reintentar un poco después (race condition fix)
  if (!ws) {
    setTimeout(wireWsSyncAndSubs, 500)
    return
  }

  // 1. Escuchar mensajes directamente (Esto es lo que arregla el pintado)
  ws.removeEventListener('message', handleRawMessage) // Evitar duplicados
  ws.addEventListener('message', handleRawMessage)

  directMsgUnbind = () => {
    try {
      ws.removeEventListener('message', handleRawMessage)
    } catch {
      /* ignore */
    }
  }

  // 2. Enviar Sync y Suscripciones
  const sendSyncAndSubs = () => {
    try {
      ws.send(JSON.stringify({ type: 'sync_request', resource: 'sensors_latest' }))
    } catch {
      /* ignore */
    }
    trySubscribeSensors()
  }

  if (ws.readyState === WebSocket.OPEN) {
    sendSyncAndSubs()
  }

  // 3. Manejar reconexiones
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
      router.push({ name: 'login', query: { redirect: router.currentRoute.value.fullPath } })
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

  // Iniciamos la escucha directa
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
        if (!liveSensorStatus.value[sid]) {
          liveSensorStatus.value[sid] = { status: 'pending' }
        }
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

function getStatusClass(status) {
  if (['timeout', 'error', 'link_down'].includes(status)) return 'status-timeout'
  if (status === 'high_latency') return 'status-high-latency'
  if (['ok', 'link_up'].includes(status)) return 'status-ok'
  return 'status-pending'
}

function goToSensorDetail(sensorId) {
  router.push(`/sensor/${sensorId}`)
}

async function showSensorDetails(sensor, event) {
  if (event?.stopPropagation) event.stopPropagation()
  await ensureChannelsLoaded()
  sensorDetailsToShow.value = sensor
}

// --------- Computed ---------
const normalizedConfig = computed(() => {
  if (!sensorDetailsToShow.value) return {}
  const cfg = sensorDetailsToShow.value.config
  if (cfg && typeof cfg === 'string') {
    try {
      return JSON.parse(cfg)
    } catch {
      return {}
    }
  }
  return cfg || {}
})

const formattedSensorConfig = computed(() => {
  const config = normalizedConfig.value
  const details = []
  for (const key in config) {
    if (Object.prototype.hasOwnProperty.call(config, key) && key !== 'alerts') {
      details.push({ key, value: config[key] })
    }
  }
  if (Array.isArray(config.alerts) && config.alerts.length > 0) {
    details.push({ key: 'Alertas configuradas', value: `${config.alerts.length}` })
  }
  return details
})

const alertsForModal = computed(() => {
  const config = normalizedConfig.value
  const arr = Array.isArray(config?.alerts) ? config.alerts : []
  return arr.map((a, idx) => {
    const channel =
      a?.channel_id != null && channelsById.value[a.channel_id]?.name
        ? channelsById.value[a.channel_id].name
        : a?.channel_id != null
          ? `Canal #${a.channel_id}`
          : '—'

    return {
      id: idx,
      typeLabel: alertTypeLabel(a?.type),
      umbral:
        a?.type === 'high_latency' && a?.threshold_ms
          ? `${a.threshold_ms} ms`
          : a?.type === 'traffic_threshold' && a?.threshold_mbps
            ? `${a.threshold_mbps} Mbps`
            : '—',
      direccion: a?.direction || '—',
      channel,
      cooldown: a?.cooldown_minutes != null ? `${a.cooldown_minutes} min` : '5 min',
    }
  })
})
</script>

<template>
  <div>
    <div v-if="monitorToDelete" class="modal-overlay" @click.self="monitorToDelete = null">
      <div class="modal-content">
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

    <div v-if="sensorDetailsToShow" class="modal-overlay" @click.self="sensorDetailsToShow = null">
      <div class="modal-content">
        <h3>Detalles del Sensor: {{ sensorDetailsToShow.name }}</h3>
        <table class="details-table">
          <tbody>
            <tr v-for="item in formattedSensorConfig" :key="item.key">
              <th>{{ item.key }}</th>
              <td>
                <pre v-if="isMultilineValue(item.value)" class="value-pre">{{
                  toDisplay(item.value)
                }}</pre>
                <span v-else>{{ toDisplay(item.value) }}</span>
              </td>
            </tr>
          </tbody>
        </table>
        <div v-if="alertsForModal.length" class="alerts-section">
          <h4>Alertas configuradas</h4>
          <table class="alerts-table">
            <thead>
              <tr>
                <th>Tipo</th>
                <th>Umbral</th>
                <th>Dirección</th>
                <th>Canal</th>
                <th>Cooldown</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in alertsForModal" :key="row.id">
                <td>{{ row.typeLabel }}</td>
                <td>{{ row.umbral }}</td>
                <td>{{ row.direccion }}</td>
                <td>{{ row.channel }}</td>
                <td>{{ row.cooldown }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div class="modal-actions">
          <button class="btn-secondary" @click="sensorDetailsToShow = null">Cerrar</button>
        </div>
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
                    <span v-else>
                      {{ formatLatency(liveSensorStatus[String(sensor.id)]?.latency_ms) }} ms
                    </span>
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

                  <template v-else>
                    {{ liveSensorStatus[String(sensor.id)]?.status || 'pending' }}
                  </template>
                </div>
                <button class="details-btn" @click="showSensorDetails(sensor, $event)">⋮</button>
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
  max-width: 700px;
  width: 92%;
  text-align: left;
  max-height: 80vh;
  overflow: auto;
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
.details-table {
  width: 100%;
  text-align: left;
  margin-top: 1rem;
  border-collapse: collapse;
}
.details-table th,
.details-table td {
  padding: 0.75rem;
  border-bottom: 1px solid var(--primary-color);
  vertical-align: top;
}
.details-table th {
  color: var(--gray);
  text-transform: capitalize;
  width: 220px;
}
.details-table td {
  color: white;
  white-space: normal;
  word-break: break-word;
}
.value-pre {
  background: rgba(255, 255, 255, 0.06);
  padding: 0.6rem 0.75rem;
  border-radius: 8px;
  white-space: pre-wrap;
  word-break: normal;
  font-family:
    ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New',
    monospace;
  font-size: 0.9rem;
  line-height: 1.25rem;
  margin: 0;
}
.alerts-section {
  margin-top: 1.25rem;
}
.alerts-section h4 {
  margin: 0 0 0.5rem 0;
}
.alerts-table {
  width: 100%;
  border-collapse: collapse;
}
.alerts-table th,
.alerts-table td {
  padding: 0.6rem 0.75rem;
  border-bottom: 1px solid var(--primary-color);
}
.alerts-table th {
  color: var(--gray);
  font-size: 0.9rem;
  text-transform: uppercase;
  letter-spacing: 0.02em;
}
.alerts-table td {
  color: white;
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
  font-size: 1.5rem;
  font-weight: bold;
  cursor: pointer;
  border-radius: 50%;
  width: 30px;
  height: 30px;
  line-height: 30px;
  text-align: center;
}
.details-btn:hover {
  background-color: rgba(255, 255, 255, 0.1);
}
</style>
