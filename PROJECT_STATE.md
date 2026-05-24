# Estado do Projeto — TCC Monitoramento Urbano

**Última atualização:** fase fundação (backend + CRUD + MySQL)

## Estado atual

| Componente | Status |
|-----------|--------|
| API FastAPI | ✅ Rodando (`http://127.0.0.1:8000`) |
| Swagger `/docs` | ✅ Disponível |
| Banco MySQL | ✅ `tcc_monitoramento_urbano` |
| Tabela `eventos` | ✅ Schema simplificado |
| CRUD `/eventos` | ✅ GET, POST, PUT, DELETE |
| Rota raiz `GET /` | ✅ Health message |
| Data Fusion | ✅ Módulo testado (fase básica) |
| Frontend mapa | ✅ Google Maps + criticidade |
| YOLO | ⏸ **Não implementado — fase final** |

## Arquitetura

```
┌─────────────┐     HTTP      ┌──────────────────┐
│  Frontend   │ ────────────► │  FastAPI         │
│  (HTML/JS)  │               │  /eventos CRUD   │
│  Google Maps│               │  /fusion         │
└─────────────┘               └────────┬─────────┘
                                       │ SQLAlchemy
                                       ▼
                              ┌──────────────────┐
                              │  MySQL           │
                              │  tcc_monitoramento_urbano
                              │  └── eventos     │
                              └──────────────────┘

┌──────────────────┐
│  data_fusion/    │  ← módulo Python (IA + clima + fonte)
└──────────────────┘

┌──────────────────┐
│  ml/             │  ← reservado para YOLO (fase posterior)
└──────────────────┘
```

### Camadas do backend

- `app/main.py` — aplicação FastAPI, CORS, rotas
- `app/config.py` — variáveis de ambiente (`pydantic-settings`)
- `app/database.py` — engine SQLAlchemy + sessão
- `app/models/evento.py` — modelo ORM
- `app/routers/eventos.py` — CRUD
- `app/routers/fusion.py` — confiabilidade (Data Fusion)
- `app/models/legacy/` — modelos da fase avançada (não ativos)

## Modelo `eventos` (fase atual)

| Campo | Tipo |
|-------|------|
| id | INT PK |
| tipo | VARCHAR(100) |
| descricao | TEXT |
| criticidade | VARCHAR(50) |
| latitude | DECIMAL(10,7) |
| longitude | DECIMAL(10,7) |
| status | VARCHAR(50) |
| confiabilidade | FLOAT |
| fonte | VARCHAR(100) |
| criado_em | TIMESTAMP |

## Roadmap

### Fase 1 — Fundação ✅ (atual)
- [x] Backend FastAPI estruturado
- [x] Conexão MySQL + SQLAlchemy
- [x] CRUD completo de eventos
- [x] Schema SQL + seeds
- [x] Frontend com mapa
- [x] Data Fusion básico (score por fonte)

### Fase 2 — Enriquecimento
- [ ] Schema estendido (`database/schema_extended.sql`)
- [ ] Regiões, localizações, evidências, logs
- [ ] Data Fusion com clima e IA real
- [ ] WebSockets / SSE tempo real
- [ ] Autenticação

### Fase 3 — Automação visual (por último)
- [ ] **YOLO** — detecção em câmeras (`ml/`)
- [ ] Pipeline de inferência → `POST /eventos`
- [ ] Evidências visuais no banco

> **YOLO será implementado por último**, como módulo de automação visual separado, após a fundação do backend, persistência e API estarem estáveis.

## Comandos rápidos

```bash
cd backend
venv\Scripts\activate
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

```bash
mysql -u root -p < database/schema.sql
```
