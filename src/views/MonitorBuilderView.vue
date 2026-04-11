<script setup>
import { ref, watch, onMounted, computed } from 'vue'
import api from '@/lib/api'
import SensorConfigurator from '@/components/SensorConfigurator.vue' // <-- NUEVO COMPONENTE IMPORTADO

//
// --- Estado General ---
const searchQuery = ref('')
const searchResults = ref([])
const isLoading = ref(false)
const selectedDevice = ref(null)
const allMonitors = ref([])
const currentMonitor = ref(null)
const activeSensors = ref([])
const notification = ref({ show: false, message: '', type: 'success' })
const formToShow = ref(null)
const channels = ref([])
const autoTasks = ref([]) // NUEVO: Tareas programadas/manuales disponibles

// --- Nuevo Estado para Grupo ---
const dbGroups = ref([]) // Grupos traídos de la API
const selectedGroupOption = ref('') // Dropdown
const customGroupName = ref('') // Input manual

// --- Estado para Edición ---
const sensorToEdit = ref(null)
const isEditMode = ref(false)

// --- Estado para Selector de Destino (Ping) ---
const allDevicesList = ref([]) // Lista completa para el selector de destino

// --- NUEVO ESTADO PARA INTERFACES ---
const deviceInterfaces = ref([])
const isLoadingInterfaces = ref(false)

// --- COMPUTADO: Validación de Maestro ---
const hasParentMaestro = computed(() => {
  return !!selectedDevice.value?.maestro_id
})

// --- COMPUTADO: Grupos Disponibles ---
const availableGroups = computed(() => {
  // Inicializamos con los grupos traídos de la DB
  const groups = new Set(dbGroups.value)

  // Por seguridad, agregamos también los que estén en uso en monitores cargados
  if (Array.isArray(allMonitors.value)) {
    allMonitors.value.forEach((m) => {
      const g = m.group_name ? m.group_name.trim() : null
      if (g && g !== 'General') {
        groups.add(g)
      }
    })
  }
  // Convertimos a array y ordenamos alfabéticamente
  return Array.from(groups).sort()
})

