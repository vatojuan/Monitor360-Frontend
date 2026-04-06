<script setup>
import { computed, getCurrentInstance } from 'vue'

const props = defineProps({
  modelValue: { type: Object, required: true },
  sensorType: { type: String, required: true }, // 'ping', 'ethernet', 'wireless', 'system'
  channels: { type: Array, default: () => [] },
  autoTasks: { type: Array, default: () => [] },
  deviceInterfaces: { type: Array, default: () => [] },
  suggestedTargetDevices: { type: Array, default: () => [] },
  hasParentMaestro: { type: Boolean, default: false },
  isLoadingInterfaces: { type: Boolean, default: false },
  hideName: { type: Boolean, default: false }, // Útil para acciones masivas
  isCompact: { type: Boolean, default: false } // Útil para la Receta de ScanView
})

const emit = defineEmits(['update:modelValue'])

// Sincronización reactiva con el objeto del padre
const s = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

// Generador de ID único para evitar colisiones de IDs (datalists, labels) si se usa múltiples veces en la misma vista
const uid = getCurrentInstance()?.uid || Math.random().toString(36).substr(2, 9)
</script>

<template>
  <div class="sensor-configurator" :class="{ 'compact-mode': isCompact }">
    
    <template v-if="sensorType === 'ping' && s.config">
      <div class="form-group span-3" v-if="!hideName">
        <label>Nombre del Sensor</label>
        <input type="text" v-model="s.name" required />
      </div>

      <div class="form-group span-2">
        <label>Tipo de Ping</label>
        <select v-model="s.config.ping_type" :disabled="!hasParentMaestro">
          <option value="device_to_external">Ping desde Dispositivo (Salida)</option>
          <option value="maestro_to_device" v-if="hasParentMaestro">Ping al Dispositivo (Desde Maestro)</option>
        </select>
        <p v-if="!hasParentMaestro && !isCompact" class="form-hint warning-text">⚠️ Sin maestro asignado.</p>
      </div>

      <div class="form-group" v-if="s.config.ping_type === 'device_to_external'">
        <label>IP de Destino</label>
        <div style="position: relative">
          <input
            :list="'target-devices-' + uid"
            type="text"
            v-model="s.config.target_ip"
            placeholder="Ej: 8.8.8.8"
            class="search-input"
          />
          <datalist :id="'target-devices-' + uid">
            <option v-for="d in suggestedTargetDevices" :key="d.id" :value="d.ip_address">
              {{ d.client_name }}
            </option>
          </datalist>
        </div>
      </div>

      <div class="form-group">
        <label>Intervalo (s)</label>
        <input type="number" v-model.number="s.config.interval_sec" required min="10" />
      </div>
      <div class="form-group">
        <label>Umbral Latencia (ms)</label>
        <input type="number" v-model.number="s.config.latency_threshold_ms" required />
      </div>
      <div class="form-group">
        <label>Visualización</label>
        <select v-model="s.config.display_mode">
          <option value="realtime">Tiempo Real</option>
          <option value="average">Promedio</option>
        </select>
      </div>
      <div class="form-group" v-if="s.config.display_mode === 'average'">
        <label>Muestras para Promedio</label>
        <input type="number" v-model.number="s.config.average_count" />
      </div>

      <div class="sub-section span-3" v-if="s.ui_alert_timeout && s.ui_alert_latency">
        <h4>Alertas</h4>

        <div class="alert-config-item span-3">
          <div class="form-group checkbox-group">
            <input type="checkbox" v-model="s.ui_alert_timeout.enabled" :id="'pTo-' + uid" />
            <label :for="'pTo-' + uid">Timeout</label>
          </div>
          <template v-if="s.ui_alert_timeout.enabled">
            <div class="form-group">
              <label>Canal</label>
              <select v-model="s.ui_alert_timeout.channel_id">
                <option :value="null">--</option>
                <option v-for="c in channels" :key="c.id" :value="c.id">{{ c.name }}</option>
              </select>
            </div>

            <div class="form-group checkbox-group alert-auto-task">
              <input type="checkbox" v-model="s.ui_alert_timeout.use_auto_task" :id="'pTo_auto-' + uid" />
              <label :for="'pTo_auto-' + uid">⚡ Auto-Remediación</label>
            </div>
            <div class="form-group" v-if="s.ui_alert_timeout.use_auto_task">
              <label>Tarea a Ejecutar</label>
              <select v-model="s.ui_alert_timeout.trigger_task_id">
                <option :value="null">-- Seleccionar Tarea --</option>
                <option v-for="t in autoTasks" :key="t.id" :value="t.id">{{ t.name }}</option>
              </select>
            </div>

            <div class="form-group">
              <label>Enfriamiento (min)</label>
              <input type="number" v-model.number="s.ui_alert_timeout.cooldown_minutes" />
            </div>
            <div class="form-group">
              <label>Tolerancia</label>
              <input type="number" v-model.number="s.ui_alert_timeout.tolerance_count" />
            </div>
            <div class="form-group checkbox-group">
              <input type="checkbox" v-model="s.ui_alert_timeout.notify_recovery" :id="'pToRec-' + uid" />
              <label :for="'pToRec-' + uid">Notificar Reanudación 🟢</label>
            </div>

            <div class="form-group span-3 custom-msg-box">
              <div class="checkbox-group">
                <input type="checkbox" v-model="s.ui_alert_timeout.use_custom_message" :id="'pTo_cmsg-' + uid" />
                <label :for="'pTo_cmsg-' + uid">✏️ Personalizar texto de alerta</label>
              </div>
              <div v-if="s.ui_alert_timeout.use_custom_message" style="margin-top: 0.8rem;">
                <textarea v-model="s.ui_alert_timeout.custom_message" rows="2" class="search-input custom-textarea" placeholder="Ej: Nodo {client_name} ({ip}) no responde. Estado: {status}"></textarea>
                <span class="form-hint">Variables: {client_name}, {ip}, {status}, {sensor_name}</span>
              </div>
            </div>

            <div class="form-group span-3 custom-msg-box" v-if="s.ui_alert_timeout.notify_recovery">
              <div class="checkbox-group">
                <input type="checkbox" v-model="s.ui_alert_timeout.use_custom_recovery_message" :id="'pTo_crmsg-' + uid" />
                <label :for="'pTo_crmsg-' + uid">✏️ Personalizar texto de reanudación</label>
              </div>
              <div v-if="s.ui_alert_timeout.use_custom_recovery_message" style="margin-top: 0.8rem;">
                <textarea v-model="s.ui_alert_timeout.custom_recovery_message" rows="2" class="search-input custom-textarea" placeholder="Ej: 🟢 El nodo {client_name} ha vuelto a la normalidad."></textarea>
                <span class="form-hint">Variables: {client_name}, {ip}, {status}, {sensor_name}</span>
              </div>
            </div>
          </template>
        </div>

        <hr class="separator span-3" />

        <div class="alert-config-item span-3">
          <div class="form-group checkbox-group">
            <input type="checkbox" v-model="s.ui_alert_latency.enabled" :id="'pLat-' + uid" />
            <label :for="'pLat-' + uid">Latencia Alta</label>
          </div>
          <template v-if="s.ui_alert_latency.enabled">
            <div class="form-group">
              <label>Umbral (ms)</label>
              <input type="number" v-model.number="s.ui_alert_latency.threshold_ms" />
            </div>
            <div class="form-group">
              <label>Canal</label>
              <select v-model="s.ui_alert_latency.channel_id">
                <option :value="null">--</option>
                <option v-for="c in channels" :key="c.id" :value="c.id">{{ c.name }}</option>
              </select>
            </div>

            <div class="form-group checkbox-group alert-auto-task">
              <input type="checkbox" v-model="s.ui_alert_latency.use_auto_task" :id="'pLat_auto-' + uid" />
              <label :for="'pLat_auto-' + uid">⚡ Auto-Remediación</label>
            </div>
            <div class="form-group" v-if="s.ui_alert_latency.use_auto_task">
              <label>Tarea a Ejecutar</label>
              <select v-model="s.ui_alert_latency.trigger_task_id">
                <option :value="null">-- Seleccionar Tarea --</option>
                <option v-for="t in autoTasks" :key="t.id" :value="t.id">{{ t.name }}</option>
              </select>
            </div>

            <div class="form-group">
              <label>Enfriamiento (min)</label>
              <input type="number" v-model.number="s.ui_alert_latency.cooldown_minutes" />
            </div>
            <div class="form-group">
              <label>Tolerancia</label>
              <input type="number" v-model.number="s.ui_alert_latency.tolerance_count" />
            </div>
            <div class="form-group checkbox-group">
              <input type="checkbox" v-model="s.ui_alert_latency.notify_recovery" :id="'pLatRec-' + uid" />
              <label :for="'pLatRec-' + uid">Notificar Reanudación 🟢</label>
            </div>

            <div class="form-group span-3 custom-msg-box">
              <div class="checkbox-group">
                <input type="checkbox" v-model="s.ui_alert_latency.use_custom_message" :id="'pLat_cmsg-' + uid" />
                <label :for="'pLat_cmsg-' + uid">✏️ Personalizar texto de alerta</label>
              </div>
              <div v-if="s.ui_alert_latency.use_custom_message" style="margin-top: 0.8rem;">
                <textarea v-model="s.ui_alert_latency.custom_message" rows="2" class="search-input custom-textarea" placeholder="Ej: Latencia alta de {latency_ms}ms en el nodo {client_name}"></textarea>
                <span class="form-hint">Variables: {client_name}, {ip}, {status}, {sensor_name}, {latency_ms}</span>
              </div>
            </div>

            <div class="form-group span-3 custom-msg-box" v-if="s.ui_alert_latency.notify_recovery">
              <div class="checkbox-group">
                <input type="checkbox" v-model="s.ui_alert_latency.use_custom_recovery_message" :id="'pLat_crmsg-' + uid" />
                <label :for="'pLat_crmsg-' + uid">✏️ Personalizar texto de reanudación</label>
              </div>
              <div v-if="s.ui_alert_latency.use_custom_recovery_message" style="margin-top: 0.8rem;">
                <textarea v-model="s.ui_alert_latency.custom_recovery_message" rows="2" class="search-input custom-textarea" placeholder="Ej: 🟢 La latencia del nodo {client_name} se ha estabilizado."></textarea>
                <span class="form-hint">Variables: {client_name}, {ip}, {status}, {sensor_name}, {latency_ms}</span>
              </div>
            </div>
          </template>
        </div>
      </div>
    </template>

    <template v-else-if="sensorType === 'ethernet' && s.config">
      <div class="form-group span-2" v-if="!hideName">
        <label>Nombre</label>
        <input type="text" v-model="s.name" required />
      </div>
      
      <div class="form-group" :class="{'span-3': hideName}">
        <label style="display: flex; justify-content: space-between; align-items: center;">
            Interfaz
            <span v-if="isLoadingInterfaces" style="font-size: 0.8rem; color: var(--blue);">⏳ Detectando...</span>
            <span v-else-if="!deviceInterfaces.length" style="font-size: 0.8rem; color: var(--error-red);">⚠️ Falló detección</span>
        </label>
        <template v-if="deviceInterfaces.length > 0 || isLoadingInterfaces">
            <select v-model="s.config.interface_name" required :disabled="isLoadingInterfaces">
                <option value="" disabled>Seleccione una interfaz</option>
                <option v-if="s.config.interface_name && !deviceInterfaces.some(i => i.name === s.config.interface_name)" :value="s.config.interface_name">
                    {{ s.config.interface_name }} (Actual)
                </option>
                <option v-for="iface in deviceInterfaces" :key="iface.name" :value="iface.name">
                    {{ iface.name }} {{ iface.type !== 'unknown' ? `[${iface.type}]` : '' }} {{ iface.disabled ? '(Inactiva)' : '' }}
                </option>
            </select>
        </template>
        <template v-else>
            <input type="text" v-model="s.config.interface_name" required placeholder="Ej: ether1" />
        </template>
      </div>

      <div class="form-group span-3">
        <label>Intervalo (s)</label>
        <input type="number" v-model.number="s.config.interval_sec" required min="10" />
      </div>

      <div class="sub-section span-3" v-if="s.ui_alert_speed_change && s.ui_alert_traffic">
        <h4>Alertas</h4>

        <div class="alert-config-item span-3">
          <div class="form-group checkbox-group">
            <input type="checkbox" v-model="s.ui_alert_speed_change.enabled" :id="'eSpd-' + uid" />
            <label :for="'eSpd-' + uid">Cambio de Velocidad / Desconexión</label>
          </div>
          <template v-if="s.ui_alert_speed_change.enabled">
            <div class="form-group">
              <label>Canal</label>
              <select v-model="s.ui_alert_speed_change.channel_id">
                <option :value="null">--</option>
                <option v-for="c in channels" :key="c.id" :value="c.id">{{ c.name }}</option>
              </select>
            </div>

            <div class="form-group checkbox-group alert-auto-task">
              <input type="checkbox" v-model="s.ui_alert_speed_change.use_auto_task" :id="'eSpd_auto-' + uid" />
              <label :for="'eSpd_auto-' + uid">⚡ Auto-Remediación</label>
            </div>
            <div class="form-group" v-if="s.ui_alert_speed_change.use_auto_task">
              <label>Tarea a Ejecutar</label>
              <select v-model="s.ui_alert_speed_change.trigger_task_id">
                <option :value="null">-- Seleccionar Tarea --</option>
                <option v-for="t in autoTasks" :key="t.id" :value="t.id">{{ t.name }}</option>
              </select>
            </div>

            <div class="form-group">
              <label>Enfriamiento</label>
              <input type="number" v-model.number="s.ui_alert_speed_change.cooldown_minutes" />
            </div>
            <div class="form-group">
              <label>Tolerancia</label>
              <input type="number" v-model.number="s.ui_alert_speed_change.tolerance_count" />
            </div>
            <div class="form-group checkbox-group">
              <input type="checkbox" v-model="s.ui_alert_speed_change.notify_recovery" :id="'eSpdRec-' + uid" />
              <label :for="'eSpdRec-' + uid">Notificar Reanudación 🟢</label>
            </div>

            <div class="form-group span-3 custom-msg-box">
              <div class="checkbox-group">
                <input type="checkbox" v-model="s.ui_alert_speed_change.use_custom_message" :id="'eSpd_cmsg-' + uid" />
                <label :for="'eSpd_cmsg-' + uid">✏️ Personalizar texto de alerta</label>
              </div>
              <div v-if="s.ui_alert_speed_change.use_custom_message" style="margin-top: 0.8rem;">
                <textarea v-model="s.ui_alert_speed_change.custom_message" rows="2" class="search-input custom-textarea" placeholder="Ej: Cable desconectado o fallo en interfaz de {client_name}"></textarea>
                <span class="form-hint">Variables: {client_name}, {ip}, {status}, {sensor_name}, {speed}</span>
              </div>
            </div>

            <div class="form-group span-3 custom-msg-box" v-if="s.ui_alert_speed_change.notify_recovery">
              <div class="checkbox-group">
                <input type="checkbox" v-model="s.ui_alert_speed_change.use_custom_recovery_message" :id="'eSpd_crmsg-' + uid" />
                <label :for="'eSpd_crmsg-' + uid">✏️ Personalizar texto de reanudación</label>
              </div>
              <div v-if="s.ui_alert_speed_change.use_custom_recovery_message" style="margin-top: 0.8rem;">
                <textarea v-model="s.ui_alert_speed_change.custom_recovery_message" rows="2" class="search-input custom-textarea" placeholder="Ej: 🟢 La interfaz en {client_name} ha vuelto a conectar a {speed}."></textarea>
                <span class="form-hint">Variables: {client_name}, {ip}, {status}, {sensor_name}, {speed}</span>
              </div>
            </div>
          </template>
        </div>

        <hr class="separator span-3" />

        <div class="alert-config-item span-3">
          <div class="form-group checkbox-group">
            <input type="checkbox" v-model="s.ui_alert_traffic.enabled" :id="'eTrf-' + uid" />
            <label :for="'eTrf-' + uid">Umbral Tráfico</label>
          </div>
          <template v-if="s.ui_alert_traffic.enabled">
            <div class="form-group">
              <label>Mbps</label>
              <input type="number" v-model.number="s.ui_alert_traffic.threshold_mbps" />
            </div>
            <div class="form-group">
              <label>Dirección</label>
              <select v-model="s.ui_alert_traffic.direction">
                <option value="any">Cualquiera</option>
                <option value="rx">Bajada</option>
                <option value="tx">Subida</option>
              </select>
            </div>
            <div class="form-group">
              <label>Canal</label>
              <select v-model="s.ui_alert_traffic.channel_id">
                <option :value="null">--</option>
                <option v-for="c in channels" :key="c.id" :value="c.id">{{ c.name }}</option>
              </select>
            </div>

            <div class="form-group checkbox-group alert-auto-task">
              <input type="checkbox" v-model="s.ui_alert_traffic.use_auto_task" :id="'eTrf_auto-' + uid" />
              <label :for="'eTrf_auto-' + uid">⚡ Auto-Remediación</label>
            </div>
            <div class="form-group" v-if="s.ui_alert_traffic.use_auto_task">
              <label>Tarea a Ejecutar</label>
              <select v-model="s.ui_alert_traffic.trigger_task_id">
                <option :value="null">-- Seleccionar Tarea --</option>
                <option v-for="t in autoTasks" :key="t.id" :value="t.id">{{ t.name }}</option>
              </select>
            </div>

            <div class="form-group">
              <label>Enfriamiento</label>
              <input type="number" v-model.number="s.ui_alert_traffic.cooldown_minutes" />
            </div>
            <div class="form-group">
              <label>Tolerancia</label>
              <input type="number" v-model.number="s.ui_alert_traffic.tolerance_count" />
            </div>
            <div class="form-group checkbox-group">
              <input type="checkbox" v-model="s.ui_alert_traffic.notify_recovery" :id="'eTrfRec-' + uid" />
              <label :for="'eTrfRec-' + uid">Notificar Reanudación 🟢</label>
            </div>

            <div class="form-group span-3 custom-msg-box">
              <div class="checkbox-group">
                <input type="checkbox" v-model="s.ui_alert_traffic.use_custom_message" :id="'eTrf_cmsg-' + uid" />
                <label :for="'eTrf_cmsg-' + uid">✏️ Personalizar texto de alerta</label>
              </div>
              <div v-if="s.ui_alert_traffic.use_custom_message" style="margin-top: 0.8rem;">
                <textarea v-model="s.ui_alert_traffic.custom_message" rows="2" class="search-input custom-textarea" placeholder="Ej: Tráfico elevado detectado en {client_name}"></textarea>
                <span class="form-hint">Variables: {client_name}, {ip}, {status}, {sensor_name}, {tx_bitrate}, {rx_bitrate}</span>
              </div>
            </div>

            <div class="form-group span-3 custom-msg-box" v-if="s.ui_alert_traffic.notify_recovery">
              <div class="checkbox-group">
                <input type="checkbox" v-model="s.ui_alert_traffic.use_custom_recovery_message" :id="'eTrf_crmsg-' + uid" />
                <label :for="'eTrf_crmsg-' + uid">✏️ Personalizar texto de reanudación</label>
              </div>
              <div v-if="s.ui_alert_traffic.use_custom_recovery_message" style="margin-top: 0.8rem;">
                <textarea v-model="s.ui_alert_traffic.custom_recovery_message" rows="2" class="search-input custom-textarea" placeholder="Ej: 🟢 El tráfico en {client_name} ha vuelto a valores normales."></textarea>
                <span class="form-hint">Variables: {client_name}, {ip}, {status}, {sensor_name}, {tx_bitrate}, {rx_bitrate}</span>
              </div>
            </div>
          </template>
        </div>
      </div>
    </template>

    <template v-else-if="sensorType === 'wireless' && s.config && s.config.thresholds">
      <div class="form-group span-2" v-if="!hideName">
        <label>Nombre del Sensor</label>
        <input type="text" v-model="s.name" required />
      </div>
      
      <div class="form-group" :class="{'span-3': hideName}">
        <label style="display: flex; justify-content: space-between; align-items: center;">
            Interfaz Inalámbrica
            <span v-if="isLoadingInterfaces" style="font-size: 0.8rem; color: var(--blue);">⏳ Detectando...</span>
            <span v-else-if="!deviceInterfaces.length" style="font-size: 0.8rem; color: var(--error-red);">⚠️ Falló detección</span>
        </label>
        <template v-if="deviceInterfaces.length > 0 || isLoadingInterfaces">
            <select v-model="s.config.interface_name" required :disabled="isLoadingInterfaces">
                <option value="" disabled>Seleccione una interfaz</option>
                <option v-if="s.config.interface_name && !deviceInterfaces.some(i => i.name === s.config.interface_name)" :value="s.config.interface_name">
                    {{ s.config.interface_name }} (Actual)
                </option>
                <option v-for="iface in deviceInterfaces" :key="iface.name" :value="iface.name">
                    {{ iface.name }} {{ iface.type !== 'unknown' ? `[${iface.type}]` : '' }} {{ iface.disabled ? '(Inactiva)' : '' }}
                </option>
            </select>
        </template>
        <template v-else>
            <input type="text" v-model="s.config.interface_name" required placeholder="Ej: wlan1" />
        </template>
      </div>

      <div class="form-group span-3">
        <label>Intervalo (s)</label>
        <input type="number" v-model.number="s.config.interval_sec" required min="10" />
      </div>

      <div class="sub-section span-3">
        <h4>Umbrales y Calidad de Enlace</h4>
        <div class="threshold-grid">
          <div class="form-group">
            <label>Señal Mínima (dBm)</label>
            <input type="number" v-model.number="s.config.thresholds.min_signal_dbm" placeholder="-80" />
            <span class="form-hint" v-if="!isCompact">Alerta si empeora (ej: -85)</span>
          </div>
          <div class="form-group">
            <label>CCQ Mínimo (%)</label>
            <input type="number" v-model.number="s.config.thresholds.min_ccq_percent" placeholder="75" />
            <span class="form-hint" v-if="!isCompact">Calidad aceptable (0 a 100)</span>
          </div>
          <div class="form-group">
            <label>Clientes Mínimos</label>
            <input type="number" v-model.number="s.config.thresholds.min_client_count" placeholder="0" min="0" />
            <span class="form-hint" v-if="!isCompact">Alerta caída masiva de clientes</span>
          </div>
          <div class="form-group">
            <label>TX Rate Mínimo (Mbps)</label>
            <input type="number" v-model.number="s.config.thresholds.min_tx_rate_mbps" placeholder="0" min="0" />
            <span class="form-hint" v-if="!isCompact">0 para desactivar</span>
          </div>
          <div class="form-group">
            <label>RX Rate Mínimo (Mbps)</label>
            <input type="number" v-model.number="s.config.thresholds.min_rx_rate_mbps" placeholder="0" min="0" />
            <span class="form-hint" v-if="!isCompact">0 para desactivar</span>
          </div>
        </div>
        <div class="form-group span-3" style="border-top: 1px dashed var(--primary-color); padding-top: 1rem; margin-top: 0.5rem;">
          <label>Tolerancia Anti-Spam (Redis)</label>
          <input type="number" v-model.number="s.config.tolerance_checks" placeholder="3" min="1" />
          <span class="form-hint" v-if="!isCompact">Chequeos consecutivos necesarios para alertar.</span>
        </div>
      </div>

      <div class="sub-section span-3" v-if="s.ui_alert_status">
        <h4>Notificaciones Inalámbricas</h4>
        <div class="alert-config-item span-3">
          <div class="form-group checkbox-group">
            <input type="checkbox" v-model="s.ui_alert_status.enabled" :id="'wStat-' + uid" />
            <label :for="'wStat-' + uid">Alertar por Degradación / Desconexión</label>
          </div>
          <template v-if="s.ui_alert_status.enabled">
            <div class="form-group">
              <label>Canal de Alerta</label>
              <select v-model="s.ui_alert_status.channel_id">
                <option :value="null">-- Seleccionar --</option>
                <option v-for="c in channels" :key="c.id" :value="c.id">{{ c.name }}</option>
              </select>
            </div>

            <div class="form-group checkbox-group alert-auto-task">
              <input type="checkbox" v-model="s.ui_alert_status.use_auto_task" :id="'wStat_auto-' + uid" />
              <label :for="'wStat_auto-' + uid">⚡ Auto-Remediación</label>
            </div>
            <div class="form-group" v-if="s.ui_alert_status.use_auto_task">
              <label>Tarea a Ejecutar</label>
              <select v-model="s.ui_alert_status.trigger_task_id">
                <option :value="null">-- Seleccionar Tarea --</option>
                <option v-for="t in autoTasks" :key="t.id" :value="t.id">{{ t.name }}</option>
              </select>
            </div>

            <div class="form-group">
              <label>Enfriamiento (min)</label>
              <input type="number" v-model.number="s.ui_alert_status.cooldown_minutes" />
            </div>
            <div class="form-group checkbox-group" style="grid-column: span 1;">
              <input type="checkbox" v-model="s.ui_alert_status.notify_recovery" :id="'wRec-' + uid" />
              <label :for="'wRec-' + uid">Notificar Reanudación 🟢</label>
            </div>

            <div class="form-group span-3 custom-msg-box">
              <div class="checkbox-group">
                <input type="checkbox" v-model="s.ui_alert_status.use_custom_message" :id="'wStat_cmsg-' + uid" />
                <label :for="'wStat_cmsg-' + uid">✏️ Personalizar texto de alerta</label>
              </div>
              <div v-if="s.ui_alert_status.use_custom_message" style="margin-top: 0.8rem;">
                <textarea v-model="s.ui_alert_status.custom_message" rows="2" class="search-input custom-textarea" placeholder="Ej: Degradación de señal detectada en {client_name}. Estado actual: {status}"></textarea>
                <span class="form-hint">Variables: {client_name}, {ip}, {status}, {signal_strength}, {tx_ccq}, {rx_ccq}, {client_count}</span>
              </div>
            </div>

            <div class="form-group span-3 custom-msg-box" v-if="s.ui_alert_status.notify_recovery">
              <div class="checkbox-group">
                <input type="checkbox" v-model="s.ui_alert_status.use_custom_recovery_message" :id="'wStat_crmsg-' + uid" />
                <label :for="'wStat_crmsg-' + uid">✏️ Personalizar texto de reanudación</label>
              </div>
              <div v-if="s.ui_alert_status.use_custom_recovery_message" style="margin-top: 0.8rem;">
                <textarea v-model="s.ui_alert_status.custom_recovery_message" rows="2" class="search-input custom-textarea" placeholder="Ej: 🟢 La calidad del enlace en {client_name} se ha recuperado."></textarea>
                <span class="form-hint">Variables: {client_name}, {ip}, {status}, {signal_strength}, {tx_ccq}, {rx_ccq}, {client_count}</span>
              </div>
            </div>
          </template>
        </div>
      </div>
    </template>

    <template v-else-if="sensorType === 'system' && s.config && s.config.thresholds">
      <div class="form-group span-3" v-if="!hideName">
        <label>Nombre del Sensor</label>
        <input type="text" v-model="s.name" required placeholder="Ej: Recursos y Salud" />
      </div>

      <div class="form-group span-3">
        <label>Intervalo (s)</label>
        <input type="number" v-model.number="s.config.interval_sec" required min="10" />
      </div>

      <div class="sub-section span-3">
        <h4>Umbrales de Sistema</h4>
        <div class="threshold-grid">
          <div class="form-group">
            <label>CPU Máximo (%)</label>
            <input type="number" v-model.number="s.config.thresholds.max_cpu_percent" placeholder="85" min="1" max="100" />
            <span class="form-hint" v-if="!isCompact">Dejar vacío para ignorar</span>
          </div>
          <div class="form-group">
            <label>Memoria Máxima (%)</label>
            <input type="number" v-model.number="s.config.thresholds.max_memory_percent" placeholder="90" min="1" max="100" />
            <span class="form-hint" v-if="!isCompact">Dejar vacío para ignorar</span>
          </div>
          <div class="form-group">
            <label>Temp. Máxima (°C)</label>
            <input type="number" v-model.number="s.config.thresholds.max_temperature" placeholder="75" />
            <span class="form-hint" v-if="!isCompact">Solo si tiene sensor</span>
          </div>
          <div class="form-group">
            <label>Voltaje Mínimo (V)</label>
            <input type="number" step="0.1" v-model.number="s.config.thresholds.min_voltage" placeholder="23.5" />
            <span class="form-hint" v-if="!isCompact">Caída de baterías</span>
          </div>
          <div class="form-group">
            <label>Voltaje Máximo (V)</label>
            <input type="number" step="0.1" v-model.number="s.config.thresholds.max_voltage" placeholder="28.0" />
            <span class="form-hint" v-if="!isCompact">Sobrecarga</span>
          </div>
          <div class="form-group">
            <label>Uptime Reinicio (s)</label>
            <input type="number" v-model.number="s.config.thresholds.restart_uptime_seconds" placeholder="300" min="0" />
            <span class="form-hint" v-if="!isCompact">Alerta si se reinició recién</span>
          </div>
        </div>
        <div class="form-group span-3" style="border-top: 1px dashed var(--primary-color); padding-top: 1rem; margin-top: 0.5rem;">
          <label>Tolerancia Anti-Spam (Redis)</label>
          <input type="number" v-model.number="s.config.tolerance_checks" placeholder="3" min="1" />
          <span class="form-hint" v-if="!isCompact">Chequeos consecutivos superando umbrales.</span>
        </div>
      </div>

      <div class="sub-section span-3" v-if="s.ui_alert_status">
        <h4>Notificaciones de Sistema</h4>
        <div class="alert-config-item span-3">
          <div class="form-group checkbox-group">
            <input type="checkbox" v-model="s.ui_alert_status.enabled" :id="'sysStat-' + uid" />
            <label :for="'sysStat-' + uid">Alertar por Exceso de Recursos / Reinicios</label>
          </div>
          <template v-if="s.ui_alert_status.enabled">
            <div class="form-group">
              <label>Canal de Alerta</label>
              <select v-model="s.ui_alert_status.channel_id">
                <option :value="null">-- Seleccionar --</option>
                <option v-for="c in channels" :key="c.id" :value="c.id">{{ c.name }}</option>
              </select>
            </div>

            <div class="form-group checkbox-group alert-auto-task">
              <input type="checkbox" v-model="s.ui_alert_status.use_auto_task" :id="'sysStat_auto-' + uid" />
              <label :for="'sysStat_auto-' + uid">⚡ Auto-Remediación</label>
            </div>
            <div class="form-group" v-if="s.ui_alert_status.use_auto_task">
              <label>Tarea a Ejecutar</label>
              <select v-model="s.ui_alert_status.trigger_task_id">
                <option :value="null">-- Seleccionar Tarea --</option>
                <option v-for="t in autoTasks" :key="t.id" :value="t.id">{{ t.name }}</option>
              </select>
            </div>

            <div class="form-group">
              <label>Enfriamiento (min)</label>
              <input type="number" v-model.number="s.ui_alert_status.cooldown_minutes" />
            </div>
            <div class="form-group checkbox-group" style="grid-column: span 1;">
              <input type="checkbox" v-model="s.ui_alert_status.notify_recovery" :id="'sysRec-' + uid" />
              <label :for="'sysRec-' + uid">Notificar Reanudación 🟢</label>
            </div>

            <div class="form-group span-3 custom-msg-box">
              <div class="checkbox-group">
                <input type="checkbox" v-model="s.ui_alert_status.use_custom_message" :id="'sysStat_cmsg-' + uid" />
                <label :for="'sysStat_cmsg-' + uid">✏️ Personalizar texto de alerta</label>
              </div>
              <div v-if="s.ui_alert_status.use_custom_message" style="margin-top: 0.8rem;">
                <textarea v-model="s.ui_alert_status.custom_message" rows="2" class="search-input custom-textarea" placeholder="Ej: Equipo {client_name} con recursos al límite. CPU: {cpu_percent}%, Temp: {temperature}°C"></textarea>
                <span class="form-hint">Variables: {client_name}, {ip}, {status}, {sensor_name}, {cpu_percent}, {memory_percent}, {temperature}, {voltage}</span>
              </div>
            </div>

            <div class="form-group span-3 custom-msg-box" v-if="s.ui_alert_status.notify_recovery">
              <div class="checkbox-group">
                <input type="checkbox" v-model="s.ui_alert_status.use_custom_recovery_message" :id="'sysStat_crmsg-' + uid" />
                <label :for="'sysStat_crmsg-' + uid">✏️ Personalizar texto de reanudación</label>
              </div>
              <div v-if="s.ui_alert_status.use_custom_recovery_message" style="margin-top: 0.8rem;">
                <textarea v-model="s.ui_alert_status.custom_recovery_message" rows="2" class="search-input custom-textarea" placeholder="Ej: 🟢 Los recursos de {client_name} han vuelto a niveles normales."></textarea>
                <span class="form-hint">Variables: {client_name}, {ip}, {status}, {sensor_name}, {cpu_percent}, {memory_percent}, {temperature}, {voltage}</span>
              </div>
            </div>
          </template>
        </div>
      </div>
    </template>

  </div>
