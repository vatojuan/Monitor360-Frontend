<script setup>
import { ref, onMounted, computed, onUnmounted, watch } from 'vue'
import api from '@/lib/api'
import SensorConfigurator from '@/components/SensorConfigurator.vue' // <-- NUEVO: Fuente de la verdad

// --- ESTADO GLOBAL ---
const activeTab = ref('inbox')
const isLoading = ref(false)
const isScanning = ref(false)
const isAdopting = ref(false)
const notification = ref({ show: false, message: '', type: 'success' })

// --- DATOS ---
const maestros = ref([])
const allDevicesList = ref([]) // Inventario completo
const credentialProfiles = ref([])
const pendingDevices = ref([])
const ignoredDevices = ref([]) // Lista Negra
const scanProfiles = ref([])
const channels = ref([]) 
const groups = ref([])
const autoTasks = ref([]) // Lista de Tareas Automáticas disponibles

// --- ESTADO PARA SONDAS (PROBES) ---
const availableProbes = ref([])
const probeSearchText = ref('')
const isProbeDropdownOpen = ref(false)

// --- ESTADO PARA INTERFACES ---
const maestroInterfaces = ref([])
const isLoadingInterfaces = ref(false)

// --- ESTADO FILTROS INBOX ---
const inboxFilter = ref({
  search: '',
  type: 'all', // all, infra, generic
  vendor: ''
})

// --- ESTADO FILTROS IGNORADOS ---
const ignoredFilter = ref({
  search: '',
  type: 'all',
  vendor: ''
})

// --- ESTADO SELECCIÓN ---
const selectedPending = ref([])
const selectedIgnored = ref([])


// --- ESTADO CONFIGURACIÓN (SCAN) ---
const scanConfig = ref({
  id: null,
  source_device_id: '', // <-- AHORA ES LA SONDA
  network_cidr: '192.168.88.0/24',
  interface: '',
  scan_ports: '8728, 80, 22', 
  scan_mode: 'manual', 
  credential_profile_id: null,
  is_active: false,
  scan_interval_minutes: 60, 
  target_group: 'General',
  adopt_only_managed: false,
})

// --- ESTADO: LISTA DINÁMICA DE SENSORES PARA LA RECETA (SCANNER) ---
const sensorsTemplateList = ref([])

// --- ESTADO: MODAL DE ADOPCIÓN MANUAL ---
const showAdoptModal = ref(false)
const adoptCredentialId = ref(null)
const adoptTargetGroup = ref('General')
const adoptSensorsList = ref([]) // Receta de sensores para adopción manual

const newSensorType = ref('ping') // Usado tanto por Scanner como por Modal

const hasSystemSensorScanner = computed(() => sensorsTemplateList.value.some(s => s.sensor_type === 'system'))
const hasSystemSensorModal = computed(() => adoptSensorsList.value.some(s => s.sensor_type === 'system'))


// --- COMPUTADA: Sondas Sugeridas (Filtro Autocomplete) ---
const filteredProbes = computed(() => {
    if (!probeSearchText.value) return availableProbes.value;
    const q = probeSearchText.value.toLowerCase();
    return availableProbes.value.filter(p => 
        (p.client_name || '').toLowerCase().includes(q) ||
        (p.ip_address || '').toLowerCase().includes(q) ||
        (p.vendor || '').toLowerCase().includes(q)
    );
});

// Getter seguro para mostrar el nombre en el input de búsqueda
const selectedProbeName = computed(() => {
    if (!scanConfig.value.source_device_id) return '';
    const p = availableProbes.value.find(x => x.id === scanConfig.value.source_device_id);
    return p ? `${p.client_name} (${p.ip_address})` : 'Dispositivo Desconocido';
});

// --- COMPUTADA: Dispositivos Sugeridos (Para el Ping Target) ---
const suggestedTargetDevices = computed(() => {
  if (!scanConfig.value.source_device_id) return []
  const selectedProbe = allDevicesList.value.find((d) => d.id === scanConfig.value.source_device_id)
  if (!selectedProbe) return allDevicesList.value 
  const currentVpnId = selectedProbe.vpn_profile_id
  return allDevicesList.value.filter((d) => {
    if (!currentVpnId) return true
    if (d.is_maestro) return d.vpn_profile_id === currentVpnId
    if (d.maestro_id) {
      const dMaestro = allDevicesList.value.find((m) => m.id === d.maestro_id)
      return dMaestro && dMaestro.vpn_profile_id === currentVpnId
    }
    return d.vpn_profile_id === currentVpnId
  })
})

// =============================================================================
// LÓGICA DE INTERFACES Y BUSCADOR
// =============================================================================

function selectProbe(probe) {
    scanConfig.value.source_device_id = probe.id;
    probeSearchText.value = '';
    isProbeDropdownOpen.value = false;
}

function clearProbe() {
    scanConfig.value.source_device_id = '';
    probeSearchText.value = '';
    maestroInterfaces.value = [];
}

// Cierra el dropdown si se hace clic afuera (comportamiento básico)
function hideProbeDropdown() {
    setTimeout(() => { isProbeDropdownOpen.value = false; }, 200);
}

watch(() => scanConfig.value.source_device_id, async (newSourceId) => {
  if (!newSourceId) {
    maestroInterfaces.value = [];
    return;
  }
  
  isLoadingInterfaces.value = true;
  try {
    const { data } = await api.get(`/devices/${newSourceId}/interfaces`);
    maestroInterfaces.value = data || [];
  } catch (e) {
    console.error('Error cargando interfaces de la Sonda:', e);
    maestroInterfaces.value = [];
    showNotification('No se pudieron cargar las interfaces del Router', 'error');
  } finally {
    isLoadingInterfaces.value = false;
  }
});

// =============================================================================
// LÓGICA DE FILTRADO INBOX/IGNORED (REFINADA)
// =============================================================================

function isInfra(dev) {
    const v = (dev.vendor || '').toLowerCase();
    const p = (dev.platform || '').toLowerCase();
    const managedVendors = ['mikrotik', 'ubiquiti', 'ubnt', 'mimosa', 'cambium', 'cisco', 'juniper'];
    return managedVendors.some(mv => v.includes(mv)) || p.length > 0 || !!dev.identity;
}

function filterDevicesList(list, filters) {
    return list.filter(d => {
        if (filters.search) {
            const q = filters.search.toLowerCase().trim();
            const textMatch = (
                (d.ip_address || '').toLowerCase().includes(q) ||
                (d.mac_address || '').toLowerCase().includes(q) ||
                (d.identity || '').toLowerCase().includes(q) ||
                (d.hostname || '').toLowerCase().includes(q) ||
                (d.vendor || '').toLowerCase().includes(q)
            );
            if (!textMatch) return false;
        }
        if (filters.vendor && filters.vendor !== '') {
            if ((d.vendor || 'Desconocido') !== filters.vendor) return false;
        }
        if (filters.type === 'infra') {
            if (!isInfra(d)) return false;
        } else if (filters.type === 'generic') {
            if (isInfra(d)) return false;
        }
        return true;
    });
}

const filteredPendingDevices = computed(() => filterDevicesList(pendingDevices.value, inboxFilter.value));
const filteredIgnoredDevices = computed(() => filterDevicesList(ignoredDevices.value, ignoredFilter.value));
const pendingVendors = computed(() => [...new Set(pendingDevices.value.map(d => d.vendor || 'Desconocido'))].sort());
const ignoredVendors = computed(() => [...new Set(ignoredDevices.value.map(d => d.vendor || 'Desconocido'))].sort());


// =============================================================================
// LIFECYCLE & EVENTOS WEBSOCKET REACTIVOS (CORREGIDO)
// =============================================================================

const handleDiscoveryRefresh = async () => {
  // Refresco de seguridad para sincronizar listas completas
  await fetchPendingDevices();
  await fetchIgnoredDevices();
};

const handleDeviceFound = (event) => {
  // Extraemos el dispositivo del 'detail' del CustomEvent enviado por AppLayout
  const newDevice = event.detail?.device || event.detail;
  
  if (newDevice && newDevice.mac_address) {
    // Evitamos duplicados en la tabla reactiva
    const exists = pendingDevices.value.some(d => d.mac_address === newDevice.mac_address);
    if (!exists) {
      console.log("Tiempo Real: Inyectando equipo hallado ->", newDevice.ip_address);
      pendingDevices.value.push(newDevice);
    }
  }
};

const handleScanFinished = async () => {
  if (isScanning.value) {
    isScanning.value = false;
    showNotification('✅ Escaneo finalizado. Red peinada.', 'success');
    await fetchPendingDevices(); // Sincronización final por si algún paquete de red se perdió
  }
};

onMounted(async () => { 
  await loadGlobalData();
  
  // 1. Escuchar señal de refresco (general)
  window.addEventListener('discovery_refresh', handleDiscoveryRefresh);
  
  // 2. Escuchar hallazgos automáticos (estos sí podrían sonar en la campanita)
  window.addEventListener('discovery_device_found', handleDeviceFound); 
  
  // 3. ESCUCHA SILENCIOSA (MANUAL): Para recibir datos sin activar la Campanita
  window.addEventListener('discovery_manual_hit', handleDeviceFound); 
  
  // 4. Escuchar fin de tarea
  window.addEventListener('discovery_scan_finished', handleScanFinished);
})

