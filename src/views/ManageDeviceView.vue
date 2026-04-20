<script setup>
import { ref, onMounted, computed, onUnmounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import api from '@/lib/api'
import SmartTerminalModal from '@/components/SmartTerminalModal.vue'
import SensorConfigurator from '@/components/SensorConfigurator.vue' // <-- NUEVA FUENTE DE LA VERDAD
import * as XLSX from 'xlsx' // <-- DEPENDENCIA PARA LEER EXCEL

const router = useRouter()

// ===== UI Estado general =====
const currentTab = ref('manage') // 'manage' | 'add' | 'tasks'
const notification = ref({ show: false, message: '', type: 'success' })

// --- MODAL DE ERROR DE AUTENTICACIÓN ---
const showAuthErrorModal = ref(false)
const authErrorMessage = ref('')

// --- MODAL DE LÍMITES DE FACTURACIÓN ---
const showLimitModal = ref(false)
const limitMessage = ref('')

function showNotification(message, type = 'success') {
  notification.value = { show: true, message, type }
  setTimeout(() => (notification.value.show = false), 4000)
}

function goToBilling() {
  showLimitModal.value = false
  router.push('/billing')
}

// ===== Alta en un paso (ACTUALIZADO DUAL-CHECK) =====
const addForm = ref({
  client_name: '',
  ip_address: '',
  api_port: 8728,
  ssh_port: 22, // <-- NUEVO: Soporte DUAL-CHECK
  mac_address: '',
  node: '',
  connection_method: 'vpn',
  vpn_profile_id: null,
  credential_id: null,
  maestro_id: null,
  vendor: 'Mikrotik', // Default
})
const isSubmitting = ref(false)
const isTesting = ref(false)
const testResult = ref(null)

// ===== Listados =====
const allDevices = ref([])
const vpnProfiles = ref([])
const credentialProfiles = ref([])
const channels = ref([])
const autoTasks = ref([]) // <-- NUEVO PARA AUTO-REMEDIACIÓN
const isLoadingDevices = ref(false)
const deletingId = ref(null)

// --- Nuevo Estado para Selector de IP Destino (Masivo) ---
const allDevicesList = ref([])

// ===== ESTADO FILTROS INVENTARIO =====
const inventoryFilter = ref({
  search: '',
  vendor: '',
  role: 'all' // 'all', 'maestro', 'managed', 'generic'
})

// ===== ESTADO ACCIONES MASIVAS =====
const selectedDevices = ref([])
const showBulkModal = ref(false)
const isBulking = ref(false)
const isDeletingBulk = ref(false)

// ===== ESTADO ACTUALIZACIÓN MASIVA EXCEL (RENAME) =====
const showBulkRenameModal = ref(false)
const isUploadingExcel = ref(false)
const isSubmittingBulkRename = ref(false)
const bulkRenameData = ref([])
const bulkRenameHeaders = ref([])
const bulkRenamePreview = ref([])

const bulkRenameForm = ref({
  vpn_profile_id: null,
  ip_column: '',
  name_column: ''
})

// Estado del Modal Masivo
const bulkSensorType = ref('ping')
const bulkNameTemplate = ref('{{hostname}} - Sensor')

// Modelos de configuración COMPLETO
const createNewPingSensor = () => ({
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
  is_active: true,
  alerts_paused: false,
})

const createNewEthernetSensor = () => ({
  config: {
    interface_name: '',
    interval_sec: 30,
  },
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
  is_active: true,
  alerts_paused: false,
})

const createNewWirelessSensor = () => ({
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
  is_active: true,
  alerts_paused: false,
})

const createNewSystemSensor = () => ({
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
  is_active: true,
  alerts_paused: false,
})

const bulkPingConfig = ref(createNewPingSensor())
const bulkEthernetConfig = ref(createNewEthernetSensor())
const bulkWirelessConfig = ref(createNewWirelessSensor())
const bulkSystemConfig = ref(createNewSystemSensor())

// ===== BITÁCORA =====
const showCommentsModal = ref(false)
const activeDeviceForComments = ref(null)
const deviceComments = ref([])
const newComment = ref('')
const isLoadingComments = ref(false)
const isSendingComment = ref(false)

async function openCommentsModal(device) {
  activeDeviceForComments.value = device
  showCommentsModal.value = true
  newComment.value = ''
  activeDropdown.value = null // Cierra el menú si está abierto
  await loadComments(device.id)
}

async function loadComments(deviceId) {
  isLoadingComments.value = true
  try {
    const { data } = await api.get(`/devices/${deviceId}/comments`)
    deviceComments.value = data
  } catch (error) {
    console.error(error)
    showNotification('Error cargando bitácora', 'error')
  } finally {
    isLoadingComments.value = false
  }
}

async function submitComment() {
  if (!newComment.value.trim()) return
  isSendingComment.value = true
  try {
    await api.post(`/devices/${activeDeviceForComments.value.id}/comments`, {
      content: newComment.value,
    })
    newComment.value = ''
    await loadComments(activeDeviceForComments.value.id)
  } catch (error) {
    console.error(error)
    showNotification('Error guardando nota', 'error')
  } finally {
    isSendingComment.value = false
  }
}

function formatDate(isoStr) {
  if (!isoStr) return '-'
  return new Date(isoStr).toLocaleString('es-ES', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

// ===== ESTADO TERMINAL =====
const showTerminalSetupModal = ref(false)
const showTerminalModal = ref(false)
const activeTerminalDevice = ref(null)
const activeTerminalPort = ref(22)

const terminalSetupDevice = ref(null)
const terminalSetupPort = ref(22)

function openTerminalSetup(device) {
  terminalSetupDevice.value = device
  terminalSetupPort.value = device.ssh_port || 22
  showTerminalSetupModal.value = true
  activeDropdown.value = null // Cierra el menú si está abierto
}

function confirmTerminalSetup() {
  activeTerminalDevice.value = terminalSetupDevice.value
  activeTerminalPort.value = terminalSetupPort.value
  showTerminalSetupModal.value = false
  showTerminalModal.value = true
}

function closeTerminal() {
  showTerminalModal.value = false
  activeTerminalDevice.value = null
  fetchAllDevices()
}

// ===== ESTADO ROTAR CREDENCIALES =====
const showRotateCredentialsModal = ref(false)
const activeDeviceForPassword = ref(null)
const rotateCredentialsForm = ref({ newUsername: '', newPassword: '', confirmPassword: '', credentialName: '' })
const isRotatingCredentials = ref(false)

function openRotateCredentialsModal(device) {
  activeDeviceForPassword.value = device
  rotateCredentialsForm.value = {
    newUsername: '',
    newPassword: '',
    confirmPassword: '',
    credentialName: `Cred-${device.client_name}-${new Date().toISOString().split('T')[0]}`
  }
  showRotateCredentialsModal.value = true
  activeDropdown.value = null 
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
    await api.post(`/devices/${activeDeviceForPassword.value.id}/rotate-credentials`, {
      new_username: rotateCredentialsForm.value.newUsername.trim() || null,
      new_password: rotateCredentialsForm.value.newPassword,
      new_credential_name: rotateCredentialsForm.value.credentialName
    })
    
    showNotification('Credenciales rotadas exitosamente', 'success')
    showRotateCredentialsModal.value = false
    activeDeviceForPassword.value = null 
    
    await fetchAllDevices()
    await fetchCredentials()
  } catch (err) {
    showNotification(err.response?.data?.detail || 'Error al rotar credenciales', 'error')
  } finally {
    isRotatingCredentials.value = false
  }
}

// ===== REINICIO =====
const isRebooting = ref(false)

async function requestReboot(device) {
  if (!confirm(`¿Estás seguro de REINICIAR el dispositivo ${device.client_name}?\nSe perderá la conexión temporalmente.`)) {
    return
  }
  
  isRebooting.value = true
  activeDropdown.value = null 
  
  try {
    await api.post(`/devices/${device.id}/reboot`)
    showNotification(`Reiniciando ${device.client_name}...`, 'success')
  } catch (err) {
    console.error(err)
    showNotification(err.response?.data?.detail || 'Error al enviar comando de reinicio.', 'error')
  } finally {
    isRebooting.value = false
  }
}

// ===== GESTIÓN DEL DROPDOWN MENU =====
const activeDropdown = ref(null)

function toggleDropdown(deviceId) {
  if (activeDropdown.value === deviceId) {
    activeDropdown.value = null
  } else {
    activeDropdown.value = deviceId
  }
}

function closeDropdownOnClickOutside(e) {
  if (!e.target.closest('.dropdown-container')) {
    activeDropdown.value = null
  }
}

// ===== TAREAS PROGRAMADAS Y MANUALES (RMM) =====
const scheduledTasks = ref([])
const isLoadingTasks = ref(false)
const showTaskModal = ref(false)
const isCreatingTask = ref(false)

const daysOfWeek = [
  { value: 'mon', label: 'Lu' }, { value: 'tue', label: 'Ma' },
  { value: 'wed', label: 'Mi' }, { value: 'thu', label: 'Ju' },
  { value: 'fri', label: 'Vi' }, { value: 'sat', label: 'Sá' },
  { value: 'sun', label: 'Do' }
]

const newTaskForm = ref({
  name: '',
  trigger_mode: 'cron', // NUEVO: 'cron' o 'manual'
  action_type: 'conditional_reboot',
  min_uptime_days: 30,
  script_body: '',
  time: '03:00',
  days: [] 
})

// === NUEVO ESTADO: CAMBIO DE PUERTOS MASIVO ===
const portChangeConfig = ref({
  ssh: { enabled: false, port: 22, disable: false },
  api: { enabled: false, port: 8728, disable: false },
  winbox: { enabled: false, port: 8291, disable: false },
  www: { enabled: false, port: 80, disable: false },
  telnet: { enabled: false, port: 23, disable: false }
})

// Logs Modal
const showTaskLogsModal = ref(false)
const activeTaskLogs = ref([])
const isLoadingTaskLogs = ref(false)
const activeTaskForLogs = ref(null)
const isClearingLogs = ref(false)

// Lazy load para tareas
watch(currentTab, (newTab) => {
  if (newTab === 'tasks' && scheduledTasks.value.length === 0) {
    fetchScheduledTasks()
  }
})

async function fetchScheduledTasks() {
  isLoadingTasks.value = true
  try {
    const { data } = await api.get('/scheduled-tasks') 
    scheduledTasks.value = data
  } catch (error) {
    console.error(error)
    showNotification('Error cargando tareas programadas', 'error')
  } finally {
    isLoadingTasks.value = false
  }
}

function openTaskModal() {
  if (selectedDevices.value.length === 0) return
  newTaskForm.value = {
    name: '',
    trigger_mode: 'cron',
    action_type: 'conditional_reboot',
    min_uptime_days: 30,
    script_body: '',
    time: '03:00',
    days: []
  }
  
  // Reiniciamos estado de puertos
  portChangeConfig.value = {
    ssh: { enabled: false, port: 22, disable: false },
    api: { enabled: false, port: 8728, disable: false },
    winbox: { enabled: false, port: 8291, disable: false },
    www: { enabled: false, port: 80, disable: false },
    telnet: { enabled: false, port: 23, disable: false }
  }

  showTaskModal.value = true
}

function toggleDaySelection(dayValue) {
  if (newTaskForm.value.days.includes(dayValue)) {
    newTaskForm.value.days = newTaskForm.value.days.filter(d => d !== dayValue)
  } else {
    newTaskForm.value.days.push(dayValue)
  }
}

async function submitScheduledTask() {
  if (!newTaskForm.value.name.trim()) return showNotification('El nombre de la tarea es obligatorio', 'error')

  const payload = {
    name: newTaskForm.value.name,
    action_type: newTaskForm.value.action_type,
    action_payload: {},
    schedule_config: {
      trigger_mode: newTaskForm.value.trigger_mode,
      time: newTaskForm.value.trigger_mode === 'cron' ? newTaskForm.value.time : null,
      days: newTaskForm.value.trigger_mode === 'cron' ? newTaskForm.value.days : []
    },
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
    target_device_ids: selectedDevices.value
  }

  if (newTaskForm.value.action_type === 'conditional_reboot') {
    payload.action_payload.min_uptime_days = newTaskForm.value.min_uptime_days
  } else if (newTaskForm.value.action_type === 'custom_script') {
    if (!newTaskForm.value.script_body.trim()) return showNotification('El script no puede estar vacío', 'error')
    payload.action_payload.script_body = newTaskForm.value.script_body
  } else if (newTaskForm.value.action_type === 'change_ports') {
    // --- Lógica del Payload de Puertos ---
    const portsPayload = {}
    let anySelected = false
    
    for (const key in portChangeConfig.value) {
      const conf = portChangeConfig.value[key]
      if (conf.enabled) {
        portsPayload[key] = conf.disable ? 0 : (conf.port || null)
        anySelected = true
      } else {
        portsPayload[key] = null
      }
    }
    
    if (!anySelected) {
      return showNotification('Debes seleccionar al menos un servicio para cambiar o deshabilitar.', 'error')
    }
    payload.action_payload = portsPayload
  }

  isCreatingTask.value = true
  try {
    const { data } = await api.post('/scheduled-tasks', payload) 
    showNotification(`Tarea creada exitosamente. (Asignada a ${data.assigned_devices} equipos)`, 'success')
    showTaskModal.value = false
    selectedDevices.value = []
    
    currentTab.value = 'tasks'
    await fetchScheduledTasks()
  } catch (error) {
    console.error(error)
    showNotification(error.response?.data?.detail || 'Error al crear la tarea programada', 'error')
  } finally {
    isCreatingTask.value = false
  }
}

async function toggleTaskState(task) {
  try {
    const res = await api.patch(`/scheduled-tasks/${task.id}/toggle`, { is_active: !task.is_active })
    task.is_active = res.data.is_active
    showNotification(task.is_active ? 'Tarea reanudada' : 'Tarea pausada', 'success')
  } catch(e) {
    showNotification('Error al cambiar el estado de la tarea', 'error')
  }
}

async function deleteScheduledTask(task) {
  if (!confirm(`¿Estás seguro de eliminar la tarea "${task.name}" y todo su historial de ejecuciones?`)) return
  try {
    await api.delete(`/scheduled-tasks/${task.id}`)
    showNotification('Tarea programada eliminada', 'success')
    await fetchScheduledTasks()
  } catch(e) {
    showNotification('Error al eliminar tarea', 'error')
  }
}

// === EJECUCIÓN MANUAL Y LOGS ===
async function runTaskNow(task) {
  if (!confirm(`¿Deseas iniciar la ejecución de "${task.name}" ahora mismo en todos sus equipos asignados?`)) return
  try {
    const { data } = await api.post(`/scheduled-tasks/${task.id}/run`)
    showNotification(`Ejecución iniciada en ${data.dispatched_count} equipos. Revisá el historial en unos minutos.`, 'success')
    await fetchScheduledTasks() // Para actualizar la fecha de last_run
  } catch(e) {
    showNotification(e.response?.data?.detail || 'Error al iniciar ejecución manual', 'error')
  }
}

async function clearTaskLogs() {
  if (!activeTaskForLogs.value) return
  if (!confirm(`¿Estás seguro de vaciar el historial completo de la tarea "${activeTaskForLogs.value.name}"?`)) return
  
  isClearingLogs.value = true
  try {
    await api.delete(`/scheduled-tasks/${activeTaskForLogs.value.id}/logs`)
    showNotification('Historial limpiado exitosamente', 'success')
    activeTaskLogs.value = [] // Limpiamos la vista en vivo
  } catch(e) {
    showNotification('Error al limpiar historial', 'error')
  } finally {
    isClearingLogs.value = false
  }
}

async function openTaskLogsModal(task) {
  activeTaskForLogs.value = task
  showTaskLogsModal.value = true
  isLoadingTaskLogs.value = true
  try {
    const { data } = await api.get(`/scheduled-tasks/${task.id}/logs`)
    activeTaskLogs.value = data
  } catch(e) {
    showNotification('Error cargando historial de tarea', 'error')
  } finally {
    isLoadingTaskLogs.value = false
  }
}

const taskCompatibility = computed(() => {
  const stats = selectionStats.value
  return {
    compatible: stats.managed,
    skipped: stats.generic,
    isPartial: stats.generic > 0,
    message: stats.generic > 0
        ? `⚠️ Atención: Se programará solo para ${stats.managed} equipos gestionados. Se omitirán ${stats.generic} equipos genéricos.`
        : `✅ Compatible con los ${stats.managed} dispositivos gestionados seleccionados.`,
  }
})

// ===== COMPUTADAS INTELIGENTES Y FILTROS =====

function getDeviceRole(device) {
  if (device.is_maestro) return { label: 'Maestro', class: 'maestro' }
  if (device.credential_id) return { label: 'Gestionado', class: 'managed' }
  return { label: 'Dispositivo', class: 'device' }
}

const maestros = computed(() => allDevices.value.filter((d) => d.is_maestro))

function getVpnName(vpnId) {
  if (!vpnId) return null
  const vpn = vpnProfiles.value.find((v) => v.id === vpnId)
  return vpn ? vpn.name : null
}

function getMaestroById(maestroId) {
  if (!maestroId) return null
  return allDevices.value.find((d) => d.id === maestroId) || null
}

const uniqueVendors = computed(() => {
  const vendors = allDevices.value.map(d => d.vendor || 'Generico')
  return [...new Set(vendors)].sort()
})

const filteredDevices = computed(() => {
  return allDevices.value.filter(d => {
    // 1. Search text
    if (inventoryFilter.value.search) {
      const q = inventoryFilter.value.search.toLowerCase().trim()
      const match = (
        (d.client_name || '').toLowerCase().includes(q) ||
        (d.ip_address || '').toLowerCase().includes(q) ||
        (d.mac_address || '').toLowerCase().includes(q) ||
        (d.identity || '').toLowerCase().includes(q)
      )
      if (!match) return false
    }

    // 2. Vendor
    if (inventoryFilter.value.vendor) {
      const dVendor = d.vendor || 'Generico'
      if (dVendor !== inventoryFilter.value.vendor) return false
    }

    // 3. Role
    if (inventoryFilter.value.role !== 'all') {
      const roleClass = getDeviceRole(d).class
      if (inventoryFilter.value.role === 'maestro' && roleClass !== 'maestro') return false
      if (inventoryFilter.value.role === 'managed' && roleClass !== 'managed') return false
      if (inventoryFilter.value.role === 'generic' && roleClass !== 'device') return false
    }

    return true
  })
})

function onVendorChange() {
  if (addForm.value.vendor === 'Generic') {
    addForm.value.connection_method = 'maestro'
    addForm.value.api_port = null
    addForm.value.ssh_port = null
    addForm.value.credential_id = null
  } else if (addForm.value.vendor === 'Mikrotik') {
    addForm.value.api_port = 8728
    addForm.value.ssh_port = 22
  } else if (addForm.value.vendor === 'Ubiquiti' || addForm.value.vendor === 'Mimosa') {
    addForm.value.api_port = 22 // Legacy API fallback
    addForm.value.ssh_port = 22
  } else if (addForm.value.vendor === 'SNMP') {
    addForm.value.api_port = 161
    addForm.value.ssh_port = null
  } else {
    addForm.value.api_port = 8728
    addForm.value.ssh_port = 22
  }
}

const selectionStats = computed(() => {
  const selected = allDevices.value.filter((d) => selectedDevices.value.includes(d.id))
  const managedCount = selected.filter((d) => d.credential_id || d.is_maestro).length
  const genericCount = selected.length - managedCount

  return {
    total: selected.length,
    managed: managedCount,
    generic: genericCount,
  }
})

const bulkCompatibility = computed(() => {
  const stats = selectionStats.value
  if (bulkSensorType.value === 'ping') {
    return {
      compatible: stats.total,
      skipped: 0,
      isPartial: false,
      message: `✅ Compatible con TODOS los ${stats.total} dispositivos.`,
    }
  } else {
    return {
      compatible: stats.managed,
      skipped: stats.generic,
      isPartial: stats.generic > 0,
      message:
        stats.generic > 0
          ? `⚠️ Atención: Se aplicará solo a ${stats.managed} dispositivos gestionados. Se omitirán ${stats.generic} genéricos.`
          : `✅ Compatible con los ${stats.managed} dispositivos gestionados seleccionados.`,
    }
  }
})

const suggestedTargetDevicesForBulk = computed(() => {
  if (selectedDevices.value.length === 0) return []
  const selectedDevs = allDevicesList.value.filter((d) => selectedDevices.value.includes(d.id))
  const involvedVpnIds = new Set()

  selectedDevs.forEach((d) => {
    let vpnId = d.vpn_profile_id
    if (!vpnId && d.maestro_id) {
      const m = allDevicesList.value.find((x) => x.id === d.maestro_id)
      if (m) vpnId = m.vpn_profile_id
    }
    if (vpnId) involvedVpnIds.add(vpnId)
  })

  if (involvedVpnIds.size === 0) return allDevicesList.value

  return allDevicesList.value.filter((d) => {
    let dVpnId = d.vpn_profile_id
    if (!dVpnId && d.maestro_id) {
      const m = allDevicesList.value.find((x) => x.id === d.maestro_id)
      if (m) dVpnId = m.vpn_profile_id
    }
    return dVpnId && involvedVpnIds.has(dVpnId)
  })
})

// ===== FUNCIONES ACTUALIZACIÓN MASIVA NOMBRES (NUEVO) =====

function isValidIP(ipString) {
  if (!ipString) return false;
  let s = String(ipString).trim();
  if (s.includes(':') && s.split(':').length === 2 && !isNaN(s.split(':')[1])) {
    s = s.split(':')[0];
  }
  if (s.includes('/')) {
    s = s.split('/')[0];
  }
  const ipv4Regex = /^(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$/;
  return ipv4Regex.test(s);
}

function openBulkRenameModal() {
  showBulkRenameModal.value = true
  bulkRenameData.value = []
  bulkRenameHeaders.value = []
  bulkRenamePreview.value = []
  bulkRenameForm.value = { vpn_profile_id: null, ip_column: '', name_column: '' }
  const fileInput = document.getElementById('excelFileInput')
  if (fileInput) fileInput.value = ''
}

function closeBulkRenameModal() {
  showBulkRenameModal.value = false
  bulkRenameData.value = []
  bulkRenameHeaders.value = []
  bulkRenamePreview.value = []
}

async function handleFileUpload(event) {
  const file = event.target.files[0]
  if (!file) return

  isUploadingExcel.value = true
  try {
    const data = await file.arrayBuffer()
    const workbook = XLSX.read(data)
    const firstSheetName = workbook.SheetNames[0]
    const worksheet = workbook.Sheets[firstSheetName]
    
    const jsonData = XLSX.utils.sheet_to_json(worksheet, { defval: '' })
    
    if (jsonData.length > 0) {
      bulkRenameData.value = jsonData
      bulkRenameHeaders.value = Object.keys(jsonData[0])
      
      const lowerHeaders = bulkRenameHeaders.value.map(h => h.toLowerCase())
      
      const ipMatchIndex = lowerHeaders.findIndex(h => h.includes('ip') || h === 'direccion' || h === 'address')
      if (ipMatchIndex !== -1) bulkRenameForm.value.ip_column = bulkRenameHeaders.value[ipMatchIndex]

      const nameMatchIndex = lowerHeaders.findIndex(h => h.includes('nombre') || h.includes('name') || h.includes('cliente'))
      if (nameMatchIndex !== -1) bulkRenameForm.value.name_column = bulkRenameHeaders.value[nameMatchIndex]
      
      updateBulkRenamePreview()
    } else {
      showNotification('El archivo Excel parece estar vacío.', 'warning')
    }
  } catch (error) {
    console.error('Error leyendo Excel:', error)
    showNotification('Error al procesar el archivo. Asegúrate de que sea un Excel válido.', 'error')
  } finally {
    isUploadingExcel.value = false
  }
}

function updateBulkRenamePreview() {
  if (!bulkRenameForm.value.ip_column || !bulkRenameForm.value.name_column) {
    bulkRenamePreview.value = []
    return
  }
  
  bulkRenamePreview.value = bulkRenameData.value
    .map(row => ({
      ip_address: String(row[bulkRenameForm.value.ip_column]).trim(),
      new_client_name: String(row[bulkRenameForm.value.name_column]).trim()
    }))
    .filter(item => item.ip_address && item.new_client_name && isValidIP(item.ip_address)) 
    .slice(0, 5) 
}

watch([() => bulkRenameForm.value.ip_column, () => bulkRenameForm.value.name_column], () => {
  updateBulkRenamePreview()
})

async function submitBulkRename() {
  if (!bulkRenameForm.value.ip_column || !bulkRenameForm.value.name_column) {
    return showNotification('Debes seleccionar las columnas de IP y Nombre.', 'error')
  }

  let ignoredCount = 0;

  const finalDevicesList = bulkRenameData.value
    .map(row => ({
      ip_address: String(row[bulkRenameForm.value.ip_column] || '').trim(),
      new_client_name: String(row[bulkRenameForm.value.name_column] || '').trim()
    }))
    .filter(item => {
      if (!item.ip_address || !item.new_client_name) return false;
      if (!isValidIP(item.ip_address)) {
        ignoredCount++;
        return false;
      }
      return true;
    })

  if (finalDevicesList.length === 0) {
    return showNotification('No se encontraron registros válidos (IPs válidas) para enviar.', 'error')
  }

  isSubmittingBulkRename.value = true
  try {
    const payload = {
      vpn_profile_id: bulkRenameForm.value.vpn_profile_id,
      devices: finalDevicesList
    }

    const { data } = await api.post('/devices/bulk-rename', payload)
    
    let successMsg = data.message || 'Proceso encolado correctamente.';
    if (ignoredCount > 0) {
      successMsg += ` (Se ignoraron ${ignoredCount} filas con IPs inválidas o en blanco).`;
    }
    
    showNotification(successMsg, ignoredCount > 0 ? 'warning' : 'success')
    closeBulkRenameModal()
  } catch (error) {
    console.error('Error al enviar actualización masiva:', error)
    
    if (error.response?.status === 422 && Array.isArray(error.response?.data?.detail)) {
      const pydanticError = error.response.data.detail[0];
      const errorField = pydanticError.loc ? pydanticError.loc[pydanticError.loc.length - 1] : 'desconocido';
      const locIdx = pydanticError.loc && pydanticError.loc.length > 2 ? pydanticError.loc[2] : '';
      const rowInfo = locIdx !== '' ? ` en la fila ${typeof locIdx === 'number' ? locIdx + 1 : locIdx}` : '';
      
      showNotification(`Error de formato${rowInfo}. Campo "${errorField}": ${pydanticError.msg}`, 'error');
    } else {
      showNotification(error.response?.data?.detail || 'Error al iniciar actualización masiva.', 'error')
    }
  } finally {
    isSubmittingBulkRename.value = false
  }
}

const handleRenameComplete = (event) => {
  const payload = event?.detail;

  if (payload && typeof payload.success_count !== 'undefined') {
      let msg = `Renombramiento listo: ${payload.success_count} exitosos.`;
      if (payload.not_found_count > 0) {
          msg += ` (${payload.not_found_count} IPs no encontradas)`;
      }
      showNotification(msg, payload.success_count > 0 ? 'success' : 'warning');
  } else {
      showNotification('Proceso de renombramiento finalizado.', 'success');
  }

  fetchAllDevices()
}

const handleDeviceDeleted = (event) => {
  const { device_id } = event?.detail || {}
  if (!device_id) return
  allDevices.value = allDevices.value.filter(d => d.id !== device_id)
  allDevicesList.value = allDevicesList.value.filter(d => d.id !== device_id)
  selectedDevices.value = selectedDevices.value.filter(id => id !== device_id)
}

const handleBulkDeleteCompleted = (event) => {
  const { device_ids } = event?.detail || {}
  if (!Array.isArray(device_ids) || device_ids.length === 0) return
  const deleted = new Set(device_ids)
  allDevices.value = allDevices.value.filter(d => !deleted.has(d.id))
  allDevicesList.value = allDevicesList.value.filter(d => !deleted.has(d.id))
  selectedDevices.value = selectedDevices.value.filter(id => !deleted.has(id))
}

// ===== CARGA DE DATOS =====
async function fetchAllDevices() {
  isLoadingDevices.value = true
  try {
    const { data } = await api.get('/devices')
    allDevices.value = Array.isArray(data) ? data : []
    allDevicesList.value = allDevices.value

    const currentIds = allDevices.value.map((d) => d.id)
    selectedDevices.value = selectedDevices.value.filter((id) => currentIds.includes(id))
  } catch (error) {
    console.error('Error al cargar dispositivos:', error)
    showNotification(error.response?.data?.detail || 'Error al cargar dispositivos.', 'error')
  } finally {
    isLoadingDevices.value = false
  }
}

async function fetchVpnProfiles() {
  try {
    const { data } = await api.get('/vpns')
    vpnProfiles.value = Array.isArray(data) ? data : []
  } catch (error) {
    console.error(error)
  }
}

async function fetchCredentials() {
  try {
    const { data } = await api.get('/credentials')
    credentialProfiles.value = Array.isArray(data) ? data : []
  } catch (error) {
    console.error(error)
  }
}

async function fetchChannels() {
  try {
    const { data } = await api.get('/channels')
    channels.value = data || []
  } catch (error) {
    console.error(error)
  }
}

async function fetchAutoTasks() {
  try {
    const { data } = await api.get('/scheduled-tasks') 
    autoTasks.value = data || []
  } catch (error) {
    console.error(error)
  }
}

// ===== FUNCIONES ALTA =====
async function handleAddDeviceOneStep(forceGeneric = false) {
  const isForced = typeof forceGeneric === 'boolean' ? forceGeneric : false

  if (!addForm.value.client_name?.trim() || !addForm.value.ip_address?.trim()) {
    return showNotification('Completá Cliente e IP.', 'error')
  }
  if (addForm.value.connection_method === 'vpn' && !addForm.value.vpn_profile_id) {
    return showNotification('Seleccioná un Perfil VPN.', 'error')
  }
  if (addForm.value.connection_method === 'maestro' && !addForm.value.maestro_id) {
    return showNotification('Seleccioná un Maestro.', 'error')
  }

  let finalVpnId = null;
  if (addForm.value.connection_method === 'vpn') {
    finalVpnId = addForm.value.vpn_profile_id;
  } else if (addForm.value.connection_method === 'maestro' && addForm.value.maestro_id) {
    const selectedMaestro = maestros.value.find(m => m.id === addForm.value.maestro_id);
    if (selectedMaestro) finalVpnId = selectedMaestro.vpn_profile_id;
  }

  const payload = {
    client_name: addForm.value.client_name,
    ip_address: addForm.value.ip_address,
    api_port: Number(addForm.value.api_port) || 8728,
    ssh_port: Number(addForm.value.ssh_port) || null,
    mac_address: addForm.value.mac_address || '',
    node: addForm.value.node || '',
    maestro_id: addForm.value.connection_method === 'maestro' ? addForm.value.maestro_id : null,
    vpn_profile_id: finalVpnId,
    credential_id: addForm.value.credential_id,
    vendor: addForm.value.vendor,
    force_generic_ping: isForced,
  }

  isSubmitting.value = true
  if (isForced) showAuthErrorModal.value = false

  try {
    const { data } = await api.post('/devices/manual', payload)

    const successMsg = isForced
      ? `Dispositivo "${data.client_name}" agregado como Genérico (Solo Ping).`
      : `Dispositivo "${data.client_name}" gestionado correctamente.`

    showNotification(successMsg, 'success')
    resetAddForm()
    fetchAllDevices()
    currentTab.value = 'manage'
  } catch (error) {
    console.error('Error creando dispositivo:', error)
    const detail = error.response?.data?.detail || ''
    
    if (error?.response?.status === 403 || error?.response?.status === 402) {
      limitMessage.value = detail || 'Has alcanzado el límite de dispositivos de tu plan actual.'
      showLimitModal.value = true
    } 
    else if (detail.includes('AUTH_FAILED') && !isForced) {
      authErrorMessage.value = detail.replace('AUTH_FAILED: ', '')
      showAuthErrorModal.value = true
    } else {
      showNotification(detail || 'Error al añadir dispositivo.', 'error')
    }
  } finally {
    isSubmitting.value = false
  }
}

async function handleTestReachability() {
  if (!addForm.value.ip_address?.trim()) return showNotification('Ingresá la IP.', 'error')
  
  const payload = {
    ip_address: addForm.value.ip_address,
    api_port: Number(addForm.value.api_port) || 8728,
    ssh_port: Number(addForm.value.ssh_port) || null,
    vendor: addForm.value.vendor,
  }
  
  if (addForm.value.connection_method === 'vpn') {
    payload.vpn_profile_id = addForm.value.vpn_profile_id
  } else if (addForm.value.connection_method === 'maestro') {
    payload.maestro_id = addForm.value.maestro_id
    const selectedMaestro = maestros.value.find(m => m.id === addForm.value.maestro_id);
    if (selectedMaestro && selectedMaestro.vpn_profile_id) {
      payload.vpn_profile_id = selectedMaestro.vpn_profile_id;
    }
  }

  isTesting.value = true
  testResult.value = null
  try {
    const { data } = await api.post('/devices/test_reachability', payload)
    testResult.value = data
    if (data.reachable) {
        showNotification('¡Conexión OK!', 'success')
        if (data.api_port) addForm.value.api_port = data.api_port
        if (data.ssh_port) addForm.value.ssh_port = data.ssh_port
    }
    else showNotification(data.detail || 'No alcanzable.', 'error')
  } catch (error) {
    console.error(error)
    showNotification('Error al probar conexión.', 'error')
    testResult.value = { reachable: false }
  } finally {
    isTesting.value = false
  }
}

function resetAddForm() {
  addForm.value = {
    client_name: '',
    ip_address: '',
    api_port: 8728,
    ssh_port: 22,
    mac_address: '',
    node: '',
    connection_method: 'vpn',
    vpn_profile_id: null,
    credential_id: null,
    maestro_id: null,
    vendor: 'Mikrotik',
  }
  testResult.value = null
}

// ===== FUNCIONES GESTIÓN =====
async function promoteToMaestro(device) {
  if (!confirm(`¿Promover a "${device.client_name}" como Maestro?`)) return
  try {
    await api.put(`/devices/${device.id}/promote`, {})
    device.is_maestro = true
    showNotification('Promovido a Maestro.', 'success')
  } catch (error) {
    console.error(error)
    showNotification('Error al promover.', 'error')
  }
}

async function handleVpnAssociation(device) {
  try {
    await api.put(`/devices/${device.id}/associate_vpn`, {
      vpn_profile_id: device.vpn_profile_id || null,
    })
    showNotification('VPN actualizada.', 'success')
  } catch (error) {
    console.error(error)
    showNotification('Error al actualizar VPN.', 'error')
  }
}

async function deleteDevice(device) {
  activeDropdown.value = null
  if (!confirm(`¿Eliminar "${device.client_name}"?`)) return

  try {
    deletingId.value = device.id
    await api.delete(`/devices/${device.id}`)
    // Eliminar del estado local tras confirmar 204
    allDevices.value = allDevices.value.filter(d => d.id !== device.id)
    allDevicesList.value = [...allDevices.value]
    selectedDevices.value = selectedDevices.value.filter(id => id !== device.id)
    showNotification('Eliminado.', 'success')
  } catch (error) {
    console.error(error)
    showNotification('Error al eliminar.', 'error')
  } finally {
    deletingId.value = null
  }
}

// ===== LÓGICA DE SELECCIÓN Y MASIVAS =====
function toggleSelection(id) {
  if (selectedDevices.value.includes(id)) {
    selectedDevices.value = selectedDevices.value.filter((d) => d !== id)
  } else {
    selectedDevices.value.push(id)
  }
}

function selectAll() {
  const visibleIds = filteredDevices.value.map(d => d.id)
  const allVisibleSelected = visibleIds.every(id => selectedDevices.value.includes(id))

  if (allVisibleSelected) {
    selectedDevices.value = selectedDevices.value.filter(id => !visibleIds.includes(id))
  } else {
    const newSelections = visibleIds.filter(id => !selectedDevices.value.includes(id))
    selectedDevices.value.push(...newSelections)
  }
}

// ---- Borrado Masivo ----
async function handleBulkDelete() {
  if (selectedDevices.value.length === 0) return
  if (
    !confirm(
      `⚠️ ¿Estás seguro de eliminar PERMANENTEMENTE ${selectedDevices.value.length} dispositivos y todo su historial?`,
    )
  )
    return

  isDeletingBulk.value = true
  try {
    const idsToDelete = [...selectedDevices.value]
    await api.post('/devices/bulk-delete', { device_ids: idsToDelete })

    // Eliminar del estado local tras confirmar respuesta del servidor
    const deletedSet = new Set(idsToDelete)
    allDevices.value = allDevices.value.filter(d => !deletedSet.has(d.id))
    allDevicesList.value = [...allDevices.value]
    selectedDevices.value = []
    showNotification(`${idsToDelete.length} dispositivos eliminados.`, 'success')
  } catch (error) {
    console.error(error)
    showNotification('Error en borrado masivo.', 'error')
  } finally {
    isDeletingBulk.value = false
  }
}

// ---- Modal Creación Masiva Monitores ----
function openBulkModal() {
  if (selectedDevices.value.length === 0) return
  bulkPingConfig.value = createNewPingSensor()
  bulkEthernetConfig.value = createNewEthernetSensor()
  bulkWirelessConfig.value = createNewWirelessSensor()
  bulkSystemConfig.value = createNewSystemSensor()
  bulkNameTemplate.value = '{{hostname}} - Sensor'
  showBulkModal.value = true
}

function buildSensorConfig(type, data) {
  const finalConfig = { ...data.config }
  finalConfig.alerts = []
  const num = (v, f) => (typeof v === 'number' && !isNaN(v) ? v : f)

  if (type === 'ping') {
    finalConfig.ping_type = 'device_to_external'
    if (!finalConfig.target_ip) finalConfig.target_ip = '8.8.8.8'

    if (data.ui_alert_timeout?.enabled) {
      const a = data.ui_alert_timeout
      if (a.channel_id) {
        const alertObj = {
          type: 'timeout',
          channel_id: a.channel_id,
          cooldown_minutes: num(a.cooldown_minutes, 5),
          tolerance_count: Math.max(1, num(a.tolerance_count, 1)),
          notify_recovery: !!a.notify_recovery,
        }
        if (a.use_custom_message && a.custom_message?.trim()) alertObj.custom_message = a.custom_message.trim()
        if (a.use_custom_recovery_message && a.custom_recovery_message?.trim()) alertObj.custom_recovery_message = a.custom_recovery_message.trim()
        if (a.use_auto_task && a.trigger_task_id) alertObj.trigger_task_id = a.trigger_task_id
        finalConfig.alerts.push(alertObj)
      }
    }
    if (data.ui_alert_latency?.enabled) {
      const a = data.ui_alert_latency
      if (a.channel_id) {
        const alertObj = {
          type: 'high_latency',
          threshold_ms: num(a.threshold_ms, 200),
          channel_id: a.channel_id,
          cooldown_minutes: num(a.cooldown_minutes, 5),
          tolerance_count: Math.max(1, num(a.tolerance_count, 1)),
          notify_recovery: !!a.notify_recovery,
        }
        if (a.use_custom_message && a.custom_message?.trim()) alertObj.custom_message = a.custom_message.trim()
        if (a.use_custom_recovery_message && a.custom_recovery_message?.trim()) alertObj.custom_recovery_message = a.custom_recovery_message.trim()
        if (a.use_auto_task && a.trigger_task_id) alertObj.trigger_task_id = a.trigger_task_id
        finalConfig.alerts.push(alertObj)
      }
    }
  } else if (type === 'ethernet') {
    if (data.ui_alert_speed_change?.enabled) {
      const a = data.ui_alert_speed_change
      if (a.channel_id) {
        const alertObj = {
          type: 'speed_change',
          channel_id: a.channel_id,
          cooldown_minutes: num(a.cooldown_minutes, 10),
          tolerance_count: Math.max(1, num(a.tolerance_count, 1)),
          notify_recovery: !!a.notify_recovery,
        }
        if (a.use_custom_message && a.custom_message?.trim()) alertObj.custom_message = a.custom_message.trim()
        if (a.use_custom_recovery_message && a.custom_recovery_message?.trim()) alertObj.custom_recovery_message = a.custom_recovery_message.trim()
        if (a.use_auto_task && a.trigger_task_id) alertObj.trigger_task_id = a.trigger_task_id
        finalConfig.alerts.push(alertObj)
      }
    }
    if (data.ui_alert_traffic?.enabled) {
      const a = data.ui_alert_traffic
      if (a.channel_id) {
        const alertObj = {
          type: 'traffic_threshold',
          threshold_mbps: num(a.threshold_mbps, 100),
          direction: a.direction || 'any',
          channel_id: a.channel_id,
          cooldown_minutes: num(a.cooldown_minutes, 5),
          tolerance_count: Math.max(1, num(a.tolerance_count, 1)),
          notify_recovery: !!a.notify_recovery,
        }
        if (a.use_custom_message && a.custom_message?.trim()) alertObj.custom_message = a.custom_message.trim()
        if (a.use_custom_recovery_message && a.custom_recovery_message?.trim()) alertObj.custom_recovery_message = a.custom_recovery_message.trim()
        if (a.use_auto_task && a.trigger_task_id) alertObj.trigger_task_id = a.trigger_task_id
        finalConfig.alerts.push(alertObj)
      }
    }
  } else if (type === 'wireless') {
    finalConfig.thresholds = {
      min_signal_dbm: num(data.config.thresholds?.min_signal_dbm, -80),
      min_ccq_percent: num(data.config.thresholds?.min_ccq_percent, 75),
      min_client_count: num(data.config.thresholds?.min_client_count, 0),
      min_tx_rate_mbps: num(data.config.thresholds?.min_tx_rate_mbps, 0),
      min_rx_rate_mbps: num(data.config.thresholds?.min_rx_rate_mbps, 0),
    }
    finalConfig.tolerance_checks = Math.max(1, num(data.config.tolerance_checks, 3))

    if (data.ui_alert_status?.enabled) {
      const a = data.ui_alert_status
      if (a.channel_id) {
        const alertObj = {
          type: 'wireless_status',
          channel_id: a.channel_id,
          cooldown_minutes: num(a.cooldown_minutes, 10),
          notify_recovery: !!a.notify_recovery,
        }
        if (a.use_custom_message && a.custom_message?.trim()) alertObj.custom_message = a.custom_message.trim()
        if (a.use_custom_recovery_message && a.custom_recovery_message?.trim()) alertObj.custom_recovery_message = a.custom_recovery_message.trim()
        if (a.use_auto_task && a.trigger_task_id) alertObj.trigger_task_id = a.trigger_task_id
        finalConfig.alerts.push(alertObj)
      }
    }
  } else if (type === 'system') {
    finalConfig.thresholds = {
      max_cpu_percent: num(data.config.thresholds?.max_cpu_percent, null),
      max_memory_percent: num(data.config.thresholds?.max_memory_percent, null),
      max_temperature: num(data.config.thresholds?.max_temperature, null),
      min_voltage: num(data.config.thresholds?.min_voltage, null),
      max_voltage: num(data.config.thresholds?.max_voltage, null),
      restart_uptime_seconds: num(data.config.thresholds?.restart_uptime_seconds, 300),
    }
    finalConfig.tolerance_checks = Math.max(1, num(data.config.tolerance_checks, 3))

    if (data.ui_alert_status?.enabled) {
      const a = data.ui_alert_status
      if (a.channel_id) {
        const alertObj = {
          type: 'system_status',
          channel_id: a.channel_id,
          cooldown_minutes: num(a.cooldown_minutes, 10),
          notify_recovery: !!a.notify_recovery,
        }
        if (a.use_custom_message && a.custom_message?.trim()) alertObj.custom_message = a.custom_message.trim()
        if (a.use_custom_recovery_message && a.custom_recovery_message?.trim()) alertObj.custom_recovery_message = a.custom_recovery_message.trim()
        if (a.use_auto_task && a.trigger_task_id) alertObj.trigger_task_id = a.trigger_task_id
        finalConfig.alerts.push(alertObj)
      }
    }
  }

  return {
    sensor_type: type,
    name_template: bulkNameTemplate.value,
    config: finalConfig,
    is_active: data.is_active,
    alerts_paused: data.alerts_paused,
  }
}

async function submitBulkMonitors() {
  if (!bulkNameTemplate.value) return showNotification('Define una plantilla de nombre', 'error')

  const sourceData =
    bulkSensorType.value === 'ping' ? bulkPingConfig.value :
    bulkSensorType.value === 'ethernet' ? bulkEthernetConfig.value :
    bulkSensorType.value === 'wireless' ? bulkWirelessConfig.value :
    bulkSystemConfig.value
    
  const sensorConfigPayload = buildSensorConfig(bulkSensorType.value, sourceData)

  isBulking.value = true
  try {
    const payload = {
      device_ids: selectedDevices.value,
      sensor_config: sensorConfigPayload,
    }

    const { data } = await api.post('/monitors/bulk', payload)

    let msg = `Creados: ${data.created}`
    if (data.skipped > 0) msg += ` | Omitidos: ${data.skipped} (No compatibles)`

    showNotification(msg, data.skipped > 0 ? 'warning' : 'success')
    showBulkModal.value = false
    selectedDevices.value = []
  } catch (error) {
    console.error('Error creando monitores masivos:', error)
    showNotification('Error al crear monitores masivos.', 'error')
  } finally {
    isBulking.value = false
  }
}

// ===== Lifecycle =====
onMounted(() => {
  document.addEventListener('click', closeDropdownOnClickOutside)
  window.addEventListener('bulk_rename_completed', handleRenameComplete)
  window.addEventListener('device_deleted', handleDeviceDeleted)
  window.addEventListener('bulk_delete_completed', handleBulkDeleteCompleted)
  fetchAllDevices()
  fetchVpnProfiles()
  fetchCredentials()
  fetchChannels()
  fetchAutoTasks()
})

onUnmounted(() => {
  document.removeEventListener('click', closeDropdownOnClickOutside)
  window.removeEventListener('bulk_rename_completed', handleRenameComplete)
  window.removeEventListener('device_deleted', handleDeviceDeleted)
  window.removeEventListener('bulk_delete_completed', handleBulkDeleteCompleted)
})
</script>

<template>
  <div class="page-wrap">
    <header class="topbar">
      <h1>Dispositivos</h1>
    </header>

    <div class="tabs">
      <button :class="{ active: currentTab === 'manage' }" @click="currentTab = 'manage'">
        Gestionar
      </button>
      <button :class="{ active: currentTab === 'add' }" @click="currentTab = 'add'">Agregar</button>
      <button :class="{ active: currentTab === 'tasks' }" @click="currentTab = 'tasks'">
        Panel de Tareas
      </button>
    </div>

    <section v-if="currentTab === 'add'" class="control-section fade-in">
      <h2><i class="icon">➕</i> Alta de dispositivo</h2>
      <form @submit.prevent="handleAddDeviceOneStep(false)" class="form-layout">
        <div class="grid-2">
          <div>
            <label>Fabricante (Vendor)</label>
            <select v-model="addForm.vendor" @change="onVendorChange">
              <option value="Mikrotik">MikroTik (RouterOS)</option>
              <option value="Ubiquiti">Ubiquiti (AirOS/UniFi)</option>
              <option value="Mimosa">Mimosa</option>
              <option value="Generic">Genérico (Solo Ping)</option>
            </select>
          </div>
          <div>
            <label>Cliente / Nombre *</label>
            <input
              type="text"
              v-model="addForm.client_name"
              placeholder="Nombre del cliente"
              required
            />
          </div>
        </div>

        <div class="grid-2">
          <div>
            <label>Dirección IP *</label>
            <input type="text" v-model="addForm.ip_address" placeholder="192.168.88.1" required />
          </div>
          <div class="ip-port-grid">
            <div v-if="['Mikrotik', 'SNMP'].includes(addForm.vendor)" style="flex: 1;">
              <label>{{ addForm.vendor === 'SNMP' ? 'Puerto SNMP' : 'Puerto API' }}</label>
              <input
                type="number"
                v-model="addForm.api_port"
                :placeholder="addForm.vendor === 'SNMP' ? '161' : '8728'"
                required
              />
            </div>
            <div v-if="['Mikrotik', 'Ubiquiti', 'Mimosa'].includes(addForm.vendor)" style="flex: 1;">
              <label>Puerto SSH</label>
              <input
                type="number"
                v-model="addForm.ssh_port"
                placeholder="22"
                :required="['Mikrotik', 'Ubiquiti', 'Mimosa'].includes(addForm.vendor)"
              />
            </div>
            <div v-if="addForm.vendor === 'Generic'" class="generic-hint">
              <span>📡 Solo Ping — sin API ni SSH</span>
            </div>
          </div>
        </div>

        <div class="grid-2">
          <div v-if="addForm.vendor !== 'Generic'">
            <label>Método de conexión</label>
            <select v-model="addForm.connection_method">
              <option value="vpn">A través de Perfil VPN</option>
              <option value="maestro">A través de Maestro existente</option>
            </select>

            <label style="margin-top: 0.8rem">Perfil de Credenciales</label>
            <select v-model="addForm.credential_id">
              <option :value="null">-- Auto-detectar (Lento) --</option>
              <option v-for="cred in credentialProfiles" :key="cred.id" :value="cred.id">
                {{ cred.name }} ({{ cred.username }})
              </option>
            </select>
          </div>

          <div v-if="addForm.vendor === 'Generic'" class="generic-maestro-info">
            <p>Un dispositivo genérico solo puede monitorearse mediante ping desde un Maestro.</p>
          </div>

          <div v-if="addForm.connection_method === 'vpn' && addForm.vendor !== 'Generic'">
            <label>Perfil VPN</label>
            <select v-model="addForm.vpn_profile_id" required>
              <option :value="null" disabled>-- Selecciona VPN --</option>
              <option v-for="vpn in vpnProfiles" :key="vpn.id" :value="vpn.id">
                {{ vpn.name }}
              </option>
            </select>
          </div>

          <div v-if="addForm.connection_method === 'maestro' || addForm.vendor === 'Generic'">
            <label>Maestro <span v-if="addForm.vendor === 'Generic'" style="color: var(--red);">*</span></label>
            <select v-model="addForm.maestro_id" required>
              <option :value="null" disabled>-- Selecciona Maestro --</option>
              <option v-for="m in maestros" :key="m.id" :value="m.id">{{ m.client_name }}</option>
            </select>
          </div>
        </div>

        <div class="grid-2">
          <div><label>MAC (opcional)</label><input v-model="addForm.mac_address" /></div>
          <div><label>Node (opcional)</label><input v-model="addForm.node" /></div>
        </div>

        <div class="actions-row">
          <button class="btn-primary" type="submit" :disabled="isSubmitting">
            {{ isSubmitting ? 'Creando...' : 'Crear dispositivo' }}
          </button>
          <button
            class="btn-secondary"
            type="button"
            @click="handleTestReachability"
            :disabled="isTesting || (addForm.vendor === 'Generic' && !addForm.maestro_id)"
            :title="addForm.vendor === 'Generic' && !addForm.maestro_id ? 'Seleccioná un Maestro primero' : ''"
          >
            {{ isTesting ? 'Probando...' : (addForm.vendor === 'Generic' ? 'Probar Ping desde Maestro' : 'Probar conexión') }}
          </button>
        </div>

        <div v-if="testResult" class="test-box" :class="testResult.reachable ? 'ok' : 'error'">
          <div style="font-weight: bold;">
            {{ testResult.reachable
              ? (addForm.vendor === 'Generic' ? '✅ Ping OK desde Maestro' : '✅ Alcanzable y Autenticado')
              : '❌ Fallo en la prueba' }}
          </div>
          <div v-if="!testResult.reachable && testResult.detail" class="text-dim" style="margin-top: 5px;">
            {{ testResult.detail }}
          </div>
          <div v-if="testResult.reachable && (testResult.api_port || testResult.ssh_port) && addForm.vendor !== 'Generic'" class="text-dim" style="margin-top: 5px;">
            Puertos confirmados:
            <span v-if="testResult.api_port" style="color: var(--blue);">API ({{testResult.api_port}}) </span>
            <span v-if="testResult.ssh_port" style="color: var(--green);">SSH ({{testResult.ssh_port}})</span>
          </div>
        </div>
      </form>
    </section>

    <section v-if="currentTab === 'manage'" class="control-section fade-in">
      <div class="manage-header">
        <div class="inventory-title-row">
          <h2><i class="icon">👑</i> Inventario</h2>
          <button class="btn-secondary btn-excel-import" @click="openBulkRenameModal">
            📂 Importar Excel (Renombrar)
          </button>
        </div>

        <div v-if="selectedDevices.length > 0" class="bulk-actions-wrapper fade-in">
          <button @click="openTaskModal" class="btn-bulk btn-primary">
            ⏱️ Nueva Acción/Tarea ({{ selectedDevices.length }})
          </button>
          <button @click="openBulkModal" class="btn-bulk btn-info">
            📡 Configurar Monitores ({{ selectedDevices.length }})
          </button>
          <button @click="handleBulkDelete" class="btn-bulk btn-danger" :disabled="isDeletingBulk">
            {{ isDeletingBulk ? 'Eliminando...' : `🗑️ Eliminar (${selectedDevices.length})` }}
          </button>
        </div>
      </div>

      <div class="filter-bar fade-in" v-if="!isLoadingDevices && allDevices.length > 0">
        <div class="search-group">
          <span class="icon">🔍</span>
          <input type="text" v-model="inventoryFilter.search" placeholder="Buscar IP, MAC, Nombre..." class="filter-input" />
        </div>
        
        <div class="filter-controls">
          <select v-model="inventoryFilter.vendor" class="filter-select">
            <option value="">Todo Fabricante</option>
            <option v-for="v in uniqueVendors" :key="v" :value="v">{{ v }}</option>
          </select>

          <div class="toggle-group">
            <button :class="{ active: inventoryFilter.role === 'all' }" @click="inventoryFilter.role = 'all'">Todos</button>
            <button :class="{ active: inventoryFilter.role === 'maestro' }" @click="inventoryFilter.role = 'maestro'">Maestros</button>
            <button :class="{ active: inventoryFilter.role === 'managed' }" @click="inventoryFilter.role = 'managed'">Gestionados</button>
            <button :class="{ active: inventoryFilter.role === 'generic' }" @click="inventoryFilter.role = 'generic'">Genéricos</button>
          </div>
        </div>
      </div>

      <div v-if="isLoadingDevices" class="loading-text">Cargando inventario...</div>

      <div v-else class="table-responsive">
        <table class="device-table">
          <thead>
            <tr>
              <th width="40">
                <input
                  type="checkbox"
                  @change="selectAll"
                  :checked="
                    selectedDevices.length > 0 && filteredDevices.length > 0 && filteredDevices.every(d => selectedDevices.includes(d.id))
                  "
                />
              </th>
              <th>Nombre</th>
              <th>IP Address</th>
              <th>Fabricante</th>
              <th>Rol</th>
              <th>Conexión</th>
              <th style="text-align: right;">Acciones</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="filteredDevices.length === 0">
              <td colspan="7" style="text-align: center; padding: 2.5rem; color: #888; font-style: italic; border: 2px dashed var(--primary-color);">
                🔍 No se encontraron dispositivos con los filtros actuales.
              </td>
            </tr>
            <tr
              v-for="device in filteredDevices"
              :key="device.id"
              :class="{ selected: selectedDevices.includes(device.id) }"
            >
              <td>
                <input
                  type="checkbox"
                  :checked="selectedDevices.includes(device.id)"
                  @click="toggleSelection(device.id)"
                />
              </td>
              <td>
                <strong>{{ device.client_name }}</strong>
                <div class="text-dim small">{{ device.identity || '' }}</div>
              </td>
              <td class="font-mono">
                {{ device.ip_address }}
                <div class="text-dim small" v-if="device.api_port && device.api_port !== 8728 && device.api_port !== 22">
                  API: {{ device.api_port }}
                </div>
                <div class="text-dim small" v-if="device.ssh_port && device.ssh_port !== 22">
                  SSH: {{ device.ssh_port }}
                </div>
              </td>
              <td>
                {{ device.vendor || 'Generico' }}
                <span v-if="device.vendor === 'Generic'" class="badge device" style="margin-left:4px;font-size:0.68rem;">Solo Ping</span>
              </td>
              <td>
                <span :class="['badge', getDeviceRole(device).class]">{{
                  getDeviceRole(device).label
                }}</span>
              </td>
              <td>
                <div v-if="device.is_maestro">
                  <div class="conn-line">
                    <span class="conn-tag vpn-tag">VPN</span>
                    <select
                      v-model="device.vpn_profile_id"
                      @change="handleVpnAssociation(device)"
                      class="mini-select"
                    >
                      <option :value="null">Sin VPN</option>
                      <option v-for="vpn in vpnProfiles" :key="vpn.id" :value="vpn.id">
                        {{ vpn.name }}
                      </option>
                    </select>
                  </div>
                </div>
                <div v-else-if="device.maestro_id" class="conn-line">
                  <span class="conn-tag maestro-tag">Maestro</span>
                  <div class="conn-info">
                    <strong>{{ getMaestroById(device.maestro_id)?.client_name || 'Desconocido' }}</strong>
                    <div class="text-dim small font-mono" v-if="getMaestroById(device.maestro_id)?.ip_address">
                      {{ getMaestroById(device.maestro_id).ip_address }}
                    </div>
                    <div class="text-dim small" v-if="getVpnName(device.vpn_profile_id)">
                      vía VPN: {{ getVpnName(device.vpn_profile_id) }}
                    </div>
                  </div>
                </div>
                <div v-else-if="device.vpn_profile_id" class="conn-line">
                  <span class="conn-tag vpn-tag">VPN</span>
                  <strong>{{ getVpnName(device.vpn_profile_id) || 'Desconocida' }}</strong>
                </div>
                <div v-else class="text-dim">Sin conexión</div>
              </td>
              
              <td style="text-align: right; position: relative;">
                <div class="dropdown-container">
                  <button 
                    class="btn-kebab" 
                    @click.stop="toggleDropdown(device.id)"
                  >
                    ⋮
                  </button>
                  
                  <div class="dropdown-menu" v-if="activeDropdown === device.id">
                    <button class="dropdown-item" @click="openCommentsModal(device)">
                      <span class="icon">📝</span> Bitácora
                    </button>

                    <button v-if="device.vendor !== 'Generic'" class="dropdown-item" @click="openTerminalSetup(device)">
                      <span class="icon">💻</span> Smart Terminal
                    </button>

                    <button
                      v-if="!device.is_maestro && device.credential_id"
                      class="dropdown-item"
                      @click="promoteToMaestro(device)"
                    >
                      <span class="icon">⬆️</span> Promover Maestro
                    </button>

                    <button v-if="device.vendor !== 'Generic'" class="dropdown-item text-warning" @click="openRotateCredentialsModal(device)">
                      <span class="icon">🔑</span> Rotar Credenciales
                    </button>

                    <button v-if="device.vendor !== 'Generic'" class="dropdown-item text-danger" @click="requestReboot(device)" :disabled="isRebooting">
                      <span class="icon">🔄</span> Reiniciar Equipo
                    </button>

                    <div class="dropdown-divider"></div>

                    <button class="dropdown-item text-danger" @click="deleteDevice(device)" :disabled="deletingId === device.id">
                      <span class="icon">🗑️</span> Eliminar
                    </button>
                  </div>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section v-if="currentTab === 'tasks'" class="control-section fade-in">
      <div class="manage-header">
        <h2><i class="icon">⚙️</i> Panel de Tareas</h2>
      </div>
      
      <p class="text-dim" style="margin-bottom: 1.5rem;">
        Aquí puedes gestionar las tareas masivas que se ejecutan automáticamente en el fondo o bajo demanda (Firmware, Scripts, Reinicios).
      </p>

      <div v-if="isLoadingTasks" class="loading-text">Cargando tareas programadas...</div>
      
      <div v-else-if="scheduledTasks.length === 0" class="empty-state" style="padding: 3rem 0;">
        <div class="empty-icon">⏳</div>
        <p>No tienes tareas o acciones creadas aún.</p>
        <span class="text-dim small">Selecciona equipos desde la pestaña de Gestión para crear una.</span>
      </div>

      <div v-else class="table-responsive">
        <table class="device-table">
          <thead>
            <tr>
              <th>Estado</th>
              <th>Nombre de Tarea</th>
              <th>Acción</th>
              <th>Modo / Frecuencia</th>
              <th>Equipos</th>
              <th>Última Ejecución</th>
              <th style="text-align: right;">Opciones</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="task in scheduledTasks" :key="task.id">
              <td>
                <label class="toggle-switch" v-if="task.schedule_config.trigger_mode !== 'manual'">
                  <input type="checkbox" :checked="task.is_active" @change="toggleTaskState(task)" />
                  <span class="slider"></span>
                </label>
                <span class="badge" style="background: #444;" v-else>Bajo Demanda</span>
              </td>
              <td>
                <strong>{{ task.name }}</strong>
                <div class="text-dim small">ID: {{ task.id }}</div>
              </td>
              <td>
                <span class="badge maestro" v-if="task.action_type === 'conditional_reboot'">Reinicio Condicional</span>
                <span class="badge managed" v-else-if="task.action_type === 'custom_script'">Script Personalizado</span>
                <span class="badge device" v-else-if="task.action_type === 'firmware_update'">Actualización Firmware</span>
                <span class="badge" style="background: #fbbf24; color: #111;" v-else-if="task.action_type === 'change_ports'">Cambio de Puertos</span>
                <span class="badge device" v-else>Reinicio Forzado</span>
              </td>
              <td>
                <div v-if="task.schedule_config.trigger_mode === 'manual'">
                  <span class="badge" style="background: var(--blue); color: white;">MANUAL</span>
                </div>
                <div v-else>
                  <div style="font-weight: bold;">{{ task.schedule_config.time }}</div>
                  <div class="text-dim small">
                    {{ task.schedule_config.days && task.schedule_config.days.length > 0 ? task.schedule_config.days.join(', ').toUpperCase() : 'Todos los días' }}
                  </div>
                </div>
              </td>
              <td><span class="badge" style="background: rgba(255,255,255,0.1);">{{ task.target_count }} asignados</span></td>
              <td>{{ formatDate(task.last_run) }}</td>
              <td style="text-align: right;">
                <div style="display: flex; gap: 0.5rem; justify-content: flex-end;">
                  <button class="btn-secondary" style="padding: 0.4rem 0.8rem; font-size: 0.85rem; border-color: var(--green); color: var(--green);" @click="runTaskNow(task)">
                    ▶️ Ejecutar Ahora
                  </button>
                  <button class="btn-secondary" style="padding: 0.4rem 0.8rem; font-size: 0.85rem;" @click="openTaskLogsModal(task)">
                    📋 Historial
                  </button>
                  <button class="btn-secondary text-danger" style="padding: 0.4rem 0.8rem; font-size: 0.85rem; border-color: rgba(255,0,0,0.3);" @click="deleteScheduledTask(task)">
                    🗑️
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <div v-if="showLimitModal" class="modal-overlay" @click="showLimitModal = false" style="z-index: 9999;">
      <div class="limit-modal" @click.stop>
        <div class="limit-icon">🛑</div>
        <h3>Límite Alcanzado</h3>
        <p>{{ limitMessage }}</p>
        <div class="limit-actions">
          <button class="btn-secondary" @click="showLimitModal = false">Entendido</button>
          <button class="btn-primary" @click="goToBilling">Ampliar mi Plan</button>
        </div>
      </div>
    </div>

    <div v-if="showBulkRenameModal" class="modal-overlay" @click.self="closeBulkRenameModal">
      <div class="modal-content large-modal">
        <div class="manage-header">
          <h3>📂 Actualización Masiva desde Excel</h3>
          <button class="btn-secondary" @click="closeBulkRenameModal">X</button>
        </div>

        <p class="text-dim" style="margin-bottom: 1rem;">
          Sube un archivo Excel (.xlsx, .csv) extraído de otro sistema (Ej: MikroWisp) para actualizar los nombres de los dispositivos asociándolos por su dirección IP.
        </p>

        <div class="form-group" style="margin-bottom: 1.5rem;">
          <label>1. Selecciona a qué VPN pertenecen las IPs (Opcional, pero recomendado)</label>
          <select v-model="bulkRenameForm.vpn_profile_id" class="filter-select" style="width: 100%; margin-top: 0.5rem;">
            <option :value="null">Todas las VPN (Cuidado si hay IPs repetidas)</option>
            <option v-for="vpn in vpnProfiles" :key="vpn.id" :value="vpn.id">
              {{ vpn.name }}
            </option>
          </select>
        </div>

        <div class="form-group">
          <label>2. Carga tu archivo</label>
          <input 
            type="file" 
            id="excelFileInput"
            accept=".xlsx, .xls, .csv" 
            @change="handleFileUpload" 
            style="display: block; padding: 10px 0;"
          />
          <small v-if="isUploadingExcel" class="text-warning">Procesando archivo...</small>
        </div>

        <div v-if="bulkRenameHeaders.length > 0" class="config-grid" style="margin-top: 1rem; background: rgba(0,0,0,0.2); padding: 1rem; border-radius: 8px;">
          <div class="form-group">
            <label style="color: var(--blue);">3. Columna de la IP</label>
            <select v-model="bulkRenameForm.ip_column" class="filter-select">
              <option value="" disabled>Selecciona la columna...</option>
              <option v-for="col in bulkRenameHeaders" :key="col" :value="col">{{ col }}</option>
            </select>
          </div>
          
          <div class="form-group">
            <label style="color: var(--green);">4. Columna del Nuevo Nombre</label>
            <select v-model="bulkRenameForm.name_column" class="filter-select">
              <option value="" disabled>Selecciona la columna...</option>
              <option v-for="col in bulkRenameHeaders" :key="col" :value="col">{{ col }}</option>
            </select>
          </div>
        </div>

        <div v-if="bulkRenamePreview.length > 0" style="margin-top: 1.5rem;">
          <h4>Vista Previa (Primeros 5 registros)</h4>
          <table class="device-table" style="font-size: 0.85rem;">
            <thead>
              <tr>
                <th style="color: var(--blue);">IP a Buscar</th>
                <th style="color: var(--green);">Nuevo Nombre Asignado</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(item, i) in bulkRenamePreview" :key="i">
                <td class="font-mono">{{ item.ip_address }}</td>
                <td><strong>{{ item.new_client_name }}</strong></td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="modal-actions" style="margin-top: 2rem;">
          <button @click="closeBulkRenameModal" class="btn-secondary" :disabled="isSubmittingBulkRename">Cancelar</button>
          <button @click="submitBulkRename" class="btn-primary" :disabled="isSubmittingBulkRename || !bulkRenameForm.ip_column || !bulkRenameForm.name_column">
            {{ isSubmittingBulkRename ? 'Enviando...' : 'Iniciar Actualización Masiva' }}
          </button>
        </div>
      </div>
    </div>

    <div v-if="showTaskModal" class="modal-overlay">
      <div class="modal-content large-modal">
        <h3>⏱️ Configurar Tarea o Acción Masiva</h3>

        <div class="compatibility-box" :class="taskCompatibility.isPartial ? 'warning' : 'ok'">
          {{ taskCompatibility.message }}
        </div>

        <form @submit.prevent="submitScheduledTask" class="bulk-form">
          
          <div class="grid-2">
            <div class="form-group">
              <label>Modo de Ejecución</label>
              <select v-model="newTaskForm.trigger_mode">
                <option value="cron">Automático (Programado por Horario)</option>
                <option value="manual">Manual (A demanda / Una sola vez)</option>
              </select>
            </div>
            
            <div class="form-group">
              <label>Nombre del Grupo o Tarea</label>
              <input v-model="newTaskForm.name" type="text" placeholder="Ej: Actualizar Nodo Central" required />
            </div>
          </div>

          <div class="form-group">
            <label>Tipo de Acción</label>
            <select v-model="newTaskForm.action_type">
              <option value="conditional_reboot">Reinicio Condicional (Seguro)</option>
              <option value="reboot">Reinicio Forzado (Inmediato)</option>
              <option value="firmware_update">Actualización de Firmware (MikroTik)</option>
              <option value="custom_script">Ejecutar Script Personalizado</option>
              <option value="change_ports">Cambio Masivo de Puertos y Servicios</option>
            </select>
          </div>

          <div class="form-group" v-if="newTaskForm.action_type === 'conditional_reboot'" style="background: rgba(255,255,255,0.03); padding: 1rem; border-radius: 8px;">
            <label>Condición: Días mínimos de encendido (Uptime)</label>
            <div style="display: flex; align-items: center; gap: 10px;">
              <input type="number" v-model.number="newTaskForm.min_uptime_days" min="1" required style="width: 100px;"/>
              <span class="text-dim">días. Si el equipo tiene menos tiempo, se omitirá el reinicio.</span>
            </div>
          </div>

          <div class="form-group" v-if="newTaskForm.action_type === 'firmware_update'" style="background: rgba(52, 152, 219, 0.1); padding: 1rem; border-radius: 8px; border: 1px solid var(--blue);">
            <p style="margin-top: 0; margin-bottom: 0.5rem; font-weight: bold; color: var(--blue);">ℹ️ Información sobre Actualizaciones</p>
            <span class="text-dim small" style="line-height: 1.4;">
              El sistema actualizará los equipos MikroTik a la versión estable más reciente. Si el equipo está en v6, el sistema ejecutará un doble salto (v6 -> canal upgrade -> v7 -> canal stable -> v7 actual) manejando los reinicios automáticamente.<br>
              <strong>Nota:</strong> Los equipos Ubiquiti o Mimosa serán omitidos.
            </span>
          </div>

          <div class="form-group" v-if="newTaskForm.action_type === 'custom_script'">
            <label>Código del Script (RouterOS o Bash)</label>
            <textarea 
              v-model="newTaskForm.script_body" 
              rows="6" 
              class="terminal-textarea"
              placeholder="# Escribe aquí el comando crudo. Ej:\n/system reboot"
              required
            ></textarea>
            <small class="text-dim">La sintaxis dependerá del fabricante de los equipos seleccionados.</small>
          </div>

          <div class="form-group" v-if="newTaskForm.action_type === 'change_ports'" style="background: rgba(255,255,255,0.03); padding: 1rem; border-radius: 8px; border: 1px solid var(--primary-color);">
            <p style="margin-top: 0; margin-bottom: 1rem; font-weight: bold; color: #fbbf24;">⚠️ Cambio de Puertos Multi-Vendor</p>
            <span class="text-dim small" style="display:block; margin-bottom: 1rem; line-height: 1.4;">
              Selecciona qué servicios deseas modificar o deshabilitar. <br>
              <strong>Nota:</strong> Si cambias o deshabilitas los puertos principales de gestión (API o SSH), la plataforma sincronizará automáticamente la base de datos para no perder conexión. Los servicios exclusivos (API, Winbox) solo afectarán a equipos MikroTik. Tras aplicar cambios exitosos, los equipos se reiniciarán automáticamente.
            </span>
            
            <div class="table-responsive">
              <table class="device-table" style="font-size: 0.9rem;">
                <thead>
                  <tr>
                    <th style="width: 80px; text-align: center;">Tocar</th>
                    <th>Servicio</th>
                    <th>Nuevo Puerto</th>
                    <th>Deshabilitar</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(cfg, key) in portChangeConfig" :key="key">
                    <td style="text-align: center;">
                      <input type="checkbox" v-model="cfg.enabled" />
                    </td>
                    <td style="text-transform: uppercase; font-weight: bold; color: var(--blue);">
                      {{ key === 'www' ? 'HTTP (WWW)' : key }}
                    </td>
                    <td>
                      <input 
                        type="number" 
                        v-model.number="cfg.port" 
                        :disabled="!cfg.enabled || cfg.disable" 
                        class="mini-select" 
                        style="width: 100px; padding: 0.3rem;"
                      />
                    </td>
                    <td>
                      <label style="display: inline-flex; align-items: center; gap: 8px; cursor: pointer;" :style="{ opacity: !cfg.enabled ? '0.5' : '1' }">
                        <input type="checkbox" v-model="cfg.disable" :disabled="!cfg.enabled" /> 
                        <span class="text-danger" v-if="cfg.disable">Apagar</span>
                        <span v-else>Mantener activo</span>
                      </label>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <template v-if="newTaskForm.trigger_mode === 'cron'">
            <hr class="separator" />
            <h4>🕒 Horario de Ejecución Automática</h4>

            <div class="grid-2" style="margin-top: 1rem;">
              <div class="form-group">
                <label>Hora Local (HH:MM)</label>
                <input type="time" v-model="newTaskForm.time" required />
              </div>
              
              <div class="form-group">
                <label>Días de la Semana</label>
                <div class="day-picker">
                  <button 
                    type="button"
                    v-for="day in daysOfWeek" 
                    :key="day.value"
                    :class="['day-pill', { active: newTaskForm.days.includes(day.value) }]"
                    @click="toggleDaySelection(day.value)"
                  >
                    {{ day.label }}
                  </button>
                </div>
                <small class="text-dim" style="margin-top: 5px;">Si no seleccionas ninguno, se ejecutará <strong>todos los días</strong>.</small>
              </div>
            </div>
          </template>

          <div class="modal-actions">
            <button type="button" @click="showTaskModal = false" class="btn-secondary">Cancelar</button>
            <button type="submit" class="btn-primary" :disabled="isCreatingTask">
              {{ isCreatingTask ? 'Guardando...' : 'Guardar Configuración' }}
            </button>
          </div>
        </form>
      </div>
    </div>

    <div v-if="showTaskLogsModal" class="modal-overlay" @click.self="showTaskLogsModal = false">
      <div class="modal-content large-modal" style="max-width: 900px;">
        <div class="manage-header" style="align-items: flex-start;">
          <div>
            <h3 style="margin: 0;">📋 Consola de Auditoría</h3>
            <span class="text-dim">{{ activeTaskForLogs?.name }}</span>
          </div>
          <div style="display: flex; gap: 10px;">
            <button class="btn-secondary text-danger" @click="clearTaskLogs" :disabled="isClearingLogs" title="Vaciar Historial Completo" style="border-color: rgba(255,0,0,0.3); font-size: 0.85rem; padding: 0.4rem 0.8rem;">
              <span v-if="!isClearingLogs">🗑️ Limpiar Logs</span>
              <span v-else>Limpiando...</span>
            </button>
            <button class="btn-secondary" @click="showTaskLogsModal = false">X</button>
          </div>
        </div>

        <div class="comments-list" style="background: rgba(0,0,0,0.3);">
          <div v-if="isLoadingTaskLogs" class="loading-text">Cargando bitácora de ejecuciones...</div>
          <div v-else-if="activeTaskLogs.length === 0" class="empty-state">
            <div class="empty-icon">📂</div>
            <p>La bitácora está limpia.</p>
          </div>

          <div v-else class="comments-scroll" style="max-height: 50vh;">
            <div v-for="log in activeTaskLogs" :key="log.id" class="comment-item">
              <div class="comment-header">
                <strong>{{ log.client_name }} ({{ log.ip_address }})</strong>
                <span class="comment-date" style="display: flex; gap: 10px; align-items: center;">
                  {{ formatDate(log.executed_at) }}
                  <span :class="['status-badge', log.status]">{{ log.status.replace('_', ' ').toUpperCase() }}</span>
                </span>
              </div>
              <div v-if="log.output" class="comment-body terminal-output">
                {{ log.output }}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div v-if="showBulkModal" class="modal-overlay">
      <div class="modal-content large-modal">
        <h3>⚡ Crear Monitores Masivos</h3>

        <div class="compatibility-box" :class="bulkCompatibility.isPartial ? 'warning' : 'ok'">
          {{ bulkCompatibility.message }}
        </div>

        <div class="bulk-form">
          <div class="form-group">
            <label>Tipo de Sensor</label>
            <div class="sensor-type-selector" style="flex-wrap: wrap;">
              <button :class="{ active: bulkSensorType === 'ping' }" @click="bulkSensorType = 'ping'">
                PING (ICMP)
              </button>
              <button :class="{ active: bulkSensorType === 'ethernet' }" @click="bulkSensorType = 'ethernet'">
                ETHERNET
              </button>
              <button :class="{ active: bulkSensorType === 'wireless' }" @click="bulkSensorType = 'wireless'">
                WIRELESS 📡
              </button>
              <button :class="{ active: bulkSensorType === 'system' }" @click="bulkSensorType = 'system'">
                SISTEMA 💻
              </button>
            </div>
          </div>

          <div class="form-group">
            <label>Plantilla de Nombre</label>
            <input v-model="bulkNameTemplate" placeholder="{{hostname}} - Sensor" />
            <small>Variables: <code v-pre>{{ hostname }}</code>, <code v-pre>{{ ip }}</code></small>
          </div>

          <hr class="separator" />

          <div class="config-form-wrapper">
            <SensorConfigurator
              v-if="bulkSensorType === 'ping'"
              v-model="bulkPingConfig"
              sensor-type="ping"
              :channels="channels"
              :auto-tasks="autoTasks"
              :suggested-target-devices="suggestedTargetDevicesForBulk"
              hide-name
            />
            <SensorConfigurator
              v-else-if="bulkSensorType === 'ethernet'"
              v-model="bulkEthernetConfig"
              sensor-type="ethernet"
              :channels="channels"
              :auto-tasks="autoTasks"
              hide-name
            />
            <SensorConfigurator
              v-else-if="bulkSensorType === 'wireless'"
              v-model="bulkWirelessConfig"
              sensor-type="wireless"
              :channels="channels"
              :auto-tasks="autoTasks"
              hide-name
            />
            <SensorConfigurator
              v-else-if="bulkSensorType === 'system'"
              v-model="bulkSystemConfig"
              sensor-type="system"
              :channels="channels"
              :auto-tasks="autoTasks"
              hide-name
            />
          </div>

          <div class="form-group checkbox" style="margin-top: 1.5rem">
            <label>
              <input type="checkbox" v-if="bulkSensorType === 'ping'" v-model="bulkPingConfig.is_active" />
              <input type="checkbox" v-if="bulkSensorType === 'ethernet'" v-model="bulkEthernetConfig.is_active" />
              <input type="checkbox" v-if="bulkSensorType === 'wireless'" v-model="bulkWirelessConfig.is_active" />
              <input type="checkbox" v-if="bulkSensorType === 'system'" v-model="bulkSystemConfig.is_active" />
              Activar monitores inmediatamente
            </label>
          </div>
        </div>

        <div class="modal-actions">
          <button @click="showBulkModal = false" class="btn-secondary">Cancelar</button>
          <button @click="submitBulkMonitors" class="btn-primary" :disabled="isBulking">
            {{ isBulking ? 'Procesando...' : 'Aplicar Configuración' }}
          </button>
        </div>
      </div>
    </div>

    <div v-if="showRotateCredentialsModal" class="modal-overlay" @click.self="showRotateCredentialsModal = false; activeDeviceForPassword = null" style="z-index: 4000">
      <div class="modal-content" style="max-width: 450px;">
        <div class="modal-header-alert" style="text-align: center; margin-bottom: 1rem;">
          <span style="font-size: 2.5rem; display: block; margin-bottom: 0.5rem;">🔑</span>
          <h3 style="margin:0;">Rotar Credenciales</h3>
          <p class="text-dim" style="margin-top: 0.5rem;">
            {{ activeDeviceForPassword?.client_name }} ({{ activeDeviceForPassword?.ip_address }})
          </p>
        </div>
        
        <form @submit.prevent="submitRotateCredentials" style="display: flex; flex-direction: column; gap: 1rem;">
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

          <div class="form-group" style="margin-top: 0.5rem; border-top: 1px dashed var(--primary-color); padding-top: 1rem;">
            <label>Nombre del Nuevo Perfil de Credencial</label>
            <input type="text" v-model="rotateCredentialsForm.credentialName" required />
            <small class="text-dim" style="margin-top: 0.3rem; display: block; line-height: 1.3;">
              Para no perder el acceso a otros equipos que comparten la credencial actual, se creará este nuevo perfil y se asignará automáticamente a este dispositivo.
            </small>
          </div>

          <div class="modal-actions">
            <button type="button" class="btn-secondary" @click="showRotateCredentialsModal = false; activeDeviceForPassword = null" :disabled="isRotatingCredentials">Cancelar</button>
            <button type="submit" class="btn-warning" :disabled="isRotatingCredentials">
              {{ isRotatingCredentials ? 'Cambiando...' : 'Aplicar Cambio' }}
            </button>
          </div>
        </form>
      </div>
    </div>

    <div v-if="showCommentsModal" class="modal-overlay" @click.self="showCommentsModal = false">
      <div class="modal-content large-modal">
        <div class="manage-header">
          <h3>📖 Bitácora: {{ activeDeviceForComments?.client_name }}</h3>
          <button class="btn-secondary" @click="showCommentsModal = false">X</button>
        </div>

        <div class="comments-list">
          <div v-if="isLoadingComments" class="loading-text">Cargando notas...</div>
          <div v-else-if="deviceComments.length === 0" class="empty-state">
            <div class="empty-icon">📂</div>
            <p>No hay registros en la bitácora aún.</p>
          </div>

          <div v-else class="comments-scroll">
            <div v-for="c in deviceComments" :key="c.id" class="comment-item">
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
            placeholder="Escribe un comentario sobre mantenimiento, cambios, etc..."
          ></textarea>
          <div class="modal-actions">
            <button class="btn-primary" @click="submitComment" :disabled="isSendingComment">
              {{ isSendingComment ? 'Guardando...' : 'Agregar Nota' }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <div v-if="showAuthErrorModal" class="modal-overlay" style="z-index: 4000">
      <div class="modal-content">
        <h3 style="color: #e74c3c">⚠️ Fallo de Autenticación</h3>
        <p style="margin: 1rem 0">
          {{ authErrorMessage }}
        </p>
        <p class="text-dim">
          No se pudo gestionar el equipo. ¿Deseas agregarlo como un
          <strong>Dispositivo Genérico</strong> para monitorear solo su estado con Ping (ICMP)?
        </p>
        <div class="modal-actions">
          <button @click="showAuthErrorModal = false" class="btn-secondary">Cancelar</button>
          <button @click="handleAddDeviceOneStep(true)" class="btn-primary">
            Sí, agregar solo Ping
          </button>
        </div>
      </div>
    </div>

    <div v-if="showTerminalSetupModal" class="modal-overlay" style="z-index: 4000">
      <div class="modal-content" style="max-width: 400px; width: 100%;">
        <h3>💻 Conexión Smart Terminal</h3>
        <p class="text-dim" style="margin-bottom: 1.5rem;">
          Conectando a <strong>{{ terminalSetupDevice?.client_name }}</strong> ({{ terminalSetupDevice?.ip_address }})
        </p>
        
        <div class="form-group">
          <label>Puerto SSH</label>
          <input 
            type="number" 
            v-model="terminalSetupPort" 
            placeholder="22" 
            @keyup.enter="confirmTerminalSetup"
          />
          <small class="text-dim" style="margin-top: 5px;">
            Por defecto es 22. Si la conexión es exitosa, este puerto se guardará automáticamente para la próxima vez.
          </small>
        </div>

        <div class="modal-actions">
          <button @click="showTerminalSetupModal = false" class="btn-secondary">Cancelar</button>
          <button @click="confirmTerminalSetup" class="btn-primary">Conectar</button>
        </div>
      </div>
    </div>

    <SmartTerminalModal
      v-if="showTerminalModal"
      :device="activeTerminalDevice"
      protocol="ssh"
      :port="activeTerminalPort"
      @close="closeTerminal"
    />

    <div v-if="notification.show" class="notification" :class="notification.type">
      {{ notification.message }}
    </div>
  </div>
</template>

<style scoped>
/* ESTILOS BASE (COPIADOS) */
.page-wrap {
  padding: 1rem;
  max-width: 1400px;
  margin: 0 auto;
}
.topbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}
.topbar h1 {
  color: var(--blue);
}
.tabs {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 1rem;
}
.tabs > button {
  background: transparent;
  color: var(--gray);
  border: 1px solid var(--primary-color);
  border-radius: 8px;
  padding: 0.5rem 1rem;
  cursor: pointer;
  transition: 0.2s;
  font-weight: bold;
}
.tabs > button.active {
  background: var(--primary-color);
  color: white;
}
.control-section {
  background: var(--surface-color);
  padding: 1.5rem;
  border-radius: 10px;
  border: 1px solid var(--primary-color);
  }
.control-section h2 {
  color: white;
  margin-top: 0;
  margin-bottom: 1.5rem;
}
.form-layout {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  max-width: 800px;
}
.grid-2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}
.ip-port-grid {
  display: flex;
  gap: 1rem;
  align-items: flex-end;
}
.generic-hint {
  flex: 1;
  padding: 0.55rem 0.75rem;
  background: rgba(83, 130, 240, 0.07);
  border: 1px solid rgba(83, 130, 240, 0.2);
  border-radius: 6px;
  font-size: 0.82rem;
  color: var(--text-dim, #9aa0a6);
  display: flex;
  align-items: center;
}
.generic-maestro-info {
  padding: 0.65rem 0.9rem;
  background: rgba(83, 130, 240, 0.07);
  border: 1px solid rgba(83, 130, 240, 0.2);
  border-radius: 6px;
  font-size: 0.82rem;
  color: var(--text-dim, #9aa0a6);
  line-height: 1.5;
}
.generic-maestro-info p { margin: 0; }
.form-group {
  margin-bottom: 1rem;
}
input:not([type='checkbox']),
select,
textarea {
  width: 100%;
  background-color: var(--bg-color);
  color: white;
  border: 1px solid var(--primary-color);
  border-radius: 6px;
  padding: 0.7rem;
  margin-top: 0.3rem;
  outline: none;
  font-family: inherit;
}
select option {
  background-color: var(--bg-color);
  color: white;
}
label {
  font-size: 0.9rem;
  font-weight: bold;
  color: var(--gray);
}
.text-dim {
  color: #777;
  font-size: 0.8rem;
  display: block;
  margin-top: 2px;
}
.actions-row {
  display: flex;
  gap: 1rem;
  margin-top: 1rem;
}

/* =========================================
   BOTONES
   ========================================= */
.btn-primary {
  background: var(--green);
  color: white;
  padding: 0.7rem 1.2rem;
  border-radius: 6px;
  border: none;
  cursor: pointer;
  font-weight: bold;
}
.btn-secondary {
  background: transparent;
  border: 1px solid var(--primary-color);
  color: white;
  padding: 0.7rem 1.2rem;
  border-radius: 6px;
  cursor: pointer;
}
.btn-warning {
  background: #f59e0b;
  color: #111;
  border: none;
  padding: 0.7rem 1.2rem;
  border-radius: 6px;
  cursor: pointer;
  font-weight: bold;
}
.btn-warning:hover:not(:disabled) {
  background: #fbbf24;
}

/* Estilo para el botón de Eliminar Masivo */
.btn-danger {
  background: var(--error-red) !important;
  color: white !important;
}
.btn-danger:hover:not(:disabled) {
  background: #ff8787 !important; 
}
.btn-danger:disabled {
  background: rgba(231, 76, 60, 0.5) !important;
  cursor: not-allowed;
  opacity: 0.8;
}

/* Estilo para el botón de Configurar Monitores (Celeste/Teal tecnológico) */
.btn-info {
  background: #0ea5e9 !important;
  color: white !important;
}
.btn-info:hover:not(:disabled) {
  background: #38bdf8 !important;
}

/* =========================================
   ESTADO Y NOTIFICACIONES
   ========================================= */
.test-box {
  padding: 1rem;
  margin-top: 1rem;
  border-radius: 6px;
  background: var(--bg-color);
  border: 1px solid var(--primary-color);
}
.test-box.ok {
  border-color: var(--green);
  color: var(--green);
}
.test-box.error {
  border-color: var(--error-red);
  color: var(--error-red);
}
.notification {
  position: fixed;
  top: 90px;
  right: 20px;
  padding: 1rem 1.5rem;
  border-radius: 8px;
  color: white;
  font-weight: bold;
  z-index: 5000;
}
.notification.success {
  background: var(--green);
}
.notification.error {
  background: var(--error-red);
}
.notification.warning {
  background: #f39c12;
  color: white;
}

/* =========================================
   ESTILOS BARRA DE FILTROS
   ========================================= */
.filter-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: rgba(255, 255, 255, 0.03);
  padding: 12px 15px;
  border-radius: 8px 8px 0 0;
  margin-bottom: 2px;
  flex-wrap: wrap;
  gap: 15px;
}
.search-group {
  display: flex;
  align-items: center;
  background: var(--bg-color);
  padding: 0 10px;
  border-radius: 6px;
  border: 1px solid #444;
  flex: 1;
  min-width: 200px;
  max-width: 400px;
}
.search-group .icon { color: #777; margin-right: 5px; }
.filter-input {
  background: transparent !important;
  border: none !important;
  color: white;
  padding: 8px 0 !important;
  margin-top: 0 !important;
  width: 100%;
  outline: none;
}
.filter-controls {
  display: flex;
  align-items: center;
  gap: 15px;
  flex-wrap: wrap;
}
.filter-select {
  background: var(--bg-color) !important;
  color: white;
  border: 1px solid #444 !important;
  padding: 6px 10px !important;
  margin-top: 0 !important;
  border-radius: 6px !important;
  outline: none;
  font-size: 0.9rem;
  min-width: 150px;
}
.toggle-group {
  display: flex;
  background: var(--bg-color);
  border-radius: 6px;
  border: 1px solid #444;
  overflow: hidden;
}
.toggle-group button {
  background: transparent;
  border: none;
  color: #aaa;
  padding: 6px 12px;
  cursor: pointer;
  font-size: 0.85rem;
  transition: all 0.2s;
  border-right: 1px solid #444;
}
.toggle-group button:last-child { border-right: none; }
.toggle-group button:hover { color: white; background: rgba(255,255,255,0.05); }
.toggle-group button.active {
  background: var(--primary-color);
  color: white;
  font-weight: bold;
}

/* =========================================
   ESTILOS TABLE & BULK
   ========================================= */
.manage-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 1rem;
  flex-wrap: wrap;
  gap: 0.75rem;
}
.inventory-title-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
}
.btn-excel-import {
  padding: 0.4rem 0.8rem;
  font-size: 0.85rem;
  white-space: nowrap;
}
.bulk-actions-wrapper {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}
.btn-bulk {
  color: #fff;
  border: none;
  padding: 0.6rem 1rem;
  border-radius: 6px;
  font-weight: bold;
  cursor: pointer;
  transition: opacity 0.2s;
}
.btn-bulk:hover {
  opacity: 0.9;
}

.table-responsive {
  overflow-x: auto; /* Permite scroll horizontal en móvil */
  -webkit-overflow-scrolling: touch;
}
.device-table {
  width: 100%;
  border-collapse: collapse;
}
.device-table th {
  text-align: left;
  padding: 1rem;
  background: rgba(255, 255, 255, 0.05);
  color: var(--gray);
  font-weight: 500;
  border-bottom: 1px solid var(--primary-color);
}
.device-table td {
  padding: 1rem;
  border-bottom: 1px solid var(--primary-color);
  color: white;
}
.device-table tr:hover {
  background: rgba(255, 255, 255, 0.03);
}
.device-table tr.selected {
  background: rgba(106, 180, 255, 0.1);
}
.badge {
  padding: 3px 8px;
  border-radius: 12px;
  font-size: 0.75rem;
  text-transform: uppercase;
  font-weight: bold;
}
.badge.maestro {
  background: var(--blue);
  color: white;
}
.badge.managed {
  background: var(--green);
  color: white;
}
.badge.device {
  background: #555;
  color: #ccc;
}
.mini-select {
  padding: 0.4rem;
  font-size: 0.85rem;
  border-radius: 4px;
  background-color: var(--bg-color);
  border: 1px solid var(--primary-color);
  color: white;
}

.conn-line {
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
}
.conn-info {
  display: flex;
  flex-direction: column;
  line-height: 1.25;
}
.conn-tag {
  display: inline-block;
  padding: 0.15rem 0.45rem;
  font-size: 0.68rem;
  font-weight: 700;
  border-radius: 4px;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  flex-shrink: 0;
  margin-top: 2px;
}
.conn-tag.vpn-tag {
  background: rgba(52, 152, 219, 0.18);
  color: #5dade2;
  border: 1px solid rgba(52, 152, 219, 0.4);
}
.conn-tag.maestro-tag {
  background: rgba(241, 196, 15, 0.15);
  color: #f1c40f;
  border: 1px solid rgba(241, 196, 15, 0.4);
}

/* =========================================
   DROPDOWN MENU STYLES (KEBAB)
   ========================================= */
.dropdown-container {
  position: relative;
  display: inline-block;
}

.btn-kebab {
  background: transparent;
  border: none;
  color: #aaa;
  font-size: 1.5rem;
  line-height: 1;
  padding: 4px 8px;
  cursor: pointer;
  border-radius: 4px;
  transition: all 0.2s;
}

.btn-kebab:hover, .btn-kebab:focus {
  background: rgba(255, 255, 255, 0.1);
  color: white;
}

.dropdown-menu {
  position: absolute;
  right: 0;
  top: 100%;
  margin-top: 5px;
  background-color: var(--surface-color);
  border: 1px solid var(--primary-color);
  border-radius: 8px;
  box-shadow: 0 4px 15px rgba(0,0,0,0.5);
  min-width: 200px;
  z-index: 1000;
  display: flex;
  flex-direction: column;
  padding: 0.5rem 0;
}

.dropdown-item {
  background: transparent;
  border: none;
  color: #ddd;
  text-align: left;
  padding: 0.8rem 1.2rem;
  cursor: pointer;
  font-size: 0.9rem;
  display: flex;
  align-items: center;
  gap: 10px;
  transition: background 0.2s;
}

.dropdown-item:hover {
  background: rgba(255,255,255,0.05);
  color: white;
}

.dropdown-item:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.dropdown-divider {
  height: 1px;
  background-color: var(--primary-color);
  margin: 0.5rem 0;
}

.text-warning {
  color: #fbbf24;
}
.text-danger {
  color: #ff6b6b;
}

.font-mono {
  font-family: monospace;
}
.fade-in {
  animation: fadeIn 0.3s ease;
}
@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(5px);
  }
  to {
    opacity: 1;
    transform: 0;
  }
}

