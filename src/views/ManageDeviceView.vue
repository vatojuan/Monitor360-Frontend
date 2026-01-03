<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import api from '@/lib/api'
import { supabase } from '@/lib/supabase'

const router = useRouter()

// ===== UI Estado general =====
const currentTab = ref('add') // 'add' | 'manage'
const notification = ref({ show: false, message: '', type: 'success' })

function showNotification(message, type = 'success') {
  notification.value = { show: true, message, type }
  setTimeout(() => (notification.value.show = false), 4000)
}

// ===== Usuario =====
const userEmail = ref('')
async function loadUser() {
  const { data } = await supabase.auth.getUser()
  userEmail.value = data.user?.email || ''
}
async function logout() {
  await supabase.auth.signOut()
  showNotification('Sesión cerrada.', 'success')
  router.push('/login')
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
  maestro_id: null,
})
const isSubmitting = ref(false)
const isTesting = ref(false)
const testResult = ref(null)

// ===== Listados =====
const allDevices = ref([])
const vpnProfiles = ref([])
const isLoadingDevices = ref(false)
const deletingId = ref(null)

// ===== ESTADO ACCIONES MASIVAS =====
const selectedDevices = ref([]) // IDs seleccionados
const showBulkModal = ref(false)
const isBulking = ref(false)

const bulkForm = ref({
  sensor_type: 'ping',
  name_template: '{{hostname}} - Ping Check',
  interval: 60,
  packet_count: 3,
  packet_size: 56,
  is_active: true,
  alerts_paused: false,
})

const maestros = computed(() => allDevices.value.filter((d) => d.is_maestro))

// ===== CARGA DE DATOS =====
async function fetchAllDevices() {
  isLoadingDevices.value = true
  try {
    const { data } = await api.get('/devices')
    allDevices.value = Array.isArray(data) ? data : []
    selectedDevices.value = []
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
    console.error('Error cargando perfiles VPN:', error)
  }
}

// ===== FUNCIONES ALTA =====
async function handleAddDeviceOneStep() {
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
  }

  isSubmitting.value = true
  try {
    const { data } = await api.post('/devices/manual', payload)
    showNotification(`Dispositivo "${data.client_name}" creado.`, 'success')
    resetAddForm()
    fetchAllDevices()
    currentTab.value = 'manage'
  } catch (error) {
    console.error('Error creando dispositivo:', error)
    showNotification(error.response?.data?.detail || 'Error al añadir dispositivo.', 'error')
  } finally {
    isSubmitting.value = false
  }
}

async function handleTestReachability() {
  if (!addForm.value.ip_address?.trim()) return showNotification('Ingresá la IP.', 'error')

  const payload = {
    ip_address: addForm.value.ip_address,
    api_port: Number(addForm.value.api_port) || 8728,
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
    console.error('Error probando conexión:', error)
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
    maestro_id: null,
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
    console.error('Error promoviendo a maestro:', error)
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
    console.error('Error asociando VPN:', error)
    showNotification('Error al actualizar VPN.', 'error')
  }
}

async function deleteDevice(device) {
  if (!confirm(`¿Eliminar "${device.client_name}"?`)) return
  try {
    deletingId.value = device.id
    await api.delete(`/devices/${device.id}`)
    await fetchAllDevices()
    showNotification('Eliminado.', 'success')
  } catch (error) {
    console.error('Error eliminando dispositivo:', error)
    showNotification('Error al eliminar.', 'error')
  } finally {
    deletingId.value = null
  }
}

// ===== LOGICA SELECCIÓN MULTIPLE =====
function toggleSelection(id) {
  if (selectedDevices.value.includes(id)) {
    selectedDevices.value = selectedDevices.value.filter((d) => d !== id)
  } else {
    selectedDevices.value.push(id)
  }
}

function selectAll() {
  if (selectedDevices.value.length === allDevices.value.length) {
    selectedDevices.value = []
  } else {
    selectedDevices.value = allDevices.value.map((d) => d.id)
  }
}

function openBulkModal() {
  if (selectedDevices.value.length === 0) return
  showBulkModal.value = true
}

async function submitBulkMonitors() {
  isBulking.value = true
  try {
    const payload = {
      device_ids: selectedDevices.value,
      sensor_config: {
        sensor_type: bulkForm.value.sensor_type,
        name_template: bulkForm.value.name_template,
        is_active: bulkForm.value.is_active,
        alerts_paused: bulkForm.value.alerts_paused,
        config: {
          interval: bulkForm.value.interval,
          count: bulkForm.value.packet_count,
          size: bulkForm.value.packet_size,
        },
      },
    }

    const { data } = await api.post('/monitors/bulk', payload)
    showNotification(`Se crearon ${data.created} monitores exitosamente.`, 'success')
    showBulkModal.value = false
    selectedDevices.value = [] // Reset selección
  } catch (error) {
    console.error('Error creando monitores masivos:', error)
    showNotification('Error al crear monitores masivos.', 'error')
  } finally {
    isBulking.value = false
  }
}