onUnmounted(() => {
  // Limpieza de todos los listeners para evitar fugas de memoria
  window.removeEventListener('discovery_refresh', handleDiscoveryRefresh);
  window.removeEventListener('discovery_device_found', handleDeviceFound);
  window.removeEventListener('discovery_manual_hit', handleDeviceFound);
  window.removeEventListener('discovery_scan_finished', handleScanFinished);
})

async function loadGlobalData() {
  isLoading.value = true
  try {
    await Promise.all([
      fetchMaestrosAndDevices(), fetchCredentialProfiles(), fetchPendingDevices(),
      fetchIgnoredDevices(), fetchScanProfiles(), fetchChannels(), fetchGroups(),
      fetchAutoTasks(), fetchProbes()
    ])
  } catch (e) { showNotification('Error cargando datos', 'error') } 
  finally { isLoading.value = false }
}

async function fetchMaestrosAndDevices() {
  try {
    const { data } = await api.get('/devices')
    allDevicesList.value = data || []
    maestro.value = (data || []).filter((d) => d.is_maestro === true)
  } catch (e) { maestros.value = []; allDevicesList.value = [] }
}
async function fetchProbes() {
  try {
      const { data } = await api.get('/discovery/probes')
      availableProbes.value = data || []
  } catch(e) { availableProbes.value = [] }
}

async function fetchCredentialProfiles() { const { data } = await api.get('/credentials/profiles'); credentialProfiles.value = data || [] }
async function fetchPendingDevices() { const { data } = await api.get('/discovery/pending', { params: { include_manual: true } }); pendingDevices.value = data || [] }
async function fetchIgnoredDevices() { try { const { data } = await api.get('/discovery/ignored'); ignoredDevices.value = data || [] } catch (e) {} }
async function fetchScanProfiles() { try { const { data } = await api.get('/discovery/profiles'); scanProfiles.value = data || [] } catch (e) {} }
async function fetchChannels() { try { const { data } = await api.get('/channels'); channels.value = data || [] } catch (e) {} }
async function fetchGroups() { try { const { data } = await api.get('/groups'); groups.value = (data || []).map((g) => g.name) } catch (e) {} }
async function fetchAutoTasks() { try { const { data } = await api.get('/scheduled-tasks/'); autoTasks.value = data || [] } catch (e) { console.error(e) } }

// =============================================================================
// GESTIÓN DINÁMICA DE SENSORES (RECETA REUTILIZABLE) CON FORMATO UNIFICADO
// =============================================================================

function createDefaultSensor(type) {
  const base = {
      id: Date.now() + Math.random(), 
      sensor_type: type,
      name_template: '{{hostname}} - Sensor',
      is_active: true,
      alerts_paused: false,
      attach_to: 'device', 
      config: {}
  }

  // Se ajustan los payloads a la estructura estándar que espera SensorConfigurator
  if (type === 'ping') {
      base.config = { interval_sec: 60, latency_threshold_ms: 150, display_mode: 'realtime', average_count: 5, ping_type: 'device_to_external', target_ip: '' }
      base.ui_alert_timeout = { enabled: false, channel_id: null, cooldown_minutes: 5, tolerance_count: 1, notify_recovery: false, use_custom_message: false, custom_message: '', use_custom_recovery_message: false, custom_recovery_message: '', use_auto_task: false, trigger_task_id: null }
      base.ui_alert_latency = { enabled: false, threshold_ms: 200, channel_id: null, cooldown_minutes: 5, tolerance_count: 1, notify_recovery: false, use_custom_message: false, custom_message: '', use_custom_recovery_message: false, custom_recovery_message: '', use_auto_task: false, trigger_task_id: null }
  } else if (type === 'ethernet') {
      base.config = { interface_name: '', interval_sec: 30 }
      base.ui_alert_speed_change = { enabled: false, channel_id: null, cooldown_minutes: 10, tolerance_count: 1, notify_recovery: false, use_custom_message: false, custom_message: '', use_custom_recovery_message: false, custom_recovery_message: '', use_auto_task: false, trigger_task_id: null }
      base.ui_alert_traffic = { enabled: false, threshold_mbps: 100, direction: 'any', channel_id: null, cooldown_minutes: 5, tolerance_count: 1, notify_recovery: false, use_custom_message: false, custom_message: '', use_custom_recovery_message: false, custom_recovery_message: '', use_auto_task: false, trigger_task_id: null }
  } else if (type === 'wireless') {
      base.config = { interface_name: '', interval_sec: 60, thresholds: { min_signal_dbm: -80, min_ccq_percent: 75, min_tx_rate_mbps: 0, min_rx_rate_mbps: 0, min_client_count: 0 }, tolerance_checks: 3 }
      base.ui_alert_status = { enabled: false, channel_id: null, cooldown_minutes: 10, notify_recovery: true, use_custom_message: false, custom_message: '', use_custom_recovery_message: false, custom_recovery_message: '', use_auto_task: false, trigger_task_id: null }
  } else if (type === 'system') {
      base.config = { interval_sec: 60, thresholds: { max_cpu_percent: 85, max_memory_percent: 90, restart_uptime_seconds: 300, min_voltage: null, max_voltage: null, max_temperature: 75 }, tolerance_checks: 3 }
      base.ui_alert_status = { enabled: false, channel_id: null, cooldown_minutes: 10, notify_recovery: true, use_custom_message: false, custom_message: '', use_custom_recovery_message: false, custom_recovery_message: '', use_auto_task: false, trigger_task_id: null }
  }
  return base
}

function addSensorToRecipe(targetList, hasSystemFn) {
    if (newSensorType.value === 'system' && hasSystemFn) return;
    targetList.push(createDefaultSensor(newSensorType.value))
}

function removeSensor(targetList, index) {
    targetList.splice(index, 1)
}

function getSensorIcon(type) {
    const icons = { 'ping': '📡', 'ethernet': '🔌', 'wireless': '📶', 'system': '🖥️' }
    return icons[type] || '⚙️'
}

