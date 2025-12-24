<script setup>
import { ref, watch, onMounted, computed } from 'vue'
import api from '@/lib/api'

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

// --- Nuevo Estado para Grupo ---
const dbGroups = ref([]) // Grupos traídos de la API
const selectedGroupOption = ref('') // Dropdown
const customGroupName = ref('') // Input manual

// --- Estado para Edición ---
const sensorToEdit = ref(null)
const isEditMode = ref(false)

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

//
// --- Plantillas de Formularios (ACTUALIZADO: notify_recovery) ---
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
    notify_recovery: false, // <--- NUEVO
  },
  ui_alert_latency: {
    enabled: false,
    threshold_ms: 200,
    channel_id: null,
    cooldown_minutes: 5,
    tolerance_count: 1,
    notify_recovery: false, // <--- NUEVO
  },
})

const createNewEthernetSensor = () => ({
  name: '',
  config: {
    interface_name: '',
    interval_sec: 3,
  },
  ui_alert_speed_change: {
    enabled: false,
    channel_id: null,
    cooldown_minutes: 10,
    tolerance_count: 1,
    notify_recovery: false, // <--- NUEVO
  },
  ui_alert_traffic: {
    enabled: false,
    threshold_mbps: 100,
    direction: 'any',
    channel_id: null,
    cooldown_minutes: 5,
    tolerance_count: 1,
    notify_recovery: false, // <--- NUEVO
  },
})

const newPingSensor = ref(createNewPingSensor())
const newEthernetSensor = ref(createNewEthernetSensor())

