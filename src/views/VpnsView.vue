<script setup>
import { ref, nextTick, onBeforeUnmount, onMounted } from 'vue'
import { QrcodeStream } from 'vue-qrcode-reader'
import QrcodeVue from 'qrcode.vue'
import api from '@/lib/api'
import { addWsListener, connectWebSocketWhenAuthenticated, removeWsListener } from '@/lib/ws'

// === Estado del modal ===
const scanOpen = ref(false)
const step = ref('choose')

// === Local (Opción A)
const localActive = ref(false)
const localError = ref('')
const localStreamKey = ref(0)
const localPaused = ref(false)

// === Remoto (Opción B)
const pairing = ref(null) // { id, url, expires_in }
let wsUnsub = null

// === Formulario creación VPN ===
const newProfile = ref({
  name: '',
  check_ip: '',
  config_data: '',
})

const vpnProfiles = ref([])
const isLoading = ref(false)

const notification = ref({ show: false, message: '', type: 'success' })
function showNotification(message, type = 'success') {
  notification.value = { show: true, message, type }
  setTimeout(() => (notification.value.show = false), 4000)
}

// --- Modal QR ---
function openScanModal() {
  scanOpen.value = true
  step.value = 'choose'
  localError.value = ''
  localActive.value = false
  localPaused.value = false
  pairing.value = null
}

function closeScanModal() {
  scanOpen.value = false
  cleanupRemote()
}

function applyConfigAndClose(text) {
  newProfile.value.config_data = text?.trim() || ''
  closeScanModal()
  showNotification('Configuración cargada desde QR', 'success')
}

// === Opción A ===
async function chooseLocal() {
  step.value = 'local'
  await nextTick()
  localStreamKey.value++
  localActive.value = true
  localPaused.value = false
  localError.value = ''
}

async function onLocalInit(promise) {
  try {
    await promise
  } catch (err) {
    if (err?.name === 'NotAllowedError') localError.value = 'Debes dar permiso a la cámara.'
    else if (err?.name === 'NotFoundError')
      localError.value = 'No se encontró cámara en este dispositivo.'
    else localError.value = 'No se pudo iniciar la cámara.'
    localActive.value = false
  }
}

function onLocalDecode(text) {
  if (localPaused.value) return
  localPaused.value = true
  applyConfigAndClose(text)
}

// === Opción B ===
async function chooseRemote() {
  step.value = 'remote'
  const { data } = await api.post('/qr/start')
  pairing.value = { id: data.session_id, url: data.mobile_url, expires_in: data.expires_in }

  await connectWebSocketWhenAuthenticated()
  wsUnsub = addWsListener((msg) => {
    if (msg?.type === 'qr_config' && msg.session_id === pairing.value?.id) {
      applyConfigAndClose(msg.config_text)
    }
  })
}

function cleanupRemote() {
  if (wsUnsub) {
    try {
      removeWsListener(wsUnsub)
    } catch {}
    wsUnsub = null
  }
}

onBeforeUnmount(() => cleanupRemote())

// --- CRUD VPN Profiles ---
async function fetchVpnProfiles() {
  isLoading.value = true
  try {
    const { data } = await api.get('/vpns')
    vpnProfiles.value = (data || []).map((p) => ({
      ...p,
      is_default: !!p.is_default,
      _expanded: false,
    }))
  } catch (err) {
    console.error('Error al cargar perfiles VPN:', err)
    showNotification(err.response?.data?.detail || 'Error al cargar perfiles VPN.', 'error')
  } finally {
    isLoading.value = false
  }
}

async function createProfile() {
  if (!newProfile.value.name.trim() || !newProfile.value.config_data.trim()) {
    showNotification('Nombre y Config son obligatorios.', 'error')
    return
  }
  try {
    const body = {
      name: newProfile.value.name.trim(),
      config_data: newProfile.value.config_data,
      check_ip: newProfile.value.check_ip.trim(),
    }
    const { data } = await api.post('/vpns', body)
    vpnProfiles.value.push({ ...data, is_default: !!data.is_default, _expanded: false })
    newProfile.value = { name: '', check_ip: '', config_data: '' }
    showNotification('Perfil VPN creado.', 'success')
  } catch (err) {
    console.error('Error al crear perfil:', err)
    showNotification(err.response?.data?.detail || 'Error al crear perfil.', 'error')
  }
}

