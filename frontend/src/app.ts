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

type UrbanRegion = {
  id: number;
  nome: string;
  codigo?: string | null;
  descricao?: string | null;
  ativo: boolean;
};

type DataSource = {
  id: number;
  nome: string;
  tipo: string;
  endpoint?: string | null;
  descricao?: string | null;
  ativo: boolean;
};

type UrbanNotification = {
  id: number;
  evento_id: number;
  canal: string;
  destinatario?: string | null;
  titulo: string;
  mensagem: string;
  status: string;
  tentativas: number;
  erro_detalhe?: string | null;
  criado_em?: string | null;
};

type FusionComponent = { nome: string; pontuacao: number; peso: number; contribuicao: number; detalhe: string };
type FusionResult = { evento_id: number; confiabilidade: number; nivel: string; componentes: FusionComponent[] };

type ViewKey = "dashboard" | "eventos" | "alertas" | "regioes" | "fontes" | "fusao" | "cv" | "config";

type RailItem = { view: ViewKey; label: string; svg: string };
type RailSection = { key: string; title: string; items: RailItem[] };

const RAIL_ICONS: Record<string, string> = {
  eventos: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M12 9v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>',
  alertas: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"/></svg>',
  regioes: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7"/></svg>',
  fontes: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><ellipse cx="12" cy="5" rx="7" ry="3"/><path d="M5 5v14c0 1.66 3.13 3 7 3s7-1.34 7-3V5M5 12c0 1.66 3.13 3 7 3s7-1.34 7-3"/></svg>',
  fusao: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M12 2a10 10 0 110 20 10 10 0 010-20zm0 4v4l3 3"/></svg>',
  cv: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7z"/><circle cx="12" cy="12" r="3"/></svg>',
  config: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 11-2.83 2.83l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 11-4 0v-.09a1.65 1.65 0 00-1-1.51 1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 11-2.83-2.83l.06-.06a1.65 1.65 0 00.33-1.82 1.65 1.65 0 00-1.51-1H3a2 2 0 110-4h.09a1.65 1.65 0 001.51-1 1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 112.83-2.83l.06.06a1.65 1.65 0 001.82.33h.01a1.65 1.65 0 001-1.51V3a2 2 0 114 0v.09a1.65 1.65 0 001 1.51h.01a1.65 1.65 0 001.82-.33l.06-.06a2 2 0 112.83 2.83l-.06.06a1.65 1.65 0 00-.33 1.82v.01a1.65 1.65 0 001.51 1H21a2 2 0 110 4h-.09a1.65 1.65 0 00-1.51 1z"/></svg>',
  dashboard: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg>',
};

const RAIL_SECTIONS: RailSection[] = [
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
];

const VIEW_TO_RAIL: Record<ViewKey, string> = {
  dashboard: "painel",
  eventos: "operacoes",
  alertas: "operacoes",
  regioes: "operacoes",
  fontes: "operacoes",
  fusao: "inteligencia",
  cv: "inteligencia",
  config: "sistema",
};

declare global {
  interface Window {
    CONFIG: AppConfig;
    GOOGLE_MAPS_API_KEY?: string;
    initMapa: () => void;
    google: any;
  }
}

const SEVERITIES: Record<SeverityKey, SeverityStyle> = {
  baixa: { label: "Baixa", color: "#22c55e", scale: 9, zIndex: 2 },
  media: { label: "Média", color: "#FFB300", scale: 11, zIndex: 3 },
  alta: { label: "Alta", color: "#FF8A00", scale: 13, zIndex: 4 },
  critica: { label: "Crítica", color: "#FF5500", scale: 15, zIndex: 5 },
};

let map: any = null;
let openInfoWindow: any = null;
let loadedEvents: UrbanEvent[] = [];
let trainingRegions: UrbanRegion[] = [];
let dataSources: DataSource[] = [];
let notifications: UrbanNotification[] = [];
let searchTerm = "";
let selectedEventId: number | null = null;
let lastUpdateLabel = "";
const markersById = new Map<number, any>();
const activeSeverities = new Set<SeverityKey>(Object.keys(SEVERITIES) as SeverityKey[]);
let railPanelOpen = false;
let activeView: ViewKey = "dashboard";

