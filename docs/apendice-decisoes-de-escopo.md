# Apêndice A: Decisões de escopo

[← voltar ao README](../README.md#documentação)

## 19. Decisões de escopo (o que foi removido e por quê)

Esta seção existe porque várias coisas que faltam no código foram decisões, e não
pendências. Antes de trazer algo daqui de volta, vale saber por que saiu.

### Classes de detecção removidas

`buraco`, `lixo`, `incendio`, `construcao_irregular`, `arvore_caida` e `vazamento`. O
grupo focou o TCC nos dois tipos que têm um detector funcionando de forma contínua:
alagamento e trânsito. Os IDs não foram reaproveitados, então modelos antigos continuam
funcionando.

### Autenticação (etapa 17, 03/09/2026, migração `003`)

Foram removidos o login, os perfis (operador e administrador) e o registro por usuário. A
tela de login já não existia e todo acesso caía num administrador padrão, então essa parte
parecia dar segurança sem dar nenhuma. Ver [§18](testes-e-seguranca.md#18-segurança-e-limitações).

### Escrita pelo painel (etapa 18, migração `004`)

Foram removidas as rotas de escrita de eventos e evidências, a janela "Registrar
ocorrência" (que já não abria, porque o botão dela tinha sumido), os botões de status e de
resolver, o placar "OPERADOR URBANO" (que dava pontos por eventos que a câmera criou
sozinha) e a coluna `logs_sistema.ip_origem`, que nunca foi preenchida.

### Notificações (etapa 19, migração `005`)

Saíram a tabela, o model, o schema, a rota, a aba no detalhe do evento e o uso no painel.
O banco nunca teve nenhuma notificação: o único jeito de criar uma era o formulário
manual, removido na etapa anterior.

### GeoSampa / Defesa Civil / CET como gatilho em lote

O sistema já teve um monitoramento de alagamento, acidente de trânsito e queda de árvore
a partir de datasets publicados em lote. Eram dados oficiais e com coordenadas reais, e
mesmo assim saíram. O motivo é que eles eram publicados semanas ou anos depois do
ocorrido, então cada evento saía com o horário em que o sistema viu o registro, e não com
o horário real. É o mesmo problema que apareceu depois com a câmera da CET travada. Ficou
definido que tempo real só vale para a detecção pelas câmeras ao vivo.

O histórico do CGE e do GeoSampa voltou depois, mas só como um dado fixo para ajustar o
Data Fusion. Ele não cria eventos nem conta como fonte ao vivo, então não quebra essa
regra.

### Waze for Cities e site do CGE

Nunca chegaram a entrar. O Waze for Cities exige um convênio da prefeitura com o Google, e
o site do CGE não tem API pública, só daria para ler o HTML da página, o que quebra fácil.
A TomTom entrou no lugar porque o cadastro é grátis e feito pela própria pessoa, e ela
responde com dados ao vivo.

### Câmera 22 da CET (04/09/2026)

A "Paulista - Metrô Consolação" saiu do catálogo por estar sempre travada, com
`Last-Modified` de uns 191 dias atrás. Mantê-la só gastava uma thread e um download a cada
intervalo para jogar o resultado fora. A câmera 23 fica a uns 50 m e cobre o mesmo
cruzamento. A checagem `frame_esta_desatualizado` continua valendo para todas, porque
qualquer outra pode travar do mesmo jeito, e foi assim que esta foi descoberta.

### Telas sem navegação e rotas de demonstração (02/10/2026)

O painel tinha seis telas (`eventos`, `regioes`, `fontes`, `fusao`, `cv` e `config`), uma
gaveta de detalhe do evento e os blocos "Alertas" e "Atividade da sessão" que nenhum botão
abria. O código funcionava, mas ninguém conseguia chegar até ele. Junto saíram as rotas que
só essas telas usavam (`/deteccao/frame`, `/deteccao/confirmar` e `/ws/cv`) e as de
simulação (`/deteccao/simular` e `/deteccao/video`). Com isso nenhuma rota HTTP cria
evento, e o único caminho é a detecção nas câmeras. A busca de eventos e o filtro por
severidade, que também estavam escondidos, saíram pelo mesmo motivo.

### Histórico de etapas concluídas

| Etapa | Entrega |
|---|---|
| 0 a 2 | `.gitignore`, build do TypeScript, validação com `Literal[]` |
| 3 e 4 | Frontend para celular e acessibilidade; SSE com reconexão |
| 5 e 6 | Prova de conceito do YOLO; testes de ponta a ponta |
| 7 e 8 | Documentação e validação |
| 9 | WebSocket com troca automática de canal |
| 10 e 11 | CSS com design tokens; revisão em 9 resoluções e 4 níveis de zoom |
| 12 e 13 | Operação ao vivo: Leaflet, Open-Meteo, câmera autorizada e YOLO real |
| 14 a 16 | Verificação integrada local e atualização da documentação |
| 17 | Remoção da autenticação |
| 18 | Painel somente leitura |
| 19 | Remoção das notificações |
| depois | Novo treino do modelo de alagamento com imagens negativas; TomTom em três faixas; histórico de alagamento das vias; troca do mapa para o GeoSampa WMS |
