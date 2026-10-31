export type Ponto = { latitude: number; longitude: number };

export const RAIO_BUSCA_M = 1500;

export type ResultadoNominatim = { lat: string; lon: string; display_name: string; address?: { city?: string } };

// Retângulo da cidade de São Paulo (oeste, norte, leste, sul). Ele ainda pega pedaços
// de Guarulhos, Osasco e outras vizinhas, por isso o resultado também é conferido pelo município.
const CAIXA_SAO_PAULO = "-46.826,-23.356,-46.365,-24.008";

/** Distância em metros entre dois pontos, pela fórmula de haversine. */
export function distanciaMetros(a: Ponto, b: Ponto): number {
  const raioTerra = 6371000;
  const rad = Math.PI / 180;
  const dLat = (b.latitude - a.latitude) * rad;
  const dLng = (b.longitude - a.longitude) * rad;
  const h = Math.sin(dLat / 2) ** 2 +
    Math.cos(a.latitude * rad) * Math.cos(b.latitude * rad) * Math.sin(dLng / 2) ** 2;
  return 2 * raioTerra * Math.asin(Math.sqrt(h));
}

/** Pontos (eventos ou câmeras) que estão até o raio informado, do mais perto para o mais longe. */
export function pontosNoRaio<T extends Ponto>(pontos: T[], centro: Ponto, raio = RAIO_BUSCA_M): { ponto: T; distancia: number }[] {
  return pontos
    .map((ponto) => ({ ponto, distancia: distanciaMetros(centro, ponto) }))
    .filter((item) => item.distancia <= raio)
    .sort((a, b) => a.distancia - b.distancia);
}

/** Endereço de consulta do Nominatim (OpenStreetMap), limitado à cidade de São Paulo. */
export function urlBuscaEndereco(texto: string): string {
  const params = new URLSearchParams({
    q: texto.trim(),
    format: "jsonv2",
    limit: "5",
    addressdetails: "1",
    countrycodes: "br",
    viewbox: CAIXA_SAO_PAULO,
    bounded: "1",
    "accept-language": "pt-BR",
  });
  return "https://nominatim.openstreetmap.org/search?" + params.toString();
}

/** Primeiro resultado que fica no município de São Paulo, ou null se nenhum fica. */
export function resultadoNaCapital(lista: ResultadoNominatim[]): ResultadoNominatim | null {
  return lista.find((item) => item.address?.city === "São Paulo") || null;
}

/** Mostra 230 m ou 1,2 km. */
export function formatarDistancia(metros: number): string {
  if (metros < 1000) return Math.round(metros) + " m";
  return (metros / 1000).toLocaleString("pt-BR", { maximumFractionDigits: 1 }) + " km";
}

/** O nome completo do Nominatim é longo. Fica só com as duas primeiras partes. */
export function nomeCurtoDoLocal(nomeCompleto: string): string {
  return nomeCompleto.split(",").map((parte) => parte.trim()).filter(Boolean).slice(0, 2).join(", ");
}
