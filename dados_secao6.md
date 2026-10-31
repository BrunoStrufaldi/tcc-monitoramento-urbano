# Dados para a seção 6 (Resultados Obtidos)

Levantamento feito em 31/10/2026, só com leitura de arquivos, comandos indicados e consultas SELECT. Nenhum código, configuração ou banco foi alterado. Escopo: modelo de veículos (gx-veiculos.pt) e sistema de trânsito. Alagamento ficou de fora, exceto na separação dos testes (item 6).

Arquivos gerados na raiz: `results_veiculos.csv` (cópia de `ml/runs/veiculos/results.csv`), `latencia.json` (saída do benchmark) e este arquivo.

---

## 1. Treino do modelo de veículos

### 1a) Configuração do treino (`ml/runs/veiculos/args.yaml`)

| Parâmetro | Valor |
|---|---|
| Modelo de partida | `ml/models/yolo11m.pt` (YOLO11m pré-treinado no COCO) |
| Épocas configuradas | 60 |
| Batch | 4 |
| imgsz | 1280 |
| lr0 | 0.002 (configurado, mas **não usado**, ver abaixo) |
| lrf | 0.01 |
| momentum | 0.937 (configurado, mas não usado) |
| weight_decay | 0.0005 |
| warmup_epochs / warmup_momentum / warmup_bias_lr | 3.0 / 0.8 / 0.1 |
| freeze | 10 (camadas 0 a 9 congeladas, que formam o backbone do YOLO11m) |
| patience | 15 |
| optimizer | auto |
| cos_lr | false |
| amp | true |
| seed / deterministic | 42 / true |
| pretrained | true |
| workers | 8 |
| val split | val (que no data.yaml aponta para `images/test`) |

Otimizador real (log `ml/runs/treino_veiculos.log`):

> `optimizer: 'optimizer=auto' found, ignoring 'lr0=0.002' and 'momentum=0.937' and determining best 'optimizer', 'lr0' and 'momentum' automatically...`
> `optimizer: AdamW(lr=0.000119, momentum=0.9) with parameter groups 106 weight(decay=0.0), 113 weight(decay=0.0005), 112 bias(decay=0.0)`

Ou seja, com `optimizer=auto` o Ultralytics escolheu AdamW com lr = 0.000119 e ignorou o lr0 = 0.002 do script. A coluna `lr/pg0` do results.csv confirma: o pico é 0.000114594 na época 3.

Data augmentation:

| Parâmetro | Valor |
|---|---|
| hsv_h | 0.015 |
| hsv_s | 0.7 |
| hsv_v | 0.4 |
| degrees | 0.0 |
| translate | 0.1 |
| scale | 0.5 |
| shear | 0.0 |
| perspective | 0.0 |
| flipud | 0.0 |
| fliplr | 0.5 |
| bgr | 0.0 |
| mosaic | 1.0 |
| close_mosaic | 10 (desliga o mosaic nas últimas 10 épocas) |
| mixup | 0.0 |
| cutmix | 0.0 |
| copy_paste | 0.0 (copy_paste_mode: flip) |
| multi_scale | 0.0 |
| auto_augment | randaugment |
| erasing | 0.4 |

Observação: na documentação do Ultralytics, `auto_augment` e `erasing` são descritos como opções de treino de classificação. Vale conferir antes de citá-los como augmentation usada neste treino de detecção.

Outros parâmetros de perda: box 7.5, cls 0.5, dfl 1.5, nbs 64, iou 0.7, max_det 300.

### 1b) Resultados (`ml/runs/veiculos/results.csv`)

- Épocas que rodaram de fato: **30 de 60**. O treino parou por early stopping. Log: `Training stopped early as no improvement observed in last 15 epochs. Best results observed at epoch 15, best model saved as best.pt.`
- Melhor época: **15**.
- `ml/models/gx-veiculos.pt` é idêntico a `ml/runs/veiculos/weights/best.pt` (mesmo SHA-256: `d6d028a6...c5e68465`), então o modelo em uso é o da época 15.

| Métrica (conjunto de validação, todas as classes) | Época 15 (melhor, no CSV) | Validação final do best.pt (log) | Época 30 (última, no CSV) |
|---|---|---|---|
| Precision | 0.64384 | 0.646 | 0.71635 |
| Recall | 0.72225 | 0.721 | 0.70575 |
| mAP50 | 0.74686 | 0.747 | 0.72875 |
| mAP50-95 | 0.60597 | 0.606 | 0.59154 |

