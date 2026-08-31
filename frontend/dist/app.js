import { formatFusionEquation, formatFusionPercent, fusionComponentLabel } from "./fusion-format.js";
import { detailEmptyMessage, detailValue } from "./event-detail-format.js";
import { buildRouteUrl, isResolvedStatus } from "./event-actions-format.js";
const RAIL_ICONS = {
    eventos: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M12 9v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>',
    alertas: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"/></svg>',
    regioes: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7"/></svg>',
    fontes: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><ellipse cx="12" cy="5" rx="7" ry="3"/><path d="M5 5v14c0 1.66 3.13 3 7 3s7-1.34 7-3V5M5 12c0 1.66 3.13 3 7 3s7-1.34 7-3"/></svg>',
    fusao: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M12 2a10 10 0 110 20 10 10 0 010-20zm0 4v4l3 3"/></svg>',
    cv: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7z"/><circle cx="12" cy="12" r="3"/></svg>',
    config: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 11-2.83 2.83l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 11-4 0v-.09a1.65 1.65 0 00-1-1.51 1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 11-2.83-2.83l.06-.06a1.65 1.65 0 00.33-1.82 1.65 1.65 0 00-1.51-1H3a2 2 0 110-4h.09a1.65 1.65 0 001.51-1 1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 112.83-2.83l.06.06a1.65 1.65 0 001.82.33h.01a1.65 1.65 0 001-1.51V3a2 2 0 114 0v.09a1.65 1.65 0 001 1.51h.01a1.65 1.65 0 001.82-.33l.06-.06a2 2 0 112.83 2.83l-.06.06a1.65 1.65 0 00-.33 1.82v.01a1.65 1.65 0 001.51 1H21a2 2 0 110 4h-.09a1.65 1.65 0 00-1.51 1z"/></svg>',
    dashboard: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg>',
};
const RAIL_SECTIONS = [
    { key: "painel", title: "Visão Geral", items: [{ view: "dashboard", label: "Painel", svg: RAIL_ICONS.dashboard }] },
    {
        key: "operacoes", title: "Operações",
        items: [
            { view: "eventos", label: "Eventos", svg: RAIL_ICONS.eventos },
            { view: "alertas", label: "Alertas", svg: RAIL_ICONS.alertas },
            { view: "regioes", label: "Regiões", svg: RAIL_ICONS.regioes },
            { view: "fontes", label: "Fontes", svg: RAIL_ICONS.fontes },
        ],
    },
    {
        key: "inteligencia", title: "Inteligência",
        items: [
            { view: "fusao", label: "Fusão de Dados", svg: RAIL_ICONS.fusao },
            { view: "cv", label: "Visão Computacional", svg: RAIL_ICONS.cv },
        ],
    },
    { key: "sistema", title: "Sistema", items: [{ view: "config", label: "Configurações", svg: RAIL_ICONS.config }] },
    {
        key: "relatorios", title: "Relatórios",
        items: [
            { view: "eventos", label: "Eventos monitorados", svg: RAIL_ICONS.eventos },
            { view: "fusao", label: "Auditoria Data Fusion", svg: RAIL_ICONS.fusao },
        ],
    },
];
const VIEW_TO_RAIL = {
    dashboard: "painel",
    eventos: "operacoes",
    alertas: "operacoes",
    regioes: "operacoes",
    fontes: "operacoes",
    fusao: "inteligencia",
    cv: "inteligencia",
    config: "sistema",
};
const SEVERITIES = {
    baixa: { label: "Baixa", color: "#22c55e", scale: 10, zIndex: 2 },
    media: { label: "Média", color: "#FFB300", scale: 12, zIndex: 3 },
    alta: { label: "Alta", color: "#FF8A00", scale: 14, zIndex: 4 },
    critica: { label: "Crítica", color: "#FF5500", scale: 16, zIndex: 5 },
};
let map = null;
let openInfoWindow = null;
let popupReturnFocusToMarker = true;
let loadedEvents = [];
let trainingRegions = [];
let selectedMarkerId = null;
let dataSources = [];
let notifications = [];
let searchTerm = "";
let selectedEventId = null;
let detailEventId = null;
let detailActiveTab = "resumo";
let detailActionInFlight = false;
let lastUpdateLabel = "";
let searchRenderTimer = null;
let markerRefreshTimer = null;
const markersById = new Map();
const transientMarkerLayers = new Set();
const activeSeverities = new Set(Object.keys(SEVERITIES));
let railPanelOpen = false;
let activeView = "dashboard";
let rightPanelOpen = false;
let leftPanelOpen = false;
const sessionActivity = [];
const MAX_SESSION_ACTIVITY = 50;
const MARKER_CLUSTER_THRESHOLD = 120;
const MAX_RENDERED_EVENT_CARDS = 180;
let connectionMode = "disconnected";
let wsConnection = null;
let sseConnection = null;
let pollingTimer = null;
let reconnectAttempt = 0;
const WS_MAX_RECONNECT = 8;
const WS_BASE_DELAY_MS = 1000;
const POLLING_INTERVAL_MS = 15000;
let pingTimer = null;
let cvSelectedFile = null;
let cvPreviewUrl = null;
let cvCameraStream = null;
let cvLastDetections = [];
let cvMonitorTimer = null;
let cvMonitoring = false;
let cvAnalyzing = false;
let cvDetectorAvailable = false;
let cvLastLatencyMs = null;
let cvFrameSocket = null;
let appInitialized = false;
const evidenceObjectUrls = new Set();
const byId = (id) => document.getElementById(id);
function accessToken() {
    try {
        return sessionStorage.getItem("gx_access_token");
    }
    catch {
        return null;
    }
}
async function apiFetch(path, init = {}) {
    const headers = new Headers(init.headers);
    const token = accessToken();
    if (token)
        headers.set("Authorization", "Bearer " + token);
    const request = { ...init, headers };
    let response;
    try {
        response = await fetch(window.CONFIG.API_BASE_URL + path, request);
    }
    catch (error) {
        const method = String(init.method || "GET").toUpperCase();
        if (method !== "GET" && method !== "HEAD")
            throw error;
        await new Promise((resolve) => window.setTimeout(resolve, 250));
        response = await fetch(window.CONFIG.API_BASE_URL + path, request);
    }
    if (response.status === 401 && token) {
        try {
            sessionStorage.removeItem("gx_access_token");
        }
        catch { /* armazenamento indisponível */ }
    }
    return response;
}
function escapeHtml(value) {
    if (value == null)
        return "";
    return String(value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
}
/* ============================================================
   REAL-TIME: WebSocket → SSE → Polling (cascata de fallback)
   ============================================================ */
function updateConnectionStatus() {
    const el = byId("status-conexao");
    if (!el)
        return;
    const labels = {
        ws: "Sistema ao vivo (WS)",
        sse: "Sistema ao vivo (SSE)",
        polling: "Sistema em polling",
        disconnected: "Desconectado",
    };
    const classes = {
        ws: "conn-ws",
        sse: "conn-sse",
        polling: "conn-polling",
        disconnected: "conn-off",
    };
    el.textContent = labels[connectionMode];
    el.className = "status-badge " + classes[connectionMode];
}
function clearAllConnections() {
    if (wsConnection) {
        wsConnection.close();
        wsConnection = null;
    }
    if (sseConnection) {
        sseConnection.close();
        sseConnection = null;
    }
    if (pollingTimer) {
        clearInterval(pollingTimer);
        pollingTimer = null;
    }
    if (pingTimer) {
        clearInterval(pingTimer);
        pingTimer = null;
    }
}
function connectWebSocket() {
    clearAllConnections();
    const token = accessToken() || "";
    const wsUrl = window.CONFIG.API_BASE_URL.replace(/^http/, "ws") + "/ws";
    try {
        wsConnection = new WebSocket(wsUrl);
    }
    catch {
        connectionMode = "disconnected";
        updateConnectionStatus();
        fallbackToSSE();
        return;
    }
    wsConnection.onopen = () => {
        wsConnection?.send(JSON.stringify({ tipo: "auth", token }));
    };
    const startHeartbeat = () => {
        connectionMode = "ws";
        reconnectAttempt = 0;
        updateConnectionStatus();
        logSessionActivity("sincronizacao", "Canal WebSocket autenticado");
        if (loadedEvents.length)
            void loadRightPanelAlerts();
        if (pingTimer)
            clearInterval(pingTimer);
        pingTimer = setInterval(() => {
            if (wsConnection && wsConnection.readyState === WebSocket.OPEN) {
                wsConnection.send(JSON.stringify({ tipo: "ping" }));
            }
        }, 30000);
    };
    wsConnection.onmessage = (event) => {
        try {
            const msg = JSON.parse(event.data);
            if (msg.tipo === "auth_ok") {
                startHeartbeat();
                return;
            }
            if (msg.tipo === "pong")
                return;
            handleRealtimeMessage(msg.tipo, msg.dados);
        }
        catch { /* ignore malformed */ }
    };
    wsConnection.onclose = () => {
        if (pingTimer) {
            clearInterval(pingTimer);
            pingTimer = null;
        }
        wsConnection = null;
        if (connectionMode !== "sse" && connectionMode !== "polling") {
            fallbackReconnect();
        }
    };
    wsConnection.onerror = () => {
        wsConnection?.close();
        wsConnection = null;
    };
}
function fallbackToSSE() {
    clearAllConnections();
    const url = window.CONFIG.API_BASE_URL + "/events/stream";
    try {
        sseConnection = new EventSource(url);
    }
    catch {
        connectionMode = "disconnected";
        updateConnectionStatus();
        fallbackToPolling();
        return;
    }
    sseConnection.addEventListener("evento_criado", (e) => {
        reconnectAttempt = 0;
        handleRealtimeMessage("evento_criado", JSON.parse(e.data));
    });
    sseConnection.addEventListener("evento_atualizado", (e) => {
        reconnectAttempt = 0;
        handleRealtimeMessage("evento_atualizado", JSON.parse(e.data));
    });
    sseConnection.addEventListener("evento_removido", (e) => {
        reconnectAttempt = 0;
        handleRealtimeMessage("evento_removido", JSON.parse(e.data));
    });
    sseConnection.addEventListener("notificacao_criada", (e) => {
        handleRealtimeMessage("notificacao_criada", JSON.parse(e.data));
    });
    sseConnection.addEventListener("notificacao_atualizada", (e) => {
        handleRealtimeMessage("notificacao_atualizada", JSON.parse(e.data));
    });
    sseConnection.onopen = () => {
        connectionMode = "sse";
        reconnectAttempt = 0;
        updateConnectionStatus();
    };
    sseConnection.onerror = () => {
        sseConnection?.close();
        sseConnection = null;
        connectionMode = "disconnected";
        updateConnectionStatus();
        fallbackToPolling();
    };
}
function fallbackToPolling() {
    clearAllConnections();
    connectionMode = "polling";
    updateConnectionStatus();
    if (pollingTimer)
        clearInterval(pollingTimer);
    pollingTimer = setInterval(() => {
        void loadEvents();
    }, POLLING_INTERVAL_MS);
}
function fallbackReconnect() {
    if (reconnectAttempt >= WS_MAX_RECONNECT) {
        fallbackToSSE();
        return;
    }
    const delay = WS_BASE_DELAY_MS * Math.pow(2, reconnectAttempt);
    reconnectAttempt++;
    connectionMode = "disconnected";
    updateConnectionStatus();
    setTimeout(connectWebSocket, delay);
}
function handleRealtimeMessage(tipo, dados) {
    switch (tipo) {
        case "evento_criado": {
            const evento = dados;
            if (!loadedEvents.some((e) => e.id === evento.id)) {
                loadedEvents.unshift(evento);
            }
            renderEventList(loadedEvents);
            updateMetrics(loadedEvents);
            updateMarker(evento);
            logSessionActivity("evento_criado", "Evento criado: " + evento.titulo, evento.id, evento.severidade);
            break;
        }
        case "evento_atualizado": {
            const atualizado = dados;
            const idx = loadedEvents.findIndex((ev) => ev.id === atualizado.id);
            if (idx !== -1) {
                loadedEvents[idx] = { ...loadedEvents[idx], ...atualizado };
            }
            else {
                loadedEvents.unshift(atualizado);
            }
            renderEventList(loadedEvents);
            updateMetrics(loadedEvents);
            updateMarker(atualizado);
            logSessionActivity("evento_atualizado", "Evento atualizado: " + (atualizado.titulo || "#" + atualizado.id), atualizado.id, atualizado.severidade);
            if (selectedEventId === atualizado.id) {
                renderSelectedEvent(atualizado);
            }
            break;
        }
        case "evento_removido": {
            const id = Number(dados.id);
            loadedEvents = loadedEvents.filter((ev) => ev.id !== id);
            renderEventList(loadedEvents);
            updateMetrics(loadedEvents);
            removeMarker(id);
            if (selectedEventId === id) {
                selectedEventId = null;
                clearEventEvidence();
                byId("selected-title").textContent = "Selecione um evento";
                byId("selected-description").textContent = "Selecione um evento para visualizar os detalhes operacionais.";
            }
            break;
        }
        case "notificacao_criada":
        case "notificacao_atualizada": {
            logSessionActivity("notificacao", "Notificação: " + (dados.titulo || "atualizada"), undefined);
            void loadRightPanelAlerts();
            break;
        }
    }
}
function updateMarker(evento) {
    if (map && loadedEvents.filter(isEventVisible).length > MARKER_CLUSTER_THRESHOLD && map.getZoom() < 15) {
        scheduleMarkerRefresh();
        return;
    }
    const existing = markersById.get(evento.id);
    if (existing) {
        const style = severityStyle(evento.severidade);
        existing.setIcon(markerIcon(evento, style));
        existing.bindPopup(infoWindowContent(evento));
    }
    else {
        createMarker(evento);
    }
}
function removeMarker(id) {
    if (map && loadedEvents.filter(isEventVisible).length > MARKER_CLUSTER_THRESHOLD && map.getZoom() < 15) {
        scheduleMarkerRefresh();
        return;
    }
    const marker = markersById.get(id);
    if (marker) {
        marker.remove();
        transientMarkerLayers.delete(marker);
        markersById.delete(id);
    }
}
function normalizeSeverity(value) {
    const key = String(value || "media").toLowerCase().trim();
    return key in SEVERITIES ? key : "media";
}
function severityStyle(value) {
    return SEVERITIES[normalizeSeverity(value)];
}
function setApiStatus(ok, message) {
    const element = byId("status-api");
    element.textContent = message;
    element.classList.toggle("ok", ok);
    element.classList.toggle("erro", !ok);
}
function loadGoogleMaps() {
    initMapa();
}
function cvSetFeedback(message, tone = "") {
    const feedback = byId("cv-feedback");
    feedback.textContent = message;
    feedback.className = "cv-feedback" + (tone ? " " + tone : "");
}
function cvSetMetrics(connection, fps = 0, latency = null) {
    byId("cv-connection-status").textContent = connection;
    byId("cv-fps").textContent = String(fps);
    byId("cv-latency").textContent = latency == null ? "--" : latency + " ms";
}
function cvAccessToken() {
    try {
        return sessionStorage.getItem("gx_access_token");
    }
    catch {
        return null;
    }
}
function cvConnectFrames() {
    const token = cvAccessToken() || "";
    if (cvFrameSocket?.readyState === WebSocket.OPEN || cvFrameSocket?.readyState === WebSocket.CONNECTING) {
        return;
    }
    const url = window.CONFIG.API_BASE_URL.replace(/^http/, "ws") + "/ws/cv";
    cvFrameSocket = new WebSocket(url);
    cvFrameSocket.onopen = () => cvFrameSocket?.send(JSON.stringify({ tipo: "auth", token }));
    cvFrameSocket.onmessage = (event) => {
        const message = JSON.parse(event.data);
        if (message.tipo === "auth_ok")
            cvSetMetrics("WebSocket", 0, cvLastLatencyMs);
        if (message.tipo === "frame_resultado") {
            const data = message.dados;
            cvLastDetections = data.deteccoes;
            cvLastLatencyMs = data.latencia_ms;
            cvRenderResults(data.deteccoes);
            cvDrawBoxes(data.deteccoes);
            byId("cv-confirm").disabled = !data.deteccoes.length;
            cvSetMetrics("WebSocket", 1, data.latencia_ms);
            cvSetFeedback(data.deteccoes.length + " detecção(ões) retornada(s) pelo canal ao vivo.", "success");
        }
    };
    cvFrameSocket.onerror = () => cvSetMetrics("Falha; upload", 0, cvLastLatencyMs);
    cvFrameSocket.onclose = () => { cvFrameSocket = null; if (cvMonitoring)
        cvSetMetrics("Upload fallback", 1, cvLastLatencyMs); };
}
async function cvSendFrame(file) {
    if (cvFrameSocket?.readyState !== WebSocket.OPEN || cvAnalyzing)
        return false;
    cvAnalyzing = true;
    try {
        const bytes = new Uint8Array(await file.arrayBuffer());
        let binary = "";
        bytes.forEach((byte) => { binary += String.fromCharCode(byte); });
        cvFrameSocket.send(JSON.stringify({ tipo: "frame", frame_id: "cv-" + Date.now(), mime: file.type, conteudo: btoa(binary), threshold: Number(byId("cv-threshold").value) / 100 }));
        return true;
    }
    finally {
        cvAnalyzing = false;
    }
}
function cvDrawBoxes(detections) {
    const video = byId("cv-video");
    const canvas = byId("cv-overlay");
    if (!video.videoWidth || !video.videoHeight) {
        canvas.hidden = true;
        return;
    }
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const context = canvas.getContext("2d");
    if (!context)
        return;
    context.clearRect(0, 0, canvas.width, canvas.height);
    detections.forEach((item) => {
        const [x1, y1, x2, y2] = item.bbox;
        const color = severityStyle(item.severidade).color;
        context.strokeStyle = color;
        context.lineWidth = Math.max(2, canvas.width / 420);
        context.strokeRect(x1, y1, Math.max(1, x2 - x1), Math.max(1, y2 - y1));
        context.fillStyle = color;
        context.font = Math.max(12, canvas.width / 48) + "px Inter";
        context.fillText(item.nome + " " + Math.round(item.confianca * 100) + "%", x1 + 3, Math.max(14, y1 - 5));
    });
    canvas.hidden = !detections.length;
}
function cvClearFile() {
    cvSelectedFile = null;
    const input = byId("cv-file");
    input.value = "";
    const preview = byId("cv-preview");
    preview.hidden = true;
    if (cvPreviewUrl)
        URL.revokeObjectURL(cvPreviewUrl);
    cvPreviewUrl = null;
    byId("cv-preview-image").removeAttribute("src");
    byId("cv-file-label").textContent = "Selecionar imagem de evidência";
    byId("cv-analyze").disabled = true;
    byId("cv-confirm").disabled = true;
    cvLastDetections = [];
    byId("cv-overlay").hidden = true;
    byId("cv-results").innerHTML = "";
    cvSetFeedback("Selecione uma imagem para iniciar a análise.");
}
function cvSetFile(file, sourceLabel) {
    if (file.size > 10 * 1024 * 1024) {
        cvSetFeedback("A imagem ultrapassa o limite de 10 MB.", "error");
        return;
    }
    cvSelectedFile = file;
    if (cvPreviewUrl)
        URL.revokeObjectURL(cvPreviewUrl);
    cvPreviewUrl = URL.createObjectURL(file);
    byId("cv-preview-image").src = cvPreviewUrl;
    byId("cv-preview").hidden = false;
    byId("cv-file-label").textContent = sourceLabel;
    byId("cv-analyze").disabled = false;
    byId("cv-confirm").disabled = true;
    cvLastDetections = [];
    byId("cv-results").innerHTML = "";
    cvSetFeedback("Quadro real pronto para análise por YOLO.");
}
function cvStopMonitoring() {
    if (cvMonitorTimer)
        window.clearInterval(cvMonitorTimer);
    cvMonitorTimer = null;
    cvMonitoring = false;
    const monitor = byId("cv-camera-monitor");
    monitor.textContent = "Iniciar monitoramento (1 FPS)";
}
function cvStopCamera() {
    cvStopMonitoring();
    cvCameraStream?.getTracks().forEach((track) => track.stop());
    cvCameraStream = null;
    cvFrameSocket?.close();
    cvFrameSocket = null;
    const video = byId("cv-video");
    video.srcObject = null;
    byId("cv-video-empty").hidden = false;
    byId("cv-camera-status").textContent = "Câmera encerrada. Nenhuma imagem é transmitida sem ação do operador.";
    byId("cv-camera-start").disabled = false;
    byId("cv-camera-capture").disabled = true;
    const monitor = byId("cv-camera-monitor");
    monitor.disabled = true;
    byId("cv-camera-stop").disabled = true;
    byId("cv-overlay").hidden = true;
    cvSetMetrics("Encerrada");
}
function cvCaptureFrame() {
    const video = byId("cv-video");
    if (!cvCameraStream || !video.videoWidth || !video.videoHeight)
        return Promise.resolve(null);
    const canvas = document.createElement("canvas");
    const scale = Math.min(1, 1280 / video.videoWidth);
    canvas.width = Math.round(video.videoWidth * scale);
    canvas.height = Math.round(video.videoHeight * scale);
    canvas.getContext("2d")?.drawImage(video, 0, 0, canvas.width, canvas.height);
    return new Promise((resolve) => canvas.toBlob((blob) => {
        resolve(blob ? new File([blob], "gx-camera-" + Date.now() + ".jpg", { type: "image/jpeg" }) : null);
    }, "image/jpeg", 0.9));
}
async function cvAnalyzeCurrent(auto = false) {
    const analyze = byId("cv-analyze");
    const confirm = byId("cv-confirm");
    if (!cvSelectedFile || cvAnalyzing)
        return;
    cvAnalyzing = true;
    analyze.disabled = true;
    if (!auto)
        cvSetFeedback("Executando inferência YOLO…");
    try {
        const form = new FormData();
        form.append("file", cvSelectedFile);
        form.append("frame_id", "cv-" + Date.now());
        const threshold = byId("cv-threshold");
        form.append("threshold", String(Number(threshold.value) / 100));
        const response = await apiFetch("/deteccao/frame", { method: "POST", body: form });
        const payload = await response.json();
        if (!response.ok)
            throw new Error("detail" in payload ? payload.detail : "Não foi possível analisar a imagem");
        const frame = payload;
        const detections = frame.deteccoes;
        cvLastDetections = detections;
        cvRenderResults(detections);
        cvLastLatencyMs = frame.latencia_ms;
        cvSetMetrics("Upload sob demanda", auto ? 1 : 0, frame.latencia_ms);
        cvDrawBoxes(detections);
        confirm.disabled = !detections.length;
        cvSetFeedback(auto
            ? "Monitoramento ao vivo: " + detections.length + " detecção(ões) no último quadro."
            : detections.length + " detecção(ões) retornada(s) pelo modelo.", "success");
    }
    catch (error) {
        cvSetFeedback(error instanceof Error ? error.message : "Falha ao analisar a imagem.", "error");
    }
    finally {
        cvAnalyzing = false;
        analyze.disabled = false;
    }
}
function cvRenderResults(detections) {
    const results = byId("cv-results");
    if (!detections.length) {
        results.innerHTML = '<div class="empty-state">Nenhum objeto compatível foi reconhecido acima do limiar selecionado.</div>';
        return;
    }
    results.innerHTML = detections.map((item) => {
        const severity = normalizeSeverity(item.severidade);
        const style = severityStyle(severity);
        const bbox = item.bbox.join(", ");
        return '<article class="cv-result" style="border-left-color:' + style.color + '">' +
            '<span class="cv-result-icon" style="background:' + style.color + '">' + escapeHtml(item.nome.slice(0, 1).toUpperCase()) + '</span>' +
            '<span><strong>' + escapeHtml(item.nome.replace(/_/g, " ")) + '</strong><small>' +
            (item.classe_modelo ? 'classe YOLO: ' + escapeHtml(item.classe_modelo) + ' · ' : '') +
            escapeHtml(item.tipo) + ' · caixa: ' + bbox + '</small></span>' +
            '<span class="cv-result-confidence">' + Math.round(item.confianca * 100) + '%</span></article>';
    }).join("");
}
async function cvLoadStatus() {
    const badge = byId("cv-model-status");
    try {
        const response = await apiFetch("/deteccao/status");
        if (!response.ok)
            throw new Error("status indisponível");
        const status = await response.json();
        cvDetectorAvailable = status.disponivel;
        badge.textContent = status.disponivel ? "YOLO pronto" : "Modelo não configurado";
        badge.className = "cv-status " + (status.disponivel ? "ready" : "unavailable");
        if (status.disponivel)
            logSessionActivity("sincronizacao", "YOLO pronto para inferência real");
        if (loadedEvents.length)
            void loadRightPanelAlerts();
        if (!status.disponivel)
            cvSetFeedback(status.erro || "Configure os pesos YOLO para ativar a análise real.");
    }
    catch {
        badge.textContent = "API indisponível";
        badge.className = "cv-status unavailable";
    }
}
function initComputerVision() {
    const input = byId("cv-file");
    const analyze = byId("cv-analyze");
    const confirm = byId("cv-confirm");
    const threshold = byId("cv-threshold");
    const thresholdValue = byId("cv-threshold-value");
    input.addEventListener("change", () => {
        const file = input.files?.[0] || null;
        if (!file)
            return;
        cvSetFile(file, file.name);
    });
    byId("cv-remove-file").addEventListener("click", cvClearFile);
    byId("cv-camera-start").addEventListener("click", async () => {
        if (!navigator.mediaDevices?.getUserMedia) {
            cvSetFeedback("Este navegador não disponibiliza acesso à câmera.", "error");
            return;
        }
        try {
            cvSetFeedback("Solicitando autorização da câmera…");
            cvCameraStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: "environment" }, width: { ideal: 1280 }, height: { ideal: 720 } }, audio: false });
            const video = byId("cv-video");
            video.srcObject = cvCameraStream;
            await video.play();
            byId("cv-video-empty").hidden = true;
            byId("cv-camera-status").textContent = "Câmera ao vivo local — captura somente quando você solicitar.";
            byId("cv-camera-start").disabled = true;
            byId("cv-camera-capture").disabled = false;
            byId("cv-camera-monitor").disabled = false;
            byId("cv-camera-stop").disabled = false;
            cvSetMetrics("Câmera local", 0, cvLastLatencyMs);
            cvConnectFrames();
            cvSetFeedback("Prévia ao vivo pronta. Capture um quadro para analisar.", "success");
        }
        catch (error) {
            const message = error instanceof Error && error.name === "NotAllowedError"
                ? "Permissão da câmera não concedida."
                : "Não foi possível iniciar a câmera selecionada.";
            cvSetFeedback(message, "error");
        }
    });
    byId("cv-camera-stop").addEventListener("click", cvStopCamera);
    byId("cv-camera-capture").addEventListener("click", async () => {
        const frame = await cvCaptureFrame();
        if (!frame) {
            cvSetFeedback("Aguarde a prévia da câmera ficar disponível.", "error");
            return;
        }
        cvSetFile(frame, "Quadro capturado da câmera ao vivo");
    });
    byId("cv-camera-monitor").addEventListener("click", async () => {
        const monitor = byId("cv-camera-monitor");
        if (cvMonitoring) {
            cvStopMonitoring();
            cvSetFeedback("Monitoramento pausado. A câmera continua disponível.");
            return;
        }
        const processFrame = async () => {
            const frame = await cvCaptureFrame();
            if (!frame)
                return;
            if (await cvSendFrame(frame))
                return;
            cvSetFile(frame, "Quadro do monitoramento ao vivo");
            await cvAnalyzeCurrent(true);
        };
        cvMonitoring = true;
        monitor.textContent = "Parar monitoramento";
        cvSetFeedback("Monitoramento iniciado: no máximo 1 quadro por segundo.", "success");
        await processFrame();
        cvMonitorTimer = window.setInterval(() => { void processFrame(); }, 1000);
    });
    document.addEventListener("visibilitychange", () => {
        if (document.hidden && cvCameraStream)
            cvStopCamera();
    });
    threshold.addEventListener("input", () => { thresholdValue.textContent = threshold.value + "%"; });
    analyze.addEventListener("click", () => { void cvAnalyzeCurrent(); });
    confirm.addEventListener("click", async () => {
        const detection = cvLastDetections[0];
        if (!cvSelectedFile || !detection)
            return;
        confirm.disabled = true;
        cvSetFeedback("Revalidando no servidor e registrando a observação…");
        try {
            const form = new FormData();
            form.append("file", cvSelectedFile);
            form.append("nome", detection.nome);
            form.append("confianca", String(detection.confianca));
            form.append("severidade", detection.severidade);
            form.append("tipo", detection.tipo);
            form.append("latitude", String(window.CONFIG.MAP_CENTER.lat));
            form.append("longitude", String(window.CONFIG.MAP_CENTER.lng));
            const response = await apiFetch("/deteccao/confirmar", { method: "POST", body: form });
            const evento = await response.json();
            if (!response.ok)
                throw new Error("detail" in evento ? evento.detail : "Não foi possível confirmar a ocorrência");
            const item = evento;
            if (!loadedEvents.some((entry) => entry.id === item.id))
                loadedEvents.unshift(item);
            updateMetrics(loadedEvents);
            applyMarkers();
            renderEventList(loadedEvents);
            selectEvent(item.id);
            logSessionActivity("evento_criado", "Evidência YOLO confirmada: " + item.titulo, item.id, item.severidade);
            cvSetFeedback("Observação YOLO revalidada e adicionada ao mapa.", "success");
        }
        catch (error) {
            cvSetFeedback(error instanceof Error ? error.message : "Falha ao confirmar ocorrência.", "error");
        }
        finally {
            confirm.disabled = false;
        }
    });
    void cvLoadStatus();
}
/* ============================================================
   LAYOUT VERTICAL — no retrato, a "Evidência visual" (bloco do
   painel direito) desce para o painel esquerdo, ocupando o
   espaço da antiga Criticidade. Em paisagem volta ao seu lugar.
   ============================================================ */
