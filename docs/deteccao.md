# Detecção: YOLO, trânsito, alagamento e fontes externas

[← voltar ao README](../README.md#documentação)

## 9. Visão computacional (YOLO)

### Dois modelos, carregados separadamente

`ml/detector.py` mantém **dois** modelos Ultralytics independentes, ambos carregados sob
demanda (a API sobe normalmente em máquina sem GPU e sem pesos):

| Modelo | Variável | Uso | Confiança |
|---|---|---|---|
| Objetos (COCO) | `GX_YOLO_MODEL` → `yolo11m.pt` | Contagem de veículos para trânsito, upload de imagem | `YOLO_THRESHOLD` = 0,45 |
| Incidentes (próprio) | `GX_YOLO_INCIDENT_MODEL` → `gx-incident.pt` | Classe única `alagamento` | `GX_YOLO_INCIDENT_CONF` = 0,6 |

Manter os dois separados é deliberado: substituir o peso global por um treinado em
alagamento faria a contagem de veículos parar de funcionar.

### Classes urbanas (`CLASSES_URBANAS`)

| ID | Nome | Severidade | Tipo |
|---|---|---|---|
| 1 | `alagamento` | critica | alagamento |
| 2 | `transito` | media | transito |
| 8 | `veiculo` | baixa | **observacao_visual** |
| 9 | `motocicleta` | baixa | observacao_visual |
| 10 | `onibus` | baixa | observacao_visual |
| 11 | `caminhao` | baixa | observacao_visual |

Os IDs 0, 3, 4, 5, 6 e 7 pertenciam a `buraco`, `lixo`, `incendio`, `construcao_irregular`,
`arvore_caida` e `vazamento` — removidos do escopo e **não reaproveitados**.

**`observacao_visual` é uma categoria de honestidade.** O peso COCO reconhece que existe um
carro no quadro; isso não é um congestionamento. Veículo isolado nunca vira evento: só o
pipeline de contagem (§10) transforma N veículos juntos em um evento `transito`.

O mapeamento COCO→urbano é `car→veiculo`, `motorcycle→motocicleta`, `bus→onibus`,
`truck→caminhao` (fixo em `ml/detector.py`). Classes
sem destino válido são **descartadas** — é assim que um peso antigo treinado também com
`arvore_caida` continua funcionando sem gerar eventos dessa classe.

### Evidência auditável

Quando um evento é criado (`detection_events.registrar_deteccao`), o sistema grava:

- `{uuid}-original.jpg` — o frame exatamente como veio
- `{uuid}-yolo.jpg` — cópia com as caixas desenhadas (`evidence_annotation.py`)
- `sha256_original` nos metadados da evidência
- `classe_modelo` (o nome bruto do modelo, ex.: `car`) ao lado da classe urbana normalizada

Se a anotação visual falhar, o original continua sendo a evidência — a inferência já
aconteceu e o registro não se perde.

### A armadilha do frame travado

A CET-SP não expõe RTSP: cada câmera é um JPEG estático num endpoint por ID
(`https://cameras.cetsp.com.br/Cams/{id}/1.jpg`), atualizado pelo servidor deles. Em
26/08/2026 descobriu-se que a câmera 22 ("Paulista - Metrô Consolação") havia travado:
respondia **200 OK com bytes válidos**, mas sempre o mesmo JPEG de meses atrás. Sem
verificação, isso produz um evento "detectado agora" com uma foto de outra época — o oposto
de tempo real.

Por isso **toda** detecção contínua passa por `cet_camera_catalog.frame_esta_desatualizado`,
que lê o cabeçalho HTTP `Last-Modified` e descarta o frame se ele for mais velho que
`GX_CAMERA_FRESCOR_MAXIMO_SEGUNDOS` (300 s). Câmeras que não enviam `Last-Modified` são
tratadas como frescas — não dá para provar o contrário. A câmera 22 acabou removida do
catálogo em 04/09/2026 (a 23 fica a ~50 m e cobre o mesmo cruzamento), mas a checagem
continua valendo para todas: qualquer outra pode travar do mesmo jeito.

---

## 10. Detecção contínua de trânsito

`backend/app/services/live_detection.py` — uma thread por câmera, cada uma com cooldown
independente (uma avenida congestionada não pode silenciar o alerta de outra).

### O loop

1. `GET` no snapshot a cada `GX_LIVE_DETECTION_INTERVAL_SECONDS` (5 s)
2. Descarta se o `Last-Modified` estiver velho
3. Descarta se o SHA-256 for igual ao do frame anterior (nada mudou)
4. Roda o modelo de objetos e conta detecções em `{veiculo, motocicleta, onibus, caminhao}`
5. Aplica o gatilho de três faixas
6. Se criar: reduz as N detecções a **uma** detecção sintética de `transito`

### Por que contagem sozinha não basta

O YOLO/COCO não tem classe "trânsito" — só objetos. Contar veículos no quadro é a
aproximação disponível, e ela erra para os dois lados:

- **Superconta:** o enquadramento pega os dois sentidos da via + a fila da transversal. Uma
  avenida larga fluindo normalmente passa de 12 veículos à toa.
- **Subconta:** o JPEG noturno da câmera pública derruba o score do YOLO. Uma via
  comprovadamente parada às 19h fica em 4–7 veículos detectados.

### O gatilho de três faixas (`_avaliar_gatilho_transito`)

| Contagem no frame | Quem decide | Resultado |
|---|---|---|
| `≥ 16` (`_CONFIRMADO`) | Ninguém — a contagem basta | **Cria.** Frame muito cheio é sinal forte por si só. |
| `12..16` | TomTom pode **vetar** | Cria, exceto se a TomTom medir o trecho a ≥ ~70% da velocidade livre (índice < 3,0). Sem `TOMTOM_API_KEY`, volta a decidir só por contagem. |
| `4..12` (`_CORROBORADO`..`_MIN`) | TomTom **cria** | A contagem é baixa demais para se sustentar; só vira evento se a TomTom corroborar lentidão. Sem chave, esta faixa não gera nada. |
| `< 4` | — | Descartado sem consultar a TomTom. Abaixo disso não há aglomeração visível que sustente a evidência anexada ao evento, por mais lento que o trecho esteja. |

Atalho adicional: `roadClosure=true` da TomTom cria o evento independentemente da contagem.

> **O caso que motivou a faixa baixa (04/09/2026, rush das 19h):** a via estava a 9 km/h num
> trecho de 20 km/h livres, a TomTom sabia disso, e o portão de contagem barrava o frame
> *antes* de perguntar a ela. A fonte que sabia da lentidão nunca era ouvida. Hoje o portão
> inicial é o **piso** (4), não o mínimo (12).

### Confiança da detecção sintética

A confiança do evento de trânsito é a média das **`GX_TRANSITO_MIN_VEICULOS` maiores**
confianças, não de todas: veículos ao fundo aparecem pequenos e com score naturalmente
baixo, e a média de todos derrubava a dimensão de IA da fusão mesmo com congestionamento
óbvio no primeiro plano. O que importa é "há N veículos bem detectados juntos", não a
qualidade média de cada lata distante. A bbox do evento é a união das bboxes dos veículos.

### Deduplicação em duas camadas

- **Em memória:** cooldown por thread (30 min após criar, 10 min após veto). Perde-se a cada
  restart do servidor.
- **No banco:** `refrescar_evento_no_ponto` procura um evento vivo do mesmo tipo no mesmo
  ponto (tolerância 1e-4°) dentro da janela. Se achar, só renova o `detectado_em` e publica
  `evento_atualizado`, em vez de empilhar outro evento — e nem gasta chamada da TomTom.

### Dados contextuais gravados

| Chave | Origem |
|---|---|
| `indice_congestionamento` | `min(10, n_veiculos / 2)` — índice derivado da contagem |
| `indice_congestionamento_tomtom` | `10 × (1 − velocidade_atual / velocidade_livre)` |

Quando ambos existem, o Data Fusion usa a **média** — duas fontes concordando valem mais
que uma.

---

## 11. Detecção contínua de alagamento

`backend/app/services/flood_detection.py` — mesmo padrão do trânsito (thread por câmera,
mesmo catálogo, mesma checagem de frescor), mas rodando o modelo dedicado de incidentes
direto no snapshot.

Sem `GX_YOLO_INCIDENT_MODEL` configurado, o loop sobe mas cada frame é descartado
silenciosamente — mesmo comportamento defensivo do resto do sistema quando falta peso
treinado.

Detectado um `alagamento`, o serviço busca três insumos e grava todos como
`dados_contextuais` de categoria `contexto`:

| Insumo | Chave | Natureza |
|---|---|---|
| Chuva no ponto exato (Open-Meteo) | `precipitacao_mm_h` | Sensor bruto, **ao vivo** |
| Aviso ativo do INMET para São Paulo | `alerta_inmet_severidade` | Julgamento institucional, **ao vivo**. Só gravado se o texto de "riscos" mencionar alagamento/inundação/enchente. |
| Histórico de alagamento da via | `historico_alagamento_indice` | Prior espacial **estático**, lookup local sem rede. Gravado **sempre**, inclusive `0.0`. |

Gravar o histórico mesmo quando é zero é o que permite ao Data Fusion distinguir
"via sem histórico" (sinal negativo real) de "sem informação" (chave ausente).

Uma nota de escopo importante: o alagamento **não** tem um equivalente ao veto da TomTom.
As fontes climáticas entram depois da criação do evento, calibrando a confiabilidade — e é
a confiabilidade que decide se ele aparece como `ativo` ou fica `em_analise`.

---

## 14. Fontes de dados externas

| Fonte | Uso | Autenticação | Natureza |
|---|---|---|---|
| **Câmeras CET-SP** | Snapshot JPEG por ID (`cameras.cetsp.com.br/Cams/{id}/1.jpg`) | nenhuma | Ao vivo (com ressalva do `Last-Modified`) |
| **TomTom Traffic API** | Velocidade atual × livre do trecho (Flow Segment Data) | `TOMTOM_API_KEY` (cadastro gratuito self-service em developer.tomtom.com) | Ao vivo |
| **Open-Meteo** | Chuva, temperatura, vento no ponto exato | nenhuma | Ao vivo |
| **Open-Meteo Air Quality** | AQI, PM2.5, PM10 (exibição no painel) | nenhuma | Ao vivo |
| **INMET** | Avisos meteorológicos ativos (`apiprevmet3.inmet.gov.br/avisos/ativos`) | nenhuma | Ao vivo |
| **CGE-SP + GeoSampa** | Histórico de alagamento por via | — (arquivo versionado) | **Estático** |
| **GeoSampa WMS** | Camada base do mapa (`MapaBase_Politico`) | nenhuma | Cartografia |

### O catálogo de câmeras

`cet_camera_catalog.py` — as 10 câmeras vieram do HTML público de
`cameras.cetsp.com.br/View/Cam.aspx` (as "favoritas" que o próprio site expõe; não existe API
de listagem). É um subconjunto pequeno da rede real da CET.

| ID | Nome | Lat | Lon |
|---|---|---|---|
| 225 | Ascendino Reis - R Pedro de Toledo | -23,5975 | -46,6508 |
| 184 | Brasil - Av Brig Luis Antônio | -23,5608 | -46,6437 |
| 195 | Brasil - Av Henrique Schaumann | -23,5643 | -46,6780 |
| 210 | Brig Luis Antônio - Al Santos | -23,5659 | -46,6532 |
| 220 | Cidade Jardim - Av Nove de Julho | -23,5867 | -46,6900 |
| 180 | Consolação - R Caio Prado | -23,5492 | -46,6485 |
| 222 | Hélio Pellegrino - R Diogo Jácome | -23,5983 | -46,6684 |
| 224 | Ibirapuera - R Ipê | -23,5877 | -46,6585 |
| 200 | Iguatemi - Av Brig Faria Lima | -23,5772 | -46,6880 |
| 23 | Paulista - Av Brigadeiro Luiz Antônio | -23,5576 | -46,6606 |

As coordenadas foram geocodificadas a partir do nome do cruzamento (Nominatim/OSM) — são
aproximações de rua/quarteirão, não a posição exata do poste. Suficiente para "câmera mais
próxima dentro de X km", não para navegação de precisão.

### Detalhes do INMET

A API cobre o Brasil inteiro. O serviço filtra por código IBGE do município
(`3550308` = São Paulo capital, campo `geocodes`, string separada por vírgula) e escolhe o
aviso ativo **mais severo**. A escala de cor oficial vira índice 0–10 (mesma escala do
índice de congestionamento), porque o JSON não traz um ordinal limpo:

| Rótulo INMET | Cor | Índice |
|---|---|---|
| grande perigo | vermelho | 9,5 |
| perigo | laranja | 7,0 |
| perigo potencial | amarelo | 4,0 |
| (desconhecido) | — | 2,0 |

O aviso só é gravado como contexto se o texto livre de "riscos" mencionar
*alagamento*, *inunda…* ou *enchente*.
