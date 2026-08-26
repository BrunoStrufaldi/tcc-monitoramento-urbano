export function detailValue(value, fallback = "Não informado") {
    return value == null || value === "" ? fallback : String(value);
}
export function detailEmptyMessage(section) {
    return "Nenhum dado disponível em " + section + " para este evento.";
}