function initEvidencePanelDock() {
    const dock = document.getElementById("left-evidence-dock");
    const evidence = document.querySelector(".section-evidence");
    if (!dock || !evidence)
        return;
    const homeParent = evidence.parentElement;
    const portrait = window.matchMedia("(orientation: portrait)");
    const apply = () => {
        if (portrait.matches) {
            if (evidence.parentElement !== dock)
                dock.appendChild(evidence);
            dock.hidden = false;
        }
        else {
            if (homeParent && evidence.parentElement !== homeParent) {
                homeParent.appendChild(evidence);
            }
            dock.hidden = true;
        }
    };
    apply();
    portrait.addEventListener("change", apply);
}
let ytFile = null;
let ytObjectUrl = null;
let ytAnalyzing = false;
let ytMinVeiculos = 8;
const YT_CLASSES_VEICULO = ["veiculo", "motocicleta", "onibus", "caminhao"];
function ytShow(destino) {
    document.querySelectorAll(".view").forEach((v) => {
        v.hidden = true;
        v.classList.remove("view-active");
    });
    const yolo = destino === "yolo";
    const alvo = byId(yolo ? "view-yolo-teste" : "view-dashboard");
    alvo.hidden = false;
    alvo.classList.add("view-active");
    byId("rail-inicio")?.classList.toggle("active", !yolo);
    byId("rail-inicio")?.setAttribute("aria-pressed", String(!yolo));
    byId("rail-yolo-teste")?.classList.toggle("active", yolo);
    byId("rail-yolo-teste")?.setAttribute("aria-pressed", String(yolo));
}
function ytSetFeedback(message, tone = "") {
    const el = byId("yt-feedback");
    el.textContent = message;
    el.className = "yt-feedback" + (tone ? " " + tone : "");
}
function ytClearImage() {
    ytFile = null;
    if (ytObjectUrl) {
        URL.revokeObjectURL(ytObjectUrl);
        ytObjectUrl = null;
    }
    byId("yt-file").value = "";
    byId("yt-preview").hidden = true;
    byId("yt-image").removeAttribute("src");
    const canvas = byId("yt-overlay");
    canvas.getContext("2d")?.clearRect(0, 0, canvas.width, canvas.height);
    byId("yt-file-label").textContent = "Selecionar imagem";
    byId("yt-analyze").disabled = true;
    byId("yt-verdict").hidden = true;
    byId("yt-detections").innerHTML = "";
    ytSetFeedback("Selecione uma imagem para começar.");
}
function ytSetImage(file) {
    if (file.size > 10 * 1024 * 1024) {
        ytSetFeedback("A imagem ultrapassa o limite de 10 MB.", "error");
        return;
    }
    ytFile = file;
    if (ytObjectUrl)
        URL.revokeObjectURL(ytObjectUrl);
    ytObjectUrl = URL.createObjectURL(file);
    byId("yt-image").src = ytObjectUrl;
    byId("yt-preview").hidden = false;
    byId("yt-file-label").textContent = file.name;
    byId("yt-analyze").disabled = false;
    byId("yt-verdict").hidden = true;
    byId("yt-detections").innerHTML = "";
    ytSetFeedback("Imagem pronta. Clique em “Analisar imagem”.");
}
function ytDrawBoxes(deteccoes) {
    const img = byId("yt-image");
    const canvas = byId("yt-overlay");
    if (!img.naturalWidth)
        return;
    canvas.width = img.naturalWidth;
    canvas.height = img.naturalHeight;
    const ctx = canvas.getContext("2d");
    if (!ctx)
        return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    const escala = Math.max(2, canvas.width / 320);
    deteccoes.forEach((d) => {
        const [x1, y1, x2, y2] = d.bbox;
        const cor = severityStyle(d.severidade).color;
        ctx.strokeStyle = cor;
        ctx.lineWidth = escala;
        ctx.strokeRect(x1, y1, Math.max(1, x2 - x1), Math.max(1, y2 - y1));
        ctx.fillStyle = cor;
        ctx.font = "700 " + Math.max(12, canvas.width / 40) + "px Inter, sans-serif";
        ctx.fillText(d.nome + " " + Math.round(d.confianca * 100) + "%", x1 + 3, Math.max(14, y1 - 4));
    });
}
async function ytChamarModelo(rota) {
    const form = new FormData();
    form.append("file", ytFile);
    // Sem parâmetro de confiança: o servidor aplica o limiar padrão de cada modelo
    // e devolve o que reconheceu, com a confiança de cada caixa.
    const response = await apiFetch(rota, { method: "POST", body: form });
    if (response.status === 503)
        return []; // modelo indisponível — tratado no resumo
    if (!response.ok)
        throw new Error("O modelo retornou " + response.status);
    return response.json();
}
async function ytAnalisar() {
    if (!ytFile || ytAnalyzing)
        return;
    ytAnalyzing = true;
    const botao = byId("yt-analyze");
    botao.disabled = true;
    ytSetFeedback("Rodando inferência YOLO nos dois modelos…");
    try {
        const [incidentes, objetos] = await Promise.all([
            ytChamarModelo("/deteccao/incidente"),
            ytChamarModelo("/deteccao/imagem"),
        ]);
        const alagamentos = incidentes.filter((d) => d.nome === "alagamento");
        const veiculos = objetos.filter((d) => YT_CLASSES_VEICULO.includes(d.nome));
        const todas = [...alagamentos, ...incidentes.filter((d) => d.nome !== "alagamento"), ...objetos];
        let tone = "ok";
        let titulo = "Nada relevante detectado";
        let detalhe = veiculos.length
            ? veiculos.length + " veículo(s) reconhecido(s) — abaixo do limite de trânsito (" + ytMinVeiculos + ")"
            : "Nenhum objeto ou incidente reconhecido acima do limiar";
        if (alagamentos.length) {
            const maxConf = Math.max(...alagamentos.map((d) => d.confianca));
            tone = "danger";
            titulo = "Alagamento detectado";
            detalhe = alagamentos.length + " região(ões) de água · confiança máx. " + Math.round(maxConf * 100) + "%";
        }
        else if (veiculos.length >= ytMinVeiculos) {
            tone = "warn";
            titulo = "Trânsito intenso";
            detalhe = veiculos.length + " veículos no quadro (limite de congestionamento: " + ytMinVeiculos + ")";
        }
        const verdict = byId("yt-verdict");
        verdict.className = "yt-verdict yt-" + tone;
        verdict.hidden = false;
        verdict.innerHTML = '<strong>' + titulo + '</strong><span>' + escapeHtml(detalhe) + '</span>';
        const lista = byId("yt-detections");
        if (!todas.length) {
            lista.innerHTML = '<p class="yt-empty">O YOLO não retornou nenhuma caixa acima do limiar padrão dos modelos nesta imagem.</p>';
        }
        else {
            lista.innerHTML = '<div class="yt-list-head">Detecções do modelo (' + todas.length + ')</div>' +
                todas.map((d) => {
                    const cor = severityStyle(d.severidade).color;
                    const origem = d.nome === "alagamento" ? "modelo de incidentes" : "modelo de objetos";
                    return '<div class="yt-det-row" style="border-left-color:' + cor + '">' +
                        '<span class="yt-det-name">' + escapeHtml(d.nome.replace(/_/g, " ")) + '</span>' +
                        '<span class="yt-det-src">' + origem + (d.classe_modelo ? " · " + escapeHtml(d.classe_modelo) : "") + '</span>' +
                        '<span class="yt-det-conf">' + Math.round(d.confianca * 100) + '%</span>' +
                        '</div>';
                }).join("");
        }
        ytDrawBoxes(todas);
        ytSetFeedback("Análise concluída.", "success");
    }
    catch (error) {
        ytSetFeedback(error instanceof Error ? error.message : "Falha ao analisar a imagem.", "error");
    }
    finally {
        ytAnalyzing = false;
        botao.disabled = false;
    }
}
async function ytCarregarStatus() {
    const badge = byId("yt-model-status");
    try {
        const response = await apiFetch("/deteccao/status");
        if (!response.ok)
            throw new Error("status indisponível");
        const status = await response.json();
        if (typeof status.min_veiculos_transito === "number")
            ytMinVeiculos = status.min_veiculos_transito;
        const objOk = status.disponivel;
        const incOk = Boolean(status.incidente?.disponivel);
        badge.textContent = objOk && incOk ? "2 modelos prontos" : objOk || incOk ? "1 de 2 modelos" : "Modelos indisponíveis";
        badge.className = "yt-status " + (objOk && incOk ? "ready" : objOk || incOk ? "partial" : "unavailable");
        if (!incOk)
            ytSetFeedback("Modelo de alagamento indisponível no servidor — só a detecção de objetos vai responder.", "error");
    }
    catch {
        badge.textContent = "API indisponível";
        badge.className = "yt-status unavailable";
    }
}
function initYoloTester() {
    const railBtn = byId("rail-yolo-teste");
    if (!railBtn)
        return;
    railBtn.addEventListener("click", () => ytShow("yolo"));
    byId("rail-inicio")?.addEventListener("click", () => ytShow("inicio"));
    const input = byId("yt-file");
    input.addEventListener("change", () => {
        const file = input.files?.[0];
        if (file)
            ytSetImage(file);
    });
    byId("yt-clear").addEventListener("click", ytClearImage);
    byId("yt-analyze").addEventListener("click", () => { void ytAnalisar(); });
    void ytCarregarStatus();
}
async function fetchEvents() {
    const params = new URLSearchParams({ limite: "200" });
    const statusElement = byId("filtro-status");
    if (statusElement.value)
        params.set("status", statusElement.value);
    const response = await apiFetch("/eventos?" + params.toString());
    if (!response.ok)
        throw new Error("API retornou " + response.status);
    return response.json();
}
async function fetchJson(url) {
    const response = await apiFetch(url);
    if (!response.ok)
        throw new Error("API retornou " + response.status);
    return response.json();
}
/** Dados do painel operacional sempre vêm da API, inclusive em modo demonstração. */
async function fetchOperationalData(url) {
    const response = await apiFetch(url);
    if (!response.ok)
        throw new Error("API retornou " + response.status);
    return response.json();
}
async function loadLiveWeather() {
    const status = byId("live-source-status");
    try {
        const response = await apiFetch("/fontes/tempo-real/clima");
        const weather = await response.json();
        if (!response.ok || !weather.disponivel)
            throw new Error("fonte indisponível");
        const rain = Number(weather.precipitacao_mm || 0).toFixed(1);
        status.classList.remove("source-offline");
        status.innerHTML = '<span class="weather-copy"><span>Clima ao vivo</span><strong>' +
            Number(weather.temperatura_c || 0).toFixed(0) + '°C · ' + rain + ' mm</strong></span>';
        status.title = "Fonte externa: " + (weather.fonte || "Open-Meteo") + " · vento " + Number(weather.vento_kmh || 0).toFixed(0) + " km/h";
    }
    catch {
        status.innerHTML = '<span class="weather-copy"><span>Clima ao vivo</span><strong>indisponível</strong></span>';
        status.classList.add("source-offline");
    }
}
async function loadLiveAirQuality() {
    const status = byId("live-air-status");
    try {
        const response = await apiFetch("/fontes/tempo-real/ar");
        const air = await response.json();
        if (!response.ok || !air.disponivel)
            throw new Error("fonte indisponível");
        status.textContent = "Ar ao vivo: AQI " + Math.round(Number(air.aqi_us || 0)) + " · PM2.5 " + Number(air.pm2_5 || 0).toFixed(1) + " μg/m³";
        status.title = "Fonte externa: " + (air.fonte || "Open-Meteo Air Quality");
    }
    catch {
        status.textContent = "Qualidade do ar: indisponível";
        status.classList.add("source-offline");
    }
}
function formatClock(value) {
    return value.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}
