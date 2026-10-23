export type FusionDisplayComponent = {
  nome: string;
  pontuacao: number;
  peso: number;
  contribuicao: number;
  detalhe: string;
  peso_base?: number;
};

export function formatFusionPercent(value: number, fractionDigits = 1): string {
  return new Intl.NumberFormat("pt-BR", {
    style: "percent",
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits,
  }).format(value);
}

export function fusionComponentLabel(name: string, eventoTipo?: string): string {
  if (name === "contexto" && eventoTipo === "transito") return "Fonte contextual";
  const labels: Record<string, string> = {
    ia: "IA / visão computacional",
    contexto: "Dado contextual",
  };
  return labels[name] || name;
}

/**
 * Diz se o evento chegou ao limite para virar ativo, usando o percentual que
 * aparece na tela. O arredondamento é o mesmo do backend (data_fusion_service.py).
 */
export function atingeLimiarAtivo(confiabilidade: number, limiar: number): boolean {
  return Number(confiabilidade.toFixed(2)) >= limiar;
}
