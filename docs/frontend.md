# Frontend

[← voltar ao README](../README.md#documentação)

## 15. Frontend

O painel é escrito em TypeScript e compilado pelo `tsc` (`strict: true`, `noEmitOnError`)
para ES2020, sem bundler e sem framework. A pasta `dist/` vai para o Git.

### Mapa

Usa o Leaflet 1.9.4 (pelo unpkg, com SRI) com a camada WMS do GeoSampa
(`MapaBase_Politico`, crédito da PMSP), com zoom de 10 a 19. Se o Leaflet não carregar, o
painel mostra a tela de "Mapa indisponível" e todo o resto continua funcionando.

Os marcadores têm a cor do status (verde para ativo, amarelo para em análise), se agrupam
conforme o zoom, e o evento selecionado continua selecionado entre as atualizações.

### Views

| View | O que mostra |
|---|---|
| `dashboard` (Início) | Totais por status, o evento selecionado com o anel de confiança, a explicação de como a nota foi calculada e, no celular em pé, a evidência visual |
| `yolo-teste` | Testa uma imagem nos dois modelos ao mesmo tempo |

A barra de ícones (`rail`) leva a essas duas telas. O painel direito mostra a evidência
visual (a imagem com as caixas do YOLO) do evento selecionado, com opção de ampliar.

### Testador de YOLO

Envia a mesma imagem para `/deteccao/incidente` e `/deteccao/imagem` ao mesmo tempo e
mostra um resultado fácil de ler:

- alagamento detectado → `danger`
- veículos ≥ `min_veiculos_transito` (lido de `/deteccao/status`) → `warn`
- nada relevante → `ok`

Ele desenha as caixas sobre a imagem e lista cada detecção dizendo de qual modelo ela veio.

### Filtros e KPIs

O filtro de status (Todos, Ativos ou Em análise) sempre começa em Todos. O navegador pode
lembrar a escolha anterior do `<select>`, então o código volta para o padrão ao abrir. No
celular o mesmo filtro aparece como botões no painel lateral, sempre iguais ao `<select>`.

### Busca por rua

A caixa no canto do mapa recebe o nome de uma rua ou de um local de São Paulo. O texto vai
para o Nominatim (OpenStreetMap), limitado ao retângulo da cidade. Esse retângulo pega
pedaços de Guarulhos e Osasco, então o painel pede cinco resultados e usa o primeiro que fica
no município de São Paulo. Ele vira o centro de um círculo de 1,5 km. Com a busca ligada:

- o mapa e o total "Eventos no mapa" mostram só os eventos dentro do círculo, respeitando
  também o filtro de status;
- uma lista mostra esses eventos do mais perto para o mais longe, com o nome da câmera que
  detectou cada um, e um clique seleciona o evento;
- a lista é refeita quando chega evento novo pelo tempo real;
- o × ou a tecla Esc desligam a busca.

A lista também diz se o local tem cobertura, usando as câmeras de `/deteccao/cameras`:

| Situação | Mensagem |
|---|---|
| Tem evento no círculo | Os eventos e quantas câmeras monitoradas ficam na área |
| Tem câmera, mas nenhum evento | "Nenhum evento nas câmeras monitoradas", com o nome e a distância de cada câmera |
| Nenhuma câmera no círculo | "Local sem cobertura": o sistema não tem como detectar eventos ali |

A mensagem fala em câmeras monitoradas pelo MotSP, e não em câmeras da CET, porque a CET
tem muito mais câmeras do que as 10 do catálogo. As coordenadas das câmeras são aproximadas
(nível de quarteirão, ver [Detecção](deteccao.md)), o que não muda nada num raio de 1,5 km.

O Nominatim aceita no máximo uma consulta por segundo e não permite autocompletar, por isso
a busca só roda ao apertar Enter ou Buscar, espera 1,1 s entre consultas e guarda as
respostas já vistas. A conta de distância fica em `busca-local.ts`, que tem teste próprio.

Limites: o Nominatim devolve um ponto só. Numa avenida longa esse ponto é o meio de um
trecho, então a busca com número ("Av. Paulista, 1000") é mais precisa. A busca olha os
eventos que o painel já carregou (até 200).

### Design tokens (CSS)

Marca:

| Token | Valor |
|---|---|
| `--gx` | `#FF5500` |
| `--gx-light` | `#FF8A00` |
| `--gx-dim` | `rgba(255,138,0,0.10)` |

Fundos (sólidos, sem transparência):

| Token | Valor | Uso |
|---|---|---|
| `--bg-base` | `#0C0C0C` | fundo |
| `--bg-panel` | `#111111` | painéis |
| `--bg-raised` | `#161616` | elevado |
| `--bg-card` | `#1A1A1A` | cartões |
| `--bg-input` | `#0F0F0F` | campos |
| `--bg-hover` | `#1E1E1E` | hover |
| `--bg-active` | `#222222` | active |

Cores de estado:

| Token | Valor | Uso |
|---|---|---|
| `--ok` | `#2EAA5A` | sucesso, ativo |
| `--warn` | `#E6A817` | atenção, médio |
| `--danger` | `#DC3545` | erro, crítico |
| `--info` | `#4A90D9` | informação |

### Acessibilidade e responsividade

- `prefers-reduced-motion: reduce` desliga todas as animações
- `:focus-visible` com contorno laranja (aparece só com o teclado, não com o clique)
- Link "Pular para o painel de eventos", `aria-label` nos botões e seções, e `aria-live`
  nas partes que se atualizam sozinhas
- Tamanhos de tela: 1200px (o painel direito vira gaveta), 980px (barra lateral escondida
  e mapa na tela toda), 680px (layout de celular) e 480px (totais em uma coluna)
- Testado de 320×568 até 1920×1080 e com zoom de 80% a 150%
- Mensagens para quando não há nada: nenhum evento selecionado, evento sem confiança, sem
  evidência, API fora do ar e WebSocket desconectado