A validação final do log reavalia o best.pt já com as camadas fundidas, por isso difere um pouco do CSV na terceira casa.

Atenção: essas métricas consideram **todas as classes** que o professor marcou nas imagens de validação (79 imagens, 1268 instâncias), não só veículos. Por classe, na validação final do best.pt (log):

| Classe | Imagens | Instâncias | P | R | mAP50 | mAP50-95 |
|---|---|---|---|---|---|---|
| all | 79 | 1268 | 0.646 | 0.721 | 0.747 | 0.606 |
| person | 49 | 205 | 0.812 | 0.822 | 0.902 | 0.713 |
| bicycle | 6 | 6 | 0.658 | 0.833 | 0.786 | 0.716 |
| **car** | 78 | 862 | 0.862 | 0.949 | 0.969 | 0.886 |
| **motorcycle** | 17 | 24 | 0.503 | 0.875 | 0.833 | 0.515 |
| **bus** | 24 | 37 | 0.586 | 0.892 | 0.886 | 0.763 |
| train | 2 | 3 | 0.532 | 0.667 | 0.443 | 0.300 |
| **truck** | 38 | 66 | 0.752 | 0.576 | 0.700 | 0.652 |
| traffic light | 38 | 57 | 0.597 | 0.807 | 0.724 | 0.635 |
| backpack | 1 | 2 | 0.529 | 0.500 | 0.495 | 0.346 |
| umbrella | 2 | 6 | 0.624 | 0.291 | 0.730 | 0.538 |

Velocidade informada pelo Ultralytics na validação final: 0.6 ms pré-processamento, 20.8 ms inferência, 2.1 ms pós-processamento por imagem (RTX 3060).

Dois pontos de método para o texto:
1. Os rótulos não são manuais. Foram gerados pelo YOLO11x (`yolo11x.pt`, conf 0.40, imgsz 1280, TTA ligado), conforme `cmd_rotular` em `ml/train_vehicle_model.py`. As métricas medem concordância com esse modelo "professor", não com anotação humana.
2. O `data.yaml` usa `images/test` tanto para `val` quanto para `test`. Então a escolha da melhor época (early stopping) e a avaliação final foram feitas nas mesmas 79 imagens.

Cópia salva em `results_veiculos.csv` na raiz.

### 1c) Tamanho do dataset (`ml/datasets/veiculos_cet`)

| Split | Imagens | Arquivos de label | Carro (2) | Moto (3) | Ônibus (5) | Caminhão (7) | Total veículos | Total de caixas (todas as classes) |
|---|---|---|---|---|---|---|---|---|
| train | 318 | 318 | 3871 | 185 | 222 | 244 | **4522** | 5662 |
| test | 79 | 79 | 862 | 24 | 37 | 66 | **989** | 1268 |
| Total | 397 | 397 | 4733 | 209 | 259 | 310 | **5511** | 6930 |

Nenhum arquivo de label está vazio. A contagem foi feita arquivo por arquivo. Os labels não terminam com quebra de linha, então concatenar tudo com `cat` dá números errados. Os totais batem com o log do treino (318 e 79 imagens, 1268 instâncias na validação) e com a avaliação (989 instâncias de veículos no teste).

### 1d) Datas e câmeras das imagens

Os nomes dos arquivos são UUIDs (ex.: `00d6bf05...-original.jpg`), sem data. As datas abaixo vêm da data de modificação dos arquivos. O `shutil.copy2` preserva essa data, e as 397 imagens do dataset têm a mesma data das originais em `backend/app/data/evidencias`.

- Imagem mais antiga: **26/08/2026 11:02:40**
- Imagem mais recente: **02/10/2026 07:58:43**
- O treino rodou em 03/10/2026, um dia depois da imagem mais recente.

Imagens por dia:

| Dia | Imagens | Dia | Imagens |
|---|---|---|---|
| 26/08 | 31 | 05/09 | 6 |
| 27/08 | 42 | 09/09 | 12 |
| 28/08 | 51 | 18/09 | 7 |
| 29/08 | 39 | 20/09 | 2 |
| 30/08 | 6 | 21/09 | 23 |
| 31/08 | 62 | 23/09 | 11 |
| 01/09 | 18 | 28/09 | 6 |
| 02/09 | 43 | 02/10 | 4 |
| 03/09 | 7 | | |
| 04/09 | 27 | **Total** | **397** |

