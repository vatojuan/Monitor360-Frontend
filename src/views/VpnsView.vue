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

/* Si por alguna razón el backend no devolviese `commands`, armamos un fallback. */
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
  // No deberíamos llegar acá si el backend ya arma commands con la private-key.
  const clientPriv = resp?.client_private_key || ''
  return [
    '# --- Configuración sugerida para el cliente MikroTik ---',
    '# Paso 1: crear interfaz WireGuard con la clave privada provista',
    `/interface/wireguard add name=wg-m360 comment="Monitor360 VPN (auto)" private-key="${clientPriv}"`,
    '# Paso 2: asignar IP a la interfaz (¡importante!)',
    `/ip/address add address=${addr} interface=wg-m360`,
    '# Paso 3: añadir peer del servidor',
    `/interface/wireguard/peers add interface=wg-m360 public-key="${srvPub}" endpoint-address=${host} endpoint-port=${port} persistent-keepalive=25 allowed-address=${allowed}`,
    '# (Opcional) Enrutar todo por el túnel:',
    '# /ip/route add dst-address=0.0.0.0/0 gateway=wg-m360 distance=1',
    '# (Opcional) DNS para clientes detrás del MikroTik:',
    '# /ip/dns set servers=1.1.1.1',
  ].join('\n')
}

async function copyToClipboard(text) {
  await navigator.clipboard.writeText(text)
}

/* ====== Formulario / listado ====== */
const newProfile = ref({ name: '', check_ip: '', config_data: '' })
const vpnProfiles = ref([])
const isLoading = ref(false)
const isSaving = ref(false)

/* ====== Auto-generado backend (solo comandos) ====== */
const isGenerating = ref(false)
const autoGen = ref(null)

/* ====== Verificación de handshake ====== */
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

/* pretty "hace HH:MM:SS" */
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
    throw new Error(e?.response?.data?.detail || e?.message || 'Error al obtener estado del peer.')
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
      } else {
        ageSeconds = null
      }
    } else if (typeof hs === 'string' && hs) {
      const t = Date.parse(hs)
      if (!isNaN(t)) ageSeconds = Math.max(0, Math.floor((Date.now() - t) / 1000))
    }

    const recentHandshake = ageSeconds != null && ageSeconds <= 180
    const hasTraffic = rx + tx > 0
    const connected = connectedFlag || recentHandshake || hasTraffic

    verify.value.connected = connected
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

/* ====== WS para rotaciones ====== */
let wsUnsubRot = null

onBeforeUnmount(() => {
  document.removeEventListener('visibilitychange', onVisibilityChange)
  stopVerifyPolling()
  window.removeEventListener('beforeunload', onBeforeUnload)
  if (wsUnsubRot) {
    try {
      removeWsListener(wsUnsubRot)
    } catch (e) {
      void e
    }
    wsUnsubRot = null
  }
})
function onBeforeUnload() {
  /* noop: ya no dejamos cámara/QR ni streams abiertos */
}
window.addEventListener('beforeunload', onBeforeUnload)
function onVisibilityChange() {
  /* noop: ya no hay scanner que pausar/reanudar */
}

/* ====== Notificaciones ====== */
const notification = ref({ show: false, message: '', type: 'success' })
function showNotification(message, type = 'success') {
  notification.value = { show: true, message, type }
  setTimeout(() => (notification.value.show = false), 4000)
}

/* ====== Auto config (SOLO COMANDOS) ====== */
const autoBoxOpen = ref(true)

