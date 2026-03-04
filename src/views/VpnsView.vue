<script setup>
import { ref, onBeforeUnmount, onMounted, watch } from 'vue'
import api from '@/lib/api'
import { addWsListener, connectWebSocketWhenAuthenticated, removeWsListener } from '@/lib/ws'

/* ====== Helpers ====== */
const getAxiosErr = (err) => err?.response?.data?.detail || err?.message || 'Error inesperado.'

// FIX: Parseo robusto que no rompe las claves que terminan en '='
function parseWgIni(iniText) {
  const res = {
    privateKey: '',
    address: '',
    dns: '',
    publicKey: '',
    allowedIps: '',
    endpoint: '',
    serverPublicKey: '',
  }
  if (!iniText) return res

  const lines = iniText.split('\n')
  let section = ''

  for (let line of lines) {
    line = line.trim()
    if (!line || line.startsWith(';') || line.startsWith('#')) continue

    if (line.startsWith('[')) {
      section = line.toLowerCase()
    } else if (line.includes('=')) {
      // USAMOS INDEXOF para partir solo en el primer '='
      const eqIdx = line.indexOf('=')
      const k = line.substring(0, eqIdx).trim().toLowerCase()
      const v = line.substring(eqIdx + 1).trim()

      if (section === '[interface]') {
        if (k === 'privatekey') res.privateKey = v
        if (k === 'address') res.address = v
        if (k === 'dns') res.dns = v
      } else if (section === '[peer]') {
        if (k === 'publickey') res.serverPublicKey = v
        if (k === 'allowedips') res.allowedIps = v
        if (k === 'endpoint') res.endpoint = v
      }
    }
  }
  return res
}

// --- SCRIPT MIKROTIK (Sintaxis CLI con espacios) ---
function buildMikrotikCmdFromIni(iniText, clientPrivKeyOverride = null) {
  const conf = parseWgIni(iniText)
  if (!conf.address || !conf.serverPublicKey || !conf.endpoint)
    return '# Error: Configuración incompleta en el perfil.'

  const privKey = clientPrivKeyOverride || conf.privateKey
  const [host, port] = conf.endpoint.split(':')

  const iface = 'wg-m360'
  const comment = 'Monitor360 VPN'
  const portVal = port || 51820
  const allowed = conf.allowedIps || '0.0.0.0/0'

  return [
    `# === Configuración Cliente MikroTik (${comment}) ===`,
    '',
    '# 1. Limpieza previa (Evita errores de duplicados)',
    `/interface wireguard remove [find name="${iface}"]`,
    `/ip address remove [find interface="${iface}"]`,
    `/interface wireguard peers remove [find interface="${iface}"]`,
    '',
    '# 2. Crear Interfaz WireGuard',
    `/interface wireguard add name="${iface}" comment="${comment}" private-key="${privKey}" listen-port=13231`,
    '',
    '# 3. Asignar Dirección IP',
    `/ip address add address="${conf.address}" interface="${iface}" comment="${comment}"`,
    '',
    '# 4. Configurar Peer (Servidor)',
    `/interface wireguard peers add interface="${iface}" public-key="${conf.serverPublicKey}" endpoint-address="${host}" endpoint-port=${portVal} allowed-address="${allowed}" persistent-keepalive=25 comment="${comment}"`,
    '',
    '# 5. Reglas de Firewall (Forward - Tráfico del túnel)',
    '# Elimina reglas viejas para no acumular basura',
    `/ip firewall filter remove [find comment="Monitor360 WG in"]`,
    `/ip firewall filter remove [find comment="Monitor360 WG out"]`,
    '# Agrega reglas al inicio (place-before=0) para asegurar paso',
    `/ip firewall filter add chain=forward in-interface="${iface}" action=accept comment="Monitor360 WG in" place-before=0`,
    `/ip firewall filter add chain=forward out-interface="${iface}" action=accept comment="Monitor360 WG out" place-before=0`,
    '',
    '# (Opcional) NAT Masquerade si el router debe dar internet por el túnel',
    `# /ip firewall nat add chain=srcnat out-interface="${iface}" action=masquerade comment="Monitor360 NAT"`,
    '',
    '# Configuración finalizada.',
  ].join('\n')
}

async function copyToClipboard(text) {
  try {
    await navigator.clipboard.writeText(text)
    showNotification('📋 Script copiado al portapapeles', 'success')
  } catch (e) {
    console.error(e)
    showNotification('Error al copiar al portapapeles', 'error')
  }
}

