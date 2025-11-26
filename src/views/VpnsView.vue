<script setup>
import { ref, onBeforeUnmount, onMounted, watch } from 'vue'
import api from '@/lib/api'
import { addWsListener, connectWebSocketWhenAuthenticated, removeWsListener } from '@/lib/ws'

/* ====== Helpers ====== */
const getAxiosErr = (err) => err?.response?.data?.detail || err?.message || 'Error inesperado.'

function normalizeIni(txt) {
  if (!txt) return ''
  let s = String(txt).replace(/\r\n/g, '\n').trim()
  s = s.replace(/\n{3,}/g, '\n\n')
  return s
}

function isLikelyWgIni(txt) {
  if (!txt) return false
  const s = normalizeIni(txt)
  return (
    /\[Interface\]/i.test(s) &&
    /\[Peer\]/i.test(s) &&
    /PublicKey\s*=/.test(s) &&
    /AllowedIPs\s*=/.test(s) &&
    /Address\s*=/.test(s)
  )
}

function proposeProfileName(iniText) {
  try {
    const addr = (iniText.match(/Address\s*=\s*([^\n\r]+)/i)?.[1] || '').trim()
    const endpoint = (iniText.match(/Endpoint\s*=\s*([^\n\r]+)/i)?.[1] || '').trim()
    if (addr && endpoint) return `${addr.split('/')[0]} @ ${endpoint}`
    if (endpoint) return endpoint
    if (addr) return addr.split('/')[0]
  } catch {
    return ''
  }
  return ''
}

function buildMikrotikCmd(resp) {
  if (Array.isArray(resp?.commands) && resp.commands.length) {
    return resp.commands.join('\n')
  }
  const ep = String(resp?.peer_endpoint || '')
  const [host, portStr] = ep.split(':')
  const port = portStr && /^\d+$/.test(portStr) ? portStr : '51820'
  const addr = resp?.interface_address || ''
  const allowed = resp?.peer_allowed_ips || '0.0.0.0/0'
  const srvPub = resp?.peer_public_key || ''
  const clientPriv = resp?.client_private_key || ''
  return [
    '# --- Configuración sugerida para el cliente MikroTik ---',
    `/interface/wireguard add name=wg-m360 comment="Monitor360 VPN (auto)" private-key="${clientPriv}"`,
    `/ip/address add address=${addr} interface=wg-m360`,
    `/interface/wireguard/peers add interface=wg-m360 public-key="${srvPub}" endpoint-address=${host} endpoint-port=${port} persistent-keepalive=25 allowed-address=${allowed}`,
  ].join('\n')
}

async function copyToClipboard(text) {
  await navigator.clipboard.writeText(text)
}

/* ====== Estado UI ====== */
const newProfile = ref({ name: '', check_ip: '', config_data: '' })
const vpnProfiles = ref([])
const isLoading = ref(false)
const isSaving = ref(false)
const isGenerating = ref(false)
const autoGen = ref(null)
const showConfig = ref(false)

const autoBoxOpen = ref(true)

/* ====== Verificación de handshake (Polling) ====== */
const verify = ref({
  running: false,
  connected: false,
  lastHandshake: null,
  rx: 0,
  tx: 0,
  tries: 0,
  error: '',
})
let verifyTimer = null

function stopVerifyPolling() {
  if (verifyTimer) {
    clearInterval(verifyTimer)
    verifyTimer = null
  }
  verify.value.running = false
}

function formatAgoFromSeconds(sec) {
  if (sec == null || isNaN(sec)) return null
  const h = Math.floor(sec / 3600)
    .toString()
    .padStart(2, '0')
  const m = Math.floor((sec % 3600) / 60)
    .toString()
    .padStart(2, '0')
  const s = Math.floor(sec % 60)
    .toString()
    .padStart(2, '0')
  return `hace ${h}:${m}:${s}`
}