/* =========================================
   MODALES Y CONFIGURADOR DE SENSORES
   ========================================= */
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
  backdrop-filter: blur(4px);
}
.modal-content {
  background: var(--surface-color);
  padding: 2rem;
  border-radius: 10px;
  border: 1px solid var(--primary-color);
  color: white;
}
.large-modal {
  width: 750px;
  max-width: 95%;
  max-height: 90vh;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
}

.compatibility-box {
  padding: 0.8rem;
  margin-bottom: 1.5rem;
  border-radius: 6px;
  font-weight: bold;
  font-size: 0.9rem;
  border: 1px solid transparent;
}
.compatibility-box.ok {
  background: rgba(46, 204, 113, 0.15);
  border-color: var(--green);
  color: var(--green);
}
.compatibility-box.warning {
  background: rgba(243, 156, 18, 0.15);
  border-color: #f39c12;
  color: #f39c12;
}

.sensor-type-selector {
  display: flex;
  gap: 1rem;
  margin-top: 0.5rem;
}
.sensor-type-selector button {
  flex: 1;
  padding: 0.8rem;
  background: var(--bg-color);
  border: 1px solid var(--primary-color);
  color: var(--gray);
  cursor: pointer;
  font-weight: bold;
  border-radius: 6px;
}
.sensor-type-selector button.active {
  background: var(--primary-color);
  color: white;
  border-color: white;
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

.separator {
  border: 0;
  border-top: 1px solid var(--primary-color);
  margin: 1.5rem 0;
}
.config-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}
.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 1rem;
  margin-top: 2rem;
}