Hoje existem 493 imagens `-original.jpg` em `evidencias`, a mais recente de 23/10/2026. O dataset tem 397 porque o script descarta imagens repetidas (mesmo SHA-256) e porque parte das imagens chegou depois de 02/10.

Câmeras: **NÃO ENCONTRADO para o dataset inteiro.** A câmera de cada imagem só fica registrada na tabela `evidencias_visuais`, e ela está vazia no `backend/gx.db` porque a retenção apaga os eventos. Procurei nos backups em `backend/data/backups/` e só **21 das 397 imagens** aparecem lá. Essas 21 vêm de **8 câmeras diferentes**:

| Câmera (fonte registrada) | Imagens |
|---|---|
| Paulista - Av Brigadeiro Luiz Antônio | 6 |
| Iguatemi - Av Brig Faria Lima | 5 |
| Brig Luis Antônio - Al Santos | 3 |
| Ascendino Reis - R Pedro de Toledo | 2 |
| Consolação - R Caio Prado | 2 |
| Paulista - Metrô Consolação | 1 |
| Cidade Jardim - Av Nove de Julho | 1 |
| Ibirapuera - R Ipê | 1 |

Para referência, o catálogo atual (`backend/app/services/cet_camera_catalog.py`) tem 10 câmeras. Isso não prova de quantas câmeras vieram as outras 376 imagens.

### 1e) Avaliação: `python ml/train_vehicle_model.py avaliar --novo ml/models/gx-veiculos.pt`

O `python` do sistema (C:\Python314) não tem o ultralytics instalado. O comando foi rodado com `backend\venv\Scripts\python.exe`, que é o ambiente onde o treino rodou (Ultralytics 8.4.129, torch 2.13.0+cu126). Saída completa, só sem as barras de progresso:

```
Ultralytics 8.4.129  Python-3.14.7 torch-2.13.0+cu126 CUDA:0 (NVIDIA GeForce RTX 3060, 12288MiB)
YOLO11m summary (fused): 125 layers, 20,091,712 parameters, 0 gradients, 68.1 GFLOPs
WARNING val: Slow image access detected (ping: 0.30.0 ms, read: 35.711.4 MB/s, size: 31.6 KB). Use local storage instead of remote/mounted storage for better performance. See https://docs.ultralytics.com/guides/model-training-tips
                   all         79        989       0.81      0.659      0.782      0.661
Speed: 2.5ms preprocess, 31.8ms inference, 0.0ms loss, 2.6ms postprocess per image
Ultralytics 8.4.129  Python-3.14.7 torch-2.13.0+cu126 CUDA:0 (NVIDIA GeForce RTX 3060, 12288MiB)
YOLO11m summary (fused): 126 layers, 20,091,712 parameters, 0 gradients, 68.1 GFLOPs
val: Fast image access  (ping: 0.20.1 ms, read: 172.927.1 MB/s, size: 32.6 KB)
                   all         79        989       0.88        0.7      0.848      0.705
Speed: 2.4ms preprocess, 37.1ms inference, 0.0ms loss, 1.1ms postprocess per image

Frames de teste: 79 (nunca vistos no treino) · professor marca 12.5 veículos/frame
métrica                             atual     novo
mAP50 (acerto x professor)          0.782    0.848
precisão                            0.810    0.880
recall                              0.659    0.700
confiança média (12 melhores)       0.714    0.870
veículos por frame                 10.051   11.570
```

O primeiro bloco é o modelo "atual", que no script é o `yolo11m.pt` original do COCO. O segundo é o `gx-veiculos.pt`. Nessa avaliação só entram as classes de veículo (2, 3, 5, 7), por isso são 989 instâncias. O mAP50-95 aparece só na linha "all": 0.661 no antigo e 0.705 no novo.

Resumo antigo → novo: precisão 0.810 → 0.880, recall 0.659 → 0.700, mAP50 0.782 → 0.848, mAP50-95 0.661 → 0.705, confiança média das 12 melhores caixas 0.714 → 0.870, veículos por frame 10.05 → 11.57 (o professor marca 12.5).