async function fetchPeerStatus(pubKey) {
  try {
    const { data } = await api.get('/vpns/peer-status', { params: { pub: pubKey } })
    return data
  } catch (e) {
    console.error('Error en fetchPeerStatus:', e)
    throw new Error(e?.response?.data?.detail || e?.message || 'Error al obtener estado.')
  }
}

async function pollStatusOnce() {
  if (!autoGen.value?.client_public_key) return
  try {
    const data = await fetchPeerStatus(autoGen.value.client_public_key)
    let rx = Number(data?.rx_bytes || 0)
    let tx = Number(data?.tx_bytes || 0)
    let connectedFlag = !!data?.connected
    let ageSeconds = null
    const hs = data?.latest_handshake
    if (typeof hs === 'number') {
      if (hs > 0) {
        const nowSec = Math.floor(Date.now() / 1000)
        ageSeconds = Math.max(0, nowSec - hs)
      }
    } else if (typeof hs === 'string' && hs) {
      const t = Date.parse(hs)
      if (!isNaN(t)) ageSeconds = Math.max(0, Math.floor((Date.now() - t) / 1000))
    }
    const recentHandshake = ageSeconds != null && ageSeconds <= 180
    const hasTraffic = rx + tx > 0
    verify.value.connected = connectedFlag || recentHandshake || hasTraffic
    verify.value.lastHandshake = ageSeconds != null ? formatAgoFromSeconds(ageSeconds) : '—'
    verify.value.rx = rx
    verify.value.tx = tx
    verify.value.error = ''
  } catch (e) {
    verify.value.error = getAxiosErr(e)
  } finally {
    verify.value.tries += 1
    if (verify.value.tries >= 40 && !verify.value.connected) {
      stopVerifyPolling()
    }
  }
}

function startVerifyPolling() {
  if (!autoGen.value?.client_public_key || verify.value.running) return
  verify.value.running = true
  verify.value.connected = false
  verify.value.lastHandshake = null
  verify.value.rx = 0
  verify.value.tx = 0
  verify.value.tries = 0
  verify.value.error = ''
  pollStatusOnce()
  verifyTimer = setInterval(pollStatusOnce, 2500)
}

/* ====== WS / Lifecycle ====== */
let wsUnsubRot = null
onBeforeUnmount(() => {
  stopVerifyPolling()
  window.removeEventListener('beforeunload', onBeforeUnload)
  if (wsUnsubRot) removeWsListener(wsUnsubRot)
})
function onBeforeUnload() {}
window.addEventListener('beforeunload', onBeforeUnload)

/* ====== Notificaciones ====== */
const notification = ref({ show: false, message: '', type: 'success' })
function showNotification(message, type = 'success') {
  notification.value = { show: true, message, type }
  setTimeout(() => (notification.value.show = false), 4000)
}

/* ====== Lógica Principal ====== */
async function generateAutoConfig() {
  if (isGenerating.value) return
  isGenerating.value = true
  try {
    const payload = { interface: 'm360-srv0' }
    const { data } = await api.post('/vpns/mikrotik-auto', payload)

    autoGen.value = {
      ...data,
      mikrotik_cmd:
        Array.isArray(data?.commands) && data.commands.length
          ? data.commands.join('\n')
          : buildMikrotikCmd(data),
      last_auth_ok: data.last_auth_ok || null,
      last_auth_fail: data.last_auth_fail || null,
      rotations_count: data.rotations_count || 0,
    }

    const confIni = normalizeIni(data?.conf_ini || '')
    if (confIni) {
      newProfile.value.config_data = confIni
      if (!newProfile.value.name.trim()) {
        const suggested = proposeProfileName(confIni)
        if (suggested) newProfile.value.name = suggested.slice(0, 80)
      }
    }

    autoBoxOpen.value = true
    showConfig.value = false
    showNotification('Configuración generada correctamente.', 'success')

    stopVerifyPolling()
    startVerifyPolling()
  } catch (err) {
    console.error(err)
    showNotification(getAxiosErr(err), 'error')
  } finally {
    isGenerating.value = false
  }
}

