<template>
  <div class="billing-container">
    <header class="billing-header">
      <h1>Suscripción y Límites</h1>
      <p>Ajustá tu plan para monitorear todos los dispositivos de tu red WISP.</p>
    </header>

    <div class="plans-grid">
      <div class="plan-card featured">
        <div class="badge">PLAN WISP PRO</div>
        
        <div class="price-display">
          <div class="price">${{ totalPrice }}<span> USD/mes</span></div>
        </div>

        <ul class="features">
          <li><span>✔️</span> Monitoreo y automatizaciones IA</li>
          <li><span>✔️</span> Alertas por Telegram</li>
          <li><span>✔️</span> Soporte prioritario</li>
        </ul>

        <div class="sliders-section">
          <div class="slider-group">
            <div class="slider-header">
              <label>Límite de Dispositivos</label>
              <span class="slider-value">{{ formatDevices(totalDevices) }} equipos</span>
            </div>
            <input 
              type="range" 
              class="styled-slider"
              min="0" 
              max="4" 
              step="1" 
              v-model.number="extraDevices"
            />
            <div class="slider-marks">
              <span>1K (Base)</span>
              <span>5K (Máx)</span>
            </div>
          </div>

          <div class="slider-group">
            <div class="slider-header">
              <label>Túneles VPN Dedicados</label>
              <span class="slider-value">{{ totalVpns }} VPN{{ totalVpns > 1 ? 's' : '' }}</span>
            </div>
            <input 
              type="range" 
              class="styled-slider vpn-slider"
              min="0" 
              max="5" 
              step="1" 
              v-model.number="extraVpns"
            />
            <div class="slider-marks">
              <span>1 (Base)</span>
              <span>6 (Máx)</span>
            </div>
          </div>
        </div>

        <button @click="checkoutPlan" class="subscribe-btn" :disabled="isLoading">
          <span v-if="isLoading" class="loader"></span>
          {{ isLoading ? 'Generando Pago Seguro...' : 'Suscribirse Ahora' }}
        </button>
      </div>
    </div>
    
    <div class="manage-section">
      <h3>¿Ya tenés una suscripción activa?</h3>
      <p>Gestioná tus facturas, métodos de pago y descarga tus comprobantes.</p>
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
import { ref, reactive, computed } from 'vue'
import { supabase } from '@/lib/supabase'

const isLoading = ref(false)
const notification = reactive({ show: false, message: '', type: 'success' })

// Lógica de cálculo dinámico
const extraDevices = ref(0) // 0 significa solo el plan base
const extraVpns = ref(0)    // 0 significa solo el plan base

const totalDevices = computed(() => 1000 + (extraDevices.value * 1000))
const totalVpns = computed(() => 1 + extraVpns.value)

const totalPrice = computed(() => {
  const base = 29
  const addonsDev = extraDevices.value * 15
  const addonsVpn = extraVpns.value * 10
  return base + addonsDev + addonsVpn
})

const formatDevices = (num) => {
  return new Intl.NumberFormat('es-AR').format(num)
}

const showNotify = (msg, type = 'success') => {
  notification.message = msg
  notification.type = type
  notification.show = true
  setTimeout(() => notification.show = false, 4000)
}

const isProd = import.meta.env.PROD || window.location.hostname !== 'localhost'
const API_BASE = isProd ? 'https://api.monitor360.media' : 'http://localhost:8000'

