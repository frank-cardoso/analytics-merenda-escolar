# Analytics Python Inicial Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Criar o servico Python/FastAPI inicial para prever demanda e risco de desperdicio a partir de dados agregados da API Java.

**Architecture:** O servico sera independente, stateless e expora um endpoint HTTP/JSON. A regra inicial ficara em um service puro e testavel; FastAPI sera apenas a camada de transporte.

**Tech Stack:** Python 3.12+, FastAPI, Pydantic, Uvicorn, pytest, httpx, ruff.

**Spec:** Conversa de arquitetura aprovada em 2026-08-27: Java continua como core transacional/orquestrador; Python entra apenas para analytics batch com dados agregados.

## Global Constraints

- A fila nunca depende do servico Python.
- O servico Python recebe somente dados agregados.
- O primeiro algoritmo deve ser baseline explicavel, sem pandas/scikit-learn no runtime inicial.
- O contrato HTTP deve ser estavel para futura integracao pelo backend Java.
- Nao persistir dados no servico Python nesta fase.

---

### Task 1: Modelo Analitico Baseline

**Files:**
- Create: `app/domain/previsao_consumo.py`
- Test: `tests/domain/test_previsao_consumo.py`

**Interfaces:**
- Produces: `calcular_previsao(request: PrevisaoConsumoRequest) -> PrevisaoConsumoResponse`

- [ ] **Step 1: Write failing tests**

```python
from app.domain.previsao_consumo import (
    HistoricoConsumo,
    PrevisaoConsumoRequest,
    calcular_previsao,
)


def test_classifica_risco_alto_quando_consumo_fica_muito_abaixo_do_planejado():
    request = PrevisaoConsumoRequest(
        data_referencia="2026-08-26",
        turno="NOITE",
        cardapio="Arroz, feijao, frango e salada",
        quantidade_planejada=300,
        consumos_autorizados=1,
        tentativas_bloqueadas=3,
        taxa_consumo_planejado=0.33,
        sobra_estimada=299,
        historico=[],
    )

    response = calcular_previsao(request)

    assert response.demanda_estimada == 1
    assert response.ajuste_sugerido == -299
    assert response.risco_desperdicio == "ALTO"
    assert response.confianca == "BAIXA"
    assert response.metodo == "baseline-estatistico-v1"


def test_usa_media_historica_quando_historico_existe():
    request = PrevisaoConsumoRequest(
        data_referencia="2026-08-26",
        turno="NOITE",
        cardapio="Arroz, feijao, frango e salada",
        quantidade_planejada=300,
        consumos_autorizados=1,
        tentativas_bloqueadas=0,
        taxa_consumo_planejado=0.33,
        sobra_estimada=299,
        historico=[
            HistoricoConsumo(data_referencia="2026-08-23", consumos_autorizados=80),
            HistoricoConsumo(data_referencia="2026-08-24", consumos_autorizados=100),
            HistoricoConsumo(data_referencia="2026-08-25", consumos_autorizados=90),
        ],
    )

    response = calcular_previsao(request)

    assert response.demanda_estimada == 90
    assert response.ajuste_sugerido == -210
    assert response.confianca == "MEDIA"
```

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/domain/test_previsao_consumo.py -v`
Expected: FAIL because `app.domain.previsao_consumo` does not exist.

- [ ] **Step 3: Implement minimal domain model**

Create Pydantic request/response models and a deterministic function that uses current consumption when no history exists, or rounded historical average when history exists.

- [ ] **Step 4: Run tests to verify pass**

Run: `python -m pytest tests/domain/test_previsao_consumo.py -v`
Expected: PASS.

### Task 2: FastAPI Endpoint

**Files:**
- Create: `app/main.py`
- Create: `app/api/previsoes_controller.py`
- Test: `tests/api/test_previsoes_controller.py`

**Interfaces:**
- Consumes: `calcular_previsao(request: PrevisaoConsumoRequest) -> PrevisaoConsumoResponse`
- Produces: `POST /api/v1/previsoes-consumo`

- [ ] **Step 1: Write failing API test**

```python
from fastapi.testclient import TestClient

from app.main import app


def test_cria_previsao_de_consumo():
    client = TestClient(app)

    response = client.post(
        "/api/v1/previsoes-consumo",
        json={
            "dataReferencia": "2026-08-26",
            "turno": "NOITE",
            "cardapio": "Arroz, feijao, frango e salada",
            "quantidadePlanejada": 300,
            "consumosAutorizados": 1,
            "tentativasBloqueadas": 3,
            "taxaConsumoPlanejado": 0.33,
            "sobraEstimada": 299,
            "historico": [],
        },
    )

    assert response.status_code == 200
    assert response.json()["riscoDesperdicio"] == "ALTO"
```

- [ ] **Step 2: Run test to verify failure**

Run: `python -m pytest tests/api/test_previsoes_controller.py -v`
Expected: FAIL because API module does not exist.

- [ ] **Step 3: Implement FastAPI route**

Expose a POST route that receives camelCase JSON, maps to Pydantic models, calls the domain function, and returns camelCase JSON.

- [ ] **Step 4: Run test to verify pass**

Run: `python -m pytest tests/api/test_previsoes_controller.py -v`
Expected: PASS.

### Task 3: Repo Setup And Docs

**Files:**
- Create: `.gitignore`
- Create: `pyproject.toml`
- Create: `context.md`
- Create: `AGENTS.md`
- Create: `docs/agents/issue-tracker.md`
- Create: `docs/agents/triage-labels.md`
- Create: `docs/agents/domain.md`
- Modify: `README.md`

**Interfaces:**
- Produces: commands `python -m pytest`, `python -m uvicorn app.main:app --reload --port 8000`, `python -m ruff check .`

- [ ] **Step 1: Add project metadata**

Create `pyproject.toml` with FastAPI, Uvicorn, pytest, httpx and ruff.

- [ ] **Step 2: Add docs**

Document stack, endpoint, local execution, privacy constraints, and Java integration direction.

- [ ] **Step 3: Run verification**

Run: `python -m pytest -v`
Run: `python -m ruff check .`
Expected: both pass.

- [ ] **Step 4: Commit**

```bash
git add .
git commit -m "feat(analytics): criar servico inicial de previsao"
git push origin main
```