//
// --- Ciclo de Vida ---
onMounted(() => {
  fetchGroups()
  fetchAllMonitors()
  fetchChannels()
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

async function fetchGroups() {
  try {
    const { data } = await api.get('/groups')
    dbGroups.value = data.map((g) => g.name)
  } catch (err) {
    console.error('Error fetching groups:', err)
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
// --- Lógica Sensores (ACTUALIZADO: notify_recovery en payload) ---
function buildSensorPayload(sensorType, sensorData) {
  const finalConfig = { ...sensorData.config }
  if (sensorType === 'ping' && !hasParentMaestro.value) {
    finalConfig.ping_type = 'device_to_external'
  }
  finalConfig.alerts = []
  const onlyNums = (v, fallback = undefined) => (typeof v === 'number' && !isNaN(v) ? v : fallback)

  if (sensorType === 'ping') {
    if (sensorData.ui_alert_timeout.enabled) {
      const a = sensorData.ui_alert_timeout
      if (!a.channel_id) throw new Error('Selecciona un canal para la alerta de Timeout.')
      finalConfig.alerts.push({
        type: 'timeout',
        channel_id: a.channel_id,
        cooldown_minutes: onlyNums(a.cooldown_minutes, 5),
        tolerance_count: Math.max(1, onlyNums(a.tolerance_count, 1)),
        notify_recovery: !!a.notify_recovery, // <--- Payload
      })
    }
    if (sensorData.ui_alert_latency.enabled) {
      const a = sensorData.ui_alert_latency
      if (!a.channel_id) throw new Error('Selecciona un canal para la alerta de Latencia.')
      finalConfig.alerts.push({
        type: 'high_latency',
        threshold_ms: onlyNums(a.threshold_ms, 200),
        channel_id: a.channel_id,
        cooldown_minutes: onlyNums(a.cooldown_minutes, 5),
        tolerance_count: Math.max(1, onlyNums(a.tolerance_count, 1)),
        notify_recovery: !!a.notify_recovery, // <--- Payload
      })
    }
  } else if (sensorType === 'ethernet') {
    if (sensorData.ui_alert_speed_change.enabled) {
      const a = sensorData.ui_alert_speed_change
      if (!a.channel_id)
        throw new Error('Selecciona un canal para la alerta de Cambio de Velocidad.')
      finalConfig.alerts.push({
        type: 'speed_change',
        channel_id: a.channel_id,
        cooldown_minutes: onlyNums(a.cooldown_minutes, 10),
        tolerance_count: Math.max(1, onlyNums(a.tolerance_count, 1)),
        notify_recovery: !!a.notify_recovery, // <--- Payload
      })
    }
    if (sensorData.ui_alert_traffic.enabled) {
      const a = sensorData.ui_alert_traffic
      if (!a.channel_id) throw new Error('Selecciona un canal para la alerta de Umbral de Tráfico.')
      finalConfig.alerts.push({
        type: 'traffic_threshold',
        threshold_mbps: onlyNums(a.threshold_mbps, 100),
        direction: a.direction || 'any',
        channel_id: a.channel_id,
        cooldown_minutes: onlyNums(a.cooldown_minutes, 5),
        tolerance_count: Math.max(1, onlyNums(a.tolerance_count, 1)),
        notify_recovery: !!a.notify_recovery, // <--- Payload
      })
    }
  }
  return { name: sensorData.name, config: finalConfig }
}

async function handleSaveSensor() {
  if (!formToShow.value) return
  const sensorData = formToShow.value === 'ping' ? newPingSensor.value : newEthernetSensor.value
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
  if (type === 'ping' && !hasParentMaestro.value)
    newPingSensor.value.config.ping_type = 'device_to_external'
  formToShow.value = type
}

function openFormForEdit(sensor) {
  isEditMode.value = true
  sensorToEdit.value = sensor
  const cfg = typeof sensor.config === 'string' ? safeJsonParse(sensor.config, {}) : sensor.config

  // Helper para mapear alerta
  const mapAlert = (alerts, type) => alerts.find((a) => a.type === type) || {}

  if (sensor.sensor_type === 'ping') {
    const uiData = createNewPingSensor()
    uiData.name = sensor.name
    uiData.config = { ...uiData.config, ...cfg }
    if (!hasParentMaestro.value) uiData.config.ping_type = 'device_to_external'

    const alerts = cfg?.alerts || []

    // Timeout Mapping
    const tOut = mapAlert(alerts, 'timeout')
    if (tOut.type) {
      uiData.ui_alert_timeout = {
        enabled: true,
        ...tOut,
        channel_id: tOut.channel_id ?? null,
        notify_recovery: tOut.notify_recovery ?? false,
      }
    }

    // Latency Mapping
    const tLat = mapAlert(alerts, 'high_latency')
    if (tLat.type) {
      uiData.ui_alert_latency = {
        enabled: true,
        ...tLat,
        channel_id: tLat.channel_id ?? null,
        notify_recovery: tLat.notify_recovery ?? false,
      }
    }

    newPingSensor.value = uiData
  } else if (sensor.sensor_type === 'ethernet') {
    const uiData = createNewEthernetSensor()
    uiData.name = sensor.name
    uiData.config = {
      interface_name: cfg.interface_name || '',
      interval_sec: cfg.interval_sec || 30,
    }

    const alerts = cfg?.alerts || []

    // Speed Change Mapping
    const tSpd = mapAlert(alerts, 'speed_change')
    if (tSpd.type) {
      uiData.ui_alert_speed_change = {
        enabled: true,
        ...tSpd,
        channel_id: tSpd.channel_id ?? null,
        notify_recovery: tSpd.notify_recovery ?? false,
      }
    }

    // Traffic Mapping
    const tTrf = mapAlert(alerts, 'traffic_threshold')
    if (tTrf.type) {
      uiData.ui_alert_traffic = {
        enabled: true,
        ...tTrf,
        channel_id: tTrf.channel_id ?? null,
        notify_recovery: tTrf.notify_recovery ?? false,
      }
    }

    newEthernetSensor.value = uiData
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
              <strong>{{ device.client_name }}</strong
              ><span>{{ device.ip_address }}</span>
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
          <div class="sensor-list">
            <h4>Sensores Activos</h4>
            <ul v-if="activeSensors.length > 0">
              <li v-for="sensor in activeSensors" :key="sensor.id">
                <div class="sensor-info">
                  <span class="sensor-type-badge" :class="sensor.sensor_type">{{
                    sensor.sensor_type
                  }}</span>
                  <strong>{{ sensor.name }}</strong>
                  <span v-if="sensor.config?.alerts?.length" class="alert-enabled-badge">🔔</span>
                </div>
                <div class="sensor-actions">
                  <button @click="openFormForEdit(sensor)" class="action-btn edit-btn">✏️</button>
                  <button @click="deleteSensor(sensor.id)" class="action-btn delete-btn">×</button>
                </div>
              </li>
            </ul>
            <p v-else class="empty-list">No hay sensores configurados.</p>
          </div>
          <div class="add-sensor-section">
            <h4>Añadir Nuevo Sensor</h4>
            <div class="sensor-type-selector">
              <button @click="openFormForCreate('ping')">Añadir Ping</button>
              <button @click="openFormForCreate('ethernet')">Añadir Ethernet</button>
            </div>
          </div>
        </div>
      </section>
    </div>

    <div v-if="formToShow" class="modal-overlay" @click.self="closeForm">
      <div class="modal-content">
        <h3>{{ isEditMode ? 'Editar' : 'Añadir' }} Sensor {{ formToShow }}</h3>

        <form v-if="formToShow === 'ping'" @submit.prevent="handleSaveSensor" class="config-form">
          <div class="form-group span-3">
            <label>Nombre del Sensor</label>
            <input type="text" v-model="newPingSensor.name" required />
          </div>
          <div class="form-group span-2">
            <label>Tipo de Ping</label>
            <select v-model="newPingSensor.config.ping_type" :disabled="!hasParentMaestro">
              <option value="device_to_external">Ping desde Dispositivo (Salida)</option>
              <option value="maestro_to_device" v-if="hasParentMaestro">
                Ping al Dispositivo (Desde Maestro)
              </option>
            </select>
            <p v-if="!hasParentMaestro" class="form-hint warning-text">⚠️ Sin maestro asignado.</p>
          </div>
          <div class="form-group" v-if="newPingSensor.config.ping_type === 'device_to_external'">
            <label>IP de Destino</label>
            <input type="text" v-model="newPingSensor.config.target_ip" placeholder="8.8.8.8" />
          </div>
          <div class="form-group">
            <label>Intervalo (s)</label>
            <input type="number" v-model.number="newPingSensor.config.interval_sec" required />
          </div>
          <div class="form-group">
            <label>Umbral Latencia (ms)</label>
            <input
              type="number"
              v-model.number="newPingSensor.config.latency_threshold_ms"
              required
            />
          </div>
          <div class="form-group">
            <label>Visualización</label>
            <select v-model="newPingSensor.config.display_mode">
              <option value="realtime">Tiempo Real</option>
              <option value="average">Promedio</option>
            </select>
          </div>
          <div class="form-group" v-if="newPingSensor.config.display_mode === 'average'">
            <label>Muestras para Promedio</label>
            <input type="number" v-model.number="newPingSensor.config.average_count" />
          </div>

          <div class="sub-section span-3">
            <h4>Alertas</h4>

            <div class="alert-config-item span-3">
              <div class="form-group checkbox-group">
                <input type="checkbox" v-model="newPingSensor.ui_alert_timeout.enabled" id="pTo" />
                <label for="pTo">Timeout</label>
              </div>
              <template v-if="newPingSensor.ui_alert_timeout.enabled">
                <div class="form-group">
                  <label>Canal</label>
                  <select v-model="newPingSensor.ui_alert_timeout.channel_id">
                    <option :value="null">--</option>
                    <option v-for="c in channels" :key="c.id" :value="c.id">{{ c.name }}</option>
                  </select>
                </div>
                <div class="form-group">
                  <label>Enfriamiento (min)</label>
                  <input
                    type="number"
                    v-model.number="newPingSensor.ui_alert_timeout.cooldown_minutes"
                  />
                </div>
                <div class="form-group">
                  <label>Tolerancia</label>
                  <input
                    type="number"
                    v-model.number="newPingSensor.ui_alert_timeout.tolerance_count"
                  />
                </div>
                <div class="form-group checkbox-group">
                  <input
                    type="checkbox"
                    v-model="newPingSensor.ui_alert_timeout.notify_recovery"
                    id="pToRec"
                  />
                  <label for="pToRec">Notificar Reanudación 🟢</label>
                </div>
              </template>
            </div>

            <div class="alert-config-item span-3">
              <div class="form-group checkbox-group">
                <input type="checkbox" v-model="newPingSensor.ui_alert_latency.enabled" id="pLat" />
                <label for="pLat">Latencia Alta</label>
              </div>
              <template v-if="newPingSensor.ui_alert_latency.enabled">
                <div class="form-group">
                  <label>Umbral (ms)</label>
                  <input
                    type="number"
                    v-model.number="newPingSensor.ui_alert_latency.threshold_ms"
                  />
                </div>
                <div class="form-group">
                  <label>Canal</label>
                  <select v-model="newPingSensor.ui_alert_latency.channel_id">
                    <option :value="null">--</option>
                    <option v-for="c in channels" :key="c.id" :value="c.id">{{ c.name }}</option>
                  </select>
                </div>
                <div class="form-group">
                  <label>Enfriamiento (min)</label>
                  <input
                    type="number"
                    v-model.number="newPingSensor.ui_alert_latency.cooldown_minutes"
                  />
                </div>
                <div class="form-group">
                  <label>Tolerancia</label>
                  <input
                    type="number"
                    v-model.number="newPingSensor.ui_alert_latency.tolerance_count"
                  />
                </div>
                <div class="form-group checkbox-group">
                  <input
                    type="checkbox"
                    v-model="newPingSensor.ui_alert_latency.notify_recovery"
                    id="pLatRec"
                  />
                  <label for="pLatRec">Notificar Reanudación 🟢</label>
                </div>
              </template>
            </div>
          </div>
          <div class="modal-actions span-3">
            <button type="button" @click="closeForm" class="btn-secondary">Cancelar</button>
            <button type="submit" class="btn-add">Guardar</button>
          </div>
        </form>

        <form
          v-if="formToShow === 'ethernet'"
          @submit.prevent="handleSaveSensor"
          class="config-form"
        >
          <div class="form-group span-2">
            <label>Nombre</label><input type="text" v-model="newEthernetSensor.name" required />
          </div>
          <div class="form-group">
            <label>Interfaz</label>
            <input
              type="text"
              v-model="newEthernetSensor.config.interface_name"
              required
              placeholder="ether1"
            />
          </div>
          <div class="form-group span-3">
            <label>Intervalo (s)</label>
            <input type="number" v-model.number="newEthernetSensor.config.interval_sec" required />
          </div>

          <div class="sub-section span-3">
            <h4>Alertas</h4>

            <div class="alert-config-item span-3">
              <div class="form-group checkbox-group">
                <input
                  type="checkbox"
                  v-model="newEthernetSensor.ui_alert_speed_change.enabled"
                  id="eSpd"
                />
                <label for="eSpd">Cambio de Velocidad</label>
              </div>
              <template v-if="newEthernetSensor.ui_alert_speed_change.enabled">
                <div class="form-group">
                  <label>Canal</label>
                  <select v-model="newEthernetSensor.ui_alert_speed_change.channel_id">
                    <option :value="null">--</option>
                    <option v-for="c in channels" :key="c.id" :value="c.id">{{ c.name }}</option>
                  </select>
                </div>
                <div class="form-group">
                  <label>Enfriamiento</label>
                  <input
                    type="number"
                    v-model.number="newEthernetSensor.ui_alert_speed_change.cooldown_minutes"
                  />
                </div>
                <div class="form-group">
                  <label>Tolerancia</label>
                  <input
                    type="number"
                    v-model.number="newEthernetSensor.ui_alert_speed_change.tolerance_count"
                  />
                </div>
                <div class="form-group checkbox-group">
                  <input
                    type="checkbox"
                    v-model="newEthernetSensor.ui_alert_speed_change.notify_recovery"
                    id="eSpdRec"
                  />
                  <label for="eSpdRec">Notificar Reanudación 🟢</label>
                </div>
              </template>
            </div>

            <div class="alert-config-item span-3">
              <div class="form-group checkbox-group">
                <input
                  type="checkbox"
                  v-model="newEthernetSensor.ui_alert_traffic.enabled"
                  id="eTrf"
                />
                <label for="eTrf">Umbral Tráfico</label>
              </div>
              <template v-if="newEthernetSensor.ui_alert_traffic.enabled">
                <div class="form-group">
                  <label>Mbps</label>
                  <input
                    type="number"
                    v-model.number="newEthernetSensor.ui_alert_traffic.threshold_mbps"
                  />
                </div>
                <div class="form-group">
                  <label>Dirección</label>
                  <select v-model="newEthernetSensor.ui_alert_traffic.direction">
                    <option value="any">Cualquiera</option>
                    <option value="rx">Bajada</option>
                    <option value="tx">Subida</option>
                  </select>
                </div>
                <div class="form-group">
                  <label>Canal</label>
                  <select v-model="newEthernetSensor.ui_alert_traffic.channel_id">
                    <option :value="null">--</option>
                    <option v-for="c in channels" :key="c.id" :value="c.id">{{ c.name }}</option>
                  </select>
                </div>
                <div class="form-group">
                  <label>Enfriamiento</label>
                  <input
                    type="number"
                    v-model.number="newEthernetSensor.ui_alert_traffic.cooldown_minutes"
                  />
                </div>
                <div class="form-group">
                  <label>Tolerancia</label>
                  <input
                    type="number"
                    v-model.number="newEthernetSensor.ui_alert_traffic.tolerance_count"
                  />
                </div>
                <div class="form-group checkbox-group">
                  <input
                    type="checkbox"
                    v-model="newEthernetSensor.ui_alert_traffic.notify_recovery"
                    id="eTrfRec"
                  />
                  <label for="eTrfRec">Notificar Reanudación 🟢</label>
                </div>
              </template>
            </div>
          </div>
          <div class="modal-actions span-3">
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
  transition: background-color 0.2s;
}
.search-results li:hover {
  background-color: var(--primary-color);
}
.selected-device-card {
  background-color: var(--bg-color);
  padding: 1rem;
  border-radius: 8px;
  margin-top: 1rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-left: 4px solid var(--green);
}
.selected-device-card button {
  padding: 0.6rem 1.2rem;
  border: 1px solid var(--primary-color);
  background-color: var(--surface-color);
  color: #f1f1f1;
  cursor: pointer;
  border-radius: 6px;
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
.sensor-list {
  margin-top: 2rem;
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
}
.sensor-info {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}
.sensor-type-badge {
  font-size: 0.75rem;
  font-weight: bold;
  padding: 0.2rem 0.5rem;
  border-radius: 12px;
  text-transform: uppercase;
}
.sensor-type-badge.ping {
  background-color: var(--blue);
  color: white;
}
.sensor-type-badge.ethernet {
  background-color: var(--green);
  color: var(--bg-color);
}
.empty-list {
  color: var(--gray);
  font-style: italic;
}
.add-sensor-section {
  margin-top: 2rem;
  padding-top: 1.5rem;
  border-top: 1px solid var(--primary-color);
}
.sensor-type-selector {
  display: flex;
  gap: 1rem;
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
}
.alert-enabled-badge {
  font-size: 0.9rem;
}
.sensor-actions {
  display: flex;
  gap: 0.5rem;
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
.config-form {
  padding: 1.5rem;
  background-color: var(--bg-color);
  border-radius: 8px;
  border: 1px solid var(--primary-color);
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1.5rem 1rem;
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
  grid-column: span 3;
  display: flex;
  justify-content: flex-end;
  gap: 1rem;
  margin-top: 1.5rem;
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
</style>
