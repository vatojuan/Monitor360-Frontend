<script setup>
import { ref, onMounted, onUnmounted, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import api from '@/lib/api'
import { connectWebSocketWhenAuthenticated, getCurrentWebSocket } from '@/lib/ws'
import { waitForSession } from '@/lib/supabase'
import draggable from 'vuedraggable'
import SensorConfigurator from '@/components/SensorConfigurator.vue' // <-- NUEVO: Importamos la fuente de la verdad

const router = useRouter()

// --- ESTADO PRINCIPAL ---
const allMonitors = ref([])
const groupedMonitors = ref({})
const activeGroup = ref(null)
const isSidebarCollapsed = ref(false)

// Estado de grupos sincronizado con DB
const dbGroups = ref([])

// Estado Reactivo de Sensores
const liveSensorStatus = ref({})
// Caché Reactivo de Alertas de Monitores (Para no recalcular en HTML)
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

// Estado para Rotación de Credenciales
const showRotateCredentialsModal = ref(false)
const rotateCredentialsForm = ref({ newUsername: '', newPassword: '', confirmPassword: '', credentialName: '' })
const isRotatingCredentials = ref(false)

// Estado para Bitácora
const showCommentsModal = ref(false)
const deviceComments = ref([])
const newCommentContent = ref('')
const isAddingComment = ref(false)

// --- Nuevo Estado para Componente Universal ---
const allDevicesList = ref([])
const autoTasks = ref([])
const deviceInterfaces = ref([])
const isLoadingInterfaces = ref(false)

// --- COMPUTADOS ---
const hasParentMaestro = computed(() => !!currentMonitorContext.value?.maestro_id)
const channelsById = ref({})
const channelsList = computed(() => Object.values(channelsById.value))

// Ordenamos los grupos disponibles para los selectores
const availableGroups = computed(() => [...dbGroups.value].sort())

// --- COMPUTADO: Dispositivos Sugeridos para Edición (Filtrado Inteligente) ---
const suggestedTargetDevicesForEdit = computed(() => {
  if (!currentMonitorContext.value) return []

  // 1. Identificar el contexto de red del monitor actual
  let currentVpnId = currentMonitorContext.value.vpn_profile_id

  // Si tiene maestro, usamos el perfil del maestro
  if (currentMonitorContext.value.maestro_id) {
    const maestro = allDevicesList.value.find(
      (d) => d.id === currentMonitorContext.value.maestro_id,
    )
    if (maestro) {
      currentVpnId = maestro.vpn_profile_id
    }
  }

  // 2. Filtrar dispositivos que compartan ese contexto
  return allDevicesList.value.filter((d) => {
    // Excluirse a sí mismo
    if (d.id === currentMonitorContext.value.device_id) return false

    // Si no detectamos VPN, mostramos todos (fallback)
    if (!currentVpnId) return true

    // Si el destino es un maestro, chequear su VPN directa
    if (d.is_maestro) {
      return d.vpn_profile_id === currentVpnId
    }

    // Si el destino es un esclavo, chequear la VPN de SU maestro
    if (d.maestro_id) {
      const destMaestro = allDevicesList.value.find((m) => m.id === d.maestro_id)
      return destMaestro && destMaestro.vpn_profile_id === currentVpnId
    }

    // Si tiene VPN directa asignada
    return d.vpn_profile_id === currentVpnId
  })
})

// --- FORMULARIOS BASE ---
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
  ui_alert_timeout: {
    enabled: false,
    channel_id: null,
    cooldown_minutes: 5,
    tolerance_count: 1,
    notify_recovery: false,
    use_custom_message: false,
    custom_message: '',
    use_custom_recovery_message: false,
    custom_recovery_message: '',
    use_auto_task: false,
    trigger_task_id: null,
  },
  ui_alert_latency: {
    enabled: false,
    threshold_ms: 200,
    channel_id: null,
    cooldown_minutes: 5,
    tolerance_count: 1,
    notify_recovery: false,
    use_custom_message: false,
    custom_message: '',
    use_custom_recovery_message: false,
    custom_recovery_message: '',
    use_auto_task: false,
    trigger_task_id: null,
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
    notify_recovery: false,
    use_custom_message: false,
    custom_message: '',
    use_custom_recovery_message: false,
    custom_recovery_message: '',
    use_auto_task: false,
    trigger_task_id: null,
  },
  ui_alert_traffic: {
    enabled: false,
    threshold_mbps: 100,
    direction: 'any',
    channel_id: null,
    cooldown_minutes: 5,
    tolerance_count: 1,
    notify_recovery: false,
    use_custom_message: false,
    custom_message: '',
    use_custom_recovery_message: false,
    custom_recovery_message: '',
    use_auto_task: false,
    trigger_task_id: null,
  },
})