/* =========================================
   BITÁCORA STYLES
   ========================================= */
.comments-list {
  background: rgba(0, 0, 0, 0.2);
  border-radius: 6px;
  padding: 1rem;
  margin-bottom: 1rem;
  min-height: 200px;
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

/* =========================================
   NUEVOS ESTILOS TAREAS PROGRAMADAS
   ========================================= */

/* Toggle Switch (Interruptor) */
.toggle-switch {
  position: relative;
  display: inline-block;
  width: 40px;
  height: 20px;
}
.toggle-switch input {
  opacity: 0;
  width: 0;
  height: 0;
}
.slider {
  position: absolute;
  cursor: pointer;
  top: 0; left: 0; right: 0; bottom: 0;
  background-color: #555;
  transition: .3s;
  border-radius: 20px;
}
.slider:before {
  position: absolute;
  content: "";
  height: 14px;
  width: 14px;
  left: 3px;
  bottom: 3px;
  background-color: white;
  transition: .3s;
  border-radius: 50%;
}
input:checked + .slider {
  background-color: var(--green);
}
input:checked + .slider:before {
  transform: translateX(20px);
}

/* Selector de Días (Píldoras) */
.day-picker {
  display: flex;
  gap: 5px;
  margin-top: 5px;
}
.day-pill {
  background: var(--bg-color);
  border: 1px solid var(--primary-color);
  color: var(--gray);
  padding: 6px 10px;
  border-radius: 20px;
  cursor: pointer;
  font-size: 0.85rem;
  font-weight: bold;
  transition: all 0.2s;
}
.day-pill:hover {
  background: rgba(255,255,255,0.05);
  color: white;
}
.day-pill.active {
  background: var(--blue);
  color: white;
  border-color: var(--blue);
}

/* Textarea Script Estilo Consola */
.terminal-textarea {
  background-color: #1e1e1e !important;
  color: #00ff00 !important;
  font-family: 'Courier New', Courier, monospace !important;
  border: 1px solid #333 !important;
  padding: 10px !important;
  line-height: 1.4 !important;
}
.terminal-output {
  background-color: #0d1117;
  color: #c9d1d9;
  font-family: monospace;
  padding: 10px;
  border-radius: 4px;
  margin-top: 10px;
  border: 1px solid #30363d;
  font-size: 0.85rem;
  max-height: 150px;
  overflow-y: auto;
}

/* Badges de Estado de Tareas */
.status-badge {
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 0.7rem;
  font-weight: bold;
}
.status-badge.success { background: rgba(46, 204, 113, 0.2); color: var(--green); border: 1px solid var(--green); }
.status-badge.error { background: rgba(231, 76, 60, 0.2); color: var(--error-red); border: 1px solid var(--error-red); }
.status-badge.skipped { background: rgba(243, 156, 18, 0.2); color: #f39c12; border: 1px solid #f39c12; }

/* NUEVO: ESTILO PARA LA MÁQUINA DE ESTADOS DE FIRMWARE */
.status-badge.in_progress {
  background: rgba(52, 152, 219, 0.2);
  color: #3498db;
  border: 1px solid #3498db;
  animation: pulse-blue 2s infinite;
}
@keyframes pulse-blue {
  0% { box-shadow: 0 0 0 0 rgba(52, 152, 219, 0.7); }
  70% { box-shadow: 0 0 0 5px rgba(52, 152, 219, 0); }
  100% { box-shadow: 0 0 0 0 rgba(52, 152, 219, 0); }
}

/* --- MODAL DE LÍMITES --- */
.limit-modal {
  background: var(--surface-color);
  border: 1px solid var(--red, #ef4444);
  padding: 2.5rem 2rem;
  border-radius: 16px;
  max-width: 420px;
  text-align: center;
  box-shadow: 0 10px 30px rgba(0,0,0,0.6);
}
.limit-modal h3 {
  color: var(--red, #ef4444);
  margin-bottom: 0.5rem;
  font-size: 1.4rem;
}
.limit-modal p {
  color: #d1d5db;
  line-height: 1.5;
}
.limit-icon {
  font-size: 3.5rem;
  margin-bottom: 1rem;
}
.limit-actions {
  display: flex;
  gap: 1rem;
  justify-content: center;
  margin-top: 2rem;
}

@media (max-width: 820px) {
  .form-layout {
    max-width: 100%;
  }
  .grid-2 {
    grid-template-columns: 1fr;
  }
  .config-grid {
    grid-template-columns: 1fr;
  }
  .ip-port-grid {
    flex-direction: column;
  }
  .search-group {
    min-width: auto;
    max-width: 100%;
  }
  .large-modal {
    width: 95vw;
    max-width: 95vw;
    padding: 1rem;
  }
  .modal-actions {
    flex-direction: column;
    gap: 0.5rem;
  }
  .modal-actions button {
    width: 100%;
  }
  .filter-bar {
    flex-direction: column;
    align-items: stretch;
    gap: 0.5rem;
  }
  /* Título Inventario + botón Excel: apilar en columna */
  .inventory-title-row {
    flex-direction: column;
    align-items: flex-start;
  }
  .btn-excel-import {
    width: 100%;
    text-align: left;
  }
  /* Acciones masivas: columna */
  .manage-header {
    flex-direction: column;
  }
  .bulk-actions-wrapper {
    width: 100%;
  }
  /* Tabs: envuelven si no caben */
  .tabs {
    flex-wrap: wrap;
  }
  /* Botones de rol: envuelven */
  .toggle-group {
    flex-wrap: wrap;
  }
  /* Barra de acciones masivas: envuelve */
  .bulk-actions-bar,
  .manage-header {
    flex-wrap: wrap;
    gap: 0.4rem;
  }
  /* Botones más compactos en móvil */
  .tabs > button,
  .btn-bulk,
  .btn-primary,
  .btn-secondary,
  .btn-warning,
  .btn-danger,
  .btn-info {
    font-size: 0.82rem;
    padding: 0.4rem 0.6rem;
    white-space: nowrap;
  }
}
</style>