async function generateAutoConfig() {
  if (isGenerating.value) return
  isGenerating.value = true
  try {
    // Podés dejar {} (usa defaults), pero envío interface explícita para mayor claridad:
    const payload = { interface: 'm360-srv0' }
    const { data } = await api.post('/vpns/mikrotik-auto', payload)

    // 1) Guardamos todo lo que viene del backend (commands + conf_ini + metadatos)
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

    // 2) Rellenar el textarea "Config WireGuard *" con el .ini devuelto
    const confIni = normalizeIni(data?.conf_ini || '')
    if (confIni) {
      newProfile.value.config_data = confIni

      // 3) Si el nombre aún está vacío, sugerir uno a partir de Address/Endpoint
      if (!newProfile.value.name.trim()) {
        const suggested = proposeProfileName(confIni)
        if (suggested) newProfile.value.name = suggested.slice(0, 80)
      }
    }

    autoBoxOpen.value = true
    showNotification('Comandos y .ini generados automáticamente.', 'success')

    // 4) Arrancar el polling de estado (usa client_public_key)
    stopVerifyPolling()
    startVerifyPolling()
  } catch (err) {
    console.error(err)
    showNotification(getAxiosErr(err), 'error')
  } finally {
    isGenerating.value = false
  }
}

/* ====== CRUD perfiles (se mantienen igual) ====== */
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
    console.error('Error al cargar perfiles VPN:', err)
    showNotification(getAxiosErr(err) || 'Error al cargar perfiles VPN.', 'error')
  } finally {
    isLoading.value = false
  }
}

function canCreate() {
  return newProfile.value.name.trim() && isLikelyWgIni(newProfile.value.config_data)
}

async function createProfile() {
  if (!canCreate())
    return showNotification('Nombre y Config válidas (con Address=) son obligatorios.', 'error')
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
    stopVerifyPolling()
    showNotification('Perfil VPN creado.', 'success')
  } catch (err) {
    console.error('Error al crear perfil:', err)
    showNotification(getAxiosErr(err) || 'Error al crear perfil.', 'error')
  } finally {
    isSaving.value = false
  }
}

async function saveProfile(profile) {
  if (profile._saving) return
  if (!isLikelyWgIni(profile.config_data)) {
    return showNotification(
      'La config no es válida (revisá Address/Peer/PublicKey/AllowedIPs).',
      'error',
    )
  }
  profile._saving = true
  try {
    const payload = {
      name: profile.name,
      check_ip: profile.check_ip,
      config_data: normalizeIni(profile.config_data),
    }
    await api.put(`/vpns/${profile.id}`, payload)
    showNotification('Perfil actualizado.', 'success')
    await fetchVpnProfiles()
  } catch (err) {
    console.error('Error al actualizar perfil:', err)
    showNotification(getAxiosErr(err) || 'Error al actualizar perfil.', 'error')
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
    showNotification(`"${profile.name}" ahora es el default.`, 'success')
  } catch (err) {
    console.error('Error al marcar default:', err)
    showNotification(getAxiosErr(err) || 'No se pudo marcar como default.', 'error')
  } finally {
    profile._saving = false
  }
}

async function testProfile(profile) {
  if (!profile.check_ip?.trim()) {
    showNotification('Configurar "check_ip" primero para probar el túnel.', 'error')
    return
  }
  try {
    const payload = { ip_address: profile.check_ip.trim(), vpn_profile_id: profile.id }
    const { data } = await api.post('/devices/test_reachability', payload)
    if (data.reachable) showNotification(`Túnel OK. Alcanzable (${profile.check_ip}).`, 'success')
    else showNotification(data.detail || 'No alcanzable a través del túnel.', 'error')
  } catch (err) {
    const status = err?.response?.status
    const detail = getAxiosErr(err)
    showNotification(`Error (${status}): ${detail}`, 'error')
  }
}

async function deleteProfile(profile) {
  if (!confirm(`¿Eliminar el perfil "${profile.name}"?`)) return
  try {
    await api.delete(`/vpns/${profile.id}`)
    vpnProfiles.value = vpnProfiles.value.filter((p) => p.id !== profile.id)
    showNotification('Perfil eliminado.', 'success')
  } catch (err) {
    console.error('Error al eliminar perfil:', err)
    showNotification(getAxiosErr(err) || 'No se pudo eliminar el perfil.', 'error')
  }
}