const createNewWirelessSensor = () => ({
  name: '',
  is_active: true,
  alerts_paused: false,
  config: {
    interface_name: '',
    interval_sec: 60,
    thresholds: {
      min_signal_dbm: -80,
      min_ccq_percent: 75,
      min_client_count: 0,
      min_tx_rate_mbps: 0,
      min_rx_rate_mbps: 0,
    },
    tolerance_checks: 3,
  },
  ui_alert_status: {
    enabled: false,
    channel_id: null,
    cooldown_minutes: 10,
    notify_recovery: true,
    use_custom_message: false,
    custom_message: '',
    use_custom_recovery_message: false,
    custom_recovery_message: '',
    use_auto_task: false,
    trigger_task_id: null,
  },
})

const createNewSystemSensor = () => ({
  name: '',
  is_active: true,
  alerts_paused: false,
  config: {
    interval_sec: 60,
    thresholds: {
      max_cpu_percent: 85,
      max_memory_percent: 90,
      max_temperature: 75,
      min_voltage: null,
      max_voltage: null,
      restart_uptime_seconds: 300,
    },
    tolerance_checks: 3,
  },
  ui_alert_status: {
    enabled: false,
    channel_id: null,
    cooldown_minutes: 10,
    notify_recovery: true,
    use_custom_message: false,
    custom_message: '',
    use_custom_recovery_message: false,
    custom_recovery_message: '',
    use_auto_task: false,
    trigger_task_id: null,
  },
})

const newPingSensor = ref(createNewPingSensor())
const newEthernetSensor = ref(createNewEthernetSensor())
const newWirelessSensor = ref(createNewWirelessSensor())
const newSystemSensor = ref(createNewSystemSensor())

// --- API FETCHERS ---
async function fetchGroups() {
  try {
    const { data } = await api.get('/groups')
    dbGroups.value = data.map((g) => g.name)
  } catch (err) {
    console.error('Error fetching groups:', err)
  }
}

