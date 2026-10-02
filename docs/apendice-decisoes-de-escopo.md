# Apêndice A — Decisões de escopo

[← voltar ao README](../README.md#documentação)

## 19. Decisões de escopo (o que foi removido e por quê)

Esta seção existe porque várias ausências no código são **decisões**, não pendências. Se você
for reintroduzir algo daqui, saiba o que derrubou antes.

### Classes de detecção removidas

`buraco`, `lixo`, `incendio`, `construcao_irregular`, `arvore_caida`, `vazamento`.
O grupo focou o escopo do TCC nos dois tipos com detector de verdade rodando contínuo:
**alagamento** e **trânsito**. Os IDs não foram reaproveitados, então nada quebra em pesos
antigos.

### Autenticação (ETAPA 17, 03/09/2026 — migração `003`)

Login, perfis (operador/administrador) e trilha por usuário removidos. A tela de login já
não existia e todo acesso caía num admin implícito — a camada dava aparência de segurança
sem entregar nenhuma. Ver [§18](testes-e-seguranca.md#18-segurança-e-limitações).

### Escrita pelo painel (ETAPA 18 — migração `004`)

Removidas as rotas de escrita de eventos e evidências, o modal "Registrar ocorrência" (já
inalcançável — o botão que o abria não existia mais), os botões de status/resolver, o placar
"OPERADOR URBANO" (dava XP por evento que a câmera criou sozinha) e a coluna
`logs_sistema.ip_origem`, que nunca chegou a ser preenchida.

### Notificações (ETAPA 19 — migração `005`)

Tabela, model, schema, router, aba do detalhe e consumo no painel. **O banco sempre teve zero
notificações**: o único produtor era o formulário manual, removido na etapa anterior. O
painel já caía sempre no caminho alternativo de observações YOLO.

### GeoSampa / Defesa Civil / CET como gatilho em lote

Havia monitoramento reativo de alagamento, acidente de trânsito e queda de árvore a partir de
datasets em lote. Eram **dados oficiais com coordenada real** — e mesmo assim saíram.
O motivo: recarregados semanas a anos depois do ocorrido, cada evento saía carimbado com o
horário em que o sistema notou o registro, não com o horário real do incidente. É o mesmo
problema encontrado depois na câmera CET travada. Ficou definido que **"tempo real" só vale
para detecção via câmera ao vivo**.

O histórico do CGE/GeoSampa voltou depois, mas apenas como camada de referência **estática**
para calibrar a fusão — não como gatilho nem fonte ao vivo, então não fere essa regra.

### Waze for Cities e site do CGE

Nunca chegaram a entrar. O Waze for Cities exige convênio formal da prefeitura com o Google;
o site do CGE não tem API pública, só scraping de HTML frágil. A TomTom entrou no lugar
porque tem cadastro gratuito self-service e responde com dado genuinamente ao vivo.

### Câmera 22 da CET (04/09/2026)

"Paulista - Metrô Consolação", retirada do catálogo por estar permanentemente travada:
`Last-Modified` de ~191 dias atrás. Mantê-la só custava uma thread e um GET por intervalo
para jogar o resultado fora. A câmera 23 fica a ~50 m e cobre o mesmo cruzamento. A checagem
`frame_esta_desatualizado` continua valendo para todas — qualquer outra pode travar igual, e
foi assim que esta foi descoberta.

### Telas sem navegação e rotas de demonstração (02/10/2026)

O painel tinha seis telas (`eventos`, `regioes`, `fontes`, `fusao`, `cv`, `config`), um drawer
de detalhe do evento e os blocos "Alertas" e "Atividade da sessão" que nenhum botão abria —
código funcional, mas invisível para quem usa o sistema. Saíram junto as rotas que só essas
telas usavam (`/deteccao/frame`, `/deteccao/confirmar`, `/ws/cv`) e as de simulação
(`/deteccao/simular`, `/deteccao/video`). Com isso nenhuma rota HTTP cria evento: o único
caminho é a detecção contínua nas câmeras. A busca de eventos e o filtro por severidade
(também escondidos) saíram pelo mesmo motivo.

### Histórico de etapas concluídas

| Etapa | Entrega |
|---|---|
| 0–2 | `.gitignore`, build TS, contratos com `Literal[]` |
| 3–4 | Frontend mobile/ARIA; SSE + reconexão exponencial |
| 5–6 | Prova de conceito YOLO; testes ponta a ponta |
| 7–8 | Documentação e validação |
| 9 | WebSocket com fallback em cascata |
| 10–11 | CSS premium com design tokens; auditoria em 9 resoluções e 4 zooms |
| 12–13 | Operação ao vivo: Leaflet, Open-Meteo, câmera autorizada, YOLO real |
| 14–16 | Verificação integrada local e sincronização de documentação |
| 17 | Remoção da autenticação |
| 18 | Painel somente leitura |
| 19 | Remoção das notificações |
| — | Retreino do modelo de incidentes com negativos; TomTom em três faixas; prior histórico de alagamento; troca do mapa para GeoSampa WMS |
