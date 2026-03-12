<template>
  <div class="account-container">
    <header class="account-header">
      <h1>Mi Cuenta</h1>
      <p>Gestiona tu perfil personal, preferencias y revisa el consumo de tu plan actual.</p>
    </header>

    <transition name="fade">
      <div v-if="notification.show" :class="['m360-toast', notification.type]">
        {{ notification.message }}
      </div>
    </transition>

    <div v-if="isLoading" class="initial-loader">
      <span class="loader"></span> Cargando información de tu cuenta...
    </div>

    <div v-else class="account-grid">
      
      <section class="account-card">
        <div class="card-header">
          <h2>Perfil WISP</h2>
          <p>Tus datos personales o los de tu empresa.</p>
        </div>

        <div class="card-body">
          <div class="avatar-section">
            <div class="avatar-preview">
              <img v-if="profile.avatar_url" :src="profile.avatar_url" alt="Avatar" />
              <span v-else>{{ (profile.email || 'U').slice(0, 1).toUpperCase() }}</span>
            </div>
            <div class="avatar-actions">
              <button class="btn-secondary" @click="triggerFileInput" :disabled="isUploading">
                <span v-if="isUploading" class="spinner-small"></span>
                {{ isUploading ? 'Subiendo...' : 'Cambiar Logo' }}
              </button>
              <input 
                type="file" 
                ref="fileInputRef" 
                accept="image/*" 
                style="display: none;" 
                @change="handleFileUpload"
              />
              <p class="helper-text">Sube una imagen cuadrada (Max 2MB).</p>
            </div>
          </div>

          <div class="form-group">
            <label>Nombre Completo / Empresa</label>
            <input type="text" v-model="profile.full_name" placeholder="Ej: WISP Network" />
          </div>

          <div class="form-group">
            <label>Correo Electrónico</label>
            <input 
              type="email" 
              v-model="profile.email" 
              :disabled="provider === 'google'" 
              :class="{ 'is-disabled': provider === 'google' }"
            />
            <small v-if="provider === 'google'" class="helper-text text-warning">
              Iniciaste sesión con Google. El correo no se puede modificar.
            </small>
            <small v-else class="helper-text">
              Si modificas el correo, deberás verificarlo mediante un enlace que te enviaremos.
            </small>
          </div>

          <div class="form-group" v-if="provider !== 'google'">
            <label>Contraseña</label>
            <button class="btn-secondary" style="width: fit-content;" @click="resetPassword" :disabled="isResettingPassword">
              <span v-if="isResettingPassword" class="spinner-small"></span>
              {{ isResettingPassword ? 'Enviando correo...' : '🔒 Restablecer Contraseña' }}
            </button>
          </div>

          <button class="btn-primary" @click="saveProfile" :disabled="isSaving" style="margin-top: 10px;">
            {{ isSaving ? 'Guardando...' : 'Guardar Cambios' }}
          </button>
        </div>
      </section>

      <div class="right-column">
        
        <section class="account-card">
          <div class="card-header">
            <h2>Preferencias Regionales</h2>
          </div>
          <div class="card-body">
            <div class="form-group">
              <label>Idioma</label>
              <select v-model="profile.language">
                <option value="es">Español</option>
                <option value="en">English (Próximamente)</option>
                <option value="pt">Português (Próximamente)</option>
              </select>
            </div>

            <div class="form-group">
              <label>Zona Horaria</label>
              <select v-model="profile.timezone">
                <option :value="profile.timezone">{{ profile.timezone }}</option>
              </select>
              <small class="helper-text">Detectada automáticamente por tu navegador.</small>
            </div>
            
            <button class="btn-primary" @click="saveProfile" :disabled="isSaving">
              {{ isSaving ? 'Guardando...' : 'Guardar Preferencias' }}
            </button>
          </div>
        </section>

        <section class="account-card limits-card">
          <div class="card-header">
            <h2>Consumo del Plan</h2>
            <span :class="['status-badge', billing.status]">{{ billing.status.toUpperCase() }}</span>
          </div>
          
          <div class="card-body">
            <div class="progress-section">
              <div class="progress-labels">
                <span class="progress-title">Dispositivos Registrados</span>
                <span class="progress-count">{{ billing.devices.current }} / {{ billing.devices.max }}</span>
              </div>
              <div class="progress-bar-bg">
                <div class="progress-bar-fill devices-fill" :style="{ width: devicesPercentage + '%' }"></div>
              </div>
            </div>

            <div class="progress-section">
              <div class="progress-labels">
                <span class="progress-title">Perfiles VPN (Wireguard)</span>
                <span class="progress-count">{{ billing.vpns.current }} / {{ billing.vpns.max }}</span>
              </div>
              <div class="progress-bar-bg">
                <div class="progress-bar-fill vpns-fill" :style="{ width: vpnsPercentage + '%' }"></div>
              </div>
            </div>

            <div class="billing-action">
              <button class="portal-btn" @click="goToBilling">
                💳 Gestionar Facturación y Límites
              </button>
            </div>
          </div>
        </section>

        <section class="account-card danger-zone">
          <div class="card-header">
            <h2 class="text-danger">Zona de Peligro</h2>
          </div>
          <div class="card-body">
            <p class="danger-text">
              Eliminar tu cuenta cancelará cualquier suscripción activa y borrará permanentemente todos tus datos, dispositivos y configuraciones.
            </p>
            <button class="btn-danger" @click="openDeleteModal">Eliminar Cuenta</button>
          </div>
        </section>

      </div>
    </div>

    <transition name="fade">
      <div v-if="showDeleteModal" class="modal-overlay" @click.self="closeDeleteModal">
        <div class="modal-content danger-modal">
          <h3>¿Estás completamente seguro?</h3>
          <p>
            Esta acción es irreversible. Para confirmar que deseas eliminar tu cuenta permanentemente, 
            escribe la palabra <strong>ELIMINAR</strong> en el siguiente campo:
          </p>
          <div class="form-group">
            <input 
              type="text" 
              v-model="deleteConfirmationText" 
              placeholder="ELIMINAR" 
              class="danger-input"
            />
          </div>
          <div class="modal-actions">
            <button class="btn-secondary" @click="closeDeleteModal" :disabled="isDeleting">Cancelar</button>
            <button class="btn-danger" @click="deleteAccount" :disabled="isDeleting || deleteConfirmationText !== 'ELIMINAR'">
              <span v-if="isDeleting" class="spinner-small"></span>
              {{ isDeleting ? 'Eliminando...' : 'Sí, Eliminar Cuenta' }}
            </button>
          </div>
        </div>
      </div>
    </transition>

  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import api from '@/lib/api'
