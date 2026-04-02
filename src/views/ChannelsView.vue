<script setup>
import { ref, onMounted } from 'vue'
import api from '@/lib/api' // cliente central con Authorization automático

const currentTab = ref('channels')
const notification = ref({ show: false, message: '', type: 'success' })

// --- Estado ---
const channels = ref([])
const history = ref([])
const newChannelType = ref('telegram') // Cambiado el valor por defecto a telegram

// Lista de zonas horarias comunes
const commonTimezones = [
  'UTC',
  'America/Argentina/Buenos_Aires',
  'America/Santiago',
  'America/Montevideo',
  'America/Sao_Paulo',
  'America/Bogota',
  'America/Lima',
  'America/Mexico_City',
  'America/New_York',
  'America/Los_Angeles',
  'Europe/Madrid',
  'Europe/London',
]

const newChannel = ref({
  name: '',
  timezone: 'America/Argentina/Buenos_Aires', // Valor por defecto
  webhook: { url: '' },
  telegram: { bot_token: '', bot_role: 'alert_only' }, // Añadido bot_role por defecto
})

const isTestingChannel = ref(false)
const expandedChannelId = ref(null) // Para abrir/cerrar panel de accesos Telegram

onMounted(() => {
  fetchChannels()
  fetchHistory()
})

function showNotification(message, type = 'success') {
  notification.value = { show: true, message, type }
  setTimeout(() => (notification.value.show = false), 4000)
}

function safeParse(jsonLike) {
  try {
    return typeof jsonLike === 'string' ? JSON.parse(jsonLike) : jsonLike || {}
  } catch {
    return {}
  }
}

function formatDate(isoString) {
  if (!isoString) return '-'
  try {
    return new Date(isoString).toLocaleString(undefined, {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
    })
  } catch {
    return isoString
  }
}

// NUEVO: Formateador para mostrar el rol del bot de forma amigable
function formatBotRole(role) {
  if (role === 'alert_only') return 'Solo Alertas'
  if (role === 'consultant') return 'Consultor NOC'
  return 'Híbrido'
}

async function fetchChannels() {
  try {
    const { data } = await api.get('/channels')
    channels.value = (data || []).map((ch) => ({ ...ch, config: safeParse(ch.config) }))
  } catch (err) {
    console.error('Error al cargar canales:', err)
    showNotification(err.response?.data?.detail || 'Error al cargar canales.', 'error')
  }
}

async function fetchHistory() {
  try {
    const { data } = await api.get('/alerts/history')
    history.value = Array.isArray(data) ? data : []
  } catch (err) {
    console.error('Error al cargar historial:', err)
    showNotification(err.response?.data?.detail || 'Error al cargar historial.', 'error')
  }
}

async function handleAddChannel() {
  let payload
  
  if (newChannelType.value === 'webhook') {
    if (!newChannel.value.name.trim() || !newChannel.value.webhook.url.trim()) {
      return showNotification('Nombre y URL son obligatorios.', 'error')
    }
    payload = {
      name: newChannel.value.name.trim(),
      type: 'webhook',
      config: {
        url: newChannel.value.webhook.url.trim(),
        timezone: newChannel.value.timezone,
      },
    }
  } else {
    // telegram (SIMPLIFICADO Y CON ROLES)
    if (!newChannel.value.name.trim() || !newChannel.value.telegram.bot_token.trim()) {
      return showNotification('Nombre y Bot Token son obligatorios.', 'error')
    }
    payload = {
      name: newChannel.value.name.trim(),
      type: 'telegram',
      config: {
        bot_token: newChannel.value.telegram.bot_token.trim(),
        timezone: newChannel.value.timezone,
        bot_role: newChannel.value.telegram.bot_role, // <-- NUEVO: Se envía el rol a la DB
        authorized_chats: [], // Se inicializa vacío, la gente pide acceso por el bot
        pending_requests: []
      },
    }
  }

  try {
    await api.post('/channels', payload)
    showNotification('Canal añadido correctamente.', 'success')
    // Reset
    newChannel.value = {
      name: '',
      timezone: 'America/Argentina/Buenos_Aires',
      webhook: { url: '' },
      telegram: { bot_token: '', bot_role: 'alert_only' },
    }
    fetchChannels()
  } catch (err) {
    console.error('Error al añadir canal:', err)
    showNotification(err.response?.data?.detail || 'Error al añadir canal.', 'error')
  }
}

