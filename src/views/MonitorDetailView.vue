<script setup>
import { ref, reactive, onMounted, onUnmounted, computed, watch, provide } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '@/lib/api'
import { connectWebSocketWhenAuthenticated, getCurrentWebSocket } from '@/lib/ws'

// --- ECHARTS IMPORTS ---
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
  DataZoomComponent,
  MarkLineComponent,
  MarkAreaComponent,
} from 'echarts/components'
import VChart, { THEME_KEY } from 'vue-echarts'

// Registrar componentes de ECharts
use([
  CanvasRenderer,
  LineChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  DataZoomComponent,
  MarkLineComponent,
  MarkAreaComponent,
])

// Proveer tema oscuro
provide(THEME_KEY, 'dark')

/* ====== ESTADO BASE ====== */
const route = useRoute()
const router = useRouter()
const sensorId = Number(route.params.id)

const sensorInfo = ref(null)
const isBootLoading = ref(true)
const isFetching = ref(false)
let historyAbort = null
let fetchToken = 0

/* ====== ESTADO BITÁCORA ====== */
const showCommentsModal = ref(false)
const comments = ref([])
const newComment = ref('')
const isLoadingComments = ref(false)
const isSendingComment = ref(false)

/* ====== VISTA / RANGO ====== */
const timeRange = ref('24h')
const hoursMap = { '1h': 1, '12h': 12, '24h': 24, '7d': 168, '30d': 720 }
const currentWindow = ref(null) // { startMs, endMs, mode }

/* ====== STORE (raw/auto) ====== */
const store = reactive({
  raw: { startMs: null, endMs: null, map: new Map() },
  auto: { startMs: null, endMs: null, map: new Map() },
})