function isEventVisible(event) {
    if (!activeSeverities.has(normalizeSeverity(event.severidade)))
        return false;
    if (!searchTerm)
        return true;
    const haystack = [
        event.titulo,
        event.descricao,
        event.tipo,
        event.status,
        event.regiao?.nome,
        event.localizacao?.endereco,
        event.localizacao?.bairro,
        event.fonte?.nome,
    ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
    return haystack.includes(searchTerm);
}
function clearMarkers() {
    deselectCurrentMarker();
    transientMarkerLayers.forEach((marker) => marker.remove());
    transientMarkerLayers.clear();
    markersById.clear();
}
function markerGlyph(event) {
    const value = (event.tipo + " " + event.titulo).toLowerCase();
    if (event.tipo === "observacao_visual")
        return "◎";
    if (value.includes("alag") || value.includes("chuva"))
        return "≋";
    if (value.includes("trâns") || value.includes("trans") || value.includes("via"))
        return "▲";
    if (value.includes("câmera") || value.includes("camera"))
        return "◉";
    if (value.includes("bloque"))
        return "▰";
    return "!";
}
function markerIcon(event, style, selected = false) {
    const critical = style.label === "Crítica";
    const markerColor = selected ? "#ff7900" : style.color;
    return window.L.divIcon({
        className: "gx-marker-shell" + (selected ? " is-selected" : ""),
        html: '<span class="gx-map-marker' + (critical ? " is-critical" : "") + '" style="--marker-color:' + markerColor + ';--severity-color:' + style.color + '"><i>' + markerGlyph(event) + '</i></span>',
        iconSize: selected ? [58, 58] : [32, 32],
        iconAnchor: selected ? [29, 29] : [16, 16],
        popupAnchor: [0, selected ? -28 : -18],
    });
}
function formatDate(value) {
    if (!value)
        return "";
    return parseApiDate(value).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
}
function formatTime(value) {
    if (!value)
        return "";
    return parseApiDate(value).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
}
function parseApiDate(value) {
    return new Date(/[zZ]|[+-]\d\d:\d\d$/.test(value) ? value : value + "Z");
}
function formatConfidence(value) {
    if (value == null || Number.isNaN(Number(value)))
        return "";
    return String((Number(value) * 100).toFixed(0)) + "%";
}
function formatDetectadoEm(value) {
    if (!value)
        return "Sem registro";
    try {
        return parseApiDate(value).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
    }
    catch {
        return value;
    }
}
function infoWindowContent(event) {
    const style = severityStyle(event.severidade);
    const address = event.localizacao?.endereco || event.localizacao?.bairro || "";
    const confidence = formatConfidence(event.confianca);
    const source = event.fonte?.nome || "";
    const location = [address, event.regiao?.nome].filter(Boolean).join(" · ") || "Localização não informada";
    const detectedAt = event.detectado_em ? formatDate(event.detectado_em) : "Horário não informado";
    const popupId = "gx-popup-" + event.id;
    return '<article class="gx-event-popup" role="dialog" aria-modal="false" aria-labelledby="' + popupId + '-title">' +
        '<div class="gx-event-popup-head"><span class="info-criticidade" style="background:' + style.color + '">' + escapeHtml(style.label) + '</span>' +
        (confidence ? '<span class="gx-event-popup-confidence">' + confidence + ' confiança</span>' : '') + '</div>' +
        '<h3 id="' + popupId + '-title">' + escapeHtml(event.titulo) + '</h3>' +
        (event.descricao ? '<p class="gx-event-popup-description">' + escapeHtml(event.descricao) + '</p>' : '') +
        '<dl class="gx-event-popup-meta">' +
        '<div><dt>Localização</dt><dd>' + escapeHtml(location) + '</dd></div>' +
        '<div><dt>Fonte</dt><dd>' + escapeHtml(source || "Não informada") + '</dd></div>' +
        '<div><dt>Horário</dt><dd>' + escapeHtml(detectedAt) + '</dd></div>' +
        '</dl>' +
        '<button type="button" class="gx-event-popup-action" data-event-id="' + event.id + '">Ver detalhes</button>' +
        '</article>';
}
function focusSelectedEventDetails(eventId) {
    popupReturnFocusToMarker = false;
    selectEvent(eventId, false);
    if (map)
        map.closePopup();
    openEventDetail(eventId);
    window.requestAnimationFrame(() => {
        const title = byId("selected-title");
        title.focus();
    });
}
function createMarker(event) {
    if (!window.L || !map)
        return;
    const style = severityStyle(event.severidade);
    const marker = window.L.marker([event.latitude, event.longitude], {
        icon: markerIcon(event, style),
        title: style.label + ": " + event.titulo,
        riseOnHover: true,
    }).addTo(map).bindPopup(infoWindowContent(event), {
        maxWidth: 300,
        minWidth: 250,
        offset: [0, -22],
        autoPanPadding: [20, 20],
        closeButton: true,
        closeOnEscapeKey: true,
    });
    marker.on("click", () => {
        selectEvent(event.id);
    });
    markersById.set(event.id, marker);
    transientMarkerLayers.add(marker);
}
function createClusterMarkers(events) {
    if (!map || !window.L)
        return;
    const cells = new Map();
    events.forEach((event) => {
        const point = map.project([event.latitude, event.longitude], map.getZoom());
        const key = Math.floor(point.x / 56) + ":" + Math.floor(point.y / 56);
        const bucket = cells.get(key) || [];
        bucket.push(event);
        cells.set(key, bucket);
    });
    cells.forEach((bucket) => {
        if (bucket.length === 1) {
            createMarker(bucket[0]);
            return;
        }
        const latitude = bucket.reduce((sum, event) => sum + event.latitude, 0) / bucket.length;
        const longitude = bucket.reduce((sum, event) => sum + event.longitude, 0) / bucket.length;
        const marker = window.L.marker([latitude, longitude], {
            icon: window.L.divIcon({
                className: "gx-marker-cluster-shell",
                html: '<button type="button" class="gx-marker-cluster" aria-label="' + bucket.length + ' eventos agrupados">' + bucket.length + '</button>',
                iconSize: [42, 42], iconAnchor: [21, 21],
            }),
            keyboard: true,
            title: bucket.length + " eventos agrupados",
        }).addTo(map);
        marker.on("click", () => {
            const bounds = window.L.latLngBounds(bucket.map((event) => [event.latitude, event.longitude]));
            map.fitBounds(bounds, { padding: [48, 48], maxZoom: 16 });
        });
        transientMarkerLayers.add(marker);
    });
}
function fitMapBounds(events) {
    if (!events.length || !map || !window.L)
        return;
    if (events.length === 1) {
        map.setView([window.CONFIG.MAP_CENTER.lat, window.CONFIG.MAP_CENTER.lng], Math.max(window.CONFIG.MAP_ZOOM, 12));
        return;
    }
    const bounds = window.L.latLngBounds(events.map((event) => [event.latitude, event.longitude]));
    map.fitBounds(bounds, { padding: [42, 42], maxZoom: 16 });
}
function formatStatus(value) {
    const labels = {
        em_analise: "Em análise",
        observacao_visual: "Observação visual",
        veiculo: "Veículo",
        onibus: "Ônibus",
        caminhao: "Caminhão",
        transito: "Trânsito",
        incendio: "Incêndio",
    };
    return labels[value.toLocaleLowerCase("pt-BR")] || value.replace(/_/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());
}
function highlightMarker(eventId) {
    deselectCurrentMarker();
    const marker = markersById.get(eventId);
    if (!marker || !map)
        return;
    selectedMarkerId = eventId;
    const event = loadedEvents.find((e) => e.id === eventId);
    if (!event)
        return;
    const style = severityStyle(event.severidade);
    marker.setIcon(markerIcon(event, style, true));
    marker.setZIndexOffset(1000);
}
function deselectCurrentMarker() {
    if (selectedMarkerId == null)
        return;
    const marker = markersById.get(selectedMarkerId);
    if (!marker) {
        selectedMarkerId = null;
        return;
    }
    const event = loadedEvents.find((e) => e.id === selectedMarkerId);
    if (event) {
        const style = severityStyle(event.severidade);
        marker.setIcon(markerIcon(event, style));
        marker.setZIndexOffset(0);
    }
    selectedMarkerId = null;
}
function selectEvent(id, openDetails = false, openPopup = false) {
    selectedEventId = id;
    const event = loadedEvents.find((e) => e.id === id);
    renderSelectedEvent(event || null);
    highlightListItem(id);
    if (event) {
        loadEventEvidence(event.id);
    }
    else {
        clearEventEvidence();
    }
    if (event && map && window.L) {
        map.setView([event.latitude, event.longitude], Math.max(map.getZoom(), 14));
        const marker = markersById.get(event.id);
        if (marker && openPopup) {
            marker.openPopup();
        }
    }
    if (event && openDetails)
        openEventDetail(event.id);
}
function detailLoading() {
    return '<div class="detail-state detail-loading"><span class="skeleton skeleton-line w60"></span><span class="skeleton skeleton-line"></span><span class="skeleton skeleton-line w40"></span></div>';
}
function detailError() {
    return '<div class="detail-state detail-error"><strong>Não foi possível carregar esta seção.</strong><button type="button" data-action="retry-detail">Tentar novamente</button></div>';
}
function detailEmpty(section) {
    return '<div class="detail-state"><span>' + escapeHtml(detailEmptyMessage(section)) + '</span></div>';
}
function detailRows(rows) {
    return '<dl class="detail-rows">' + rows.map(([label, value]) => '<div><dt>' + escapeHtml(label) + '</dt><dd>' + escapeHtml(value) + '</dd></div>').join("") + '</dl>';
}
function evidenceImageSource(evidence) {
    return evidence.url_externa || (evidence.caminho_arquivo ? window.CONFIG.API_BASE_URL + "/evidencias/arquivo/" + encodeURIComponent(evidence.caminho_arquivo) : "");
}
function setDetailOperationFeedback(message = "", state = "") {
    const feedback = byId("detail-operation-feedback");
    feedback.textContent = message;
    feedback.className = "detail-operation-feedback" + (state ? " is-" + state : "");
}
function setDetailActionPending(pending) {
    detailActionInFlight = pending;
    document.querySelectorAll("[data-detail-action]").forEach((button) => {
        button.disabled = pending;
        button.setAttribute("aria-busy", String(pending));
    });
}
async function requestOperationalAction(path, method, body) {
    const response = await apiFetch(path, {
        method,
        headers: { "Content-Type": "application/json" },
        body: body ? JSON.stringify(body) : undefined,
    });
    if (response.ok)
        return response.json();
    let detail = "API retornou " + response.status;
    try {
        const payload = await response.json();
        if (typeof payload.detail === "string")
            detail = payload.detail;
        else if (Array.isArray(payload.detail))
            detail = payload.detail.map((item) => item.msg || "Dados inválidos").join(" · ");
    }
    catch { /* resposta sem JSON: mantém o status HTTP */ }
    throw new Error(detail);
}
async function refreshAfterDetailAction(eventId) {
    await loadEvents();
    if (detailEventId === eventId)
        await loadDetailSection();
}
async function runDetailMutation(successMessage, operation) {
    const eventId = detailEventId;
    if (eventId == null || detailActionInFlight)
        return;
    setDetailActionPending(true);
    setDetailOperationFeedback("Processando operação…", "progress");
    try {
        await operation(eventId);
        await refreshAfterDetailAction(eventId);
        setDetailOperationFeedback(successMessage, "success");
    }
    catch (error) {
        setDetailOperationFeedback("A operação não foi concluída: " + (error instanceof Error ? error.message : "erro desconhecido"), "error");
    }
    finally {
        setDetailActionPending(false);
    }
}
function syncDetailActionFields(event) {
    const status = byId("detail-event-status");
    const title = byId("detail-notification-form").elements.namedItem("titulo");
    status.value = event?.status || "ativo";
    if (title)
        title.value = event ? "Atualização: " + event.titulo : "";
    const route = byId("detail-route-link");
    if (event) {
        route.href = buildRouteUrl(event.latitude, event.longitude);
        route.removeAttribute("aria-disabled");
    }
    else {
        route.removeAttribute("href");
        route.setAttribute("aria-disabled", "true");
    }
    setDetailOperationFeedback();
}
function openEventDetail(eventId) {
    detailEventId = eventId;
    detailActiveTab = "resumo";
    const drawer = byId("event-detail-drawer");
    const event = loadedEvents.find((item) => item.id === eventId);
    byId("event-detail-title").textContent = event?.titulo || "Detalhes do evento";
    syncDetailActionFields(event);
    drawer.hidden = false;
    drawer.classList.add("open");
    updateDetailTabs();
    void loadDetailSection();
    window.requestAnimationFrame(() => byId("event-detail-close").focus());
}
function closeEventDetail() {
    const drawer = byId("event-detail-drawer");
    drawer.classList.remove("open");
    drawer.hidden = true;
    detailEventId = null;
}
function updateDetailTabs() {
    document.querySelectorAll("[data-detail-tab]").forEach((button) => {
        const active = button.dataset.detailTab === detailActiveTab;
        button.classList.toggle("active", active);
        button.setAttribute("aria-selected", String(active));
    });
}
async function loadDetailSection() {
    const eventId = detailEventId;
    const content = byId("event-detail-content");
    if (eventId == null)
        return;
    content.innerHTML = detailLoading();
    try {
        if (detailActiveTab === "resumo") {
            const event = await fetchOperationalData("/eventos/" + eventId);
            content.innerHTML = '<article class="detail-summary"><p>' + escapeHtml(detailValue(event.descricao, "Sem resumo registrado.")) + '</p>' +
                detailRows([
                    ["Localização", [event.localizacao?.endereco, event.localizacao?.bairro, event.regiao?.nome].filter(Boolean).join(" · ") || "Não informada"],
                    ["Coordenadas", event.latitude.toFixed(5) + ", " + event.longitude.toFixed(5)],
                    ["Fonte", event.fonte ? event.fonte.nome + " · " + event.fonte.tipo : "Não informada"],
                    ["Detectado", formatDetectadoEm(event.detectado_em)],
                    ["Status", formatStatus(event.status)],
                ]) + '</article>';
        }
        else if (detailActiveTab === "linha-do-tempo") {
            const [event, notifications, logs] = await Promise.all([
                fetchOperationalData("/eventos/" + eventId),
                fetchOperationalData("/notificacoes?evento_id=" + eventId + "&limite=50"),
                fetchOperationalData("/logs?evento_id=" + eventId + "&limite=50"),
            ]);
            const entries = [
                { at: event.detectado_em || "", title: "Evento detectado", detail: event.titulo },
                ...notifications.map((item) => ({ at: item.criado_em || "", title: "Notificação " + formatStatus(item.status), detail: item.titulo })),
                ...logs.map((item) => ({ at: item.criado_em, title: item.modulo, detail: item.mensagem })),
            ].sort((a, b) => new Date(b.at).getTime() - new Date(a.at).getTime());
            content.innerHTML = entries.length ? '<ol class="detail-timeline">' + entries.map((entry) => '<li><time>' + escapeHtml(formatDate(entry.at)) + '</time><strong>' + escapeHtml(entry.title) + '</strong><span>' + escapeHtml(entry.detail) + '</span></li>').join("") + '</ol>' : detailEmpty("linha do tempo");
        }
        else if (detailActiveTab === "evidencias") {
            const evidence = await fetchOperationalData("/evidencias?evento_id=" + eventId + "&limite=100");
            content.innerHTML = evidence.length ? evidence.map((item) => {
                const source = evidenceImageSource(item);
                return '<article class="detail-evidence">' +
                    (source ? '<button type="button" class="detail-evidence-thumb" data-detail-image="' + escapeHtml(source) + '" data-detail-alt="Evidência ' + escapeHtml(item.tipo) + '"><img src="' + escapeHtml(source) + '" alt="Evidência visual" loading="lazy"></button>' : '<div class="detail-evidence-thumb detail-no-image">Sem imagem disponível</div>') +
                    detailRows([["Tipo", formatStatus(item.tipo)], ["Modelo", detailValue(item.modelo_ia)], ["Classe", detailValue(item.classe_detectada)], ["Confiança", item.confianca == null ? "Não informada" : formatFusionPercent(Number(item.confianca))], ["Captura", formatDate(item.capturado_em)]]) +
                    '</article>';
            }).join("") : detailEmpty("evidências");
            content.querySelectorAll("[data-detail-image]").forEach((button) => button.addEventListener("click", () => openEvidenceViewer(button.dataset.detailImage || "", button.dataset.detailAlt || "Evidência visual")));
        }
        else if (detailActiveTab === "clima") {
            const [context, climate] = await Promise.all([
                fetchOperationalData("/dados-contextuais?evento_id=" + eventId + "&limite=100"),
                fetchOperationalData("/fontes/tempo-real/clima"),
            ]);
            const contextRows = context.filter((item) => item.categoria.toLowerCase().includes("clima")).map((item) => [item.chave, detailValue(item.valor_texto ?? item.valor_numerico, "Não informado") + (item.unidade ? " " + item.unidade : "")]);
            const liveRows = climate.disponivel ? [["Fonte atual", detailValue(climate.fonte)], ["Temperatura", climate.temperatura_c == null ? "Não informada" : climate.temperatura_c + " °C"], ["Precipitação", climate.precipitacao_mm == null ? "Não informada" : climate.precipitacao_mm + " mm"], ["Vento", climate.vento_kmh == null ? "Não informado" : climate.vento_kmh + " km/h"]] : [];
            content.innerHTML = (contextRows.length || liveRows.length) ? '<section class="detail-subsection"><h3>Contexto vinculado ao evento</h3>' + (contextRows.length ? detailRows(contextRows) : detailEmpty("contexto climático vinculado")) + '</section><section class="detail-subsection"><h3>Clima atual da fonte pública</h3>' + (liveRows.length ? detailRows(liveRows) : detailEmpty("clima atual")) + '</section>' : detailEmpty("clima");
        }
        else if (detailActiveTab === "fusion") {
            const fusion = await fetchOperationalData("/fusion/eventos/" + eventId + "/confiabilidade");
            const eventoTipo = loadedEvents.find((e) => e.id === eventId)?.tipo;
            content.innerHTML = '<section class="detail-fusion"><div class="detail-fusion-score"><strong>' + formatFusionPercent(fusion.confiabilidade) + '</strong><span>' + escapeHtml(formatFusionLevel(fusion.nivel)) + '</span><small>Calculado em ' + escapeHtml(formatDate(fusion.calculado_em)) + '</small></div>' +
                fusion.componentes.map((component) => '<article><strong>' + escapeHtml(fusionComponentLabel(component.nome, eventoTipo)) + '</strong><p>' + escapeHtml(formatFusionEquation(component, eventoTipo)) + '</p><span>Justificativa: ' + escapeHtml(detailValue(component.detalhe)) + '</span></article>').join("") +
                '<p class="detail-note">YOLO produz evidência; a decisão final vem da Fusão de Dados.</p></section>';
        }
        else if (detailActiveTab === "notificacoes") {
            const notifications = await fetchOperationalData("/notificacoes?evento_id=" + eventId + "&limite=100");
            content.innerHTML = notifications.length ? '<ul class="detail-list">' + notifications.map((item) => '<li><strong>' + escapeHtml(item.titulo) + '</strong><span>' + escapeHtml(formatStatus(item.status)) + " · " + escapeHtml(formatDate(item.criado_em)) + '</span><p>' + escapeHtml(item.mensagem) + '</p></li>').join("") + '</ul>' : detailEmpty("notificações");
        }
        else {
            const logs = await fetchOperationalData("/logs?evento_id=" + eventId + "&limite=100");
            content.innerHTML = logs.length ? '<ul class="detail-list">' + logs.map((item) => '<li><strong>' + escapeHtml(item.modulo + " · " + item.nivel) + '</strong><span>' + escapeHtml(formatDate(item.criado_em)) + '</span><p>' + escapeHtml(item.mensagem) + '</p></li>').join("") + '</ul>' : detailEmpty("histórico e logs");
        }
    }
    catch {
        content.innerHTML = detailError();
        content.querySelector("[data-action='retry-detail']")?.addEventListener("click", () => void loadDetailSection());
    }
}
function initEventDetailDrawer() {
    const drawer = byId("event-detail-drawer");
    byId("selected-open-detail").addEventListener("click", () => {
        if (selectedEventId != null)
            openEventDetail(selectedEventId);
    });
    byId("event-detail-close").addEventListener("click", closeEventDetail);
    drawer.addEventListener("click", (event) => { if (event.target === drawer)
        closeEventDetail(); });
    document.addEventListener("keydown", (event) => { if (event.key === "Escape" && !drawer.hidden)
        closeEventDetail(); });
    document.querySelectorAll("[data-detail-tab]").forEach((button) => button.addEventListener("click", () => {
        detailActiveTab = button.dataset.detailTab || "resumo";
        updateDetailTabs();
        void loadDetailSection();
    }));
    document.querySelector("[data-detail-action='update-status']")?.addEventListener("click", () => {
        const status = byId("detail-event-status").value;
        void runDetailMutation("Status atualizado na API.", (eventId) => requestOperationalAction("/eventos/" + eventId, "PATCH", { status }));
    });
    document.querySelector("[data-detail-action='resolve-event']")?.addEventListener("click", () => {
        const event = loadedEvents.find((item) => item.id === detailEventId);
        if (!event || isResolvedStatus(event.status)) {
            setDetailOperationFeedback("Este evento já está resolvido.", "progress");
            return;
        }
        if (!window.confirm("Marcar este evento como resolvido? Esta alteração será enviada à API."))
            return;
        void runDetailMutation("Evento marcado como resolvido.", (eventId) => requestOperationalAction("/eventos/" + eventId, "PATCH", { status: "resolvido" }));
    });
    document.querySelector("[data-detail-action='recalculate']")?.addEventListener("click", () => {
        void runDetailMutation("Confiança recalculada com os componentes retornados pela API.", (eventId) => requestOperationalAction("/fusion/eventos/" + eventId + "/recalcular", "POST"));
    });
    document.querySelector("[data-detail-action='copy-coordinates']")?.addEventListener("click", () => {
        const event = loadedEvents.find((item) => item.id === detailEventId);
        if (!event)
            return;
        const coordinates = event.latitude.toFixed(6) + ", " + event.longitude.toFixed(6);
        setDetailActionPending(true);
        setDetailOperationFeedback("Copiando coordenadas…", "progress");
        void (async () => {
            try {
                if (!navigator.clipboard?.writeText)
                    throw new Error("Clipboard API indisponível");
                await navigator.clipboard.writeText(coordinates);
                setDetailOperationFeedback("Coordenadas copiadas para a área de transferência.", "success");
            }
            catch {
                setDetailOperationFeedback("Não foi possível acessar a área de transferência.", "error");
            }
            finally {
                setDetailActionPending(false);
            }
        })();
    });
    byId("detail-notification-form").addEventListener("submit", (event) => {
        event.preventDefault();
        const data = new FormData(event.currentTarget);
        const value = (name) => String(data.get(name) || "").trim();
        void runDetailMutation("Notificação criada na API.", (eventId) => requestOperationalAction("/notificacoes", "POST", {
            evento_id: eventId,
            canal: value("canal"),
            destinatario: value("destinatario") || null,
            titulo: value("titulo"),
            mensagem: value("mensagem"),
        }));
    });
    byId("detail-evidence-form").addEventListener("submit", (event) => {
        event.preventDefault();
        const data = new FormData(event.currentTarget);
        const value = (name) => String(data.get(name) || "").trim();
        const confidenceValue = value("confianca");
        void runDetailMutation("Evidência registrada na API.", (eventId) => requestOperationalAction("/evidencias", "POST", {
            evento_id: eventId,
            tipo: value("tipo"),
            url_externa: value("url_externa") || null,
            modelo_ia: value("modelo_ia") || null,
            classe_detectada: value("classe_detectada") || null,
            confianca: confidenceValue === "" ? null : Number(confidenceValue),
        }));
    });
}
function renderSelectedEvent(event) {
    const selectedContainer = byId("evento-selecionado");
    const severity = byId("selected-severity");
    const title = byId("selected-title");
    const description = byId("selected-description");
    const statusPill = byId("selected-status-pill");
    const meta = byId("selected-event-meta");
    const region = byId("selected-region");
    const time = byId("selected-time");
    const source = byId("selected-source");
    const confidenceWrap = byId("confidence-circle-wrap");
    const confidenceValue = byId("confidence-circle-value");
    const confidenceRing = byId("confidence-fill-ring");
    const openDetail = byId("selected-open-detail");
    const breakdowns = document.querySelectorAll("#fusion-breakdown, #fusion-breakdown-panel");
    deselectCurrentMarker();
    if (!event) {
        delete selectedContainer.dataset.type;
        severity.textContent = "--";
        severity.style.background = "var(--text-muted)";
        title.textContent = "Selecione um evento";
        description.textContent = "Selecione um evento para visualizar os detalhes operacionais.";
        statusPill.textContent = "--";
        statusPill.className = "status-pill";
        meta.hidden = true;
        confidenceWrap.hidden = true;
        openDetail.hidden = true;
        setFusionSummary(null);
        breakdowns.forEach((b) => { b.innerHTML = ""; });
        {
            const explain = document.getElementById("fusion-explain");
            if (explain)
                explain.hidden = true;
        }
        return;
    }
    const style = severityStyle(event.severidade);
    selectedContainer.dataset.type = event.tipo;
    severity.textContent = style.label;
    severity.style.background = style.color;
    title.textContent = event.titulo;
    description.textContent = event.descricao || "Sem descrição operacional registrada.";
    const isActive = event.status === "ativo";
    statusPill.textContent = formatStatus(event.status);
    statusPill.className = "status-pill" + (isActive ? " status-ativo" : "");
    meta.hidden = false;
    region.textContent = event.regiao?.nome || event.localizacao?.bairro || "Sem região";
    time.textContent = formatDetectadoEm(event.detectado_em);
    source.textContent = event.fonte?.nome || event.fonte?.tipo || "Não identificada";
    const confValue = Number(event.confianca);
    if (!Number.isNaN(confValue)) {
        confidenceWrap.hidden = false;
        const pct = Math.round(confValue * 100);
        confidenceValue.textContent = pct + "%";
        const circumference = 188.5;
        const offset = circumference - (pct / 100) * circumference;
        confidenceRing.style.strokeDashoffset = String(offset);
        confidenceRing.classList.remove("good", "moderate", "poor");
        if (pct >= 75)
            confidenceRing.classList.add("good");
        else if (pct >= 40)
            confidenceRing.classList.add("moderate");
        else
            confidenceRing.classList.add("poor");
    }
    else {
        confidenceWrap.hidden = true;
    }
    openDetail.hidden = false;
    setFusionLoadingState();
    breakdowns.forEach((b) => { b.innerHTML = ""; });
    loadFusionBreakdown(event.id);
    highlightMarker(event.id);
}
function renderSeverityFilters() {
    const container = byId("legenda-criticidade");
    const allActive = activeSeverities.size === Object.keys(SEVERITIES).length;
    const countFor = (key) => loadedEvents.filter((e) => normalizeSeverity(e.severidade) === key).length;
    const items = [
        '<button class="sev-btn sev-all' + (allActive ? " active" : "") + '" data-criticidade="__all__" role="tab" aria-selected="' + allActive + '">' +
            '<span class="sev-dot" style="background:var(--text-secondary)"></span>' +
            '<span class="sev-label">Todos</span>' +
            '<span class="sev-count">' + loadedEvents.length + '</span>' +
            '</button>',
        ...Object.entries(SEVERITIES).map(([key, style]) => {
            const active = activeSeverities.has(key);
            const count = countFor(key);
            return '<button class="sev-btn ' + (active ? " active" : "") +
                '" style="--sev-color:' + style.color + ';--sev-dim:' + style.color + '16" data-criticidade="' + key + '" role="tab" aria-selected="' + active + '">' +
                '<span class="sev-dot" style="background:' + style.color + '"></span>' +
                '<span class="sev-label">' + style.label + '</span>' +
                (count > 0 ? '<span class="sev-count">' + count + '</span>' : '') +
                '</button>';
        }),
    ];
    container.innerHTML = '<div role="tablist" aria-label="Filtrar por severidade">' + items.join("") + '</div>';
    container.querySelectorAll("button[data-criticidade]").forEach((btn) => {
        btn.addEventListener("click", () => {
            const raw = btn.dataset.criticidade;
            if (raw === "__all__") {
                activeSeverities.clear();
                Object.keys(SEVERITIES).forEach((k) => activeSeverities.add(k));
            }
            else {
                const key = raw;
                if (activeSeverities.has(key)) {
                    activeSeverities.delete(key);
                }
                else {
                    activeSeverities.add(key);
                }
            }
            renderSeverityFilters();
            applyMarkers();
            renderEventList(loadedEvents);
        });
    });
}
function seedActivityFromEvents(events) {
    const unseen = events.filter((event) => !sessionActivity.some((entry) => entry.eventId === event.id)).slice(0, 6);
    sessionActivity.push(...unseen.map((event) => ({
        kind: "evento_criado",
        message: event.titulo,
        timestamp: event.detectado_em ? parseApiDate(event.detectado_em).getTime() : Date.now(),
        eventId: event.id,
        severity: event.severidade,
    })));
}
function updateMetrics(events) {
    const naoResolvidos = events.filter((e) => e.status !== "resolvido");
    animateKpi(byId("kpi-ativos"), String(naoResolvidos.length));
    animateKpi(byId("kpi-status-ativos"), String(events.filter((e) => e.status === "ativo").length));
    animateKpi(byId("kpi-status-analise"), String(events.filter((e) => e.status === "em_analise").length));
    renderSeverityFilters();
    renderOperatorProgress(events);
}
function renderOperatorProgress(events) {
    const resolved = events.filter((event) => event.status === "resolvido").length;
    const xp = events.length * 45 + resolved * 75;
    const level = Math.floor(xp / 250) + 1;
    const progress = xp % 250;
    byId("operator-level").textContent = "NÍVEL " + level;
    byId("operator-xp").textContent = xp + " XP";
    byId("operator-goal").textContent = "Próximo nível: " + (250 - progress) + " XP";
    byId("operator-xp-fill").style.width = Math.max(8, Math.round((progress / 250) * 100)) + "%";
    byId("operator-streak").textContent = "🔥 Sequência: " + events.filter((event) => event.status === "ativo").length;
}
function initIncidentComposer() {
    const modal = byId("incident-modal");
    const form = byId("incident-form");
    const feedback = byId("incident-feedback");
    const close = () => { modal.hidden = true; feedback.textContent = ""; feedback.className = "incident-feedback"; };
    document.getElementById("btn-novo-evento")?.addEventListener("click", () => { modal.hidden = false; form.elements.namedItem("titulo")?.focus(); });
    byId("incident-close").addEventListener("click", close);
    modal.addEventListener("click", (event) => { if (event.target === modal)
        close(); });
    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        const data = new FormData(form);
        const payload = {
            titulo: String(data.get("titulo") || ""), descricao: String(data.get("descricao") || "") || null,
            tipo: String(data.get("tipo") || "incidente"), severidade: String(data.get("severidade") || "media"),
            latitude: Number(data.get("latitude")), longitude: Number(data.get("longitude")), status: "ativo",
        };
        feedback.textContent = "Transmitindo ocorrência…";
        try {
            const response = await apiFetch("/eventos", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
            const created = await response.json();
            if (!response.ok)
                throw new Error("detail" in created ? created.detail || "Falha ao registrar" : "Falha ao registrar");
            const urbanEvent = created;
            if (!loadedEvents.some((item) => item.id === urbanEvent.id))
                loadedEvents.unshift(urbanEvent);
            updateMetrics(loadedEvents);
            applyMarkers();
            renderEventList(loadedEvents);
            selectEvent(urbanEvent.id);
            logSessionActivity("evento_criado", "Ocorrência transmitida: " + urbanEvent.titulo, urbanEvent.id, urbanEvent.severidade);
            feedback.textContent = "Ocorrência transmitida em tempo real.";
            feedback.className = "incident-feedback success";
            window.setTimeout(close, 700);
            form.reset();
        }
        catch (error) {
            feedback.textContent = error instanceof Error ? error.message : "Falha ao transmitir ocorrência.";
            feedback.className = "incident-feedback error";
        }
    });
}
function animateKpi(element, newValue) {
    if (element.textContent === newValue)
        return;
    element.style.transition = "none";
    element.style.opacity = "0.4";
    element.style.transform = "translateY(2px)";
    requestAnimationFrame(() => {
        element.textContent = newValue;
        requestAnimationFrame(() => {
            element.style.transition = "opacity 0.2s ease, transform 0.2s ease";
            element.style.opacity = "1";
            element.style.transform = "translateY(0)";
        });
    });
}
function updateCount(visible, total) {
    const label = visible === total ? String(total) : String(visible) + "/" + String(total);
    byId("contagem-eventos").textContent = label;
    const strip = byId("contagem-strip");
    if (strip)
        strip.textContent = String(visible);
}
function applyMarkers(shouldFitBounds = false) {
    clearMarkers();
    const visible = loadedEvents.filter(isEventVisible);
    const shouldCluster = !!map && visible.length > MARKER_CLUSTER_THRESHOLD && map.getZoom() < 15;
    if (shouldCluster)
        createClusterMarkers(visible);
    else
        visible.forEach(createMarker);
    if (shouldFitBounds)
        fitMapBounds(visible);
    if (selectedEventId != null && visible.some((event) => event.id === selectedEventId))
        highlightMarker(selectedEventId);
    updateCount(visible.length, loadedEvents.length);
}
function scheduleMarkerRefresh() {
    if (markerRefreshTimer)
        clearTimeout(markerRefreshTimer);
    markerRefreshTimer = setTimeout(() => applyMarkers(false), 80);
}
function renderEventList(events) {
    const list = byId("lista-eventos");
    const visible = events.filter(isEventVisible);
    list.innerHTML = "";
    if (!visible.length) {
        list.innerHTML = '<li class="empty-state">Nenhum evento encontrado.</li>';
        return;
    }
    const sorted = [...visible]
        .sort((a, b) => severityStyle(b.severidade).zIndex - severityStyle(a.severidade).zIndex)
        .slice(0, MAX_RENDERED_EVENT_CARDS);
    const fragment = document.createDocumentFragment();
    sorted.forEach((event, index) => {
        const style = severityStyle(event.severidade);
        const percent = event.confianca != null && !Number.isNaN(Number(event.confianca))
            ? Math.round(Number(event.confianca) * 100)
            : null;
        const confidence = percent == null ? "--" : percent + "%";
        const time = formatTime(event.detectado_em);
        const location = [event.regiao?.nome, event.localizacao?.bairro].filter(Boolean).join(" · ");
        const statusText = formatStatus(event.status);
        const critical = normalizeSeverity(event.severidade) === "critica";
        const item = document.createElement("li");
        item.className = "event-card" + (event.id === selectedEventId ? " active" : "");
        item.dataset.id = String(event.id);
        item.style.setProperty("--card-color", style.color);
        item.style.animationDelay = (index * 30) + "ms";
        item.classList.add("animate-in");
        item.setAttribute("tabindex", "0");
        item.setAttribute("role", "button");
        let meta = '<div class="event-meta">' +
            (time ? '<span class="meta-time">' + time + '</span>' : '') +
            '<span class="status-pill">' + escapeHtml(statusText) + '</span>' +
            '</div>';
        let confidenceMarkup = '';
        if (percent != null) {
            confidenceMarkup = '<div class="confidence-block">' +
                '<div class="confidence-head"><span class="confidence-label">CONFIABILIDADE</span>' +
                '<span class="confidence-num">' + confidence + '</span></div>' +
                '<div class="confidence-track"><div class="confidence-fill" style="width:' + percent + '%"></div></div>' +
                '</div>';
        }
        let footerMarkup = '';
        if (event.fonte) {
            footerMarkup =
                '<div class="event-divider"></div>' +
                    '<div class="intel-footer">' +
                    '<span class="intel-chip" title="Fonte da evidência">' +
                    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><ellipse cx="12" cy="5" rx="7" ry="3"/><path d="M5 5v14c0 1.66 3.13 3 7 3s7-1.34 7-3V5M5 12c0 1.66 3.13 3 7 3s7-1.34 7-3"/></svg>' +
                    '<span class="intel-label">Fonte</span>' +
                    '<span class="intel-value" title="' + escapeHtml(event.fonte.nome || event.fonte.tipo) + '">' + escapeHtml(event.fonte.nome || event.fonte.tipo) + '</span>' +
                    '</span>' +
                    (event.fonte.tipo ? '<span class="intel-chip intel-muted"><span class="intel-value" title="' + escapeHtml(formatStatus(event.fonte.tipo)) + '">' + escapeHtml(formatStatus(event.fonte.tipo)) + '</span></span>' : '') +
                    '</div>';
        }
        item.innerHTML =
            '<div class="event-card-top">' +
                '<span class="severity-badge' + (critical ? ' severity-critical' : '') + '" style="--sev-bg:' + style.color + '">' +
                '<i class="sev-dot-mini" style="background:' + style.color + '"></i>' + escapeHtml(style.label) +
                '</span>' +
                (confidence ? '<span class="confidence-badge">' + confidence + '</span>' : '') +
                '</div>' +
                '<h3 class="event-title">' + escapeHtml(event.titulo) + '</h3>' +
                (location ? '<div class="event-location"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 21s-6-5.2-6-10a6 6 0 1112 0c0 4.8-6 10-6 10z"/><circle cx="12" cy="11" r="2"/></svg><span>' + escapeHtml(location) + '</span></div>' : '') +
                (event.descricao ? '<p class="event-description">' + escapeHtml(event.descricao) + '</p>' : '') +
                meta +
                confidenceMarkup +
                footerMarkup;
        item.addEventListener("click", () => selectEvent(event.id));
        item.addEventListener("keydown", (e) => {
            if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                selectEvent(event.id);
            }
        });
        fragment.appendChild(item);
    });
    list.appendChild(fragment);
    if (visible.length > sorted.length) {
        const summary = document.createElement("li");
        summary.className = "list-limit-state";
        summary.textContent = "Mostrando os primeiros " + sorted.length + " de " + visible.length + " eventos. Use busca ou filtros para refinar.";
        list.appendChild(summary);
    }
}
function highlightListItem(id) {
    document.querySelectorAll(".event-card").forEach((element) => {
        element.classList.toggle("active", Number(element.dataset.id) === id);
    });
}
function showLoading(listId, message) {
    const msg = message || "Carregando...";
    byId(listId).innerHTML = '<li class="loading-state">' + escapeHtml(msg) + '</li>';
}
function showError(message) {
    byId("lista-eventos").innerHTML = '<li class="error-state"><strong>Dados Indisponíveis</strong><span>' + escapeHtml(message) + '</span></li>';
}
function setFusionLoadingState() {
    document.querySelectorAll(".data-fusion-level").forEach((element) => { element.textContent = "calculando..."; });
    document.querySelectorAll(".data-fusion-confidence").forEach((element) => { element.textContent = "--"; });
    document.querySelectorAll(".data-fusion-calculated-at").forEach((element) => { element.textContent = "Calculando pela API..."; });
    document.querySelectorAll("[data-action='recalculate-fusion']").forEach((button) => { button.disabled = true; });
    const explain = document.getElementById("fusion-explain");
    if (explain)
        explain.hidden = true;
}
// Pesos-base das dimensões da fusão — espelham data_fusion/fusion.py (PESOS).
const PESO_BASE_FUSAO = { ia: 0.4, clima: 0.3, fonte_oficial: 0.3 };
/** Painel no mapa: a conta completa da fusão, o veredito e o dado decisivo. */
function renderFusionExplain(result, eventoTipo) {
    const panel = document.getElementById("fusion-explain");
    const levelBadge = document.getElementById("fusion-explain-level");
    const body = document.getElementById("fusion-explain-body");
    if (!panel || !levelBadge || !body)
        return;
    const usados = result.componentes.filter((component) => component.peso > 0);
    const foraDeUso = result.componentes.filter((component) => component.peso <= 0);
    if (!usados.length) {
        panel.hidden = true;
        return;
    }
    panel.hidden = false;
    const p0 = (valor) => formatFusionPercent(valor, 0);
    const rotulo = (c) => c.nome === "ia" ? "IA" : fusionComponentLabel(c.nome, eventoTipo);
    const pesoBase = (c) => PESO_BASE_FUSAO[c.nome] ?? c.peso;
    const finalPct = p0(result.confiabilidade);
    levelBadge.textContent = formatFusionLevel(result.nivel) + " · " + finalPct;
    levelBadge.className = "fusion-explain-level nivel-" + result.nivel;
    // --- A conta ---
    const redistribuido = foraDeUso.length > 0
        && usados.some((c) => Math.abs(c.peso - pesoBase(c)) > 0.005);
    let pesos;
    if (redistribuido) {
        const somaFora = foraDeUso.reduce((soma, c) => soma + pesoBase(c), 0);
        const nomesFora = foraDeUso.map(rotulo).join(" e ");
        pesos = '<p class="fx-weights">Base: ' +
            result.componentes.map((c) => escapeHtml(rotulo(c)) + " " + p0(pesoBase(c))).join(", ") + '. ' +
            escapeHtml(nomesFora) + (foraDeUso.length > 1 ? " não pontuaram" : " não pontuou") +
            ', então ' + p0(somaFora) + ' de peso ' + (foraDeUso.length > 1 ? "delas foram rateados" : "dela foi rateado") +
            ' entre as demais &rarr; ' +
            usados.map((c) => escapeHtml(rotulo(c)) + " " + p0(pesoBase(c)) + "&rarr;" + p0(c.peso)).join(", ") + '.</p>';
    }
    else {
        pesos = '<p class="fx-weights">Pesos: ' +
            usados.map((c) => escapeHtml(rotulo(c)) + " " + p0(c.peso)).join(", ") + '.</p>';
    }
    const linhas = usados.map((c) => '<div class="fx-calc">' +
        '<span class="fx-calc-nome">' + escapeHtml(rotulo(c)) + '</span>' +
        '<b>' + p0(c.contribuicao) + '</b>' +
        '<span class="fx-calc-op">nota ' + p0(c.pontuacao) + ' × peso ' + p0(c.peso) + '</span>' +
        '</div>').join("");
    const total = '<div class="fx-calc fx-calc-total">' +
        '<span class="fx-calc-nome">Confiabilidade</span>' +
        '<b>' + finalPct + '</b>' +
        '<span class="fx-calc-op">' + usados.map((c) => p0(c.contribuicao)).join(" + ") + '</span>' +
        '</div>';
    const conta = '<div class="fx-block">' +
        '<span class="fx-label">A conta</span>' + pesos +
        '<div class="fx-calcs">' + linhas + total + '</div>' +
        '</div>';
    // --- Decisão ---
    const limiar = typeof result.limiar_ativo === "number" ? result.limiar_ativo : 0.75;
    const limiarPct = p0(limiar);
    const veredito = result.confiabilidade >= limiar
        ? 'Passou de ' + limiarPct + ' &rarr; promovido automaticamente para <strong>Ativo</strong>.'
        : 'Abaixo de ' + limiarPct + ' &rarr; fica <strong>Em análise</strong> até nova corroboração elevar o score.';
    const decisao = '<div class="fx-block">' +
        '<span class="fx-label">Decisão</span>' +
        '<p class="fx-lead">' + veredito + '</p>' +
        '</div>';
    // --- O que mais pesou ---
    const dominante = usados.reduce((maior, atual) => (atual.contribuicao > maior.contribuicao ? atual : maior));
    const decisivo = '<div class="fx-block">' +
        '<span class="fx-label">O que mais pesou</span>' +
        '<p class="fx-lead"><strong>' + escapeHtml(rotulo(dominante)) + '</strong> — ' +
        p0(dominante.contribuicao) + ' dos ' + finalPct + ' vieram daqui.</p>' +
        (dominante.detalhe ? '<p class="fx-just">' + escapeHtml(dominante.detalhe) + '</p>' : '') +
        '</div>';
    body.innerHTML = conta + decisao + decisivo;
}
function setFusionSummary(result) {
    const confidence = result ? formatFusionPercent(result.confiabilidade) : "--";
    const level = result ? formatFusionLevel(result.nivel) : "--";
    const calculatedAt = result?.calculado_em ? "Calculado em " + formatDate(result.calculado_em) : "Cálculo indisponível";
    document.querySelectorAll(".data-fusion-confidence").forEach((element) => { element.textContent = confidence; });
    document.querySelectorAll(".data-fusion-level").forEach((element) => { element.textContent = result ? level + " · " + confidence : level; });
    document.querySelectorAll(".data-fusion-calculated-at").forEach((element) => { element.textContent = calculatedAt; });
    document.querySelectorAll("[data-action='recalculate-fusion']").forEach((button) => { button.disabled = !result || selectedEventId == null; });
}
function renderFusionResult(result, eventoTipo) {
    const containers = document.querySelectorAll("#fusion-breakdown, #fusion-breakdown-panel");
    setFusionSummary(result);
    const html = result.componentes.map((component) => {
        const pct = Math.round(component.pontuacao * 100);
        const equation = formatFusionEquation(component, eventoTipo);
        const detail = component.detalhe || "Não informada pela API";
        return '<article class="fusion-item">' +
            '<div class="fusion-row"><span class="fusion-component-icon" data-component="' + escapeHtml(component.nome) + '"></span>' +
            '<span class="fusion-name">' + escapeHtml(fusionComponentLabel(component.nome, eventoTipo)) + '</span>' +
            '<span class="fusion-score">' + formatFusionPercent(component.pontuacao, 0) + '</span>' +
            '<span class="fusion-weight">Peso ' + formatFusionPercent(component.peso, 0) + '</span>' +
            '<span class="fusion-value">' + formatFusionPercent(component.contribuicao) + '</span></div>' +
            '<p class="fusion-equation" title="' + escapeHtml(equation) + '">' + escapeHtml(equation) + '</p>' +
            '<div class="fusion-track"><div class="fusion-fill" style="width:' + pct + '%"></div></div>' +
            '<p class="fusion-detail" title="' + escapeHtml(detail) + '"><strong>Justificativa:</strong> ' + escapeHtml(detail) + '</p>' +
            '</article>';
    }).join("");
    containers.forEach((container) => { container.innerHTML = html || '<p class="fusion-empty">A API não retornou componentes para este evento.</p>'; });
    document.querySelectorAll(".fusion-final-track i").forEach((bar) => {
        bar.style.width = Math.max(0, Math.min(100, Math.round(result.confiabilidade * 100))) + "%";
    });
    renderFusionExplain(result, eventoTipo);
}
async function loadFusionBreakdown(eventId) {
    const containers = document.querySelectorAll("#fusion-breakdown, #fusion-breakdown-panel");
    setFusionLoadingState();
    try {
        const eventoTipo = loadedEvents.find((e) => e.id === eventId)?.tipo;
        renderFusionResult(await fetchOperationalData("/fusion/eventos/" + eventId + "/confiabilidade"), eventoTipo);
    }
    catch {
        setFusionSummary(null);
        containers.forEach((container) => { container.innerHTML = '<p class="fusion-empty">Não foi possível carregar o cálculo da API.</p>'; });
        const explain = document.getElementById("fusion-explain");
        if (explain)
            explain.hidden = true;
    }
}
function formatFusionLevel(level) {
    const map = { alta: "alta", media: "média", baixa: "baixa" };
    return map[level] || level;
}
async function recalculateFusion(eventId) {
    setFusionLoadingState();
    try {
        const response = await apiFetch("/fusion/eventos/" + eventId + "/recalcular", { method: "POST" });
        if (!response.ok)
            throw new Error("API retornou " + response.status);
        const eventoTipo = loadedEvents.find((e) => e.id === eventId)?.tipo;
        renderFusionResult(await response.json(), eventoTipo);
    }
    catch {
        setFusionSummary(null);
        document.querySelectorAll("#fusion-breakdown, #fusion-breakdown-panel").forEach((container) => { container.innerHTML = '<p class="fusion-empty">Não foi possível recalcular pela API.</p>'; });
        const explain = document.getElementById("fusion-explain");
        if (explain)
            explain.hidden = true;
    }
}
function initFusionControls() {
    document.querySelectorAll("[data-action='recalculate-fusion']").forEach((button) => {
        button.addEventListener("click", () => { if (selectedEventId != null)
            void recalculateFusion(selectedEventId); });
        button.disabled = true;
    });
}
function updateLastUpdate() {
    const element = byId("ultima-atualizacao");
    const now = formatClock(new Date());
    lastUpdateLabel = now;
    element.textContent = "Sinc. " + now;
}
function renderRailPanel(key) {
    const section = RAIL_SECTIONS.find((s) => s.key === key);
    if (!section)
        return;
    byId("rail-panel-title").textContent = section.title;
    byId("rail-panel-items").innerHTML = section.items.map((item) => '<button class="rail-item' + (activeView === item.view ? " active" : "") + '" data-view="' + item.view + '">' +
        '<span class="rail-item-icon">' + item.svg + '</span>' +
        '<span class="rail-item-label">' + item.label + '</span>' +
        '</button>').join("");
    document.querySelectorAll("#rail-panel-items .rail-item").forEach((el) => {
        el.addEventListener("click", () => {
            switchView(el.dataset.view);
            closeRailPanel();
        });
    });
}
function openRailPanel(key) {
    const panel = byId("rail-panel");
    if (railPanelOpen && panel.dataset.section === key)
        return;
    railPanelOpen = true;
    renderRailPanel(key);
    panel.hidden = false;
    panel.dataset.section = key;
    panel.classList.remove("rail-panel-leave");
    panel.classList.add("rail-panel-open");
    setRailButtonActive(key);
}
function closeRailPanel() {
    if (!railPanelOpen)
        return;
    railPanelOpen = false;
    const panel = byId("rail-panel");
    panel.classList.remove("rail-panel-open");
    panel.classList.add("rail-panel-leave");
    window.setTimeout(() => {
        if (!railPanelOpen)
            panel.hidden = true;
    }, 180);
    setRailButtonActive(activeView);
}
function toggleRightPanel() {
    const panel = byId("right-panel");
    const btn = document.getElementById("btn-toggle-right");
    rightPanelOpen = !rightPanelOpen;
    if (rightPanelOpen && leftPanelOpen) {
        leftPanelOpen = false;
        byId("sidebar-shell").classList.remove("open");
        byId("btn-toggle-left").classList.remove("on");
    }
    panel.classList.toggle("open", rightPanelOpen);
    btn?.classList.toggle("on", rightPanelOpen);
}
function toggleLeftPanel() {
    const panel = byId("sidebar-shell");
    const btn = byId("btn-toggle-left");
    leftPanelOpen = !leftPanelOpen;
    if (leftPanelOpen && rightPanelOpen) {
        rightPanelOpen = false;
        byId("right-panel").classList.remove("open");
        document.getElementById("btn-toggle-right")?.classList.remove("on");
    }
    panel.classList.toggle("open", leftPanelOpen);
    btn.classList.toggle("on", leftPanelOpen);
}
function updateClock() {
    const el = byId("topbar-clock");
    if (el) {
        el.textContent = formatClock(new Date());
    }
    const date = document.getElementById("topbar-date");
    if (date) {
        date.textContent = new Intl.DateTimeFormat("pt-BR", { day: "2-digit", month: "2-digit", year: "numeric" }).format(new Date());
    }
}
function logSessionActivity(kind, message, eventId, severity) {
    const duplicate = sessionActivity.find((entry) => entry.kind === kind && entry.message === message && Date.now() - entry.timestamp < 60000);
    if (duplicate) {
        duplicate.timestamp = Date.now();
        sessionActivity.sort((a, b) => b.timestamp - a.timestamp);
        renderRightPanelActivity();
        return;
    }
    sessionActivity.unshift({ kind, message, timestamp: Date.now(), eventId, severity });
    if (sessionActivity.length > MAX_SESSION_ACTIVITY)
        sessionActivity.length = MAX_SESSION_ACTIVITY;
    renderRightPanelActivity();
}
/* ============================================================
   RIGHT PANEL — Alerts
   ============================================================ */
