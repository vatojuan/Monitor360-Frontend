<script setup>
import { ref, onMounted, computed } from 'vue'
import api from '@/lib/api'

const currentTab = ref('schedules')
const notification = ref({ show: false, message: '', type: 'success' })

// --- ESTADOS ---
const schedules = ref([])
const history = ref([])
const availableGroups = ref([])
const availableChannels = ref([])

// Para leer el buzón
const showReportModal = ref(false)
const selectedReportText = ref('')
const selectedReportName = ref('')

const commonTimezones = [
  'America/Argentina/Buenos_Aires',
  'America/Santiago',
  'America/Montevideo',
  'America/Sao_Paulo',
  'America/Bogota',
  'America/Lima',
  'America/Mexico_City',
  'America/New_York',
  'UTC',
  'Europe/Madrid',
]

const newSchedule = ref({
  name: '',
  time_str: '08:00',
  timezone: 'America/Argentina/Buenos_Aires',
  target_groups: [],
  channel_ids: [],
  tone: 'profesional',
  is_active: true
})

// --- VALIDACIÓN DE HORARIO COMPUTADA ---
const isTimeInvalid = computed(() => {
  if (!newSchedule.value.time_str) return true
  const hour = parseInt(newSchedule.value.time_str.split(':')[0], 10)
  // Bloquear entre las 03:00 y las 04:59
  return hour === 3 || hour === 4
})

const isFormValid = computed(() => {
  return (
    !isTimeInvalid.value &&
    newSchedule.value.name.trim() !== '' &&
    newSchedule.value.target_groups.length > 0 &&
    newSchedule.value.channel_ids.length > 0
  )
})

onMounted(() => {
  fetchInitialData()
})

function showNotification(message, type = 'success') {
  notification.value = { show: true, message, type }
  setTimeout(() => (notification.value.show = false), 4000)
}

function formatDate(isoString) {
  if (!isoString) return '-'
  try {
    return new Date(isoString).toLocaleString()
  } catch {
    return isoString
  }
}

// --- FETCHERS ---
async function fetchInitialData() {
  await Promise.all([
    fetchGroups(),
    fetchChannels(),
    fetchSchedules(),
    fetchHistory()
  ])
}

async function fetchGroups() {
  try {
    const { data } = await api.get('/groups')
    availableGroups.value = data.map((g) => g.name)
  } catch (err) {
    console.error('Error fetching groups:', err)
  }
}

async function fetchChannels() {
  try {
    const { data } = await api.get('/channels')
    availableChannels.value = data || []
  } catch (err) {
    console.error('Error fetching channels:', err)
  }
}

async function fetchSchedules() {
  try {
    // CORREGIDO: Se quitó /api/
    const { data } = await api.get('/reports/schedules')
    schedules.value = Array.isArray(data) ? data : []
  } catch (err) {
    console.error('Error al cargar reportes programados:', err)
  }
}

async function fetchHistory() {
  try {
    // CORREGIDO: Se quitó /api/
    const { data } = await api.get('/reports/history')
    history.value = Array.isArray(data) ? data : []
  } catch (err) {
    console.error('Error al cargar historial:', err)
  }
}

// --- ACCIONES ---
async function handleAddSchedule() {
  if (!isFormValid.value) return

  try {
    // CORREGIDO: Se quitó /api/
    await api.post('/reports/schedules', newSchedule.value)
    showNotification('Reporte programado con éxito.', 'success')
    
    // Resetear formulario (manteniendo la zona horaria)
    newSchedule.value = {
      name: '',
      time_str: '08:00',
      timezone: newSchedule.value.timezone,
      target_groups: [],
      channel_ids: [],
      tone: 'profesional',
      is_active: true
    }
    
    fetchSchedules()
  } catch (err) {
    console.error('Error creando reporte:', err)
    showNotification(err.response?.data?.detail || 'Error al programar reporte.', 'error')
  }
}

