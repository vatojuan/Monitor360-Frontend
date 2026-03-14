<script setup>
import { ref, onBeforeUnmount, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import api from '@/lib/api'
import { addWsListener, connectWebSocketWhenAuthenticated, removeWsListener } from '@/lib/ws'
// NUEVO: Importar librería de QR
import QrcodeVue from 'qrcode.vue'

const router = useRouter()

/* ====== Helpers ====== */
const getAxiosErr = (err) => err?.response?.data?.detail || err?.message || 'Error inesperado.'

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
const newProfile = ref({ name: '', check_ip: '', alerts_enabled: false, notification_channel_id: null, allowed_ips: '' })
const vpnProfiles = ref([])
const channels = ref([]) 
const isLoading = ref(false)
const isCreating = ref(false)

// NUEVO: Modificado para contener el objeto completo de Escritorio/Móvil
const desktopProfile = ref(null) 
const isEnablingDesktop = ref(false)
const isTogglingDesktop = ref(false)

const showLimitModal = ref(false)
const limitMessage = ref('')

function goToBilling() {
  showLimitModal.value = false
  router.push('/billing')
}

/* ====== Inspector de Estado ====== */
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
      notification_channel_id: newProfile.value.notification_channel_id,
      allowed_ips: newProfile.value.allowed_ips 
    }

    const { data: savedProfile } = await api.post('/vpns', payload)

    vpnProfiles.value.unshift({ ...savedProfile, _expanded: true })
    newProfile.value = { name: '', check_ip: '', alerts_enabled: false, notification_channel_id: null, allowed_ips: '' }
    showNotification('Perfil de Router creado y activado.', 'success')

  } catch (err) {
    if (err?.response?.status === 403 || err?.response?.status === 402) {
      limitMessage.value = err?.response?.data?.detail || 'Has alcanzado el límite de VPNs de tu plan actual.'
      showLimitModal.value = true
    } else {
      showNotification(getAxiosErr(err), 'error')
    }
  } finally {
    isCreating.value = false
  }
}

// ==== NUEVAS ACCIONES: AUTORIZACIÓN DINÁMICA ====
async function checkDesktopStatus() {
  try {
    const { data } = await api.post('/vpns/desktop/ensure')
    if (data && data.id) {
      desktopProfile.value = data
    }
  } catch (err) {
    console.error("Error verificando acceso desktop:", err)
  }
}

async function enableDesktopAccess() {
  isEnablingDesktop.value = true
  try {
    const { data } = await api.post('/vpns/desktop/ensure')
    if (data && data.id) {
      desktopProfile.value = data
      showNotification('✅ Acceso a Aplicaciones Habilitado.', 'success')
    }
  } catch (err) {
    if (err?.response?.status === 403 || err?.response?.status === 402) {
      limitMessage.value = err?.response?.data?.detail || 'Límite de PCs de escritorio alcanzado. Mejora tu plan.'
      showLimitModal.value = true
    } else {
      showNotification(getAxiosErr(err), 'error')
    }
  } finally {
    isEnablingDesktop.value = false
  }
}

async function disableDesktopAccess() {
  if (!confirm('¿Borrar definitivamente el acceso a App de Escritorio y Móvil?')) return
  isEnablingDesktop.value = true
  try {
    await api.delete(`/vpns/${desktopProfile.value.id}`)
    desktopProfile.value = null
    showNotification('💻 Acceso deshabilitado y borrado.', 'success')
  } catch (err) {
    showNotification(getAxiosErr(err), 'error')
  } finally {
    isEnablingDesktop.value = false
  }
}

async function toggleDesktopPower() {
  isTogglingDesktop.value = true
  const nextState = !desktopProfile.value.is_active
  try {
    await api.post(`/vpns/desktop/${desktopProfile.value.id}/toggle`, {
      is_active: nextState,
      active_device: desktopProfile.value.active_device
    })
    desktopProfile.value.is_active = nextState
    showNotification(nextState ? 'VPN Encendida' : 'VPN Apagada', 'success')
  } catch (err) {
    showNotification(getAxiosErr(err), 'error')
  } finally {
    isTogglingDesktop.value = false
  }
}