/* ====== HELPERS DE DATOS ====== */
function normalizePoint(p) {
  const ts = new Date(p.timestamp || p.ts || p.time).getTime()
  return { ...p, _ms: ts }
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

function decideMode(startMs, endMs) {
  const hours = Math.max(0, (endMs - startMs) / 3600000)
  return hours < 24 ? 'raw' : 'auto'
}

function parseMbps(val) {
  if (!val || val === 'N/A') return 0
  const m = String(val).match(/(\d+(?:\.\d+)?)/)
  return m ? parseFloat(m[1]) : 0
}

/* ====== DATA VISIBLE ====== */
const visibleData = computed(() => {
  if (!currentWindow.value) return []
  const { startMs, endMs, mode } = currentWindow.value
  return mapToSortedArray(mode, startMs, endMs)
})

/* ====== ESTADÍSTICAS (KPIs) ====== */
const stats = computed(() => {
  const data = visibleData.value
  if (!data.length) return null

  if (sensorInfo.value?.sensor_type === 'ping') {
    let sum = 0, max = 0, count = 0, timeouts = 0
    for (const p of data) {
      if (p.status === 'timeout') { timeouts++ } 
      else {
        const val = Number(p.latency_ms || 0)
        sum += val
        if (val > max) max = val
        count++
      }
    }
    const avg = count > 0 ? (sum / count).toFixed(1) : 0
    const loss = data.length > 0 ? ((timeouts / data.length) * 100).toFixed(1) : 0
    return [
      { label: 'Promedio', value: `${avg} ms`, color: '#5372f0' },
      { label: 'Máximo', value: `${max.toFixed(1)} ms`, color: '#facc15' },
      { label: 'Pérdida', value: `${loss}%`, color: '#e94560' },
    ]
  } else if (sensorInfo.value?.sensor_type === 'ethernet') {
    const last = data[data.length - 1]
    const rx = (Number(last.rx_bitrate || 0) / 1_000_000).toFixed(2)
    const tx = (Number(last.tx_bitrate || 0) / 1_000_000).toFixed(2)
    return [
      { label: 'Descarga', value: `${rx} Mbps`, color: '#36a2eb' },
      { label: 'Subida', value: `${tx} Mbps`, color: '#4bc0c0' },
      {
        label: 'Estado',
        value: (last.status || 'Unknown').replace('_', ' '),
        color: last.status === 'link_up' || last.status === 'ok' ? '#4caf50' : '#e94560',
      },
    ]
  } else if (sensorInfo.value?.sensor_type === 'wireless') {
    const last = data[data.length - 1]
    return [
      { label: 'Señal', value: `${last.signal_strength || 0} dBm`, color: '#36a2eb' },
      { label: 'CCQ TX', value: `${last.tx_ccq || 0}%`, color: '#4caf50' },
      { label: 'TX Rate', value: `${last.tx_rate || 'N/A'}`, color: '#facc15' },
      { label: 'RX Rate', value: `${last.rx_rate || 'N/A'}`, color: '#ff9800' }
    ]
  }
  return []
})

/* ====== ECHARTS OPTION ====== */
const chartOption = computed(() => {
  if (!sensorInfo.value) return {}

  const type = sensorInfo.value.sensor_type
  const data = visibleData.value
  const timestamps = data.map((d) => d._ms)

  const baseOption = {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross', label: { backgroundColor: '#6a7985' } },
      backgroundColor: 'rgba(20, 20, 20, 0.9)',
      borderColor: '#333',
      textStyle: { color: '#fff' },
      confine: true,
    },
    grid: { left: '2%', right: '3%', bottom: '15%', top: '12%', containLabel: true },
    dataZoom: [
      { type: 'inside', start: 0, end: 100 },
      {
        type: 'slider',
        start: 0,
        end: 100,
        bottom: 0,
        height: 20,
        fillerColor: 'rgba(83, 114, 240, 0.2)',
      },
    ],
    xAxis: {
      type: 'category',
      data: timestamps.map((ts) =>
        new Date(ts).toLocaleString('es-AR', {
          month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
        }),
      ),
      boundaryGap: false,
      axisLine: { lineStyle: { color: '#555' } },
      axisLabel: { color: '#888' },
    },
    yAxis: {
      type: 'value',
      splitLine: { lineStyle: { color: '#333', type: 'dashed' } },
      axisLabel: { color: '#888' },
    },
  }

  if (type === 'ping') {
    const latencies = data.map((d) => (d.status === 'timeout' ? null : Number(d.latency_ms)))
    const threshold = Number(sensorInfo.value.config?.latency_threshold_ms || 150)
    return {
      ...baseOption,
      series: [{
        name: 'Latencia', type: 'line', data: latencies, smooth: true, showSymbol: false,
        lineStyle: { width: 2, color: '#5372f0' },
        markLine: {
          symbol: 'none',
          data: [{ yAxis: threshold }],
          lineStyle: { color: '#ff4d4f', type: 'dashed' }
        }
      }]
    }
  }

  if (type === 'ethernet') {
    return {
      ...baseOption,
      legend: { data: ['Descarga', 'Subida'], textStyle: { color: '#ccc' }, top: 0 },
      series: [
        { name: 'Descarga', type: 'line', data: data.map(d => (Number(d.rx_bitrate)/1e6).toFixed(2)), smooth: true, showSymbol: false, itemStyle: { color: '#36a2eb' } },
        { name: 'Subida', type: 'line', data: data.map(d => (Number(d.tx_bitrate)/1e6).toFixed(2)), smooth: true, showSymbol: false, itemStyle: { color: '#4bc0c0' } }
      ]
    }
  }

  if (type === 'wireless') {
    const legendData = ['Señal (dBm)', 'CCQ TX (%)', 'TX Rate (Mbps)', 'RX Rate (Mbps)']
    const isAP = data.some(d => d.wireless_role === 'AP')
    if (isAP) legendData.push('Clientes')

    return {
      ...baseOption,
      legend: { data: legendData, textStyle: { color: '#ccc' }, top: 0 },
      grid: { ...baseOption.grid, right: '8%' },
      yAxis: [
        { type: 'value', name: 'dBm', position: 'left', axisLabel: { color: '#888' }, splitLine: { lineStyle: { color: '#333' } } },
        { type: 'value', name: '%', position: 'right', min: 0, max: 100, axisLabel: { color: '#888' }, splitLine: { show: false } },
        { type: 'value', name: 'Mbps', position: 'right', offset: 40, axisLabel: { color: '#888' }, splitLine: { show: false } }
      ],
      series: [
        { name: 'Señal (dBm)', type: 'line', yAxisIndex: 0, data: data.map(d => d.signal_strength), smooth: true, showSymbol: false, itemStyle: { color: '#36a2eb' } },
        { name: 'CCQ TX (%)', type: 'line', yAxisIndex: 1, data: data.map(d => d.tx_ccq), smooth: true, showSymbol: false, itemStyle: { color: '#4caf50' } },
        { name: 'TX Rate (Mbps)', type: 'line', yAxisIndex: 2, data: data.map(d => parseMbps(d.tx_rate)), smooth: true, showSymbol: false, itemStyle: { color: '#facc15' } },
        { name: 'RX Rate (Mbps)', type: 'line', yAxisIndex: 2, data: data.map(d => parseMbps(d.rx_rate)), smooth: true, showSymbol: false, itemStyle: { color: '#ff9800' } },
        ...(isAP ? [{ name: 'Clientes', type: 'line', yAxisIndex: 1, data: data.map(d => d.client_count), smooth: true, itemStyle: { color: '#9c27b0' } }] : [])
      ]
    }
  }
  return baseOption
})

