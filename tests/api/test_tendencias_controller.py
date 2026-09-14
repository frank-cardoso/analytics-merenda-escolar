from fastapi.testclient import TestClient

from app.main import app


def test_cria_tendencias_de_itens():
    client = TestClient(app)

    response = client.post(
        "/api/v1/tendencias-item",
        json={
            "itens": [
                {"item": "Salada de alface", "taxasExecucao": [80.0, 82.0, 40.0, 38.0]},
                {"item": "Arroz branco", "taxasExecucao": [85.0, 84.0]},
            ]
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "tendencias": [
            {"item": "Salada de alface", "tendencia": "QUEDA"},
            {"item": "Arroz branco", "tendencia": "ESTAVEL"},
        ]
    }
