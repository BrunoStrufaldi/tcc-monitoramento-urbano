export function formatFusionPercent(value, fractionDigits = 1) {
    return new Intl.NumberFormat("pt-BR", {
        style: "percent",
        minimumFractionDigits: fractionDigits,
        maximumFractionDigits: fractionDigits,
    }).format(value);
}
/** Utilitária de auditoria para teste visual; a interface exibe a contribuição retornada pela API. */
export function calculateVisualContribution(score, weight) {
    return score * weight;
}
export function fusionComponentLabel(name, eventoTipo) {
    if (name === "clima" && eventoTipo === "transito")
        return "Fonte contextual";
    const labels = {
        ia: "IA / visão computacional",
        clima: "Dado contextual",
        fonte_oficial: "Fonte oficial",
    };
    return labels[name] || name;
}
export function formatFusionEquation(component, eventoTipo) {
    return fusionComponentLabel(component.nome, eventoTipo) + " " +
        formatFusionPercent(component.pontuacao) + " × peso " +
        formatFusionPercent(component.peso) + " = " +
        formatFusionPercent(component.contribuicao);
}
