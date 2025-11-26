<script setup>
import { ref, onBeforeUnmount, onMounted } from 'vue'
import api from '@/lib/api'
import { addWsListener, connectWebSocketWhenAuthenticated, removeWsListener } from '@/lib/ws'

/* ====== Helpers ====== */
const getAxiosErr = (err) => err?.response?.data?.detail || err?.message || 'Error inesperado.'

// Parsea el INI para extraer datos clave (endpoint, keys) y armar el script de MikroTik en el frontend
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
    if (line.startsWith('[')) {
      section = line.toLowerCase()
    } else if (line.includes('=')) {
      let [k, v] = line.split('=', 2)
      k = k.trim().toLowerCase()
      v = v.trim()

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

function buildMikrotikCmdFromIni(iniText, clientPrivKeyOverride = null) {
  const conf = parseWgIni(iniText)
  if (!conf.address || !conf.serverPublicKey || !conf.endpoint) return ''

  const privKey = clientPrivKeyOverride || conf.privateKey
  const [host, port] = conf.endpoint.split(':')

  return [
    '# --- Configuración para MikroTik ---',
    `/interface/wireguard add name=wg-m360 comment="Monitor360 VPN" private-key="${privKey}"`,
    `/ip/address add address=${conf.address} interface=wg-m360`,
    `/interface/wireguard/peers add interface=wg-m360 public-key="${conf.serverPublicKey}" endpoint-address=${host} endpoint-port=${port || 51820} allowed-address=${conf.allowedIps || '0.0.0.0/0'} persistent-keepalive=25`,
  ].join('\n')
}

async function copyToClipboard(text) {
  await navigator.clipboard.writeText(text)
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
const newProfile = ref({ name: '', check_ip: '' })
const vpnProfiles = ref([])
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
    // 1. Dry Run: obtener configuración sugerida
    const { data: autoData } = await api.post('/vpns/mikrotik-auto', { interface: 'm360-srv0' })

    // 2. Crear Real: guardar en BD y activar en WG
    const payload = {
      name: newProfile.value.name,
      check_ip: newProfile.value.check_ip || autoData.interface_address?.split('/')[0],
      config_data: autoData.conf_ini,
    }

    const { data: savedProfile } = await api.post('/vpns', payload)

    // 3. Actualizar UI
    vpnProfiles.value.unshift({ ...savedProfile, _expanded: true })
    newProfile.value = { name: '', check_ip: '' }
    showNotification('Perfil creado y activado.', 'success')
  } catch (err) {
    showNotification(getAxiosErr(err), 'error')
  } finally {
    isCreating.value = false
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

// Notificaciones
const notification = ref({ show: false, message: '', type: '' })
function showNotification(msg, type = 'success') {
  notification.value = { show: true, message: msg, type }
  setTimeout(() => (notification.value.show = false), 4000)
}

onMounted(fetchVpnProfiles)
onBeforeUnmount(stopInspector)
</script>

<template>
  <div class="page-wrap">
    <h1>Gestión VPN</h1>

    <section class="control-section">
      <h2><i class="icon">🚀</i> Nuevo Cliente</h2>
      <div class="grid-2">
        <div>
          <label>Nombre del Cliente / Sitio</label>
          <input v-model="newProfile.name" type="text" placeholder="Ej: Sucursal Centro" />
        </div>
        <div>
          <label>Check IP (Opcional)</label>
          <input
            v-model="newProfile.check_ip"
            type="text"
            placeholder="IP interna para monitoreo"
          />
        </div>
      </div>
      <div class="actions-row end mt-4">
        <button class="btn-primary big" @click="createAutoProfile" :disabled="isCreating">
          {{ isCreating ? 'Generando...' : '✨ Crear Perfil Automático' }}
        </button>
      </div>
    </section>

    <section class="control-section">
      <h2><i class="icon">Vg</i> Perfiles Activos</h2>
      <div v-if="isLoading" class="loading-text">Cargando...</div>

      <ul class="vpn-list">
        <li v-for="p in vpnProfiles" :key="p.id" class="vpn-card">
          <div class="vpn-header" @click="p._expanded = !p._expanded">
            <div class="header-info">
              <strong>{{ p.name }}</strong>
              <span class="ip-tag" v-if="p.check_ip">{{ p.check_ip }}</span>
            </div>
            <div
              v-if="inspector.activeProfileId === p.id"
              class="mini-status"
              :class="inspector.connected ? 'ok' : 'bad'"
            >
              {{ inspector.connected ? 'Online' : '...' }}
            </div>
            <button class="btn-toggle-text">{{ p._expanded ? 'Ocultar' : 'Ver Detalles' }}</button>
          </div>

          <div v-if="p._expanded" class="vpn-body">
            <div class="panel-controls">
              <button class="btn-secondary" @click="downloadConfFile(p.name, p.config_data)">
                ⬇️ Bajar .conf (PC/Móvil)
              </button>
              <button
                class="btn-secondary"
                @click="copyToClipboard(buildMikrotikCmdFromIni(p.config_data))"
              >
                📋 Copiar Script MikroTik
              </button>
              <button class="btn-default" @click="checkStatus(p)">
                {{
                  inspector.activeProfileId === p.id && inspector.running
                    ? '⏹ Detener Monitor'
                    : '📡 Verificar Estado'
                }}
              </button>
              <div class="grow"></div>
              <button class="btn-danger small" @click="deleteProfile(p)">🗑️ Eliminar</button>
            </div>

            <transition name="fade">
              <div v-if="inspector.activeProfileId === p.id" class="status-box">
                <div class="stat">
                  <span class="label">Estado:</span>
                  <span class="val" :class="inspector.connected ? 'c-green' : 'c-red'">
                    {{ inspector.connected ? 'CONECTADO' : 'BUSCANDO...' }}
                  </span>
                </div>
                <div class="stat">
                  <span class="label">Último Handshake:</span>
                  <span class="val">{{ inspector.lastHandshake || '--' }}</span>
                </div>
                <div class="stat">
                  <span class="label">Tráfico:</span>
                  <span class="val"
                    >⬇️ {{ (inspector.rx / 1024).toFixed(1) }}KB ⬆️
                    {{ (inspector.tx / 1024).toFixed(1) }}KB</span
                  >
                </div>
                <div class="stat" style="align-self: center">
                  <button class="btn-text" @click="testReachability(p)">Ping Check IP</button>
                </div>
              </div>
            </transition>
          </div>
        </li>
      </ul>
    </section>

    <div v-if="notification.show" class="notification" :class="notification.type">
      {{ notification.message }}
    </div>
  </div>
</template>

<style scoped>
:root {
  --panel: #1b1b1b;
  --bg: #121212;
  --text: #eaeaea;
  --green: #10b981;
  --red: #ef4444;
  --blue: #3b82f6;
}
.page-wrap {
  max-width: 900px;
  margin: 0 auto;
  color: var(--text);
}
.control-section {
  background: var(--panel);
  border: 1px solid #333;
  border-radius: 12px;
  padding: 1.5rem;
  margin-bottom: 1.5rem;
}
.grid-2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}
.mt-4 {
  margin-top: 1rem;
}

input,
textarea {
  width: 100%;
  background: #000;
  border: 1px solid #444;
  color: #fff;
  padding: 0.7rem;
  border-radius: 6px;
}
input:focus {
  outline: 2px solid var(--blue);
  border-color: transparent;
}

button {
  cursor: pointer;
  padding: 0.6rem 1rem;
  border-radius: 6px;
  border: none;
  font-weight: 600;
  color: #fff;
  transition: opacity 0.2s;
  font-size: 0.9rem;
}
button:hover {
  opacity: 0.9;
}
.btn-primary {
  background: var(--blue);
}
.btn-primary.big {
  width: 100%;
  padding: 0.8rem;
  font-size: 1rem;
}
.btn-secondary {
  background: #333;
  border: 1px solid #555;
  color: #ddd;
}
.btn-secondary:hover {
  background: #444;
}
.btn-default {
  background: #4b5563;
}
.btn-danger {
  background: var(--red);
}
.btn-text {
  background: none;
  color: var(--blue);
  text-decoration: underline;
  padding: 0;
}
.btn-toggle-text {
  background: transparent;
  color: #888;
  font-size: 0.85rem;
}
.btn-toggle-text:hover {
  color: #bbb;
}

.vpn-list {
  list-style: none;
  padding: 0;
}
.vpn-card {
  background: #222;
  border: 1px solid #333;
  border-radius: 8px;
  margin-bottom: 0.8rem;
  overflow: hidden;
}
.vpn-header {
  padding: 1rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  cursor: pointer;
  background: #2a2a2a;
}
.vpn-header:hover {
  background: #333;
}
.header-info {
  display: flex;
  align-items: center;
  gap: 12px;
}
.ip-tag {
  background: #444;
  font-size: 0.75rem;
  padding: 2px 8px;
  border-radius: 4px;
  color: #ccc;
  font-family: monospace;
}
.vpn-body {
  padding: 1.5rem;
  border-top: 1px solid #333;
  background: #202020;
}

.panel-controls {
  display: flex;
  gap: 0.8rem;
  flex-wrap: wrap;
  margin-bottom: 1.5rem;
  align-items: center;
}
.grow {
  flex: 1;
}

.status-box {
  background: #151515;
  padding: 1rem;
  border-radius: 8px;
  border: 1px solid #333;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 1.5rem;
}
.stat {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}
.stat .label {
  font-size: 0.75rem;
  color: #888;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.stat .val {
  font-weight: bold;
  font-size: 0.95rem;
  font-family: monospace;
}
.c-green {
  color: var(--green);
}
.c-red {
  color: var(--red);
}

.mini-status {
  font-size: 0.75rem;
  font-weight: bold;
  padding: 2px 6px;
  border-radius: 4px;
}
.mini-status.ok {
  color: var(--green);
  background: rgba(16, 185, 129, 0.1);
}
.mini-status.bad {
  color: #888;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.loading-text,
.empty {
  color: #777;
  text-align: center;
  padding: 1rem;
}

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
</style>
