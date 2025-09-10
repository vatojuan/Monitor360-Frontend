<script setup>
import { onMounted, ref } from 'vue'
import {
  BrowserQRCodeReader,
  HTMLCanvasElementLuminanceSource,
  BinaryBitmap,
  HybridBinarizer,
  QRCodeReader,
} from '@zxing/browser'

const scanResult = ref(null)
const errorMessage = ref('')
const isLoading = ref(true)
let codeReader = null

// sessionId viene de la URL
const sessionId = window.location.pathname.split('/').pop()

// 👇 Base URL configurable
const API_BASE = import.meta.env.VITE_API_URL || 'https://api.conecta360.site'

async function startScan() {
  try {
    codeReader = new BrowserQRCodeReader()
    const devices = await BrowserQRCodeReader.listVideoInputDevices()
    console.log('📱 Cámaras detectadas:', devices)

    let deviceId = devices[0]?.deviceId
    const backCam = devices.find((d) => /back|rear|environment/i.test(d.label))
    if (backCam) deviceId = backCam.deviceId

    await codeReader.decodeFromVideoDevice(deviceId, 'mobile-preview', async (result, err) => {
      if (result) {
        console.log('📱 QR detectado:', result.getText())
        await sendResult(result.getText())
        codeReader.reset()
      }
      if (err && err.name !== 'NotFoundException') {
        console.warn('⚠️ ZXing error:', err)
      }
    })
  } catch (e) {
    console.error('❌ Error cámara:', e)
    errorMessage.value = 'No se pudo iniciar la cámara. Usa la opción de subir imagen.'
  } finally {
    isLoading.value = false
  }
}

async function sendResult(decodedString) {
  try {
    const response = await fetch(`${API_BASE}/api/scan/${sessionId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ config_data: decodedString }),
    })
    if (!response.ok) throw new Error('Error servidor')
    scanResult.value = 'success'
  } catch (error) {
    console.error('❌ Error al enviar QR:', error)
    scanResult.value = 'error'
  }
}

// 👇 Export explícito para ESLint
const handleFileUpload = async (event) => {
  const file = event.target.files[0]
  if (!file) return

  try {
    const img = await createImageBitmap(file)
    const canvas = document.createElement('canvas')
    const ctx = canvas.getContext('2d')
    canvas.width = img.width
    canvas.height = img.height
    ctx.drawImage(img, 0, 0)

    const luminanceSource = new HTMLCanvasElementLuminanceSource(canvas)
    const binaryBitmap = new BinaryBitmap(new HybridBinarizer(luminanceSource))
    const reader = new QRCodeReader()
    const result = reader.decode(binaryBitmap)

    console.log('🖼️ QR detectado en imagen:', result.getText())
    await sendResult(result.getText())
  } catch (err) {
    console.error('❌ Error leyendo imagen QR:', err)
    errorMessage.value = 'No se pudo leer el QR de la imagen.'
  }
}

onMounted(startScan)
</script>

<template>
  <div class="scan-page">
    <h1>Escanea el código QR de tu MikroTik</h1>

    <div v-if="scanResult === 'success'" class="message success">
      ✅ ¡Listo! Configuración enviada.<br />
      📡 Ahora volvé a tu PC para continuar.
      <div class="actions">
        <button class="btn-close" @click="window.close()">Cerrar esta pestaña</button>
      </div>
    </div>
    <div v-else-if="scanResult === 'error'" class="message error">
      ❌ Hubo un error al enviar la configuración.
    </div>

    <div v-else class="video-wrapper">
      <video id="mobile-preview" autoplay playsinline class="qr-video"></video>
      <div class="scan-frame"></div>

      <p v-if="errorMessage" class="message error">{{ errorMessage }}</p>
      <p v-if="isLoading" class="loading-text">📷 Iniciando cámara...</p>

      <!-- Fallback -->
      <div class="fallback">
        <p>📂 Si la cámara no funciona, subí una imagen del QR:</p>
        <input type="file" accept="image/*" @change="handleFileUpload" />
      </div>
    </div>
  </div>
</template>

<style scoped>
.scan-page {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100vh;
  background: #121212;
  color: #eaeaea;
  padding: 1rem;
  text-align: center;
}

h1 {
  font-size: 1.3rem;
  font-weight: 600;
  margin-bottom: 1.2rem;
  color: #6ab4ff;
}

.video-wrapper {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.qr-video {
  width: 100%;
  max-width: 360px;
  aspect-ratio: 1 / 1;
  object-fit: cover;
  border-radius: 12px;
  border: 2px solid #333;
  background: black;
}

.scan-frame {
  position: absolute;
  width: 70%;
  height: 70%;
  border: 3px solid #6ab4ff;
  border-radius: 12px;
  box-shadow: 0 0 15px rgba(106, 180, 255, 0.6);
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0% {
    box-shadow: 0 0 5px rgba(106, 180, 255, 0.6);
  }
  50% {
    box-shadow: 0 0 20px rgba(106, 180, 255, 0.9);
  }
  100% {
    box-shadow: 0 0 5px rgba(106, 180, 255, 0.6);
  }
}

.message {
  margin-top: 1rem;
  padding: 1rem;
  border-radius: 8px;
  font-weight: bold;
}
.message.success {
  background: #2ea043;
}
.message.error {
  background: #d9534f;
}
.loading-text {
  margin-top: 0.8rem;
  color: #aaa;
}

.fallback {
  margin-top: 1.2rem;
}
.fallback input {
  margin-top: 0.5rem;
}
.actions {
  margin-top: 1rem;
}

.btn-close {
  background: #444;
  color: #fff;
  border: none;
  border-radius: 6px;
  padding: 0.6rem 1rem;
  cursor: pointer;
  font-weight: 600;
  transition: background 0.2s ease-in-out;
}
.btn-close:hover {
  background: #666;
}
</style>