const byId = <T extends HTMLElement>(id: string): T => document.getElementById(id) as T;

function escapeHtml(value: unknown): string {
  if (value == null) return "";
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function normalizeSeverity(value: string | null | undefined): SeverityKey {
  const key = String(value || "media").toLowerCase().trim();
  return key in SEVERITIES ? (key as SeverityKey) : "media";
}

function severityStyle(value: string): SeverityStyle {
  return SEVERITIES[normalizeSeverity(value)];
}

function setApiStatus(ok: boolean, message: string): void {
  const element = byId("status-api");
  element.textContent = message;
  element.classList.toggle("ok", ok);
  element.classList.toggle("erro", !ok);
}

function loadGoogleMaps(): void {
  const key = window.GOOGLE_MAPS_API_KEY;
  if (!key || key === "SUA_CHAVE_AQUI") {
    setApiStatus(false, "Configure a chave do Maps");
    byId("lista-eventos").innerHTML = '<li class="empty-state">Defina <code>GOOGLE_MAPS_API_KEY</code> em <code>js/config.js</code></li>';
    return;
  }

  const script = document.createElement("script");
  script.src = "https://maps.googleapis.com/maps/api/js?key=" + encodeURIComponent(key) + "&callback=initMapa";
  script.async = true;
  script.defer = true;
  document.body.appendChild(script);
}

async function fetchEvents(): Promise<UrbanEvent[]> {
  const params = new URLSearchParams({ limite: "200" });
  const statusElement = byId<HTMLSelectElement>("filtro-status");
  if (statusElement.value) params.set("status", statusElement.value);

  const response = await fetch(window.CONFIG.API_BASE_URL + "/eventos?" + params.toString());
  if (!response.ok) throw new Error("API retornou " + response.status);
  return response.json() as Promise<UrbanEvent[]>;
}

async function fetchJson<T>(url: string): Promise<T> {
  const response = await fetch(window.CONFIG.API_BASE_URL + url);
  if (!response.ok) throw new Error("API retornou " + response.status);
  return response.json() as Promise<T>;
}

function formatClock(value: Date): string {
  return value.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function isEventVisible(event: UrbanEvent): boolean {
  if (!activeSeverities.has(normalizeSeverity(event.severidade))) return false;
  if (!searchTerm) return true;
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

function clearMarkers(): void {
  markersById.forEach((marker) => marker.setMap(null));
  markersById.clear();
}

function markerIcon(style: SeverityStyle): any {
  const critica = style.label === "Crítica";
  return {
    path: window.google.maps.SymbolPath.CIRCLE,
    scale: style.scale,
    fillColor: style.color,
    fillOpacity: 0.96,
    strokeColor: critica ? "#FFB300" : "#1a1a1a",
    strokeWeight: 2,
  };
}

function formatDate(value?: string | null): string {
  if (!value) return "";
  return new Date(value).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
}

function formatTime(value?: string | null): string {
  if (!value) return "";
  return new Date(value).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
}

function formatConfidence(value: UrbanEvent["confianca"]): string {
  if (value == null || Number.isNaN(Number(value))) return "";
  return String((Number(value) * 100).toFixed(0)) + "%";
}

function infoWindowContent(event: UrbanEvent): string {
  const style = severityStyle(event.severidade);
  const address = event.localizacao?.endereco || event.localizacao?.bairro || "";
  const region = event.regiao?.nome || "";
  const confidence = formatConfidence(event.confianca);
  const source = event.fonte?.nome || "";
  return '<div class="info-window">' +
    '<span class="info-criticidade" style="background:' + style.color + '">' + escapeHtml(style.label) + '</span>' +
    '<h3>' + escapeHtml(event.titulo) + '</h3>' +
    '<p>' + escapeHtml(event.tipo) + ' · ' + escapeHtml(event.status.replace("_", " ")) + '</p>' +
    (event.descricao ? '<p>' + escapeHtml(event.descricao) + '</p>' : '') +
    (confidence ? '<p class="info-confianca">Confiabilidade: ' + confidence + '</p>' : '') +
    (address ? '<p>' + escapeHtml(address) + '</p>' : '') +
    (region ? '<p>' + escapeHtml(region) + '</p>' : '') +
    (source ? '<p>Fonte: ' + escapeHtml(source) + '</p>' : '') +
    (event.detectado_em ? '<p>' + formatDate(event.detectado_em) + '</p>' : '') +
    '</div>';
}

function createMarker(event: UrbanEvent): void {
  const style = severityStyle(event.severidade);
  const marker = new window.google.maps.Marker({
    position: { lat: event.latitude, lng: event.longitude },
    map: map,
    title: style.label + ": " + event.titulo,
    icon: markerIcon(style),
    zIndex: style.zIndex,
  });

  marker.addListener("click", () => {
    if (openInfoWindow) openInfoWindow.close();
    openInfoWindow = new window.google.maps.InfoWindow({ content: infoWindowContent(event) });
    openInfoWindow.open({ anchor: marker, map: map });
    selectEvent(event.id);
  });

  markersById.set(event.id, marker);
}

function fitMapBounds(events: UrbanEvent[]): void {
  if (!events.length || !map) return;
  const bounds = new window.google.maps.LatLngBounds();
  events.forEach((event) => bounds.extend({ lat: event.latitude, lng: event.longitude }));
  map.fitBounds(bounds, { top: 72, right: 72, bottom: 72, left: 72 });
  const listener = window.google.maps.event.addListener(map, "idle", () => {
    if (map.getZoom() > 16) map.setZoom(16);
    window.google.maps.event.removeListener(listener);
  });
}

function formatStatus(value: string): string {
  return value.replace("_", " ").replace(/\b\w/g, (char) => char.toUpperCase());
}

function selectEvent(id: number): void {
  selectedEventId = id;
  const event = loadedEvents.find((e) => e.id === id);
  renderSelectedEvent(event || null);
  highlightListItem(id);

  if (event && map) {
    map.panTo({ lat: event.latitude, lng: event.longitude });
    if (map.getZoom() < 14) map.setZoom(14);
    const marker = markersById.get(event.id);
    if (marker) {
      if (openInfoWindow) openInfoWindow.close();
      openInfoWindow = new window.google.maps.InfoWindow({ content: infoWindowContent(event) });
      openInfoWindow.open({ anchor: marker, map: map });
    }
  }
}

function renderSelectedEvent(event: UrbanEvent | null): void {
  const severity = byId("selected-severity");
  const title = byId("selected-title");
  const description = byId("selected-description");
  const status = byId("selected-status");
  const type = byId("selected-type");
  const region = byId("selected-region");
  const confidence = byId("selected-confidence");
  const source = byId("selected-source");
  const fusion = byId("selected-fusion");
  const breakdowns = document.querySelectorAll<HTMLElement>("#fusion-breakdown, #fusion-breakdown-panel");

  if (!event) {
    severity.textContent = "--";
    severity.style.background = "var(--color-muted)";
    title.textContent = "Selecione um evento";
    description.textContent = "Selecione um evento para visualizar os detalhes operacionais.";
    status.textContent = "--";
    type.textContent = "--";
    region.textContent = "--";
    confidence.textContent = "--";
    source.textContent = "--";
    fusion.textContent = "--";
    breakdowns.forEach((b) => { b.innerHTML = ""; });
    return;
  }

  const style = severityStyle(event.severidade);
  severity.textContent = style.label;
  severity.style.background = style.color;
  title.textContent = event.titulo;
  description.textContent = event.descricao || "Sem descrição operacional registrada.";
  status.textContent = formatStatus(event.status);
  type.textContent = formatStatus(event.tipo);
  region.textContent = event.regiao?.nome || event.localizacao?.bairro || "Sem região";
  confidence.textContent = formatConfidence(event.confianca) || "--";
  source.textContent = event.fonte?.nome || event.fonte?.tipo || "Não identificada";
  fusion.textContent = "calculando...";
  loadFusionBreakdown(event.id);
}

function renderSeverityFilters(): void {
  const container = byId("legenda-criticidade");
  const allActive = activeSeverities.size === Object.keys(SEVERITIES).length;

  const countFor = (key: SeverityKey): number =>
    loadedEvents.filter((e) => normalizeSeverity(e.severidade) === key).length;

  const items = [
    '<button class="sev-btn sev-all' + (allActive ? " active" : "") + '" data-criticidade="__all__" role="tab" aria-selected="' + allActive + '">' +
      '<span class="sev-dot" style="background:var(--color-text-secondary)"></span>' +
      '<span class="sev-label">Todos</span>' +
    '</button>',
    ...Object.entries(SEVERITIES).map(([key, style]) => {
      const active = activeSeverities.has(key as SeverityKey);
      const count = countFor(key as SeverityKey);
      return '<button class="sev-btn ' + (active ? " active" : "") +
        '" style="--sev-color:' + style.color + ';--sev-dim:' + style.color + '16" data-criticidade="' + key + '" role="tab" aria-selected="' + active + '">' +
        '<span class="sev-dot" style="background:' + style.color + '"></span>' +
        '<span class="sev-label">' + style.label + '</span>' +
        (count > 0 ? '<span class="sev-count">' + count + '</span>' : '') +
        '</button>';
    }),
  ];
  container.innerHTML = '<div role="tablist" aria-label="Filtrar por severidade">' + items.join("") + '</div>';

  container.querySelectorAll<HTMLButtonElement>("button[data-criticidade]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const raw = btn.dataset.criticidade as string;
      if (raw === "__all__") {
        activeSeverities.clear();
        Object.keys(SEVERITIES).forEach((k) => activeSeverities.add(k as SeverityKey));
      } else {
        const key = raw as SeverityKey;
        if (activeSeverities.has(key)) {
          activeSeverities.delete(key);
        } else {
          activeSeverities.add(key);
        }
      }
      renderSeverityFilters();
      applyMarkers();
      renderEventList(loadedEvents);
    });
  });
}