</template>

<style scoped>
/* ==============================================================
   CSS UNIVERSAL DEL COMPONENTE (SE ADAPTA AL PADRE MÁGICAMENTE)
   ============================================================== */
.sensor-configurator {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1.5rem 1rem;
  width: 100%;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
.form-group.span-2 {
  grid-column: span 2;
}
.form-group.span-3 {
  grid-column: span 3;
}

.form-group label {
  font-weight: bold;
  color: var(--gray, #888);
  font-size: 0.85rem;
}

.form-group input,
.form-group select,
.form-group textarea {
  padding: 0.8rem;
  background-color: var(--bg-color, #1a1a1a);
  border: 1px solid var(--primary-color, #333);
  border-radius: 6px;
  color: white;
  width: 100%;
  font-family: inherit;
  outline: none;
}
.form-group select:disabled {
  opacity: 0.7;
  cursor: not-allowed;
  background-color: #2a2a2a;
}

.checkbox-group {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 0.8rem;
}
.checkbox-group input[type='checkbox'] {
  width: auto;
  accent-color: var(--blue, #3b82f6);
  cursor: pointer;
}

.sub-section {
  grid-column: span 3;
  background-color: var(--bg-color, #1a1a1a);
  padding: 1.5rem;
  border-radius: 8px;
  margin-top: 1rem;
  border: 1px solid var(--primary-color, #333);
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}
.sub-section h4 {
  margin: 0 0 0.5rem 0;
  border-bottom: 1px solid var(--primary-color, #333);
  padding-bottom: 0.5rem;
  color: #ccc;
}

.alert-config-item {
  display: contents; /* Respeta el grid del sub-section o configurator */
}
.alert-config-item > .form-group {
  grid-column: span 1;
}

.threshold-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 1rem;
}

.form-hint {
  font-size: 0.75rem;
  color: var(--gray, #888);
  margin-top: 0.25rem;
  display: block;
}
.warning-text {
  color: #fbbf24;
  font-weight: 500;
}
.alert-auto-task {
  color: #ffeb3b;
}

.separator {
  border: 0;
  border-top: 1px dashed var(--primary-color, #333);
  margin: 1.5rem 0;
  width: 100%;
}

.custom-msg-box {
  background: rgba(255, 255, 255, 0.03);
  padding: 1rem;
  border-radius: 8px;
}
.custom-textarea {
  min-height: 60px;
  resize: vertical;
}

/* ==============================================================
   COMPACT MODE (PARA RECETAS EN SCANVIEW)
   ============================================================== */
.compact-mode {
  display: flex;
  flex-direction: column;
  gap: 0.8rem;
  padding: 0;
}
.compact-mode .form-group {
  grid-column: unset;
}
.compact-mode .form-group input,
.compact-mode .form-group select {
  padding: 0.5rem;
  font-size: 0.85rem;
}
.compact-mode .sub-section {
  padding: 0.8rem;
  gap: 0.8rem;
  margin-top: 0;
  border: none;
  border-top: 1px dashed #444;
  border-radius: 0;
}
.compact-mode .threshold-grid {
  grid-template-columns: repeat(2, 1fr);
}
.compact-mode .custom-msg-box {
  padding: 0.5rem;
}
</style>