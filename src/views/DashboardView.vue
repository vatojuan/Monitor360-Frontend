<script setup>
import { ref, onMounted, onUnmounted, computed, watch, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import api from '@/lib/api'
import { connectWebSocketWhenAuthenticated, getCurrentWebSocket } from '@/lib/ws'
import { waitForSession } from '@/lib/supabase'
import draggable from 'vuedraggable'
import SensorConfigurator from '@/components/SensorConfigurator.vue'

const router = useRouter()

// --- ESTADO PRINCIPAL ---
const allMonitors = ref([])
const groupedMonitors = ref({})
const activeGroup = ref(null)
const isSidebarCollapsed = ref(false)

// --- FASE 3: ESTADO GLOBAL DE SILENCIO DE CUENTA ---
const accountMuteUntil = ref(null)
const isAccountMuted = computed(() => {
  if (!accountMuteUntil.value) return false
  return new Date(accountMuteUntil.value) > new Date()
})

// Estado de grupos sincronizado con DB
const dbGroups = ref([])
const groupMuteMap = ref({}) // NUEVO: Mapa para saber qué grupos están silenciados

// Estado Reactivo de Sensores
const liveSensorStatus = ref({})
// Caché Reactivo de Alertas de Monitores (Devuelve 'ok', 'warning', o 'critical')
const liveMonitorAlerts = ref({}) 

const monitorToDelete = ref(null)
const collapsedCards = ref(new Set())

// --- Modales y Edición ---
const sensorDetailsToShow = ref(null)
const currentMonitorContext = ref(null)

const monitorToEdit = ref(null)
const editMonitorGroup = ref('')

const showGroupModal = ref(false)
const newGroupName = ref('')
const notification = ref({ show: false, message: '', type: 'success' })
const isRebooting = ref(false)

// Estado para Kebab Menu Flotante (Sensores)
const openKebabId = ref(null)

// --- ESTADO PARA KEBAB MENU FLOTANTE (Grupos) ---
const openGroupKebab = ref(null)

const toggleGroupKebab = (gName, e) => {
  e?.stopPropagation()
  openGroupKebab.value = openGroupKebab.value === gName ? null : gName
}

const closeGroupKebab = () => {
  openGroupKebab.value = null
}

// --- FASE 4: FUNCIÓN MAESTRA PARA EVALUAR SILENCIOS EN CASCADA ---
function isItemPaused(item) {
  // 1. Silencio Supremo: Si la cuenta está silenciada, TODO está silenciado.
  if (isAccountMuted.value) return true 

  if (!item) return false
  // 2. Si está silenciado por el booleano duro
  if (item.alerts_paused === true) return true
  // 3. Si tiene un temporizador de grupo, monitor o sensor en el futuro
  if (item.alerts_paused_until) {
    const untilDate = new Date(item.alerts_paused_until)
    if (untilDate > new Date()) return true
  }
  return false
}

// --- LOGICA DE SILENCIO DE GRUPOS ---
async function muteGroup(groupName, hours, e) {
  e?.stopPropagation()
  closeGroupKebab()
  try {
    await api.put(`/groups/${encodeURIComponent(groupName)}/mute`, { hours: hours })
    showNotification(hours === -1 ? 'Alertas reactivadas para el grupo.' : 'Grupo silenciado correctamente.', 'success')
    
    // Refrescar lista de grupos para actualizar indicadores
    await fetchGroups()
    
    // Re-evaluar los pulsos visuales y sonidos de todos los monitores al instante
    allMonitors.value.forEach(m => {
        liveMonitorAlerts.value[m.monitor_id] = checkIfMonitorHasAlert(m)
    })
  } catch (err) {
    showNotification('Error al silenciar el grupo.', 'error')
  }
}

async function deleteGroupWithMonitors(groupName, e) {
  e?.stopPropagation()
  closeGroupKebab()
  
  const count = groupedMonitors.value[groupName]?.length || 0
  const msg = `¿ESTÁS ABSOLUTAMENTE SEGURO?\n\nVas a eliminar el grupo "${groupName}".\nEsto eliminará permanentemente ${count} dispositivos y todos sus sensores asociados de tu cuenta.`
  
  if (!confirm(msg)) return

  try {
    await api.delete(`/groups/${encodeURIComponent(groupName)}`)
    showNotification(`Grupo ${groupName} eliminado.`, 'success')
    
    // Refrescamos todo el entorno
    if (activeGroup.value === groupName) {
      activeGroup.value = 'General'
    }
    await fetchGroups()
    await fetchAllMonitors()
  } catch (err) {
    showNotification(err.response?.data?.detail || 'Error al eliminar el grupo.', 'error')
  }
}

// --- SISTEMA NOC: AUDIO, MEMORIA Y ACKNOWLEDGE ---

// 1. Memoria del Modo de Audio
const audioMode = ref(localStorage.getItem('noc_audio_mode') || 'mute') // 'mute', 'critical', 'all'

// 2. Memoria de Reconocimientos (Acknowledge)
let initialAcked = []
try {
  initialAcked = JSON.parse(localStorage.getItem('noc_acked_alerts') || '[]')
} catch(e) {}
const acknowledgedAlerts = ref(new Set(initialAcked))

// Función para guardar silencios permanentemente
function saveAckedAlerts() {
  localStorage.setItem('noc_acked_alerts', JSON.stringify(Array.from(acknowledgedAlerts.value)))
}

let audioCtx = null
let hasInteracted = false
let audioLoopTimer = null

function initAudio() {
  if (!audioCtx) {
    audioCtx = new (window.AudioContext || window.webkitAudioContext)()
  }
  if (audioCtx.state === 'suspended') {
    audioCtx.resume()
  }
}

function checkAndPlayExistingAlerts() {
  if (audioMode.value === 'mute' || !hasInteracted) return;
  let hasCritical = false;
  let hasWarning = false;

  for (const mid in liveMonitorAlerts.value) {
    const state = liveMonitorAlerts.value[mid];
    const isAcked = acknowledgedAlerts.value.has(mid) || acknowledgedAlerts.value.has(Number(mid)) || acknowledgedAlerts.value.has(String(mid));
    
    if (!isAcked) {
      if (state === 'critical') hasCritical = true;
      if (state === 'warning') hasWarning = true;
    }
  }

  if (hasCritical) {
    playCriticalSound();
  } else if (hasWarning && audioMode.value === 'all') {
    playWarningSound();
  }
}

function startAudioLoop() {
  if (audioLoopTimer) clearInterval(audioLoopTimer)
  audioLoopTimer = setInterval(checkAndPlayExistingAlerts, 5000)
}

function handleFirstInteraction() {
  if (hasInteracted) return;
  hasInteracted = true;
  initAudio();
  checkAndPlayExistingAlerts();
  startAudioLoop();
  document.removeEventListener('click', handleFirstInteraction);
}

function toggleAudioMode() {
  initAudio()
  if (audioMode.value === 'mute') audioMode.value = 'critical'
  else if (audioMode.value === 'critical') audioMode.value = 'all'
  else audioMode.value = 'mute'
  
  localStorage.setItem('noc_audio_mode', audioMode.value)
  showNotification(`Modo de audio: ${audioMode.value.toUpperCase()}`, 'success')
  
  checkAndPlayExistingAlerts()
}

function playWarningSound() {
  if (audioMode.value !== 'all') return
  initAudio()
  if (!audioCtx) return
  const osc = audioCtx.createOscillator()
  const gain = audioCtx.createGain()
  osc.connect(gain)
  gain.connect(audioCtx.destination)
  osc.type = 'sine'
  osc.frequency.setValueAtTime(600, audioCtx.currentTime) 
  gain.gain.setValueAtTime(0, audioCtx.currentTime)
  gain.gain.linearRampToValueAtTime(0.5, audioCtx.currentTime + 0.05)
  gain.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.5)
  osc.start(audioCtx.currentTime)
  osc.stop(audioCtx.currentTime + 0.5)
}

function playCriticalSound() {
  if (audioMode.value === 'mute') return
  initAudio()
  if (!audioCtx) return
  for (let i = 0; i < 3; i++) {
    const osc = audioCtx.createOscillator()
    const gain = audioCtx.createGain()
    osc.connect(gain)
    gain.connect(audioCtx.destination)
    osc.type = 'square' 
    osc.frequency.setValueAtTime(800 + (i % 2) * 200, audioCtx.currentTime + i * 0.2)
    gain.gain.setValueAtTime(0, audioCtx.currentTime + i * 0.2)
    gain.gain.linearRampToValueAtTime(0.3, audioCtx.currentTime + i * 0.2 + 0.02)
    gain.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + i * 0.2 + 0.15)
    osc.start(audioCtx.currentTime + i * 0.2)
    osc.stop(audioCtx.currentTime + i * 0.2 + 0.15)
  }
}

function toggleAcknowledge(monitorId, e) {
  e?.stopPropagation()
  if (acknowledgedAlerts.value.has(monitorId)) {
    acknowledgedAlerts.value.delete(monitorId)
  } else {
    acknowledgedAlerts.value.add(monitorId)
  }
  saveAckedAlerts()
}

// Estado para Rotación de Credenciales
const showRotateCredentialsModal = ref(false)
const rotateCredentialsForm = ref({ newUsername: '', newPassword: '', confirmPassword: '', credentialName: '' })
const isRotatingCredentials = ref(false)

// Estado para Bitácora
const showCommentsModal = ref(false)
const deviceComments = ref([])
const newCommentContent = ref('')
const isAddingComment = ref(false)

const allDevicesList = ref([])
const autoTasks = ref([])
const deviceInterfaces = ref([])
const isLoadingInterfaces = ref(false)

const hasParentMaestro = computed(() => !!currentMonitorContext.value?.maestro_id)
const channelsById = ref({})
const channelsList = computed(() => Object.values(channelsById.value))
const availableGroups = computed(() => [...dbGroups.value].sort())

const suggestedTargetDevicesForEdit = computed(() => {
  if (!currentMonitorContext.value) return []

  let currentVpnId = currentMonitorContext.value.vpn_profile_id

  if (currentMonitorContext.value.maestro_id) {
    const maestro = allDevicesList.value.find(
      (d) => d.id === currentMonitorContext.value.maestro_id,
    )
    if (maestro) {
      currentVpnId = maestro.vpn_profile_id
    }
  }

  return allDevicesList.value.filter((d) => {
    if (d.id === currentMonitorContext.value.device_id) return false
    if (!currentVpnId) return true
    if (d.is_maestro) {
      return d.vpn_profile_id === currentVpnId
    }
    if (d.maestro_id) {
      const destMaestro = allDevicesList.value.find((m) => m.id === d.maestro_id)
      return destMaestro && destMaestro.vpn_profile_id === currentVpnId
    }
    return d.vpn_profile_id === currentVpnId
  })
})

const createNewPingSensor = () => ({
  name: '', is_active: true, alerts_paused: false,
  config: { ping_type: 'device_to_external', target_ip: '', interval_sec: 60, latency_threshold_ms: 150, display_mode: 'realtime', average_count: 5, },
  ui_alert_timeout: { enabled: false, channel_id: null, cooldown_minutes: 5, tolerance_count: 1, notify_recovery: false, use_custom_message: false, custom_message: '', use_custom_recovery_message: false, custom_recovery_message: '', use_auto_task: false, trigger_task_id: null },
  ui_alert_latency: { enabled: false, threshold_ms: 200, channel_id: null, cooldown_minutes: 5, tolerance_count: 1, notify_recovery: false, use_custom_message: false, custom_message: '', use_custom_recovery_message: false, custom_recovery_message: '', use_auto_task: false, trigger_task_id: null },
})