/* ====== Utilidades UI ====== */
async function copyMikrotikScript() {
  try {
    const txt = autoGen.value?.mikrotik_cmd || ''
    if (!txt) throw new Error('Nada para copiar.')
    await copyToClipboard(txt)
    showNotification('Script copiado al portapapeles.', 'success')
  } catch (e) {
    showNotification(getAxiosErr(e) || 'No se pudo copiar.', 'error')
  }
}

/* ====== Montaje ====== */
onMounted(async () => {
  await fetchVpnProfiles()

  // Autocompletar nombre si el usuario tipea una config manualmente
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

  // WS para escuchar rotaciones y actualizar UI
  try {
    await connectWebSocketWhenAuthenticated()
    wsUnsubRot = addWsListener((msg) => {
      if (msg?.type === 'device_credential_rotated' && autoGen.value) {
        if (!msg.device_id || msg.device_id === autoGen.value.device_id) {
          autoGen.value.rotations_count = (autoGen.value.rotations_count ?? 0) + 1
          if (msg.ok) autoGen.value.last_auth_ok = msg.ts
          else autoGen.value.last_auth_fail = msg.ts
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
      <h2><i class="icon">➕</i> Crear Perfil</h2>
      <div class="grid-2">
        <div>
          <label>Nombre *</label>
          <input v-model="newProfile.name" type="text" placeholder="Nombre del perfil" />
        </div>
        <div>
          <label>Check IP (opcional)</label>
          <input v-model="newProfile.check_ip" type="text" placeholder="Ej: 192.168.81.4" />
          <small>IP dentro del túnel para prueba rápida.</small>
        </div>
      </div>

      <div class="stack">
        <div class="label-with-action">
          <label>Config WireGuard *</label>
          <div class="actions-right">
            <button
              @click="generateAutoConfig"
              class="btn-qr-scan"
              :disabled="isGenerating"
              title="Generar comandos desde el backend"
            >
              {{ isGenerating ? 'Generando…' : 'Generar (auto)' }}
            </button>
          </div>
        </div>

        <textarea
          v-model="newProfile.config_data"
          rows="10"
          spellcheck="false"
          placeholder="[Interface]&#10;PrivateKey = ...&#10;Address = ...&#10;DNS = ...&#10;&#10;[Peer]&#10;PublicKey = ...&#10;AllowedIPs = ...&#10;Endpoint = ..."
        />

        <div v-if="autoGen" class="auto-box">
          <div class="auto-box-header" @click="autoBoxOpen = !autoBoxOpen">
            <div class="status-chip" :class="verify.connected ? 'ok' : 'warn'">
              <span class="dot"></span>
              {{ verify.connected ? 'Túnel activo' : 'Esperando handshake' }}
            </div>
            <div class="grow"></div>
            <button class="btn-toggle" type="button">
              {{ autoBoxOpen ? 'Ocultar' : 'Mostrar' }}
            </button>
          </div>

          <transition name="fade">
            <div v-if="autoBoxOpen" class="auto-inner">
              <div class="auto-grid">
                <div><strong>Address:</strong> {{ autoGen.interface_address }}</div>
                <div><strong>Endpoint:</strong> {{ autoGen.peer_endpoint }}</div>
                <div><strong>AllowedIPs:</strong> {{ autoGen.peer_allowed_ips }}</div>
                <div class="mono-clip">
                  <strong>Server PubKey:</strong> {{ autoGen.peer_public_key }}
                </div>
                <div class="mono-clip">
                  <strong>Client PubKey:</strong> {{ autoGen.client_public_key }}
                </div>
              </div>

              <div class="auto-grid">
                <div><strong>Rotaciones:</strong> {{ autoGen.rotations_count ?? 0 }}</div>
                <div><strong>Último OK:</strong> {{ autoGen.last_auth_ok || '—' }}</div>
                <div><strong>Último fallo:</strong> {{ autoGen.last_auth_fail || '—' }}</div>
              </div>

              <div class="stack">
                <label>Script MikroTik (copiar y pegar en terminal)</label>
                <pre class="code-block">{{ autoGen.mikrotik_cmd }}</pre>
                <div class="actions-row">
                  <button class="btn-secondary" @click="copyMikrotikScript">Copiar script</button>
                  <button v-if="!verify.running" class="btn-default" @click="startVerifyPolling">
                    Verificar estado
                  </button>
                  <button v-else class="btn-danger" @click="stopVerifyPolling">
                    Detener verificación
                  </button>
                </div>
              </div>

              <div class="verify-box">
                <div>
                  <strong>Conexión:</strong>
                  <span :class="verify.connected ? 'ok' : 'warn'">
                    {{ verify.connected ? 'Conectado' : 'Sin conexión' }}
                  </span>
                </div>
                <div><strong>Último handshake:</strong> {{ verify.lastHandshake || '—' }}</div>
                <div><strong>RX / TX:</strong> {{ verify.rx }} / {{ verify.tx }} bytes</div>
                <div v-if="verify.error" class="err">Error: {{ verify.error }}</div>
                <small>Intentos: {{ verify.tries }}</small>
              </div>
            </div>
          </transition>
        </div>
      </div>

      <div class="actions-row">
        <button
          class="btn-primary"
          :disabled="!newProfile.name.trim() || !isLikelyWgIni(newProfile.config_data) || isSaving"
          @click="createProfile"
        >
          {{ isSaving ? 'Creando…' : 'Crear Perfil' }}
        </button>
      </div>
    </section>

    <section class="control-section">
      <h2><i class="icon">🗂️</i> Perfiles existentes</h2>
      <div v-if="isLoading" class="loading-text">Cargando...</div>
      <div v-else-if="!vpnProfiles.length" class="empty">No hay perfiles. Creá uno arriba.</div>

      <ul v-else class="vpn-list">
        <li v-for="p in vpnProfiles" :key="p.id" class="vpn-card">
          <div class="vpn-header" @click="p._expanded = !p._expanded">
            <div class="title">
              <span class="name">{{ p.name }}</span>
              <span v-if="p.is_default" class="badge-default" title="Default">★ Default</span>
            </div>
            <button class="btn-toggle" type="button">
              {{ p._expanded ? 'Ocultar' : 'Mostrar' }}
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
                <input
                  v-model="p.check_ip"
                  type="text"
                  placeholder="IP para testear a través del túnel"
                />
              </div>
            </div>
            <div class="stack">
              <label>Config WireGuard</label>
              <textarea v-model="p.config_data" rows="12" spellcheck="false"></textarea>
            </div>
            <div class="actions-row">
              <button class="btn-primary" :disabled="p._saving" @click.stop="saveProfile(p)">
                {{ p._saving ? 'Guardando…' : 'Guardar cambios' }}
              </button>
              <button
                class="btn-default"
                v-if="!p.is_default"
                :disabled="p._saving"
                @click.stop="setDefault(p)"
                title="Marcar este perfil como predeterminado"
              >
                Marcar como default
              </button>
              <button class="btn-secondary" :disabled="p._saving" @click.stop="testProfile(p)">
                Probar túnel
              </button>
              <button class="btn-danger" :disabled="p._saving" @click.stop="deleteProfile(p)">
                Eliminar
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
  --gray: #9aa0a6;
  --primary-color: #6ab4ff;
  --secondary-color: #ff6b6b;
  --green: #2ea043;
  --error-red: #d9534f;
  --badge: #f4d03f;
}
.page-wrap {
  color: var(--font-color);
}
h1 {
  margin: 0 0 1rem 0;
}
h2 {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.75rem;
}
.icon {
  font-style: normal;
}
.control-section {
  background: var(--panel);
  padding: 1rem;
  border-radius: 10px;
  margin-bottom: 1rem;
}
.grid-2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}
@media (max-width: 900px) {
  .grid-2 {
    grid-template-columns: 1fr;
  }
}
.stack {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}
input,
textarea,
select {
  width: 100%;
  background: #0e0e0e;
  color: var(--font-color);
  border: 1px solid #2a2a2a;
  border-radius: 8px;
  padding: 0.6rem 0.7rem;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', monospace;
}
textarea {
  white-space: pre;
}
.actions-row {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
  margin-top: 0.5rem;
}
.btn-primary,
.btn-secondary,
.btn-danger,
.btn-default,
.btn-toggle,
.btn-qr-scan,
.file-btn {
  border-radius: 8px;
  padding: 0.6rem 0.9rem;
  cursor: pointer;
  border: 1px solid transparent;
  color: white;
}
.btn-primary {
  background: var(--green);
}
.btn-primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.btn-secondary {
  background: transparent;
  color: var(--font-color);
  border-color: var(--primary-color);
}
.btn-default {
  background: #2b5cb3;
}
.btn-danger {
  background: var(--secondary-color);
}
.btn-toggle {
  background: #2a2a2a;
  color: var(--font-color);
}
.loading-text,
.empty {
  color: var(--gray);
}
.vpn-list {
  list-style: none;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}
.vpn-card {
  background: #0e0e0e;
  border: 1px solid #2a2a2a;
  border-radius: 10px;
}
.vpn-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.8rem 1rem;
  border-bottom: 1px solid #2a2a2a;
  cursor: pointer;
}
.title {
  display: flex;
  align-items: center;
  gap: 0.6rem;
}
.name {
  font-weight: 700;
}
.badge-default {
  border: 1px solid var(--badge);
  color: #161616;
  background: var(--badge);
  border-radius: 6px;
  padding: 0.1rem 0.4rem;
  font-size: 0.8rem;
}
.vpn-body {
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

/* Notificaciones */
.notification {
  position: fixed;
  bottom: 20px;
  right: 20px;
  z-index: 2000;
  padding: 1rem 1.2rem;
  border-radius: 8px;
  color: white;
  font-weight: 600;
}
.notification.success {
  background: var(--green);
}
.notification.error {
  background: var(--error-red);
}

/* Barra config */
.label-with-action {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.actions-right {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}
.btn-qr-scan {
  background: #333;
  color: var(--font-color);
  border: 1px solid #444;
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
}
.btn-qr-scan:hover {
  background: #444;
}

/* Panel autogenerado */
.auto-box {
  margin-top: 0.5rem;
  background: #0f0f0f;
  border: 1px solid #2a2a2a;
  border-radius: 8px;
}
.auto-box-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.6rem 0.75rem;
  border-bottom: 1px solid #2a2a2a;
}
.auto-inner {
  padding: 0.75rem;
}
.auto-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.5rem 0.75rem;
  margin-bottom: 0.5rem;
}
@media (max-width: 720px) {
  .auto-grid {
    grid-template-columns: 1fr;
  }
}
.mono-clip {
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', monospace;
}
.code-block {
  background: #0b0b0b;
  border: 1px solid #2a2a2a;
  border-radius: 8px;
  padding: 0.75rem;
  overflow: auto;
  white-space: pre;
}

/* Verify */
.status-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  padding: 0.25rem 0.5rem;
  border-radius: 999px;
  font-weight: 600;
  font-size: 0.9rem;
  border: 1px solid #2a2a2a;
}
.status-chip .dot {
  width: 0.6rem;
  height: 0.6rem;
  border-radius: 50%;
  display: inline-block;
}
.status-chip.ok {
  background: rgba(46, 160, 67, 0.12);
  color: #68d391;
}
.status-chip.ok .dot {
  background: #2ea043;
}
.status-chip.warn {
  background: rgba(244, 208, 63, 0.12);
  color: #f4d03f;
}
.status-chip.warn .dot {
  background: #f4d03f;
}

.verify-box {
  margin-top: 0.5rem;
  padding: 0.6rem 0.75rem;
  border: 1px solid #2a2a2a;
  border-radius: 8px;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.5rem 0.75rem;
  font-size: 0.95rem;
}
.verify-box .ok {
  color: #68d391;
}
.verify-box .warn {
  color: #f4d03f;
}
.verify-box .err {
  color: #ff6b6b;
  grid-column: 1 / -1;
}
.grow {
  flex: 1;
}

/* Transición */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.15s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
