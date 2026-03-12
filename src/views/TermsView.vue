<template>
  <div class="legal-page">
    <div class="legal-card">
      <header class="legal-header">
        <h1>Términos y Condiciones de Uso</h1>
        <p class="last-updated">Última actualización: 10 de marzo de 2026</p>
      </header>

      <section class="legal-content">
        <p>
          Bienvenido a <strong>Monitor360</strong>. Al utilizar nuestra plataforma, usted acepta los siguientes términos que rigen la relación entre el usuario y Monitor360.
        </p>

        <div class="legal-section">
          <h3>1. Descripción del Servicio</h3>
          <p>
            Monitor360 es una plataforma SaaS diseñada para el monitoreo, gestión y diagnóstico de dispositivos de red (principalmente MikroTik) mediante protocolos de API y SSH. El servicio se aloja en servidores de alta disponibilidad y utiliza tecnología de túneles cifrados para la gestión remota.
          </p>
        </div>

        <div class="legal-section">
          <h3>2. Registro y Facturación</h3>
          <ul>
            <li><strong>Autenticación:</strong> El acceso se realiza mediante Supabase Auth, permitiendo el registro mediante correo electrónico o Google OAuth.</li>
            <li><strong>Procesamiento de Pagos:</strong> Monitor360 utiliza a <strong>Lemon Squeezy</strong> como su <em>Merchant of Record</em> oficial. Al realizar un pago, usted acepta los términos de procesamiento de Lemon Squeezy.</li>
            <li><strong>Gestión de Suscripciones:</strong> Las suscripciones pueden ser canceladas o modificadas en cualquier momento a través del Portal del Cliente proporcionado por la pasarela.</li>
          </ul>
        </div>

        <div class="legal-section">
          <h3>3. Uso de la Terminal Remota (SSH)</h3>
          <p>
            El servicio de Terminal Remota permite al usuario ejecutar comandos directamente en sus dispositivos gestionados.
          </p>
          <p>
            Monitor360 actúa únicamente como un puente de comunicación cifrado. El usuario es el único responsable de los comandos ejecutados y de las consecuencias que estos puedan tener en su infraestructura. No almacenamos el contenido de las sesiones para preservar su privacidad.
          </p>
        </div>

        <div class="legal-section">
          <h3>4. Conectividad WireGuard® y VPN</h3>
          <p>
            Monitor360 ofrece funcionalidades de conectividad basadas en el protocolo WireGuard para facilitar el acceso a dispositivos detrás de firewalls o NAT.
          </p>
          <ul>
            <li><strong>Propósito:</strong> Los túneles VPN deben ser utilizados exclusivamente para la gestión y monitoreo de dispositivos de red.</li>
            <li><strong>Seguridad:</strong> El usuario es responsable de la custodia de las claves privadas generadas. Monitor360 gestiona la infraestructura del servidor y la asignación de IPs privadas.</li>
            <li><strong>Prohibiciones:</strong> Queda estrictamente prohibido el uso de los túneles para tráfico ilícito, ataques de denegación de servicio (DDoS) o cualquier actividad que viole las leyes internacionales.</li>
          </ul>
        </div>

        <div class="legal-section">
          <h3>5. Gestión de Credenciales</h3>
          <p>
            Monitor360 almacena credenciales de dispositivos necesarias para el monitoreo. Todas las contraseñas se almacenan cifradas utilizando estándares de grado industrial y el acceso está restringido únicamente al propietario de la cuenta.
          </p>
        </div>

        <div class="legal-section">
          <h3>6. Limitación de Responsabilidad</h3>
          <p>
            Monitor360 se proporciona "tal cual". No garantizamos que el servicio sea ininterrumpido. No seremos responsables por daños directos o indirectos, incluyendo la pérdida de conectividad debido a fallos de hardware o comandos de terminal mal ejecutados.
          </p>
        </div>

        <div class="legal-section">
          <h3>7. Contacto</h3>
          <p>
            Para cualquier duda o reclamación técnica, puede contactarnos en: 
            <a href="mailto:support@monitorwisp.com">support@monitorwisp.com</a>
          </p>
        </div>
      </section>

      <footer class="legal-footer">
        <button @click="$router.push('/login')" class="btn-back">Volver al Inicio</button>
      </footer>
    </div>
  </div>
</template>

<script setup>
// No se requiere lógica adicional para esta vista estática
</script>

<style scoped>
.legal-page {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  padding: 2rem;
  background-color: #0e1628; /* Fondo muy oscuro para contraste */
}

.legal-card {
  background: #16213e;
  border: 1px solid #0f3460;
  border-radius: 12px;
  padding: 2.5rem;
  max-width: 900px;
  width: 100%;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
  color: #e0e0e0;
}

.legal-header {
  text-align: center;
  margin-bottom: 2rem;
  border-bottom: 1px solid #1a2a4a;
  padding-bottom: 1.5rem;
}

.legal-header h1 {
  color: #3ddc84; /* Verde característico */
  font-size: 2rem;
  margin: 0;
}

.last-updated {
  font-size: 0.9rem;
  color: #9aa0a6;
  margin-top: 0.5rem;
}

.legal-content {
  line-height: 1.6;
  font-size: 1rem;
}

.legal-section {
  margin-top: 2rem;
}

.legal-section h3 {
  color: #6ab4ff;
  font-size: 1.25rem;
  margin-bottom: 0.75rem;
  border-left: 4px solid #6ab4ff;
  padding-left: 10px;
}

.legal-section ul {
  padding-left: 1.5rem;
}

.legal-section li {
  margin-bottom: 0.5rem;
}

.legal-section a {
  color: #6ab4ff;
  text-decoration: none;
}

.legal-footer {
  margin-top: 3rem;
  text-align: center;
}

.btn-back {
  background: transparent;
  border: 1px solid #3ddc84;
  color: #3ddc84;
  padding: 0.75rem 2rem;
  border-radius: 8px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-back:hover {
  background: #3ddc84;
  color: white;
}

/* Responsivo */
@media (max-width: 600px) {
  .legal-card {
    padding: 1.5rem;
  }
  .legal-header h1 {
    font-size: 1.5rem;
  }
}
</style>