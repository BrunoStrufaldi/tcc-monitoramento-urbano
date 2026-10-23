# Deploy no Google Cloud Run

[← voltar ao README](../README.md#documentação)

## 21. Deploy no Google Cloud Run

O sistema sobe no Cloud Run como uma imagem só, com a API, o painel e o YOLO. A escolha
tem um motivo: o Cloud Run desliga tudo quando ninguém está usando, então não existe
instância ligada enquanto o link está fechado. É o tipo de custo que um TCC hospedado com
crédito gratuito precisa.

### 21.1 Por que o sistema "só funciona quando alguém entra"

São três coisas que se somam:

| Mecanismo | Efeito |
|---|---|
| `--min-instances 0` | Sem acesso, nenhuma instância fica ligada e não há cobrança. |
| CPU só durante requisições | O Cloud Run congela a CPU do container entre uma requisição e outra. As threads de `live_detection` e `flood_detection` não rodam com o painel fechado, mesmo com `GX_MONITORAMENTO_ATIVO=true`. |
| WebSocket do painel | Enquanto alguém está com o painel aberto, o `/ws` mantém uma requisição aberta. É nesse tempo que a CPU fica disponível e a detecção contínua acontece. |

Ou seja, o próprio acesso de uma pessoa é o que liga o sistema. Fechou o painel, o
monitoramento para, e uns 15 minutos depois a instância é desligada.

O `--max-instances 1` também é de propósito: o banco é um SQLite dentro do container, então
duas instâncias ao mesmo tempo teriam dados diferentes. Ele também serve de limite de
gasto, porque um pico de acessos não multiplica a conta.

### 21.2 O que sobe e o que não sobe

| Vai para a imagem | Fica de fora (`.dockerignore` / `.gcloudignore`) |
|---|---|
| `backend/`, `ml/`, `data_fusion/`, `database/`, `frontend/` compilado | `backend/venv/` (4,8 GB), `ml/datasets/` (5,4 GB), `ml/runs/`, `runs/` |
| `ml/models/gx-veiculos.pt`, `ml/models/yolo11m.pt` (reserva) e `ml/models/gx-incident.pt` | os outros modelos (`-anterior`, `-backup`, `-v4-attempt`, `yolo11n/s`) |
| torch para CPU + ultralytics | `backend/.env`, `*.db`, `backend/app/data/` (evidências locais), testes |

> Cuidado com o `.gcloudignore`. Sem esse arquivo, o `gcloud` usa o `.gitignore` para
> escolher o que enviar, e a imagem pode subir sem os modelos. Nesse caso toda rota de
> detecção responde "modelo indisponível". O `.gcloudignore` deixa essa escolha separada
> do Git.

O `Dockerfile` instala a versão do torch só para CPU
(`--index-url https://download.pytorch.org/whl/cpu`). A versão padrão do PyPI traz uns
2,5 GB de CUDA, que não servem para nada no Cloud Run, já que ele não tem GPU no plano
gratuito.

### 21.3 Passo a passo (primeira vez)

1. Criar a conta e o projeto

   1. Entre em <https://console.cloud.google.com> com uma conta Google.
   2. Aceite a avaliação gratuita: US$ 300 de crédito por 90 dias. Ela pede um cartão (há
      uma cobrança de verificação de uns R$ 1, que é devolvida). No fim do período o
      Google não cobra sozinho: é preciso mudar para conta paga manualmente.
   3. Crie um projeto, por exemplo com o nome `MotSP TCC`, e anote o Project ID gerado
      (algo como `motsp-tcc-473120`). Os comandos usam o ID, e não o nome.

2. Instalar o Google Cloud CLI

   Baixe e instale o [GoogleCloudSDKInstaller.exe](https://dl.google.com/dl/cloudsdk/channels/rapid/GoogleCloudSDKInstaller.exe)
   e depois, num PowerShell novo:

   ```powershell
   gcloud init      # faz login no navegador e seleciona o projeto
   ```

3. Publicar

   ```powershell
   .\deploy.ps1 -ProjectId SEU-PROJECT-ID
   ```

   O script ativa as APIs necessárias (Cloud Run, Cloud Build e Artifact Registry), lê a
   `TOMTOM_API_KEY` do `backend/.env`, manda ela como variável do serviço e inicia o
   build. Na primeira vez o `gcloud` pergunta se pode criar o repositório
   `cloud-run-source-deploy`. Responda `Y`.

   O primeiro build leva uns 10 minutos, quase tudo para instalar o torch. No fim, o
   script mostra o endereço público, no formato
   `https://motsp-XXXXXXXX.southamerica-east1.run.app`. Esse é o link para compartilhar.
   O serviço sobe com `--allow-unauthenticated`, então qualquer pessoa com o endereço
   abre o painel, sem precisar de conta Google.

4. Ligar o monitoramento contínuo (opcional)

   No primeiro deploy as threads de detecção sobem desligadas (o padrão do `config.py`).
   O painel funciona, o testador de imagens funciona e nada gasta CPU sozinho. O script
   só muda isso quando é pedido. Um novo deploy sem a opção mantém o que já está na
   nuvem, porque ele usa `--update-env-vars` (que junta as variáveis) e não
   `--set-env-vars` (que trocaria todas).

   ```powershell
   .\deploy.ps1 -ProjectId SEU-PROJECT-ID -Monitoramento -PularApis          # liga
   .\deploy.ps1 -ProjectId SEU-PROJECT-ID -DesligarMonitoramento -PularApis  # desliga
   ```

   Ou, sem montar a imagem de novo:

   ```powershell
   gcloud run services update motsp --region southamerica-east1 --update-env-vars "GX_MONITORAMENTO_ATIVO=true,GX_TRANSITO_MONITORAR_CATALOGO=true"
   ```

> As aspas são obrigatórias no PowerShell. Sem elas, `a,b` vira uma lista e o gcloud
> recebe um valor só, `"true GX_TRANSITO_MONITORAR_CATALOGO=true"`. O pydantic recusa
> esse valor, o container fecha com erro e o Cloud Run mostra "failed to start and
> listen on the port". A mensagem engana: o problema não é a porta, e o log da revisão
> mostra o `ValidationError` de verdade.

> Em CPU, uma detecção do YOLO com `imgsz=1280` leva alguns segundos, muito mais que na
> GPU. Por isso o deploy usa `GX_LIVE_DETECTION_INTERVAL_SECONDS=60`, em vez do intervalo
> curto usado localmente. Ligar as 20 threads do catálogo (10 de trânsito e 10 de
> alagamento) em 2 vCPU sobrecarrega a instância. Para uma demonstração, é melhor ligar só
> o `GX_TRANSITO_MONITORAR_CATALOGO` ou apontar o `GX_CAMERA_SNAPSHOT_URL` para uma câmera só.

### 21.4 Custo e proteção do crédito

A cota gratuita mensal do Cloud Run é de 180.000 vCPU-segundos, 360.000 GiB-segundos e 2
milhões de requisições. Com a configuração deste deploy (2 vCPU e 4 GiB), isso dá umas 25
horas por mês de painel aberto de graça. Acima disso o custo é de uns US$ 0,30 por hora
de uso, e o crédito de US$ 300 cobre umas 1.000 horas. Com o painel fechado, o único custo
é guardar a imagem no Artifact Registry, que fica em centavos.

Proteções recomendadas:

1. Orçamento com alerta: Console → Faturamento → Orçamentos e alertas → criar um orçamento
   de, por exemplo, US$ 20 com alertas em 50%, 90% e 100%.
2. `--max-instances 1`: o script já aplica, e é o limite real do gasto.
3. Desligar de vez quando a banca acabar:
   ```powershell
   gcloud run services delete motsp --region southamerica-east1
   ```

### 21.5 Limitações conhecidas do ambiente de nuvem

- O primeiro acesso é lento. A imagem tem uns 2 GB (torch e modelos), e o serviço leva de
  30 a 60 segundos para ligar. Antes de apresentar para a banca, abra o link alguns
  minutos antes.
- O banco não fica salvo. O SQLite fica num disco temporário do container: cada vez que o
  serviço liga, ele começa vazio e as tabelas são criadas de novo. Isso combina com a
  janela de 45 minutos dos eventos ([§13](data-fusion.md#13-ciclo-de-vida-de-um-evento)),
  mas nada sobrevive quando o serviço desliga. Para guardar os dados de verdade seria
  preciso usar o Cloud Storage ou o Cloud SQL, e nenhum dos dois é gratuito para sempre.
- A memória é o gargalo, não a CPU. No primeiro deploy com o monitoramento ligado o
  container foi derrubado por falta de memória (`4249 MiB` de `4096`) 19 segundos depois
  de carregar o YOLO. As 10 threads de cada tipo carregavam o modelo ao mesmo tempo, cada
  uma com a sua cópia, e depois rodavam todas juntas. A trava de carregamento e o limite
  de detecções simultâneas (`GX_YOLO_MAX_CONCORRENCIA`, [§5](configuracao.md#modelos-yolo))
  existem por causa disso. Quando o container cai, o SQLite vai junto e o painel volta a
  zero sem aviso.
- As evidências ocupam memória. As imagens com as caixas são gravadas em
  `backend/app/data/evidencias/`, que no Cloud Run fica na memória e conta dentro dos
  4 GiB da instância.

### 21.6 Diferenças de execução entre local e container

No painel não muda nada: nos dois casos o FastAPI serve o `frontend/` em `/` (opção
`GX_SERVE_FRONTEND`, ligada por padrão), o `GET /api/status` responde o status da API e o
`frontend/js/config.js` usa o `window.location.origin` como `API_BASE_URL`. É o mesmo
endereço, então não precisa de CORS. O painel é registrado depois de todas as rotas,
senão ele responderia no lugar de `/eventos`, `/ws` e `/docs`. Com a opção desligada, o
`/` volta a mostrar o status em JSON.

O que muda é só de onde vem a configuração: localmente do `backend/.env`, e no Cloud Run
das variáveis do serviço.

### 21.7 Deploy automático a cada push (Cloud Build)

O `cloudbuild.yaml` da raiz descreve o caminho automático: um gatilho do Cloud Build olha
a branch `main` do GitHub e, a cada push, monta a imagem com o mesmo `Dockerfile`, envia
para o Artifact Registry e publica uma versão nova no Cloud Run. O resultado é o mesmo do
`deploy.ps1`, mas sem depender da máquina local.

| | `deploy.ps1` (manual) | Gatilho do Cloud Build (automático) |
|---|---|---|
| Origem do código | a pasta local, do jeito que está no disco (filtrada pelo `.gcloudignore`) | o repositório do GitHub (só o que está commitado) |
| Modelos do YOLO | copiados do disco | precisam estar no Git. Por isso o `.gitignore` libera só `gx-veiculos.pt`, `yolo11m.pt` e `gx-incident.pt` |
| Variáveis do serviço | atualiza as que o script conhece (`--update-env-vars`) | não mexe em nenhuma: memória, TomTom e monitoramento continuam como estão |
| Quando usar | emergência, ou para testar sem passar pelo GitHub | no dia a dia: `git push` e pronto |

Cada push na `main` é uma publicação real (uns 10 minutos de build, e a cota gratuita do
Cloud Build é de 120 minutos por dia). Trabalho em andamento fica numa branch e só entra
na `main` quando estiver pronto para o link público.

Para ativar (uma vez só), depois de commitar o `cloudbuild.yaml` e os modelos:

1. Console → Cloud Build → Gatilhos → Conectar repositório (isso instala o app do Cloud
   Build no GitHub e autoriza o repositório).
2. Criar gatilho: evento "push para uma branch", branch `^main$`, configuração "arquivo
   de configuração do Cloud Build", local `cloudbuild.yaml`, e a conta de serviço do
   Compute (`<número>-compute@developer.gserviceaccount.com`).
3. Essa conta precisa, além do `cloudbuild.builds.builder` (que o `deploy.ps1` já dá),
   das permissões Cloud Run Admin e Service Account User para publicar. Sem elas o build
   funciona, mas a publicação falha com "permission denied":
   ```powershell
   gcloud projects add-iam-policy-binding SEU-PROJECT-ID --member "serviceAccount:NUMERO-compute@developer.gserviceaccount.com" --role roles/run.admin
   gcloud projects add-iam-policy-binding SEU-PROJECT-ID --member "serviceAccount:NUMERO-compute@developer.gserviceaccount.com" --role roles/iam.serviceAccountUser
   ```

O gatilho também pode ser criado por linha de comando
(`gcloud builds triggers create github ...`), mas a conexão com o GitHub (passo 1) só dá
para fazer pelo console.
