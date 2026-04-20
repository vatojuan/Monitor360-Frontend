<template>
  <div class="landing-page">

    <!-- ======================== NAVBAR ======================== -->
    <header class="l-nav" :class="{ scrolled: isScrolled }">
      <div class="l-nav-inner">
        <a href="/" class="l-logo">
          <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
            <circle cx="14" cy="14" r="12" stroke="url(#logo-g)" stroke-width="1.8"/>
            <circle cx="14" cy="14" r="5" fill="url(#logo-g)"/>
            <line x1="14" y1="2" x2="14" y2="7" stroke="url(#logo-g)" stroke-width="1.8" stroke-linecap="round"/>
            <line x1="14" y1="21" x2="14" y2="26" stroke="url(#logo-g)" stroke-width="1.8" stroke-linecap="round"/>
            <line x1="2" y1="14" x2="7" y2="14" stroke="url(#logo-g)" stroke-width="1.8" stroke-linecap="round"/>
            <line x1="21" y1="14" x2="26" y2="14" stroke="url(#logo-g)" stroke-width="1.8" stroke-linecap="round"/>
            <defs>
              <linearGradient id="logo-g" x1="0" y1="0" x2="28" y2="28" gradientUnits="userSpaceOnUse">
                <stop stop-color="#5372f0"/>
                <stop offset="1" stop-color="#3ddc84"/>
              </linearGradient>
            </defs>
          </svg>
          <span>MonitorWISP</span>
        </a>

        <nav class="l-nav-links" :class="{ open: mobileMenuOpen }">
          <a href="#features" @click="closeMobileMenu">Características</a>
          <a href="#how-it-works" @click="closeMobileMenu">Cómo funciona</a>
          <a href="#pricing" @click="closeMobileMenu">Precios</a>
        </nav>

        <div class="l-nav-cta">
          <router-link to="/login" class="l-btn l-btn-ghost">Ingresar</router-link>
          <router-link to="/login" class="l-btn l-btn-primary">Crear Cuenta</router-link>
        </div>

        <button class="l-hamburger" @click="mobileMenuOpen = !mobileMenuOpen" :class="{ active: mobileMenuOpen }">
          <span></span><span></span><span></span>
        </button>
      </div>
    </header>

    <!-- ======================== HERO ======================== -->
    <section class="l-hero">
      <div class="l-hero-inner">
        <div class="l-hero-content">
          <div class="l-badge">
            <span class="l-badge-dot"></span>
            Monitoreo cada 10 segundos · Tiempo real
          </div>
          <h1 class="l-hero-title">
            Detectá problemas en tu red<br>
            <span class="l-gradient-text">antes de que llamen tus clientes</span>
          </h1>
          <p class="l-hero-sub">
            Monitoreá, gestioná y diagnosticá toda tu red WISP desde un solo panel — sin abrir
            puertos, sin VPN externa y con un copiloto de IA que te ayuda a resolver los
            problemas en segundos.
          </p>
          <ul class="l-hero-bullets">
            <li>
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><circle cx="8" cy="8" r="7" stroke="#3ddc84" stroke-width="1.5"/><path d="M5 8l2 2 4-4" stroke="#3ddc84" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>
              <span>Descubrimiento automático de toda tu red</span>
            </li>
            <li>
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><circle cx="8" cy="8" r="7" stroke="#3ddc84" stroke-width="1.5"/><path d="M5 8l2 2 4-4" stroke="#3ddc84" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>
              <span>Acceso remoto a equipos detrás de NAT sin abrir puertos</span>
            </li>
            <li>
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><circle cx="8" cy="8" r="7" stroke="#3ddc84" stroke-width="1.5"/><path d="M5 8l2 2 4-4" stroke="#3ddc84" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>
              <span>Reportes ejecutivos generados por IA cada mañana</span>
            </li>
            <li>
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><circle cx="8" cy="8" r="7" stroke="#3ddc84" stroke-width="1.5"/><path d="M5 8l2 2 4-4" stroke="#3ddc84" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>
              <span>Terminal remota con copiloto IA integrado</span>
            </li>
          </ul>
          <div class="l-hero-actions">
            <router-link to="/login" class="l-btn l-btn-primary l-btn-lg">
              Crear Cuenta
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M3 8h10M9 4l4 4-4 4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>
            </router-link>
            <a href="#features" class="l-btn l-btn-ghost l-btn-lg">Ver Características</a>
          </div>
          <div class="l-hero-proof">
            <div class="l-proof-item">
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><circle cx="7" cy="7" r="6" stroke="#3ddc84" stroke-width="1.5"/><path d="M4 7l2.5 2.5L10 5" stroke="#3ddc84" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
              Confiado por WISPs e ISPs en Latinoamérica
            </div>
            <div class="l-proof-item">
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><circle cx="7" cy="7" r="6" stroke="#3ddc84" stroke-width="1.5"/><path d="M4 7l2.5 2.5L10 5" stroke="#3ddc84" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
              Sin contratos, sin configuración compleja
            </div>
          </div>
        </div>

        <!-- REALISTIC DEVICE CARD MOCK -->
        <div class="l-hero-visual">
          <div class="l-card-glow"></div>
          <div class="l-mock-card">
            <div class="l-mock-card-header">
              <div class="l-mock-card-title-area">
                <div class="l-mock-status-dot ok"></div>
                <div>
                  <div class="l-mock-device-name">Router-Core-01</div>
                  <div class="l-mock-device-sub">192.168.88.1</div>
                </div>
              </div>
              <div class="l-mock-card-badges">
                <span class="l-mock-badge group">Producción</span>
                <span class="l-mock-badge ok">OK</span>
              </div>
              <div class="l-mock-card-actions">
                <span class="l-mock-action-btn">⚙</span>
                <span class="l-mock-action-btn">↓</span>
              </div>
            </div>

            <!-- SENSOR: PING -->
            <div class="l-mock-sensor ok">
              <div class="l-mock-sensor-top">
                <div class="l-mock-sensor-left">
                  <span class="l-mock-sensor-dot ok"></span>
                  <span class="l-mock-sensor-name">Ping Principal</span>
                  <span class="l-mock-sensor-type">ping</span>
                </div>
                <span class="l-mock-sensor-status ok">OK</span>
              </div>
              <div class="l-mock-sensor-metrics">
                <span class="l-mock-metric"><span class="l-mock-metric-label">Latencia</span><span class="l-mock-metric-value ok">8 ms</span></span>
                <span class="l-mock-metric"><span class="l-mock-metric-label">Pérdida PKT</span><span class="l-mock-metric-value ok">0%</span></span>
                <span class="l-mock-metric"><span class="l-mock-metric-label">Uptime</span><span class="l-mock-metric-value">99.8%</span></span>
              </div>
            </div>

            <!-- SENSOR: ETHERNET -->
            <div class="l-mock-sensor ok">
              <div class="l-mock-sensor-top">
                <div class="l-mock-sensor-left">
                  <span class="l-mock-sensor-dot ok"></span>
                  <span class="l-mock-sensor-name">Ethernet ether1</span>
                  <span class="l-mock-sensor-type">ethernet</span>
                </div>
                <span class="l-mock-sensor-status ok">OK</span>
              </div>
              <div class="l-mock-sensor-metrics">
                <span class="l-mock-metric"><span class="l-mock-metric-label">RX</span><span class="l-mock-metric-value ok">45.2 Mbps</span></span>
                <span class="l-mock-metric"><span class="l-mock-metric-label">TX</span><span class="l-mock-metric-value ok">12.8 Mbps</span></span>
                <span class="l-mock-metric"><span class="l-mock-metric-label">Errores</span><span class="l-mock-metric-value">0</span></span>
              </div>
            </div>

            <!-- SENSOR: WIRELESS -->
            <div class="l-mock-sensor warning">
              <div class="l-mock-sensor-top">
                <div class="l-mock-sensor-left">
                  <span class="l-mock-sensor-dot warning"></span>
                  <span class="l-mock-sensor-name">Wireless wlan1</span>
                  <span class="l-mock-sensor-type">wireless</span>
                </div>
                <span class="l-mock-sensor-status warning">DEGRADADO</span>
              </div>
              <div class="l-mock-sensor-metrics">
                <span class="l-mock-metric"><span class="l-mock-metric-label">CCQ</span><span class="l-mock-metric-value warning">79%</span></span>
                <span class="l-mock-metric"><span class="l-mock-metric-label">RSSI</span><span class="l-mock-metric-value warning">–72 dBm</span></span>
                <span class="l-mock-metric"><span class="l-mock-metric-label">Clientes</span><span class="l-mock-metric-value">14</span></span>
              </div>
            </div>

            <!-- SENSOR: SYSTEM -->
            <div class="l-mock-sensor ok">
              <div class="l-mock-sensor-top">
                <div class="l-mock-sensor-left">
                  <span class="l-mock-sensor-dot ok"></span>
                  <span class="l-mock-sensor-name">Sistema</span>
                  <span class="l-mock-sensor-type">system</span>
                </div>
                <span class="l-mock-sensor-status ok">OK</span>
              </div>
              <div class="l-mock-sensor-metrics">
                <span class="l-mock-metric"><span class="l-mock-metric-label">CPU</span><span class="l-mock-metric-value ok">23%</span></span>
                <span class="l-mock-metric"><span class="l-mock-metric-label">RAM</span><span class="l-mock-metric-value ok">41%</span></span>
                <span class="l-mock-metric"><span class="l-mock-metric-label">Temp</span><span class="l-mock-metric-value">52 °C</span></span>
              </div>
            </div>

            <div class="l-mock-card-footer">
              <span class="l-mock-realtime-dot"></span>
              Actualizando en tiempo real · hace 3s
            </div>
          </div>

          <!-- Second card peek -->
          <div class="l-mock-card l-mock-card-peek critical">
            <div class="l-mock-card-header">
              <div class="l-mock-card-title-area">
                <div class="l-mock-status-dot critical"></div>
                <div>
                  <div class="l-mock-device-name">AP-Sector-Norte</div>
                  <div class="l-mock-device-sub">192.168.88.12</div>
                </div>
              </div>
              <div class="l-mock-card-badges">
                <span class="l-mock-badge group">Torre-A</span>
                <span class="l-mock-badge critical">CRÍTICO</span>
              </div>
            </div>
            <div class="l-mock-sensor critical">
              <div class="l-mock-sensor-top">
                <div class="l-mock-sensor-left">
                  <span class="l-mock-sensor-dot critical"></span>
                  <span class="l-mock-sensor-name">Ping Principal</span>
                </div>
                <span class="l-mock-sensor-status critical">TIMEOUT</span>
              </div>
              <div class="l-mock-sensor-metrics">
                <span class="l-mock-metric"><span class="l-mock-metric-label">Latencia</span><span class="l-mock-metric-value critical">— ms</span></span>
                <span class="l-mock-metric"><span class="l-mock-metric-label">Pérdida PKT</span><span class="l-mock-metric-value critical">100%</span></span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- ======================== COMPATIBILITY BAR ======================== -->
    <section class="l-compat">
      <div class="l-compat-inner">
        <span class="l-compat-label">Compatible con</span>
        <div class="l-compat-items">
          <div class="l-compat-item">
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none"><rect x="1" y="1" width="16" height="16" rx="3" stroke="#5372f0" stroke-width="1.4"/><path d="M5 9h8M9 5v8" stroke="#5372f0" stroke-width="1.4" stroke-linecap="round"/></svg>
            MikroTik
          </div>
          <span class="l-compat-sep">·</span>
          <div class="l-compat-item">
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none"><circle cx="9" cy="9" r="7" stroke="#5372f0" stroke-width="1.4"/><path d="M9 5v4l3 2" stroke="#5372f0" stroke-width="1.4" stroke-linecap="round"/></svg>
            Ubiquiti
          </div>
          <span class="l-compat-sep">·</span>
          <div class="l-compat-item">
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none"><rect x="2" y="4" width="14" height="10" rx="2" stroke="#5372f0" stroke-width="1.4"/><path d="M6 8h6M6 11h4" stroke="#5372f0" stroke-width="1.4" stroke-linecap="round"/></svg>
            Linux / SSH
          </div>
          <span class="l-compat-sep">·</span>
          <div class="l-compat-item">
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none"><path d="M4 9a5 5 0 0 1 10 0" stroke="#5372f0" stroke-width="1.4" stroke-linecap="round"/><path d="M2 9a7 7 0 0 1 14 0" stroke="#5372f0" stroke-width="1.4" stroke-linecap="round" opacity=".4"/><circle cx="9" cy="9" r="2" fill="#5372f0"/></svg>
            WireGuard VPN
          </div>
          <span class="l-compat-sep">·</span>
          <div class="l-compat-item">
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none"><rect x="1" y="5" width="16" height="8" rx="2" stroke="#5372f0" stroke-width="1.4"/><path d="M5 9h.01M9 9h.01M13 9h.01" stroke="#5372f0" stroke-width="2" stroke-linecap="round"/></svg>
            Dispositivos SSH genéricos
          </div>
        </div>
        <span class="l-compat-note">Conexión directa · Dispositivo sonda · Acceso seguro detrás de NAT</span>
      </div>
    </section>

    <!-- ======================== PROBLEM / SOLUTION ======================== -->
    <section class="l-section l-problem-solution">
      <div class="l-container">
        <div class="l-ps-grid">
          <div class="l-ps-problem">
            <div class="l-section-eyebrow">El problema</div>
            <h2 class="l-section-title">¿Tu red falla y te enterás cuando ya llamaron los clientes?</h2>
            <div class="l-problem-list">
              <div class="l-problem-item">
                <div class="l-problem-icon">
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><circle cx="8" cy="8" r="7" stroke="#e94560" stroke-width="1.5"/><path d="M8 4v5M8 11v1" stroke="#e94560" stroke-width="1.8" stroke-linecap="round"/></svg>
                </div>
                <div>
                  <strong>Sin visibilidad en tiempo real</strong>
                  <p>No sabés si un enlace wireless se degradó o si el CPU de un router está al límite hasta que es demasiado tarde.</p>
                </div>
              </div>
              <div class="l-problem-item">
                <div class="l-problem-icon">
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><circle cx="8" cy="8" r="7" stroke="#e94560" stroke-width="1.5"/><path d="M8 4v5M8 11v1" stroke="#e94560" stroke-width="1.8" stroke-linecap="round"/></svg>
                </div>
                <div>
                  <strong>Alertas tardías o inexistentes</strong>
                  <p>Herramientas genéricas que no entienden RouterOS API ni las métricas específicas de redes WISP.</p>
                </div>
              </div>
              <div class="l-problem-item">
                <div class="l-problem-icon">
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><circle cx="8" cy="8" r="7" stroke="#e94560" stroke-width="1.5"/><path d="M8 4v5M8 11v1" stroke="#e94560" stroke-width="1.8" stroke-linecap="round"/></svg>
                </div>
                <div>
                  <strong>Acceso remoto inseguro</strong>
                  <p>Abrir puertos en routers distribuidos o usar VPNs complejas solo para revisar una interfaz.</p>
                </div>
              </div>
            </div>
          </div>
          <div class="l-ps-solution">
            <div class="l-section-eyebrow solution">La solución</div>
            <h2 class="l-section-title">MonitorWISP detecta el problema. Vos lo resolvés.</h2>
            <div class="l-solution-list">
              <div class="l-solution-item">
                <div class="l-solution-icon">
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><circle cx="8" cy="8" r="7" stroke="#3ddc84" stroke-width="1.5"/><path d="M5 8l2.5 2.5L11 6" stroke="#3ddc84" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>
                </div>
                <span>Sondeo cada <strong>10 segundos</strong>, dashboard en vivo sin refrescar</span>
              </div>
              <div class="l-solution-item">
                <div class="l-solution-icon">
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><circle cx="8" cy="8" r="7" stroke="#3ddc84" stroke-width="1.5"/><path d="M5 8l2.5 2.5L11 6" stroke="#3ddc84" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>
                </div>
                <span>Alerta en <strong>Telegram</strong> antes de que llegue el reclamo</span>
              </div>
              <div class="l-solution-item">
                <div class="l-solution-icon">
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><circle cx="8" cy="8" r="7" stroke="#3ddc84" stroke-width="1.5"/><path d="M5 8l2.5 2.5L11 6" stroke="#3ddc84" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>
                </div>
                <span><strong>VPN WireGuard</strong> integrada — acceso remoto sin abrir puertos</span>
              </div>
              <div class="l-solution-item">
                <div class="l-solution-icon">
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><circle cx="8" cy="8" r="7" stroke="#3ddc84" stroke-width="1.5"/><path d="M5 8l2.5 2.5L11 6" stroke="#3ddc84" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>
                </div>
                <span><strong>Reporte IA diario</strong> — análisis ejecutivo en tu Telegram a las 7:00 UTC</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- ======================== SCENARIOS ======================== -->
    <section class="l-section l-scenarios">
      <div class="l-container">
        <div class="l-section-header">
          <div class="l-section-eyebrow">Casos de uso</div>
          <h2 class="l-section-title l-centered">Así lo usan los WISPs todos los días</h2>
          <p class="l-section-sub">Tres escenarios reales donde MonitorWISP ahorra horas de guardia, evita reclamos y automatiza tareas tediosas.</p>
        </div>
        <div class="l-scenarios-grid">

          <!-- Scenario 1 — Alert at dawn -->
          <div class="l-scenario">
            <div class="l-scenario-time">
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><circle cx="7" cy="7" r="6" stroke="#fbbf24" stroke-width="1.3"/><path d="M7 4v3l2 1.5" stroke="#fbbf24" stroke-width="1.3" stroke-linecap="round"/></svg>
              03:14 AM
            </div>
            <h3>Caída en el enlace troncal</h3>
            <p class="l-scenario-sub">WISP con 180 dispositivos · Equipo de guardia de 1 persona</p>
            <div class="l-scenario-body">
              <p>El enlace wireless hacia Torre Norte empieza a perder paquetes. MonitorWISP lo detecta en el siguiente ciclo de sondeo y manda la alerta a Telegram:</p>
              <div class="l-scenario-chat">
                <div class="l-sc-msg critical">🔴 CRÍTICO · Router-Torre-Norte<br><span>Pérdida: 38% · Latencia: 412 ms</span></div>
              </div>
              <p>El técnico de guardia abre la terminal desde el navegador, diagnostica y resetea la interfaz. <strong>A las 03:21 el problema ya estaba resuelto.</strong> Ningún cliente llamó.</p>
            </div>
            <div class="l-scenario-outcome">
              <strong>+7 min</strong> para resolver un incidente que, sin visibilidad, se habría convertido en <strong>horas de reclamos</strong>.
            </div>
          </div>

          <!-- Scenario 2 — Mass password rotation -->
          <div class="l-scenario">
            <div class="l-scenario-time">
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><rect x="2" y="6" width="10" height="7" rx="1.5" stroke="#5372f0" stroke-width="1.3"/><path d="M4.5 6V4.5a2.5 2.5 0 0 1 5 0V6" stroke="#5372f0" stroke-width="1.3"/></svg>
              1 CLIC
            </div>
            <h3>Cambio masivo de contraseñas</h3>
            <p class="l-scenario-sub">Se fue el técnico que conocía el password de admin</p>
            <div class="l-scenario-body">
              <p>Había que rotar la contraseña de administrador en <strong>200 routers</strong> distribuidos en toda la red. Hacerlo a mano implicaba 3 días.</p>
              <div class="l-scenario-progress">
                <div class="l-sc-prog-label">
                  <span>Rotando credenciales…</span>
                  <span><strong>182</strong>/200</span>
                </div>
                <div class="l-sc-prog-bar"><div class="l-sc-prog-fill" style="width:91%"></div></div>
                <div class="l-sc-prog-foot">
                  <span class="l-sc-prog-dot ok"></span> 178 OK <span class="l-sc-prog-dot critical"></span> 4 fallidas
                </div>
              </div>
              <p>Seleccionaron los equipos, eligieron la credencial nueva y MonitorWISP se conectó equipo por equipo actualizando el password. <strong>Tiempo total: 8 minutos.</strong></p>
            </div>
            <div class="l-scenario-outcome">
              De <strong>3 días</strong> de trabajo manual a <strong>8 minutos</strong> automatizados, con reporte de fallas equipo por equipo.
            </div>
          </div>

          <!-- Scenario 3 — Auto discovery -->
          <div class="l-scenario">
            <div class="l-scenario-time">
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><circle cx="7" cy="7" r="6" stroke="#3ddc84" stroke-width="1.3" stroke-dasharray="2 1.5"/><circle cx="7" cy="7" r="2" fill="#3ddc84"/></svg>
              47 NUEVOS
            </div>
            <h3>Inventario completo en 5 minutos</h3>
            <p class="l-scenario-sub">Migración desde un sistema anterior · ISP urbano</p>
            <div class="l-scenario-body">
              <p>El cliente llegó con una planilla Excel incompleta y una frase: "tenemos como 40 o 50 equipos". Configuraron MonitorWISP, ingresaron el rango de la red y apretaron "Escanear ahora".</p>
              <div class="l-scenario-discovery">
                <div class="l-sc-disc-row">
                  <span class="l-sc-disc-ip">192.168.88.3</span>
                  <span class="l-sc-disc-vendor mikrotik">MikroTik · CCR1009</span>
                  <span class="l-sc-disc-status ok">✓ Autenticado</span>
                </div>
                <div class="l-sc-disc-row">
                  <span class="l-sc-disc-ip">192.168.88.14</span>
                  <span class="l-sc-disc-vendor mikrotik">MikroTik · hAP ac²</span>
                  <span class="l-sc-disc-status ok">✓ Autenticado</span>
                </div>
                <div class="l-sc-disc-row">
                  <span class="l-sc-disc-ip">192.168.88.22</span>
                  <span class="l-sc-disc-vendor ubnt">Ubiquiti · NanoStation</span>
                  <span class="l-sc-disc-status ok">✓ Autenticado</span>
                </div>
                <div class="l-sc-disc-row ghost">
                  <span class="l-sc-disc-ip">…</span>
                  <span class="l-sc-disc-vendor">44 equipos más</span>
                  <span class="l-sc-disc-status ok">✓</span>
                </div>
              </div>
              <p>En 5 minutos aparecieron <strong>47 equipos</strong>, detectados por vendor y listos para adoptar. Clic en "Adoptar todo", aplicar plantilla de sensores, y el NOC quedó armado.</p>
            </div>
            <div class="l-scenario-outcome">
              De <strong>Excel desactualizado</strong> a <strong>NOC completo y monitoreado</strong> antes del café de la mañana.
            </div>
          </div>

        </div>
      </div>
    </section>

    <!-- ======================== FEATURES ======================== -->
    <section id="features" class="l-section l-features">
      <div class="l-container">
        <div class="l-section-header">
          <div class="l-section-eyebrow">Funcionalidades</div>
          <h2 class="l-section-title l-centered">Todo lo que necesitás para gestionar tu red</h2>
          <p class="l-section-sub">Diseñado específicamente para la infraestructura MikroTik, Ubiquiti y SSH que ya usás.</p>
        </div>
        <div class="l-features-grid">
          <div class="l-feature-card">
            <div class="l-feature-icon blue">
              <svg width="22" height="22" viewBox="0 0 22 22" fill="none"><circle cx="11" cy="11" r="9" stroke="currentColor" stroke-width="1.6"/><path d="M11 6v5l3.5 2" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/><circle cx="11" cy="11" r="2" fill="currentColor" opacity=".4"/></svg>
            </div>
            <h3>Detección en menos de 10 segundos</h3>
            <p>Cuando un enlace se cae o un router se recalienta, lo ves en el dashboard antes de terminar de tomar café. El panel se actualiza solo, sin refrescar la página ni apretar ningún botón.</p>
            <div class="l-feature-tag">Tiempo real · Sondeo continuo</div>
          </div>

          <div class="l-feature-card">
            <div class="l-feature-icon purple">
              <svg width="22" height="22" viewBox="0 0 22 22" fill="none"><rect x="2" y="6" width="8" height="10" rx="2" stroke="currentColor" stroke-width="1.6"/><rect x="12" y="6" width="8" height="10" rx="2" stroke="currentColor" stroke-width="1.6"/><path d="M10 11h2" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>
            </div>
            <h3>Compatible con lo que ya tenés</h3>
            <p>Integración nativa con MikroTik vía API RouterOS, Ubiquiti y cualquier dispositivo con SSH. No importa si están en la oficina, en una torre remota o en casa del cliente detrás de NAT — los monitoreás a todos desde el mismo panel.</p>
            <div class="l-feature-tag">MikroTik · Ubiquiti · Linux · SSH</div>
          </div>

          <div class="l-feature-card">
            <div class="l-feature-icon green">
              <svg width="22" height="22" viewBox="0 0 22 22" fill="none"><path d="M11 3l2 4h4l-3 3 1 4-4-2-4 2 1-4-3-3h4z" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/><circle cx="11" cy="11" r="2" fill="currentColor" opacity=".3"/></svg>
            </div>
            <h3>VPN WireGuard integrada</h3>
            <p>Accedé a cualquier router de tu red — incluso los que están detrás de NAT o sin IP pública — sin abrir puertos, sin VPNs externas y sin configuraciones manuales. Generás un script, lo pegás en el MikroTik, y listo.</p>
            <div class="l-feature-tag">WireGuard · Sin abrir puertos · Configuración automática</div>
          </div>

          <div class="l-feature-card">
            <div class="l-feature-icon orange">
              <svg width="22" height="22" viewBox="0 0 22 22" fill="none"><circle cx="11" cy="11" r="9" stroke="currentColor" stroke-width="1.6" stroke-dasharray="3 2"/><circle cx="11" cy="11" r="3" stroke="currentColor" stroke-width="1.6"/><path d="M11 3v2M11 17v2M3 11h2M17 11h2" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>
            </div>
            <h3>Descubrí toda tu red en minutos</h3>
            <p>¿Tenés 200 equipos sin inventariar? MonitorWISP escanea tu red, detecta automáticamente qué marca y modelo es cada uno, prueba las credenciales y los adopta en bloque. Lo que te tomaría días, en minutos.</p>
            <div class="l-feature-tag">Escaneo automático · Detección de vendor · Adopción masiva</div>
          </div>

          <div class="l-feature-card">
            <div class="l-feature-icon blue">
              <svg width="22" height="22" viewBox="0 0 22 22" fill="none"><rect x="2" y="4" width="18" height="14" rx="2" stroke="currentColor" stroke-width="1.6"/><path d="M6 9l2 2-2 2M11 13h5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>
            </div>
            <h3>Terminal + Copiloto IA</h3>
            <p>Abrí una terminal contra cualquier router directamente desde el navegador. Y si no te acordás el comando exacto, pedile a la IA: "¿cómo bloqueo esta IP en el firewall?" — te responde con el comando RouterOS listo para ejecutar.</p>
            <div class="l-feature-tag">Terminal remota · IA integrada · Comandos asistidos</div>
          </div>

          <div class="l-feature-card">
            <div class="l-feature-icon green">
              <svg width="22" height="22" viewBox="0 0 22 22" fill="none"><path d="M4 18V8l7-5 7 5v10H4z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/><path d="M9 14v4h4v-4" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/><path d="M9 11h4" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>
            </div>
            <h3>Reportes diarios con IA</h3>
            <p>Cada mañana recibís un resumen con todo lo importante: qué se cayó, cuánto duró, qué clientes se vieron afectados y qué recomienda la IA hacer. En tono técnico, ejecutivo o para mandarle al dueño del WISP. Directo a tu Telegram.</p>
            <div class="l-feature-tag">Resumen diario · 3 tonos · Telegram o Webhook</div>
          </div>
        </div>
      </div>
    </section>

    <!-- ======================== HOW IT WORKS ======================== -->
    <section id="how-it-works" class="l-section l-how">
      <div class="l-container">
        <div class="l-section-header">
          <div class="l-section-eyebrow">Proceso</div>
          <h2 class="l-section-title l-centered">Tres pasos para tener tu red bajo control</h2>
        </div>
        <div class="l-steps">
          <div class="l-step">
            <div class="l-step-number">1</div>
            <div class="l-step-connector"></div>
            <div class="l-step-icon">
              <svg width="28" height="28" viewBox="0 0 28 28" fill="none"><rect x="4" y="8" width="20" height="14" rx="3" stroke="#5372f0" stroke-width="1.8"/><path d="M10 8V6a4 4 0 0 1 8 0v2" stroke="#5372f0" stroke-width="1.8" stroke-linecap="round"/><circle cx="14" cy="15" r="2" fill="#5372f0"/></svg>
            </div>
            <h3>Conectá tus dispositivos</h3>
            <p>Cargás las credenciales una sola vez (usuario y contraseña) y los equipos quedan conectados. ¿Están detrás de NAT? Copiás un script que te genera el sistema, lo pegás en el MikroTik y listo — aparece conectado en segundos, sin abrir puertos ni tocar el firewall.</p>
          </div>
          <div class="l-step">
            <div class="l-step-number">2</div>
            <div class="l-step-connector"></div>
            <div class="l-step-icon">
              <svg width="28" height="28" viewBox="0 0 28 28" fill="none"><circle cx="14" cy="14" r="10" stroke="#3ddc84" stroke-width="1.8"/><circle cx="14" cy="14" r="4" fill="#3ddc84" opacity=".3" stroke="#3ddc84" stroke-width="1.8"/><path d="M14 4v4M14 20v4M4 14h4M20 14h4" stroke="#3ddc84" stroke-width="1.8" stroke-linecap="round"/></svg>
            </div>
            <h3>Monitoreo continuo cada 10 s</h3>
            <p>MonitorWISP interroga a cada sensor cada 10 segundos: ping y pérdida de paquetes, calidad de señal wireless, tráfico de interfaces, CPU, RAM y temperatura. Todo aparece en el dashboard en tiempo real, agrupado por sitio, torre o cliente para que encuentres lo que buscás de un vistazo.</p>
          </div>
          <div class="l-step">
            <div class="l-step-number">3</div>
            <div class="l-step-connector last"></div>
            <div class="l-step-icon">
              <svg width="28" height="28" viewBox="0 0 28 28" fill="none"><path d="M14 4a8 8 0 0 1 8 8v4l2 3H4l2-3v-4a8 8 0 0 1 8-8z" stroke="#fbbf24" stroke-width="1.8" stroke-linejoin="round"/><path d="M11 22a3 3 0 0 0 6 0" stroke="#fbbf24" stroke-width="1.8"/></svg>
            </div>
            <h3>Recibís alertas al instante</h3>
            <p>Cuando un sensor cruza el umbral que vos definiste, la alerta llega a tu Telegram (o al canal que prefieras) con toda la info del evento: dispositivo, sensor afectado, métricas exactas y grupo. Y cuando el problema se resuelve, te avisa también — con la duración total de la caída.</p>
          </div>
        </div>
      </div>
    </section>

    <!-- ======================== DASHBOARD SHOWCASE ======================== -->
    <section class="l-section l-showcase">
      <div class="l-container">
        <div class="l-section-header">
          <div class="l-section-eyebrow">Dashboard</div>
          <h2 class="l-section-title l-centered">Todo tu NOC en una sola pantalla</h2>
          <p class="l-section-sub">Agrupá dispositivos por sitio o cliente. Filtrá por estado. Identificá de un vistazo qué está caído y qué está degradado.</p>
        </div>
        <div class="l-showcase-window">
          <div class="l-showcase-topbar">
            <div class="l-showcase-dots">
              <span></span><span></span><span></span>
            </div>
            <div class="l-showcase-url">monitorwisp.com/dashboard</div>
            <div class="l-showcase-realtime">
              <span class="l-realtime-dot"></span>
              Tiempo real
            </div>
          </div>
          <div class="l-showcase-body">
            <!-- Card 1: OK -->
            <div class="l-showcase-card ok">
              <div class="l-showcase-card-header">
                <div class="l-showcase-card-title-row">
                  <div class="l-mock-status-dot ok" style="width:8px;height:8px;"></div>
                  <span class="l-showcase-card-name">MK-Tower-Central</span>
                  <span class="l-showcase-card-ip">10.10.1.1</span>
                </div>
                <div style="display:flex;gap:4px">
                  <span class="l-mock-badge group" style="font-size:10px;padding:2px 6px">Torres</span>
                </div>
              </div>
              <div class="l-showcase-sensors">
                <div class="l-showcase-sensor-row ok"><span class="l-mock-sensor-dot ok" style="width:7px;height:7px;flex-shrink:0"></span><span>Ping</span><span class="l-ms">11 ms</span></div>
                <div class="l-showcase-sensor-row ok"><span class="l-mock-sensor-dot ok" style="width:7px;height:7px;flex-shrink:0"></span><span>Ethernet ether1</span><span class="l-ms">38.4 / 9.1 Mbps</span></div>
                <div class="l-showcase-sensor-row ok"><span class="l-mock-sensor-dot ok" style="width:7px;height:7px;flex-shrink:0"></span><span>Wireless wlan1</span><span class="l-ms">CCQ 94% · –58 dBm</span></div>
                <div class="l-showcase-sensor-row ok"><span class="l-mock-sensor-dot ok" style="width:7px;height:7px;flex-shrink:0"></span><span>Sistema</span><span class="l-ms">CPU 18% · RAM 35%</span></div>
              </div>
            </div>

            <!-- Card 2: WARNING -->
            <div class="l-showcase-card warning">
              <div class="l-showcase-card-header">
                <div class="l-showcase-card-title-row">
                  <div class="l-mock-status-dot warning" style="width:8px;height:8px;"></div>
                  <span class="l-showcase-card-name">AP-Sector-Norte</span>
                  <span class="l-showcase-card-ip">10.10.1.14</span>
                </div>
                <div style="display:flex;gap:4px">
                  <span class="l-mock-badge group" style="font-size:10px;padding:2px 6px">Sector N</span>
                </div>
              </div>
              <div class="l-showcase-sensors">
                <div class="l-showcase-sensor-row ok"><span class="l-mock-sensor-dot ok" style="width:7px;height:7px;flex-shrink:0"></span><span>Ping</span><span class="l-ms">22 ms</span></div>
                <div class="l-showcase-sensor-row warning"><span class="l-mock-sensor-dot warning" style="width:7px;height:7px;flex-shrink:0"></span><span>Wireless wlan1</span><span class="l-ms warning-text">CCQ 71% · –74 dBm</span></div>
                <div class="l-showcase-sensor-row ok"><span class="l-mock-sensor-dot ok" style="width:7px;height:7px;flex-shrink:0"></span><span>Sistema</span><span class="l-ms">CPU 31% · RAM 48%</span></div>
              </div>
            </div>

            <!-- Card 3: CRITICAL -->
            <div class="l-showcase-card critical">
              <div class="l-showcase-card-header">
                <div class="l-showcase-card-title-row">
                  <div class="l-mock-status-dot critical" style="width:8px;height:8px;"></div>
                  <span class="l-showcase-card-name">Router-Acceso-02</span>
                  <span class="l-showcase-card-ip">10.10.2.1</span>
                </div>
                <div style="display:flex;gap:4px">
                  <span class="l-mock-badge critical" style="font-size:10px;padding:2px 6px">CRÍTICO</span>
                </div>
              </div>
              <div class="l-showcase-sensors">
                <div class="l-showcase-sensor-row critical"><span class="l-mock-sensor-dot critical" style="width:7px;height:7px;flex-shrink:0"></span><span>Ping Principal</span><span class="l-ms critical-text">TIMEOUT · 100% loss</span></div>
                <div class="l-showcase-sensor-row critical"><span class="l-mock-sensor-dot critical" style="width:7px;height:7px;flex-shrink:0"></span><span>Ethernet ether1</span><span class="l-ms critical-text">Sin datos</span></div>
              </div>
            </div>

            <!-- Placeholder cards -->
            <div class="l-showcase-card-placeholder">
              <div class="l-placeholder-line" style="width:60%"></div>
              <div class="l-placeholder-line" style="width:40%;opacity:.5"></div>
              <div class="l-placeholder-line" style="width:80%;opacity:.3;margin-top:8px"></div>
              <div class="l-placeholder-line" style="width:70%;opacity:.3"></div>
            </div>
            <div class="l-showcase-card-placeholder">
              <div class="l-placeholder-line" style="width:55%"></div>
              <div class="l-placeholder-line" style="width:35%;opacity:.5"></div>
              <div class="l-placeholder-line" style="width:75%;opacity:.3;margin-top:8px"></div>
              <div class="l-placeholder-line" style="width:65%;opacity:.3"></div>
            </div>
          </div>
        </div>
        <p class="l-showcase-caption">
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><circle cx="7" cy="7" r="6" stroke="#5372f0" stroke-width="1.3"/><path d="M7 5v3l2 1" stroke="#5372f0" stroke-width="1.3" stroke-linecap="round"/></svg>
          El dashboard se actualiza en tiempo real sin refrescar la página. Los colores reflejan el peor estado de los sensores del dispositivo.
        </p>
      </div>
    </section>

    <!-- ======================== TERMINAL + AI COPILOT ======================== -->
    <section class="l-section l-terminal">
      <div class="l-container">
        <div class="l-split">
          <div class="l-split-text">
            <div class="l-section-eyebrow">Terminal + IA</div>
            <h2 class="l-section-title">Un copiloto RouterOS dentro del navegador</h2>
            <p class="l-split-desc">Abrí una sesión en cualquier MikroTik desde el mismo panel. Y si no te acordás la sintaxis exacta, pedísela a la IA en lenguaje natural — te responde con el comando listo para ejecutar.</p>
            <div class="l-term-features">
              <div class="l-term-feature">
                <div class="l-tf-icon">
                  <svg width="18" height="18" viewBox="0 0 18 18" fill="none"><rect x="1" y="3" width="16" height="12" rx="2" stroke="#5372f0" stroke-width="1.4"/><path d="M5 8l2 2-2 2M9 12h4" stroke="#5372f0" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/></svg>
                </div>
                <div>
                  <strong>Sin instalar clientes SSH</strong>
                  <p>La terminal vive en el navegador. No necesitás Winbox ni PuTTY — incluso funciona desde el celular.</p>
                </div>
              </div>
              <div class="l-term-feature">
                <div class="l-tf-icon">
                  <svg width="18" height="18" viewBox="0 0 18 18" fill="none"><path d="M9 1.5l1.8 3.7 4 .6-2.9 2.8.7 4L9 10.7l-3.6 1.9.7-4L3.2 5.8l4-.6z" stroke="#5372f0" stroke-width="1.4" stroke-linejoin="round"/></svg>
                </div>
                <div>
                  <strong>Copiloto con contexto real</strong>
                  <p>La IA lee la configuración del equipo conectado y te responde sobre tu red, no con respuestas genéricas de manual.</p>
                </div>
              </div>
              <div class="l-term-feature">
                <div class="l-tf-icon">
                  <svg width="18" height="18" viewBox="0 0 18 18" fill="none"><circle cx="9" cy="9" r="7" stroke="#5372f0" stroke-width="1.4"/><path d="M9 5v4l2.5 1.5" stroke="#5372f0" stroke-width="1.4" stroke-linecap="round"/></svg>
                </div>
                <div>
                  <strong>Funciona incluso detrás de NAT</strong>
                  <p>Si el equipo está conectado por VPN, la terminal lo encuentra. No importa dónde esté el router físicamente.</p>
                </div>
              </div>
            </div>
          </div>
          <div class="l-split-visual">
            <div class="l-term-mock">
              <div class="l-term-topbar">
                <div class="l-term-dots"><span></span><span></span><span></span></div>
                <div class="l-term-title">Router-Core-01 · terminal</div>
              </div>
              <div class="l-term-body">
                <div class="l-term-line"><span class="l-term-prompt">[admin@Router-Core-01] &gt;</span> <span class="l-term-cmd">/interface/print where running=yes</span></div>
                <div class="l-term-line output">Flags: R - RUNNING</div>
                <div class="l-term-line output"> #   NAME         TYPE        ACTUAL-MTU  MAC-ADDRESS</div>
                <div class="l-term-line output"> 0 R ether1       ether       1500        E4:8D:8C:11:22:33</div>
                <div class="l-term-line output"> 1 R wlan1        wlan        1500        E4:8D:8C:11:22:34</div>
                <div class="l-term-line output"> 2 R bridge-lan   bridge      1500        E4:8D:8C:11:22:35</div>
                <div class="l-term-spacer"></div>
                <div class="l-term-ai-prompt">
                  <div class="l-term-ai-label">
                    <svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M6 1l1.5 3H11L8.5 6l1 3L6 7.5 2.5 9l1-3L1 4h3.5z" fill="#3ddc84"/></svg>
                    Pedile a la IA
                  </div>
                  <div class="l-term-ai-question">"¿Cómo bloqueo la IP 1.2.3.4 en el firewall input?"</div>
                </div>
                <div class="l-term-ai-answer">
                  <div class="l-term-ai-answer-label">
                    <svg width="12" height="12" viewBox="0 0 12 12" fill="none"><circle cx="6" cy="6" r="5" stroke="#5372f0" stroke-width="1.2"/><path d="M4 6l1.5 1.5L8 5" stroke="#5372f0" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/></svg>
                    Comando sugerido
                  </div>
                  <div class="l-term-ai-code">/ip/firewall/filter/add chain=input src-address=1.2.3.4 action=drop comment="Bloqueo manual"</div>
                  <div class="l-term-ai-actions">
                    <span class="l-term-ai-btn primary">▶ Ejecutar</span>
                    <span class="l-term-ai-btn">Copiar</span>
                  </div>
                </div>
              </div>
              <div class="l-term-footer">
                <span class="l-term-cursor"></span>
                Conectado vía VPN · Sesión activa
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- ======================== ALERTS ======================== -->
    <section class="l-section l-alerts">
      <div class="l-container">
        <div class="l-split">
          <div class="l-split-text">
            <div class="l-section-eyebrow">Alertas inteligentes</div>
            <h2 class="l-section-title">Sabé lo que pasa antes que tus clientes</h2>
            <p class="l-split-desc">Configurá umbrales por sensor. Cuando algo sale del rango normal, la notificación llega instantáneamente a tu canal preferido.</p>
            <div class="l-alert-features">
              <div class="l-alert-feature">
                <div class="l-af-icon">
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M8 2a5 5 0 0 1 5 5v3l1.5 2H1.5L3 10V7a5 5 0 0 1 5-5z" stroke="#5372f0" stroke-width="1.4" stroke-linejoin="round"/><path d="M6 13.5a2 2 0 0 0 4 0" stroke="#5372f0" stroke-width="1.4"/></svg>
                </div>
                <div>
                  <strong>Telegram Bot</strong>
                  <p>Alertas en tiempo real en tu grupo o chat privado, con toda la información del evento.</p>
                </div>
              </div>
              <div class="l-alert-feature">
                <div class="l-af-icon">
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M2 4h12v9H2z" stroke="#5372f0" stroke-width="1.4" stroke-linejoin="round"/><path d="M2 4l6 5 6-5" stroke="#5372f0" stroke-width="1.4" stroke-linecap="round"/></svg>
                </div>
                <div>
                  <strong>Webhooks personalizados</strong>
                  <p>Integración con cualquier sistema: Slack, PagerDuty, tu propio CRM o sistema de tickets.</p>
                </div>
              </div>
              <div class="l-alert-feature">
                <div class="l-af-icon">
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M8 2v3M4 4l2 2M12 4l-2 2M3 8H1M15 8h-2M4 12l2-2M12 12l-2-2M8 14v-3" stroke="#5372f0" stroke-width="1.4" stroke-linecap="round"/></svg>
                </div>
                <div>
                  <strong>Silenciado granular</strong>
                  <p>Silenciá por sensor, monitor, grupo o cuenta completa. Control total sin ruido innecesario.</p>
                </div>
              </div>
            </div>
          </div>
          <div class="l-split-visual">
            <!-- Telegram mock -->
            <div class="l-telegram-mock">
              <div class="l-telegram-header">
                <div class="l-telegram-avatar">
                  <svg width="22" height="22" viewBox="0 0 22 22" fill="none"><path d="M2 11l17-8-5 17-4-6-8-3z" fill="#5372f0"/></svg>
                </div>
                <div>
                  <div class="l-telegram-bot-name">MonitorWISP Bot</div>
                  <div class="l-telegram-bot-sub">bot · en línea</div>
                </div>
              </div>
              <div class="l-telegram-messages">
                <div class="l-tg-msg critical-msg">
                  <div class="l-tg-msg-header">🔴 CRÍTICO</div>
                  <div class="l-tg-msg-body">
                    <div><strong>Dispositivo:</strong> Router-Acceso-02</div>
                    <div><strong>Sensor:</strong> Ping Principal</div>
                    <div><strong>Estado:</strong> TIMEOUT (3 intentos)</div>
                    <div><strong>IP:</strong> 10.10.2.1</div>
                    <div><strong>Grupo:</strong> Distribución</div>
                    <div class="l-tg-msg-ts">2026-04-19 · 14:32:07 UTC</div>
                  </div>
                </div>
                <div class="l-tg-msg ok-msg">
                  <div class="l-tg-msg-header">🟢 RESUELTO</div>
                  <div class="l-tg-msg-body">
                    <div><strong>Dispositivo:</strong> Router-Acceso-02</div>
                    <div><strong>Sensor:</strong> Ping Principal</div>
                    <div><strong>Latencia:</strong> 14 ms · Pérdida: 0%</div>
                    <div class="l-tg-msg-ts">2026-04-19 · 14:47:31 UTC · Duración: 15m 24s</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- ======================== AUTOMATION / SCHEDULED TASKS ======================== -->
    <section class="l-section l-automation">
      <div class="l-container">
        <div class="l-section-header">
          <div class="l-section-eyebrow">Automatización</div>
          <h2 class="l-section-title l-centered">Tareas que se ejecutan solas, mientras dormís</h2>
          <p class="l-section-sub">Programá mantenimientos preventivos, ejecutá scripts masivos y liberá a tu equipo de las tareas repetitivas.</p>
        </div>

        <div class="l-auto-grid">

          <!-- Tarea 1 -->
          <div class="l-auto-card">
            <div class="l-auto-card-head">
              <div class="l-auto-icon blue">
                <svg width="20" height="20" viewBox="0 0 20 20" fill="none"><path d="M10 3v3l2 1" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/><circle cx="10" cy="10" r="7" stroke="currentColor" stroke-width="1.6"/></svg>
              </div>
              <div>
                <div class="l-auto-card-title">Reinicio preventivo mensual</div>
                <div class="l-auto-card-sub">Domingo 03:00 AM · Uptime &gt; 30 días</div>
              </div>
            </div>
            <p class="l-auto-card-desc">Reiniciás toda la flota una vez al mes para liberar memoria, pero solo los equipos que llevan más de 30 días encendidos. El resto se ignoran automáticamente.</p>
            <div class="l-auto-card-stat">
              <span class="l-auto-stat-dot ok"></span>
              <span>120 equipos programados · 4 ignorados (sin credencial)</span>
            </div>
          </div>

          <!-- Tarea 2 -->
          <div class="l-auto-card">
            <div class="l-auto-card-head">
              <div class="l-auto-icon green">
                <svg width="20" height="20" viewBox="0 0 20 20" fill="none"><path d="M3 10l3 3 8-8" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/><path d="M3 15h14" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>
              </div>
              <div>
                <div class="l-auto-card-title">Cambio de DNS masivo</div>
                <div class="l-auto-card-sub">Script personalizado · 200 equipos</div>
              </div>
            </div>
            <p class="l-auto-card-desc">Cargás el bloque de comandos RouterOS una vez, seleccionás los equipos y MonitorWISP los ejecuta uno por uno, guardando el resultado de cada ejecución.</p>
            <div class="l-auto-card-stat">
              <span class="l-auto-stat-dot ok"></span>
              <span>Ejecución en 12 min · Logs por equipo</span>
            </div>
          </div>

          <!-- Tarea 3 -->
          <div class="l-auto-card">
            <div class="l-auto-card-head">
              <div class="l-auto-icon purple">
                <svg width="20" height="20" viewBox="0 0 20 20" fill="none"><path d="M4 8h12M4 12h12" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/><rect x="2" y="4" width="16" height="12" rx="2" stroke="currentColor" stroke-width="1.6"/></svg>
              </div>
              <div>
                <div class="l-auto-card-title">Actualización de firmware</div>
                <div class="l-auto-card-sub">Por grupo · Fuera de horario</div>
              </div>
            </div>
            <p class="l-auto-card-desc">Agendás la actualización de firmware por grupo de dispositivos, en la ventana horaria que menos impacta a tus clientes. Si algo falla, te enterás en el log.</p>
            <div class="l-auto-card-stat">
              <span class="l-auto-stat-dot ok"></span>
              <span>Ventana configurable · Reintentos automáticos</span>
            </div>
          </div>

          <!-- Tarea 4 -->
          <div class="l-auto-card">
            <div class="l-auto-card-head">
              <div class="l-auto-icon orange">
                <svg width="20" height="20" viewBox="0 0 20 20" fill="none"><path d="M10 2a8 8 0 0 1 8 8v4l2 3H0l2-3v-4a8 8 0 0 1 8-8z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/><path d="M7 17a3 3 0 0 0 6 0" stroke="currentColor" stroke-width="1.6"/></svg>
              </div>
              <div>
                <div class="l-auto-card-title">Silenciado por mantenimiento</div>
                <div class="l-auto-card-sub">Grupo · Ventana horaria</div>
              </div>
            </div>
            <p class="l-auto-card-desc">Vas a hacer mantenimiento en un sitio entero. Silenciás el grupo durante 4 horas — nadie recibe falsas alarmas, el dashboard sigue midiendo, y el silenciado se levanta solo.</p>
            <div class="l-auto-card-stat">
              <span class="l-auto-stat-dot ok"></span>
              <span>Sin falsas alarmas · Auto-reactivación</span>
            </div>
          </div>

        </div>

        <div class="l-auto-footer-note">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><circle cx="8" cy="8" r="7" stroke="#3ddc84" stroke-width="1.4"/><path d="M5 8l2 2 4-4" stroke="#3ddc84" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/></svg>
          Todas las tareas quedan registradas equipo por equipo, con el output exacto de lo que devolvió cada dispositivo.
        </div>
      </div>
    </section>

    <!-- ======================== AI REPORTS ======================== -->
    <section class="l-section l-reports">
      <div class="l-container">
        <div class="l-split l-split-reverse">
          <div class="l-split-visual">
            <div class="l-report-mock">
              <div class="l-report-header">
                <svg width="20" height="20" viewBox="0 0 20 20" fill="none"><rect x="2" y="2" width="16" height="16" rx="3" stroke="#5372f0" stroke-width="1.5"/><path d="M6 7h8M6 10h8M6 13h5" stroke="#5372f0" stroke-width="1.5" stroke-linecap="round"/></svg>
                <div>
                  <div class="l-report-title">Reporte Diario · 19 Abr 2026</div>
                  <div class="l-report-period">Período: 00:00 – 23:59 UTC</div>
                </div>
              </div>
              <div class="l-report-stats">
                <div class="l-report-stat">
                  <div class="l-report-stat-value ok">99.3%</div>
                  <div class="l-report-stat-label">Uptime promedio</div>
                </div>
                <div class="l-report-stat">
                  <div class="l-report-stat-value ok">11.2 ms</div>
                  <div class="l-report-stat-label">Latencia media</div>
                </div>
                <div class="l-report-stat">
                  <div class="l-report-stat-value critical">2</div>
                  <div class="l-report-stat-label">Eventos críticos</div>
                </div>
              </div>
              <div class="l-report-divider"></div>
              <div class="l-report-ai-text">
                <div class="l-report-ai-badge">
                  <svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M6 1l1.5 3H11L8.5 6l1 3L6 7.5 2.5 9l1-3L1 4h3.5z" fill="#5372f0"/></svg>
                  Análisis IA
                </div>
                <p>El enlace <strong>Router-Acceso-02</strong> presentó una interrupción entre las 14:32 y 14:47 UTC con pérdida de paquetes del 100% (duración 15m 24s). El resto de la red operó dentro de parámetros normales. <strong>Recomendación:</strong> revisar la alimentación del equipo y el estado del enlace físico en ese nodo.</p>
              </div>
              <div class="l-report-footer-note">
                <svg width="13" height="13" viewBox="0 0 13 13" fill="none"><path d="M2 11L10 2M5 2h5v5" stroke="#9aa0a6" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/></svg>
                Entregado vía Telegram · 07:00 UTC
              </div>
            </div>
          </div>
          <div class="l-split-text">
            <div class="l-section-eyebrow">Reportes con IA</div>
            <h2 class="l-section-title">Tu red analizada cada mañana, sin intervención manual</h2>
            <p class="l-split-desc">Empezá el día sabiendo exactamente qué pasó en tu red las últimas 24 horas, sin revisar logs ni tablas de métricas.</p>
            <div class="l-report-options">
              <div class="l-report-option">
                <div class="l-ro-dot blue"></div>
                <div>
                  <strong>Tono técnico</strong>
                  <p>Métricas, tiempos exactos, comandos sugeridos para resolver los incidentes detectados.</p>
                </div>
              </div>
              <div class="l-report-option">
                <div class="l-ro-dot green"></div>
                <div>
                  <strong>Tono ejecutivo</strong>
                  <p>Resumen ejecutivo en lenguaje no técnico, ideal para reportar a clientes o gerencia.</p>
                </div>
              </div>
              <div class="l-report-option">
                <div class="l-ro-dot purple"></div>
                <div>
                  <strong>Tono profesional</strong>
                  <p>Balance entre detalle técnico y claridad. Para equipos NOC y técnicos senior.</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- ======================== SECURITY ======================== -->
    <section class="l-section l-security">
      <div class="l-container">
        <div class="l-security-band">
          <div class="l-security-head">
            <div class="l-section-eyebrow">Seguridad</div>
            <h2 class="l-section-title">Tu red sigue siendo tuya</h2>
            <p class="l-security-sub">Construido con los estándares de seguridad que esperás de una plataforma que tiene acceso a toda tu infraestructura.</p>
          </div>
          <div class="l-security-grid">
            <div class="l-security-item">
              <div class="l-sec-icon">
                <svg width="22" height="22" viewBox="0 0 22 22" fill="none"><rect x="4" y="9" width="14" height="10" rx="2" stroke="#3ddc84" stroke-width="1.6"/><path d="M7 9V6a4 4 0 0 1 8 0v3" stroke="#3ddc84" stroke-width="1.6"/><circle cx="11" cy="14" r="1.5" fill="#3ddc84"/></svg>
              </div>
              <div>
                <strong>Contraseñas encriptadas en reposo</strong>
                <p>Ningún administrador de MonitorWISP puede ver tus credenciales de router, ni siquiera nosotros. Se encriptan antes de guardarse y se desencriptan solo en el momento de la conexión.</p>
              </div>
            </div>
            <div class="l-security-item">
              <div class="l-sec-icon">
                <svg width="22" height="22" viewBox="0 0 22 22" fill="none"><path d="M11 2L3 6v6c0 5 4 8 8 8s8-3 8-8V6l-8-4z" stroke="#3ddc84" stroke-width="1.6" stroke-linejoin="round"/><path d="M8 11l2 2 4-4" stroke="#3ddc84" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>
              </div>
              <div>
                <strong>Aislamiento total por cuenta</strong>
                <p>Cada operador ve únicamente sus propios dispositivos, credenciales y alertas. Aislamiento completo a nivel base de datos, no solo a nivel de interfaz.</p>
              </div>
            </div>
            <div class="l-security-item">
              <div class="l-sec-icon">
                <svg width="22" height="22" viewBox="0 0 22 22" fill="none"><circle cx="11" cy="11" r="9" stroke="#3ddc84" stroke-width="1.6"/><path d="M11 6v5l3.5 2" stroke="#3ddc84" stroke-width="1.6" stroke-linecap="round"/></svg>
              </div>
              <div>
                <strong>Sesiones y tokens con expiración</strong>
                <p>Autenticación moderna con tokens que rotan y caducan. Si alguien intenta usar una sesión vieja, el sistema la rechaza automáticamente.</p>
              </div>
            </div>
            <div class="l-security-item">
              <div class="l-sec-icon">
                <svg width="22" height="22" viewBox="0 0 22 22" fill="none"><path d="M11 2v18M2 11h18" stroke="#3ddc84" stroke-width="1.6" stroke-linecap="round"/><circle cx="11" cy="11" r="4" stroke="#3ddc84" stroke-width="1.6"/></svg>
              </div>
              <div>
                <strong>Comunicación cifrada de punta a punta</strong>
                <p>Tráfico TLS obligatorio desde tu navegador hasta nuestros servidores, y desde nuestros servidores hasta tus dispositivos vía SSH y WireGuard.</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- ======================== PRICING ======================== -->
    <section id="pricing" class="l-section l-pricing">
      <div class="l-container">
        <div class="l-section-header">
          <div class="l-section-eyebrow">Planes</div>
          <h2 class="l-section-title l-centered">Planes que escalan con tu red</h2>
          <p class="l-section-sub">Elegí el plan que se ajusta a tu infraestructura. Podés agregar dispositivos y VPNs a medida que tu red crece.</p>
        </div>
        <div class="l-pricing-grid">
          <div class="l-plan-card">
            <div class="l-plan-name">Starter</div>
            <div class="l-plan-desc">Para WISPs pequeños y redes en crecimiento</div>
            <div class="l-plan-price">
              <span class="l-plan-price-label">Desde</span>
              <span class="l-plan-price-value">$19</span>
              <span class="l-plan-price-period">/mes</span>
            </div>
            <ul class="l-plan-features">
              <li><svg width="13" height="13" viewBox="0 0 13 13" fill="none"><circle cx="6.5" cy="6.5" r="5.5" stroke="#3ddc84" stroke-width="1.3"/><path d="M4 6.5l2 2 3-3" stroke="#3ddc84" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/></svg> Hasta 20 dispositivos</li>
              <li><svg width="13" height="13" viewBox="0 0 13 13" fill="none"><circle cx="6.5" cy="6.5" r="5.5" stroke="#3ddc84" stroke-width="1.3"/><path d="M4 6.5l2 2 3-3" stroke="#3ddc84" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/></svg> 4 sensores por dispositivo</li>
              <li><svg width="13" height="13" viewBox="0 0 13 13" fill="none"><circle cx="6.5" cy="6.5" r="5.5" stroke="#3ddc84" stroke-width="1.3"/><path d="M4 6.5l2 2 3-3" stroke="#3ddc84" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/></svg> Alertas Telegram + Webhook</li>
              <li><svg width="13" height="13" viewBox="0 0 13 13" fill="none"><circle cx="6.5" cy="6.5" r="5.5" stroke="#3ddc84" stroke-width="1.3"/><path d="M4 6.5l2 2 3-3" stroke="#3ddc84" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/></svg> Reportes IA diarios</li>
              <li><svg width="13" height="13" viewBox="0 0 13 13" fill="none"><circle cx="6.5" cy="6.5" r="5.5" stroke="#3ddc84" stroke-width="1.3"/><path d="M4 6.5l2 2 3-3" stroke="#3ddc84" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/></svg> Terminal remota SSH</li>
              <li class="l-plan-feature-disabled"><svg width="13" height="13" viewBox="0 0 13 13" fill="none"><circle cx="6.5" cy="6.5" r="5.5" stroke="#444" stroke-width="1.3"/><path d="M4.5 8.5l4-4M8.5 8.5l-4-4" stroke="#444" stroke-width="1.3" stroke-linecap="round"/></svg> VPN WireGuard</li>
              <li class="l-plan-feature-disabled"><svg width="13" height="13" viewBox="0 0 13 13" fill="none"><circle cx="6.5" cy="6.5" r="5.5" stroke="#444" stroke-width="1.3"/><path d="M4.5 8.5l4-4M8.5 8.5l-4-4" stroke="#444" stroke-width="1.3" stroke-linecap="round"/></svg> Descubrimiento automático</li>
            </ul>
            <router-link to="/login" class="l-btn l-btn-ghost l-btn-full">Crear Cuenta</router-link>
          </div>

          <div class="l-plan-card l-plan-featured">
            <div class="l-plan-popular-badge">Más popular</div>
            <div class="l-plan-name">Pro</div>
            <div class="l-plan-desc">Para ISPs y WISPs con infraestructura distribuida</div>
            <div class="l-plan-price">
              <span class="l-plan-price-label">Desde</span>
              <span class="l-plan-price-value">$49</span>
              <span class="l-plan-price-period">/mes</span>
            </div>
            <ul class="l-plan-features">
              <li><svg width="13" height="13" viewBox="0 0 13 13" fill="none"><circle cx="6.5" cy="6.5" r="5.5" stroke="#3ddc84" stroke-width="1.3"/><path d="M4 6.5l2 2 3-3" stroke="#3ddc84" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/></svg> Hasta 50 dispositivos</li>
              <li><svg width="13" height="13" viewBox="0 0 13 13" fill="none"><circle cx="6.5" cy="6.5" r="5.5" stroke="#3ddc84" stroke-width="1.3"/><path d="M4 6.5l2 2 3-3" stroke="#3ddc84" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/></svg> 4 sensores por dispositivo</li>
              <li><svg width="13" height="13" viewBox="0 0 13 13" fill="none"><circle cx="6.5" cy="6.5" r="5.5" stroke="#3ddc84" stroke-width="1.3"/><path d="M4 6.5l2 2 3-3" stroke="#3ddc84" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/></svg> Alertas Telegram + Webhook</li>
              <li><svg width="13" height="13" viewBox="0 0 13 13" fill="none"><circle cx="6.5" cy="6.5" r="5.5" stroke="#3ddc84" stroke-width="1.3"/><path d="M4 6.5l2 2 3-3" stroke="#3ddc84" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/></svg> Reportes IA diarios</li>
              <li><svg width="13" height="13" viewBox="0 0 13 13" fill="none"><circle cx="6.5" cy="6.5" r="5.5" stroke="#3ddc84" stroke-width="1.3"/><path d="M4 6.5l2 2 3-3" stroke="#3ddc84" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/></svg> Terminal remota SSH</li>
              <li><svg width="13" height="13" viewBox="0 0 13 13" fill="none"><circle cx="6.5" cy="6.5" r="5.5" stroke="#3ddc84" stroke-width="1.3"/><path d="M4 6.5l2 2 3-3" stroke="#3ddc84" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/></svg> VPN WireGuard integrada</li>
              <li><svg width="13" height="13" viewBox="0 0 13 13" fill="none"><circle cx="6.5" cy="6.5" r="5.5" stroke="#3ddc84" stroke-width="1.3"/><path d="M4 6.5l2 2 3-3" stroke="#3ddc84" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/></svg> Descubrimiento automático</li>
            </ul>
            <router-link to="/login" class="l-btn l-btn-primary l-btn-full">Crear Cuenta</router-link>
          </div>

          <div class="l-plan-card l-plan-addons">
            <div class="l-plan-name">Add-ons</div>
            <div class="l-plan-desc">Expandí tu plan según crece tu red</div>
            <div class="l-plan-addons-list">
              <div class="l-addon">
                <div class="l-addon-icon">
                  <svg width="18" height="18" viewBox="0 0 18 18" fill="none"><rect x="2" y="2" width="14" height="14" rx="3" stroke="#5372f0" stroke-width="1.4"/><path d="M9 6v6M6 9h6" stroke="#5372f0" stroke-width="1.4" stroke-linecap="round"/></svg>
                </div>
                <div>
                  <strong>+10 dispositivos</strong>
                  <p>Agregá bloques de 10 dispositivos extra a cualquier plan.</p>
                </div>
              </div>
              <div class="l-addon">
                <div class="l-addon-icon">
                  <svg width="18" height="18" viewBox="0 0 18 18" fill="none"><path d="M9 2a6 6 0 0 1 6 6v3l1.5 2H1.5L3 11V8a6 6 0 0 1 6-6z" stroke="#5372f0" stroke-width="1.4" stroke-linejoin="round"/><path d="M7 15.5a2 2 0 0 0 4 0" stroke="#5372f0" stroke-width="1.4"/></svg>
                </div>
                <div>
                  <strong>+Perfiles VPN</strong>
                  <p>Bloques de perfiles WireGuard adicionales para routers y escritorios.</p>
                </div>
              </div>
            </div>
            <div class="l-addon-note">Los precios exactos se muestran en el panel de facturación al registrarte.</div>
            <router-link to="/login" class="l-btn l-btn-ghost l-btn-full">Ver Precios Completos</router-link>
          </div>
        </div>
      </div>
    </section>

    <!-- ======================== FAQ ======================== -->
    <section class="l-section l-faq">
      <div class="l-container">
        <div class="l-section-header">
          <div class="l-section-eyebrow">Preguntas frecuentes</div>
          <h2 class="l-section-title l-centered">Todo lo que querés saber antes de empezar</h2>
        </div>
        <div class="l-faq-grid">

          <details class="l-faq-item">
            <summary>
              <span>¿Necesito abrir puertos en mis routers para que MonitorWISP los pueda monitorear?</span>
              <span class="l-faq-chev">+</span>
            </summary>
            <div class="l-faq-answer">
              <p>No. MonitorWISP tiene VPN WireGuard integrada: generás un bloque de comandos, lo pegás en el MikroTik, y el router se conecta desde adentro hacia afuera. No hay que abrir puertos, ni exponer servicios, ni configurar NAT. Funciona incluso con IP dinámica.</p>
            </div>
          </details>

          <details class="l-faq-item">
            <summary>
              <span>¿Puedo monitorear equipos que no son MikroTik?</span>
              <span class="l-faq-chev">+</span>
            </summary>
            <div class="l-faq-answer">
              <p>Sí. MonitorWISP soporta MikroTik con API nativa, Ubiquiti vía SSH y cualquier equipo Linux o que acepte conexión SSH estándar. Y próximamente SNMP para equipos legacy.</p>
            </div>
          </details>

          <details class="l-faq-item">
            <summary>
              <span>¿Qué pasa si tengo 200 o 500 equipos? ¿Es mucho trabajo configurar uno por uno?</span>
              <span class="l-faq-chev">+</span>
            </summary>
            <div class="l-faq-answer">
              <p>No hace falta cargar uno por uno. Usás el descubrimiento automático: ingresás el rango de red, MonitorWISP escanea, detecta los equipos, prueba las credenciales y te los muestra listos para adoptar en bloque. Configuraciones masivas como renombrar, silenciar o aplicar plantillas de sensores también se hacen con un clic.</p>
            </div>
          </details>

          <details class="l-faq-item">
            <summary>
              <span>¿Mis contraseñas de admin están seguras?</span>
              <span class="l-faq-chev">+</span>
            </summary>
            <div class="l-faq-answer">
              <p>Las credenciales se encriptan antes de guardarse. Ni siquiera nuestro equipo puede verlas en claro. Se desencriptan solo en el momento exacto de conectarse al equipo, y nunca se loguean ni aparecen en reportes. Además, cada cuenta está aislada de las demás a nivel de base de datos.</p>
            </div>
          </details>

          <details class="l-faq-item">
            <summary>
              <span>¿Cómo funciona el copiloto de IA? ¿Ve toda mi red?</span>
              <span class="l-faq-chev">+</span>
            </summary>
            <div class="l-faq-answer">
              <p>La IA solo ve el contexto del equipo donde estás trabajando en ese momento, y solo cuando vos le hacés una pregunta explícita. No monitorea en background, no manda datos sin tu acción. Y los comandos que sugiere nunca se ejecutan solos — siempre decidís vos si los ejecutás o no.</p>
            </div>
          </details>

          <details class="l-faq-item">
            <summary>
              <span>¿Qué pasa si se cae la conexión entre mi red y MonitorWISP?</span>
              <span class="l-faq-chev">+</span>
            </summary>
            <div class="l-faq-answer">
              <p>MonitorWISP te avisa inmediatamente cuando pierde contacto con un equipo o con un grupo entero. Los datos históricos siguen disponibles para revisión, y cuando la conexión vuelve, los sensores retoman el monitoreo automáticamente.</p>
            </div>
          </details>

          <details class="l-faq-item">
            <summary>
              <span>¿Puedo probar la plataforma antes de decidir?</span>
              <span class="l-faq-chev">+</span>
            </summary>
            <div class="l-faq-answer">
              <p>Sí. Te registrás sin tarjeta, conectás tus primeros dispositivos y evaluás la plataforma con tu red real. Si después querés escalar, elegís el plan que se ajuste a tu cantidad de equipos.</p>
            </div>
          </details>

          <details class="l-faq-item">
            <summary>
              <span>¿Puedo subir o bajar de plan después?</span>
              <span class="l-faq-chev">+</span>
            </summary>
            <div class="l-faq-answer">
              <p>Siempre. Desde el panel de facturación ajustás la cantidad de dispositivos y perfiles VPN con dos sliders, y el precio se recalcula en vivo. Los cambios se aplican en segundos, sin interrupciones ni migraciones.</p>
            </div>
          </details>

          <details class="l-faq-item">
            <summary>
              <span>¿Dónde se guardan los datos? ¿Hay límite de retención?</span>
              <span class="l-faq-chev">+</span>
            </summary>
            <div class="l-faq-answer">
              <p>Tus datos y métricas se guardan en nuestra infraestructura cloud con respaldos diarios. El historial detallado está disponible durante meses, suficiente para análisis de tendencias, reportes de SLA y auditorías retroactivas.</p>
            </div>
          </details>

        </div>
      </div>
    </section>

    <!-- ======================== CTA FINAL ======================== -->
    <section class="l-cta-banner">
      <div class="l-container">
        <div class="l-cta-inner">
          <div class="l-cta-text">
            <h2>¿Listo para tener visibilidad total de tu red?</h2>
            <p>Conectá tus primeros dispositivos en minutos. Sin configuración compleja, sin agentes externos.</p>
          </div>
          <div class="l-cta-actions">
            <router-link to="/login" class="l-btn l-btn-primary l-btn-lg">Crear Cuenta</router-link>
            <router-link to="/login" class="l-btn l-btn-ghost l-btn-lg">Ingresar</router-link>
          </div>
        </div>
      </div>
    </section>

    <!-- ======================== FOOTER ======================== -->
    <footer class="l-footer">
      <div class="l-container">
        <div class="l-footer-grid">
          <div class="l-footer-brand">
            <a href="/" class="l-logo" style="margin-bottom:1rem;display:inline-flex">
              <svg width="22" height="22" viewBox="0 0 28 28" fill="none">
                <circle cx="14" cy="14" r="12" stroke="url(#footer-logo-g)" stroke-width="1.8"/>
                <circle cx="14" cy="14" r="5" fill="url(#footer-logo-g)"/>
                <line x1="14" y1="2" x2="14" y2="7" stroke="url(#footer-logo-g)" stroke-width="1.8" stroke-linecap="round"/>
                <line x1="14" y1="21" x2="14" y2="26" stroke="url(#footer-logo-g)" stroke-width="1.8" stroke-linecap="round"/>
                <line x1="2" y1="14" x2="7" y2="14" stroke="url(#footer-logo-g)" stroke-width="1.8" stroke-linecap="round"/>
                <line x1="21" y1="14" x2="26" y2="14" stroke="url(#footer-logo-g)" stroke-width="1.8" stroke-linecap="round"/>
                <defs><linearGradient id="footer-logo-g" x1="0" y1="0" x2="28" y2="28" gradientUnits="userSpaceOnUse"><stop stop-color="#5372f0"/><stop offset="1" stop-color="#3ddc84"/></linearGradient></defs>
              </svg>
              <span>MonitorWISP</span>
            </a>
            <p class="l-footer-desc">Plataforma SaaS de monitoreo de infraestructura de red para WISPs, ISPs y empresas con redes heterogéneas.</p>
          </div>
          <div class="l-footer-col">
            <h4>Producto</h4>
            <ul>
              <li><a href="#features">Características</a></li>
              <li><a href="#pricing">Planes</a></li>
              <li><a href="#how-it-works">Cómo funciona</a></li>
            </ul>
          </div>
          <div class="l-footer-col">
            <h4>Legal</h4>
            <ul>
              <li><router-link to="/terms">Términos de Servicio</router-link></li>
              <li><router-link to="/privacy">Política de Privacidad</router-link></li>
            </ul>
          </div>
          <div class="l-footer-col">
            <h4>Contacto</h4>
            <ul>
              <li><a href="mailto:support@monitorwisp.com">support@monitorwisp.com</a></li>
              <li><router-link to="/login">Acceder a la plataforma</router-link></li>
            </ul>
          </div>
        </div>
        <div class="l-footer-bottom">
          <p>&copy; 2026 MonitorWISP. Todos los derechos reservados.</p>
          <div class="l-footer-tech">
            Monitoreo inteligente con IA · WireGuard integrado · Tiempo real
          </div>
        </div>
      </div>
    </footer>

  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'