function buildSensorConfigPayload(sensorData) { 
  const finalConfig = { ...sensorData.config }
  const alerts = []
  const onlyNums = (v, f) => (typeof v === 'number' && !isNaN(v) ? v : f)
  const sType = sensorData.sensor_type

  // Intercepción inteligente de auto-asociación a maestro (basado en el ping_type seleccionado en UI)
  let attachTo = sensorData.attach_to || 'device';
  if (sType === 'ping') {
      if (finalConfig.ping_type === 'maestro_to_device') {
          attachTo = 'maestro';
          finalConfig.target_ip = 'dynamic_ip'; // Instrucción para backend
      } else {
          attachTo = 'device';
          if (!finalConfig.target_ip) finalConfig.target_ip = '8.8.8.8'; // Fallback
      }
  }

  if (sType === 'ping') {
    if (sensorData.ui_alert_timeout?.enabled && sensorData.ui_alert_timeout?.channel_id) {
        const a = { type: 'timeout', channel_id: sensorData.ui_alert_timeout.channel_id, cooldown_minutes: onlyNums(sensorData.ui_alert_timeout.cooldown_minutes, 5), tolerance_count: Math.max(1, onlyNums(sensorData.ui_alert_timeout.tolerance_count, 1)), notify_recovery: !!sensorData.ui_alert_timeout.notify_recovery };
        if (sensorData.ui_alert_timeout.use_custom_message && sensorData.ui_alert_timeout.custom_message?.trim()) a.custom_message = sensorData.ui_alert_timeout.custom_message.trim();
        if (sensorData.ui_alert_timeout.use_custom_recovery_message && sensorData.ui_alert_timeout.custom_recovery_message?.trim()) a.custom_recovery_message = sensorData.ui_alert_timeout.custom_recovery_message.trim();
        if (sensorData.ui_alert_timeout.use_auto_task && sensorData.ui_alert_timeout.trigger_task_id) a.trigger_task_id = sensorData.ui_alert_timeout.trigger_task_id;
        alerts.push(a);
    }
    if (sensorData.ui_alert_latency?.enabled && sensorData.ui_alert_latency?.channel_id) {
        const a = { type: 'high_latency', threshold_ms: onlyNums(sensorData.ui_alert_latency.threshold_ms, 200), channel_id: sensorData.ui_alert_latency.channel_id, cooldown_minutes: onlyNums(sensorData.ui_alert_latency.cooldown_minutes, 5), tolerance_count: Math.max(1, onlyNums(sensorData.ui_alert_latency.tolerance_count, 1)), notify_recovery: !!sensorData.ui_alert_latency.notify_recovery };
        if (sensorData.ui_alert_latency.use_custom_message && sensorData.ui_alert_latency.custom_message?.trim()) a.custom_message = sensorData.ui_alert_latency.custom_message.trim();
        if (sensorData.ui_alert_latency.use_custom_recovery_message && sensorData.ui_alert_latency.custom_recovery_message?.trim()) a.custom_recovery_message = sensorData.ui_alert_latency.custom_recovery_message.trim();
        if (sensorData.ui_alert_latency.use_auto_task && sensorData.ui_alert_latency.trigger_task_id) a.trigger_task_id = sensorData.ui_alert_latency.trigger_task_id;
        alerts.push(a);
    }
  } else if (sType === 'ethernet') {
    if (sensorData.ui_alert_speed_change?.enabled && sensorData.ui_alert_speed_change?.channel_id) {
        const a = { type: 'speed_change', channel_id: sensorData.ui_alert_speed_change.channel_id, cooldown_minutes: onlyNums(sensorData.ui_alert_speed_change.cooldown_minutes, 10), tolerance_count: Math.max(1, onlyNums(sensorData.ui_alert_speed_change.tolerance_count, 1)), notify_recovery: !!sensorData.ui_alert_speed_change.notify_recovery };
        if (sensorData.ui_alert_speed_change.use_custom_message && sensorData.ui_alert_speed_change.custom_message?.trim()) a.custom_message = sensorData.ui_alert_speed_change.custom_message.trim();
        if (sensorData.ui_alert_speed_change.use_custom_recovery_message && sensorData.ui_alert_speed_change.custom_recovery_message?.trim()) a.custom_recovery_message = sensorData.ui_alert_speed_change.custom_recovery_message.trim();
        if (sensorData.ui_alert_speed_change.use_auto_task && sensorData.ui_alert_speed_change.trigger_task_id) a.trigger_task_id = sensorData.ui_alert_speed_change.trigger_task_id;
        alerts.push(a);
    }
    if (sensorData.ui_alert_traffic?.enabled && sensorData.ui_alert_traffic?.channel_id) {
        const a = { type: 'traffic_threshold', threshold_mbps: onlyNums(sensorData.ui_alert_traffic.threshold_mbps, 100), direction: sensorData.ui_alert_traffic.direction || 'any', channel_id: sensorData.ui_alert_traffic.channel_id, cooldown_minutes: onlyNums(sensorData.ui_alert_traffic.cooldown_minutes, 5), tolerance_count: Math.max(1, onlyNums(sensorData.ui_alert_traffic.tolerance_count, 1)), notify_recovery: !!sensorData.ui_alert_traffic.notify_recovery };
        if (sensorData.ui_alert_traffic.use_custom_message && sensorData.ui_alert_traffic.custom_message?.trim()) a.custom_message = sensorData.ui_alert_traffic.custom_message.trim();
        if (sensorData.ui_alert_traffic.use_custom_recovery_message && sensorData.ui_alert_traffic.custom_recovery_message?.trim()) a.custom_recovery_message = sensorData.ui_alert_traffic.custom_recovery_message.trim();
        if (sensorData.ui_alert_traffic.use_auto_task && sensorData.ui_alert_traffic.trigger_task_id) a.trigger_task_id = sensorData.ui_alert_traffic.trigger_task_id;
        alerts.push(a);
    }
  } else if (sType === 'wireless') {
    if (sensorData.ui_alert_status?.enabled && sensorData.ui_alert_status?.channel_id) {
        const a = { type: 'wireless_status', channel_id: sensorData.ui_alert_status.channel_id, cooldown_minutes: onlyNums(sensorData.ui_alert_status.cooldown_minutes, 10), notify_recovery: !!sensorData.ui_alert_status.notify_recovery };
        if (sensorData.ui_alert_status.use_custom_message && sensorData.ui_alert_status.custom_message?.trim()) a.custom_message = sensorData.ui_alert_status.custom_message.trim();
        if (sensorData.ui_alert_status.use_custom_recovery_message && sensorData.ui_alert_status.custom_recovery_message?.trim()) a.custom_recovery_message = sensorData.ui_alert_status.custom_recovery_message.trim();
        if (sensorData.ui_alert_status.use_auto_task && sensorData.ui_alert_status.trigger_task_id) a.trigger_task_id = sensorData.ui_alert_status.trigger_task_id;
        alerts.push(a);
    }
  } else if (sType === 'system') {
    if (sensorData.ui_alert_status?.enabled && sensorData.ui_alert_status?.channel_id) {
        const a = { type: 'system_status', channel_id: sensorData.ui_alert_status.channel_id, cooldown_minutes: onlyNums(sensorData.ui_alert_status.cooldown_minutes, 10), notify_recovery: !!sensorData.ui_alert_status.notify_recovery };
        if (sensorData.ui_alert_status.use_custom_message && sensorData.ui_alert_status.custom_message?.trim()) a.custom_message = sensorData.ui_alert_status.custom_message.trim();
        if (sensorData.ui_alert_status.use_custom_recovery_message && sensorData.ui_alert_status.custom_recovery_message?.trim()) a.custom_recovery_message = sensorData.ui_alert_status.custom_recovery_message.trim();
        if (sensorData.ui_alert_status.use_auto_task && sensorData.ui_alert_status.trigger_task_id) a.trigger_task_id = sensorData.ui_alert_status.trigger_task_id;
        alerts.push(a);
    }
  }

  finalConfig.alerts = alerts;
  return { 
      sensor_type: sType, 
      name_template: sensorData.name_template || '{{hostname}} - Sensor', 
      config: finalConfig, 
      is_active: sensorData.is_active ?? true, 
      alerts_paused: sensorData.alerts_paused ?? false,
      attach_to: attachTo
  }
}

function restoreSensorConfig(sensors) { 
  sensorsTemplateList.value = []
  if (!sensors || !Array.isArray(sensors)) return

  sensors.forEach(backendSensor => {
      const s = createDefaultSensor(backendSensor.sensor_type)
      s.name_template = backendSensor.name_template || s.name_template
      s.is_active = backendSensor.is_active ?? true
      s.alerts_paused = backendSensor.alerts_paused ?? false
      s.attach_to = backendSensor.attach_to || 'device'
      s.config = { ...s.config, ...backendSensor.config }

      if (s.sensor_type === 'ping' && s.attach_to === 'maestro') {
          s.config.ping_type = 'maestro_to_device';
      }

      if (backendSensor.config && backendSensor.config.alerts) {
          backendSensor.config.alerts.forEach(a => {
              if (s.sensor_type === 'ping') {
                 if (a.type === 'timeout') s.ui_alert_timeout = { ...s.ui_alert_timeout, ...a, enabled: true, use_custom_message: !!a.custom_message, custom_message: a.custom_message || '', use_custom_recovery_message: !!a.custom_recovery_message, custom_recovery_message: a.custom_recovery_message || '', use_auto_task: !!a.trigger_task_id, trigger_task_id: a.trigger_task_id || null }
                 if (a.type === 'high_latency') s.ui_alert_latency = { ...s.ui_alert_latency, ...a, enabled: true, use_custom_message: !!a.custom_message, custom_message: a.custom_message || '', use_custom_recovery_message: !!a.custom_recovery_message, custom_recovery_message: a.custom_recovery_message || '', use_auto_task: !!a.trigger_task_id, trigger_task_id: a.trigger_task_id || null }
              } else if (s.sensor_type === 'ethernet') {
                 if (a.type === 'speed_change') s.ui_alert_speed_change = { ...s.ui_alert_speed_change, ...a, enabled: true, use_custom_message: !!a.custom_message, custom_message: a.custom_message || '', use_custom_recovery_message: !!a.custom_recovery_message, custom_recovery_message: a.custom_recovery_message || '', use_auto_task: !!a.trigger_task_id, trigger_task_id: a.trigger_task_id || null }
                 if (a.type === 'traffic_threshold') s.ui_alert_traffic = { ...s.ui_alert_traffic, ...a, enabled: true, use_custom_message: !!a.custom_message, custom_message: a.custom_message || '', use_custom_recovery_message: !!a.custom_recovery_message, custom_recovery_message: a.custom_recovery_message || '', use_auto_task: !!a.trigger_task_id, trigger_task_id: a.trigger_task_id || null }
              } else if (s.sensor_type === 'wireless') {
                 if (a.type === 'wireless_status') s.ui_alert_status = { ...s.ui_alert_status, ...a, enabled: true, use_custom_message: !!a.custom_message, custom_message: a.custom_message || '', use_custom_recovery_message: !!a.custom_recovery_message, custom_recovery_message: a.custom_recovery_message || '', use_auto_task: !!a.trigger_task_id, trigger_task_id: a.trigger_task_id || null }
              } else if (s.sensor_type === 'system') {
                 if (a.type === 'system_status') s.ui_alert_status = { ...s.ui_alert_status, ...a, enabled: true, use_custom_message: !!a.custom_message, custom_message: a.custom_message || '', use_custom_recovery_message: !!a.custom_recovery_message, custom_recovery_message: a.custom_recovery_message || '', use_auto_task: !!a.trigger_task_id, trigger_task_id: a.trigger_task_id || null }
              }
          })
      }
      sensorsTemplateList.value.push(s)
  })
}

// =============================================================================
// ACCIONES DE ESCANEO RE-ESTRUCTURADAS (SIN POLLING)
// =============================================================================

async function runScan() {
  if (!scanConfig.value.source_device_id) return showNotification('Selecciona una Sonda de Escaneo', 'error')
  
  isScanning.value = true 
  try {
    const payload = { ...scanConfig.value }
    if (scanConfig.value.is_active && scanConfig.value.scan_mode === 'auto') {
      payload.sensors_config = sensorsTemplateList.value.map(s => buildSensorConfigPayload(s))
    }

    if (scanConfig.value.is_active) {
       await api.post('/discovery/config', payload); 
       showNotification(scanConfig.value.id ? '✅ Tarea actualizada' : '✅ Nueva tarea creada', 'success'); 
       resetConfigForm();
       isScanning.value = false; // Como es solo guardar configuración, no queda escaneando.
    } else {
        const { data } = await api.post(`/discovery/scan/${scanConfig.value.source_device_id}`, payload); 
        if (data.status === 'started') {
          showNotification('🚀 Escaneo iniciado. Recibiendo datos en tiempo real...', 'info');
          
          // Eliminamos el polling ruidoso (los 6s y 12s). 
          // Ahora dependemos de los WebSockets para ver los resultados en vivo (handleDeviceFound y handleScanFinished).
          // Solo dejamos un Fallback de seguridad extrema (ej. 3 minutos) por si el worker muere silenciosamente.
          setTimeout(() => {
              if (isScanning.value) {
                  isScanning.value = false;
                  fetchPendingDevices();
              }
          }, 180000); 

        } else {
          isScanning.value = false;
        }
    }
    await fetchScanProfiles()
  } catch (e) { 
    showNotification(e.response?.data?.detail || 'Error', 'error'); 
    isScanning.value = false;
  }
}