function updateMetrics(events: UrbanEvent[]): void {
  const confidences = events.map((event) => Number(event.confianca)).filter((value) => !Number.isNaN(value));
  const confidenceAverage = confidences.length
    ? String(Math.round((confidences.reduce((sum, value) => sum + value, 0) / confidences.length) * 100)) + "%"
    : "--";

  const kpiTotal = byId("kpi-total");
  const kpiAtivos = byId("kpi-ativos");
  const kpiCriticos = byId("kpi-criticos");
  const kpiConfianca = byId("kpi-confianca");

  animateKpi(kpiTotal, String(events.length));
  animateKpi(kpiAtivos, String(events.filter((e) => e.status === "ativo").length));
  animateKpi(kpiCriticos, String(events.filter((e) => normalizeSeverity(e.severidade) === "critica").length));
  animateKpi(kpiConfianca, confidenceAverage);
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

function updateCount(visible: number, total: number): void {
  const label = visible === total ? String(total) : String(visible) + "/" + String(total);
  byId("contagem-eventos").textContent = label;
  const strip = byId("contagem-strip");
  if (strip) strip.textContent = String(visible);
}

function applyMarkers(): void {
  clearMarkers();
  const visible = loadedEvents.filter(isEventVisible);
  visible.forEach(createMarker);
  fitMapBounds(visible);
  updateCount(visible.length, loadedEvents.length);
}

function renderEventList(events: UrbanEvent[]): void {
  const list = byId("lista-eventos");
  const visible = events.filter(isEventVisible);
  list.innerHTML = "";

  if (!visible.length) {
    list.innerHTML = '<li class="empty-state">Nenhum evento encontrado.</li>';
    return;
  }

  [...visible]
    .sort((a, b) => severityStyle(b.severidade).zIndex - severityStyle(a.severidade).zIndex)
    .forEach((event, index) => {
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
      item.style.animationDelay = (index * 26) + "ms";
      item.classList.add("animate-in");

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
              '<span class="intel-value">' + escapeHtml(event.fonte.nome || event.fonte.tipo) + '</span>' +
            '</span>' +
            (event.fonte.tipo ? '<span class="intel-chip intel-muted"><span class="intel-value">' + escapeHtml(formatStatus(event.fonte.tipo)) + '</span></span>' : '') +
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
      list.appendChild(item);
    });
}

function highlightListItem(id: number): void {
  document.querySelectorAll<HTMLElement>(".event-card").forEach((element) => {
    element.classList.toggle("active", Number(element.dataset.id) === id);
  });
}

function showLoading(listId: string, message?: string): void {
  const msg = message || "Carregando...";
  byId(listId).innerHTML = '<li class="loading-state">' + escapeHtml(msg) + '</li>';
}

function showError(message: string): void {
  byId("lista-eventos").innerHTML = '<li class="error-state"><strong>Dados Indisponíveis</strong><span>' + escapeHtml(message) + '</span></li>';
}

async function loadFusionBreakdown(eventId: number): Promise<void> {
  const containers = document.querySelectorAll<HTMLElement>("#fusion-breakdown, #fusion-breakdown-panel");
  const fusion = byId("selected-fusion");
  try {
    const result = await fetchJson<FusionResult>("/fusion/eventos/" + eventId + "/confiabilidade");
    fusion.textContent = formatConfidence(result.confiabilidade) + " · " + formatFusionLevel(result.nivel);
    const html = result.componentes.map((component) => {
      const pct = Math.round(component.pontuacao * 100);
      return '<div class="fusion-item">' +
        '<div class="fusion-row"><span class="fusion-name">' + escapeHtml(labelFusionComponent(component.nome)) + '</span>' +
          '<span class="fusion-value">' + pct + '%</span></div>' +
        '<div class="fusion-track"><div class="fusion-fill" style="width:' + pct + '%"></div></div>' +
        (component.detalhe ? '<span class="fusion-detail">' + escapeHtml(component.detalhe) + '</span>' : '') +
        '</div>';
    }).join("");
    containers.forEach((container) => { container.innerHTML = html; });
  } catch {
    fusion.textContent = "--";
    containers.forEach((container) => { container.innerHTML = ''; });
  }
}

function formatFusionLevel(level: string): string {
  const map: Record<string, string> = { alta: "alta", media: "média", baixa: "baixa" };
  return map[level] || level;
}

function labelFusionComponent(name: string): string {
  const map: Record<string, string> = {
    ia: "Visão computacional",
    clima: "Contexto climático",
    fonte_oficial: "Fonte oficial",
  };
  return map[name] || name;
}

function updateLastUpdate(): void {
  const element = byId("ultima-atualizacao");
  const now = formatClock(new Date());
  lastUpdateLabel = now;
  element.textContent = "Sinc. " + now;
}

function renderRailPanel(key: string): void {
  const section = RAIL_SECTIONS.find((s) => s.key === key);
  if (!section) return;
  byId("rail-panel-title").textContent = section.title;
  byId("rail-panel-items").innerHTML = section.items.map((item) =>
    '<button class="rail-item' + (activeView === item.view ? " active" : "") + '" data-view="' + item.view + '">' +
      '<span class="rail-item-icon">' + item.svg + '</span>' +
      '<span class="rail-item-label">' + item.label + '</span>' +
    '</button>'
  ).join("");
  document.querySelectorAll<HTMLButtonElement>("#rail-panel-items .rail-item").forEach((el) => {
    el.addEventListener("click", () => {
      switchView(el.dataset.view as ViewKey);
      closeRailPanel();
    });
  });
}

function openRailPanel(key: string): void {
  const panel = byId("rail-panel");
  if (railPanelOpen && panel.dataset.section === key) return;
  railPanelOpen = true;
  renderRailPanel(key);
  panel.hidden = false;
  panel.dataset.section = key;
  panel.classList.remove("rail-panel-leave");
  panel.classList.add("rail-panel-open");
  setRailButtonActive(key);
}

function closeRailPanel(): void {
  if (!railPanelOpen) return;
  railPanelOpen = false;
  const panel = byId("rail-panel");
  panel.classList.remove("rail-panel-open");
  panel.classList.add("rail-panel-leave");
  window.setTimeout(() => {
    if (!railPanelOpen) panel.hidden = true;
  }, 160);
  setRailButtonActive(activeView);
}

function setRailButtonActive(key: string): void {
  document.querySelectorAll<HTMLButtonElement>(".rail-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.rail === key);
  });
}

