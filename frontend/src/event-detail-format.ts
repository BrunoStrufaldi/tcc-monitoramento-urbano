export function detailValue(value: string | number | null | undefined, fallback = "Não informado"): string {
  return value == null || value === "" ? fallback : String(value);
}

export function detailEmptyMessage(section: string): string {
  return "Nenhum dado disponível em " + section + " para este evento.";
}