function resetConfigForm() {
    scanConfig.value = { id: null, source_device_id: '', network_cidr: '192.168.88.0/24', interface: '', scan_ports: '8728, 80, 22', scan_mode: 'manual', credential_profile_id: null, is_active: false, scan_interval_minutes: 60, target_group: 'General', adopt_only_managed: false }
    probeSearchText.value = '';
    sensorsTemplateList.value = []
}

// --- ACTIONS INBOX ---
function toggleSelection(mac) { selectedPending.value.includes(mac) ? selectedPending.value = selectedPending.value.filter(m => m !== mac) : selectedPending.value.push(mac) }

function selectAll() {
  const visibleMacs = filteredPendingDevices.value.map(d => d.mac_address);
  const allVisibleSelected = visibleMacs.every(mac => selectedPending.value.includes(mac));
  
  if (allVisibleSelected) {
      selectedPending.value = selectedPending.value.filter(mac => !visibleMacs.includes(mac));
  } else {
      const newSelections = visibleMacs.filter(mac => !selectedPending.value.includes(mac));
      selectedPending.value.push(...newSelections);
  }
}

function openAdoptModal() {
  if (selectedPending.value.length === 0) return;
  adoptSensorsList.value = []; // Resetear receta al abrir
  adoptTargetGroup.value = 'General';
  showAdoptModal.value = true;
}

function cancelAdoption() {
  showAdoptModal.value = false;
}

// LÓGICA CONFIRMADA DESDE EL MODAL
async function confirmAdoption() {
  showAdoptModal.value = false;
  isAdopting.value = true;

  try {
    const devicesToAdopt = pendingDevices.value.filter((d) => selectedPending.value.includes(d.mac_address));
    
    // Procesar la receta de sensores del modal
    const finalSensorsPayload = adoptSensorsList.value.map(s => buildSensorConfigPayload(s));

    const payload = { 
        source_device_id: devicesToAdopt[0].source_device_id || devicesToAdopt[0].maestro_id, 
        credential_profile_id: adoptCredentialId.value, 
        target_group: adoptTargetGroup.value,
        sensors_config: finalSensorsPayload.length > 0 ? finalSensorsPayload : null,
        devices: devicesToAdopt, 
        naming_strategy: 'hostname' 
    };
    
    const { data } = await api.post('/discovery/adopt', payload); 
    
    if (data.status === 'processing') {
      showNotification('⏳ ' + data.message, 'info');
      
      pendingDevices.value = pendingDevices.value.filter(d => !selectedPending.value.includes(d.mac_address));
      selectedPending.value = [];

      [4000, 10000].forEach(delay => {
        setTimeout(async () => {
          await fetchPendingDevices();
          window.dispatchEvent(new Event('refresh-notifications'));
        }, delay);
      });

    } else if (data.adopted !== undefined) {
      if (data.adopted > 0) showNotification(`¡${data.adopted} adoptados!`, 'success');
      selectedPending.value = [];
      await fetchPendingDevices();
    }

  } catch (e) { 
    showNotification('Error al enviar orden de adopción', 'error') 
  } finally {
    isAdopting.value = false
  }
}

async function ignoreSelected() {
    if (selectedPending.value.length === 0) return;
    if (!confirm(`¿Ignorar ${selectedPending.value.length} dispositivos?`)) return;
    isLoading.value = true;
    try {
        await Promise.all(selectedPending.value.map(mac => api.delete(`/discovery/pending/${mac}`)));
        showNotification('Ignorados correctamente', 'success'); selectedPending.value = []; await fetchPendingDevices(); await fetchIgnoredDevices();
    } catch (e) { showNotification('Error', 'error') } finally { isLoading.value = false; }
}

async function deletePending(mac) {
  if (!confirm('¿Ignorar este dispositivo?')) return
  try { await api.delete(`/discovery/pending/${mac}`); await fetchPendingDevices(); await fetchIgnoredDevices(); showNotification('Movido a Ignorados', 'success') } catch (e) { showNotification('Error', 'error') }
}

// --- ACTIONS IGNORED ---
function toggleIgnoredSelection(mac) { selectedIgnored.value.includes(mac) ? selectedIgnored.value = selectedIgnored.value.filter(m => m !== mac) : selectedIgnored.value.push(mac) }

function selectAllIgnored() {
    const visibleMacs = filteredIgnoredDevices.value.map(d => d.mac_address);
    const allVisibleSelected = visibleMacs.every(mac => selectedIgnored.value.includes(mac));
    
    if (allVisibleSelected) {
        selectedIgnored.value = selectedIgnored.value.filter(mac => !visibleMacs.includes(mac));
    } else {
        const newSelections = visibleMacs.filter(mac => !selectedIgnored.value.includes(mac));
        selectedIgnored.value.push(...newSelections);
    }
}

async function restoreSelected() {
    if (selectedIgnored.value.length === 0) return;
    if (!confirm(`¿Restaurar ${selectedIgnored.value.length} dispositivos?`)) return;
    isLoading.value = true;
    try { await Promise.all(selectedIgnored.value.map(mac => api.post(`/discovery/restore/${mac}`))); showNotification('Restaurados', 'success'); selectedIgnored.value = []; await fetchIgnoredDevices(); await fetchPendingDevices(); } catch (e) { showNotification('Error', 'error') } finally { isLoading.value = false; }
}

async function hardDeleteSelected() {
    if (selectedIgnored.value.length === 0) return;
    if (!confirm(`⚠️ ¿Eliminar DEFINITIVAMENTE ${selectedIgnored.value.length} dispositivos?`)) return;
    isLoading.value = true;
    try { await Promise.all(selectedIgnored.value.map(mac => api.delete(`/discovery/ignored/${mac}`))); showNotification('Eliminados', 'info'); selectedIgnored.value = []; await fetchIgnoredDevices(); } catch (e) { showNotification('Error', 'error') } finally { isLoading.value = false; }
}

async function restoreDevice(mac) { if(!confirm('¿Restaurar?')) return; try { await api.post(`/discovery/restore/${mac}`); await fetchIgnoredDevices(); await fetchPendingDevices(); showNotification('Restaurado', 'success') } catch(e) {} }
async function hardDeleteDevice(mac) { if(!confirm('¿Eliminar DEFINITIVAMENTE?')) return; try { await api.delete(`/discovery/ignored/${mac}`); await fetchIgnoredDevices(); showNotification('Eliminado', 'info') } catch(e) {} }

// --- UTIL ---
async function deleteScanProfile(id) { if (!confirm('¿Eliminar tarea?')) return; try { await api.delete(`/discovery/profiles/${id}`); await fetchScanProfiles(); showNotification('Eliminada', 'success') } catch (e) {} }
function editScanProfile(profile) { 
    scanConfig.value = { ...scanConfig.value, id: profile.id, source_device_id: profile.source_device_id || profile.maestro_id, network_cidr: profile.network_cidr, interface: profile.interface, scan_ports: profile.scan_ports, scan_mode: profile.scan_mode, credential_profile_id: profile.credential_profile_id, is_active: profile.is_active, scan_interval_minutes: profile.scan_interval_minutes, target_group: profile.target_group || 'General', adopt_only_managed: profile.adopt_only_managed || false }
    if (profile.sensors_template) restoreSensorConfig(profile.sensors_template); else { sensorsTemplateList.value = [] }
    window.scrollTo({ top: 0, behavior: 'smooth' }); showNotification(`✏️ Editando: ${profile.network_cidr}`, 'info') 
}
function showNotification(msg, type) { notification.value = { show: true, message: msg, type }; setTimeout(() => (notification.value.show = false), 5000) }

function getProbeName(id) { 
    const p = availableProbes.value.find((x) => x.id === id) || maestros.value.find(x => x.id === id); 
    if (!p) return 'Desconocido';
    return `${p.client_name || p.name || p.ip_address} ${p.is_maestro ? '(👑)' : '(📡)'}`; 
}

function getCredentialName(id) { if (!id) return 'Sin Credenciales'; const c = credentialProfiles.value.find(p => p.id === id); return c ? c.name : 'ID Desconocido' }
async function toggleProfileStatus(profile) { const newState = !profile.is_active; try { profile.is_active = newState; await api.patch(`/discovery/profiles/${profile.id}/toggle`, { active: newState }); showNotification(newState ? 'Reanudada' : 'Pausada', 'info'); } catch (e) { profile.is_active = !newState; } }
</script>

