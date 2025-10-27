<script setup>
import { ref, reactive, onMounted, onUnmounted, computed, watch } from 'vue'
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

/* ====== CONSTANTES ====== */
const PING_TIMEOUT_MS = 10000
const PING_MAX_HARD = 1000

/* ====== PLUGINS VISUALES ====== */
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

/* ====== ESTADO BASE ====== */
const route = useRoute()
const router = useRouter()
const sensorId = Number(route.params.id)

const chartRef = ref(null)
const sensorInfo = ref(null)

const isBootLoading = ref(true)
const isFetching = ref(false)
let historyAbort = null
let fetchToken = 0

/* ====== VISTA / RANGO ====== */
const timeRange = ref('24h')
const localTz = Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'
const hoursMap = { '1h': 1, '12h': 12, '24h': 24, '7d': 168, '30d': 720 }
const currentWindow = ref(null) // { startMs, endMs, mode }
const lastXRange = ref(null) // para detectar cambios reales en X

/* ====== STORE (raw/auto) ====== */
const store = reactive({
  raw: { startMs: null, endMs: null, map: new Map() },
  auto: { startMs: null, endMs: null, map: new Map() },
})

/* ====== HELPERS ====== */
function decideMode(startMs, endMs) {
  const hours = Math.max(0, (endMs - startMs) / 3600000)
  return hours < 24 ? 'raw' : 'auto'
}
function normalizePoint(p) {
  const ts = new Date(p.timestamp || p.ts || p.time).getTime()
  const iso = new Date(ts).toISOString()
  return { ...p, timestamp: iso, _ms: ts }
}
function mergeItems(mode, items) {
  const target = store[mode]
  for (const raw of items) {
    const p = normalizePoint(raw)
    target.map.set(p._ms, p)
  }
}
function extendRange(mode, startMs, endMs) {
  const t = store[mode]
  if (t.startMs === null || startMs < t.startMs) t.startMs = startMs
  if (t.endMs === null || endMs > t.endMs) t.endMs = endMs
}
function hasCoverage(mode, startMs, endMs, slopMs = 60_000) {
  const t = store[mode]
  if (t.startMs === null || t.endMs === null) return false
  return t.startMs <= startMs + slopMs && t.endMs >= endMs - slopMs
}
function missingSegments(mode, startMs, endMs) {
  const t = store[mode]
  if (t.startMs === null || t.endMs === null) return [{ s: startMs, e: endMs }]
  const segs = []
  if (startMs < t.startMs) segs.push({ s: startMs, e: Math.min(t.startMs, endMs) })
  if (endMs > t.endMs) segs.push({ s: Math.max(t.endMs, startMs), e: endMs })
  return segs.filter((x) => x.e > x.s)
}
function mapToSortedArray(mode, startMs, endMs) {
  const out = []
  store[mode].map.forEach((p) => {
    if (p._ms >= startMs && p._ms <= endMs) out.push(p)
  })
  out.sort((a, b) => a._ms - b._ms)
  return out
}

/* ====== TICKS / TIME UNIT ====== */
const visibleSpanMs = computed(() => {
  if (!currentWindow.value) return (hoursMap[timeRange.value] ?? 24) * 3600000
  return currentWindow.value.endMs - currentWindow.value.startMs
})
const timeUnit = computed(() => {
  const h = visibleSpanMs.value / 3600000
  if (h <= 2) return 'minute'
  if (h <= 72) return 'hour'
  if (h <= 24 * 60) return 'day'
  if (h <= 24 * 365) return 'month'
  return 'year'
})

/* ====== THRESHOLD PING ====== */
const thresholdMs = computed(() => {
  const cfg = sensorInfo.value?.config ?? {}
  return Number(cfg.latency_threshold_ms ?? cfg.latency_threshold_visual ?? 150)
})

/* ====== DATA VISIBLE ====== */
const visibleData = computed(() => {
  if (!currentWindow.value) return []
  const { startMs, endMs, mode } = currentWindow.value
  return mapToSortedArray(mode, startMs, endMs)
})

