import test from "node:test";
import assert from "node:assert/strict";
import { buildRouteUrl, isResolvedStatus } from "../dist/event-actions-format.js";

test("monta rota usando apenas as coordenadas recebidas", () => {
  assert.equal(
    buildRouteUrl(-23.55052, -46.633308),
    "https://www.google.com/maps/dir/?api=1&destination=-23.55052%2C-46.633308",
  );
});

test("reconhece somente o status resolvido", () => {
  assert.equal(isResolvedStatus("resolvido"), true);
  assert.equal(isResolvedStatus("em_analise"), false);
  assert.equal(isResolvedStatus(undefined), false);
});