const createNewEthernetSensor = () => ({
  name: '', is_active: true, alerts_paused: false,
  config: { interface_name: '', interval_sec: 30 },
  ui_alert_speed_change: { enabled: false, channel_id: null, cooldown_minutes: 10, tolerance_count: 1, notify_recovery: false, use_custom_message: false, custom_message: '', use_custom_recovery_message: false, custom_recovery_message: '', use_auto_task: false, trigger_task_id: null },
  ui_alert_traffic: { enabled: false, threshold_mbps: 100, direction: 'any', channel_id: null, cooldown_minutes: 5, tolerance_count: 1, notify_recovery: false, use_custom_message: false, custom_message: '', use_custom_recovery_message: false, custom_recovery_message: '', use_auto_task: false, trigger_task_id: null },
})

const createNewWirelessSensor = () => ({
  name: '', is_active: true, alerts_paused: false,
  config: { interface_name: '', interval_sec: 60, ignore_degraded: false, thresholds: { min_signal_dbm: -80, min_ccq_percent: 75, min_client_count: 0, min_tx_rate_mbps: 0, min_rx_rate_mbps: 0 }, tolerance_checks: 3, },
  ui_alert_status: { enabled: false, channel_id: null, cooldown_minutes: 10, notify_recovery: true, use_custom_message: false, custom_message: '', use_custom_recovery_message: false, custom_recovery_message: '', use_auto_task: false, trigger_task_id: null },
})

const createNewSystemSensor = () => ({
  name: '', is_active: true, alerts_paused: false,
  config: { interval_sec: 60, thresholds: { max_cpu_percent: 85, max_memory_percent: 90, max_temperature: 75, min_voltage: null, max_voltage: null, restart_uptime_seconds: 300 }, tolerance_checks: 3, },
  ui_alert_status: { enabled: false, channel_id: null, cooldown_minutes: 10, notify_recovery: true, use_custom_message: false, custom_message: '', use_custom_recovery_message: false, custom_recovery_message: '', use_auto_task: false, trigger_task_id: null },
})

const newPingSensor = ref(createNewPingSensor())
const newEthernetSensor = ref(createNewEthernetSensor())
const newWirelessSensor = ref(createNewWirelessSensor())
const newSystemSensor = ref(createNewSystemSensor())

const toggleKebab = (id, e) => {
  e?.stopPropagation()
  openKebabId.value = openKebabId.value === id ? null : id
}
const closeKebab = () => {
  openKebabId.value = null
}

// --- LOGICA UNIFICADA DE ALERTAS ---
function checkIfMonitorHasAlert(monitor) {
  if (!monitor || monitor.is_active === false) return 'ok';
  
  // VERIFICACIÓN VISUAL MAESTRA DE SILENCIO (Para silenciar la tarjeta y no molestar)
  if (isItemPaused(monitor)) return 'ok';
  if (groupMuteMap.value[monitor.group_name || 'General']) return 'ok';
  
  if (!monitor.sensors || monitor.sensors.length === 0) return 'ok';

  let highestSeverity = 'ok';

  for (const s of monitor.sensors) {
    if (s.is_active === false || isItemPaused(s)) continue;
    
    const status = liveSensorStatus.value[String(s.id)]?.status;
    const cfg = typeof s.config === 'string' ? safeJsonParse(s.config, {}) : (s.config || {});

    if (['timeout', 'error', 'link_down', 'critical'].includes(status)) {
      return 'critical'; 
    }

    if (['high_latency', 'degraded', 'searching'].includes(status)) {
      if (status === 'degraded' && cfg.ignore_degraded === true) {
        continue;
      }
      highestSeverity = 'warning'; 
    }
  }

  return highestSeverity;
}

// --- API FETCHERS ---
async function fetchGroups() {
  try {
    const { data } = await api.get('/groups')
    dbGroups.value = data.map((g) => g.name)
    
    // Mapeamos los estados silenciados por cada grupo
    const mutes = {}
    data.forEach(g => {
      mutes[g.name] = isItemPaused(g)
    })
    groupMuteMap.value = mutes
  } catch (err) {
    console.error('Error fetching groups:', err)
  }
}

async function fetchAllMonitors() {
  try {
    const { data } = await api.get('/monitors')
    allMonitors.value = Array.isArray(data) ? data : []

    // FASE 3: Extraer estado global de la cuenta (el backend lo inyecta en cada fila)
    if (allMonitors.value.length > 0) {
      accountMuteUntil.value = allMonitors.value[0].account_alerts_paused_until || null
    } else {
      accountMuteUntil.value = null
    }

    const initialStatus = {}
    const initialAlerts = {}

    allMonitors.value.forEach((m) => {
      if (m.is_active === null || m.is_active === undefined) m.is_active = true
      
      ;(m.sensors || []).forEach((s) => {
        const sid = String(s.id)
        if (!liveSensorStatus.value[sid]) initialStatus[sid] = { status: 'pending' }
        else initialStatus[sid] = liveSensorStatus.value[sid]
      })
      
      initialAlerts[m.monitor_id] = checkIfMonitorHasAlert(m)
    })
    
    liveSensorStatus.value = initialStatus
    liveMonitorAlerts.value = initialAlerts

    refreshGroupedMonitors()
    trySubscribeSensors()
  } catch (err) {
    console.error(err)
  }
}

async function fetchAllDevices() {
  try {
    const { data } = await api.get('/devices')
    allDevicesList.value = Array.isArray(data) ? data : []
  } catch (err) {
    console.error('Error fetching devices list:', err)
  }
}

async function fetchAutoTasks() {
  try {
    const { data } = await api.get('/scheduled-tasks/')
    autoTasks.value = data || []
  } catch (err) {
    console.error('Error al cargar tareas automáticas:', err)
  }
}

async function fetchDeviceInterfaces(deviceId) {
  isLoadingInterfaces.value = true;
  deviceInterfaces.value = [];
  try {
    const { data } = await api.get(`/devices/${deviceId}/interfaces`);
    deviceInterfaces.value = data || [];
  } catch (e) {
    console.warn(`No se pudieron cargar las interfaces para el equipo ${deviceId}.`);
  } finally {
    isLoadingInterfaces.value = false;
  }
}

async function addNewGroup() {
  const name = newGroupName.value.trim()
  if (!name) return

  try {
    await api.post('/groups', { name: name })
    await fetchGroups()
    refreshGroupedMonitors()
    activeGroup.value = name
    showGroupModal.value = false
    newGroupName.value = ''
    showNotification('Grupo creado exitosamente.')
  } catch (err) {
    console.error(err)
    showNotification('Error al crear grupo.', 'error')
  }
}

function refreshGroupedMonitors() {
  const groups = {}
  dbGroups.value.forEach((gName) => {
    groups[gName] = []
  })
  if (!groups['General']) groups['General'] = []

  const sorted = [...allMonitors.value].sort((a, b) => (a.position || 0) - (b.position || 0))
  sorted.forEach((m) => {
    const gName = m.group_name || 'General'
    if (!groups[gName]) groups[gName] = []
    groups[gName].push(m)
  })

  groupedMonitors.value = groups

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
  let hasWarning = false;
  for (const m of monitors) {
    if (!m.is_active) continue
    const state = liveMonitorAlerts.value[m.monitor_id];
    if (state === 'critical') return 'dot-red';
    if (state === 'warning') hasWarning = true;
  }
  return hasWarning ? 'dot-warning' : 'dot-green';
}

function expandAll() {
  if (!activeGroup.value || !groupedMonitors.value[activeGroup.value]) return
  groupedMonitors.value[activeGroup.value].forEach(m => collapsedCards.value.delete(m.monitor_id))
}

function collapseAll() {
  if (!activeGroup.value || !groupedMonitors.value[activeGroup.value]) return
  groupedMonitors.value[activeGroup.value].forEach(m => collapsedCards.value.add(m.monitor_id))
}

function expandAlertsOnly() {
  if (!activeGroup.value || !groupedMonitors.value[activeGroup.value]) return
  groupedMonitors.value[activeGroup.value].forEach(m => {
    const state = liveMonitorAlerts.value[m.monitor_id];
    if (state === 'critical' || state === 'warning') {
      collapsedCards.value.delete(m.monitor_id)
    } else {
      collapsedCards.value.add(m.monitor_id)
    }
  })
}

