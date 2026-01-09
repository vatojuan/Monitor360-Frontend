<script setup>
import { ref, onMounted, computed } from 'vue'
import api from '@/lib/api'

// --- ESTADO GLOBAL ---
const activeTab = ref('credentials') // 'credentials' | 'profiles'
const notification = ref({ show: false, message: '', type: 'success' })

// --- ESTADO CREDENCIALES (BÓVEDA) ---
const savedCredentials = ref([])
// NUEVO: Agregamos 'type' por defecto
const newCredential = ref({ name: '', username: '', password: '', type: 'mikrotik_api' })
const credentialToDeleteId = ref(null)

// --- ESTADO PERFILES (LLAVEROS) ---
const savedProfiles = ref([])
const isProfileModalOpen = ref(false)
const profileToDeleteId = ref(null)

// Formulario reactivo para crear/editar perfil
const profileForm = ref({
  id: null,
  name: '',
  selectedCreds: [], // Array de objetos {id, name, username} en orden de prioridad
})

// --- LIFECYCLE ---
onMounted(() => {
  fetchCredentials()
  fetchProfiles()
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
  } catch (err) {
    console.error('Error al cargar credenciales:', err)
    showNotification('Error al cargar credenciales.', 'error')
  }
}

async function handleAddCredential() {
  if (!newCredential.value.name.trim() || !newCredential.value.username.trim()) {
    showNotification('Nombre y Usuario son obligatorios.', 'error')
    return
  }
  try {
    await api.post('/credentials', newCredential.value)
    showNotification(`Credencial '${newCredential.value.name}' guardada.`, 'success')
    // Resetear formulario con default type
    newCredential.value = { name: '', username: '', password: '', type: 'mikrotik_api' }
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
    fetchProfiles() // Refrescar perfiles por si se borró una usada
  } catch (err) {
    showNotification(err.response?.data?.detail || 'Error al eliminar.', 'error')
  } finally {
    credentialToDeleteId.value = null
  }
}

// Helper visual para tipos
function getTypeName(type) {
  const map = {
    mikrotik_api: 'MikroTik API',
    ssh: 'SSH / UBNT',
    snmp: 'SNMP',
  }
  return map[type] || 'MikroTik API'
}

function getTypeClass(type) {
  if (type === 'ssh') return 'badge-ssh'
  if (type === 'snmp') return 'badge-snmp'
  return 'badge-ros'
}

// ==========================================
// 2. LOGICA DE PERFILES (LLAVEROS)
// ==========================================
async function fetchProfiles() {
  try {
    const { data } = await api.get('/credentials/profiles')
    savedProfiles.value = Array.isArray(data) ? data : []
  } catch (err) {
    console.error('Error profiles:', err)
  }
}

// Computed: Credenciales disponibles (las que NO están ya seleccionadas)
const availableCredentials = computed(() => {
  const selectedIds = new Set(profileForm.value.selectedCreds.map((c) => c.id))
  return savedCredentials.value.filter((c) => !selectedIds.has(c.id))
})

function openProfileModal(profile = null) {
  if (profile) {
    // Editar
    // Mapeamos items a formato UI simple
    const mappedSelection = profile.items.map((item) => ({
      id: item.credential_id,
      name: item.name,
      username: item.username,
      type: item.type, // Ahora traemos el tipo también
    }))
    profileForm.value = {
      id: profile.id,
      name: profile.name,
      selectedCreds: mappedSelection,
    }
  } else {
    // Crear Nuevo
    profileForm.value = { id: null, name: '', selectedCreds: [] }
  }
  isProfileModalOpen.value = true
}

function closeProfileModal() {
  isProfileModalOpen.value = false
}

