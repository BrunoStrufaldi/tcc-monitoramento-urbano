import test from "node:test";
import assert from "node:assert/strict";
import {
  formatFusionPercent,
  atingeLimiarAtivo,
  fusionComponentLabel,
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

test("rotula as duas dimensões da fusão", () => {
  assert.equal(fusionComponentLabel("ia"), "IA / visão computacional");
  assert.equal(fusionComponentLabel("contexto", "alagamento"), "Dado contextual");
  assert.equal(fusionComponentLabel("contexto", "transito"), "Fonte contextual");
});
