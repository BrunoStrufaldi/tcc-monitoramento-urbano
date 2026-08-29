# Sistema de Notificações Urbanas em Tempo Real

Projeto TCC — API FastAPI, frontend TypeScript com Leaflet, Data Fusion, YOLO real para veículos e atualizações em tempo real com fallback SSE → Polling.

## Estrutura

```
Projeto Gx/
├── backend/                # API FastAPI (Python)
│   ├── app/
│   │   ├── models/         # 8 models SQLAlchemy
│   │   ├── routers/        # 11 routers (eventos, fusion, deteccao, tempo_real, websocket, etc.)
│   │   ├── schemas/        # Schemas Pydantic com Literal validation
│   │   ├── services/       # Bridge data_fusion_service
│   │   └── ws_manager.py   # ConnectionManager para WebSocket
│   └── tests/              # 132 testes (pytest + SQLite em memória)
├── frontend/
│   ├── src/app.ts          # TypeScript principal (navigation rail, event cards, filtros)
│   ├── dist/app.js         # Bundle compilado
│   ├── css/style.css       # UI premium dark responsiva
│   └── index.html          # SPA com ARIA labels, views, overlays
├── data_fusion/            # Motor de confiabilidade (IA 40%, clima 30%, fonte 30%)
├── ml/                     # Detector YOLO real e pesos locais opcionais
├── database/
│   ├── schema.sql          # DDL 8 tabelas; não cria eventos fictícios
│   └── ERD.md              # Diagrama entidade-relação
└── package.json            # Scripts: build:frontend, serve
```

## Pré-requisitos

- Python 3.11+
- Node.js 18+ (para build do frontend)
- MySQL 8.x (produção) ou SQLite (testes)
- Para inferência real: `pip install -r requirements-yolo.txt` e o peso local `ml/models/yolo11m.pt` (ou pesos urbanos próprios)

## Início Rápido

### 1. Frontend (TypeScript)

```bash
npm install
npm run build:frontend    # Compila src/ → dist/
```

### 2. Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Edite `.env` com suas credenciais MySQL (ou ignore para usar SQLite via testes).

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 3. Frontend (servir)

```bash
cd frontend
python -m http.server 5500
```

Abra http://localhost:5500

### 4. Testes

```bash
cd backend
pytest tests/ -v           # 132 testes
python -m data_fusion.test_fusion
```

