<script setup>
import { ref, onMounted, onUnmounted, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '@/lib/api'
import { Line } from 'vue-chartjs'
import {
  Chart as ChartJS,
  Title,
  Tooltip,
  Legend,
  LineElement,
  CategoryScale,
  LinearScale,
  PointElement,
  TimeScale,
  Filler,
  Decimation,
} from 'chart.js'
import 'chartjs-adapter-date-fns'
import { es } from 'date-fns/locale'
import zoomPlugin from 'chartjs-plugin-zoom'
import { addWsListener, connectWebSocketWhenAuthenticated, getCurrentWebSocket } from '@/lib/ws'

ChartJS.register(
  Title,
  Tooltip,
  Legend,
  LineElement,
  CategoryScale,
  LinearScale,
  PointElement,
  TimeScale,
  Filler,
  Decimation,
  zoomPlugin,
)

/* -------- Plugins visuales -------- */
const thresholdLinePlugin = {
  id: 'thresholdLine',
  afterDatasetsDraw(chart, _args, opts) {
    if (!opts || !opts.show || typeof opts.y !== 'number') return
    const { ctx, chartArea, scales } = chart
    const yPix = scales.y.getPixelForValue(opts.y)
    if (isNaN(yPix)) return
    ctx.save()
    ctx.strokeStyle = 'rgba(233,69,96,0.9)'
    ctx.setLineDash([6, 6])
    ctx.lineWidth = 1.5
    ctx.beginPath()
    ctx.moveTo(chartArea.left, yPix)
    ctx.lineTo(chartArea.right, yPix)
    ctx.stroke()
    ctx.setLineDash([])
    ctx.fillStyle = 'rgba(233,69,96,0.9)'
    ctx.font = '12px sans-serif'
    ctx.fillText(`Umbral: ${opts.y} ms`, chartArea.left + 8, yPix - 6)
    ctx.restore()
  },
}
const linkDownShadePlugin = {
  id: 'linkDownShade',
  beforeDatasetsDraw(chart, _args, opts) {
    if (!opts || !Array.isArray(opts.ranges) || opts.ranges.length === 0) return
    const { ctx, chartArea, scales } = chart
    ctx.save()
    ctx.fillStyle = 'rgba(233,69,96,0.08)'
    for (const r of opts.ranges) {
      const x1 = scales.x.getPixelForValue(r.startMs)
      const x2 = scales.x.getPixelForValue(r.endMs)
      const left = Math.max(chartArea.left, Math.min(x1, x2))
      const right = Math.min(chartArea.right, Math.max(x1, x2))
      if (isFinite(left) && isFinite(right) && right > left) {
        ctx.fillRect(left, chartArea.top, right - left, chartArea.bottom - chartArea.top)
      }
    }
    ctx.restore()
  },
}
ChartJS.register(thresholdLinePlugin, linkDownShadePlugin)

/* -------- Estado -------- */
const route = useRoute()
const router = useRouter()
const sensorId = Number(route.params.id)

const chartRef = ref(null)
const sensorInfo = ref(null)
const historyData = ref([])
const isLoading = ref(true)
const isSyncing = ref(false)

const timeRange = ref('24h') // solo define la vista inicial
const resolutionMode = ref('raw') // 'raw' | 'auto' (lo pedimos así)

const currentWindow = ref(null) // { startMs, endMs, mode }
const chartKey = computed(() =>
  currentWindow.value
    ? `${currentWindow.value.startMs}-${currentWindow.value.endMs}-${resolutionMode.value}`
    : 'init',
)

const localTz = Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'
const hoursMap = { '1h': 1, '12h': 12, '24h': 24, '7d': 168, '30d': 720 }
const timeRanges = hoursMap

/* -------- Cache -------- */
const historyCache = new Map()
const CACHE_TTL_MS = 5 * 60_000
function cacheGet(key) {
  const e = historyCache.get(key)
  if (e && Date.now() - e.timestamp < CACHE_TTL_MS) return e
  return null
}
function cacheSet(key, data, windowObj) {
  historyCache.set(key, { data, window: windowObj ?? null, timestamp: Date.now() })
}
setInterval(() => {
  const now = Date.now()
  for (const [k, e] of historyCache.entries())
    if (now - e.timestamp > 10 * 60_000) historyCache.delete(k)
}, 60_000)

/* -------- Helpers -------- */
function formatBitrateForChart(bits) {
  const n = Number(bits)
  return !Number.isFinite(n) || n < 0 ? 0 : Number((n / 1_000_000).toFixed(2))
}
function pickTimestamp(obj) {
  if (!obj) return new Date()
  const v = obj.timestamp || obj.ts || obj.time
  const d = new Date(v)
  return isNaN(d.valueOf()) ? new Date() : d
}
const isLongRange = computed(() => timeRange.value === '7d' || timeRange.value === '30d')
const thresholdMs = computed(() => {
  const cfg = sensorInfo.value?.config ?? {}
  return Number(cfg.latency_threshold_ms ?? cfg.latency_threshold_visual ?? 150)
})
function decideMode(startMs, endMs) {
  const visibleHours = Math.max(0, (endMs - startMs) / 1000 / 3600)
  return visibleHours < 24 ? 'raw' : 'auto'
}
function clampToNow(startMs, endMs) {
  const now = Date.now()
  if (endMs <= now) return [startMs, endMs]
  const span = endMs - startMs
  return [now - span, now]
}

/* Unidad de tiempo dinámica por ventana */
const visibleSpanMs = computed(() =>
  currentWindow.value
    ? currentWindow.value.endMs - currentWindow.value.startMs
    : (hoursMap[timeRange.value] ?? 24) * 3600 * 1000,
)
const timeUnit = computed(() => {
  const h = visibleSpanMs.value / 3600000
  if (h <= 2) return 'minute'
  if (h <= 72) return 'hour'
  if (h <= 24 * 60) return 'day'
  if (h <= 24 * 365) return 'month'
  return 'year'
})

/* -------- Fetch centralizado: SIEMPRE history_window -------- */
let historyAbort = null
async function loadWindow(startMs, endMs, mode) {
  if (historyAbort) historyAbort.abort()
  historyAbort = new AbortController()

  // clamp a “no futuro”
  ;[startMs, endMs] = clampToNow(startMs, endMs)
  mode = mode || decideMode(startMs, endMs)

  isLoading.value = true
  try {
    const cacheKey = `${sensorId}:win:${Math.round(startMs)}-${Math.round(endMs)}:${mode}`
    const cached = cacheGet(cacheKey)
    if (cached) {
      historyData.value = cached.data
      currentWindow.value = cached.window || { startMs, endMs, mode }
      resolutionMode.value = mode
      isLoading.value = false
      return
    }
    const startIso = new Date(startMs).toISOString()
    const endIso = new Date(endMs).toISOString()
    const { data } = await api.get(`/sensors/${sensorId}/history_window`, {
      params: { start: startIso, end: endIso, max_points: 1800, mode },
      timeout: 30000,
      signal: historyAbort.signal,
    })
    historyData.value = Array.isArray(data?.items) ? data.items : []
    currentWindow.value = { startMs, endMs, mode }
    resolutionMode.value = mode
    cacheSet(cacheKey, historyData.value, currentWindow.value)
  } catch (err) {
    if (err?.code !== 'ERR_CANCELED') console.error('Error loading window:', err)
    historyData.value = []
  } finally {
    isLoading.value = false
  }
}

/* -------- WebSocket -------- */
function onBusMessage(payload) {
  if (!currentWindow.value) return
  isSyncing.value = true
  setTimeout(() => (isSyncing.value = false), 700)

  const updates = Array.isArray(payload) ? payload : [payload]
  const relevant = updates.filter((u) => u && Number(u.sensor_id) === sensorId)
  if (relevant.length === 0) return

  const { startMs, endMs } = currentWindow.value
  const map = new Map(historyData.value.map((p) => [new Date(p.timestamp).toISOString(), p]))

  for (const u of relevant) {
    const d = pickTimestamp(u)
    const t = d.getTime()
    if (t < startMs || t > endMs) continue
    const key = d.toISOString()
    map.set(key, { ...u, timestamp: key })
  }
  const merged = Array.from(map.values()).sort(
    (a, b) => new Date(a.timestamp) - new Date(b.timestamp),
  )
  historyData.value = merged.filter((p) => {
    const t = new Date(p.timestamp).getTime()
    return t >= startMs && t <= endMs
  })
}

/* -------- Datos para gráfico -------- */
const linkDownIntervals = computed(() => {
  if (sensorInfo.value?.sensor_type !== 'ethernet' || historyData.value.length === 0) return []
  const sorted = [...historyData.value].sort(
    (a, b) => new Date(a.timestamp) - new Date(b.timestamp),
  )
  const ranges = []
  let downStart = null
  for (const p of sorted) {
    const t = new Date(p.timestamp).getTime()
    const st = (p.status || '').toLowerCase()
    if (st === 'link_down') {
      if (downStart === null) downStart = t
    } else if (downStart !== null) {
      ranges.push({ startMs: downStart, endMs: t })
      downStart = null
    }
  }
  if (downStart !== null) {
    const lastT = new Date(sorted[sorted.length - 1].timestamp).getTime()
    ranges.push({ startMs: downStart, endMs: lastT })
  }
  return ranges
})

const chartData = computed(() => {
  if (!sensorInfo.value) return { datasets: [] }
  const points = historyData.value
  const type = sensorInfo.value.sensor_type

  if (type === 'ping') {
    const baseColor = '#5372f0'
    const alarmColor = 'rgba(233,69,96,1)'
    return {
      datasets: [
        {
          label: 'Latencia (ms)',
          backgroundColor: baseColor,
          borderColor: baseColor,
          data: points.map((d) => ({
            x: new Date(d.timestamp).valueOf(),
            y: Number(d.latency_ms ?? 0),
          })),
          tension: 0.2,
          pointRadius: 2,
          pointBackgroundColor: (ctx) => (ctx.raw?.y > thresholdMs.value ? alarmColor : baseColor),
          pointBorderColor: (ctx) => (ctx.raw?.y > thresholdMs.value ? alarmColor : baseColor),
        },
      ],
    }
  }

  if (type === 'ethernet') {
    return {
      datasets: [
        {
          label: 'Descarga (Mbps)',
          backgroundColor: 'rgba(54, 162, 235, 0.5)',
          borderColor: 'rgba(54, 162, 235, 1)',
          data: points.map((d) => ({
            x: new Date(d.timestamp).valueOf(),
            y: formatBitrateForChart(d.rx_bitrate),
          })),
          tension: 0.2,
          pointRadius: 2,
          fill: true,
        },
        {
          label: 'Subida (Mbps)',
          backgroundColor: 'rgba(75, 192, 192, 0.5)',
          borderColor: 'rgba(75, 192, 192, 1)',
          data: points.map((d) => ({
            x: new Date(d.timestamp).valueOf(),
            y: formatBitrateForChart(d.tx_bitrate),
          })),
          tension: 0.2,
          pointRadius: 2,
          fill: true,
        },
      ],
    }
  }
  return { datasets: [] }
})

/* -------- Pan/Zoom (sin recursiones) -------- */
function viewFromChart(chart) {
  const xScale = chart.scales.x
  let start = xScale.min
  let end = xScale.max
  if (!isFinite(start) || !isFinite(end)) return null
  ;[start, end] = clampToNow(start, end)
  return { start, end, mode: decideMode(start, end) }
}
const handleViewChange = ({ chart }) => {
  const v = viewFromChart(chart)
  if (!v) return
  loadWindow(v.start, v.end, v.mode)
}

const chartOptions = computed(() => {
  const isPing = sensorInfo.value?.sensor_type === 'ping'
  const xMin = currentWindow.value?.startMs
  const xMax = currentWindow.value?.endMs

  return {
    responsive: true,
    maintainAspectRatio: false,
    animation: { duration: 0 },
    parsing: false,
    spanGaps: true,
    scales: {
      x: {
        type: 'time',
        min: xMin,
        max: xMax,
        adapters: { date: { locale: es } },
        time: {
          unit: timeUnit.value,
          displayFormats: {
            minute: 'HH:mm',
            hour: 'dd MMM HH:mm',
            day: 'dd MMM',
            month: 'MMM yyyy',
            year: 'yyyy',
          },
        },
        ticks: { autoSkip: true, maxTicksLimit: 8, maxRotation: 0, minRotation: 0 },
      },
      y: { beginAtZero: true },
    },
    plugins: {
      legend: { display: sensorInfo.value?.sensor_type === 'ethernet' },
      decimation: { enabled: true, algorithm: 'min-max', samples: 1500 },
      thresholdLine: { show: isPing, y: thresholdMs.value },
      linkDownShade: { ranges: linkDownIntervals.value },
      zoom: {
        pan: { enabled: true, mode: 'x', onPanComplete: handleViewChange },
        zoom: {
          wheel: { enabled: true },
          pinch: { enabled: true },
          drag: {
            enabled: true,
            backgroundColor: 'rgba(83,114,240,0.15)',
            borderColor: 'rgba(83,114,240,0.6)',
            borderWidth: 1,
          },
          mode: 'x',
          limits: { x: { minRange: 1000 * 60 * 5 } },
          onZoomComplete: handleViewChange,
        },
      },
    },
    interaction: { mode: 'nearest', intersect: false },
  }
})

/* -------- Controles (atrás/adelante/zoom/reset) -------- */
function ensureWindow() {
  if (!currentWindow.value) {
    const end = Date.now()
    const start = end - (hoursMap[timeRange.value] ?? 24) * 3600 * 1000
    currentWindow.value = { startMs: start, endMs: end, mode: isLongRange.value ? 'auto' : 'raw' }
  }
  return currentWindow.value
}
async function shiftWindow(direction = -1) {
  const cw = ensureWindow()
  const span = cw.endMs - cw.startMs
  const step = Math.max(span * 0.8, 5 * 60 * 1000)
  let start = cw.startMs + step * direction
  let end = cw.endMs + step * direction
  ;[start, end] = clampToNow(start, end)
  const mode = decideMode(start, end)
  await loadWindow(start, end, mode)
}
async function zoomBy(factor = 0.5) {
  const cw = ensureWindow()
  const span = cw.endMs - cw.startMs
  const center = cw.startMs + span / 2
  let newSpan = Math.max(span * factor, 5 * 60 * 1000)
  let start = center - newSpan / 2
  let end = center + newSpan / 2
  ;[start, end] = clampToNow(start, end)
  const mode = decideMode(start, end)
  await loadWindow(start, end, mode)
}
function goLive() {
  const end = Date.now()
  const start = end - (hoursMap[timeRange.value] ?? 24) * 3600 * 1000
  loadWindow(start, end, isLongRange.value ? 'auto' : 'raw')
}
function resetZoom() {
  goLive()
}

/* -------- Rango inicial -------- */
function setRange(range) {
  timeRange.value = range
  goLive()
}

/* -------- Ciclo de vida -------- */
let offBus = null
onMounted(async () => {
  try {
    const { data } = await api.get(`/sensors/${sensorId}/details`)
    sensorInfo.value = data

    await connectWebSocketWhenAuthenticated()
    offBus = addWsListener(onBusMessage)
    const ws = getCurrentWebSocket()
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'subscribe_sensors', sensor_ids: [sensorId] }))
    }
    goLive()
  } catch (err) {
    console.error('Error loading sensor details:', err)
    router.push('/')
  }
})
onUnmounted(() => {
  if (offBus) offBus()
  if (historyAbort) historyAbort.abort()
})
watch(timeRange, () => goLive())

