<script setup>
import { ref, onMounted, computed, onUnmounted } from 'vue'
import api from '@/lib/api'

// --- AÑADIDO: Importamos el gestor central de WebSockets ---
import { connectWebSocketWhenAuthenticated, getCurrentWebSocket } from '@/lib/ws'

// --- ESTADO GLOBAL ---
const activeTab = ref('credentials') // 'credentials' | 'profiles'
const notification = ref({ show: false, message: '', type: 'success' })

// --- ESTADO CREDENCIALES (BÓVEDA) ---
const savedCredentials = ref([])
const newCredential = ref({
  name: '',
  username: '',
  password: '',
  type: 'mikrotik_api',
  vendor: 'Mikrotik', // Default
  is_password_only: false,
})
const credentialToDeleteId = ref(null)

// --- ESTADO PERFILES (LLAVEROS) ---
const savedProfiles = ref([])
const isProfileModalOpen = ref(false)
const profileToDeleteId = ref(null)

// Formulario reactivo para crear/editar perfil
const profileForm = ref({
  id: null,
  name: '',
  selectedCreds: [], // Array de objetos {id, name, username, type}
})

// --- ESTADO ROTACIÓN MASIVA ---
const isRotateModalOpen = ref(false)
const rotateSourceCred = ref(null)
const rotateMode = ref('new') // 'new' | 'existing'
const rotateTargetId = ref(null)
const rotateNewCred = ref({
  name: '',
  username: '',
  password: '',
  type: 'mikrotik_api',
  vendor: 'Mikrotik',
  is_password_only: false,
})

// NUEVO: Estado para cargar y seleccionar dispositivos manualmente
const allDevices = ref([])
const isLoadingDevices = ref(false)
const rotateSelectedDevices = ref([]) // IDs de los equipos seleccionados

// --- ESTADO REPORTES DE ROTACIÓN ---
const isReportsModalOpen = ref(false)
const activeReportsCred = ref(null)

// Variable para guardar la función de desvinculación del listener WS
let wsUnbind = null

// --- LIFECYCLE ---
onMounted(async () => {
  fetchCredentials()
  fetchProfiles()
  
  // Aseguramos que el WS centralizado esté conectado y luego nos colgamos de él
  await connectWebSocketWhenAuthenticated()
  initRealTime()
})

onUnmounted(() => {
  if (wsUnbind) {
    wsUnbind()
  }
})

// --- NOTIFICACIONES ---
function showNotification(message, type = 'success') {
  notification.value = { show: true, message, type }
  setTimeout(() => {
    notification.value.show = false
  }, 4000)
}

// ==========================================
// 1. LOGICA DE CREDENCIALES (BÓVEDA)
// ==========================================
async function fetchCredentials() {
  try {
    const { data } = await api.get('/credentials')
    savedCredentials.value = Array.isArray(data) ? data : []
    
    // Si el modal de reportes está abierto, actualizamos su data
    if (activeReportsCred.value) {
      const updatedCred = savedCredentials.value.find(c => c.id === activeReportsCred.value.id)
      if (updatedCred) {
        activeReportsCred.value = updatedCred
      }
    }
  } catch (err) {
    console.error('Error al cargar credenciales:', err)
    showNotification('Error al cargar credenciales.', 'error')
  }
}

// Cambio automático de tipo al seleccionar vendor
function onVendorChange(targetObj) {
  const v = targetObj.vendor
  if (v === 'Mikrotik') {
    targetObj.type = 'mikrotik_api'
    targetObj.is_password_only = false
  } else if (v === 'Ubiquiti') {
    targetObj.type = 'ssh'
    targetObj.is_password_only = false
  } else if (v === 'Mimosa') {
    targetObj.type = 'ssh'
  } else if (v === 'SNMP') {
    targetObj.type = 'snmp'
    targetObj.is_password_only = false 
  }
}

async function handleAddCredential() {
  // Validación dinámica
  if (!newCredential.value.name.trim()) {
    return showNotification('El nombre es obligatorio.', 'error')
  }
  if (!newCredential.value.is_password_only && !newCredential.value.username.trim()) {
    return showNotification('El usuario es obligatorio.', 'error')
  }

  try {
    const payload = {
      ...newCredential.value,
      username: newCredential.value.is_password_only ? null : newCredential.value.username,
    }

    await api.post('/credentials', payload)
    showNotification(`Credencial '${newCredential.value.name}' guardada.`, 'success')

    // Resetear formulario
    newCredential.value = {
      name: '',
      username: '',
      password: '',
      type: 'mikrotik_api',
      vendor: 'Mikrotik',
      is_password_only: false,
    }
    fetchCredentials()
  } catch (err) {
    showNotification(err.response?.data?.detail || 'Error al guardar.', 'error')
  }
}

function requestDeleteCredential(id) {
  credentialToDeleteId.value = id
}

async function confirmDeleteCredential() {
  if (!credentialToDeleteId.value) return
  try {
    await api.delete(`/credentials/${credentialToDeleteId.value}`)
    showNotification('Credencial eliminada.', 'success')
    fetchCredentials()
    fetchProfiles()
  } catch (err) {
    showNotification(err.response?.data?.detail || 'Error al eliminar.', 'error')
  } finally {
    credentialToDeleteId.value = null
  }
}

// ==========================================
// 2. LOGICA ROTACIÓN MASIVA Y REPORTES
// ==========================================