A conf usada para contar veículos por frame é 0.45, a mesma do sistema. Vale o mesmo aviso do 1b: a referência é o professor YOLO11x, não anotação manual.

### 1f) Tempo de treino

| Fonte | Valor |
|---|---|
| Log do Ultralytics | `30 epochs completed in 0.227 hours` (≈ 13,6 min) |
| results.csv, coluna `time` na época 30 | 814,8 s (≈ 13,6 min) |
| Datas dos arquivos | args.yaml 03/10/2026 16:05:55 → best.pt 16:20:06 → log 16:20:12 (≈ 14,3 min, contando preparo e validação final) |

Por época, a partir da época 2: cerca de 26 s (80 iterações de batch 4, a ~3,4 it/s no log). A primeira época levou 54 s.

---

## 2. Hardware

| Item | Valor | Fonte |
|---|---|---|
| GPU | NVIDIA GeForce RTX 3060, 12288 MiB (12 GB), driver 617.42, CUDA UMD 13.4 | nvidia-smi |
| CPU | Intel Core i5-14600KF, 14 núcleos, 20 threads | Win32_Processor |
| RAM | 31,8 GB (2 pentes de 16 GB, 3200 MHz) | Win32_PhysicalMemory |
| SO | Windows 11 Home, versão 10.0.26300 (build 26300), 64 bits | Win32_OperatingSystem / platform |
| Python / torch | Python 3.14.7, torch 2.13.0+cu126 (CUDA 12.6), Ultralytics 8.4.129 | backend\venv |

O treino rodou nesta máquina. O log do treino traz `Ultralytics 8.4.129 Python-3.14.7 torch-2.13.0+cu126 CUDA:0 (NVIDIA GeForce RTX 3060, 12288MiB)`, que é exatamente a GPU e as versões de hoje, e os caminhos do log são `C:\Users\bruno\OneDrive\Área de Trabalho\TCC\...`. A memória de GPU usada no treino aparece no log como 4.73G.

---

## 3. Tempos de processamento

Comando: `backend\venv\Scripts\python.exe backend\benchmark_latencia.py --cpu --json latencia.json`
Rodou sem erro (exit 0) em 31/10/2026 14:49 UTC. O resultado completo está em `latencia.json` na raiz.

O benchmark grava banco e evidências numa pasta temporária, não no projeto. Como foi chamado da raiz, o `backend/.env` não foi lido. Isso não muda os tempos: TTA ligado, imgsz 1280 e conf 0.45 são os mesmos valores do uso local.

Tabela do terminal:

