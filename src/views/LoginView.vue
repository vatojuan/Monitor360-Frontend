<script setup>
import { ref, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { supabase } from '@/lib/supabase'

const router = useRouter()
const route = useRoute()

const authMode = ref('login') // 'login' | 'signup' | 'forgot'
const email = ref('')
const password = ref('')
const showPassword = ref(false)
const isAuthLoading = ref(false)
const notification = ref({ show: false, message: '', type: 'success' })

function showNotification(message, type = 'success', ttl = 4000) {
  notification.value = { show: true, message, type }
  setTimeout(() => (notification.value.show = false), ttl)
}

function destAfterLogin() {
  const q = route.query?.redirect
  return typeof q === 'string' && q.length > 0 ? q : '/'
}

// Auto-redirección si ya está logueado
onMounted(async () => {
  const { data } = await supabase.auth.getSession()
  if (data.session) {
    router.replace(destAfterLogin())
  }
})

async function handleAuthSubmit() {
  if (isAuthLoading.value) return
  
  if (authMode.value === 'forgot') {
    if (!email.value?.trim()) {
      showNotification('Por favor, ingresá tu email.', 'error')
      return
    }
    isAuthLoading.value = true
    try {
      const { error } = await supabase.auth.resetPasswordForEmail(email.value.trim(), {
        // Redirige a la página de reseteo de tu app (Asegúrate de configurarlo en Supabase)
        redirectTo: new URL('/reset-password', window.location.origin).href, 
      })
      if (error) throw error
      showNotification('Te enviamos un email con las instrucciones para recuperar tu contraseña.', 'success', 6000)
      authMode.value = 'login'
    } catch (err) {
      console.error('[Reset Password]', err)
      showNotification(err?.message || 'Error al solicitar el cambio de contraseña.', 'error')
    } finally {
      isAuthLoading.value = false
    }
    return
  }

  if (!email.value?.trim() || !password.value) {
    showNotification('Completá email y password.', 'error')
    return
  }
  
  isAuthLoading.value = true

  try {
    if (authMode.value === 'login') {
      const { data, error } = await supabase.auth.signInWithPassword({
        email: email.value.trim(),
        password: password.value,
      })
      if (error) {
        const code = error?.message?.toLowerCase?.() || ''
        if (code.includes('email not confirmed') || code.includes('email_not_confirmed')) {
          throw new Error('Tu email no está confirmado. Revisá tu bandeja y confirmá la cuenta.')
        }
        if (code.includes('invalid login') || code.includes('invalid_credentials')) {
          throw new Error('Credenciales inválidas. Verificá tu email y password.')
        }
        throw error
      }

      showNotification('Sesión iniciada ✔', 'success', 1200)
      router.replace(destAfterLogin()) // replace para no volver al login con "atrás"
    } else {
      const { error } = await supabase.auth.signUp({
        email: email.value.trim(),
        password: password.value,
      })
      if (error) throw error
      showNotification(
        'Cuenta creada. Te enviamos un email para confirmar la dirección. Revisá tu bandeja.',
        'success',
        6000,
      )
      authMode.value = 'login'
    }
  } catch (err) {
    console.error('[Auth]', err)
    showNotification(err?.message || 'Error de autenticación.', 'error')
  } finally {
    isAuthLoading.value = false
  }
}

async function handleGoogleAuth() {
  if (isAuthLoading.value) return
  isAuthLoading.value = true
  
  try {
    const { error } = await supabase.auth.signInWithOAuth({
      provider: 'google',
      options: {
        // Uso de API URL nativa para evitar dobles barras que rompen OAuth
        redirectTo: new URL(destAfterLogin(), window.location.origin).href
      }
    })
    if (error) throw error
  } catch (err) {
    console.error('[Google Auth]', err)
    showNotification(err?.message || 'Error al conectar con Google.', 'error')
    isAuthLoading.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <div class="login-card">
      <h2>
        <template v-if="authMode === 'login'">Iniciar sesión</template>
        <template v-else-if="authMode === 'signup'">Crear cuenta</template>
        <template v-else>Recuperar contraseña</template>
      </h2>

      <p v-if="authMode === 'forgot'" class="text-muted" style="margin-bottom: 1.5rem; font-size: 0.9rem;">
        Ingresá tu correo electrónico y te enviaremos un enlace para restablecer tu contraseña.
      </p>

      <form @submit.prevent="handleAuthSubmit" class="login-form" autocomplete="on">
        <label for="email" class="sr-only">Email</label>
        <input
          id="email"
          type="email"
          v-model.trim="email"
          placeholder="tu@email.com"
          required
          autocomplete="email"
          inputmode="email"
        />

        <template v-if="authMode !== 'forgot'">
          <label for="password" class="sr-only">Password</label>
          <div class="password-row">
            <input
              id="password"
              :type="showPassword ? 'text' : 'password'"
              v-model="password"
              placeholder="••••••••"
              required
              :autocomplete="authMode === 'login' ? 'current-password' : 'new-password'"
            />
            <button
              type="button"
              class="btn-eye"
              @click="showPassword = !showPassword"
              :aria-pressed="showPassword"
              aria-label="Mostrar/Ocultar password"
            >
              {{ showPassword ? '🙈' : '👁️' }}
            </button>
          </div>
          
          <div v-if="authMode === 'login'" class="forgot-link-wrapper">
            <a href="#" @click.prevent="authMode = 'forgot'" class="forgot-link">¿Olvidaste tu contraseña?</a>
          </div>
        </template>

        <button type="submit" class="btn-primary" :disabled="isAuthLoading">
          <span v-if="isAuthLoading" class="loader"></span>
          <span v-else>
            <template v-if="authMode === 'login'">Entrar</template>
            <template v-else-if="authMode === 'signup'">Registrarme</template>
            <template v-else>Enviar Enlace</template>
          </span>
        </button>
        
        <button v-if="authMode === 'forgot'" type="button" class="btn-secondary" @click="authMode = 'login'" :disabled="isAuthLoading" style="margin-top: 0.5rem;">
          Volver al Login
        </button>
      </form>

      <div v-if="authMode !== 'forgot'">
        <div class="divider">
          <span>O</span>
        </div>

        <button type="button" class="btn-google" @click="handleGoogleAuth" :disabled="isAuthLoading">
          <svg class="google-icon" viewBox="0 0 24 24">
            <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
            <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
            <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
            <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
          </svg>
          Continuar con Google
        </button>
        
        <p class="switch-mode">
          <span v-if="authMode === 'login'">
            ¿No tenés cuenta?
            <a href="#" @click.prevent="authMode = 'signup'">Crear cuenta</a>
          </span>
          <span v-else>
            ¿Ya tenés cuenta?
            <a href="#" @click.prevent="authMode = 'login'">Iniciar sesión</a>
          </span>
        </p>
      </div>
    </div>

    <div v-if="notification.show" class="notification" :class="notification.type">
      {{ notification.message }}
    </div>
  </div>
</template>

<style scoped>
.login-page {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: calc(100vh - 120px);
  padding: 2rem;
}
.login-card {
  background: var(--surface-color, #16213e);
  border: 1px solid var(--primary-color, #0f3460);
  border-radius: 12px;
  padding: 2.5rem 2rem;
  max-width: 420px;
  width: 100%;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
  text-align: center;
}
.login-card h2 {
  margin-bottom: 1.5rem;
  color: var(--font-color, #e0e0e0);
  font-size: 1.6rem;
}
.text-muted {
  color: #9aa0a6;
}
.login-form {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}
.login-form input {
  width: 100%;
  background: #0e0e0e;
  color: #eaeaea;
  border: 1px solid #2a2a2a;
  border-radius: 8px;
  padding: 0.8rem;
  font-size: 0.95rem;
}
.login-form input:focus {
  outline: none;
  border-color: var(--blue, #5372f0);
}
.password-row {
  position: relative;
  display: flex;
  align-items: center;
}
.password-row input {
  padding-right: 3rem;
}
.btn-eye {
  position: absolute;
  right: 0.35rem;
  border: none;
  background: transparent;
  color: #9aa0a6;
  font-size: 1.1rem;
  cursor: pointer;
  padding: 0.25rem 0.5rem;
}
.btn-eye:hover {
  opacity: 0.8;
}
.forgot-link-wrapper {
  text-align: right;
  margin-top: -0.5rem;
  margin-bottom: 0.5rem;
}
.forgot-link {
  color: #6ab4ff;
  font-size: 0.85rem;
  text-decoration: none;
}
.forgot-link:hover {
  text-decoration: underline;
}

.btn-primary {
  background: var(--green, #3ddc84);
  border: none;
  border-radius: 8px;
  color: #0b1220;
  font-weight: 700;
  padding: 0.8rem;
  cursor: pointer;
  transition: background 0.2s;
  display: flex;
  justify-content: center;
  align-items: center;
}
.btn-primary:hover:not(:disabled) {
  background: #32c176;
}
.btn-primary:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.btn-secondary {
  background: transparent;
  border: 1px solid var(--primary-color, #0f3460);
  border-radius: 8px;
  color: var(--font-color, #e0e0e0);
  font-weight: 600;
  padding: 0.8rem;
  cursor: pointer;
  transition: background 0.2s;
}
.btn-secondary:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.05);
}

/* Spinner animado */
.loader {
  display: inline-block;
  width: 20px;
  height: 20px;
  border: 3px solid rgba(0, 0, 0, 0.3);
  border-top-color: #0b1220;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

/* ESTILOS AÑADIDOS PARA GOOGLE */
.divider {
  display: flex;
  align-items: center;
  text-align: center;
  margin: 1.5rem 0;
  color: #6b7280;
  font-size: 0.9rem;
}
.divider::before,
.divider::after {
  content: '';
  flex: 1;
  border-bottom: 1px solid #2a2a2a;
}
.divider span {
  padding: 0 10px;
}
.btn-google {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  background: white;
  color: #333;
  border: none;
  border-radius: 8px;
  font-weight: 600;
  padding: 0.8rem;
  width: 100%;
  cursor: pointer;
  transition: background 0.2s;
}
.btn-google:hover:not(:disabled) {
  background: #f1f1f1;
}
.btn-google:disabled {
  opacity: 0.7;
  cursor: default;
}
.google-icon {
  width: 20px;
  height: 20px;
}
/* FIN ESTILOS GOOGLE */

.switch-mode {
  margin-top: 1.5rem;
  color: #9aa0a6;
  font-size: 0.9rem;
}
.switch-mode a {
  color: #6ab4ff;
  cursor: pointer;
  text-decoration: none;
  font-weight: 600;
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
  background: #2ea043;
}
.notification.error {
  background: #d9534f;
}
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  border: 0;
}
</style>