async function openRotateModal(cred) {
  rotateSourceCred.value = cred
  rotateMode.value = 'new'
  rotateTargetId.value = null
  rotateSelectedDevices.value = []
  rotateNewCred.value = {
    name: `Migración de ${cred.name}`,
    username: cred.username || '',
    password: '',
    type: cred.type || 'mikrotik_api',
    vendor: cred.vendor || 'Mikrotik',
    is_password_only: cred.is_password_only || false,
  }
  
  isRotateModalOpen.value = true
  await fetchDevicesForRotation(cred.id)
}

// NUEVO: Traer equipos vinculados explícitamente a esta credencial
async function fetchDevicesForRotation(currentCredId) {
  isLoadingDevices.value = true
  try {
    const { data } = await api.get('/devices')
    const allFetched = Array.isArray(data) ? data : []
    
    // FILTRAMOS: Solo mostramos los que tengan esta credencial
    allDevices.value = allFetched.filter(d => String(d.credential_id) === String(currentCredId))
    
    // Auto-seleccionar todos por defecto
    rotateSelectedDevices.value = allDevices.value.map(d => d.id)
  } catch (err) {
    console.error('Error cargando equipos', err)
  } finally {
    isLoadingDevices.value = false
  }
}

// NUEVO: Marcar/Desmarcar todos
function toggleAllDevices(event) {
  if (event.target.checked) {
    rotateSelectedDevices.value = allDevices.value.map(d => d.id)
  } else {
    rotateSelectedDevices.value = []
  }
}

const availableTargetsForRotation = computed(() => {
  if (!rotateSourceCred.value) return []
  return savedCredentials.value.filter(c => c.id !== rotateSourceCred.value.id)
})

async function submitBulkRotation() {
  if (rotateSelectedDevices.value.length === 0) {
    return showNotification('Debes seleccionar al menos un equipo.', 'error')
  }
  
  if (rotateMode.value === 'existing' && !rotateTargetId.value) {
    return showNotification('Selecciona una credencial destino.', 'error')
  }
  if (rotateMode.value === 'new') {
    if (!rotateNewCred.value.name.trim()) return showNotification('Nombre obligatorio.', 'error')
    if (!rotateNewCred.value.is_password_only && !rotateNewCred.value.username.trim()) return showNotification('Usuario obligatorio.', 'error')
  }

  const payload = {
    // ENVIAMOS EL ARRAY DE EQUIPOS AL BACKEND
    device_ids: rotateSelectedDevices.value.map(String) 
  }
  
  if (rotateMode.value === 'existing') {
    payload.target_credential_id = rotateTargetId.value
  } else {
    payload.new_credential_data = {
      ...rotateNewCred.value,
      username: rotateNewCred.value.is_password_only ? null : rotateNewCred.value.username
    }
  }

  try {
    await api.post(`/credentials/${rotateSourceCred.value.id}/bulk-rotate`, payload)
    showNotification('Rotación masiva iniciada en segundo plano.', 'success')
    isRotateModalOpen.value = false
    fetchCredentials() // Refrescamos para ver el nuevo reporte en progreso
  } catch (err) {
    showNotification(err.response?.data?.detail || 'Error iniciando rotación masiva.', 'error')
  }
}

function openReportsModal(cred) {
  activeReportsCred.value = cred
  isReportsModalOpen.value = true
}

async function deleteReport(jobId) {
  if (!activeReportsCred.value) return
  try {
    await api.delete(`/credentials/${activeReportsCred.value.id}/reports/${jobId}`)
    showNotification('Reporte eliminado.', 'success')
    fetchCredentials()
  } catch (err) {
    showNotification(err.response?.data?.detail || 'Error eliminando reporte.', 'error')
  }
}

// ==========================================
// LÓGICA WEBSOCKET GLOBAL (INTEGRADO)
// ==========================================
function initRealTime() {
  const ws = getCurrentWebSocket()
  
  if (!ws) {
    // Si aún no está listo el socket global, reintentamos en un rato
    setTimeout(initRealTime, 1000)
    return
  }

  // Listener para mensajes entrantes de Celery
  const handleMessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      if (data.type === 'bulk_rotation_progress') {
        handleRealtimeProgress(data)
      }
    } catch (e) {
      /* Ignorar errores de parseo (pueden ser pings u otros eventos) */
    }
  }

  // Desvinculamos por si acaso ya existía, y lo volvemos a añadir
  ws.removeEventListener('message', handleMessage)
  ws.addEventListener('message', handleMessage)

  // Guardamos la función para poder destruirla en el onUnmounted
  wsUnbind = () => ws.removeEventListener('message', handleMessage)
}

function handleRealtimeProgress(data) {
  const cred = savedCredentials.value.find(c => c.id === data.credential_id)
  if (cred) {
    let reports = cred.rotation_reports || []
    const idx = reports.findIndex(r => r.job_id === data.job_id)
    
    if (idx !== -1) {
      reports[idx] = { ...reports[idx], ...data }
    } else {
      reports.unshift(data)
    }
    
    // Forzamos reactividad reemplazando el array
    cred.rotation_reports = [...reports]
    
    // Si el modal de reportes está abierto para esta credencial, actualizamos
    if (activeReportsCred.value && activeReportsCred.value.id === data.credential_id) {
      activeReportsCred.value.rotation_reports = [...reports]
    }
  }
}

