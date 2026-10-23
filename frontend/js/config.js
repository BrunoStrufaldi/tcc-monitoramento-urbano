/**
 * Configuração do painel. A API e o painel ficam no mesmo endereço, então a
 * URL da API vem do próprio navegador.
 */
window.CONFIG = {
  API_BASE_URL: window.location.origin,
  MAP_CENTER: { lat: -23.55052, lng: -46.633308 },
  MAP_ZOOM: 12,
  REFRESH_INTERVAL_MS: 30000,
};