function downloadConfFile(name, content) {
  const filename = `${(name || 'vpn').replace(/\s+/g, '_')}.conf`
  const blob = new Blob([content], { type: 'text/plain' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

/* ====== Estado UI ====== */
const newProfile = ref({ name: '', check_ip: '', alerts_enabled: false, notification_channel_id: null })
const vpnProfiles = ref([])
const channels = ref([]) // <-- NUEVO: Almacena canales de notificación
const isLoading = ref(false)
const isCreating = ref(false)

/* ====== Inspector de Estado (Polling) ====== */
const inspector = ref({
  activeProfileId: null,
  running: false,
  connected: false,
  lastHandshake: null,
  rx: 0,
  tx: 0,
  timer: null,
})

function stopInspector() {
  if (inspector.value.timer) clearInterval(inspector.value.timer)
  inspector.value.timer = null
  inspector.value.running = false
  inspector.value.activeProfileId = null
}

async function checkStatus(profile) {
  if (inspector.value.activeProfileId === profile.id && inspector.value.running) {
    stopInspector()
    return
  }

  stopInspector()
  inspector.value.activeProfileId = profile.id
  inspector.value.running = true
  inspector.value.connected = false

  const pubKey = profile.public_key || profile.server_public_key
  if (!pubKey) {
    showNotification('No se encontró Public Key para este perfil.', 'error')
    stopInspector()
    return
  }

  const poll = async () => {
    if (!inspector.value.running) return
    try {
      const { data } = await api.get('/vpns/peer-status', { params: { pub: pubKey } })
      inspector.value.connected = !!data.connected
      inspector.value.rx = data.rx_bytes
      inspector.value.tx = data.tx_bytes
      inspector.value.lastHandshake = data.latest_handshake
        ? new Date(data.latest_handshake * 1000).toLocaleTimeString()
        : 'Nunca'
    } catch (e) {
      console.error(e)
    }
  }

  poll()
  inspector.value.timer = setInterval(poll, 3000)
}

/* ====== Acciones Perfil ====== */
async function fetchChannels() {
  try {
    const { data } = await api.get('/channels')
    channels.value = data || []
  } catch (err) {
    console.error('Error al cargar canales:', err)
  }
}

async function fetchVpnProfiles() {
  isLoading.value = true
  try {
    const { data } = await api.get('/vpns')
    vpnProfiles.value = (data || []).map((p) => ({ ...p, _expanded: false, _saving: false }))
  } catch (err) {
    showNotification(getAxiosErr(err), 'error')
  } finally {
    isLoading.value = false
  }
}

async function createAutoProfile() {
  if (!newProfile.value.name.trim()) return showNotification('Nombre requerido', 'error')
  isCreating.value = true

  try {
    const { data: autoData } = await api.post('/vpns/mikrotik-auto', { interface: 'm360-srv0' })

    const payload = {
      name: newProfile.value.name,
      check_ip: newProfile.value.check_ip || autoData.interface_address?.split('/')[0],
      config_data: autoData.conf_ini,
      alerts_enabled: newProfile.value.alerts_enabled,
      notification_channel_id: newProfile.value.notification_channel_id
    }

    const { data: savedProfile } = await api.post('/vpns', payload)

    vpnProfiles.value.unshift({ ...savedProfile, _expanded: true })
    newProfile.value = { name: '', check_ip: '', alerts_enabled: false, notification_channel_id: null }
    showNotification('Perfil creado y activado.', 'success')
  } catch (err) {
    showNotification(getAxiosErr(err), 'error')
  } finally {
    isCreating.value = false
  }
}

async function updateVpnAlerts(profile) {
  try {
    await api.put(`/vpns/${profile.id}`, {
      alerts_enabled: profile.alerts_enabled,
      notification_channel_id: profile.notification_channel_id
    })
    showNotification('Configuración de alertas actualizada', 'success')
  } catch (err) {
    showNotification(getAxiosErr(err), 'error')
  }
}

async function deleteProfile(profile) {
  if (!confirm('¿Borrar perfil? Se desconectará el cliente.')) return
  try {
    await api.delete(`/vpns/${profile.id}`)
    vpnProfiles.value = vpnProfiles.value.filter((p) => p.id !== profile.id)
    if (inspector.value.activeProfileId === profile.id) stopInspector()
    showNotification('Eliminado', 'success')
  } catch (e) {
    showNotification(getAxiosErr(e), 'error')
  }
}

async function testReachability(profile) {
  if (!profile.check_ip) return showNotification('Sin Check IP', 'error')
  try {
    const { data } = await api.post('/devices/test_reachability', {
      ip_address: profile.check_ip,
      vpn_profile_id: profile.id,
    })
    showNotification(
      data.reachable ? '✅ Ping OK' : '❌ Sin respuesta',
      data.reachable ? 'success' : 'error',
    )
  } catch (e) {
    showNotification(getAxiosErr(e), 'error')
  }
}

async function copyMikrotikScript(configData) {
  try {
    const script = buildMikrotikCmdFromIni(configData)
    if (!script) throw new Error('No se pudo generar el script.')
    await copyToClipboard(script)
  } catch (e) {
    showNotification(getAxiosErr(e), 'error')
  }
}

// Notificaciones
const notification = ref({ show: false, message: '', type: '' })
function showNotification(msg, type = 'success') {
  notification.value = { show: true, message: msg, type }
  setTimeout(() => (notification.value.show = false), 4000)
}

// Variables WS
let wsUnsubRot = null

onBeforeUnmount(() => {
  stopInspector()
  if (wsUnsubRot) removeWsListener(wsUnsubRot)
})

// Funciones auxiliares para proposeProfileName
function proposeProfileName(iniText) {
  try {
    const conf = parseWgIni(iniText)
    if (conf.address && conf.endpoint) return `${conf.address.split('/')[0]} @ ${conf.endpoint}`
    if (conf.endpoint) return conf.endpoint
    if (conf.address) return conf.address.split('/')[0]
  } catch (e) {
    console.debug('Error proponiendo nombre:', e)
    return ''
  }
  return ''
}

onMounted(async () => {
  await fetchChannels() // <-- NUEVO: Cargamos los canales de alerta
  await fetchVpnProfiles()

  // Watch para autocompletar nombre
  watch(
    () => newProfile.value.config_data,
    (val, old) => {
      if (!old && val && !newProfile.value.name.trim()) {
        const suggested = proposeProfileName(val)
        if (suggested) newProfile.value.name = suggested.slice(0, 80)
      }
    },
    { flush: 'post' },
  )

  // WebSocket
  try {
    await connectWebSocketWhenAuthenticated()
    wsUnsubRot = addWsListener((msg) => {
      if (msg?.type === 'device_credential_rotated') {
        console.log('Rotación detectada:', msg)
      }
    })
  } catch (e) {
    console.error('WS error:', e)
  }
})
</script>

<template>
  <div class="page-wrap">
    <div class="header-section">
      <h1>Gestión VPN</h1>
      <p>Administra los túneles WireGuard para tus dispositivos remotos.</p>
    </div>

    <section class="control-section">
      <div class="section-title">
        <i class="icon">🚀</i>
        <h3>Nuevo Cliente</h3>
      </div>

      <div class="create-form-grid">
        <div class="form-group">
          <label>Nombre del Cliente / Sitio</label>
          <input v-model="newProfile.name" type="text" placeholder="Ej: Sucursal Centro" />
        </div>
        
        <div class="form-group">
          <label>Check IP (Opcional)</label>
          <input
            v-model="newProfile.check_ip"
            type="text"
            placeholder="IP interna para monitoreo"
          />
        </div>

        <div class="form-group alert-toggle-group">
          <label class="toggle-label" style="margin-top: auto; margin-bottom: 0.8rem;">
            <input type="checkbox" v-model="newProfile.alerts_enabled" />
            🔔 Habilitar Alertas de Caída
          </label>
        </div>

        <div class="form-group" v-if="newProfile.alerts_enabled">
          <label>Canal de Notificación</label>
          <select v-model="newProfile.notification_channel_id" class="input-select">
            <option :value="null">-- Seleccionar --</option>
            <option v-for="c in channels" :key="c.id" :value="c.id">{{ c.name }}</option>
          </select>
        </div>

        <div class="form-actions" style="grid-column: 1 / -1; text-align: right; margin-top: 0.5rem;">
          <button class="btn-primary" @click="createAutoProfile" :disabled="isCreating">
            {{ isCreating ? 'Generando...' : 'Generar Perfil Automático' }}
          </button>
        </div>
      </div>
    </section>

    <section class="control-section">
      <div class="section-title">
        <i class="icon">📡</i>
        <h3>Perfiles Activos</h3>
      </div>

      <div v-if="isLoading" class="loading-state">
        <span class="spinner"></span> Cargando perfiles...
      </div>

      <ul v-else class="vpn-list">
        <li
          v-for="p in vpnProfiles"
          :key="p.id"
          class="vpn-card"
          :class="{ 'is-active': inspector.activeProfileId === p.id }"
        >
          <div class="vpn-header" @click="p._expanded = !p._expanded">
            <div class="header-main">
              <span
                class="status-dot"
                :class="{ online: inspector.activeProfileId === p.id && inspector.connected }"
              ></span>
              <strong>{{ p.name }}</strong>
              <span class="alert-badge" v-if="p.alerts_enabled" title="Alertas habilitadas">🔔</span>
              <span class="ip-tag" v-if="p.check_ip">{{ p.check_ip }}</span>
            </div>

            <div class="header-actions">
              <span class="toggle-icon">{{ p._expanded ? '▲' : '▼' }}</span>
            </div>
          </div>

          <div v-if="p._expanded" class="vpn-body">
            <div class="toolbar">
              <div class="tool-group">
                <button
                  class="btn-secondary small"
                  @click="downloadConfFile(p.name, p.config_data)"
                >
                  ⬇️ Config
                </button>
                <button class="btn-secondary small" @click="copyMikrotikScript(p.config_data)">
                  📋 Script ROS
                </button>
              </div>

              <div class="tool-group">
                <button
                  class="btn-monitor small"
                  :class="{
                    'is-monitoring': inspector.activeProfileId === p.id && inspector.running,
                  }"
                  @click="checkStatus(p)"
                >
                  {{
                    inspector.activeProfileId === p.id && inspector.running
                      ? '⏹ Detener'
                      : '📡 Monitorizar'
                  }}
                </button>
                <button class="btn-danger small" @click="deleteProfile(p)">Eliminar</button>
              </div>
            </div>

            <div class="alerts-inline-section">
              <h4>⚙️ Alertas y Monitoreo</h4>
              <div class="alerts-controls">
                <label class="toggle-label">
                  <input type="checkbox" v-model="p.alerts_enabled" @change="updateVpnAlerts(p)" />
                  Habilitar Alertas de Caída
                </label>
                
                <select 
                  v-if="p.alerts_enabled" 
                  v-model="p.notification_channel_id" 
                  @change="updateVpnAlerts(p)" 
                  class="input-select"
                >
                  <option :value="null">-- Sin canal seleccionado --</option>
                  <option v-for="c in channels" :key="c.id" :value="c.id">{{ c.name }}</option>
                </select>
              </div>
            </div>
            <transition name="fade">
              <div v-if="inspector.activeProfileId === p.id" class="inspector-panel">
                <div class="inspector-grid">
                  <div class="insp-item">
                    <span class="insp-label">Estado</span>
                    <span class="insp-value" :class="inspector.connected ? 'c-green' : 'c-red'">
                      {{ inspector.connected ? 'CONECTADO' : 'BUSCANDO...' }}
                    </span>
                  </div>
                  <div class="insp-item">
                    <span class="insp-label">Último Handshake</span>
                    <span class="insp-value">{{ inspector.lastHandshake || '--' }}</span>
                  </div>
                  <div class="insp-item">
                    <span class="insp-label">Tráfico (RX/TX)</span>
                    <span class="insp-value">
                      ⬇️ {{ (inspector.rx / 1024).toFixed(1) }} KB
                      <span class="divider">|</span>
                      ⬆️ {{ (inspector.tx / 1024).toFixed(1) }} KB
                    </span>
                  </div>
                  <div class="insp-item action">
                    <button class="btn-ping" @click="testReachability(p)">Test Ping (ICMP)</button>
                  </div>
                </div>
              </div>
            </transition>

            <details class="tech-details">
              <summary>Ver Código y Configuración</summary>
              <div class="code-grid">
                <div class="code-block">
                  <label>Script MikroTik</label>
                  <textarea readonly :value="buildMikrotikCmdFromIni(p.config_data)"></textarea>
                </div>
                <div class="code-block">
                  <label>WireGuard .conf</label>
                  <textarea readonly :value="p.config_data"></textarea>
                </div>
              </div>
            </details>
          </div>
        </li>
      </ul>

      <div v-if="!isLoading && vpnProfiles.length === 0" class="empty-state">
        No hay perfiles VPN creados.
      </div>
    </section>

    <div v-if="notification.show" class="notification" :class="notification.type">
      {{ notification.message }}
    </div>
  </div>
</template>

<style scoped>
/* VARIABLES (Mapeadas a las globales del proyecto) */
:root {
  --bg-color: #121212;
  --surface-color: #1e1e1e;
  --primary-color: #333;
  --blue: #3b82f6;
  --green: #10b981;
  --red: #ef4444;
  --text-main: #eaeaea;
  --text-muted: #888;
}

.page-wrap {
  max-width: 1000px;
  margin: 0 auto;
  color: var(--font-color, #eaeaea);
  padding-bottom: 3rem;
}

.header-section {
  margin-bottom: 2rem;
}
.header-section h1 {
  font-size: 1.8rem;
  margin-bottom: 0.5rem;
}
.header-section p {
  color: var(--gray, #888);
}

/* SECCIONES PRINCIPALES */
.control-section {
  background: var(--surface-color);
  border: 1px solid var(--primary-color);
  border-radius: 12px;
  padding: 1.5rem;
  margin-bottom: 2rem;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 1.5rem;
  border-bottom: 1px solid var(--primary-color);
  padding-bottom: 1rem;
}
.section-title h3 {
  margin: 0;
  font-size: 1.2rem;
}

/* NUEVO: FORMULARIO CREACIÓN RESPONSIVE */
.create-form-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 1.5rem 1rem;
  align-items: end;
}
.form-group {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
.form-group label {
  font-weight: bold;
  font-size: 0.9rem;
  color: var(--gray, #888);
}
.form-group input {
  background: var(--surface-color);
  border: 1px solid var(--primary-color);
  color: white;
  padding: 0.8rem;
  border-radius: 6px;
  width: 100%;
}
.form-group input:focus {
  outline: 1px solid var(--blue, #3b82f6);
  border-color: var(--blue, #3b82f6);
}

/* NUEVO: INPUT SELECT Y TOGGLES */
.input-select {
  background: var(--surface-color);
  border: 1px solid var(--primary-color);
  color: white;
  padding: 0.8rem;
  border-radius: 6px;
  width: 100%;
  cursor: pointer;
}
.input-select option {
  background-color: var(--surface-color);
  color: white;
}
.input-select:focus {
  outline: 1px solid var(--blue, #3b82f6);
  border-color: var(--blue, #3b82f6);
}
.toggle-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  cursor: pointer;
  color: var(--font-color, #eaeaea);
  font-weight: 600;
  font-size: 0.9rem;
}
.toggle-label input[type="checkbox"] {
  width: 18px;
  height: 18px;
  accent-color: var(--blue);
  cursor: pointer;
}
.alert-toggle-group {
  justify-content: flex-end;
}

/* BOTONES */
button {
  cursor: pointer;
  border: none;
  border-radius: 6px;
  font-weight: 600;
  transition: all 0.2s;
}
.btn-primary {
  background-color: var(--blue, #3b82f6);
  color: white;
  padding: 0.8rem 1.5rem;
}
.btn-primary:hover {
  filter: brightness(1.1);
}
.btn-primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.btn-secondary {
  background-color: transparent;
  border: 1px solid var(--primary-color);
  color: var(--font-color, #ccc);
  padding: 0.5rem 1rem;
}
.btn-secondary:hover {
  background-color: var(--primary-color);
  color: white;
}
.btn-monitor {
  background-color: var(--primary-color);
  color: white;
  padding: 0.5rem 1rem;
}
.btn-monitor:hover {
  filter: brightness(1.2);
}
.btn-monitor.is-monitoring {
  background-color: #f59e0b;
  color: black;
}
.btn-danger {
  background-color: transparent;
  border: 1px solid var(--red, #ef4444);
  color: var(--red, #ef4444);
  padding: 0.5rem 1rem;
}
.btn-danger:hover {
  background-color: var(--red, #ef4444);
  color: white;
}
.btn-ping {
  background: transparent;
  color: var(--blue);
  border: 1px dashed var(--primary-color);
  padding: 0.4rem 1rem;
  font-size: 0.85rem;
}
.btn-ping:hover {
  border-color: var(--blue);
  background: rgba(59, 130, 246, 0.1);
}

/* LISTADO DE TARJETAS */
.vpn-list {
  list-style: none;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.vpn-card {
  background-color: var(--bg-color, #121212);
  border: 1px solid var(--primary-color);
  border-radius: 8px;
  overflow: hidden;
  transition: border-color 0.2s;
}
.vpn-card:hover {
  border-color: #555;
}
.vpn-card.is-active {
  border-color: var(--blue);
}

.vpn-header {
  padding: 1rem 1.5rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
  cursor: pointer;
  background-color: var(--surface-color);
}
.vpn-header:hover {
  background-color: rgba(255, 255, 255, 0.03);
}

.header-main {
  display: flex;
  align-items: center;
  gap: 1rem;
}
.status-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background-color: #444;
  transition: background-color 0.3s;
}
.status-dot.online {
  background-color: var(--green, #10b981);
  box-shadow: 0 0 8px var(--green, #10b981);
}
.alert-badge {
  font-size: 0.95rem;
  cursor: help;
  filter: drop-shadow(0 0 4px rgba(255, 255, 255, 0.2));
}

.ip-tag {
  background: var(--bg-color);
  border: 1px solid var(--primary-color);
  font-family: monospace;
  font-size: 0.8rem;
  padding: 2px 8px;
  border-radius: 4px;
  color: var(--gray, #888);
}

.toggle-icon {
  font-size: 0.8rem;
  color: var(--gray, #888);
}

/* CUERPO DE LA TARJETA */
.vpn-body {
  padding: 1.5rem;
  border-top: 1px solid var(--primary-color);
}

.toolbar {
  display: flex;
  justify-content: space-between;
  margin-bottom: 1.5rem;
  flex-wrap: wrap;
  gap: 1rem;
}
.tool-group {
  display: flex;
  gap: 0.5rem;
}

/* NUEVO: SECCIÓN INLINE DE ALERTAS */
.alerts-inline-section {
  background: rgba(255, 255, 255, 0.02);
  border: 1px dashed var(--primary-color);
  border-radius: 8px;
  padding: 1rem 1.5rem;
  margin-bottom: 1.5rem;
}
.alerts-inline-section h4 {
  margin: 0 0 1rem 0;
  font-size: 0.95rem;
  color: var(--blue);
}
.alerts-controls {
  display: flex;
  gap: 1.5rem;
  align-items: center;
  flex-wrap: wrap;
}
.alerts-controls .input-select {
  max-width: 300px;
}

/* INSPECTOR PANEL */
.inspector-panel {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid var(--primary-color);
  border-radius: 8px;
  padding: 1rem;
  margin-bottom: 1.5rem;
}
.inspector-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 1.5rem;
  align-items: center;
}
.insp-item {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}
.insp-item.action {
  align-items: flex-end;
}
.insp-label {
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--gray, #888);
}
.insp-value {
  font-family: monospace;
  font-size: 1rem;
  font-weight: bold;
}
.c-green {
  color: var(--green, #10b981);
}
.c-red {
  color: var(--red, #ef4444);
}
.divider {
  color: var(--primary-color);
  margin: 0 5px;
}

/* DETALLES TÉCNICOS (Code) */
.tech-details summary {
  color: var(--blue);
  cursor: pointer;
  font-size: 0.9rem;
  margin-bottom: 1rem;
  outline: none;
}
.code-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}
.code-block {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
.code-block label {
  font-size: 0.8rem;
  color: var(--gray, #888);
}
textarea {
  background: #0d0d0d;
  border: 1px solid var(--primary-color);
  color: #a3e635; /* Verde consola */
  font-family: 'Consolas', monospace;
  font-size: 0.8rem;
  padding: 1rem;
  border-radius: 6px;
  resize: vertical;
  min-height: 150px;
}

/* UTILIDADES */
.loading-state,
.empty-state {
  text-align: center;
  padding: 3rem;
  color: var(--gray, #888);
  font-style: italic;
}
.spinner {
  display: inline-block;
  width: 12px;
  height: 12px;
  border: 2px solid var(--gray);
  border-top-color: var(--blue);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

/* NOTIFICACION */
.notification {
  position: fixed;
  bottom: 20px;
  right: 20px;
  padding: 1rem 1.5rem;
  border-radius: 8px;
  color: #fff;
  font-weight: bold;
  z-index: 9999;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
}
.notification.success {
  background: var(--green);
}
.notification.error {
  background: var(--red);
}

/* RESPONSIVE */
@media (max-width: 768px) {
  .code-grid {
    grid-template-columns: 1fr;
  }
  .toolbar {
    flex-direction: column;
    align-items: stretch;
  }
  .tool-group {
    justify-content: space-between;
  }
  .alerts-controls select {
    max-width: 100%;
    width: 100%;
  }
}
</style>