async function handleDeleteSchedule(id) {
  if (!confirm('¿Seguro que deseas eliminar esta programación?')) return
  try {
    // CORREGIDO: Se quitó /api/
    await api.delete(`/reports/schedules/${id}`)
    showNotification('Programación eliminada.', 'success')
    fetchSchedules()
  } catch (err) {
    console.error('Error eliminando reporte:', err)
    showNotification('Error al eliminar.', 'error')
  }
}

const runningScheduleId = ref(null)

async function handleRunNow(schedule) {
  runningScheduleId.value = schedule.id
  try {
    await api.post(`/reports/schedules/${schedule.id}/run`)
    showNotification(`Reporte "${schedule.name}" disparado. Aparecerá en el buzón en unos segundos.`, 'success')
    setTimeout(() => fetchHistory(), 3000)
  } catch (err) {
    console.error('Error ejecutando reporte:', err)
    showNotification(err.response?.data?.detail || 'Error al ejecutar el reporte.', 'error')
  } finally {
    runningScheduleId.value = null
  }
}

async function toggleScheduleActive(schedule) {
  const newVal = !schedule.is_active
  try {
    // CORREGIDO: Se quitó /api/
    await api.put(`/reports/schedules/${schedule.id}`, { is_active: newVal })
    schedule.is_active = newVal
    showNotification(newVal ? 'Reporte activado.' : 'Reporte pausado.')
  } catch (err) {
    showNotification('Error al cambiar el estado.', 'error')
  }
}

function openReportReader(historyItem) {
  selectedReportName.value = historyItem.report_name || 'Reporte de IA'
  selectedReportText.value = historyItem.report_text || 'Sin contenido.'
  showReportModal.value = true
}

function getChannelName(id) {
  const ch = availableChannels.value.find(c => c.id === id)
  return ch ? ch.name : 'Canal Borrado'
}
</script>