// --- NUEVO: Función para descargar .conf ---
function downloadClientConf() {
  const content = newProfile.value.config_data
  if (!content) return showNotification('No hay configuración para descargar.', 'error')

  const name = (newProfile.value.name || 'wireguard-client').replace(/\s+/g, '_')
  const filename = `${name}.conf`

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

async function fetchVpnProfiles() {
  isLoading.value = true
  try {
    const { data } = await api.get('/vpns')
    vpnProfiles.value = (data || []).map((p) => ({
      ...p,
      is_default: !!p.is_default,
      _expanded: false,
      _saving: false,
    }))
  } catch (err) {
    showNotification(getAxiosErr(err), 'error')
  } finally {
    isLoading.value = false
  }
}

async function createProfile() {
  if (!newProfile.value.name.trim()) return showNotification('Falta el nombre.', 'error')
  if (!isLikelyWgIni(newProfile.value.config_data))
    return showNotification('Falta la configuración válida.', 'error')

  if (isSaving.value) return
  isSaving.value = true
  try {
    const body = {
      name: newProfile.value.name.trim(),
      config_data: normalizeIni(newProfile.value.config_data),
      check_ip: newProfile.value.check_ip.trim(),
    }
    const { data } = await api.post('/vpns', body)
    vpnProfiles.value.unshift({
      ...data,
      is_default: !!data.is_default,
      _expanded: false,
      _saving: false,
    })
    newProfile.value = { name: '', check_ip: '', config_data: '' }
    autoGen.value = null
    showConfig.value = false
    stopVerifyPolling()
    showNotification('Perfil VPN creado.', 'success')
  } catch (err) {
    showNotification(getAxiosErr(err), 'error')
  } finally {
    isSaving.value = false
  }
}

async function saveProfile(profile) {
  if (profile._saving) return
  if (!isLikelyWgIni(profile.config_data)) return showNotification('Config inválida.', 'error')
  profile._saving = true
  try {
    await api.put(`/vpns/${profile.id}`, {
      name: profile.name,
      check_ip: profile.check_ip,
      config_data: normalizeIni(profile.config_data),
    })
    showNotification('Actualizado.', 'success')
    await fetchVpnProfiles()
  } catch (err) {
    showNotification(getAxiosErr(err), 'error')
  } finally {
    profile._saving = false
  }
}

async function setDefault(profile) {
  if (profile._saving) return
  profile._saving = true
  try {
    await api.put(`/vpns/${profile.id}`, { is_default: true })
    await fetchVpnProfiles()
    showNotification('Marcado como default.', 'success')
  } catch (err) {
    showNotification(getAxiosErr(err), 'error')
  } finally {
    profile._saving = false
  }
}

async function testProfile(profile) {
  if (!profile.check_ip?.trim()) return showNotification('Falta check_ip.', 'error')
  try {
    const { data } = await api.post('/devices/test_reachability', {
      ip_address: profile.check_ip.trim(),
      vpn_profile_id: profile.id,
    })
    if (data.reachable) showNotification(`OK. Alcanzable (${profile.check_ip}).`, 'success')
    else showNotification(data.detail || 'No alcanzable.', 'error')
  } catch (err) {
    showNotification(`Error: ${getAxiosErr(err)}`, 'error')
  }
}

async function deleteProfile(profile) {
  if (!confirm(`¿Eliminar "${profile.name}"?`)) return
  try {
    await api.delete(`/vpns/${profile.id}`)
    vpnProfiles.value = vpnProfiles.value.filter((p) => p.id !== profile.id)
    showNotification('Eliminado.', 'success')
  } catch (err) {
    showNotification(getAxiosErr(err), 'error')
  }
}

async function copyMikrotikScript() {
  try {
    if (!autoGen.value?.mikrotik_cmd) throw new Error('Nada para copiar.')
    await copyToClipboard(autoGen.value.mikrotik_cmd)
    showNotification('Copiado.', 'success')
  } catch (e) {
    // FIX ESLINT: Usamos 'e' para mostrar el error
    showNotification(getAxiosErr(e), 'error')
  }
}

onMounted(async () => {
  await fetchVpnProfiles()
  watch(
    () => newProfile.value.config_data,
    (val, old) => {
      if (!old && val && !newProfile.value.name.trim() && isLikelyWgIni(val)) {
        const suggested = proposeProfileName(val)
        if (suggested) newProfile.value.name = suggested.slice(0, 80)
      }
    },
    { flush: 'post' },
  )

  try {
    await connectWebSocketWhenAuthenticated()
    wsUnsubRot = addWsListener((msg) => {
      if (msg?.type === 'device_credential_rotated' && autoGen.value) {
        if (!msg.device_id || msg.device_id === autoGen.value.device_id) {
          autoGen.value.rotations_count = (autoGen.value.rotations_count ?? 0) + 1
          msg.ok ? (autoGen.value.last_auth_ok = msg.ts) : (autoGen.value.last_auth_fail = msg.ts)
        }
      }
    })
  } catch (e) {
    void e
  }
})
</script>

<template>
  <div class="page-wrap">
    <h1>Perfiles VPN</h1>

    <section class="control-section">
      <h2><i class="icon">➕</i> Nuevo Perfil</h2>
      <div class="grid-2">
        <div>
          <label>Nombre</label>
          <input v-model="newProfile.name" type="text" placeholder="Ej: Cliente Juan Perez" />
        </div>
        <div>
          <label>Check IP (opcional)</label>
          <input v-model="newProfile.check_ip" type="text" placeholder="Ej: 192.168.88.1" />
        </div>
      </div>

      <div class="stack">
        <div class="config-actions">
          <button
            @click="generateAutoConfig"
            class="btn-qr-scan full-width"
            :disabled="isGenerating"
          >
            <i class="icon">⚡</i>
            {{ isGenerating ? 'Generando...' : 'Generar Configuración Automática' }}
          </button>

          <div class="config-status">
            <div v-if="newProfile.config_data" class="status-group">
              <div v-if="!showConfig" class="status-ok">✅ Configuración lista</div>
              <button
                type="button"
                class="btn-download-link"
                @click="downloadClientConf"
                title="Descargar archivo .conf para clientes"
              >
                ⬇️ Descargar archivo .conf
              </button>
            </div>

            <a href="#" @click.prevent="showConfig = !showConfig" class="link-toggle">
              {{
                showConfig
                  ? 'Ocultar configuración manual'
                  : newProfile.config_data
                    ? 'Ver configuración técnica'
                    : 'Editar configuración manualmente'
              }}
            </a>
          </div>
        </div>

        <transition name="fade">
          <div v-if="showConfig">
            <label>Configuración WireGuard (INI)</label>
            <textarea
              v-model="newProfile.config_data"
              rows="10"
              spellcheck="false"
              class="code-input"
              placeholder="[Interface]..."
            />
          </div>
        </transition>

        <div v-if="autoGen" class="auto-box">
          <div class="auto-box-header" @click="autoBoxOpen = !autoBoxOpen">
            <div class="status-chip" :class="verify.connected ? 'ok' : 'warn'">
              <span class="dot"></span>
              {{ verify.connected ? 'Conectado' : 'Esperando conexión...' }}
            </div>
            <div class="grow"></div>
            <button class="btn-toggle-text" type="button">
              {{ autoBoxOpen ? 'Ocultar Detalles' : 'Mostrar Detalles' }}
            </button>
          </div>

          <transition name="fade">
            <div v-if="autoBoxOpen" class="auto-inner">
              <div class="auto-grid">
                <div><strong>IP Túnel:</strong> {{ autoGen.interface_address }}</div>
                <div><strong>Endpoint:</strong> {{ autoGen.peer_endpoint }}</div>
              </div>

              <div class="stack">
                <label>Script de Instalación (MikroTik)</label>
                <div class="code-container">
                  <pre class="code-block">{{ autoGen.mikrotik_cmd }}</pre>
                  <button class="btn-copy" @click="copyMikrotikScript" title="Copiar">📋</button>
                </div>

                <div class="actions-row centered">
                  <button
                    v-if="!verify.running"
                    class="btn-secondary small"
                    @click="startVerifyPolling"
                  >
                    Re-verificar estado
                  </button>
                  <span v-else class="loading-dots">Verificando</span>
                </div>
              </div>
            </div>
          </transition>
        </div>
      </div>

      <div class="actions-row end">
        <button
          class="btn-primary big"
          :disabled="!newProfile.name.trim() || !isLikelyWgIni(newProfile.config_data) || isSaving"
          @click="createProfile"
        >
          {{ isSaving ? 'Guardando...' : 'Guardar Perfil' }}
        </button>
      </div>
    </section>

    <section class="control-section">
      <h2><i class="icon">🗂️</i> Perfiles</h2>
      <div v-if="isLoading" class="loading-text">Cargando...</div>
      <div v-else-if="!vpnProfiles.length" class="empty">No hay perfiles creados.</div>

      <ul v-else class="vpn-list">
        <li v-for="p in vpnProfiles" :key="p.id" class="vpn-card">
          <div class="vpn-header" @click="p._expanded = !p._expanded">
            <div class="title">
              <span class="name">{{ p.name }}</span>
              <span v-if="p.is_default" class="badge-default">Default</span>
            </div>
            <button class="btn-toggle-text" type="button">
              {{ p._expanded ? 'Ocultar' : 'Ver' }}
            </button>
          </div>

          <div v-if="p._expanded" class="vpn-body">
            <div class="grid-2">
              <div>
                <label>Nombre</label>
                <input v-model="p.name" type="text" />
              </div>
              <div>
                <label>Check IP</label>
                <input v-model="p.check_ip" type="text" />
              </div>
            </div>

            <div class="actions-row">
              <button class="btn-primary" :disabled="p._saving" @click.stop="saveProfile(p)">
                Guardar
              </button>
              <button class="btn-secondary" :disabled="p._saving" @click.stop="testProfile(p)">
                Probar Túnel
              </button>
              <button class="btn-danger" :disabled="p._saving" @click.stop="deleteProfile(p)">
                Eliminar
              </button>
              <button
                class="btn-default"
                v-if="!p.is_default"
                :disabled="p._saving"
                @click.stop="setDefault(p)"
              >
                Hacer Default
              </button>
            </div>
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
  --bg-color: #121212;
  --panel: #1b1b1b;
  --font-color: #eaeaea;
  --primary-color: #3b82f6;
  --green: #10b981;
  --border: #333;
}

