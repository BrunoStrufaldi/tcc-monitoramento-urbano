# Configuração

[← voltar ao README](../README.md#documentação)

## 5. Configuração (`.env`)

Todas as variáveis são lidas pelo `backend/app/config.py` (pydantic-settings). O prefixo
`GX_` vem do nome antigo do projeto e foi mantido para não quebrar ambientes que já
existiam.

### Infraestrutura

| Variável | Padrão | O que faz |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./gx.db` | Conexão do SQLAlchemy. Se tiver os dados de exemplo (`usuario:senha@` ou `root:senha@`), o sistema usa SQLite. Assim um `.env` copiado sem editar não deixa a API parada. |
| `API_HOST` / `API_PORT` | `0.0.0.0` / `8000` | Endereço e porta do uvicorn. |
| `CORS_ORIGINS` | vazio | Lista separada por vírgula. Só é preciso se o painel for aberto a partir de outro endereço; servido pela API, o endereço é o mesmo. Não é autenticação. |

### Modelos YOLO

Todas passam pelo `config.py` (valem no `.env` e nas variáveis do Cloud Run). Caminhos
relativos dos modelos partem da raiz do projeto, e não de `backend/`.

| Variável | Padrão | O que faz |
|---|---|---|
| `GX_YOLO_MODEL` | `ml/models/gx-veiculos.pt` | Modelo de contagem de veículos: o `yolo11m` ajustado nas câmeras da CET pelo `ml/train_vehicle_model.py`. Nas 79 imagens de teste, a confiança média foi de 0,71 para 0,87, a precisão de 0,81 para 0,88 e os veículos por imagem de 10,1 para 11,6, com a mesma velocidade. O `ml/models/yolo11m.pt` continua no repositório como reserva. Usamos o tamanho `m`, e não o `n` ou o `s`, porque os menores perdiam carros pequenos, distantes e à noite. |
| `GX_YOLO_IMGSZ` | `1280` | Tamanho da imagem na detecção de trânsito. Com 640 (o padrão do Ultralytics) o YOLO deixa de contar uns 35% da fila ao fundo. Na GPU, o custo é de dezenas de milissegundos. |
| `YOLO_THRESHOLD` | `0.45` | Confiança mínima do modelo de veículos. |
| `GX_YOLO_INCIDENT_MODEL` | `ml/models/gx-incident.pt` | Modelo de alagamento, carregado separado do de veículos (trocar um pelo outro quebraria a contagem de veículos). |
| `GX_YOLO_INCIDENT_CONF` | `0.6` | Confiança mínima do modelo de alagamento. É mais alta de propósito, porque abaixo disso ele confundia pista seca com alagamento. |
| `GX_YOLO_TTA` | `true` | TTA na contagem de veículos: o YOLO também analisa a imagem espelhada e em outros tamanhos. Encontra cerca de 1 veículo a mais por imagem nas câmeras da CET, mas deixa a detecção duas vezes mais lenta. Fica ligado localmente (GPU), e a imagem do Cloud Run (CPU) já vem com `false` no `Dockerfile`. |
| `GX_YOLO_MAX_CONCORRENCIA` | `2` | Quantas detecções podem rodar ao mesmo tempo (limite em `ml/detector.py`). Com o catálogo ligado são 20 threads chamando o YOLO. Na GPU isso não faz diferença, mas em CPU com 4 GiB (Cloud Run) 20 detecções juntas em 1280 estouram a memória e o container cai. As threads continuam existindo, só esperam a vez. O carregamento dos modelos também tem uma trava, porque antes cada thread carregava a sua cópia. Além disso, cada modelo tem a sua trava de detecção (uma chamada por vez), já que o YOLO dá erro com duas detecções ao mesmo tempo no mesmo modelo (`'Conv' object has no attribute 'bn'`). Trânsito e alagamento rodam em paralelo por serem modelos diferentes, então na prática o valor útil aqui é 2. |

### Monitoramento contínuo

| Variável | Padrão | O que faz |
|---|---|---|
| `GX_MONITORAMENTO_ATIVO` | `false` | Chave geral. Sem ela, nenhuma thread de detecção sobe. |
| `GX_TRANSITO_MONITORAR_CATALOGO` | `false` | Liga uma thread de trânsito para cada câmera do catálogo (10). |
| `GX_ALAGAMENTO_MONITORAR_CATALOGO` | `false` | Liga uma thread de alagamento para cada câmera do catálogo (10). |
| `GX_CAMERA_SNAPSHOT_URL` | vazio | Câmera avulsa (útil para testar com um endereço conhecido). Precisa de latitude e longitude. |
| `GX_CAMERA_LATITUDE` / `_LONGITUDE` | vazio | Coordenada da câmera avulsa. |
| `GX_LIVE_DETECTION_INTERVAL_SECONDS` | `5` | Intervalo entre os downloads da imagem. |
| `GX_CAMERA_FRESCOR_MAXIMO_SEGUNDOS` | `300` | Idade máxima do `Last-Modified` para a imagem contar como ao vivo. Ver [§9](deteccao.md#a-armadilha-do-frame-travado). |

### Gatilho de trânsito (as três faixas)

| Variável | Padrão | O que faz |
|---|---|---|
| `GX_TRANSITO_MIN_VEICULOS_CORROBORADO` | `4` | Piso. Abaixo disso a imagem é descartada sem consultar a TomTom. |
| `GX_TRANSITO_MIN_VEICULOS` | `12` | A partir dessa contagem a imagem já basta, sem confirmação de fora (mas a TomTom ainda pode recusar). |
| `GX_TRANSITO_MIN_VEICULOS_CONFIRMADO` | `16` | A partir dessa contagem o evento é criado sem consultar ninguém. |
| `GX_TRANSITO_TOMTOM_INDICE_MINIMO` | `3.0` | Índice de congestionamento (0 a 10) que a TomTom precisa informar na faixa do meio. Abaixo disso (trecho a 70% ou mais da velocidade normal) ela recusa. |
| `TOMTOM_API_KEY` | vazio | Chave da TomTom Traffic API (cadastro grátis). |

> A `TOMTOM_API_KEY` é lida pelo `config.py` e não por `os.getenv`, porque o
> pydantic-settings lê o `.env` e preenche o objeto `Settings`, mas não o `os.environ`.
> Quando o serviço lia `os.getenv` direto, a chave do `.env` nunca chegava nele, já que o
> `start.ps1` não define variáveis de ambiente.

### Cooldowns e ciclo de vida

| Variável | Padrão | O que faz |
|---|---|---|
| `GX_ALERTA_COOLDOWN_SECONDS` | `1800` (30 min) | Tempo que a câmera espera depois de criar um evento. |
| `GX_TRANSITO_VETO_COOLDOWN_SECONDS` | `600` (10 min) | Tempo de espera depois de uma recusa da TomTom. É curto de propósito: uma recusa às 19h00 não pode deixar a câmera parada até 19h30 se a via travar no meio do caminho. Também limita o uso da API: 1 consulta por câmera a cada 10 min dá umas 1.400 chamadas por dia nas 10 câmeras, dentro do plano gratuito. |
| `GX_EVENTO_JANELA_MINUTOS` | `45` | Janela de tempo real. Um evento detectado antes disso é apagado do banco. Fica acima do tempo de espera do alerta, para não abrir um buraco entre uma detecção e a próxima. |
| `GX_FUSION_AUTO_ATIVO_MIN` | `0.77` | Confiabilidade a partir da qual um evento `em_analise` passa para `ativo`. |