const isScrolled = ref(false)
const mobileMenuOpen = ref(false)

function handleScroll() {
  isScrolled.value = window.scrollY > 20
}

function closeMobileMenu() {
  mobileMenuOpen.value = false
}

onMounted(() => {
  window.addEventListener('scroll', handleScroll, { passive: true })
})

onBeforeUnmount(() => {
  window.removeEventListener('scroll', handleScroll)
})
</script>

<style scoped>
/* ============================================================
   LANDING PAGE — MonitorWISP
   Self-contained styles, prefixed with .l- to avoid collisions
   ============================================================ */

.landing-page {
  background: #0b1220;
  color: #e0e0e0;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  line-height: 1.6;
  overflow-x: hidden;
}

/* ---- SHARED ---- */
.l-container {
  max-width: 1160px;
  margin: 0 auto;
  padding: 0 1.5rem;
}

.l-section {
  padding: 5rem 0;
}

.l-section-header {
  text-align: center;
  margin-bottom: 3.5rem;
}

.l-section-eyebrow {
  font-size: 0.75rem;
  font-weight: 700;
  letter-spacing: 2px;
  text-transform: uppercase;
  color: #5372f0;
  margin-bottom: 0.75rem;
}

.l-section-eyebrow.solution {
  color: #3ddc84;
}

