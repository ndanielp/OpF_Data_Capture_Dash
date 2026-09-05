# Classificação de Instituições por Grupo

**Status**: Confirmado linha a linha (todas as 63 instituições) em 2026-09-05.

Este documento lista todas as instituições (receptores + transmissores) presentes na
base `consents.db` na data de criação e define o grupo de cada uma, para alimentar o
filtro da spec [009-filtro-grupos-instituicoes](./spec.md).

## Incumbentes (6)

| Instituição |
|---|
| Bradesco |
| Itaú Unibanco |
| Santander Brasil |
| Caixa Econômica Federal |
| Banco do Brasil |
| Banco BTG Pactual |

## Neo Banks (7)

| Instituição |
|---|
| Nubank |
| Banco Inter |
| Banco C6 (C6 Bank) |
| Mercado Pago |
| PagSeguro |
| PicPay |
| RecargaPay |

## ITPs — Iniciadores de Transação de Pagamento (16)

| Instituição |
|---|
| Belvo IP |
| Klavi Instituição de Pagamento e Gestão de Dados |
| Pluggy Brasil Instituição de Pagamento |
| Cumbuca Instituição de Pagamento |
| Delend Instituição de Pagamento |
| Finnet S/A - Tecnologia e Instituição de Pagamento |
| Lina Instituição de Pagamento |
| Google Pay Brasil Instituição de Pagamento |
| Iniciador |
| Celcoin |
| CloudWalk |
| Okto |
| PagueVeloz |
| UP.p |
| Midway |
| Crystal BMC |

## Outros/Não classificado (34)

| Instituição |
|---|
| Banrisul |
| BRB - Banco de Brasília |
| Citibank |
| BNDES |
| Banco Safra |
| Sicoob |
| Sicredi |
| Unicred do Brasil |
| Banco BMG |
| Banco Bocom BBM |
| Banco do Nordeste |
| Banco Mercantil do Brasil |
| Banco Votorantim (BV) |
| Banco Digio |
| Banco Original |
| Banco PAN |
| Banco Sofisa |
| Banco XP |
| Asaas Gestão Financeira |
| Banco CSF S/A |
| Banco Paulista |
| Geru |
| QI |
| ASA Sociedade de Crédito, Financiamento e Investimento |
| Banco de La Nacion Argentina |
| Crefisa |
| Realize Sociedade de Crédito, Financiamento e Investimento |
| Shopee (ShopeePay) |
| Banco Master S/A |
| BPP |
| Neon Pagamentos |
| 99Pay Instituição de Pagamento |
| Stone |
| Cielo |

## Observações

- 63 instituições no total (união de receptores e transmissores distintos na base em
  2026-09-05): 6 Incumbentes, 7 Neo Banks, 16 ITPs, 34 Outros/Não classificado.
- "Incumbentes" ficou restrito ao núcleo dos grandes bancos de varejo tradicionais
  (os "5 grandes" + BTG Pactual) — bancos públicos regionais (Banrisul, BRB, Banco do
  Nordeste), cooperativas (Sicoob, Sicredi, Unicred), banco de fomento (BNDES) e bancos
  estrangeiros (Citibank, Banco de La Nacion Argentina) foram deliberadamente
  classificados como "Outros" nesta rodada de revisão.
- "Neo Banks" inclui tanto bancos digitais nativos (Nubank, Inter, C6) quanto grandes
  carteiras/fintechs de pagamento de marca consolidada (Mercado Pago, PagSeguro,
  PicPay, RecargaPay) — Stone, Cielo e 99Pay ficaram fora desse grupo (Outros).
- "ITPs" ficou reservado a Instituições de Pagamento de porte menor/especializadas em
  agregação e iniciação (Belvo, Klavi, Pluggy, Cumbuca, Delend, Finnet, Lina, Google
  Pay, Iniciador, Celcoin, CloudWalk, Okto, PagueVeloz, UP.p, Midway, Crystal BMC).

## Próximos passos

1. Este mapeamento é convertido em constante versionada (ex.:
   `dashboard/services/constants.py::INSTITUTION_GROUPS`), no mesmo padrão de
   `BRAND_COLORS` (match por substring do nome, case-insensitive).
2. Instituições que não constarem no mapeamento no momento em que passarem a existir na
   coleta caem automaticamente em "Outros/Não classificado" (comportamento definido em
   FR-002 da spec).
