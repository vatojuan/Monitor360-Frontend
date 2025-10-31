<script setup>
import { ref, nextTick, onBeforeUnmount, onMounted } from 'vue'
import QrcodeVue from 'qrcode.vue'
import api from '@/lib/api'
import { addWsListener, connectWebSocketWhenAuthenticated, removeWsListener } from '@/lib/ws'
import { BrowserQRCodeReader } from '@zxing/browser'
import { NotFoundException } from '@zxing/library'

/* ====== Helpers ====== */
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
const getAxiosErr = (err) => err?.response?.data?.detail || err?.message || 'Error inesperado.'

/** Validación mínima de un ini de WireGuard (ahora exige Address también) */
function isLikelyWgIni(txt) {
  if (!txt) return false
  const s = txt.trim()
  return (
    /\[Interface\]/i.test(s) &&
    /(^|\n)\s*Address\s*=\s*.+/i.test(s) &&
    /\[Peer\]/i.test(s) &&
    /(^|\n)\s*PublicKey\s*=\s*.+/i.test(s) &&
    /(^|\n)\s*AllowedIPs\s*=\s*.+/i.test(s)
  )
}

/** Inyecta Address=... en el bloque [Interface] si falta */
function ensureAddressInIni(iniText, fallbackAddr) {
  let out = (iniText || '').trim()
  if (!/(^|\n)\s*Address\s*=\s*.+/i.test(out)) {
    if (!fallbackAddr) return null
    // Insertar debajo de la primera línea [Interface]
    out = out.replace(/\[Interface\]\s*/i, (m) => `${m}\nAddress = ${fallbackAddr}\n`)
  }
  return out
}

/** Intenta proponer un nombre a partir de Address/Endpoint */
function proposeProfileName(iniText) {
  try {
    const addr = (iniText.match(/(^|\n)\s*Address\s*=\s*([^\n\r]+)/i)?.[2] || '').trim()
    const endpoint = (iniText.match(/(^|\n)\s*Endpoint\s*=\s*([^\n\r]+)/i)?.[2] || '').trim()
    if (addr && endpoint) return `${addr.split('/')[0]} @ ${endpoint}`
    if (endpoint) return endpoint
    if (addr) return addr.split('/')[0]
  } catch {
    return ''
  }
  return ''
}

