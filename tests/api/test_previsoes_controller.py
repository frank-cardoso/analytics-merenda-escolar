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
            "sobraDePlanejamento": 299,
            "historico": [],
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "demandaEstimada": 1,
        "mediaHistorica": None,
        "pisoRealizado": 1,
        "origemEstimativa": "REALIZADO_SEM_HISTORICO",
        "diferencaPrevisaoPlanejamento": -299,
        "riscoDesperdicio": "NAO_AVALIAVEL",
        "desperdicioMotivo": (
            "Nao ha medicao de sobra nao distribuida nem de resto no prato. A diferenca entre "
            "planejamento e autorizacoes e sobra de planejamento, nao desperdicio de alimento."
        ),
        "confianca": "BAIXA",
        "metodo": "baseline-estatistico-v2",
        "evidencias": [
            "Foram autorizados 1 consumos de 300 refeicoes planejadas.",
            "A sobra de planejamento informada pela API Java foi de 299 refeicoes; "
            "e diferenca de planejamento, nao desperdicio medido.",
            "Historico insuficiente; a estimativa e o proprio realizado do dia.",
            "Houve 3 tentativas bloqueadas no periodo.",
        ],
    }


def test_health_check():
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "UP"}