.page-wrap {
  color: var(--font-color);
  max-width: 800px;
  margin: 0 auto;
}
.control-section {
  background: var(--panel);
  padding: 1.5rem;
  border-radius: 12px;
  margin-bottom: 1.5rem;
  border: 1px solid var(--border);
}
.stack {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  margin-top: 1rem;
}
.grid-2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}

.full-width {
  width: 100%;
  justify-content: center;
  padding: 0.8rem;
  font-size: 1rem;
  background: #2563eb;
  border: none;
}
.full-width:hover {
  background: #1d4ed8;
}

/* Barra de estado de configuración */
.config-status {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  align-items: center;
  font-size: 0.9rem;
  margin-top: 0.5rem;
  gap: 1rem;
}
.status-group {
  display: flex;
  align-items: center;
  gap: 1rem;
}
.status-ok {
  color: var(--green);
  font-weight: 600;
}

/* Botón de descarga estilo enlace pero destacado */
.btn-download-link {
  background: transparent;
  border: 1px solid #444;
  color: #ddd;
  padding: 0.3rem 0.8rem;
  border-radius: 4px;
  font-size: 0.85rem;
  cursor: pointer;
  transition: all 0.2s;
}
.btn-download-link:hover {
  background: #333;
  color: white;
  border-color: #666;
}

