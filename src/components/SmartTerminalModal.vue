<script setup>
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { Terminal } from 'xterm'
import { FitAddon } from 'xterm-addon-fit'
import { WebLinksAddon } from 'xterm-addon-web-links'
import 'xterm/css/xterm.css'
import { marked } from 'marked'
import api from '@/lib/api'
import { supabase } from '@/lib/supabase'

// PROPS
const props = defineProps({
  device: {
    type: Object,
    required: true
  },
  protocol: {
    type: String,
    default: 'ssh'
  }
})

const emit = defineEmits(['close'])

// REFS
const terminalContainer = ref(null)
const chatInput = ref('')
const messages = ref([
  { role: 'system', content: `👋 Hola. Soy tu copiloto de red. Estoy analizando la configuración de **${props.device.client_name}**...` }
])
const isAiLoading = ref(false)
const aiContextStatus = ref({ loaded: false, lines: 0 })
const connectionStatus = ref('connecting')

// VARIABLES GLOBALES
let term = null
let socket = null
let fitAddon = null
let resizeObserver = null

// --- GESTIÓN DE TERMINAL & WEBSOCKET ---

async function initTerminal() {
  term = new Terminal({
    cursorBlink: true,
    fontSize: 14,
    fontFamily: 'Menlo, Monaco, "Courier New", monospace',
    theme: {
      background: '#1e1e1e', // Coincide con el tema de la app (Surface Color)
      foreground: '#d4d4d4', // Texto gris suave (VS Code Style)
      cursor: '#cccccc',     // Cursor profesional (no verde matrix)
      selectionBackground: 'rgba(255, 255, 255, 0.2)'
    },
    convertEol: true,
  })

  fitAddon = new FitAddon()
  term.loadAddon(fitAddon)
  term.loadAddon(new WebLinksAddon())

  term.open(terminalContainer.value)
  fitAddon.fit()

  term.onData(data => {
    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({ type: 'input', data: data }))
    }
  })

  term.onResize(size => {
    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({ type: 'resize', rows: size.rows, cols: size.cols }))
    }
  })

  resizeObserver = new ResizeObserver(() => {
    fitAddon.fit()
  })
  resizeObserver.observe(terminalContainer.value)

  await connectWebSocket()
}

async function connectWebSocket() {
  try {
    const { data: { session } } = await supabase.auth.getSession()
    const token = session?.access_token

    if (!token) throw new Error("No hay sesión activa")

    const protocolPrefix = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.hostname
    const port = window.location.port ? window.location.port : '' 
    const wsUrl = `${protocolPrefix}//${host}:${port}/ws/terminal/${props.device.id}?token=${token}&protocol=${props.protocol}`

    socket = new WebSocket(wsUrl)

    socket.onopen = () => {
      connectionStatus.value = 'connected'
      term.writeln(`\x1b[32m[SYSTEM] Conectado a ${props.device.ip_address}...\x1b[0m\r\n`)
      setTimeout(() => fitAddon.fit(), 500)
    }

    socket.onmessage = (event) => {
      const msg = JSON.parse(event.data)
      
      if (msg.type === 'output') {
        term.write(msg.data)
      } 
      else if (msg.type === 'ai_status') {
        if (msg.status === 'ready') {
            aiContextStatus.value = { loaded: true, lines: msg.context_len }
            addSystemMessage(`✅ Contexto cargado (${msg.context_len} líneas).`)
        } else if (msg.status === 'loading') {
            // Silencioso
        } else {
            addSystemMessage(`⚠️ ${msg.msg}`)
        }
      }
    }

    socket.onclose = () => {
      connectionStatus.value = 'disconnected'
      term.writeln('\r\n\x1b[31m[SYSTEM] Conexión cerrada.\x1b[0m')
    }

    socket.onerror = (err) => {
      connectionStatus.value = 'error'
      console.error("WS Error", err)
    }

  } catch (e) {
    term.writeln(`\r\n\x1b[31m[SYSTEM] Error fatal: ${e.message}\x1b[0m`)
  }
}

// --- GESTIÓN DE CHAT IA ---

function addSystemMessage(text) {
    messages.value.push({ role: 'system', content: text })
    scrollToBottom()
}

function scrollToBottom() {
    nextTick(() => {
        const chatBox = document.querySelector('.chat-messages')
        if (chatBox) chatBox.scrollTop = chatBox.scrollHeight
    })
}

function renderMarkdown(text) {
    return marked(text)
}

