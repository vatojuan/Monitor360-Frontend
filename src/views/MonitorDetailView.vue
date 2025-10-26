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

/* ────────────────────────────────────────────────────────────────
   Registro base de ChartJS + plugins
   ──────────────────────────────────────────────────────────────── */
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

/* Plugins visuales (Paso 6)
   - thresholdLine: línea horizontal para umbral de latencia
   - linkDownShade: franjas rojas para intervalos link_down en ethernet
*/
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
    // Etiqueta compacta del umbral
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

/* ────────────────────────────────────────────────────────────────
   Estado del componente
   ──────────────────────────────────────────────────────────────── */
const route = useRoute()
const router = useRouter()
const sensorId = Number(route.params.id)

const chartRef = ref(null)
const sensorInfo = ref(null)
const historyData = ref([])
const isLoading = ref(true)
const isZoomed = ref(false)
const timeRange = ref('24h')
const isSyncing = ref(false) // indicador sutil de sincronización

// ventana actual cuando estamos en modo "window" (zoom) o long-range
// { startMs: number, endMs: number, mode: 'auto' | 'raw' } | null
const currentWindow = ref(null)

const localTz = Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'
const hoursMap = { '1h': 1, '12h': 12, '24h': 24, '7d': 168, '30d': 720 }
const timeRanges = hoursMap

/* ────────────────────────────────────────────────────────────────
   Caché de historial (Paso 5)
   ──────────────────────────────────────────────────────────────── */
const historyCache = new Map()
// clave de ejemplo:
//   - rangos:  `${sensorId}:range:${range}`
//   - ventanas: `${sensorId}:win:${startMs}-${endMs}:${mode}`

const CACHE_TTL_MS = 5 * 60_000 // 5 min
function cacheGet(key) {
  const e = historyCache.get(key)
  if (e && Date.now() - e.timestamp < CACHE_TTL_MS) return e
  return null
}
function cacheSet(key, data, windowObj) {
  historyCache.set(key, { data, window: windowObj ?? null, timestamp: Date.now() })
}
// Limpieza cada minuto (borra entradas > 10 min)
setInterval(() => {
  const now = Date.now()
  for (const [k, e] of historyCache.entries()) {
    if (now - e.timestamp > 10 * 60_000) historyCache.delete(k)
  }
}, 60_000)

/* ────────────────────────────────────────────────────────────────
   Helpers
   ──────────────────────────────────────────────────────────────── */
function formatBitrateForChart(bits) {
  const n = Number(bits)
  return !Number.isFinite(n) || n < 0 ? 0 : Number((n / 1_000_000).toFixed(2))
}
function pickTimestamp(obj) {
  if (!obj) return null
  const v = obj.timestamp || obj.ts || obj.time
  if (v) {
    const d = new Date(v)
    if (!isNaN(d.valueOf())) return d
  }
  return new Date()
}
const isLongRange = computed(() => timeRange.value === '7d' || timeRange.value === '30d')

// Umbral visual para ping (Paso 6)
const thresholdMs = computed(() => {
  const cfg = sensorInfo.value?.config ?? {}
  // Acepta latency_threshold_ms o latency_threshold_visual (fallback del backend)
  return Number(cfg.latency_threshold_ms ?? cfg.latency_threshold_visual ?? 150)
})

/* ────────────────────────────────────────────────────────────────
   Fetch con cancelación, cache y timeouts
   ──────────────────────────────────────────────────────────────── */
let historyAbort = null