<template>
  <div>
    <div v-if="notification.show" :class="['notification', notification.type]">
      {{ notification.message }}
    </div>

    <div class="tabs">
      <button @click="currentTab = 'schedules'" :class="{ active: currentTab === 'schedules' }">
        Configurar Reportes
      </button>
      <button @click="currentTab = 'history'" :class="{ active: currentTab === 'history' }">
        Buzón / Historial
      </button>
    </div>

    <div class="tab-content">
      <section v-if="currentTab === 'schedules'" class="grid-layout">
        
        <div class="control-section">
          <h2><i class="icon">🤖</i> Nuevo Reporte IA</h2>
          <p>Programa al asistente virtual para redactar y enviar estados de red.</p>

          <form @submit.prevent="handleAddSchedule" class="form-layout">
            <label>Nombre del Reporte</label>
            <input type="text" v-model="newSchedule.name" placeholder="Ej: Resumen Matutino Gerencia" required />

            <div class="grid-2-cols">
              <div>
                <label>Horario de Envío</label>
                <input type="time" v-model="newSchedule.time_str" required />
              </div>
              <div>
                <label>Zona Horaria</label>
                <select v-model="newSchedule.timezone" required>
                  <option v-for="tz in commonTimezones" :key="tz" :value="tz">{{ tz }}</option>
                </select>
              </div>
            </div>

            <div v-if="isTimeInvalid" class="form-hint-box danger-hint">
              <strong>⚠️ Horario Inválido:</strong>
              El sistema consolida los datos masivos de red a las 04:00 AM. 
              Por favor, configura el envío a partir de las <strong>05:00 AM</strong>.
            </div>

            <label>Grupos a Monitorear</label>
            <div class="checkbox-scroll-box">
              <div v-if="availableGroups.length === 0" class="empty-hint">No hay grupos creados.</div>
              <label v-for="group in availableGroups" :key="group" class="custom-checkbox">
                <input type="checkbox" :value="group" v-model="newSchedule.target_groups" />
                {{ group }}
              </label>
            </div>

            <label>Canales de Destino (Telegram/Webhook)</label>
            <div class="checkbox-scroll-box">
              <div v-if="availableChannels.length === 0" class="empty-hint">Añade canales en la pestaña 'Notificaciones'.</div>
              <label v-for="channel in availableChannels" :key="channel.id" class="custom-checkbox">
                <input type="checkbox" :value="channel.id" v-model="newSchedule.channel_ids" />
                {{ channel.name }} <small>({{ channel.type }})</small>
              </label>
            </div>

            <label>Tono del Reporte</label>
            <select v-model="newSchedule.tone">
              <option value="profesional">Profesional (Equilibrado)</option>
              <option value="tecnico">Técnico (Detallado con valores)</option>
              <option value="ejecutivo">Ejecutivo (Resumido para gerencia)</option>
            </select>

            <button type="submit" :disabled="!isFormValid" :class="{'disabled-btn': !isFormValid}">
              Programar Reporte
            </button>
          </form>
        </div>

        <div class="control-section">
          <h2><i class="icon">📋</i> Reportes Programados</h2>
          
          <ul v-if="schedules.length > 0" class="item-list">
            <li v-for="schedule in schedules" :key="schedule.id" :class="{'is-inactive': !schedule.is_active}">
              <div class="item-info vertical-info">
                <div class="header-info">
                  <strong>{{ schedule.name }}</strong>
                  <span class="time-badge">
                    🕒 {{ schedule.schedule_config?.time_str || '08:00' }}
                  </span>
                </div>
                
                <div class="meta-info">
                  <span class="meta-tag" title="Grupos">
                    📁 {{ schedule.action_payload?.target_groups?.length || 0 }} grupos
                  </span>
                  <span class="meta-tag" title="Canales">
                    📡 {{ schedule.action_payload?.channel_ids?.length || 0 }} canales
                  </span>
                </div>
              </div>
              
              <div class="item-actions">
                <button
                  @click="handleRunNow(schedule)"
                  class="run-now-btn"
                  :disabled="runningScheduleId === schedule.id"
                  title="Ejecutar ahora"
                >
                  {{ runningScheduleId === schedule.id ? '...' : '▶ Ahora' }}
                </button>
                <button
                  @click="toggleScheduleActive(schedule)"
                  class="test-btn"
                  :class="{'active-mode': schedule.is_active}"
                  :title="schedule.is_active ? 'Pausar' : 'Activar'"
                >
                  {{ schedule.is_active ? 'ON' : 'OFF' }}
                </button>
                <button @click="handleDeleteSchedule(schedule.id)" class="delete-btn" title="Eliminar">×</button>
              </div>
            </li>
          </ul>
          <div v-else class="empty-list">No hay reportes programados actualmente.</div>
        </div>
      </section>

      <section v-if="currentTab === 'history'" class="control-section full-width">
        <h2><i class="icon">📬</i> Buzón de Reportes IA</h2>
        <p>Aquí puedes leer las copias exactas de los resúmenes que la IA envió a los canales.</p>

        <table v-if="history.length > 0" class="history-table">
          <thead>
            <tr>
              <th>Fecha y Hora</th>
              <th>Reporte</th>
              <th>Grupos Incluidos</th>
              <th>Acción</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in history" :key="item.id">
              <td class="nowrap">{{ formatDate(item.created_at) }}</td>
              <td><strong>{{ item.report_name }}</strong></td>
              <td>
                <span class="group-pill" v-for="g in item.target_groups" :key="g">{{ g }}</span>
              </td>
              <td>
                <button @click="openReportReader(item)" class="read-btn">📖 Leer Resumen</button>
              </td>
            </tr>
          </tbody>
        </table>
        <div v-else class="empty-list">El buzón está vacío. Aquí aparecerán los reportes cuando el sistema los genere.</div>
      </section>
    </div>

    <div v-if="showReportModal" class="modal-overlay" @click.self="showReportModal = false">
      <div class="modal-content large">
        <h3>{{ selectedReportName }}</h3>
        <hr class="separator"/>
        
        <div class="report-reader-box">
          <pre class="report-text">{{ selectedReportText }}</pre>
        </div>

        <div class="modal-actions">
          <button class="btn-primary" @click="showReportModal = false">Cerrar</button>
        </div>
      </div>
    </div>

  </div>