// --- COMPUTADO: Dispositivos Sugeridos para Destino (Filtrado Inteligente) ---
const suggestedTargetDevices = computed(() => {
  if (!selectedDevice.value) return []

  // 1. Identificar el contexto de red del dispositivo seleccionado
  let currentVpnId = selectedDevice.value.vpn_profile_id

  // Si tiene maestro, usamos el perfil del maestro (ya que es quien enruta)
  if (selectedDevice.value.maestro_id) {
    const maestro = allDevicesList.value.find((d) => d.id === selectedDevice.value.maestro_id)
    if (maestro) {
      currentVpnId = maestro.vpn_profile_id
    }
  }

  // 2. Filtrar dispositivos que compartan ese contexto
  return allDevicesList.value.filter((d) => {
    // Excluirse a sí mismo
    if (d.id === selectedDevice.value.id) return false

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

//
// --- Plantillas de Formularios (ACTUALIZADO: Mensajes Personalizados y Auto-Tasks) ---
const createNewPingSensor = () => ({
  name: '',
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
    use_auto_task: false, // NUEVO
    trigger_task_id: null, // NUEVO
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
    use_auto_task: false, // NUEVO
    trigger_task_id: null, // NUEVO
  },
})

const createNewEthernetSensor = () => ({
  name: '',
  config: {
    interface_name: '',
    interval_sec: 60,
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
    use_auto_task: false, // NUEVO
    trigger_task_id: null, // NUEVO
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
    use_auto_task: false, // NUEVO
    trigger_task_id: null, // NUEVO
  },
})

const createNewWirelessSensor = () => ({
  name: '',
  config: {
    interface_name: '',
    interval_sec: 60, // <-- AÑADIDO
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
    use_auto_task: false, // NUEVO
    trigger_task_id: null, // NUEVO
  },
})

const createNewSystemSensor = () => ({
  name: '',
  config: {
    interval_sec: 60, // <-- AÑADIDO
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
    use_auto_task: false, // NUEVO
    trigger_task_id: null, // NUEVO
  },
})

const newPingSensor = ref(createNewPingSensor())
const newEthernetSensor = ref(createNewEthernetSensor())
const newWirelessSensor = ref(createNewWirelessSensor())
const newSystemSensor = ref(createNewSystemSensor())

//
// --- Ciclo de Vida ---
onMounted(() => {
  fetchGroups()
  fetchAllMonitors()
  fetchChannels()
  fetchAllDevices() 
  fetchAutoTasks() // NUEVO: Cargar las tareas para los selectores
})

// RESETEO
watch(selectedDevice, () => {
  newPingSensor.value = createNewPingSensor()
  if (!hasParentMaestro.value) {
    newPingSensor.value.config.ping_type = 'device_to_external'
  }
})

function showNotification(message, type = 'success') {
  notification.value = { show: true, message, type }
  setTimeout(() => {
    notification.value.show = false
  }, 4000)
}

async function fetchChannels() {
  try {
    const { data } = await api.get('/channels')
    channels.value = (data || []).map((ch) => ({
      ...ch,
      config: typeof ch.config === 'string' ? safeJsonParse(ch.config) : ch.config,
    }))
  } catch (err) {
    console.error('Error al cargar canales:', err)
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

async function fetchGroups() {
  try {
    const { data } = await api.get('/groups')
    dbGroups.value = data.map((g) => g.name)
  } catch (err) {
    console.error('Error fetching groups:', err)
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

// --- NUEVO: Obtener Interfaces del Dispositivo Activo ---
async function fetchDeviceInterfaces(deviceId) {
  isLoadingInterfaces.value = true;
  deviceInterfaces.value = [];
  try {
    const { data } = await api.get(`/devices/${deviceId}/interfaces`);
    deviceInterfaces.value = data || [];
  } catch (e) {
    console.warn(`No se pudieron cargar las interfaces para el equipo ${deviceId}. Fallback a input manual.`);
    deviceInterfaces.value = []; // Queda vacío para activar el fallback manual
  } finally {
    isLoadingInterfaces.value = false;
  }
}

function safeJsonParse(v, fallback = null) {
  try {
    return JSON.parse(v)
  } catch {
    return fallback
  }
}

//
// --- Lógica Sensores ---
function buildSensorPayload(sensorType, sensorData) {
  const finalConfig = { ...sensorData.config }
  finalConfig.alerts = []
  const onlyNums = (v, fallback = undefined) => (typeof v === 'number' && !isNaN(v) ? v : fallback)

  if (sensorType === 'ping') {
    if (!hasParentMaestro.value) {
      finalConfig.ping_type = 'device_to_external'
    }
    if (sensorData.ui_alert_timeout.enabled) {
      const a = sensorData.ui_alert_timeout
      if (!a.channel_id) throw new Error('Selecciona un canal para la alerta de Timeout.')
      const alertObj = {
        type: 'timeout',
        channel_id: a.channel_id,
        cooldown_minutes: onlyNums(a.cooldown_minutes, 5),
        tolerance_count: Math.max(1, onlyNums(a.tolerance_count, 1)),
        notify_recovery: !!a.notify_recovery,
      }
      if (a.use_custom_message && a.custom_message?.trim()) alertObj.custom_message = a.custom_message.trim()
      if (a.use_custom_recovery_message && a.custom_recovery_message?.trim()) alertObj.custom_recovery_message = a.custom_recovery_message.trim()
      if (a.use_auto_task && a.trigger_task_id) alertObj.trigger_task_id = a.trigger_task_id // NUEVO
      finalConfig.alerts.push(alertObj)
    }
    if (sensorData.ui_alert_latency.enabled) {
      const a = sensorData.ui_alert_latency
      if (!a.channel_id) throw new Error('Selecciona un canal para la alerta de Latencia.')
      const alertObj = {
        type: 'high_latency',
        threshold_ms: onlyNums(a.threshold_ms, 200),
        channel_id: a.channel_id,
        cooldown_minutes: onlyNums(a.cooldown_minutes, 5),
        tolerance_count: Math.max(1, onlyNums(a.tolerance_count, 1)),
        notify_recovery: !!a.notify_recovery,
      }
      if (a.use_custom_message && a.custom_message?.trim()) alertObj.custom_message = a.custom_message.trim()
      if (a.use_custom_recovery_message && a.custom_recovery_message?.trim()) alertObj.custom_recovery_message = a.custom_recovery_message.trim()
      if (a.use_auto_task && a.trigger_task_id) alertObj.trigger_task_id = a.trigger_task_id // NUEVO
      finalConfig.alerts.push(alertObj)
    }
  } else if (sensorType === 'ethernet') {
    if (sensorData.ui_alert_speed_change.enabled) {
      const a = sensorData.ui_alert_speed_change
      if (!a.channel_id) throw new Error('Selecciona un canal para la alerta de Cambio de Velocidad.')
      const alertObj = {
        type: 'speed_change',
        channel_id: a.channel_id,
        cooldown_minutes: onlyNums(a.cooldown_minutes, 10),
        tolerance_count: Math.max(1, onlyNums(a.tolerance_count, 1)),
        notify_recovery: !!a.notify_recovery,
      }
      if (a.use_custom_message && a.custom_message?.trim()) alertObj.custom_message = a.custom_message.trim()
      if (a.use_custom_recovery_message && a.custom_recovery_message?.trim()) alertObj.custom_recovery_message = a.custom_recovery_message.trim()
      if (a.use_auto_task && a.trigger_task_id) alertObj.trigger_task_id = a.trigger_task_id // NUEVO
      finalConfig.alerts.push(alertObj)
    }
    if (sensorData.ui_alert_traffic.enabled) {
      const a = sensorData.ui_alert_traffic
      if (!a.channel_id) throw new Error('Selecciona un canal para la alerta de Umbral de Tráfico.')
      const alertObj = {
        type: 'traffic_threshold',
        threshold_mbps: onlyNums(a.threshold_mbps, 100),
        direction: a.direction || 'any',
        channel_id: a.channel_id,
        cooldown_minutes: onlyNums(a.cooldown_minutes, 5),
        tolerance_count: Math.max(1, onlyNums(a.tolerance_count, 1)),
        notify_recovery: !!a.notify_recovery,
      }
      if (a.use_custom_message && a.custom_message?.trim()) alertObj.custom_message = a.custom_message.trim()
      if (a.use_custom_recovery_message && a.custom_recovery_message?.trim()) alertObj.custom_recovery_message = a.custom_recovery_message.trim()
      if (a.use_auto_task && a.trigger_task_id) alertObj.trigger_task_id = a.trigger_task_id // NUEVO
      finalConfig.alerts.push(alertObj)
    }
  } else if (sensorType === 'wireless') {
    finalConfig.thresholds = {
      min_signal_dbm: onlyNums(sensorData.config.thresholds.min_signal_dbm, -80),
      min_ccq_percent: onlyNums(sensorData.config.thresholds.min_ccq_percent, 75),
      min_client_count: onlyNums(sensorData.config.thresholds.min_client_count, 0),
      min_tx_rate_mbps: onlyNums(sensorData.config.thresholds.min_tx_rate_mbps, 0),
      min_rx_rate_mbps: onlyNums(sensorData.config.thresholds.min_rx_rate_mbps, 0),
    }
    finalConfig.tolerance_checks = Math.max(1, onlyNums(sensorData.config.tolerance_checks, 3))

    if (sensorData.ui_alert_status?.enabled) {
      const a = sensorData.ui_alert_status
      if (!a.channel_id) throw new Error('Selecciona un canal para la alerta Inalámbrica.')
      const alertObj = {
        type: 'wireless_status',
        channel_id: a.channel_id,
        cooldown_minutes: onlyNums(a.cooldown_minutes, 10),
        notify_recovery: !!a.notify_recovery,
      }
      if (a.use_custom_message && a.custom_message?.trim()) alertObj.custom_message = a.custom_message.trim()
      if (a.use_custom_recovery_message && a.custom_recovery_message?.trim()) alertObj.custom_recovery_message = a.custom_recovery_message.trim()
      if (a.use_auto_task && a.trigger_task_id) alertObj.trigger_task_id = a.trigger_task_id // NUEVO
      finalConfig.alerts.push(alertObj)
    }
  } else if (sensorType === 'system') {
    finalConfig.thresholds = {
      max_cpu_percent: onlyNums(sensorData.config.thresholds.max_cpu_percent, null),
      max_memory_percent: onlyNums(sensorData.config.thresholds.max_memory_percent, null),
      max_temperature: onlyNums(sensorData.config.thresholds.max_temperature, null),
      min_voltage: onlyNums(sensorData.config.thresholds.min_voltage, null),
      max_voltage: onlyNums(sensorData.config.thresholds.max_voltage, null),
      restart_uptime_seconds: onlyNums(sensorData.config.thresholds.restart_uptime_seconds, 300),
    }
    finalConfig.tolerance_checks = Math.max(1, onlyNums(sensorData.config.tolerance_checks, 3))

    if (sensorData.ui_alert_status?.enabled) {
      const a = sensorData.ui_alert_status
      if (!a.channel_id) throw new Error('Selecciona un canal para la alerta de Sistema.')
      const alertObj = {
        type: 'system_status',
        channel_id: a.channel_id,
        cooldown_minutes: onlyNums(a.cooldown_minutes, 10),
        notify_recovery: !!a.notify_recovery,
      }
      if (a.use_custom_message && a.custom_message?.trim()) alertObj.custom_message = a.custom_message.trim()
      if (a.use_custom_recovery_message && a.custom_recovery_message?.trim()) alertObj.custom_recovery_message = a.custom_recovery_message.trim()
      if (a.use_auto_task && a.trigger_task_id) alertObj.trigger_task_id = a.trigger_task_id // NUEVO
      finalConfig.alerts.push(alertObj)
    }
  }
  return { name: sensorData.name, config: finalConfig }
}

async function handleSaveSensor() {
  if (!formToShow.value) return
  
  const sensorData = formToShow.value === 'ping' 
    ? newPingSensor.value 
    : formToShow.value === 'ethernet' 
      ? newEthernetSensor.value 
      : formToShow.value === 'wireless'
        ? newWirelessSensor.value
        : newSystemSensor.value

  try {
    const payload = buildSensorPayload(formToShow.value, sensorData)
    if (isEditMode.value && sensorToEdit.value) {
      const { data } = await api.put(`/sensors/${sensorToEdit.value.id}`, payload)
      const idx = activeSensors.value.findIndex((s) => s.id === sensorToEdit.value.id)
      if (idx !== -1) {
        activeSensors.value[idx] = {
          ...activeSensors.value[idx],
          ...data,
          config: typeof data.config === 'string' ? safeJsonParse(data.config, {}) : data.config,
        }
      }
      showNotification('Sensor actualizado.', 'success')
    } else {
      if (!currentMonitor.value?.monitor_id) {
        showNotification('Primero crea la tarjeta de monitoreo.', 'error')
        return
      }
      const createPayload = {
        monitor_id: currentMonitor.value.monitor_id,
        sensor_type: formToShow.value,
        ...payload,
      }
      const { data } = await api.post('/sensors', createPayload)
      activeSensors.value.push({
        ...data,
        config: typeof data.config === 'string' ? safeJsonParse(data.config, {}) : data.config,
      })
      showNotification('Sensor añadido.', 'success')
    }
    await selectDevice(selectedDevice.value)
    closeForm()
  } catch (err) {
    showNotification(err?.message || 'Error al guardar el sensor.', 'error')
  }
}

function openFormForCreate(type) {
  isEditMode.value = false
  sensorToEdit.value = null
  newPingSensor.value = createNewPingSensor()
  newEthernetSensor.value = createNewEthernetSensor()
  newWirelessSensor.value = createNewWirelessSensor()
  newSystemSensor.value = createNewSystemSensor()
  
  if (type === 'ping' && !hasParentMaestro.value) {
    newPingSensor.value.config.ping_type = 'device_to_external'
  }
  formToShow.value = type
}

function openFormForEdit(sensor) {
  isEditMode.value = true
  sensorToEdit.value = sensor
  const cfg = typeof sensor.config === 'string' ? safeJsonParse(sensor.config, {}) : sensor.config

  // Helper para mapear alerta
  const mapAlert = (alerts, type) => alerts.find((a) => a.type === type) || {}
  const alerts = cfg?.alerts || []

  if (sensor.sensor_type === 'ping') {
    const uiData = createNewPingSensor()
    uiData.name = sensor.name
    uiData.config = { ...uiData.config, ...cfg }
    if (!hasParentMaestro.value) uiData.config.ping_type = 'device_to_external'

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
        use_auto_task: !!tOut.trigger_task_id, // NUEVO
        trigger_task_id: tOut.trigger_task_id || null, // NUEVO
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
        use_auto_task: !!tLat.trigger_task_id, // NUEVO
        trigger_task_id: tLat.trigger_task_id || null, // NUEVO
      }
    }
    newPingSensor.value = uiData

  } else if (sensor.sensor_type === 'ethernet') {
    const uiData = createNewEthernetSensor()
    uiData.name = sensor.name
    uiData.config = {
      interface_name: cfg.interface_name || '',
      interval_sec: cfg.interval_sec || 60, // <-- Edit: Carga correcta
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
        use_auto_task: !!tSpd.trigger_task_id, // NUEVO
        trigger_task_id: tSpd.trigger_task_id || null, // NUEVO
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
        use_auto_task: !!tTrf.trigger_task_id, // NUEVO
        trigger_task_id: tTrf.trigger_task_id || null, // NUEVO
      }
    }
    newEthernetSensor.value = uiData

  } else if (sensor.sensor_type === 'wireless') {
    const uiData = createNewWirelessSensor()
    uiData.name = sensor.name
    uiData.config = {
      interface_name: cfg.interface_name || '',
      interval_sec: cfg.interval_sec || 60, // <-- Edit: AÑADIDO
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
        use_auto_task: !!tWir.trigger_task_id, // NUEVO
        trigger_task_id: tWir.trigger_task_id || null, // NUEVO
      }
    }
    newWirelessSensor.value = uiData

  } else if (sensor.sensor_type === 'system') {
    const uiData = createNewSystemSensor()
    uiData.name = sensor.name
    uiData.config = {
      interval_sec: cfg.interval_sec || 60, // <-- Edit: AÑADIDO
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
        use_auto_task: !!tSys.trigger_task_id, // NUEVO
        trigger_task_id: tSys.trigger_task_id || null, // NUEVO
      }
    }
    newSystemSensor.value = uiData
  }
  
  formToShow.value = sensor.sensor_type
}

function closeForm() {
  formToShow.value = null
  sensorToEdit.value = null
  isEditMode.value = false
}

async function fetchAllMonitors() {
  try {
    const { data } = await api.get('/monitors')
    allMonitors.value = Array.isArray(data) ? data : []
  } catch (err) {
    console.error('Error fetching monitors:', err)
  }
}

async function selectDevice(device) {
  selectedDevice.value = device
  searchQuery.value = ''
  searchResults.value = []
  selectedGroupOption.value = ''
  customGroupName.value = ''

  // Despachamos la carga de interfaces en background
  fetchDeviceInterfaces(device.id);

  await fetchAllMonitors()
  const monitor = allMonitors.value.find((m) => m.device_id === device.id)
  if (monitor) {
    currentMonitor.value = monitor
    activeSensors.value = Array.isArray(monitor.sensors)
      ? monitor.sensors.map((s) => ({
          ...s,
          config: typeof s.config === 'string' ? safeJsonParse(s.config, {}) : s.config,
        }))
      : []
  } else {
    currentMonitor.value = null
    activeSensors.value = []
  }
}

function clearSelectedDevice() {
  selectedDevice.value = null
  currentMonitor.value = null
  activeSensors.value = []
  deviceInterfaces.value = [] // Limpiamos las interfaces en cache
  closeForm()
}

async function createMonitorCard() {
  if (!selectedDevice.value) return

  let finalGroupName = ''
  if (selectedGroupOption.value === '__NEW__') {
    finalGroupName = customGroupName.value.trim()
  } else {
    finalGroupName = selectedGroupOption.value
  }
  if (!finalGroupName) finalGroupName = 'General'

  try {
    await api.post('/monitors', {
      device_id: selectedDevice.value.id,
      group_name: finalGroupName,
    })
    showNotification('Tarjeta creada con éxito.', 'success')
    await fetchGroups()
    await selectDevice(selectedDevice.value)
  } catch (err) {
    showNotification(err?.response?.data?.detail || 'Error al crear la tarjeta.', 'error')
  }
}

async function deleteSensor(sensorId) {
  if (!confirm('¿Eliminar sensor?')) return
  try {
    await api.delete(`/sensors/${sensorId}`)
    activeSensors.value = activeSensors.value.filter((s) => s.id !== sensorId)
    showNotification('Sensor eliminado.', 'success')
  } catch (err) {
    console.error(err)
    showNotification('Error al eliminar.', 'error')
  }
}

let searchDebounce = null
watch(searchQuery, (newQuery) => {
  clearTimeout(searchDebounce)
  if (newQuery.length < 2) {
    searchResults.value = []
    return
  }
  isLoading.value = true
  searchDebounce = setTimeout(async () => {
    try {
      const { data } = await api.get('/devices/search', { params: { search: newQuery } })
      searchResults.value = data
    } catch {
      /* ignore */
    } finally {
      isLoading.value = false
    }
  }, 350)
})
</script>

<template>
  <div>
    <div v-if="notification.show" :class="['notification', notification.type]">
      {{ notification.message }}
    </div>
    <div class="builder-layout">
      <section class="builder-step">
        <h2><span class="step-number">1</span> Seleccionar Dispositivo</h2>
        <div v-if="!selectedDevice">
          <div class="search-wrapper">
            <input
              type="text"
              v-model="searchQuery"
              placeholder="Buscar dispositivo..."
              class="search-input"
            />
          </div>
          <ul v-if="searchResults.length > 0" class="search-results">
            <li v-for="device in searchResults" :key="device.id" @click="selectDevice(device)">
              <strong>{{ device.client_name }}</strong>
              <span>{{ device.ip_address }}</span>
            </li>
          </ul>
        </div>
        <div v-else class="selected-device-card">
          <div>
            <h3>{{ selectedDevice.client_name }}</h3>
            <p>
              {{ selectedDevice.ip_address }}
              <span v-if="selectedDevice.is_maestro" class="maestro-badge">MAESTRO</span>
            </p>
          </div>
          <button @click="clearSelectedDevice">Cambiar</button>
        </div>
      </section>

      <section v-if="selectedDevice" class="builder-step">
        <div v-if="!currentMonitor">
          <h2><span class="step-number">2</span> Crear Tarjeta de Monitoreo</h2>

          <div class="form-group" style="margin-bottom: 1rem">
            <label>Asignar Grupo</label>
            <select v-model="selectedGroupOption" class="search-input">
              <option value="">-- Grupo General / Sin Grupo --</option>

              <option v-for="g in availableGroups" :key="g" :value="g">
                {{ g }}
              </option>

              <option disabled>──────────────────</option>
              <option value="__NEW__">➕ Crear Nuevo Grupo...</option>
            </select>
          </div>

          <div
            v-if="selectedGroupOption === '__NEW__'"
            class="form-group"
            style="margin-bottom: 1rem"
          >
            <label>Nombre del Nuevo Grupo</label>
            <input
              type="text"
              v-model="customGroupName"
              placeholder="Ej: Sucursal Norte"
              class="search-input"
            />
          </div>

          <button @click="createMonitorCard" class="btn-create">Crear Tarjeta</button>
        </div>
        <div v-else>
          <h2><span class="step-number">2</span> Gestionar Sensores</h2>
          
          <div class="add-sensor-section">
            <h4>Añadir Nuevo Sensor</h4>
            <div class="sensor-type-selector">
              <button @click="openFormForCreate('ping')">Añadir Ping</button>
              <button @click="openFormForCreate('ethernet')">Añadir Ethernet</button>
              <button @click="openFormForCreate('wireless')">Añadir Wireless 📡</button>
              <button @click="openFormForCreate('system')">Añadir Sistema 💻</button>
            </div>
          </div>

          <div class="sensor-list">
            <h4>Sensores Activos ({{ activeSensors.length }})</h4>
            <ul v-if="activeSensors.length > 0">
              <li v-for="sensor in activeSensors" :key="sensor.id">
                <div class="sensor-info">
                  <strong :title="sensor.name">{{ sensor.name }}</strong>
                </div>
                <div class="sensor-actions">
                  <span v-if="sensor.config?.alerts?.length" class="alert-enabled-badge" title="Alerta configurada">🔔</span>
                  <span class="sensor-type-badge" :class="sensor.sensor_type">{{
                    sensor.sensor_type
                  }}</span>
                  <button @click="openFormForEdit(sensor)" class="action-btn edit-btn" title="Editar Sensor">✏️</button>
                  <button @click="deleteSensor(sensor.id)" class="action-btn delete-btn" title="Eliminar Sensor">×</button>
                </div>
              </li>
            </ul>
            <p v-else class="empty-list">No hay sensores configurados.</p>
          </div>
        </div>
      </section>
    </div>

    <div v-if="formToShow" class="modal-overlay" @click.self="closeForm">
      <div class="modal-content">
        <h3>{{ isEditMode ? 'Editar' : 'Añadir' }} Sensor {{ formToShow.toUpperCase() }}</h3>

        <form @submit.prevent="handleSaveSensor" class="config-form-wrapper">
          
          <SensorConfigurator
            v-if="formToShow === 'ping'"
            v-model="newPingSensor"
            sensor-type="ping"
            :channels="channels"
            :auto-tasks="autoTasks"
            :suggested-target-devices="suggestedTargetDevices"
            :has-parent-maestro="hasParentMaestro"
          />

          <SensorConfigurator
            v-else-if="formToShow === 'ethernet'"
            v-model="newEthernetSensor"
            sensor-type="ethernet"
            :channels="channels"
            :auto-tasks="autoTasks"
            :device-interfaces="deviceInterfaces"
            :is-loading-interfaces="isLoadingInterfaces"
          />

          <SensorConfigurator
            v-else-if="formToShow === 'wireless'"
            v-model="newWirelessSensor"
            sensor-type="wireless"
            :channels="channels"
            :auto-tasks="autoTasks"
            :device-interfaces="deviceInterfaces"
            :is-loading-interfaces="isLoadingInterfaces"
          />

          <SensorConfigurator
            v-else-if="formToShow === 'system'"
            v-model="newSystemSensor"
            sensor-type="system"
            :channels="channels"
            :auto-tasks="autoTasks"
          />

          <div class="modal-actions">
            <button type="button" @click="closeForm" class="btn-secondary">Cancelar</button>
            <button type="submit" class="btn-add">Guardar</button>
          </div>
        </form>

      </div>
    </div>
  </div>
</template>

<style scoped>
/* Estilos necesarios para corregir la visibilidad del Select */
.search-input option {
  background-color: var(--surface-color); /* Fondo oscuro para las opciones */
  color: white; /* Texto blanco */
}

/* Permitir cambiar el alto manualmente del área de texto personalizado */
textarea.search-input {
  resize: vertical;
  min-height: 60px;
}

/* Resto de estilos */
.builder-layout {
  max-width: 900px;
  margin: auto;
  display: flex;
  flex-direction: column;
  gap: 2rem;
}
.builder-step {
  background-color: var(--surface-color);
  padding: 2rem;
  border-radius: 12px;
}
.step-number {
  background-color: var(--blue);
  color: white;
  border-radius: 50%;
  width: 30px;
  height: 30px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
  margin-right: 1rem;
}
h2,
h4 {
  color: #f1f1f1;
}
.maestro-badge {
  background-color: var(--blue);
  color: white;
  font-size: 0.7rem;
  padding: 2px 6px;
  border-radius: 4px;
  margin-left: 8px;
  font-weight: bold;
}
.warning-text {
  color: #fbbf24;
  font-size: 0.85rem;
  margin-top: 0.5rem;
  font-weight: 500;
}
.search-wrapper {
  position: relative;
}
.search-input {
  width: 100%;
  padding: 0.8rem;
  background-color: var(--bg-color);
  border: 1px solid var(--primary-color);
  border-radius: 6px;
  color: white;
}

/* ==============================================
   FIX: TRUNCADO PROFESIONAL PARA LISTAS Y TARJETAS
   ============================================== */

/* 1. Resultados de búsqueda blindados */
.search-results {
  list-style: none;
  padding: 0;
  margin-top: 0.5rem;
}
.search-results li {
  padding: 0.8rem;
  background-color: var(--bg-color);
  border-radius: 6px;
  margin-bottom: 0.5rem;
  cursor: pointer;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem; /* Espaciado entre nombre e IP */
  transition: background-color 0.2s;
}
.search-results li:hover {
  background-color: var(--primary-color);
}
.search-results li strong {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 1;
  min-width: 0;
}
.search-results li span {
  flex-shrink: 0;
  color: #aaa;
}

/* 2. Tarjeta de dispositivo seleccionado blindada */
.selected-device-card {
  background-color: var(--bg-color);
  padding: 1rem;
  border-radius: 8px;
  margin-top: 1rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem; /* Previene colisiones */
  border-left: 4px solid var(--green);
}
.selected-device-card > div {
  flex: 1;
  min-width: 0;
}
.selected-device-card h3 {
  margin: 0 0 0.2rem 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.selected-device-card button {
  padding: 0.6rem 1.2rem;
  border: 1px solid var(--primary-color);
  background-color: var(--surface-color);
  color: #f1f1f1;
  cursor: pointer;
  border-radius: 6px;
  flex-shrink: 0; /* Nunca se aplasta el botón */
}

.btn-create {
  width: 100%;
  padding: 1rem;
  background-color: var(--green);
  color: var(--bg-color);
  font-size: 1.2rem;
  font-weight: bold;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  margin-top: 1rem;
}

/* 3. Lista de Sensores (MonitorBuilder) blindada */
.sensor-list {
  margin-top: 1.5rem;
  padding-top: 1.5rem;
  border-top: 1px solid var(--primary-color);
}
.sensor-list ul {
  list-style: none;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.8rem;
}
.sensor-list li {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background-color: var(--bg-color);
  padding: 0.75rem 1rem;
  border-radius: 8px;
  gap: 1rem; /* Previene que el nombre y botones choquen */
}
.sensor-info {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex: 1;
  min-width: 0;
}
.sensor-info strong {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 1;
  min-width: 0;
}
.sensor-type-badge {
  font-size: 0.75rem;
  font-weight: bold;
  padding: 0.2rem 0.5rem;
  border-radius: 12px;
  text-transform: uppercase;
  flex-shrink: 0; /* Badge sagrado */
}
.sensor-type-badge.ping {
  background-color: var(--blue);
  color: white;
}
.sensor-type-badge.ethernet {
  background-color: var(--green);
  color: var(--bg-color);
}
.sensor-type-badge.wireless {
  background-color: #8b5cf6;
  color: white;
}
.sensor-type-badge.system {
  background-color: #f59e0b; /* Color Ambar distintivo */
  color: var(--bg-color);
}

.sensor-actions {
  display: flex;
  align-items: center;
  gap: 0.8rem; /* Aumentado ligeramente para separar el badge de los botones */
  flex-shrink: 0; /* Botones sagrados */
}
.action-btn {
  background: none;
  border: none;
  font-size: 1.2rem;
  cursor: pointer;
  padding: 0.2rem 0.5rem;
  border-radius: 4px;
  transition: background-color 0.2s;
}
.edit-btn:hover {
  background-color: var(--blue);
}
.delete-btn {
  font-size: 1.8rem;
  color: var(--gray);
}
.delete-btn:hover {
  background-color: transparent;
  color: var(--secondary-color);
}
/* ============================================== */

.empty-list {
  color: var(--gray);
  font-style: italic;
}
.add-sensor-section {
  margin-top: 1rem; /* Modificado para integrarlo mejor */
}
.sensor-type-selector {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  margin-bottom: 1.5rem;
}
.sensor-type-selector button {
  padding: 0.8rem 1.5rem;
  border: 1px solid var(--primary-color);
  background-color: transparent;
  color: var(--gray);
  font-weight: bold;
  cursor: pointer;
  border-radius: 8px;
  flex: 1 1 auto;
}
.notification {
  position: fixed;
  top: 90px;
  right: 20px;
  padding: 1rem 1.5rem;
  border-radius: 8px;
  color: white;
  font-weight: bold;
  z-index: 1000;
}
.notification.success {
  background-color: var(--green);
}
.notification.error {
  background-color: var(--error-red);
}
.form-hint {
  font-size: 0.8rem;
  color: var(--gray);
  margin-top: 0.25rem;
  display: block;
}
.alert-enabled-badge {
  font-size: 0.9rem;
  flex-shrink: 0;
}

.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background-color: rgba(0, 0, 0, 0.7);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 2000;
}
.modal-content {
  background-color: var(--surface-color);
  padding: 2rem;
  border-radius: 12px;
  width: 90%;
  max-width: 900px;
  max-height: 90vh;
  overflow-y: auto;
}
.modal-content h3 {
  margin-top: 0;
}

/* CLASE NUEVA PARA EL WRAPPER DEL COMPONENTE */
.config-form-wrapper {
  padding: 1.5rem;
  background-color: var(--bg-color);
  border-radius: 8px;
  border: 1px solid var(--primary-color);
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
.form-group.span-2 {
  grid-column: span 2;
}
.form-group.span-3 {
  grid-column: span 3;
}
.form-group label {
  font-weight: bold;
  color: var(--gray);
}
.form-group input,
.form-group select {
  padding: 0.8rem;
  background-color: var(--surface-color);
  border: 1px solid var(--primary-color);
  border-radius: 6px;
  color: white;
  width: 100%;
}
.form-group select:disabled {
  opacity: 0.7;
  cursor: not-allowed;
  background-color: #2a2a2a;
}
.sub-section {
  grid-column: span 3;
  background-color: var(--surface-color);
  padding: 1.5rem;
  border-radius: 8px;
  margin-top: 1rem;
  border: 1px solid var(--primary-color);
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}
.sub-section h4 {
  margin: 0 0 0.5rem 0;
  border-bottom: 1px solid var(--primary-color);
  padding-bottom: 0.5rem;
}
.checkbox-group {
  flex-direction: row;
  align-items: center;
  gap: 0.8rem;
}
.checkbox-group input[type='checkbox'] {
  width: auto;
  accent-color: var(--blue);
}
.alert-config-item {
  border-top: 1px dashed var(--primary-color);
  padding-top: 1.5rem;
  display: contents;
}
.alert-config-item > .form-group {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1rem;
  grid-column: span 3;
  align-items: center;
}
.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 1rem;
  margin-top: 1.5rem;
  border-top: 1px solid var(--primary-color);
  padding-top: 1.5rem;
}
.modal-actions button {
  padding: 0.8rem 1.5rem;
  border: none;
  border-radius: 6px;
  font-weight: bold;
  cursor: pointer;
}
.btn-secondary {
  background-color: var(--primary-color);
  color: white;
}
.btn-add {
  background-color: var(--blue);
  color: white;
}

@media (max-width: 820px) {
  .modal-content {
    width: 95vw;
    max-width: 95vw;
    padding: 1.25rem;
  }
  .alert-config-item > .form-group {
    grid-template-columns: 1fr;
    grid-column: span 1;
  }
  .modal-actions {
    flex-direction: column;
    gap: 0.5rem;
  }
  .modal-actions button {
    width: 100%;
  }
  /* Botones de tipo sensor: uno por línea en pantallas muy pequeñas */
  .sensor-type-selector {
    flex-direction: column;
  }
  .sensor-type-selector button {
    width: 100%;
    padding: 0.65rem 1rem;
    text-align: left;
  }
}
</style>