// ===== Lifecycle =====
onMounted(async () => {
  await loadUser()
  fetchAllDevices()
  fetchVpnProfiles()
})
</script>

<template>
  <div class="page-wrap">
    <header class="topbar">
      <h1>Dispositivos</h1>
      <div class="auth-box">
        <span v-if="userEmail" class="user-pill">{{ userEmail }}</span>
        <button class="btn-secondary" @click="logout">Cerrar sesión</button>
      </div>
    </header>

    <div class="tabs">
      <button :class="{ active: currentTab === 'add' }" @click="currentTab = 'add'">Agregar</button>
      <button :class="{ active: currentTab === 'manage' }" @click="currentTab = 'manage'">
        Gestionar
      </button>
    </div>

    <section v-if="currentTab === 'add'" class="control-section fade-in">
      <h2><i class="icon">➕</i> Alta de dispositivo (en un paso)</h2>
      <form @submit.prevent="handleAddDeviceOneStep" class="form-layout">
        <div class="grid-2">
          <div>
            <label>Cliente *</label>
            <input
              type="text"
              v-model="addForm.client_name"
              placeholder="Nombre del cliente"
              required
            />
          </div>
          <div class="ip-port-grid">
            <div style="flex-grow: 3">
              <label>IP *</label>
              <input type="text" v-model="addForm.ip_address" placeholder="192.168.88.1" required />
            </div>
            <div style="flex-grow: 1">
              <label>Puerto API</label>
              <input type="number" v-model="addForm.api_port" placeholder="8728" required />
            </div>
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

        <button v-if="selectedDevices.length > 0" @click="openBulkModal" class="btn-bulk fade-in">
          ⚡ Acciones Masivas ({{ selectedDevices.length }})
        </button>
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
                    selectedDevices.length > 0 && selectedDevices.length === allDevices.length
                  "
                />
              </th>
              <th>Nombre</th>
              <th>IP Address</th>
              <th>Rol</th>
              <th>Conexión</th>
              <th>Acciones</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="device in allDevices"
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
              </td>
              <td class="font-mono">
                {{ device.ip_address
                }}<span v-if="device.api_port !== 8728" class="text-dim"
                  >:{{ device.api_port }}</span
                >
              </td>
              <td>
                <span v-if="device.is_maestro" class="badge maestro">Maestro</span>
                <span v-else class="badge device">Dispositivo</span>
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
              <td>
                <div class="row-actions">
                  <button
                    v-if="!device.is_maestro"
                    @click="promoteToMaestro(device)"
                    class="btn-sm btn-action"
                    title="Promover a Maestro"
                  >
                    ⬆️
                  </button>
                  <button
                    @click="deleteDevice(device)"
                    class="btn-sm btn-del"
                    :disabled="deletingId === device.id"
                  >
                    🗑️
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <div v-if="showBulkModal" class="modal-overlay">
      <div class="modal-content">
        <h3>⚡ Crear Monitores Masivos</h3>
        <p>
          Se crearán monitores para <strong>{{ selectedDevices.length }}</strong> dispositivos.
        </p>

        <div class="bulk-form">
          <div class="form-group">
            <label>Plantilla de Nombre</label>
            <input v-model="bulkForm.name_template" placeholder="{{hostname}} - Ping Check" />
            <small
              >Usa <code v-pre>{{ hostname }}</code> o <code v-pre>{{ ip }}</code> para nombres
              dinámicos.</small
            >
          </div>

          <div class="form-row">
            <div class="form-group">
              <label>Intervalo (seg)</label>
              <input type="number" v-model="bulkForm.interval" />
            </div>
            <div class="form-group">
              <label>Paquetes</label>
              <input type="number" v-model="bulkForm.packet_count" />
            </div>
          </div>

          <div class="form-group checkbox">
            <label
              ><input type="checkbox" v-model="bulkForm.is_active" /> Activar inmediatamente</label
            >
          </div>
        </div>

        <div class="modal-actions">
          <button @click="showBulkModal = false" class="btn-secondary">Cancelar</button>
          <button @click="submitBulkMonitors" class="btn-primary" :disabled="isBulking">
            {{ isBulking ? 'Procesando...' : 'Crear Monitores' }}
          </button>
        </div>
      </div>
    </div>

    <div v-if="notification.show" class="notification" :class="notification.type">
      {{ notification.message }}
    </div>
  </div>