/* ====== P95 PARA INICIALIZAR Y UNA SOLA VEZ ====== */
function percentile(values, p) {
  if (!values.length) return NaN
  const sorted = [...values].sort((a, b) => a - b)
  const idx = (sorted.length - 1) * p
  const lo = Math.floor(idx),
    hi = Math.ceil(idx)
  if (lo === hi) return sorted[lo]
  const w = idx - lo
  return sorted[lo] * (1 - w) + sorted[hi] * w
}
function calcInitialCap() {
  const vals = visibleData.value
    .map((d) => Number(d.latency_ms ?? 0))
    .filter((v) => Number.isFinite(v) && v > 0 && v < PING_TIMEOUT_MS)
  if (!vals.length) return 200
  return Math.min(Math.max(percentile(vals, 0.95) * 1.1, 120), PING_MAX_HARD)
}

/* ====== ESTADO PERSISTENTE DEL EJE Y ====== */
const yState = reactive({
  min: null, // null => auto
  max: null, // null => auto
  initialized: false, // inicializado una vez con P95
})
watch(visibleData, () => {
  // Inicializamos Y una sola vez cuando hay datos
  if (!yState.initialized && sensorInfo.value?.sensor_type === 'ping' && visibleData.value.length) {
    yState.min = 0
    yState.max = calcInitialCap()
    yState.initialized = true
  }
})

/* ====== EVENTOS LINK DOWN ====== */
const linkDownIntervals = computed(() => {
  if (sensorInfo.value?.sensor_type !== 'ethernet' || visibleData.value.length === 0) return []
  const ranges = []
  let downStart = null
  for (const p of visibleData.value) {
    const st = (p.status || '').toLowerCase()
    if (st === 'link_down') {
      if (downStart === null) downStart = p._ms
    } else if (downStart !== null) {
      ranges.push({ startMs: downStart, endMs: p._ms })
      downStart = null
    }
  }
  if (downStart !== null) {
    const last = visibleData.value[visibleData.value.length - 1]
    ranges.push({ startMs: downStart, endMs: last._ms })
  }
  return ranges
})

/* ====== DATASETS ====== */
function mbps(bits) {
  const n = Number(bits)
  return !Number.isFinite(n) || n < 0 ? 0 : Number((n / 1_000_000).toFixed(2))
}
const chartData = computed(() => {
  if (!sensorInfo.value) return { datasets: [] }
  const pts = visibleData.value
  const type = sensorInfo.value.sensor_type

  if (type === 'ping') {
    const base = '#5372f0'
    const alarm = 'rgba(233,69,96,1)'

    // Línea principal (omitimos outliers/timeout)
    const linePoints = pts.map((d) => {
      const v = Number(d.latency_ms ?? 0)
      const isTimeout = v >= PING_TIMEOUT_MS
      // si hay max definido y v>max => “cortamos” para no aplastar visual
      const isOutOfView = typeof yState.max === 'number' && v > yState.max && !isTimeout
      return { x: d._ms, y: isTimeout || isOutOfView ? null : v }
    })

    // Picos fuera de vista (por encima del max actual) como pines en eje oculto
    const outlierPoints = pts
      .map((d) => {
        const v = Number(d.latency_ms ?? 0)
        const over = typeof yState.max === 'number' && v > yState.max && v < PING_TIMEOUT_MS
        if (over) return { x: d._ms, y: 1, _actual: v }
        return null
      })
      .filter(Boolean)

    // Timeouts como triángulos en eje oculto
    const timeoutPoints = pts
      .filter((d) => Number(d.latency_ms ?? 0) >= PING_TIMEOUT_MS)
      .map((d) => ({ x: d._ms, y: 1, _actual: Number(d.latency_ms ?? PING_TIMEOUT_MS) }))

    return {
      datasets: [
        {
          label: 'Latencia (ms)',
          backgroundColor: base,
          borderColor: base,
          data: linePoints,
          tension: 0.2,
          pointRadius: 2,
          spanGaps: false,
          pointBackgroundColor: (ctx) => {
            const v = ctx.raw?.y
            return typeof v === 'number' && v > thresholdMs.value ? alarm : base
          },
          pointBorderColor: (ctx) => {
            const v = ctx.raw?.y
            return typeof v === 'number' && v > thresholdMs.value ? alarm : base
          },
        },
        {
          label: 'Pico',
          type: 'line',
          yAxisID: 'y_outlier',
          data: outlierPoints,
          showLine: false,
          pointRadius: 4,
          pointHoverRadius: 5,
          pointStyle: 'rectRot',
          backgroundColor: 'rgba(255,193,7,1)',
          borderColor: 'rgba(255,193,7,1)',
          clip: false,
        },
        {
          label: 'Timeout',
          type: 'line',
          yAxisID: 'y_timeout',
          data: timeoutPoints,
          showLine: false,
          pointRadius: 5,
          pointHoverRadius: 6,
          pointStyle: 'triangle',
          backgroundColor: 'rgba(233,69,96,1)',
          borderColor: 'rgba(233,69,96,1)',
          clip: false,
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
          data: pts.map((d) => ({ x: d._ms, y: mbps(d.rx_bitrate) })),
          tension: 0.2,
          pointRadius: 2,
          fill: true,
        },
        {
          label: 'Subida (Mbps)',
          backgroundColor: 'rgba(75, 192, 192, 0.5)',
          borderColor: 'rgba(75, 192, 192, 1)',
          data: pts.map((d) => ({ x: d._ms, y: mbps(d.tx_bitrate) })),
          tension: 0.2,
          pointRadius: 2,
          fill: true,
        },
      ],
    }
  }

  return { datasets: [] }
})