async function onDragChange() {
  if (!activeGroup.value) return
  const monitorsInGroup = groupedMonitors.value[activeGroup.value]
  const payloadItems = []

  monitorsInGroup.forEach((m, index) => {
    m.position = index
    payloadItems.push({ monitor_id: m.monitor_id, group_name: activeGroup.value, position: index })
  })

  try {
    await api.post('/monitors/reorder', { items: payloadItems })
  } catch {
    /* ignore */
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
function formatRateString(rate) {
  if (!rate || rate === 'N/A') return 'N/A'
  return String(rate).replace(/mbps/ig, '').trim()
}
function formatUptimeShort(seconds) {
  if (seconds == null) return ''
  const d = Math.floor(seconds / 86400)
  if (d > 0) return `${d}d`
  const h = Math.floor((seconds % 86400) / 3600)
  if (h > 0) return `${h}h`
  const m = Math.floor((seconds % 3600) / 60)
  return `${m}m`
}
function getStatusClass(status) {
  if (['timeout', 'error', 'link_down', 'critical'].includes(status)) return 'status-timeout'
  if (['high_latency', 'degraded', 'searching'].includes(status)) return 'status-high-latency'
  if (['ok', 'link_up', 'connected', 'optimal'].includes(status)) return 'status-ok'
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
  nextTick(resizeAllGridItems)
}
function formatDate(dateString) {
  if (!dateString) return ''
  return new Date(dateString).toLocaleString()
}
function isDegradedIgnored(sensor) {
  const cfg = typeof sensor.config === 'string' ? safeJsonParse(sensor.config, {}) : (sensor.config || {});
  return !!cfg.ignore_degraded;
}

// --- LOGICA "MASONRY" (CSS GRID DINÁMICO) ---
let gridResizeObserver = null;

function resizeGridItem(item) {
  if (!item) return;
  const grid = item.closest('.dashboard-grid');
  if (!grid) return;
  
  const rowHeight = parseInt(window.getComputedStyle(grid).getPropertyValue('grid-auto-rows'));
  const rowGap = parseInt(window.getComputedStyle(grid).getPropertyValue('gap'));
  
  const rowSpan = Math.ceil((item.querySelector('.monitor-card-inner').getBoundingClientRect().height + rowGap) / (rowHeight + rowGap));
  
  item.style.gridRowEnd = "span " + rowSpan;
}

function resizeAllGridItems() {
  const allItems = document.getElementsByClassName("monitor-card-wrapper");
  for (let x = 0; x < allItems.length; x++) {
    resizeGridItem(allItems[x]);
  }
}

function setupGridResizeObserver() {
  if (gridResizeObserver) {
    gridResizeObserver.disconnect();
  }
  
  gridResizeObserver = new ResizeObserver((entries) => {
    for (let entry of entries) {
      const wrapper = entry.target.closest('.monitor-card-wrapper');
      if (wrapper) resizeGridItem(wrapper);
    }
  });

  nextTick(() => {
    const inners = document.querySelectorAll('.monitor-card-inner');
    inners.forEach(inner => gridResizeObserver.observe(inner));
    resizeAllGridItems();
  });
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
    m.is_active !== false
      ? (m.sensors || []).filter((s) => s.is_active !== false).map((s) => s.id)
      : [],
  )
}

let subscribeTimeout = null;

function trySubscribeSensors() {
  if (subscribeTimeout) clearTimeout(subscribeTimeout);
  
  subscribeTimeout = setTimeout(() => {
    const ws = getCurrentWebSocket()
    if (!ws || ws.readyState !== 1) return
    
    const ids = currentSensorIds()
    if (ids.length > 0) {
      ws.send(JSON.stringify({ type: 'subscribe_sensors', sensor_ids: ids }))
    }
  }, 500);
}

watch(() => allMonitors.value.length, () => {
  trySubscribeSensors();
  setupGridResizeObserver();
})

watch(activeGroup, () => {
  nextTick(setupGridResizeObserver);
})

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

// BUZÓN TEMPORAL Y LÓGICA DE ESCALADA DE ALERTAS
let pendingWsUpdates = {}
let wsBufferTimer = null

function flushWsUpdates() {
  if (Object.keys(pendingWsUpdates).length === 0) return
  
  liveSensorStatus.value = { ...liveSensorStatus.value, ...pendingWsUpdates }
  const newAlerts = { ...liveMonitorAlerts.value }
  
  const affectedMonitorIds = new Set()
  const sensorToMonitorMap = {}
  allMonitors.value.forEach(m => {
      (m.sensors || []).forEach(s => {
          sensorToMonitorMap[String(s.id)] = m.monitor_id
      })
  })

  Object.keys(pendingWsUpdates).forEach(sid => {
      const mid = sensorToMonitorMap[sid]
      if (mid) affectedMonitorIds.add(mid)
  })

  affectedMonitorIds.forEach(mid => {
      const m = allMonitors.value.find(x => x.monitor_id === mid)
      const newState = checkIfMonitorHasAlert(m)
      
      newAlerts[mid] = newState

      // Si el equipo se recuperó, quitamos el "Acknowledge" automáticamente y de la memoria
      if (newState === 'ok' && acknowledgedAlerts.value.has(mid)) {
        acknowledgedAlerts.value.delete(mid)
        saveAckedAlerts()
      }
  })

  liveMonitorAlerts.value = newAlerts
  pendingWsUpdates = {}
}

function handleRawMessage(evt) {
  try {
    const parsed = JSON.parse(evt.data)

    // 1. Homogeneizamos la respuesta a un Array (sea un objeto único o un Batch de Fase 3)
    const eventsArray = Array.isArray(parsed) ? parsed : [parsed]

    // 2. --- NUEVO: Interceptar comandos del Bot de Telegram ---
    // Buscamos si AL MENOS UN evento en el lote solicita recargar la UI
    const needsReload = eventsArray.some(e => e && e.type === 'ui_reload_required')
    
    if (needsReload) {
      console.log("[WS] Recarga de UI solicitada por backend (Silencio/Bot).")
      fetchGroups()
      fetchAllMonitors()
      // IMPORTANTE: Ya no hacemos "return" aquí. 
      // El lote (batch) podría contener también pings o métricas importantes 
      // mezcladas con la alerta de recarga, así que dejamos que el código continúe.
    }
    // ------------------------------------------------------------------

    // 3. Dejamos que el normalizador extraiga únicamente lo que es de sensores
    const updates = normalizeWsPayload(parsed)
    updates.forEach((u) => {
      if (u.sensor_id) {
        pendingWsUpdates[String(u.sensor_id)] = {
          ...(liveSensorStatus.value[String(u.sensor_id)] || {}),
          ...(pendingWsUpdates[String(u.sensor_id)] || {}),
          ...u,
        }
      }
    })
  } catch {
    /* ignore */
  }
}

let wsOpenUnbind = null,
  directMsgUnbind = null

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
  await fetchGroups()
  await fetchAllMonitors()
  await fetchAllDevices()
  await fetchAutoTasks()

  await connectWebSocketWhenAuthenticated()
  wireWsSyncAndSubs()

  wsBufferTimer = setInterval(flushWsUpdates, 500)
  window.addEventListener("resize", resizeAllGridItems);
  
  document.addEventListener('click', closeKebab)
  document.addEventListener('click', closeGroupKebab) 
  document.addEventListener('click', handleFirstInteraction)
})

onUnmounted(() => {
  if (typeof wsOpenUnbind === 'function') wsOpenUnbind()
  if (typeof directMsgUnbind === 'function') directMsgUnbind()
  if (wsBufferTimer) clearInterval(wsBufferTimer)
  
  if (typeof audioLoopTimer !== 'undefined' && audioLoopTimer) clearInterval(audioLoopTimer)
  
  window.removeEventListener("resize", resizeAllGridItems);
  if (gridResizeObserver) gridResizeObserver.disconnect();
  document.removeEventListener('click', closeKebab)
  document.removeEventListener('click', closeGroupKebab)
  document.removeEventListener('click', handleFirstInteraction)
})

async function toggleMonitorPause(monitor) {
  const currentlyPaused = isItemPaused(monitor)
  const newVal = !currentlyPaused
  
  try {
    await api.put(`/monitors/${monitor.monitor_id}`, { alerts_paused: newVal })
    
    // Si quitamos la pausa, forzamos que se destrabe también a nivel frontend por si estaba en "until"
    monitor.alerts_paused = newVal
    if (!newVal) monitor.alerts_paused_until = null
    
    showNotification(newVal ? 'Alertas pausadas' : 'Alertas activas')
    liveMonitorAlerts.value[monitor.monitor_id] = checkIfMonitorHasAlert(monitor)
  } catch {
    showNotification('Error', 'error')
  }
}

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

async function deleteSensor(sensor, monitor, e) {
  e?.stopPropagation()
  closeKebab()
  if (!confirm(`¿Eliminar sensor "${sensor.name}"?`)) return

  try {
    await api.delete(`/sensors/${sensor.id}`)

    if (monitor && monitor.sensors) {
      monitor.sensors = monitor.sensors.filter((s) => s.id !== sensor.id)
    }

    if (activeGroup.value && groupedMonitors.value[activeGroup.value]) {
        const groupMonitor = groupedMonitors.value[activeGroup.value].find(m => m.monitor_id === monitor.monitor_id);
        if (groupMonitor && groupMonitor.sensors) {
            groupMonitor.sensors = groupMonitor.sensors.filter((s) => s.id !== sensor.id);
        }
    }

    showNotification('Sensor eliminado correctamente.', 'success')
  } catch (err) {
    console.error(err)
    showNotification('Error al eliminar sensor.', 'error')
  }
}

async function toggleSensorPause(sensor, monitor, e) {
  e?.stopPropagation()
  closeKebab()
  
  const currentlyPaused = isItemPaused(sensor)
  const newVal = !currentlyPaused

  try {
    const cfg = typeof sensor.config === 'string' ? safeJsonParse(sensor.config, {}) : { ...(sensor.config || {}) }
    const payload = {
      name: sensor.name,
      is_active: sensor.is_active,
      alerts_paused: newVal,
      config: cfg
    }
    
    await api.put(`/sensors/${sensor.id}`, payload)
    
    sensor.alerts_paused = newVal
    if (!newVal) sensor.alerts_paused_until = null
    
    liveMonitorAlerts.value[monitor.monitor_id] = checkIfMonitorHasAlert(monitor)
    showNotification(newVal ? 'Alertas pausadas para este sensor.' : 'Alertas reactivadas.', 'success')
  } catch (err) {
    console.error(err)
    showNotification('Error al cambiar estado del sensor.', 'error')
  }
}

async function toggleIgnoreDegraded(sensor, monitor, e) {
  e?.stopPropagation()
  closeKebab()
  
  const cfg = typeof sensor.config === 'string' ? safeJsonParse(sensor.config, {}) : { ...(sensor.config || {}) }
  const currentIgnore = !!cfg.ignore_degraded
  const newIgnore = !currentIgnore
  
  cfg.ignore_degraded = newIgnore

  try {
    const payload = {
      name: sensor.name,
      is_active: sensor.is_active,
      alerts_paused: sensor.alerts_paused,
      config: cfg
    }
    
    await api.put(`/sensors/${sensor.id}`, payload)
    sensor.config = cfg
    
    liveMonitorAlerts.value[monitor.monitor_id] = checkIfMonitorHasAlert(monitor)
    showNotification(newIgnore ? 'Avisos "Degraded" silenciados para este sensor.' : 'Avisos "Degraded" reactivados.', 'success')
  } catch (err) {
    console.error(err)
    showNotification('Error al silenciar aviso degraded.', 'error')
  }
}

// --- GESTIÓN DE HERRAMIENTAS DEL DISPOSITIVO ---
function openMonitorSettings(monitor) {
  monitorToEdit.value = monitor
  editMonitorGroup.value = monitor.group_name || 'General'
}

function openTerminal() {
  if (!monitorToEdit.value?.device_id) return
  const routeData = router.resolve({
    path: '/terminal',
    query: { device_id: monitorToEdit.value.device_id }
  })
  window.open(routeData.href, '_blank')
}

async function openCommentsModal() {
  if (!monitorToEdit.value?.device_id) return
  showCommentsModal.value = true
  deviceComments.value = []
  newCommentContent.value = ''
  try {
    const { data } = await api.get(`/devices/${monitorToEdit.value.device_id}/comments`)
    deviceComments.value = data
  } catch (err) {
    showNotification('Error al cargar comentarios.', 'error')
  }
}

async function addComment() {
  if (!newCommentContent.value.trim()) return
  isAddingComment.value = true
  try {
    const { data } = await api.post(`/devices/${monitorToEdit.value.device_id}/comments`, {
      content: newCommentContent.value.trim()
    })
    deviceComments.value.unshift(data)
    newCommentContent.value = ''
    showNotification('Comentario agregado')
  } catch (err) {
    showNotification('Error al agregar comentario', 'error')
  } finally {
    isAddingComment.value = false
  }
}

function triggerRotateCredentials() {
  rotateCredentialsForm.value = {
    newUsername: '',
    newPassword: '',
    confirmPassword: '',
    credentialName: `Cred-${monitorToEdit.value.client_name}-${new Date().toISOString().split('T')[0]}`
  }
  showRotateCredentialsModal.value = true
}

async function submitRotateCredentials() {
  if (rotateCredentialsForm.value.newPassword !== rotateCredentialsForm.value.confirmPassword) {
    showNotification('Las contraseñas no coinciden', 'error')
    return
  }
  if (!rotateCredentialsForm.value.credentialName.trim()) {
    showNotification('El nombre de perfil es obligatorio', 'error')
    return
  }

  isRotatingCredentials.value = true
  try {
    await api.post(`/devices/${monitorToEdit.value.device_id}/rotate-credentials`, {
      new_username: rotateCredentialsForm.value.newUsername.trim() || null,
      new_password: rotateCredentialsForm.value.newPassword,
      new_credential_name: rotateCredentialsForm.value.credentialName
    })
    
    showNotification('Credenciales rotadas exitosamente', 'success')
    showRotateCredentialsModal.value = false
    monitorToEdit.value = null 
    
    await fetchAllMonitors()
    await fetchAllDevices()
    
  } catch (err) {
    showNotification(err.response?.data?.detail || 'Error al rotar credenciales', 'error')
  } finally {
    isRotatingCredentials.value = false
  }
}

