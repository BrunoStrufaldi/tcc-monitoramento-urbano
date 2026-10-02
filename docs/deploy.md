# Deploy no Google Cloud Run

[← voltar ao README](../README.md#documentação)

## 21. Deploy no Google Cloud Run

O sistema sobe como **uma única imagem** (API + painel + YOLO) no Cloud Run. A
escolha não é arbitrária: o Cloud Run escala a zero, então **não existe
instância ligada enquanto ninguém está usando o link** — que é exatamente o
regime de custo que um TCC hospedado com crédito gratuito precisa.

### 21.1 Por que o sistema "só funciona quando alguém entra"

Três mecanismos se somam, e vale entender a diferença entre eles:

| Mecanismo | Efeito |
|---|---|
| `--min-instances 0` | Sem acesso, zero instâncias de pé. Zero cobrança. |
| CPU alocada por requisição | O Cloud Run congela a CPU do container entre requisições. As threads de `live_detection` e `flood_detection` **não rodam** com o painel fechado, mesmo com `GX_MONITORAMENTO_ATIVO=true`. |
| WebSocket do painel | Enquanto alguém tem o painel aberto, o `/ws` mantém uma requisição viva — e é durante ela que a CPU fica alocada e a detecção contínua efetivamente acontece. |

Ou seja: o próprio acesso de uma pessoa é o "gatilho de ativação". Fechou o
painel, o monitoramento para; ~15 minutos depois a instância é destruída.

`--max-instances 1` é igualmente proposital: o banco é um SQLite **dentro** do
container, então duas instâncias simultâneas teriam estados divergentes. Serve
também de teto de gasto — um pico de acessos não multiplica a conta.

### 21.2 O que sobe e o que não sobe

| Vai para a imagem | Fica de fora (`.dockerignore` / `.gcloudignore`) |
|---|---|
| `backend/`, `ml/`, `data_fusion/`, `database/`, `frontend/` compilado | `backend/venv/` (4,8 GB), `ml/datasets/` (5,4 GB), `ml/runs/`, `runs/` |
| `ml/models/yolo11m.pt` e `ml/models/gx-incident.pt` | demais pesos (`-anterior`, `-backup`, `-v4-attempt`, `yolo11n/s`) |
| torch **CPU** + ultralytics | `backend/.env`, `*.db`, `backend/app/data/` (evidências locais), testes |

> **Armadilha do `.gcloudignore`.** Sem esse arquivo, o `gcloud` usa o
> `.gitignore` como filtro de upload — e o `.gitignore` exclui `ml/models/*.pt`.
> A imagem subiria sem peso nenhum e toda rota de detecção responderia
> "modelo indisponível". O `.gcloudignore` existe para quebrar essa herança.

O `Dockerfile` instala o torch pelo índice de CPU
(`--index-url https://download.pytorch.org/whl/cpu`). O wheel padrão do PyPI
traz ~2,5 GB de CUDA que não tem uso no Cloud Run, que não oferece GPU no plano
gratuito.

### 21.3 Passo a passo (primeira vez)

**1. Criar a conta e o projeto**

1. Entre em <https://console.cloud.google.com> com uma conta Google.
2. Aceite a **avaliação gratuita**: US$ 300 de crédito por 90 dias. Exige cartão
   (há uma cobrança temporária de verificação, ~R$ 1, estornada). Ao fim do
   período o Google **não** cobra automaticamente: é preciso fazer o upgrade
   manual para conta paga.
3. Crie um projeto — ex.: nome `MotSP TCC`, e **anote o Project ID** gerado
   (algo como `motsp-tcc-473120`). É o ID, não o nome, que os comandos usam.

**2. Instalar o Google Cloud CLI**

Baixe e instale o [GoogleCloudSDKInstaller.exe](https://dl.google.com/dl/cloudsdk/channels/rapid/GoogleCloudSDKInstaller.exe),
depois, num PowerShell novo:

```powershell
gcloud init      # faz login no navegador e seleciona o projeto
```

**3. Publicar**

```powershell
.\deploy.ps1 -ProjectId SEU-PROJECT-ID
```

O script habilita as APIs necessárias (Cloud Run, Cloud Build, Artifact
Registry), lê a `TOMTOM_API_KEY` do `backend/.env` e a envia como variável de
ambiente do serviço, e dispara o build. Na primeira execução o `gcloud` pergunta
se pode criar o repositório `cloud-run-source-deploy` — responda `Y`.

A primeira build leva ~10 minutos (instalar o torch domina o tempo). No fim, o
script imprime a URL pública, no formato
`https://motsp-XXXXXXXX.southamerica-east1.run.app`. **Esse é o link para
compartilhar** — o serviço sobe com `--allow-unauthenticated`, então qualquer
pessoa com o endereço abre o painel, sem conta Google.

**4. Ligar o monitoramento contínuo (opcional)**

No primeiro deploy as threads de detecção sobem **desligadas** (padrão do
`config.py`): o painel funciona, a inferência sob demanda funciona, e nada
consome CPU sozinho. O script só mexe nesse estado quando você pede — um
redeploy sem flag **preserva** o que está na nuvem (ele usa `--update-env-vars`,
que mescla, e não `--set-env-vars`, que substituiria tudo).

```powershell
.\deploy.ps1 -ProjectId SEU-PROJECT-ID -Monitoramento -PularApis          # liga
.\deploy.ps1 -ProjectId SEU-PROJECT-ID -DesligarMonitoramento -PularApis  # desliga
```

Ou, sem rebuildar a imagem:

```powershell
gcloud run services update motsp --region southamerica-east1 --update-env-vars "GX_MONITORAMENTO_ATIVO=true,GX_TRANSITO_MONITORAR_CATALOGO=true"
```

> As **aspas são obrigatórias no PowerShell**: sem elas, `a,b` vira uma lista e o
> gcloud recebe um único valor `"true GX_TRANSITO_MONITORAR_CATALOGO=true"`. O
> pydantic recusa o booleano, o container sai com `exit(1)` e o Cloud Run
> reporta "failed to start and listen on the port" — a mensagem engana: a porta
> não é o problema, o log da revisão mostra o `ValidationError` real.

> Em CPU, uma inferência do `yolo11m` a `imgsz=1280` custa alguns segundos —
> ordens de grandeza acima da GPU local. Por isso o deploy usa
> `GX_LIVE_DETECTION_INTERVAL_SECONDS=60` em vez dos 15s locais. Ligar as 20
> threads do catálogo (10 trânsito + 10 alagamento) em 2 vCPU satura a
> instância: para demonstração, prefira ligar só `GX_TRANSITO_MONITORAR_CATALOGO`,
> ou apontar `GX_CAMERA_SNAPSHOT_URL` para uma câmera só.

### 21.4 Custo e proteção do crédito

Cota gratuita mensal do Cloud Run: 180.000 vCPU-s, 360.000 GiB-s e 2 milhões de
requisições. Com a configuração deste deploy (2 vCPU / 4 GiB), isso equivale a
**~25 horas por mês de painel aberto, de graça**. Acima disso, ~US$ 0,30 por
hora de uso efetivo — e o crédito de US$ 300 cobre ~1.000 horas. Com o painel
fechado, o custo é o armazenamento da imagem no Artifact Registry: centavos.

Proteções recomendadas:

1. **Orçamento com alerta**: Console → Faturamento → Orçamentos e alertas →
   criar orçamento de, por exemplo, US$ 20 com alerta em 50%/90%/100%.
2. **`--max-instances 1`**: já aplicado pelo script; é o teto físico do gasto.
3. **Desligar de vez** quando a banca acabar:
   ```powershell
   gcloud run services delete motsp --region southamerica-east1
   ```

### 21.5 Limitações conhecidas do ambiente de nuvem

- **Primeiro acesso é lento.** A imagem tem ~2 GB (torch + pesos); o cold start
  fica entre 30 e 60 segundos. Se for apresentar para a banca, abra o link
  alguns minutos antes para "acordar" o serviço.
- **O banco não persiste.** O SQLite vive no sistema de arquivos efêmero do
  container: cada vez que o serviço acorda, começa vazio e as tabelas são
  recriadas no startup. Coerente com a janela de 45 minutos dos eventos
  ([§13](data-fusion.md#13-ciclo-de-vida-de-um-evento)), mas nada sobrevive ao sono. Para
  persistir de verdade seria preciso montar um bucket do Cloud Storage ou usar
  Cloud SQL — nenhum dos dois é gratuito de forma indefinida.
- **Memória é o gargalo, não CPU.** No primeiro deploy com monitoramento ligado
  o container foi morto por OOM (`4249 MiB` de `4096`) 19 s depois de carregar
  o YOLO: as 10 threads de cada tipo chegavam juntas no carregamento e cada uma
  subia a própria cópia do peso, e depois inferiam todas ao mesmo tempo. A
  trava de carga e o semáforo de inferência (`GX_YOLO_MAX_CONCORRENCIA`, [§5](configuracao.md#modelos-yolo))
  existem por causa disso. Quando o container morre, o SQLite morre junto —
  o painel volta a zero sem nenhum aviso.
- **Evidências ocupam memória.** Os JPEGs anotados são gravados em
  `backend/app/data/evidencias/`, que no Cloud Run é um tmpfs contado dentro dos
  4 GiB de RAM da instância.

### 21.6 Diferenças de execução entre local e container

Nenhuma no painel: nos dois casos o FastAPI serve `frontend/` em `/` (flag
`GX_SERVE_FRONTEND`, padrão `true`), `GET /api/status` responde o status da API e
`frontend/js/config.js` usa `window.location.origin` como `API_BASE_URL` — mesma origem,
sem CORS. O mount é registrado **depois** de todos os routers, senão engoliria
`/eventos`, `/ws` e `/docs`. Com a flag desligada, `/` volta a ser o JSON de status.

O que muda é só a configuração: local lê `backend/.env`; no Cloud Run vêm das variáveis
de ambiente do serviço.

### 21.7 Deploy automático a cada push (Cloud Build)

`cloudbuild.yaml` na raiz descreve o caminho automático: um gatilho do Cloud
Build observa a branch `main` do GitHub e, a cada push, builda a imagem com o
mesmo `Dockerfile`, envia ao Artifact Registry e publica uma revisão nova no
Cloud Run. É o mesmo resultado do `deploy.ps1`, sem depender da máquina local.

| | `deploy.ps1` (manual) | Gatilho do Cloud Build (automático) |
|---|---|---|
| Fonte do código | pasta local, como está no disco (`.gcloudignore` filtra) | clone do GitHub (só o que está commitado) |
| Pesos do YOLO | copiados do disco | **precisam estar no Git** — por isso `.gitignore` libera só `yolo11m.pt` e `gx-incident.pt` |
| Variáveis do serviço | mescla as que o script conhece (`--update-env-vars`) | não toca em nenhuma: memória, TomTom e monitoramento ficam como estão |
| Quando usar | emergência, ou testar sem passar pelo GitHub | rotina: `git push` e pronto |

Cada push na `main` é uma publicação real (~10 min de build; a cota gratuita
do Cloud Build é de 120 min/dia). Trabalho em andamento fica em branch e só
entra na `main` quando estiver pronto para o link público.

**Ativação (uma vez).** Depois de commitar `cloudbuild.yaml` e os dois pesos:

1. Console → **Cloud Build → Gatilhos → Conectar repositório** (instala o app
   do Cloud Build no GitHub e autoriza o repositório).
2. **Criar gatilho**: evento *push para uma branch*, branch `^main$`, tipo de
   configuração *arquivo de configuração do Cloud Build*, local `cloudbuild.yaml`,
   conta de serviço a do Compute (`<número>-compute@developer.gserviceaccount.com`).
3. Essa conta precisa, além de `cloudbuild.builds.builder` (o `deploy.ps1` já
   concede), de **Cloud Run Admin** e **Service Account User** para o passo de
   deploy — sem eles a build passa e a publicação falha com *permission denied*:
   ```powershell
   gcloud projects add-iam-policy-binding SEU-PROJECT-ID --member "serviceAccount:NUMERO-compute@developer.gserviceaccount.com" --role roles/run.admin
   gcloud projects add-iam-policy-binding SEU-PROJECT-ID --member "serviceAccount:NUMERO-compute@developer.gserviceaccount.com" --role roles/iam.serviceAccountUser
   ```

O gatilho também pode ser criado por linha de comando
(`gcloud builds triggers create github ...`), mas a conexão com o GitHub
(passo 1) só existe pelo console.