/* ====== OPCIONES (Y con estado propio, zoom/pan XY) ====== */
const chartOptions = computed(() => {
  const xMin = currentWindow.value?.startMs ?? undefined
  const xMax = currentWindow.value?.endMs ?? undefined
  const isPing = sensorInfo.value?.sensor_type === 'ping'

  return {
    responsive: true,
    maintainAspectRatio: false,
    animation: { duration: 0 },
    parsing: false,
    spanGaps: isPing ? false : true,
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
      y: {
        // NO fijamos beginAtZero para permitir pan/zoom real
        min: typeof yState.min === 'number' ? yState.min : undefined,
        max: typeof yState.max === 'number' ? yState.max : undefined,
        grace: '5%',
      },
      y_outlier: { min: 0, max: 1, display: false, grid: { display: false } },
      y_timeout: { min: 0, max: 1, display: false, grid: { display: false } },
    },
    plugins: {
      legend: { display: sensorInfo.value?.sensor_type === 'ethernet' },
      decimation: { enabled: true, algorithm: 'min-max', samples: 1500 },
      thresholdLine: { show: isPing, y: thresholdMs.value },
      linkDownShade: { ranges: linkDownIntervals.value },
      zoom: {
        pan: {
          enabled: true,
          mode: 'xy',
          threshold: 3,
          onPanComplete: onZoomPanDone,
        },
        zoom: {
          wheel: { enabled: true, speed: 0.15 },
          pinch: { enabled: true },
          drag: { enabled: false },
          mode: 'xy',
          limits: { x: { minRange: 5 * 60 * 1000 } },
          onZoomComplete: onZoomPanDone,
        },
      },
      tooltip: {
        callbacks: {
          label(ctx) {
            const ds = ctx.dataset?.label
            if (ds === 'Timeout') return 'Timeout'
            if (ds === 'Pico') {
              const val = ctx.raw?._actual
              return typeof val === 'number' ? `Pico: ${val} ms` : 'Pico'
            }
            const v = ctx.parsed?.y
            return typeof v === 'number' ? `Latencia: ${v} ms` : ''
          },
        },
      },
    },
    interaction: { mode: 'nearest', intersect: false },
  }
})

/* ====== HANDLERS ZOOM/PAN ====== */
function onZoomPanDone({ chart }) {
  const xScale = chart.scales.x
  const yScale = chart.scales.y

  // Persistimos Y tal como quedó tras el gesto (trading-like)
  if (yScale) {
    yState.min = Number.isFinite(yScale.min) ? yScale.min : null
    yState.max = Number.isFinite(yScale.max) ? yScale.max : null
    yState.initialized = true
  }

  // Sólo refetcheamos si cambió X “de verdad”
  if (xScale) {
    const newStart = Math.round(xScale.min)
    const newEnd = Math.round(xScale.max)
    const prev = lastXRange.value
    const EPS = 1000 // 1s
    const changedX =
      !prev || Math.abs(newStart - prev.start) > EPS || Math.abs(newEnd - prev.end) > EPS
    if (changedX) {
      lastXRange.value = { start: newStart, end: newEnd }
      const pad = Math.max((newEnd - newStart) * 0.05, 60_000)
      setView(newStart - pad, newEnd + pad)
    }
  }
}