/* -------- Tabla de eventos -------- */
const linkStatusEvents = computed(() => {
  if (sensorInfo.value?.sensor_type !== 'ethernet' || historyData.value.length === 0) return []
  const events = []
  let lastStatus = null,
    lastSpeed = null
  historyData.value.forEach((d) => {
    if (d.status !== lastStatus || d.speed !== lastSpeed) {
      events.push({
        timestamp: new Intl.DateTimeFormat('es-AR', {
          dateStyle: 'medium',
          timeStyle: 'medium',
        }).format(new Date(d.timestamp)),
        status: d.status,
        speed: d.speed,
      })
      lastStatus = d.status
      lastSpeed = d.speed
    }
  })
  return events.reverse()
})
</script>

<template>
  <div class="detail-view">
    <button @click="router.push('/')" class="back-button">‹ Volver al Dashboard</button>

    <div v-if="sensorInfo" class="monitor-header">
      <h1>{{ sensorInfo.name }}</h1>
      <p>
        Sensor en <strong>{{ sensorInfo.client_name }}</strong> ({{ sensorInfo.ip_address }})
      </p>
    </div>

    <!-- Barra: rangos + controles -->
    <div class="time-controls">
      <div class="range-selector">
        <button
          v-for="(hours, range) in timeRanges"
          :key="range"
          @click="setRange(range)"
          :class="{ active: timeRange === range }"
        >
          {{ range }}
        </button>
      </div>

      <div class="chart-toolbar">
        <button @click="shiftWindow(-1)" title="Ir hacia atrás (80% ventana)">◀ Atrás</button>
        <button @click="goLive()" title="Ir a ahora">● Hoy</button>
        <button @click="shiftWindow(1)" title="Ir hacia adelante (80% ventana)">Adelante ▶</button>
        <span class="sep"></span>
        <button @click="zoomBy(0.5)" title="Acercar (zoom in)">＋</button>
        <button @click="zoomBy(2)" title="Alejar (zoom out)">－</button>
        <span class="sep"></span>
        <button @click="resetZoom" title="Resetear vista">Reset</button>
      </div>
    </div>

    <div class="chart-container">
      <div v-if="isSyncing" class="sync-overlay">
        <span class="dot"></span> Actualizando datos en tiempo real...
      </div>

      <Line
        v-if="!isLoading && historyData.length > 0"
        :key="chartKey"
        ref="chartRef"
        :data="chartData"
        :options="chartOptions"
      />

      <div v-else class="loading-overlay">
        <p>
          {{
            isLoading
              ? 'Cargando datos...'
              : 'No hay historial para este rango o la consulta tardó demasiado.'
          }}
        </p>
      </div>

      <div class="tz-hint">
        Mostrando horas en tu zona: <strong>{{ localTz }}</strong>
      </div>
    </div>

    <div
      v-if="sensorInfo?.sensor_type === 'ethernet' && linkStatusEvents.length > 0"
      class="events-container"
    >
      <h3>Historial de Eventos del Enlace</h3>
      <table class="events-table">
        <thead>
          <tr>
            <th>Fecha y Hora</th>
            <th>Evento</th>
            <th>Velocidad</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(event, index) in linkStatusEvents" :key="index">
            <td>{{ event.timestamp }}</td>
            <td>
              <span :class="['status-badge', event.status]">
                <span v-if="event.status === 'link_up'">✓ Enlace Activo</span>
                <span v-else-if="event.status === 'link_down'">✗ Enlace Caído</span>
                <span v-else>{{ event.status }}</span>
              </span>
            </td>
            <td>{{ event.status === 'link_up' ? event.speed : 'N/A' }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<style scoped>
.detail-view {
  max-width: 1200px;
  margin: auto;
}
.back-button {
  background: none;
  border: 1px solid var(--primary-color);
  color: var(--font-color);
  padding: 0.5rem 1rem;
  border-radius: 6px;
  cursor: pointer;
  margin-bottom: 1rem;
}
.monitor-header {
  background-color: var(--surface-color);
  padding: 1.25rem 1.5rem;
  border-radius: 12px;
  margin-bottom: 0.75rem;
}
.monitor-header h1 {
  margin: 0 0 0.35rem 0;
}
.monitor-header p {
  margin: 0;
  color: var(--gray);
}

/* Barra: rangos + controles */
.time-controls {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.75rem;
  margin-bottom: 0.75rem;
  padding: 0.75rem;
  background-color: var(--surface-color);
  border-radius: 12px;
}
.range-selector {
  display: flex;
  gap: 0.5rem;
}
.time-controls button {
  background-color: var(--primary-color);
  color: var(--font-color);
  border: none;
  padding: 0.45rem 0.8rem;
  border-radius: 6px;
  cursor: pointer;
  line-height: 1;
}
.time-controls button:hover {
  background-color: #5372f0;
}
.time-controls button.active {
  background-color: var(--blue);
  color: white;
}
.chart-toolbar {
  display: flex;
  align-items: center;
  gap: 0.4rem;
}
.chart-toolbar .sep {
  width: 1px;
  height: 22px;
  background: var(--primary-color);
  opacity: 0.6;
  margin: 0 0.4rem;
}

.chart-container {
  background-color: var(--surface-color);
  padding: 1.1rem 1.1rem 1.5rem;
  border-radius: 12px;
  height: 520px;
  position: relative;
}
.loading-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  justify-content: center;
  align-items: center;
}
.tz-hint {
  position: absolute;
  left: 1rem;
  bottom: 0.5rem;
  color: var(--gray);
  font-size: 0.85rem;
}

