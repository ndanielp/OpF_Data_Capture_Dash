# Quickstart: Filtro de Grupos de Instituições

## Rodar localmente

```powershell
cd dashboard
uvicorn server:app --reload --port 8000
```

## Validar a metadata de grupo

```powershell
curl http://localhost:8000/api/of/institution-groups
```

Confirmar: 4 grupos presentes, contagens batendo com `institution-groups-draft.md`
(6 Incumbentes, 7 Neo Banks, 16 ITPs, 34 Outros — sobre as instituições realmente
presentes na base local).

## Validar o filtro nos endpoints existentes

```powershell
# Sem filtro de grupo — baseline
curl "http://localhost:8000/api/consents?start=2026-01-01&end=2026-09-01"

# Só Incumbentes
curl "http://localhost:8000/api/consents?start=2026-01-01&end=2026-09-01&groups=incumbentes"

# Incumbentes + Neo Banks (união)
curl "http://localhost:8000/api/consents?start=2026-01-01&end=2026-09-01&groups=incumbentes,neo_banks"

# Todos os 4 grupos == baseline sem filtro (SC-003 da spec)
curl "http://localhost:8000/api/consents?start=2026-01-01&end=2026-09-01&groups=incumbentes,neo_banks,itps,outros"
```

## Validar a matriz (2 eixos)

```powershell
curl "http://localhost:8000/api/active-consents/matrix?groups=incumbentes"
```

Confirmar: tanto as linhas (receptores) quanto as colunas (transmissores) retornadas
pertencem ao grupo Incumbentes — não apenas um dos dois eixos.

## Validar no navegador (Principle II — checagem manual obrigatória)

1. Abrir `http://localhost:8000/` (Ecossistema).
2. Selecionar o grupo "Neo Banks" no novo filtro da sidebar.
3. Confirmar que matriz, gráficos e rankings recalculam para mostrar só instituições
   desse grupo.
4. Trocar para a aba "Perfil Receptores" — confirmar que o filtro de grupo persiste
   (lido de `sessionStorage['opf:filters'].groups`).
5. Trocar para "Ativos" — mesma verificação, incluindo a matriz receptor×transmissor.
6. Limpar o filtro de grupo — confirmar que os dados voltam a mostrar todas as
   instituições (comportamento idêntico ao estado antes da feature).
