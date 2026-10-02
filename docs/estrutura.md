# Estrutura do repositório

[← voltar ao README](../README.md#documentação)

## 3. Estrutura de diretórios

```text
TCC-Atualizado/
├── README.md                     visão geral + mapa da documentação
├── ROADMAP.md                    roteiro de melhorias (checklist com commits)
├── docs/                         documentação detalhada, um arquivo por assunto (§3–§21)
├── package.json                  build/test do frontend (tsc + node:test)
├── start.ps1                     sobe a API, que também serve o painel, em http://localhost:8000
├── Dockerfile                    imagem única API + painel + YOLO (CPU) para o Cloud Run — §21
├── deploy.ps1                    deploy manual no Cloud Run (build a partir da pasta local)
├── cloudbuild.yaml               deploy automático: gatilho a cada push na main do GitHub
├── .dockerignore / .gcloudignore o que fica fora da imagem (venv, datasets, .env, pesos extras)
│
├── backend/
│   ├── requirements.txt          FastAPI, SQLAlchemy, Pydantic, Pillow, pytest…
│   ├── requirements-yolo.txt     + ultralytics (só na máquina que roda/treina o modelo)
│   ├── .env.example              todas as variáveis, com o racional de cada uma
│   ├── app/
│   │   ├── main.py               app FastAPI, lifespan, loop de manutenção (120 s)
│   │   ├── config.py             Settings (pydantic-settings) — fonte única de configuração
│   │   ├── database.py           engine, SessionLocal, Base, PRAGMA WAL para SQLite
│   │   ├── broadcast.py          agenda coroutines no loop principal a partir de threads
│   │   ├── ws_manager.py         ConnectionManager + WSMessage (protocolo WebSocket)
│   │   ├── models/               8 models SQLAlchemy (um arquivo por entidade)
│   │   ├── schemas/              schemas Pydantic (Literal[] para enums)
│   │   ├── routers/              11 routers (ver §7)
│   │   ├── services/
│   │   │   ├── live_detection.py        detecção contínua de TRÂNSITO (thread/câmera)
│   │   │   ├── flood_detection.py       detecção contínua de ALAGAMENTO (thread/câmera)
│   │   │   ├── detection_events.py      persiste evento + evidência e faz o broadcast
│   │   │   ├── event_retention.py       purga, colapsa duplicados
│   │   │   ├── data_fusion_service.py   ponte app ↔ data_fusion; promove/rebaixa status
│   │   │   ├── cet_camera_catalog.py    catálogo das 10 câmeras + checagem de frescor
│   │   │   ├── tomtom_traffic_source.py velocidade atual × livre do trecho
│   │   │   ├── weather_source.py        Open-Meteo (clima e qualidade do ar)
│   │   │   ├── inmet_alert_source.py    avisos meteorológicos oficiais ativos
│   │   │   └── evidence_annotation.py   desenha as caixas YOLO sobre a evidência
│   │   └── data/evidencias/      JPEGs gravados em runtime (fora do git)
│   └── tests/                    165 testes pytest (SQLite em memória)
│
├── data_fusion/                  motor de confiabilidade (puro Python, sem FastAPI)
│   ├── fusion.py                 combinação ponderada das dimensões
│   ├── scores.py                 pontuação por dimensão e por tipo de evento
│   ├── models.py                 dataclasses de entrada/saída
│   ├── historico_alagamento.py   prior espacial estático (lookup local, sem rede)
│   ├── data/pontos_alagamento_sp.json   20 pontos CGE-SP/GeoSampa
│   ├── test_fusion.py            `python -m data_fusion.test_fusion`
│   └── test_historico_alagamento.py
│
├── ml/
│   ├── detector.py               carrega os DOIS modelos YOLO, normaliza classes
│   ├── train_incident_model.py   inspect/download/merge/train do modelo de alagamento
│   ├── collect_negatives.py      coleta frames CET-SP como negativos de treino
│   ├── models/                   pesos .pt (fora do git)
│   ├── datasets/ · runs/         datasets e runs de treino (fora do git)
│
├── database/
│   ├── schema.sql                DDL MySQL das 7 tabelas + seed mínimo
│   └── migrations/               001…005 (ver §6)
│
└── frontend/
    ├── index.html                SPA com ARIA: painel de eventos, testador YOLO, overlays
    ├── css/style.css             design tokens, dark theme sólido
    ├── js/config.js              API_BASE_URL (= window.location.origin), centro/zoom do mapa
    ├── src/                      TypeScript fonte
    │   ├── app.ts                aplicação inteira (mapa, tempo real, YOLO, fusão)
    │   └── fusion-format.ts      formatação e limiar de promoção (espelha o backend)
    ├── dist/                     saída do `tsc` (versionada)
    └── tests/                    testes node:test do módulo puro de formatação
```