function bindRightPanelEventCards(container) {
    container.querySelectorAll(".rp-alert-card[data-event-id]").forEach((card) => {
        card.addEventListener("click", () => {
            const id = Number(card.dataset.eventId);
            if (!id)
                return;
            if (loadedEvents.some((event) => event.id === id)) {
                selectEvent(id);
                return;
            }
            void loadEvents().then(() => {
                if (loadedEvents.some((event) => event.id === id))
                    selectEvent(id);
            });
        });
    });
}
async function loadRightPanelAlerts() {
    const container = byId("right-panel-alerts");
    if (!container)
        return;
    container.innerHTML = '<div class="rp-loading"><div class="skeleton skeleton-block"></div><div class="skeleton skeleton-block"></div></div>';
    try {
        const all = await fetchOperationalData("/notificacoes?limite=50");
        const relevant = all.filter((n) => (n.status === "pendente" || n.status === "enviada") &&
            loadedEvents.some((event) => event.id === n.evento_id));
        const alertItems = relevant.map((notif) => ({
            notif, event: loadedEvents.find((event) => event.id === notif.evento_id),
        }));
        if (!alertItems.length) {
            const observations = loadedEvents.filter((event) => event.tipo === "observacao_visual" && event.status === "em_analise");
            if (!observations.length) {
                container.innerHTML = '<div class="right-panel-empty"><span>Nenhum alerta confirmado</span><p class="rp-empty-hint">Detecções YOLO aparecem como observações até validação operacional.</p></div>';
                return;
            }
            container.innerHTML = observations.slice(0, 3).map((event) => {
                const sevStyle = severityStyle(event.severidade);
                const location = [event.localizacao?.endereco || event.localizacao?.bairro, event.regiao?.nome].filter(Boolean).join(" · ") || "Localização não informada";
                return '<button type="button" class="rp-alert-card rp-observation-card" data-event-id="' + event.id + '" style="--alert-color:#f59e0b">' +
                    '<span class="rp-alert-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="3"/><path d="M12 2v2m0 16v2M2 12h2m16 0h2"/></svg></span>' +
                    '<span class="rp-alert-body"><span class="rp-alert-kicker">OBSERVAÇÃO YOLO · NÃO É INCIDENTE CONFIRMADO</span>' +
                    '<span class="rp-alert-head"><span class="rp-alert-title">' + escapeHtml(event.titulo) + '</span><span class="rp-alert-sev" style="background:' + sevStyle.color + '">' + escapeHtml(sevStyle.label) + '</span></span>' +
                    '<span class="rp-alert-location">' + escapeHtml(location) + '</span>' +
                    '<span class="rp-alert-meta"><span class="rp-alert-category">Observação visual</span><span class="rp-alert-status rp-status-analysis">Em análise</span></span></span></button>';
            }).join("") +
                (connectionMode === "ws" || connectionMode === "sse" ?
                    '<div class="rp-alert-card rp-system-card" style="--alert-color:#20c8e5"><span class="rp-alert-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M5 12.5a10 10 0 0114 0M8 15.5a6 6 0 018 0M11 18.5a2 2 0 012 0"/></svg></span><span class="rp-alert-body"><span class="rp-alert-kicker rp-system-kicker">SISTEMA EM TEMPO REAL</span><span class="rp-alert-head"><span class="rp-alert-title">Canal operacional conectado</span></span><span class="rp-alert-location">' + escapeHtml(connectionMode === "ws" ? "WebSocket autenticado" : "SSE conectado") + '</span><span class="rp-alert-meta"><span class="rp-alert-category">Telemetria</span><span class="rp-alert-status">Online</span></span></span></div>' : '') +
                (cvDetectorAvailable ?
                    '<div class="rp-alert-card rp-system-card" style="--alert-color:#25d77d"><span class="rp-alert-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M4 8h16v10H4zM8 4v4m8-4v4M8 13h.01M12 13h.01M16 13h.01"/></svg></span><span class="rp-alert-body"><span class="rp-alert-kicker rp-system-kicker">VISÃO COMPUTACIONAL</span><span class="rp-alert-head"><span class="rp-alert-title">YOLO pronto para inferência</span></span><span class="rp-alert-location">Modelo validado pelo backend</span><span class="rp-alert-meta"><span class="rp-alert-category">Motor de IA</span><span class="rp-alert-status">Disponível</span></span></span></div>' : '') +
                '<div class="rp-alert-card rp-system-card" style="--alert-color:#2eaa5a"><span class="rp-alert-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M4 5h16v14H4zM8 9h8M8 13h5"/><path d="M16 16l2 2 3-4"/></svg></span><span class="rp-alert-body"><span class="rp-alert-kicker rp-system-kicker">FONTE OPERACIONAL</span><span class="rp-alert-head"><span class="rp-alert-title">API de eventos operacional</span></span><span class="rp-alert-location">Dados autenticados recebidos</span><span class="rp-alert-meta"><span class="rp-alert-category">Backend MotSP</span><span class="rp-alert-status">Online</span></span></span></div>';
            bindRightPanelEventCards(container);
            return;
        }
        container.innerHTML = alertItems.slice(0, 5).map(({ notif, event }) => {
            const sevStyle = event ? severityStyle(event.severidade) : null;
            const sevBadge = sevStyle
                ? '<span class="rp-alert-sev" style="background:' + sevStyle.color + '">' + escapeHtml(sevStyle.label) + '</span>'
                : '<span class="rp-alert-sev rp-alert-sev-unknown">Não informada</span>';
            const time = formatDate(notif.criado_em);
            const statusClass = notif.status === "lida" ? " rp-read" : (notif.status === "falha" ? " rp-fail" : "");
            const category = event?.tipo || notif.canal || "Não informada";
            const location = [event?.localizacao?.endereco || event?.localizacao?.bairro, event?.regiao?.nome].filter(Boolean).join(" · ") || "Localização não informada";
            const iconSource = (event?.tipo || notif.titulo || "").toLocaleLowerCase("pt-BR");
            const icon = /alag|enchente|chuva/.test(iconSource)
                ? '<path d="M4 13c1.3 1.4 3 1.4 4.3 0 1.3-1.4 3-1.4 4.3 0 1.3 1.4 3 1.4 4.3 0M4 18c1.3 1.4 3 1.4 4.3 0 1.3-1.4 3-1.4 4.3 0 1.3 1.4 3 1.4 4.3 0M12 4v5"/>'
                : /transito|congestion|via|carro/.test(iconSource)
                    ? '<path d="M5 16l1-6h12l1 6M4 16h16v3H4zM7.5 13h.01M16.5 13h.01M7 19v1M17 19v1"/>'
                    : '<path d="M12 4l8 15H4L12 4zM12 10v4m0 2h.01"/>';
            return '<button type="button" class="rp-alert-card' + statusClass + (notif.evento_id ? '" data-event-id="' + notif.evento_id : "") + '" style="--alert-color:' + (sevStyle?.color || "var(--gx-light)") + '">' +
                '<span class="rp-alert-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">' + icon + '</svg></span>' +
                '<span class="rp-alert-body">' +
                '<span class="rp-alert-head"><span class="rp-alert-title">' + escapeHtml(notif.titulo) + '</span>' + sevBadge + '</span>' +
                '<span class="rp-alert-location">' + escapeHtml(location) + '</span>' +
                '<span class="rp-alert-meta"><span class="rp-alert-category">' + escapeHtml(formatStatus(category)) + '</span>' +
                (time ? '<span class="rp-alert-time" title="' + escapeHtml(time) + '">' + time + '</span>' : '') +
                '<span class="rp-alert-status">' + escapeHtml(formatStatus(notif.status)) + '</span></span>' +
                '</span></button>';
        }).join("");
        bindRightPanelEventCards(container);
    }
    catch {
        container.innerHTML = '<div class="right-panel-empty rp-error">' +
            '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="10"/><path d="M12 8v4M12 16h.01"/></svg>' +
            '<span>Erro ao carregar alertas</span>' +
            '<button class="rp-retry" data-action="retry-alerts">Tentar novamente</button>' +
            '</div>';
        container.querySelector("[data-action='retry-alerts']")?.addEventListener("click", () => loadRightPanelAlerts());
    }
}
/* ============================================================
   RIGHT PANEL — Evidence
   ============================================================ */