import { supabase } from '@/lib/supabase'

const router = useRouter()

// Estados Generales
const isLoading = ref(true)
const isSaving = ref(false)
const isUploading = ref(false)
const isResettingPassword = ref(false) // Nuevo estado para contraseña
const notification = ref({ show: false, message: '', type: 'success' })

const fileInputRef = ref(null)

// Estados para Eliminación de Cuenta
const showDeleteModal = ref(false)
const deleteConfirmationText = ref('')
const isDeleting = ref(false)

// Estructura de Datos
const originalEmail = ref('') // Guardamos el correo original para detectar cambios
const profile = ref({
  id: '',
  full_name: '',
  email: '',
  avatar_url: '',
  language: 'es',
  timezone: ''
})
const provider = ref('email')
const billing = ref({
  status: 'active',
  devices: { current: 0, max: 10 },
  vpns: { current: 0, max: 1 }
})

// Porcentajes Computados para las Barras
const devicesPercentage = computed(() => {
  if (billing.value.devices.max === 0) return 0
  const pct = (billing.value.devices.current / billing.value.devices.max) * 100
  return pct > 100 ? 100 : pct
})

const vpnsPercentage = computed(() => {
  if (billing.value.vpns.max === 0) return 0
  const pct = (billing.value.vpns.current / billing.value.vpns.max) * 100
  return pct > 100 ? 100 : pct
})

const showNotification = (message, type = 'success') => {
  notification.value = { show: true, message, type }
  setTimeout(() => (notification.value.show = false), 4000)
}