/** Construye plantilla CLI para MikroTik a partir de la respuesta /mikrotik-auto */
function buildMikrotikCmd(resp) {
  const ep = String(resp?.peer_endpoint || '')
  const [host, port] = ep.split(':')
  const addr = resp?.interface_address || ''
  const allowed = resp?.peer_allowed_ips || '0.0.0.0/0'
  const srvPub = resp?.peer_public_key || ''
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

/* ====== ZXing / Cámara ====== */
let codeReader = null
let currentStream = null
const cameras = ref([])
const selectedCameraId = ref('')

async function listCameras() {
  cameras.value = await BrowserQRCodeReader.listVideoInputDevices()
  // Preferir trasera si existe
  const backCam = cameras.value.find((d) => /back|trás|rear|environment/i.test(d.label))
  selectedCameraId.value = backCam?.deviceId || cameras.value[0]?.deviceId || ''
}

/** Algunos navegadores permiten torch */
async function setTorch(on) {
  try {
    const track = currentStream?.getVideoTracks?.()[0]
    const caps = track?.getCapabilities?.()
    if (caps?.torch) {
      await track.applyConstraints({ advanced: [{ torch: !!on }] })
      return true
    }
  } catch {
    return false
  }
  return false
}

/* ====== Estado del modal QR ====== */
const scanOpen = ref(false)
const step = ref('choose')

const localActive = ref(false)
const localError = ref('')
const localPaused = ref(false)
const torchEnabled = ref(false)

const pairing = ref(null) // { id, url, expires_in }
let wsUnsub = null
let remoteTimer = null
const remoteCountdown = ref(0)
const remoteExpired = ref(false)

/* ====== Formulario / listado de VPNs ====== */
const newProfile = ref({
  name: '',
  check_ip: '',
  config_data: '',
})

const vpnProfiles = ref([])
const isLoading = ref(false)
const isSaving = ref(false)

/* ====== Auto-generado backend ====== */
const isGenerating = ref(false)
const autoGen = ref(null) // guarda última respuesta útil para mostrar detalles y comando

/* ====== Verificación de handshake (polling) ====== */
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

async function pollStatusOnce() {
  if (!autoGen.value?.client_public_key) return
  try {
    const url = `/vpns/peer-status/${encodeURIComponent(autoGen.value.client_public_key)}`
    const { data } = await api.get(url)
    verify.value.connected = !!data?.connected
    verify.value.lastHandshake = data?.latest_handshake || null
    verify.value.rx = data?.rx_bytes || 0
    verify.value.tx = data?.tx_bytes || 0
    verify.value.error = ''
  } catch (e) {
    verify.value.error = getAxiosErr(e)
  } finally {
    verify.value.tries += 1
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
  // Primer intento inmediato
  pollStatusOnce()
  // Luego cada ~2.5s
  verifyTimer = setInterval(pollStatusOnce, 2500)
}

onBeforeUnmount(() => {
  stopLocalScan()
  cleanupRemote()
  document.removeEventListener('visibilitychange', onVisibilityChange)
  stopVerifyPolling()
})

/* ====== Notificaciones ====== */
const notification = ref({ show: false, message: '', type: 'success' })
function showNotification(message, type = 'success') {
  notification.value = { show: true, message, type }
  setTimeout(() => (notification.value.show = false), 4000)
}

/* ====== Abrir / cerrar modal ====== */
function openScanModal() {
  scanOpen.value = true
  step.value = 'choose'
  localError.value = ''
  localActive.value = false
  localPaused.value = false
  pairing.value = null
  remoteCountdown.value = 0
  remoteExpired.value = false
}

function closeScanModal() {
  scanOpen.value = false
  cleanupRemote()
  stopLocalScan()
}

/** Intenta arreglar Address faltante si tenemos un address del backend */
function fixOrRejectIni(text) {
  const withMaybeAddress = ensureAddressInIni(text, autoGen.value?.interface_address || '') || null

  if (!withMaybeAddress) {
    // No pudimos inyectar Address porque no tenemos fallback
    return {
      ok: false,
      text: null,
      reason:
        'La configuración no incluye "Address = ..." y no se pudo inferir automáticamente. Editá el .conf y agregá la línea Address.',
    }
  }

  // Validar final
  if (!isLikelyWgIni(withMaybeAddress)) {
    return {
      ok: false,
      text: null,
      reason:
        'La configuración de WireGuard no es válida. Verificá [Interface], Address, [Peer], PublicKey y AllowedIPs.',
    }
  }
  return { ok: true, text: withMaybeAddress }
}

/* ====== Aplicar config desde QR/archivo ====== */
function applyConfigAndClose(text) {
  const conf = (text || '').trim()
  // 1) Intentar inyectar Address si falta
  const result = fixOrRejectIni(conf)
  if (!result.ok) {
    showNotification(result.reason, 'error')
    return
  }

  const finalConf = result.text
  newProfile.value.config_data = finalConf

  // Sugerir nombre si falta
  if (!newProfile.value.name.trim()) {
    const suggested = proposeProfileName(finalConf)
    if (suggested) newProfile.value.name = suggested.slice(0, 80)
  }

  closeScanModal()
  showNotification('Configuración cargada.', 'success')
}

/* ====== Opción A: Cámara local ====== */
async function chooseLocal() {
  step.value = 'local'
  await nextTick()
  localError.value = ''
  localActive.value = true
  localPaused.value = false
  torchEnabled.value = false

  try {
    await listCameras()
    if (!selectedCameraId.value) {
      localError.value = 'No se encontró ninguna cámara disponible.'
      return
    }

    // Permiso de cámara (algunos navegadores lo requieren explícito)
    try {
      currentStream = await navigator.mediaDevices.getUserMedia({
        video: { deviceId: selectedCameraId.value },
      })
      // liberar porque ZXing tomará control
      currentStream.getTracks().forEach((t) => t.stop())
      currentStream = null
    } catch {
      localError.value = 'Permiso de cámara denegado o no disponible.'
      return
    }

    codeReader = new BrowserQRCodeReader()
    await codeReader.decodeFromVideoDevice(selectedCameraId.value, 'preview', (result, err) => {
      if (result) {
        applyConfigAndClose(result.getText())
        stopLocalScan()
      }
      if (err && !(err instanceof NotFoundException)) {
        void err
      }
    })

    // Guardar stream para Torch y pausas
    const preview = document.getElementById('preview')
    currentStream = preview?.srcObject || null
  } catch (err) {
    console.error('Error iniciando ZXing:', err)
    localError.value = 'No se pudo iniciar el lector de QR.'
  }
}

async function onChangeCamera() {
  if (!localActive.value) return
  stopLocalScan()
  await sleep(150)
  await chooseLocal()
}

async function toggleTorch() {
  const ok = await setTorch(!torchEnabled.value)
  if (ok) torchEnabled.value = !torchEnabled.value
  else showNotification('Este dispositivo no soporta linterna.', 'error')
}

function stopLocalScan() {
  try {
    if (codeReader) {
      codeReader.reset()
      codeReader = null
    }
    if (currentStream) {
      currentStream.getTracks().forEach((t) => t.stop?.())
      currentStream = null
    }
  } catch (e) {
    void e
  }
  localActive.value = false
  torchEnabled.value = false
}

/* Pausar cámara cuando se oculta la pestaña (ahorra recursos) */
function onVisibilityChange() {
  if (!localActive.value) return
  if (document.hidden) {
    localPaused.value = true
    stopLocalScan()
  } else if (localPaused.value) {
    chooseLocal()
  }
}
document.addEventListener('visibilitychange', onVisibilityChange)

/* ====== Opción B: Remoto con celular ====== */
async function chooseRemote() {
  step.value = 'remote'
  try {
    const { data } = await api.post('/qr/start')
    pairing.value = { id: data.session_id, url: data.mobile_url, expires_in: data.expires_in }
    remoteCountdown.value = Number(data.expires_in || 300)
    remoteExpired.value = false

    // Countdown
    if (remoteTimer) clearInterval(remoteTimer)
    remoteTimer = setInterval(() => {
      if (remoteCountdown.value > 0) remoteCountdown.value -= 1
      if (remoteCountdown.value <= 0) {
        remoteExpired.value = true
        cleanupRemote()
        clearInterval(remoteTimer)
        remoteTimer = null
      }
    }, 1000)

    await connectWebSocketWhenAuthenticated()
    wsUnsub = addWsListener((msg) => {
      if (msg?.type === 'qr_config' && msg.session_id === pairing.value?.id) {
        applyConfigAndClose(msg.config_text)
        cleanupRemote()
      }
    })
  } catch (err) {
    showNotification(getAxiosErr(err), 'error')
    step.value = 'choose'
  }
}

function cleanupRemote() {
  if (wsUnsub) {
    try {
      removeWsListener(wsUnsub)
    } catch (e) {
      void e
    }
    wsUnsub = null
  }
  if (remoteTimer) {
    clearInterval(remoteTimer)
    remoteTimer = null
  }
  pairing.value = null
  remoteCountdown.value = 0
  remoteExpired.value = false
}

/* ====== Importar desde archivo .conf ====== */
async function importFromFile(e) {
  const file = e.target?.files?.[0]
  if (!file) return
  try {
    const txt = await file.text()
    applyConfigAndClose(txt)
  } catch {
    showNotification('No se pudo leer el archivo.', 'error')
  } finally {
    e.target.value = '' // reset input
  }
}

/* ====== Generar config automáticamente (backend) ====== */
const autoBoxOpen = ref(true)

async function generateAutoConfig() {
  if (isGenerating.value) return
  isGenerating.value = true
  try {
    const { data } = await api.post('/vpns/mikrotik-auto', {}) // usa ENV del backend
    // Asegurar que el INI tenga Address; si falta, lo inyectamos con interface_address
    const rawConf = (data?.conf_ini || '').trim()
    const ensured = ensureAddressInIni(rawConf, data?.interface_address || '')
    if (!ensured) {
      throw new Error('El backend no devolvió Address y no se pudo inferir.')
    }
    if (!isLikelyWgIni(ensured)) {
      throw new Error('La conf generada es inválida. Faltan campos obligatorios.')
    }

    newProfile.value.config_data = ensured
    if (!newProfile.value.name.trim()) {
      const suggested = proposeProfileName(ensured)
      if (suggested) newProfile.value.name = suggested.slice(0, 80)
    }

    autoGen.value = {
      ...data,
      conf_ini: ensured,
      mikrotik_cmd: buildMikrotikCmd({ ...data, interface_address: data?.interface_address }),
    }
    autoBoxOpen.value = true
    showNotification('Configuración generada automáticamente.', 'success')
    // Iniciar verificación automática
    stopVerifyPolling()
    startVerifyPolling()
  } catch (err) {
    console.error(err)
    showNotification(getAxiosErr(err), 'error')
  } finally {
    isGenerating.value = false
  }
}

/* ====== CRUD VPN Profiles ====== */
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
  if (!canCreate()) {
    // Mensaje más específico de ayuda
    const msg = /Address\s*=/.test(newProfile.value.config_data || '')
      ? 'Nombre y Config válidas son obligatorios.'
      : 'La config debe incluir "Address = ..." dentro de [Interface].'
    showNotification(msg, 'error')
    return
  }
  if (isSaving.value) return
  isSaving.value = true
  try {
    const body = {
      name: newProfile.value.name.trim(),
      config_data: newProfile.value.config_data,
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
  // Validar que mantenga Address
  if (!isLikelyWgIni(profile.config_data || '')) {
    showNotification(
      'La config debe incluir "Address = ..." en [Interface], PublicKey y AllowedIPs.',
      'error',
    )
    return
  }
  profile._saving = true
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
    if (data.reachable) {
      showNotification(`Túnel OK. Alcanzable (${profile.check_ip}).`, 'success')
    } else {
      showNotification(data.detail || 'No alcanzable a través del túnel.', 'error')
    }
  } catch (err) {
    console.error('Error al probar túnel:', err)
    showNotification(getAxiosErr(err) || 'Error al probar el túnel.', 'error')
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

/* ====== Utilidad: copiar script MikroTik ====== */
async function copyMikrotikScript() {
  const txt = autoGen.value?.mikrotik_cmd || ''
  if (!txt.trim()) {
    showNotification('No hay script para copiar.', 'error')
    return
  }
  try {
    await navigator.clipboard.writeText(txt)
    showNotification('Script copiado al portapapeles.', 'success')
  } catch {
    // Fallback
    try {
      const ta = document.createElement('textarea')
      ta.value = txt
      document.body.appendChild(ta)
      ta.select()
      document.execCommand('copy')
      document.body.removeChild(ta)
      showNotification('Script copiado al portapapeles.', 'success')
    } catch {
      showNotification('No se pudo copiar el script.', 'error')
    }
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
          <div class="actions-right">
            <label class="file-btn" title="Importar .conf">
              Importar .conf
              <input type="file" accept=".conf,.txt" @change="importFromFile" hidden />
            </label>
            <button
              @click="generateAutoConfig"
              class="btn-qr-scan"
              :disabled="isGenerating"
              title="Generar automáticamente desde el backend"
            >
              {{ isGenerating ? 'Generando…' : 'Generar config (auto)' }}
            </button>
            <button @click="openScanModal" class="btn-qr-scan" title="Escanear Código QR">
              <svg viewBox="0 0 24 24" fill="currentColor">
                <path
                  d="M3 11h8V3H3v8zm2-6h4v4H5V5zM3 21h8v-8H3v8zm2-6h4v4H5v-4zM13 3v8h8V3h-8zm6 6h-4V5h4v4zM13 13h2v2h-2zM15 15h2v2h-2zM13 17h2v2h-2zM17 17h2v2h-2zM19 19h2v2h-2zM15 19h2v2h-2zM17 13h2v2h-2zM19 15h2v2h-2z"
                ></path>
              </svg>
              Escanear
            </button>
          </div>
        </div>

        <textarea
          v-model="newProfile.config_data"
          rows="10"
          spellcheck="false"
          placeholder="[Interface]&#10;PrivateKey = ...&#10;Address = 10.10.13.X/24&#10;DNS = ...&#10;&#10;[Peer]&#10;PublicKey = ...&#10;AllowedIPs = 0.0.0.0/0&#10;Endpoint = host:port"
        />

        <!-- Panel autogenerado -->
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
                  <span :class="verify.connected ? 'ok' : 'warn'">{{
                    verify.connected ? 'Conectado' : 'Sin conexión'
                  }}</span>
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
          <h3>¿Cómo querés escanear el QR?</h3>
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
          <h3>Apuntá al código QR de MikroTik</h3>
          <div v-if="localError" class="text-red-400">{{ localError }}</div>
          <div class="local-controls" v-else>
            <select v-if="cameras.length" v-model="selectedCameraId" @change="onChangeCamera">
              <option v-for="c in cameras" :key="c.deviceId" :value="c.deviceId">
                {{ c.label || 'Cámara' }}
              </option>
            </select>
            <button class="btn-qr-scan" @click="toggleTorch" title="Linterna">
              {{ torchEnabled ? 'Apagar linterna' : 'Encender linterna' }}
            </button>
          </div>
          <div class="remote-qr-container">
            <video id="preview" class="qr-video" autoplay playsinline></video>
          </div>
        </div>

        <!-- Paso remoto -->
        <div v-else-if="step === 'remote'">
          <h3>1. Escaneá este QR con tu celular</h3>
          <p class="remote-scan-subtitle">Se abrirá una página para escanear el QR de MikroTik.</p>
          <div class="remote-qr-container">
            <QrcodeVue
              :value="pairing?.url"
              :size="220"
              level="H"
              v-if="pairing?.url && !remoteExpired"
            />
            <div v-else class="expired">La sesión expiró.</div>
          </div>
          <p v-if="!remoteExpired" class="waiting-text">
            Esperando datos del celular… ({{ remoteCountdown }}s)
          </p>
          <div v-else class="expired-actions">
            <button class="btn-qr-scan" @click="chooseRemote">Reintentar</button>
          </div>
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

/* Botones barra config */
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
.file-btn {
  background: #333;
  color: var(--font-color);
  border: 1px solid #444;
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
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
.btn-qr-scan svg {
  width: 1rem;
  height: 1rem;
}

/* Modal QR */
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
  max-width: 540px;
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
.expired {
  color: var(--error-red);
  font-weight: 600;
  margin-top: 0.5rem;
}
.expired-actions {
  margin-top: 0.75rem;
}

.local-controls {
  display: flex;
  gap: 0.5rem;
  align-items: center;
  justify-content: center;
  margin-bottom: 0.5rem;
}
.qr-video {
  width: 100%;
  max-width: 420px;
  aspect-ratio: 1 / 1;
  object-fit: cover;
  border-radius: 12px;
  border: 2px solid #444;
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

/* Verify badge */
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