async function loadEventEvidence(eventId) {
    const container = byId("right-panel-evidence");
    if (!container)
        return;
    container.innerHTML = '<div class="rp-loading"><div class="skeleton skeleton-block"></div><div class="skeleton skeleton-circle"></div></div>';
    try {
        const all = await fetchOperationalData("/evidencias?limite=200");
        const eventEvidences = all.filter((e) => e.evento_id === eventId);
        if (!eventEvidences.length) {
            byId("evidence-live-confidence").textContent = "--";
            container.innerHTML = '<div class="right-panel-empty">' +
                '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7z"/><circle cx="12" cy="12" r="3"/></svg>' +
                '<span>Nenhuma evidência visual para este evento</span>' +
                '<p class="rp-empty-hint">A evidência de IA integra o Data Fusion para gerar o score de confiabilidade.</p>' +
                '</div>';
            return;
        }
        const primaryConfidence = Number(eventEvidences[0]?.confianca);
        byId("evidence-live-confidence").textContent = Number.isFinite(primaryConfidence) ? Math.round(primaryConfidence * 100) + "%" : "Verificado";
        for (const objectUrl of evidenceObjectUrls)
            URL.revokeObjectURL(objectUrl);
        evidenceObjectUrls.clear();
        const prepared = await Promise.all(eventEvidences.map(async (ev) => {
            if (ev.url_externa)
                return { ev, imageSrc: ev.url_externa };
            if (!ev.caminho_arquivo)
                return { ev, imageSrc: "" };
            const response = await apiFetch("/evidencias/arquivo/" + encodeURIComponent(ev.caminho_arquivo));
            if (!response.ok)
                return { ev, imageSrc: "" };
            const objectUrl = URL.createObjectURL(await response.blob());
            evidenceObjectUrls.add(objectUrl);
            return { ev, imageSrc: objectUrl };
        }));
        container.innerHTML = prepared.map(({ ev, imageSrc }) => {
            const hasImage = !!imageSrc;
            const confPct = ev.confianca != null ? Math.round(Number(ev.confianca) * 100) : null;
            const time = formatDate(ev.capturado_em);
            const cameraId = typeof ev.metadados?.camera_id === "string" || typeof ev.metadados?.camera_id === "number" ? String(ev.metadados.camera_id) : "";
            const cameraLocal = typeof ev.metadados?.camera_local === "string" ? ev.metadados.camera_local : "";
            const cameraLabel = [cameraId ? "Câmera CET-SP " + cameraId : "", cameraLocal].filter(Boolean).join(" · ");
            const verified = ev.metadados?.validado_no_servidor === true;
            if (verified)
                logSessionActivity("sincronizacao", "Evidência da câmera CET-SP validada", eventId);
            return '<div class="rp-evidence-card">' +
                (cameraLabel || verified ? '<div class="rp-camera-head"><span>' + escapeHtml(cameraLabel || "Evidência visual") + '</span>' + (verified ? '<strong>VERIFICADO</strong>' : '') + '</div>' : '') +
                (hasImage ? '<button type="button" class="rp-evidence-img rp-evidence-expand" data-evidence-image="' + escapeHtml(imageSrc) + '" data-evidence-alt="Evidência ' + escapeHtml(ev.tipo) + '" aria-label="Ampliar evidência visual"><img src="' + escapeHtml(imageSrc) + '" alt="Evidência visual" loading="lazy" onerror="this.parentElement.innerHTML=\'<span class=rp-img-fallback>Imagem indisponível</span>\'"></button>' : '<div class="rp-evidence-img"><span class="rp-img-fallback">Sem imagem disponível</span></div>') +
                '<div class="rp-evidence-toolbar"><button type="button" class="rp-evidence-open" data-evidence-image="' + escapeHtml(imageSrc) + '" data-evidence-alt="Evidência ' + escapeHtml(ev.tipo) + '">Ampliar</button><button type="button" class="rp-evidence-details">Ver detalhes</button></div>' +
                '<div class="rp-evidence-info">' +
                '<div class="rp-evidence-row"><span class="rp-evidence-label">Tipo</span><span class="rp-evidence-val">' + escapeHtml(formatStatus(ev.tipo)) + '</span></div>' +
                (ev.modelo_ia ? '<div class="rp-evidence-row"><span class="rp-evidence-label">Modelo</span><span class="rp-evidence-val">' + escapeHtml(ev.modelo_ia) + '</span></div>' : '') +
                (ev.classe_detectada ? '<div class="rp-evidence-row"><span class="rp-evidence-label">Classe</span><span class="rp-evidence-val rp-evidence-class">' + escapeHtml(formatStatus(ev.classe_detectada)) + '</span></div>' : '') +
                (confPct != null ? '<div class="rp-evidence-row"><span class="rp-evidence-label">Confiança</span><span class="rp-evidence-val">' + confPct + '%</span></div>' : '') +
                (time ? '<div class="rp-evidence-row"><span class="rp-evidence-label">Capturado</span><span class="rp-evidence-val">' + time + '</span></div>' : '') +
                '</div>' +
                '</div>';
        }).join("") +
            '<p class="rp-evidence-disclaimer">' +
            '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="12" height="12"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/></svg>' +
            'A evidência de IA integra o Data Fusion para o cálculo de confiabilidade.' +
            '</p>';
        container.querySelectorAll(".rp-evidence-expand").forEach((button) => {
            button.addEventListener("click", () => openEvidenceViewer(button.dataset.evidenceImage || "", button.dataset.evidenceAlt || "Evidência visual"));
        });
        container.querySelectorAll(".rp-evidence-open").forEach((button) => {
            button.addEventListener("click", () => openEvidenceViewer(button.dataset.evidenceImage || "", button.dataset.evidenceAlt || "Evidência visual"));
        });
        container.querySelectorAll(".rp-evidence-details").forEach((button) => {
            button.addEventListener("click", () => openEventDetail(eventId));
        });
    }
    catch {
        container.innerHTML = '<div class="right-panel-empty rp-error">' +
            '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="10"/><path d="M12 8v4M12 16h.01"/></svg>' +
            '<span>Erro ao carregar evidências</span><button class="rp-retry" data-action="retry-evidence">Tentar novamente</button>' +
            '</div>';
        container.querySelector("[data-action='retry-evidence']")?.addEventListener("click", () => loadEventEvidence(eventId));
    }
}
function openEvidenceViewer(src, alt) {
    if (!src)
        return;
    const viewer = byId("evidence-viewer");
    const image = byId("evidence-viewer-image");
    image.src = src;
    image.alt = alt;
    viewer.hidden = false;
    byId("evidence-viewer-close").focus();
}
function initEvidenceViewer() {
    const viewer = byId("evidence-viewer");
    const close = () => { viewer.hidden = true; byId("evidence-viewer-image").removeAttribute("src"); };
    byId("evidence-viewer-close").addEventListener("click", close);
    viewer.addEventListener("click", (event) => { if (event.target === viewer)
        close(); });
    document.addEventListener("keydown", (event) => { if (event.key === "Escape" && !viewer.hidden)
        close(); });
}
function clearEventEvidence() {
    const container = byId("right-panel-evidence");
    if (!container)
        return;
    for (const objectUrl of evidenceObjectUrls)
        URL.revokeObjectURL(objectUrl);
    evidenceObjectUrls.clear();
    byId("evidence-live-confidence").textContent = "--";
    container.innerHTML = '<div class="right-panel-empty">' +
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7z"/><circle cx="12" cy="12" r="3"/></svg>' +
        '<span>Selecione um evento para ver evidências</span>' +
        '<p class="rp-empty-hint">A evidência de IA integra o Data Fusion para gerar o score de confiabilidade.</p>' +
        '</div>';
}
/* ============================================================
   RIGHT PANEL — Session Activity
   ============================================================ */
