# Estrutura do repositório

[← voltar ao README](../README.md#documentação)

## 3. Estrutura de diretórios

```text
TCC-Atualizado/
├── README.md                     visão geral e mapa da documentação
├── docs/                         documentação detalhada, um arquivo por assunto (§3 a §22)
├── package.json                  build e testes do frontend (tsc + node:test)
├── start.ps1                     sobe a API, que também serve o painel, em http://localhost:8000
├── Dockerfile                    imagem com API, painel e YOLO (CPU) para o Cloud Run (§21)
├── deploy.ps1                    deploy manual no Cloud Run (a partir da pasta local)
├── cloudbuild.yaml               deploy automático a cada push na main do GitHub
├── .dockerignore / .gcloudignore o que fica fora da imagem (venv, datasets, .env, modelos extras)
│
├── backend/
│   ├── requirements.txt          FastAPI, SQLAlchemy, Pydantic, Pillow, pytest…
│   ├── requirements-yolo.txt     ultralytics (só na máquina que roda ou treina o modelo)
│   ├── .env.example              todas as variáveis, com uma explicação curta de cada uma
│   ├── app/
│   │   ├── main.py               app FastAPI, início e fim, liga o monitoramento
│   │   ├── config.py             Settings (pydantic-settings), onde fica toda a configuração
│   │   ├── database.py           engine, SessionLocal, Base e PRAGMA WAL para o SQLite
│   │   ├── broadcast.py          agenda tarefas no loop principal a partir das threads
│   │   ├── ws_manager.py         ConnectionManager e WSMessage (protocolo WebSocket)
│   │   ├── models/               7 models SQLAlchemy (um arquivo por entidade)
│   │   ├── schemas/              schemas Pydantic (Literal[] para os enums)
│   │   ├── routers/              11 routers (ver §7)
│   │   ├── services/
│   │   │   ├── ciclo_monitoramento.py   olha as câmeras (com evento a cada 10 min, sem evento a cada 60 s) e cria, atualiza ou apaga eventos
│   │   │   ├── live_detection.py        regras de trânsito aplicadas a uma imagem
│   │   │   ├── flood_detection.py       regras de alagamento aplicadas a uma imagem
│   │   │   ├── detection_events.py      grava evento e evidência e avisa o painel
│   │   │   ├── event_retention.py       apaga eventos velhos e junta os repetidos
│   │   │   ├── data_fusion_service.py   liga o app ao data_fusion e muda o status
│   │   │   ├── cet_camera_catalog.py    catálogo das 10 câmeras e checagem de imagem travada
│   │   │   ├── tomtom_traffic_source.py velocidade atual e normal do trecho
│   │   │   ├── weather_source.py        Open-Meteo (clima e qualidade do ar)
│   │   │   ├── inmet_alert_source.py    avisos meteorológicos oficiais
│   │   │   └── evidence_annotation.py   desenha as caixas do YOLO na evidência
│   │   └── data/evidencias/      imagens gravadas durante a execução (fora do Git)
│   └── tests/                    testes pytest (SQLite em memória)
│
├── data_fusion/                  cálculo da confiabilidade (Python puro, sem FastAPI)
│   ├── fusion.py                 combina as dimensões com os pesos
│   ├── scores.py                 nota de cada dimensão, por tipo de evento
│   ├── models.py                 dataclasses de entrada e saída
│   ├── historico_alagamento.py   histórico de alagamento das vias (arquivo local, sem rede)
│   ├── data/pontos_alagamento_sp.json   20 pontos do CGE-SP e do GeoSampa
│   ├── test_fusion.py            `python -m data_fusion.test_fusion`
│   └── test_historico_alagamento.py
│
├── ml/
│   ├── detector.py               carrega os dois modelos do YOLO e traduz as classes
│   ├── train_vehicle_model.py    ajusta o modelo de veículos às câmeras da CET
│   ├── train_incident_model.py   inspect/download/merge/train do modelo de alagamento
│   ├── collect_negatives.py      baixa imagens das câmeras sem alagamento para o treino
│   ├── models/                   modelos .pt (só os 3 que o sistema usa vão para o Git)
│   ├── datasets/ · runs/         datasets e resultados de treino (fora do Git)
│
├── database/
│   ├── schema.sql                DDL MySQL das 6 tabelas e dados iniciais mínimos
│   └── migrations/               001 a 008 (ver §6)
│
└── frontend/
    ├── index.html                página única com ARIA: painel de eventos, mapa
    ├── css/style.css             design tokens e tema escuro
    ├── js/config.js              API_BASE_URL (= window.location.origin), centro e zoom do mapa
    ├── src/                      código TypeScript
    │   ├── app.ts                o painel inteiro (mapa, tempo real, YOLO, Data Fusion)
    │   ├── busca-local.ts        busca por rua: distância e eventos a até 1,5 km
    │   └── fusion-format.ts      formatação e limite de promoção (igual ao backend)
    ├── dist/                     saída do `tsc` (vai para o Git)
    └── tests/                    testes node:test da formatação e da busca por rua
```