async function saveMonitorSettings() {
  if (!monitorToEdit.value) return
  const newGroup = editMonitorGroup.value

  if (newGroup !== monitorToEdit.value.group_name) {
    try {
      await api.put(`/monitors/${monitorToEdit.value.monitor_id}`, { group_name: newGroup })
      if (!dbGroups.value.includes(newGroup)) {
        await fetchGroups()
      }
      const mLocal = allMonitors.value.find((m) => m.monitor_id === monitorToEdit.value.monitor_id)
      if (mLocal) mLocal.group_name = newGroup
      refreshGroupedMonitors()
      showNotification('Grupo actualizado')
    } catch (err) {
      console.error(err)
      showNotification('Error al actualizar grupo', 'error')
    }
  }
  monitorToEdit.value = null
}

async function requestReboot() {
  const m = monitorToEdit.value
  if (!m || !m.device_id) return

  if (
    !confirm(
      `¿Estás seguro de REINICIAR el dispositivo ${m.client_name}?\nSe perderá la conexión temporalmente.`,
    )
  ) {
    return
  }

  isRebooting.value = true
  try {
    await api.post(`/devices/${m.device_id}/reboot`)
    showNotification(`Reiniciando ${m.client_name}...`, 'success')
    monitorToEdit.value = null 
  } catch (err) {
    console.error(err)
    showNotification(err.response?.data?.detail || 'Error al enviar comando de reinicio.', 'error')
  } finally {
    isRebooting.value = false
  }
}

async function showSensorDetails(s, m, e) {
  e?.stopPropagation()
  closeKebab()
  await ensureChannelsLoaded()
  
  sensorDetailsToShow.value = s
  currentMonitorContext.value = m
  
  if (['ethernet', 'wireless'].includes(s.sensor_type) && m.device_id) {
    fetchDeviceInterfaces(m.device_id)
  }

  const cfg = typeof s.config === 'string' ? safeJsonParse(s.config, {}) : s.config
  const alerts = cfg?.alerts || []

  if (s.sensor_type === 'ping') {
    const uiData = createNewPingSensor()
    uiData.name = s.name
    uiData.is_active = s.is_active !== false
    uiData.alerts_paused = s.alerts_paused === true
    uiData.config = { ...uiData.config, ...cfg }
    if (!m.maestro_id) uiData.config.ping_type = 'device_to_external'

    const tOut = mapAlert(alerts, 'timeout')
    if (tOut.type) {
      uiData.ui_alert_timeout = {
        enabled: true,
        ...tOut,
        channel_id: tOut.channel_id ?? null,
        notify_recovery: tOut.notify_recovery ?? false,
        use_custom_message: !!tOut.custom_message,
        custom_message: tOut.custom_message || '',
        use_custom_recovery_message: !!tOut.custom_recovery_message,
        custom_recovery_message: tOut.custom_recovery_message || '',
        use_auto_task: !!tOut.trigger_task_id,
        trigger_task_id: tOut.trigger_task_id || null,
      }
    }

    const tLat = mapAlert(alerts, 'high_latency')
    if (tLat.type) {
      uiData.ui_alert_latency = {
        enabled: true,
        ...tLat,
        channel_id: tLat.channel_id ?? null,
        notify_recovery: tLat.notify_recovery ?? false,
        use_custom_message: !!tLat.custom_message,
        custom_message: tLat.custom_message || '',
        use_custom_recovery_message: !!tLat.custom_recovery_message,
        custom_recovery_message: tLat.custom_recovery_message || '',
        use_auto_task: !!tLat.trigger_task_id,
        trigger_task_id: tLat.trigger_task_id || null,
      }
    }
    newPingSensor.value = uiData

  } else if (s.sensor_type === 'ethernet') {
    const uiData = createNewEthernetSensor()
    uiData.name = s.name
    uiData.is_active = s.is_active !== false
    uiData.alerts_paused = s.alerts_paused === true
    uiData.config = {
      interface_name: cfg.interface_name || '',
      interval_sec: cfg.interval_sec || 60,
    }

    const tSpd = mapAlert(alerts, 'speed_change')
    if (tSpd.type) {
      uiData.ui_alert_speed_change = {
        enabled: true,
        ...tSpd,
        channel_id: tSpd.channel_id ?? null,
        notify_recovery: tSpd.notify_recovery ?? false,
        use_custom_message: !!tSpd.custom_message,
        custom_message: tSpd.custom_message || '',
        use_custom_recovery_message: !!tSpd.custom_recovery_message,
        custom_recovery_message: tSpd.custom_recovery_message || '',
        use_auto_task: !!tSpd.trigger_task_id,
        trigger_task_id: tSpd.trigger_task_id || null,
      }
    }

    const tTrf = mapAlert(alerts, 'traffic_threshold')
    if (tTrf.type) {
      uiData.ui_alert_traffic = {
        enabled: true,
        ...tTrf,
        channel_id: tTrf.channel_id ?? null,
        notify_recovery: tTrf.notify_recovery ?? false,
        use_custom_message: !!tTrf.custom_message,
        custom_message: tTrf.custom_message || '',
        use_custom_recovery_message: !!tTrf.custom_recovery_message,
        custom_recovery_message: tTrf.custom_recovery_message || '',
        use_auto_task: !!tTrf.trigger_task_id,
        trigger_task_id: tTrf.trigger_task_id || null,
      }
    }
    newEthernetSensor.value = uiData

  } else if (s.sensor_type === 'wireless') {
    const uiData = createNewWirelessSensor()
    uiData.name = s.name
    uiData.is_active = s.is_active !== false
    uiData.alerts_paused = s.alerts_paused === true
    uiData.config = {
      interface_name: cfg.interface_name || '',
      interval_sec: cfg.interval_sec || 60,
      ignore_degraded: cfg.ignore_degraded || false,
      tolerance_checks: cfg.tolerance_checks ?? 3,
      thresholds: {
        min_signal_dbm: cfg.thresholds?.min_signal_dbm ?? -80,
        min_ccq_percent: cfg.thresholds?.min_ccq_percent ?? 75,
        min_client_count: cfg.thresholds?.min_client_count ?? 0,
        min_tx_rate_mbps: cfg.thresholds?.min_tx_rate_mbps ?? 0,
        min_rx_rate_mbps: cfg.thresholds?.min_rx_rate_mbps ?? 0,
      }
    }

    const tWir = mapAlert(alerts, 'wireless_status')
    if (tWir.type) {
      uiData.ui_alert_status = {
        enabled: true,
        ...tWir,
        channel_id: tWir.channel_id ?? null,
        notify_recovery: tWir.notify_recovery ?? true,
        use_custom_message: !!tWir.custom_message,
        custom_message: tWir.custom_message || '',
        use_custom_recovery_message: !!tWir.custom_recovery_message,
        custom_recovery_message: tWir.custom_recovery_message || '',
        use_auto_task: !!tWir.trigger_task_id,
        trigger_task_id: tWir.trigger_task_id || null,
      }
    }
    newWirelessSensor.value = uiData

  } else if (s.sensor_type === 'system') {
    const uiData = createNewSystemSensor()
    uiData.name = s.name
    uiData.is_active = s.is_active !== false
    uiData.alerts_paused = s.alerts_paused === true
    uiData.config = {
      interval_sec: cfg.interval_sec || 60,
      tolerance_checks: cfg.tolerance_checks ?? 3,
      thresholds: {
        max_cpu_percent: cfg.thresholds?.max_cpu_percent ?? null,
        max_memory_percent: cfg.thresholds?.max_memory_percent ?? null,
        max_temperature: cfg.thresholds?.max_temperature ?? null,
        min_voltage: cfg.thresholds?.min_voltage ?? null,
        max_voltage: cfg.thresholds?.max_voltage ?? null,
        restart_uptime_seconds: cfg.thresholds?.restart_uptime_seconds ?? 300,
      }
    }

    const tSys = mapAlert(alerts, 'system_status')
    if (tSys.type) {
      uiData.ui_alert_status = {
        enabled: true,
        ...tSys,
        channel_id: tSys.channel_id ?? null,
        notify_recovery: tSys.notify_recovery ?? true,
        use_custom_message: !!tSys.custom_message,
        custom_message: tSys.custom_message || '',
        use_custom_recovery_message: !!tSys.custom_recovery_message,
        custom_recovery_message: tSys.custom_recovery_message || '',
        use_auto_task: !!tSys.trigger_task_id,
        trigger_task_id: tSys.trigger_task_id || null,
      }
    }
    newSystemSensor.value = uiData
  }
}

