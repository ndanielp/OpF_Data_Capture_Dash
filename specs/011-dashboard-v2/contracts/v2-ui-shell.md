# Contrato — Interface do Dashboard 2.0

Base: o design aprovado no canvas (página "Versão final — para aprovação"). Este contrato é o que a emenda do Princípio VI incorpora como "Shell v2".

## Rotas

| Rota | Página | Entrega |
|---|---|---|
| `/v2` | Quem lidera? | P1 |
| `/v2/mudancas` | O que mudou? | P2 |
| `/v2/instituicao?uuid=…` | Como opera uma instituição? | P3 |
| `/v2/evolucao` | Como evolui? | P3 |
| `/`, `/profile`, `/active-consents` | legado, inalterado (+ link "Dashboard 2.0" no titlebar) | — |

Abas ainda não entregues abrem com um aviso e um link para a página equivalente do legado (Evolução → `/`; Instituição → `/profile`; O que mudou? → card do `/`).

## Esqueleto de página

```text
<body data-theme="light|dark">
  <header class="v2-header">   marca · abas (4, ordem fixa, aria-current na ativa) · "Dados até … · atualizado em …" · tema · "Painel atual (legado)"
  <main class="v2-main">       largura máx. 1280 px, padding 24 px
    <section class="v2-filterbar">   só os controles da aba; linha 2 opcional (ex.: Sempre mostrar / Excluir / Ordenar)
    <h1> + subtítulo com semana, base e regra da métrica
    blocos (.v2-card)        cada um com título, subtítulo, botões "Copiar como imagem" e "Baixar CSV", rodapé com regra + fonte
```

## Controles por aba

| Aba | Controles |
|---|---|
| Quem lidera? | Métrica · (API: Escala, Status) · Período do crescimento · Grupos · Sempre mostrar · Excluir do ranking · Ordenar por · Exportar dados |
| Como evolui? | Métrica · (Ativos: Evolução por) · Período · Granularidade · Grupos · Instituições no gráfico · Valores/Participação |
| O que mudou? | Mês (barra + seletor) · Tipo · Sinal · Instituição · Grupos |
| Instituição | Instituição (busca) · Comparar com · Período |

## Estado e persistência

- Compartilhado entre abas: `sessionStorage['opf:v2:filters']` (período, grupos, métrica, instituições, instituição, comparar). Cada página escreve só os campos que usa e preserva os demais.
- Preferências do ranking: `localStorage['opf:v2:ranking']`; primeiro acesso fixa o Bradesco.
- Tema: `localStorage['opf:v2:theme']`, padrão `light`, aplicado antes da primeira pintura.
- Armazenamento indisponível: usa os padrões e segue funcionando (leituras e escritas protegidas).
- Qualquer mudança de filtro recarrega a aba na hora.

## Tokens visuais (tema claro)

| Token | Valor |
|---|---|
| fundo | `#F4F5F8` |
| superfície | `#FFFFFF` |
| borda | `#E3E6EC` / divisória `#ECEEF2` |
| texto | `#14171F` |
| texto secundário (≥ 4,5:1) | `#5A6275` |
| ação/link | `#1F4FD1` |
| queda | texto `#9A3412`, fundo `#FDECE4` |
| alta / acelerando | `#1A3F9E` |
| oscilação | texto `#7A4F00`, fundo `#FFF3DB` |
| novo entrante | texto `#0B6B57`, fundo `#E2F3EE` |
| destaque de fixada | `#FFF4E3` |

Cores de grupo e de grupo de API vêm sempre de `/api/v2/meta` (nunca fixas no HTML/JS). Fonte IBM Plex Sans com fallback do sistema; números tabulares. Alvos de toque ≥ 44 px; textos ≥ 12 px.

## Exportação

- **CSV**: mesmas linhas e colunas do bloco (com fixadas, sem excluídas), cabeçalho em português, separador `;`, decimal com vírgula, UTF-8 com BOM (abre direto no Excel).
- **Imagem**: PNG 1600×900 com título (incluindo filtro ativo), subtítulo (métrica, semana), conteúdo do bloco e rodapé "Fonte: dashboard Open Finance Brasil · dados até DD/MM/AAAA". Nome do arquivo: `opf-<aba>-<bloco>-<AAAA-MM-DD>.png`.

## Formatação

- Números: `22,04 mi`, `409,0 mil`, `4,51 bi`; inteiros abaixo de 10 mil com separador de milhar.
- Participação: 1 casa decimal (`15,1%`).
- Crescimento: `+49%`, `×5,0`, `estreou out/25`, `sem base`.
- Ritmo: `+22,9 mil` com `0,11%/dia` e seta ↑ ↓ →.
- Datas: `28/08/2026`; meses `ago/26`.