```
MotSP - medicao de latencia
============================================================
  medido_em:           2026-10-31T14:49:20+00:00
  so:                  Windows-11-10.0.26300-SP0
  cpu:                 Intel64 Family 6 Model 183 Stepping 1, GenuineIntel
  nucleos_fisicos:     14
  memoria_gb:          31.8
  gpu:                 NVIDIA GeForce RTX 3060
  cuda_disponivel:     True
  python:              3.14.7
  torch:               2.13.0+cu126
  modelo_transito:     C:\Users\bruno\OneDrive\Área de Trabalho\TCC\TCC-Atualizado\ml\models\gx-veiculos.pt
  modelo_alagamento:   C:\Users\bruno\OneDrive\Área de Trabalho\TCC\TCC-Atualizado\ml\models\gx-incident.pt
  imgsz:               1280
  conf_transito:       0.45
  conf_alagamento:     0.6
  frames:              20 (cameras CET-SP)

PARTIDA A FRIO (uma vez por processo)
-----------------------------------------------------------------------------------
Etapa                                       n     media       p50       p95       max
-----------------------------------------------------------------------------------
Carga do peso de transito (yolo11m, 1x)     1     546.0     546.0     546.0     546.0
Carga do peso de alagamento (1x)            1      86.2      86.2      86.2      86.2
-----------------------------------------------------------------------------------

INFERENCIA (regime permanente)
-----------------------------------------------------------------------------------------------
Etapa                                                   n     media       p50       p95       max
-----------------------------------------------------------------------------------------------
Primeira inferencia apos a carga (warm-up CUDA, 1x)     1    3204.4    3204.4    3204.4    3204.4
Inferencia YOLO11m @1280 (contagem de veiculos)        60      88.9      85.6     104.6     107.2
Inferencia do modelo de alagamento                     60      17.2      17.1      18.6      21.9
-----------------------------------------------------------------------------------------------

COMPARACAO DE HARDWARE
----------------------------------------------------------------------------
Etapa                                n     media       p50       p95       max
----------------------------------------------------------------------------
predict() em GPU (mesma chamada)     8      39.0      39.2      39.8      39.8
predict() em CPU (mesma chamada)     8     899.6     889.3     964.8     964.8
----------------------------------------------------------------------------

PIPELINE DE DETECCAO
-------------------------------------------------------------------------------------------------
Etapa                                                     n     media       p50       p95       max
-------------------------------------------------------------------------------------------------
Preparo do frame + inferencia (como no monitoramento)    60      92.3      91.5      99.8     135.8
-------------------------------------------------------------------------------------------------

PERSISTENCIA E FUSAO
--------------------------------------------------------------------------------------------------------
Etapa                                                            n     media       p50       p95       max
--------------------------------------------------------------------------------------------------------
Persistencia do evento + evidencia anotada (2 JPEG + commit)    10      20.4      13.3      82.3      82.3
Fusao de dados (IA + clima + fonte oficial) e gravacao          10      11.8       8.9      25.9      25.9
--------------------------------------------------------------------------------------------------------

API HTTP
-------------------------------------------------------------------------------------------
Etapa                                               n     media       p50       p95       max
-------------------------------------------------------------------------------------------
GET /health (piso da rede local + ASGI)            30       1.5       1.4       1.9       2.7
GET /eventos (carga do painel)                     30       3.9       3.0       6.1      29.0
POST /deteccao/imagem (upload do testador YOLO)    60     106.2     108.6     112.2     116.6
-------------------------------------------------------------------------------------------

PONTA A PONTA
----------------------------------------------------------------------------------------
Etapa                                            n     media       p50       p95       max
----------------------------------------------------------------------------------------
Broadcast do evento ate o painel (WebSocket)    10       0.5       0.4       0.9       0.9
Frame -> inferencia -> evento no painel         10     140.4     123.2     301.1     301.1
----------------------------------------------------------------------------------------

Tempos em milissegundos.
Resultado completo em latencia.json
```

O que cada linha mede, conforme `backend/benchmark_latencia.py`:
- "Inferencia YOLO11m @1280" chama `detectar_imagem_real`, igual ao sistema, com TTA ligado (`gx_yolo_tta=True` por padrão).
- A "COMPARACAO DE HARDWARE" chama `model.predict` sem TTA (`augment` não é passado), imgsz 1280 e 8 frames. É por isso que a GPU aparece com 39 ms ali e com 89 ms na inferência com TTA. Sem TTA, a CPU foi cerca de 23 vezes mais lenta que a GPU (899,6 ms contra 39,0 ms).
- A CPU medida é o i5-14600KF desta máquina, não a do Cloud Run, que tem 2 vCPU (item 4). Não há medição feita na nuvem.

O `latencia.json` tem também desvio-padrão e mínimo de cada etapa. Exemplo: inferência de contagem com desvio de 6,99 ms e mínimo de 81,5 ms; ponta a ponta com desvio de 55,3 ms e mínimo de 94,1 ms.

---

## 4. Configuração em uso

O `backend/app/config.py` lê o arquivo `.env` do diretório onde a API sobe. O `start.ps1` e o Dockerfile sobem a API a partir de `backend/`, então vale o `backend/.env`. Não existe `.env` na raiz.