async function switchDesktopDevice(device) {
  if (desktopProfile.value.active_device === device) return
  isTogglingDesktop.value = true
  try {
    await api.post(`/vpns/desktop/${desktopProfile.value.id}/toggle`, {
      is_active: desktopProfile.value.is_active,
      active_device: device
    })
    desktopProfile.value.active_device = device
    showNotification(`Permiso transferido al ${device === 'mobile' ? 'Móvil' : 'Escritorio'}`, 'success')
  } catch (err) {
    showNotification(getAxiosErr(err), 'error')
  } finally {
    isTogglingDesktop.value = false
  }
}

async function revokeMobileKeys() {
  if (!confirm('¿Generar nuevo código QR? El móvil actual perderá acceso inmediatamente.')) return
  isTogglingDesktop.value = true
  try {
    const { data } = await api.post(`/vpns/desktop/${desktopProfile.value.id}/revoke-mobile`)
    desktopProfile.value.mobile_config_data = data.mobile_config_data
    desktopProfile.value.mobile_public_key = data.mobile_public_key
    showNotification('QR regenerado. El dispositivo anterior fue desconectado.', 'success')
  } catch (err) {
    showNotification(getAxiosErr(err), 'error')
  } finally {
    isTogglingDesktop.value = false
  }
}

// ==== FUNCIONES NORMALES ====
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

