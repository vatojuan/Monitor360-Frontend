<script setup>
import { onMounted, ref } from 'vue'
import { BrowserQRCodeReader } from '@zxing/browser'

const scanResult = ref(null)
const errorMessage = ref('')
const isLoading = ref(true)
let codeReader = null

// sessionId viene de la URL
const sessionId = window.location.pathname.split('/').pop()

async function startScan() {
  try {
    codeReader = new BrowserQRCodeReader()
    const devices = await BrowserQRCodeReader.listVideoInputDevices()

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
    errorMessage.value = 'No se pudo iniciar la cámara.'
  } finally {
    isLoading.value = false
  }
}

async function sendResult(decodedString) {
  try {
    const response = await fetch(`/api/scan/${sessionId}`, {
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

onMounted(startScan)
</script>

<template>
  <div class="scan-page">
    <h1>Apunta al QR de MikroTik</h1>

    <div v-if="scanResult === 'success'" class="message success">
      ✅ ¡Listo! Configuración enviada. Ya puedes cerrar esta ventana.
    </div>
    <div v-else-if="scanResult === 'error'" class="message error">
      ❌ Hubo un error al enviar la configuración.
    </div>
    <div v-else>
      <video id="mobile-preview" autoplay playsinline class="qr-video"></video>
      <p v-if="errorMessage" class="message error">{{ errorMessage }}</p>
      <p v-if="isLoading" class="loading-text">Iniciando cámara...</p>
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

.qr-video {
  width: 100%;
  max-width: 400px;
  aspect-ratio: 1 / 1;
  object-fit: cover;
  border-radius: 12px;
  border: 2px solid #444;
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
  color: #aaa;
}
</style>
