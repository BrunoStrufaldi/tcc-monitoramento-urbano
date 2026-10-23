export function formatFusionPercent(value, fractionDigits = 1) {
    return new Intl.NumberFormat("pt-BR", {
        style: "percent",
        minimumFractionDigits: fractionDigits,
        maximumFractionDigits: fractionDigits,
    }).format(value);
}
export function fusionComponentLabel(name, eventoTipo) {
    if (name === "contexto" && eventoTipo === "transito")
        return "Fonte contextual";
    const labels = {
        ia: "IA / visão computacional",
        contexto: "Dado contextual",
    };
    return labels[name] || name;
}
/**
 * Diz se o evento chegou ao limite para virar ativo, usando o percentual que
 * aparece na tela. O arredondamento é o mesmo do backend (data_fusion_service.py).
 */
export function atingeLimiarAtivo(confiabilidade, limiar) {
    return Number(confiabilidade.toFixed(2)) >= limiar;
}