| Parâmetro | Padrão (config.py) | Local (backend/.env) | Cloud Run (variáveis do serviço) |
|---|---|---|---|
| GX_LIVE_DETECTION_INTERVAL_SECONDS | 5.0 | **15** | **60** |
| YOLO_THRESHOLD | 0.45 | não definido → **0.45** | não definido → **0.45** |
| GX_YOLO_MODEL | ml/models/gx-veiculos.pt | não definido → **gx-veiculos.pt** | não definido → **gx-veiculos.pt** |
| GX_CAMERA_FRESCOR_MAXIMO_SEGUNDOS | 300.0 | **300** | não definido → **300** |
| Limite de confiabilidade do Data Fusion (GX_FUSION_AUTO_ATIVO_MIN) | 0.77 | não definido → **0.77** | não definido → **0.77** |
| Gatilho: piso (GX_TRANSITO_MIN_VEICULOS_CORROBORADO) | 4 | **4** | não definido → **4** |
| Gatilho: mínimo (GX_TRANSITO_MIN_VEICULOS) | 12 | **8** | não definido → **12** |
| Gatilho: confirmado (GX_TRANSITO_MIN_VEICULOS_CONFIRMADO) | 16 | não definido → **16** | não definido → **16** |
| Índice mínimo da TomTom (GX_TRANSITO_TOMTOM_INDICE_MINIMO) | 3.0 | não definido → 3.0 | não definido → 3.0 |
| Espera após recusa da TomTom (GX_TRANSITO_VETO_COOLDOWN_SECONDS) | 600 | 600 | não definido → 600 |
| Intervalo entre alertas no mesmo ponto (GX_ALERTA_COOLDOWN_SECONDS) | 1800 | não definido → 1800 | não definido → 1800 |
| Janela do evento / retenção (GX_EVENTO_JANELA_MINUTOS) | 45 | não definido → 45 | não definido → 45 |
| GX_YOLO_IMGSZ | 1280 | 1280 | 1280 |
| GX_YOLO_TTA | true | true | **false** (definido no Dockerfile) |

Atenção ao mínimo do gatilho: localmente é 8 (pelo `.env`) e na nuvem é 12 (o padrão). O `backend/.env` foi modificado pela última vez em 04/09/2026.

Como o gatilho funciona (`_avaliar_gatilho_transito` e `_processar_frame` em `backend/app/services/live_detection.py`):
- Menos de 4 veículos (piso): o frame é ignorado e a TomTom nem é consultada.
- 16 ou mais (confirmado): o evento é criado sem depender da TomTom.
- TomTom informa via fechada: o evento é criado.
- Entre o piso e o mínimo (4 a 7 local, 4 a 11 na nuvem): o evento só é criado se a TomTom confirmar, com índice ≥ 3,0. Sem resposta da TomTom, o frame é descartado.
- Entre o mínimo e o confirmado (8 a 15 local, 12 a 15 na nuvem): o evento é criado, a não ser que a TomTom diga que o trecho está fluindo (índice < 3,0). Sem resposta da TomTom, decide só pela contagem.
- O evento passa de `em_analise` para `ativo` quando a confiabilidade do Data Fusion, arredondada a 2 casas, chega a 0,77.

Onde está publicado: **Google Cloud Run** (consultado com `gcloud run services describe`, só leitura).
- Serviço `motsp`, região `southamerica-east1` (São Paulo), URL `https://motsp-xqporfao4a-rj.a.run.app`.
- Recursos: **2 vCPU, 4 GiB de RAM, sem GPU**. Não há `nodeSelector` nem acelerador no serviço, e o Dockerfile instala o torch só para CPU (`torch==2.5.1` do índice `whl/cpu`).
- Escala de 0 a 1 instância, concorrência 40, timeout 3600 s, startup CPU boost ligado.
- Revisão ativa: `motsp-00018-wbl`, de 23/10/2026 21:59 UTC. A imagem é do commit `33267d5`, o HEAD atual. O serviço foi criado em 20/09/2026.
- Variáveis no serviço: DATABASE_URL=sqlite:///./gx.db, GX_MONITORAMENTO_ATIVO=true, GX_TRANSITO_MONITORAR_CATALOGO=true, GX_ALAGAMENTO_MONITORAR_CATALOGO=true, GX_LIVE_DETECTION_INTERVAL_SECONDS=60, GX_SERVE_FRONTEND=true e TOMTOM_API_KEY (definida, valor não copiado).
- Compute Engine: não usado. A API do Compute Engine nem está habilitada no projeto.

---

## 5. Dados de operação

### Qual banco tem os dados

- **Local:** SQLite em `backend/gx.db`. O `backend/.env` tem `DATABASE_URL=mysql+pymysql://usuario:senha@...`, que é o valor de exemplo. O validador em `config.py` troca esse valor por `sqlite:///./gx.db`. Não há MySQL em uso.
- **Nuvem:** também SQLite (`DATABASE_URL=sqlite:///./gx.db`), mas **dentro do container do Cloud Run**. Esse arquivo some sempre que a instância desliga (o serviço escala a zero). Cloud SQL não é usado: a API `sqladmin` não está habilitada no projeto.
- O banco da nuvem **não foi consultado**. Não dá para ler o SQLite do container de fora, e chamar a API pública acordaria a instância e ligaria o monitoramento.