async function handleUpdateSensor() {
  if (!sensorDetailsToShow.value) return

  const type = sensorDetailsToShow.value.sensor_type
  const uiData = type === 'ping' 
    ? newPingSensor.value 
    : type === 'ethernet' 
      ? newEthernetSensor.value 
      : type === 'wireless' 
        ? newWirelessSensor.value 
        : newSystemSensor.value

  const config = { ...uiData.config }
  config.alerts = []
  const num = (v, d) => (typeof v === 'number' && !isNaN(v) ? v : d)

  if (type === 'ping') {
    const t = uiData.ui_alert_timeout
    if (t.enabled && t.channel_id) {
      const alertObj = {
        type: 'timeout',
        channel_id: t.channel_id,
        cooldown_minutes: num(t.cooldown_minutes, 5),
        tolerance_count: num(t.tolerance_count, 1),
        notify_recovery: !!t.notify_recovery,
      }
      if (t.use_custom_message && t.custom_message?.trim()) alertObj.custom_message = t.custom_message.trim()
      if (t.use_custom_recovery_message && t.custom_recovery_message?.trim()) alertObj.custom_recovery_message = t.custom_recovery_message.trim()
      if (t.use_auto_task && t.trigger_task_id) alertObj.trigger_task_id = t.trigger_task_id
      config.alerts.push(alertObj)
    }

    const l = uiData.ui_alert_latency
    if (l.enabled && l.channel_id) {
      const alertObj = {
        type: 'high_latency',
        threshold_ms: num(l.threshold_ms, 200),
        channel_id: l.channel_id,
        cooldown_minutes: num(l.cooldown_minutes, 5),
        tolerance_count: num(l.tolerance_count, 1),
        notify_recovery: !!l.notify_recovery,
      }
      if (l.use_custom_message && l.custom_message?.trim()) alertObj.custom_message = l.custom_message.trim()
      if (l.use_custom_recovery_message && l.custom_recovery_message?.trim()) alertObj.custom_recovery_message = l.custom_recovery_message.trim()
      if (l.use_auto_task && l.trigger_task_id) alertObj.trigger_task_id = l.trigger_task_id
      config.alerts.push(alertObj)
    }
  } else if (type === 'ethernet') {
    const s = uiData.ui_alert_speed_change
    if (s.enabled && s.channel_id) {
      const alertObj = {
        type: 'speed_change',
        channel_id: s.channel_id,
        cooldown_minutes: num(s.cooldown_minutes, 10),
        tolerance_count: num(s.tolerance_count, 1),
        notify_recovery: !!s.notify_recovery,
      }
      if (s.use_custom_message && s.custom_message?.trim()) alertObj.custom_message = s.custom_message.trim()
      if (s.use_custom_recovery_message && s.custom_recovery_message?.trim()) alertObj.custom_recovery_message = s.custom_recovery_message.trim()
      if (s.use_auto_task && s.trigger_task_id) alertObj.trigger_task_id = s.trigger_task_id
      config.alerts.push(alertObj)
    }

    const tr = uiData.ui_alert_traffic
    if (tr.enabled && tr.channel_id) {
      const alertObj = {
        type: 'traffic_threshold',
        threshold_mbps: num(tr.threshold_mbps, 100),
        direction: tr.direction || 'any',
        channel_id: tr.channel_id,
        cooldown_minutes: num(tr.cooldown_minutes, 5),
        tolerance_count: num(tr.tolerance_count, 1),
        notify_recovery: !!tr.notify_recovery,
      }
      if (tr.use_custom_message && tr.custom_message?.trim()) alertObj.custom_message = tr.custom_message.trim()
      if (tr.use_custom_recovery_message && tr.custom_recovery_message?.trim()) alertObj.custom_recovery_message = tr.custom_recovery_message.trim()
      if (tr.use_auto_task && tr.trigger_task_id) alertObj.trigger_task_id = tr.trigger_task_id
      config.alerts.push(alertObj)
    }
  } else if (type === 'wireless') {
    config.thresholds = {
      min_signal_dbm: num(uiData.config.thresholds.min_signal_dbm, -80),
      min_ccq_percent: num(uiData.config.thresholds.min_ccq_percent, 75),
      min_client_count: num(uiData.config.thresholds.min_client_count, 0),
      min_tx_rate_mbps: num(uiData.config.thresholds.min_tx_rate_mbps, 0),
      min_rx_rate_mbps: num(uiData.config.thresholds.min_rx_rate_mbps, 0)
    }
    config.tolerance_checks = Math.max(1, num(uiData.config.tolerance_checks, 3))

    const w = uiData.ui_alert_status
    if (w.enabled && w.channel_id) {
      const alertObj = {
        type: 'wireless_status',
        channel_id: w.channel_id,
        cooldown_minutes: num(w.cooldown_minutes, 10),
        notify_recovery: !!w.notify_recovery
      }
      if (w.use_custom_message && w.custom_message?.trim()) alertObj.custom_message = w.custom_message.trim()
      if (w.use_custom_recovery_message && w.custom_recovery_message?.trim()) alertObj.custom_recovery_message = w.custom_recovery_message.trim()
      if (w.use_auto_task && w.trigger_task_id) alertObj.trigger_task_id = w.trigger_task_id
      config.alerts.push(alertObj)
    }
  } else if (type === 'system') {
    config.thresholds = {
      max_cpu_percent: num(uiData.config.thresholds.max_cpu_percent, null),
      max_memory_percent: num(uiData.config.thresholds.max_memory_percent, null),
      max_temperature: num(uiData.config.thresholds.max_temperature, null),
      min_voltage: num(uiData.config.thresholds.min_voltage, null),
      max_voltage: num(uiData.config.thresholds.max_voltage, null),
      restart_uptime_seconds: num(uiData.config.thresholds.restart_uptime_seconds, 300),
    }
    config.tolerance_checks = Math.max(1, num(uiData.config.tolerance_checks, 3))

    const w = uiData.ui_alert_status
    if (w.enabled && w.channel_id) {
      const alertObj = {
        type: 'system_status',
        channel_id: w.channel_id,
        cooldown_minutes: num(w.cooldown_minutes, 10),
        notify_recovery: !!w.notify_recovery
      }
      if (w.use_custom_message && w.custom_message?.trim()) alertObj.custom_message = w.custom_message.trim()
      if (w.use_custom_recovery_message && w.custom_recovery_message?.trim()) alertObj.custom_recovery_message = w.custom_recovery_message.trim()
      if (w.use_auto_task && w.trigger_task_id) alertObj.trigger_task_id = w.trigger_task_id
      config.alerts.push(alertObj)
    }
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

    showNotification('Sensor guardado')
    if (payload.is_active !== sensorDetailsToShow.value.is_active) trySubscribeSensors()
    closeSensorDetails()
  } catch {
    showNotification('Error al guardar sensor', 'error')
  }
}

function closeSensorDetails() {
  sensorDetailsToShow.value = null
  currentMonitorContext.value = null
}
</script>

