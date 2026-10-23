# MotSP: Monitoramento Urbano de São Paulo

Sistema de detecção e monitoramento de eventos urbanos em tempo real, desenvolvido como TCC.
O sistema observa câmeras públicas da CET-SP com visão computacional (YOLO), confere o
que vê com outras fontes de dados (trânsito, clima, avisos oficiais e histórico de
alagamento da via) e só mostra no painel o que essas fontes confirmam.

> Este README é a visão geral: o que o sistema faz, como as partes se ligam e como rodar.
> Os detalhes de cada parte estão em `docs/`. As seções seguem a mesma numeração (§1 a §21)
> em todos os arquivos.

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
(painel) e `python -m pytest -q data_fusion` na raiz. Detalhes em [§17](docs/testes-e-seguranca.md#17-testes).

---

## 1. O que o sistema faz (e o que ele não faz)

### Faz

- Detecta sozinho. De tempos em tempos o sistema baixa a imagem de 10 câmeras públicas da
  CET-SP e roda o YOLO nela. Dois tipos de evento estão no escopo: trânsito
  (congestionamento) e alagamento.
- Confere com outras fontes. Nenhum evento é criado só pelo que a câmera viu. No trânsito,
  quem ajuda a decidir é a velocidade real do trecho (TomTom). No alagamento entram a
  chuva medida (Open-Meteo), o aviso oficial do INMET e o histórico de alagamento da via
  (CGE-SP e GeoSampa).
- Calcula a confiabilidade. O Data Fusion junta duas notas, IA (57%) e contexto (43%), num
  valor de 0 a 1. O evento só aparece como `ativo` quando passa do limite (77% por
  padrão). Abaixo disso fica `em_analise`.
- Atualiza em tempo real. Todo evento criado, atualizado ou removido chega ao painel por
  WebSocket. Se ele não funcionar, o painel usa SSE e, por último, consulta periódica.
- Apaga o que ficou velho. Um evento dura no máximo 45 minutos depois da última detecção.
  Depois disso ele sai do banco e do painel.

### Não faz

- Não manda notificações. Não há e-mail, SMS, push nem webhook. O sistema detecta e mostra
  no painel. A tabela `notificacoes` foi removida na migração `005`, porque nada gravava
  nela.
- Não tem login. Não há usuários, perfis nem sessão (removidos na migração `003`). Os
  eventos vêm das câmeras, não de pessoas.
- Não aceita registro manual. O painel só consulta: nenhuma rota cria, altera ou remove
  eventos ou evidências. Os eventos vêm só da detecção nas câmeras.
- Não detecta buraco, incêndio, lixo, árvore caída nem vazamento. Essas classes saíram do
  escopo (ver [§19](docs/apendice-decisoes-de-escopo.md#19-decisões-de-escopo-o-que-foi-removido-e-por-quê)).
- Não usa dados atrasados. Fontes que publicam as ocorrências semanas ou anos depois
  (GeoSampa e Defesa Civil como gatilho) foram removidas, porque o evento saía com o
  horário em que o sistema viu o registro, e não com o horário real.

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
  │  gx-veiculos.pt →         │◄─┘                  │                  │
  │  contagem de veículos     │                     │                  │
  ├───────────────────────────┤                     │                  │
  │ flood_detection.py        │◄────────────────────┴──────────────────┘
  │  gx-incident.pt →         │
  │  classe "alagamento"      │      + data_fusion/historico_alagamento.py
  └───────────┬───────────────┘        (histórico da via, arquivo local)
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
   │  · apaga eventos fora da janela de 45 min      │
   │  · junta duplicados no mesmo ponto             │
   │  · promove/rebaixa por confiabilidade          │
   └────────────────────────────────────────────────┘
```

A ideia central do projeto é que o YOLO dá uma evidência, não a resposta final. Quem
decide se o evento aparece como real é o Data Fusion, conferindo com as outras fontes.

---

## 4. Como rodar

### Pré-requisitos

- Python 3.11 ou mais novo
- Node.js 18 ou mais novo (só para compilar o TypeScript)
- MySQL 8 é opcional. Sem `DATABASE_URL`, o sistema usa um SQLite local
  (`backend/gx.db`) e cria as tabelas sozinho ao iniciar.
- Para a detecção funcionar: `backend/requirements-yolo.txt` e os modelos em `ml/models/`
  (`gx-veiculos.pt` para trânsito, `gx-incident.pt` para alagamento e `yolo11m.pt` como
  reserva). Os modelos estão no Git porque o deploy automático monta a imagem a partir do
  GitHub.

### Caminho rápido (Windows)

```powershell
.\start.ps1
```

Sobe o uvicorn numa janela do PowerShell e abre o navegador em `http://localhost:8000`.
É um processo só: o FastAPI serve a API e o painel (`frontend/`) no mesmo endereço, igual
na nuvem.

> O `start.ps1` não define variáveis de ambiente. Toda a configuração fica em
> `backend/.env`, que é lido pelo `config.py` (ver [§5](docs/configuracao.md#5-configuração-env)).

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

Coloque os modelos em `ml/models/` e confira com `GET /deteccao/status` antes de enviar
imagens. Sem os modelos, a API avisa que a detecção está indisponível.

### Ligar o monitoramento automático

Vem desligado por padrão, inclusive nos testes, para nada acessar as câmeras sem querer.
No `.env`:

```env
GX_MONITORAMENTO_ATIVO=true
GX_TRANSITO_MONITORAR_CATALOGO=true      # 10 threads de trânsito
GX_ALAGAMENTO_MONITORAR_CATALOGO=true    # 10 threads de alagamento (exige gx-incident.pt)
TOMTOM_API_KEY=...                       # sem ela, o trânsito é decidido só pela contagem
```

---

## Licença

Projeto acadêmico (TCC), para uso educacional.