/* ====== FETCHING DATA ====== */
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
          mode,
        },
        signal: historyAbort.signal,
      })
      if (myToken !== fetchToken) return
      mergeItems(mode, data?.items || [])
      extendRange(mode, seg.s, seg.e)
    }
  } catch (err) {
    if (err?.code !== 'ERR_CANCELED') console.error(err)
  } finally {
    if (myToken === fetchToken) isFetching.value = false
  }
}

async function setRange(range) {
  timeRange.value = range
  const endMs = Date.now()
  const startMs = endMs - (hoursMap[range] ?? 24) * 3600 * 1000
  const mode = decideMode(startMs, endMs)
  await ensureCoverage(mode, startMs, endMs)
  currentWindow.value = { startMs, endMs, mode }
}

/* ====== WEBSOCKET ====== */
let wsUnbind = null
function handleRawMessage(event) {
  try {
    const parsed = JSON.parse(event.data)
    const updates = parsed.type === 'sensor_update' ? [parsed] : []
    const relevant = updates.filter((u) => String(u.sensor_id) === String(sensorId))
    if (relevant.length > 0) {
      const points = relevant.map(normalizePoint)
      mergeItems('raw', points)
      mergeItems('auto', points)
      store.raw = { ...store.raw }
    }
  } catch {}
}

function initRealTime() {
  const ws = getCurrentWebSocket()
  if (!ws) return setTimeout(initRealTime, 1000)
  ws.send(JSON.stringify({ type: 'subscribe_sensors', sensor_ids: [sensorId] }))
  ws.addEventListener('message', handleRawMessage)
  wsUnbind = () => ws.removeEventListener('message', handleRawMessage)
}

/* ====== BITÁCORA ====== */
async function openCommentsModal() {
  showCommentsModal.value = true
  await loadComments()
}
async function loadComments() {
  isLoadingComments.value = true
  try {
    const { data } = await api.get(`/sensors/${sensorId}/comments`)
    comments.value = data
  } finally { isLoadingComments.value = false }
}
async function submitComment() {
  if (!newComment.value.trim()) return
  isSendingComment.value = true
  try {
    await api.post(`/sensors/${sensorId}/comments`, { content: newComment.value })
    newComment.value = ''; await loadComments()
  } finally { isSendingComment.value = false }
}
function formatDate(isoStr) {
  return isoStr ? new Date(isoStr).toLocaleString('es-ES') : ''
}

/* ====== LIFECYCLE ====== */
onMounted(async () => {
  try {
    const { data } = await api.get(`/sensors/${sensorId}/details`)
    sensorInfo.value = data
    await connectWebSocketWhenAuthenticated()
    await setRange(timeRange.value)
    initRealTime()
  } catch { router.push('/') }
  finally { isBootLoading.value = false }
})

onUnmounted(() => {
  if (historyAbort) historyAbort.abort()
  if (wsUnbind) wsUnbind()
})

watch(timeRange, r => setRange(r))
</script>