.l-section-title {
  font-size: 2rem;
  font-weight: 800;
  line-height: 1.2;
  color: #fff;
  margin: 0 0 0.75rem;
}

.l-section-title.l-centered {
  text-align: center;
}

.l-section-sub {
  font-size: 1rem;
  color: #9aa0a6;
  max-width: 560px;
  margin: 0 auto;
  text-align: center;
}

.l-gradient-text {
  background: linear-gradient(135deg, #5372f0 0%, #3ddc84 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

/* ---- BUTTONS ---- */
.l-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.6rem 1.25rem;
  border-radius: 7px;
  font-weight: 600;
  font-size: 0.9rem;
  text-decoration: none;
  cursor: pointer;
  border: none;
  transition: all 0.2s;
  white-space: nowrap;
}

.l-btn-primary {
  background: linear-gradient(135deg, #5372f0 0%, #3b5bdb 100%);
  color: #fff;
}

.l-btn-primary:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(83, 114, 240, 0.35);
}

.l-btn-ghost {
  background: transparent;
  border: 1px solid rgba(83, 114, 240, 0.35);
  color: #5372f0;
}

.l-btn-ghost:hover {
  border-color: #5372f0;
  background: rgba(83, 114, 240, 0.1);
}

.l-btn-lg {
  padding: 0.8rem 1.75rem;
  font-size: 0.95rem;
}

.l-btn-full {
  width: 100%;
  justify-content: center;
  margin-top: 1.5rem;
}

/* ---- NAVBAR ---- */
.l-nav {
  position: sticky;
  top: 0;
  z-index: 200;
  background: rgba(11, 18, 32, 0.7);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  border-bottom: 1px solid transparent;
  transition: border-color 0.3s, background 0.3s;
  padding: 0 1.5rem;
}

.l-nav.scrolled {
  background: rgba(11, 18, 32, 0.95);
  border-bottom-color: rgba(83, 114, 240, 0.15);
}

.l-nav-inner {
  max-width: 1160px;
  margin: 0 auto;
  display: flex;
  align-items: center;
  gap: 2rem;
  height: 60px;
}

.l-logo {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  font-size: 1.15rem;
  font-weight: 800;
  color: #fff;
  text-decoration: none;
  letter-spacing: -0.3px;
  flex-shrink: 0;
}

.l-nav-links {
  display: flex;
  gap: 2rem;
  margin-left: auto;
}

.l-nav-links a {
  color: #9aa0a6;
  text-decoration: none;
  font-size: 0.9rem;
  font-weight: 500;
  transition: color 0.2s;
}

.l-nav-links a:hover {
  color: #5372f0;
}

.l-nav-cta {
  display: flex;
  gap: 0.75rem;
  align-items: center;
  margin-left: auto;
}

.l-hamburger {
  display: none;
  flex-direction: column;
  gap: 5px;
  background: none;
  border: none;
  cursor: pointer;
  padding: 4px;
  margin-left: auto;
}

.l-hamburger span {
  display: block;
  width: 22px;
  height: 2px;
  background: #e0e0e0;
  border-radius: 2px;
  transition: all 0.25s;
}

/* ---- HERO ---- */
.l-hero {
  padding: 5rem 1.5rem 4rem;
  position: relative;
}

.l-hero::before {
  content: '';
  position: absolute;
  top: 0;
  left: 50%;
  transform: translateX(-50%);
  width: 600px;
  height: 400px;
  background: radial-gradient(ellipse at center, rgba(83, 114, 240, 0.12) 0%, transparent 70%);
  pointer-events: none;
}

.l-hero-inner {
  max-width: 1160px;
  margin: 0 auto;
  display: grid;
  grid-template-columns: 1fr 1.1fr;
  gap: 4rem;
  align-items: center;
}

.l-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  background: rgba(83, 114, 240, 0.1);
  border: 1px solid rgba(83, 114, 240, 0.25);
  border-radius: 20px;
  padding: 0.3rem 0.85rem;
  font-size: 0.8rem;
  font-weight: 600;
  color: #5372f0;
  margin-bottom: 1.5rem;
}