function renderRightPanelActivity() {
    const container = byId("right-panel-activity");
    if (!container)
        return;
    if (!sessionActivity.length) {
        container.innerHTML = '<div class="right-panel-empty">' +
            '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>' +
            '<span>Sem atividade registrada</span></div>';
        return;
    }
    container.innerHTML = sessionActivity.slice(0, 15).map((entry) => {
        const time = formatTime(new Date(entry.timestamp).toISOString());
        const icons = {
            evento_criado: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><path d="M12 5v14M5 12h14"/></svg>',
            evento_atualizado: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><path d="M23 4v6h-6"/><path d="M1 20v-6h6"/></svg>',
            notificacao: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><path d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6 6 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5"/></svg>',
            sincronizacao: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><path d="M1 4v6h6"/><path d="M23 20v-6h-6"/></svg>',
        };
        const icon = icons[entry.kind] || icons.sincronizacao;
        return '<div class="rp-activity-item">' +
            '<span class="rp-activity-icon">' + icon + '</span>' +
            '<span class="rp-activity-msg" title="' + escapeHtml(entry.message) + '">' + escapeHtml(entry.message) + '</span>' +
            '<span class="rp-activity-time">' + time + '</span>' +
            '</div>';
    }).join("");
}
function setRailButtonActive(key) {
    document.querySelectorAll(".rail-btn").forEach((btn) => {
        btn.classList.toggle("active", btn.dataset.rail === key);
    });
}
function initRail() {
    // A barra de ícones foi esvaziada; a navegação será reconstruída.
    // Mantém apenas o atalho "Ver todos" do painel de alertas à direita.
    byId("btn-view-alerts")?.addEventListener("click", () => switchView("alertas"));
}
function switchView(key) {
    activeView = key;
    document.querySelectorAll(".view").forEach((view) => {
        view.hidden = view.id !== "view-" + key;
        view.classList.toggle("view-active", view.id === "view-" + key);
    });
    const railKey = VIEW_TO_RAIL[key];
    setRailButtonActive(railKey);
    if (railPanelOpen)
        renderRailPanel(railKey);
    if (key === "regioes")
        void loadRegions();
    if (key === "fontes")
        void loadSources();
    if (key === "alertas")
        void loadNotifications();
    if (key === "fusao") {
        const active = loadedEvents.find((e) => e.id === selectedEventId) || loadedEvents[0];
        if (active)
            void loadFusionBreakdown(active.id);
    }
}
async function loadRegions() {
    const list = byId("lista-regioes");
    try {
        trainingRegions = await fetchJson("/regioes?ativo=true&limite=200");
        byId("contagem-regioes").textContent = String(trainingRegions.length);
        if (!trainingRegions.length) {
            list.innerHTML = '<li class="empty-state">Nenhuma região monitorada.</li>';
            return;
        }
        list.innerHTML = trainingRegions.map((region) => '<li class="info-card"><div class="info-card-head"><h3>' + escapeHtml(region.nome) + '</h3>' +
            (region.codigo ? '<span class="code-pill">' + escapeHtml(region.codigo) + '</span>' : '') + '</div>' +
            (region.descricao ? '<p class="event-description">' + escapeHtml(region.descricao) + '</p>' : '') +
            '</li>').join("");
    }
    catch {
        list.innerHTML = '<li class="error-state">Não foi possível carregar as regiões.</li>';
    }
}
async function loadSources() {
    const list = byId("lista-fontes");
    try {
        dataSources = await fetchJson("/fontes?ativo=true&limite=200");
        byId("contagem-fontes").textContent = String(dataSources.length);
        if (!dataSources.length) {
            list.innerHTML = '<li class="empty-state">Nenhuma fonte cadastrada.</li>';
            return;
        }
        list.innerHTML = dataSources.map((source) => '<li class="info-card"><div class="info-card-head"><h3>' + escapeHtml(source.nome) + '</h3>' +
            '<span class="source-type">' + escapeHtml(source.tipo) + '</span></div>' +
            (source.descricao ? '<p class="event-description">' + escapeHtml(source.descricao) + '</p>' : '') +
            (source.endpoint ? '<p class="event-meta"><span>' + escapeHtml(source.endpoint) + '</span></p>' : '') +
            '</li>').join("");
    }
    catch {
        list.innerHTML = '<li class="error-state">Não foi possível carregar as fontes.</li>';
    }
}
async function loadNotifications() {
    const list = byId("lista-notificacoes");
    try {
        notifications = await fetchJson("/notificacoes?status=pendente&limite=200");
        byId("contagem-notificacoes").textContent = String(notifications.length);
        if (!notifications.length) {
            list.innerHTML = '<li class="empty-state">Nenhuma notificação pendente.</li>';
            return;
        }
        list.innerHTML = notifications.map((notification) => {
            const statusClass = notification.status === "lida" ? "notif-read" : "";
            return '<li class="info-card notif ' + statusClass + '">' +
                '<div class="info-card-head"><h3>' + escapeHtml(notification.titulo) + '</h3>' +
                '<span class="source-type">' + escapeHtml(notification.canal) + '</span></div>' +
                '<p class="event-description">' + escapeHtml(notification.mensagem) + '</p>' +
                '<p class="event-meta"><span>' + escapeHtml(notification.status) + '</span>' +
                (notification.criado_em ? '<span>' + formatDate(notification.criado_em) + '</span>' : '') +
                '</p></li>';
        }).join("");
    }
    catch {
        list.innerHTML = '<li class="error-state">Não foi possível carregar as notificações.</li>';
    }
}
async function loadEvents() {
    try {
        setApiStatus(true, "Sincronizando");
        showLoading("lista-eventos", "Carregando eventos...");
        loadedEvents = await fetchEvents();
        seedActivityFromEvents(loadedEvents);
        updateMetrics(loadedEvents);
        applyMarkers(!selectedEventId);
        renderEventList(loadedEvents);
        const ongoingId = selectedEventId && !loadedEvents.some((e) => e.id === selectedEventId) ? null : selectedEventId;
        const target = loadedEvents.find((e) => e.id === ongoingId) || (ongoingId ? null : (loadedEvents.find(isEventVisible) || loadedEvents[0] || null));
        selectedEventId = target?.id || null;
        renderSelectedEvent(target || null);
        if (target)
            highlightListItem(target.id);
        updateLastUpdate();
        setApiStatus(true, "Conectado");
        refreshFeeds();
        logSessionActivity("sincronizacao", "API operacional");
        logSessionActivity("sincronizacao", "Sincronização concluída — " + loadedEvents.length + (loadedEvents.length === 1 ? " evento" : " eventos"));
        if (!cvDetectorAvailable)
            void cvLoadStatus();
        void loadRightPanelAlerts();
        if (selectedEventId) {
            loadEventEvidence(selectedEventId);
        }
        else {
            clearEventEvidence();
        }
        renderRightPanelActivity();
    }
    catch (error) {
        console.error(error);
        setApiStatus(false, "API indisponível");
        loadedEvents = [];
        updateMetrics([]);
        applyMarkers(false);
        renderEventList([]);
        renderSelectedEvent(null);
        showError("Não foi possível carregar eventos da API. Verifique se o backend está rodando em " + window.CONFIG.API_BASE_URL);
    }
}
function refreshFeeds() {
    void loadRegions();
    void loadSources();
    void loadNotifications();
}
function mapStyles() {
    return [
        { featureType: "poi", stylers: [{ visibility: "off" }] },
        { featureType: "transit", stylers: [{ visibility: "off" }] },
        { elementType: "geometry", stylers: [{ color: "#1a1f25" }] },
        { featureType: "road", elementType: "geometry", stylers: [{ color: "#252b33" }] },
        { featureType: "water", elementType: "geometry", stylers: [{ color: "#0d1117" }] },
        { elementType: "labels.text.fill", stylers: [{ color: "#8a9098" }] },
        { elementType: "labels.text.stroke", stylers: [{ color: "#0d1117" }] },
    ];
}
function initMapa() {
    if (appInitialized)
        return;
    appInitialized = true;
    byId("topbar-map-search")?.addEventListener("click", () => {
        byId("map-search")?.focus();
    });
    const toggleLeftBtn = byId("btn-toggle-left");
    if (toggleLeftBtn) {
        toggleLeftBtn.hidden = false;
        toggleLeftBtn.addEventListener("click", toggleLeftPanel);
    }
    initEvidencePanelDock();
    if (!window.L) {
        const mapaDiv = byId("mapa");
        mapaDiv.innerHTML = '<div class="map-fallback">' +
            '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M12 21s-6-5.2-6-10a6 6 0 1112 0c0 4.8-6 10-6 10z"/><circle cx="12" cy="11" r="2"/></svg>' +
            '<span class="map-fallback-text">Mapa indisponível</span>' +
            '<span class="map-fallback-sub">O painel continua disponível sem a camada cartográfica.</span>' +
            '</div>';
        renderSeverityFilters();
        initRail();
        initComputerVision();
        initYoloTester();
        initIncidentComposer();
        initEvidenceViewer();
        initFusionControls();
        initEventDetailDrawer();
        byId("btn-atualizar").addEventListener("click", loadEvents);
        byId("filtro-status").addEventListener("change", loadEvents);
        const toggleRightBtn = byId("btn-toggle-right");
        if (toggleRightBtn) {
            toggleRightBtn.hidden = false;
            toggleRightBtn.addEventListener("click", toggleRightPanel);
        }
        const closeRightBtn = byId("btn-close-right");
        if (closeRightBtn) {
            closeRightBtn.addEventListener("click", toggleRightPanel);
        }
        const configBtn = byId("btn-config");
        if (configBtn) {
            configBtn.addEventListener("click", () => switchView("config"));
        }
        updateClock();
        window.setInterval(updateClock, 1000);
        void loadLiveWeather();
        void loadLiveAirQuality();
        window.setInterval(() => { void loadLiveWeather(); void loadLiveAirQuality(); }, 300000);
        loadEvents();
        connectWebSocket();
        return;
    }
    map = window.L.map("mapa", {
        zoomControl: false,
        attributionControl: true,
        closePopupOnClick: true,
    }).setView([window.CONFIG.MAP_CENTER.lat, window.CONFIG.MAP_CENTER.lng], window.CONFIG.MAP_ZOOM);
    window.L.tileLayer.wms("https://wms.geosampa.prefeitura.sp.gov.br/geoserver/geoportal/wms", {
        layers: "MapaBase_Politico",
        format: "image/png",
        transparent: true,
        version: "1.1.1",
        attribution: '&copy; <a href="https://geosampa.prefeitura.sp.gov.br/">GeoSampa</a> — PMSP',
        maxZoom: 19,
        minZoom: 10,
    }).addTo(map);
    window.L.control.zoom({ position: "bottomright" }).addTo(map);
    map.on("zoomend", scheduleMarkerRefresh);
    map.on("popupopen", (popupEvent) => {
        openInfoWindow = popupEvent.popup;
        const popupElement = popupEvent.popup?.getElement?.();
        if (!popupElement)
            return;
        const action = popupElement.querySelector(".gx-event-popup-action");
        action?.addEventListener("click", () => {
            const eventId = Number(action.dataset.eventId);
            if (Number.isInteger(eventId))
                focusSelectedEventDetails(eventId);
        }, { once: true });
        window.requestAnimationFrame(() => action?.focus());
    });
    map.on("popupclose", (popupEvent) => {
        const shouldReturnFocus = popupReturnFocusToMarker;
        popupReturnFocusToMarker = true;
        openInfoWindow = null;
        if (!shouldReturnFocus)
            return;
        const markerElement = popupEvent.popup?._source?.getElement?.();
        window.requestAnimationFrame(() => markerElement?.focus());
    });
    document.addEventListener("keydown", (keyboardEvent) => {
        if (keyboardEvent.key !== "Escape" || !openInfoWindow || !map)
            return;
        map.closePopup(openInfoWindow);
    });
    byId("map-recenter")?.addEventListener("click", () => {
        map?.setView([window.CONFIG.MAP_CENTER.lat, window.CONFIG.MAP_CENTER.lng], Math.max(window.CONFIG.MAP_ZOOM, 12));
    });
    renderSeverityFilters();
    initRail();
    initComputerVision();
    initYoloTester();
    initIncidentComposer();
    initEvidenceViewer();
    initFusionControls();
    initEventDetailDrawer();
    byId("btn-atualizar").addEventListener("click", loadEvents);
    byId("filtro-status").addEventListener("change", loadEvents);
    const toggleRightBtn = byId("btn-toggle-right");
    if (toggleRightBtn) {
        toggleRightBtn.hidden = false;
        toggleRightBtn.addEventListener("click", toggleRightPanel);
    }
    const closeRightBtn = byId("btn-close-right");
    if (closeRightBtn) {
        closeRightBtn.addEventListener("click", toggleRightPanel);
    }
    const configBtn = byId("btn-config");
    if (configBtn) {
        configBtn.addEventListener("click", () => switchView("config"));
    }
    updateClock();
    window.setInterval(updateClock, 1000);
    void loadLiveWeather();
    void loadLiveAirQuality();
    window.setInterval(() => { void loadLiveWeather(); void loadLiveAirQuality(); }, 300000);
    const searchInput = byId("busca-eventos");
    const clearButton = byId("busca-limpar");
    const applySearch = () => {
        searchTerm = searchInput.value.trim().toLowerCase();
        clearButton.hidden = !searchInput.value;
        if (searchRenderTimer)
            clearTimeout(searchRenderTimer);
        searchRenderTimer = setTimeout(() => {
            applyMarkers(false);
            renderEventList(loadedEvents);
        }, 120);
    };
    searchInput.addEventListener("input", applySearch);
    searchInput.addEventListener("keydown", (event) => {
        if (event.key === "Escape") {
            searchInput.value = "";
            applySearch();
            searchInput.blur();
        }
    });
    clearButton.addEventListener("click", () => {
        searchInput.value = "";
        applySearch();
        searchInput.focus();
    });
    const mapSearch = byId("map-search");
    if (mapSearch) {
        mapSearch.addEventListener("input", () => {
            searchTerm = mapSearch.value.trim().toLowerCase();
            const mainSearch = byId("busca-eventos");
            if (mainSearch)
                mainSearch.value = mapSearch.value;
            const clearBtn = byId("busca-limpar");
            if (clearBtn)
                clearBtn.hidden = !mapSearch.value;
            applySearch();
        });
        mapSearch.addEventListener("keydown", (event) => {
            if (event.key === "Escape") {
                mapSearch.value = "";
                searchTerm = "";
                const mainSearch = byId("busca-eventos");
                if (mainSearch)
                    mainSearch.value = "";
                const clearBtn = byId("busca-limpar");
                if (clearBtn)
                    clearBtn.hidden = true;
                applySearch();
                mapSearch.blur();
            }
        });
    }
    loadEvents();
    connectWebSocket();
}
window.initMapa = initMapa;
loadGoogleMaps();
