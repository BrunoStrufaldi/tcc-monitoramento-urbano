/**
 * Configuração do painel para deploy em container (Cloud Run), onde API e
 * frontend são servidos pela mesma origem. O Dockerfile copia este arquivo
 * como js/config.js.
 *
 * API_BASE_URL sai de window.location em vez de ser fixo: o mesmo build serve
 * qualquer URL (a do Cloud Run muda se o serviço for recriado) e o WebSocket
 * vira wss:// sozinho sob HTTPS — app.ts monta a URL com
 * API_BASE_URL.replace(/^http/, "ws"), que quebraria com valor fixo http://.
 */
window.CONFIG = {
  API_BASE_URL: window.location.origin,
  MAP_CENTER: { lat: -23.55052, lng: -46.633308 },
  MAP_ZOOM: 12,
  REFRESH_INTERVAL_MS: 30000,
};
