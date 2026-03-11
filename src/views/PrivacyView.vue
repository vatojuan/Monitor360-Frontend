<template>
  <div class="legal-page">
    <div class="legal-card">
      <header class="legal-header">
        <h1>Política de Privacidad</h1>
        <p class="last-updated">Última actualización: 10 de marzo de 2026</p>
      </header>

      <section class="legal-content">
        <p>
          En <strong>Monitor360</strong>, la privacidad y la seguridad de los datos de nuestros usuarios son nuestra máxima prioridad. Esta política detalla cómo recopilamos, usamos y protegemos su información.
        </p>

        <div class="legal-section">
          <h3>1. Información que Recopilamos</h3>
          <ul>
            <li><strong>Datos de Cuenta:</strong> Dirección de correo electrónico y nombre completo proporcionados durante el registro manual o a través de Google OAuth.</li>
            <li><strong>Datos de Red:</strong> Para el funcionamiento del servicio, almacenamos direcciones IP, nombres de identidad de dispositivos, modelos y estadísticas de rendimiento.</li>
            <li><strong>Credenciales de Dispositivos:</strong> Nombres de usuario y contraseñas necesarios para la conexión vía API o SSH, los cuales se almacenan bajo estrictos protocolos de cifrado.</li>
          </ul>
        </div>

        <div class="legal-section">
          <h3>2. Uso de los Datos de Google</h3>
          <p>
            Al utilizar el inicio de sesión con Google, Monitor360 accede únicamente a su dirección de correo electrónico y nombre de perfil para la creación y autenticación de su cuenta.
          </p>
          <p>
            No accedemos, recopilamos ni compartimos sus contactos, archivos, fotos ni ninguna otra información privada de su cuenta de Google.
          </p>
        </div>

        <div class="legal-section">
          <h3>3. Finalidad del Tratamiento</h3>
          <p>Utilizamos su información exclusivamente para:</p>
          <ul>
            <li>Proveer el servicio de monitoreo y gestión de red en tiempo real.</li>
            <li>Gestionar su suscripción y límites según el plan contratado.</li>
            <li>Enviar alertas críticas de red configuradas por usted.</li>
            <li>Garantizar la seguridad de las sesiones de Terminal y túneles VPN.</li>
          </ul>
        </div>

        <div class="legal-section">
          <h3>4. Compartición de Datos con Terceros</h3>
          <p>
            Monitor360 no vende sus datos a terceros. Solo compartimos la información mínima necesaria con proveedores esenciales:
          </p>
          <ul>
            <li><strong>Lemon Squeezy:</strong> Procesa sus datos de pago y facturación como nuestro Merchant of Record oficial.</li>
            <li><strong>Supabase:</strong> Provee la infraestructura de autenticación y base de datos segura.</li>
          </ul>
        </div>

        <div class="legal-section">
          <h3>5. Seguridad y Almacenamiento</h3>
          <p>
            Su información se aloja en servidores seguros ubicados en <strong>Hetzner (Alemania)</strong> y en bases de datos cifradas de Supabase. Aplicamos cifrado de grado industrial para proteger las contraseñas de sus dispositivos y las sesiones de terminal.
          </p>
        </div>

        <div class="legal-section">
          <h3>6. Sus Derechos</h3>
          <p>
            Usted tiene derecho a acceder, corregir o eliminar sus datos personales en cualquier momento. Puede solicitar la eliminación total de su cuenta y toda la información asociada desde el panel de configuración o enviando un correo a soporte.
          </p>
        </div>

        <div class="legal-section">
          <h3>7. Contacto</h3>
          <p>
            Para consultas sobre su privacidad, contáctenos en: 
            <a href="mailto:soporte@monitor360.media">soporte@monitor360.media</a>
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
// Componente estático informativo
</script>

<style scoped>
.legal-page {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  padding: 2rem;
  background-color: #0e1628;
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
  color: #3ddc84;
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

@media (max-width: 600px) {
  .legal-card {
    padding: 1.5rem;
  }
  .legal-header h1 {
    font-size: 1.5rem;
  }
}
</style>