<template>
  <div class="layout-container">
    <aside class="sidebar" :class="{ 'sidebar-collapsed': isSidebarCollapsed }">
      <div class="sidebar-header">
        <h3 v-if="!isSidebarCollapsed">GRUPOS</h3>
        <button
          class="btn-toggle-sidebar"
          @click="isSidebarCollapsed = !isSidebarCollapsed"
          title="Alternar Barra"
        >
          {{ isSidebarCollapsed ? '☰' : '«' }}
        </button>
      </div>

      <div class="sidebar-actions" v-if="!isSidebarCollapsed">
        <button class="btn-add-group" @click="showGroupModal = true">+ Nuevo Grupo</button>
      </div>

      <ul class="group-list">
        <li
          v-for="gName in Object.keys(groupedMonitors).sort()"
          :key="gName"
          :class="{ active: activeGroup === gName }"
          @click="activeGroup = gName"
          :title="gName"
          style="position: relative;"
        >
          <span :class="['status-dot', getGroupStatusClass(gName)]"></span>
          
          <span v-if="!isSidebarCollapsed" class="group-name" :class="{'text-orange': groupMuteMap[gName]}">
            {{ gName }} 
            <small v-if="groupMuteMap[gName] || isAccountMuted" title="Silenciado">🔕</small>
          </span>
          
          <span v-if="!isSidebarCollapsed" class="badge">{{ groupedMonitors[gName].length }}</span>
          
          <div v-if="!isSidebarCollapsed && gName !== 'General'" class="kebab-container" style="margin-left: auto; padding-left: 5px;" @click.stop>
            <button class="kebab-btn" @click="toggleGroupKebab(gName, $event)">⋮</button>
            <div v-if="openGroupKebab === gName" class="kebab-dropdown" style="top: 100%; right: 0; left: auto; position: absolute;">
              <button class="kebab-item" @click="muteGroup(gName, 1, $event)">⏳ Silenciar 1 Hora</button>
              <button class="kebab-item" @click="muteGroup(gName, 12, $event)">⏳ Silenciar 12 Horas</button>
              <button class="kebab-item" @click="muteGroup(gName, 0, $event)">💤 Silenciar Indefinido</button>
              <button class="kebab-item" @click="muteGroup(gName, -1, $event)">🔊 Reanudar Alertas</button>
              <hr style="border: 0; border-top: 1px solid var(--primary-color); margin: 4px 0;">
              <button class="kebab-item text-danger" @click="deleteGroupWithMonitors(gName, $event)">🗑️ Eliminar Grupo</button>
            </div>
          </div>
        </li>
      </ul>
    </aside>

    <main class="main-content">
      <div v-if="isAccountMuted" class="global-mute-banner">
        <span>🔇 <strong>MODO SILENCIO GLOBAL ACTIVO:</strong> Las notificaciones de toda la cuenta están pausadas.</span>
        <span class="mute-time" v-if="accountMuteUntil && new Date(accountMuteUntil).getFullYear() < 2030">
          Hasta: {{ new Date(accountMuteUntil).toLocaleString() }}
        </span>
        <span class="mute-time" v-else>
          (Indefinido)
        </span>
      </div>

      <header class="content-header" v-if="activeGroup">
        <h2>{{ activeGroup }}</h2>
        <div class="header-actions">
          
          <div class="view-controls" style="margin-right: 15px;">
            <button 
              class="action-icon-btn audio-btn" 
              :class="{'is-muted': audioMode === 'mute'}"
              @click="toggleAudioMode" 
              :title="'Modo Audio NOC: ' + audioMode.toUpperCase()"
            >
              <template v-if="audioMode === 'all'">🔊 Todo</template>
              <template v-else-if="audioMode === 'critical'">⚠️ Crítico</template>
              <template v-else>🔇 Mute</template>
            </button>
          </div>

          <div class="view-controls">
            <button class="action-icon-btn" @click="expandAll" title="Abrir todas las tarjetas">🔽</button>
            <button class="action-icon-btn" @click="collapseAll" title="Cerrar todas las tarjetas">🔼</button>
            <button class="action-icon-btn text-orange" @click="expandAlertsOnly" title="Abrir Inteligente (Solo con alertas)">⚠️</button>
          </div>
          <router-link to="/monitor-builder" class="btn-primary">Añadir Dispositivo</router-link>
        </div>
      </header>
      <div v-else-if="!isAccountMuted" class="empty-selection">
        <p>Selecciona un grupo para ver sus monitores</p>
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
            <div class="monitor-card-wrapper" :data-id="monitor.monitor_id">
              <div
                class="monitor-card monitor-card-inner"
                :class="{
                  'status-critical': liveMonitorAlerts[monitor.monitor_id] === 'critical',
                  'status-warning': liveMonitorAlerts[monitor.monitor_id] === 'warning',
                  'is-inactive': !monitor.is_active,
                  'is-collapsed': collapsedCards.has(monitor.monitor_id),
                  'is-acknowledged': acknowledgedAlerts.has(monitor.monitor_id) || acknowledgedAlerts.has(String(monitor.monitor_id))
                }"
              >
                <div class="card-header" @dblclick="toggleCardCollapse(monitor.monitor_id)">
                  <div class="header-left">
                    <span class="drag-handle">::</span>
                    <div class="title-container">
                      <h3>{{ monitor.client_name }}</h3>
                      <div class="badges-row">
                        <span v-if="!monitor.is_active" class="off-badge">OFF</span>
                        <span v-if="isItemPaused(monitor) || groupMuteMap[monitor.group_name || 'General']" class="pause-badge" title="Alertas Pausadas">⏸️</span>
                      </div>
                    </div>
                  </div>

                  <div class="card-actions-right">
                    <span class="device-ip" v-if="!collapsedCards.has(monitor.monitor_id)">
                      {{ monitor.ip_address }}
                    </span>
                    
                    <template v-if="liveMonitorAlerts[monitor.monitor_id] === 'critical' || liveMonitorAlerts[monitor.monitor_id] === 'warning'">
                      <button 
                        class="action-icon-btn ack-btn"
                        :class="{'is-acked': acknowledgedAlerts.has(monitor.monitor_id) || acknowledgedAlerts.has(String(monitor.monitor_id))}"
                        @click="toggleAcknowledge(monitor.monitor_id, $event)"
                        :title="(acknowledgedAlerts.has(monitor.monitor_id) || acknowledgedAlerts.has(String(monitor.monitor_id))) ? 'Reactivar Alarma' : 'Reconocer / Silenciar Alarma (Acknowledge)'"
                      >
                        {{ (acknowledgedAlerts.has(monitor.monitor_id) || acknowledgedAlerts.has(String(monitor.monitor_id))) ? '🔕' : '🔔' }}
                      </button>
                    </template>

                    <button
                      class="action-icon-btn"
                      @click="openMonitorSettings(monitor)"
                      title="Configuración y Herramientas"
                    >
                      ⚙️
                    </button>

                    <button
                      class="action-icon-btn"
                      @click="toggleCardCollapse(monitor.monitor_id)"
                      :title="collapsedCards.has(monitor.monitor_id) ? 'Expandir' : 'Colapsar'"
                    >
                      {{ collapsedCards.has(monitor.monitor_id) ? '🔽' : '🔼' }}
                    </button>
                    <button
                      class="action-icon-btn"
                      :class="{ 'active-orange': isItemPaused(monitor) }"
                      @click="toggleMonitorPause(monitor)"
                      title="Pausar Alertas"
                    >
                      {{ isItemPaused(monitor) ? '🔕' : '🔔' }}
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
                        'row-paused': isItemPaused(sensor),
                      }"
                    >
                      <div class="sensor-tier-top" @click="goToSensorDetail(sensor.id)">
                        <span class="sensor-name" :title="sensor.name">
                          {{ sensor.name }}
                          <small v-if="isItemPaused(sensor)" title="Alertas Pausadas">⏸️</small>
                        </span>

                        <div class="sensor-top-right">
                          <div
                            class="sensor-main-status"
                            :class="getStatusClass(liveSensorStatus[String(sensor.id)]?.status)"
                          >
                            <template v-if="!sensor.is_active">
                              <span class="text-off">OFF</span>
                            </template>

                            <template v-else-if="sensor.sensor_type === 'ping'">
                              <span v-if="liveSensorStatus[String(sensor.id)]?.status === 'timeout'">Timeout</span>
                              <span v-else-if="liveSensorStatus[String(sensor.id)]?.status === 'error'">Error</span>
                              <span v-else-if="liveSensorStatus[String(sensor.id)]?.status === 'pending'">...</span>
                              <span v-else>{{ formatLatency(liveSensorStatus[String(sensor.id)]?.latency_ms) }} ms</span>
                            </template>

                            <template v-else-if="sensor.sensor_type === 'ethernet'">
                              {{ (liveSensorStatus[String(sensor.id)]?.status || 'pending').replace('_', ' ').toUpperCase() }}
                            </template>

                            <template v-else-if="sensor.sensor_type === 'wireless'">
                              <span v-if="liveSensorStatus[String(sensor.id)]?.wireless_role === 'AP'" title="Punto de Acceso">📡 AP</span>
                              <span v-else-if="liveSensorStatus[String(sensor.id)]?.wireless_role === 'CPE'" title="Estación / Cliente">📶 CPE</span>
                              <span v-else>📡</span>
                              {{ (liveSensorStatus[String(sensor.id)]?.status || 'pending').toUpperCase() }}
                            </template>

                            <template v-else-if="sensor.sensor_type === 'system'">
                              💻 {{ (liveSensorStatus[String(sensor.id)]?.status || 'pending').toUpperCase() }}
                            </template>

                            <template v-else>
                              {{ liveSensorStatus[String(sensor.id)]?.status || 'pending' }}
                            </template>
                          </div>

                          <div class="kebab-container" @click.stop>
                            <button class="kebab-btn" @click="toggleKebab(sensor.id, $event)">⋮</button>
                            <div v-if="openKebabId === sensor.id" class="kebab-dropdown">
                              <button class="kebab-item" @click="toggleSensorPause(sensor, monitor, $event)">
                                {{ isItemPaused(sensor) ? '▶ Reanudar Alertas' : '⏸ Pausar Alertas' }}
                              </button>
                              <button 
                                v-if="sensor.sensor_type === 'wireless'" 
                                class="kebab-item" 
                                @click="toggleIgnoreDegraded(sensor, monitor, $event)"
                              >
                                {{ isDegradedIgnored(sensor) ? '🙉 Avisar Degraded' : '🙈 Ignorar Degraded' }}
                              </button>
                              <button class="kebab-item" @click="showSensorDetails(sensor, monitor, $event)">
                                ✎ Editar Sensor
                              </button>
                              <button class="kebab-item text-danger" @click="deleteSensor(sensor, monitor, $event)">
                                ✕ Eliminar Sensor
                              </button>
                            </div>
                          </div>
                        </div>
                      </div>

                      <div
                        class="sensor-tier-bottom"
                        v-if="sensor.is_active && sensor.sensor_type !== 'ping' && !['pending', 'timeout', 'error'].includes(liveSensorStatus[String(sensor.id)]?.status)"
                      >
                        <template v-if="sensor.sensor_type === 'ethernet'">
                          <span class="metric-item speed" v-if="liveSensorStatus[String(sensor.id)]?.status === 'link_up'">
                            🔗 {{ liveSensorStatus[String(sensor.id)]?.speed || '—' }}
                          </span>
                          <span class="metric-item">↓ {{ formatBitrate(liveSensorStatus[String(sensor.id)]?.rx_bitrate) }}</span>
                          <span class="metric-item">↑ {{ formatBitrate(liveSensorStatus[String(sensor.id)]?.tx_bitrate) }}</span>
                        </template>

                        <template v-else-if="sensor.sensor_type === 'wireless'">
                          <span class="metric-item" title="Señal">
                            📶 {{ liveSensorStatus[String(sensor.id)]?.signal_strength || 0 }} dBm
                          </span>
                          <span class="metric-item" title="CCQ (TX)">
                            📊 {{ liveSensorStatus[String(sensor.id)]?.tx_ccq || 0 }}%
                          </span>
                          <span class="metric-item" v-if="liveSensorStatus[String(sensor.id)]?.wireless_role === 'AP'" title="Clientes">
                            👥 {{ liveSensorStatus[String(sensor.id)]?.client_count || 0 }}
                          </span>
                          <span class="metric-item" title="TX / RX Rate (Mbps)">
                            🚀 {{ formatRateString(liveSensorStatus[String(sensor.id)]?.tx_rate) }} / {{ formatRateString(liveSensorStatus[String(sensor.id)]?.rx_rate) }} Mbps
                          </span>
                        </template>

                        <template v-else-if="sensor.sensor_type === 'system'">
                          <span class="metric-item" v-if="liveSensorStatus[String(sensor.id)]?.cpu_percent != null" title="Uso de CPU">
                            ⚙️ {{ Number(liveSensorStatus[String(sensor.id)]?.cpu_percent || 0).toFixed(1) }}%
                          </span>
                          <span class="metric-item" v-if="liveSensorStatus[String(sensor.id)]?.memory_percent != null" title="Uso de RAM">
                            🧠 {{ Number(liveSensorStatus[String(sensor.id)]?.memory_percent || 0).toFixed(1) }}%
                          </span>
                          <span class="metric-item" v-if="liveSensorStatus[String(sensor.id)]?.temperature != null" title="Temperatura">
                            🌡️ {{ liveSensorStatus[String(sensor.id)]?.temperature }}°C
                          </span>
                          <span class="metric-item" v-if="liveSensorStatus[String(sensor.id)]?.voltage != null" title="Voltaje">
                            ⚡ {{ Number(liveSensorStatus[String(sensor.id)]?.voltage || 0).toFixed(1) }}V
                          </span>
                          <span class="metric-item" v-if="liveSensorStatus[String(sensor.id)]?.uptime_seconds != null" title="Tiempo de Actividad">
                            ⏱️ {{ formatUptimeShort(liveSensorStatus[String(sensor.id)]?.uptime_seconds) }}
                          </span>
                        </template>
                      </div>
                    </div>
                  </div>
                </div>

                <div
                  v-else
                  class="card-body collapsed-summary"
                  :class="{ 
                    'has-critical': liveMonitorAlerts[monitor.monitor_id] === 'critical',
                    'has-warning': liveMonitorAlerts[monitor.monitor_id] === 'warning'
                  }"
                >
                  <span v-if="liveMonitorAlerts[monitor.monitor_id] === 'critical'" class="summary-alert">🔴 Atención Requerida</span>
                  <span v-else-if="liveMonitorAlerts[monitor.monitor_id] === 'warning'" class="summary-warning">🟡 Advertencia</span>
                  <span v-else class="summary-ok">✓ Sistema Operativo</span>
                </div>
              </div>
            </div>
          </template>
        </draggable>
      </div>
    </main>

    <div v-if="showGroupModal" class="modal-overlay" @click.self="showGroupModal = false">
      <div class="modal-content small">
        <h3>Crear Nuevo Grupo</h3>
        <input v-model="newGroupName" placeholder="Nombre del Grupo" class="full-width-input" />
        <div class="modal-actions">
          <button class="btn-secondary" @click="showGroupModal = false">Cancelar</button>
          <button class="btn-primary" @click="addNewGroup">Crear</button>
        </div>
      </div>
    </div>

    <div v-if="monitorToEdit" class="modal-overlay" @click.self="monitorToEdit = null">
      <div class="modal-content small">
        <h3>Herramientas del Dispositivo</h3>
        <p class="modal-subtitle">
          {{ monitorToEdit.client_name }} ({{ monitorToEdit.ip_address }})
        </p>

        <div class="tools-grid">
          <button class="tool-btn" @click="openTerminal">
            <span class="tool-icon">›_</span>
            <span class="tool-text">Terminal SSH</span>
          </button>
          
          <button class="tool-btn" @click="openCommentsModal">
            <span class="tool-icon">📝</span>
            <span class="tool-text">Bitácora</span>
          </button>

          <button class="tool-btn danger" @click="requestReboot" :disabled="isRebooting">
            <span class="tool-icon">🔄</span>
            <span class="tool-text">{{ isRebooting ? 'Reiniciando...' : 'Reiniciar Equipo' }}</span>
          </button>

          <button class="tool-btn warning" @click="triggerRotateCredentials">
            <span class="tool-icon">🔑</span>
            <span class="tool-text">Rotar Credenciales</span>
          </button>
        </div>

        <div class="dashboard-config-section">
          <label>Mover a Grupo del Dashboard:</label>
          <select v-model="editMonitorGroup" class="full-width-input mt-2">
            <option v-for="g in availableGroups" :key="g" :value="g">{{ g }}</option>
            <option value="Sin Grupo">Sin Grupo</option>
          </select>
        </div>

        <div class="modal-actions">
          <button class="btn-secondary" @click="monitorToEdit = null">Cancelar</button>
          <button class="btn-primary" @click="saveMonitorSettings">Guardar Grupo</button>
        </div>
      </div>
    </div>

    <div v-if="showRotateCredentialsModal" class="modal-overlay" @click.self="showRotateCredentialsModal = false">
      <div class="modal-content small">
        <div class="modal-header-alert">
          <span class="alert-icon-large">🔑</span>
          <h3>Rotar Credenciales</h3>
        </div>
        <p class="modal-subtitle" style="text-align: center; margin-bottom: 1.5rem;">
          Se cambiará el usuario y/o contraseña en el equipo físico y se actualizará el perfil.
        </p>
        
        <form @submit.prevent="submitRotateCredentials" class="vertical-form">
          <div class="form-group">
            <label>Nuevo Usuario (Opcional)</label>
            <input type="text" v-model="rotateCredentialsForm.newUsername" placeholder="Dejar en blanco para mantener actual" />
          </div>

          <div class="form-group">
            <label>Nueva Contraseña</label>
            <input type="password" v-model="rotateCredentialsForm.newPassword" required placeholder="Ingresa la nueva clave" />
          </div>
          
          <div class="form-group">
            <label>Confirmar Contraseña</label>
            <input type="password" v-model="rotateCredentialsForm.confirmPassword" required placeholder="Repite la clave" />
          </div>

          <div class="form-group" style="margin-top: 1rem; border-top: 1px dashed #555; padding-top: 1rem;">
            <label>Nombre del Nuevo Perfil de Credencial</label>
            <input type="text" v-model="rotateCredentialsForm.credentialName" required />
            <small style="color: #888; font-size: 0.75rem; margin-top: 0.2rem;">Este perfil se guardará en la base de datos para no perder el acceso.</small>
          </div>

          <div class="modal-actions" style="margin-top: 2rem;">
            <button type="button" class="btn-secondary" @click="showRotateCredentialsModal = false" :disabled="isRotatingCredentials">Cancelar</button>
            <button type="submit" class="btn-warning" :disabled="isRotatingCredentials">
              {{ isRotatingCredentials ? 'Cambiando...' : 'Aplicar Cambio' }}
            </button>
          </div>
        </form>
      </div>
    </div>

    <div v-if="showCommentsModal" class="modal-overlay" @click.self="showCommentsModal = false">
      <div class="modal-content" style="max-width: 500px;">
        <h3>Bitácora del Dispositivo</h3>
        <p class="modal-subtitle">{{ monitorToEdit?.client_name }}</p>

        <div class="comments-container">
          <div v-if="deviceComments.length === 0" class="no-comments">
            No hay registros en la bitácora.
          </div>
          <div v-else class="comments-list">
            <div v-for="comment in deviceComments" :key="comment.id" class="comment-item">
              <div class="comment-header">
                <span class="comment-date">{{ formatDate(comment.created_at) }}</span>
              </div>
              <div class="comment-body">{{ comment.content }}</div>
            </div>
          </div>
        </div>

        <form @submit.prevent="addComment" class="comment-form">
          <textarea 
            v-model="newCommentContent" 
            placeholder="Escribe un nuevo registro..." 
            rows="3" 
            required
            class="full-width-input"
          ></textarea>
          <div class="modal-actions">
            <button type="button" class="btn-secondary" @click="showCommentsModal = false">Cerrar</button>
            <button type="submit" class="btn-primary" :disabled="isAddingComment">
              {{ isAddingComment ? 'Guardando...' : 'Agregar Registro' }}
            </button>
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

    <div v-if="sensorDetailsToShow" class="modal-overlay" @click.self="closeSensorDetails">
      <div class="modal-content">
        <h3>Editar: {{ sensorDetailsToShow.name }}</h3>

        <form @submit.prevent="handleUpdateSensor" class="config-form-wrapper">
          <div class="sub-section span-3">
            <h4>Estado del Sensor</h4>
            <div class="general-config-grid">
              <div class="form-group checkbox-group">
                <input
                  type="checkbox"
                  v-model="(sensorDetailsToShow.sensor_type === 'ping' ? newPingSensor : sensorDetailsToShow.sensor_type === 'ethernet' ? newEthernetSensor : sensorDetailsToShow.sensor_type === 'wireless' ? newWirelessSensor : newSystemSensor).is_active"
                  id="gAct"
                />
                <label for="gAct">Encendido (Monitorear)</label>
              </div>
              <div class="form-group checkbox-group">
                <input
                  type="checkbox"
                  v-model="(sensorDetailsToShow.sensor_type === 'ping' ? newPingSensor : sensorDetailsToShow.sensor_type === 'ethernet' ? newEthernetSensor : sensorDetailsToShow.sensor_type === 'wireless' ? newWirelessSensor : newSystemSensor).alerts_paused"
                  id="gPau"
                />
                <label for="gPau">Pausar Alertas de este Sensor</label>
              </div>
            </div>
          </div>

          <SensorConfigurator
            v-if="sensorDetailsToShow.sensor_type === 'ping'"
            v-model="newPingSensor"
            sensor-type="ping"
            :channels="channelsList"
            :auto-tasks="autoTasks"
            :suggested-target-devices="suggestedTargetDevicesForEdit"
            :has-parent-maestro="hasParentMaestro"
          />

          <SensorConfigurator
            v-else-if="sensorDetailsToShow.sensor_type === 'ethernet'"
            v-model="newEthernetSensor"
            sensor-type="ethernet"
            :channels="channelsList"
            :auto-tasks="autoTasks"
            :device-interfaces="deviceInterfaces"
            :is-loading-interfaces="isLoadingInterfaces"
          />

          <SensorConfigurator
            v-else-if="sensorDetailsToShow.sensor_type === 'wireless'"
            v-model="newWirelessSensor"
            sensor-type="wireless"
            :channels="channelsList"
            :auto-tasks="autoTasks"
            :device-interfaces="deviceInterfaces"
            :is-loading-interfaces="isLoadingInterfaces"
          />

          <SensorConfigurator
            v-else-if="sensorDetailsToShow.sensor_type === 'system'"
            v-model="newSystemSensor"
            sensor-type="system"
            :channels="channelsList"
            :auto-tasks="autoTasks"
          />

          <div class="modal-actions span-3">
            <button type="button" class="btn-secondary" @click="closeSensorDetails">Cancelar</button>
            <button type="submit" class="btn-add">Guardar Cambios</button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* =========================================
   LAYOUT & SIDEBAR (USANDO VARIABLES DE TEMA)
   ========================================= */