// 1. Cargar Datos
const fetchAccountData = async () => {
  isLoading.value = true
  try {
    const { data } = await api.get('/account/me')
    
    profile.value = data.profile || profile.value
    originalEmail.value = profile.value.email // Guardamos correo actual
    provider.value = data.provider
    billing.value = data.billing

    // Magia Silenciosa: Detectar Zona Horaria y Actualizar si difiere
    const browserTz = Intl.DateTimeFormat().resolvedOptions().timeZone
    if (profile.value.timezone !== browserTz) {
      profile.value.timezone = browserTz
      api.patch('/account/me', { timezone: browserTz }).catch(e => console.error("Error silente TZ:", e))
    }

  } catch (error) {
    console.error('Error al cargar la cuenta:', error)
    showNotification('Error al cargar los datos de la cuenta.', 'error')
  } finally {
    isLoading.value = false
  }
}

// 2. Guardar Cambios (Nombre, Correo, Idioma, etc)
const saveProfile = async () => {
  isSaving.value = true
  try {
    let emailMessage = ''
    
    // Si el usuario modificó el correo y no es de Google, notificamos a Supabase
    if (provider.value !== 'google' && profile.value.email !== originalEmail.value) {
      const { error: authError } = await supabase.auth.updateUser({ email: profile.value.email })
      
      if (authError) throw authError
      
      emailMessage = ' Se ha enviado un enlace de confirmación a tu nueva dirección de correo.'
      originalEmail.value = profile.value.email // Evitamos múltiples envíos
    }

    // Guardamos el resto de las preferencias en nuestro Backend
    await api.patch('/account/me', {
      full_name: profile.value.full_name,
      language: profile.value.language,
      timezone: profile.value.timezone
    })
    
    showNotification(`Perfil actualizado correctamente.${emailMessage}`)
  } catch (error) {
    console.error('Error guardando perfil:', error)
    const errorMsg = error.message || 'Error al guardar los cambios.'
    showNotification(errorMsg, 'error')
  } finally {
    isSaving.value = false
  }
}

// 3. Restablecer Contraseña
const resetPassword = async () => {
  isResettingPassword.value = true
  try {
    // Supabase envía el correo al email original (por seguridad)
    const { error } = await supabase.auth.resetPasswordForEmail(originalEmail.value)
    if (error) throw error
    
    showNotification('Te hemos enviado un correo con instrucciones para cambiar tu contraseña.')
  } catch (error) {
    console.error('Error enviando reseteo:', error)
    showNotification('Error al enviar el correo. Inténtalo de nuevo más tarde.', 'error')
  } finally {
    isResettingPassword.value = false
  }
}

// 4. Subir Avatar a Supabase Storage Directamente
const triggerFileInput = () => {
  fileInputRef.value.click()
}

const handleFileUpload = async (event) => {
  const file = event.target.files[0]
  if (!file) return

  if (file.size > 2 * 1024 * 1024) { // 2MB Limit
    showNotification('La imagen es muy grande. Máximo 2MB.', 'error')
    return
  }

  isUploading.value = true
  try {
    const fileExt = file.name.split('.').pop()
    const fileName = `${profile.value.id}-${Date.now()}.${fileExt}`
    const filePath = `public/${fileName}`

    const { error: uploadError } = await supabase.storage
      .from('avatars')
      .upload(filePath, file, { cacheControl: '3600', upsert: true })

    if (uploadError) throw uploadError

    const { data: urlData } = supabase.storage
      .from('avatars')
      .getPublicUrl(filePath)

    const publicUrl = urlData.publicUrl

    await api.patch('/account/me', { avatar_url: publicUrl })
    
    profile.value.avatar_url = publicUrl
    showNotification('Logo actualizado correctamente.')

  } catch (error) {
    console.error('Error subiendo imagen:', error)
    showNotification('Error al subir la imagen. Verifica tu conexión.', 'error')
  } finally {
    isUploading.value = false
    event.target.value = ''
  }
}

// 5. Lógica de Eliminación de Cuenta
const openDeleteModal = () => {
  deleteConfirmationText.value = ''
  showDeleteModal.value = true
}

const closeDeleteModal = () => {
  if (isDeleting.value) return
  showDeleteModal.value = false
}

const deleteAccount = async () => {
  if (deleteConfirmationText.value !== 'ELIMINAR') return
  isDeleting.value = true
  try {
    await api.delete('/account/me')
    
    showNotification('Cuenta eliminada correctamente. Redirigiendo...', 'success')
    
    await supabase.auth.signOut()
    localStorage.clear()
    sessionStorage.clear()
    
    setTimeout(() => {
      router.push('/login')
    }, 2000)

  } catch (error) {
    console.error('Error eliminando cuenta:', error)
    const errorMsg = error.response?.data?.detail || 'Ocurrió un error. Por favor contacta a soporte.'
    showNotification(errorMsg, 'error')
    closeDeleteModal()
  } finally {
    isDeleting.value = false
  }
}