</template>

<style scoped>
/* REUSANDO CLASES DEL DISEÑO BASE */
.tabs {
  display: flex;
  gap: 0.5rem;
  border-bottom: 2px solid var(--primary-color);
  margin-bottom: 2rem;
}
.tabs button {
  padding: 0.8rem 1.5rem;
  border: none;
  background-color: transparent;
  color: var(--gray);
  font-size: 1rem;
  font-weight: bold;
  cursor: pointer;
  border-radius: 8px 8px 0 0;
  transition: all 0.2s;
}
.tabs button:hover {
  background-color: rgba(255,255,255,0.05);
}
.tabs button.active {
  background-color: var(--primary-color);
  color: white;
}

.grid-layout {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
  gap: 2rem;
  align-items: start;
}
.control-section {
  background-color: var(--surface-color);
  padding: 2rem;
  border-radius: 12px;
  border: 1px solid var(--primary-color);
}
.control-section.full-width {
  grid-column: 1 / -1;
}
.control-section h2 {
  margin-top: 0;
  color: white;
  margin-bottom: 0.5rem;
  display: flex;
  align-items: center;
  gap: 10px;
}
.control-section p {
  color: var(--gray);
  margin-bottom: 1.5rem;
  font-size: 0.9rem;
}

.form-layout {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}
.form-layout label {
  font-weight: bold;
  color: var(--gray);
  margin-bottom: -0.5rem;
  font-size: 0.9rem;
}
.form-layout input[type="text"],
.form-layout input[type="time"],
.form-layout select {
  padding: 0.8rem;
  background-color: var(--bg-color);
  border: 1px solid var(--primary-color);
  border-radius: 6px;
  color: white;
  width: 100%;
}
.form-layout button {
  padding: 1rem;
  margin-top: 1rem;
  background-color: var(--blue);
  border: none;
  border-radius: 6px;
  color: white;
  font-weight: bold;
  cursor: pointer;
  transition: background 0.2s;
}
.form-layout button:hover:not(:disabled) {
  filter: brightness(1.1);
}
.form-layout button.disabled-btn {
  background-color: #555;
  cursor: not-allowed;
  opacity: 0.6;
}

.grid-2-cols {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}

/* CAJA DE CHECKBOXES CON SCROLL */
.checkbox-scroll-box {
  background: var(--bg-color);
  border: 1px solid var(--primary-color);
  border-radius: 6px;
  padding: 0.5rem;
  max-height: 150px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}
.custom-checkbox {
  display: flex;
  align-items: center;
  gap: 10px;
  color: #ccc;
  font-weight: normal !important;
  cursor: pointer;
  padding: 0.4rem;
  border-radius: 4px;
}
.custom-checkbox:hover {
  background: rgba(255,255,255,0.05);
}
.custom-checkbox input[type="checkbox"] {
  width: 16px;
  height: 16px;
  margin: 0;
  cursor: pointer;
}
.empty-hint {
  color: #666;
  font-size: 0.85rem;
  padding: 0.5rem;
  font-style: italic;
}

/* ALERTA DE VALIDACION */
.form-hint-box {
  background-color: var(--bg-color);
  border: 1px solid var(--primary-color);
  border-radius: 6px;
  padding: 1rem;
  font-size: 0.9rem;
  color: var(--gray);
}
.form-hint-box.danger-hint {
  border-color: rgba(255, 107, 107, 0.5);
  background-color: rgba(255, 107, 107, 0.05);
  color: #ff6b6b;
}