async function handleDeleteChannel(id) {
  if (!confirm('¿Seguro? Los sensores que usen este canal dejarán de notificar y los operadores de Telegram perderán acceso.')) return
  try {
    await api.delete(`/channels/${id}`)
    showNotification('Canal eliminado.', 'success')
    fetchChannels()
  } catch (err) {
    console.error('Error al eliminar canal:', err)
    showNotification(err.response?.data?.detail || 'Error al eliminar canal.', 'error')
  }
}

async function handleTestChannel(id) {
  if (isTestingChannel.value) return
  isTestingChannel.value = true
  
  try {
    showNotification('Enviando mensaje de prueba...', 'success')
    const { data } = await api.post(`/channels/${id}/test`)
    showNotification(data.message || 'Prueba enviada correctamente.', 'success')
  } catch (err) {
    console.error('Error al probar canal:', err)
    showNotification(err.response?.data?.detail || 'Error al enviar el mensaje de prueba. Verifica la configuración.', 'error')
  } finally {
    isTestingChannel.value = false
  }
}

// --- NUEVO: Gestión de Accesos de Telegram ---
function toggleAccessPanel(channelId) {
  expandedChannelId.value = expandedChannelId.value === channelId ? null : channelId
}

async function approveAccess(channelId, requestObj) {
  try {
    await api.post(`/channels/${channelId}/approve_chat`, {
      chat_id: requestObj.chat_id,
      name: requestObj.name,
      username: requestObj.username
    })
    showNotification(`Acceso concedido a ${requestObj.name}`, 'success')
    fetchChannels()
  } catch (err) {
    showNotification(err.response?.data?.detail || 'Error al aprobar.', 'error')
  }
}

async function revokeAccess(channelId, chatId) {
  if (!confirm('¿Seguro que deseas revocar el acceso a este usuario/grupo?')) return
  try {
    await api.post(`/channels/${channelId}/revoke_chat`, { chat_id: chatId })
    showNotification('Acceso revocado.', 'success')
    fetchChannels()
  } catch (err) {
    showNotification(err.response?.data?.detail || 'Error al revocar.', 'error')
  }
}

function formatHistoryDetails(details) {
  try {
    const parsed = safeParse(details)
    return parsed?.reason || details
  } catch {
    return details
  }
}
</script>