/* ====== FETCH INCREMENTAL ====== */
async function ensureCoverage(mode, startMs, endMs) {
  if (historyAbort) historyAbort.abort()
  historyAbort = new AbortController()
  const myToken = ++fetchToken

  if (hasCoverage(mode, startMs, endMs)) return
  const segs = missingSegments(mode, startMs, endMs)
  if (segs.length === 0) return

  isFetching.value = true
  try {
    for (const seg of segs) {
      const { data } = await api.get(`/sensors/${sensorId}/history_window`, {
        params: {
          start: new Date(seg.s).toISOString(),
          end: new Date(seg.e).toISOString(),
          max_points: mode === 'raw' ? 1800 : 2000,
          mode,
        },
        timeout: 30000,
        signal: historyAbort.signal,
      })
      if (myToken !== fetchToken) return
      const items = Array.isArray(data?.items) ? data.items : []
      mergeItems(mode, items)
      extendRange(mode, seg.s, seg.e)
    }
  } catch (err) {
    if (err?.code !== 'ERR_CANCELED') console.error('ensureCoverage error:', err)
  } finally {
    if (myToken === fetchToken) isFetching.value = false
  }
}

/* ====== VIEW / RANGO ====== */
async function setView(startMs, endMs) {
  const mode = decideMode(startMs, endMs)
  await ensureCoverage(mode, startMs, endMs)
  currentWindow.value = { startMs, endMs, mode }
  lastXRange.value = { start: startMs, end: endMs }
}

/* ====== CONTROLES DE RANGO ====== */
async function setRange(range) {
  timeRange.value = range
  const endMs = Date.now()
  const startMs = endMs - (hoursMap[range] ?? 24) * 3600 * 1000
  await setView(startMs, endMs)
}
async function shiftWindow(direction = -1) {
  const cw = currentWindow.value
  const now = Date.now()
  const fallbackStart = now - (hoursMap[timeRange.value] ?? 24) * 3600 * 1000
  const start = cw?.startMs ?? fallbackStart
  const end = cw?.endMs ?? now
  const span = end - start
  const step = Math.max(span * 0.8, 5 * 60 * 1000)
  await setView(start + direction * step, end + direction * step)
}
async function zoomBy(factor = 0.5) {
  const cw = currentWindow.value
  const now = Date.now()
  const fallbackStart = now - (hoursMap[timeRange.value] ?? 24) * 3600 * 1000
  const start = cw?.startMs ?? fallbackStart
  const end = cw?.endMs ?? now
  const span = end - start
  const center = start + span / 2
  const newSpan = Math.max(span * factor, 5 * 60 * 1000)
  await setView(center - newSpan / 2, center + newSpan / 2)
}
async function goLive() {
  const endMs = Date.now()
  const startMs = endMs - (hoursMap[timeRange.value] ?? 24) * 3600 * 1000
  await setView(startMs, endMs)
}

/* ====== CONTROLES DE Y (PRO) ====== */
function resetY() {
  yState.min = null
  yState.max = null
  yState.initialized = false
}
function fitY() {
  yState.min = 0
  yState.max = calcInitialCap()
  yState.initialized = true
}

/* ====== WEBSOCKET ====== */
function onBusMessage(payload) {
  const updates = (Array.isArray(payload) ? payload : [payload]).filter(
    (u) => u && Number(u.sensor_id) === sensorId,
  )
  if (updates.length === 0) return
  const points = updates.map(normalizePoint)
  for (const mode of ['raw', 'auto']) {
    mergeItems(mode, points)
    for (const p of points) {
      if (store[mode].startMs === null || p._ms < store[mode].startMs) store[mode].startMs = p._ms
      if (store[mode].endMs === null || p._ms > store[mode].endMs) store[mode].endMs = p._ms
    }
  }
}