const goToBilling = () => {
  router.push('/billing')
}

onMounted(() => {
  fetchAccountData()
})
</script>

<style scoped>
/* ========================================================= */
/* VARIABLES Y CONTENEDOR PRINCIPAL                          */
/* ========================================================= */
.account-container {
  max-width: 1100px;
  margin: 0 auto;
  padding: 20px;
  color: #c9d1d9;
}

.account-header {
  margin-bottom: 30px;
}
.account-header h1 {
  font-size: 24px;
  color: #ffffff;
  margin-bottom: 5px;
}
.account-header p {
  color: #8b949e;
  font-size: 14px;
}

/* ========================================================= */
/* GRID Y TARJETAS                                           */
/* ========================================================= */
.account-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 25px;
  align-items: start;
}

@media (max-width: 860px) {
  .account-grid {
    grid-template-columns: 1fr;
  }
}

.right-column {
  display: flex;
  flex-direction: column;
  gap: 25px;
}

.account-card {
  background-color: var(--surface-color, #161b22);
  border: 1px solid var(--primary-color, #30363d);
  border-radius: 12px;
  overflow: hidden;
}

.card-header {
  padding: 18px 20px;
  border-bottom: 1px solid var(--primary-color, #30363d);
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.card-header h2 {
  font-size: 16px;
  color: #e6edf3;
  margin: 0;
}
.card-header p {
  font-size: 12px;
  color: #8b949e;
  margin: 4px 0 0 0;
}

.card-body {
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* ========================================================= */
/* AVATAR UPLOAD SECCIÓN                                     */
/* ========================================================= */
.avatar-section {
  display: flex;
  align-items: center;
  gap: 20px;
  padding-bottom: 20px;
  border-bottom: 1px solid var(--primary-color, #30363d);
}

.avatar-preview {
  width: 72px;
  height: 72px;
  border-radius: 50%;
  background: #21262d;
  border: 2px solid var(--blue, #5372f0);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 28px;
  font-weight: bold;
  color: #c9d1d9;
  overflow: hidden;
}
.avatar-preview img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.avatar-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

/* ========================================================= */
/* FORMULARIOS                                               */
/* ========================================================= */
.form-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.form-group label {
  font-size: 13px;
  font-weight: 600;
  color: #8b949e;
}
.form-group input,
.form-group select {
  padding: 10px 12px;
  background-color: #0d1117;
  border: 1px solid var(--primary-color, #30363d);
  border-radius: 6px;
  color: #c9d1d9;
  font-family: inherit;
  transition: border-color 0.2s;
}
.form-group input:focus,
.form-group select:focus {
  outline: none;
  border-color: var(--blue, #5372f0);
}
.is-disabled {
  opacity: 0.6;
  cursor: not-allowed;
  background-color: #21262d !important;
}

.helper-text {
  font-size: 11px;
  color: #8b949e;
  margin: 0;
}
.text-warning {
  color: #d29922;
}

/* ========================================================= */
/* BARRAS DE PROGRESO (Consumo)                              */
/* ========================================================= */
.limits-card .card-body {
  gap: 25px;
}

.progress-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.progress-labels {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
  font-weight: 600;
}
.progress-title {
  color: #c9d1d9;
}
.progress-count {
  color: #8b949e;
}

.progress-bar-bg {
  height: 8px;
  background: #21262d;
  border-radius: 4px;
  overflow: hidden;
}
.progress-bar-fill {
  height: 100%;
  border-radius: 4px;
  transition: width 0.5s ease-out;
}
.devices-fill {
  background: var(--blue, #5372f0);
}
.vpns-fill {
  background: var(--green, #238636);
}

.status-badge {
  padding: 4px 10px;
  border-radius: 12px;
  font-size: 10px;
  font-weight: bold;
}
.status-badge.active { background: rgba(35, 134, 54, 0.2); color: #3fb950; border: 1px solid #238636; }
.status-badge.past_due { background: rgba(210, 153, 34, 0.2); color: #d29922; border: 1px solid #d29922; }
.status-badge.canceled { background: rgba(248, 81, 73, 0.2); color: #ff7b72; border: 1px solid #f85149; }

/* ========================================================= */
/* BOTONES Y ZONA DE PELIGRO                                 */
/* ========================================================= */
.btn-primary {
  background: var(--blue, #5372f0);
  color: white;
  border: none;
  padding: 10px 16px;
  border-radius: 6px;
  font-weight: 600;
  cursor: pointer;
  align-self: flex-start;
  transition: opacity 0.2s;
}
.btn-primary:hover:not(:disabled) {
  opacity: 0.9;
}
.btn-secondary {
  background: transparent;
  color: #c9d1d9;
  border: 1px solid #30363d;
  padding: 8px 14px;
  border-radius: 6px;
  font-weight: 600;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 8px;
}
.btn-secondary:hover:not(:disabled) {
  background: rgba(255,255,255,0.05);
}
.btn-primary:disabled, .btn-secondary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.billing-action {
  margin-top: 10px;
  border-top: 1px dashed var(--primary-color, #30363d);
  padding-top: 20px;
}
.portal-btn {
  width: 100%;
  background-color: transparent;
  color: var(--blue, #5372f0);
  border: 1px solid var(--blue, #5372f0);
  padding: 12px;
  border-radius: 8px;
  cursor: pointer;
  font-weight: 600;
  transition: background 0.2s;
}
.portal-btn:hover {
  background: rgba(83, 114, 240, 0.1);
}

.danger-zone {
  border-color: #7b1e1c;
}
.text-danger {
  color: #ff7b72 !important;
}
.danger-text {
  font-size: 13px;
  color: #8b949e;
  line-height: 1.5;
}
.btn-danger {
  background: #da3633;
  color: white;
  border: 1px solid #da3633;
  padding: 10px 16px;
  border-radius: 6px;
  font-weight: 600;
  cursor: pointer;
  align-self: flex-start;
  display: flex;
  align-items: center;
  gap: 8px;
  transition: opacity 0.2s;
}
.btn-danger:hover:not(:disabled) {
  background: #b62324;
  border-color: #b62324;
}
.btn-danger:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* ========================================================= */
/* MODAL DE CONFIRMACIÓN                                     */
/* ========================================================= */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  background: rgba(0, 0, 0, 0.75);
  backdrop-filter: blur(3px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2000;
}
.modal-content {
  background: #161b22;
  border: 1px solid #30363d;
  border-radius: 12px;
  padding: 24px;
  width: 90%;
  max-width: 440px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  box-shadow: 0 12px 28px rgba(0,0,0,0.6);
}
.danger-modal {
  border-top: 4px solid #da3633;
}
.danger-modal h3 {
  margin: 0;
  color: #ff7b72;
  font-size: 18px;
}
.danger-modal p {
  margin: 0;
  color: #c9d1d9;
  font-size: 14px;
  line-height: 1.5;
}
.danger-input {
  text-transform: uppercase;
}
.danger-input:focus {
  border-color: #da3633 !important;
  box-shadow: 0 0 0 1px #da3633;
}
.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 10px;
}

/* ========================================================= */
/* SPINNERS & TOASTS                                         */
/* ========================================================= */
.initial-loader {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 15px;
  height: 200px;
  color: #8b949e;
}
.loader {
  width: 24px;
  height: 24px;
  border: 3px solid rgba(255,255,255,0.1);
  border-bottom-color: var(--blue, #5372f0);
  border-radius: 50%;
  animation: rotation 1s linear infinite;
}
.spinner-small {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255,255,255,0.3);
  border-bottom-color: white;
  border-radius: 50%;
  animation: rotation 1s linear infinite;
}
@keyframes rotation {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.m360-toast {
  position: fixed;
  bottom: 24px;
  right: 24px;
  padding: 12px 20px;
  border-radius: 8px;
  color: #fff;
  font-size: 14px;
  font-weight: 500;
  z-index: 1000;
  box-shadow: 0 4px 12px rgba(0,0,0,0.15);
}
.m360-toast.success { background-color: var(--green, #238636); }
.m360-toast.error { background-color: #da3633; }

.fade-enter-active, .fade-leave-active { transition: opacity 0.3s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>