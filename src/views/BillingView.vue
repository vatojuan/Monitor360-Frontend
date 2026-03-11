<template>
  <div class="billing-container">
    <header class="billing-header">
      <h1>Suscripción y Límites</h1>
      <p>Mejorá tu plan para monitorear más dispositivos en tu red WISP.</p>
    </header>

    <div class="plans-grid">
      <div class="plan-card featured">
        <div class="badge">RECOMENDADO</div>
        <h3>Plan WISP Pro</h3>
        <div class="price">$29<span>/mes</span></div>
        <ul class="features">
          <li><span>✔️</span> Hasta 500 dispositivos</li>
          <li><span>✔️</span> Monitoreo cada 1 minuto</li>
          <li><span>✔️</span> Alertas por Telegram y Email</li>
          <li><span>✔️</span> Acceso a Terminal Remota</li>
          <li><span>✔️</span> Soporte prioritario</li>
        </ul>
        <button @click="checkoutPlan(1389240)" class="subscribe-btn" :disabled="isLoading">
          <span v-if="isLoading" class="loader"></span>
          {{ isLoading ? 'Conectando...' : 'Suscribirse al Plan Pro' }}
        </button>
      </div>
    </div>
    
    <div class="manage-section">
      <h3>¿Ya tenés una suscripción activa?</h3>
      <p>Gestioná tus facturas y métodos de pago de forma segura.</p>
      <button @click="openCustomerPortal" class="portal-btn">
        Ir al Portal de Facturación
      </button>
    </div>

    <div v-if="notification.show" class="notification" :class="notification.type">
      {{ notification.message }}
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { supabase } from '@/lib/supabase'

const isLoading = ref(false)
const notification = reactive({ show: false, message: '', type: 'success' })

const showNotify = (msg, type = 'success') => {
  notification.message = msg
  notification.type = type
  notification.show = true
  setTimeout(() => notification.show = false, 4000)
}

// Cambia esta URL por la IP o dominio de tu backend en Hetzner
const API_BASE = 'https://api.monitor360.media' 

const getAuthHeaders = async () => {
  const { data: { session } } = await supabase.auth.getSession()
  return {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${session?.access_token}`
  }
}

const checkoutPlan = async (variantId) => {
  if (variantId === '12345') {
    showNotify('Error: Debes configurar el Variant ID real de Lemon Squeezy.', 'error')
    return
  }

  isLoading.value = true
  try {
    const headers = await getAuthHeaders()
    // ⚠️ USAMOS API_BASE EN LUGAR DE LOCALHOST
    const res = await fetch(`${API_BASE}/checkout`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ variant_id: variantId })
    })
    
    if (!res.ok) throw new Error('Error al generar el link de pago')
    
    const data = await res.json()
    
    if (data.checkout_url) {
      // REDIRECCIÓN EXTERNA
      window.location.href = data.checkout_url
    } else {
      throw new Error('No se recibió la URL de pago')
    }
  } catch (err) {
    console.error('[Billing]', err)
    showNotify('No se pudo conectar con la pasarela de pagos.', 'error')
  } finally {
    isLoading.value = false
  }
}

const openCustomerPortal = async () => {
  try {
    const headers = await getAuthHeaders()
    const res = await fetch(`${API_BASE}/portal`, {
      method: 'GET',
      headers
    })
    
    if (!res.ok) throw new Error('Error al obtener el portal')
    
    const data = await res.json()
    window.open(data.portal_url, '_blank')
  } catch (err) {
    console.error(err)
    showNotify('Aún no tenés un perfil de facturación activo.', 'error')
  }
}
</script>

<style scoped>
.billing-container {
  padding: 2rem;
  max-width: 900px;
  margin: 0 auto;
  color: var(--font-color, #e0e0e0);
}

.billing-header {
  text-align: center;
  margin-bottom: 3rem;
}

.billing-header h1 {
  font-size: 2.5rem;
  color: var(--green, #3ddc84);
  margin-bottom: 0.5rem;
}

.plans-grid {
  display: flex;
  justify-content: center;
  gap: 2rem;
  margin-bottom: 4rem;
}

.plan-card {
  background: var(--surface-color, #16213e);
  border: 1px solid var(--primary-color, #0f3460);
  padding: 2.5rem;
  border-radius: 16px;
  text-align: center;
  width: 100%;
  max-width: 400px;
  position: relative;
  transition: transform 0.3s ease;
}

.plan-card:hover {
  transform: translateY(-5px);
}

.plan-card.featured {
  border-color: var(--green, #3ddc84);
  box-shadow: 0 10px 30px rgba(61, 220, 132, 0.1);
}

.badge {
  position: absolute;
  top: -12px;
  left: 50%;
  transform: translateX(-50%);
  background: var(--green, #3ddc84);
  color: #0b1220;
  padding: 4px 12px;
  border-radius: 20px;
  font-size: 0.75rem;
  font-weight: bold;
}

.price {
  font-size: 3rem;
  font-weight: 800;
  margin: 1.5rem 0;
  color: white;
}

.price span {
  font-size: 1.2rem;
  color: var(--gray, #8d8d8d);
}

.features {
  list-style: none;
  padding: 0;
  text-align: left;
  margin: 2rem 0;
}

.features li {
  margin-bottom: 1rem;
  display: flex;
  gap: 10px;
  font-size: 1rem;
}

.subscribe-btn {
  background-color: var(--green, #3ddc84);
  color: #0b1220;
  border: none;
  padding: 1rem;
  border-radius: 12px;
  width: 100%;
  cursor: pointer;
  font-weight: 700;
  font-size: 1.1rem;
  transition: opacity 0.2s;
}

.subscribe-btn:hover:not(:disabled) {
  opacity: 0.9;
}

.subscribe-btn:disabled {
  background-color: var(--gray, #8d8d8d);
  cursor: not-allowed;
}

.manage-section {
  background: rgba(255, 255, 255, 0.03);
  padding: 2rem;
  border-radius: 12px;
  text-align: center;
  border: 1px dashed var(--primary-color, #0f3460);
}

.portal-btn {
  margin-top: 1rem;
  background-color: transparent;
  color: var(--blue, #5372f0);
  border: 1px solid var(--blue, #5372f0);
  padding: 10px 24px;
  border-radius: 8px;
  cursor: pointer;
  font-weight: 600;
}

.portal-btn:hover {
  background: rgba(83, 114, 240, 0.1);
}

.notification {
  position: fixed;
  bottom: 20px;
  right: 20px;
  padding: 1rem 1.5rem;
  border-radius: 8px;
  color: white;
  font-weight: bold;
  z-index: 9999;
}
.notification.error { background: #f87171; }
.notification.success { background: #3ddc84; }

@media (max-width: 600px) {
  .billing-container { padding: 1rem; }
  .plan-card { padding: 1.5rem; }
}
</style>