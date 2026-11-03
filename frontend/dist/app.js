import { atingeLimiarAtivo, formatFusionPercent, fusionComponentLabel } from "./fusion-format.js";
import { RAIO_BUSCA_M, pontosNoRaio, formatarDistancia, nomeCurtoDoLocal, resultadoNaCapital, urlBuscaEndereco } from "./busca-local.js";
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
let selectedMarkerId = null;
let selectedEventId = null;
let markerRefreshTimer = null;
const markersById = new Map();
const transientMarkerLayers = new Set();
let rightPanelOpen = false;
let leftPanelOpen = false;
const MARKER_CLUSTER_THRESHOLD = 120;
let buscaAtual = null;
let buscaCamada = null;
let ultimaBuscaEm = 0;
const buscaCache = new Map();
let camerasMonitoradas = null;
let connectionMode = "disconnected";
let wsConnection = null;
let sseConnection = null;
let pollingTimer = null;
let reconnectAttempt = 0;
const WS_MAX_RECONNECT = 8;
const WS_BASE_DELAY_MS = 1000;
const POLLING_INTERVAL_MS = 15000;
// De tempos em tempos a lista é conferida com a API, mesmo com o tempo real
// funcionando. Assim, se alguma mensagem se perder, nenhum evento velho fica na tela.
const RESYNC_INTERVAL_MS = 120000;
let pingTimer = null;
let resyncTimer = null;
let appInitialized = false;
const evidenceObjectUrls = new Set();
const byId = (id) => document.getElementById(id);
async function apiFetch(path, init = {}) {
    const request = { ...init, headers: new Headers(init.headers) };
    try {
        return await fetch(window.CONFIG.API_BASE_URL + path, request);
    }
    catch (error) {
        const method = String(init.method || "GET").toUpperCase();
        if (method !== "GET" && method !== "HEAD")
            throw error;
        await new Promise((resolve) => window.setTimeout(resolve, 250));
        return await fetch(window.CONFIG.API_BASE_URL + path, request);
    }
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
   TEMPO REAL: tenta WebSocket, depois SSE e por último consulta periódica
   ============================================================ */
function updateConnectionStatus() {
    const el = byId("status-conexao");
    if (!el)
        return;
    // Para quem usa o painel tanto faz se é WebSocket ou SSE, os dois são tempo real.
    const labels = {
        ws: "Sistema ao vivo",
        sse: "Sistema ao vivo",
        polling: "Sistema em polling",
        disconnected: "Desconectado",
    };
    const classes = {
        ws: "conn-ws",
        sse: "conn-sse",
        polling: "conn-polling",
        disconnected: "conn-off",
    };
    const titles = {
        ws: "Atualizações em tempo real via WebSocket",
        sse: "Atualizações em tempo real via Server-Sent Events",
        polling: "Consultando a API periodicamente",
        disconnected: "Sem conexão com o backend",
    };
    el.textContent = labels[connectionMode];
    el.title = titles[connectionMode];
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
    if (resyncTimer) {
        clearInterval(resyncTimer);
        resyncTimer = null;
    }
}
function connectWebSocket() {
    clearAllConnections();
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
    const startHeartbeat = () => {
        connectionMode = "ws";
        reconnectAttempt = 0;
        updateConnectionStatus();
        // Enquanto a conexão esteve fora, eventos podem ter mudado sem a tela saber.
        void resyncEvents();
        startResyncTimer();
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
            if (msg.tipo === "pronto") {
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
    sseConnection.onopen = () => {
        connectionMode = "sse";
        reconnectAttempt = 0;
        updateConnectionStatus();
        void resyncEvents();
        startResyncTimer();
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
function startResyncTimer() {
    if (resyncTimer)
        clearInterval(resyncTimer);
    resyncTimer = setInterval(() => { void resyncEvents(); }, RESYNC_INTERVAL_MS);
}
/** Deixa a lista igual à da API sem piscar a tela e sem trocar o evento selecionado. */
async function resyncEvents() {
    try {
        const remotos = await fetchEvents();
        const idsRemotos = new Set(remotos.map((event) => event.id));
        const sumiram = loadedEvents.filter((event) => !idsRemotos.has(event.id)).length;
        if (!sumiram && remotos.length === loadedEvents.length)
            return;
        loadedEvents = remotos;
        updateMetrics(loadedEvents);
        applyMarkers(false);
        if (selectedEventId != null && !idsRemotos.has(selectedEventId)) {
            selectedEventId = null;
            clearEventEvidence();
            renderSelectedEvent(null);
        }
        updateLastUpdate();
    }
    catch {
        // Se falhar, não faz nada: o aviso de API fora do ar já aparece em outro lugar.
    }
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
            updateMetrics(loadedEvents);
            updateMarker(evento);
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
            updateMetrics(loadedEvents);
            updateMarker(atualizado);
            if (selectedEventId === atualizado.id) {
                renderSelectedEvent(atualizado);
            }
            break;
        }
        case "evento_removido": {
            const id = Number(dados.id);
            loadedEvents = loadedEvents.filter((ev) => ev.id !== id);
            updateMetrics(loadedEvents);
            removeMarker(id);
            if (selectedEventId === id) {
                selectedEventId = null;
                clearEventEvidence();
                renderSelectedEvent(null);
            }
            break;
        }
    }
}
function updateMarker(evento) {
    // Se o evento não passa no filtro atual, ele não aparece no mapa.
    if (!isEventVisible(evento)) {
        removeMarker(evento.id);
        return;
    }
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
/** Cor do marcador no mapa segundo o status operacional do evento. */
function statusColor(status) {
    switch (String(status || "").toLowerCase()) {
        case "ativo": return "#2EAA5A"; // verde
        case "em_analise": return "#E6A817"; // amarelo
        default: return "#E6A817";
    }
}
/** Ícone de carro usado nos eventos de trânsito. */
const GLYPH_CARRO = '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M18.92 6.01C18.72 5.42 18.16 5 17.5 5h-11c-.66 0-1.21.42-1.42 1.01L3 12v8c0 .55.45 1 1 1h1c.55 0 1-.45 1-1v-1h12v1c0 .55.45 1 1 1h1c.55 0 1-.45 1-1v-8l-2.08-5.99zM6.5 16c-.83 0-1.5-.67-1.5-1.5S5.67 13 6.5 13s1.5.67 1.5 1.5S7.33 16 6.5 16zm11 0c-.83 0-1.5-.67-1.5-1.5s.67-1.5 1.5-1.5 1.5.67 1.5 1.5-.67 1.5-1.5 1.5zM5 11l1.5-4.5h11L19 11H5z"/></svg>';
function isEventoTransito(event) {
    const value = (event.tipo + " " + event.titulo).toLowerCase();
    return event.tipo === "transito" || value.includes("trâns") || value.includes("trans") || value.includes("via");
}
function setApiStatus(ok, message) {
    const element = byId("status-api");
    element.textContent = message;
    element.classList.toggle("ok", ok);
    element.classList.toggle("erro", !ok);
}
/* ============================================================
   CELULAR EM PÉ: a evidência visual passa do painel direito
   para o esquerdo. Com o celular deitado ela volta ao lugar.
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
/** Baixa os eventos de todos os status. O filtro é aplicado aqui no navegador,
 * assim os totais continuam certos mesmo com o filtro ligado. */
async function fetchEvents() {
    const params = new URLSearchParams({ limite: "200" });
    const response = await apiFetch("/eventos?" + params.toString());
    if (!response.ok)
        throw new Error("API retornou " + response.status);
    return response.json();
}
/** Faz um GET na API e dá erro se a resposta não for de sucesso. */
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
function currentStatusFilter() {
    return byId("filtro-status")?.value || "";
}
function matchesStatusFilter(event) {
    const statusFiltro = currentStatusFilter();
    return !statusFiltro || event.status === statusFiltro;
}
/** Mantém o filtro do celular e o do computador sempre iguais. */
function syncStatusFilterButtons() {
    const current = currentStatusFilter();
    document.querySelectorAll("#filtro-status-mobile button[data-status]").forEach((btn) => {
        const active = (btn.dataset.status || "") === current;
        btn.classList.toggle("active", active);
        btn.setAttribute("aria-selected", String(active));
    });
}
function initStatusFilter() {
    const select = byId("filtro-status");
    select.addEventListener("change", () => { syncStatusFilterButtons(); void loadEvents(); });
    document.querySelectorAll("#filtro-status-mobile button[data-status]").forEach((btn) => {
        btn.addEventListener("click", () => {
            select.value = btn.dataset.status || "";
            syncStatusFilterButtons();
            void loadEvents();
        });
    });
    syncStatusFilterButtons();
}
function isEventVisible(event) {
    return matchesStatusFilter(event) && dentroDaBusca(event);
}
function dentroDaBusca(event) {
    return !buscaAtual || pontosNoRaio([event], buscaAtual).length > 0;
}
function clearMarkers() {
    deselectCurrentMarker();
    transientMarkerLayers.forEach((marker) => marker.remove());
    transientMarkerLayers.clear();
    markersById.clear();
}
function markerGlyph(event) {
    const value = (event.tipo + " " + event.titulo).toLowerCase();
    if (isEventoTransito(event))
        return GLYPH_CARRO;
    if (value.includes("alag") || value.includes("chuva"))
        return "≋";
    if (value.includes("câmera") || value.includes("camera"))
        return "◉";
    if (value.includes("bloque"))
        return "▰";
    return "!";
}
function markerIcon(event, style, selected = false) {
    const critical = style.label === "Crítica";
    // A cor do marcador mostra o status: verde é ativo e amarelo é em análise.
    // O selecionado tem a mesma cor, só que maior e com brilho.
    const markerColor = statusColor(event.status);
    const hue = markerColor;
    const transito = isEventoTransito(event);
    return window.L.divIcon({
        className: "gx-marker-shell" + (selected ? " is-selected" : ""),
        html: '<span class="gx-map-marker' + (critical ? " is-critical" : "") + (transito ? " has-svg-glyph" : "") + '" style="--marker-color:' + markerColor + ';--severity-color:' + hue + '"><i>' + markerGlyph(event) + '</i></span>',
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
    const confidence = formatConfidence(event.confianca);
    const source = event.fonte?.nome || "";
    const detectedAt = event.detectado_em ? formatDate(event.detectado_em) : "Horário não informado";
    const popupId = "gx-popup-" + event.id;
    const hue = statusColor(event.status);
    return '<article class="gx-event-popup" role="dialog" aria-modal="false" aria-labelledby="' + popupId + '-title">' +
        (confidence ? '<div class="gx-event-popup-head"><span class="gx-event-popup-confidence" style="color:' + hue + '">' + confidence + ' confiança</span></div>' : '') +
        '<h3 id="' + popupId + '-title">' + escapeHtml(event.titulo) + '</h3>' +
        (event.descricao ? '<p class="gx-event-popup-description">' + escapeHtml(event.descricao) + '</p>' : '') +
        '<dl class="gx-event-popup-meta">' +
        '<div><dt>Fonte</dt><dd>' + escapeHtml(source || "Não informada") + '</dd></div>' +
        '<div><dt>Horário</dt><dd>' + escapeHtml(detectedAt) + '</dd></div>' +
        '</dl>' +
        '</article>';
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
        transito: "Trânsito",
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
function selectEvent(id, openPopup = false) {
    selectedEventId = id;
    const event = loadedEvents.find((e) => e.id === id);
    renderSelectedEvent(event || null);
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
}
function renderSelectedEvent(event) {
    const selectedContainer = byId("evento-selecionado");
    const title = byId("selected-title");
    const statusPill = byId("selected-status-pill");
    const meta = byId("selected-event-meta");
    const time = byId("selected-time");
    const source = byId("selected-source");
    const confidenceWrap = byId("confidence-circle-wrap");
    const confidenceValue = byId("confidence-circle-value");
    const confidenceRing = byId("confidence-fill-ring");
    deselectCurrentMarker();
    if (!event) {
        delete selectedContainer.dataset.type;
        title.textContent = "Selecione um evento";
        statusPill.textContent = "--";
        statusPill.className = "status-pill";
        meta.hidden = true;
        confidenceWrap.hidden = true;
        hideFusionExplain();
        return;
    }
    selectedContainer.dataset.type = event.tipo;
    title.textContent = event.titulo;
    const status = String(event.status || "").toLowerCase();
    statusPill.textContent = formatStatus(event.status);
    statusPill.className = "status-pill" +
        (status === "ativo" ? " status-ativo" : status === "em_analise" ? " status-analise" : "");
    meta.hidden = false;
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
    loadFusionBreakdown(event.id);
    highlightMarker(event.id);
}
function updateMetrics(events) {
    const noMapa = events.filter(isEventVisible);
    animateKpi(byId("kpi-ativos"), String(noMapa.length));
    animateKpi(byId("kpi-status-ativos"), String(events.filter((e) => e.status === "ativo").length));
    animateKpi(byId("kpi-status-analise"), String(events.filter((e) => e.status === "em_analise").length));
    renderBuscaResultado();
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
}
function scheduleMarkerRefresh() {
    if (markerRefreshTimer)
        clearTimeout(markerRefreshTimer);
    markerRefreshTimer = setTimeout(() => applyMarkers(false), 80);
}
// Pesos padrão do Data Fusion, iguais aos de data_fusion/fusion.py. Só são
// usados se a API não mandar os pesos dela.
const PESO_BASE_FUSAO = { ia: 4 / 7, contexto: 3 / 7 };
/** Painel no mapa com a conta do Data Fusion, o resultado e o que mais pesou. */
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
    const pesoBase = (c) => c.peso_base || PESO_BASE_FUSAO[c.nome] || c.peso;
    const finalPct = p0(result.confiabilidade);
    levelBadge.textContent = formatFusionLevel(result.nivel) + " · " + finalPct;
    levelBadge.className = "fusion-explain-level nivel-" + result.nivel;
    // --- A conta ---
    // Quando o peso do contexto muda, isso aparece numa frase separada, para a
    // lista de pesos padrão continuar somando 100%.
    const ajustados = usados.filter((c) => PESO_BASE_FUSAO[c.nome] != null
        && Math.abs(pesoBase(c) - PESO_BASE_FUSAO[c.nome]) > 0.005);
    const ajuste = ajustados.map((c) => escapeHtml(rotulo(c)) + " " + p0(PESO_BASE_FUSAO[c.nome]) + "&rarr;" + p0(pesoBase(c)) +
        (pesoBase(c) > PESO_BASE_FUSAO[c.nome] ? " (fontes concordam)" : " (fontes divergem)")).join(", ");
    const redistribuido = foraDeUso.length > 0
        && usados.some((c) => Math.abs(c.peso - pesoBase(c)) > 0.005);
    let pesos;
    if (redistribuido) {
        const somaFora = foraDeUso.reduce((soma, c) => soma + pesoBase(c), 0);
        const nomesFora = foraDeUso.map(rotulo).join(" e ");
        pesos = '<p class="fx-weights">Base: ' +
            result.componentes.map((c) => escapeHtml(rotulo(c)) + " " + p0(PESO_BASE_FUSAO[c.nome] ?? pesoBase(c))).join(", ") + '. ' +
            (ajuste ? 'Ajuste por concordância: ' + ajuste + '. ' : '') +
            escapeHtml(nomesFora) + (foraDeUso.length > 1 ? " não pontuaram" : " não pontuou") +
            ', então ' + p0(somaFora) + ' de peso ' + (foraDeUso.length > 1 ? "delas foram rateados" : "dela foi rateado") +
            ' entre as demais &rarr; ' +
            usados.map((c) => escapeHtml(rotulo(c)) + " " + p0(pesoBase(c)) + "&rarr;" + p0(c.peso)).join(", ") + '.</p>';
    }
    else {
        pesos = '<p class="fx-weights">Pesos: ' +
            usados.map((c) => escapeHtml(rotulo(c)) + " " + p0(c.peso)).join(", ") + '.' +
            (ajuste ? ' Ajuste por concordância: ' + ajuste + '.' : '') + '</p>';
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
    const limiar = typeof result.limiar_ativo === "number" ? result.limiar_ativo : 0.80;
    const limiarPct = p0(limiar);
    const veredito = atingeLimiarAtivo(result.confiabilidade, limiar)
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
        '<p class="fx-lead"><strong>' + escapeHtml(rotulo(dominante)) + '</strong>: ' +
        p0(dominante.contribuicao) + ' dos ' + finalPct + ' vieram daqui.</p>' +
        (dominante.detalhe ? '<p class="fx-just">' + escapeHtml(dominante.detalhe) + '</p>' : '') +
        '</div>';
    body.innerHTML = conta + decisao + decisivo;
}
function hideFusionExplain() {
    const explain = document.getElementById("fusion-explain");
    if (explain)
        explain.hidden = true;
}
async function loadFusionBreakdown(eventId) {
    hideFusionExplain();
    try {
        const eventoTipo = loadedEvents.find((e) => e.id === eventId)?.tipo;
        renderFusionExplain(await fetchOperationalData("/fusion/eventos/" + eventId + "/confiabilidade"), eventoTipo);
    }
    catch {
        hideFusionExplain();
    }
}
function formatFusionLevel(level) {
    const map = { alta: "alta", media: "média", baixa: "baixa" };
    return map[level] || level;
}
function updateLastUpdate() {
    const element = byId("ultima-atualizacao");
    element.textContent = "Sinc. " + formatClock(new Date());
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
/* ============================================================
   PAINEL DIREITO: evidência visual
   ============================================================ */
async function loadEventEvidence(eventId) {
    const container = byId("right-panel-evidence");
    if (!container)
        return;
    container.innerHTML = '<div class="rp-loading"><div class="skeleton skeleton-block"></div><div class="skeleton skeleton-circle"></div></div>';
    try {
        const eventEvidences = await fetchOperationalData("/evidencias?evento_id=" + eventId);
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
            return '<div class="rp-evidence-card">' +
                (cameraLabel || verified ? '<div class="rp-camera-head"><span>' + escapeHtml(cameraLabel || "Evidência visual") + '</span>' + (verified ? '<strong>VERIFICADO</strong>' : '') + '</div>' : '') +
                (hasImage ? '<button type="button" class="rp-evidence-img rp-evidence-expand" data-evidence-image="' + escapeHtml(imageSrc) + '" data-evidence-alt="Evidência ' + escapeHtml(ev.tipo) + '" aria-label="Ampliar evidência visual"><img src="' + escapeHtml(imageSrc) + '" alt="Evidência visual" loading="lazy" onerror="this.parentElement.innerHTML=\'<span class=rp-img-fallback>Imagem indisponível</span>\'"></button>' : '<div class="rp-evidence-img"><span class="rp-img-fallback">Sem imagem disponível</span></div>') +
                '<div class="rp-evidence-toolbar"><button type="button" class="rp-evidence-open" data-evidence-image="' + escapeHtml(imageSrc) + '" data-evidence-alt="Evidência ' + escapeHtml(ev.tipo) + '">Ampliar</button></div>' +
                '<div class="rp-evidence-info">' +
                '<div class="rp-evidence-row rp-evidence-row--tipo"><span class="rp-evidence-label">Tipo</span><span class="rp-evidence-val">' + escapeHtml(formatStatus(ev.tipo)) + '</span></div>' +
                (ev.modelo_ia ? '<div class="rp-evidence-row rp-evidence-row--modelo"><span class="rp-evidence-label">Modelo</span><span class="rp-evidence-val">' + escapeHtml(ev.modelo_ia) + '</span></div>' : '') +
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
async function loadEvents() {
    try {
        setApiStatus(true, "Sincronizando");
        loadedEvents = await fetchEvents();
        updateMetrics(loadedEvents);
        // Com uma busca ligada o mapa fica parado no círculo da busca.
        applyMarkers(!selectedEventId && !buscaAtual);
        const ongoingId = selectedEventId && !loadedEvents.some((e) => e.id === selectedEventId) ? null : selectedEventId;
        const target = loadedEvents.find((e) => e.id === ongoingId) || (ongoingId ? null : (loadedEvents.find(isEventVisible) || (buscaAtual ? null : loadedEvents[0]) || null));
        selectedEventId = target?.id || null;
        renderSelectedEvent(target || null);
        updateLastUpdate();
        setApiStatus(true, "Conectado");
        if (selectedEventId) {
            loadEventEvidence(selectedEventId);
        }
        else {
            clearEventEvidence();
        }
    }
    catch (error) {
        console.error(error);
        setApiStatus(false, "API indisponível");
        loadedEvents = [];
        updateMetrics([]);
        applyMarkers(false);
        renderSelectedEvent(null);
    }
}
/* ============================================================
   BUSCA POR RUA: eventos a até 1,5 km do local digitado
   ============================================================ */
function initBusca() {
    const form = byId("busca-form");
    const input = byId("busca-texto");
    const limpar = byId("busca-limpar");
    form.addEventListener("submit", (submitEvent) => {
        submitEvent.preventDefault();
        void buscarEndereco(input.value);
    });
    input.addEventListener("input", () => { limpar.hidden = !input.value && !buscaAtual; });
    input.addEventListener("keydown", (keyEvent) => { if (keyEvent.key === "Escape")
        limparBusca(); });
    limpar.addEventListener("click", () => { limparBusca(); input.focus(); });
    byId("busca-resultado").addEventListener("click", (clickEvent) => {
        const botao = clickEvent.target.closest("button[data-evento-id]");
        if (botao)
            selectEvent(Number(botao.dataset.eventoId), true);
    });
    fetchOperationalData("/deteccao/cameras")
        .then((lista) => { camerasMonitoradas = lista; renderBuscaResultado(); })
        .catch((error) => console.error(error));
}
async function buscarEndereco(texto) {
    const chave = texto.trim().toLocaleLowerCase("pt-BR");
    if (chave.length < 3) {
        setBuscaMensagem("Digite pelo menos 3 letras do nome da rua.", true);
        return;
    }
    const botao = byId("busca-enviar");
    botao.disabled = true;
    setBuscaMensagem("Buscando…");
    try {
        let local = buscaCache.get(chave);
        if (local === undefined) {
            // O Nominatim aceita no máximo uma consulta por segundo.
            const espera = ultimaBuscaEm + 1100 - Date.now();
            if (espera > 0)
                await new Promise((resolve) => window.setTimeout(resolve, espera));
            ultimaBuscaEm = Date.now();
            const resposta = await fetch(urlBuscaEndereco(texto));
            if (!resposta.ok)
                throw new Error("Nominatim retornou " + resposta.status);
            const achado = resultadoNaCapital(await resposta.json());
            local = achado
                ? { latitude: Number(achado.lat), longitude: Number(achado.lon), nome: nomeCurtoDoLocal(achado.display_name) }
                : null;
            buscaCache.set(chave, local);
        }
        if (!local) {
            desfazerBusca();
            setBuscaMensagem("Não encontramos esse endereço em São Paulo. Tente incluir o número ou o bairro.", true);
            return;
        }
        aplicarBusca(local);
    }
    catch (error) {
        console.error(error);
        desfazerBusca();
        setBuscaMensagem("A busca de endereços está fora do ar agora. Tente de novo em alguns instantes.", true);
    }
    finally {
        botao.disabled = false;
    }
}
function aplicarBusca(local) {
    buscaAtual = local;
    byId("busca-limpar").hidden = false;
    desenharAreaBusca();
    // Se o evento selecionado ficou fora do círculo, ele deixa de ser mostrado.
    if (selectedEventId != null && !loadedEvents.some((e) => e.id === selectedEventId && isEventVisible(e))) {
        selectedEventId = null;
        clearEventEvidence();
        renderSelectedEvent(null);
    }
    applyMarkers(false);
    updateMetrics(loadedEvents);
}
/** Tira o círculo e volta a mostrar todos os eventos, sem mexer no texto digitado. */
function desfazerBusca() {
    if (!buscaAtual)
        return;
    buscaAtual = null;
    desenharAreaBusca();
    applyMarkers(false);
    updateMetrics(loadedEvents);
}
function limparBusca() {
    desfazerBusca();
    byId("busca-texto").value = "";
    byId("busca-limpar").hidden = true;
    byId("busca-resultado").hidden = true;
}
function desenharAreaBusca() {
    buscaCamada?.remove();
    buscaCamada = null;
    if (!buscaAtual || !map || !window.L)
        return;
    const centro = [buscaAtual.latitude, buscaAtual.longitude];
    buscaCamada = window.L.layerGroup([
        window.L.circle(centro, { radius: RAIO_BUSCA_M, color: "#FF8A00", weight: 2, fillColor: "#FF8A00", fillOpacity: 0.08, interactive: false }),
        window.L.circleMarker(centro, { radius: 5, color: "#ffffff", weight: 2, fillColor: "#FF5500", fillOpacity: 1, interactive: false }),
    ]).addTo(map);
    map.fitBounds(window.L.latLng(centro).toBounds(RAIO_BUSCA_M * 2), { padding: [40, 40] });
}
function setBuscaMensagem(texto, erro = false) {
    const painel = byId("busca-resultado");
    painel.hidden = false;
    painel.innerHTML = '<p class="map-search-message' + (erro ? " is-error" : "") + '">' + escapeHtml(texto) + "</p>";
}
const ICONE_CAMERA = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M23 7l-7 5 7 5V7z"/><rect x="1" y="5" width="15" height="14" rx="2"/></svg>';
function listaCameras(cameras) {
    return '<ul class="map-search-cameras">' + cameras.map(({ ponto, distancia }) => "<li>" + ICONE_CAMERA + '<span class="map-search-camera-name">' + escapeHtml(ponto.nome) + "</span>" +
        '<span class="map-search-meta">' + formatarDistancia(distancia) + "</span></li>").join("") + "</ul>";
}
/** Lista os eventos dentro do círculo. Roda de novo sempre que a lista de eventos muda. */
function renderBuscaResultado() {
    if (!buscaAtual)
        return;
    const raio = formatarDistancia(RAIO_BUSCA_M);
    const local = escapeHtml(buscaAtual.nome);
    const proximos = pontosNoRaio(loadedEvents.filter(matchesStatusFilter), buscaAtual);
    const camerasPerto = camerasMonitoradas ? pontosNoRaio(camerasMonitoradas, buscaAtual) : null;
    let html;
    if (camerasPerto && !camerasPerto.length && !proximos.length) {
        html = '<p class="map-search-message is-warning"><strong>Local sem cobertura.</strong> Nenhuma câmera monitorada pelo MotSP fica a até ' +
            raio + " de <strong>" + local + "</strong>, então o sistema não tem como detectar eventos aqui.</p>";
    }
    else if (!proximos.length) {
        const filtro = currentStatusFilter();
        const quais = filtro ? formatStatus(filtro).toLocaleLowerCase("pt-BR") : "ativo ou em análise";
        html = '<p class="map-search-message">Nenhum evento ' + quais + (camerasPerto ? " nas câmeras monitoradas" : "") +
            " a até " + raio + " de <strong>" + local + "</strong>" + (camerasPerto ? ":" : ".") + "</p>" +
            (camerasPerto ? listaCameras(camerasPerto) : "");
    }
    else {
        const total = proximos.length === 1 ? "1 evento" : proximos.length + " eventos";
        const cobertura = camerasPerto?.length
            ? '<p class="map-search-coverage">' + ICONE_CAMERA + (camerasPerto.length === 1 ? "1 câmera monitorada" : camerasPerto.length + " câmeras monitoradas") + " nessa área</p>"
            : "";
        html = '<p class="map-search-message"><strong>' + total + "</strong> a até " + raio + " de <strong>" + local + "</strong></p>" + cobertura +
            '<ul class="map-search-list">' + proximos.map(({ ponto: evento, distancia }) => {
            // A detecção grava o nome da câmera como endereço do evento.
            const camera = evento.localizacao?.endereco;
            return '<li><button type="button" data-evento-id="' + evento.id + '" title="' + escapeHtml(evento.titulo + (camera ? " · " + camera : "")) + '">' +
                '<span class="map-search-dot" style="background:' + statusColor(evento.status) + '"></span>' +
                '<span class="map-search-title">' + escapeHtml(evento.titulo) + "</span>" +
                (camera ? '<span class="map-search-camera">' + ICONE_CAMERA + escapeHtml(camera) + "</span>" : "") +
                '<span class="map-search-meta">' + escapeHtml(formatStatus(evento.status)) + " · " + formatarDistancia(distancia) + "</span>" +
                "</button></li>";
        }).join("") + "</ul>";
    }
    const painel = byId("busca-resultado");
    painel.hidden = false;
    painel.innerHTML = html + '<p class="map-search-credit">Endereços: &copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a></p>';
}
function mostrarMapaIndisponivel() {
    byId("mapa").innerHTML = '<div class="map-fallback">' +
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M12 21s-6-5.2-6-10a6 6 0 1112 0c0 4.8-6 10-6 10z"/><circle cx="12" cy="11" r="2"/></svg>' +
        '<span class="map-fallback-text">Mapa indisponível</span>' +
        '<span class="map-fallback-sub">O painel continua disponível sem a camada cartográfica.</span>' +
        '</div>';
}
function criarMapa() {
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
    // No iPhone a barra de endereço muda de tamanho depois que a página carrega,
    // e o mapa precisa ser recalculado para os botões não sumirem da tela.
    const remedirMapa = () => { if (map)
        map.invalidateSize({ pan: false }); };
    window.visualViewport?.addEventListener("resize", remedirMapa);
    window.addEventListener("orientationchange", () => { window.setTimeout(remedirMapa, 250); });
    window.setTimeout(remedirMapa, 500);
    map.on("popupopen", (popupEvent) => {
        openInfoWindow = popupEvent.popup;
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
}
function initMapa() {
    if (appInitialized)
        return;
    appInitialized = true;
    // O mapa sempre abre mostrando todos os status, mesmo que o navegador
    // lembre o filtro anterior.
    const filtroStatusInicial = byId("filtro-status");
    if (filtroStatusInicial)
        filtroStatusInicial.value = "";
    const toggleLeftBtn = byId("btn-toggle-left");
    if (toggleLeftBtn) {
        toggleLeftBtn.hidden = false;
        toggleLeftBtn.addEventListener("click", toggleLeftPanel);
    }
    initEvidencePanelDock();
    if (window.L)
        criarMapa();
    else
        mostrarMapaIndisponivel();
    initEvidenceViewer();
    byId("btn-atualizar").addEventListener("click", loadEvents);
    initStatusFilter();
    initBusca();
    const closeRightBtn = byId("btn-close-right");
    if (closeRightBtn) {
        closeRightBtn.addEventListener("click", toggleRightPanel);
    }
    updateClock();
    window.setInterval(updateClock, 1000);
    void loadLiveWeather();
    void loadLiveAirQuality();
    window.setInterval(() => { void loadLiveWeather(); void loadLiveAirQuality(); }, 300000);
    loadEvents();
    connectWebSocket();
}
initMapa();
