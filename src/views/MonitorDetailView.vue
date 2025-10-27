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

/* ChartJS base */
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

/* Plugins visuales */
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

/* Estado */
const route = useRoute()
const router = useRouter()
const sensorId = Number(route.params.id)

const chartRef = ref(null)
const sensorInfo = ref(null)
const historyData = ref([])

/* Carga: stale-while-revalidate */
const isBootLoading = ref(true) // solo la primera carga
const isFetching = ref(false) // refetch no bloqueante
let fetchToken = 0 // coalescing: ignora respuestas viejas

const isZoomed = ref(false)
const timeRange = ref('24h')
const resolutionMode = ref('raw') // interno (sin badge)

/* Ventana visible controlada */
const currentWindow = ref(null) // { startMs, endMs, mode: 'auto' | 'raw' } | null

const localTz = Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'
const hoursMap = { '1h': 1, '12h': 12, '24h': 24, '7d': 168, '30d': 720 }
const timeRanges = hoursMap

/* Cache */
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
  for (const [k, e] of historyCache.entries()) {
    if (now - e.timestamp > 10 * 60_000) historyCache.delete(k)
  }
}, 60_000)

/* Helpers */
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
const thresholdMs = computed(() => {
  const cfg = sensorInfo.value?.config ?? {}
  return Number(cfg.latency_threshold_ms ?? cfg.latency_threshold_visual ?? 150)
})
function debounce(fn, wait = 300) {
  let t = null
  return (...args) => {
    clearTimeout(t)
    t = setTimeout(() => fn(...args), wait)
  }
}
function decideMode(startMs, endMs) {
  const visibleHours = Math.max(0, (endMs - startMs) / 1000 / 3600)
  return visibleHours < 24 ? 'raw' : 'auto'
}

/* Unidad de tiempo dinámica */
const visibleSpanMs = computed(() => {
  if (currentWindow.value) return currentWindow.value.endMs - currentWindow.value.startMs
  const h = hoursMap[timeRange.value] ?? 24
  return h * 3600 * 1000
})
const timeUnit = computed(() => {
  const h = visibleSpanMs.value / 3600000
  if (h <= 2) return 'minute'
  if (h <= 72) return 'hour'
  if (h <= 24 * 60) return 'day'
  if (h <= 24 * 365) return 'month'
  return 'year'
})

/* Fetch (stale-while-revalidate + coalescing) */
let historyAbort = null

async function fetchHistory() {
  if (historyAbort) historyAbort.abort()
  historyAbort = new AbortController()

  const myToken = ++fetchToken
  if (isBootLoading.value) {
    // primera carga: loader de pantalla
  } else {
    isFetching.value = true // refetch no bloqueante
  }

  try {
    const endMs = Date.now()
    const hours = hoursMap[timeRange.value] ?? 24
    const startMs = endMs - hours * 3600 * 1000

    if (isLongRange.value) {
      const cacheKey = `${sensorId}:win:${Math.round(startMs)}-${Math.round(endMs)}:auto`
      const cached = cacheGet(cacheKey)
      if (cached) {
        if (myToken !== fetchToken) return
        historyData.value = cached.data
        currentWindow.value = cached.window || { startMs, endMs, mode: 'auto' }
        resolutionMode.value = 'auto'
      } else {
        const { data } = await api.get(`/sensors/${sensorId}/history_window`, {
          params: {
            start: new Date(startMs).toISOString(),
            end: new Date(endMs).toISOString(),
            max_points: 2000,
            mode: 'auto',
          },
          timeout: 60000,
          signal: historyAbort.signal,
        })
        if (myToken !== fetchToken) return
        historyData.value = Array.isArray(data?.items) ? data.items : []
        currentWindow.value = { startMs, endMs, mode: 'auto' }
        resolutionMode.value = 'auto'
        cacheSet(cacheKey, historyData.value, currentWindow.value)
      }
    } else {
      const cacheKey = `${sensorId}:range:${timeRange.value}`
      const cached = cacheGet(cacheKey)
      if (cached) {
        if (myToken !== fetchToken) return
        historyData.value = cached.data
        currentWindow.value = { startMs, endMs, mode: 'raw' }
        resolutionMode.value = 'raw'
      } else {
        const { data } = await api.get(`/sensors/${sensorId}/history_range`, {
          params: { time_range: timeRange.value },
          timeout: 20000,
          signal: historyAbort.signal,
        })
        if (myToken !== fetchToken) return
        historyData.value = Array.isArray(data) ? data : []
        currentWindow.value = { startMs, endMs, mode: 'raw' }
        resolutionMode.value = 'raw'
        cacheSet(cacheKey, historyData.value, null)
      }
    }
  } catch (err) {
    if (err?.code !== 'ERR_CANCELED') console.error('Error fetching history:', err)
  } finally {
    if (myToken === fetchToken) {
      isBootLoading.value = false
      isFetching.value = false
    }
  }
}