function initRail(): void {
  const rail = document.querySelector<HTMLElement>(".rail");
  const railButtons = document.querySelectorAll<HTMLButtonElement>(".rail-btn");
  let openTimer: number | null = null;
  let closeTimer: number | null = null;

  railButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      const key = btn.dataset.rail || "painel";
      const section = RAIL_SECTIONS.find((s) => s.key === key);
      if (railPanelOpen && document.querySelector<HTMLElement>("#rail-panel")?.dataset.section === key) {
        closeRailPanel();
        return;
      }
      openRailPanel(key);
      if (section && section.items.length === 1) switchView(section.items[0].view);
    });
    btn.addEventListener("mouseenter", () => {
      if (closeTimer) { window.clearTimeout(closeTimer); closeTimer = null; }
      openTimer = window.setTimeout(() => openRailPanel(btn.dataset.rail || "painel"), 60);
    });
    btn.addEventListener("mouseleave", () => {
      if (openTimer) { window.clearTimeout(openTimer); openTimer = null; }
      closeTimer = window.setTimeout(closeRailPanel, 220);
    });
  });

  const panel = byId("rail-panel");
  panel.addEventListener("mouseenter", () => {
    if (closeTimer) { window.clearTimeout(closeTimer); closeTimer = null; }
  });
  panel.addEventListener("mouseleave", () => {
    closeTimer = window.setTimeout(closeRailPanel, 180);
  });

  if (rail) {
    rail.addEventListener("mouseleave", () => {
      closeTimer = window.setTimeout(closeRailPanel, 200);
    });
  }

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeRailPanel();
  });
}