.layout-container {
  display: flex;
  height: 100vh;
  background: var(--bg-color);
  color: #eee;
  overflow: hidden;
}

/* Sidebar */
.sidebar {
  width: 250px;
  background: var(--surface-color);
  border-right: 1px solid var(--primary-color);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  transition: width 0.3s ease;
}
.sidebar.sidebar-collapsed {
  width: 60px;
}

.sidebar-header {
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 1rem;
  border-bottom: 1px solid var(--primary-color);
}
.sidebar-header h3 {
  margin: 0;
  font-size: 1rem;
  color: #fff;
  white-space: nowrap;
  overflow: hidden;
}
.btn-toggle-sidebar {
  background: none;
  border: 1px solid var(--primary-color);
  color: #aaa;
  cursor: pointer;
  padding: 2px 6px;
  border-radius: 4px;
}

.sidebar-actions {
  padding: 1rem;
  border-bottom: 1px solid var(--primary-color);
}
.btn-add-group {
  width: 100%;
  background: var(--blue);
  color: white;
  border: none;
  padding: 0.5rem;
  border-radius: 4px;
  cursor: pointer;
  font-weight: bold;
}

.group-list {
  list-style: none;
  padding: 0;
  margin: 0;
  overflow-y: auto;
  flex-grow: 1;
}
.group-list li {
  padding: 0.8rem 1rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 10px;
  border-left: 3px solid transparent;
  transition: background 0.2s;
  height: 50px;
}
.group-list li:hover {
  background: rgba(255, 255, 255, 0.05);
}
.group-list li.active {
  background: rgba(255, 255, 255, 0.1);
  border-left-color: var(--blue);
}

.group-name {
  flex-grow: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  font-size: 0.9rem;
}
.badge {
  background: var(--bg-color);
  padding: 2px 6px;
  border-radius: 10px;
  font-size: 0.75rem;
  color: #aaa;
  border: 1px solid var(--primary-color);
}

/* ESTADOS DE LOS DOTS LATERALES */
.status-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  display: block;
  flex-shrink: 0;
  transition: background-color 0.3s, box-shadow 0.3s;
}
.dot-green {
  background-color: var(--green);
  box-shadow: 0 0 5px var(--green);
}
.dot-warning {
  background-color: #fbbf24;
  box-shadow: 0 0 5px #fbbf24;
}
.dot-red {
  background-color: var(--secondary-color);
  box-shadow: 0 0 5px var(--secondary-color);
}

/* MAIN CONTENT */
.main-content {
  flex-grow: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  position: relative;
}
.content-header {
  height: 60px;
  padding: 0 2rem;
  border-bottom: 1px solid var(--primary-color);
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-shrink: 0;
  background: var(--surface-color);
}
.content-header h2 {
  margin: 0;
  font-size: 1.4rem;
  color: white;
}

/* NUEVAS CLASES PARA EL HEADER ACTIONS (BOTONERA) */
.header-actions {
  display: flex;
  align-items: center;
  gap: 1.5rem;
}
.view-controls {
  display: flex;
  gap: 0.2rem;
  background: var(--bg-color);
  padding: 0.2rem;
  border-radius: 6px;
  border: 1px solid var(--primary-color);
}

.audio-btn {
  font-weight: bold;
  padding: 4px 10px !important;
  color: #eee;
}
.audio-btn.is-muted {
  color: #888;
  opacity: 0.6;
}

.btn-primary {
  background: var(--blue);
  color: white;
  border: none;
  padding: 0.5rem 1rem;
  border-radius: 4px;
  text-decoration: none;
  font-weight: bold;
}
.empty-selection {
  flex-grow: 1;
  display: flex;
  justify-content: center;
  align-items: center;
  color: #666;
  font-size: 1.2rem;
}

/* --- FASE 5: BANNER DE SILENCIO GLOBAL --- */
.global-mute-banner {
  background-color: rgba(251, 191, 36, 0.15);
  color: #fbbf24;
  padding: 0.6rem 2rem;
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 1rem;
  border-bottom: 1px solid rgba(251, 191, 36, 0.3);
  font-size: 0.95rem;
  z-index: 10;
  flex-shrink: 0;
}
.global-mute-banner strong {
  color: #fcd34d;
}
.mute-time {
  background: rgba(0,0,0,0.3);
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 0.85rem;
  border: 1px solid rgba(251, 191, 36, 0.2);
}

/* =========================================
   GRID & TARJETAS
   ========================================= */
.scroll-area {
  flex-grow: 1;
  overflow-y: auto;
  padding: 2rem;
}
.dashboard-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
  gap: 1.5rem;
  grid-auto-rows: 10px; 
  align-items: start; 
}

.monitor-card-wrapper {
  transition: grid-row-end 0.2s ease;
}

.monitor-card {
  background-color: var(--surface-color);
  border: 1px solid var(--primary-color);
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  transition: all 0.2s;
  position: relative; /* Asegura el contexto de posicionamiento para Kebab */
}

/* Redondeamos internas para compensar falta de overflow:hidden */
.card-header {
  border-top-left-radius: 7px;
  border-top-right-radius: 7px;
}
.card-body.collapsed-summary {
  border-bottom-left-radius: 7px;
  border-bottom-right-radius: 7px;
}

/* ANIMACIONES NOC (PULSO DE ALARMA) */
@keyframes pulse-critical {
  0% { box-shadow: 0 0 0 0 rgba(255, 107, 107, 0.7); border-color: var(--secondary-color); }
  70% { box-shadow: 0 0 0 10px rgba(255, 107, 107, 0); border-color: var(--secondary-color); }
  100% { box-shadow: 0 0 0 0 rgba(255, 107, 107, 0); border-color: var(--secondary-color); }
}