async function fetchHistoryCustomRange(startMs, endMs, mode = 'auto') {
  if (historyAbort) historyAbort.abort()
  historyAbort = new AbortController()

  const myToken = ++fetchToken
  isFetching.value = true // refetch suave

  try {
    const cacheKey = `${sensorId}:win:${Math.round(startMs)}-${Math.round(endMs)}:${mode}`
    const cached = cacheGet(cacheKey)
    if (cached) {
      if (myToken !== fetchToken) return
      historyData.value = cached.data
      currentWindow.value = cached.window || { startMs, endMs, mode }
      resolutionMode.value = mode
      return
    }

    const call = async (m) => {
      const { data } = await api.get(`/sensors/${sensorId}/history_window`, {
        params: {
          start: new Date(startMs).toISOString(),
          end: new Date(endMs).toISOString(),
          max_points: 1800,
          mode: m,
        },
        timeout: 30000,
        signal: historyAbort.signal,
      })
      return Array.isArray(data?.items) ? data.items : []
    }

    let items = await call(mode)
    if (items.length === 0) {
      const alt = mode === 'raw' ? 'auto' : 'raw'
      try {
        const altItems = await call(alt)
        if (altItems.length > 0) {
          items = altItems
          mode = alt
        }
      } catch (e) {
        // fallback silencioso (no interrumpe UI)
        console.debug('history_window alt mode failed', e)
      }
    }

    if (myToken !== fetchToken) return
    historyData.value = items
    currentWindow.value = { startMs, endMs, mode }
    resolutionMode.value = mode
    cacheSet(cacheKey, historyData.value, currentWindow.value)
  } catch (err) {
    if (err?.code !== 'ERR_CANCELED') console.error('Error fetching custom window:', err)
  } finally {
    if (myToken === fetchToken) isFetching.value = false
  }
}

