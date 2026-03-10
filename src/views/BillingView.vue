<template>
  <div class="billing-container">
    <h1>Suscripción y Límites</h1>
    <p>Mejora tu plan para monitorear más dispositivos en tu red.</p>

    <div class="plans-grid">
      <div class="plan-card">
        <h3>Plan WISP Pro</h3>
        <div class="price">$29<span>/mes</span></div>
        <ul class="features">
          <li>✔️ Hasta 500 dispositivos</li>
          <li>✔️ Monitoreo cada 1 minuto</li>
          <li>✔️ Alertas por Telegram y Email</li>
          <li>✔️ Acceso a Terminal Remota</li>
        </ul>
        <button @click="checkoutPlan('12345')" class="subscribe-btn" :disabled="isLoading">
          {{ isLoading ? 'Procesando...' : 'Suscribirse al Plan Pro' }}
        </button>
      </div>
    </div>
    
    <hr class="divider" />
    
    <div class="manage-section">
      <h3>¿Ya tienes una suscripción?</h3>
      <button @click="openCustomerPortal" class="portal-btn">
        Gestionar Métodos de Pago y Facturas
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { supabase } from '@/lib/supabase'

const isLoading = ref(false)

// Función para obtener el JWT actual de Supabase y enviarlo a tu backend
const getAuthHeaders = async () => {
  const { data: { session } } = await supabase.auth.getSession()
  return {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${session?.access_token}`
  }
}

// Llama al endpoint /checkout que armamos en tu backend
const checkoutPlan = async (variantId) => {
  isLoading.value = true
  try {
    const headers = await getAuthHeaders()
    const res = await fetch('http://localhost:8000/checkout', {
      method: 'POST',
      headers,
      body: JSON.stringify({ plan_id: variantId })
    })
    
    if (!res.ok) throw new Error('Error al generar el pago')
    
    const data = await res.json()
    // Redirigir al usuario a Lemon Squeezy para que ponga la tarjeta
    window.location.href = data.checkout_url
  } catch (err) {
    console.error(err)
    alert('Hubo un error al conectar con el sistema de pagos.')
  } finally {
    isLoading.value = false
  }
}

// Llama al endpoint /portal para gestionar la tarjeta
const openCustomerPortal = async () => {
  try {
    const headers = await getAuthHeaders()
    const res = await fetch('http://localhost:8000/portal', {
      method: 'GET',
      headers
    })
    
    if (!res.ok) throw new Error('Error al obtener el portal')
    
    const data = await res.json()
    window.open(data.portal_url, '_blank')
  } catch (err) {
    console.error(err)
    alert('Aún no tienes un perfil de facturación activo.')
  }
}
</script>

<style scoped>
.billing-container {
  padding: 2rem;
  max-width: 800px;
  margin: 0 auto;
}
.plans-grid {
  display: flex;
  gap: 20px;
  margin-top: 2rem;
}
.plan-card {
  border: 1px solid #e5e7eb;
  padding: 2rem;
  border-radius: 8px;
  text-align: center;
  background: white;
  flex: 1;
}
.price {
  font-size: 2rem;
  font-weight: bold;
  margin: 1rem 0;
}
.price span {
  font-size: 1rem;
  color: #6b7280;
}
.features {
  list-style: none;
  padding: 0;
  text-align: left;
  margin-bottom: 2rem;
}
.features li {
  margin-bottom: 0.5rem;
  color: #374151;
}
.subscribe-btn {
  background-color: #10B981;
  color: white;
  border: none;
  padding: 10px 20px;
  border-radius: 4px;
  width: 100%;
  cursor: pointer;
  font-weight: bold;
}
.subscribe-btn:hover { background-color: #059669; }
.divider { margin: 3rem 0; border: 0; border-top: 1px solid #e5e7eb; }
.portal-btn {
  background-color: #f3f4f6;
  color: #374151;
  border: 1px solid #d1d5db;
  padding: 10px 20px;
  border-radius: 4px;
  cursor: pointer;
}
.portal-btn:hover { background-color: #e5e7eb; }
</style>