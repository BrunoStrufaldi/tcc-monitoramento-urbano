let mapa = null;
let infoWindowAberta = null;
const marcadoresPorId = new Map();
let eventosCarregados = [];

const filtrosCriticidade = new Set(Object.keys(CRITICIDADE));

function escapeHtml(texto) {
  if (texto == null) return "";
  return String(texto)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function carregarGoogleMaps() {
  if (typeof GOOGLE_MAPS_API_KEY === "undefined" || GOOGLE_MAPS_API_KEY === "SUA_CHAVE_AQUI") {
    atualizarStatusApi(false, "Configure a chave do Maps");
    document.getElementById("lista-eventos").innerHTML =
      '<li class="empty-state">Defina <code>GOOGLE_MAPS_API_KEY</code> em <code>js/config.js</code></li>';
    return;
  }
  const script = document.createElement("script");
  script.src = `https://maps.googleapis.com/maps/api/js?key=${GOOGLE_MAPS_API_KEY}&callback=initMapa`;
  script.async = true;
  script.defer = true;
  document.body.appendChild(script);
}

function atualizarStatusApi(ok, mensagem) {
  const el = document.getElementById("status-api");
  el.textContent = mensagem;
  el.classList.toggle("ok", ok);
  el.classList.toggle("erro", !ok);
}

async function buscarEventos() {
  const params = new URLSearchParams({ limite: "200" });
  const statusEl = document.getElementById("filtro-status");
  if (statusEl && statusEl.value) params.set("status", statusEl.value);
  const resposta = await fetch(`${CONFIG.API_BASE_URL}/eventos?${params}`);
  if (!resposta.ok) throw new Error(`API retornou ${resposta.status}`);
  return resposta.json();
}

function eventoVisivel(evento) {
  return filtrosCriticidade.has(normalizarCriticidade(evento.severidade));
}

function limparMarcadores() {
  marcadoresPorId.forEach((m) => m.setMap(null));
  marcadoresPorId.clear();
}

function criarIconeMarcador(estilo) {
  return {
    path: google.maps.SymbolPath.CIRCLE,
    scale: estilo.escala,
    fillColor: estilo.cor,
    fillOpacity: 0.95,
    strokeColor: "#ffffff",
    strokeWeight: 2,
  };
}

function conteudoInfoWindow(evento) {
  const estilo = obterEstiloCriticidade(evento.severidade);
  const endereco = evento.localizacao?.endereco || evento.localizacao?.bairro || "";
  const regiao = evento.regiao?.nome || "";
  const detectado = evento.detectado_em
    ? new Date(evento.detectado_em).toLocaleString("pt-BR")
    : "";
  const confianca = evento.confianca != null ? `${(Number(evento.confianca) * 100).toFixed(0)}%` : "";

  return `
    <div class="info-window">
      <span class="info-criticidade" style="background:${estilo.cor}">${escapeHtml(rotuloCriticidade(evento.severidade))}</span>
      <h3>${escapeHtml(evento.titulo)}</h3>
      <p class="info-tipo">${escapeHtml(evento.tipo)} · ${escapeHtml(evento.status)}</p>
      ${evento.descricao ? `<p>${escapeHtml(evento.descricao)}</p>` : ""}
      ${confianca ? `<p class="info-confianca">Confiabilidade: ${confianca}</p>` : ""}
      ${endereco ? `<p class="info-endereco">${escapeHtml(endereco)}</p>` : ""}
      ${regiao ? `<p class="info-regiao">${escapeHtml(regiao)}</p>` : ""}
      ${detectado ? `<p class="info-data">${detectado}</p>` : ""}
    </div>
  `;
}

function criarMarcador(evento) {
  const estilo = obterEstiloCriticidade(evento.severidade);
  const marcador = new google.maps.Marker({
    position: { lat: evento.latitude, lng: evento.longitude },
    map: mapa,
    title: `${rotuloCriticidade(evento.severidade)}: ${evento.titulo}`,
    icon: criarIconeMarcador(estilo),
    zIndex: estilo.zIndex,
  });
  marcador.addListener("click", () => {
    if (infoWindowAberta) infoWindowAberta.close();
    infoWindowAberta = new google.maps.InfoWindow({ content: conteudoInfoWindow(evento) });
    infoWindowAberta.open({ anchor: marcador, map: mapa });
    destacarItemLista(evento.id);
  });
  marcadoresPorId.set(evento.id, marcador);
  return marcador;
}

function ajustarBoundsMapa(eventos) {
  if (!eventos.length) return;
  const bounds = new google.maps.LatLngBounds();
  eventos.forEach((e) => bounds.extend({ lat: e.latitude, lng: e.longitude }));
  mapa.fitBounds(bounds, { top: 48, right: 48, bottom: 48, left: 48 });
  const listener = google.maps.event.addListener(mapa, "idle", () => {
    if (mapa.getZoom() > 16) mapa.setZoom(16);
    google.maps.event.removeListener(listener);
  });
}

function renderizarLegenda() {
  const container = document.getElementById("legenda-criticidade");
  if (!container) return;
  container.innerHTML = Object.entries(CRITICIDADE)
    .map(
      ([chave, estilo]) => `
      <label class="legenda-item">
        <input type="checkbox" data-criticidade="${chave}" ${filtrosCriticidade.has(chave) ? "checked" : ""} />
        <span class="legenda-cor" style="background:${estilo.cor}"></span>
        <span>${estilo.label}</span>
      </label>`
    )
    .join("");
  container.querySelectorAll("input[data-criticidade]").forEach((input) => {
    input.addEventListener("change", () => {
      const chave = input.dataset.criticidade;
      if (input.checked) filtrosCriticidade.add(chave);
      else filtrosCriticidade.delete(chave);
      aplicarMarcadoresNoMapa();
      renderizarLista(eventosCarregados);
    });
  });
}

function aplicarMarcadoresNoMapa() {
  limparMarcadores();
  const visiveis = eventosCarregados.filter(eventoVisivel);
  visiveis.forEach(criarMarcador);
  if (visiveis.length) ajustarBoundsMapa(visiveis);
  atualizarContagem(visiveis.length, eventosCarregados.length);
}

function atualizarContagem(visiveis, total) {
  const el = document.getElementById("contagem-eventos");
  if (!el) return;
  el.textContent =
    visiveis === total ? `${total} evento(s) no mapa` : `${visiveis} de ${total} evento(s) no mapa`;
}

function renderizarLista(eventos) {
  const lista = document.getElementById("lista-eventos");
  const visiveis = eventos.filter(eventoVisivel);
  lista.innerHTML = "";
  if (!visiveis.length) {
    lista.innerHTML = '<li class="empty-state">Nenhum evento para os filtros selecionados.</li>';
    return;
  }
  [...visiveis]
    .sort(
      (a, b) =>
        obterEstiloCriticidade(b.severidade).zIndex - obterEstiloCriticidade(a.severidade).zIndex
    )
    .forEach((evento) => {
      const estilo = obterEstiloCriticidade(evento.severidade);
      const li = document.createElement("li");
      li.className = "evento-item";
      li.dataset.id = evento.id;
      li.innerHTML = `
        <div class="evento-cabecalho">
          <span class="crit-badge" style="background:${estilo.cor}">${escapeHtml(estilo.label)}</span>
          <h3>${escapeHtml(evento.titulo)}</h3>
        </div>
        <div class="evento-meta">
          <span class="tag">${escapeHtml(evento.tipo)}</span>
          <span class="tag">${escapeHtml(evento.status)}</span>
          ${evento.regiao ? `<span>${escapeHtml(evento.regiao.nome)}</span>` : ""}
        </div>`;
      li.addEventListener("click", () => {
        mapa.panTo({ lat: evento.latitude, lng: evento.longitude });
        mapa.setZoom(16);
        const marcador = marcadoresPorId.get(evento.id);
        if (marcador) google.maps.event.trigger(marcador, "click");
        destacarItemLista(evento.id);
      });
      lista.appendChild(li);
    });
}

function destacarItemLista(id) {
  document.querySelectorAll(".evento-item").forEach((el) => {
    el.classList.toggle("ativo", Number(el.dataset.id) === id);
  });
}

async function carregarEventos() {
  try {
    eventosCarregados = await buscarEventos();
    aplicarMarcadoresNoMapa();
    renderizarLista(eventosCarregados);
    atualizarStatusApi(true, "Conectado");
  } catch (erro) {
    console.error(erro);
    atualizarStatusApi(false, "Erro na API");
    document.getElementById("lista-eventos").innerHTML =
      '<li class="empty-state">Não foi possível carregar eventos. Verifique se a API está em <code>' +
      escapeHtml(CONFIG.API_BASE_URL) +
      "</code></li>";
  }
}

function initMapa() {
  mapa = new google.maps.Map(document.getElementById("mapa"), {
    center: CONFIG.MAP_CENTER,
    zoom: CONFIG.MAP_ZOOM,
    mapTypeControl: false,
    streetViewControl: false,
    fullscreenControl: true,
    styles: [
      { elementType: "geometry", stylers: [{ color: "#1a2332" }] },
      { elementType: "labels.text.fill", stylers: [{ color: "#8b9cb3" }] },
      { elementType: "labels.text.stroke", stylers: [{ color: "#0f1419" }] },
      { featureType: "road", elementType: "geometry", stylers: [{ color: "#2d3a4f" }] },
      { featureType: "water", elementType: "geometry", stylers: [{ color: "#0f1419" }] },
    ],
  });
  renderizarLegenda();
  document.getElementById("btn-atualizar").addEventListener("click", carregarEventos);
  document.getElementById("filtro-status")?.addEventListener("change", carregarEventos);
  carregarEventos();
  if (CONFIG.REFRESH_INTERVAL_MS > 0) setInterval(carregarEventos, CONFIG.REFRESH_INTERVAL_MS);
}

window.initMapa = initMapa;
carregarGoogleMaps();