/* overlay de sincronización */
.sync-overlay {
  position: absolute;
  top: 10px;
  left: 10px;
  background: rgba(0, 0, 0, 0.4);
  color: #fff;
  padding: 4px 10px;
  border-radius: 8px;
  font-size: 0.8rem;
  display: flex;
  align-items: center;
  gap: 6px;
  z-index: 15;
  backdrop-filter: blur(2px);
}
.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background-color: #4caf50;
  animation: blink 1s infinite alternate;
}
@keyframes blink {
  from {
    opacity: 1;
  }
  to {
    opacity: 0.3;
  }
}

.events-container {
  background-color: var(--surface-color);
  padding: 1.1rem 1.3rem;
  border-radius: 12px;
  margin-top: 0.8rem;
}
.events-container h3 {
  margin: 0 0 0.9rem 0;
}
.events-table {
  width: 100%;
  border-collapse: collapse;
}
.events-table th,
.events-table td {
  padding: 0.6rem 0.9rem;
  text-align: left;
  border-bottom: 1px solid var(--primary-color);
}
.events-table th {
  color: var(--gray);
  font-size: 0.9rem;
  text-transform: uppercase;
}
.status-badge {
  padding: 0.25rem 0.55rem;
  border-radius: 12px;
  font-weight: 600;
  font-size: 0.85rem;
}
.status-badge.link_up {
  background-color: rgba(61, 220, 132, 0.2);
  color: var(--green);
}
.status-badge.link_down {
  background-color: rgba(233, 69, 96, 0.2);
  color: var(--secondary-color);
}
</style>
