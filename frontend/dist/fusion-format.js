export function formatFusionPercent(value, fractionDigits = 1) {
    return new Intl.NumberFormat("pt-BR", {
        style: "percent",
        minimumFractionDigits: fractionDigits,
        maximumFractionDigits: fractionDigits,
    }).format(value);
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
/**
 * A promoção automática para "Ativo" decide pelo percentual **exibido**: um
 * evento de 0,7977 aparece como "80%" no painel e precisa contar como 80%.
 * `toFixed` arredonda meio-para-cima sobre a representação decimal, o mesmo
 * critério do `Decimal(str(v)).quantize(ROUND_HALF_UP)` em
 * backend/app/services/data_fusion_service.py — as duas pontas têm que
 * concordar, senão o veredito do painel contradiz o status do evento.
 */
export function atingeLimiarAtivo(confiabilidade, limiar) {
    return Number(confiabilidade.toFixed(2)) >= limiar;
}