<template>
  <div class="discovery-layout fade-in">
    <div v-if="notification.show" :class="['notification', notification.type]">
      {{ notification.message }}
    </div>

    <div class="header">
      <div class="title-block">
        <h1>📡 Centro de Descubrimiento</h1>
        <p class="subtitle">Escanea, clasifica y adopta dispositivos en tu red usando Sondas Gestionadas.</p>
      </div>
      <div class="tabs">
        <button :class="['tab-btn', { active: activeTab === 'inbox' }]" @click="activeTab = 'inbox'">
          📨 Bandeja de Entrada
          <span class="badge" v-if="pendingDevices.length">{{ pendingDevices.length }}</span>
        </button>
        <button :class="['tab-btn', { active: activeTab === 'ignored' }]" @click="activeTab = 'ignored'">
          🚫 Ignorados
          <span class="badge badge-gray" v-if="ignoredDevices.length">{{ ignoredDevices.length }}</span>
        </button>
        <button :class="['tab-btn', { active: activeTab === 'scanners' }]" @click="activeTab = 'scanners'">
          ⚙️ Motores de Escaneo
        </button>
      </div>
    </div>

    <div v-if="activeTab === 'inbox'" class="content-panel fade-in">
      
      <div class="filter-bar">
          <div class="search-group">
              <span class="icon">🔍</span>
              <input type="text" v-model="inboxFilter.search" placeholder="Buscar IP, MAC, Nombre..." class="filter-input" />
          </div>
          
          <div class="filter-controls">
              <select v-model="inboxFilter.vendor" class="filter-select">
                  <option value="">Todo Fabricante</option>
                  <option v-for="v in pendingVendors" :key="v" :value="v">{{ v }}</option>
              </select>

              <div class="toggle-group">
                  <button :class="{ active: inboxFilter.type === 'all' }" @click="inboxFilter.type = 'all'">Todos</button>
                  <button :class="{ active: inboxFilter.type === 'infra' }" @click="inboxFilter.type = 'infra'" title="Mikrotik, Ubiquiti, Cisco...">Infra</button>
                  <button :class="{ active: inboxFilter.type === 'generic' }" @click="inboxFilter.type = 'generic'">Genéricos</button>
              </div>
          </div>
      </div>

      <div class="toolbar">
        <div class="toolbar-left">
          <span class="selection-count" v-if="selectedPending.length > 0">
            {{ selectedPending.length }} seleccionados
          </span>
          <span class="selection-count" v-else> 
              Mostrando {{ filteredPendingDevices.length }} de {{ pendingDevices.length }}
          </span>
        </div>
        <div class="toolbar-right">
            <button v-if="selectedPending.length > 0" @click="ignoreSelected" class="btn-action-del" style="margin-right: 15px;">
                🚫 Ignorar ({{ selectedPending.length }})
            </button>

            <button v-if="selectedPending.length > 0" @click="openAdoptModal" class="btn-adopt" :disabled="isAdopting">
                {{ isAdopting ? '⏳ Adoptando...' : '✅ Adoptar Seleccionados' }}
            </button>

            <button @click="loadGlobalData" class="btn-icon" title="Recargar Lista" style="margin-left: 15px;">🔄</button>
        </div>
      </div>

      <div class="table-container">
        <table class="devices-table">
          <thead>
            <tr>
              <th width="40">
                <input type="checkbox" @change="selectAll" 
                       :checked="selectedPending.length > 0 && filteredPendingDevices.length > 0 && filteredPendingDevices.every(d => selectedPending.includes(d.mac_address))" />
              </th>
              <th>IP Address</th>
              <th>MAC Address</th>
              <th>Identity</th>
              <th>Fabricante</th>
              <th>Plataforma</th>
              <th>Hostname</th>
              <th>Origen</th>
              <th>Acciones</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="filteredPendingDevices.length === 0">
              <td colspan="9" class="empty-row">
                  {{ pendingDevices.length === 0 ? '📭 Bandeja vacía.' : '🔍 No se encontraron dispositivos con los filtros actuales.' }}
              </td>
            </tr>
            <tr v-for="dev in filteredPendingDevices" :key="dev.mac_address" :class="{ selected: selectedPending.includes(dev.mac_address) }">
              <td>
                <input type="checkbox" :checked="selectedPending.includes(dev.mac_address)" @click="toggleSelection(dev.mac_address)" />
              </td>
              <td class="font-mono">
                <div class="text-highlight">{{ dev.ip_address }}</div>
                <div class="text-dim" style="font-size: 0.8rem; margin-top: 3px;" v-if="(dev.api_port && dev.api_port !== 8728) || (dev.ssh_port && dev.ssh_port !== 22)">
                  <span v-if="dev.api_port && dev.api_port !== 8728 && dev.api_port !== 22" style="color: var(--blue); margin-right: 5px;">API: {{ dev.api_port }}</span>
                  <span v-if="dev.ssh_port && dev.ssh_port !== 22" style="color: var(--green);">SSH: {{ dev.ssh_port }}</span>
                </div>
              </td>
              <td class="font-mono text-dim">{{ dev.mac_address }}</td>
              <td class="text-highlight font-weight-bold">{{ dev.identity || '-' }}</td>
              <td>{{ dev.vendor || 'Desconocido' }}</td>
              <td>{{ dev.platform || '-' }}</td>
              <td>{{ dev.hostname || '-' }}</td>
              <td>{{ getProbeName(dev.source_device_id || dev.maestro_id) }}</td>
              <td>
                <button @click="deletePending(dev.mac_address)" class="btn-sm btn-del" title="Ignorar (Mover a Blacklist)">🚫</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div v-if="activeTab === 'ignored'" class="content-panel fade-in">
        <div class="filter-bar filter-bar-ignored">
            <div class="search-group">
                <span class="icon">🔍</span>
                <input type="text" v-model="ignoredFilter.search" placeholder="Buscar en Ignorados..." class="filter-input" />
            </div>
            <div class="filter-controls">
                <select v-model="ignoredFilter.vendor" class="filter-select">
                    <option value="">Todo Fabricante</option>
                    <option v-for="v in ignoredVendors" :key="v" :value="v">{{ v }}</option>
                </select>
                <div class="toggle-group">
                    <button :class="{ active: ignoredFilter.type === 'all' }" @click="ignoredFilter.type = 'all'">Todos</button>
                    <button :class="{ active: ignoredFilter.type === 'infra' }" @click="ignoredFilter.type = 'infra'">Infra</button>
                    <button :class="{ active: ignoredFilter.type === 'generic' }" @click="ignoredFilter.type = 'generic'">Genéricos</button>
                </div>
            </div>
        </div>
        <div class="toolbar" style="background: rgba(255,50,50,0.1); border-color: var(--error-red);">
            <div class="toolbar-left">
                <span class="selection-count" style="color: white; font-weight: bold;" v-if="selectedIgnored.length > 0">
                    {{ selectedIgnored.length }} seleccionados
                </span>
                <span class="selection-count" style="color: #ffaaaa;" v-else>
                    🚫 Mostrando {{ filteredIgnoredDevices.length }} ignorados
                </span>
            </div>
            <div class="toolbar-right">
                <div v-if="selectedIgnored.length > 0" style="display: flex; gap: 10px; margin-right: 15px;">
                    <button @click="restoreSelected" class="btn-action-restore">♻️ Restaurar ({{ selectedIgnored.length }})</button>
                    <button @click="hardDeleteSelected" class="btn-action-del">💀 Olvidar ({{ selectedIgnored.length }})</button>
                </div>
                <button @click="fetchIgnoredDevices" class="btn-icon" title="Recargar Lista">🔄</button>
            </div>
        </div>
        <div class="table-container">
            <table class="devices-table">
                <thead>
                    <tr>
                        <th width="40"><input type="checkbox" @change="selectAllIgnored" :checked="selectedIgnored.length > 0 && filteredIgnoredDevices.length > 0 && filteredIgnoredDevices.every(d => selectedIgnored.includes(d.mac_address))" /></th>
                        <th>IP Address</th><th>MAC Address</th><th>Identity</th><th>Fabricante</th><th>Plataforma</th><th>Hostname</th><th style="text-align: right;">Acciones</th>
                    </tr>
                </thead>
                <tbody>
                    <tr v-if="filteredIgnoredDevices.length === 0">
                        <td colspan="8" class="empty-row">{{ ignoredDevices.length === 0 ? '✅ No hay dispositivos ignorados.' : '🔍 No se encontraron dispositivos con los filtros actuales.' }}</td>
                    </tr>
                    <tr v-for="dev in filteredIgnoredDevices" :key="dev.mac_address" class="ignored-row" :class="{ selected: selectedIgnored.includes(dev.mac_address) }">
                        <td><input type="checkbox" :checked="selectedIgnored.includes(dev.mac_address)" @click="toggleIgnoredSelection(dev.mac_address)" /></td>
                        <td class="font-mono text-dim">
                          {{ dev.ip_address }}
                          <div style="font-size: 0.8rem; margin-top: 3px;" v-if="(dev.api_port && dev.api_port !== 8728) || (dev.ssh_port && dev.ssh_port !== 22)">
                            <span v-if="dev.api_port && dev.api_port !== 8728 && dev.api_port !== 22" style="color: var(--blue); margin-right: 5px;">API: {{ dev.api_port }}</span>
                            <span v-if="dev.ssh_port && dev.ssh_port !== 22" style="color: var(--green);">SSH: {{ dev.ssh_port }}</span>
                          </div>
                        </td>
                        <td class="font-mono text-dim">{{ dev.mac_address }}</td><td class="text-dim">{{ dev.identity || '-' }}</td><td class="text-dim">{{ dev.vendor || 'Desconocido' }}</td><td class="text-dim">{{ dev.platform || '-' }}</td><td class="text-dim">{{ dev.hostname || '-' }}</td>
                        <td style="text-align: right;">
                            <button @click="restoreDevice(dev.mac_address)" class="btn-sm btn-restore" title="Restaurar" style="margin-right: 10px;">♻️</button>
                            <button @click="hardDeleteDevice(dev.mac_address)" class="btn-sm btn-del" title="Olvidar Definitivamente">💀</button>
                        </td>
                    </tr>
                </tbody>
            </table>
        </div>
    </div>

    <div v-if="activeTab === 'scanners'" class="content-grid fade-in">
      <aside class="config-panel">
        <div class="panel-header">
          <h3>{{ scanConfig.id ? '✏️ Editando Tarea' : '🚀 Nuevo Escaneo' }}</h3>
        </div>
        <div class="form-body">
          
          <div class="form-group dropdown-container" v-blur="hideProbeDropdown">
            <label>Dispositivo Origen (Sonda de Red)</label>
            <div class="search-input probe-input" @click="isProbeDropdownOpen = true; probeSearchText = ''">
                <template v-if="scanConfig.source_device_id">
                    <span class="selected-probe-text">{{ selectedProbeName }}</span>
                    <button @click.stop="clearProbe" class="btn-clear-probe" title="Limpiar Sonda">✖</button>
                </template>
                <template v-else>
                    <input 
                        type="text" 
                        v-model="probeSearchText" 
                        placeholder="Buscar router gestionado o maestro..." 
                        class="probe-search-field"
                    />
                </template>
            </div>
            
            <div v-if="isProbeDropdownOpen && !scanConfig.source_device_id" class="probe-dropdown fade-in">
                <div v-if="filteredProbes.length === 0" class="probe-option empty">No se encontraron dispositivos gestionados.</div>
                <div 
                    v-for="p in filteredProbes" 
                    :key="p.id" 
                    @click="selectProbe(p)"
                    class="probe-option"
                >
                    <div class="probe-icon">{{ p.is_maestro ? '👑' : '📡' }}</div>
                    <div class="probe-details">
                        <strong>{{ p.client_name }}</strong>
                        <span>{{ p.ip_address }} | {{ p.vendor || 'Generic' }}</span>
                    </div>
                </div>
            </div>
          </div>
          <div class="form-group">
            <label>Red Objetivo (CIDR)</label>
            <input type="text" v-model="scanConfig.network_cidr" placeholder="Ej: 192.168.88.0/24" />
          </div>
          <div class="form-group">
            <label style="display: flex; justify-content: space-between; align-items: center;">
                Interfaz
                <span v-if="isLoadingInterfaces" style="font-size: 0.8rem; color: var(--blue);">⏳ Detectando...</span>
            </label>
            <select v-model="scanConfig.interface" :disabled="isLoadingInterfaces || (!maestroInterfaces.length && !scanConfig.interface)">
                <option value="">Auto-detectar (Recomendado)</option>
                <option v-if="scanConfig.interface && !maestroInterfaces.some(i => i.name === scanConfig.interface)" :value="scanConfig.interface">{{ scanConfig.interface }} (Manual)</option>
                <option v-for="iface in maestroInterfaces" :key="iface.name" :value="iface.name">{{ iface.name }} {{ iface.type !== 'unknown' ? `[${iface.type}]` : '' }} {{ iface.disabled ? '(Inactiva)' : '' }}</option>
            </select>
          </div>
          <div class="form-group">
            <label>Puertos</label>
            <input type="text" v-model="scanConfig.scan_ports" placeholder="8728, 80, 22" />
          </div>
          <div class="form-group">
            <label>Credenciales Default</label>
            <select v-model="scanConfig.credential_profile_id">
              <option :value="null">-- Ninguno --</option>
              <option v-for="p in credentialProfiles" :key="p.id" :value="p.id">{{ p.name }}</option>
            </select>
          </div>

          <div class="automation-box">
            <h4>🤖 Automatización</h4>
            <div class="checkbox-row">
              <input type="checkbox" id="activeTask" v-model="scanConfig.is_active" />
              <label for="activeTask">Tarea Recurrente</label>
            </div>
            <template v-if="scanConfig.is_active">
              <div class="form-group interval-group">
                <label>Intervalo (min)</label>
                <div class="input-hint-row">
                  <input type="number" v-model.number="scanConfig.scan_interval_minutes" min="5" placeholder="60" />
                  <span class="hint">Recomendado: >15 min</span>
                </div>
              </div>
              <div class="radio-group">
                <label><input type="radio" v-model="scanConfig.scan_mode" value="notify" /> Notificar</label>
                <label><input type="radio" v-model="scanConfig.scan_mode" value="auto" /> Auto-Adoptar</label>
              </div>
               <div v-if="scanConfig.scan_mode === 'notify' || (scanConfig.scan_mode === 'auto' && sensorsTemplateList.length === 0)" class="checkbox-row" style="margin-top:10px; margin-bottom:15px; margin-left:5px;">
                   <input type="checkbox" id="chkManaged" v-model="scanConfig.adopt_only_managed" />
                   <label for="chkManaged" style="font-size:0.9rem; color:#ccc;">Solo Gestionados (Credenciales)</label>
              </div>
              <div v-if="scanConfig.scan_mode === 'auto'" class="auto-adopt-panel fade-in">
                <hr class="separator" />
                <h4 class="mini-title">🏗️ Receta</h4>
                <div class="form-group">
                  <label>Grupo de Dispositivos Nuevos</label>
                  <select v-model="scanConfig.target_group">
                    <option value="General">General</option>
                    <option v-for="g in groups" :key="g" :value="g">{{ g }}</option>
                  </select>
                </div>
                
                <div class="sensors-recipe-container">
                    <div class="add-sensor-controls">
                        <select v-model="newSensorType" class="mini-select" style="width: auto;">
                            <option value="ping">📡 Ping</option>
                            <option value="ethernet">🔌 Ethernet</option>
                            <option value="wireless">📶 Wireless</option>
                            <option value="system" :disabled="hasSystemSensorScanner">🖥️ Sistema</option>
                        </select>
                        <button @click="addSensorToRecipe(sensorsTemplateList, hasSystemSensorScanner)" class="btn-sm btn-action-restore" style="margin-left: 10px;">➕ Añadir Sensor</button>
                    </div>

                    <div class="sensor-cards-list">
                        <div v-for="(sensor, index) in sensorsTemplateList" :key="sensor.id" class="sensor-card fade-in">
                            <div class="sensor-card-header">
                                <div><span class="sensor-icon">{{ getSensorIcon(sensor.sensor_type) }}</span><strong>{{ sensor.sensor_type.toUpperCase() }}</strong></div>
                                <button @click="removeSensor(sensorsTemplateList, index)" class="btn-sm btn-del btn-remove-sensor" title="Eliminar Sensor">🗑️</button>
                            </div>

                            <div class="mini-config">
                                <SensorConfigurator
                                    v-model="sensorsTemplateList[index]"
                                    :sensor-type="sensor.sensor_type"
                                    :channels="channels"
                                    :auto-tasks="autoTasks"
                                    :suggested-target-devices="[]"
                                    :has-parent-maestro="true"
                                    :device-interfaces="[]"
                                    :is-loading-interfaces="isLoadingInterfaces"
                                    hide-name
                                    is-compact
                                />
                            </div>
                        </div>
                    </div>
                </div>
              </div>
            </template>
          </div>
          <div class="form-actions">
            <button v-if="scanConfig.id" @click="resetConfigForm" class="btn-cancel" :disabled="isScanning">❌ Cancelar</button>
            <button @click="runScan" class="btn-scan" :disabled="isScanning">
               {{ isScanning ? '⏳ Escaneando red...' : (scanConfig.id ? '💾 Guardar Cambios' : (scanConfig.is_active ? '💾 Guardar Tarea' : '🚀 Escanear Ahora')) }}
            </button>
          </div>
        </div>
      </aside>

      <section class="profiles-panel">
        <div class="panel-header"><h3>⚙️ Tareas Activas</h3></div>
        <div class="profiles-list">
          <div v-if="scanProfiles.length === 0" class="empty-list">Sin tareas.</div>
          <div v-for="prof in scanProfiles" :key="prof.id" class="profile-card">
            <div class="profile-info">
              <strong>{{ getProbeName(prof.source_device_id || prof.maestro_id) }}</strong>
              <div class="profile-details"><span>🌐 {{ prof.network_cidr }}</span><span>🔌 {{ prof.interface || 'Auto-detectada' }}</span></div>
              <div class="profile-sub-details">
                 <span class="cred-badge">🔐 {{ getCredentialName(prof.credential_profile_id) }}</span>
                 <span v-if="prof.scan_mode === 'auto'" class="auto-tag">🤖 Auto</span>
                 <span v-else class="notify-tag">🔔 Notify</span>
              </div>
            </div>
            <div class="profile-actions">
              <button @click="editScanProfile(prof)" class="btn-icon-action btn-edit" title="Editar">✏️</button>
              <button @click="toggleProfileStatus(prof)" class="btn-icon-action">{{ prof.is_active ? '⏸️' : '▶️' }}</button>
              <button @click="deleteScanProfile(prof.id)" class="btn-sm btn-del" title="Eliminar">🗑️</button>
            </div>
          </div>
        </div>
      </section>
    </div>

    <div v-if="showAdoptModal" class="modal-overlay fade-in">
        <div class="modal-content">
            <div class="modal-header">
                <h3>🚀 Adoptar Dispositivos ({{ selectedPending.length }})</h3>
                <button @click="cancelAdoption" class="btn-icon">✖️</button>
            </div>
            
            <div class="modal-body" style="max-height: 70vh; overflow-y: auto;">
                <p style="color: #aaa; margin-bottom: 20px; font-size: 0.9rem;">
                    Configura las credenciales, el grupo y la receta de monitoreo que se aplicará a todos los equipos seleccionados.
                </p>

                <div class="form-group">
                    <label>🔐 Credenciales Globales (Opcional)</label>
                    <select v-model="adoptCredentialId" class="search-input">
                        <option :value="null">-- Usar Credenciales del Escaneo / Ninguna --</option>
                        <option v-for="p in credentialProfiles" :key="p.id" :value="p.id">{{ p.name }}</option>
                    </select>
                </div>

                <div class="form-group">
                    <label>🗂️ Grupo de Destino</label>
                    <select v-model="adoptTargetGroup" class="search-input">
                        <option value="General">General</option>
                        <option v-for="g in groups" :key="g" :value="g">{{ g }}</option>
                    </select>
                </div>

                <hr class="separator" style="margin: 20px 0;" />
                
                <h4 class="mini-title">🏗️ Receta de Sensores (Opcional)</h4>
                
                <div class="sensors-recipe-container" style="margin-top: 10px;">
                    <div class="add-sensor-controls">
                        <select v-model="newSensorType" class="mini-select" style="width: auto;">
                            <option value="ping">📡 Ping</option>
                            <option value="ethernet">🔌 Ethernet</option>
                            <option value="wireless">📶 Wireless</option>
                            <option value="system" :disabled="hasSystemSensorModal">🖥️ Sistema</option>
                        </select>
                        <button @click="addSensorToRecipe(adoptSensorsList, hasSystemSensorModal)" class="btn-sm btn-action-restore" style="margin-left: 10px;">➕ Añadir Sensor</button>
                    </div>

                    <div class="sensor-cards-list">
                        <div v-for="(sensor, index) in adoptSensorsList" :key="sensor.id" class="sensor-card fade-in">
                            <div class="sensor-card-header">
                                <div><span class="sensor-icon">{{ getSensorIcon(sensor.sensor_type) }}</span><strong>{{ sensor.sensor_type.toUpperCase() }}</strong></div>
                                <button @click="removeSensor(adoptSensorsList, index)" class="btn-sm btn-del btn-remove-sensor" title="Eliminar Sensor">🗑️</button>
                            </div>

                            <div class="mini-config">
                                <SensorConfigurator
                                    v-model="adoptSensorsList[index]"
                                    :sensor-type="sensor.sensor_type"
                                    :channels="channels"
                                    :auto-tasks="autoTasks"
                                    :suggested-target-devices="[]"
                                    :has-parent-maestro="true"
                                    :device-interfaces="[]"
                                    :is-loading-interfaces="false"
                                    hide-name
                                    is-compact
                                />
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <div class="modal-footer" style="margin-top: 20px; display: flex; justify-content: flex-end; gap: 15px; border-top: 1px solid rgba(255,255,255,0.1); padding-top: 15px;">
                <button @click="cancelAdoption" class="btn-cancel">Cancelar</button>
                <button @click="confirmAdoption" class="btn-scan" style="flex: none; padding: 10px 20px;">🚀 Confirmar Adopción</button>
            </div>
        </div>
    </div>

  </div>