async function fetchHistory() {
  if (historyAbort) historyAbort.abort()
  historyAbort = new AbortController()

  isLoading.value = true
  try {
    if (isLongRange.value) {
      const endMs = Date.now()
      const hours = hoursMap[timeRange.value] ?? 24
      const startMs = endMs - hours * 3600 * 1000
      const cacheKey = `${sensorId}:win:${Math.round(startMs)}-${Math.round(endMs)}:auto`

      const cached = cacheGet(cacheKey)
      if (cached) {
        historyData.value = cached.data
        currentWindow.value = cached.window
        isLoading.value = false
        return
      }

      const startIso = new Date(startMs).toISOString()
      const endIso = new Date(endMs).toISOString()
      const { data } = await api.get(`/sensors/${sensorId}/history_window`, {
        params: { start: startIso, end: endIso, max_points: 2000, mode: 'auto' },
        timeout: 60000,
        signal: historyAbort.signal,
      })
      historyData.value = Array.isArray(data?.items) ? data.items : []
      currentWindow.value = { startMs, endMs, mode: 'auto' }
      cacheSet(cacheKey, historyData.value, currentWindow.value)
    } else {
      const cacheKey = `${sensorId}:range:${timeRange.value}`
      const cached = cacheGet(cacheKey)
      if (cached) {
        historyData.value = cached.data
        currentWindow.value = null
        isLoading.value = false
        return
      }
      const { data } = await api.get(`/sensors/${sensorId}/history_range`, {
        params: { time_range: timeRange.value },
        timeout: 20000,
        signal: historyAbort.signal,
      })
      historyData.value = Array.isArray(data) ? data : []
      currentWindow.value = null
      cacheSet(cacheKey, historyData.value, null)
    }
  } catch (err) {
    if (err?.code === 'ERR_CANCELED') return
    console.error('Error fetching history:', err)
    historyData.value = []
  } finally {
    isLoading.value = false
  }
}

async function fetchHistoryCustomRange(startMs, endMs, mode = 'auto') {
  if (historyAbort) historyAbort.abort()
  historyAbort = new AbortController()

  try {
    const cacheKey = `${sensorId}:win:${Math.round(startMs)}-${Math.round(endMs)}:${mode}`
    const cached = cacheGet(cacheKey)
    if (cached) {
      historyData.value = cached.data
      currentWindow.value = cached.window
      return
    }

    const startIso = new Date(startMs).toISOString()
    const endIso = new Date(endMs).toISOString()
    const { data } = await api.get(`/sensors/${sensorId}/history_window`, {
      params: { start: startIso, end: endIso, max_points: 1500, mode },
      timeout: 30000,
      signal: historyAbort.signal,
    })
    historyData.value = Array.isArray(data?.items) ? data.items : []
    currentWindow.value = { startMs, endMs, mode }
    cacheSet(cacheKey, historyData.value, currentWindow.value)
  } catch (err) {
    if (err?.code === 'ERR_CANCELED') return
    console.error('Error fetching zoomed history:', err)
  }
}

/* ────────────────────────────────────────────────────────────────
   WebSocket: ingest en vivo (respeta ventana activa o rango)
   ──────────────────────────────────────────────────────────────── */
function onBusMessage(payload) {
  isSyncing.value = true
  setTimeout(() => (isSyncing.value = false), 800)

  const updates = Array.isArray(payload) ? payload : [payload]
  const relevantUpdates = updates.filter((u) => u && Number(u.sensor_id) === sensorId)
  if (relevantUpdates.length === 0) return

  const startBound = currentWindow.value?.startMs ?? null
  const endBound = currentWindow.value?.endMs ?? null

  const dataMap = new Map()
  historyData.value.forEach((point) => {
    const ts = new Date(point.timestamp).toISOString()
    dataMap.set(ts, point)
  })
  relevantUpdates.forEach((point) => {
    const tsDate = pickTimestamp(point)
    const tsMs = tsDate.getTime()
    if (startBound !== null && tsMs < startBound) return
    if (endBound !== null && tsMs > endBound) return
    const ts = tsDate.toISOString()
    dataMap.set(ts, { ...point, timestamp: ts })
  })

  const newHistory = Array.from(dataMap.values())
  newHistory.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp))

  if (startBound !== null || endBound !== null) {
    historyData.value = newHistory.filter((p) => {
      const t = new Date(p.timestamp).getTime()
      if (startBound !== null && t < startBound) return false
      if (endBound !== null && t > endBound) return false
      return true
    })
  } else {
    const nowMs = Date.now()
    const hours = hoursMap[timeRange.value] ?? 24
    const cutoff = nowMs - hours * 3600 * 1000
    historyData.value = newHistory.filter((p) => new Date(p.timestamp).getTime() >= cutoff)
  }
}

