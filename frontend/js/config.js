/**
 * Configuração do painel. API e painel moram na mesma origem — o FastAPI serve
 * os dois, local (start.ps1) e no container — então a URL da API sai de
 * window.location em vez de ser fixa: vale para qualquer porta ou domínio, e o
 * WebSocket vira wss:// sozinho sob HTTPS (app.ts monta a URL com
 * API_BASE_URL.replace(/^http/, "ws")).
 */
window.CONFIG = {
  API_BASE_URL: window.location.origin,
  MAP_CENTER: { lat: -23.55052, lng: -46.633308 },
  MAP_ZOOM: 12,
  REFRESH_INTERVAL_MS: 30000,
};
