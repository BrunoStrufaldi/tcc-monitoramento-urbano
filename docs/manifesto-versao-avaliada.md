# Manifesto da versão avaliada

[← voltar ao README](../README.md#documentação)

## 22. Manifesto da versão avaliada

Este documento liga os resultados do TCC (capítulo 6 e seção 4.6.6) a uma versão
exata do sistema: o código, os pesos do modelo, o ambiente, as partições do dataset,
os limiares e os testes. Com ele, qualquer pessoa consegue baixar a mesma versão e
conferir que ela é a que gerou os números do texto.

### 22.1 Identificação

| Item | Valor |
|---|---|
| Tag da versão avaliada | `v1.0-banca` |
| Release | https://github.com/BrunoStrufaldi/tcc-monitoramento-urbano/releases/tag/v1.0-banca |
| Código do sistema publicado | commit `a14223061c9afcba0439c551a39c2a2f9d92b1af` (02/11/2026). A tag aponta para o commit seguinte, que só acrescenta este manifesto e o replay sintético, sem mudar o sistema |
| Código usado no treino do modelo | commit `87346e49a839cc504d8a5600dca2cb475b200ff8` (03/10/2026) |
| Pacote do modelo (Zenodo) | DOI https://doi.org/10.5281/zenodo.23866184 |
| Serviço na nuvem | Google Cloud Run, serviço `motsp`, região `southamerica-east1`, revisão `motsp-00022-ld5` |
| Imagem Docker publicada | `motsp:a14223061c9afcba0439c551a39c2a2f9d92b1af`, digest `sha256:80ceb7b3c65af6a627ef64456412d90c2fd0f487ebc40435ba36cdea70d82a64` |
| Build que gerou a imagem | Cloud Build `4f5f963b-ce09-4b0b-97e5-bec7a1d176ef` (03/11/2026 00:23 UTC) |

Para ver que a tag não muda o sistema, rode `git diff --stat a142230 v1.0-banca`. Só
aparecem este manifesto, o replay, o teste do replay, a saída esperada e ajustes de
documentação.

A imagem do Cloud Run recebe como etiqueta o hash do commit (ver `cloudbuild.yaml`).
Por isso dá para confirmar qual código está no ar com
`gcloud run services describe motsp --region southamerica-east1`.

### 22.2 Pesos dos modelos (SHA-256)

| Arquivo | Papel | SHA-256 |
|---|---|---|
| `ml/models/gx-veiculos.pt` | Contagem de veículos (YOLO11m ajustado, época 15). No Zenodo se chama `YOLO11m-veiculos.pt` | `d6d028a6f2395a34b46b6cf43042c4c410bb792e4f272d5996f67e6fe5c68465` |
| `ml/models/gx-incident.pt` | Detecção de alagamento | `1415c846b30135b2c746195baa9320806fa43417c4d0ecdbaf9c7d8735fd22ff` |
| `ml/models/yolo11m.pt` | Pesos de partida do ajuste (COCO, Ultralytics) | `d5ffc1a674953a08e11a8d21e022781b1b23a19b730afc309290bd9fb5305b95` |
| `yolo11x.pt` (fora do repositório) | "Professor" que gerou os rótulos (COCO, Ultralytics) | `7bc158aa95c0ebfdd87f70f01653c1131b93e92522dbe15c228bcd742e773a24` |

Para conferir: `sha256sum ml/models/gx-veiculos.pt` (Linux) ou
`Get-FileHash ml\models\gx-veiculos.pt` (PowerShell).

### 22.3 Ambiente

| | Treino do modelo | Testes e medições locais | Cloud Run (versão publicada) |
|---|---|---|---|
| Data | 03/10/2026 | 31/10 e 16/11/2026 | build de 03/11/2026 |
| Python | 3.14.7 | 3.14.7 | 3.11 (imagem `python:3.11-slim`) |
| Ultralytics | 8.4.129 | 8.4.129 | 8.4.198 |
| PyTorch | 2.13.0+cu126 | 2.13.0+cu126 | 2.5.1+cpu |
| FastAPI | não usado | 0.141.1 | 0.162.0 |
| SQLAlchemy | não usado | 2.0.52 | 2.1.6 |
| Pydantic / pydantic-settings | não usado | 2.13.4 / 2.15.0 | 2.14.2 / 2.16.2 |
| Uvicorn | não usado | 0.52.4 | 0.54.0 |
| Pillow | 12.3.0 | 12.3.0 | 13.0.0 |
| Node (compila o painel) | não usado | 20 | 20 (imagem `node:20-slim`) |
| Hardware | RTX 3060 12 GB, i5-14600KF, 32 GB | o mesmo | 2 vCPU, 4 GiB, sem GPU |
| Sistema | Windows 11 | Windows 11 | Linux (Debian, imagem slim) |

As versões do Cloud Run foram tiradas do log do build `4f5f963b`. Os
`requirements.txt` usam versão mínima (`>=`), então um build novo pode instalar versões
mais recentes. A versão avaliada é a da tabela.

### 22.4 Partições do dataset do modelo de veículos

| Partição | Frames | Carro | Moto | Ônibus | Caminhão | Veículos | Caixas (todas as classes) |
|---|---|---|---|---|---|---|---|
| Treino | 318 | 3.871 | 185 | 222 | 244 | 4.522 | 5.662 |
| Teste | 79 | 862 | 24 | 37 | 66 | 989 | 1.268 |
| Total | 397 | 4.733 | 209 | 259 | 310 | 5.511 | 6.930 |

Os 397 frames são únicos (repetidos pelo SHA-256 foram descartados), capturados entre
26/08 e 02/10/2026 e divididos de forma aleatória com semente 42. A lista completa está
em `dataset/frames.csv` no Zenodo, com uma linha por frame: nome, partição, SHA-256 da
imagem, data da captura e número de veículos. Com ela dá para conferir que nenhum frame
está nas duas partições. As imagens não foram publicadas porque mostram pessoas e
placas (LGPD). O SHA-256 de `frames.csv` é
`61a6d1906d25ffb80624ee2093fd596694c04a02407b7be282d15265465e7bc0`.

Limitação: o conjunto de teste também foi usado como validação para escolher a melhor
época, então as métricas tendem a ser um pouco otimistas.

### 22.5 Condições de inferência

| Parâmetro | Veículos | Alagamento |
|---|---|---|
| Modelo | `gx-veiculos.pt` | `gx-incident.pt` |
| Confiança mínima | 0,45 (`YOLO_THRESHOLD`) | 0,60 (`GX_YOLO_INCIDENT_CONF`) |
| IoU da supressão de caixas | 0,7 (padrão do Ultralytics) | 0,7 (padrão do Ultralytics) |
| Tamanho da imagem (imgsz) | 1280 | 640 (padrão do Ultralytics) |
| TTA | ligado no local, desligado no Cloud Run (`GX_YOLO_TTA=false` no Dockerfile) | não usado |
| Dispositivo | GPU no local, CPU no Cloud Run | o mesmo |
| Inferências simultâneas | 2 (`GX_YOLO_MAX_CONCORRENCIA`) | 2 |
| Intervalo entre imagens de cada câmera | 15 s no local, 60 s no Cloud Run | o mesmo |

As métricas do capítulo 6 (mAP50 0,848 etc.) foram medidas com confiança 0,45 e
imgsz 1280 na GPU local, conforme `avaliacao.txt` no Zenodo.

### 22.6 Limiares de decisão e de fusão

Valores da versão publicada. São os padrões de `backend/app/config.py`, porque o Cloud
Run não sobrescreve nenhum deles.

| Regra | Valor | Variável |
|---|---|---|
| Abaixo disso a imagem é descartada sem consultar a TomTom | 4 veículos | `GX_TRANSITO_MIN_VEICULOS_CORROBORADO` |
| De 4 a 11 veículos, só cria se a TomTom confirmar lentidão | 12 veículos | `GX_TRANSITO_MIN_VEICULOS` |
| A partir disso cria sem depender da TomTom | 16 veículos | `GX_TRANSITO_MIN_VEICULOS_CONFIRMADO` |
| Índice da TomTom que confirma lentidão | 3,0 (de 0 a 10) | `GX_TRANSITO_TOMTOM_INDICE_MINIMO` |
| Intervalo entre alertas na mesma câmera | 1.800 s (30 min) | `GX_ALERTA_COOLDOWN_SECONDS` |
| Espera depois de uma recusa da TomTom | 600 s (10 min) | `GX_TRANSITO_VETO_COOLDOWN_SECONDS` |
| Idade máxima do frame (câmera travada) | 300 s | `GX_CAMERA_FRESCOR_MAXIMO_SEGUNDOS` |
| Tempo até o evento expirar sem nova detecção | 45 min | `GX_EVENTO_JANELA_MINUTOS` |
| Confiabilidade para passar de "em análise" a "ativo" | 0,80 | `GX_FUSION_AUTO_ATIVO_MIN` |
| Pesos da fusão (fixos) | IA 4/7 (57%), contexto 3/7 (43%) | `data_fusion/fusion.py` |
| Faixas de nível | alta a partir de 0,80, média a partir de 0,55 | `data_fusion/fusion.py` |
| Rotina de manutenção (expira, junta repetidos, recalcula notas) | a cada 120 s | `backend/app/main.py` |

Diferença no ambiente local: o `backend/.env` da máquina de desenvolvimento usa
`GX_TRANSITO_MIN_VEICULOS=8`. Os números do texto e o replay usam o valor da versão
publicada (12).

O limiar de 0,80 entrou no commit `c92a388` (02/11/2026). Antes dele o padrão era 0,77.

### 22.7 Diário de métricas do treino

Arquivo completo: `treino/results.csv` no Zenodo (SHA-256
`b3542a39eb2e208e05b6ad0221bf84d90a351c3bfe1c5c11674a9104c3c3b43c`), com perdas,
métricas e taxa de aprendizado de cada época. As métricas abaixo são da validação do
Ultralytics, com todas as classes que o professor marcou. A comparação só com veículos
(mAP50 0,848) está em `avaliacao.txt`.

Perda = soma de box, cls e dfl. A época 15 (em negrito) é a melhor e gerou o
`gx-veiculos.pt`. O treino parou na época 30 por falta de melhora em 15 épocas.

| Época | Perda treino | Perda validação | Precisão | Recall | mAP50 | mAP50-95 |
|---|---|---|---|---|---|---|
| 1 | 2,479 | 1,964 | 0,727 | 0,610 | 0,747 | 0,601 |
| 2 | 2,150 | 1,927 | 0,564 | 0,669 | 0,741 | 0,604 |
| 3 | 2,070 | 1,896 | 0,607 | 0,702 | 0,754 | 0,597 |
| 4 | 2,036 | 1,905 | 0,587 | 0,751 | 0,730 | 0,596 |
| 5 | 2,050 | 1,925 | 0,701 | 0,641 | 0,733 | 0,589 |
| 6 | 2,000 | 1,901 | 0,705 | 0,675 | 0,739 | 0,589 |
| 7 | 1,956 | 1,874 | 0,706 | 0,638 | 0,741 | 0,591 |
| 8 | 1,931 | 1,869 | 0,637 | 0,676 | 0,721 | 0,580 |
| 9 | 1,907 | 1,863 | 0,715 | 0,594 | 0,710 | 0,571 |
| 10 | 1,895 | 1,832 | 0,742 | 0,657 | 0,730 | 0,603 |
| 11 | 1,864 | 1,852 | 0,690 | 0,650 | 0,721 | 0,583 |
| 12 | 1,837 | 1,857 | 0,656 | 0,682 | 0,727 | 0,601 |
| 13 | 1,822 | 1,839 | 0,680 | 0,707 | 0,724 | 0,594 |
| 14 | 1,817 | 1,845 | 0,588 | 0,678 | 0,724 | 0,596 |
| **15** | **1,801** | **1,836** | **0,644** | **0,722** | **0,747** | **0,606** |
| 16 | 1,785 | 1,829 | 0,664 | 0,725 | 0,744 | 0,603 |
| 17 | 1,767 | 1,845 | 0,682 | 0,662 | 0,724 | 0,588 |
| 18 | 1,762 | 1,838 | 0,764 | 0,640 | 0,713 | 0,573 |
| 19 | 1,752 | 1,817 | 0,772 | 0,625 | 0,715 | 0,591 |
| 20 | 1,740 | 1,827 | 0,621 | 0,736 | 0,734 | 0,595 |
| 21 | 1,754 | 1,837 | 0,646 | 0,755 | 0,735 | 0,604 |
| 22 | 1,761 | 1,829 | 0,700 | 0,717 | 0,729 | 0,598 |
| 23 | 1,720 | 1,850 | 0,690 | 0,676 | 0,706 | 0,571 |
| 24 | 1,712 | 1,832 | 0,752 | 0,646 | 0,707 | 0,569 |
| 25 | 1,689 | 1,836 | 0,783 | 0,638 | 0,712 | 0,574 |
| 26 | 1,705 | 1,807 | 0,806 | 0,660 | 0,735 | 0,597 |
| 27 | 1,693 | 1,835 | 0,694 | 0,682 | 0,725 | 0,592 |
| 28 | 1,699 | 1,820 | 0,771 | 0,693 | 0,731 | 0,598 |
| 29 | 1,679 | 1,825 | 0,731 | 0,730 | 0,757 | 0,596 |
| 30 | 1,663 | 1,834 | 0,716 | 0,706 | 0,729 | 0,592 |

### 22.8 Matriz requisito-teste

Requisitos da seção 4.6.1 do TCC. Os testes ficam em `backend/tests/`, `data_fusion/`
e `frontend/tests/`. "Replay" indica o cenário do replay sintético (seção 22.10).

| Requisito | O que é verificado | Teste | Resultado |
|---|---|---|---|
| RF01 Monitorar câmeras e descartar frames idênticos ou desatualizados | Frame com mais de 300 s é ignorado | `test_cet_camera_catalog::test_frame_antigo_e_desatualizado`, `test_live_detection::test_loop_ignora_frame_desatualizado_e_nao_processa`, `test_flood_detection::test_loop_ignora_frame_desatualizado_e_nao_processa`, replay C1 | passou |
| | Frame igual ao anterior (mesmo SHA-256) não vai para o YOLO | replay C2 | passou |
| | Uma thread por câmera, só quando o monitoramento está ligado | `test_live_detection::test_iniciar_sobe_uma_thread_por_camera_so_quando_ligado`, `test_flood_detection::test_iniciar_sobe_uma_thread_por_camera_so_quando_ligado` | passou |
| RF02 Contar veículos com IA e detectar congestionamento | Faixas de 4, 12 e 16 veículos | `test_live_detection::test_gatilho_de_tres_faixas_com_a_tomtom`, `test_live_detection::test_processar_frame_com_poucos_veiculos_nem_consulta_a_tomtom`, replay T1, T5 | passou |
| | Sem modelo ou em espera, nada é criado | `test_live_detection::test_processar_frame_nao_cria_em_espera_ou_sem_modelo` | passou |
| RF03 Consultar a TomTom | Cálculo do índice e falha de rede | `test_tomtom_traffic_source` (2 testes) | passou |
| | TomTom confirma ou recusa o evento | `test_live_detection::test_processar_frame_cria_transito_com_as_duas_fontes`, `test_live_detection::test_processar_frame_veto_da_tomtom_nao_cria_e_espera_pouco`, replay T2, T3, T4 | passou |
| RF04 Calcular a confiabilidade (Data Fusion) | Pesos, chuva, aviso do INMET, histórico, trânsito | `data_fusion/test_fusion.py` (8 testes), `data_fusion/test_historico_alagamento.py` (2), `test_e2e::test_fluxo_fusao_dados`, replay T1, T3, A1, A2 | passou |
| RF05 "Em análise" abaixo de 80% e "ativo" a partir de 80%, em tempo real | Promoção e rebaixamento pelo limiar arredondado | `test_data_fusion_service` (3 testes de limiar), `frontend/tests/fusion-format.test.mjs` (2), replay T1 (0,86 ativo), T3 (0,77 em análise) | passou |
| | Painel recebe o evento em tempo real | `test_tempo_real` (7 testes) | passou |
| RF06 Guardar foto original, foto marcada e hash | Arquivos gravados e SHA-256 da original | `test_evidencias::test_registrar_deteccao_grava_evento_e_evidencia_auditavel`, `test_evidencias::test_obter_arquivo_de_evidencia` | passou |
| RF07 Rotina periódica: expirar em 45 min, juntar repetidos, recalcular notas | Expiração e junção | `test_event_retention` (2 testes), replay E1 | passou |
| | Recalcular notas | `test_data_fusion_service::test_evento_yolo_e_rebaixado_abaixo_do_limiar_mas_o_manual_nao` | passou |
| | Intervalo de 120 s | leitura de `backend/app/main.py` | verificação manual |
| RNF01 Python, FastAPI e Uvicorn | API e painel respondem | `test_e2e::test_painel_e_status_da_api` | passou |
| RNF02 YOLO11m, Ultralytics e Pillow | Cada modelo carrega uma vez, inferências limitadas, configuração lida | `test_detector_concorrencia` (3 testes), `test_deteccao::test_status_e_classes_do_detector` | passou |
| | Pesos usados | SHA-256 da seção 22.2 | conferido |
| RNF03 WebSocket com alternativa | WebSocket, SSE e reconexão | `test_tempo_real` (7 testes) | passou |
| | Polling quando WebSocket e SSE caem | painel | verificação manual |
| RNF04 TypeScript e Leaflet | Funções do painel | `frontend/tests/busca-local.test.mjs` (2), `frontend/tests/fusion-format.test.mjs` (2) | passou |
| | Mapa e marcadores | painel | verificação manual |
| RNF05 SQLite com suporte a MySQL, via SQLAlchemy | Consultas e filtros | `test_consultas` (5 testes), todos rodando em SQLite | passou |
| | MySQL | não testado | não verificado |
| RNF06 Cloud Run com publicação pelo Cloud Build | Versão no ar | build `4f5f963b`, revisão `motsp-00022-ld5` (seção 22.1) | conferido |
| RNF07 HTTPS e variáveis protegidas pelo Pydantic | Configuração lida das variáveis de ambiente | `test_detector_concorrencia::test_configuracao_do_yolo_vem_do_settings` | passou |
| | Painel só consulta, sem rotas de escrita | `test_consultas::test_rotas_de_escrita_nao_existem`, `test_deteccao::test_rotas_de_upload_foram_removidas` | passou |
| | HTTPS | URL do Cloud Run (`https://motsp-xqporfao4a-rj.a.run.app`) | verificação manual |

Total na versão da tag: 63 testes automatizados, todos aprovados em 16/11/2026
(51 no back-end, 8 no Data Fusion e 4 no front-end). O 51º do back-end é
`test_replay_sintetico`, que roda o replay e compara com a saída esperada.

Os testes rodam com banco em memória e com o YOLO, a TomTom e as câmeras simulados. A
qualidade do modelo real é medida à parte (seção 22.7 e `avaliacao.txt` no Zenodo).

### 22.9 Logs sanitizados

O que existe e como foi limpo:

| Origem | O que mostra | Limpeza |
|---|---|---|
| Saída do replay (`backend/replay_saida_esperada.txt`) | Cada decisão do sistema (evento criado, recusa da TomTom, frame ignorado) com o motivo | Dados 100% sintéticos. A data do frame vira `<data do frame>` |
| Cloud Logging do serviço `motsp` (01/10 a 30/10/2026) | 9.584 avisos de câmera travada, ou seja, frames descartados pela regra dos 300 s | Só a contagem foi usada. Endereços das câmeras são públicos (CET-SP) |
| Tabela `logs_sistema` | Mudanças de status feitas pelo Data Fusion | Sem dados pessoais nem chaves |
| `treino/treino_veiculos.log` no Zenodo | Log completo do treino | Caminhos da máquina trocados por `<projeto>` |

A chave da TomTom fica só nas variáveis de ambiente do Cloud Run e no `backend/.env`,
que não vai para o Git. Ela vai na URL da consulta, e a biblioteca httpx registra URLs
em nível INFO. Como o sistema não liga o nível INFO, essas linhas não são gravadas: no
Cloud Logging de 01/10 a 30/10/2026 não há nenhuma linha com "TomTom". Se o nível INFO
for ligado no futuro, será preciso filtrar a chave antes.

Limitação: o sistema não configura o `logging` do Python, então no Cloud Run só chegam
avisos (WARNING). As decisões de trânsito (nível INFO) não ficaram registradas na nuvem.
O replay mostra essas decisões com entradas sintéticas.

### 22.10 Replay sintético

`backend/replay_sintetico.py` roda as regras do sistema com entradas fixas, sem imagens
reais, sem internet, sem GPU e sem os modelos. A contagem do YOLO e as respostas da
TomTom, do clima e do INMET são simuladas, e o banco é um SQLite em memória. O script
fixa os limiares da seção 22.6, então o resultado não depende do `.env`.

```powershell
cd backend
venv\Scripts\python replay_sintetico.py
```

O script mostra a saída e termina com `OK: a saída é igual à esperada.` A saída esperada
fica em `backend/replay_saida_esperada.txt`. Os cenários:

| Cenário | Entrada | Saída esperada | Regra |
|---|---|---|---|
| T1 | 18 veículos, TomTom fora do ar | evento criado, confiabilidade 0,86, ativo | 16 ou mais cria direto |
| T2 | 13 veículos, TomTom índice 1,0 | nada criado | TomTom diz que flui |
| T3 | 6 veículos, TomTom índice 8,0 | evento criado, 0,77, em análise | contagem baixa sustentada pela TomTom, mas abaixo de 0,80 |
| T4 | 6 veículos, TomTom fora do ar | nada criado | contagem baixa sem confirmação |
| T5 | 3 veículos | nada criado, TomTom nem consultada | abaixo do piso de 4 |
| T6 e T7 | 18 veículos duas vezes na mesma câmera | um evento só | intervalo de 30 min entre alertas |
| A1 | alagamento 0,81 sem chuva, aviso ou histórico | evento criado, 0,57, em análise | contexto fraco derruba a nota |
| A2 | alagamento 0,81, chuva 30 mm/h, INMET 9,5, via que alaga sempre | evento criado, 0,89, ativo | contexto forte confirma |
| C1 | frame com 10 min de idade | não vai para o YOLO | frame acima de 300 s |
| C2 | o mesmo frame 3 vezes e depois um novo | só 2 vão para o YOLO | SHA-256 igual ao anterior |
| E1 | eventos de 50 e de 10 min atrás | o de 50 min é removido | janela de 45 min |

### 22.11 Como conferir

```bash
git clone https://github.com/BrunoStrufaldi/tcc-monitoramento-urbano.git
cd tcc-monitoramento-urbano
git checkout v1.0-banca

sha256sum ml/models/gx-veiculos.pt     # deve dar d6d028a6...c5e68465

cd backend
python -m venv venv
venv/Scripts/pip install -r requirements.txt
venv/Scripts/python -m pytest -q        # 51 passed
venv/Scripts/python replay_sintetico.py # OK: a saída é igual à esperada.
cd ..
backend/venv/Scripts/python -m pytest -q data_fusion   # 8 passed
npm install && npm run test:frontend                   # 4 pass
```

No Linux, troque `venv/Scripts` por `venv/bin`. O Ultralytics não é necessário para os
testes nem para o replay.