.link-toggle {
  color: #60a5fa;
  text-decoration: none;
  font-size: 0.85rem;
  border-bottom: 1px dashed #60a5fa;
}
.link-toggle:hover {
  color: #93c5fd;
  border-bottom-style: solid;
}

.code-input {
  font-family: monospace;
  font-size: 0.85rem;
  background: #000;
  border: 1px solid #444;
  color: #ccc;
}

.code-container {
  position: relative;
}
.code-block {
  background: #050505;
  padding: 1rem;
  border-radius: 6px;
  border: 1px solid #333;
  color: #a3e635;
  font-size: 0.85rem;
  overflow-x: auto;
}
.btn-copy {
  position: absolute;
  top: 8px;
  right: 8px;
  background: rgba(255, 255, 255, 0.1);
  border: none;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 4px;
}
.btn-copy:hover {
  background: rgba(255, 255, 255, 0.2);
}

/* Toggle Button Text */
.btn-toggle-text {
  background: transparent;
  border: none;
  color: #888;
  font-size: 0.85rem;
  cursor: pointer;
  font-weight: 600;
}
.btn-toggle-text:hover {
  color: #bbb;
}

.actions-row.end {
  margin-top: 1.5rem;
  justify-content: flex-end;
  display: flex;
}
.btn-primary.big {
  padding: 0.8rem 2rem;
  font-size: 1rem;
  font-weight: bold;
}

