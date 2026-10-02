# Roteiro de melhorias (análise de 01/10/2026)

Checklist gerado a partir de uma varredura completa do projeto. Marque `[x]` ao
concluir cada item e anote o commit. Ao iniciar um chat novo, peça:
"continue o ROADMAP.md, item X".

**Regra de entrega:** toda resposta final, depois de concluir um trabalho, termina com um
resumo em duas partes:
- **O que foi feito:** itens concluídos nesta sessão (com o commit).
- **O que ainda falta:** próximos itens não marcados deste roteiro.

Estado na análise: 171 testes backend + 14 data_fusion + frontend passando.
Comandos de teste:
- `backend\venv\Scripts\python.exe -m pytest -q` (dentro de `backend/`)
- `backend\venv\Scripts\python.exe -m pytest -q data_fusion` (na raiz)
- `npm run test:frontend` / `npm run build:frontend` (na raiz)

---

## 0. Antes de tudo
- [x] (`af9665b`) Commitar as mudanças pendentes do Data Fusion (peso flexível por concordância:
      `data_fusion/*`, `backend/app/routers/fusion.py`, `schemas/fusion.py`,
      `frontend/src/app.ts`, `fusion-format.ts`, `ml/detector.py` com TTA).

## 1. Código morto (deletar) — concluído em 02/10/2026

- [x] (`4c1aa46`) Scripts e dependências: `reset_mysql.*`, `cleanup_demo_data.py`,
      `migrate_yolo_observations.py`, `pyproj`, `python-dotenv`
- [x] (`8958b3d`) Backend: `/deteccao/simular`, `/video`, `/frame`, `/confirmar`, `/ws/cv`,
      `visual_validation.py` (+ configs `YOLO_MAX_FPS/FRAME/COOLDOWN`), simulação e classe
      `hidrante` em `ml/detector.py`, model `OcorrenciaExterna`, status `resolvido`/`resolvido_em`
      (migração `006`), schemas `EventoCreate/Update` e `EvidenciaVisualCreate`, `_fonte_yolo`.
      `benchmark_latencia.py` agora mede o caminho real (frame → YOLO → evento → WebSocket).
- [x] (`69149fb`) Frontend: 6 telas inalcançáveis, drawer de detalhe (decisão: apagar), blocos
      "Alertas"/"Atividade" (contêineres inexistentes), busca (decisão: apagar), filtro de
      severidade (seção com `display:none`), `refreshFeeds`, módulos `event-detail-format` e
      `event-actions-format`, `initMapa` sem duplicação. `app.ts` 2505 → 1407 linhas,
      `style.css` 3455 → 2394. Conferido no Chrome (desktop e celular), sem erros no console.
- [x] Arquivos locais apagados: `gx.db` da raiz, `notificacoes-urbanas/`, `weights/`, `backend/ml/`,
      `ml/models/yolo11n.pt` (pesos públicos, rebaixáveis).
- [x] Decidido: `ml/models/gx-incident-anterior.pt` **fica** — é o backup de rollback que
      `ml/train_incident_model.py` cria a cada treino (README §16). Os gráficos que importam para
      o TCC estão em `ml/runs/` (treino atual + validação atual × anterior), que também fica.
- [x] Apagados (com permissão pontual em `.claude/settings.local.json`, removida depois):
      `runs/` da raiz (validações de 26/08 das tentativas v3/v4), `ml/models/gx-incident-v3-backup.pt`
      e `ml/models/gx-incident-v4-attempt.pt`.
- [x] (`9e12700`, `ed3f180`) Ramos mortos de `data_fusion/scores.py` e fontes "Painel manual"/
      "Open-Meteo" do seed — resolvidos junto com o 3a.

### Observação encontrada no teste visual (não corrigida)
- No celular (390px) o relógio do topo fica cortado na borda direita. Já acontecia antes da limpeza.

## 2. Rápido, baixo risco — concluído em 02/10/2026
- [x] (`204b97c`) **Segurança:** `/regioes`, `/fontes`, `/localizacoes` e `/dados-contextuais`
      só com GET; `POST /fusion/recalcular-todos` removido; schemas `*Create/*Update` apagados.
      Testes montam os dados direto no banco e checam o 405. Ficou `POST /fusion/eventos/{id}/
      recalcular` (não injeta dado, só refaz o que o ciclo de 2 min já faz) e os uploads do
      testador YOLO (`/deteccao/imagem|incidente`, isolados do pipeline de evento).
- [x] (`faccaef`) `app/broadcast.py`: `coro.close()` sem loop — 55 warnings → 1 (do httpx/starlette).
- [x] (`20a9c81`, `5bb3904`) `aplicar_fusao_evento` grava `LogSistema` só quando promove/rebaixa.
- [x] (`8fd401a`) `CLASSES_URBANAS`: `tipo` = `"alagamento"`/`"transito"`; saíram o `replace` do
      `flood_detection.py` e o `tipo="transito"` forçado do `live_detection.py`.
