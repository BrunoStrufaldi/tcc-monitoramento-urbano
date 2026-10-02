# MotSP — Monitoramento Urbano de São Paulo

Sistema de detecção e monitoramento de eventos urbanos em tempo real, desenvolvido como TCC.
O sistema observa câmeras públicas da CET-SP com visão computacional (YOLO), cruza o que
vê com fontes de dados independentes (trânsito, clima, avisos oficiais, histórico de
alagamento da via) e publica no painel apenas o que sobrevive a esse cruzamento.

> A documentação tem duas camadas: este README é a visão geral (o que o sistema faz, como
> ele se encaixa e como rodar), e os detalhes de cada parte estão em `docs/`. As seções
> mantêm a numeração (§1–§21) em todos os arquivos. Se você é um agente/LLM lendo o
> repositório pela primeira vez: leia este README e depois o arquivo de `docs/` da parte
> que vai tocar.

---

## Documentação

| § | Assunto | Onde |
|---|---|---|
| §1 | [O que o sistema faz (e o que ele não faz)](#1-o-que-o-sistema-faz-e-o-que-ele-não-faz) | este arquivo |
| §2 | [Arquitetura e fluxo de dados](#2-arquitetura-e-fluxo-de-dados) | este arquivo |
| §3 | [Estrutura de diretórios](docs/estrutura.md#3-estrutura-de-diretórios) | `docs/estrutura.md` |
| §4 | [Como rodar](#4-como-rodar) | este arquivo |
| §5 | [Configuração (`.env`)](docs/configuracao.md#5-configuração-env) | `docs/configuracao.md` |
| §6 | [Banco de dados](docs/banco-de-dados.md#6-banco-de-dados) | `docs/banco-de-dados.md` |
| §7 | [API HTTP](docs/api-e-tempo-real.md#7-api-http) | `docs/api-e-tempo-real.md` |
| §8 | [Tempo real: WebSocket, SSE e polling](docs/api-e-tempo-real.md#8-tempo-real-websocket-sse-e-polling) | `docs/api-e-tempo-real.md` |
| §9 | [Visão computacional (YOLO)](docs/deteccao.md#9-visão-computacional-yolo) | `docs/deteccao.md` |
| §10 | [Detecção contínua de trânsito](docs/deteccao.md#10-detecção-contínua-de-trânsito) | `docs/deteccao.md` |
| §11 | [Detecção contínua de alagamento](docs/deteccao.md#11-detecção-contínua-de-alagamento) | `docs/deteccao.md` |
| §12 | [Data Fusion (confiabilidade)](docs/data-fusion.md#12-data-fusion-confiabilidade) | `docs/data-fusion.md` |
| §13 | [Ciclo de vida de um evento](docs/data-fusion.md#13-ciclo-de-vida-de-um-evento) | `docs/data-fusion.md` |
| §14 | [Fontes de dados externas](docs/deteccao.md#14-fontes-de-dados-externas) | `docs/deteccao.md` |
| §15 | [Frontend](docs/frontend.md#15-frontend) | `docs/frontend.md` |
| §16 | [Treino do modelo de alagamento](docs/treino-do-modelo.md#16-treino-do-modelo-de-alagamento) | `docs/treino-do-modelo.md` |
| §17 | [Testes](docs/testes-e-seguranca.md#17-testes) | `docs/testes-e-seguranca.md` |
| §18 | [Segurança e limitações](docs/testes-e-seguranca.md#18-segurança-e-limitações) | `docs/testes-e-seguranca.md` |
| §19 | [Decisões de escopo (o que foi removido e por quê)](docs/apendice-decisoes-de-escopo.md#19-decisões-de-escopo-o-que-foi-removido-e-por-quê) | `docs/apendice-decisoes-de-escopo.md` |
| §20 | [Referências técnicas](docs/apendice-referencias.md#20-referências-técnicas) | `docs/apendice-referencias.md` |
| §21 | [Deploy no Google Cloud Run](docs/deploy.md#21-deploy-no-google-cloud-run) | `docs/deploy.md` |

Testes: `cd backend; venv\Scripts\python -m pytest -q` (backend), `npm run test:frontend`
(painel) e `python -m pytest -q data_fusion` na raiz — detalhes em [§17](docs/testes-e-seguranca.md#17-testes).

---

## 1. O que o sistema faz (e o que ele não faz)

### Faz

- **Detecta sozinho.** Threads de monitoramento baixam periodicamente o snapshot JPEG de
  10 câmeras públicas da CET-SP e rodam YOLO em cima. Dois tipos de evento urbano estão
  no escopo: **trânsito** (congestionamento) e **alagamento**.
- **Cruza com fontes independentes.** Nenhum evento nasce só do que a câmera viu. Trânsito
  é arbitrado pela velocidade real do trecho (TomTom Traffic API); alagamento é corroborado
  por chuva medida (Open-Meteo), aviso oficial ativo (INMET) e o histórico de alagamento
  daquela via (CGE-SP/GeoSampa, camada estática).
- **Pontua a confiabilidade.** O módulo Data Fusion combina duas dimensões, IA (57%) e
  contexto (43%), num score 0–1. Um evento só é promovido a `ativo` no painel quando
  cruza o limiar (padrão 77%); abaixo disso fica `em_analise`.
- **Publica em tempo real.** Toda criação, atualização e remoção de evento é transmitida
  por WebSocket, com fallback automático para SSE e depois polling.
- **Expira sozinho.** "Tempo real" é literal: um evento vive no máximo 45 minutos após a
  última detecção. Passou disso, é apagado do banco e removido do painel.

### Não faz

- **Não notifica ninguém.** Não há e-mail, SMS, push ou webhook. O sistema detecta e mostra
  no painel; avisar terceiros nunca foi implementado (a tabela `notificacoes` foi removida
  na migração `005` — nada jamais a preencheu).
- **Não tem login.** Sem usuários, perfis, sessão ou trilha por operador (removido na
  migração `003`). Os eventos nascem de câmera, não de gente.
- **Não aceita registro manual de ocorrência.** O painel é somente leitura: não existe rota
  que crie, altere ou remova evento/evidência por requisição de operador. Evento só nasce
  da detecção contínua nas câmeras.
- **Não detecta buraco, incêndio, lixo, árvore caída ou vazamento.** Todas essas classes
  saíram do escopo (ver [§19](docs/apendice-decisoes-de-escopo.md#19-decisões-de-escopo-o-que-foi-removido-e-por-quê)).
- **Não usa dado em lote.** Fontes que republicam ocorrências semanas ou anos depois
  (GeoSampa/Defesa Civil como gatilho) foram removidas: o evento saía carimbado com o
  horário em que o sistema notou o registro, não com o horário do incidente.

---

## 2. Arquitetura e fluxo de dados

```text
        ┌──────────────────────── FONTES AO VIVO ────────────────────────┐
        │                                                                │
  Câmeras CET-SP          TomTom Traffic       Open-Meteo        INMET avisos
  (10 snapshots JPEG)     (velocidade via)     (chuva, AQI)      (aviso oficial)
        │                        │                  │                  │
        ▼                        │                  │                  │
  ┌───────────────────────────┐  │                  │                  │
  │ live_detection.py         │  │                  │                  │
  │  YOLO11m COCO → contagem  │◄─┘                  │                  │
  │  de veículos              │                     │                  │
  ├───────────────────────────┤                     │                  │
  │ flood_detection.py        │◄────────────────────┴──────────────────┘
  │  gx-incident.pt →         │
  │  classe "alagamento"      │      + data_fusion/historico_alagamento.py
  └───────────┬───────────────┘        (prior espacial ESTÁTICO, lookup local)
              │
              ▼
   ┌────────────────────────────────────────────────┐
   │ detection_events.registrar_deteccao()          │
   │  · grava JPEG original + cópia com caixas YOLO │
   │  · SHA-256 do original (auditoria)             │
   │  · cria Localizacao + Evento (em_analise)      │
   │  · cria EvidenciaVisual                        │
   │  · grava DadoContextual (contexto/índices)     │
   └───────────┬────────────────────────────────────┘
               │
               ▼
   ┌────────────────────────────────────────────────┐
   │ data_fusion/  ──►  confiabilidade 0..1         │
   │  IA 57% · contexto 43%                         │
   │  ≥ 0,77 → status vira "ativo"                  │
   └───────────┬────────────────────────────────────┘
               │
               ▼
   ┌───────────────────────────┐        ┌──────────────────────────────┐
   │ FastAPI (REST + WS + SSE) │───────►│ Frontend TypeScript          │
   │ SQLAlchemy → SQLite/MySQL │        │ Leaflet + GeoSampa WMS       │
   └───────────┬───────────────┘        │ WS ─► SSE ─► polling (15s)   │
               │                        └──────────────────────────────┘
               ▼
   ┌────────────────────────────────────────────────┐
   │ event_retention (loop a cada 120 s)            │
   │  · purga eventos fora da janela de 45 min      │
   │  · colapsa duplicados no mesmo ponto           │
   │  · promove/rebaixa por confiabilidade          │
   └────────────────────────────────────────────────┘
```

**Princípio central do projeto:** o YOLO produz *evidência*, não *veredito*. A decisão de
mostrar um evento como real vem sempre do cruzamento no Data Fusion.

---

## 4. Como rodar

### Pré-requisitos

- **Python 3.11+**
- **Node.js 18+** (apenas para compilar o TypeScript)
- **MySQL 8.x** opcional — sem `DATABASE_URL` configurada, o sistema usa SQLite local
  (`backend/gx.db`) e cria as tabelas sozinho no startup
- Para inferência real: `backend/requirements-yolo.txt` + os pesos em `ml/models/`
  (`yolo11m.pt` para trânsito, `gx-incident.pt` para alagamento). Esses dois estão no git:
  o deploy automático builda a imagem a partir do GitHub.

### Caminho rápido (Windows)

```powershell
.\start.ps1
```

Sobe o uvicorn numa janela do PowerShell e abre o navegador em `http://localhost:8000`.
Um processo só: o FastAPI serve a API e o painel (`frontend/`) na mesma origem, igual ao
container.

> `start.ps1` chama o uvicorn direto, **sem exportar variável de ambiente nenhuma**. Toda
> configuração precisa estar em `backend/.env` — é por isso que `config.py` é a única
> leitora de configuração no projeto (ver a nota sobre `TOMTOM_API_KEY` em [§5](docs/configuracao.md#5-configuração-env)).

### Caminho manual

```bash
# 1) Frontend (compilar TypeScript)
npm install
npm run build:frontend          # src/ → dist/

# 2) Backend
cd backend
python -m venv venv
venv\Scripts\activate           # Windows
pip install -r requirements.txt
copy .env.example .env          # e edite
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000   # painel em http://localhost:8000
```

### Inferência YOLO real

```bash
cd backend
venv\Scripts\python -m pip install -r requirements-yolo.txt
```

Coloque os pesos em `ml/models/` e confirme com `GET /deteccao/status` antes de enviar
imagens. Sem os pesos, a API responde indisponibilidade explicitamente em vez de fingir
que detectou algo.

### Ligar o monitoramento automático

Desligado por padrão, **inclusive nos testes** (evita threads de rede real subindo sozinhas).
No `.env`:

```env
GX_MONITORAMENTO_ATIVO=true
GX_TRANSITO_MONITORAR_CATALOGO=true      # 10 threads de trânsito
GX_ALAGAMENTO_MONITORAR_CATALOGO=true    # 10 threads de alagamento (exige gx-incident.pt)
TOMTOM_API_KEY=...                       # sem ela, parte da lógica de trânsito degrada
```

---

## Licença

Projeto acadêmico — TCC. Uso educacional.