// Helpers visuales
function getVendorBadgeClass(vendor) {
  if (!vendor) return 'badge-gray'
  const v = vendor.toLowerCase()
  if (v.includes('mikrotik')) return 'badge-ros'
  if (v.includes('ubiquiti')) return 'badge-ubnt'
  if (v.includes('mimosa')) return 'badge-mimosa'
  if (v.includes('snmp')) return 'badge-snmp'
  return 'badge-gray'
}

// ==========================================
// 3. LOGICA DE PERFILES (LLAVEROS)
// ==========================================
async function fetchProfiles() {
  try {
    const { data } = await api.get('/credentials/profiles')
    savedProfiles.value = Array.isArray(data) ? data : []
  } catch (err) {
    console.error('Error profiles:', err)
  }
}

const availableCredentials = computed(() => {
  const selectedIds = new Set(profileForm.value.selectedCreds.map((c) => c.id))
  return savedCredentials.value.filter((c) => !selectedIds.has(c.id))
})

function openProfileModal(profile = null) {
  if (profile) {
    const mappedSelection = profile.items.map((item) => ({
      id: item.credential_id,
      name: item.name,
      username: item.username,
      vendor: item.vendor,
      type: item.type,
    }))
    profileForm.value = {
      id: profile.id,
      name: profile.name,
      selectedCreds: mappedSelection,
    }
  } else {
    profileForm.value = { id: null, name: '', selectedCreds: [] }
  }
  isProfileModalOpen.value = true
}

function closeProfileModal() {
  isProfileModalOpen.value = false
}

function addToProfile(cred) {
  profileForm.value.selectedCreds.push(cred)
}

function removeFromProfile(index) {
  profileForm.value.selectedCreds.splice(index, 1)
}

function moveUp(index) {
  if (index > 0) {
    const arr = profileForm.value.selectedCreds
    const temp = arr[index]
    arr[index] = arr[index - 1]
    arr[index - 1] = temp
  }
}

function moveDown(index) {
  const arr = profileForm.value.selectedCreds
  if (index < arr.length - 1) {
    const temp = arr[index]
    arr[index] = arr[index + 1]
    arr[index + 1] = temp
  }
}

async function saveProfile() {
  if (!profileForm.value.name.trim()) {
    showNotification('El nombre del perfil es obligatorio.', 'error')
    return
  }

  const payload = {
    name: profileForm.value.name,
    credential_ids: profileForm.value.selectedCreds.map((c) => c.id),
  }

  try {
    if (profileForm.value.id) {
      await api.put(`/credentials/profiles/${profileForm.value.id}`, payload)
      showNotification('Perfil actualizado.', 'success')
    } else {
      await api.post('/credentials/profiles', payload)
      showNotification('Perfil creado.', 'success')
    }
    closeProfileModal()
    fetchProfiles()
  } catch (err) {
    showNotification(err.response?.data?.detail || 'Error al guardar perfil.', 'error')
  }
}

function requestDeleteProfile(id) {
  profileToDeleteId.value = id
}

async function confirmDeleteProfile() {
  if (!profileToDeleteId.value) return
  try {
    await api.delete(`/credentials/profiles/${profileToDeleteId.value}`)
    showNotification('Perfil eliminado.', 'success')
    fetchProfiles()
  } catch (err) {
    console.error(err)
    showNotification(err.response?.data?.detail || 'Error al eliminar perfil.', 'error')
  } finally {
    profileToDeleteId.value = null
  }
}
</script>