Todos os números abaixo vêm do `backend/gx.db` local (última gravação em 23/10/2026 18:55) e dos backups em `backend/data/backups/`.

### 5a) Período coberto

| Tabela | Registros | Primeiro | Último |
|---|---|---|---|
| eventos (gx.db) | **0** | — | — |
| logs_sistema (gx.db) | 32.044 | 22/08/2026 00:12:38 | 23/10/2026 20:52:52 |

Os 32.044 logs se dividem em 32.043 do módulo `data_fusion` e 1 do `api` (o seed). Todos são de nível INFO. Logs por dia: 22/08: 11 · 26/08: 53 · 27/08: 64 · 28/08: 5140 · 29/08: 5935 · 30/08: 82 · 31/08: 513 · 01/09: 34 · 02/09: 8942 · 03/09: 7 · 04/09: 7989 · 05/09: 82 · 09/09: 12 · 18/09: 19 · 21/09: 2034 · 23/09: 26 · 28/09: 6 · 02/10: 1084 · 05/10: 7 · 23/10: 4.

### 5b) Eventos de trânsito por status

**No gx.db atual: 0 eventos de qualquer tipo** (em_analise: 0, ativo: 0).

O único histórico de eventos de trânsito está nos backups antigos, de antes do modelo gx-veiculos (03/10):

| Backup | Trânsito em_analise | Trânsito ativo | Detectados entre |
|---|---|---|---|
| gx-antes-remocao-arvore-20260826-223125.db | 71 | 0 | 26/08 20:52 e 26/08 21:40 |
| gx-antes-remocao-camera22-20260826-224743.db | 72 | 0 | 26/08 20:52 e 27/08 01:36 |
| gx-before-demo-cleanup-20260823-231757.db | 0 | 1 (dado de demonstração do seed) | — |
| gx-antes-remocao-auth-20260903-192924.db | 0 | 0 | — |

Os dois primeiros backups se sobrepõem (são quase os mesmos eventos), então não devem ser somados.

### 5c) Recusas e confirmações da TomTom

**NÃO ENCONTRADO.** Onde procurei:
- O código registra essas decisões com `logger.info("Trânsito descartado em ...")` e `logger.info("Trânsito sinalizado em ...")`, que não vão para a tabela `logs_sistema`. A tabela só recebe as mudanças de status do Data Fusion.
- No Cloud Logging do serviço `motsp`, que guarda 30 dias (01/10 a 30/10/2026), não há nenhuma linha com "descartado", "sinalizado", "renovado", "TomTom" ou "Trânsito". O app não configura o `logging` do Python, então só avisos de nível WARNING chegam ao stdout.
- Os logs locais em `backend/data/*.log` são de 23/08/2026, antes do gatilho com a TomTom.

Dado relacionado que apareceu no Cloud Logging: entre 01/10 e 30/10/2026 houve **9.584 avisos** de "câmera travada num frame antigo", ou seja, frames descartados pela regra de frescor de 300 s. A câmera com mais avisos foi "Brasil - Av Henrique Schaumann" (1.398). Esses avisos valem para os dois monitoramentos (trânsito e alagamento), porque o aviso não diz qual dos dois descartou o frame.

### 5d) Média da confiabilidade dos eventos de trânsito

**NÃO ENCONTRADO no banco atual**, porque a tabela `eventos` está vazia.

O que existe:
- Backups antigos (agosto, antes do gx-veiculos e da versão atual do Data Fusion): 71 eventos de trânsito com confiabilidade média **0,7107**, mínimo 0,6429 e máximo 0,7977 (backup `gx-antes-remocao-arvore`). No backup `gx-antes-remocao-camera22`, 72 eventos com média 0,7110.
- `logs_sistema`: 32.043 registros do Data Fusion com média 0,7122, mediana 0,7149, mínimo 0,34 e máximo 0,9123. **Esses números não podem ser usados como média do trânsito.** Os logs não guardam o tipo do evento (o `evento_id` foi zerado pela retenção), misturam todos os tipos e contam várias vezes o mesmo evento. As versões antigas gravavam um log a cada novo cálculo. Hoje só se grava quando o status muda.
- Mudanças de status registradas nos logs: 111 promoções para ativo e 2 rebaixamentos para em análise, de todos os tipos. Desde 05/10 há 11 logs no formato atual (componentes "ia" e "contexto"), com média 0,8438. O tipo deles também não aparece.

