import test from "node:test";
import assert from "node:assert/strict";
import { detailEmptyMessage, detailValue } from "../dist/event-detail-format.js";

test("preserva valores reais e usa fallback somente quando ausentes", () => {
  assert.equal(detailValue("Fonte oficial"), "Fonte oficial");
  assert.equal(detailValue(null), "Não informado");
});

test("gera estado vazio específico para a seção", () => {
  assert.equal(detailEmptyMessage("evidências"), "Nenhum dado disponível em evidências para este evento.");
});
