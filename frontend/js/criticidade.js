/**
 * Mapeamento de criticidade (campo API: severidade)
 */
const CRITICIDADE = {
  baixa: {
    label: "Baixa",
    cor: "#22c55e",
    escala: 9,
    zIndex: 1,
  },
  media: {
    label: "Média",
    cor: "#f59e0b",
    escala: 11,
    zIndex: 2,
  },
  alta: {
    label: "Alta",
    cor: "#ef4444",
    escala: 13,
    zIndex: 3,
  },
  critica: {
    label: "Crítica",
    cor: "#a855f7",
    escala: 15,
    zIndex: 4,
  },
};

const CRITICIDADE_PADRAO = CRITICIDADE.media;

function normalizarCriticidade(valor) {
  if (!valor) return "media";
  return String(valor).toLowerCase().trim();
}

function obterEstiloCriticidade(severidade) {
  const chave = normalizarCriticidade(severidade);
  return CRITICIDADE[chave] || CRITICIDADE_PADRAO;
}

function rotuloCriticidade(severidade) {
  return obterEstiloCriticidade(severidade).label;
}
