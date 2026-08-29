export type FusionDisplayComponent = {
  nome: string;
  pontuacao: number;
  peso: number;
  contribuicao: number;
  detalhe: string;
};

export function formatFusionPercent(value: number, fractionDigits = 1): string {
  return new Intl.NumberFormat("pt-BR", {
    style: "percent",
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits,
  }).format(value);
}

/** Utilitária de auditoria para teste visual; a interface exibe a contribuição retornada pela API. */
export function calculateVisualContribution(score: number, weight: number): number {
  return score * weight;
}

export function fusionComponentLabel(name: string, eventoTipo?: string): string {
  if (name === "clima" && eventoTipo === "transito") return "Fonte contextual";
  const labels: Record<string, string> = {
    ia: "IA / visão computacional",
    clima: "Dado contextual",
    fonte_oficial: "Fonte oficial",
  };
  return labels[name] || name;
}

export function formatFusionEquation(component: FusionDisplayComponent, eventoTipo?: string): string {
  return fusionComponentLabel(component.nome, eventoTipo) + " " +
    formatFusionPercent(component.pontuacao) + " × peso " +
    formatFusionPercent(component.peso) + " = " +
    formatFusionPercent(component.contribuicao);
}