async function updateVpnRoutes(profile) {
  try {
    await api.put(`/vpns/${profile.id}`, {
      allowed_ips: profile.allowed_ips
    })
    showNotification('Rutas de servidor actualizadas', 'success')
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

const notification = ref({ show: false, message: '', type: '' })
function showNotification(msg, type = 'success') {
  notification.value = { show: true, message: msg, type }
  setTimeout(() => (notification.value.show = false), 4000)
}

let wsUnsubRot = null

onBeforeUnmount(() => {
  stopInspector()
  if (wsUnsubRot) removeWsListener(wsUnsubRot)
})

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
  await fetchChannels() 
  await fetchVpnProfiles()
  await checkDesktopStatus()

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
      <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 1rem;">
        <div>
          <h1>Gestión VPN</h1>
          <p>Administra los túneles WireGuard para tus dispositivos remotos.</p>
        </div>
        <button 
          :class="desktopProfile ? 'btn-outline-danger' : 'btn-outline-primary'" 
          @click="desktopProfile ? disableDesktopAccess() : enableDesktopAccess()" 
          :disabled="isEnablingDesktop"
          style="display: flex; align-items: center; gap: 8px; padding: 0.6rem 1.2rem; border-radius: 8px;"
        >
          <span v-if="isEnablingDesktop" class="spinner" style="margin: 0; width: 14px; height: 14px;"></span>
          <template v-else>
            <span>💻</span>
            {{ desktopProfile ? 'Eliminar Acceso a Apps' : 'Habilitar Acceso a Apps' }}
          </template>
        </button>
      </div>
    </div>

    <section v-if="desktopProfile" class="control-section auth-dynamic-panel">
      <div class="section-title">
        <i class="icon">📱</i>
        <h3>Acceso Seguro a Apps (Escritorio / Móvil)</h3>
        
        <div class="power-switch-container" style="margin-left: auto;">
          <label class="toggle-label" :class="{ 'text-disabled': isTogglingDesktop }">
            <span style="font-size: 0.85rem; color: var(--gray);">Permitir Conexión:</span>
            <input 
              type="checkbox" 
              :checked="desktopProfile.is_active" 
              @change="toggleDesktopPower" 
              :disabled="isTogglingDesktop"
            />
          </label>
        </div>
      </div>

      <div class="dynamic-auth-body" :class="{ 'is-disabled': !desktopProfile.is_active }">
        <p class="info-text">
          Selecciona en qué dispositivo quieres usar la VPN. Solo un dispositivo puede estar activo a la vez para garantizar el ruteo seguro.
        </p>

        <div class="device-switcher">
          <button 
            class="switch-btn" 
            :class="{ 'active': desktopProfile.active_device === 'desktop' }"
            @click="switchDesktopDevice('desktop')"
            :disabled="isTogglingDesktop || !desktopProfile.is_active"
          >
            💻 App de Escritorio
          </button>
          <button 
            class="switch-btn" 
            :class="{ 'active': desktopProfile.active_device === 'mobile' }"
            @click="switchDesktopDevice('mobile')"
            :disabled="isTogglingDesktop || !desktopProfile.is_active"
          >
            📱 App Móvil (QR)
          </button>
        </div>

        <transition name="fade">
          <div v-if="desktopProfile.active_device === 'mobile'" class="qr-container">
            <div class="qr-box">
              <qrcode-vue 
                v-if="desktopProfile.mobile_config_data" 
                :value="desktopProfile.mobile_config_data" 
                :size="180" 
                level="M" 
                render-as="svg" 
              />
              <span v-else class="spinner"></span>
            </div>
            <div class="qr-instructions">
              <h4>Cómo usar en tu móvil</h4>
              <ol>
                <li>Descarga la app oficial <strong>WireGuard</strong> (iOS / Android).</li>
                <li>Toca el botón <strong>+</strong> y selecciona <strong>"Escanear código QR"</strong>.</li>
                <li>Apunta la cámara a este código y ponle un nombre (ej. Monitor360).</li>
              </ol>
              <button 
                class="btn-danger small" 
                style="margin-top: 1rem; align-self: flex-start;" 
                @click="revokeMobileKeys"
                :disabled="isTogglingDesktop"
              >
                ⚠️ Revocar QR actual
              </button>
            </div>
          </div>
        </transition>

        <transition name="fade">
          <div v-if="desktopProfile.active_device === 'desktop'" class="desktop-instructions">
            <div class="status-box-ok">
              <span style="font-size: 1.5rem;">✅</span>
              <div>
                <h4>Permiso concedido a la App de Escritorio</h4>
                <p style="margin: 0; font-size: 0.9rem; color: var(--gray);">La aplicación de Windows ahora tiene acceso al túnel. Puedes ir allí y hacer clic en "Conectar".</p>
              </div>
            </div>
          </div>
        </transition>

      </div>
    </section>

    <section class="control-section">
      <div class="section-title">
        <i class="icon">🚀</i>
        <h3>Nuevo Cliente (Router)</h3>
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

        <div class="form-group">
          <label>Redes LAN a Enrutar (Pools)</label>
          <input
            v-model="newProfile.allowed_ips"
            type="text"
            placeholder="Ej: 192.168.80.0/24, 10.0.0.0/16"
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
        <h3>Perfiles Activos (Routers)</h3>
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
              <h4>⚙️ Configuración y Alertas</h4>
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

              <div class="form-group" style="margin-top: 1.2rem;">
                <label style="color: var(--blue);">Redes alcanzables (Rutas para acceso desde PC)</label>
                <div style="display: flex; gap: 0.5rem; margin-top: 0.2rem;">
                  <input type="text" v-model="p.allowed_ips" placeholder="Ej: 192.168.80.0/24" style="flex: 1;" />
                  <button class="btn-secondary" style="padding: 0 1.5rem;" @click="updateVpnRoutes(p)">💾 Guardar</button>
                </div>
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

    <div v-if="showLimitModal" class="modal-overlay" @click="showLimitModal = false">
      <div class="limit-modal" @click.stop>
        <div class="limit-icon">🛑</div>
        <h3>Límite Alcanzado</h3>
        <p>{{ limitMessage }}</p>
        <div class="limit-actions">
          <button class="btn-secondary" @click="showLimitModal = false">Entendido</button>
          <button class="btn-primary" @click="goToBilling">Ampliar mi Plan</button>
        </div>
      </div>
    </div>

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

/* ==== NUEVOS ESTILOS PARA AUTORIZACIÓN DINÁMICA ==== */
.auth-dynamic-panel {
  border-color: var(--blue);
  box-shadow: 0 0 15px rgba(59, 130, 246, 0.1);
}
.dynamic-auth-body {
  transition: opacity 0.3s;
}
.dynamic-auth-body.is-disabled {
  opacity: 0.4;
  pointer-events: none;
}
.info-text {
  font-size: 0.9rem;
  color: var(--gray);
  margin-bottom: 1.5rem;
}

.device-switcher {
  display: flex;
  background: rgba(0,0,0,0.2);
  border: 1px solid var(--primary-color);
  border-radius: 8px;
  overflow: hidden;
  margin-bottom: 1.5rem;
}
.switch-btn {
  flex: 1;
  padding: 1rem;
  background: transparent;
  color: var(--gray);
  border: none;
  font-size: 1rem;
  font-weight: bold;
  border-radius: 0;
  transition: all 0.2s;
}
.switch-btn.active {
  background: var(--blue);
  color: white;
}
.switch-btn:not(.active):hover {
  background: rgba(255,255,255,0.05);
}

.qr-container {
  display: flex;
  gap: 2rem;
  background: rgba(0,0,0,0.2);
  padding: 1.5rem;
  border-radius: 8px;
  border: 1px dashed var(--primary-color);
  align-items: center;
}
.qr-box {
  background: white;
  padding: 10px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 200px;
  min-height: 200px;
}
.qr-instructions h4 {
  margin-top: 0;
  color: var(--blue);
  margin-bottom: 1rem;
}
.qr-instructions ol {
  padding-left: 1.2rem;
  color: #ccc;
  line-height: 1.6;
}
.qr-instructions li {
  margin-bottom: 0.5rem;
}

.status-box-ok {
  display: flex;
  align-items: center;
  gap: 1rem;
  background: rgba(16, 185, 129, 0.1);
  border: 1px solid var(--green);
  padding: 1rem 1.5rem;
  border-radius: 8px;
}
.text-disabled {
  opacity: 0.5;
}

/* FORMULARIO CREACIÓN RESPONSIVE */
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

/* INPUT SELECT Y TOGGLES */
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
.btn-outline-primary {
  background-color: transparent;
  border: 1px solid var(--blue);
  color: var(--blue);
  padding: 0.5rem 1rem;
}
.btn-outline-primary:hover {
  background-color: rgba(59, 130, 246, 0.1);
}
.btn-outline-primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-outline-danger {
  background-color: transparent;
  border: 1px solid var(--red);
  color: var(--red);
  padding: 0.5rem 1rem;
}
.btn-outline-danger:hover {
  background-color: rgba(239, 68, 68, 0.1);
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

/* SECCIÓN INLINE DE ALERTAS */
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

/* --- MODAL DE LÍMITES --- */
.modal-overlay {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0, 0, 0, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
  backdrop-filter: blur(4px);
}
.limit-modal {
  background: var(--surface-color);
  border: 1px solid var(--red, #ef4444);
  padding: 2.5rem 2rem;
  border-radius: 16px;
  max-width: 420px;
  text-align: center;
  box-shadow: 0 10px 30px rgba(0,0,0,0.6);
}
.limit-modal h3 {
  color: var(--red, #ef4444);
  margin-bottom: 0.5rem;
  font-size: 1.4rem;
}
.limit-modal p {
  color: #d1d5db;
  line-height: 1.5;
}
.limit-icon {
  font-size: 3.5rem;
  margin-bottom: 1rem;
}
.limit-actions {
  display: flex;
  gap: 1rem;
  justify-content: center;
  margin-top: 2rem;
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

/* ANIMACION FADE */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
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
  .qr-container {
    flex-direction: column;
    text-align: center;
  }
  .qr-instructions ol {
    text-align: left;
  }
}
</style>