function switchView(key: ViewKey): void {
  activeView = key;
  document.querySelectorAll<HTMLElement>(".view").forEach((view) => {
    view.hidden = view.id !== "view-" + key;
    view.classList.toggle("view-active", view.id === "view-" + key);
  });
  const railKey = VIEW_TO_RAIL[key];
  setRailButtonActive(railKey);
  if (railPanelOpen) renderRailPanel(railKey);
  if (key === "regioes") void loadRegions();
  if (key === "fontes") void loadSources();
  if (key === "alertas") void loadNotifications();
  if (key === "fusao") {
    const active = loadedEvents.find((e) => e.id === selectedEventId) || loadedEvents[0];
    if (active) void loadFusionBreakdown(active.id);
  }
}

async function loadRegions(): Promise<void> {
  const list = byId("lista-regioes");
  try {
    trainingRegions = await fetchJson<UrbanRegion[]>("/regioes?ativo=true&limite=200");
    byId("contagem-regioes").textContent = String(trainingRegions.length);
    if (!trainingRegions.length) {
      list.innerHTML = '<li class="empty-state">Nenhuma região monitorada.</li>';
      return;
    }
    list.innerHTML = trainingRegions.map((region) =>
      '<li class="info-card"><div class="info-card-head"><h3>' + escapeHtml(region.nome) + '</h3>' +
      (region.codigo ? '<span class="code-pill">' + escapeHtml(region.codigo) + '</span>' : '') + '</div>' +
      (region.descricao ? '<p class="event-description">' + escapeHtml(region.descricao) + '</p>' : '') +
      '</li>'
    ).join("");
  } catch {
    list.innerHTML = '<li class="error-state">Não foi possível carregar as regiões.</li>';
  }
}

