import { atingeLimiarAtivo, formatFusionPercent, fusionComponentLabel, type FusionDisplayComponent } from "./fusion-format.js";

type SeverityKey = "baixa" | "media" | "alta" | "critica";

type SeverityStyle = {
  label: string;
  color: string;
  scale: number;
  zIndex: number;
};

type AppConfig = {
  API_BASE_URL: string;
  MAP_CENTER: { lat: number; lng: number };
  MAP_ZOOM: number;
  REFRESH_INTERVAL_MS: number;
};

type EventLocation = { endereco?: string | null; bairro?: string | null; cidade?: string | null };
type EventRegion = { nome: string };
type EventFonte = { nome: string; tipo: string };

type UrbanEvent = {
  id: number;
  titulo: string;
  descricao?: string | null;
  tipo: string;
  severidade: string;
  status: string;
  latitude: number;
  longitude: number;
  confianca?: number | string | null;
  detectado_em?: string | null;
  localizacao?: EventLocation | null;
  regiao?: EventRegion | null;
  fonte?: EventFonte | null;
};

type FusionResult = { evento_id: number; confiabilidade: number; nivel: string; componentes: FusionDisplayComponent[]; calculado_em: string; limiar_ativo?: number };

type EvidenciaVisual = {
  id: number;
  evento_id: number;
  fonte_id?: number | null;
  tipo: string;
  caminho_arquivo?: string | null;
  url_externa?: string | null;
  modelo_ia?: string | null;
  classe_detectada?: string | null;
  confianca?: number | string | null;
  largura_px?: number | null;
  altura_px?: number | null;
  metadados?: Record<string, unknown> | null;
  capturado_em: string;
  criado_em: string;
};


declare global {
  interface Window {
    CONFIG: AppConfig;
    L: any;
  }
}

const SEVERITIES: Record<SeverityKey, SeverityStyle> = {
  baixa: { label: "Baixa", color: "#22c55e", scale: 10, zIndex: 2 },
  media: { label: "Média", color: "#FFB300", scale: 12, zIndex: 3 },
  alta: { label: "Alta", color: "#FF8A00", scale: 14, zIndex: 4 },
  critica: { label: "Crítica", color: "#FF5500", scale: 16, zIndex: 5 },
};

let map: any = null;
let openInfoWindow: any = null;
let popupReturnFocusToMarker = true;
let loadedEvents: UrbanEvent[] = [];
let selectedMarkerId: number | null = null;
let selectedEventId: number | null = null;
let markerRefreshTimer: ReturnType<typeof setTimeout> | null = null;
const markersById = new Map<number, any>();
const transientMarkerLayers = new Set<any>();
let rightPanelOpen = false;
let leftPanelOpen = false;
const MARKER_CLUSTER_THRESHOLD = 120;

// Real-time connection state
type ConnectionMode = "ws" | "sse" | "polling" | "disconnected";
let connectionMode: ConnectionMode = "disconnected";
let wsConnection: WebSocket | null = null;
let sseConnection: EventSource | null = null;
let pollingTimer: ReturnType<typeof setInterval> | null = null;
let reconnectAttempt = 0;
const WS_MAX_RECONNECT = 8;
const WS_BASE_DELAY_MS = 1000;
const POLLING_INTERVAL_MS = 15000;
// Rede de segurança: mesmo com WS/SSE vivos, reconcilia a lista com a API de
// tempos em tempos. Qualquer mensagem perdida (socket caído entre o create e o
// remove, remoção feita fora do broadcast) deixaria evento fantasma na tela.
const RESYNC_INTERVAL_MS = 120000;
let pingTimer: ReturnType<typeof setInterval> | null = null;
let resyncTimer: ReturnType<typeof setInterval> | null = null;
let appInitialized = false;
const evidenceObjectUrls = new Set<string>();

const byId = <T extends HTMLElement>(id: string): T => document.getElementById(id) as T;

async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const request = { ...init, headers: new Headers(init.headers) };
  try {
    return await fetch(window.CONFIG.API_BASE_URL + path, request);
  } catch (error) {
    const method = String(init.method || "GET").toUpperCase();
    if (method !== "GET" && method !== "HEAD") throw error;
    await new Promise((resolve) => window.setTimeout(resolve, 250));
    return await fetch(window.CONFIG.API_BASE_URL + path, request);
  }
}