/* LISTA DE PROGRAMADOS */
.empty-list {
  color: var(--gray);
  text-align: center;
  padding: 2rem;
  border: 2px dashed var(--primary-color);
  border-radius: 8px;
}
.item-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 0.8rem;
}
.item-list li {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background-color: var(--bg-color);
  padding: 1rem;
  border-radius: 8px;
  border-left: 4px solid var(--blue);
  transition: opacity 0.2s;
}
.item-list li.is-inactive {
  border-left-color: #555;
  opacity: 0.6;
}

.vertical-info {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  width: 100%;
}
.header-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}
.header-info strong {
  color: white;
  font-size: 1.1rem;
}
.time-badge {
  background: rgba(255,255,255,0.1);
  padding: 4px 8px;
  border-radius: 4px;
  font-family: monospace;
  font-size: 0.9rem;
  color: #fff;
}
.meta-info {
  display: flex;
  gap: 10px;
}
.meta-tag {
  font-size: 0.8rem;
  color: #aaa;
  background: var(--surface-color);
  padding: 2px 6px;
  border-radius: 4px;
}

.item-actions {
  display: flex;
  align-items: center;
  gap: 0.8rem;
  flex-shrink: 0;
  margin-left: 1rem;
}
.run-now-btn {
  background-color: transparent;
  border: 1px solid var(--blue);
  color: var(--blue);
  padding: 0.4rem 0.8rem;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.85rem;
  font-weight: bold;
  transition: background 0.2s;
}
.run-now-btn:hover:not(:disabled) {
  background-color: rgba(66, 135, 245, 0.15);
}
.run-now-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.test-btn {
  background-color: transparent;
  border: 1px solid var(--primary-color);
  color: #888;
  padding: 0.4rem 0.8rem;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.85rem;
  font-weight: bold;
}
.test-btn.active-mode {
  border-color: var(--green);
  color: var(--green);
}
.delete-btn {
  background: none;
  border: none;
  color: var(--gray);
  font-size: 1.8rem;
  cursor: pointer;
  padding: 0 0.5rem;
}
.delete-btn:hover {
  color: var(--error-red);
}

/* HISTORIAL / TABLA */
.history-table {
  width: 100%;
  border-collapse: collapse;
}
.history-table th,
.history-table td {
  padding: 1rem;
  text-align: left;
  border-bottom: 1px solid var(--primary-color);
}
.history-table th {
  color: var(--gray);
  font-weight: bold;
}
.history-table td {
  color: #eee;
}
.nowrap {
  white-space: nowrap;
}
.group-pill {
  display: inline-block;
  background: var(--bg-color);
  border: 1px solid var(--primary-color);
  color: #ccc;
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 0.8rem;
  margin-right: 5px;
}
.read-btn {
  background: var(--primary-color);
  border: none;
  color: white;
  padding: 0.5rem 1rem;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.9rem;
}
.read-btn:hover {
  filter: brightness(1.2);
}

/* MODAL Y LECTOR */
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
  max-width: 500px;
  border: 1px solid var(--primary-color);
}
.modal-content.large {
  max-width: 800px;
}
.modal-content h3 {
  margin-top: 0;
  color: white;
}
.separator {
  border: 0;
  border-top: 1px solid var(--primary-color);
  margin: 1rem 0;
}
.report-reader-box {
  background: var(--bg-color);
  padding: 1.5rem;
  border-radius: 6px;
  max-height: 60vh;
  overflow-y: auto;
  border: 1px solid #333;
}
.report-text {
  color: #eee;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; /* Fuente de lectura limpia */
  white-space: pre-wrap;
  line-height: 1.6;
  font-size: 0.95rem;
  margin: 0;
}
.modal-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 1.5rem;
}
.btn-primary {
  background: var(--blue);
  color: white;
  border: none;
  padding: 0.6rem 1.5rem;
  border-radius: 4px;
  cursor: pointer;
  font-weight: bold;
}

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

@media (max-width: 820px) {
  .grid-layout {
    grid-template-columns: 1fr;
    gap: 1rem;
  }
  .control-section {
    padding: 1rem;
  }
  .tabs {
    flex-wrap: wrap;
  }
}
</style>