async function saveProfile(profile) {
  try {
    const payload = {
      name: profile.name,
      check_ip: profile.check_ip,
      config_data: profile.config_data,
    }
    await api.put(`/vpns/${profile.id}`, payload)
    showNotification('Perfil actualizado.', 'success')
    await fetchVpnProfiles()
  } catch (err) {
    console.error('Error al actualizar perfil:', err)
    showNotification(err.response?.data?.detail || 'Error al actualizar perfil.', 'error')
  }
}

async function setDefault(profile) {
  try {
    await api.put(`/vpns/${profile.id}`, { is_default: true })
    await fetchVpnProfiles()
    showNotification(`"${profile.name}" ahora es el default.`, 'success')
  } catch (err) {
    console.error('Error al marcar default:', err)
    showNotification(err.response?.data?.detail || 'No se pudo marcar como default.', 'error')
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
    if (data.reachable) {
      showNotification(`Túnel OK. Alcanzable (${profile.check_ip}).`, 'success')
    } else {
      showNotification(data.detail || 'No alcanzable a través del túnel.', 'error')
    }
  } catch (err) {
    console.error('Error al probar túnel:', err)
    showNotification(err.response?.data?.detail || 'Error al probar el túnel.', 'error')
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
    showNotification(err.response?.data?.detail || 'No se pudo eliminar el perfil.', 'error')
  }
}

onMounted(fetchVpnProfiles)
</script>

