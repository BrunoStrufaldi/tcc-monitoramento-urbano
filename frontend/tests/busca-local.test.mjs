import test from "node:test";
import assert from "node:assert/strict";
import { distanciaMetros, pontosNoRaio, formatarDistancia, nomeCurtoDoLocal, resultadoNaCapital, urlBuscaEndereco } from "../dist/busca-local.js";

const MASP = { latitude: -23.5614, longitude: -46.6559 };

test("só entram os eventos a até 1,5 km, do mais perto para o mais longe", () => {
  const eventos = [
    { id: 1, latitude: -23.5650, longitude: -46.6520 }, // uns 550 m
    { id: 2, latitude: -23.5630, longitude: -46.6559 }, // uns 180 m
    { id: 3, latitude: -23.5614, longitude: -46.6559 }, // no próprio ponto
    { id: 4, latitude: -23.5505, longitude: -46.6333 }, // Praça da Sé, mais de 2 km
  ];
  const resultado = pontosNoRaio(eventos, MASP);
  assert.deepEqual(resultado.map((item) => item.ponto.id), [3, 2, 1]);
  assert.ok(Math.abs(distanciaMetros(MASP, eventos[1]) - 178) < 5);
  assert.ok(distanciaMetros(MASP, eventos[3]) > 1500);
  assert.equal(formatarDistancia(178.4), "178 m");
  assert.equal(formatarDistancia(1500), "1,5 km");
});

test("a busca fica presa à cidade de São Paulo e o nome é encurtado", () => {
  // O retângulo da cidade pega um pedaço de Guarulhos, que tem outra Rua Augusta.
  const guarulhos = { lat: "-23.48", lon: "-46.54", display_name: "Rua Augusta, Guarulhos", address: { city: "Guarulhos" } };
  const capital = { lat: "-23.55", lon: "-46.65", display_name: "Rua Augusta, Consolação", address: { city: "São Paulo" } };
  assert.equal(resultadoNaCapital([guarulhos, capital]), capital);
  assert.equal(resultadoNaCapital([guarulhos]), null);

  const url = new URL(urlBuscaEndereco("  Avenida Paulista "));
  assert.equal(url.hostname, "nominatim.openstreetmap.org");
  assert.equal(url.searchParams.get("q"), "Avenida Paulista");
  assert.equal(url.searchParams.get("bounded"), "1");
  assert.ok(url.searchParams.get("viewbox"));
  assert.equal(nomeCurtoDoLocal("Avenida Paulista, Bela Vista, São Paulo, Região Imediata de São Paulo, Brasil"), "Avenida Paulista, Bela Vista");
});