async function loadSources(): Promise<void> {
  const list = byId("lista-fontes");
  try {
    dataSources = await fetchJson<DataSource[]>("/fontes?ativo=true&limite=200");
    byId("contagem-fontes").textContent = String(dataSources.length);
    if (!dataSources.length) {
      list.innerHTML = '<li class="empty-state">Nenhuma fonte cadastrada.</li>';
      return;
    }
    list.innerHTML = dataSources.map((source) =>
      '<li class="info-card"><div class="info-card-head"><h3>' + escapeHtml(source.nome) + '</h3>' +
      '<span class="source-type">' + escapeHtml(source.tipo) + '</span></div>' +
      (source.descricao ? '<p class="event-description">' + escapeHtml(source.descricao) + '</p>' : '') +
      (source.endpoint ? '<p class="event-meta"><span>' + escapeHtml(source.endpoint) + '</span></p>' : '') +
      '</li>'
    ).join("");
  } catch {
    list.innerHTML = '<li class="error-state">Não foi possível carregar as fontes.</li>';
  }
}

async function loadNotifications(): Promise<void> {
  const list = byId("lista-notificacoes");
  try {
    notifications = await fetchJson<UrbanNotification[]>("/notificacoes?status=pendente&limite=200");
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
  } catch {
    list.innerHTML = '<li class="error-state">Não foi possível carregar as notificações.</li>';
  }
}