async function fetchAllMonitors() {
  try {
    const { data } = await api.get('/monitors')
    allMonitors.value = Array.isArray(data) ? data : []

    const initialStatus = {}
    const initialAlerts = {}

    allMonitors.value.forEach((m) => {
      if (m.is_active === null || m.is_active === undefined) m.is_active = true
      if (m.alerts_paused === null || m.alerts_paused === undefined) m.alerts_paused = false
      
      let hasAlert = false
      ;(m.sensors || []).forEach((s) => {
        const sid = String(s.id)
        if (!liveSensorStatus.value[sid]) initialStatus[sid] = { status: 'pending' }
        else initialStatus[sid] = liveSensorStatus.value[sid]

        if (['timeout', 'error', 'high_latency', 'link_down', 'degraded', 'critical'].includes(initialStatus[sid].status)) {
            hasAlert = true
        }
      })
      if (m.is_active === false) hasAlert = false
      initialAlerts[m.monitor_id] = hasAlert
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

// --- LOGICA DE GRUPOS ---
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
  for (const m of monitors) {
    if (!m.is_active) continue
    if (liveMonitorAlerts.value[m.monitor_id]) {
      return 'dot-red'
    }
  }
  return 'dot-green'
}

// --- D&D ---
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

// --- UTILIDADES ---
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
}
function formatDate(dateString) {
  if (!dateString) return ''
  return new Date(dateString).toLocaleString()
}

// --- WEBSOCKETS OPTIMIZADOS (BUFFERING) ---
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
function trySubscribeSensors() {
  const ws = getCurrentWebSocket()
  if (!ws || ws.readyState !== 1) return
  const ids = currentSensorIds()
  if (ids.length > 0) ws.send(JSON.stringify({ type: 'subscribe_sensors', sensor_ids: ids }))
}
watch(() => allMonitors.value, trySubscribeSensors, { deep: true })

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

// BUZÓN TEMPORAL
let pendingWsUpdates = {}
let wsBufferTimer = null

function flushWsUpdates() {
  if (Object.keys(pendingWsUpdates).length === 0) return
  
  // 1. Actualización Atómica de Sensores (Cero estrés a Vue)
  liveSensorStatus.value = { ...liveSensorStatus.value, ...pendingWsUpdates }

  // 2. Pre-Cálculo de Alertas Globales (Para no hacerlo en HTML)
  const newAlerts = { ...liveMonitorAlerts.value }
  
  // Mapeamos los IDs de sensores actualizados para saber qué monitores recalcular
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

  // Recalculamos SOLO los monitores que sufrieron cambios
  affectedMonitorIds.forEach(mid => {
      const m = allMonitors.value.find(x => x.monitor_id === mid)
      if (!m || m.is_active === false) {
          newAlerts[mid] = false
          return
      }
      let hasAlert = false
      if (m.sensors && m.sensors.length) {
          hasAlert = m.sensors.some(s => {
              const st = liveSensorStatus.value[String(s.id)]?.status
              return ['timeout', 'error', 'high_latency', 'link_down', 'degraded', 'critical'].includes(st)
          })
      }
      newAlerts[mid] = hasAlert
  })

  liveMonitorAlerts.value = newAlerts
  pendingWsUpdates = {}
}

function handleRawMessage(evt) {
  try {
    const parsed = JSON.parse(evt.data)
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

// --- LIFECYCLE ---
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

  // Iniciamos el Reloj del Buffer (Vacía la cola cada 500ms)
  wsBufferTimer = setInterval(flushWsUpdates, 500)
})

onUnmounted(() => {
  if (typeof wsOpenUnbind === 'function') wsOpenUnbind()
  if (typeof directMsgUnbind === 'function') directMsgUnbind()
  if (wsBufferTimer) clearInterval(wsBufferTimer)
})

// --- ACCIONES DE TARJETA ---
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
async function toggleMonitorPause(monitor) {
  const newVal = !monitor.alerts_paused
  monitor.alerts_paused = newVal
  try {
    await api.put(`/monitors/${monitor.monitor_id}`, { alerts_paused: newVal })
    showNotification(newVal ? 'Alertas pausadas' : 'Alertas activas')
  } catch {
    monitor.alerts_paused = !newVal
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

async function deleteSensor(sensor, e) {
  e?.stopPropagation()
  if (!confirm(`¿Eliminar sensor "${sensor.name}"?`)) return

  try {
    await api.delete(`/sensors/${sensor.id}`)

    const monitor = allMonitors.value.find((m) => m.monitor_id === sensor.monitor_id)
    if (monitor && monitor.sensors) {
      monitor.sensors = monitor.sensors.filter((s) => s.id !== sensor.id)
      monitor.sensors = [...monitor.sensors]
    }

    if (activeGroup.value && groupedMonitors.value[activeGroup.value]) {
      const groupMonitor = groupedMonitors.value[activeGroup.value].find(
        (m) => m.monitor_id === sensor.monitor_id,
      )
      if (groupMonitor && groupMonitor.sensors) {
        groupMonitor.sensors = groupMonitor.sensors.filter((s) => s.id !== sensor.id)
      }
    }

    showNotification('Sensor eliminado correctamente.', 'success')
  } catch (err) {
    console.error(err)
    showNotification('Error al eliminar sensor.', 'error')
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

// Lógica de Bitácora
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

// Lógica de Rotación de Credenciales
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

// Configuración de Monitor y Reinicio
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

// --- EDICION SENSOR CON SENSORCONFIGURATOR ---
const mapAlert = (alerts, type) => alerts.find((a) => a.type === type) || {}

async function showSensorDetails(s, m, e) {
  e?.stopPropagation()
  await ensureChannelsLoaded()
  
  sensorDetailsToShow.value = s
  currentMonitorContext.value = m
  
  // Si el sensor pertenece a un equipo, cargamos sus interfaces para que el select se pueble
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
        >
          <span :class="['status-dot', getGroupStatusClass(gName)]"></span>
          <span v-if="!isSidebarCollapsed" class="group-name">{{ gName }}</span>
          <span v-if="!isSidebarCollapsed" class="badge">{{ groupedMonitors[gName].length }}</span>
        </li>
      </ul>
    </aside>

    <main class="main-content">
      <header class="content-header" v-if="activeGroup">
        <h2>{{ activeGroup }}</h2>
        <router-link to="/monitor-builder" class="btn-primary">Añadir Dispositivo</router-link>
      </header>
      <div v-else class="empty-selection">
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
            <div
              :class="[
                'monitor-card',
                {
                  'status-alert': liveMonitorAlerts[monitor.monitor_id],
                  'is-inactive': !monitor.is_active,
                  'is-collapsed': collapsedCards.has(monitor.monitor_id),
                },
              ]"
            >
              <div class="card-header" @dblclick="toggleCardCollapse(monitor.monitor_id)">
                <div class="header-left">
                  <span class="drag-handle">::</span>
                  <div class="title-container">
                    <h3>{{ monitor.client_name }}</h3>
                    <div class="badges-row">
                      <span v-if="!monitor.is_active" class="off-badge">OFF</span>
                      <span v-if="monitor.alerts_paused" class="pause-badge">⏸️</span>
                    </div>
                  </div>
                </div>

                <div class="card-actions-right">
                  <span class="device-ip" v-if="!collapsedCards.has(monitor.monitor_id)">
                    {{ monitor.ip_address }}
                  </span>
                  <span v-if="liveMonitorAlerts[monitor.monitor_id]" class="alert-icon">⚠️</span>

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
                    :class="{ 'active-orange': monitor.alerts_paused }"
                    @click="toggleMonitorPause(monitor)"
                    title="Pausar Alertas"
                  >
                    {{ monitor.alerts_paused ? '🔕' : '🔔' }}
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
                      'row-paused': sensor.alerts_paused,
                    }"
                    @click="goToSensorDetail(sensor.id)"
                  >
                    <div class="sensor-tier-top">
                      <span class="sensor-name" :title="sensor.name">
                        {{ sensor.name }}
                        <small v-if="sensor.alerts_paused" title="Alertas Pausadas">⏸️</small>
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

                        <div class="sensor-row-actions">
                          <button
                            class="details-btn"
                            @click="showSensorDetails(sensor, monitor, $event)"
                            title="Editar"
                          >
                            ✎
                          </button>
                          <button
                            class="details-btn delete-btn-sensor"
                            @click="deleteSensor(sensor, $event)"
                            title="Eliminar Sensor"
                          >
                            ✕
                          </button>
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
                :class="{ 'has-alert': liveMonitorAlerts[monitor.monitor_id] }"
              >
                <span v-if="liveMonitorAlerts[monitor.monitor_id]" class="summary-alert"
                  >⚠️ Atención Requerida</span
                >
                <span v-else class="summary-ok">✓ Sistema Operativo</span>
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
.status-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  display: block;
  flex-shrink: 0;
}
.dot-green {
  background-color: var(--green);
  box-shadow: 0 0 5px var(--green);
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
}

.monitor-card {
  background-color: var(--surface-color);
  border: 1px solid var(--primary-color);
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  transition: all 0.2s;
}
.monitor-card.status-alert {
  border-color: var(--secondary-color);
  box-shadow: 0 0 8px rgba(255, 100, 100, 0.2);
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
  padding: 2px;
}
.action-icon-btn:hover {
  color: #fff;
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
   SENSORES: DISEÑO "TWO-TIER" (Dos Niveles)
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
  cursor: pointer;
  transition: background 0.2s;
}
.sensor-row:hover {
  background: rgba(255, 255, 255, 0.05); /* Suave highlight al pasar el ratón */
}
.sensor-row.row-paused {
  border-left-color: #fbbf24;
}
.sensor-row.row-inactive {
  opacity: 0.5;
}

/* NIVEL SUPERIOR: Cabecera del sensor */
.sensor-tier-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
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

/* BOTONES DE ACCIÓN PARA SENSORES */
.sensor-row-actions {
  display: flex;
  gap: 6px;
  margin-left: 4px;
}

.details-btn {
  background: none;
  border: none;
  color: #666;
  font-size: 1.1rem;
  cursor: pointer;
  padding: 2px;
  transition: color 0.2s;
}
.details-btn:hover {
  color: var(--blue);
}

.delete-btn-sensor {
  color: #888;
  font-size: 1.2rem;
  line-height: 1;
}
.delete-btn-sensor:hover {
  color: var(--secondary-color); /* Rojo */
}

/* OTROS ESTILOS */
.collapsed-summary {
  padding: 0.5rem 1rem;
  background: var(--bg-color);
  font-size: 0.85rem;
  text-align: center;
  color: #888;
}
.collapsed-summary.has-alert {
  background: rgba(255, 107, 107, 0.1);
  color: var(--secondary-color);
  font-weight: bold;
}
.summary-ok {
  color: var(--green);
}
.summary-alert {
  color: var(--secondary-color);
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