## Endpoints da API

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/` | Status da API |
| GET | `/health` | Health check |
| **Eventos** | | |
| GET | `/eventos` | Lista eventos (filtros: status, tipo) |
| POST | `/eventos` | Cria evento |
| GET | `/eventos/{id}` | Obtém evento |
| PATCH | `/eventos/{id}` | Atualiza evento |
| DELETE | `/eventos/{id}` | Remove evento |
| **Data Fusion** | | |
| GET | `/fusion/eventos/{id}/confiabilidade` | Score de confiabilidade |
| POST | `/fusion/eventos/{id}/recalcular` | Recalcula e grava |
| **Tempo Real** | | |
| WS | `/ws` | WebSocket — eventos em tempo real |
| GET | `/events/stream` | SSE — fallback para WebSocket |
| GET | `/events/connected` | Clientes SSE conectados |
| **YOLO** | | |
| GET | `/deteccao/classes` | Classes detectáveis |
| POST | `/deteccao/simular` | Simula detecção |
| POST | `/deteccao/imagem` | Upload + detecção |
| POST | `/deteccao/video` | Demonstração de fluxo de frames |
| **Outros** | | |
| `/notificacoes` | CRUD notificações |
| `/regioes` | CRUD regiões |
| `/fontes` | CRUD fontes de dados |
| `/localizacoes` | CRUD localizações |
| `/evidencias` | CRUD evidências visuais |
| `/dados-contextuais` | CRUD dados contextuais |
| `/logs` | Logs do sistema |

## Arquitetura

- **Backend**: FastAPI + SQLAlchemy + Pydantic (Literal validation para enums)
- **Frontend**: TypeScript + Leaflet/CARTO Dark + Navigation Rail + Event Cards premium
- **Data Fusion**: Motor de confiabilidade (IA 40%, clima 30%, fonte oficial 30%)
- **Tempo Real**: WebSocket com fallback cascata WS → SSE → Polling
- **YOLO**: inferência real de veículos com YOLO11n; pesos urbanos próprios são configuráveis
- **Testes**: 121 testes pytest com SQLite em memória

## Protocolo WebSocket

### Endpoint

```
ws://host:port/ws
```

### Formato das Mensagens

```json
{
  "tipo": "evento_criado",
  "timestamp": "2026-08-14T12:00:00+00:00",
  "dados": { ... }
}
```

### Mensagens Servidor → Cliente

| `tipo` | Trigger |
|--------|---------|
| `evento_criado` | `POST /eventos` |
| `evento_atualizado` | `PATCH /eventos/{id}` |
| `evento_removido` | `DELETE /eventos/{id}` |
| `notificacao_criada` | `POST /notificacoes` |
| `notificacao_atualizada` | `PATCH /notificacoes/{id}`, `/lida`, `/arquivar` |
| `pong` | Resposta a `ping` do cliente |

### Cascata de Fallback

```
WebSocket ──falha──► SSE (/events/stream) ──falha──► Polling (15s)
```

- Reconexão exponencial: 1s → 2s → 4s → ... → 128s (max 8 tentativas)
- Ping/pong a cada 30s para manter conexão viva
- Seleção e filtros preservados durante atualizações

## Enums do Sistema

- **Severidade**: `baixa`, `media`, `alta`, `critica`
- **Status evento**: `ativo`, `em_analise`, `resolvido`
- **Canal notificação**: `painel`, `push`, `email`, `sms`, `webhook`
- **Status notificação**: `pendente`, `enviada`, `falha`, `lida`

## Segurança básica

As rotas HTTP operacionais exigem `Authorization: Bearer <token>`. O token é assinado, expira por padrão em 60 minutos e é emitido por `POST /auth/login`. Senhas são armazenadas somente como hash PBKDF2-SHA256 com salt individual; nem senhas nem chaves entram no repositório.

Configure as variáveis abaixo em `backend/.env` (copie `backend/.env.example`). Gere o segredo fora do projeto e mantenha-o no gerenciador de segredos do ambiente.

```env
AUTH_SECRET_KEY=<segredo-longo-e-aleatorio>
AUTH_TOKEN_EXPIRE_MINUTES=60
AUTH_BOOTSTRAP_ADMIN_USERNAME=admin-inicial
AUTH_BOOTSTRAP_ADMIN_PASSWORD=<senha-longa-unica>
AUTH_ALLOW_SELF_REGISTRATION=false
```

No primeiro start, o par `AUTH_BOOTSTRAP_ADMIN_*` cria um administrador somente se ele ainda não existir. Depois, um administrador pode criar usuários em `POST /auth/usuarios`; o auto-registro público, quando habilitado, cria apenas `operador`.

| Perfil | Permissões |
|---|---|
| `operador` | Consultar dados e executar ações operacionais: atualizar evento, recalcular Data Fusion, criar notificação e registrar evidência. |
| `administrador` | Todas as permissões de operador, além de criar usuários e remover eventos. |

As ações operacionais registram usuário, ação, evento quando aplicável, horário e resultado em `auditoria_acoes`. A migração aditiva está em `database/migrations/001_security.sql`; aplique-a no MySQL existente antes de ativar a API. Em SQLite local, as tabelas novas são criadas sem remover dados via SQLAlchemy.

### Riscos e limitações atuais

- O frontend solicita login antes de iniciar a operação e mantém o token somente em `sessionStorage`; se a API responder `401`, a sessão é removida e o login é solicitado novamente.
- Os WebSockets `/ws` e `/ws/cv` exigem uma primeira mensagem `{ "tipo": "auth", "token": "..." }`; o token não é colocado na URL.
- Não há refresh token, revogação imediata nem MFA. Reduza a expiração e troque `AUTH_SECRET_KEY` para revogar tokens em caso de incidente.
- Use HTTPS, CORS restritivo, rate limit no login, TLS no banco e um secret manager em produção.

## Validação visual YOLO (MVP)

Fluxo: `câmera/imagem → YOLO → detecções → evidência → evento → Data Fusion → dashboard`.

- `POST /deteccao/frame` aceita JPEG, PNG e WEBP, limita o frame por `YOLO_MAX_FRAME_BYTES` e retorna `frame_id`, caixas, confiança, timestamp e latência. O frame é temporário e removido após a inferência.
- Evidência só é persistida quando `persistir=true`, há uma detecção não duplicada e um `evento_id` informado. Ela é vinculada à fonte `GX YOLO` (`tipo=yolo`) e recalcula a confiança por Data Fusion.
- `WS /ws/cv` exige uma primeira mensagem `{ "tipo":"auth", "token":"..." }`; depois aceita frames base64 em até `YOLO_MAX_FPS`. Se não houver WebSocket autenticado, a tela usa upload HTTP sob demanda.
- A câmera do navegador nunca inicia automaticamente. O operador deve conceder permissão e pode pausar ou encerrar; ao encerrar, tracks e timer são interrompidos.
- Opcionalmente, o backend pode rodar monitoramento 100% automático — sem operador nem câmera obrigatória — ligado por `GX_MONITORAMENTO_ATIVO=true` (desligado por padrão, inclusive em testes). Dois módulos, mesmo padrão (câmeras públicas CET-SP, thread por câmera, sem confirmação humana):
  - **Trânsito** (`live_detection`, exige `backend/requirements-yolo.txt`): lê periodicamente o snapshot de câmeras públicas CET-SP (`https://cameras.cetsp.com.br/Cams/{id}/1.jpg`, atualizado por HTTP, não RTSP) — uma câmera avulsa via `GX_CAMERA_SNAPSHOT_URL`, e/ou todas as 11 câmeras já catalogadas (`cet_camera_catalog.py`) via `GX_TRANSITO_MONITORAR_CATALOGO=true`. O YOLO/COCO padrão só reconhece objetos (veículo, ônibus, caminhão, moto), não "trânsito" como classe — por isso o sistema conta quantos veículos aparecem juntos no mesmo frame e, a partir de `GX_TRANSITO_MIN_VEICULOS` (padrão 12; as câmeras da CET pegam um trecho curto de via, raramente mostram 20+ carros e o YOLO ainda subconta fila ao fundo), sinaliza um único evento de congestionamento. Esse índice por contagem de veículos é corroborado, quando `TOMTOM_API_KEY` está configurada, com a velocidade atual x livre do trecho na TomTom Traffic API (dado ao vivo, não em lote) — as duas fontes entram como a mesma dimensão de clima no Data Fusion, com peso combinado quando concordam.
  - **Alagamento** (`flood_detection`, exige `GX_YOLO_INCIDENT_MODEL` configurado): mesmo catálogo de 11 câmeras via `GX_ALAGAMENTO_MONITORAR_CATALOGO=true`, mas roda o modelo dedicado de incidentes (não o COCO padrão, que não reconhece essa classe) direto no snapshot mais recente. Cada detecção busca duas fontes climáticas independentes e grava como dado contextual: a chuva atual no ponto exato (Open-Meteo, sensor bruto ao vivo) e um aviso oficial ativo do INMET pra São Paulo (`inmet_alert_source`, API pública sem chave, `apiprevmet3.inmet.gov.br/avisos/ativos` — julgamento institucional, só é gravado quando o aviso menciona risco de alagamento no texto de "riscos"). Quando as duas existem, `data_fusion.scores` faz a média em vez de confiar só numa — mesmo padrão do trânsito (índice de veículos + TomTom).
  - Havia também monitoramento de alagamento, acidente de trânsito e queda de árvore via datasets em lote do GeoSampa/Defesa Civil/CET aqui — **removido por decisão do grupo**: eram dados oficiais e com coordenada real, mas recarregados semanas a anos depois do ocorrido, e cada evento saía carimbado com o horário em que o sistema notou o registro, não o horário real do incidente — o mesmo tipo de problema achado depois numa câmera CET específica que ficou travada meses num frame antigo (ver `frame_esta_desatualizado` abaixo). Ficou definido que "tempo real" só vale pra detecção via câmera ao vivo. Pelo mesmo motivo, Waze for Cities (exige convênio formal da prefeitura com o Google) e o site do CGE (sem API pública, só scraping de HTML frágil) nunca chegaram a entrar.
  - Toda detecção contínua em câmera passa por `cet_camera_catalog.frame_esta_desatualizado` (cabeçalho HTTP `Last-Modified`, limite `GX_CAMERA_FRESCOR_MAXIMO_SEGUNDOS`, padrão 300s) antes de virar evento — descoberto na prática que a CET às vezes trava numa câmera específica e devolve sempre o mesmo JPEG antigo (200 OK, só o conteúdo é velho); sem essa checagem, isso vira um evento "detectado agora" com uma foto de outra época.
  - No painel, o filtro de status (`Ativo` por padrão) esconde os eventos `em_analise` do mapa e da lista — o operador pode trocar pra "Em análise" ou "Todos" pra auditar o que ainda não foi confirmado.