<template>
  <div>
    <div v-if="notification.show" :class="['notification', notification.type]">
      {{ notification.message }}
    </div>

    <div class="tabs">
      <button @click="currentTab = 'channels'" :class="{ active: currentTab === 'channels' }">
        Canales de Notificación
      </button>
      <button @click="currentTab = 'history'" :class="{ active: currentTab === 'history' }">
        Historial de Alertas
      </button>
    </div>

    <div class="tab-content">
      <section v-if="currentTab === 'channels'" class="grid-layout">
        <div class="control-section">
          <h2><i class="icon">➕</i> Añadir Canal</h2>

          <div class="channel-type-selector">
            <button
              @click="newChannelType = 'telegram'"
              :class="{ active: newChannelType === 'telegram' }"
            >
              Telegram Bot
            </button>
            <button
              @click="newChannelType = 'webhook'"
              :class="{ active: newChannelType === 'webhook' }"
            >
              Webhook
            </button>
          </div>

          <form
            v-if="newChannelType === 'telegram'"
            @submit.prevent="handleAddChannel"
            class="form-layout"
          >
            <p>Conecta tu bot de Telegram para notificaciones y consultas en tiempo real.</p>
            <label>Nombre del Canal</label>
            <input
              type="text"
              v-model="newChannel.name"
              placeholder="Ej: NOC Telegram"
              required
            />

            <label>Rol del Bot</label>
            <select v-model="newChannel.telegram.bot_role" required>
              <option value="alert_only">Canal de Alertas (Solo envía notificaciones)</option>
              <option value="consultant">Consultor de Estado NOC (Interactivo)</option>
              <option value="both">Híbrido (Alertas y Consultas)</option>
            </select>

            <label>Zona Horaria</label>
            <select v-model="newChannel.timezone" required>
              <option v-for="tz in commonTimezones" :key="tz" :value="tz">{{ tz }}</option>
            </select>

            <label>Bot Token</label>
            <input
              type="text"
              v-model="newChannel.telegram.bot_token"
              placeholder="Ej: 123456:ABC-DEF1234ghIkl-zyx..."
              required
            />

            <div class="form-hint-box">
              <strong>Nuevo Flujo de Seguridad:</strong>
              <ol>
                <li>Crea tu bot con BotFather y pega el Token arriba.</li>
                <li>Guarda este canal.</li>
                <li>Abre Telegram, busca tu bot y envíale <b>/start</b>.</li>
                <li>El bot te pedirá identificarte. Tras hacerlo, vuelve aquí para aprobar tu propio acceso.</li>
              </ol>
            </div>
            <button type="submit">Guardar y Habilitar Bot</button>
          </form>

          <form
            v-if="newChannelType === 'webhook'"
            @submit.prevent="handleAddChannel"
            class="form-layout"
          >
            <p>Envía alertas a una URL. Ideal para Discord o Slack.</p>
            <label>Nombre del Canal</label>
            <input
              type="text"
              v-model="newChannel.name"
              placeholder="Ej: Slack #soporte"
              required
            />
            <label>URL del Webhook</label>
            <input
              type="url"
              v-model="newChannel.webhook.url"
              placeholder="https://hooks.slack.com/..."
              required
            />

            <label>Zona Horaria</label>
            <select v-model="newChannel.timezone" required>
              <option v-for="tz in commonTimezones" :key="tz" :value="tz">{{ tz }}</option>
            </select>

            <button type="submit">Añadir Canal Webhook</button>
          </form>
        </div>

        <div class="control-section">
          <h2><i class="icon">📡</i> Canales Guardados</h2>
          <ul v-if="channels.length > 0" class="item-list">
            <li v-for="channel in channels" :key="channel.id" class="channel-card">
              <div class="channel-header">
                <div class="item-info">
                  <strong>{{ channel.name }}</strong>
                  <span class="channel-type-badge" :class="channel.type">{{ channel.type }}</span>
                  
                  <span v-if="channel.type === 'telegram'" class="role-badge" :class="channel.config?.bot_role || 'both'">
                    {{ formatBotRole(channel.config?.bot_role || 'both') }}
                  </span>

                  <span style="font-size: 0.8rem; color: #888; margin-left: 0.5rem">
                    ({{ channel.config?.timezone || 'UTC' }})
                  </span>
                  
                  <span v-if="channel.type === 'telegram' && channel.config?.pending_requests?.length > 0" class="pending-badge">
                    {{ channel.config.pending_requests.length }} sol.
                  </span>
                </div>
                
                <div class="item-actions">
                  <button v-if="channel.type === 'telegram'" @click="toggleAccessPanel(channel.id)" class="access-btn" title="Gestionar Accesos">
                    👥
                  </button>
                  <button @click="handleTestChannel(channel.id)" class="test-btn" :disabled="isTestingChannel" title="Probar conexión">🔔</button>
                  <button @click="handleDeleteChannel(channel.id)" class="delete-btn" title="Eliminar Canal">×</button>
                </div>
              </div>

              <div v-if="expandedChannelId === channel.id && channel.type === 'telegram'" class="access-panel">
                <div class="access-column">
                  <h4>Pendientes de Aprobación</h4>
                  <div v-if="!channel.config?.pending_requests || channel.config.pending_requests.length === 0" class="empty-mini">
                    No hay solicitudes
                  </div>
                  <ul v-else class="mini-list">
                    <li v-for="req in channel.config.pending_requests" :key="req.chat_id">
                      <div>
                        <b>{{ req.name }}</b><br>
                        <small>@{{ req.username || 'Sin_alias' }} (ID: {{ req.chat_id }})</small>
                      </div>
                      <div class="mini-actions">
                        <button @click="approveAccess(channel.id, req)" class="btn-approve">✓</button>
                        <button @click="revokeAccess(channel.id, req.chat_id)" class="btn-reject">✕</button>
                      </div>
                    </li>
                  </ul>
                </div>

                <div class="access-column">
                  <h4>Operadores / Grupos Autorizados</h4>
                  <div v-if="!channel.config?.authorized_chats || channel.config.authorized_chats.length === 0" class="empty-mini">
                    Ningún usuario autorizado
                  </div>
                  <ul v-else class="mini-list">
                    <li v-for="chat in channel.config.authorized_chats" :key="chat.chat_id || chat">
                      <div>
                        <b>{{ chat.name || 'Chat ID:' }}</b>
                        <small v-if="chat.chat_id">{{ chat.chat_id }}</small>
                        <small v-else>{{ chat }}</small>
                      </div>
                      <button @click="revokeAccess(channel.id, chat.chat_id || chat)" class="btn-reject" title="Revocar Acceso">✕</button>
                    </li>
                  </ul>
                </div>
              </div>
            </li>
          </ul>
          <div v-else class="empty-list">No hay canales configurados.</div>
        </div>
      </section>

      <section v-if="currentTab === 'history'" class="control-section full-width">
        <h2><i class="icon">📚</i> Historial de Alertas Enviadas</h2>
        <table v-if="history.length > 0" class="history-table">
          <thead>
            <tr>
              <th>Fecha</th>
              <th>Sensor Afectado</th>
              <th>Detalles del Evento</th>
              <th>Canal Notificado</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in history" :key="item.id">
              <td class="nowrap">{{ formatDate(item.timestamp) }}</td>
              <td>{{ item.sensor_name }}</td>
              <td>{{ formatHistoryDetails(item.details) }}</td>
              <td>{{ item.channel_name }}</td>
            </tr>
          </tbody>
        </table>
        <div v-else class="empty-list">No se han registrado alertas.</div>
      </section>
    </div>
  </div>