const getAuthHeaders = async () => {
  const { data: { session } } = await supabase.auth.getSession()
  return {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${session?.access_token}`
  }
}

// La función ya no necesita recibir un variantId porque el backend lo calcula
const checkoutPlan = async () => {
  isLoading.value = true
  try {
    const headers = await getAuthHeaders()
    
    const res = await fetch(`${API_BASE}/billing/checkout`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ 
        extra_devices: extraDevices.value,
        extra_vpns: extraVpns.value
      })
    })
    
    if (!res.ok) {
        const errData = await res.json()
        // Mostramos el mensaje de error que el backend nos envía (ej: "Plan no configurado")
        throw new Error(errData.detail || `Error ${res.status}: ${res.statusText}`)
    }
    
    const data = await res.json()
    
    if (data.checkout_url) {
      window.location.href = data.checkout_url
    } else {
      throw new Error('No se recibió la URL de pago desde el backend')
    }
  } catch (err) {
    console.error('[Billing Error]', err)
    showNotify(err.message || 'No se pudo conectar con la pasarela de pagos. Verifica la consola.', 'error')
  } finally {
    isLoading.value = false
  }
}

const openCustomerPortal = async () => {
  try {
    const headers = await getAuthHeaders()
    
    const res = await fetch(`${API_BASE}/billing/portal`, {
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
  margin-bottom: 4rem;
}

.plan-card {
  background: var(--surface-color, #16213e);
  border: 1px solid var(--primary-color, #0f3460);
  padding: 2.5rem;
  border-radius: 16px;
  width: 100%;
  max-width: 480px;
  position: relative;
  transition: transform 0.3s ease;
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
  padding: 4px 16px;
  border-radius: 20px;
  font-size: 0.8rem;
  font-weight: bold;
  letter-spacing: 0.5px;
}

.price-display {
  text-align: center;
  padding-bottom: 1.5rem;
  margin-bottom: 1.5rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  margin-top: 1rem;
}
.price {
  font-size: 3.5rem;
  font-weight: 800;
  color: white;
  line-height: 1;
}
.price span {
  font-size: 1.2rem;
  color: var(--gray, #8d8d8d);
  font-weight: 600;
}

.features {
  list-style: none;
  padding: 0;
  margin: 0 0 2rem 0;
}
.features li {
  margin-bottom: 0.8rem;
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 1rem;
  color: #d1d5db;
}

/* --- SLIDERS INTERACTIVOS --- */
.sliders-section {
  background: rgba(0, 0, 0, 0.2);
  border-radius: 12px;
  padding: 1.5rem;
  margin-bottom: 2rem;
  border: 1px solid rgba(255,255,255,0.05);
}

.slider-group {
  margin-bottom: 1.5rem;
}
.slider-group:last-child {
  margin-bottom: 0;
}

.slider-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}
.slider-header label {
  font-size: 0.95rem;
  font-weight: 600;
  color: #9ca3af;
}
.slider-value {
  background: var(--blue, #5372f0);
  color: white;
  padding: 2px 8px;
  border-radius: 6px;
  font-size: 0.85rem;
  font-weight: bold;
}

.styled-slider {
  -webkit-appearance: none;
  width: 100%;
  height: 6px;
  border-radius: 5px;
  background: #374151;
  outline: none;
  margin-bottom: 8px;
}
.styled-slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: var(--green, #3ddc84);
  cursor: pointer;
  transition: transform 0.1s;
}
.styled-slider.vpn-slider::-webkit-slider-thumb {
  background: #a78bfa; /* Color distinto para diferenciar la VPN */
}
.styled-slider::-webkit-slider-thumb:hover {
  transform: scale(1.2);
}

.slider-marks {
  display: flex;
  justify-content: space-between;
  font-size: 0.75rem;
  color: #6b7280;
  font-weight: 600;
}

/* Botones */
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
  transition: all 0.2s;
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 10px;
}
.subscribe-btn:hover:not(:disabled) {
  opacity: 0.9;
  transform: translateY(-2px);
}
.subscribe-btn:disabled {
  background-color: #374151;
  color: #9ca3af;
  cursor: not-allowed;
  transform: none;
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
  transition: background 0.2s;
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
.notification.error { background: #ef4444; }
.notification.success { background: #10b981; }

@media (max-width: 600px) {
  .billing-container { padding: 1rem; }
  .plan-card { padding: 1.5rem; }
  .price { font-size: 2.8rem; }
}
</style>