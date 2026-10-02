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
- [ ] **Apagar manualmente** (a exclusão automática foi bloqueada por ser irreversível):
      `runs/` da raiz (validações de 26/08 das tentativas v3/v4), `ml/models/gx-incident-v3-backup.pt`
      e `ml/models/gx-incident-v4-attempt.pt`.
- [ ] **Movido para o 3a:** ramos mortos de `data_fusion/scores.py` (fontes `api/sensor/manual/
      data_fusion`, chaves `precipitacao`/`congestionamento`) e as fontes "Painel manual" e
      "Open-Meteo" do `backend/seed.py` — estão presos à dimensão "fonte oficial", que o 3a redesenha.

### Observação encontrada no teste visual (não corrigida)
- No celular (390px) o relógio do topo fica cortado na borda direita. Já acontecia antes da limpeza.

## 2. Rápido, baixo risco
- [ ] **Segurança:** remover POST/PATCH/DELETE públicos de `/regioes`, `/fontes`, `/localizacoes`,
      `/dados-contextuais` e `POST /fusion/recalcular-todos` (sem login no Cloud Run, qualquer um
      injeta dado "clima" e promove evento a ativo). Manter só GET.
- [ ] `app/broadcast.py`: `coro.close()` quando não há loop (elimina 55 warnings "never awaited")
- [ ] `data_fusion_service.aplicar_fusao_evento`: gravar `LogSistema` só quando o status mudar
      (hoje grava 1 log por evento aberto a cada 2 min, e logs nunca são purgados)
- [ ] `CLASSES_URBANAS`: `tipo` = `"alagamento"`/`"transito"` direto; remover os `replace(..., tipo=...)`
      em `flood_detection.py` e o `tipo="transito"` forçado em `live_detection.py`
- [ ] Nomes legados: título "Notificações Urbanas" (`main.py`), `aria-label="Mapa Google Maps"`
      (é Leaflet/GeoSampa), User-Agent "GX-TCC", "notificações" na docstring de `event_retention.py`,
      docstring após import em `routers/evidencias.py`
- [ ] Dev em processo único: `GX_SERVE_FRONTEND=true` local, `config.js` = `window.location.origin`,
      simplificar `start.ps1` (tirar `C:\Python314` fixo e o `http.server 5500`)
- [ ] README: remover a tabela "Números atuais" (já desatualizada)

## 3. Mais trabalhoso
- [ ] **(a) Data Fusion honesto.** Todo evento tem fonte `yolo` → `fonte_oficial` sempre 0 → pesos
      reais são IA 57% / contexto 43%. INMET (fonte oficial de verdade) está dentro de "clima", e
      "clima" também guarda índice de trânsito.
      Opção A (recomendada): IA / medição ao vivo (Open-Meteo, TomTom) / fonte oficial (INMET);
      renomear "clima" → "contexto". Opção B: assumir 2 dimensões. Atualizar front (`PESO_BASE_FUSAO`) e README §12.
- [ ] **(b) Unificar `live_detection.py` + `flood_detection.py`:** uma thread por câmera, baixa o
      frame uma vez e roda os dois modelos (hoje 20 threads e download duplo).
- [ ] **(c) Tempo real com 2 canais:** WebSocket + polling; remover SSE (`routers/tempo_real.py`,
      chamadas `_broadcast` duplicadas, `fallbackToSSE` no front).
- [ ] **(d) Config única:** mover `GX_YOLO_MODEL`, `GX_YOLO_IMGSZ`, `GX_YOLO_TTA`,
      `GX_YOLO_MAX_CONCORRENCIA`, `GX_YOLO_INCIDENT_MODEL` de `os.getenv` (`ml/detector.py`) para
      `Settings`; remover `GX_YOLO_CLASS_MAPPING`; unir `detectar_imagem_real` e `detectar_incidentes_imagem`.
- [ ] **(e) MySQL × SQLite:** produção usa SQLite. Se MySQL não for exigência, manter `schema.sql`
      só como documentação e remover migrações/pymysql.
- [ ] **(f) Regiões:** `regiao_id` nunca é preenchido. Associar câmera→região ou remover tabela/rota/seed.
- [ ] **(g) Quebrar `frontend/src/app.ts`** em módulos (realtime, map, detail-drawer, yolo-tester, fusion-panel).
- [ ] **(h) README em duas camadas:** README curto + `docs/` com detalhes; §19 vira apêndice.

## Ordem sugerida
0 → 1 + itens 2 → 3a → 3b + 3c → resto.
