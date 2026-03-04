<script setup>
import { ref, onMounted, computed, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import api from '@/lib/api'
import SmartTerminalModal from '@/components/SmartTerminalModal.vue'

const router = useRouter()

// ===== UI Estado general =====
const currentTab = ref('add') // 'add' | 'manage'
const notification = ref({ show: false, message: '', type: 'success' })

// --- MODAL DE ERROR DE AUTENTICACIÓN ---
const showAuthErrorModal = ref(false)
const authErrorMessage = ref('')

function showNotification(message, type = 'success') {
  notification.value = { show: true, message, type }
  setTimeout(() => (notification.value.show = false), 4000)
}

// ===== Alta en un paso =====
const addForm = ref({
  client_name: '',
  ip_address: '',
  api_port: 8728,
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
const isLoadingDevices = ref(false)
const deletingId = ref(null)

// --- Nuevo Estado para Selector de IP Destino (Masivo) ---
const allDevicesList = ref([])

// ===== ESTADO FILTROS INVENTARIO (NUEVO) =====
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

// Estado del Modal Masivo
const bulkSensorType = ref('ping')
const bulkNameTemplate = ref('{{hostname}} - Sensor')

// Modelos de configuración
const createNewPingSensor = () => ({
  config: {
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
  },
  ui_alert_latency: {
    enabled: false,
    threshold_ms: 200,
    channel_id: null,
    cooldown_minutes: 5,
    tolerance_count: 1,
    notify_recovery: false,
  },
  is_active: true,
  alerts_paused: false,
})

const createNewEthernetSensor = () => ({
  config: {
    interface_name: 'ether1',
    interval_sec: 30,
  },
  ui_alert_speed_change: {
    enabled: false,
    channel_id: null,
    cooldown_minutes: 10,
    tolerance_count: 1,
    notify_recovery: false,
  },
  ui_alert_traffic: {
    enabled: false,
    threshold_mbps: 100,
    direction: 'any',
    channel_id: null,
    cooldown_minutes: 5,
    tolerance_count: 1,
    notify_recovery: false,
  },
  is_active: true,
  alerts_paused: false,
})

const bulkPingConfig = ref(createNewPingSensor())
const bulkEthernetConfig = ref(createNewEthernetSensor())

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
  if (!isoStr) return ''
  return new Date(isoStr).toLocaleString('es-ES', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

// ===== ESTADO TERMINAL (MODAL PREVIO DE PUERTO) =====
const showTerminalSetupModal = ref(false)
const showTerminalModal = ref(false)
const activeTerminalDevice = ref(null)
const activeTerminalPort = ref(22)

const terminalSetupDevice = ref(null)
const terminalSetupPort = ref(22)

// 1. Abrimos el modal de setup de puerto
function openTerminalSetup(device) {
  terminalSetupDevice.value = device
  terminalSetupPort.value = device.ssh_port || 22
  showTerminalSetupModal.value = true
  activeDropdown.value = null // Cierra el menú si está abierto
}

// 2. Confirmamos y lanzamos la terminal real
function confirmTerminalSetup() {
  activeTerminalDevice.value = terminalSetupDevice.value
  activeTerminalPort.value = terminalSetupPort.value
  showTerminalSetupModal.value = false
  showTerminalModal.value = true
}

// 3. Al cerrar la terminal
function closeTerminal() {
  showTerminalModal.value = false
  activeTerminalDevice.value = null
  fetchAllDevices()
}

// ===== NUEVO: ESTADO ROTAR CREDENCIALES =====
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
  activeDropdown.value = null // Cierra el menú si está abierto
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
    activeDeviceForPassword.value = null // <-- CORRECCIÓN: Resetea y cierra el modal
    
    // --- Refrescar el inventario y las credenciales en vivo ---
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
  activeDropdown.value = null // Cierra el menú si está abierto
  
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

onMounted(() => {
  document.addEventListener('click', closeDropdownOnClickOutside)
})
onUnmounted(() => {
  document.removeEventListener('click', closeDropdownOnClickOutside)
})

// ===== COMPUTADAS INTELIGENTES Y FILTROS =====

// Lógica de roles helper (movida arriba para poder usarla en el computed)
function getDeviceRole(device) {
  if (device.is_maestro) return { label: 'Maestro', class: 'maestro' }
  if (device.credential_id) return { label: 'Gestionado', class: 'managed' }
  return { label: 'Dispositivo', class: 'device' }
}

const maestros = computed(() => allDevices.value.filter((d) => d.is_maestro))

const uniqueVendors = computed(() => {
  const vendors = allDevices.value.map(d => d.vendor || 'Generico')
  return [...new Set(vendors)].sort()
})

const filteredDevices = computed(() => {
  return allDevices.value.filter(d => {
    // 1. Search text (Búsqueda difusa)
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
      const roleClass = getDeviceRole(d).class // 'maestro', 'managed', 'device' (genérico)
      if (inventoryFilter.value.role === 'maestro' && roleClass !== 'maestro') return false
      if (inventoryFilter.value.role === 'managed' && roleClass !== 'managed') return false
      if (inventoryFilter.value.role === 'generic' && roleClass !== 'device') return false
    }

    return true
  })
})

// Helper para Label del Puerto Dinámico
const portLabel = computed(() => {
  const v = addForm.value.vendor
  if (v === 'Mikrotik') return 'Puerto API (Winbox)'
  if (v === 'Ubiquiti' || v === 'Mimosa') return 'Puerto SSH'
  if (v === 'SNMP') return 'Puerto SNMP'
  return 'Puerto de Gestión'
})

// Cambio automático de puerto default al cambiar vendor
function onVendorChange() {
  if (addForm.value.vendor === 'Mikrotik') addForm.value.api_port = 8728
  else if (addForm.value.vendor === 'Ubiquiti') addForm.value.api_port = 22
  else if (addForm.value.vendor === 'Mimosa') addForm.value.api_port = 22
  else if (addForm.value.vendor === 'SNMP') addForm.value.api_port = 161
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

  const payload = {
    client_name: addForm.value.client_name,
    ip_address: addForm.value.ip_address,
    api_port: Number(addForm.value.api_port) || 8728,
    mac_address: addForm.value.mac_address || '',
    node: addForm.value.node || '',
    maestro_id: addForm.value.connection_method === 'maestro' ? addForm.value.maestro_id : null,
    vpn_profile_id: addForm.value.connection_method === 'vpn' ? addForm.value.vpn_profile_id : null,
    credential_id: addForm.value.connection_method === 'vpn' ? addForm.value.credential_id : null,
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

    if (detail.includes('AUTH_FAILED') && !isForced) {
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
    vendor: addForm.value.vendor,
  }
  if (addForm.value.connection_method === 'vpn') {
    payload.vpn_profile_id = addForm.value.vpn_profile_id
  } else if (addForm.value.connection_method === 'maestro') {
    payload.maestro_id = addForm.value.maestro_id
  }

  isTesting.value = true
  testResult.value = null
  try {
    const { data } = await api.post('/devices/test_reachability', payload)
    testResult.value = data
    if (data.reachable) showNotification('¡Conexión OK!', 'success')
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
  activeDropdown.value = null // Cierra el menú si está abierto
  if (!confirm(`¿Eliminar "${device.client_name}"?`)) return
  try {
    deletingId.value = device.id
    await api.delete(`/devices/${device.id}`)
    await fetchAllDevices()
    showNotification('Eliminado.', 'success')
  } catch (error) {
    console.error(error)
    showNotification('Error al eliminar.', 'error')
  } finally {
    deletingId.value = null
  }
}

// ===== LÓGICA DE SELECCIÓN Y MASIVAS (ACTUALIZADO PARA FILTROS) =====
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
    // Si todos los visibles están seleccionados, los deseleccionamos
    selectedDevices.value = selectedDevices.value.filter(id => !visibleIds.includes(id))
  } else {
    // Si no, seleccionamos solo los que están actualmente visibles
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
    await api.post('/devices/bulk-delete', { device_ids: selectedDevices.value })
    showNotification(`${selectedDevices.value.length} dispositivos eliminados.`, 'success')
    selectedDevices.value = []
    await fetchAllDevices()
  } catch (error) {
    console.error(error)
    showNotification('Error en borrado masivo.', 'error')
  } finally {
    isDeletingBulk.value = false
  }
}

// ---- Modal Creación Masiva ----
function openBulkModal() {
  if (selectedDevices.value.length === 0) return
  bulkPingConfig.value = createNewPingSensor()
  bulkEthernetConfig.value = createNewEthernetSensor()
  bulkNameTemplate.value = '{{hostname}} - Sensor'
  showBulkModal.value = true
}

// Helper de construcción de payload
function buildSensorConfig(type, data) {
  const finalConfig = { ...data.config }
  const alerts = []
  const onlyNums = (v, f) => (typeof v === 'number' && !isNaN(v) ? v : f)

  if (type === 'ping') {
    finalConfig.ping_type = 'device_to_external'
    if (!finalConfig.target_ip) finalConfig.target_ip = '8.8.8.8'

    if (data.ui_alert_timeout.enabled) {
      const a = data.ui_alert_timeout
      if (a.channel_id)
        alerts.push({
          type: 'timeout',
          channel_id: a.channel_id,
          cooldown_minutes: onlyNums(a.cooldown_minutes, 5),
          tolerance_count: Math.max(1, onlyNums(a.tolerance_count, 1)),
          notify_recovery: !!a.notify_recovery,
        })
    }
    if (data.ui_alert_latency.enabled) {
      const a = data.ui_alert_latency
      if (a.channel_id)
        alerts.push({
          type: 'high_latency',
          threshold_ms: onlyNums(a.threshold_ms, 200),
          channel_id: a.channel_id,
          cooldown_minutes: onlyNums(a.cooldown_minutes, 5),
          tolerance_count: Math.max(1, onlyNums(a.tolerance_count, 1)),
          notify_recovery: !!a.notify_recovery,
        })
    }
  } else if (type === 'ethernet') {
    if (data.ui_alert_speed_change.enabled) {
      const a = data.ui_alert_speed_change
      if (a.channel_id)
        alerts.push({
          type: 'speed_change',
          channel_id: a.channel_id,
          cooldown_minutes: onlyNums(a.cooldown_minutes, 10),
          tolerance_count: Math.max(1, onlyNums(a.tolerance_count, 1)),
          notify_recovery: !!a.notify_recovery,
        })
    }
    if (data.ui_alert_traffic.enabled) {
      const a = data.ui_alert_traffic
      if (a.channel_id)
        alerts.push({
          type: 'traffic_threshold',
          threshold_mbps: onlyNums(a.threshold_mbps, 100),
          direction: a.direction || 'any',
          channel_id: a.channel_id,
          cooldown_minutes: onlyNums(a.cooldown_minutes, 5),
          tolerance_count: Math.max(1, onlyNums(a.tolerance_count, 1)),
          notify_recovery: !!a.notify_recovery,
        })
    }
  }

  finalConfig.alerts = alerts
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
    bulkSensorType.value === 'ping' ? bulkPingConfig.value : bulkEthernetConfig.value
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
onMounted(async () => {
  fetchAllDevices()
  fetchVpnProfiles()
  fetchCredentials()
  fetchChannels()
})
</script>

<template>
  <div class="page-wrap">
    <header class="topbar">
      <h1>Dispositivos</h1>
    </header>

    <div class="tabs">
      <button :class="{ active: currentTab === 'add' }" @click="currentTab = 'add'">Agregar</button>
      <button :class="{ active: currentTab === 'manage' }" @click="currentTab = 'manage'">
        Gestionar
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
          <div>
            <label>{{ portLabel }}</label>
            <input
              type="number"
              v-model="addForm.api_port"
              :placeholder="addForm.vendor === 'Ubiquiti' ? '22' : '8728'"
              required
            />
            <small v-if="addForm.vendor === 'Mikrotik'" class="text-dim"
              >Puerto API (Default 8728)</small
            >
            <small v-if="addForm.vendor === 'Ubiquiti'" class="text-dim"
              >Puerto SSH (Default 22)</small
            >
          </div>
        </div>

        <div class="grid-2">
          <div>
            <label>Método de conexión</label>
            <select v-model="addForm.connection_method">
              <option value="vpn">A través de Perfil VPN</option>
              <option value="maestro">A través de Maestro existente</option>
            </select>
          </div>
          <div v-if="addForm.connection_method === 'vpn'">
            <label>Perfil VPN</label>
            <select v-model="addForm.vpn_profile_id" required>
              <option :value="null" disabled>-- Selecciona VPN --</option>
              <option v-for="vpn in vpnProfiles" :key="vpn.id" :value="vpn.id">
                {{ vpn.name }}
              </option>
            </select>

            <label style="margin-top: 0.8rem">Perfil de Credenciales</label>
            <select v-model="addForm.credential_id">
              <option :value="null">-- Auto-detectar (Lento) --</option>
              <option v-for="cred in credentialProfiles" :key="cred.id" :value="cred.id">
                {{ cred.name }} ({{ cred.username }})
              </option>
            </select>
          </div>

          <div v-if="addForm.connection_method === 'maestro'">
            <label>Maestro</label>
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
            :disabled="isTesting"
          >
            {{ isTesting ? 'Probando...' : 'Probar conexión' }}
          </button>
        </div>

        <div v-if="testResult" class="test-box" :class="testResult.reachable ? 'ok' : 'error'">
          {{
            testResult.reachable
              ? '✅ Alcanzable'
              : '❌ No alcanzable: ' + (testResult.detail || '')
          }}
        </div>
      </form>
    </section>

    <section v-if="currentTab === 'manage'" class="control-section fade-in">
      <div class="manage-header">
        <h2><i class="icon">👑</i> Inventario</h2>

        <div v-if="selectedDevices.length > 0" class="bulk-actions-wrapper fade-in">
          <button @click="openBulkModal" class="btn-bulk btn-warning">
            ⚡ Configurar Monitores ({{ selectedDevices.length }})
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
                {{ device.ip_address
                }}<span
                  v-if="device.api_port && device.api_port !== 8728 && device.api_port !== 22"
                  class="text-dim"
                  >:{{ device.api_port }}</span
                >
              </td>
              <td>
                {{ device.vendor || 'Generico' }}
              </td>
              <td>
                <span :class="['badge', getDeviceRole(device).class]">{{
                  getDeviceRole(device).label
                }}</span>
              </td>
              <td>
                <div v-if="device.is_maestro">
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
                <div v-else class="text-dim">-</div>
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
                    
                    <button class="dropdown-item" @click="openTerminalSetup(device)">
                      <span class="icon">💻</span> Smart Terminal
                    </button>

                    <button 
                      v-if="!device.is_maestro && device.credential_id" 
                      class="dropdown-item" 
                      @click="promoteToMaestro(device)"
                    >
                      <span class="icon">⬆️</span> Promover Maestro
                    </button>

                    <button class="dropdown-item text-warning" @click="openRotateCredentialsModal(device)">
                      <span class="icon">🔑</span> Rotar Credenciales
                    </button>

                    <button class="dropdown-item text-danger" @click="requestReboot(device)" :disabled="isRebooting">
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

    <div v-if="showBulkModal" class="modal-overlay">
      <div class="modal-content large-modal">
        <h3>⚡ Crear Monitores Masivos</h3>

        <div class="compatibility-box" :class="bulkCompatibility.isPartial ? 'warning' : 'ok'">
          {{ bulkCompatibility.message }}
        </div>

        <div class="bulk-form">
          <div class="form-group">
            <label>Tipo de Sensor</label>
            <div class="sensor-type-selector">
              <button
                :class="{ active: bulkSensorType === 'ping' }"
                @click="bulkSensorType = 'ping'"
              >
                PING (ICMP)
              </button>
              <button
                :class="{ active: bulkSensorType === 'ethernet' }"
                @click="bulkSensorType = 'ethernet'"
              >
                ETHERNET (Tráfico)
              </button>
            </div>
          </div>

          <div class="form-group">
            <label>Plantilla de Nombre</label>
            <input v-model="bulkNameTemplate" placeholder="{{hostname}} - Sensor" />
            <small
              >Variables: <code v-pre>{{ hostname }}</code
              >, <code v-pre>{{ ip }}</code></small
            >
          </div>

          <hr class="separator" />

          <div v-if="bulkSensorType === 'ping'" class="config-grid">
            <div class="form-group">
              <label>Destino (Fallback si no es P2P)</label>
              <div style="position: relative">
                <input
                  list="bulk-target-devices"
                  type="text"
                  v-model="bulkPingConfig.config.target_ip"
                  placeholder="Ej: 8.8.8.8 o selecciona de la lista"
                  class="search-input"
                />
                <datalist id="bulk-target-devices">
                  <option
                    v-for="d in suggestedTargetDevicesForBulk"
                    :key="d.id"
                    :value="d.ip_address"
                  >
                    {{ d.client_name }}
                  </option>
                </datalist>
              </div>
            </div>
            <div class="form-group">
              <label>Intervalo (s)</label>
              <input type="number" v-model.number="bulkPingConfig.config.interval_sec" />
            </div>

            <div class="alert-section span-2">
              <h4>Alertas</h4>

              <div class="alert-row">
                <div class="chk-label">
                  <input type="checkbox" v-model="bulkPingConfig.ui_alert_timeout.enabled" />
                  Timeout
                </div>
                <select
                  v-model="bulkPingConfig.ui_alert_timeout.channel_id"
                  :disabled="!bulkPingConfig.ui_alert_timeout.enabled"
                >
                  <option :value="null">-- Canal --</option>
                  <option v-for="c in channels" :key="c.id" :value="c.id">{{ c.name }}</option>
                </select>
                <span class="small-label">Tolerancia a Fallos:</span>
                <input
                  type="number"
                  placeholder="Tolerancia a Fallos"
                  v-model.number="bulkPingConfig.ui_alert_timeout.tolerance_count"
                  class="tiny-input"
                />
                <label class="tiny-chk"
                  ><input
                    type="checkbox"
                    v-model="bulkPingConfig.ui_alert_timeout.notify_recovery"
                  />
                  Recup.</label
                >
              </div>

              <div class="alert-row">
                <div class="chk-label">
                  <input type="checkbox" v-model="bulkPingConfig.ui_alert_latency.enabled" />
                  Latencia > {{ bulkPingConfig.ui_alert_latency.threshold_ms }}ms
                </div>
                <select
                  v-model="bulkPingConfig.ui_alert_latency.channel_id"
                  :disabled="!bulkPingConfig.ui_alert_latency.enabled"
                >
                  <option :value="null">-- Canal --</option>
                  <option v-for="c in channels" :key="c.id" :value="c.id">{{ c.name }}</option>
                </select>
                <span class="small-label">Tolerancia a Fallos:</span>
                <input
                  type="number"
                  placeholder="Tolerancia a Fallos"
                  v-model.number="bulkPingConfig.ui_alert_latency.tolerance_count"
                  class="tiny-input"
                />
                <label class="tiny-chk"
                  ><input
                    type="checkbox"
                    v-model="bulkPingConfig.ui_alert_latency.notify_recovery"
                  />
                  Recup.</label
                >
              </div>
            </div>
          </div>

          <div v-if="bulkSensorType === 'ethernet'" class="config-grid">
            <div class="form-group">
              <label>Interfaz</label>
              <input v-model="bulkEthernetConfig.config.interface_name" placeholder="ether1" />
            </div>
            <div class="form-group">
              <label>Intervalo (s)</label>
              <input type="number" v-model.number="bulkEthernetConfig.config.interval_sec" />
            </div>

            <div class="alert-section span-2">
              <h4>Alertas</h4>

              <div class="alert-row">
                <div class="chk-label">
                  <input
                    type="checkbox"
                    v-model="bulkEthernetConfig.ui_alert_speed_change.enabled"
                  />
                  Cambio Velocidad
                </div>
                <select
                  v-model="bulkEthernetConfig.ui_alert_speed_change.channel_id"
                  :disabled="!bulkEthernetConfig.ui_alert_speed_change.enabled"
                >
                  <option :value="null">-- Canal --</option>
                  <option v-for="c in channels" :key="c.id" :value="c.id">{{ c.name }}</option>
                </select>
                <span class="small-label">Tolerancia a Fallos:</span>
                <input
                  type="number"
                  placeholder="Tolerancia a Fallos"
                  v-model.number="bulkEthernetConfig.ui_alert_speed_change.tolerance_count"
                  class="tiny-input"
                />
                <label class="tiny-chk"
                  ><input
                    type="checkbox"
                    v-model="bulkEthernetConfig.ui_alert_speed_change.notify_recovery"
                  />
                  Recup.</label
                >
              </div>

              <div class="alert-row">
                <div class="chk-label">
                  <input type="checkbox" v-model="bulkEthernetConfig.ui_alert_traffic.enabled" />
                  Tráfico > {{ bulkEthernetConfig.ui_alert_traffic.threshold_mbps }}Mbps
                </div>
                <select
                  v-model="bulkEthernetConfig.ui_alert_traffic.channel_id"
                  :disabled="!bulkEthernetConfig.ui_alert_traffic.enabled"
                >
                  <option :value="null">-- Canal --</option>
                  <option v-for="c in channels" :key="c.id" :value="c.id">{{ c.name }}</option>
                </select>
                <span class="small-label">Tolerancia a Fallos:</span>
                <input
                  type="number"
                  placeholder="Tolerancia a Fallos"
                  v-model.number="bulkEthernetConfig.ui_alert_traffic.tolerance_count"
                  class="tiny-input"
                />
                <label class="tiny-chk"
                  ><input
                    type="checkbox"
                    v-model="bulkEthernetConfig.ui_alert_traffic.notify_recovery"
                  />
                  Recup.</label
                >
              </div>
            </div>
          </div>

          <div class="form-group checkbox" style="margin-top: 1rem">
            <label>
              <input
                type="checkbox"
                v-model="
                  (bulkSensorType === 'ping' ? bulkPingConfig : bulkEthernetConfig).is_active
                "
              />
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
}
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
   ESTILOS BARRA DE FILTROS (NUEVOS)
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

/* ESTILOS TABLE & BULK */
.manage-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}
.bulk-actions-wrapper {
  display: flex;
  gap: 0.5rem;
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
  overflow-x: visible; /* Cambiado para no ocultar dropdowns */
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

/* MODALES */
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
  width: 700px;
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
.alert-section {
  background: rgba(0, 0, 0, 0.2);
  padding: 1rem;
  border-radius: 6px;
  margin-top: 0.5rem;
}
.span-2 {
  grid-column: span 2;
}
.alert-row {
  display: flex;
  align-items: center;
  gap: 0.8rem;
  margin-bottom: 0.8rem;
}
.alert-row:last-child {
  margin-bottom: 0;
}
.chk-label {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.9rem;
}
.small-label {
  font-size: 0.8rem;
  color: #aaa;
  white-space: nowrap;
}
.tiny-input {
  width: 60px !important;
  padding: 0.4rem !important;
}
.tiny-chk {
  font-size: 0.8rem;
  display: flex;
  align-items: center;
  gap: 0.3rem;
  font-weight: normal;
  color: #ccc;
}
.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 1rem;
  margin-top: 2rem;
}

/* BITÁCORA STYLES */
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
</style>