Configuração de execução:

```env
YOLO_THRESHOLD=0.45
YOLO_MAX_FPS=3
YOLO_MAX_FRAME_BYTES=1500000
YOLO_MAX_FRAME_WIDTH=1280
YOLO_COOLDOWN_SECONDS=20
GX_YOLO_MODEL=/caminho/para/pesos-urbanos.pt
GX_YOLO_CLASS_MAPPING={"car":"veiculo","truck":"caminhao"}
```

Sem `GX_YOLO_MODEL`, a API informa indisponibilidade do modelo real e os testes usam detector controlado. O peso padrão YOLO11n/COCO registra veículos e hidrantes apenas como **observações visuais**; ele não transforma a presença de um carro em congestionamento e **não** detecta alagamento, fumaça ou incêndio. Essas ocorrências exigem pesos urbanos treinados e validação operacional. Antes de criar um registro no mapa, `/deteccao/confirmar` repete a inferência no servidor, preserva o original, grava seu SHA-256 e gera uma cópia com caixas YOLO.

Privacidade: não envie frames sem consentimento, não use a câmera em segundo plano e não persista imagem a menos que a evidência seja relevante e o operador confirme. CPU tem maior latência/FPS menor; GPU exige CUDA/Ultralytics compatíveis. Meça latência por frame no retorno da API e FPS no painel, pois ambos dependem de hardware, rede e peso utilizado.

## Licença

Projeto acadêmico — TCC.