<template>
  <div class="page-wrap">
    <h1>Perfiles VPN</h1>

    <!-- Crear nuevo perfil -->
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
          <button @click="openScanModal" class="btn-qr-scan" title="Escanear Código QR">
            <svg viewBox="0 0 24 24" fill="currentColor">
              <path
                d="M3 11h8V3H3v8zm2-6h4v4H5V5zM3 21h8v-8H3v8zm2-6h4v4H5v-4zM13 3v8h8V3h-8zm6 6h-4V5h4v4zM13 13h2v2h-2zM15 15h2v2h-2zM13 17h2v2h-2zM17 17h2v2h-2zM19 19h2v2h-2zM15 19h2v2h-2zM17 13h2v2h-2zM19 15h2v2h-2z"
              ></path>
            </svg>
            Escanear
          </button>
        </div>
        <textarea
          v-model="newProfile.config_data"
          rows="10"
          spellcheck="false"
          placeholder="[Interface]&#10;PrivateKey = ...&#10;Address = ...&#10;DNS = ...&#10;&#10;[Peer]&#10;PublicKey = ...&#10;AllowedIPs = ...&#10;Endpoint = ..."
        />
      </div>
      <div class="actions-row">
        <button class="btn-primary" @click="createProfile">Crear Perfil</button>
      </div>
    </section>

    <!-- Listado / edición -->
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
              <button class="btn-primary" @click.stop="saveProfile(p)">Guardar cambios</button>
              <button
                class="btn-default"
                v-if="!p.is_default"
                @click.stop="setDefault(p)"
                title="Marcar este perfil como predeterminado"
              >
                Marcar como default
              </button>
              <button class="btn-secondary" @click.stop="testProfile(p)">Probar túnel</button>
              <button class="btn-danger" @click.stop="deleteProfile(p)">Eliminar</button>
            </div>
          </div>
        </li>
      </ul>
    </section>

    <!-- Notificaciones -->
    <div v-if="notification.show" class="notification" :class="notification.type">
      {{ notification.message }}
    </div>

    <!-- Modal del escáner QR -->
    <div v-if="scanOpen" class="qr-scanner-modal" @click.self="closeScanModal">
      <div class="qr-scanner-content">
        <button @click="closeScanModal" class="btn-close-modal" title="Cerrar">&times;</button>

        <!-- Paso elegir -->
        <div v-if="step === 'choose'">
          <h3>¿Cómo quieres escanear el QR?</h3>
          <div class="choose-options">
            <button @click="chooseLocal" class="btn-choose">
              <svg viewBox="0 0 24 24">
                <path
                  d="M17 10.5V7c0-.55-.45-1-1-1H4c-.55 0-1 .45-1 1v10c0 .55.45 1 1 1h12c.55 0 1-.45 1-1v-3.5l4 4v-11l-4 4z"
                />
              </svg>
              <span>Usar cámara de este dispositivo</span>
            </button>
            <button @click="chooseRemote" class="btn-choose">
              <svg viewBox="0 0 24 24">
                <path
                  d="M15 7.5V2H9v5.5l3 3 3-3zM7.5 9H2v6h5.5l3-3-3-3zM9 16.5V22h6v-5.5l-3-3-3 3zM16.5 15l-3 3 3 3H22v-6h-5.5z"
                />
              </svg>
              <span>Usar cámara de mi celular</span>
            </button>
          </div>
        </div>

        <!-- Paso local -->
        <div v-else-if="step === 'local'">
          <h3>Apunta al código QR de MikroTik</h3>
          <div v-if="localError" class="text-red-400">{{ localError }}</div>
          <div v-else class="remote-qr-container">
            <QrcodeStream
              :key="localStreamKey"
              :paused="localPaused"
              :constraints="{ facingMode: 'environment' }"
              @init="onLocalInit"
              @decode="onLocalDecode"
            />
          </div>
        </div>

        <!-- Paso remoto -->
        <div v-else-if="step === 'remote'">
          <h3>1. Escanea este QR con tu celular</h3>
          <p class="remote-scan-subtitle">Se abrirá una página para escanear el QR de MikroTik.</p>
          <div class="remote-qr-container">
            <QrcodeVue :value="pairing?.url" :size="220" level="H" v-if="pairing?.url" />
          </div>
          <p class="waiting-text">Esperando datos del celular...</p>
        </div>
      </div>
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
textarea {
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
.btn-toggle {
  border-radius: 8px;
  padding: 0.6rem 0.9rem;
  cursor: pointer;
  border: 1px solid transparent;
  color: white;
}
.btn-primary {
  background: var(--green);
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
.label-with-action {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.btn-qr-scan {
  background: #333;
  color: var(--font-color);
  border: 1px solid #444;
  border-radius: 6px;
  padding: 0.25rem 0.6rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 0.4rem;
}
.btn-qr-scan:hover {
  background: #444;
}
.btn-qr-scan svg {
  width: 1rem;
  height: 1rem;
}
.qr-scanner-modal {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  z-index: 1000;
  background-color: rgba(0, 0, 0, 0.8);
  display: flex;
  align-items: center;
  justify-content: center;
}
.qr-scanner-content {
  background-color: var(--panel);
  padding: 1.5rem;
  border-radius: 12px;
  text-align: center;
  width: 90%;
  max-width: 500px;
  position: relative;
}
.btn-close-modal {
  position: absolute;
  top: 10px;
  right: 10px;
  background: transparent;
  border: none;
  color: #999;
  font-size: 2rem;
  line-height: 1;
  cursor: pointer;
}
.choose-options {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  margin-top: 1.5rem;
}
.btn-choose {
  background: #2a2a2a;
  color: var(--font-color);
  border: 1px solid #444;
  border-radius: 8px;
  padding: 1rem;
  font-size: 1rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 0.8rem;
  text-align: left;
}
.btn-choose:hover {
  background: #333;
}
.btn-choose:disabled {
  background: #222;
  color: #555;
  cursor: not-allowed;
}
.btn-choose svg {
  width: 2.5rem;
  height: 2.5rem;
  fill: var(--primary-color);
  flex-shrink: 0;
}
.remote-scan-subtitle {
  color: var(--gray);
  margin: -0.5rem 0 1rem 0;
}
.remote-qr-container {
  background: white;
  padding: 1rem;
  display: inline-block;
  border-radius: 8px;
}
.waiting-text {
  margin-top: 1rem;
  color: var(--primary-color);
}
</style>
