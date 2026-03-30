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

// Proveer tema oscuro (o default si prefieres claro)
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

/* ====== ESTADO DE ZOOM ====== */
const zoomStart = ref(0)
const zoomEnd = ref(100)

/* ====== STORE (raw/auto) OPTIMIZADO ====== */
// Usamos un objeto puro para máximo rendimiento. Evitamos que Vue rastree miles de puntos de datos inútilmente.
const store = {
  raw: { startMs: null, endMs: null, map: new Map() },
  auto: { startMs: null, endMs: null, map: new Map() },
}
// Control maestro reactivo: lo incrementamos cuando hay datos nuevos para forzar a Vue a repintar.
const dataVersion = ref(0) 

/* ====== HELPERS DE DATOS ====== */
function normalizePoint(p) {
  // Asegurar timestamp numérico
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

/* ====== EVENTOS DE GRAFICA ====== */
function handleDataZoom(params) {
  // Almacenar el nivel de zoom actual configurado por el usuario
  const start = params.batch ? params.batch[0].start : params.start
  const end = params.batch ? params.batch[0].end : params.end
  
  if (start !== undefined && end !== undefined) {
    zoomStart.value = start
    zoomEnd.value = end
  }
}

/* ====== DATA VISIBLE ====== */
const visibleData = computed(() => {
  // Declarar dependencia explícita: cuando dataVersion cambia, esto se recalcula
  const _trigger = dataVersion.value
  
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
      if (p.status === 'timeout') {
        timeouts++
      } else {
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
    const sig = last.signal_strength || 0
    const ccq = last.tx_ccq || 0
    const role = last.wireless_role || 'unknown'

    const kpis = [
      { label: 'Señal', value: `${sig} dBm`, color: sig <= -80 ? '#e94560' : '#36a2eb' },
      { label: 'CCQ TX', value: `${ccq}%`, color: ccq < 75 ? '#facc15' : '#4caf50' },
      { label: 'TX Rate', value: `${last.tx_rate || 'N/A'}`, color: '#facc15' },
      { label: 'RX Rate', value: `${last.rx_rate || 'N/A'}`, color: '#ff9800' }
    ]

    if (role === 'AP') {
      kpis.push({ label: 'Clientes Activos', value: `${last.client_count || 0}`, color: '#9c27b0' })
    } else {
      const st = (last.status || 'pending').toUpperCase()
      const stColor = ['CONNECTED', 'OPTIMAL', 'LINK_UP'].includes(st) ? '#4caf50' : '#e94560'
      kpis.push({ label: 'Estado', value: st, color: stColor })
    }
    return kpis
  } else if (sensorInfo.value?.sensor_type === 'system') {
    const last = data[data.length - 1]
    const cpu = last.cpu_percent !== null && last.cpu_percent !== undefined ? Number(last.cpu_percent).toFixed(1) : null
    const mem = last.memory_percent !== null && last.memory_percent !== undefined ? Number(last.memory_percent).toFixed(1) : null
    const temp = last.temperature !== null && last.temperature !== undefined ? Number(last.temperature).toFixed(1) : null
    const volt = last.voltage !== null && last.voltage !== undefined ? Number(last.voltage).toFixed(2) : null
    const uptime = last.uptime_seconds

    const kpis = []
    
    if (cpu !== null) kpis.push({ label: 'CPU', value: `${cpu}%`, color: cpu > 85 ? '#e94560' : '#36a2eb' })
    if (mem !== null) kpis.push({ label: 'RAM', value: `${mem}%`, color: mem > 90 ? '#e94560' : '#4bc0c0' })
    if (temp !== null) kpis.push({ label: 'Temperatura', value: `${temp}°C`, color: temp > 75 ? '#facc15' : '#ff9800' })
    if (volt !== null) kpis.push({ label: 'Voltaje', value: `${volt}V`, color: '#9c27b0' })

    if (uptime !== null && uptime !== undefined) {
      const d = Math.floor(uptime / 86400)
      const h = Math.floor((uptime % 86400) / 3600)
      const m = Math.floor((uptime % 3600) / 60)
      let upStr = ''
      if (d > 0) upStr += `${d}d `
      if (h > 0 || d > 0) upStr += `${h}h `
      upStr += `${m}m`
      kpis.push({ label: 'Uptime', value: upStr || '< 1m', color: '#4caf50' })
    }
    
    // Si no hay datos legibles o dio error
    if (kpis.length === 0) {
        kpis.push({ label: 'Estado', value: (last.status || 'unknown').toUpperCase(), color: '#e94560' })
    }

    return kpis
  }
  return []
})

/* ====== ECHARTS OPTION ====== */
const chartOption = computed(() => {
  if (!sensorInfo.value) return {}

  const type = sensorInfo.value.sensor_type
  const data = visibleData.value

  // Extraer timestamps y valores
  const timestamps = data.map((d) => d._ms)

  // Configuración base (Tema oscuro manual para coincidir con CSS)
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
    // Ajuste de Bottom fijo en píxeles para evitar que se pise con el Slider de zoom
    grid: { left: '2%', right: '3%', bottom: 75, top: '10%', containLabel: true },
    dataZoom: [
      { type: 'inside', start: zoomStart.value, end: zoomEnd.value }, // Zoom con rueda (respeta estado)
      {
        type: 'slider',
        start: zoomStart.value, // Mantener posicion
        end: zoomEnd.value,     // Mantener posicion
        bottom: 10,
        height: 24,
        handleSize: '100%',
        showDetail: false,
        fillerColor: 'rgba(83, 114, 240, 0.2)',
      },
    ],
    xAxis: {
      type: 'category',
      data: timestamps.map((ts) =>
        new Date(ts).toLocaleString('es-AR', {
          month: 'short',
          day: 'numeric',
          hour: '2-digit',
          minute: '2-digit',
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

  // --- Lógica PING ---
  if (type === 'ping') {
    const latencies = data.map((d) => (d.status === 'timeout' ? null : Number(d.latency_ms)))

    // Generar áreas rojas para Timeouts
    const markAreas = []
    let startIdx = null
    data.forEach((d, i) => {
      if (d.status === 'timeout') {
        if (startIdx === null) startIdx = i
      } else {
        if (startIdx !== null) {
          markAreas.push([{ xAxis: startIdx }, { xAxis: i - 1 }])
          startIdx = null
        }
      }
    })
    if (startIdx !== null) markAreas.push([{ xAxis: startIdx }, { xAxis: data.length - 1 }])

    const threshold = Number(sensorInfo.value.config?.latency_threshold_ms || 150)

    return {
      ...baseOption,
      yAxis: { ...baseOption.yAxis, name: 'ms', nameTextStyle: { padding: [0, 0, 0, 10] } },
      series: [
        {
          name: 'Latencia',
          type: 'line',
          data: latencies,
          smooth: true,
          showSymbol: false,
          lineStyle: { width: 2, color: '#5372f0' },
          areaStyle: {
            color: {
              type: 'linear',
              x: 0,
              y: 0,
              x2: 0,
              y2: 1,
              colorStops: [
                { offset: 0, color: 'rgba(83, 114, 240, 0.5)' },
                { offset: 1, color: 'rgba(83, 114, 240, 0.0)' },
              ],
            },
          },
          markLine: {
            symbol: 'none',
            label: { formatter: '{c} ms', color: '#ff4d4f', position: 'insideEndTop' },
            lineStyle: { color: '#ff4d4f', type: 'dashed', width: 1 },
            data: [{ yAxis: threshold }],
          },
          markArea: {
            itemStyle: { color: 'rgba(255, 77, 79, 0.15)' },
            data: markAreas,
          },
        },
      ],
    }
  }

  // --- Lógica ETHERNET ---
  if (type === 'ethernet') {
    const rx = data.map((d) => (Number(d.rx_bitrate || 0) / 1_000_000).toFixed(2)) // Mbps
    const tx = data.map((d) => (Number(d.tx_bitrate || 0) / 1_000_000).toFixed(2)) // Mbps

    return {
      ...baseOption,
      legend: { data: ['Descarga', 'Subida'], textStyle: { color: '#ccc' }, top: 0 },
      yAxis: { ...baseOption.yAxis, name: 'Mbps' },
      series: [
        {
          name: 'Descarga',
          type: 'line',
          data: rx,
          smooth: true,
          showSymbol: false,
          itemStyle: { color: '#36a2eb' },
          areaStyle: {
            color: {
              type: 'linear',
              x: 0,
              y: 0,
              x2: 0,
              y2: 1,
              colorStops: [
                { offset: 0, color: 'rgba(54, 162, 235, 0.5)' },
                { offset: 1, color: 'rgba(54, 162, 235, 0)' },
              ],
            },
          },
        },
        {
          name: 'Subida',
          type: 'line',
          data: tx,
          smooth: true,
          showSymbol: false,
          itemStyle: { color: '#4bc0c0' },
          areaStyle: {
            color: {
              type: 'linear',
              x: 0,
              y: 0,
              x2: 0,
              y2: 1,
              colorStops: [
                { offset: 0, color: 'rgba(75, 192, 192, 0.5)' },
                { offset: 1, color: 'rgba(75, 192, 192, 0)' },
              ],
            },
          },
        },
      ],
    }
  }

  // --- Lógica WIRELESS ---
  if (type === 'wireless') {
    const signals = data.map((d) => Number(d.signal_strength || 0))
    const ccqs = data.map((d) => Number(d.tx_ccq || 0))
    const txRates = data.map((d) => parseMbps(d.tx_rate))
    const rxRates = data.map((d) => parseMbps(d.rx_rate))
    const clients = data.map((d) => Number(d.client_count || 0))
    
    const isAP = data.some((d) => d.wireless_role === 'AP')

    const series = [
      {
        name: 'Señal (dBm)',
        type: 'line',
        data: signals,
        smooth: true,
        showSymbol: false,
        yAxisIndex: 0,
        itemStyle: { color: '#36a2eb' },
        lineStyle: { width: 2 }
      },
      {
        name: 'CCQ TX (%)',
        type: 'line',
        data: ccqs,
        smooth: true,
        showSymbol: false,
        yAxisIndex: 1,
        itemStyle: { color: '#4caf50' },
        lineStyle: { width: 2 }
      },
      {
        name: 'TX Rate (Mbps)',
        type: 'line',
        data: txRates,
        smooth: true,
        showSymbol: false,
        yAxisIndex: 2,
        itemStyle: { color: '#facc15' },
        lineStyle: { width: 1, type: 'solid' }
      },
      {
        name: 'RX Rate (Mbps)',
        type: 'line',
        data: rxRates,
        smooth: true,
        showSymbol: false,
        yAxisIndex: 2,
        itemStyle: { color: '#ff9800' },
        lineStyle: { width: 1, type: 'solid' }
      }
    ]

    const legendData = ['Señal (dBm)', 'CCQ TX (%)', 'TX Rate (Mbps)', 'RX Rate (Mbps)']
    
    // Múltiples ejes Y para que las escalas no se rompan visualmente
    const yAxes = [
      {
        type: 'value',
        name: 'dBm',
        position: 'left',
        splitLine: { lineStyle: { color: '#333', type: 'dashed' } },
        axisLabel: { color: '#888' },
      },
      {
        type: 'value',
        name: 'CCQ %',
        position: 'right',
        splitLine: { show: false },
        axisLabel: { color: '#888' },
        min: 0,
        max: 100
      },
      {
        type: 'value',
        name: 'Mbps',
        position: 'right',
        offset: 50, // Desplazado para no pisar el %
        splitLine: { show: false },
        axisLabel: { color: '#888' }
      }
    ]

    // Si detectamos que es Nodo/AP, agregamos la 4ta línea
    if (isAP) {
      series.push({
        name: 'Clientes Activos',
        type: 'line',
        data: clients,
        smooth: true,
        showSymbol: false,
        yAxisIndex: 3,
        itemStyle: { color: '#9c27b0' },
        lineStyle: { width: 2, type: 'dashed' }
      })
      legendData.push('Clientes Activos')
      yAxes.push({
        type: 'value',
        name: 'Clientes',
        position: 'right',
        offset: 100, // Desplazado para no pisar Mbps
        splitLine: { show: false },
        axisLabel: { color: '#888' },
        minInterval: 1
      })
    }

    return {
      ...baseOption,
      legend: { data: legendData, textStyle: { color: '#ccc' }, top: 0 },
      // Ajuste de grid para dejar espacio a los ejes Y derechos y fijar el bottom en 75px
      grid: { left: '2%', right: isAP ? '18%' : '10%', bottom: 75, top: '15%', containLabel: true },
      yAxis: yAxes,
      series: series
    }
  }

  // --- Lógica SYSTEM ---
  if (type === 'system') {
    const cpuData = data.map((d) => d.cpu_percent !== null && d.cpu_percent !== undefined ? Number(d.cpu_percent).toFixed(1) : null)
    const memData = data.map((d) => d.memory_percent !== null && d.memory_percent !== undefined ? Number(d.memory_percent).toFixed(1) : null)
    const tempData = data.map((d) => d.temperature !== null && d.temperature !== undefined ? Number(d.temperature).toFixed(1) : null)
    const voltData = data.map((d) => d.voltage !== null && d.voltage !== undefined ? Number(d.voltage).toFixed(2) : null)

    const hasTemp = tempData.some((v) => v !== null)
    const hasVolt = voltData.some((v) => v !== null)

    const series = [
      {
        name: 'CPU (%)',
        type: 'line',
        data: cpuData,
        smooth: true,
        showSymbol: false,
        yAxisIndex: 0,
        itemStyle: { color: '#36a2eb' },
        areaStyle: {
          color: {
            type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [{ offset: 0, color: 'rgba(54, 162, 235, 0.3)' }, { offset: 1, color: 'rgba(54, 162, 235, 0)' }]
          }
        },
      },
      {
        name: 'RAM (%)',
        type: 'line',
        data: memData,
        smooth: true,
        showSymbol: false,
        yAxisIndex: 0,
        itemStyle: { color: '#4bc0c0' },
        areaStyle: {
          color: {
            type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [{ offset: 0, color: 'rgba(75, 192, 192, 0.3)' }, { offset: 1, color: 'rgba(75, 192, 192, 0)' }]
          }
        },
      }
    ]

    const legendData = ['CPU (%)', 'RAM (%)']
    
    const yAxes = [
      {
        type: 'value',
        name: '% (CPU/RAM)',
        position: 'left',
        min: 0,
        max: 100,
        splitLine: { lineStyle: { color: '#333', type: 'dashed' } },
        axisLabel: { color: '#888' }
      }
    ]

    let rightOffset = 0

    if (hasTemp) {
      series.push({
        name: 'Temp (°C)',
        type: 'line',
        data: tempData,
        smooth: true,
        showSymbol: false,
        yAxisIndex: yAxes.length,
        itemStyle: { color: '#ff9800' }
      })
      legendData.push('Temp (°C)')
      yAxes.push({
        type: 'value',
        name: '°C',
        position: 'right',
        offset: rightOffset,
        splitLine: { show: false },
        axisLabel: { color: '#888' }
      })
      rightOffset += 50
    }

    if (hasVolt) {
      series.push({
        name: 'Voltaje (V)',
        type: 'line',
        data: voltData,
        smooth: true,
        showSymbol: false,
        yAxisIndex: yAxes.length,
        itemStyle: { color: '#9c27b0' }
      })
      legendData.push('Voltaje (V)')
      yAxes.push({
        type: 'value',
        name: 'V',
        position: 'right',
        offset: rightOffset,
        splitLine: { show: false },
        axisLabel: { color: '#888' }
      })
      rightOffset += 50
    }

    return {
      ...baseOption,
      legend: { data: legendData, textStyle: { color: '#ccc' }, top: 0 },
      grid: { 
        left: '2%', 
        right: rightOffset > 0 ? `${rightOffset + 30}px` : '5%', 
        bottom: 75, 
        top: '15%', 
        containLabel: true 
      },
      yAxis: yAxes,
      series: series
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
      
      // Forzar repintado reactivo tras cargar este bloque
      dataVersion.value++
    }
  } catch (err) {
    if (err?.code !== 'ERR_CANCELED') console.error('ensureCoverage error:', err)
  } finally {
    if (myToken === fetchToken) isFetching.value = false
  }
}

async function setView(startMs, endMs) {
  const mode = decideMode(startMs, endMs)
  await ensureCoverage(mode, startMs, endMs)
  currentWindow.value = { startMs, endMs, mode }
}

async function setRange(range) {
  // Cuando cambiamos de pestaña (ej de 24h a 7d), reseteamos el zoom a la vista completa
  zoomStart.value = 0
  zoomEnd.value = 100
  timeRange.value = range
  const endMs = Date.now()
  const startMs = endMs - (hoursMap[range] ?? 24) * 3600 * 1000
  await setView(startMs, endMs)
}

/* ====== WEBSOCKET REAL-TIME FIX ====== */
let wsUnbind = null

function normalizeWsPayload(raw) {
  if (typeof raw === 'string') {
    try {
      return normalizeWsPayload(JSON.parse(raw))
    } catch {
      return []
    }
  }
  if (raw && typeof raw === 'object') {
    if (['sensor_update', 'sensor-status'].includes(raw.type)) {
      return [raw.data || raw.payload || raw]
    }
  }
  return []
}

function handleRawMessage(event) {
  try {
    const msg = event.data
    if (msg.includes('pong')) return
    const parsed = JSON.parse(msg)
    const updates = normalizeWsPayload(parsed)

    const relevant = updates.filter((u) => String(u.sensor_id) === String(sensorId))

    if (relevant.length > 0) {
      const points = relevant.map(normalizePoint)
      mergeItems('raw', points)
      mergeItems('auto', points) // Actualizamos ambas memorias de forma superrápida

      // --- MAGIA DEL TIEMPO REAL (SLIDING WINDOW) ---
      if (currentWindow.value) {
        // Encontrar el timestamp más nuevo que acaba de llegar
        const latestMs = Math.max(...points.map((p) => p._ms))
        
        // Si el dato es más nuevo que el límite final de nuestra ventana visual
        if (latestMs > currentWindow.value.endMs) {
          // Calculamos cuánto tiempo pasó (el delta) y empujamos la ventana hacia adelante
          const delta = latestMs - currentWindow.value.endMs
          currentWindow.value.endMs += delta
          currentWindow.value.startMs += delta
        }
      }

      // Trigger de reactividad: Avisamos a Vue que hay datos nuevos
      dataVersion.value++
    }
  } catch {
    /* ignore */
  }
}

function initRealTime() {
  const ws = getCurrentWebSocket()
  if (!ws) {
    setTimeout(initRealTime, 1000)
    return
  }

  try {
    ws.send(JSON.stringify({ type: 'subscribe_sensors', sensor_ids: [sensorId] }))
  } catch {
    /* ignore */
  }

  ws.removeEventListener('message', handleRawMessage)
  ws.addEventListener('message', handleRawMessage)

  wsUnbind = () => ws.removeEventListener('message', handleRawMessage)
}

/* ====== FUNCIONES BITÁCORA ====== */
async function openCommentsModal() {
  showCommentsModal.value = true
  newComment.value = ''
  await loadComments()
}

async function loadComments() {
  isLoadingComments.value = true
  try {
    const { data } = await api.get(`/sensors/${sensorId}/comments`)
    comments.value = data
  } catch (error) {
    console.error('Error cargando comentarios', error)
  } finally {
    isLoadingComments.value = false
  }
}

async function submitComment() {
  if (!newComment.value.trim()) return
  isSendingComment.value = true
  try {
    await api.post(`/sensors/${sensorId}/comments`, { content: newComment.value })
    newComment.value = ''
    await loadComments()
  } catch (error) {
    console.error('Error enviando comentario', error)
  } finally {
    isSendingComment.value = false
  }
}

function formatDate(isoStr) {
  if (!isoStr) return ''
  return new Date(isoStr).toLocaleString('es-ES', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

/* ====== LIFECYCLE ====== */
onMounted(async () => {
  try {
    const { data } = await api.get(`/sensors/${sensorId}/details`)
    sensorInfo.value = data
    await connectWebSocketWhenAuthenticated()

    await setRange(timeRange.value)
    initRealTime()
  } catch (err) {
    console.error(err)
    router.push('/')
  } finally {
    isBootLoading.value = false
  }
})

onUnmounted(() => {
  if (historyAbort) historyAbort.abort()
  if (wsUnbind) wsUnbind()
})

watch(timeRange, async (r) => {
  await setRange(r)
})
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
      <div
        v-for="(stat, i) in stats"
        :key="i"
        class="stat-card"
        :style="{ borderTopColor: stat.color }"
      >
        <span class="stat-label">{{ stat.label }}</span>
        <span class="stat-value" :style="{ color: stat.color }">{{ stat.value }}</span>
      </div>
    </div>

    <div class="chart-wrapper">
      <div class="toolbar">
        <div class="range-btns">
          <button
            v-for="(_, r) in hoursMap"
            :key="r"
            :class="{ active: timeRange === r }"
            @click="setRange(r)"
          >
            {{ r }}
          </button>
        </div>
        <div v-show="isFetching" class="spinner">↻</div>
      </div>

      <div class="chart-container">
        <v-chart class="chart" :option="chartOption" autoresize @datazoom="handleDataZoom" />
      </div>
    </div>

    <div v-if="showCommentsModal" class="modal-overlay" @click.self="showCommentsModal = false">
      <div class="modal-content large-modal">
        <div class="modal-header">
          <h3>📖 Bitácora: {{ sensorInfo?.name }}</h3>
          <button class="btn-close" @click="showCommentsModal = false">X</button>
        </div>

        <div class="comments-list">
          <div v-if="isLoadingComments" class="loading-text">Cargando notas...</div>
          <div v-else-if="comments.length === 0" class="empty-state">
            <div class="empty-icon">📂</div>
            <p>No hay registros en la bitácora aún.</p>
          </div>

          <div v-else class="comments-scroll">
            <div v-for="c in comments" :key="c.id" class="comment-item">
              <div class="comment-header">
                <span class="comment-date">{{ formatDate(c.created_at) }}</span>
              </div>
              <div class="comment-body">{{ c.content }}</div>
            </div>
          </div>
        </div>

        <hr class="separator" />

        <div class="comment-form">
          <label>Nueva Nota</label>
          <textarea
            v-model="newComment"
            rows="3"
            placeholder="Registrar mantenimiento, alertas falsas, cambios de configuración..."
          ></textarea>
          <div class="modal-actions">
            <button class="btn-primary" @click="submitComment" :disabled="isSendingComment">
              {{ isSendingComment ? 'Guardando...' : 'Agregar Nota' }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.detail-view {
  max-width: 1400px;
  margin: 0 auto;
  padding: 1rem;
}

.top-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
}
.left-group {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.back-btn {
  background: var(--surface-color);
  border: 1px solid var(--primary-color);
  color: var(--font-color);
  padding: 0.5rem 1rem;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
}
.back-btn:hover {
  background: var(--primary-color);
  color: white;
}

.btn-action {
  background: var(--surface-color);
  border: 1px solid var(--blue);
  color: var(--blue);
  padding: 0.5rem 1rem;
  border-radius: 8px;
  cursor: pointer;
  font-weight: bold;
  transition: 0.2s;
}
.btn-action:hover {
  background: var(--blue);
  color: white;
}

.info h1 {
  margin: 0;
  font-size: 1.5rem;
}
.info small {
  color: var(--gray);
  font-family: monospace;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 1rem;
  margin-bottom: 1.5rem;
}
.stat-card {
  background: var(--surface-color);
  padding: 1rem;
  border-radius: 8px;
  border-top: 3px solid var(--primary-color);
  display: flex;
  flex-direction: column;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
}
.stat-label {
  font-size: 0.85rem;
  color: var(--gray);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.stat-value {
  font-size: 1.8rem;
  font-weight: bold;
  margin-top: 0.25rem;
}

.chart-wrapper {
  background: var(--surface-color);
  border-radius: 12px;
  padding: 1rem;
  height: 600px;
  display: flex;
  flex-direction: column;
}

.toolbar {
  display: flex;
  justify-content: space-between;
  margin-bottom: 1rem;
}

.range-btns button {
  background: transparent;
  border: 1px solid var(--gray);
  color: var(--gray);
  padding: 0.25rem 0.75rem;
  margin-right: 0.5rem;
  border-radius: 4px;
  cursor: pointer;
}
.range-btns button.active {
  background: var(--blue);
  border-color: var(--blue);
  color: white;
}

.chart-container {
  flex-grow: 1;
  position: relative;
  min-height: 0;
}
.chart {
  height: 100%;
  width: 100%;
}

.spinner {
  animation: spin 1s linear infinite;
  font-weight: bold;
  color: var(--blue);
}
@keyframes spin {
  100% {
    transform: rotate(360deg);
  }
}

.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0, 0, 0, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 3000;
}
.modal-content {
  background: var(--surface-color);
  padding: 2rem;
  border-radius: 10px;
  border: 1px solid var(--primary-color);
  color: white;
}
.large-modal {
  width: 600px;
  max-width: 95%;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
}
.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}
.btn-close {
  background: transparent;
  border: 1px solid var(--gray);
  color: var(--gray);
  border-radius: 4px;
  cursor: pointer;
}

.comments-list {
  background: rgba(0, 0, 0, 0.2);
  border-radius: 6px;
  padding: 1rem;
  margin-bottom: 1rem;
  min-height: 200px;
  border: 1px solid rgba(255, 255, 255, 0.05);
}
.comments-scroll {
  max-height: 300px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}
.comment-item {
  background: var(--bg-color);
  border: 1px solid var(--primary-color);
  padding: 0.8rem;
  border-radius: 6px;
}
.comment-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 0.5rem;
  font-size: 0.8rem;
  color: var(--gray);
}
.comment-body {
  white-space: pre-wrap;
  color: #eee;
  font-size: 0.95rem;
}
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--gray);
}
.empty-icon {
  font-size: 2rem;
  margin-bottom: 0.5rem;
}
.separator {
  border: 0;
  border-top: 1px solid var(--primary-color);
  margin: 1rem 0;
}
.comment-form textarea {
  width: 100%;
  background-color: var(--bg-color);
  color: white;
  border: 1px solid var(--primary-color);
  border-radius: 6px;
  padding: 0.7rem;
  margin-top: 0.5rem;
  outline: none;
  font-family: inherit;
  resize: vertical;
}
.modal-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 1rem;
}
.btn-primary {
  background: var(--green);
  color: white;
  padding: 0.6rem 1.2rem;
  border-radius: 6px;
  border: none;
  cursor: pointer;
  font-weight: bold;
}
.btn-primary:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}
</style>