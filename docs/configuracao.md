# Configuração

[← voltar ao README](../README.md#documentação)

## 5. Configuração (`.env`)

Todas as variáveis são lidas por `backend/app/config.py` (pydantic-settings). Prefixo `GX_`
é herança do nome antigo do projeto e foi mantido para não quebrar ambientes existentes.

### Infraestrutura

| Variável | Padrão | O que faz |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./gx.db` | Conexão SQLAlchemy. Se contiver as credenciais de exemplo (`usuario:senha@` / `root:senha@`), um validador força SQLite — evita que um `.env` copiado sem editar deixe a API inutilizável. |
| `API_HOST` / `API_PORT` | `0.0.0.0` / `8000` | Bind do uvicorn. |
| `CORS_ORIGINS` | vazio | Lista separada por vírgula. Só importa se o painel for aberto de outra origem — servido pela API, é mesma origem. **Não é autenticação.** |

### Modelos YOLO

Todas passam por `config.py` (valem no `.env` e nas variáveis do Cloud Run). Caminho de
peso relativo é resolvido a partir da **raiz do projeto**, não de `backend/`.

| Variável | Padrão | O que faz |
|---|---|---|
| `GX_YOLO_MODEL` | `ml/models/yolo11m.pt` | Peso COCO para contagem de veículos. `m` e não `n`/`s`: o nano/small perdiam carro pequeno, distante e noturno. |
| `GX_YOLO_IMGSZ` | `1280` | Resolução de inferência do modelo de trânsito. Em 640 (padrão do Ultralytics) o YOLO subconta ~35% da fila ao fundo. Custo em GPU: dezenas de ms. |
| `YOLO_THRESHOLD` | `0.45` | Confiança mínima do modelo de objetos. |
| `GX_YOLO_INCIDENT_MODEL` | `ml/models/gx-incident.pt` | Peso dedicado a alagamento, carregado **separado** do modelo padrão (trocar o global quebraria a contagem de veículos). |
| `GX_YOLO_INCIDENT_CONF` | `0.6` | Confiança mínima só do modelo de alagamento. Mais alta de propósito: enquanto o peso não é retreinado com negativos, ele crava caixa em cena seca com score baixo. |
| `GX_YOLO_TTA` | `true` | Test-time augmentation na contagem de veículos (frame espelhado e em escalas menores): ~1 veículo a mais por frame nas câmeras CET, ao custo de ~2x a inferência. `false` desliga se o ciclo em CPU apertar. |
| `GX_YOLO_MAX_CONCORRENCIA` | `2` | Quantas inferências rodam ao mesmo tempo no processo (semáforo em `ml/detector.py`). Com o catálogo ligado são 20 threads chamando o YOLO; em GPU tanto faz, em CPU com 4 GiB (Cloud Run) 20 inferências simultâneas a 1280 estouram a memória e o container é morto. As threads continuam existindo — só esperam a vez. O carregamento dos pesos também tem trava própria: sem ela cada thread carregava a sua cópia. Além do semáforo, cada modelo tem um lock de inferência (uma chamada por vez por modelo): o objeto YOLO não é seguro entre threads — duas `predict` simultâneas no mesmo modelo quebravam no fuse da primeira chamada (`'Conv' object has no attribute 'bn'`). Trânsito e alagamento seguem em paralelo por serem objetos distintos; na prática o teto útil deste knob é 2. |

### Monitoramento contínuo

| Variável | Padrão | O que faz |
|---|---|---|
| `GX_MONITORAMENTO_ATIVO` | `false` | Chave mestra. Sem ela, **nenhuma** thread de detecção sobe. |
| `GX_TRANSITO_MONITORAR_CATALOGO` | `false` | Liga uma thread de trânsito por câmera do catálogo (10). |
| `GX_ALAGAMENTO_MONITORAR_CATALOGO` | `false` | Liga uma thread de alagamento por câmera do catálogo (10). |
| `GX_CAMERA_SNAPSHOT_URL` | — | Câmera avulsa (útil para testar com URL controlada). Exige lat/lon. |
| `GX_CAMERA_LATITUDE` / `_LONGITUDE` | — | Coordenada da câmera avulsa. |
| `GX_LIVE_DETECTION_INTERVAL_SECONDS` | `5` | Intervalo entre downloads de snapshot. |
| `GX_CAMERA_FRESCOR_MAXIMO_SEGUNDOS` | `300` | Idade máxima do `Last-Modified` para o frame contar como "ao vivo". Ver [§9](deteccao.md#a-armadilha-do-frame-travado). |

### Gatilho de trânsito (as três faixas)

| Variável | Padrão | O que faz |
|---|---|---|
| `GX_TRANSITO_MIN_VEICULOS_CORROBORADO` | `4` | **Piso absoluto.** Abaixo disso o frame é descartado sem nem consultar a TomTom. |
| `GX_TRANSITO_MIN_VEICULOS` | `12` | Contagem a partir da qual o frame se sustenta sem corroboração externa (mas ainda pode ser vetado). |
| `GX_TRANSITO_MIN_VEICULOS_CONFIRMADO` | `16` | Contagem que cria o evento sozinha, sem consultar ninguém. |
| `GX_TRANSITO_TOMTOM_INDICE_MINIMO` | `3.0` | Índice de congestionamento (0–10) que a TomTom precisa reportar na faixa intermediária. Abaixo disso (trecho a ≥ ~70% da velocidade livre) ela veta. |
| `TOMTOM_API_KEY` | — | Chave da TomTom Traffic API (cadastro gratuito self-service). |

> **Por que `TOMTOM_API_KEY` passa por `config.py` e não por `os.getenv`:** o `.env` é lido
> pelo pydantic-settings, que popula o objeto `Settings` mas **não** o `os.environ` do
> processo. Enquanto o serviço lia `os.getenv` direto, a chave configurada no `.env` nunca
> chegava nele e toda consulta caía em "TOMTOM_API_KEY não configurada" em silêncio —
> porque `start.ps1` sobe o uvicorn sem exportar variável nenhuma.

### Cooldowns e ciclo de vida

| Variável | Padrão | O que faz |
|---|---|---|
| `GX_ALERTA_COOLDOWN_SECONDS` | `1800` (30 min) | Silêncio da câmera depois de um evento **criado**. |
| `GX_TRANSITO_VETO_COOLDOWN_SECONDS` | `600` (10 min) | Silêncio depois de um **veto** da TomTom. Curto de propósito: um veto às 19h00 não pode calar a câmera até 19h30 se a via travar no meio do caminho. Também é o teto de consumo da API: 1 consulta por câmera a cada 10 min ≈ 1,4 k chamadas/dia nas 10 câmeras, dentro do plano gratuito. |
| `GX_EVENTO_JANELA_MINUTOS` | `45` | Janela de "tempo real". Evento detectado antes disso é apagado do banco. Mantido acima do cooldown de alerta para não abrir buraco entre uma detecção e a próxima. |
| `GX_FUSION_AUTO_ATIVO_MIN` | `0.77` | Confiabilidade a partir da qual um evento `em_analise` é promovido a `ativo`. |