/* ====== MOUNT ====== */
onMounted(async () => {
  try {
    const { data } = await api.get(`/sensors/${sensorId}/details`)
    sensorInfo.value = data

    await connectWebSocketWhenAuthenticated()
    const off = addWsListener(onBusMessage)

    // tocar el ws para evitar no-unused-vars y subscribir
    const ws = getCurrentWebSocket && getCurrentWebSocket()
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'subscribe_sensors', sensor_ids: [sensorId] }))
    }

    onUnmounted(() => {
      off && off()
    })

    await setRange(timeRange.value)
  } catch (err) {
    console.error('Error loading sensor details:', err)
    router.push('/')
  } finally {
    isBootLoading.value = false
  }
})

onUnmounted(() => {
  if (historyAbort) historyAbort.abort()
})
watch(timeRange, async (r) => {
  await setRange(r)
})

/* ====== TABLA DE EVENTOS ====== */
const linkStatusEvents = computed(() => {
  if (sensorInfo.value?.sensor_type !== 'ethernet' || visibleData.value.length === 0) return []
  const events = []
  let lastStatus = null,
    lastSpeed = null
  for (const d of [...visibleData.value].reverse()) {
    if (d.status !== lastStatus || d.speed !== lastSpeed) {
      events.push({
        timestamp: new Intl.DateTimeFormat('es-AR', {
          dateStyle: 'medium',
          timeStyle: 'medium',
        }).format(new Date(d._ms)),
        status: d.status,
        speed: d.speed,
      })
      lastStatus = d.status
      lastSpeed = d.speed
    }
  }
  return events
})

const showEmptyHint = computed(() => !isBootLoading.value && visibleData.value.length === 0)
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
          v-for="(hours, range) in { '1h': 1, '12h': 12, '24h': 24, '7d': 168, '30d': 720 }"
          :key="range"
          @click="setRange(range)"
          :class="{ active: timeRange === range }"
        >
          {{ range }}
        </button>
      </div>

      <div class="chart-toolbar">
        <button @click="shiftWindow(-1)" title="Pan atrás (80% ventana)">◀ Atrás</button>
        <button @click="goLive()" title="Ir a ahora">● Hoy</button>
        <button @click="shiftWindow(1)" title="Pan adelante (80% ventana)">Adelante ▶</button>
        <span class="sep"></span>
        <button @click="zoomBy(0.5)" title="Acercar (zoom in)">＋</button>
        <button @click="zoomBy(2)" title="Alejar (zoom out)">－</button>
        <span class="sep"></span>
        <button @click="fitY()" title="Ajustar Y a P95 actual">Fit Y (P95)</button>
        <button @click="resetY()" title="Automático (resetear Y)">Auto Y</button>
      </div>
    </div>

    <div class="chart-container">
      <div v-show="isFetching" class="top-progress"></div>

      <div v-if="isBootLoading" class="loading-overlay"><p>Cargando datos…</p></div>
      <div v-if="showEmptyHint" class="empty-hint">Sin datos en esta ventana</div>

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
          <tr v-for="(event, i) in linkStatusEvents" :key="i">
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
  background: var(--surface-color);
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

.time-controls {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.75rem;
  margin-bottom: 0.75rem;
  padding: 0.75rem;
  background: var(--surface-color);
  border-radius: 12px;
}
.range-selector {
  display: flex;
  gap: 0.5rem;
}
.time-controls button {
  background: var(--primary-color);
  color: var(--font-color);
  border: none;
  padding: 0.45rem 0.8rem;
  border-radius: 6px;
  cursor: pointer;
  line-height: 1;
}
.time-controls button:hover {
  background: #5372f0;
}
.time-controls button.active {
  background: var(--blue);
  color: #fff;
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
  background: var(--surface-color);
  padding: 1.25rem 1.25rem 1.6rem;
  border-radius: 12px;
  height: 520px;
  position: relative;
}
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

.events-container {
  background: var(--surface-color);
  padding: 1.25rem 1.5rem;
  border-radius: 12px;
  margin-top: 1rem;
}
.events-container h3 {
  margin: 0 0 1rem 0;
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
  background: rgba(61, 220, 132, 0.2);
  color: var(--green);
}
.status-badge.link_down {
  background: rgba(233, 69, 96, 0.2);
  color: var(--secondary-color);
}
</style>
