# Detecção: YOLO, trânsito, alagamento e fontes externas

[← voltar ao README](../README.md#documentação)

## 9. Visão computacional (YOLO)

### Dois modelos, carregados separadamente

O `ml/detector.py` usa dois modelos do Ultralytics, cada um carregado só quando é usado
pela primeira vez. Assim a API sobe normalmente numa máquina sem GPU e sem os modelos.

| Modelo | Variável | Uso | Confiança |
|---|---|---|---|
| Veículos (YOLO ajustado nas câmeras CET) | `GX_YOLO_MODEL` → `gx-veiculos.pt` | Contagem de veículos para trânsito | `YOLO_THRESHOLD` = 0,45 |
| Incidentes (próprio) | `GX_YOLO_INCIDENT_MODEL` → `gx-incident.pt` | Classe única `alagamento` | `GX_YOLO_INCIDENT_CONF` = 0,6 |

Os dois ficam separados de propósito: se o modelo de veículos fosse trocado por um
treinado em alagamento, a contagem de veículos pararia de funcionar.

### O modelo de veículos ajustado às câmeras CET

O `yolo11m` foi treinado com fotos comuns, e as câmeras da CET mandam imagens de 480x270,
comprimidas, com carros pequenos ao fundo e muitas cenas noturnas. O
`ml/train_vehicle_model.py` ajusta o modelo a essas imagens sem ninguém marcar carro à
mão: um modelo maior e lento demais para o tempo real (`yolo11x` com TTA) marca as imagens
salvas como evidência, e o `yolo11m` aprende com essas marcações. As 80 classes do YOLO
continuam as mesmas, então o mapeamento de classes do detector não muda.

Resultado em 79 imagens de teste separadas antes do treino (de 397 imagens diferentes),
com a confiança mínima do sistema (0,45) e sem TTA:

| | `yolo11m.pt` (antes) | `gx-veiculos.pt` (agora) |
|---|---|---|
| Acerto em relação ao modelo maior (mAP50, veículos) | 0,78 | 0,85 |
| Precisão | 0,81 | 0,88 |
| Confiança média (12 melhores veículos da imagem) | 0,71 | 0,87 |
| Veículos por imagem (o modelo maior marca 12,5) | 10,1 | 11,6 |

A arquitetura e a velocidade são as mesmas. Para voltar ao modelo anterior basta usar
`GX_YOLO_MODEL=ml/models/yolo11m.pt` (no Cloud Run, como variável do serviço, sem precisar
de um novo build). O modelo original continua no repositório para isso.

### Classes urbanas (`CLASSES_URBANAS`)

| ID | Nome | Severidade | Tipo |
|---|---|---|---|
| 1 | `alagamento` | critica | alagamento |
| 2 | `transito` | media | transito |
| 8 | `veiculo` | baixa | observacao_visual |
| 9 | `motocicleta` | baixa | observacao_visual |
| 10 | `onibus` | baixa | observacao_visual |
| 11 | `caminhao` | baixa | observacao_visual |

Os IDs 0, 3, 4, 5, 6 e 7 eram de `buraco`, `lixo`, `incendio`, `construcao_irregular`,
`arvore_caida` e `vazamento`. Essas classes saíram do escopo e os IDs não foram
reaproveitados.

O tipo `observacao_visual` existe porque ver um carro na imagem não quer dizer que há
congestionamento. Um veículo sozinho nunca vira evento: só a contagem (§10) transforma
vários veículos juntos num evento de `transito`.

O mapeamento das classes do YOLO para as do sistema é `car→veiculo`,
`motorcycle→motocicleta`, `bus→onibus` e `truck→caminhao` (fixo em `ml/detector.py`).
Classes sem correspondência são descartadas. Por isso um modelo antigo, treinado também
com `arvore_caida`, continua funcionando sem gerar eventos dessa classe.

### Evidência auditável

Quando um evento é criado (`detection_events.registrar_deteccao`), o sistema grava:

- `{uuid}-original.jpg`: a imagem exatamente como veio
- `{uuid}-yolo.jpg`: uma cópia com as caixas desenhadas (`evidence_annotation.py`)
- `sha256_original` nos dados da evidência
- `classe_modelo` (o nome da classe no modelo, ex.: `car`) ao lado da classe do sistema

Se der erro ao desenhar as caixas, a imagem original continua valendo como evidência e o
registro não se perde.

### A armadilha do frame travado

A CET-SP não oferece RTSP. Cada câmera é uma imagem JPEG num endereço com o ID dela
(`https://cameras.cetsp.com.br/Cams/{id}/1.jpg`), atualizada pelo servidor da CET. Em
26/08/2026 percebemos que a câmera 22 ("Paulista - Metrô Consolação") tinha travado: ela
respondia normalmente, com uma imagem válida, mas era sempre a mesma foto de meses atrás.
Sem uma verificação, isso gera um evento "detectado agora" com uma foto antiga, o
contrário de tempo real.

Por isso toda detecção contínua passa por `cet_camera_catalog.frame_esta_desatualizado`,
que lê o cabeçalho HTTP `Last-Modified` e descarta a imagem se ela for mais velha que
`GX_CAMERA_FRESCOR_MAXIMO_SEGUNDOS` (300 s). Câmeras que não mandam `Last-Modified` são
tratadas como atuais, porque não dá para provar o contrário. A câmera 22 foi tirada do
catálogo em 04/09/2026 (a 23 fica a uns 50 m e cobre o mesmo cruzamento), mas a checagem
continua valendo para todas, já que qualquer outra pode travar do mesmo jeito.

---

## 10. Ciclo de monitoramento e detecção de trânsito

### O ciclo

O `backend/app/services/ciclo_monitoramento.py` tem dois ritmos:

| Passada | Quando | Quais câmeras |
|---|---|---|
| Completa | Uma vez, quando o sistema liga | Todas |
| Ciclo geral | A cada `GX_CICLO_MINUTOS` (10 min), contados a partir do fim da passada completa | Só as que têm evento no mapa |
| Sem evento | A cada `GX_CICLO_SEM_EVENTO_SEGUNDOS` (60 s), contados a partir do fim da verificação anterior | Só as que não têm evento no mapa |

Um evento criado pela verificação de 60 s entra no próximo horário do ciclo geral, que é
igual para todos os eventos. Quando um evento é apagado, a câmera volta para a verificação
de 60 s. O ritmo é separado por tipo de evento: numa câmera com evento de trânsito e sem
evento de alagamento, o trânsito vai para o ciclo geral e o alagamento continua na
verificação de 60 s. Por enquanto só o trânsito é monitorado
(`GX_ALAGAMENTO_MONITORAR_CATALOGO=false`).

Em cada passada, para cada câmera olhada:

1. Baixa a imagem
2. Descarta se o `Last-Modified` estiver velho (câmera travada)
3. Descarta se o SHA-256 for igual ao da última imagem dela (câmera parada)
4. Roda as regras de trânsito (`live_detection.analisar_frame`) e, se ligado, as de
   alagamento (`flood_detection.analisar_frame`)
5. Para cada tipo, compara o resultado com o evento que já existe no ponto da câmera

| O ciclo viu o evento? | Já existe evento no ponto? | O que acontece |
|---|---|---|
| Sim | Não | Cria o evento. A fusão decide se ele entra `em_analise` ou `ativo`. |
| Sim | Sim | Atualiza o mesmo evento: foto nova, dados de contexto novos, fusão recalculada e `detectado_em` renovado. Um evento `em_analise` pode virar `ativo` e um `ativo` pode voltar para `em_analise`. |
| Não | Sim | Conta um ciclo sem confirmação. No 2º ciclo seguido (`GX_CICLOS_SEM_CONFIRMACAO_PARA_REMOVER`) o evento é apagado. |
| Imagem descartada nos passos 2 ou 3 | Sim | Nada muda. Sem imagem nova não dá para saber se o evento continua. |
| Modelo indisponível ou erro | Sim | Nada muda, pelo mesmo motivo. |

Como o evento é atualizado no lugar, o mapa nunca mostra dois eventos do mesmo tipo na
mesma câmera, e o número do evento não muda entre os ciclos. Trânsito e alagamento são
eventos separados: um não impede o outro na mesma câmera.

Não existe prazo de validade: um evento só sai do mapa quando a câmera passa 2 ciclos
seguidos sem confirmar. Se a câmera parar de mandar imagem, o evento fica no mapa até ela
voltar.

Ao terminar, cada passada junta eventos repetidos que tenham sobrado e grava um resumo em
`logs_sistema` (módulo `ciclo_monitoramento`). A verificação de 60 s só grava quando cria
um evento ou tem falha, para não encher a tabela. O resumo da última passada de cada ritmo
aparece em `GET /monitoramento/status`. Só roda uma passada por vez.

O relógio fica dentro do próprio sistema, numa thread. Na nuvem a CPU só existe enquanto
alguém está com o painel aberto, então o monitoramento anda só nesse tempo. Ver
[deploy.md](deploy.md).

A verificação de 60 s pode consultar a TomTom toda vez que vê de 4 a 15 veículos numa
câmera sem evento. Para não gastar a cota gratuita diária, cada leitura boa da TomTom é
reaproveitada no mesmo ponto por `GX_TOMTOM_CACHE_SEGUNDOS` (300 s). O ciclo geral, de
10 min, sempre pega uma leitura nova.

### O que a regra de trânsito faz com a imagem

1. Roda o modelo de veículos e conta as detecções de `{veiculo, motocicleta, onibus, caminhao}`
2. Aplica o gatilho de três faixas
3. Se for evento, junta as detecções numa única detecção de `transito`

### Por que contagem sozinha não basta

O YOLO não tem a classe "trânsito", só objetos. Contar os veículos da imagem é a
aproximação possível, e ela erra para os dois lados:

- Conta demais: a câmera pega os dois sentidos da via e a fila da rua que cruza. Uma
  avenida larga com o trânsito normal passa de 12 veículos com facilidade.
- Conta de menos: à noite a imagem fica escura e o YOLO perde carros. Uma via parada às
  19h chega a mostrar só 4 a 7 veículos detectados.

### O gatilho de três faixas (`_avaliar_gatilho_transito`)

| Contagem na imagem | Quem decide | Resultado |
|---|---|---|
| `≥ 16` (`_CONFIRMADO`) | Só a contagem | Cria. Imagem muito cheia já é um sinal forte. |
| `12..16` | A TomTom pode recusar | Cria, a não ser que a TomTom meça o trecho a 70% ou mais da velocidade normal (índice abaixo de 3,0). Sem `TOMTOM_API_KEY`, decide só pela contagem. |
| `4..12` (`_CORROBORADO`..`_MIN`) | A TomTom cria | A contagem é baixa demais sozinha. Só vira evento se a TomTom confirmar a lentidão. Sem a chave, esta faixa não gera nada. |
| `< 4` | Ninguém | Descartado sem consultar a TomTom. Com tão poucos veículos a imagem não mostra o congestionamento, mesmo que o trecho esteja lento. |

Além disso, se a TomTom informar a via como fechada (`roadClosure=true`), o evento é
criado independente da contagem.

> O caso que motivou a faixa baixa (04/09/2026, horário de pico das 19h): a via estava a
> 9 km/h num trecho de 20 km/h normais e a TomTom sabia disso, mas a contagem barrava a
> imagem antes de consultar a TomTom. Hoje o primeiro corte é o piso (4), e não o mínimo (12).

### Confiança da detecção sintética

A confiança do evento de trânsito é a média das `GX_TRANSITO_MIN_VEICULOS` maiores
confianças, e não de todas. Os veículos ao fundo aparecem pequenos e com nota baixa, e a
média de todos derrubava a nota da IA mesmo com o congestionamento claro na frente da
câmera. O que importa é haver vários veículos bem detectados juntos. A caixa do evento é
a união das caixas dos veículos.

### Sem eventos repetidos

`buscar_evento_no_ponto` procura o evento aberto do mesmo tipo no ponto da câmera
(tolerância de 1e-4°). Se ele existe, o ciclo atualiza esse evento em vez de criar outro
(`atualizar_evento`) e publica `evento_atualizado`. A confirmação passa pelo mesmo gatilho
da criação (contagem e TomTom), então uma via movimentada mas fluindo não mantém o evento
vivo. Por garantia, `colapsar_eventos_duplicados` ainda roda no fim de cada ciclo e deixa
só o evento mais recente de cada tipo em cada ponto.

### Dados contextuais gravados

| Chave | Origem |
|---|---|
| `indice_congestionamento` | `min(10, n_veiculos / 2)`, índice calculado pela contagem |
| `indice_congestionamento_tomtom` | `10 × (1 − velocidade_atual / velocidade_livre)` |

Quando os dois existem, a nota do contexto usa a média dos dois índices. O peso do
contexto continua fixo em 43%.

---

## 11. Detecção contínua de alagamento

O `backend/app/services/flood_detection.py` roda no mesmo ciclo do trânsito, com a mesma
imagem e as mesmas regras de criar, atualizar e apagar, mas usa o modelo de alagamento.

Sem `GX_YOLO_INCIDENT_MODEL` configurado, a análise de alagamento falha em todas as
câmeras e o ciclo registra a falha sem mexer nos eventos que já existem.

Quando um `alagamento` é detectado, o serviço busca três dados e grava todos em
`dados_contextuais` com a categoria `contexto`:

| Dado | Chave | Tipo |
|---|---|---|
| Chuva no ponto exato (Open-Meteo) | `precipitacao_mm_h` | Medição ao vivo |
| Aviso ativo do INMET para São Paulo | `alerta_inmet_severidade` | Aviso oficial ao vivo. Só é gravado se o texto de "riscos" falar em alagamento, inundação ou enchente. |
| Histórico de alagamento da via | `historico_alagamento_indice` | Dado fixo, consultado num arquivo local. É gravado sempre, inclusive quando é `0.0`. |

Gravar o histórico mesmo quando ele é zero permite ao Data Fusion separar uma "via sem
histórico" (que é um sinal negativo) de "sem informação" (quando a chave não existe).

Uma diferença importante: o alagamento não tem nada parecido com a recusa da TomTom. Os
dados de clima não decidem se o evento existe. Eles ajustam a confiabilidade, e é ela que
decide se o evento aparece como `ativo` ou fica `em_analise`. Como os dados são buscados
de novo a cada ciclo, um alagamento que começou `em_analise` vira `ativo` quando a chuva
ou o aviso do INMET aparecem.

---

## 14. Fontes de dados externas

| Fonte | Uso | Autenticação | Tipo |
|---|---|---|---|
| Câmeras CET-SP | Imagem JPEG por ID (`cameras.cetsp.com.br/Cams/{id}/1.jpg`) | nenhuma | Ao vivo (com a checagem do `Last-Modified`) |
| TomTom Traffic API | Velocidade atual e velocidade normal do trecho (Flow Segment Data) | `TOMTOM_API_KEY` (cadastro grátis em developer.tomtom.com) | Ao vivo |
| Open-Meteo | Chuva, temperatura e vento no ponto exato | nenhuma | Ao vivo |
| Open-Meteo Air Quality | AQI, PM2.5 e PM10 (mostrados no painel) | nenhuma | Ao vivo |
| INMET | Avisos meteorológicos ativos (`apiprevmet3.inmet.gov.br/avisos/ativos`) | nenhuma | Ao vivo |
| CGE-SP + GeoSampa | Histórico de alagamento por via | arquivo no repositório | Fixo |
| GeoSampa WMS | Mapa de fundo (`MapaBase_Politico`) | nenhuma | Cartografia |

### O catálogo de câmeras

As 10 câmeras do `cet_camera_catalog.py` foram tiradas da página pública
`cameras.cetsp.com.br/View/Cam.aspx` (as "favoritas" que o próprio site mostra, já que não
existe uma API com a lista). É uma parte pequena da rede de câmeras da CET.

| ID | Nome | Lat | Lon |
|---|---|---|---|
| 225 | Ascendino Reis - R Pedro de Toledo | -23,5975 | -46,6508 |
| 184 | Brasil - Av Brig Luis Antônio | -23,5608 | -46,6437 |
| 220 | Cidade Jardim - Av Nove de Julho | -23,5867 | -46,6900 |
| 180 | Consolação - R Caio Prado | -23,5492 | -46,6485 |
| 222 | Hélio Pellegrino - R Diogo Jácome | -23,5983 | -46,6684 |
| 224 | Ibirapuera - R Ipê | -23,5877 | -46,6585 |
| 200 | Iguatemi - Av Brig Faria Lima | -23,5772 | -46,6880 |
| 31 | Juscelino Kubitschek - Av Brig. Faria Lima | -23,5905 | -46,6814 |
| 23 | Paulista - Av Brigadeiro Luiz Antônio | -23,5576 | -46,6606 |
| 15 | Paulista - Metrô Paulista | -23,5556 | -46,6628 |

Em 18/11/2026 a CET trocou duas câmeras do site: saíram a 195 (Brasil - Av Henrique
Schaumann) e a 210 (Brig Luis Antônio - Al Santos), que estavam travadas desde outubro, e
entraram a 31 e a 15. O site marca a 180 e a 15 como inativas. Elas continuam no catálogo,
mas a foto antiga é descartada pela checagem de frescor (`Last-Modified` com mais de 300 s).

As coordenadas foram calculadas a partir do nome do cruzamento (Nominatim/OpenStreetMap).
São aproximadas, no nível da rua ou do quarteirão, e não a posição exata do poste. Isso
basta para achar a "câmera mais próxima", mas não serve para navegação precisa.

### Detalhes do INMET

A API cobre o Brasil todo. O serviço filtra pelo código IBGE do município (`3550308` para
São Paulo capital, no campo `geocodes`, que é um texto separado por vírgulas) e escolhe o
aviso ativo mais grave. Como o JSON só traz o nível em texto, cada nível vira um índice de
0 a 10, a mesma escala do congestionamento:

| Nível INMET | Cor | Índice |
|---|---|---|
| grande perigo | vermelho | 9,5 |
| perigo | laranja | 7,0 |
| perigo potencial | amarelo | 4,0 |
| (desconhecido) | sem cor | 2,0 |

O aviso só é gravado como contexto se o texto de "riscos" falar em alagamento, inundação
ou enchente.