// -- Manipulación de listas en el Modal --
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
    const arr = profileForm.value.selectedCreds
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
    credential_ids: profileForm.value.selectedCreds.map((c) => c.id), // Enviar solo IDs en orden
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
        <p>¿Seguro? Si está en uso por algún perfil o dispositivo, podría fallar.</p>
        <div class="modal-actions">
          <button @click="credentialToDeleteId = null" class="btn-secondary">Cancelar</button>
          <button @click="confirmDeleteCredential" class="btn-danger">Eliminar</button>
        </div>
      </div>
    </div>

    <div v-if="profileToDeleteId" class="modal-overlay">
      <div class="modal-content">
        <h3>Eliminar Perfil</h3>
        <p>Las credenciales individuales NO se borrarán.</p>
        <div class="modal-actions">
          <button @click="profileToDeleteId = null" class="btn-secondary">Cancelar</button>
          <button @click="confirmDeleteProfile" class="btn-danger">Eliminar</button>
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
                  <span :class="['mini-badge', getTypeClass(cred.type)]">{{
                    getTypeName(cred.type)
                  }}</span>
                </div>
                <span class="small-user">({{ cred.username }})</span>
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
                      <span :class="['mini-badge', getTypeClass(cred.type || 'mikrotik_api')]">
                        {{ getTypeName(cred.type || 'mikrotik_api') }}
                      </span>
                    </div>
                    <span class="small-user">{{ cred.username }}</span>
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
            <label class="label-small">Tipo de Dispositivo / Protocolo</label>
            <select v-model="newCredential.type" class="type-select">
              <option value="mikrotik_api">📡 MikroTik (API Port 8728)</option>
              <option value="ssh">💻 Ubiquiti / Linux (SSH Port 22)</option>
              <option value="snmp">🌐 SNMP (Solo Monitoreo)</option>
            </select>
          </div>

          <input
            type="text"
            v-model="newCredential.name"
            placeholder="Nombre (ej: Admin General) *"
          />
          <input
            type="text"
            v-model="newCredential.username"
            placeholder="Usuario (o Community String para SNMP) *"
          />
          <input
            type="password"
            v-model="newCredential.password"
            placeholder="Contraseña (opcional para SNMP)"
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
                <span :class="['badge-pill', getTypeClass(cred.type)]">{{
                  getTypeName(cred.type)
                }}</span>
              </span>
              <span class="cred-user">Usuario: {{ cred.username }}</span>
            </div>
            <button @click="requestDeleteCredential(cred.id)" class="delete-btn">×</button>
          </li>
        </ul>
        <div v-else class="empty-list">No hay credenciales guardadas.</div>
      </section>
    </div>

    <div v-if="activeTab === 'profiles'" class="profiles-layout fade-in">
      <div class="profiles-header">
        <p class="helper-text">
          Crea grupos de credenciales para probar secuencialmente durante el escaneo.
        </p>
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
            <span class="preview-label">Secuencia de prueba:</span>
            <ol>
              <li v-for="item in profile.items" :key="item.credential_id">
                <span :class="['dot', getTypeClass(item.type)]"></span> {{ item.name }}
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
.badge-ssh {
  background-color: rgba(16, 185, 129, 0.2);
  color: #34d399;
  border: 1px solid #059669;
}
.badge-snmp {
  background-color: rgba(245, 158, 11, 0.2);
  color: #fbbf24;
  border: 1px solid #d97706;
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
.dot.badge-ros {
  background-color: #60a5fa;
  border: none;
}
.dot.badge-ssh {
  background-color: #34d399;
  border: none;
}
.dot.badge-snmp {
  background-color: #fbbf24;
  border: none;
}

.cred-user {
  font-size: 0.9rem;
  color: var(--gray);
}
.delete-btn {
  background: none;
  border: none;
  color: var(--gray);
  font-size: 1.5rem;
  cursor: pointer;
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
.btn-primary {
  background-color: var(--blue);
  color: white;
}
.btn-secondary {
  background-color: var(--primary-color);
  color: white;
}
.btn-danger {
  background-color: var(--error-red);
  color: white;
}

/* DUAL LIST STYLES (EDITOR) */
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
.list-item:hover {
  background-color: rgba(255, 255, 255, 0.08);
}
.list-item.available .action-icon {
  font-size: 0.8rem;
  color: var(--green);
}
.small-user {
  font-size: 0.8rem;
  color: var(--gray);
  margin-left: 0.5rem;
}
.item-text-row {
  display: flex;
  align-items: center;
}

.list-item.selected {
  cursor: default;
  justify-content: space-between;
  background-color: rgba(58, 130, 246, 0.1);
  border: 1px solid rgba(58, 130, 246, 0.2);
}
.item-content {
  display: flex;
  align-items: center;
  gap: 0.8rem;
}
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
.text-col {
  display: flex;
  flex-direction: column;
  line-height: 1.2;
}
.item-actions {
  display: flex;
  gap: 0.3rem;
}
.item-actions button {
  background: none;
  border: none;
  color: var(--gray);
  cursor: pointer;
  padding: 0.2rem;
  font-size: 0.8rem;
}
.item-actions button:hover {
  color: white;
}
.item-actions button:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}
.btn-remove {
  color: var(--error-red) !important;
  font-size: 0.9rem !important;
  margin-left: 0.3rem;
}

.empty-msg {
  text-align: center;
  color: var(--gray);
  margin-top: 2rem;
  font-size: 0.9rem;
}
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
  z-index: 1000;
}
.notification.success {
  background-color: var(--green);
}
.notification.error {
  background-color: var(--error-red);
}
</style>