async function sendAiPrompt() {
    const text = chatInput.value.trim()
    if (!text) return

    messages.value.push({ role: 'user', content: text })
    chatInput.value = ''
    scrollToBottom()
    isAiLoading.value = true

    try {
        const { data } = await api.post(`/terminal/${props.device.id}/ask`, {
            question: text,
            vendor: props.device.vendor || 'Generic'
        })
        messages.value.push({ role: 'assistant', content: data.answer })
    } catch (error) {
        messages.value.push({ role: 'system', content: '❌ Error consultando a la IA.' })
    } finally {
        isAiLoading.value = false
        scrollToBottom()
    }
}

function pasteCodeToTerminal(content) {
    const codeBlockRegex = /```[\s\S]*?\n([\s\S]*?)```/g
    let match
    let codeFound = false

    while ((match = codeBlockRegex.exec(content)) !== null) {
        if (match[1]) {
            if (socket && socket.readyState === WebSocket.OPEN) {
                socket.send(JSON.stringify({ type: 'input', data: match[1] }))
                codeFound = true
            }
        }
    }

    if (!codeFound) {
        if (socket && socket.readyState === WebSocket.OPEN) {
             socket.send(JSON.stringify({ type: 'input', data: content }))
        }
    }
    term.focus()
}

// LIFECYCLE
onMounted(() => {
  initTerminal()
})

onUnmounted(() => {
  if (socket) socket.close()
  if (term) term.dispose()
  if (resizeObserver) resizeObserver.disconnect()
})
</script>

<template>
  <div class="terminal-modal-overlay">
    <div class="smart-terminal-container">
      
      <header class="terminal-header">
        <div class="header-left">
          <div class="status-dot" :class="connectionStatus"></div>
          <h3>{{ device.client_name }} <span class="ip-tag">({{ device.ip_address }})</span></h3>
        </div>
        <div class="header-center">
            <span v-if="aiContextStatus.loaded" class="ai-badge ready" title="Configuración cargada">
                🧠 IA Context: OK
            </span>
            <span v-else class="ai-badge loading">
                🧠 Cargando contexto...
            </span>
        </div>
        <button class="close-btn" @click="emit('close')">✖</button>
      </header>

      <div class="terminal-body">
        
        <div class="terminal-pane" ref="terminalContainer"></div>

        <div class="ai-pane">
            <div class="ai-header">
                ASISTENCIA EN TERMINAL
            </div>
            
            <div class="chat-messages">
                <div v-for="(msg, index) in messages" :key="index" class="message-row" :class="msg.role">
                    
                    <div v-if="msg.role === 'system'" class="msg-bubble system">
                        {{ msg.content }}
                    </div>
                    
                    <div v-else-if="msg.role === 'user'" class="msg-bubble user">
                        {{ msg.content }}
                    </div>
                    
                    <div v-else class="msg-bubble assistant">
                        <div class="markdown-content" v-html="renderMarkdown(msg.content)"></div>
                        <div class="msg-actions">
                            <button class="action-btn" @click="pasteCodeToTerminal(msg.content)">
                                ▶ Pegar
                            </button>
                        </div>
                    </div>

                </div>
                
                <div v-if="isAiLoading" class="loading-dots">
                    <span>.</span><span>.</span><span>.</span>
                </div>
            </div>

            <div class="chat-input-area">
                <textarea 
                    v-model="chatInput" 
                    placeholder="Escribe tu consulta..."
                    @keydown.enter.prevent="sendAiPrompt"
                ></textarea>
                <button @click="sendAiPrompt" :disabled="isAiLoading || !chatInput.trim()">
                    ➤
                </button>
            </div>
        </div>

      </div>
    </div>
  </div>
</template>

<style scoped>
/* VARIABLES */
.terminal-modal-overlay {
  position: fixed;
  top: 0; left: 0; width: 100vw; height: 100vh;
  background: rgba(0, 0, 0, 0.85);
  z-index: 5000;
  display: flex;
  align-items: center;
  justify-content: center;
  backdrop-filter: blur(4px);
}