.l-badge-dot {
  width: 6px;
  height: 6px;
  background: #3ddc84;
  border-radius: 50%;
  animation: l-pulse-dot 2s infinite;
}

@keyframes l-pulse-dot {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.5; transform: scale(0.8); }
}

.l-hero-title {
  font-size: 2.8rem;
  font-weight: 900;
  line-height: 1.1;
  color: #fff;
  margin: 0 0 1.25rem;
}

.l-hero-sub {
  font-size: 1rem;
  color: #9aa0a6;
  line-height: 1.75;
  margin: 0 0 2rem;
  max-width: 480px;
}

.l-hero-actions {
  display: flex;
  gap: 0.75rem;
  flex-wrap: wrap;
  margin-bottom: 1.5rem;
}

.l-hero-proof {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.l-proof-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.83rem;
  color: #9aa0a6;
}

/* ---- HERO VISUAL ---- */
.l-hero-visual {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.l-card-glow {
  position: absolute;
  top: 20%;
  left: 50%;
  transform: translateX(-50%);
  width: 300px;
  height: 300px;
  background: radial-gradient(circle, rgba(83, 114, 240, 0.15) 0%, transparent 70%);
  pointer-events: none;
  z-index: 0;
}

/* REALISTIC DEVICE CARD */
.l-mock-card {
  position: relative;
  z-index: 1;
  background: #16213e;
  border: 1px solid rgba(83, 114, 240, 0.2);
  border-radius: 10px;
  overflow: hidden;
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.5);
  animation: l-float 6s ease-in-out infinite;
}