</template>

<style scoped>
/* ESTILO CORREGIDO */

.page-wrap {
  padding: 1rem;
  max-width: 1400px;
  margin: 0 auto;
}

/* Topbar */
.topbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}
.topbar h1 {
  color: var(--blue);
}
.auth-box {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}
.user-pill {
  padding: 0.25rem 0.5rem;
  border: 1px solid var(--primary-color);
  border-radius: 20px;
  font-size: 0.9rem;
  color: var(--gray);
}

/* Tabs */
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

/* Sections */
.control-section {
  background: var(--surface-color);
  padding: 1.5rem;
  border-radius: 10px;
}
.control-section h2 {
  color: white;
  margin-top: 0;
  margin-bottom: 1.5rem;
}

/* Forms */
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

/* Inputs & Selects - FIX PARA CHECKBOXES Y SELECTS */
/* Excluimos checkbox de la regla width: 100% para que no se deformen */
input:not([type='checkbox']),
select {
  width: 100%;
  background-color: var(--bg-color); /* Fondo del tema */
  color: white;
  border: 1px solid var(--primary-color);
  border-radius: 6px;
  padding: 0.7rem;
  margin-top: 0.3rem;
  outline: none;

  /* Estilos para selectores correctos */
  -webkit-appearance: none;
  appearance: none;
  background-image: url('data:image/svg+xml;charset=US-ASCII,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20width%3D%22292.4%22%20height%3D%22292.4%22%3E%3Cpath%20fill%3D%22%23FFF%22%20d%3D%22M287%2069.4a17.6%2017.6%200%200%200-13-5.4H18.4c-5%200-9.3%201.8-12.9%205.4A17.6%2017.6%200%200%200%200%2082.2c0%205%201.8%209.3%205.4%2012.9l128%20127.9c3.6%203.6%207.8%205.4%2012.8%205.4s9.2-1.8%2012.8-5.4L287%2095c3.5-3.5%205.4-7.8%205.4-12.8%200-5-1.9-9.2-5.5-12.8z%22%2F%3E%3C%2Fsvg%3E');
  background-repeat: no-repeat;
  background-position: right 0.7em top 50%;
  background-size: 0.65em auto;
}

/* Excepción para inputs de texto (quitar flecha) */
input[type='text'],
input[type='number'] {
  background-image: none;
}

/* Estilo específico para Checkboxes normales */
input[type='checkbox'] {
  width: auto;
  margin-right: 0.5rem;
  transform: scale(1.2);
  cursor: pointer;
}

/* FIX: Opciones del desplegable oscuras */
select:invalid {
  color: white !important;
}
select option {
  background-color: var(--bg-color) !important;
  color: white !important;
}

label {
  font-size: 0.9rem;
  font-weight: bold;
  color: var(--gray);
}

/* Buttons */
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
.btn-bulk {
  background: #f39c12;
  color: #fff;
  border: none;
  padding: 0.6rem 1rem;
  border-radius: 6px;
  font-weight: bold;
  cursor: pointer;
}

/* Table Style */
.manage-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}
.table-responsive {
  overflow-x: auto;
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

/* BOTONES DE ACCIÓN DE TABLA */
.row-actions {
  display: flex;
  gap: 0.5rem;
}
.btn-sm {
  padding: 4px 8px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}
/* Estilo unificado para botón de acción normal */
.btn-action {
  border: 1px solid var(--primary-color);
  background: transparent;
  color: white;
}
/* FIX: Estilo del botón de borrar para que coincida con ScanView */
.btn-del {
  background-color: var(--error-red);
  color: white;
  border: none; /* Quitamos borde para que sea sólido */
}

/* Modal */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
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
  width: 500px;
  max-width: 90%;
  box-shadow: 0 10px 25px rgba(0, 0, 0, 0.5);
  border: 1px solid var(--primary-color);
  color: white;
}
.bulk-form {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  margin: 1.5rem 0;
}
.form-row {
  display: flex;
  gap: 1rem;
}
.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 1rem;
}

/* Utilities */
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
.font-mono {
  font-family: monospace;
}
.text-dim {
  color: #777;
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

.notification {
  position: fixed;
  top: 90px;
  right: 20px;
  z-index: 4000;
  padding: 1rem 1.5rem;
  border-radius: 8px;
  font-weight: bold;
  color: white;
}
.notification.success {
  background: var(--green);
}
.notification.error {
  background: var(--error-red);
}
</style>