<template>
  <div>
    <div v-if="notification.show" :class="['notification', notification.type]">
      {{ notification.message }}
    </div>

    <div v-if="credentialToDeleteId" class="modal-overlay">
      <div class="modal-content">
        <h3>Eliminar Credencial</h3>
        <p>¿Seguro? Si está en uso, podría afectar la gestión.</p>
        <div class="modal-actions">
          <button @click="credentialToDeleteId = null" class="btn-secondary">Cancelar</button>
          <button @click="confirmDeleteCredential" class="btn-danger">Eliminar</button>
        </div>
      </div>
    </div>

    <div v-if="profileToDeleteId" class="modal-overlay">
      <div class="modal-content">
        <h3>Eliminar Perfil</h3>
        <div class="modal-actions">
          <button @click="profileToDeleteId = null" class="btn-secondary">Cancelar</button>
          <button @click="confirmDeleteProfile" class="btn-danger">Eliminar</button>
        </div>
      </div>
    </div>

    <div v-if="isRotateModalOpen" class="modal-overlay">
      <div class="modal-content large-modal">
        <h3>🔄 Rotación Masiva</h3>
        <p class="helper-text">Migrar equipos desde <strong>{{ rotateSourceCred?.name }}</strong> hacia una nueva credencial.</p>
        
        <div class="rotation-modes">
          <label class="radio-label">
            <input type="radio" v-model="rotateMode" value="new"> Crear nueva credencial
          </label>
          <label class="radio-label">
            <input type="radio" v-model="rotateMode" value="existing"> Elegir de la bóveda
          </label>
        </div>

        <div v-if="rotateMode === 'new'" class="credential-form mt-1">
          <div class="form-group-no-margin">
            <label class="label-small">Fabricante / Tipo</label>
            <select v-model="rotateNewCred.vendor" @change="onVendorChange(rotateNewCred)" class="type-select">
              <option value="Mikrotik">📡 MikroTik (RouterOS)</option>
              <option value="Ubiquiti">💻 Ubiquiti (AirOS / EdgeOS)</option>
              <option value="Mimosa">📡 Mimosa Networks</option>
              <option value="SNMP">🌐 SNMP (Solo Lectura)</option>
            </select>
          </div>

          <input type="text" v-model="rotateNewCred.name" placeholder="Nombre descriptivo (Ej: Admin 2026) *" />

          <div v-if="rotateNewCred.vendor === 'Mimosa'" class="checkbox-row">
            <label>
              <input type="checkbox" v-model="rotateNewCred.is_password_only" />
              Solo Contraseña (Sin usuario)
            </label>
          </div>

          <input v-if="!rotateNewCred.is_password_only" type="text" v-model="rotateNewCred.username" 
                 :placeholder="rotateNewCred.vendor === 'SNMP' ? 'Community String *' : 'Nuevo Usuario *'" />

          <input type="password" v-model="rotateNewCred.password" 
                 :placeholder="rotateNewCred.vendor === 'SNMP' ? 'Contraseña (Opcional)' : 'Nueva Contraseña *'" />
        </div>

        <div v-if="rotateMode === 'existing'" class="credential-form mt-1">
          <label class="label-small">Selecciona la credencial destino:</label>
          <select v-model="rotateTargetId" class="type-select full-width-input">
            <option value="null" disabled>-- Seleccionar --</option>
            <option v-for="cred in availableTargetsForRotation" :key="cred.id" :value="cred.id">
              {{ cred.name }} {{ cred.username ? `(${cred.username})` : '' }}
            </option>
          </select>
        </div>

        <div class="devices-selection mt-2">
          <h4>Equipos vinculados a esta credencial</h4>
          <p class="helper-text-small">Estos son los dispositivos en la base de datos que actualmente usan esta configuración.</p>
          
          <div v-if="isLoadingDevices" class="empty-msg">Cargando lista de equipos...</div>
          <div v-else class="devices-listbox">
            <div class="device-item-row header-row" v-if="allDevices.length > 0">
              <label>
                <input type="checkbox" @change="toggleAllDevices" :checked="rotateSelectedDevices.length === allDevices.length" />
                Seleccionar Todos
              </label>
            </div>
            
            <div v-for="dev in allDevices" :key="dev.id" class="device-item-row">
              <label>
                <input type="checkbox" :value="dev.id" v-model="rotateSelectedDevices" />
                <span class="dev-name">{{ dev.name }}</span>
                <span class="dev-ip">({{ dev.ip_address }})</span>
                <span class="dev-badge">Vinculado</span>
              </label>
            </div>
            
            <div v-if="allDevices.length === 0" class="empty-msg">Ningún equipo usa explícitamente esta credencial.</div>
          </div>
        </div>

        <div class="modal-actions mt-2">
          <button @click="isRotateModalOpen = false" class="btn-secondary">Cancelar</button>
          <button @click="submitBulkRotation" class="btn-primary" :disabled="allDevices.length === 0 || rotateSelectedDevices.length === 0">🚀 Iniciar Migración</button>
        </div>
      </div>
    </div>

    <div v-if="isReportsModalOpen" class="modal-overlay">
      <div class="modal-content large-modal reports-modal">
        <h3>📊 Historial de Rotaciones: {{ activeReportsCred?.name }}</h3>
        
        <div v-if="!activeReportsCred?.rotation_reports || activeReportsCred.rotation_reports.length === 0" class="empty-msg">
          No hay reportes de rotación masiva para esta credencial.
        </div>

        <div class="reports-list" v-else>
          <div v-for="report in activeReportsCred.rotation_reports" :key="report.job_id" class="report-card">
            <div class="report-header">
              <div class="report-title-row">
                <strong>{{ report.timestamp ? new Date(report.timestamp).toLocaleString() : 'Reciente' }}</strong>
                <span :class="['status-badge', report.status]">{{ report.status === 'in_progress' ? '🔄 En Progreso' : '✅ Completado' }}</span>
              </div>
              <p class="target-group">{{ report.target_group }}</p>
            </div>
            
            <div class="progress-section">
              <div class="stats">
                <span class="text-green">Éxito: {{ report.success_count }}</span>
                <span class="text-red">Error: {{ report.error_count }}</span>
                <span class="text-gray" v-if="report.total">Total: {{ report.total }}</span>
              </div>
              <div class="progress-bar-container" v-if="report.total && report.total > 0">
                <div class="progress-bar-fill" 
                     :style="{ width: (((report.success_count + report.error_count) / report.total) * 100) + '%' }">
                </div>
              </div>
            </div>

            <div v-if="report.errors && report.errors.length > 0" class="errors-list">
              <p class="error-title">Equipos fallidos:</p>
              <ul>
                <li v-for="err in report.errors" :key="err.ip"><strong>{{ err.ip }}:</strong> {{ err.reason }}</li>
              </ul>
            </div>

            <div class="report-footer">
              <button class="btn-remove-report" @click="deleteReport(report.job_id)">🗑️ Borrar Reporte</button>
            </div>
          </div>
        </div>

        <div class="modal-actions">
          <button @click="isReportsModalOpen = false" class="btn-secondary">Cerrar</button>
        </div>
      </div>
    </div>

    <div v-if="isProfileModalOpen" class="modal-overlay">
      <div class="modal-content large-modal">
        <h3>{{ profileForm.id ? 'Editar Perfil' : 'Nuevo Perfil' }}</h3>

        <div class="form-group">
          <label>Nombre del Perfil:</label>
          <input
            type="text"
            v-model="profileForm.name"
            placeholder="Ej: Escaneo Bloque A"
            class="full-width-input"
          />
        </div>

        <div class="dual-list-container">
          <div class="list-column">
            <h4>Disponibles</h4>
            <div class="list-box">
              <div
                v-for="cred in availableCredentials"
                :key="cred.id"
                class="list-item available"
                @click="addToProfile(cred)"
              >
                <div class="item-text-row">
                  <span>{{ cred.name }}</span>
                  <span :class="['mini-badge', getVendorBadgeClass(cred.vendor)]">
                    {{ cred.vendor || 'Gen' }}
                  </span>
                </div>
                <span class="small-user">
                  {{ cred.username ? `(${cred.username})` : '(Solo Password)' }}
                </span>
                <span class="action-icon">➕</span>
              </div>
              <div v-if="availableCredentials.length === 0" class="empty-msg">
                No hay más credenciales.
              </div>
            </div>
          </div>

          <div class="list-controls">
            <span class="arrow-icon">➡</span>
          </div>

          <div class="list-column">
            <h4>En este Perfil (Ordenadas)</h4>
            <div class="list-box">
              <div
                v-for="(cred, idx) in profileForm.selectedCreds"
                :key="cred.id"
                class="list-item selected"
              >
                <div class="item-content">
                  <span class="priority-badge">{{ idx + 1 }}</span>
                  <div class="text-col">
                    <div class="item-text-row">
                      <span>{{ cred.name }}</span>
                      <span :class="['mini-badge', getVendorBadgeClass(cred.vendor)]">
                        {{ cred.vendor || 'Gen' }}
                      </span>
                    </div>
                    <span class="small-user">
                      {{ cred.username || '***' }}
                    </span>
                  </div>
                </div>
                <div class="item-actions">
                  <button @click.stop="moveUp(idx)" :disabled="idx === 0">▲</button>
                  <button
                    @click.stop="moveDown(idx)"
                    :disabled="idx === profileForm.selectedCreds.length - 1"
                  >
                    ▼
                  </button>
                  <button @click.stop="removeFromProfile(idx)" class="btn-remove">✖</button>
                </div>
              </div>
              <div v-if="profileForm.selectedCreds.length === 0" class="empty-msg">
                Arrastra o añade aquí.
              </div>
            </div>
          </div>
        </div>

        <div class="modal-actions">
          <button @click="closeProfileModal" class="btn-secondary">Cancelar</button>
          <button @click="saveProfile" class="btn-primary">Guardar Perfil</button>
        </div>
      </div>
    </div>

    <div class="tabs-header">
      <button
        :class="['tab-btn', { active: activeTab === 'credentials' }]"
        @click="activeTab = 'credentials'"
      >
        🔐 Mis Credenciales
      </button>
      <button
        :class="['tab-btn', { active: activeTab === 'profiles' }]"
        @click="activeTab = 'profiles'"
      >
        📚 Perfiles de Acceso
      </button>
    </div>

    <div v-if="activeTab === 'credentials'" class="credentials-layout fade-in">
      <section class="control-section">
        <h2><i class="icon">➕</i> Añadir Credencial</h2>
        <form @submit.prevent="handleAddCredential" class="credential-form">
          <div class="form-group-no-margin">
            <label class="label-small">Fabricante / Tipo</label>
            <select v-model="newCredential.vendor" @change="onVendorChange(newCredential)" class="type-select">
              <option value="Mikrotik">📡 MikroTik (RouterOS)</option>
              <option value="Ubiquiti">💻 Ubiquiti (AirOS / EdgeOS)</option>
              <option value="Mimosa">📡 Mimosa Networks</option>
              <option value="SNMP">🌐 SNMP (Solo Lectura)</option>
            </select>
          </div>

          <input
            type="text"
            v-model="newCredential.name"
            placeholder="Nombre descriptivo (ej: Torre Norte) *"
          />

          <div v-if="newCredential.vendor === 'Mimosa'" class="checkbox-row">
            <label>
              <input type="checkbox" v-model="newCredential.is_password_only" />
              Solo Contraseña (Sin usuario)
            </label>
          </div>

          <input
            v-if="!newCredential.is_password_only"
            type="text"
            v-model="newCredential.username"
            :placeholder="newCredential.vendor === 'SNMP' ? 'Community String *' : 'Usuario *'"
          />

          <input
            type="password"
            v-model="newCredential.password"
            :placeholder="
              newCredential.vendor === 'SNMP' ? 'Contraseña (Opcional)' : 'Contraseña'
            "
          />

          <button type="submit">Guardar en Bóveda</button>
        </form>
      </section>

      <section class="control-section">
        <h2><i class="icon">📋</i> Bóveda de Claves</h2>
        <ul v-if="savedCredentials.length > 0" class="credentials-list">
          <li v-for="cred in savedCredentials" :key="cred.id">
            <div class="cred-info">
              <span class="cred-name">
                {{ cred.name }}
                <span :class="['badge-pill', getVendorBadgeClass(cred.vendor)]">
                  {{ cred.vendor || 'Generico' }}
                </span>
              </span>
              <span class="cred-user">
                {{ cred.username ? `Usuario: ${cred.username}` : '🔑 (Solo clave)' }}
              </span>
            </div>
            <div class="cred-actions-group">
              <button @click="openRotateModal(cred)" class="action-btn" title="Rotación Masiva">🔄</button>
              
              <button v-if="cred.rotation_reports && cred.rotation_reports.length > 0" 
                      @click="openReportsModal(cred)" 
                      class="action-btn btn-reports" 
                      title="Ver Reportes de Rotación">
                📊 ({{ cred.rotation_reports.length }})
              </button>

              <button @click="requestDeleteCredential(cred.id)" class="delete-btn" title="Eliminar">×</button>
            </div>
          </li>
        </ul>
        <div v-else class="empty-list">No hay credenciales guardadas.</div>
      </section>
    </div>

    <div v-if="activeTab === 'profiles'" class="profiles-layout fade-in">
      <div class="profiles-header">
        <p class="helper-text">Agrupa credenciales para que el escáner las pruebe en orden.</p>
        <button @click="openProfileModal()" class="btn-create-profile">+ Nuevo Perfil</button>
      </div>

      <div class="profiles-grid">
        <div v-for="profile in savedProfiles" :key="profile.id" class="profile-card">
          <div class="profile-card-header">
            <h3>{{ profile.name }}</h3>
            <div class="card-actions">
              <button @click="openProfileModal(profile)">✏️</button>
              <button @click="requestDeleteProfile(profile.id)" class="text-danger">🗑️</button>
            </div>
          </div>

          <div class="profile-items-preview">
            <span class="preview-label">Secuencia:</span>
            <ol>
              <li v-for="item in profile.items" :key="item.credential_id">
                <span :class="['dot', getVendorBadgeClass(item.vendor)]"></span>
                {{ item.name }}
              </li>
            </ol>
            <div v-if="!profile.items || profile.items.length === 0" class="empty-items">
              Sin credenciales
            </div>
          </div>
        </div>
      </div>

      <div v-if="savedProfiles.length === 0" class="empty-list large-empty">
        No hay perfiles configurados.
      </div>
    </div>
  </div>
