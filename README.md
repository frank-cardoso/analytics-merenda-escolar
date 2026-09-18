# Analytics — Controle de Merenda Escolar

Servico analitico em Python/FastAPI para previsao de demanda e risco de desperdicio do Controle de Merenda Escolar.

## Responsabilidade

Este servico recebe somente dados agregados da API Java e devolve uma previsao estruturada. Ele nao participa da fila, nao valida consumo e nao armazena dados pessoais.

## Stack

- Python 3.12+
- FastAPI
- Pydantic
- Uvicorn
- pytest
- httpx
- ruff

`pandas` e `scikit-learn` ficam como evolucao planejada para quando houver historico suficiente.

## Execucao local

**Windows (PowerShell):**

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

**Linux/macOS:**

```bash
python3 -m venv .venv
./.venv/bin/python -m pip install -e ".[dev]"
./.venv/bin/python -m uvicorn app.main:app --reload --port 8000
```

API local:

```text
http://localhost:8000
```

Swagger:

```text
http://localhost:8000/docs
```

Health check:

```http
GET /health
```

## Endpoint inicial

```http
POST /api/v1/previsoes-consumo
Content-Type: application/json
```

Request:

```json
{
  "dataReferencia": "2026-08-26",
  "turno": "NOITE",
  "cardapio": "Arroz, feijao, frango e salada",
  "quantidadePlanejada": 300,
  "consumosAutorizados": 1,
  "tentativasBloqueadas": 3,
  "taxaConsumoPlanejado": 0.33,
  "sobraEstimada": 299,
  "historico": []
}
```

Response:

```json
{
  "demandaEstimada": 1,
  "ajusteSugerido": -299,
  "riscoDesperdicio": "ALTO",
  "confianca": "BAIXA",
  "metodo": "baseline-estatistico-v1",
  "evidencias": [
    "Foram autorizados 1 consumos de 300 refeicoes planejadas.",
    "A sobra estimada informada pela API Java foi de 299 refeicoes.",
    "Historico insuficiente; previsao baseada no consumo atual.",
    "Houve 3 tentativas bloqueadas no periodo."
  ]
}
```

## Verificacao

### Indicadores logísticos

`POST /api/v1/indicadores-logisticos` recebe dados já agregados do Java. Os schemas completos
estão no Swagger (`/docs`) e em `app/domain/indicadores_logisticos.py`.

Entrada: `dataReferencia`, `inicioHistorico`, `turno`, `quantidadePlanejada`,
`consumosRegistrados`, `alunosUnicos`, `metaPercentual`, `turmas` e `itens`.
Saída versionada (`schemaVersion=2`): `execucaoPlanejamento`, `atendimentos`,
`topComidas`, `porTurma`, `ingredientes`, `rotacaoCardapio` e `avisos`.

- Meta: comparação antes do arredondamento; denominador zero gera percentual nulo.
- Repetições: consumos menos alunos únicos do mesmo dia/turno.
- Ranking: execuções registradas / planejamentos, mínimo 5 registros por item, top 10,
  desempate por tamanho da amostra e nome. Não é ranking de aceitação ou refeições completas.
- Quantidade servida zero conta como registro; ausência de registro não comprova rejeição.
- Sem presença elegível, adesão por turma não é calculada.
- Sem receitas/ingredientes e séries comparáveis, não se recomenda ciclo de cardápio.
- Nenhuma persistência ou chamada ao Gemini é feita pelo Python.

Os dados chegam agregados; esta primeira versão usa Python padrão/Pydantic, sem adicionar
Pandas apenas para calcular razões e ordenar contagens. Pandas continua como opção para
futuros cálculos sobre séries e composições.

### Comandos

**Windows (PowerShell):**

```powershell
.\.venv\Scripts\python.exe -m pytest -v
.\.venv\Scripts\python.exe -m ruff check .
```

**Linux/macOS:**

```bash
./.venv/bin/python -m pytest -v
./.venv/bin/python -m ruff check .
```