### Aviso sobre a retenção

Os números do banco **não representam o histórico completo**. A retenção (`event_retention.py`, janela de 45 min) apaga eventos, evidências e dados contextuais e zera o `evento_id` nos logs. Por isso o gx.db local está sem nenhum evento. Na nuvem, além disso, o SQLite fica dentro do container e se perde a cada desligamento da instância: houve 55 desligamentos no período de 01/10 a 30/10. Para a seção 6, a contagem histórica de eventos de trânsito só pode vir dos backups de agosto, com as ressalvas acima.

---

## 6. Testes automatizados

Todos rodaram em 31/10/2026 com `backend\venv` (Python 3.14.7). Para o startup da API não mexer no `gx.db`, o pytest rodou com `DATABASE_URL` apontando para um SQLite temporário fora do projeto. Só foi definida a variável de ambiente, sem alterar código.

| Suíte | Comando | Resultado |
|---|---|---|
| Backend | `pytest tests -v` (em `backend/`) | **50 passaram**, 0 falhas, 1 aviso (deprecação do httpx no TestClient do Starlette) |
| Data Fusion | `pytest data_fusion -v` (na raiz) | **8 passaram**, 0 falhas |
| Frontend | `npm run test:frontend` (`node --test`) | **2 passaram**, 0 falhas |
| **Total** | | **60 passaram** |

Observação: `data_fusion/test_fusion.py` tem uma alteração ainda não commitada. Em `test_pesos_e_dimensoes_ausentes`, `modelo_ia` mudou de "YOLO11n" para "YOLO11m". O resultado acima é com essa alteração.

Separação alagamento × demais. Critério: o teste é de alagamento quando testa algo exclusivo do alagamento (modelo de incidente, monitoramento de alagamento, aviso do INMET, histórico de alagamento, fusão do alagamento). Testes de infraestrutura que só usam "alagamento" como tipo de exemplo ficaram em "demais".

| Suíte | Alagamento | Demais | Total |
|---|---|---|---|
| Backend | 10 | 40 | 50 |
| Data Fusion | 5 | 3 | 8 |
| Frontend | 0 | 2 | 2 |
| **Total** | **15** | **45** | **60** |

Testes de alagamento (15):
- Backend: `test_flood_detection.py` (6), `test_inmet_alert_source.py` (3) e `test_deteccao.py::test_incidente_imagem_retorna_deteccoes` (1).
- Data Fusion: `test_alagamento_pela_chuva`, `test_alagamento_combina_chuva_e_aviso_inmet`, `test_historico_da_via_reforca_ou_derruba_o_alagamento` e `test_historico_alagamento.py` (2).

Demais (45):
- Backend (40):
  - `test_live_detection.py` (7, gatilho de trânsito)
  - `test_tomtom_traffic_source.py` (2)
  - `test_tempo_real.py` (7)
  - `test_consultas.py` (5)
  - `test_data_fusion_service.py` (4)
  - `test_deteccao.py` (3)
  - `test_detector_concorrencia.py` (3)
  - `test_e2e.py` (3)
  - `test_event_retention.py` (2)
  - `test_evidencias.py` (2)
  - `test_cet_camera_catalog.py` (2)
- Data Fusion (3): `test_pesos_e_dimensoes_ausentes`, `test_transito_combina_veiculos_e_tomtom` e `test_transito_nota_e_peso_variam_continuamente`.
- Frontend (2): formatação dos percentuais da fusão e promoção pelo percentual exibido.

Testes de "demais" que usam alagamento só como exemplo: `test_e2e::test_fluxo_evento_detectado_ate_consulta`, `test_tempo_real::test_evento_detectado_chega_pelo_sse` e `test_consultas::test_listar_e_filtrar_eventos`. Os três de `test_detector_concorrencia` cobrem o carregamento dos dois modelos. Se quiser um critério mais rígido, mova esses 6 para alagamento: ficariam 21 de alagamento e 39 demais.

Testes ligados diretamente ao trânsito: 7 em `test_live_detection`, 2 em `test_tomtom_traffic_source` e 2 no Data Fusion, total de 11.