<template>
  <div class="detail-view">
    <div class="top-bar">
      <div class="left-group">
        <button @click="router.push('/')" class="back-btn">‹ Dashboard</button>
        <div v-if="sensorInfo" class="info">
          <h1>{{ sensorInfo.name }}</h1>
          <small>{{ sensorInfo.client_name }} — {{ sensorInfo.ip_address }}</small>
        </div>
      </div>
      <button @click="openCommentsModal" class="btn-action">📝 Bitácora</button>
    </div>

    <div class="stats-grid" v-if="stats">
      <div v-for="(stat, i) in stats" :key="i" class="stat-card" :style="{ borderTopColor: stat.color }">
        <span class="stat-label">{{ stat.label }}</span>
        <span class="stat-value" :style="{ color: stat.color }">{{ stat.value }}</span>
      </div>
    </div>

    <div class="chart-wrapper">
      <div class="toolbar">
        <div class="range-btns">
          <button v-for="(_, r) in hoursMap" :key="r" :class="{ active: timeRange === r }" @click="setRange(r)">{{ r }}</button>
        </div>
        <div v-show="isFetching" class="spinner">↻</div>
      </div>
      <div class="chart-container">
        <v-chart class="chart" :option="chartOption" autoresize />
      </div>
    </div>

    <div v-if="showCommentsModal" class="modal-overlay" @click.self="showCommentsModal = false">
      <div class="modal-content large-modal">
        <div class="modal-header">
          <h3>📖 Bitácora: {{ sensorInfo?.name }}</h3>
          <button class="btn-close" @click="showCommentsModal = false">X</button>
        </div>
        <div class="comments-list">
          <div v-if="isLoadingComments">Cargando...</div>
          <div v-else-if="comments.length === 0" class="empty-state">📂 Sin registros.</div>
          <div v-else class="comments-scroll">
            <div v-for="c in comments" :key="c.id" class="comment-item">
              <div class="comment-header"><span>{{ formatDate(c.created_at) }}</span></div>
              <div class="comment-body">{{ c.content }}</div>
            </div>
          </div>
        </div>
        <div class="comment-form">
          <textarea v-model="newComment" rows="3" placeholder="Registrar mantenimiento..."></textarea>
          <div class="modal-actions">
            <button class="btn-primary" @click="submitComment" :disabled="isSendingComment">Agregar Nota</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.detail-view { max-width: 1400px; margin: 0 auto; padding: 1rem; }
.top-bar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem; }
.left-group { display: flex; align-items: center; gap: 1rem; }
.back-btn { background: var(--surface-color); border: 1px solid var(--primary-color); color: var(--font-color); padding: 0.5rem 1rem; border-radius: 8px; cursor: pointer; }
.btn-action { background: var(--surface-color); border: 1px solid var(--blue); color: var(--blue); padding: 0.5rem 1rem; border-radius: 8px; cursor: pointer; font-weight: bold; }
.info h1 { margin: 0; font-size: 1.5rem; }
.info small { color: var(--gray); font-family: monospace; }
.stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-bottom: 1.5rem; }
.stat-card { background: var(--surface-color); padding: 1rem; border-radius: 8px; border-top: 3px solid var(--primary-color); display: flex; flex-direction: column; }
.stat-label { font-size: 0.85rem; color: var(--gray); text-transform: uppercase; }
.stat-value { font-size: 1.8rem; font-weight: bold; margin-top: 0.25rem; }
.chart-wrapper { background: var(--surface-color); border-radius: 12px; padding: 1rem; height: 600px; display: flex; flex-direction: column; }
.toolbar { display: flex; justify-content: space-between; margin-bottom: 1rem; }
.range-btns button { background: transparent; border: 1px solid var(--gray); color: var(--gray); padding: 0.25rem 0.75rem; margin-right: 0.5rem; border-radius: 4px; cursor: pointer; }
.range-btns button.active { background: var(--blue); border-color: var(--blue); color: white; }
.chart-container { flex-grow: 1; position: relative; min-height: 0; }
.chart { height: 100%; width: 100%; }
.spinner { animation: spin 1s linear infinite; color: var(--blue); }
@keyframes spin { 100% { transform: rotate(360deg); } }
.modal-overlay { position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0, 0, 0, 0.7); display: flex; align-items: center; justify-content: center; z-index: 3000; }
.modal-content { background: var(--surface-color); padding: 2rem; border-radius: 10px; border: 1px solid var(--primary-color); color: white; }
.large-modal { width: 600px; max-width: 95%; max-height: 85vh; display: flex; flex-direction: column; }
.modal-header { display: flex; justify-content: space-between; margin-bottom: 1rem; }
.comments-list { background: rgba(0,0,0,0.2); border-radius: 6px; padding: 1rem; margin-bottom: 1rem; min-height: 200px; }
.comments-scroll { max-height: 300px; overflow-y: auto; display: flex; flex-direction: column; gap: 1rem; }
.comment-item { background: var(--bg-color); border: 1px solid var(--primary-color); padding: 0.8rem; border-radius: 6px; }
.comment-header { font-size: 0.8rem; color: var(--gray); margin-bottom: 0.5rem; }
.comment-body { white-space: pre-wrap; font-size: 0.95rem; }
.comment-form textarea { width: 100%; background: var(--bg-color); color: white; border: 1px solid var(--primary-color); border-radius: 6px; padding: 0.7rem; }
.modal-actions { display: flex; justify-content: flex-end; margin-top: 1rem; }
.btn-primary { background: var(--green); color: white; padding: 0.6rem 1.2rem; border-radius: 6px; border: none; cursor: pointer; font-weight: bold; }
</style>