/* ────────────────────────────────────────────────────────────────
   Computados de datos para el gráfico
   ──────────────────────────────────────────────────────────────── */
const linkDownIntervals = computed(() => {
  // Solo ethernet y cuando exista historial
  if (sensorInfo.value?.sensor_type !== 'ethernet' || historyData.value.length === 0) return []
  const sorted = [...historyData.value].sort(
    (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime(),
  )
  const ranges = []
  let downStart = null

  for (let i = 0; i < sorted.length; i++) {
    const p = sorted[i]
    const t = new Date(p.timestamp).getTime()
    const st = (p.status || '').toLowerCase()

    if (st === 'link_down') {
      if (downStart === null) downStart = t
    } else {
      if (downStart !== null) {
        ranges.push({ startMs: downStart, endMs: t })
        downStart = null
      }
    }
  }
  // si terminó la serie estando caído, cerrar en el último punto (o ahora)
  if (downStart !== null) {
    const lastT = new Date(sorted[sorted.length - 1].timestamp).getTime()
    ranges.push({ startMs: downStart, endMs: lastT })
  }
  return ranges
})

const chartData = computed(() => {
  if (!sensorInfo.value) return { datasets: [] }
  const dataPoints = historyData.value
  const type = sensorInfo.value.sensor_type

  if (type === 'ping') {
    const baseColor = '#5372f0'
    const alarmColor = 'rgba(233,69,96,1)' // rojo para > umbral

    return {
      datasets: [
        {
          label: 'Latencia (ms)',
          backgroundColor: baseColor,
          borderColor: baseColor,
          data: dataPoints.map((d) => ({
            x: new Date(d.timestamp).valueOf(),
            y: Number(d.latency_ms ?? 0),
          })),
          tension: 0.2,
          pointRadius: 2,
          // Puntos rojos cuando superan el umbral (Paso 6)
          pointBackgroundColor: (ctx) => {
            const v = ctx.raw?.y
            if (typeof v === 'number' && v > thresholdMs.value) return alarmColor
            return baseColor
          },
          pointBorderColor: (ctx) => {
            const v = ctx.raw?.y
            if (typeof v === 'number' && v > thresholdMs.value) return alarmColor
            return baseColor
          },
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
          data: dataPoints.map((d) => ({
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
          data: dataPoints.map((d) => ({
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

const chartOptions = computed(() => {
  const longRange = isLongRange.value
  const isPing = sensorInfo.value?.sensor_type === 'ping'
  return {
    responsive: true,
    maintainAspectRatio: false,
    animation: {
      duration: 250,
      easing: 'easeOutQuart',
      onComplete: () => {
        chartRef.value?.chart.update('none')
      },
    },
    parsing: false,
    spanGaps: true,
    scales: {
      x: {
        type: 'time',
        adapters: { date: { locale: es } },
        time: {
          unit: timeRange.value === '1h' ? 'minute' : longRange ? 'day' : 'hour',
          tooltipFormat: 'dd MMM, HH:mm:ss',
          displayFormats: {
            minute: 'HH:mm',
            hour: 'dd MMM HH:mm',
            day: 'dd MMM',
          },
        },
      },
      y: { beginAtZero: true },
    },
    plugins: {
      legend: { display: sensorInfo.value?.sensor_type === 'ethernet' },
      decimation: {
        enabled: true,
        algorithm: 'min-max',
        samples: 1500,
      },
      // Paso 6: línea de umbral para ping
      thresholdLine: {
        show: isPing,
        y: thresholdMs.value,
      },
      // Paso 6: franjas link_down para ethernet
      linkDownShade: {
        ranges: linkDownIntervals.value,
      },
      zoom: {
        pan: { enabled: true, mode: 'x' },
        zoom: {
          wheel: { enabled: true },
          mode: 'x',
          limits: { x: { minRange: 1000 * 60 * 10 } }, // mínimo 10 minutos visibles
          onZoomComplete: ({ chart }) => {
            const xScale = chart.scales.x
            const start = xScale.min
            const end = xScale.max
            const visibleHours = (end - start) / 1000 / 3600
            isZoomed.value = true

            if (visibleHours < 24 && longRange) {
              fetchHistoryCustomRange(start, end, 'raw')
            } else {
              if (longRange) fetchHistoryCustomRange(start, end, 'auto')
            }
          },
        },
      },
    },
    interaction: { mode: 'nearest', intersect: false },
  }
})

/* ────────────────────────────────────────────────────────────────
   Acciones de UI
   ──────────────────────────────────────────────────────────────── */
function setRange(range) {
  timeRange.value = range
  isZoomed.value = false
  currentWindow.value = null
  chartRef.value?.chart.resetZoom()
  fetchHistory()
}
function resetZoom() {
  chartRef.value?.chart.resetZoom()
  isZoomed.value = false
  currentWindow.value = null
  fetchHistory()
}

/* ────────────────────────────────────────────────────────────────
   Ciclo de vida
   ──────────────────────────────────────────────────────────────── */
let offBus = null

onMounted(async () => {
  try {
    const { data } = await api.get(`/sensors/${sensorId}/details`)
    sensorInfo.value = data
    await fetchHistory()
  } catch (err) {
    console.error('Error loading sensor details:', err)
    router.push('/')
    return
  }

  await connectWebSocketWhenAuthenticated()
  offBus = addWsListener(onBusMessage)

  const ws = getCurrentWebSocket()
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: 'subscribe_sensors', sensor_ids: [sensorId] }))
  }
})

onUnmounted(() => {
  if (offBus) offBus()
  if (historyAbort) historyAbort.abort()
})

watch(timeRange, () => {
  currentWindow.value = null
  fetchHistory()
})

/* ────────────────────────────────────────────────────────────────
   Tabla de eventos de enlace (ethernet)
   ──────────────────────────────────────────────────────────────── */
const linkStatusEvents = computed(() => {
  if (sensorInfo.value?.sensor_type !== 'ethernet' || historyData.value.length === 0) return []
  const events = []
  let lastStatus = null
  let lastSpeed = null
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
    </div>

    <div class="chart-container">
      <!-- indicador de sincronización en vivo -->
      <div v-if="isSyncing" class="sync-overlay">
        <span class="dot"></span> Actualizando datos en tiempo real...
      </div>

      <button v-if="isZoomed" @click="resetZoom" class="reset-zoom-btn">Resetear Zoom</button>

      <Line
        v-if="!isLoading && historyData.length > 0"
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
  margin-bottom: 2rem;
}
.monitor-header {
  background-color: var(--surface-color);
  padding: 1.5rem 2rem;
  border-radius: 12px;
  margin-bottom: 1rem;
}
.monitor-header h1 {
  margin: 0 0 0.5rem 0;
}
.monitor-header p {
  margin: 0;
  color: var(--gray);
}
.time-controls {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 1rem;
  margin-bottom: 1rem;
  padding: 1rem;
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
  padding: 0.5rem 1rem;
  border-radius: 6px;
  cursor: pointer;
}
.time-controls button:hover {
  background-color: #5372f0;
}
.time-controls button.active {
  background-color: var(--blue);
  color: white;
}

.chart-container {
  background-color: var(--surface-color);
  padding: 2rem;
  border-radius: 12px;
  height: 500px;
  position: relative;
}
.reset-zoom-btn {
  position: absolute;
  top: 1rem;
  right: 1rem;
  z-index: 10;
  background-color: var(--secondary-color);
  color: white;
  border: none;
  padding: 0.5rem 1rem;
  border-radius: 6px;
  cursor: pointer;
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
  bottom: 0.75rem;
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
  padding: 1.5rem 2rem;
  border-radius: 12px;
  margin-top: 2rem;
}
.events-container h3 {
  margin-top: 0;
  margin-bottom: 1.5rem;
}
.events-table {
  width: 100%;
  border-collapse: collapse;
}
.events-table th,
.events-table td {
  padding: 0.75rem 1rem;
  text-align: left;
  border-bottom: 1px solid var(--primary-color);
}
.events-table th {
  color: var(--gray);
  font-size: 0.9rem;
  text-transform: uppercase;
}
.status-badge {
  padding: 0.3rem 0.6rem;
  border-radius: 12px;
  font-weight: bold;
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