function escapeHtml(value: unknown): string {
  if (value == null) return "";
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

function updateConnectionStatus(): void {
  const el = byId("status-conexao");
  if (!el) return;
  // O canal (WebSocket/SSE) fica só na classe CSS e no title: para quem usa
  // o painel a diferença não importa, os dois são tempo real.
  const labels: Record<ConnectionMode, string> = {
    ws: "Sistema ao vivo",
    sse: "Sistema ao vivo",
    polling: "Sistema em polling",
    disconnected: "Desconectado",
  };
  const classes: Record<ConnectionMode, string> = {
    ws: "conn-ws",
    sse: "conn-sse",
    polling: "conn-polling",
    disconnected: "conn-off",
  };
  const titles: Record<ConnectionMode, string> = {
    ws: "Atualizações em tempo real via WebSocket",
    sse: "Atualizações em tempo real via Server-Sent Events",
    polling: "Consultando a API periodicamente",
    disconnected: "Sem conexão com o backend",
  };
  el.textContent = labels[connectionMode];
  el.title = titles[connectionMode];
  el.className = "status-badge " + classes[connectionMode];
}

function clearAllConnections(): void {
  if (wsConnection) { wsConnection.close(); wsConnection = null; }
  if (sseConnection) { sseConnection.close(); sseConnection = null; }
  if (pollingTimer) { clearInterval(pollingTimer); pollingTimer = null; }
  if (pingTimer) { clearInterval(pingTimer); pingTimer = null; }
  if (resyncTimer) { clearInterval(resyncTimer); resyncTimer = null; }
}

function connectWebSocket(): void {
  clearAllConnections();
  const wsUrl = window.CONFIG.API_BASE_URL.replace(/^http/, "ws") + "/ws";
  try {
    wsConnection = new WebSocket(wsUrl);
  } catch {
    connectionMode = "disconnected";
    updateConnectionStatus();
    fallbackToSSE();
    return;
  }

  const startHeartbeat = () => {
    connectionMode = "ws";
    reconnectAttempt = 0;
    updateConnectionStatus();
    // Reconecta ≠ continua de onde parou: enquanto o canal esteve fora, eventos
    // podem ter sido criados e removidos sem a tela saber.
    void resyncEvents();
    startResyncTimer();
    if (pingTimer) clearInterval(pingTimer);
    pingTimer = setInterval(() => {
      if (wsConnection && wsConnection.readyState === WebSocket.OPEN) {
        wsConnection.send(JSON.stringify({ tipo: "ping" }));
      }
    }, 30000);
  };

  wsConnection.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data);
      if (msg.tipo === "pronto") { startHeartbeat(); return; }
      if (msg.tipo === "pong") return;
      handleRealtimeMessage(msg.tipo, msg.dados);
    } catch { /* ignore malformed */ }
  };

  wsConnection.onclose = () => {
    if (pingTimer) { clearInterval(pingTimer); pingTimer = null; }
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

function fallbackToSSE(): void {
  clearAllConnections();
  const url = window.CONFIG.API_BASE_URL + "/events/stream";
  try {
    sseConnection = new EventSource(url);
  } catch {
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

function fallbackToPolling(): void {
  clearAllConnections();
  connectionMode = "polling";
  updateConnectionStatus();
  if (pollingTimer) clearInterval(pollingTimer);
  pollingTimer = setInterval(() => {
    void loadEvents();
  }, POLLING_INTERVAL_MS);
}

function startResyncTimer(): void {
  if (resyncTimer) clearInterval(resyncTimer);
  resyncTimer = setInterval(() => { void resyncEvents(); }, RESYNC_INTERVAL_MS);
}

/** Reconciliação silenciosa com a API: deixa a lista exatamente igual à do
 * backend, sem o "flash" de carregamento do loadEvents e sem trocar o evento
 * selecionado por conta própria. */
async function resyncEvents(): Promise<void> {
  try {
    const remotos = await fetchEvents();
    const idsRemotos = new Set(remotos.map((event) => event.id));
    const sumiram = loadedEvents.filter((event) => !idsRemotos.has(event.id)).length;
    if (!sumiram && remotos.length === loadedEvents.length) return;
    loadedEvents = remotos;
    updateMetrics(loadedEvents);
    applyMarkers(false);
    if (selectedEventId != null && !idsRemotos.has(selectedEventId)) {
      selectedEventId = null;
      clearEventEvidence();
      renderSelectedEvent(null);
    }
    updateLastUpdate();
  } catch {
    // Silencioso de propósito: o canal de tempo real e o polling já sinalizam
    // API indisponível; um resync que falha não deve limpar a tela.
  }
}

function fallbackReconnect(): void {
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

function handleRealtimeMessage(tipo: string, dados: Record<string, unknown>): void {
  switch (tipo) {
    case "evento_criado": {
      const evento = dados as unknown as UrbanEvent;
      if (!loadedEvents.some((e) => e.id === evento.id)) {
        loadedEvents.unshift(evento);
      }
      updateMetrics(loadedEvents);
      updateMarker(evento);
      break;
    }
    case "evento_atualizado": {
      const atualizado = dados as unknown as UrbanEvent;
      const idx = loadedEvents.findIndex((ev) => ev.id === atualizado.id);
      if (idx !== -1) {
        loadedEvents[idx] = { ...loadedEvents[idx], ...atualizado };
      } else {
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

function updateMarker(evento: UrbanEvent): void {
  // Evento que não passa no filtro atual (status/severidade/busca) não pode
  // ganhar marcador só por ter chegado via WebSocket — remove se já existir.
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
  } else {
    createMarker(evento);
  }
}

function removeMarker(id: number): void {
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

function normalizeSeverity(value: string | null | undefined): SeverityKey {
  const key = String(value || "media").toLowerCase().trim();
  return key in SEVERITIES ? (key as SeverityKey) : "media";
}

function severityStyle(value: string): SeverityStyle {
  return SEVERITIES[normalizeSeverity(value)];
}

/** Cor do marcador no mapa segundo o status operacional do evento. */
function statusColor(status: string | null | undefined): string {
  switch (String(status || "").toLowerCase()) {
    case "ativo": return "#2EAA5A";      // verde
    case "em_analise": return "#E6A817"; // amarelo
    default: return "#E6A817";
  }
}

/** Ícone de carro (Material "directions_car") usado em eventos de trânsito. */
const GLYPH_CARRO =
  '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M18.92 6.01C18.72 5.42 18.16 5 17.5 5h-11c-.66 0-1.21.42-1.42 1.01L3 12v8c0 .55.45 1 1 1h1c.55 0 1-.45 1-1v-1h12v1c0 .55.45 1 1 1h1c.55 0 1-.45 1-1v-8l-2.08-5.99zM6.5 16c-.83 0-1.5-.67-1.5-1.5S5.67 13 6.5 13s1.5.67 1.5 1.5S7.33 16 6.5 16zm11 0c-.83 0-1.5-.67-1.5-1.5s.67-1.5 1.5-1.5 1.5.67 1.5 1.5-.67 1.5-1.5 1.5zM5 11l1.5-4.5h11L19 11H5z"/></svg>';

function isEventoTransito(event: UrbanEvent): boolean {
  const value = (event.tipo + " " + event.titulo).toLowerCase();
  return event.tipo === "transito" || value.includes("trâns") || value.includes("trans") || value.includes("via");
}

function setApiStatus(ok: boolean, message: string): void {
  const element = byId("status-api");
  element.textContent = message;
  element.classList.toggle("ok", ok);
  element.classList.toggle("erro", !ok);
}

/* ============================================================
   LAYOUT VERTICAL — no retrato, a "Evidência visual" (bloco do
   painel direito) desce para o painel esquerdo, ocupando o
   espaço da antiga Criticidade. Em paisagem volta ao seu lugar.
   ============================================================ */
function initEvidencePanelDock(): void {
  const dock = document.getElementById("left-evidence-dock");
  const evidence = document.querySelector<HTMLElement>(".section-evidence");
  if (!dock || !evidence) return;
  const homeParent = evidence.parentElement;
  const portrait = window.matchMedia("(orientation: portrait)");
  const apply = (): void => {
    if (portrait.matches) {
      if (evidence.parentElement !== dock) dock.appendChild(evidence);
      dock.hidden = false;
    } else {
      if (homeParent && evidence.parentElement !== homeParent) {
        homeParent.appendChild(evidence);
      }
      dock.hidden = true;
    }
  };
  apply();
  portrait.addEventListener("change", apply);
}

/* ============================================================
   TESTADOR YOLO — barra esquerda: sobe uma imagem e vê o que
   os dois modelos (alagamento + objetos COCO) reconhecem.
   ============================================================ */

type YoloDeteccao = {
  nome: string;
  confianca: number;
  severidade: string;
  tipo: string;
  bbox: [number, number, number, number];
  classe_modelo?: string | null;
};

let ytFile: File | null = null;
let ytObjectUrl: string | null = null;
let ytAnalyzing = false;
let ytMinVeiculos = 8;
const YT_CLASSES_VEICULO = ["veiculo", "motocicleta", "onibus", "caminhao"];

function ytShow(destino: "inicio" | "yolo"): void {
  document.querySelectorAll<HTMLElement>(".view").forEach((v) => {
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

function ytSetFeedback(message: string, tone: "" | "error" | "success" = ""): void {
  const el = byId("yt-feedback");
  el.textContent = message;
  el.className = "yt-feedback" + (tone ? " " + tone : "");
}

function ytClearImage(): void {
  ytFile = null;
  if (ytObjectUrl) { URL.revokeObjectURL(ytObjectUrl); ytObjectUrl = null; }
  byId<HTMLInputElement>("yt-file").value = "";
  byId("yt-preview").hidden = true;
  byId<HTMLImageElement>("yt-image").removeAttribute("src");
  const canvas = byId<HTMLCanvasElement>("yt-overlay");
  canvas.getContext("2d")?.clearRect(0, 0, canvas.width, canvas.height);
  byId("yt-file-label").textContent = "Selecionar imagem";
  byId<HTMLButtonElement>("yt-analyze").disabled = true;
  byId("yt-verdict").hidden = true;
  byId("yt-detections").innerHTML = "";
  ytSetFeedback("Selecione uma imagem para começar.");
}

function ytSetImage(file: File): void {
  if (file.size > 10 * 1024 * 1024) {
    ytSetFeedback("A imagem ultrapassa o limite de 10 MB.", "error");
    return;
  }
  ytFile = file;
  if (ytObjectUrl) URL.revokeObjectURL(ytObjectUrl);
  ytObjectUrl = URL.createObjectURL(file);
  byId<HTMLImageElement>("yt-image").src = ytObjectUrl;
  byId("yt-preview").hidden = false;
  byId("yt-file-label").textContent = file.name;
  byId<HTMLButtonElement>("yt-analyze").disabled = false;
  byId("yt-verdict").hidden = true;
  byId("yt-detections").innerHTML = "";
  ytSetFeedback("Imagem pronta. Clique em “Analisar imagem”.");
}

function ytDrawBoxes(deteccoes: YoloDeteccao[]): void {
  const img = byId<HTMLImageElement>("yt-image");
  const canvas = byId<HTMLCanvasElement>("yt-overlay");
  if (!img.naturalWidth) return;
  canvas.width = img.naturalWidth;
  canvas.height = img.naturalHeight;
  const ctx = canvas.getContext("2d");
  if (!ctx) return;
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

async function ytChamarModelo(rota: string): Promise<YoloDeteccao[]> {
  const form = new FormData();
  form.append("file", ytFile as File);
  // Sem parâmetro de confiança: o servidor aplica o limiar padrão de cada modelo
  // e devolve o que reconheceu, com a confiança de cada caixa.
  const response = await apiFetch(rota, { method: "POST", body: form });
  if (response.status === 503) return []; // modelo indisponível — tratado no resumo
  if (!response.ok) throw new Error("O modelo retornou " + response.status);
  return response.json() as Promise<YoloDeteccao[]>;
}

async function ytAnalisar(): Promise<void> {
  if (!ytFile || ytAnalyzing) return;
  ytAnalyzing = true;
  const botao = byId<HTMLButtonElement>("yt-analyze");
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

    let tone: "danger" | "warn" | "ok" = "ok";
    let titulo = "Nada relevante detectado";
    let detalhe = veiculos.length
      ? veiculos.length + " veículo(s) reconhecido(s) — abaixo do limite de trânsito (" + ytMinVeiculos + ")"
      : "Nenhum objeto ou incidente reconhecido acima do limiar";
    if (alagamentos.length) {
      const maxConf = Math.max(...alagamentos.map((d) => d.confianca));
      tone = "danger";
      titulo = "Alagamento detectado";
      detalhe = alagamentos.length + " região(ões) de água · confiança máx. " + Math.round(maxConf * 100) + "%";
    } else if (veiculos.length >= ytMinVeiculos) {
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
    } else {
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
  } catch (error) {
    ytSetFeedback(error instanceof Error ? error.message : "Falha ao analisar a imagem.", "error");
  } finally {
    ytAnalyzing = false;
    botao.disabled = false;
  }
}

async function ytCarregarStatus(): Promise<void> {
  const badge = byId("yt-model-status");
  try {
    const response = await apiFetch("/deteccao/status");
    if (!response.ok) throw new Error("status indisponível");
    const status = await response.json() as {
      disponivel: boolean;
      incidente?: { disponivel: boolean };
      min_veiculos_transito?: number;
    };
    if (typeof status.min_veiculos_transito === "number") ytMinVeiculos = status.min_veiculos_transito;
    const objOk = status.disponivel;
    const incOk = Boolean(status.incidente?.disponivel);
    badge.textContent = objOk && incOk ? "2 modelos prontos" : objOk || incOk ? "1 de 2 modelos" : "Modelos indisponíveis";
    badge.className = "yt-status " + (objOk && incOk ? "ready" : objOk || incOk ? "partial" : "unavailable");
    if (!incOk) ytSetFeedback("Modelo de alagamento indisponível no servidor — só a detecção de objetos vai responder.", "error");
  } catch {
    badge.textContent = "API indisponível";
    badge.className = "yt-status unavailable";
  }
}

function initYoloTester(): void {
  const railBtn = byId("rail-yolo-teste");
  if (!railBtn) return;
  railBtn.addEventListener("click", () => ytShow("yolo"));
  byId("rail-inicio")?.addEventListener("click", () => ytShow("inicio"));

  const input = byId<HTMLInputElement>("yt-file");
  input.addEventListener("change", () => {
    const file = input.files?.[0];
    if (file) ytSetImage(file);
  });
  byId("yt-clear").addEventListener("click", ytClearImage);
  byId<HTMLButtonElement>("yt-analyze").addEventListener("click", () => { void ytAnalisar(); });
  void ytCarregarStatus();
}

/** Baixa todos os status de uma vez: o filtro Ativos/Em análise é aplicado no
 * cliente (isEventVisible), assim os KPIs mostram o total real de cada status
 * mesmo com o filtro ligado. */
async function fetchEvents(): Promise<UrbanEvent[]> {
  const params = new URLSearchParams({ limite: "200" });
  const response = await apiFetch("/eventos?" + params.toString());
  if (!response.ok) throw new Error("API retornou " + response.status);
  return response.json() as Promise<UrbanEvent[]>;
}

/** GET na API que lança erro em resposta não-2xx. */
async function fetchOperationalData<T>(url: string): Promise<T> {
  const response = await apiFetch(url);
  if (!response.ok) throw new Error("API retornou " + response.status);
  return response.json() as Promise<T>;
}

type LiveWeather = { disponivel: boolean; temperatura_c?: number; precipitacao_mm?: number; vento_kmh?: number; fonte?: string };
type LiveAirQuality = { disponivel: boolean; aqi_us?: number; pm2_5?: number; fonte?: string };

async function loadLiveWeather(): Promise<void> {
  const status = byId("live-source-status");
  try {
    const response = await apiFetch("/fontes/tempo-real/clima");
    const weather = await response.json() as LiveWeather;
    if (!response.ok || !weather.disponivel) throw new Error("fonte indisponível");
    const rain = Number(weather.precipitacao_mm || 0).toFixed(1);
    status.classList.remove("source-offline");
    status.innerHTML = '<span class="weather-copy"><span>Clima ao vivo</span><strong>' +
      Number(weather.temperatura_c || 0).toFixed(0) + '°C · ' + rain + ' mm</strong></span>';
    status.title = "Fonte externa: " + (weather.fonte || "Open-Meteo") + " · vento " + Number(weather.vento_kmh || 0).toFixed(0) + " km/h";
  } catch {
    status.innerHTML = '<span class="weather-copy"><span>Clima ao vivo</span><strong>indisponível</strong></span>';
    status.classList.add("source-offline");
  }
}

async function loadLiveAirQuality(): Promise<void> {
  const status = byId("live-air-status");
  try {
    const response = await apiFetch("/fontes/tempo-real/ar");
    const air = await response.json() as LiveAirQuality;
    if (!response.ok || !air.disponivel) throw new Error("fonte indisponível");
    status.textContent = "Ar ao vivo: AQI " + Math.round(Number(air.aqi_us || 0)) + " · PM2.5 " + Number(air.pm2_5 || 0).toFixed(1) + " μg/m³";
    status.title = "Fonte externa: " + (air.fonte || "Open-Meteo Air Quality");
  } catch {
    status.textContent = "Qualidade do ar: indisponível";
    status.classList.add("source-offline");
  }
}

function formatClock(value: Date): string {
  return value.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function currentStatusFilter(): string {
  return byId<HTMLSelectElement>("filtro-status")?.value || "";
}

function matchesStatusFilter(event: UrbanEvent): boolean {
  const statusFiltro = currentStatusFilter();
  return !statusFiltro || event.status === statusFiltro;
}

/** Sincroniza o controle segmentado do painel lateral (mobile) com o <select>
 * do mapa (desktop); os dois manipulam o mesmo filtro. */
function syncStatusFilterButtons(): void {
  const current = currentStatusFilter();
  document.querySelectorAll<HTMLButtonElement>("#filtro-status-mobile button[data-status]").forEach((btn) => {
    const active = (btn.dataset.status || "") === current;
    btn.classList.toggle("active", active);
    btn.setAttribute("aria-selected", String(active));
  });
}

function initStatusFilter(): void {
  const select = byId<HTMLSelectElement>("filtro-status");
  select.addEventListener("change", () => { syncStatusFilterButtons(); void loadEvents(); });
  document.querySelectorAll<HTMLButtonElement>("#filtro-status-mobile button[data-status]").forEach((btn) => {
    btn.addEventListener("click", () => {
      select.value = btn.dataset.status || "";
      syncStatusFilterButtons();
      void loadEvents();
    });
  });
  syncStatusFilterButtons();
}

function isEventVisible(event: UrbanEvent): boolean {
  return matchesStatusFilter(event);
}

function clearMarkers(): void {
  deselectCurrentMarker();
  transientMarkerLayers.forEach((marker) => marker.remove());
  transientMarkerLayers.clear();
  markersById.clear();
}

function markerGlyph(event: UrbanEvent): string {
  const value = (event.tipo + " " + event.titulo).toLowerCase();
  if (isEventoTransito(event)) return GLYPH_CARRO;
  if (value.includes("alag") || value.includes("chuva")) return "≋";
  if (value.includes("câmera") || value.includes("camera")) return "◉";
  if (value.includes("bloque")) return "▰";
  return "!";
}

function markerIcon(event: UrbanEvent, style: SeverityStyle, selected = false): any {
  const critical = style.label === "Crítica";
  // O marcador passa a comunicar o STATUS (ativo = verde, em análise = amarelo),
  // não mais a criticidade.
  // Selecionado usa a MESMA cor do status (só maior e com brilho), não laranja.
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

function formatDate(value?: string | null): string {
  if (!value) return "";
  return parseApiDate(value).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
}

function parseApiDate(value: string): Date {
  return new Date(/[zZ]|[+-]\d\d:\d\d$/.test(value) ? value : value + "Z");
}

function formatConfidence(value: UrbanEvent["confianca"]): string {
  if (value == null || Number.isNaN(Number(value))) return "";
  return String((Number(value) * 100).toFixed(0)) + "%";
}

function formatDetectadoEm(value?: string | null): string {
  if (!value) return "Sem registro";
  try {
    return parseApiDate(value).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
  } catch {
    return value;
  }
}

function infoWindowContent(event: UrbanEvent): string {
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

function createMarker(event: UrbanEvent): void {
  if (!window.L || !map) return;
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

function createClusterMarkers(events: UrbanEvent[]): void {
  if (!map || !window.L) return;
  const cells = new Map<string, UrbanEvent[]>();
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

function fitMapBounds(events: UrbanEvent[]): void {
  if (!events.length || !map || !window.L) return;
  if (events.length === 1) {
    map.setView([window.CONFIG.MAP_CENTER.lat, window.CONFIG.MAP_CENTER.lng], Math.max(window.CONFIG.MAP_ZOOM, 12));
    return;
  }
  const bounds = window.L.latLngBounds(events.map((event) => [event.latitude, event.longitude]));
  map.fitBounds(bounds, { padding: [42, 42], maxZoom: 16 });
}

function formatStatus(value: string): string {
  const labels: Record<string, string> = {
    em_analise: "Em análise",
    transito: "Trânsito",
  };
  return labels[value.toLocaleLowerCase("pt-BR")] || value.replace(/_/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());
}

function highlightMarker(eventId: number): void {
  deselectCurrentMarker();
  const marker = markersById.get(eventId);
  if (!marker || !map) return;
  selectedMarkerId = eventId;
  const event = loadedEvents.find((e) => e.id === eventId);
  if (!event) return;
  const style = severityStyle(event.severidade);
  marker.setIcon(markerIcon(event, style, true));
  marker.setZIndexOffset(1000);
}

function deselectCurrentMarker(): void {
  if (selectedMarkerId == null) return;
  const marker = markersById.get(selectedMarkerId);
  if (!marker) { selectedMarkerId = null; return; }
  const event = loadedEvents.find((e) => e.id === selectedMarkerId);
  if (event) {
    const style = severityStyle(event.severidade);
    marker.setIcon(markerIcon(event, style));
    marker.setZIndexOffset(0);
  }
  selectedMarkerId = null;
}

function selectEvent(id: number, openPopup = false): void {
  selectedEventId = id;
  const event = loadedEvents.find((e) => e.id === id);
  renderSelectedEvent(event || null);

  if (event) {
    loadEventEvidence(event.id);
  } else {
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

function renderSelectedEvent(event: UrbanEvent | null): void {
  const selectedContainer = byId("evento-selecionado");
  const title = byId("selected-title");
  const statusPill = byId("selected-status-pill");
  const meta = byId("selected-event-meta");
  const time = byId("selected-time");
  const source = byId("selected-source");
  const confidenceWrap = byId("confidence-circle-wrap");
  const confidenceValue = byId("confidence-circle-value");
  const confidenceRing = byId("confidence-fill-ring") as unknown as SVGCircleElement;

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
    if (pct >= 75) confidenceRing.classList.add("good");
    else if (pct >= 40) confidenceRing.classList.add("moderate");
    else confidenceRing.classList.add("poor");
  } else {
    confidenceWrap.hidden = true;
  }

  loadFusionBreakdown(event.id);

  highlightMarker(event.id);
}

function updateMetrics(events: UrbanEvent[]): void {
  const noMapa = events.filter(matchesStatusFilter);
  animateKpi(byId("kpi-ativos"), String(noMapa.length));
  animateKpi(byId("kpi-status-ativos"), String(events.filter((e) => e.status === "ativo").length));
  animateKpi(byId("kpi-status-analise"), String(events.filter((e) => e.status === "em_analise").length));
}

function animateKpi(element: HTMLElement, newValue: string): void {
  if (element.textContent === newValue) return;
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

function applyMarkers(shouldFitBounds = false): void {
  clearMarkers();
  const visible = loadedEvents.filter(isEventVisible);
  const shouldCluster = !!map && visible.length > MARKER_CLUSTER_THRESHOLD && map.getZoom() < 15;
  if (shouldCluster) createClusterMarkers(visible);
  else visible.forEach(createMarker);
  if (shouldFitBounds) fitMapBounds(visible);
  if (selectedEventId != null && visible.some((event) => event.id === selectedEventId)) highlightMarker(selectedEventId);
}

function scheduleMarkerRefresh(): void {
  if (markerRefreshTimer) clearTimeout(markerRefreshTimer);
  markerRefreshTimer = setTimeout(() => applyMarkers(false), 80);
}

// Pesos-base das dimensões da fusão — espelham data_fusion/fusion.py (PESOS).
// Só fallback: a API manda `peso_base` por componente, e o de contexto varia
// com a concordância entre as fontes contextuais. Proporção 4:3.
const PESO_BASE_FUSAO: Record<string, number> = { ia: 4 / 7, contexto: 3 / 7 };

/** Painel no mapa: a conta completa da fusão, o veredito e o dado decisivo. */
function renderFusionExplain(result: FusionResult, eventoTipo?: string): void {
  const panel = document.getElementById("fusion-explain");
  const levelBadge = document.getElementById("fusion-explain-level");
  const body = document.getElementById("fusion-explain-body");
  if (!panel || !levelBadge || !body) return;

  const usados = result.componentes.filter((component) => component.peso > 0);
  const foraDeUso = result.componentes.filter((component) => component.peso <= 0);
  if (!usados.length) { panel.hidden = true; return; }
  panel.hidden = false;

  const p0 = (valor: number): string => formatFusionPercent(valor, 0);
  const rotulo = (c: FusionDisplayComponent): string =>
    c.nome === "ia" ? "IA" : fusionComponentLabel(c.nome, eventoTipo);
  const pesoBase = (c: FusionDisplayComponent): number => c.peso_base || PESO_BASE_FUSAO[c.nome] || c.peso;
  const finalPct = p0(result.confiabilidade);

  levelBadge.textContent = formatFusionLevel(result.nivel) + " · " + finalPct;
  levelBadge.className = "fusion-explain-level nivel-" + result.nivel;

  // --- A conta ---
  // Peso contextual flexionado pela concordância das fontes: vira frase própria
  // para a lista "Base" continuar mostrando os pesos fixos, que somam 100%.
  const ajustados = usados.filter((c) => PESO_BASE_FUSAO[c.nome] != null
    && Math.abs(pesoBase(c) - PESO_BASE_FUSAO[c.nome]) > 0.005);
  const ajuste = ajustados.map((c) => escapeHtml(rotulo(c)) + " " + p0(PESO_BASE_FUSAO[c.nome]) + "&rarr;" + p0(pesoBase(c)) +
    (pesoBase(c) > PESO_BASE_FUSAO[c.nome] ? " (fontes concordam)" : " (fontes divergem)")).join(", ");
  const redistribuido = foraDeUso.length > 0
    && usados.some((c) => Math.abs(c.peso - pesoBase(c)) > 0.005);
  let pesos: string;
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
  } else {
    pesos = '<p class="fx-weights">Pesos: ' +
      usados.map((c) => escapeHtml(rotulo(c)) + " " + p0(c.peso)).join(", ") + '.' +
      (ajuste ? ' Ajuste por concordância: ' + ajuste + '.' : '') + '</p>';
  }

  const linhas = usados.map((c) =>
    '<div class="fx-calc">' +
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
  const limiar = typeof result.limiar_ativo === "number" ? result.limiar_ativo : 0.77;
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
    '<p class="fx-lead"><strong>' + escapeHtml(rotulo(dominante)) + '</strong> — ' +
      p0(dominante.contribuicao) + ' dos ' + finalPct + ' vieram daqui.</p>' +
    (dominante.detalhe ? '<p class="fx-just">' + escapeHtml(dominante.detalhe) + '</p>' : '') +
    '</div>';

  body.innerHTML = conta + decisao + decisivo;
}

function hideFusionExplain(): void {
  const explain = document.getElementById("fusion-explain");
  if (explain) explain.hidden = true;
}

async function loadFusionBreakdown(eventId: number): Promise<void> {
  hideFusionExplain();
  try {
    const eventoTipo = loadedEvents.find((e) => e.id === eventId)?.tipo;
    renderFusionExplain(await fetchOperationalData<FusionResult>("/fusion/eventos/" + eventId + "/confiabilidade"), eventoTipo);
  } catch {
    hideFusionExplain();
  }
}

function formatFusionLevel(level: string): string {
  const map: Record<string, string> = { alta: "alta", media: "média", baixa: "baixa" };
  return map[level] || level;
}

function updateLastUpdate(): void {
  const element = byId("ultima-atualizacao");
  element.textContent = "Sinc. " + formatClock(new Date());
}

function toggleRightPanel(): void {
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

function toggleLeftPanel(): void {
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

function updateClock(): void {
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
   RIGHT PANEL — Evidence
   ============================================================ */
async function loadEventEvidence(eventId: number): Promise<void> {
  const container = byId("right-panel-evidence");
  if (!container) return;
  container.innerHTML = '<div class="rp-loading"><div class="skeleton skeleton-block"></div><div class="skeleton skeleton-circle"></div></div>';
  try {
    const eventEvidences = await fetchOperationalData<EvidenciaVisual[]>("/evidencias?evento_id=" + eventId);
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
    for (const objectUrl of evidenceObjectUrls) URL.revokeObjectURL(objectUrl);
    evidenceObjectUrls.clear();
    const prepared = await Promise.all(eventEvidences.map(async (ev) => {
      if (ev.url_externa) return { ev, imageSrc: ev.url_externa };
      if (!ev.caminho_arquivo) return { ev, imageSrc: "" };
      const response = await apiFetch("/evidencias/arquivo/" + encodeURIComponent(ev.caminho_arquivo));
      if (!response.ok) return { ev, imageSrc: "" };
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
    container.querySelectorAll<HTMLButtonElement>(".rp-evidence-expand").forEach((button) => {
      button.addEventListener("click", () => openEvidenceViewer(button.dataset.evidenceImage || "", button.dataset.evidenceAlt || "Evidência visual"));
    });
    container.querySelectorAll<HTMLButtonElement>(".rp-evidence-open").forEach((button) => {
      button.addEventListener("click", () => openEvidenceViewer(button.dataset.evidenceImage || "", button.dataset.evidenceAlt || "Evidência visual"));
    });
  } catch {
    container.innerHTML = '<div class="right-panel-empty rp-error">' +
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="10"/><path d="M12 8v4M12 16h.01"/></svg>' +
      '<span>Erro ao carregar evidências</span><button class="rp-retry" data-action="retry-evidence">Tentar novamente</button>' +
      '</div>';
    container.querySelector<HTMLElement>("[data-action='retry-evidence']")?.addEventListener("click", () => loadEventEvidence(eventId));
  }
}

function openEvidenceViewer(src: string, alt: string): void {
  if (!src) return;
  const viewer = byId<HTMLElement>("evidence-viewer");
  const image = byId<HTMLImageElement>("evidence-viewer-image");
  image.src = src;
  image.alt = alt;
  viewer.hidden = false;
  byId<HTMLButtonElement>("evidence-viewer-close").focus();
}

function initEvidenceViewer(): void {
  const viewer = byId<HTMLElement>("evidence-viewer");
  const close = () => { viewer.hidden = true; byId<HTMLImageElement>("evidence-viewer-image").removeAttribute("src"); };
  byId<HTMLButtonElement>("evidence-viewer-close").addEventListener("click", close);
  viewer.addEventListener("click", (event) => { if (event.target === viewer) close(); });
  document.addEventListener("keydown", (event) => { if (event.key === "Escape" && !viewer.hidden) close(); });
}

function clearEventEvidence(): void {
  const container = byId("right-panel-evidence");
  if (!container) return;
  for (const objectUrl of evidenceObjectUrls) URL.revokeObjectURL(objectUrl);
  evidenceObjectUrls.clear();
  byId("evidence-live-confidence").textContent = "--";
  container.innerHTML = '<div class="right-panel-empty">' +
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7z"/><circle cx="12" cy="12" r="3"/></svg>' +
    '<span>Selecione um evento para ver evidências</span>' +
    '<p class="rp-empty-hint">A evidência de IA integra o Data Fusion para gerar o score de confiabilidade.</p>' +
    '</div>';
}

async function loadEvents(): Promise<void> {
  try {
    setApiStatus(true, "Sincronizando");
    loadedEvents = await fetchEvents();
    updateMetrics(loadedEvents);
    applyMarkers(!selectedEventId);
    const ongoingId = selectedEventId && !loadedEvents.some((e) => e.id === selectedEventId) ? null : selectedEventId;
    const target = loadedEvents.find((e) => e.id === ongoingId) || (ongoingId ? null : (loadedEvents.find(isEventVisible) || loadedEvents[0] || null));
    selectedEventId = target?.id || null;
    renderSelectedEvent(target || null);
    updateLastUpdate();
    setApiStatus(true, "Conectado");
    if (selectedEventId) {
      loadEventEvidence(selectedEventId);
    } else {
      clearEventEvidence();
    }
  } catch (error) {
    console.error(error);
    setApiStatus(false, "API indisponível");
    loadedEvents = [];
    updateMetrics([]);
    applyMarkers(false);
    renderSelectedEvent(null);
  }
}

function mostrarMapaIndisponivel(): void {
  byId("mapa").innerHTML = '<div class="map-fallback">' +
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M12 21s-6-5.2-6-10a6 6 0 1112 0c0 4.8-6 10-6 10z"/><circle cx="12" cy="11" r="2"/></svg>' +
    '<span class="map-fallback-text">Mapa indisponível</span>' +
    '<span class="map-fallback-sub">O painel continua disponível sem a camada cartográfica.</span>' +
    '</div>';
}

function criarMapa(): void {
  map = window.L.map("mapa", {
    zoomControl: false,
    attributionControl: true,
    closePopupOnClick: true,
  }).setView(
    [window.CONFIG.MAP_CENTER.lat, window.CONFIG.MAP_CENTER.lng], window.CONFIG.MAP_ZOOM,
  );
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
  // iOS Safari: a barra de endereço recolhe/expande depois do carregamento e o
  // mapa fica com a altura medida no primeiro layout — os controles do rodapé
  // caem fora da tela. O Leaflet só escuta o resize da window, que nem sempre
  // dispara nesse caso; o visualViewport dispara.
  const remedirMapa = (): void => { if (map) map.invalidateSize({ pan: false }); };
  window.visualViewport?.addEventListener("resize", remedirMapa);
  window.addEventListener("orientationchange", () => { window.setTimeout(remedirMapa, 250); });
  window.setTimeout(remedirMapa, 500);
  map.on("popupopen", (popupEvent: any) => {
    openInfoWindow = popupEvent.popup;
  });
  map.on("popupclose", (popupEvent: any) => {
    const shouldReturnFocus = popupReturnFocusToMarker;
    popupReturnFocusToMarker = true;
    openInfoWindow = null;
    if (!shouldReturnFocus) return;
    const markerElement = popupEvent.popup?._source?.getElement?.();
    window.requestAnimationFrame(() => markerElement?.focus());
  });
  document.addEventListener("keydown", (keyboardEvent) => {
    if (keyboardEvent.key !== "Escape" || !openInfoWindow || !map) return;
    map.closePopup(openInfoWindow);
  });
  byId<HTMLButtonElement>("map-recenter")?.addEventListener("click", () => {
    map?.setView([window.CONFIG.MAP_CENTER.lat, window.CONFIG.MAP_CENTER.lng], Math.max(window.CONFIG.MAP_ZOOM, 12));
  });
}

function initMapa(): void {
  if (appInitialized) return;
  appInitialized = true;
  // Ao iniciar o sistema o mapa mostra todos os status; o navegador pode
  // restaurar a seleção anterior do <select>, então forçamos o padrão.
  const filtroStatusInicial = byId<HTMLSelectElement>("filtro-status");
  if (filtroStatusInicial) filtroStatusInicial.value = "";
  const toggleLeftBtn = byId<HTMLButtonElement>("btn-toggle-left");
  if (toggleLeftBtn) {
    toggleLeftBtn.hidden = false;
    toggleLeftBtn.addEventListener("click", toggleLeftPanel);
  }
  initEvidencePanelDock();
  if (window.L) criarMapa();
  else mostrarMapaIndisponivel();

  initYoloTester();
  initEvidenceViewer();
  byId("btn-atualizar").addEventListener("click", loadEvents);
  initStatusFilter();

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

export {};