</template>

<style scoped>
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
}
.tabs button.active {
  background-color: var(--primary-color);
  color: white;
}
.grid-layout {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(450px, 1fr));
  gap: 2rem;
}
.control-section {
  background-color: var(--surface-color);
  padding: 2rem;
  border-radius: 12px;
}
.control-section.full-width {
  grid-column: 1 / -1;
}
.control-section h2 {
  margin-top: 0;
  color: white;
  margin-bottom: 1.5rem;
}
.control-section p {
  color: var(--gray);
  margin-bottom: 1.5rem;
  margin-top: -0.5rem;
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
}
.form-layout input,
.form-layout select {
  padding: 0.8rem;
  background-color: var(--bg-color);
  border: 1px solid var(--primary-color);
  border-radius: 6px;
  color: white;
  width: 100%;
}
.form-layout button {
  padding: 0.8rem;
  margin-top: 1rem;
  background-color: var(--blue);
  border: none;
  border-radius: 6px;
  color: white;
  font-weight: bold;
  cursor: pointer;
}
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
.channel-card {
  display: flex;
  flex-direction: column;
  background-color: var(--bg-color);
  border-radius: 8px;
  overflow: hidden;
}
.channel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem;
}
.item-info {
  display: flex;
  align-items: center;
  gap: 1rem;
  overflow: hidden;
  flex-wrap: wrap; /* Permitir wrap si el nombre es muy largo */
}
.item-info strong {
  color: white;
}
.item-actions {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-shrink: 0;
}
.test-btn, .access-btn {
  background-color: transparent;
  border: 1px solid var(--primary-color);
  color: white;
  padding: 0.4rem 0.6rem;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s ease;
}
.test-btn:hover:not(:disabled), .access-btn:hover {
  background-color: var(--primary-color);
}
.test-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.delete-btn {
  background: none;
  border: none;
  color: var(--gray);
  font-size: 1.5rem;
  cursor: pointer;
  padding: 0 0.5rem;
  transition: color 0.2s ease;
}
.delete-btn:hover {
  color: var(--error-red);
}