.l-mock-card.critical {
  border-color: rgba(233, 69, 96, 0.4);
  animation: l-pulse-critical-border 2s ease-in-out infinite, l-float 6s ease-in-out infinite;
}

@keyframes l-float {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-8px); }
}

@keyframes l-pulse-critical-border {
  0%, 100% { border-color: rgba(233, 69, 96, 0.4); box-shadow: 0 0 0 0 rgba(233, 69, 96, 0); }
  50% { border-color: rgba(233, 69, 96, 0.7); box-shadow: 0 0 12px rgba(233, 69, 96, 0.2); }
}

.l-mock-card-peek {
  opacity: 0.7;
  transform: scale(0.96);
  animation-delay: 0.5s;
}

.l-mock-card-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.75rem 1rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  background: rgba(15, 52, 96, 0.4);
}

.l-mock-card-title-area {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex: 1;
  min-width: 0;
}

.l-mock-device-name {
  font-size: 0.88rem;
  font-weight: 700;
  color: #fff;
}

.l-mock-device-sub {
  font-size: 0.72rem;
  color: #9aa0a6;
  font-family: 'Courier New', monospace;
}

.l-mock-status-dot {
  width: 9px;
  height: 9px;
  border-radius: 50%;
  flex-shrink: 0;
}

.l-mock-status-dot.ok { background: #3ddc84; box-shadow: 0 0 6px rgba(61, 220, 132, 0.5); }
.l-mock-status-dot.warning { background: #fbbf24; box-shadow: 0 0 6px rgba(251, 191, 36, 0.5); animation: l-pulse-dot 2s infinite; }
.l-mock-status-dot.critical { background: #e94560; box-shadow: 0 0 6px rgba(233, 69, 96, 0.5); animation: l-pulse-dot 1.2s infinite; }

.l-mock-card-badges {
  display: flex;
  gap: 0.35rem;
  flex-shrink: 0;
}

.l-mock-badge {
  font-size: 0.68rem;
  font-weight: 700;
  padding: 2px 7px;
  border-radius: 4px;
  letter-spacing: 0.3px;
  text-transform: uppercase;
}

.l-mock-badge.group {
  background: rgba(83, 114, 240, 0.15);
  color: #5372f0;
  border: 1px solid rgba(83, 114, 240, 0.3);
}

.l-mock-badge.ok {
  background: rgba(61, 220, 132, 0.12);
  color: #3ddc84;
  border: 1px solid rgba(61, 220, 132, 0.25);
}

.l-mock-badge.warning {
  background: rgba(251, 191, 36, 0.12);
  color: #fbbf24;
  border: 1px solid rgba(251, 191, 36, 0.25);
}

.l-mock-badge.critical {
  background: rgba(233, 69, 96, 0.12);
  color: #e94560;
  border: 1px solid rgba(233, 69, 96, 0.3);
}

.l-mock-card-actions {
  display: flex;
  gap: 0.25rem;
  flex-shrink: 0;
}

.l-mock-action-btn {
  font-size: 0.8rem;
  color: #9aa0a6;
  cursor: default;
  padding: 2px 5px;
}

/* SENSOR ROWS */
.l-mock-sensor {
  padding: 0.6rem 1rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
}

.l-mock-sensor:last-of-type {
  border-bottom: none;
}

.l-mock-sensor.warning {
  background: rgba(251, 191, 36, 0.03);
}

.l-mock-sensor.critical {
  background: rgba(233, 69, 96, 0.04);
}

.l-mock-sensor-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.4rem;
}

.l-mock-sensor-left {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.l-mock-sensor-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  flex-shrink: 0;
}

.l-mock-sensor-dot.ok { background: #3ddc84; }
.l-mock-sensor-dot.warning { background: #fbbf24; animation: l-pulse-dot 2s infinite; }
.l-mock-sensor-dot.critical { background: #e94560; animation: l-pulse-dot 1.2s infinite; }

.l-mock-sensor-name {
  font-size: 0.8rem;
  font-weight: 600;
  color: #e0e0e0;
}

.l-mock-sensor-type {
  font-size: 0.65rem;
  color: #9aa0a6;
  background: rgba(255, 255, 255, 0.05);
  padding: 1px 5px;
  border-radius: 3px;
  text-transform: lowercase;
  font-family: 'Courier New', monospace;
}

.l-mock-sensor-status {
  font-size: 0.68rem;
  font-weight: 700;
  letter-spacing: 0.5px;
}

.l-mock-sensor-status.ok { color: #3ddc84; }
.l-mock-sensor-status.warning { color: #fbbf24; }
.l-mock-sensor-status.critical { color: #e94560; }

.l-mock-sensor-metrics {
  display: flex;
  gap: 1rem;
  flex-wrap: wrap;
}

.l-mock-metric {
  display: flex;
  align-items: center;
  gap: 0.3rem;
  font-size: 0.75rem;
}

.l-mock-metric-label {
  color: #9aa0a6;
}

.l-mock-metric-value {
  font-family: 'Courier New', monospace;
  font-weight: 700;
  color: #e0e0e0;
}

.l-mock-metric-value.ok { color: #3ddc84; }
.l-mock-metric-value.warning { color: #fbbf24; }
.l-mock-metric-value.critical { color: #e94560; }

.l-mock-card-footer {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.5rem 1rem;
  background: rgba(0, 0, 0, 0.2);
  font-size: 0.68rem;
  color: #9aa0a6;
}

.l-mock-realtime-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: #3ddc84;
  animation: l-pulse-dot 2s infinite;
}

/* ---- COMPATIBILITY BAR ---- */
.l-compat {
  background: rgba(15, 52, 96, 0.3);
  border-top: 1px solid rgba(83, 114, 240, 0.1);
  border-bottom: 1px solid rgba(83, 114, 240, 0.1);
  padding: 1.25rem 1.5rem;
}

.l-compat-inner {
  max-width: 1160px;
  margin: 0 auto;
  display: flex;
  align-items: center;
  gap: 1.5rem;
  flex-wrap: wrap;
  justify-content: center;
}

.l-compat-label {
  font-size: 0.8rem;
  color: #9aa0a6;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 1px;
}

.l-compat-items {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
  justify-content: center;
}

.l-compat-item {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.85rem;
  font-weight: 600;
  color: #e0e0e0;
}

.l-compat-sep {
  color: rgba(83, 114, 240, 0.4);
  font-weight: 300;
}

.l-compat-note {
  font-size: 0.75rem;
  color: #9aa0a6;
  width: 100%;
  text-align: center;
}

/* ---- PROBLEM / SOLUTION ---- */
.l-problem-solution {
  background: linear-gradient(180deg, #0b1220 0%, #0d1a2e 100%);
}

.l-ps-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 4rem;
  align-items: start;
}

.l-problem-list,
.l-solution-list {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
  margin-top: 1.5rem;
}

.l-problem-item {
  display: flex;
  gap: 0.75rem;
}

.l-problem-icon {
  flex-shrink: 0;
  margin-top: 3px;
}

.l-problem-item strong {
  display: block;
  font-size: 0.9rem;
  color: #fff;
  margin-bottom: 0.2rem;
}

.l-problem-item p {
  font-size: 0.85rem;
  color: #9aa0a6;
  margin: 0;
}

.l-solution-item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  font-size: 0.9rem;
  color: #e0e0e0;
  background: rgba(61, 220, 132, 0.05);
  border: 1px solid rgba(61, 220, 132, 0.1);
  border-radius: 8px;
  padding: 0.65rem 0.9rem;
}

.l-solution-icon {
  flex-shrink: 0;
}

/* ---- FEATURES GRID ---- */
.l-features {
  background: #0d1629;
}

.l-features-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1.25rem;
}

.l-feature-card {
  background: #16213e;
  border: 1px solid rgba(83, 114, 240, 0.12);
  border-radius: 10px;
  padding: 1.5rem;
  transition: all 0.25s;
}

.l-feature-card:hover {
  border-color: rgba(83, 114, 240, 0.35);
  transform: translateY(-4px);
  box-shadow: 0 8px 28px rgba(83, 114, 240, 0.1);
}

.l-feature-icon {
  width: 44px;
  height: 44px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 1rem;
}

.l-feature-icon.blue { background: rgba(83, 114, 240, 0.12); color: #5372f0; }
.l-feature-icon.green { background: rgba(61, 220, 132, 0.1); color: #3ddc84; }
.l-feature-icon.purple { background: rgba(147, 112, 219, 0.12); color: #9370db; }
.l-feature-icon.orange { background: rgba(251, 191, 36, 0.1); color: #fbbf24; }

.l-feature-card h3 {
  font-size: 0.95rem;
  font-weight: 700;
  color: #fff;
  margin: 0 0 0.5rem;
}

.l-feature-card p {
  font-size: 0.83rem;
  color: #9aa0a6;
  line-height: 1.6;
  margin: 0 0 0.75rem;
}

.l-feature-tag {
  font-size: 0.7rem;
  color: #5372f0;
  background: rgba(83, 114, 240, 0.08);
  border-radius: 4px;
  padding: 3px 7px;
  display: inline-block;
  font-family: 'Courier New', monospace;
}

/* ---- HOW IT WORKS ---- */
.l-how {
  background: #0b1220;
}

.l-steps {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 2rem;
  position: relative;
}

.l-steps::before {
  content: '';
  position: absolute;
  top: 40px;
  left: calc(16.66% + 20px);
  right: calc(16.66% + 20px);
  height: 1px;
  background: linear-gradient(90deg, #5372f0 0%, #3ddc84 100%);
  opacity: 0.3;
}

.l-step {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  position: relative;
}

.l-step-number {
  position: absolute;
  top: -8px;
  right: 0;
  font-size: 5rem;
  font-weight: 900;
  color: rgba(83, 114, 240, 0.06);
  line-height: 1;
  user-select: none;
}

.l-step-icon {
  width: 64px;
  height: 64px;
  background: rgba(15, 52, 96, 0.5);
  border: 1px solid rgba(83, 114, 240, 0.2);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 1.25rem;
  position: relative;
  z-index: 1;
}

.l-step h3 {
  font-size: 1rem;
  font-weight: 700;
  color: #fff;
  margin: 0 0 0.5rem;
}

.l-step p {
  font-size: 0.83rem;
  color: #9aa0a6;
  line-height: 1.6;
  margin: 0;
}

/* ---- SHOWCASE ---- */
.l-showcase {
  background: #080f1c;
}

.l-showcase-window {
  border: 1px solid rgba(83, 114, 240, 0.2);
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 24px 60px rgba(0, 0, 0, 0.6);
}

.l-showcase-topbar {
  background: #0f1e35;
  padding: 0.75rem 1.25rem;
  display: flex;
  align-items: center;
  gap: 1rem;
  border-bottom: 1px solid rgba(83, 114, 240, 0.1);
}

.l-showcase-dots {
  display: flex;
  gap: 5px;
}

.l-showcase-dots span {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.15);
}

.l-showcase-url {
  font-size: 0.75rem;
  color: #9aa0a6;
  font-family: 'Courier New', monospace;
  flex: 1;
  text-align: center;
}

.l-showcase-realtime {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.72rem;
  color: #3ddc84;
  font-weight: 600;
}

.l-realtime-dot {
  width: 6px;
  height: 6px;
  background: #3ddc84;
  border-radius: 50%;
  animation: l-pulse-dot 1.5s infinite;
}

.l-showcase-body {
  padding: 1.25rem;
  background: #0b1220;
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1rem;
  min-height: 280px;
}

.l-showcase-card {
  background: #16213e;
  border-radius: 8px;
  overflow: hidden;
}

.l-showcase-card.ok { border: 1px solid rgba(61, 220, 132, 0.15); }
.l-showcase-card.warning { border: 1px solid rgba(251, 191, 36, 0.25); }
.l-showcase-card.critical {
  border: 1px solid rgba(233, 69, 96, 0.35);
  animation: l-pulse-critical-border 2s ease-in-out infinite;
}

.l-showcase-card-header {
  padding: 0.6rem 0.75rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
  background: rgba(15, 52, 96, 0.3);
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}

.l-showcase-card-title-row {
  display: flex;
  align-items: center;
  gap: 0.4rem;
}

.l-showcase-card-name {
  font-size: 0.8rem;
  font-weight: 700;
  color: #fff;
  flex: 1;
}

.l-showcase-card-ip {
  font-size: 0.65rem;
  color: #9aa0a6;
  font-family: 'Courier New', monospace;
}

.l-showcase-sensors {
  padding: 0.5rem 0.75rem;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.l-showcase-sensor-row {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.75rem;
  color: #9aa0a6;
}

.l-showcase-sensor-row span:nth-child(2) {
  flex: 1;
}

.l-ms {
  font-family: 'Courier New', monospace;
  font-size: 0.7rem;
  color: #9aa0a6;
}

.warning-text { color: #fbbf24 !important; }
.critical-text { color: #e94560 !important; }

.l-showcase-card-placeholder {
  background: rgba(22, 33, 62, 0.4);
  border: 1px solid rgba(255, 255, 255, 0.04);
  border-radius: 8px;
  padding: 1rem;
}

.l-placeholder-line {
  height: 8px;
  background: rgba(255, 255, 255, 0.06);
  border-radius: 4px;
  margin-bottom: 6px;
}

.l-showcase-caption {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.78rem;
  color: #9aa0a6;
  margin-top: 1rem;
  justify-content: center;
}

/* ---- ALERTS ---- */
.l-alerts {
  background: #0d1629;
}

.l-split {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 4rem;
  align-items: center;
}

.l-split-reverse {
  direction: rtl;
}

.l-split-reverse > * {
  direction: ltr;
}

.l-split-desc {
  font-size: 0.9rem;
  color: #9aa0a6;
  line-height: 1.7;
  margin: 0.75rem 0 1.5rem;
}

.l-alert-features {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.l-alert-feature {
  display: flex;
  gap: 0.75rem;
  align-items: flex-start;
}

.l-af-icon {
  width: 36px;
  height: 36px;
  background: rgba(83, 114, 240, 0.1);
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.l-alert-feature strong {
  display: block;
  font-size: 0.88rem;
  color: #fff;
  margin-bottom: 0.15rem;
}

.l-alert-feature p {
  font-size: 0.82rem;
  color: #9aa0a6;
  margin: 0;
}

/* Telegram mock */
.l-telegram-mock {
  background: #17212b;
  border-radius: 12px;
  overflow: hidden;
  max-width: 340px;
  margin: 0 auto;
  box-shadow: 0 16px 48px rgba(0, 0, 0, 0.5);
}

.l-telegram-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.85rem 1rem;
  background: #1c2733;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.l-telegram-avatar {
  width: 38px;
  height: 38px;
  background: rgba(83, 114, 240, 0.15);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.l-telegram-bot-name {
  font-size: 0.88rem;
  font-weight: 700;
  color: #fff;
}

.l-telegram-bot-sub {
  font-size: 0.72rem;
  color: #3ddc84;
}

.l-telegram-messages {
  padding: 0.75rem;
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}

.l-tg-msg {
  border-radius: 8px;
  overflow: hidden;
  font-size: 0.78rem;
}

.l-tg-msg-header {
  padding: 0.4rem 0.75rem;
  font-weight: 700;
  font-size: 0.8rem;
}

.l-tg-msg-body {
  padding: 0.5rem 0.75rem 0.6rem;
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
  color: #e0e0e0;
}

.l-tg-msg-ts {
  font-size: 0.68rem;
  color: #9aa0a6;
  margin-top: 0.25rem;
}

.critical-msg { background: rgba(233, 69, 96, 0.08); border: 1px solid rgba(233, 69, 96, 0.25); }
.critical-msg .l-tg-msg-header { color: #e94560; background: rgba(233, 69, 96, 0.08); }

.ok-msg { background: rgba(61, 220, 132, 0.06); border: 1px solid rgba(61, 220, 132, 0.2); }
.ok-msg .l-tg-msg-header { color: #3ddc84; background: rgba(61, 220, 132, 0.06); }

/* ---- AI REPORTS ---- */
.l-reports {
  background: #0b1220;
}

.l-report-mock {
  background: #16213e;
  border: 1px solid rgba(83, 114, 240, 0.2);
  border-radius: 12px;
  overflow: hidden;
  max-width: 400px;
  margin: 0 auto;
  box-shadow: 0 16px 48px rgba(0, 0, 0, 0.4);
}

.l-report-header {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  padding: 1rem;
  background: rgba(15, 52, 96, 0.4);
  border-bottom: 1px solid rgba(83, 114, 240, 0.1);
}

.l-report-title {
  font-size: 0.88rem;
  font-weight: 700;
  color: #fff;
}

.l-report-period {
  font-size: 0.72rem;
  color: #9aa0a6;
  margin-top: 2px;
}

.l-report-stats {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0;
  padding: 0;
}

.l-report-stat {
  padding: 0.85rem 0.75rem;
  border-right: 1px solid rgba(255, 255, 255, 0.05);
  text-align: center;
}

.l-report-stat:last-child {
  border-right: none;
}

.l-report-stat-value {
  font-size: 1.1rem;
  font-weight: 800;
  font-family: 'Courier New', monospace;
  color: #e0e0e0;
}

.l-report-stat-value.ok { color: #3ddc84; }
.l-report-stat-value.critical { color: #e94560; }

.l-report-stat-label {
  font-size: 0.65rem;
  color: #9aa0a6;
  margin-top: 2px;
}

.l-report-divider {
  height: 1px;
  background: rgba(255, 255, 255, 0.05);
}

.l-report-ai-text {
  padding: 0.85rem 1rem;
}

.l-report-ai-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  background: rgba(83, 114, 240, 0.1);
  border: 1px solid rgba(83, 114, 240, 0.2);
  border-radius: 4px;
  padding: 2px 7px;
  font-size: 0.68rem;
  font-weight: 700;
  color: #5372f0;
  letter-spacing: 0.5px;
  text-transform: uppercase;
  margin-bottom: 0.5rem;
}

.l-report-ai-text p {
  font-size: 0.8rem;
  color: #9aa0a6;
  line-height: 1.65;
  margin: 0;
}

.l-report-footer-note {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.5rem 1rem;
  background: rgba(0, 0, 0, 0.15);
  font-size: 0.68rem;
  color: #9aa0a6;
  border-top: 1px solid rgba(255, 255, 255, 0.04);
}

.l-report-options {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  margin-top: 0.5rem;
}

.l-report-option {
  display: flex;
  gap: 0.75rem;
  align-items: flex-start;
}

.l-ro-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
  margin-top: 5px;
}

.l-ro-dot.blue { background: #5372f0; }
.l-ro-dot.green { background: #3ddc84; }
.l-ro-dot.purple { background: #9370db; }

.l-report-option strong {
  display: block;
  font-size: 0.88rem;
  color: #fff;
  margin-bottom: 0.15rem;
}

.l-report-option p {
  font-size: 0.82rem;
  color: #9aa0a6;
  margin: 0;
}

/* ---- PRICING ---- */
.l-pricing {
  background: #0d1629;
}

.l-pricing-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1.25rem;
  align-items: start;
}

.l-plan-card {
  background: #16213e;
  border: 1px solid rgba(83, 114, 240, 0.15);
  border-radius: 12px;
  padding: 1.75rem;
  position: relative;
}

.l-plan-featured {
  border-color: rgba(83, 114, 240, 0.4);
  background: linear-gradient(180deg, rgba(83, 114, 240, 0.08) 0%, #16213e 100%);
  box-shadow: 0 0 0 1px rgba(83, 114, 240, 0.25), 0 16px 40px rgba(83, 114, 240, 0.1);
}

.l-plan-popular-badge {
  position: absolute;
  top: -11px;
  left: 50%;
  transform: translateX(-50%);
  background: linear-gradient(135deg, #5372f0 0%, #3b5bdb 100%);
  color: #fff;
  font-size: 0.72rem;
  font-weight: 700;
  padding: 3px 12px;
  border-radius: 20px;
  white-space: nowrap;
  letter-spacing: 0.3px;
}

.l-plan-name {
  font-size: 1.1rem;
  font-weight: 800;
  color: #fff;
  margin-bottom: 0.25rem;
}

.l-plan-desc {
  font-size: 0.8rem;
  color: #9aa0a6;
  margin-bottom: 1.25rem;
  line-height: 1.4;
}

.l-plan-price {
  display: flex;
  align-items: baseline;
  gap: 0.25rem;
  margin-bottom: 1.25rem;
}

.l-plan-price-label {
  font-size: 0.78rem;
  color: #9aa0a6;
}

.l-plan-price-value {
  font-size: 2rem;
  font-weight: 900;
  color: #fff;
  line-height: 1;
}

.l-plan-price-period {
  font-size: 0.8rem;
  color: #9aa0a6;
}

.l-plan-features {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}

.l-plan-features li {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.83rem;
  color: #e0e0e0;
}

.l-plan-feature-disabled {
  color: #9aa0a6 !important;
  opacity: 0.5;
}

.l-plan-addons {
  background: rgba(22, 33, 62, 0.6);
  border-style: dashed;
}

.l-plan-addons-list {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  margin-bottom: 1.25rem;
}

.l-addon {
  display: flex;
  gap: 0.75rem;
  align-items: flex-start;
}

.l-addon-icon {
  width: 36px;
  height: 36px;
  background: rgba(83, 114, 240, 0.08);
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.l-addon strong {
  display: block;
  font-size: 0.85rem;
  color: #fff;
  margin-bottom: 0.15rem;
}

.l-addon p {
  font-size: 0.78rem;
  color: #9aa0a6;
  margin: 0;
}

.l-addon-note {
  font-size: 0.75rem;
  color: #9aa0a6;
  background: rgba(83, 114, 240, 0.05);
  border: 1px solid rgba(83, 114, 240, 0.1);
  border-radius: 6px;
  padding: 0.5rem 0.75rem;
  margin-bottom: 0.5rem;
  line-height: 1.5;
}

/* ---- CTA BANNER ---- */
.l-cta-banner {
  background: linear-gradient(135deg, rgba(83, 114, 240, 0.12) 0%, rgba(61, 220, 132, 0.06) 100%);
  border-top: 1px solid rgba(83, 114, 240, 0.2);
  border-bottom: 1px solid rgba(83, 114, 240, 0.2);
  padding: 4rem 1.5rem;
}

.l-cta-inner {
  max-width: 1160px;
  margin: 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 2rem;
  flex-wrap: wrap;
}

.l-cta-text h2 {
  font-size: 1.6rem;
  font-weight: 800;
  color: #fff;
  margin: 0 0 0.5rem;
}

.l-cta-text p {
  font-size: 0.9rem;
  color: #9aa0a6;
  margin: 0;
}

.l-cta-actions {
  display: flex;
  gap: 0.75rem;
  flex-shrink: 0;
}

/* ---- FOOTER ---- */
.l-footer {
  background: rgba(8, 15, 28, 0.95);
  border-top: 1px solid rgba(83, 114, 240, 0.1);
  padding: 3.5rem 1.5rem 2rem;
}

.l-footer-grid {
  display: grid;
  grid-template-columns: 2fr 1fr 1fr 1fr;
  gap: 2.5rem;
  margin-bottom: 2.5rem;
}

.l-footer-brand .l-logo {
  font-size: 1rem;
}

.l-footer-desc {
  font-size: 0.82rem;
  color: #9aa0a6;
  line-height: 1.65;
  margin: 0;
}

.l-footer-col h4 {
  font-size: 0.78rem;
  font-weight: 700;
  color: #fff;
  text-transform: uppercase;
  letter-spacing: 1px;
  margin: 0 0 0.85rem;
}

.l-footer-col ul {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.l-footer-col a {
  font-size: 0.83rem;
  color: #9aa0a6;
  text-decoration: none;
  transition: color 0.2s;
}

.l-footer-col a:hover {
  color: #5372f0;
}

.l-footer-bottom {
  border-top: 1px solid rgba(83, 114, 240, 0.08);
  padding-top: 1.5rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.75rem;
}

.l-footer-bottom p {
  font-size: 0.8rem;
  color: #9aa0a6;
  margin: 0;
}

.l-footer-tech {
  font-size: 0.72rem;
  color: rgba(83, 114, 240, 0.6);
  font-family: 'Courier New', monospace;
}

/* ============================================================
   RESPONSIVE
   ============================================================ */

@media (max-width: 1024px) {
  .l-hero-title { font-size: 2.2rem; }
  .l-features-grid { grid-template-columns: repeat(2, 1fr); }
  .l-pricing-grid { grid-template-columns: 1fr 1fr; }
  .l-plan-addons { grid-column: 1 / -1; }
}

@media (max-width: 820px) {
  .l-hero-inner { grid-template-columns: 1fr; gap: 2.5rem; }
  .l-hero { padding: 4rem 1.5rem 3rem; }
  .l-hero-title { font-size: 2rem; }
  .l-mock-card-peek { display: none; }
  .l-ps-grid { grid-template-columns: 1fr; gap: 2.5rem; }
  .l-split { grid-template-columns: 1fr; gap: 2.5rem; }
  .l-split-reverse { direction: ltr; }
  .l-features-grid { grid-template-columns: 1fr; }
  .l-steps { grid-template-columns: 1fr; gap: 2rem; }
  .l-steps::before { display: none; }
  .l-showcase-body { grid-template-columns: 1fr; }
  .l-showcase-card-placeholder { display: none; }
  .l-pricing-grid { grid-template-columns: 1fr; }
  .l-plan-addons { grid-column: auto; }
  .l-footer-grid { grid-template-columns: 1fr 1fr; }
  .l-footer-brand { grid-column: 1 / -1; }
  .l-cta-inner { flex-direction: column; text-align: center; }
  .l-cta-actions { justify-content: center; }
  .l-nav-links { display: none; }
  .l-nav-links.open {
    display: flex;
    flex-direction: column;
    position: absolute;
    top: 60px;
    left: 0;
    right: 0;
    background: rgba(11, 18, 32, 0.98);
    backdrop-filter: blur(14px);
    padding: 1rem 1.5rem;
    gap: 1rem;
    border-bottom: 1px solid rgba(83, 114, 240, 0.15);
    z-index: 199;
  }
  .l-hamburger { display: flex; }
  .l-nav-cta .l-btn-ghost { display: none; }
}

@media (max-width: 480px) {
  .l-section { padding: 3.5rem 0; }
  .l-hero-title { font-size: 1.7rem; }
  .l-section-title { font-size: 1.5rem; }
  .l-hero-actions { flex-direction: column; }
  .l-footer-grid { grid-template-columns: 1fr; }
  .l-footer-bottom { flex-direction: column; text-align: center; }
  .l-compat-inner { gap: 0.75rem; }
  .l-report-stats { grid-template-columns: repeat(3, 1fr); }
  .l-plan-price-value { font-size: 1.6rem; }
  .l-cta-text h2 { font-size: 1.3rem; }
}

/* ============================================================
   HERO BULLETS (nuevo)
   ============================================================ */
.l-hero-bullets {
  list-style: none;
  padding: 0;
  margin: 0 0 2rem;
  display: flex;
  flex-direction: column;
  gap: 0.55rem;
}

.l-hero-bullets li {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  font-size: 0.9rem;
  color: #cfd3d9;
}

.l-hero-bullets li svg {
  flex-shrink: 0;
}

/* ============================================================
   SCENARIOS
   ============================================================ */
.l-scenarios {
  background: linear-gradient(180deg, transparent 0%, rgba(15, 52, 96, 0.12) 50%, transparent 100%);
}

.l-scenarios-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1.5rem;
}

.l-scenario {
  background: #16213e;
  border: 1px solid rgba(83, 114, 240, 0.2);
  border-radius: 12px;
  padding: 1.5rem;
  display: flex;
  flex-direction: column;
  position: relative;
  transition: transform 0.25s, border-color 0.25s, box-shadow 0.25s;
}

.l-scenario:hover {
  transform: translateY(-4px);
  border-color: rgba(83, 114, 240, 0.5);
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.4);
}

.l-scenario-time {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  background: rgba(83, 114, 240, 0.12);
  border: 1px solid rgba(83, 114, 240, 0.3);
  color: #5372f0;
  font-size: 0.7rem;
  font-weight: 700;
  letter-spacing: 0.5px;
  text-transform: uppercase;
  padding: 0.3rem 0.7rem;
  border-radius: 20px;
  align-self: flex-start;
  margin-bottom: 1rem;
}

.l-scenario h3 {
  font-size: 1.15rem;
  color: #fff;
  margin: 0 0 0.35rem;
  font-weight: 700;
}

.l-scenario-sub {
  font-size: 0.78rem;
  color: #9aa0a6;
  margin: 0 0 1.1rem;
}

.l-scenario-body {
  flex: 1;
}

.l-scenario-body p {
  font-size: 0.88rem;
  color: #cfd3d9;
  line-height: 1.6;
  margin: 0 0 0.9rem;
}

.l-scenario-body p:last-child {
  margin-bottom: 0;
}

/* Scenario 1 — chat mock */
.l-scenario-chat {
  background: #0b1220;
  border-radius: 8px;
  padding: 0.85rem;
  margin: 0.9rem 0;
  border: 1px solid rgba(233, 69, 96, 0.25);
}

.l-sc-msg {
  font-size: 0.8rem;
  line-height: 1.5;
}

.l-sc-msg.critical {
  color: #fff;
  font-weight: 600;
}

.l-sc-msg.critical span {
  display: block;
  margin-top: 3px;
  color: #e94560;
  font-weight: 500;
  font-size: 0.75rem;
  font-family: 'Courier New', monospace;
}

/* Scenario 2 — progress bar */
.l-scenario-progress {
  background: #0b1220;
  border-radius: 8px;
  padding: 0.85rem;
  margin: 0.9rem 0;
  border: 1px solid rgba(83, 114, 240, 0.2);
}

.l-sc-prog-label {
  display: flex;
  justify-content: space-between;
  font-size: 0.8rem;
  color: #cfd3d9;
  margin-bottom: 0.45rem;
}

.l-sc-prog-label strong {
  color: #3ddc84;
}

.l-sc-prog-bar {
  height: 6px;
  background: rgba(83, 114, 240, 0.12);
  border-radius: 3px;
  overflow: hidden;
  margin-bottom: 0.6rem;
}

.l-sc-prog-fill {
  height: 100%;
  background: linear-gradient(90deg, #5372f0, #3ddc84);
  border-radius: 3px;
  animation: l-prog-pulse 2.2s ease-in-out infinite;
}

@keyframes l-prog-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.7; }
}

.l-sc-prog-foot {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.72rem;
  color: #9aa0a6;
}

.l-sc-prog-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  display: inline-block;
}

.l-sc-prog-dot.ok { background: #3ddc84; }
.l-sc-prog-dot.critical { background: #e94560; margin-left: 0.35rem; }

/* Scenario 3 — discovery list */
.l-scenario-discovery {
  background: #0b1220;
  border-radius: 8px;
  padding: 0.6rem 0.85rem;
  margin: 0.9rem 0;
  border: 1px solid rgba(61, 220, 132, 0.2);
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.l-sc-disc-row {
  display: grid;
  grid-template-columns: 1fr 1.4fr auto;
  gap: 0.5rem;
  align-items: center;
  font-size: 0.75rem;
  padding: 0.25rem 0;
  border-bottom: 1px dashed rgba(83, 114, 240, 0.08);
}

.l-sc-disc-row:last-child {
  border-bottom: none;
}

.l-sc-disc-row.ghost {
  opacity: 0.55;
  font-style: italic;
}

.l-sc-disc-ip {
  color: #9aa0a6;
  font-family: 'Courier New', monospace;
}

.l-sc-disc-vendor {
  color: #cfd3d9;
  font-weight: 600;
}

.l-sc-disc-vendor.mikrotik { color: #5372f0; }
.l-sc-disc-vendor.ubnt { color: #3ddc84; }

.l-sc-disc-status {
  color: #3ddc84;
  font-weight: 700;
  font-size: 0.72rem;
}

.l-scenario-outcome {
  margin-top: 1.1rem;
  padding-top: 1.1rem;
  border-top: 1px solid rgba(83, 114, 240, 0.15);
  font-size: 0.83rem;
  color: #cfd3d9;
  line-height: 1.55;
}

.l-scenario-outcome strong {
  color: #3ddc84;
  font-weight: 700;
}

/* ============================================================
   TERMINAL + AI COPILOT
   ============================================================ */
.l-terminal {
  background: linear-gradient(180deg, transparent 0%, rgba(15, 52, 96, 0.1) 100%);
}

.l-term-features {
  display: flex;
  flex-direction: column;
  gap: 1.1rem;
  margin-top: 1.5rem;
}

.l-term-feature {
  display: flex;
  gap: 0.9rem;
  align-items: flex-start;
}

.l-tf-icon {
  flex-shrink: 0;
  width: 36px;
  height: 36px;
  background: rgba(83, 114, 240, 0.12);
  border: 1px solid rgba(83, 114, 240, 0.3);
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.l-term-feature strong {
  display: block;
  color: #fff;
  font-size: 0.95rem;
  margin-bottom: 0.2rem;
}

.l-term-feature p {
  font-size: 0.85rem;
  color: #9aa0a6;
  margin: 0;
  line-height: 1.55;
}

/* Terminal mock */
.l-term-mock {
  background: #0a0f1a;
  border-radius: 10px;
  border: 1px solid rgba(83, 114, 240, 0.25);
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.5);
  overflow: hidden;
  font-family: 'Courier New', 'Monaco', monospace;
}

.l-term-topbar {
  background: #16213e;
  padding: 0.6rem 1rem;
  display: flex;
  align-items: center;
  gap: 0.75rem;
  border-bottom: 1px solid rgba(83, 114, 240, 0.2);
}

.l-term-dots {
  display: flex;
  gap: 6px;
}

.l-term-dots span {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #2a3a5a;
}

.l-term-dots span:nth-child(1) { background: #e94560; }
.l-term-dots span:nth-child(2) { background: #fbbf24; }
.l-term-dots span:nth-child(3) { background: #3ddc84; }

.l-term-title {
  font-size: 0.78rem;
  color: #9aa0a6;
  letter-spacing: 0.3px;
  font-family: -apple-system, sans-serif;
}

.l-term-body {
  padding: 1rem 1.1rem;
  font-size: 0.78rem;
  color: #e0e0e0;
  line-height: 1.55;
}

.l-term-line {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-all;
}

.l-term-prompt {
  color: #3ddc84;
  font-weight: 700;
}

.l-term-cmd {
  color: #fff;
}

.l-term-line.output {
  color: #9aa0a6;
  font-size: 0.74rem;
}

.l-term-spacer {
  height: 0.8rem;
}

.l-term-ai-prompt {
  background: rgba(61, 220, 132, 0.06);
  border-left: 2px solid #3ddc84;
  padding: 0.6rem 0.8rem;
  border-radius: 0 6px 6px 0;
  margin-bottom: 0.7rem;
}

.l-term-ai-label {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.7rem;
  font-weight: 700;
  color: #3ddc84;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  font-family: -apple-system, sans-serif;
  margin-bottom: 0.3rem;
}

.l-term-ai-question {
  color: #cfd3d9;
  font-family: -apple-system, sans-serif;
  font-size: 0.85rem;
  font-style: italic;
}

.l-term-ai-answer {
  background: rgba(83, 114, 240, 0.07);
  border-left: 2px solid #5372f0;
  padding: 0.7rem 0.85rem;
  border-radius: 0 6px 6px 0;
}

.l-term-ai-answer-label {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.7rem;
  font-weight: 700;
  color: #5372f0;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  font-family: -apple-system, sans-serif;
  margin-bottom: 0.5rem;
}

.l-term-ai-code {
  background: #0b1220;
  padding: 0.55rem 0.7rem;
  border-radius: 5px;
  color: #3ddc84;
  font-size: 0.74rem;
  margin-bottom: 0.55rem;
  word-break: break-all;
}

.l-term-ai-actions {
  display: flex;
  gap: 0.45rem;
}

.l-term-ai-btn {
  font-family: -apple-system, sans-serif;
  font-size: 0.72rem;
  font-weight: 600;
  padding: 0.3rem 0.7rem;
  border-radius: 5px;
  border: 1px solid rgba(83, 114, 240, 0.35);
  color: #5372f0;
  cursor: pointer;
}

.l-term-ai-btn.primary {
  background: linear-gradient(135deg, #5372f0 0%, #3b5bdb 100%);
  color: #fff;
  border-color: transparent;
}

.l-term-footer {
  background: #16213e;
  padding: 0.5rem 1rem;
  border-top: 1px solid rgba(83, 114, 240, 0.2);
  font-size: 0.72rem;
  color: #9aa0a6;
  font-family: -apple-system, sans-serif;
  display: flex;
  align-items: center;
  gap: 0.4rem;
}

.l-term-cursor {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #3ddc84;
  animation: l-pulse-dot 1.1s infinite;
}

/* ============================================================
   AUTOMATION
   ============================================================ */
.l-auto-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 1.25rem;
}

.l-auto-card {
  background: #16213e;
  border: 1px solid rgba(83, 114, 240, 0.18);
  border-radius: 11px;
  padding: 1.4rem;
  transition: transform 0.25s, border-color 0.25s;
}

.l-auto-card:hover {
  transform: translateY(-3px);
  border-color: rgba(83, 114, 240, 0.45);
}

.l-auto-card-head {
  display: flex;
  gap: 0.85rem;
  align-items: center;
  margin-bottom: 0.9rem;
}

.l-auto-icon {
  width: 42px;
  height: 42px;
  border-radius: 9px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.l-auto-icon.blue {
  background: rgba(83, 114, 240, 0.12);
  border: 1px solid rgba(83, 114, 240, 0.3);
  color: #5372f0;
}

.l-auto-icon.green {
  background: rgba(61, 220, 132, 0.1);
  border: 1px solid rgba(61, 220, 132, 0.3);
  color: #3ddc84;
}

.l-auto-icon.purple {
  background: rgba(167, 139, 250, 0.1);
  border: 1px solid rgba(167, 139, 250, 0.3);
  color: #a78bfa;
}

.l-auto-icon.orange {
  background: rgba(251, 191, 36, 0.1);
  border: 1px solid rgba(251, 191, 36, 0.3);
  color: #fbbf24;
}

.l-auto-card-title {
  font-size: 1rem;
  font-weight: 700;
  color: #fff;
  line-height: 1.3;
}

.l-auto-card-sub {
  font-size: 0.78rem;
  color: #9aa0a6;
  margin-top: 0.15rem;
}

.l-auto-card-desc {
  font-size: 0.88rem;
  color: #cfd3d9;
  line-height: 1.6;
  margin: 0 0 1rem;
}

.l-auto-card-stat {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.55rem 0.75rem;
  background: #0b1220;
  border-radius: 6px;
  font-size: 0.78rem;
  color: #9aa0a6;
}

.l-auto-stat-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  flex-shrink: 0;
}

.l-auto-stat-dot.ok {
  background: #3ddc84;
  box-shadow: 0 0 6px rgba(61, 220, 132, 0.5);
}

.l-auto-footer-note {
  margin-top: 2rem;
  display: flex;
  align-items: center;
  gap: 0.6rem;
  justify-content: center;
  font-size: 0.85rem;
  color: #9aa0a6;
  text-align: center;
}

/* ============================================================
   SECURITY
   ============================================================ */
.l-security {
  padding: 3rem 0;
}

.l-security-band {
  background: linear-gradient(135deg, rgba(61, 220, 132, 0.04) 0%, rgba(83, 114, 240, 0.06) 100%);
  border: 1px solid rgba(61, 220, 132, 0.18);
  border-radius: 14px;
  padding: 2.5rem 2rem;
}

.l-security-head {
  text-align: center;
  max-width: 620px;
  margin: 0 auto 2.5rem;
}

.l-security-head .l-section-title {
  text-align: center;
}

.l-security-sub {
  color: #9aa0a6;
  font-size: 0.95rem;
  margin: 0.5rem 0 0;
}

.l-security-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 1.5rem;
}

.l-security-item {
  display: flex;
  gap: 1rem;
  align-items: flex-start;
  background: rgba(11, 18, 32, 0.5);
  border: 1px solid rgba(83, 114, 240, 0.1);
  border-radius: 10px;
  padding: 1.1rem 1.2rem;
}

.l-sec-icon {
  flex-shrink: 0;
  width: 42px;
  height: 42px;
  background: rgba(61, 220, 132, 0.08);
  border: 1px solid rgba(61, 220, 132, 0.25);
  border-radius: 9px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.l-security-item strong {
  display: block;
  color: #fff;
  font-size: 0.95rem;
  margin-bottom: 0.3rem;
}

.l-security-item p {
  color: #9aa0a6;
  font-size: 0.85rem;
  line-height: 1.55;
  margin: 0;
}

/* ============================================================
   FAQ
   ============================================================ */
.l-faq {
  background: linear-gradient(180deg, transparent 0%, rgba(15, 52, 96, 0.1) 100%);
}

.l-faq-grid {
  max-width: 820px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.l-faq-item {
  background: #16213e;
  border: 1px solid rgba(83, 114, 240, 0.18);
  border-radius: 10px;
  overflow: hidden;
  transition: border-color 0.2s;
}

.l-faq-item[open] {
  border-color: rgba(83, 114, 240, 0.45);
}

.l-faq-item summary {
  list-style: none;
  cursor: pointer;
  padding: 1rem 1.3rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  color: #fff;
  font-weight: 600;
  font-size: 0.95rem;
  user-select: none;
}

.l-faq-item summary::-webkit-details-marker {
  display: none;
}

.l-faq-chev {
  flex-shrink: 0;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  border: 1px solid rgba(83, 114, 240, 0.3);
  color: #5372f0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.1rem;
  font-weight: 400;
  transition: transform 0.3s, background 0.2s;
  line-height: 1;
}

.l-faq-item[open] .l-faq-chev {
  transform: rotate(45deg);
  background: rgba(83, 114, 240, 0.12);
}

.l-faq-answer {
  padding: 0 1.3rem 1.15rem;
  color: #cfd3d9;
  font-size: 0.9rem;
  line-height: 1.65;
}

.l-faq-answer p {
  margin: 0;
}

/* ============================================================
   RESPONSIVE — NEW SECTIONS
   ============================================================ */
@media (max-width: 960px) {
  .l-scenarios-grid { grid-template-columns: 1fr; }
  .l-auto-grid { grid-template-columns: 1fr; }
  .l-security-grid { grid-template-columns: 1fr; }
}

@media (max-width: 600px) {
  .l-security-band { padding: 1.75rem 1.25rem; }
  .l-term-mock { font-size: 0.72rem; }
  .l-term-body { padding: 0.8rem 0.85rem; }
  .l-faq-item summary { font-size: 0.9rem; padding: 0.85rem 1rem; }
  .l-faq-answer { padding: 0 1rem 1rem; font-size: 0.86rem; }
  .l-scenario { padding: 1.2rem; }
}
</style>
