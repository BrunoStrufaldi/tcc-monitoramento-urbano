import test from "node:test";
import assert from "node:assert/strict";
import {
  formatFusionPercent,
  atingeLimiarAtivo,
} from "../dist/fusion-format.js";

test("formata percentuais para auditoria em pt-BR", () => {
  assert.equal(formatFusionPercent(0.285), "28,5%");
  assert.equal(formatFusionPercent(0.95), "95,0%");
});

test("promove pelo percentual exibido, não pelo float cru", () => {
  // 0,7977 aparece como "80%" no painel — a decisão tem que acompanhar.
  assert.equal(atingeLimiarAtivo(0.7977, 0.8), true);
  assert.equal(atingeLimiarAtivo(0.7949, 0.8), false);
  assert.equal(atingeLimiarAtivo(0.8, 0.8), true);
});