</template>

<style scoped>
/* GENERAL */
.fade-in {
  animation: fadeIn 0.3s ease-in-out;
}
@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(5px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
.mt-1 { margin-top: 1rem; }
.mt-2 { margin-top: 2rem; }

/* TABS */
.tabs-header {
  display: flex;
  gap: 1rem;
  margin-bottom: 2rem;
  border-bottom: 2px solid var(--surface-color);
  padding-bottom: 0.5rem;
}
.tab-btn {
  background: none;
  border: none;
  color: var(--gray);
  font-size: 1.1rem;
  font-weight: bold;
  padding: 0.8rem 1.5rem;
  cursor: pointer;
  border-radius: 8px 8px 0 0;
  transition: all 0.2s;
}
.tab-btn:hover {
  color: white;
  background-color: rgba(255, 255, 255, 0.05);
}
.tab-btn.active {
  color: var(--blue);
  border-bottom: 3px solid var(--blue);
  background-color: var(--surface-color);
}

/* CREDENTIALS LAYOUT (TAB 1) */
.credentials-layout {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
  gap: 2rem;
}
.control-section {
  background-color: var(--surface-color);
  padding: 2rem;
  border-radius: 12px;
}
.control-section h2 {
  margin-top: 0;
  color: white;
  font-size: 1.3rem;
}

.credential-form {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}
.credential-form input,
.credential-form select {
  padding: 0.8rem;
  background-color: var(--bg-color);
  border: 1px solid var(--primary-color);
  border-radius: 6px;
  color: white;
}
.type-select {
  cursor: pointer;
}
.checkbox-row {
  display: flex;
  align-items: center;
  color: var(--gray);
  font-size: 0.9rem;
}
.checkbox-row input {
  width: auto;
  margin-right: 8px;
}
.label-small {
  font-size: 0.85rem;
  color: var(--gray);
  margin-bottom: 4px;
  display: block;
}
.credential-form button {
  padding: 0.8rem;
  background-color: var(--blue);
  border: none;
  border-radius: 6px;
  color: white;
  font-weight: bold;
  cursor: pointer;
}
.credential-form button:hover {
  opacity: 0.9;
}

.credentials-list {
  list-style: none;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.8rem;
}
.credentials-list li {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background-color: var(--bg-color);
  padding: 1rem;
  border-radius: 8px;
}
.cred-info {
  display: flex;
  flex-direction: column;
}
.cred-name {
  font-weight: bold;
  color: white;
  display: flex;
  align-items: center;
  gap: 8px;
}
/* Badges visuales */
.badge-pill {
  font-size: 0.7rem;
  padding: 2px 6px;
  border-radius: 4px;
  font-weight: normal;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.badge-ros {
  background-color: rgba(58, 130, 246, 0.2);
  color: #60a5fa;
  border: 1px solid #2563eb;
}
.badge-ubnt {
  background-color: rgba(16, 185, 129, 0.2);
  color: #34d399;
  border: 1px solid #059669;
}
.badge-mimosa {
  background-color: rgba(236, 72, 153, 0.2); /* Rosa */
  color: #f472b6;
  border: 1px solid #db2777;
}
.badge-snmp {
  background-color: rgba(245, 158, 11, 0.2);
  color: #fbbf24;
  border: 1px solid #d97706;
}
.badge-gray {
  background-color: #444;
  color: #ccc;
}

.mini-badge {
  font-size: 0.65rem;
  padding: 1px 4px;
  border-radius: 3px;
  margin-left: 6px;
  vertical-align: middle;
}

.dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-right: 6px;
}
.dot.badge-ros { background-color: #60a5fa; }
.dot.badge-ubnt { background-color: #34d399; }
.dot.badge-mimosa { background-color: #f472b6; }
.dot.badge-snmp { background-color: #fbbf24; }
.dot.badge-gray { background-color: #888; }

.cred-user {
  font-size: 0.9rem;
  color: var(--gray);
}

.cred-actions-group {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
.action-btn {
  background: none;
  border: 1px solid transparent;
  color: white;
  font-size: 1.1rem;
  cursor: pointer;
  padding: 4px;
  border-radius: 6px;
  transition: all 0.2s;
}
.action-btn:hover {
  background-color: rgba(255, 255, 255, 0.1);
  border-color: rgba(255, 255, 255, 0.2);
}
.btn-reports {
  font-size: 0.9rem;
  background-color: rgba(58, 130, 246, 0.1);
  border: 1px solid var(--blue);
  color: #60a5fa;
  padding: 4px 8px;
}
.btn-reports:hover {
  background-color: var(--blue);
  color: white;
}
.delete-btn {
  background: none;
  border: none;
  color: var(--gray);
  font-size: 1.5rem;
  cursor: pointer;
  margin-left: 0.5rem;
}
.delete-btn:hover {
  color: var(--error-red);
}

/* PROFILES LAYOUT (TAB 2) */
.profiles-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
}
.helper-text {
  color: var(--gray);
  font-style: italic;
}
.btn-create-profile {
  background-color: var(--green);
  color: white;
  border: none;
  padding: 0.8rem 1.5rem;
  border-radius: 6px;
  font-weight: bold;
  cursor: pointer;
}
.profiles-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 1.5rem;
}
.profile-card {
  background-color: var(--surface-color);
  padding: 1.5rem;
  border-radius: 12px;
  border: 1px solid var(--primary-color);
}
.profile-card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 1rem;
}
.profile-card-header h3 {
  margin: 0;
  color: var(--blue);
  font-size: 1.2rem;
}
.card-actions button {
  background: none;
  border: none;
  font-size: 1.2rem;
  cursor: pointer;
  margin-left: 0.5rem;
}
.preview-label {
  font-size: 0.85rem;
  color: var(--gray);
  display: block;
  margin-bottom: 0.5rem;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.profile-items-preview ol {
  padding-left: 1.2rem;
  margin: 0;
  color: white;
  font-size: 0.95rem;
}
.profile-items-preview li {
  margin-bottom: 0.3rem;
}
.dim {
  color: var(--gray);
  font-size: 0.85rem;
}
.empty-items {
  color: var(--gray);
  font-style: italic;
  font-size: 0.9rem;
}

/* MODALS */
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
  max-width: 400px;
  width: 90%;
  text-align: center;
  color: white;
  max-height: 90vh;
  overflow-y: auto;
}
.modal-content.large-modal {
  max-width: 700px;
  text-align: left;
}
.modal-content h3 {
  margin-top: 0;
  color: white;
}
.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 1rem;
  margin-top: 1.5rem;
}
.modal-actions button {
  padding: 0.6rem 1.2rem;
  border: none;
  border-radius: 6px;
  font-weight: bold;
  cursor: pointer;
}
.btn-primary { background-color: var(--blue); color: white; }
.btn-secondary { background-color: var(--primary-color); color: white; }
.btn-danger { background-color: var(--error-red); color: white; }

/* NUEVO: ESTILOS SELECTOR DE EQUIPOS (ROTACIÓN MANUAL) */
.helper-text-small {
  color: var(--gray);
  font-size: 0.8rem;
  margin-bottom: 0.8rem;
}
.devices-selection {
  margin-top: 1.5rem;
  border-top: 1px solid var(--primary-color);
  padding-top: 1rem;
  text-align: left;
}
.devices-selection h4 {
  margin: 0;
  color: white;
}
.devices-listbox {
  max-height: 200px;
  overflow-y: auto;
  background-color: rgba(0, 0, 0, 0.2);
  border: 1px solid var(--primary-color);
  border-radius: 6px;
  padding: 0.5rem;
}
.device-item-row {
  display: flex;
  align-items: center;
  padding: 0.4rem 0;
  color: white;
  font-size: 0.9rem;
}
.device-item-row:not(:last-child) {
  border-bottom: 1px solid rgba(255,255,255,0.05);
}
.device-item-row.header-row {
  border-bottom: 1px solid var(--primary-color);
  margin-bottom: 0.5rem;
  padding-bottom: 0.5rem;
  color: var(--blue);
}
.device-item-row label {
  display: flex;
  align-items: center;
  cursor: pointer;
  width: 100%;
}
.device-item-row input[type="checkbox"] {
  margin-right: 0.6rem;
  cursor: pointer;
}
.dev-name { font-weight: bold; margin-right: 0.4rem; }
.dev-ip { color: var(--gray); font-family: monospace; font-size: 0.85rem; margin-right: 0.5rem; }
.dev-badge { 
  background-color: rgba(16, 185, 129, 0.2); 
  color: #34d399; 
  font-size: 0.7rem; 
  padding: 2px 6px; 
  border-radius: 4px; 
  border: 1px solid #059669; 
  margin-left: auto; 
}

/* DUAL LIST STYLES (EDITOR PERFILES) */
.full-width-input {
  width: 100%;
  padding: 0.8rem;
  border-radius: 6px;
  border: 1px solid var(--primary-color);
  background-color: var(--bg-color);
  color: white;
  margin-top: 0.5rem;
}
.dual-list-container {
  display: grid;
  grid-template-columns: 1fr 40px 1fr;
  gap: 0.5rem;
  margin-top: 1.5rem;
  height: 350px;
}
.list-column h4 {
  margin: 0 0 0.5rem 0;
  font-size: 0.9rem;
  color: var(--gray);
}
.list-box {
  background-color: var(--bg-color);
  border: 1px solid var(--primary-color);
  border-radius: 8px;
  height: 100%;
  overflow-y: auto;
  padding: 0.5rem;
}
.list-controls {
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--gray);
  font-size: 1.5rem;
}
.list-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.6rem;
  border-radius: 4px;
  margin-bottom: 0.4rem;
  cursor: pointer;
  background-color: rgba(255, 255, 255, 0.03);
  transition: background 0.2s;
}
.list-item:hover { background-color: rgba(255, 255, 255, 0.08); }
.list-item.available .action-icon { font-size: 0.8rem; color: var(--green); }
.small-user { font-size: 0.8rem; color: var(--gray); margin-left: 0.5rem; }
.item-text-row { display: flex; align-items: center; }

.list-item.selected {
  cursor: default;
  justify-content: space-between;
  background-color: rgba(58, 130, 246, 0.1);
  border: 1px solid rgba(58, 130, 246, 0.2);
}
.item-content { display: flex; align-items: center; gap: 0.8rem; }
.priority-badge {
  background-color: var(--blue);
  color: white;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.75rem;
  font-weight: bold;
}
.text-col { display: flex; flex-direction: column; line-height: 1.2; }
.item-actions { display: flex; gap: 0.3rem; }
.item-actions button {
  background: none;
  border: none;
  color: var(--gray);
  cursor: pointer;
  padding: 0.2rem;
  font-size: 0.8rem;
}
.item-actions button:hover { color: white; }
.item-actions button:disabled { opacity: 0.3; cursor: not-allowed; }
.btn-remove { color: var(--error-red) !important; font-size: 0.9rem !important; margin-left: 0.3rem; }

.empty-msg { text-align: center; color: var(--gray); margin-top: 2rem; font-size: 0.9rem; }
.empty-list {
  color: var(--gray);
  text-align: center;
  padding: 2rem;
  border: 2px dashed var(--primary-color);
  border-radius: 8px;
}

/* NOTIFICATION */
.notification {
  position: fixed;
  top: 90px;
  right: 20px;
  padding: 1rem 1.5rem;
  border-radius: 8px;
  color: white;
  font-weight: bold;
  z-index: 3000;
}
.notification.success { background-color: var(--green); }
.notification.error { background-color: var(--error-red); }

/* ESTILOS ESPECÍFICOS DE ROTACIÓN MASIVA */
.radio-label {
  display: inline-block;
  margin-right: 1.5rem;
  color: white;
  cursor: pointer;
  font-size: 1rem;
}
.radio-label input { margin-right: 8px; }

/* ESTILOS DE REPORTES */
.reports-modal {
  max-width: 600px;
}
.reports-list {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  margin-top: 1rem;
}
.report-card {
  background-color: var(--bg-color);
  border: 1px solid var(--primary-color);
  border-radius: 8px;
  padding: 1rem;
}
.report-header {
  border-bottom: 1px solid rgba(255,255,255,0.1);
  padding-bottom: 0.5rem;
  margin-bottom: 0.8rem;
}
.report-title-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.target-group {
  margin: 0.3rem 0 0 0;
  font-size: 0.9rem;
  color: var(--gray);
}
.status-badge {
  font-size: 0.8rem;
  padding: 3px 8px;
  border-radius: 12px;
  font-weight: bold;
}
.status-badge.in_progress { background-color: rgba(58, 130, 246, 0.2); color: #60a5fa; }
.status-badge.completed { background-color: rgba(16, 185, 129, 0.2); color: #34d399; }

.stats {
  display: flex;
  gap: 1.5rem;
  font-size: 0.95rem;
  margin-bottom: 0.5rem;
}
.text-green { color: #34d399; font-weight: bold; }
.text-red { color: #f87171; font-weight: bold; }
.text-gray { color: var(--gray); }

.progress-bar-container {
  background-color: #333;
  border-radius: 4px;
  height: 8px;
  width: 100%;
  overflow: hidden;
}
.progress-bar-fill {
  background-color: var(--blue);
  height: 100%;
  transition: width 0.3s ease-out;
}

.errors-list {
  margin-top: 1rem;
  background-color: rgba(248, 113, 113, 0.1);
  border-left: 3px solid #f87171;
  padding: 0.5rem 1rem;
  border-radius: 0 4px 4px 0;
}
.error-title { margin: 0 0 0.5rem 0; font-weight: bold; color: #fca5a5; font-size: 0.9rem; }
.errors-list ul { margin: 0; padding-left: 1.2rem; font-size: 0.85rem; color: #fecaca; }

.report-footer {
  margin-top: 1rem;
  text-align: right;
}
.btn-remove-report {
  background: none;
  border: none;
  color: var(--gray);
  cursor: pointer;
  font-size: 0.85rem;
}
.btn-remove-report:hover { color: var(--error-red); }
</style>