</template>

<style scoped>
/* ESTILOS GLOBALES */
.discovery-layout { max-width: 1400px; margin: 0 auto; padding: 20px; }
.header { display: flex; justify-content: space-between; align-items: flex-end; margin-bottom: 20px; border-bottom: 1px solid var(--primary-color); padding-bottom: 10px; }
.title-block h1 { margin: 0; color: var(--blue); font-size: 1.8rem; }
.title-block .subtitle { margin: 5px 0 0; color: var(--gray); font-size: 0.9rem; }
.tabs { display: flex; gap: 10px; }
.tab-btn { background: none; border: none; padding: 10px 20px; color: var(--gray); font-size: 1rem; cursor: pointer; border-radius: 8px 8px 0 0; transition: all 0.2s; position: relative; }
.tab-btn:hover { color: #ccc; }
.tab-btn.active { background-color: var(--primary-color); color: white; font-weight: bold; }
.badge { background: var(--error-red); color: white; font-size: 0.7rem; padding: 2px 6px; border-radius: 10px; position: absolute; top: 5px; right: 5px; }
.badge-gray { background: #555; color: #ccc; font-size: 0.7rem; padding: 2px 6px; border-radius: 10px; position: absolute; top: 5px; right: 5px; }

/* ESTILOS PARA LA BARRA DE FILTROS (SINCRONIZADOS CON INVENTARIO) */
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
.filter-bar-ignored { background: rgba(255, 50, 50, 0.05); }
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
.filter-controls { display: flex; align-items: center; gap: 15px; flex-wrap: wrap; }
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
.toggle-group { display: flex; background: var(--bg-color); border-radius: 6px; border: 1px solid #444; overflow: hidden; }
.toggle-group button { background: transparent; border: none; color: #aaa; padding: 6px 12px; cursor: pointer; font-size: 0.85rem; transition: all 0.2s; border-right: 1px solid #444; }
.toggle-group button:last-child { border-right: none; }
.toggle-group button:hover { color: white; background: rgba(255,255,255,0.05); }
.toggle-group button.active { background: var(--primary-color); color: white; font-weight: bold; }

/* TOOLBAR & ACTIONS */
.toolbar { background: var(--surface-color); padding: 15px; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid rgba(255,255,255,0.05); }
.selection-count { color: #aaa; font-weight: 500; }
.toolbar-right { display: flex; gap: 15px; align-items: center; }
.adopt-control { display: flex; gap: 10px; background: var(--bg-color); padding: 5px; border-radius: 6px; border: 1px solid var(--primary-color); }
.credential-select { background: transparent; border: none; color: white; padding: 5px; outline: none; }
.credential-select option { background-color: var(--bg-color); color: white; }
.btn-adopt { background: var(--green); color: white; border: none; padding: 8px 15px; border-radius: 4px; cursor: pointer; font-weight: bold; transition: all 0.2s; }
.btn-adopt:hover { background: #28a745; transform: scale(1.02); }
.btn-adopt:disabled { background: var(--bg-color); color: var(--gray); cursor: not-allowed; opacity: 0.5; transform: none; }
.btn-icon { background: none; border: none; font-size: 1.2rem; cursor: pointer; color: var(--gray); }

/* BOTONES MASIVOS NUEVOS */
.btn-action-restore { background: transparent; border: 1px solid var(--green); color: var(--green); padding: 6px 12px; border-radius: 6px; cursor: pointer; font-weight: bold; transition: all 0.2s; }
.btn-action-restore:hover { background: var(--green); color: white; }
.btn-action-del { background: transparent; border: 1px solid var(--error-red); color: var(--error-red); padding: 6px 12px; border-radius: 6px; cursor: pointer; font-weight: bold; transition: all 0.2s; }
.btn-action-del:hover { background: var(--error-red); color: white; }

/* TABLES */
.table-container { background: var(--surface-color); border-radius: 0 0 8px 8px; overflow: hidden; }
.devices-table { width: 100%; border-collapse: collapse; }
.devices-table th { background: rgba(255, 255, 255, 0.05); color: var(--gray); text-align: left; padding: 12px; font-size: 0.9rem; }
.devices-table td { padding: 12px; border-bottom: 1px solid var(--primary-color); color: white; }
.devices-table tr:hover { background: rgba(255, 255, 255, 0.03); }
.devices-table tr.selected { background: rgba(106, 180, 255, 0.1); }
.ignored-row td { color: #888; }
.font-mono { font-family: monospace; }
.text-highlight { color: var(--blue); }
.text-dim { color: #777; }
.font-weight-bold { font-weight: bold; }
.empty-row { text-align: center; padding: 40px; color: var(--gray); font-style: italic; border: 2px dashed var(--primary-color); margin: 20px; }

/* MINI BUTTONS */
.btn-sm { padding: 4px 8px; border: none; border-radius: 4px; cursor: pointer; }
.btn-del { background: transparent; border: 1px solid var(--error-red); color: var(--error-red); }
.btn-del:hover { background-color: var(--error-red); color: white; }
.btn-restore { background: transparent; border: 1px solid var(--green); color: var(--green); }
.btn-restore:hover { background-color: var(--green); color: white; }

/* LAYOUT SCANNERS */
.content-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(350px, 1fr)); gap: 20px; }
.config-panel { background: var(--surface-color); border-radius: 12px; overflow: hidden; align-self: start; }
.panel-header { background: rgba(255, 255, 255, 0.05); padding: 15px; border-bottom: 1px solid var(--primary-color); }
.panel-header h3 { margin: 0; color: var(--blue); font-size: 1.1rem; }
.form-body { padding: 20px; }
.form-group { margin-bottom: 15px; }
.form-group label { display: block; margin-bottom: 5px; font-weight: 500; font-size: 0.9rem; color: var(--gray); }
.form-group input, .form-group select { width: 100%; padding: 10px; background-color: var(--bg-color); border: 1px solid var(--primary-color); color: white; border-radius: 6px; }
.form-group select option { background-color: var(--bg-color); color: white; }
.search-input { width: 100%; padding: 10px; background-color: var(--bg-color); border: 1px solid var(--primary-color); color: white; border-radius: 6px; font-size: 0.9rem; }
.custom-textarea { padding: 6px 10px; min-height: 45px; margin-bottom: 5px; resize: vertical; } 
.form-group small { display: block; margin-top: 4px; color: #777; font-size: 0.8rem; }
.required { color: var(--error-red); font-size: 0.8rem; }
.automation-box { background: var(--bg-color); padding: 15px; border-radius: 6px; margin-bottom: 20px; border: 1px dashed var(--primary-color); }
.automation-box h4 { margin: 0 0 10px 0; font-size: 0.95rem; color: var(--gray); border-bottom: 1px solid #333; padding-bottom: 5px; }
.checkbox-row { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; color: white; }
.radio-group { display: flex; gap: 15px; margin-bottom: 10px; font-size: 0.9rem; color: #ccc; }
.auto-adopt-panel { margin-top: 15px; padding-top: 10px; }
.separator { border: 0; border-top: 1px solid var(--primary-color); margin: 10px 0; opacity: 0.5; }
.separator-light { border: 0; border-top: 1px dashed #555; margin: 8px 0; }
.mini-title { color: var(--blue); font-size: 0.9rem; margin-bottom: 10px; }

/* NUEVOS ESTILOS DE RECETA DE SENSORES */
.sensors-recipe-container { margin-top: 15px; }
.add-sensor-controls { display: flex; align-items: center; margin-bottom: 15px; background: rgba(0,0,0,0.2); padding: 10px; border-radius: 6px; }
.sensor-cards-list { display: flex; flex-direction: column; gap: 10px; }
.sensor-card { background: rgba(255, 255, 255, 0.03); border: 1px solid var(--primary-color); border-radius: 6px; overflow: hidden; }
.sensor-card-header { background: rgba(0, 0, 0, 0.2); padding: 8px 12px; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid rgba(255,255,255,0.05); }
.sensor-icon { margin-right: 8px; font-size: 1.1rem; }
.btn-remove-sensor { opacity: 0.7; }
.btn-remove-sensor:hover { opacity: 1; }

.mini-config { padding: 15px; margin-top: 0; margin-bottom: 0; background: transparent; }
.config-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.chk-label { display: flex; align-items: center; gap: 8px; font-size: 0.85rem; color: #ccc; margin-top: 8px; }
.alert-details { display: flex; gap: 5px; margin-top: 5px; margin-left: 10px; flex-wrap: wrap; align-items: center; }
.mini-select { padding: 4px; font-size: 0.8rem; background: var(--bg-color); border: 1px solid #555; color: white; border-radius: 4px; width: 90px; }
.tiny-input { width: 50px !important; padding: 4px !important; font-size: 0.8rem; height: 28px; background-color: var(--bg-color); border: 1px solid #555; color: white; border-radius: 4px; }
.tiny-input-full { width: 100% !important; padding: 6px !important; font-size: 0.85rem; }
.tiny-chk { font-size: 0.75rem; display: flex; align-items: center; gap: 3px; color: #aaa; }
.auto-tag { font-size: 0.75rem; color: var(--green); margin-top: 4px; font-weight: bold; }
.btn-scan { flex: 1; padding: 12px; background: var(--blue); color: white; border: none; border-radius: 6px; font-weight: bold; cursor: pointer; font-size: 1rem; }
.btn-scan:disabled { opacity: 0.7; cursor: not-allowed; }
.btn-cancel { padding: 12px 15px; background: transparent; border: 1px solid var(--gray); color: var(--gray); border-radius: 6px; font-weight: bold; cursor: pointer; margin-right: 10px; transition: all 0.2s; }
.btn-cancel:hover { border-color: white; color: white; }
.form-actions { display: flex; justify-content: space-between; }
.profiles-panel { background: var(--surface-color); border-radius: 12px; }
.profiles-list { padding: 20px; }
.empty-list { color: var(--gray); text-align: center; padding: 20px; border: 2px dashed var(--primary-color); border-radius: 8px; }
.profile-card { display: flex; justify-content: space-between; align-items: center; padding: 15px; background: var(--bg-color); border-radius: 8px; margin-bottom: 10px; }
.profile-info strong { display: block; margin-bottom: 5px; color: white; }
.profile-details { font-size: 0.85rem; color: #aaa; display: flex; gap: 15px; }
.profile-actions { display: flex; align-items: center; gap: 10px; }
.notification { position: fixed; top: 90px; right: 20px; padding: 1rem 1.5rem; border-radius: 8px; color: white; font-weight: bold; z-index: 1000; }
.notification.success { background: var(--green); }
.notification.error { background: var(--error-red); }
.notification.info { background: var(--blue); }
.fade-in { animation: fadeIn 0.3s ease; }
@keyframes fadeIn { from { opacity: 0; transform: translateY(5px); } to { opacity: 1; transform: 0; } }
.interval-group input { width: 100px; }
.input-hint-row { display: flex; align-items: center; gap: 10px; }
.hint { font-size: 0.8rem; color: #ffcc00; }
.profile-sub-details { margin-top: 5px; font-size: 0.8rem; display: flex; gap: 10px; align-items: center; }
.cred-badge { background: rgba(255,255,255,0.1); padding: 2px 6px; border-radius: 4px; color: #ddd; }
.notify-tag { color: var(--blue); font-weight: bold; }
.sensors-badge { background: rgba(100, 200, 255, 0.1); padding: 2px 6px; border-radius: 4px; color: #89cff0; border: 1px solid rgba(137, 207, 240, 0.3); }
.managed-badge { background: rgba(255, 165, 0, 0.1); padding: 2px 6px; border-radius: 4px; color: #ffa500; border: 1px solid rgba(255, 165, 0, 0.3); }
.btn-icon-action { background: none; border: 1px solid var(--primary-color); border-radius: 50%; width: 32px; height: 32px; cursor: pointer; display: flex; align-items: center; justify-content: center; font-size: 1rem; color: white; transition: all 0.2s; margin-right: 5px; }
.btn-icon-action:hover { background: rgba(255,255,255,0.1); }
.btn-edit:hover { border-color: var(--blue); color: var(--blue); }

/* ESTILO NUEVO PARA PING AUTO-TARGET */
.auto-ip-text {
    color: #aaa;
    font-style: italic;
    background-color: rgba(255, 255, 255, 0.05) !important;
    cursor: not-allowed;
    border-color: #555 !important;
    display: flex;
    align-items: center;
    user-select: none;
}

/* ========================================================================= */
/* ESTILOS DEL MODAL Y AUTOCOMPLETE */
/* ========================================================================= */
.modal-overlay {
    position: fixed;
    top: 0;
    left: 0;
    width: 100vw;
    height: 100vh;
    background: rgba(0, 0, 0, 0.7);
    backdrop-filter: blur(5px);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 2000;
}

.modal-content {
    background: var(--surface-color);
    border: 1px solid var(--primary-color);
    border-radius: 12px;
    width: 90%;
    max-width: 600px;
    padding: 20px;
    box-shadow: 0 10px 30px rgba(0,0,0,0.5);
}

.modal-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 1px solid rgba(255,255,255,0.1);
    padding-bottom: 10px;
    margin-bottom: 15px;
}

.modal-header h3 {
    margin: 0;
    color: var(--blue);
}

.modal-body::-webkit-scrollbar { width: 8px; }
.modal-body::-webkit-scrollbar-track { background: rgba(255,255,255,0.05); border-radius: 4px; }
.modal-body::-webkit-scrollbar-thumb { background: var(--primary-color); border-radius: 4px; }
.modal-body::-webkit-scrollbar-thumb:hover { background: var(--blue); }

/* NUEVOS ESTILOS PARA DROPDOWN (PROBES) */
.dropdown-container { position: relative; }
.probe-input { display: flex; align-items: center; justify-content: space-between; cursor: pointer; padding: 0 !important; overflow: hidden; }
.probe-search-field { width: 100%; border: none; background: transparent; color: white; padding: 10px; outline: none; }
.selected-probe-text { padding: 10px; color: white; font-weight: bold; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.btn-clear-probe { background: none; border: none; color: var(--gray); cursor: pointer; padding: 0 15px; transition: color 0.2s; font-size: 1.1rem; }
.btn-clear-probe:hover { color: var(--error-red); }
.probe-dropdown { position: absolute; top: 100%; left: 0; width: 100%; background: var(--bg-color); border: 1px solid var(--primary-color); border-radius: 0 0 6px 6px; border-top: none; max-height: 250px; overflow-y: auto; z-index: 10; box-shadow: 0 5px 15px rgba(0,0,0,0.3); }
.probe-option { display: flex; align-items: center; padding: 10px; border-bottom: 1px solid rgba(255,255,255,0.05); cursor: pointer; transition: background 0.2s; }
.probe-option:last-child { border-bottom: none; }
.probe-option:hover { background: rgba(106, 180, 255, 0.1); }
.probe-option.empty { color: #aaa; font-style: italic; cursor: default; }
.probe-option.empty:hover { background: transparent; }
.probe-icon { font-size: 1.2rem; margin-right: 10px; }
.probe-details { display: flex; flex-direction: column; }
.probe-details strong { color: white; font-size: 0.9rem; margin-bottom: 2px; }
.probe-details span { color: #aaa; font-size: 0.75rem; font-family: monospace; }
</style>