.smart-terminal-container {
  width: 95vw;
  height: 90vh;
  background: #1e1e1e;
  border: 1px solid var(--primary-color, #4a90e2);
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-shadow: 0 20px 50px rgba(0,0,0,0.5);
}

/* HEADER */
.terminal-header {
  height: 50px;
  background: #252526;
  border-bottom: 1px solid #333;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 1rem;
}
.header-left {
  display: flex;
  align-items: center;
  gap: 10px;
  color: white;
}
.ip-tag {
    color: #888;
    font-size: 0.9rem;
    font-weight: normal;
}
.status-dot {
    width: 10px; height: 10px; border-radius: 50%;
    background: gray;
}
.status-dot.connected { background: #2ecc71; box-shadow: 0 0 5px #2ecc71; }
.status-dot.disconnected { background: #e74c3c; }
.status-dot.error { background: #e74c3c; }

.header-center {
    flex: 1;
    display: flex;
    justify-content: center;
}
.ai-badge {
    font-size: 0.8rem;
    padding: 2px 8px;
    border-radius: 4px;
    background: #333;
    color: #ccc;
    border: 1px solid #444;
}
.ai-badge.ready { border-color: #2ecc71; color: #2ecc71; }
.ai-badge.loading { animation: pulse 1.5s infinite; }

.close-btn {
  background: none; border: none; color: #fff;
  font-size: 1.2rem; cursor: pointer;
}
.close-btn:hover { color: #e74c3c; }

/* BODY */
.terminal-body {
  flex: 1;
  display: flex;
  overflow: hidden;
}

/* LEFT PANE: TERMINAL */
.terminal-pane {
  flex: 2;
  background: #1e1e1e; /* CORREGIDO: Gris oscuro integrado */
  padding: 5px;
  overflow: hidden;
}

/* RIGHT PANE: AI */
.ai-pane {
  flex: 1;
  min-width: 350px;
  max-width: 500px;
  background: #1e1e1e;
  border-left: 1px solid #333;
  display: flex;
  flex-direction: column;
}

.ai-header {
    padding: 10px;
    font-weight: bold;
    color: #ccc;
    background: #252526;
    border-bottom: 1px solid #333;
    text-transform: uppercase;
    font-size: 0.8rem;
    letter-spacing: 1px;
}

.chat-messages {
    flex: 1;
    padding: 1rem;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 1rem;
}

.msg-bubble {
    padding: 10px;
    border-radius: 6px;
    font-size: 0.9rem;
    line-height: 1.4;
    max-width: 95%;
}
.msg-bubble.system {
    color: #888;
    font-style: italic;
    font-size: 0.8rem;
    text-align: center;
    width: 100%;
}
.msg-bubble.user {
    background: #0e639c;
    color: white;
    align-self: flex-end;
}
.msg-bubble.assistant {
    background: #333;
    color: #ddd;
    align-self: flex-start;
    border: 1px solid #444;
}

/* Markdown Styles inside Chat */
.markdown-content :deep(pre) {
    background: #252526; /* CORREGIDO: Gris oscuro suave */
    padding: 8px;
    border-radius: 4px;
    overflow-x: auto;
    margin: 5px 0;
    border: 1px solid #444;
}
.markdown-content :deep(code) {
    font-family: monospace;
    color: #ce9178;
}

.msg-actions {
    margin-top: 8px;
    display: flex;
    justify-content: flex-end;
}
.action-btn {
    background: #252526;
    border: 1px solid #0e639c;
    color: #0e639c;
    padding: 4px 8px;
    font-size: 0.8rem;
    border-radius: 3px;
    cursor: pointer;
    transition: all 0.2s;
}
.action-btn:hover {
    background: #0e639c;
    color: white;
}

.chat-input-area {
    padding: 10px;
    background: #252526;
    border-top: 1px solid #333;
    display: flex;
    gap: 10px;
}
.chat-input-area textarea {
    flex: 1;
    background: #3c3c3c;
    border: 1px solid #555;
    color: white;
    border-radius: 4px;
    padding: 8px;
    resize: none;
    height: 40px;
    font-family: sans-serif;
}
.chat-input-area textarea:focus {
    outline: 1px solid #0e639c;
}
.chat-input-area button {
    width: 40px;
    background: #0e639c;
    color: white;
    border: none;
    border-radius: 4px;
    cursor: pointer;
}
.chat-input-area button:disabled {
    background: #555;
    cursor: not-allowed;
}

.loading-dots span {
    animation: pulse 1s infinite;
    color: #888;
    font-size: 1.5rem;
    margin: 0 2px;
}
.loading-dots span:nth-child(2) { animation-delay: 0.2s; }
.loading-dots span:nth-child(3) { animation-delay: 0.4s; }

@keyframes pulse {
    0%, 100% { opacity: 0.5; }
    50% { opacity: 1; }
}
</style>