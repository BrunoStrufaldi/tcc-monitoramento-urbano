import test from "node:test";
import assert from "node:assert/strict";
import {
  calculateVisualContribution,
  formatFusionEquation,
  formatFusionPercent,
} from "../dist/fusion-format.js";

test("formata percentuais para auditoria em pt-BR", () => {
  assert.equal(formatFusionPercent(0.285), "28,5%");
  assert.equal(formatFusionPercent(0.95), "95,0%");
});

test("calcula a contribuição visual de pontuação e peso", () => {
  assert.equal(calculateVisualContribution(0.95, 0.3), 0.285);
});

test("monta a equação com a contribuição fornecida pela API", () => {
  assert.equal(formatFusionEquation({
    nome: "clima", pontuacao: 0.95, peso: 0.3, contribuicao: 0.285, detalhe: "",
  }), "Dado contextual 95,0% × peso 30,0% = 28,5%");
});