/* --- ESTILOS PANEL DE ACCESOS --- */
.pending-badge {
  background-color: var(--error-red);
  color: white;
  font-size: 0.7rem;
  padding: 0.1rem 0.4rem;
  border-radius: 10px;
  font-weight: bold;
}
.access-panel {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
  padding: 1rem;
  background-color: rgba(0,0,0,0.2);
  border-top: 1px solid var(--primary-color);
}
.access-column h4 {
  margin: 0 0 0.8rem 0;
  color: var(--gray);
  font-size: 0.85rem;
  text-transform: uppercase;
}
.mini-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
.mini-list li {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background-color: var(--surface-color);
  padding: 0.6rem;
  border-radius: 6px;
  font-size: 0.85rem;
}
.mini-list b { color: white; }
.mini-list small { color: var(--gray); display: block; }
.mini-actions { display: flex; gap: 0.3rem; }
.btn-approve, .btn-reject {
  border: none;
  border-radius: 4px;
  color: white;
  padding: 0.3rem 0.6rem;
  cursor: pointer;
  font-weight: bold;
}
.btn-approve { background-color: var(--green); }
.btn-reject { background-color: var(--error-red); }
.empty-mini {
  font-size: 0.85rem;
  color: var(--gray);
  font-style: italic;
}

/* --- TABLAS --- */
.history-table {
  width: 100%;
  border-collapse: collapse;
}
.history-table th,
.history-table td {
  padding: 0.75rem 1rem;
  text-align: left;
  border-bottom: 1px solid var(--primary-color);
}
.history-table th {
  color: var(--gray);
}
.nowrap {
  white-space: nowrap;
}

/* --- OTROS --- */
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
.notification.success { background-color: var(--green); }
.notification.error { background-color: var(--error-red); }

.channel-type-selector {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 1.5rem;
  background-color: var(--bg-color);
  padding: 0.5rem;
  border-radius: 8px;
}
.channel-type-selector button {
  flex-grow: 1;
  padding: 0.6rem;
  border: none;
  background-color: transparent;
  color: var(--gray);
  font-weight: bold;
  cursor: pointer;
  border-radius: 6px;
  transition: all 0.2s ease;
}
.channel-type-selector button.active {
  background-color: var(--blue);
  color: white;
}
.channel-type-badge {
  font-size: 0.75rem;
  font-weight: bold;
  padding: 0.2rem 0.6rem;
  border-radius: 12px;
  text-transform: capitalize;
  color: white;
  width: fit-content;
}
.channel-type-badge.webhook { background-color: var(--blue); }
.channel-type-badge.telegram { background-color: #34a8de; }

/* NUEVO ESTILO: Badge del Rol del Bot */
.role-badge {
  font-size: 0.7rem;
  padding: 0.15rem 0.5rem;
  border-radius: 4px;
  background-color: var(--bg-color);
  border: 1px solid var(--gray);
  color: var(--gray);
}
.role-badge.alert_only { border-color: var(--error-red); color: var(--error-red); }
.role-badge.consultant { border-color: var(--green); color: var(--green); }
.role-badge.both { border-color: var(--blue); color: var(--blue); }

.form-hint-box {
  background-color: var(--bg-color);
  border: 1px solid var(--primary-color);
  border-radius: 6px;
  padding: 1rem;
  margin-top: 0.5rem;
  font-size: 0.9rem;
  color: var(--gray);
}
.form-hint-box strong {
  color: var(--font-color);
  display: block;
  margin-bottom: 0.5rem;
}
.form-hint-box ol {
  padding-left: 1.2rem;
  margin: 0;
}
.form-hint-box li {
  margin-bottom: 0.25rem;
}
</style>