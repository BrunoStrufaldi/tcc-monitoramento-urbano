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
