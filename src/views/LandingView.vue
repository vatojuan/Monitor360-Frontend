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
            MonitorWISP centraliza el estado de toda tu infraestructura de red en un solo panel.
            API nativa MikroTik, alertas por Telegram, reportes diarios con IA y terminal remota
            integrada — diseñado para WISPs e ISPs que no pueden darse el lujo de enterarse tarde.
          </p>
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
        <span class="l-compat-note">Conexión directa · Maestro (bridge) · Túnel SSH L4</span>
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
                <span>Sondeo cada <strong>10 segundos</strong>, dashboard vía WebSocket</span>
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
            <h3>Tiempo Real · 10 segundos</h3>
            <p>Sondeo continuo con actualizaciones instantáneas vía WebSocket al navegador. No necesitás refrescar — el dashboard se actualiza solo.</p>
            <div class="l-feature-tag">WebSocket · Polling activo</div>
          </div>

          <div class="l-feature-card">
            <div class="l-feature-icon purple">
              <svg width="22" height="22" viewBox="0 0 22 22" fill="none"><rect x="2" y="6" width="8" height="10" rx="2" stroke="currentColor" stroke-width="1.6"/><rect x="12" y="6" width="8" height="10" rx="2" stroke="currentColor" stroke-width="1.6"/><path d="M10 11h2" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>
            </div>
            <h3>Multi-vendor nativo</h3>
            <p>API RouterOS para MikroTik, SSH para Ubiquiti y Linux. Conexión directa, por dispositivo Maestro (bridge) o vía túnel SSH L4 para equipos detrás de NAT.</p>
            <div class="l-feature-tag">MikroTik · Ubiquiti · Linux · SSH</div>
          </div>

          <div class="l-feature-card">
            <div class="l-feature-icon green">
              <svg width="22" height="22" viewBox="0 0 22 22" fill="none"><path d="M11 3l2 4h4l-3 3 1 4-4-2-4 2 1-4-3-3h4z" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/><circle cx="11" cy="11" r="2" fill="currentColor" opacity=".3"/></svg>
            </div>
            <h3>VPN WireGuard integrada</h3>
            <p>Creá perfiles VPN para routers y escritorios en segundos. Acceso remoto seguro a cualquier dispositivo sin abrir puertos públicos. Reconciliación automática de peers.</p>
            <div class="l-feature-tag">WireGuard · BoringTun · Zero-config</div>
          </div>

          <div class="l-feature-card">
            <div class="l-feature-icon orange">
              <svg width="22" height="22" viewBox="0 0 22 22" fill="none"><circle cx="11" cy="11" r="9" stroke="currentColor" stroke-width="1.6" stroke-dasharray="3 2"/><circle cx="11" cy="11" r="3" stroke="currentColor" stroke-width="1.6"/><path d="M11 3v2M11 17v2M3 11h2M17 11h2" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>
            </div>
            <h3>Descubrimiento automático</h3>
            <p>Escaneo de rangos CIDR completos con nmap. Detección automática de vendor y modelo. Adopción de dispositivos en un solo clic desde el panel.</p>
            <div class="l-feature-tag">CIDR scan · nmap · Auto-detección</div>
          </div>

          <div class="l-feature-card">
            <div class="l-feature-icon blue">
              <svg width="22" height="22" viewBox="0 0 22 22" fill="none"><rect x="2" y="4" width="18" height="14" rx="2" stroke="currentColor" stroke-width="1.6"/><path d="M6 9l2 2-2 2M11 13h5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>
            </div>
            <h3>Terminal remota en el navegador</h3>
            <p>Sesión SSH interactiva con xterm.js. Comandos RouterOS API para MikroTik. Asistente IA integrado que sugiere comandos y explica salidas en lenguaje natural.</p>
            <div class="l-feature-tag">xterm.js · RouterOS API · Asistente IA</div>
          </div>

          <div class="l-feature-card">
            <div class="l-feature-icon green">
              <svg width="22" height="22" viewBox="0 0 22 22" fill="none"><path d="M4 18V8l7-5 7 5v10H4z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/><path d="M9 14v4h4v-4" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/><path d="M9 11h4" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>
            </div>
            <h3>Reportes diarios con IA</h3>
            <p>Resumen ejecutivo generado automáticamente a las 07:00 UTC. Análisis de uptime, latencia promedio y eventos críticos. Tonos técnico, ejecutivo o profesional. Entrega por Telegram o Webhook.</p>
            <div class="l-feature-tag">IA · Telegram · Webhook · Tonos</div>
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
            <p>Ingresás las credenciales de acceso: RouterOS API, SSH o SNMP. Compatible con dispositivos detrás de NAT vía túnel L4.</p>
          </div>
          <div class="l-step">
            <div class="l-step-number">2</div>
            <div class="l-step-connector"></div>
            <div class="l-step-icon">
              <svg width="28" height="28" viewBox="0 0 28 28" fill="none"><circle cx="14" cy="14" r="10" stroke="#3ddc84" stroke-width="1.8"/><circle cx="14" cy="14" r="4" fill="#3ddc84" opacity=".3" stroke="#3ddc84" stroke-width="1.8"/><path d="M14 4v4M14 20v4M4 14h4M20 14h4" stroke="#3ddc84" stroke-width="1.8" stroke-linecap="round"/></svg>
            </div>
            <h3>MonitorWISP monitorea</h3>
            <p>Cada sensor es sondeado cada 10 segundos. Ping, señal wireless, tráfico ethernet, CPU, RAM y temperatura — todo en tiempo real en tu dashboard.</p>
          </div>
          <div class="l-step">
            <div class="l-step-number">3</div>
            <div class="l-step-connector last"></div>
            <div class="l-step-icon">
              <svg width="28" height="28" viewBox="0 0 28 28" fill="none"><path d="M14 4a8 8 0 0 1 8 8v4l2 3H4l2-3v-4a8 8 0 0 1 8-8z" stroke="#fbbf24" stroke-width="1.8" stroke-linejoin="round"/><path d="M11 22a3 3 0 0 0 6 0" stroke="#fbbf24" stroke-width="1.8"/></svg>
            </div>
            <h3>Recibís alertas al instante</h3>
            <p>Cuando un sensor supera el umbral, llega la notificación a tu Telegram o Webhook antes de que lo note un cliente. Historial completo y silenciado granular.</p>
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
          El dashboard se actualiza en tiempo real vía WebSocket. Los colores reflejan el peor estado de los sensores del dispositivo.
        </p>
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
            Construido con TimescaleDB · WireGuard · Redis · WebSockets · IA
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
</style>