@keyframes pulse-warning {
  0% { box-shadow: 0 0 0 0 rgba(251, 191, 36, 0.7); border-color: #fbbf24; }
  70% { box-shadow: 0 0 0 10px rgba(251, 191, 36, 0); border-color: #fbbf24; }
  100% { box-shadow: 0 0 0 0 rgba(251, 191, 36, 0); border-color: #fbbf24; }
}

/* ESTADOS DE GRAVEDAD PARA LA TARJETA */
.monitor-card.status-critical:not(.is-acknowledged) {
  animation: pulse-critical 2s infinite;
}
.monitor-card.status-warning:not(.is-acknowledged) {
  animation: pulse-warning 2s infinite;
}

/* ESTADOS ACKNOWLEDGED (Dejan de parpadear pero mantienen color estático) */
.monitor-card.status-critical.is-acknowledged {
  border-color: var(--secondary-color);
  box-shadow: 0 0 5px rgba(255, 107, 107, 0.3);
}
.monitor-card.status-warning.is-acknowledged {
  border-color: #fbbf24;
  box-shadow: 0 0 5px rgba(251, 191, 36, 0.2);
}

.monitor-card.is-inactive {
  opacity: 0.7;
  border-style: dashed;
}

.card-header {
  background: var(--primary-color);
  padding: 0.6rem 1rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
  cursor: grab;
}
.header-left {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  overflow: hidden;
}
.drag-handle {
  color: rgba(255, 255, 255, 0.5);
  cursor: grab;
  font-size: 1.2rem;
  margin-right: 5px;
}
.title-container h3 {
  margin: 0;
  font-size: 1rem;
  color: #fff;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  display: flex;
  align-items: center;
}
.off-badge {
  background: #444;
  font-size: 0.7rem;
  padding: 1px 4px;
  border-radius: 3px;
  margin-left: 5px;
}
.pause-badge {
  font-size: 0.9rem;
  margin-left: 5px;
}

.card-actions-right {
  display: flex;
  align-items: center;
  gap: 4px;
}
.device-ip {
  font-size: 0.8rem;
  color: #ccc;
  margin-right: 8px;
}
.action-icon-btn {
  background: none;
  border: none;
  font-size: 1.1rem;
  color: #ccc;
  cursor: pointer;
  padding: 4px;
  border-radius: 4px;
}
.action-icon-btn:hover {
  color: #fff;
  background: rgba(255, 255, 255, 0.1);
}

/* BOTÓN ACKNOWLEDGE */
@keyframes shake {
  0% { transform: rotate(0deg); }
  25% { transform: rotate(15deg); }
  50% { transform: rotate(0deg); }
  75% { transform: rotate(-15deg); }
  100% { transform: rotate(0deg); }
}
.ack-btn:not(.is-acked) {
  color: var(--blue);
  animation: shake 0.5s ease-in-out infinite;
  display: inline-block;
}
.ack-btn.is-acked {
  opacity: 0.5;
  animation: none;
}

.active-orange {
  color: #fbbf24;
  opacity: 1;
}
.active-red {
  color: #ff6b6b;
  opacity: 1;
}
.remove-btn {
  color: #ccc;
  font-size: 1.4rem;
  background: none;
  border: none;
  cursor: pointer;
  margin-left: 5px;
}

.card-body {
  padding: 0.8rem;
  flex-grow: 1;
}

/* =========================================
   SENSORES & KEBAB MENU
   ========================================= */
.sensors-container {
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}

.sensor-row {
  display: flex;
  flex-direction: column;
  gap: 8px;
  background: var(--bg-color);
  padding: 0.6rem 0.8rem;
  border-radius: 6px;
  border-left: 3px solid transparent;
  cursor: default;
  transition: background 0.2s;
}
.sensor-row:hover {
  background: rgba(255, 255, 255, 0.05);
}
.sensor-row.row-paused {
  border-left-color: #fbbf24;
}
.sensor-row.row-inactive {
  opacity: 0.5;
}

.sensor-tier-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  cursor: pointer;
}

.sensor-name {
  font-size: 0.95rem;
  color: #eee;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 1;
  min-width: 0;
}

.sensor-top-right {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}

.sensor-main-status {
  font-size: 0.85rem;
  font-family: monospace;
  font-weight: bold;
  display: flex;
  align-items: center;
  gap: 5px;
}
.text-off {
  color: #666;
  font-weight: bold;
  font-size: 0.8rem;
}

/* NUEVO: ESTILOS DEL MENÚ KEBAB */
.kebab-container {
  position: relative;
  display: inline-block;
}

.kebab-btn {
  background: none;
  border: none;
  color: #888;
  font-size: 1.4rem;
  cursor: pointer;
  padding: 0 5px;
  border-radius: 4px;
  line-height: 1;
  transition: color 0.2s, background 0.2s;
}

.kebab-btn:hover {
  color: #fff;
  background: rgba(255, 255, 255, 0.1);
}

.kebab-dropdown {
  position: absolute;
  top: 100%;
  right: 0;
  background-color: var(--surface-color);
  border: 1px solid var(--primary-color);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.5);
  border-radius: 6px;
  min-width: 180px;
  z-index: 9999; /* Z-index altísimo para superar a la grilla y otras tarjetas */
  display: flex;
  flex-direction: column;
  padding: 0.4rem 0;
  margin-top: 5px;
}

.kebab-item {
  background: none;
  border: none;
  color: #ddd;
  padding: 0.6rem 1rem;
  text-align: left;
  font-size: 0.85rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 8px;
  transition: background 0.2s, color 0.2s;
}

.kebab-item:hover {
  background-color: rgba(255, 255, 255, 0.05);
  color: #fff;
}

.text-danger {
  color: #ff6b6b;
}
.text-danger:hover {
  background-color: rgba(255, 107, 107, 0.1) !important;
  color: #ff6b6b;
}


/* NIVEL INFERIOR: Caja de Métricas */
.sensor-tier-bottom {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
  background: rgba(0, 0, 0, 0.2);
  padding: 6px 10px;
  border-radius: 4px;
  border-left: 2px solid rgba(255, 255, 255, 0.1);
}

.metric-item {
  font-size: 0.75rem;
  color: #aaa;
  display: flex;
  align-items: center;
  gap: 5px;
  white-space: nowrap;
}
.metric-item.speed {
  color: #ccc;
  font-weight: bold;
}

/* ESTADOS DE COLOR */
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

/* ESTILOS SUMMARY */
.collapsed-summary {
  padding: 0.5rem 1rem;
  background: var(--bg-color);
  font-size: 0.85rem;
  text-align: center;
  color: #888;
}
.collapsed-summary.has-critical {
  background: rgba(255, 107, 107, 0.1);
  color: var(--secondary-color);
  font-weight: bold;
}
.collapsed-summary.has-warning {
  background: rgba(251, 191, 36, 0.1);
  color: #fbbf24;
  font-weight: bold;
}
.summary-ok {
  color: var(--green);
}
.summary-alert {
  color: var(--secondary-color);
}
.summary-warning {
  color: #fbbf24;
}

/* MODALES */
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
  border-radius: 8px;
  width: 90%;
  max-width: 650px;
  max-height: 90vh;
  overflow-y: auto;
}
.modal-content.small {
  max-width: 400px;
}
.modal-subtitle {
  color: #aaa;
  font-size: 0.9rem;
  margin-top: -0.5rem;
  margin-bottom: 1.5rem;
}
.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 1rem;
  margin-top: 1.5rem;
}

/* CLASE DEL FORMULARIO CONFIGURATOR */
.config-form-wrapper {
  padding: 1.5rem;
  background-color: var(--bg-color);
  border-radius: 8px;
  border: 1px solid var(--primary-color);
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}
.general-config-grid {
  display: flex;
  gap: 1.5rem;
  align-items: center;
}

/* HERRAMIENTAS Y BOTONES UNIFICADOS */
.tools-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
  margin-bottom: 2rem;
}

.tool-btn {
  background: var(--bg-color);
  border: 1px solid var(--primary-color);
  border-radius: 8px;
  padding: 1rem;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
  color: white;
  cursor: pointer;
  transition: all 0.2s;
}

.tool-btn:hover:not(:disabled) {
  background: var(--primary-color);
  transform: translateY(-2px);
}

.tool-btn.danger {
  border-color: rgba(255, 107, 107, 0.3);
}
.tool-btn.danger:hover:not(:disabled) {
  background: rgba(255, 107, 107, 0.1);
  border-color: #ff6b6b;
}

.tool-btn.warning {
  border-color: rgba(251, 191, 36, 0.3);
}
.tool-btn.warning:hover:not(:disabled) {
  background: rgba(251, 191, 36, 0.1);
  border-color: #fbbf24;
}

.tool-icon {
  font-size: 1.5rem;
}
.tool-text {
  font-size: 0.85rem;
  font-weight: bold;
}

.dashboard-config-section {
  border-top: 1px dashed #555;
  padding-top: 1.5rem;
}

.modal-header-alert {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  margin-bottom: 0.5rem;
}
.alert-icon-large {
  font-size: 2rem;
}

.vertical-form {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

/* ESTILOS DE BITÁCORA */
.comments-container {
  background: var(--bg-color);
  border: 1px solid var(--primary-color);
  border-radius: 6px;
  height: 250px;
  overflow-y: auto;
  margin-bottom: 1rem;
  padding: 0.5rem;
}
.no-comments {
  color: #666;
  text-align: center;
  padding: 2rem;
  font-style: italic;
}
.comments-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
.comment-item {
  background: rgba(255, 255, 255, 0.03);
  padding: 0.8rem;
  border-radius: 4px;
  border-left: 3px solid var(--blue);
}
.comment-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 0.3rem;
  font-size: 0.75rem;
  color: #888;
}
.comment-body {
  font-size: 0.9rem;
  line-height: 1.4;
  white-space: pre-wrap;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}
.form-group label {
  font-weight: bold;
  color: #888;
  font-size: 0.8rem;
}
.form-group input,
.form-group select {
  padding: 0.6rem;
  background: var(--bg-color);
  border: 1px solid var(--primary-color);
  border-radius: 4px;
  color: white;
  width: 100%;
}
.full-width-input {
  width: 100%;
  padding: 0.8rem;
  background: var(--bg-color);
  border: 1px solid var(--primary-color);
  border-radius: 4px;
  color: white;
  font-family: inherit;
}
.sub-section {
  grid-column: span 3;
  background: var(--surface-color);
  padding: 1rem;
  border-radius: 6px;
  border: 1px solid var(--primary-color);
  margin-top: 0.5rem;
}
.sub-section h4 {
  margin: 0 0 0.8rem 0;
  border-bottom: 1px solid var(--primary-color);
  padding-bottom: 0.5rem;
  color: #ccc;
}

/* CORRECCIÓN DE ALINEACIÓN DE CHECKBOXES */
.checkbox-group {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 0.5rem;
}
.checkbox-group input[type='checkbox'] {
  width: auto;
  margin: 0;
  accent-color: var(--blue);
}

.text-green {
  color: var(--green);
  font-weight: bold;
}
.text-gray {
  color: #666;
  font-weight: bold;
}
.text-orange {
  color: #fbbf24;
  font-weight: bold;
}
.btn-secondary {
  background: var(--primary-color);
  color: white;
  border: none;
  padding: 0.6rem 1.2rem;
  border-radius: 6px;
  cursor: pointer;
}
.btn-danger {
  background: var(--secondary-color);
  color: white;
  border: none;
  padding: 0.6rem 1.2rem;
  border-radius: 6px;
  cursor: pointer;
}
.btn-warning {
  background: #f59e0b;
  color: #111;
  border: none;
  padding: 0.6rem 1.2rem;
  border-radius: 6px;
  cursor: pointer;
  font-weight: bold;
}
.btn-warning:hover:not(:disabled) {
  background: #fbbf24;
}
.btn-add {
  background-color: var(--blue);
  color: white;
  border: none;
  padding: 0.6rem 1.2rem;
  border-radius: 6px;
  cursor: pointer;
  font-weight: bold;
}
.btn-danger-outline {
  width: 100%;
  background: transparent;
  color: #ff6b6b;
  border: 1px solid #ff6b6b;
  padding: 0.8rem;
  border-radius: 6px;
  cursor: pointer;
  font-weight: bold;
  transition: all 0.2s;
}
.btn-danger-outline:hover:not(:disabled) {
  background: #ff6b6b;
  color: white;
}
.btn-danger-outline:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.notification {
  position: fixed;
  top: 20px;
  right: 20px;
  padding: 1rem 1.5rem;
  border-radius: 4px;
  z-index: 3000;
  color: white;
  font-weight: bold;
}
.notification.success {
  background: var(--green);
}
.notification.error {
  background: var(--secondary-color);
}
</style>