- [x] (`24df76f`) Nomes legados → MotSP (título/descrição da API, User-Agent, docstrings,
      docstring de `routers/evidencias.py` no topo). O `aria-label` do mapa já estava certo.
- [x] (`7c493f6`) Dev em processo único: `GX_SERVE_FRONTEND` = `true` por padrão; `config.js`
      versionado com `window.location.origin` (saíram `config.example.js` e `config.prod.js`, e
      a exclusão dele em `.gitignore`/`.dockerignore`/`.gcloudignore`); `start.ps1` só sobe o
      uvicorn em :8000; `CORS_ORIGINS` vazio por padrão; `serve:frontend` removido.
      Efeito colateral: com o painel montado em `/`, POST em rota inexistente dá 405, não 404.
      Seu `backend/.env` ainda tem `CORS_ORIGINS` com a porta 5500 — inofensivo, pode apagar.
- [x] (`53b9744`) README: tabela "Números atuais" removida.

Estado depois do item 2: 146 testes backend + 14 data_fusion + 2 frontend passando.
Itens 0–2 publicados no Cloud Run em 02/10/2026 (revisão `motsp-00011-85j`, conferida).

## 3. Mais trabalhoso
- [x] **(a) Data Fusion honesto — opção B (2 dimensões), concluído em 02/10/2026.**
      (`9e12700`) `PESOS` = IA 4/7 (57%) + contexto 3/7 (43%) — os pesos efetivos que já valiam;
      sai a dimensão `fonte_oficial` (`FonteInfo`, `pontuar_fonte_oficial`); "clima" → "contexto"
      no núcleo, na API e no painel; HTML/JS servidos com `no-cache`. Scores idênticos em 620
      cenários (descoberta: 0,0 mm/h de chuva conta como "sem sinal" — mantido e comentado).
      (`624e443`) `categoria` dos dados contextuais `clima` → `contexto`, com `UPDATE` idempotente
      no startup + migração `007` para o MySQL. (`ed3f180`) seed e README §12.
      Conferido ponta a ponta local: evento gravado com a categoria antiga dá o mesmo 0,7805.
- [~] **(b) Removido do roteiro em 02/10/2026** — era unificar `live_detection.py` +
      `flood_detection.py` (uma thread por câmera, download único). Ganho pequeno: o custo está na
      inferência, que continuaria igual (2 modelos por frame); 10 downloads/min a mais e 20 threads
      dormindo são irrelevantes. Risco alto: mexe nas únicas peças que criam evento, os testes
      simulam câmera/YOLO/TomTom, e uma falha deixaria o painel vazio em silêncio. Não refazer.
- [~] **(c) Removido em 02/10/2026** — era tirar o SSE. Ele é o plano B para redes que bloqueiam
      WebSocket; sem ele essas redes caem direto no polling de 30 s. ~150 linhas no total, e as
      chamadas `_broadcast` + `ws_manager.broadcast_evento` são uma por canal, não duplicação.
- [x] (`e634502`) **(d) Config única — só a parte de config:** mover `GX_YOLO_MODEL`, `GX_YOLO_IMGSZ`,
      `GX_YOLO_TTA`, `GX_YOLO_MAX_CONCORRENCIA`, `GX_YOLO_INCIDENT_MODEL` de `os.getenv`
      (`ml/detector.py`) para `Settings` — hoje o `backend/.env` não chega neles localmente (só
      funciona por coincidência com o caminho padrão); remover `GX_YOLO_CLASS_MAPPING`.
      **Não** unir `detectar_imagem_real` e `detectar_incidentes_imagem` (mesma área sensível do 3b).
      Feito com caminho relativo resolvido a partir da raiz (o `.env` tem `ml/models/gx-incident.pt`
      e o uvicorn sobe de `backend/` — sem isso o alagamento parava localmente). Resolução idêntica
      à anterior com e sem `.env`; os dois pesos carregam e inferem numa imagem real.
- [~] **(e) Removido em 02/10/2026** — MySQL × SQLite não é questão técnica: `schema.sql` e as
      migrações sustentam o MySQL se o TCC citar. Só corrigir no README (3h) que a produção no
      Cloud Run usa SQLite.
- [~] **(f) Removido em 02/10/2026** — regiões: remover mexe em tabela/FKs/testes só por limpeza;
      associar câmera→região seria funcionalidade nova. A tabela parada não atrapalha.
- [~] **(g) Removido em 02/10/2026** — quebrar `app.ts` (1407 linhas, quase sem teste de UI) arrisca
      quebrar a tela sem aviso por ganho só de organização. Reavaliar só se a banca for ler o front.
- [ ] **(h) README em duas camadas:** README curto + `docs/` com detalhes; §19 vira apêndice. Corrigir
      no caminho: "MySQL em produção" (é SQLite no Cloud Run) e a nota sobre `os.getenv` (§21.5).
- [ ] **Relógio do topo cortado no celular (390px)** — ver observação no item 1.

## Ordem sugerida
0 → 1 + itens 2 → 3a → 3d → 3h → relógio. (3b, 3c, 3e, 3f e 3g removidos — ver motivos.)
