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
    assert response.json() == {
        "demandaEstimada": 1,
        "ajusteSugerido": -299,
        "riscoDesperdicio": "ALTO",
        "confianca": "BAIXA",
        "metodo": "baseline-estatistico-v1",
        "evidencias": [
            "Foram autorizados 1 consumos de 300 refeicoes planejadas.",
            "A sobra estimada informada pela API Java foi de 299 refeicoes.",
            "Historico insuficiente; previsao baseada no consumo atual.",
            "Houve 3 tentativas bloqueadas no periodo.",
        ],
    }


def test_health_check():
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "UP"}