async function loadEvents(): Promise<void> {
  try {
    setApiStatus(true, "Sincronizando");
    showLoading("lista-eventos", "Carregando eventos...");
    loadedEvents = await fetchEvents();
    updateMetrics(loadedEvents);
    applyMarkers();
    renderEventList(loadedEvents);
    const ongoingId = selectedEventId && !loadedEvents.some((e) => e.id === selectedEventId) ? null : selectedEventId;
    const target = loadedEvents.find((e) => e.id === ongoingId) || (ongoingId ? null : (loadedEvents.find(isEventVisible) || loadedEvents[0] || null));
    renderSelectedEvent(target || null);
    if (target) highlightListItem(target.id);
    updateLastUpdate();
    setApiStatus(true, "Conectado");
    refreshFeeds();
  } catch (error) {
    console.error(error);
    setApiStatus(false, "API indisponível");
    loadedEvents = [];
    updateMetrics([]);
    applyMarkers();
    renderEventList([]);
    renderSelectedEvent(null);
    showError("Não foi possível carregar eventos da API. Verifique se o backend está rodando em " + window.CONFIG.API_BASE_URL);
  }
}

function refreshFeeds(): void {
  void loadRegions();
  void loadSources();
  void loadNotifications();
}

function mapStyles(): any[] {
  return [
    { featureType: "poi", stylers: [{ visibility: "off" }] },
    { featureType: "transit", stylers: [{ visibility: "off" }] },
    { elementType: "geometry", stylers: [{ color: "#1a1a1a" }] },
    { featureType: "road", elementType: "geometry", stylers: [{ color: "#242424" }] },
    { featureType: "water", elementType: "geometry", stylers: [{ color: "#121212" }] },
    { elementType: "labels.text.fill", stylers: [{ color: "#8a8a8a" }] },
    { elementType: "labels.text.stroke", stylers: [{ color: "#0d0d0d" }] },
  ];
}

function initMapa(): void {
  map = new window.google.maps.Map(byId("mapa"), {
    center: window.CONFIG.MAP_CENTER,
    zoom: window.CONFIG.MAP_ZOOM,
    mapTypeControl: false,
    streetViewControl: false,
    fullscreenControl: true,
    styles: mapStyles(),
    backgroundColor: "#0b0f12",
  });

  renderSeverityFilters();
  initRail();
  byId("btn-atualizar").addEventListener("click", loadEvents);
  byId("filtro-status").addEventListener("change", loadEvents);
  const searchInput = byId<HTMLInputElement>("busca-eventos");
  const clearButton = byId<HTMLButtonElement>("busca-limpar");
  const applySearch = (): void => {
    searchTerm = searchInput.value.trim().toLowerCase();
    clearButton.hidden = !searchInput.value;
    applyMarkers();
    renderEventList(loadedEvents);
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
  loadEvents();

  if (window.CONFIG.REFRESH_INTERVAL_MS > 0) {
    window.setInterval(loadEvents, window.CONFIG.REFRESH_INTERVAL_MS);
  }
}

window.initMapa = initMapa;
loadGoogleMaps();

export {};