.fade-enter-active,
.fade-leave-active {
  transition: all 0.2s ease;
  max-height: 500px;
  opacity: 1;
}
.fade-enter-from,
.fade-leave-to {
  max-height: 0;
  opacity: 0;
  overflow: hidden;
}

input {
  width: 100%;
  background: #262626;
  border: 1px solid #404040;
  color: white;
  padding: 0.7rem;
  border-radius: 6px;
}
input:focus {
  outline: 2px solid var(--primary-color);
  border-color: transparent;
}

button {
  cursor: pointer;
  border-radius: 6px;
  color: white;
  transition: background 0.2s;
}
.btn-primary {
  background: var(--green);
  border: none;
  padding: 0.6rem 1rem;
}
.btn-primary:hover {
  background: #059669;
}
.btn-secondary {
  background: transparent;
  border: 1px solid #555;
  color: #ddd;
  padding: 0.5rem 1rem;
}
.btn-secondary:hover {
  background: #333;
}
.btn-danger {
  background: #ef4444;
  border: none;
  padding: 0.5rem 1rem;
}
.btn-default {
  background: #4b5563;
  border: none;
  padding: 0.5rem 1rem;
}

.vpn-list {
  list-style: none;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
.vpn-card {
  background: #262626;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid #333;
}
.vpn-header {
  padding: 1rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
  cursor: pointer;
  background: #2a2a2a;
}
.vpn-header:hover {
  background: #333;
}
.vpn-body {
  padding: 1.5rem;
  border-top: 1px solid #333;
  background: #202020;
}
.badge-default {
  background: #f59e0b;
  color: black;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 0.7rem;
  font-weight: bold;
  margin-left: 0.5rem;
}

.notification {
  position: fixed;
  bottom: 20px;
  right: 20px;
  padding: 1rem;
  border-radius: 8px;
  color: white;
  font-weight: bold;
  z-index: 9999;
}
.notification.success {
  background: var(--green);
}
.notification.error {
  background: #ef4444;
}
</style>