/* WebSocket (sin overlays) */
function onBusMessage(payload) {
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

/* Datos para gráfico */
const linkDownIntervals = computed(() => {
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
  const dataPoints = historyData.value
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
          data: dataPoints.map((d) => ({
            x: new Date(d.timestamp).valueOf(),
            y: Number(d.latency_ms ?? 0),
          })),
          tension: 0.2,
          pointRadius: 2,
          pointBackgroundColor: (ctx) => {
            const v = ctx.raw?.y
            return typeof v === 'number' && v > thresholdMs.value ? alarmColor : baseColor
          },
          pointBorderColor: (ctx) => {
            const v = ctx.raw?.y
            return typeof v === 'number' && v > thresholdMs.value ? alarmColor : baseColor
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

/* Pan/Zoom handlers (debounced + optimista) */
const handleViewChange = debounce(({ chart }) => {
  const xScale = chart.scales.x
  const start = xScale.min
  const end = xScale.max
  if (!isFinite(start) || !isFinite(end)) return

  const mode = decideMode(start, end)
  isZoomed.value = true

  const cw = currentWindow.value
  if (!cw) {
    currentWindow.value = { startMs: start, endMs: end, mode } // optimista
    fetchHistoryCustomRange(start, end, mode)
    return
  }

  const pad = Math.max((end - start) * 0.12, 5 * 60 * 1000) // 12% o 5m
  const needLeft = start < cw.startMs + (cw.endMs - cw.startMs) * 0.05
  const needRight = end > cw.endMs - (cw.endMs - cw.startMs) * 0.05
  const outside = start < cw.startMs || end > cw.endMs

  currentWindow.value = { startMs: start, endMs: end, mode } // optimista

  if (outside || needLeft || needRight || cw.mode !== mode) {
    const newStart = Math.min(start - pad, cw.startMs)
    const newEnd = Math.max(end + pad, cw.endMs)
    fetchHistoryCustomRange(newStart, newEnd, mode)
  }
}, 450)

const handleZoomComplete = (args) => handleViewChange(args)
const handlePanComplete = (args) => handleViewChange(args)

/* Opciones del gráfico */
const chartOptions = computed(() => {
  const isPing = sensorInfo.value?.sensor_type === 'ping'
  const xMin = currentWindow.value?.startMs ?? undefined
  const xMax = currentWindow.value?.endMs ?? undefined

  return {
    responsive: true,
    maintainAspectRatio: false,
    animation: { duration: 0 }, // sin animación para fluidez
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
        ticks: {
          autoSkip: true,
          maxTicksLimit: 8,
          maxRotation: 0,
          minRotation: 0,
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
      thresholdLine: {
        show: isPing,
        y: thresholdMs.value,
      },
      linkDownShade: {
        ranges: linkDownIntervals.value,
      },
      zoom: {
        pan: {
          enabled: true,
          mode: 'x',
          onPanComplete: handlePanComplete,
        },
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
          limits: { x: { minRange: 1000 * 60 * 5 } }, // mínimo 5 minutos visibles
          onZoomComplete: handleZoomComplete,
        },
      },
    },
    interaction: { mode: 'nearest', intersect: false },
  }
})

/* Controles programáticos (optimistas) */
function ensureWindow() {
  if (!currentWindow.value) {
    const endMs = Date.now()
    const hours = hoursMap[timeRange.value] ?? 24
    const startMs = endMs - hours * 3600 * 1000
    currentWindow.value = { startMs, endMs, mode: isLongRange.value ? 'auto' : 'raw' }
  }
  return currentWindow.value
}

function shiftWindow(direction = -1) {
  const cw = ensureWindow()
  const span = cw.endMs - cw.startMs
  const step = Math.max(span * 0.8, 5 * 60 * 1000) // 80% o 5m
  const start = cw.startMs + step * direction
  const end = cw.endMs + step * direction
  const mode = decideMode(start, end)
  isZoomed.value = true
  currentWindow.value = { startMs: start, endMs: end, mode } // optimista
  fetchHistoryCustomRange(start, end, mode)
}

function zoomBy(factor = 0.5) {
  const cw = ensureWindow()
  const span = cw.endMs - cw.startMs
  const center = cw.startMs + span / 2
  const newSpan = Math.max(span * factor, 5 * 60 * 1000) // mínimo 5m
  const start = center - newSpan / 2
  const end = center + newSpan / 2
  const mode = decideMode(start, end)
  isZoomed.value = true
  currentWindow.value = { startMs: start, endMs: end, mode } // optimista
  fetchHistoryCustomRange(start, end, mode)
}

function goLive() {
  isZoomed.value = false
  currentWindow.value = null
  fetchHistory()
}

function resetZoom() {
  goLive()
}

/* Rango */
function setRange(range) {
  timeRange.value = range
  isZoomed.value = false
  currentWindow.value = null
  resolutionMode.value = range === '7d' || range === '30d' ? 'auto' : 'raw'
  fetchHistory()
}

/* Ciclo de vida */
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

    await fetchHistory()
  } catch (err) {
    console.error('Error loading sensor details:', err)
    router.push('/')
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

/* Tabla de eventos */
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

/* Hint sutil si no hay puntos */
const showEmptyHint = computed(() => !isBootLoading.value && historyData.value.length === 0)
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
        <button @click="shiftWindow(-1)" title="Ir hacia atrás (80% de la ventana)">
          ◀ Atrás
        </button>
        <button @click="goLive()" title="Ir a ahora">● Hoy</button>
        <button @click="shiftWindow(1)" title="Ir hacia adelante (80% de la ventana)">
          Adelante ▶
        </button>
        <span class="sep"></span>
        <button @click="zoomBy(0.5)" title="Acercar (zoom in)">＋</button>
        <button @click="zoomBy(2)" title="Alejar (zoom out)">－</button>
        <span class="sep"></span>
        <button @click="resetZoom" title="Resetear vista">Reset</button>
      </div>
    </div>

    <div class="chart-container">
      <!-- barra de progreso fina (no bloqueante) -->
      <div v-show="isFetching" class="top-progress"></div>

      <!-- loader solo en la primera carga -->
      <div v-if="isBootLoading" class="loading-overlay">
        <p>Cargando datos…</p>
      </div>

      <!-- hint sutil si la ventana no tiene puntos -->
      <div v-if="showEmptyHint" class="empty-hint">Sin datos en esta ventana</div>

      <!-- El gráfico se muestra desde la primera carga -->
      <Line v-if="!isBootLoading" ref="chartRef" :data="chartData" :options="chartOptions" />

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
  margin-bottom: 1.25rem;
}
.monitor-header {
  background-color: var(--surface-color);
  padding: 1.25rem 1.5rem;
  border-radius: 12px;
  margin-bottom: 1rem;
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
  display: inline-block;
  width: 1px;
  height: 22px;
  background: var(--primary-color);
  margin: 0 0.4rem;
  opacity: 0.6;
}

/* Chart */
.chart-container {
  background-color: var(--surface-color);
  padding: 1.25rem 1.25rem 1.6rem;
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
  z-index: 10;
}
.empty-hint {
  position: absolute;
  top: 10px;
  right: 12px;
  background: rgba(0, 0, 0, 0.35);
  color: #fff;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 0.8rem;
  z-index: 9;
}
.tz-hint {
  position: absolute;
  left: 1rem;
  bottom: 0.5rem;
  color: var(--gray);
  font-size: 0.85rem;
}

/* barra de progreso fina */
.top-progress {
  position: absolute;
  top: 0;
  left: 0;
  height: 3px;
  width: 100%;
  overflow: hidden;
  background: transparent;
  z-index: 12;
}
.top-progress::before {
  content: '';
  position: absolute;
  left: -40%;
  top: 0;
  height: 100%;
  width: 40%;
  background: linear-gradient(90deg, transparent, var(--blue), transparent);
  animation: indeterminate 1.1s infinite;
  opacity: 0.85;
}
@keyframes indeterminate {
  0% {
    left: -40%;
  }
  50% {
    left: 60%;
  }
  100% {
    left: 110%;
  }
}

/* Tabla eventos */
.events-container {
  background-color: var(--surface-color);
  padding: 1.25rem 1.5rem;
  border-radius: 12px;
  margin-top: 1rem;
}
.events-container h3 {
  margin-top: 0;
  margin-bottom: 1rem;
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
